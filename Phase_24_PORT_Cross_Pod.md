# Phase 24 — PORT Mission Cross-Pod Coordination

**Status:** Planned
**Last updated:** 2026-05-18
**Depends on:** Phase 23 (absorption execution), Phase 20 (CEO reasoning),
Phase 21 (pod manager delegation depth)

---

## Problem

`PORT` missions (convert source in language A to target language B) are
selectable in Mission Control but route to a single pod. The CEO picks one
pod manager based on the requested target language. The source language pod
is never involved. This means:

- The source language's specialist never extracts intent from the original code.
- The target language's specialist generates from the PM contract alone, not
  from a structured extraction of the source.
- No AIM (Application Intelligence Map) is produced from the source before
  generation begins.
- The equivalence report compares generated output against the contract, not
  against the original source behavior.

A PORT mission should be a two-pod sequence:
1. Source pod extracts intent → LogicNodes + AIM from original source
2. Target pod generates → new implementation from those LogicNodes in the
   target language
3. Equivalence harness compares source behavior against target output

---

## Change 1 — CEO PORT strategy: two-cluster decomposition

Phase 20 added mission-type-aware CEO prompting. Extend the PORT strategy
in `_build_ceo_delegation_prompt()` to produce a specific two-cluster
structure:

```python
"PORT": (
    "This is a PORT mission. It MUST produce exactly two logic clusters:\n"
    "  Cluster 1 (EXTRACTION): assigned to the source-language pod and specialist.\n"
    "    Domain: source_extraction. Priority: HIGH.\n"
    "    This cluster extracts intent from the original source code.\n"
    "  Cluster 2 (GENERATION): assigned to the target-language pod and specialist.\n"
    "    Domain: target_generation. Priority: MEDIUM. depends_on: [Cluster 1].\n"
    "    This cluster generates the target-language implementation.\n"
    "Identify both the source language and the target language from the prompt "
    "and mission contract. Assign each cluster to the correct pod."
),
```

The CEO delegation for PORT missions must therefore return two pod manager
assignments: `source_pod_manager_agent_id` and `target_pod_manager_agent_id`.
Extend `_normalize_ceo_delegation()` to capture both.

---

## Change 2 — Two-phase mission flow for PORT

Add a `PORT` execution path in `mission_flow_v2.py`.

### 2a. Detect PORT and set up two-phase metadata

In `_prepare_ceo_delegated()`, when `mission_type == "PORT"`:

```python
if mission_type == "PORT":
    source_language = _detect_source_language(mission.prompt, metadata)
    target_language = mission.requested_target_language or "python"
    metadata["port_source_language"] = source_language
    metadata["port_target_language"] = target_language
    metadata["port_phase"] = "extraction"
```

`_detect_source_language()` reads from the prompt, the source bundle file
extensions, or the AIM if already present.

### 2b. Extraction phase — source pod runs first

In `_prepare_specialist_assigned()`, when `port_phase == "extraction"`:

- Route to the source-language specialist (from cluster 1 assignment).
- Generate AIM from the source code using the source language.
- Run source-language extraction to produce LogicNodes from the original.
- Store as `metadata["port_source_logicnodes"]` and
  `metadata["port_source_aim"]`.
- Emit `MISSION_PORT_EXTRACTION_COMPLETE`.
- Set `metadata["port_phase"] = "generation"`.
- Re-queue the mission at `POD_ASSIGNED` to trigger the generation phase.

### 2c. Generation phase — target pod runs second

On the second pass through `_prepare_specialist_assigned()`,
when `port_phase == "generation"`:

- Route to the target-language specialist (from cluster 2 assignment).
- Pass `port_source_logicnodes` and `port_source_aim` into the code
  generation prompt as source behavior context.
- Generate target-language implementation informed by extracted source intent.
- Store as the normal `generated_output`.
- Emit `MISSION_PORT_GENERATION_COMPLETE`.

### 2d. Extend codegen prompt for PORT

In `_build_codegen_prompt()`, when `mission_context` contains
`port_source_logicnodes`:

```python
source_context = ""
port_nodes = mission_context.get("port_source_logicnodes") or []
if port_nodes:
    node_lines = "\n".join(
        f"- {n.get('domain')}.{n.get('concept')}: {n.get('intent', '')[:80]}"
        for n in port_nodes[:15]
    )
    source_context = (
        f"\nSource behavior extracted from original {source_lang} code:\n"
        f"{node_lines}\n"
        "Preserve this behavior in your {target_lang} implementation.\n"
    )
```

---

## Change 3 — PORT equivalence: source vs target

Extend `equivalence_verifier.py` for PORT missions to compare source
LogicNodes against target LogicNodes rather than contract alone:

```python
def _port_equivalence_checks(
    source_logicnodes: list[dict],
    target_logicnodes: list[dict],
) -> list[dict]:
    """
    For PORT missions: verify that every source domain.concept appears
    in the target extraction at equivalent confidence.
    """
    source_concepts = {
        f"{n.get('domain')}.{n.get('concept')}" for n in source_logicnodes
    }
    target_concepts = {
        f"{n.get('domain')}.{n.get('concept')}" for n in target_logicnodes
    }
    missing = source_concepts - target_concepts
    checks = []
    for concept in source_concepts:
        present = concept in target_concepts
        checks.append({
            "check": f"concept_preserved:{concept}",
            "status": "pass" if present else "manual_review",
            "required": False,  # semantic equivalence is advisory for PORT
        })
    return checks
```

---

## Change 4 — Mission Control PORT phase indicator

In Mission Detail, for PORT missions show a two-phase progress indicator:

```
[EXTRACTION: Python ✓] → [GENERATION: Rust ●]
```

Derived from `port_phase`, `port_source_language`, `port_target_language`,
and the presence of `port_source_logicnodes` in chain trace metadata.

---

## Settings

```bash
PORT_TWO_PHASE_ENABLED=false   # Enable two-pod PORT execution
# Single-pod fallback remains the default
```

---

## Validation

- [ ] `PORT_TWO_PHASE_ENABLED=false`: PORT missions route single-pod as before.
- [ ] Flag enabled: CEO produces two clusters for a PORT mission prompt.
- [ ] `port_source_language` detected from source bundle file extensions.
- [ ] `MISSION_PORT_EXTRACTION_COMPLETE` event in chain trace with source
      LogicNode count.
- [ ] `MISSION_PORT_GENERATION_COMPLETE` event with target `generated_output`.
- [ ] Codegen prompt for generation phase includes source LogicNode context.
- [ ] PORT equivalence checks include `concept_preserved` items.
- [ ] Mission Control renders two-phase progress indicator for PORT missions.
- [ ] `python -m pytest -q` passes. `ruff check` passes.
