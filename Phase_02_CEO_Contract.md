# Phase 2 - Durable Mission Contract
## Tier 1 | Estimated Duration: 3-5 days

---

## Context

Today the CEO delegation path is real but narrow. It selects routing metadata:
pod manager, specialist, and rationale. The Chat page also creates a local
feature-contract style preview, but that preview is not the durable contract that
downstream workers use.

The missing piece is a persisted mission contract: a structured, versioned
artifact that says what the mission is supposed to build, analyze, repair, port,
or transform. This contract becomes the working agreement between PM intake,
CEO routing, pod extraction, specialist generation, verification, and Mission
Control.

This phase should not try to implement the whole factory. It creates the durable
specification that Phase 3 can generate from.

---

## Validated Starting Point

- `llm_delegation.py` currently has CEO routing and specialist planning, not a
  generated build contract.
- `mission_flow_v2.py` stores CEO delegation metadata, but no formal contract.
- Chain trace exposes routing, artifacts, provenance, and events, but no durable
  mission contract.
- Mission Control mission detail has trace and artifact panels, but no contract
  panel.
- `schemas/mission_charter.v1.json` exists and should be reused or extended
  where practical instead of creating unrelated schema sprawl.

---

## Exit State

Every mission can expose a durable mission contract with:

- contract version;
- mission summary;
- mission type;
- target language or language set;
- output mode;
- required domains;
- logicnode requirements;
- acceptance criteria;
- risk notes;
- source: `llm` or `fallback`;
- model/provider route when LLM-sourced;
- creation timestamp.

The contract must be visible in:

- mission metadata;
- chain trace API;
- Mission Control mission detail;
- audit or chain events.

---

## Exact Work

### 1. Define the contract shape

Add a small versioned schema or extend the existing mission-charter schema.
Prefer one of these approaches:

- extend `schemas/mission_charter.v1.json` with a nested `mission_contract`;
- or add `schemas/mission_contract.v1.schema.json` if keeping it separate is
  cleaner.

Minimum shape:

```json
{
  "schema_version": "mission_contract.v1",
  "contract_summary": "Build a Python CSV reader.",
  "mission_type": "BUILD_NEW",
  "target_languages": ["python"],
  "output_mode": "FULL_BUILD",
  "output_format": "standalone_script",
  "required_domains": ["file_io", "csv_parsing", "data_mapping"],
  "logicnode_requirements": [
    {
      "domain": "csv_parsing",
      "concept": "read_csv_rows",
      "intent": "Read CSV rows and convert them into dictionaries",
      "priority": "HIGH"
    }
  ],
  "acceptance_criteria": [
    "Reads a CSV file with headers",
    "Returns a list of dictionaries"
  ],
  "risk_notes": [],
  "source": "llm",
  "model_provider": "openai",
  "model": "verified-model-id",
  "created_at": "2026-05-16T00:00:00Z"
}
```

### 2. Add LLM and fallback contract generation

In `services/orchestrator/orchestrator/llm_delegation.py`, add a contract
generation path after CEO routing.

Required functions:

- `_build_mission_contract_prompt(...)`
- `_normalize_mission_contract(...)`
- `_fallback_mission_contract(...)`
- `generate_mission_contract(...)`

Rules:

- The prompt must request JSON only.
- User prompt and context must be bounded and sanitized.
- Invalid priorities, output modes, and empty arrays must be normalized.
- The fallback contract must be useful enough for local/offline operation.
- The generated object must clearly report `source`.

Do not tie this to a specific model ID. Use the Phase 1 model-governance result
through the existing recommendation path.

### 3. Persist the contract in the mission flow

In `services/orchestrator/orchestrator/mission_flow_v2.py`, call contract
generation after successful CEO routing.

Store the result in mission metadata:

```python
metadata["mission_contract"] = contract
```

If existing docs or code prefer `mission_charter`, also mirror or reference it
there, but avoid two divergent source-of-truth objects.

Emit a chain event:

```text
MISSION_CONTRACT_GENERATED
```

The event should include:

- source;
- requirement count;
- acceptance criteria count;
- output format;
- model/provider when present.

Contract generation should be non-blocking for existing mission types during
initial rollout. A failure should produce fallback or continue with a clear
warning, not strand the mission.

### 4. Expose the contract through chain trace

In `services/orchestrator/orchestrator/routes/internal.py`, add the contract to
the chain trace response.

Preferred field:

```json
{
  "mission_contract": { ... }
}
```

If older docs use `refined_ir_contract`, treat that as a compatibility alias or
rename it consistently in one pass. The preferred product language is **Mission
Contract** because this artifact is broader than Refined IR.

### 5. Add frontend types and Mission Control panel

In `apps/mission-control/app/lib/types.ts`, add a typed contract model and
include it in `MissionChainTrace`.

In `apps/mission-control/app/(shell)/missions/[id]/page.tsx`, add a Mission
Contract panel showing:

- summary;
- output format;
- target language;
- source/fallback status;
- required domains;
- logicnode requirements;
- acceptance criteria;
- risk notes.

Keep the UI dense and operational. This is a mission detail surface, not a
marketing page.

### 6. Align docs

Update:

- `docs/IMPLEMENTATION_STATUS.md`
- `docs/ARCHITECTURE.md` if flow diagrams mention CEO delegation only;
- `docs/ARCHITECTURE_DATA_FLOWS.md` if chain trace/artifact flow changes;
- `HGR_Phased_Build_Plan.md` if implementation choices differ from this phase.

---

## Files Likely Changed

- `schemas/mission_contract.v1.schema.json` or `schemas/mission_charter.v1.json`
- `services/orchestrator/orchestrator/llm_delegation.py`
- `services/orchestrator/orchestrator/mission_flow_v2.py`
- `services/orchestrator/orchestrator/routes/internal.py`
- `apps/mission-control/app/lib/types.ts`
- `apps/mission-control/app/(shell)/missions/[id]/page.tsx`
- `tests/services/test_llm_delegation_unit.py`
- `tests/services/test_mission_flow_v2*.py`
- `docs/IMPLEMENTATION_STATUS.md`

---

## Tests

Add unit tests for:

- fallback contract includes required fields;
- normalizer caps list sizes;
- invalid priority falls back to `MEDIUM`;
- invalid output mode falls back to a supported value;
- control characters are stripped;
- generated chain trace includes `mission_contract`;
- mission flow persists the contract metadata.

Frontend validation:

```bash
npm --prefix apps/mission-control run typecheck
```

Backend validation:

```bash
pytest tests/services/test_llm_delegation_unit.py -v
pytest tests/services/test_mission_flow_v2*.py -v
make test
```

---

## Live Validation

Submit a mission such as:

```json
{
  "prompt": "Write a Python function that reads a CSV file and returns a list of dictionaries",
  "requested_target_language": "python",
  "metadata": {
    "mission_type": "BUILD_NEW",
    "output_mode": "FULL_BUILD"
  }
}
```

Expected result:

- mission reaches at least CEO-delegated/running state;
- chain trace includes `mission_contract`;
- contract has at least one logicnode requirement;
- Mission Detail renders the Mission Contract panel;
- fallback source is clearly shown when no provider credentials are available.

---

## Definition of Done

- [ ] Mission contract schema exists or mission-charter schema is extended.
- [ ] `generate_mission_contract()` is implemented with fallback.
- [ ] Mission flow persists `metadata["mission_contract"]`.
- [ ] Chain trace API exposes `mission_contract`.
- [ ] Mission Control displays the Mission Contract panel.
- [ ] Unit tests cover fallback, normalization, persistence, and trace exposure.
- [ ] Frontend typecheck passes.
- [ ] Backend tests pass.
- [ ] Live mission validation proves contract visibility.
- [ ] Current docs are updated without overstating Phase 3 capabilities.

---

## Risk Notes

### Contract naming

The previous plan used `refined_ir_contract`. That name is too narrow for the
artifact being created here. The contract should guide generation and validation,
not only refined IR. Use `mission_contract` unless existing code compatibility
requires an alias during transition.

### Prompt injection

The user prompt is included in the contract prompt. Keep length bounds,
sanitization, and prompt-guard checks in place before sending it to a provider.

### Fallback quality

The fallback contract is not a fake success. It should be marked as fallback and
give enough structure for local smoke tests, while clearly signaling that the
LLM intelligence path was not used.

### Do not block existing missions too early

Until Phase 3 consumes the contract reliably, contract-generation failure should
not fail otherwise healthy analysis/source-bundle missions.
