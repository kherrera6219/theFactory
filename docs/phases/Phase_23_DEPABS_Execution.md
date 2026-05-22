# Phase 23 — DEPABS Execution: Absorption with Modified Artifacts

**Status:** Core execution slice implemented locally; live verification remains gated
**Last updated:** 2026-05-20
**Depends on:** Phase 14 dependency inventory/classification/advisory
absorption planning, Phase 12 equivalence harness, Phase 13
security/compliance report, and Phase 22 runtime-QC evidence when sandbox
execution is available. Phase 22 is a verification dependency for promotion,
not a hard prerequisite for generating a modified artifact behind a disabled
feature flag.

---

## Problem

Phase 14 produces dependency inventory, classification, and advisory absorption
plans. It stops there. No mission ever delivers an artifact with dependencies
actually removed. The absorption doctrine (`docs/DEPENDENCY_ABSORPTION_DOCTRINE.md`)
states "the default action is ABSORB" — but AGENT-39-DEPABS currently only
classifies and advises, never absorbs.

This phase closes that gap for `REDUCE_DEPENDENCIES` missions on Python and
JavaScript targets. It adds:
- replacement code generation for Absorb-classified dependencies
- source splicing (remove the import, inline or local-module the replacement)
- equivalence verification of the modified artifact via the Phase 12 harness
- runtime verification via the Phase 22 RQCA sandbox
- before/after SBOM delta as a deliverable artifact

---

## Review Update — 2026-05-20

Validated against the current repo:

- Phase 14 is implemented as advisory planning only in
  `dependency_absorption.py`.
- The current absorption report uses `planned_replacements`, not the older
  sample shape `analysis` with `action == "Absorb"`.
- A replacement is only `ready_for_planning` when equivalence and
  security/compliance evidence already pass; otherwise it is `gated`.
- Mission Flow v2 already records `MISSION_DEPENDENCY_ABSORPTION_REPORTED`,
  but no modified artifact, `depabs_execution`, or `sbom_delta` exists yet.
- Mission Control already renders dependency inventory/classification/
  absorption planning evidence, but no SBOM delta panel or DEPABS execution
  panel exists.

Plan corrections:

- Phase 23 must consume `dependency_absorption_report.planned_replacements`
  where `status == "ready_for_planning"`.
- Do not execute absorption for safety-blocked, survival-justified, or gated
  dependencies.
- Keep `DEPABS_EXECUTION_ENABLED=false` by default and treat all execution as
  non-critical path until equivalence, security/compliance, and runtime-QC
  evidence are attached to the modified artifact.
- Python should be the first executable splice target. JavaScript/TypeScript
  should follow only after import/require/ESM handling has explicit tests.
- Operator approval remains required for Production/Regulated depth modes as
  described in `docs/DEPENDENCY_ABSORPTION_DOCTRINE.md`.

---

## Implementation Update — 2026-05-20

Completed in this pass:

- Added `execute_absorption()` using the current
  `dependency_absorption_report.planned_replacements` shape.
- Limited execution to `status="ready_for_planning"` replacements and skipped
  gated, safety-blocked, and survival-justified dependencies.
- Added conservative deterministic Python splicing for small utility
  replacements, with `ast.parse()` syntax validation before accepting a splice.
- Added `build_sbom_delta()` using `dependency_inventory.dependencies`.
- Wired DEPABS execution into Mission Flow v2 behind
  `DEPABS_EXECUTION_ENABLED=false`.
- Added `depabs_execution` and `sbom_delta` chain-trace exposure and Mission
  Control rendering.

Still gated:

- JavaScript/TypeScript splicing remains disabled until import/require/ESM
  handling has explicit tests.
- Modified artifacts still require the normal equivalence/security/runtime-QC
  evidence path before promotion claims.

---

## Change 1 — Absorption execution in `dependency_absorption.py`

Extend with an execution tier beyond advisory:

```python
async def execute_absorption(
    *,
    mission_id: str,
    source_code: str,
    language: str,
    absorption_report: dict[str, Any],
    settings: Any,
) -> dict[str, Any]:
    """
    Execute absorption: for each Absorb-classified dependency, generate
    first-party replacement code and splice it into the source.
    Returns modified_source and splice_manifest.
    Only runs for python and javascript/typescript.
    """
    if language.lower() not in {"python", "javascript", "typescript"}:
        return {
            "status": "skipped",
            "reason": f"Absorption execution not yet supported for {language}.",
            "modified_source": source_code,
            "splices": [],
        }

    candidates = [
        item for item in (absorption_report.get("planned_replacements") or [])
        if item.get("status") == "ready_for_planning"
    ][:3]  # cap: 3 absorptions per mission in Phase 23

    if not candidates:
        return {
            "status": "nothing_to_absorb",
            "modified_source": source_code,
            "splices": [],
        }

    splices = []
    modified = source_code

    for dep in candidates:
        library = dep.get("name", "")
        used_symbols = _detect_used_symbols(modified, library, language)
        if not used_symbols:
            continue

        replacement = await _generate_replacement(
            library=library,
            used_symbols=used_symbols,
            language=language,
            mission_id=mission_id,
        )
        if not replacement.get("replacement_code"):
            continue

        modified, splice_result = _splice_replacement(
            source=modified,
            library=library,
            language=language,
            replacement=replacement,
        )
        splices.append({
            "library": library,
            "symbols_replaced": used_symbols,
            "filename": replacement.get("filename"),
            "status": splice_result,
        })

    return {
        "status": "executed" if splices else "no_splices_applied",
        "modified_source": modified,
        "splices": splices,
        "absorption_count": len([s for s in splices if s["status"] == "ok"]),
    }
```

`_splice_replacement()` removes the original import statement and appends
the replacement code as an inline module at the end of the source file.
It is intentionally conservative: if the splice would produce a syntax
error (detectable via `ast.parse` for Python), it is skipped and logged.

### 1b. SBOM delta generation

```python
def build_sbom_delta(
    *,
    original_dependencies: list[dict[str, Any]],
    absorption_result: dict[str, Any],
    absorption_report: dict[str, Any],
    survival_justifications: list[dict[str, Any]],
) -> dict[str, Any]:
    absorbed = [s["library"] for s in absorption_result.get("splices", [])
                if s["status"] == "ok"]
    original_names = [
        item.get("name") for item in original_dependencies if isinstance(item, dict)
    ]
    kept = [
        item.get("dependency_name") or item.get("name")
        for item in survival_justifications
        if isinstance(item, dict)
    ]
    removed = absorbed
    remaining = [name for name in original_names if name not in removed]
    return {
        "schema_version": "sbom_delta.v1",
        "original_dependency_count": len(original_names),
        "removed": removed,
        "remaining": remaining,
        "kept_with_justification": [item for item in kept if item],
        "reduction_percent": round(
            len(removed) / max(len(original_names), 1) * 100, 1
        ),
    }
```

---

## Change 2 — Wire into REDUCE_DEPENDENCIES mission flow

In `mission_flow_v2.py`, in `_prepare_specialist_plan()`, after the existing
dependency classification runs:

```python
if (
    mission_type == "REDUCE_DEPENDENCIES"
    and metadata.get("source_code")
    and depabs_execution_enabled
):
    execution_result = await execute_absorption(
        mission_id=mission_id,
        source_code=metadata["source_code"],
        language=mission.requested_target_language or "python",
        absorption_report=metadata.get("dependency_absorption_report", {}),
        settings=settings,
    )
    metadata["depabs_execution"] = execution_result

    if execution_result.get("absorption_count", 0) > 0:
        # Replace generated_output with the absorption-modified source
        modified = execution_result["modified_source"]
        metadata["generated_output"] = {
            "generated_code": modified,
            "filename": f"absorbed_{mission.requested_target_language or 'output'}.py",
            "language": mission.requested_target_language or "python",
            "description": (
                f"Source with {execution_result['absorption_count']} "
                "dependencies absorbed into first-party code."
            ),
            "source": "depabs_execution",
        }

    sbom_delta = build_sbom_delta(
        original_dependencies=metadata.get(
            "dependency_inventory", {}
        ).get("dependencies", []),
        absorption_result=execution_result,
        absorption_report=metadata.get("dependency_absorption_report", {}),
        survival_justifications=metadata.get("dependency_survival_justifications", []),
    )
    metadata["sbom_delta"] = sbom_delta
    append_chain_event(
        metadata,
        event_type="MISSION_DEPABS_EXECUTED",
        agent_id="AGENT-39-DEPABS",
        details={
            "absorption_count": execution_result.get("absorption_count", 0),
            "status": execution_result.get("status"),
            "reduction_percent": sbom_delta.get("reduction_percent"),
        },
    )
```

After execution, the modified source goes through the normal equivalence and
RQCA pipeline — the Phase 12 equivalence harness runs against the modified
artifact, and Phase 22 RQCA sandbox executes it to verify runtime behavior
is preserved.

---

## Change 3 — Mission Control SBOM delta panel

In Mission Detail, when `metadata.sbom_delta` is present:

```tsx
{sbomDelta && (
  <SBOMDeltaPanel
    originalCount={sbomDelta.original_dependency_count}
    removed={sbomDelta.removed}
    remaining={sbomDelta.remaining}
    reductionPercent={sbomDelta.reduction_percent}
  />
)}
```

Show: original count, removed (absorbed) list, remaining list,
reduction percentage as a prominent metric.

---

## Settings

```bash
DEPABS_EXECUTION_ENABLED=false   # Execute absorption (generate + splice)
# Classification from Phase 14 always runs when source code is present
```

---

## Validation

- [x] `DEPABS_EXECUTION_ENABLED=false`: advisory classification only, unchanged.
- [x] Only `planned_replacements` with `status="ready_for_planning"` are
      eligible for execution.
- [x] Gated replacements and survival-justified dependencies are never spliced.
- [x] Python source with a supported small utility produces a splice with the
      dependency import removed and replacement code inlined.
- [ ] Python source with `import cryptography` is NOT absorbed (safety block list).
- [x] Splice that would produce a syntax error is skipped, not applied.
- [x] `MISSION_DEPABS_EXECUTED` event in chain trace.
- [x] `sbom_delta.reduction_percent > 0` for a mission with at least one absorbed dep.
- [x] `sbom_delta.remaining` is computed from
      `dependency_inventory.dependencies`.
- [ ] Modified artifact passes RQCA sandbox execution (when sandbox available).
- [x] SBOM delta panel renders in Mission Control.
- [x] Focused pytest and ruff checks pass.
