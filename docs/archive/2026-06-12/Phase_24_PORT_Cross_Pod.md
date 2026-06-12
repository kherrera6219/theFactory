# Phase 24 — PORT Mission Cross-Pod Coordination

**Status:** In progress
**Last updated:** 2026-05-20
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

## Pre-implementation findings (2026-05-20)

After reading the live codebase before implementing:

- `_build_ceo_delegation_prompt()` in `llm_delegation.py` already has a PORT
  entry at line 878 — but it is weak ("Two languages are involved. Note
  source extraction..."). **Change 1 replaces this existing entry** rather
  than adding a new one.
- There is no `_normalize_ceo_delegation()` standalone function. CEO delegation
  normalization happens inline in `_prepare_ceo_delegated()` in
  `mission_flow_v2.py`. **Change 1 also patches that inline block** to
  capture `source_pod_manager_agent_id` from the PORT two-cluster response.
- `detect_required_languages()` already exists in `is_agent.py` and handles
  source bundle extension scanning. **Change 2a reuses it** for source
  language detection rather than writing a new function.
- The settings pattern is established (`DEPABS_EXECUTION_ENABLED`,
  `RQCA_AGENT_ENABLED`, etc.). `PORT_TWO_PHASE_ENABLED=false` follows the
  same pattern exactly.
- `_build_codegen_prompt()` is a standalone function in `llm_delegation.py`
  at line 1338. **Change 2d patches it directly** to inject source LogicNode
  context when `port_source_logicnodes` is present in `mission_context`.

---

## Change 1 — CEO PORT strategy: two-cluster decomposition

### 1a. Replace weak PORT strategy in `_build_ceo_delegation_prompt()`

File: `services/orchestrator/orchestrator/llm_delegation.py`

Replace the existing `"PORT"` entry in `type_strategy` dict (line ~878):

```python
# BEFORE (weak)
"PORT": (
    "Two languages are involved. Note source extraction, target generation, "
    "and any cross-pod dependency in your rationale."
),

# AFTER (mandatory two-cluster)
"PORT": (
    "This is a PORT mission. It MUST produce exactly two logic clusters:\n"
    "  Cluster 1 (EXTRACTION): domain=source_extraction, priority=HIGH.\n"
    "    Assigned to the SOURCE language pod manager and specialist.\n"
    "    Purpose: extract intent and LogicNodes from the original source.\n"
    "  Cluster 2 (GENERATION): domain=target_generation, priority=MEDIUM.\n"
    "    Assigned to the TARGET language pod manager and specialist.\n"
    "    depends_on: [Cluster 1 title].\n"
    "    Purpose: generate target-language implementation from extracted intent.\n"
    "Identify source and target language from the prompt. "
    "Assign each cluster to the CORRECT pod."
),
```

### 1b. Capture source pod from PORT clusters in `_prepare_ceo_delegated()`

File: `services/orchestrator/orchestrator/mission_flow_v2.py`

After `logic_clusters` is stored in metadata, when `mission_type == "PORT"`:
extract the source-pod cluster from the clusters list and store
`port_source_pod_manager_agent_id` and `port_source_specialist_agent_id`
in metadata for use in the two-phase flow.

---

## Change 2 — Two-phase mission flow for PORT

File: `services/orchestrator/orchestrator/mission_flow_v2.py`

### 2a. Feature flag + source language detection

Add `port_two_phase_enabled` to settings. When disabled, PORT routes
single-pod as before. When enabled:

In `_prepare_ceo_delegated()`, when `mission_type == "PORT"` and flag is on:
- Call `detect_required_languages()` (already in `is_agent.py`) to identify
  source language from source bundle file extensions.
- Store `port_source_language`, `port_target_language`, `port_phase="extraction"`
  in metadata.

### 2b. Extraction phase — source pod runs first

In `_run_specialist_phase()`, when `port_phase == "extraction"`:
- Override specialist routing to use `port_source_specialist_agent_id`.
- Run AIM generation on source code with source language.
- Run extraction to produce LogicNodes.
- Store as `port_source_logicnodes` and `port_source_aim`.
- Emit `MISSION_PORT_EXTRACTION_COMPLETE` chain event.
- Set `port_phase = "generation"` and re-queue at `POD_ASSIGNED`.

### 2c. Generation phase — target pod runs second

On second pass through `_run_specialist_phase()`,
when `port_phase == "generation"`:
- Route to target specialist normally.
- Pass `port_source_logicnodes` and `port_source_aim` into codegen context.
- Emit `MISSION_PORT_GENERATION_COMPLETE`.

### 2d. Inject source LogicNode context into codegen prompt

In `_build_codegen_prompt()` in `llm_delegation.py`:
When `mission_context` contains `port_source_logicnodes`, append a
"Source behavior extracted from original code" block to the prompt.

---

## Change 3 — PORT equivalence: concept coverage check

File: `services/orchestrator/orchestrator/equivalence_verifier.py`

Add `_port_equivalence_checks()` called when `port_source_logicnodes`
is present in metadata. Checks that every `domain.concept` from the source
extraction appears in the target extraction. All checks are `required=False`
(advisory) — semantic equivalence is not enforced for PORT.

---

## Change 4 — Mission Control PORT phase indicator

File: `apps/mission-control/app/(shell)/missions/[id]/page.tsx`

For PORT missions, render a two-phase progress indicator in the Mission
Signals panel derived from `port_phase`, `port_source_language`,
`port_target_language`, and presence of `port_source_logicnodes` in chain
trace metadata.

---

## Settings

Add to `services/orchestrator/orchestrator/settings.py`:

```python
port_two_phase_enabled=_as_bool(os.getenv("PORT_TWO_PHASE_ENABLED", "false"), False),
```

Add to `.env.example`:
```bash
PORT_TWO_PHASE_ENABLED=false   # Enable two-pod PORT execution (default: single-pod)
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
