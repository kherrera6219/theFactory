# Phase 23 — DEPABS Execution: Absorption with Modified Artifacts

**Status:** Planned
**Last updated:** 2026-05-18
**Depends on:** Phase 22 (RQCA sandbox), Phase 14 (inventory/classification),
Phase 12 (equivalence harness)

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
- source splicing (remove the import, inline the replacement)
- equivalence verification of the modified artifact via the Phase 12 harness
- runtime verification via the Phase 22 RQCA sandbox
- before/after SBOM delta as a deliverable artifact

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
        item for item in (absorption_report.get("analysis") or [])
        if item.get("action") == "Absorb"
    ][:5]  # cap: 5 absorptions per mission in Phase 23

    if not candidates:
        return {
            "status": "nothing_to_absorb",
            "modified_source": source_code,
            "splices": [],
        }

    splices = []
    modified = source_code

    for dep in candidates:
        library = dep.get("library", "")
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
    original_dependencies: list[str],
    absorption_result: dict[str, Any],
    absorption_report: dict[str, Any],
) -> dict[str, Any]:
    absorbed = [s["library"] for s in absorption_result.get("splices", [])
                if s["status"] == "ok"]
    kept = [item["library"] for item in (absorption_report.get("analysis") or [])
            if item.get("action") in {"Keep", "Wrap", "Pin", "Block"}]
    removed = absorbed
    remaining = [d for d in original_dependencies if d not in removed]
    return {
        "schema_version": "sbom_delta.v1",
        "original_dependency_count": len(original_dependencies),
        "removed": removed,
        "remaining": remaining,
        "kept_with_justification": kept,
        "reduction_percent": round(
            len(removed) / max(len(original_dependencies), 1) * 100, 1
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
        ).get("detected_libraries", []),
        absorption_result=execution_result,
        absorption_report=metadata.get("dependency_absorption_report", {}),
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

- [ ] `DEPABS_EXECUTION_ENABLED=false`: advisory classification only, unchanged.
- [ ] Python source with `import click` produces splice with `click` removed and
      replacement code inlined.
- [ ] Python source with `import cryptography` is NOT absorbed (safety block list).
- [ ] Splice that would produce a syntax error is skipped, not applied.
- [ ] `MISSION_DEPABS_EXECUTED` event in chain trace.
- [ ] `sbom_delta.reduction_percent > 0` for a mission with at least one absorbed dep.
- [ ] Modified artifact passes RQCA sandbox execution (when sandbox available).
- [ ] SBOM delta panel renders in Mission Control.
- [ ] `python -m pytest -q` passes. `ruff check` passes.
