# Phase 4 - PM Feature Contract and Mission Charter
## Tier 2 | Estimated Duration: 3-5 days

---

## Context

After Tier 1, theFactory should have:

- verified model governance and live/fallback LLM behavior;
- a durable `mission_contract`;
- the first narrow generated-code artifact for BUILD_NEW missions.

At that point, the next weakness is intake quality. Today the PM role is mostly
represented by mission prompt storage and UI-local chat heuristics. The Chat page
can create a preview-like contract, but it is not a durable PM work product and
does not become the source of truth for the mission.

Phase 4 gives the PM agent a real, persisted output:

- a **Feature Contract** that interprets the user's request into product-level
  requirements;
- a **Mission Charter** that records governance fields such as mission type,
  depth, output mode, risk, approval needs, and acceptance criteria.

The PM artifacts should feed the existing Phase 2 mission-contract generation
rather than compete with it.

---

## Validated Starting Point

- `mission.prompt` stores the raw user request.
- Chat has local preview logic that is useful for UX but not authoritative.
- `schemas/mission_charter.v1.json` and related mission-charter docs already
  exist.
- Mission Flow v2 has a PM_INTAKE state, but PM cognition is not yet a durable
  artifact.
- Chain trace currently exposes routing/artifact information, not PM-authored
  feature-contract and charter artifacts.

---

## Exit State

Every eligible mission can expose:

- `metadata["feature_contract"]`
- `metadata["mission_charter"]`
- chain events showing PM intake output
- audit evidence for PM artifact creation
- Mission Control panels for Feature Contract and Mission Charter
- Chat preview backed by the same PM contract path or a clearly marked local
  fallback

The CEO mission-contract generation from Phase 2 should use the PM artifacts
when they exist.

---

## Scope Boundaries

This phase includes:

- PM feature-contract generation;
- mission-charter creation/validation;
- chain trace exposure;
- Mission Control display;
- chat preview integration;
- deterministic fallback behavior.

This phase does not include:

- blocking launch until clarifying questions are answered;
- multi-turn requirements negotiation;
- full approval workflow;
- AIM generation;
- runtime QC;
- generated-code verification.

Those remain later phases.

---

## Exact Work

### 1. Define the PM Feature Contract shape

Add a typed, versioned PM artifact. A separate schema is optional, but the shape
should be explicit and testable.

Minimum shape:

```json
{
  "schema_version": "feature_contract.v1",
  "title": "CSV Reader",
  "summary": "Build a Python helper that reads CSV rows into dictionaries.",
  "functional_requirements": [
    "Read a CSV file with headers",
    "Return each row as a dictionary"
  ],
  "non_functional_requirements": [
    "Use the Python standard library"
  ],
  "acceptance_criteria": [
    "Given a CSV with headers, output list entries use header names as keys"
  ],
  "target_languages": ["python"],
  "estimated_complexity": "low",
  "human_approval_required": false,
  "risk_notes": [],
  "clarifying_questions": [],
  "source": "llm",
  "model_provider": "verified-provider",
  "model": "verified-model-id",
  "created_at": "2026-05-16T00:00:00Z"
}
```

### 2. Add PM generation in `llm_delegation.py`

Add:

- `_build_pm_feature_contract_prompt(...)`
- `_normalize_pm_feature_contract(...)`
- `_fallback_pm_feature_contract(...)`
- `generate_pm_feature_contract(...)`

Rules:

- Use the Phase 1 model-governance recommendation path.
- Do not hard-code provider/model IDs in the plan implementation.
- Bound and sanitize prompt/context.
- Request JSON only.
- Normalize empty/invalid list fields.
- Mark source as `llm` or `fallback`.
- Include clarifying questions, but do not block the mission in this phase.

The PM contract should describe product/user intent. It should not duplicate the
Phase 2 mission contract's lower-level logicnode requirements.

### 3. Build a schema-valid Mission Charter

Use the existing mission-charter schema where practical.

Add or update a helper in `mission_flow_v2.py` or a focused charter module:

```python
build_mission_charter(
    mission_id: str,
    feature_contract: dict[str, Any],
    mission_type: str,
    depth_mode: str,
    output_mode: str,
) -> dict[str, Any]
```

The output must validate against `schemas/mission_charter.v1.json` or the schema
must be intentionally versioned forward.

The charter should include:

- mission id;
- mission type;
- depth mode;
- output mode;
- target outcome;
- output format;
- risk level;
- human approval flag;
- functional requirements;
- acceptance criteria;
- risk notes;
- source.

### 4. Wire PM artifacts into Mission Flow v2

In `_prepare_pm_intake()`:

- fetch mission and metadata;
- generate `feature_contract`;
- build `mission_charter`;
- store both in metadata;
- emit a chain event such as `FEATURE_CONTRACT_CREATED`;
- record an audit event;
- continue with fallback if the LLM path fails.

Persisted fields:

```python
metadata["feature_contract"] = feature_contract
metadata["mission_charter"] = mission_charter
```

Phase 2 mission-contract generation should read these PM artifacts when present:

- feature contract summary and requirements;
- mission charter mission type/depth/output mode;
- acceptance criteria.

This keeps the PM -> CEO -> specialist sequence coherent.

### 5. Expose through chain trace

In `services/orchestrator/orchestrator/routes/internal.py`, include:

```json
{
  "feature_contract": { ... },
  "mission_charter": { ... }
}
```

Do not remove existing fields used by Mission Control. Additive changes are
preferred.

### 6. Add Mission Control panels

In mission detail, show the PM artifacts above the Mission Contract panel:

1. Feature Contract
2. Mission Charter
3. Mission Contract
4. Generated Output

Feature Contract panel:

- title;
- summary;
- functional requirements;
- non-functional requirements;
- acceptance criteria;
- target languages;
- complexity;
- source/fallback;
- clarifying questions if present.

Mission Charter panel:

- mission type;
- depth;
- output mode;
- risk;
- approval flag;
- target outcome;
- charter id/version.

Keep the layout operational and compact.

### 7. Update Chat preview integration

The Chat page should stop treating the local preview as authoritative once this
phase lands.

Preferred approach:

- add an orchestrator/API Gateway endpoint for PM feature-contract preview;
- have the Next.js API route call the gateway;
- retain the local preview only as a clearly marked offline fallback.

Avoid importing orchestrator internals directly inside API Gateway if that
violates the service boundary. The cleaner shape is:

```text
Mission Control route -> API Gateway -> Orchestrator PM preview endpoint
```

Candidate endpoints:

```text
POST /v1/pm/feature-contract
POST /internal/pm/feature-contract
```

Request:

```json
{
  "prompt": "Build a CSV reader",
  "mission_type": "BUILD_NEW",
  "depth_mode": "STANDARD",
  "output_mode": "FULL_BUILD",
  "attached_files_summary": "1 source file attached"
}
```

Response:

```json
{
  "feature_contract": { ... },
  "source": "llm"
}
```

### 8. Align docs

Update:

- `docs/IMPLEMENTATION_STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/ARCHITECTURE_DATA_FLOWS.md`
- `docs/00_PRODUCT_OVERVIEW.md` if it describes PM behavior
- `HGR_Phased_Build_Plan.md` if implementation choices differ

Docs should state that this phase adds structured intake, not full multi-turn
requirements negotiation.

---

## Files Likely Changed

- `services/orchestrator/orchestrator/llm_delegation.py`
- `services/orchestrator/orchestrator/mission_flow_v2.py`
- `services/orchestrator/orchestrator/routes/internal.py`
- `services/orchestrator/orchestrator/routes/missions.py` or a focused PM route
- `services/api-gateway/api_gateway/main.py`
- `apps/mission-control/app/api/pm/feature-contract/route.ts`
- `apps/mission-control/app/(shell)/chat/page.tsx`
- `apps/mission-control/app/(shell)/missions/[id]/page.tsx`
- `apps/mission-control/app/lib/types.ts`
- `schemas/feature_contract.v1.schema.json` if a separate schema is added
- `schemas/mission_charter.v1.json` if extended
- `tests/services/test_llm_delegation_unit.py`
- `tests/services/test_mission_flow_v2*.py`
- `docs/IMPLEMENTATION_STATUS.md`

---

## Tests

Add unit tests for:

- PM fallback contract includes required fields;
- PM normalizer caps list sizes;
- invalid complexity falls back to `medium`;
- human approval coercion is deterministic;
- mission charter validates against schema;
- PM_INTAKE persists feature contract and charter;
- chain trace exposes both artifacts;
- Phase 2 contract generation can consume PM artifacts when present.

Frontend validation:

```bash
npm --prefix apps/mission-control run typecheck
```

Backend validation:

```bash
pytest tests/services/test_llm_delegation_unit.py -v
pytest tests/services/test_mission_flow_v2*.py -v
python scripts/validate_schemas.py
make test
```

---

## Live Validation

Submit a mission:

```json
{
  "prompt": "Build a Python web scraper that fetches product prices from an e-commerce site",
  "requested_target_language": "python",
  "metadata": {
    "mission_type": "BUILD_NEW",
    "output_mode": "FULL_BUILD",
    "depth_mode": "STANDARD"
  }
}
```

Expected:

- PM_INTAKE creates `feature_contract`;
- PM_INTAKE creates `mission_charter`;
- chain trace exposes both;
- Mission Detail displays both panels;
- CEO mission contract uses the PM contract/charter context;
- fallback source is visible if provider credentials are absent.

Chat validation:

- enter the same prompt in Chat;
- PM preview comes from the backend endpoint when available;
- local preview fallback is visible when backend/API credentials are unavailable.

---

## Definition of Done

- [ ] `generate_pm_feature_contract()` implemented with fallback.
- [ ] PM feature-contract output shape is typed and tested.
- [ ] Mission charter builder validates against the mission-charter schema.
- [ ] `_prepare_pm_intake()` persists `feature_contract` and `mission_charter`.
- [ ] Chain trace exposes both artifacts.
- [ ] Phase 2 mission-contract generation consumes PM artifacts when present.
- [ ] Mission Control displays Feature Contract and Mission Charter panels.
- [ ] Chat preview uses backend PM endpoint with local fallback.
- [ ] Unit tests cover fallback, normalization, schema validation, persistence, and trace exposure.
- [ ] Frontend typecheck passes.
- [ ] Backend tests pass.
- [ ] Live mission validation proves PM artifacts are visible.
- [ ] Current docs are updated without claiming multi-turn PM negotiation.

---

## Risk Notes

### PM and CEO contract overlap

The Feature Contract is product-level intent. The Mission Contract is execution
intent. Keep these separate:

- PM Feature Contract: what the user wants and how success is judged.
- Mission Charter: governance, risk, approval, and mission mode.
- Mission Contract: what the factory must build or analyze.

### Clarifying questions

This phase may surface clarifying questions, but it does not block launch. A
future phase can add multi-turn requirement negotiation and approval gates.

### Service boundary

The PM preview endpoint should preserve the gateway/orchestrator boundary. Avoid
solving chat preview by importing orchestrator internals into unrelated runtime
contexts if a routed API can do the same job.

### Schema drift

If `mission_charter.v1` cannot represent the desired charter cleanly, either
extend it intentionally or create `mission_charter.v2`. Do not store unvalidated
objects under a schema name they do not satisfy.

### Fallback honesty

Fallback artifacts should keep the app usable, but they must be visible as
fallback so operators do not mistake offline heuristics for PM cognition.
