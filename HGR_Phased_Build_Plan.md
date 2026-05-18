# theFactory / Holy Grail Refinery
## Validated Phased Build Plan - Current State to Working Factory
**Date:** May 2026  
**Basis:** Current documentation review, static code validation, gap report validation

---

## Validation Summary

The prior plan was directionally right about the major missing capabilities, but
Phase 1 overstated the model problem. Model availability is time-sensitive and
must be verified against the live provider before replacement. The correct first
phase was model governance and live/fallback LLM validation, not a blind
replacement with `o3`, `o4-mini`, or `gpt-4o`.

As of the May 16 implementation pass, Phases 1-5 have moved from planned to
implemented:

- active OpenAI model defaults use verified `gpt-5.5` executive/operations
  routes and `gpt-5.3-codex` coding routes, with deterministic no-key fallback
  smoke coverage;
- PM intake creates persisted `feature_contract` and `mission_charter`
  metadata;
- CEO delegation creates a durable `mission_contract`;
- specialist planning can create a first narrow `generated_output`, and build
  artifact packaging can expose it as a `generated_code` artifact;
- CEO delegation now decomposes the mission contract into `logic_clusters`;
- Mission Detail displays PM contracts, mission charters, mission contracts,
  logic clusters, generated output metadata, generated code preview text when
  present, and a generated-code download action.

As of the May 18 Phase 6 pass, pod managers now also produce pod group
standards during the v2 GATING phase:

- pod group standard generation exists with LLM routing and deterministic
  fallback deduplication;
- Mission Flow v2 stores `metadata["pod_group_standards"]` and emits
  `MISSION_POD_GROUP_STANDARD_PRODUCED`;
- chain trace exposes pod standards;
- Mission Detail displays pod standards, canonical LogicNode counts, duplicate
  removal counts, and canonical node summaries.

The core remaining validated gap is now narrower:

- theFactory has real mission orchestration, eventing, extraction, RIR storage,
  Mission Control visibility, durable PM/CEO contracts, first generated-output
  artifact support, source-bundle artifact packaging, and CEO logic clusters.
- theFactory does not yet have real JavaScript/Java AST extraction, full
  FETCH/FUSION execution, AIM, dependency absorption, runtime QC, equivalence
  validation, compliance/security enforcement, or cost accounting.
- Current docs split between accurate implementation-status docs and
  forward-looking product docs that describe future capabilities in present tense.

This plan separates implemented reality from planned capability and keeps each
phase tied to a demonstrable result.

`HGR_Phased_Build_Plan_1.md` is retained only as an older/stale draft. It still
contains unverified model replacement guidance and should not be used as the
source of truth unless it is reconciled against live provider catalogs and the
current implementation.

---

## Operating Rules

1. Code is truth when docs and implementation disagree.
2. Every phase must update `docs/IMPLEMENTATION_STATUS.md`.
3. Every phase must update affected public/current docs so they do not overstate
   the shipped system.
4. Every new LLM path must have a deterministic fallback.
5. Every new artifact must be visible in Mission Control and in an API response.
6. Every phase must include unit tests and, when applicable, a live-stack smoke
   test.
7. Python validation should be run before marking a phase complete. If Python is
   unavailable in the local shell, that is a blocker to phase completion, not a
   reason to skip validation.

---

# Tier 1 - First Working Loop
## Goal: a mission produces a durable specification and an output artifact

---

## Phase 1 - Model Governance and Live LLM Validation
**Duration:** 1-2 days  
**Entry state:** Model strings are hard-coded across runtime config, docs, and UI.
Live model validity has not been revalidated in this review.  
**Exit state:** The active model matrix is provider-verified, promotion-approved,
documented, and proven by at least one live CEO delegation call or a clearly
documented no-key fallback.

### What to do

1. Inventory all configured model IDs from:
   - `services/orchestrator/orchestrator/agent_integrations.py`
   - `services/orchestrator/orchestrator/llm_delegation.py`
   - `services/api-gateway/api_gateway/main.py`
   - `apps/mission-control/app/(shell)/settings/page.tsx`
   - `.env.example`
   - `deploy/docker-compose.yaml`
   - model governance docs

2. Verify each model ID against the live provider/API or the provider's current
   official model catalog.

3. Update the model matrix only after verification:
   - keep existing IDs that are valid and production-approved;
   - replace IDs that are unavailable, deprecated, preview-only, or blocked by
     promotion policy;
   - keep provider fallbacks explicit.

4. Add a model-governance smoke test that fails if a configured production agent
   maps to an unknown, preview, rolling, or blocked model.

5. Run a live CEO delegation smoke test when API credentials are available.
   Without API credentials, validate deterministic fallback behavior and record
   the limitation.

### Files likely changed

- `services/orchestrator/orchestrator/agent_integrations.py`
- `services/orchestrator/orchestrator/llm_delegation.py`
- `apps/mission-control/app/(shell)/settings/page.tsx`
- `.env.example`
- `deploy/docker-compose.yaml`
- `docs/AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md`
- `docs/MODEL_PROMOTION_GOVERNANCE.md`
- `docs/IMPLEMENTATION_STATUS.md`
- tests under `tests/services/`

### Validation

```bash
python scripts/export_agent_model_inventory.py --output-file reports/agent-model-inventory.local.json
python scripts/qualification_gate_summary.py --policy-file deploy/promotion-policy.json --output-file reports/qualification-gate-summary.local.json
pytest tests/services/test_llm_delegation_unit.py -v
make test
```

Optional live validation when credentials are present:

```bash
python scripts/smoke_ceo_delegation.py
```

If the smoke script does not exist yet, create a small checked-in script rather
than relying on ad hoc one-liners.

### Definition of done

- All production agent model assignments are verified current or intentionally
  replaced.
- Promotion model governance reports zero blocked production agents.
- Mission Control settings display matches backend model assignment.
- At least one CEO delegation path is proven: live LLM response when credentials
  exist, deterministic fallback when they do not.
- Docs no longer state unverified model IDs as guaranteed-valid.

### Current status - implemented May 16, 2026

- OpenAI executive/operations defaults were updated to `gpt-5.5`, and coding
  defaults were updated to `gpt-5.3-codex`.
- Model inventory evidence was regenerated in
  `docs/evidence/agent_model_inventory_latest.json`.
- `scripts/smoke_ceo_delegation.py` validates deterministic no-key fallback.
- Focused delegation tests and Mission Control type checks passed.

Remaining non-code blocker:

- Promotion qualification still requires fresh evidence for stale
  `max_age_days` policy checks.

---

## Phase 2 - Durable Mission Contract
**Duration:** 3-5 days  
**Entry state:** CEO delegation returns routing and rationale only. Chat has a
local preview contract, but the mission does not persist a formal build contract.  
**Exit state:** Every mission can produce and expose a durable contract describing
what should be built, analyzed, or transformed.

### What to do

1. Add a persisted mission contract schema. Prefer extending the existing
   `mission_charter` direction rather than creating an incompatible parallel
   object.

2. Add CEO contract generation after routing:
   - mission summary
   - mission type
   - target language
   - output mode
   - required domains
   - logicnode requirements
   - acceptance criteria
   - risk notes
   - source: `llm` or `fallback`

3. Store the contract in mission metadata and include it in chain trace.

4. Display the contract in Mission Control mission detail.

5. Add tests for normalization, fallback, chain trace exposure, and UI typing.

### Files likely changed

- `services/orchestrator/orchestrator/llm_delegation.py`
- `services/orchestrator/orchestrator/mission_flow_v2.py`
- `services/orchestrator/orchestrator/routes/internal.py`
- `apps/mission-control/app/lib/types.ts`
- `apps/mission-control/app/(shell)/missions/[id]/page.tsx`
- `schemas/`
- `docs/IMPLEMENTATION_STATUS.md`

### Validation

```bash
pytest tests/services/test_llm_delegation_unit.py -v
pytest tests/services/test_mission_flow_v2*.py -v
npm --prefix apps/mission-control run typecheck
make test
```

Live-stack validation:

- submit a mission;
- confirm chain trace contains the mission contract;
- confirm Mission Detail displays the contract.

### Current status - implemented May 16, 2026

- `generate_mission_contract()` exists in `llm_delegation.py` with LLM and
  deterministic fallback behavior.
- Mission Flow v2 stores `metadata["mission_contract"]`, emits
  `MISSION_CONTRACT_GENERATED`, and records audit evidence.
- Chain trace and Mission Detail expose the contract.
- Focused normalization, fallback, lifecycle, and UI typing validation passed.

---

## Phase 3 - First Generated Output Artifact
**Duration:** 5-7 days  
**Entry state:** Pod workers extract logicnodes and RIR, but output artifacts are
source bundles of submitted source code.  
**Exit state:** A BUILD_NEW mission can produce a generated code artifact that is
stored, downloadable, visible in Mission Control, and distinct from the input
source bundle.

### What to do

1. Add specialist code generation from the durable mission contract.

2. Keep the first version intentionally narrow:
   - one target language, Python first;
   - simple standalone-file output;
   - no multi-file project generation yet;
   - deterministic fallback that does not masquerade as successful generation.

3. Promote generated output to mission metadata through the orchestrator, not by
   tightly coupling pod-worker internals to the orchestrator package.

4. Add a generated-code artifact builder beside source-bundle packaging.

5. Add an artifact download endpoint.

6. Add a Mission Control "Generated Output" panel.

### Files likely changed

- `services/orchestrator/orchestrator/llm_delegation.py`
- `services/orchestrator/orchestrator/mission_flow_v2.py`
- `services/orchestrator/orchestrator/build_artifacts.py`
- `services/orchestrator/orchestrator/routes/internal.py`
- `services/api-gateway/api_gateway/main.py`
- `apps/mission-control/app/lib/types.ts`
- `apps/mission-control/app/(shell)/missions/[id]/page.tsx`
- tests under `tests/services/`

### Validation

```bash
pytest tests/services/test_llm_delegation_unit.py -v
pytest tests/services/test_build_artifacts_unit.py -v
make test
```

Live demo:

- submit: "Write a Python function called count_words that takes a string and
  returns a dict of word frequencies";
- mission reaches COMPLETE;
- chain trace includes a `generated_code` artifact;
- artifact text is not the input source bundle;
- Mission Detail renders and downloads the generated file.

Tier 1 is complete only when this demo works end to end.

### Current status - implemented May 16, 2026

- `generate_code_from_contract()` creates narrow specialist generated output
  from the durable mission contract.
- `metadata["generated_output"]` is stored during specialist planning for
  eligible non-`ANALYZE_ONLY` missions.
- `build_artifacts.py` packages valid generated output as
  `artifact_type: generated_code`.
- API Gateway exposes
  `GET /v1/missions/{mission_id}/artifact?artifact_type=generated_code`.
- Mission Detail displays generated output metadata, preview text when present,
  and a generated-code download action.

Remaining validation gap:

- A live LLM-backed demo mission still requires provider credentials. The
  current local validation proves deterministic fallback and unit/integration
  behavior.

---

# Tier 2 - Intake and Agent Cognition
## Goal: agents produce structured work products, not only routing metadata

---

## Phase 4 - PM Feature Contract and Mission Charter
**Duration:** 3-5 days  
**Entry state:** PM artifacts exist; Chat preview now uses the backend PM endpoint with local fallback.
**Exit state:** PM intake produces a persisted feature contract and mission
charter before CEO delegation.

### Scope

- Add PM LLM/fallback feature-contract generation.
- Validate output against the existing mission-charter schema or a versioned
  successor.
- Replace or reconcile the chat preview with the real PM artifact.
- Display PM contract/charter on Mission Detail.

### Current status - implemented May 16, 2026

- PM intake generates and persists `feature_contract` and schema-validated
  `mission_charter` metadata.
- Chat preview calls the routed backend PM feature-contract endpoint and keeps
  local builder preview as an offline fallback.
- Chain trace exposes both PM artifacts.
- Mission Flow v2 passes PM artifacts into CEO contract generation context.
- Mission Detail displays PM Feature Contract and Mission Charter panels.
- Focused/full backend tests, Mission Control type checks, and Mission Control
  tests passed.

---

## Phase 5 - CEO Logic Cluster Decomposition
**Duration:** 3-4 days  
**Entry state:** CEO selects pod manager and specialist only.  
**Exit state:** CEO decomposes a mission into logic clusters with assigned pods,
domains, and priorities.

### Scope

- Add `logic_clusters` to mission metadata and chain trace.
- Route pod work using cluster domain scope where available.
- Display cluster assignment in Mission Control.

### Current status - implemented May 16, 2026

- `generate_logic_clusters()` exists in `llm_delegation.py` with LLM and
  deterministic fallback behavior.
- CEO delegation stores `metadata["logic_clusters"]`, emits
  `LOGIC_CLUSTERS_DECOMPOSED`, records audit evidence, and adds a
  `logic_clusters` stage artifact summary.
- Pod-manager delegation receives `logic_clusters` in mission context.
- Pod workers consume logic-cluster domain focus and boost matching concept
  confidence for their assigned pod.
- Chain trace and Mission Detail expose cluster assignment, domain, priority,
  pod manager, specialist, requirement refs, and rationale.
- Focused/full backend tests, Mission Control type checks, and Mission Control
  tests passed.

---

## Phase 6 - Pod Group Standards
**Duration:** 4-5 days  
**Entry state:** Pod workers extract per-language logicnodes independently.  
**Exit state:** Pod managers consolidate specialist outputs into canonical pod
group standards.

### Scope

- Deduplicate semantically equivalent logicnodes across languages.
- Store `pod_group_standards`.
- Expose standards through chain trace and Mission Control.

### Current status - implemented May 18, 2026

- `generate_pod_group_standard()` exists in `llm_delegation.py` with LLM and
  deterministic fallback behavior.
- Mission Flow v2 produces pod group standards after the mission enters
  `GATING`, stores them under `metadata["pod_group_standards"]`, emits
  `MISSION_POD_GROUP_STANDARD_PRODUCED`, and records audit/artifact evidence.
- Chain trace exposes `pod_group_standards`.
- Mission Detail displays pod group standards and their canonical LogicNodes.
- Focused backend tests, ruff checks, and Mission Control lint passed.

---

## Phase 7 - JavaScript and Java AST Extractors
**Duration:** 2-4 days  
**Entry state:** JavaScript and Java AST extractors are explicit stubs.  
**Exit state:** JavaScript and Java extraction produce real function/class/import
nodes with tests.

### Scope

- Implement JavaScript parser integration.
- Implement Java parser integration.
- Add fixture-based extractor tests.
- Update implementation status from stub to active.

---

# Tier 3 - Full Smelt-Cycle Execution
## Goal: the named phases perform real work, not only state transitions

---

## Phase 8 - FETCH / Knowledge Context
**Duration:** 7-10 days  
**Entry state:** FETCH is mostly doctrine/reference material.  
**Exit state:** missions can retrieve relevant language/framework context from a
real knowledge store and attach it to downstream prompts.

### Scope

- Define knowledge context artifact.
- Use Qdrant or configured vector store for retrieval.
- Add deterministic fallback to local curated docs.
- Display fetched context summary.

---

## Phase 9 - FUSION / Master Logic Stream
**Duration:** 5-7 days  
**Entry state:** FUSION is a lifecycle checkpoint.  
**Exit state:** CEO or a fusion agent combines pod group standards into a master
logic stream used by code generation.

### Scope

- Add `master_logic_stream`.
- Resolve duplicate/conflicting logicnodes across pods.
- Feed stream into code generation when present.
- Display stream and provenance.

---

## Phase 10 - DELIVERY / PM Verification
**Duration:** 4-5 days  
**Entry state:** COMPLETE means the pipeline reached final state, but delivery is
mostly trace/artifact display.  
**Exit state:** PM generates a delivery summary tied to acceptance criteria and
the delivered artifact.

### Scope

- Add PM delivery summary.
- Compare generated output to mission contract acceptance criteria.
- Show "Mission Delivered" panel.
- Add first-class download/copy actions.

---

## Phase 11 - Application Intelligence Map
**Duration:** 5-7 days  
**Entry state:** AIM is documented as forward-looking and schema references are
not implemented.  
**Exit state:** analysis/import/modernize missions can produce an AIM artifact
before modification work begins.

### Scope

- Add AIM schema.
- Generate language/dependency/function/concept inventory.
- Add approval gate for high-risk mission types.
- Add AIM viewer.

---

# Tier 4 - Quality and Trust
## Goal: claims about verification, safety, dependency absorption, and cost are real

---

## Phase 12 - Equivalence Verification Harness
**Duration:** 7-10 days  
**Entry state:** audit checks are shallow shape checks and simple PASS reports.  
**Exit state:** generated or transformed output is checked against contract and,
where feasible, source behavior.

### Scope

- Add contract-level tests first.
- Add sandboxed execution for Python behind a flag.
- Add equivalence reports to audit evidence.
- Block COMPLETE on configured verification failures.

---

## Phase 13 - Security and Compliance Agents
**Duration:** 5-7 days  
**Entry state:** security/compliance agents exist mostly as registry/persona
entries.  
**Exit state:** generated output and extracted logicnodes receive real security
and compliance verdicts.

### Scope

- Add security scan service.
- Add compliance/license provenance checks.
- Display verdicts in audit panel.
- Define block/warn/pass policy.

---

## Phase 14 - Dependency Absorption Engine
**Duration:** 10-14 days  
**Entry state:** DEPABS is doctrine and registry wiring, not an active engine.  
**Exit state:** REDUCE_DEPENDENCIES missions classify dependencies and generate
first-party replacements for narrow, absorbable cases.

### Scope

- Add dependency inventory schema.
- Add dependency classifier.
- Add first-party replacement generation for small pure-function cases.
- Package modified output and absorption report.

---

## Phase 15 - Token and Cost Ledger
**Duration:** 2-3 days  
**Entry state:** LLM cost per mission is not tracked.  
**Exit state:** every LLM call records provider, model, token usage where
available, estimated cost, agent, and mission.

### Scope

- Wrap LLM calls with tracking.
- Add database table/migration.
- Add Mission Control cost summary.
- Add budget warning events.

---

# Tier 5 - Production Operations
## Goal: the system can be demonstrated, operated, recovered, and trusted

---

## Phase 16 - Knowledge Lake Embeddings and Auto-Refresh
**Duration:** 7-10 days  
**Entry state:** knowledge storage exists, but doc intelligence is not a complete
operational knowledge lake.  
**Exit state:** language/framework docs can be embedded, refreshed, and used by
FETCH/context retrieval.

### Scope

- Real embedding model selection.
- Initial corpus load.
- Refresh job.
- Retrieval quality tests.

---

## Phase 17 - DR Evidence and Release Hardening
**Duration:** 3-5 days  
**Entry state:** release-trust docs and scripts exist, but fresh DR evidence and
history hygiene must be verified before launch claims.  
**Exit state:** DR drill evidence exists, secrets/history risks are addressed, and
promotion gates pass.

### Scope

- Run and record DR drill.
- Verify backup/restore RTO.
- Review git history secret findings before any destructive history rewrite.
- Rotate affected credentials if needed.
- Re-run promotion gate.

---

## Phase 18 - Reproducible Demo Missions and Launch Docs
**Duration:** 5-7 days  
**Entry state:** no current demo suite proves the full factory loop.  
**Exit state:** three reproducible demo missions prove BUILD_NEW, ANALYZE_ONLY,
and IMPORT_MODERNIZE/DEBUG_REPAIR behavior.

### Scope

- Add live demo tests.
- Add `make demo`.
- Update README and current docs to match implemented behavior only.
- Archive or relabel forward-looking docs that remain aspirational.

---

# Summary Table

| Phase | Name | Tier | Duration | Status | Key Output |
|---|---|---:|---:|---|---|
| 1 | Model Governance and Live LLM Validation | 1 | 1-2 days | Implemented | Verified model matrix and fallback smoke |
| 2 | Durable Mission Contract | 1 | 3-5 days | Implemented | Mission contract in metadata/API/UI |
| 3 | First Generated Output Artifact | 1 | 5-7 days | Implemented, pending live LLM demo | Generated code artifact path |
| 4 | PM Feature Contract and Mission Charter | 2 | 3-5 days | Implemented | Structured PM intake in metadata/API/UI |
| 5 | CEO Logic Cluster Decomposition | 2 | 3-4 days | Implemented | Pod/domain work clusters |
| 6 | Pod Group Standards | 2 | 4-5 days | Implemented | Cross-language pod consolidation |
| 7 | JavaScript and Java AST Extractors | 2 | 2-4 days | Planned | Real JS/Java extraction |
| 8 | FETCH / Knowledge Context | 3 | 7-10 days | Planned | Retrieved technical context |
| 9 | FUSION / Master Logic Stream | 3 | 5-7 days | Planned | Cross-pod synthesis |
| 10 | DELIVERY / PM Verification | 3 | 4-5 days | Planned | Delivery summary and criteria check |
| 11 | Application Intelligence Map | 3 | 5-7 days | Planned | AIM artifact and approval gate |
| 12 | Equivalence Verification Harness | 4 | 7-10 days | Planned | Real verification evidence |
| 13 | Security and Compliance Agents | 4 | 5-7 days | Planned | Safety/compliance verdicts |
| 14 | Dependency Absorption Engine | 4 | 10-14 days | Planned | Dependency reduction reports/output |
| 15 | Token and Cost Ledger | 4 | 2-3 days | Planned | Per-mission LLM cost |
| 16 | Knowledge Lake Embeddings and Auto-Refresh | 5 | 7-10 days | Planned | Operational knowledge lake |
| 17 | DR Evidence and Release Hardening | 5 | 3-5 days | Planned | Recovery/release evidence |
| 18 | Reproducible Demo Missions and Launch Docs | 5 | 5-7 days | Planned | Launch-ready demo suite |

**Remaining estimate after Phase 6:** 57-87 days, excluding the live provider-key
demo and stale qualification-evidence refresh.

---

# Critical Path

Minimum path to a real working demo:

1. Complete a live provider-key BUILD_NEW demo through the implemented
   Phase 1-5 loop.
2. Phase 7 - activate JavaScript and Java AST extraction for higher-quality
   import/modernize missions.
3. Phase 10 - present delivered output cleanly with PM verification.
4. Phase 17 - refresh stale qualification evidence before release claims.

Phases 1-5 now provide the first local/fallback proof of value. The next proof
point should be either a live LLM-backed demo mission or Phase 6 pod standards,
depending on whether provider credentials are available.

---

# Documentation Cleanup Required Alongside The Build

The following docs currently overstate implemented behavior or mix doctrine with
current state:

- `README.md`
- `docs/00_PRODUCT_OVERVIEW.md`
- `docs/WHAT_THEFACTORY_IS_AND_IS_NOT.md`
- `docs/SCHEMA_REGISTRY_AND_VERSIONING.md`
- forward-looking capability docs for AIM, DEPABS, runtime QC, and schema registry

Each phase must update those docs when its capability becomes real. Until then,
these documents should label unimplemented capabilities as planned, reference,
or forward-looking rather than present-tense production behavior.
