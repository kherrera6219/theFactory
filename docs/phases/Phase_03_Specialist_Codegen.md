# Phase 3 - First Generated Output Artifact
## Tier 1 | Estimated Duration: 5-7 days

Document version: 2026.05.17  
Last updated: 2026-05-17  
Status: Implemented

---

## Context

This is the first phase where theFactory should produce new software output.

Today the app can accept a mission, route it, extract logicnodes/RIR from source
payloads, persist knowledge, show chain trace, and package source-bundle
artifacts. That is a real orchestration foundation, but it is not yet a factory
loop: there is no durable generated-code artifact distinct from input source.

Phase 3 consumes the Phase 2 mission contract and produces one narrow, visible,
downloadable generated artifact.

The goal is intentionally modest: prove the first working BUILD_NEW loop for a
single-file Python output before expanding to multi-file apps, ports,
modernization, dependency absorption, or runtime QC.

---

## Validated Starting Point

- **Current validation - May 17, 2026:** Phase 3 is implemented locally with
  deterministic fallback, generated-code artifact packaging, artifact download,
  and Mission Detail visibility. Remaining validation is a credentialed
  live-provider mission that proves non-fallback generation quality.
- Pod workers extract logicnodes and build Refined IR modules.
- `/internal/knowledge` persists worker results, and generated output is now a
  first-class mission artifact when generation runs.
- `build_artifacts.py` packages generated code when present and still packages
  source bundles when `metadata.source_code` exists.
- Mission Control can display build artifacts and generated output.
- Audit/equivalence is shallow and should not be represented as proof of
  generated-code correctness yet.

---

## Exit State

A BUILD_NEW mission can produce:

- a generated code object in mission metadata;
- a `generated_code` build artifact;
- artifact text that is not the submitted source bundle;
- filename/language/dependency metadata;
- chain trace visibility;
- Mission Control display;
- download endpoint;
- tests proving fallback and packaging behavior.

Tier 1 is complete only when a live demo mission creates a visible generated
artifact.

---

## Scope Boundaries

This phase includes:

- one generated artifact per mission;
- Python-first standalone-file generation;
- contract-driven prompt construction;
- deterministic fallback marked as fallback;
- generated artifact packaging and display.

This phase does not include:

- multi-file project generation;
- container builds;
- package publishing;
- dependency absorption;
- runtime execution/QC;
- equivalence guarantees;
- security/compliance gating;
- cost ledger.

Those are later phases.

---

## Exact Work

### 1. Add specialist generation API in orchestrator

In `services/orchestrator/orchestrator/llm_delegation.py`, add:

- `_build_codegen_prompt(...)`
- `_normalize_codegen_result(...)`
- `_fallback_codegen(...)`
- `generate_code_from_contract(...)`

Inputs:

- mission context;
- assigned specialist agent ID;
- Phase 2 `mission_contract`;
- extracted logicnodes when available;
- target language;
- output mode.

Output:

```json
{
  "schema_version": "generated_output.v1",
  "generated_code": "def count_words(text: str) -> dict[str, int]: ...",
  "filename": "count_words.py",
  "language": "python",
  "description": "Word-frequency helper function.",
  "dependencies": [],
  "usage_example": "count_words('hello hello')",
  "source": "llm",
  "specialist_agent_id": "AGENT-14-PYTHON",
  "model_provider": "openai",
  "model": "verified-model-id",
  "generated_at": "2026-05-16T00:00:00Z"
}
```

Rules:

- Generated code must be plain source text, not markdown.
- Strip code fences if a provider returns them.
- Sanitize filenames.
- Cap embedded logicnode/context count.
- Return fallback output only with `source: "fallback"`.
- Do not count fallback output as a successful generated-code artifact unless
  the product explicitly wants placeholder artifacts.

### 2. Wire generation at the right orchestration boundary

Prefer orchestrator-owned generation at the mission-flow boundary once the
mission contract and logicnode/knowledge records are available.

Avoid tightly importing orchestrator internals from pod-worker if a cleaner
orchestrator-side hook can use persisted mission data. If pod-worker must invoke
generation for the first implementation, keep it behind a feature flag and
promote the result through `/internal/knowledge` so the orchestrator remains the
metadata source of truth.

Feature flag:

```text
CODE_GENERATION_ENABLED=true
```

Skip generation when:

- output mode is `ANALYZE_ONLY`;
- no mission contract exists and no safe fallback contract can be built;
- target language is unsupported for the initial rollout.

### 3. Promote generated output into mission metadata

Store generated output in:

```python
metadata["generated_output"] = generated_output
```

Emit a chain/audit event:

```text
GENERATED_OUTPUT_CREATED
```

Payload summary should include:

- source;
- filename;
- language;
- code length;
- specialist agent ID;
- model/provider when present.

### 4. Add generated-output artifact packaging

In `services/orchestrator/orchestrator/build_artifacts.py`, add generated-code
artifact support beside source-bundle support.

Preferred artifact fields:

- `artifact_id`: `generated-code-output`
- `artifact_type`: `generated_code`
- `stage`: `squeeze`
- `status`: `SUCCESS`
- `artifact_text`: generated source code
- `manifest.filename`
- `manifest.language`
- `manifest.description`
- `manifest.dependencies`
- `manifest.source`
- `manifest.specialist_agent_id`
- `digest_sha256`
- `size_bytes`

Artifact selection rule:

- if valid `generated_output.generated_code` exists, package generated code;
- otherwise keep existing source-bundle behavior.

This preserves current missions while enabling generated artifacts.

### 5. Expose generated output through APIs

Ensure chain trace includes generated-code build artifacts.

Add or update a download endpoint:

```text
GET /v1/missions/{mission_id}/artifact?artifact_type=generated_code
```

The endpoint should:

- return 404 when no generated artifact exists;
- set a safe filename;
- choose a reasonable text MIME type;
- never expose unrelated mission data.

### 6. Add Mission Control display

In `apps/mission-control/app/(shell)/missions/[id]/page.tsx`, add a Generated
Output panel.

Show:

- filename;
- language;
- source: LLM or fallback;
- specialist;
- model/provider when present;
- description;
- dependencies;
- generated source code;
- copy/download controls.

If output is fallback, render a warning and do not present it as a successful
factory deliverable.

### 7. Update docs

Update:

- `docs/IMPLEMENTATION_STATUS.md`
- `docs/ARCHITECTURE_DATA_FLOWS.md`
- `docs/ARCHITECTURE.md` if it references source-bundle-only completion;
- `HGR_Phased_Build_Plan.md` if implementation choices differ.

Docs must state that this phase creates the first narrow generated artifact, not
full app builds, runtime QC, or equivalence guarantees.

---

## Files Likely Changed

- `services/orchestrator/orchestrator/llm_delegation.py`
- `services/orchestrator/orchestrator/mission_flow_v2.py`
- `services/orchestrator/orchestrator/build_artifacts.py`
- `services/orchestrator/orchestrator/routes/internal.py`
- `services/orchestrator/orchestrator/routes/missions.py`
- `services/api-gateway/api_gateway/main.py`
- `apps/mission-control/app/lib/types.ts`
- `apps/mission-control/app/lib/api-client.ts`
- `apps/mission-control/app/(shell)/missions/[id]/page.tsx`
- `.env.example`
- `tests/services/test_llm_delegation_unit.py`
- `tests/services/test_build_artifacts_unit.py`
- `tests/services/test_mission_flow_v2*.py`
- `docs/IMPLEMENTATION_STATUS.md`

---

## Tests

Add unit tests for:

- fallback codegen structure;
- code-fence stripping;
- empty generated code rejected;
- filename path traversal sanitized;
- generated-output artifact builder;
- source-bundle fallback when no generated output exists;
- generated output promoted into mission metadata;
- chain trace includes generated-code artifact.

Backend validation:

```bash
pytest tests/services/test_llm_delegation_unit.py -v
pytest tests/services/test_build_artifacts_unit.py -v
pytest tests/services/test_mission_flow_v2*.py -v
make test
```

Frontend validation:

```bash
npm --prefix apps/mission-control run typecheck
```

---

## Live Demo Validation

Submit a BUILD_NEW mission:

```json
{
  "prompt": "Write a Python function called count_words that takes a string and returns a dict of word frequencies",
  "requested_target_language": "python",
  "metadata": {
    "mission_type": "BUILD_NEW",
    "output_mode": "FULL_BUILD"
  }
}
```

Expected:

- mission reaches COMPLETE;
- metadata contains `generated_output`;
- build artifacts include `artifact_type: generated_code`;
- generated artifact text contains Python source code;
- generated artifact is not the input source bundle;
- Mission Detail shows Generated Output;
- artifact download endpoint returns the generated file.

If provider credentials are absent:

- mission may use fallback behavior;
- fallback must be visibly marked;
- Phase 3 is not complete until a credentialed live run proves real generated
  output or the project explicitly accepts offline fallback as the milestone.

---

## Definition of Done

- [x] `generate_code_from_contract()` or equivalent specialist generation API exists.
- [x] Generated output uses the Phase 2 mission contract.
- [x] Generation is gated by mission type/output mode and skips `ANALYZE_ONLY`.
- [x] `metadata["generated_output"]` is persisted for successful generation.
- [x] `generated_code` artifact packaging exists.
- [x] Source-bundle packaging still works when no generated output exists.
- [x] Chain trace exposes the generated artifact.
- [x] API gateway exposes artifact download.
- [x] Mission Control displays generated output with copy/download controls.
- [x] Fallback output is clearly marked and not misreported as credentialed generation.
- [x] Backend focused/full Python tests and frontend lint/tests passed during the Phase 1-5 implementation pass.
- [ ] Credentialed live demo mission proves a real non-fallback generated artifact.
- [x] Current docs are updated to reflect the narrow shipped capability.

---

## Risk Notes

### Service boundary

The earlier plan imported orchestrator LLM functions directly into pod-worker.
That may be expedient, but it increases coupling. Prefer orchestrator-owned
generation if the existing mission-flow data path can support it.

### False success

A fallback placeholder is useful for local operation, but it is not generated
software. The UI, artifact manifest, and validation should keep that distinction
visible.

### Quality claims

This phase proves generation and packaging, not correctness. Do not claim
equivalence, security, runtime QC, or dependency safety until later phases
implement those checks.

### Prompt size

Large source imports can produce many logicnodes. Cap prompt context and prefer
the mission contract plus a small representative logicnode set for the first
version.

### Generated code safety

Do not execute generated code in this phase. Runtime execution belongs behind
the later runtime QC/sandbox phases.
