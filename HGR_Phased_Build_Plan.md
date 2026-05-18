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

As of the May 18 implementation pass, Phases 1-9 have moved from planned to
implemented:

- active OpenAI model defaults use verified `gpt-5.5` executive/operations
  routes and `gpt-5.3-codex` coding routes, with deterministic no-key fallback
  smoke coverage;
- PM intake creates persisted `feature_contract` and `mission_charter`
  metadata;
- CEO delegation creates a durable `mission_contract`;
- specialist planning can create a first narrow `generated_output`, and build
  artifact packaging can expose it as a `generated_code` artifact;
- Phase 8 FETCH indexes deterministic bootstrap docs, mirrors them into
  mission-scoped knowledge, exposes `fetch_result`, and passes documentation
  context to pod extraction;
- Phase 9 FUSION creates `master_logic_stream`, exposes it to Mission Control,
  and can replace missing/fallback generated output from the fused stream;
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

As of the May 18 Phase 7 pass, JavaScript/TypeScript and Java AST extraction is
active behind feature flags:

- `javalang` and `esprima` are bundled in the pod-worker requirements;
- Java AST extraction captures packages, imports, classes/interfaces/enums,
  constructors, methods, parameters, modifiers, annotations, and signatures;
- JavaScript/TypeScript AST extraction captures imports, classes, class methods,
  function declarations, and arrow/function-expression assignments;
- pod-worker AST feature flags route JS/TS and Java to AST-backed structural
  enrichment while preserving regex concept detection and regex fallback.

The core remaining validated gap is now narrower:

- theFactory has real mission orchestration, eventing, extraction, RIR storage,
  Mission Control visibility, durable PM/CEO contracts, first generated-output
  artifact support, source-bundle artifact packaging, and CEO logic clusters.
- theFactory now has FETCH/FUSION execution, AIM for source-bearing missions,
  equivalence reports, and security/compliance reports for generated outputs; it
  does not yet have dependency absorption, runtime QC, or cost accounting.
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
npm --prefix apps/mission-control run lint
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

### Current status - implemented May 18, 2026

- `extract_java_ast()` is implemented with `javalang`.
- `extract_js_ast()` is implemented with `esprima` and conservative TypeScript
  syntax stripping.
- `JavaAstExtractor` and `JavaScriptAstExtractor` wrap the existing regex
  extractors, replacing structural fields only after successful AST parsing.
- `JAVA_AST_EXTRACTOR_ENABLED` and `JS_AST_EXTRACTOR_ENABLED` are wired into
  pod-worker runtime selection and compose defaults.
- Golden tests cover Java, JavaScript, and TypeScript AST structural output.

---

# Tier 3 - Full Smelt-Cycle Execution
## Goal: the named phases perform real work, not only state transitions

---

## Phase 8 - FETCH / Knowledge Context
**Duration:** 7-10 days  
**Status:** Implemented May 18, 2026
**Entry state:** FETCH was mostly doctrine/reference material.
**Exit state:** missions retrieve deterministic bootstrap language context from
knowledge storage and attach it to downstream extraction/generation surfaces.

### Scope

- `fetch_result` metadata and chain-trace artifact.
- IS-agent bootstrap docs mirrored to global and mission-scoped knowledge.
- Pod-worker `doc_context` retrieval before extraction.
- Mission Control fetched-context summary.

---

## Phase 9 - FUSION / Master Logic Stream
**Duration:** 5-7 days  
**Status:** Implemented May 18, 2026
**Entry state:** FUSION was a lifecycle checkpoint.
**Exit state:** CEO/fusion logic combines pod group standards into a
`master_logic_stream` exposed in chain trace and used to replace missing or
fallback generated output when eligible.

### Scope

- `master_logic_stream` generation.
- Cross-pod duplicate accounting.
- Fallback/missing generated-output replacement from the fused stream.
- Mission Control stream/provenance display.

---

## Phase 10 - DELIVERY / PM Verification
**Duration:** 4-5 days  
**Status:** Implemented May 18, 2026
**Entry state:** COMPLETE means the pipeline reached final state, but delivery is
mostly trace/artifact display and generated-code artifacts already have a
download route.
**Exit state:** PM generates a delivery summary tied to acceptance criteria and
the delivered artifact, and Mission Detail shows an artifact-aware delivery
banner.

### Scope

- Add PM delivery summary.
- Compare generated output to mission contract acceptance criteria.
- Show "Mission Delivered" panel.
- Reuse the existing generated-code artifact download route.
- Adapt delivery copy/actions for source-bundle-only and analysis-only missions.

---

## Phase 11 - Application Intelligence Map
**Duration:** 5-7 days  
**Entry state:** source bundles, PM contracts, FETCH/FUSION/DELIVERY, and
language extractors exist; AIM generation, chain-trace exposure, and Mission
Control rendering are not implemented.
**Exit state:** source-bearing analysis/import/modernize/debug/security missions
produce an AIM artifact before modification or specialist codegen begins.

### Scope

- Add AIM schema and `application_intelligence_map` chain-trace field.
- Generate bounded source-bundle inventory using existing language extractors;
  do not send raw `source_code` to an LLM prompt.
- Store language, dependency, function, class, concept, complexity, and risk
  flags before CEO/specialist modification work.
- Add Mission Control AIM viewer.
- Capture high-risk approval recommendations as metadata now; defer a blocking
  approval gate to the quality/trust phases unless Phase 11 explicitly builds
  the gate.

---

# Tier 4 - Quality and Trust
## Goal: claims about verification, safety, dependency absorption, and cost are real

---

## Phase 12 - Equivalence Verification Harness
**Duration:** 7-10 days  
**Entry state:** build artifacts have digest verification, PM delivery summaries
check acceptance criteria text, audit-report endpoints exist, and the Phase 11
AIM can describe source-bearing missions. There is no durable equivalence report
or COMPLETE gate tied to behavioral evidence.
**Exit state:** generated or transformed output is checked against PM/CEO
contract criteria, build artifacts, and AIM/source inventory where available;
the result is stored as durable audit evidence and can block COMPLETE when a
configured required check fails.

### Scope

- Add `equivalence_report.v1` schema/normalizer for deterministic verification
  results.
- Generate contract-level checks from `feature_contract`, `mission_contract`,
  `generated_output`, build artifacts, and `application_intelligence_map`.
- Store `metadata["equivalence_report"]`, emit
  `MISSION_EQUIVALENCE_VERIFIED` or `MISSION_EQUIVALENCE_BLOCKED`, expose the
  report in chain trace, and render it in Mission Control audit evidence.
- Wire the existing `VERIFIED -> COMPLETE` completion gate to require passing
  equivalence for generated/transformed output when Phase 12 enforcement is
  enabled.
- Keep source-bundle-only and `ANALYZE_ONLY` missions non-blocking unless they
  explicitly produce generated/transformed output.
- Add Python sandbox execution only behind an explicit opt-in flag after the
  deterministic report path is in place. Do not execute arbitrary submitted
  source by default.

---

## Phase 13 - Security and Compliance Agents
**Duration:** 5-7 days  
**Entry state:** AGENT-05-SECURITY and AGENT-08-COMPLIANCE exist in the
registry/persona/model matrix, repo-level security and compliance evidence docs
exist, Mission Flow has build artifacts plus Phase 12 equivalence reports, and
Mission Control can render audit evidence. There is no mission-local security or
compliance verdict yet.
**Exit state:** generated output and source-bearing mission artifacts receive
deterministic security/compliance verdicts that are stored in metadata, exposed
through chain trace/audit evidence, rendered in Mission Control, and optionally
block COMPLETE under policy.

### Scope

- Add `security_compliance_report.v1` normalizer with separate security and
  compliance sections.
- Reuse existing inputs first: `generated_output`, build artifacts,
  `application_intelligence_map`, `equivalence_report`, mission contracts, data
  classification, and source-bundle manifests.
- Implement deterministic checks before external scanners: secret-pattern
  detection, dangerous API/import hints, insecure generated-code patterns,
  missing artifact/equivalence evidence, data-classification flags, and
  license/provenance unknowns.
- Emit `MISSION_SECURITY_COMPLIANCE_PASSED`,
  `MISSION_SECURITY_COMPLIANCE_WARNED`, or
  `MISSION_SECURITY_COMPLIANCE_BLOCKED`; store
  `metadata["security_compliance_report"]`.
- Expose the report in chain trace and Mission Control audit evidence.
- Add COMPLETE gating only when `MISSION_SECURITY_COMPLIANCE_ENFORCEMENT_ENABLED`
  is true or the mission depth/data classification requires it.
- Keep external SAST/SCA tooling optional in this phase; wire it as evidence
  input when available, not as a hard runtime dependency.

---

## Phase 14 - Dependency Absorption Engine
**Duration:** 10-14 days  
**Entry state:** AGENT-39-DEPABS exists in registry/personas, the dependency
absorption doctrine defines safety blocks and gates, AIM exposes detected
dependencies, and Phase 12 equivalence reports exist. There is no mission-local
dependency inventory, classifier, survival justification, or absorption report.
**Exit state:** `REDUCE_DEPENDENCIES` and source-bearing modernization missions
produce dependency inventory, classification, and safety-block evidence; only
low-risk pure-function candidates can proceed to first-party replacement
planning, and replacement execution remains gated by equivalence and
security/compliance verdicts.

### Scope

- Add `dependency_inventory.v1`, `dependency_classification_report.v1`, and
  `dependency_absorption_report.v1` runtime shapes.
- Build inventory from AIM dependency hints, source-bundle manifests, lockfiles
  when present, package metadata, and generated-output dependency lists.
- Implement deterministic classifier categories from the doctrine: absorb,
  reimplement, replace, vendor, wrap, pin, keep, block.
- Enforce the initial safety block list before any replacement generation.
- Require Phase 12 `equivalence_report` and Phase 13
  `security_compliance_report` before any dependency is marked absorbed.
- Limit first implementation to recommendations and replacement plans for small,
  pure, local utility dependencies. Do not remove runtime/platform/security
  dependencies automatically.
- Expose reports in chain trace and Mission Control; package modified output
  only after the report is non-blocking and equivalence/security gates pass.

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
| 7 | JavaScript and Java AST Extractors | 2 | 2-4 days | Implemented | Real JS/Java extraction |
| 8 | FETCH / Knowledge Context | 3 | 7-10 days | Implemented | Retrieved technical context |
| 9 | FUSION / Master Logic Stream | 3 | 5-7 days | Implemented | Cross-pod synthesis |
| 10 | DELIVERY / PM Verification | 3 | 4-5 days | Implemented | Delivery summary and criteria check |
| 11 | Application Intelligence Map | 3 | 5-7 days | Implemented | AIM artifact, UI, and risk flags |
| 12 | Equivalence Verification Harness | 4 | 7-10 days | Implemented | Real verification evidence |
| 13 | Security and Compliance Agents | 4 | 5-7 days | Implemented | Safety/compliance verdicts |
| 14 | Dependency Absorption Engine | 4 | 10-14 days | Implemented | Dependency inventory/classification and advisory plans |
| 15 | Token and Cost Ledger | 4 | 2-3 days | Planned | Per-mission LLM cost |
| 16 | Knowledge Lake Embeddings and Auto-Refresh | 5 | 7-10 days | Planned | Operational knowledge lake |
| 17 | DR Evidence and Release Hardening | 5 | 3-5 days | Planned | Recovery/release evidence |
| 18 | Reproducible Demo Missions and Launch Docs | 5 | 5-7 days | Planned | Launch-ready demo suite |

**Remaining estimate after Phase 9:** 43-66 days, excluding the live provider-key
demo and stale qualification-evidence refresh.

---

# Critical Path

Minimum path to a real working demo:

1. Complete a live provider-key BUILD_NEW demo through the implemented
   Phase 1-11 loop.
2. Phase 15 - add token and cost ledger for LLM-backed work.
3. Phase 17 - refresh stale qualification evidence before release claims.

Phases 1-14 now provide the first local/fallback proof of value: structured PM
and CEO contracts, FETCH context, FUSION synthesis, generated-output packaging,
PM delivery summaries, AIM source inventory, equivalence evidence, pod
standards, security/compliance verdicts, dependency inventory/classification,
advisory dependency absorption plans, and AST-backed Python/JavaScript/
TypeScript/Java extraction. The next proof point should be Phase 15 token/cost
ledgering, with a live LLM-backed demo mission run as soon as provider
credentials are available.

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
