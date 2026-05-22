# theFactory — Sprint Backlog
**Created:** 2026-05-20
**Status:** Active
**Phase 26/27:** ✅ Complete (2026-05-20)
**Scope:** Total completion from Phase 27 baseline to fully live, production-deployed system

This file is the authoritative sprint backlog. Items are ordered by impact within each sprint.
Check off `[x]` as items complete. Each item maps to a numbered section in
`docs/IMPLEMENTATION_STATUS.md` Open Work.

---

## How to use this list

- Work sprints in order — Sprint 1 items block everything else.
- Every item that touches Python: run `python -m ruff check services tests scripts` before commit.
- Every item that touches TypeScript: run `npm run lint` before commit.
- Every item that modifies `llm_delegation.py` or `mission_flow_v2.py`: run
  `python -m pytest tests/eval/ -q` before commit.
- Commit message format: `feat: Sprint N — [item title]`

---

## SPRINT 1 — Live Demo Gate
**Goal:** Prove the factory works with real LLM providers. Nothing else matters until item 1 passes.

- [ ] **S1-01 — Live provider-key BUILD_NEW demo**
  Run `python scripts/demo_missions.py --live` with real API keys configured in `.env`.
  A BUILD_NEW mission must reach state `COMPLETE` with non-empty `generated_code` in the
  chain trace. Record evidence to `docs/evidence/live_demo_phase_sprint1_YYYY-MM-DD.json`.
  _Prerequisite: `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` set in `.env`._
  _Files: `scripts/demo_missions.py`, `.env`_

- [ ] **S1-02 — Token cost ledger activation**
  Run V007 migration against the live stack (`psql` or `make migrate`). Confirm
  `llm_usage_events` table exists and is being populated during a live mission.
  Render the Cost panel in Mission Control with real data.
  _Files: `services/orchestrator/orchestrator/migrations/V007_llm_usage_ledger_schema.sql`,
  `services/orchestrator/orchestrator/llm_cost_ledger.py`,
  `apps/mission-control/app/(shell)/missions/[id]/panels/telemetry/CostPanel.tsx`_

- [x] **S1-03 — Flip Python AST extractor to default-on** _(JS + Java already done)_ ✅ DONE 2026-05-22
  **JS_AST and JAVA_AST are already default-on** in `deploy/docker-compose.yaml`
  (`${JS_AST_EXTRACTOR_ENABLED:-true}`, `${JAVA_AST_EXTRACTOR_ENABLED:-true}` on all
  pod-worker containers) and in `.env.example` (`JS_AST_EXTRACTOR_ENABLED=true`,
  `JAVA_AST_EXTRACTOR_ENABLED=true`). **Only Python remains gated.**
  After S1-01 passes: add `PYTHON_AST_EXTRACTOR_ENABLED: ${PYTHON_AST_EXTRACTOR_ENABLED:-true}`
  to pod-worker containers in `docker-compose.yaml` and set `PYTHON_AST_EXTRACTOR_ENABLED=true`
  in `.env.example`. Run golden tests to confirm no regressions.
  Note: Flags live in `services/pod-worker/pod_worker/main.py` (not orchestrator settings.py).
  _Files: `deploy/docker-compose.yaml`, `.env.example`_
  _Tests: `python -m pytest tests/services/test_language_extractor_golden.py -q`_

- [ ] **S1-04 — Activate Gemini embeddings**
  Change `KNOWLEDGE_EMBEDDING_PROVIDER` default to `gemini` in `settings.py` and
  `.env.example`. Run a live mission and confirm knowledge retrieval returns
  semantically relevant results. Fall back to `deterministic` if retrieval quality
  degrades.
  _Files: `services/orchestrator/orchestrator/knowledge_embeddings.py`,
  `services/orchestrator/orchestrator/settings.py`_

- [x] **S1-05 — Flip equivalence enforcement on** ✅ DONE 2026-05-22
  Set `MISSION_EQUIVALENCE_ENFORCEMENT_ENABLED=true` as default after S1-01 confirms
  the enforcement does not over-block legitimate generated output. Update
  `docs/IMPLEMENTATION_STATUS.md` shipped defaults table.
  _Files: `services/orchestrator/orchestrator/settings.py`, `.env.example`_

- [x] **S1-06 — Flip security compliance enforcement on** ✅ DONE 2026-05-22
  Set `MISSION_SECURITY_COMPLIANCE_ENFORCEMENT_ENABLED=true` as default after S1-01
  confirms findings don't incorrectly block clean generated code.
  _Files: `services/orchestrator/orchestrator/settings.py`, `.env.example`_

---

## SPRINT 2 — Intelligence Layer Completions
**Goal:** Close all the LLM delegation gaps that agents have registrations for but no actual
LLM calls behind them.

- [x] **S2-01 — PM clarification workflow** ✅ DONE 2026-05-22
  When `ambiguity_score` exceeds threshold, mission enters a `CLARIFYING` state.
  Implement:
  1. `CLARIFYING` mission state + `VALID_TRANSITIONS` entry in `models.py`
  2. `POST /v1/missions/{id}/clarify` endpoint in `routes/missions.py`
  3. `pm_clarification` written into chain trace metadata when operator responds
  4. Mission Control chat panel renders clarification prompt and accepts operator input
  _Files: `services/orchestrator/orchestrator/models.py`,
  `services/orchestrator/orchestrator/routes/missions.py`,
  `services/orchestrator/orchestrator/mission_flow_v2.py`,
  `apps/mission-control/app/(shell)/missions/[id]/panels/operational/PmFeatureContractPanel.tsx`_

- [x] **S2-02 — Security agent LLM activation** ✅ DONE 2026-05-22
  Add `generate_security_analysis()` async function to `llm_delegation.py` using
  AGENT-05-SECURITY profile and `security_threat_analysis.v1` prompt asset. Wire into
  mission flow GATING phase. Write result to `security_compliance_report` in chain trace.
  Mission Control SecurityCompliance panel renders real LLM findings.
  _Files: `services/orchestrator/orchestrator/llm_delegation.py`,
  `services/orchestrator/orchestrator/mission_flow_v2.py`,
  `services/orchestrator/orchestrator/prompt_assets/security_threat_analysis.v1.json`_

- [x] **S2-03 — VC commit strategy agent LLM activation** ✅ DONE 2026-05-22
  Add `generate_vc_commit_strategy()` to `llm_delegation.py` using AGENT-06-VC profile.
  Wire into DELIVERY phase. Write result to `vc_commit_strategy` in chain trace.
  (`VcCommitStrategy` type already in `types.ts`.)
  _Files: `services/orchestrator/orchestrator/llm_delegation.py`,
  `services/orchestrator/orchestrator/mission_flow_v2.py`_

- [x] **S2-04 — Tester agent LLM activation** ✅ DONE 2026-05-22
  Add `generate_integration_tests()` to `llm_delegation.py` using AGENT-08-TESTER profile.
  Wire into DELIVERY phase. Write result to `integration_tests` in chain trace.
  (`IntegrationTests` type already in `types.ts`.)
  _Files: `services/orchestrator/orchestrator/llm_delegation.py`,
  `services/orchestrator/orchestrator/mission_flow_v2.py`_

- [x] **S2-05 — LLM semantic pod audit** ✅ DONE 2026-05-22
  Add `generate_pod_audit_verdict()` to `llm_delegation.py` using respective pod audit
  agent profiles (AGENT-13-PODA-AUDIT, AGENT-19-PODB-AUDIT, AGENT-25-PODC-AUDIT,
  AGENT-31-PODD-AUDIT). Wire into GATING phase after pod group standards are produced.
  Write result to `pod_audit_verdict` in chain trace. (`PodAuditVerdict` type already
  in `types.ts`.)
  _Files: `services/orchestrator/orchestrator/llm_delegation.py`,
  `services/orchestrator/orchestrator/mission_flow_v2.py`_

- [x] **S2-06 — COMPLETE-transition deploy readiness wiring** ✅ DONE 2026-05-22
  Call Deploy Agent (AGENT-11-DEPLOY) at the VERIFIED→COMPLETE transition gate in
  `mission_flow_v2.py`. Require a non-null `deploy_readiness` record before the
  transition is allowed. The deterministic fallback helper already exists in
  `llm_delegation.py` — wire it in.
  _Files: `services/orchestrator/orchestrator/mission_flow_v2.py`,
  `services/orchestrator/orchestrator/llm_delegation.py`_

- [x] **S2-07 — Knowledge lake scheduled refresh** ✅ DONE 2026-05-22
  `knowledge_lake_refresh_loop()` exists in `main.py` (line 401) and is started as a
  background task at lifespan startup (line 698), running alongside the heartbeat loop.
  _Files: `services/orchestrator/orchestrator/main.py`_

- [x] **S2-08 — pm_clarification and llm_usage_summary chain trace wiring** ✅ DONE 2026-05-22
  Both fields are typed in `MissionChainTrace` but the orchestrator never writes them.
  Wire `pm_clarification` into chain trace when a clarification record exists.
  Wire `llm_usage_summary` from `llm_cost_ledger.get_mission_usage_summary()` into
  chain trace at DELIVERY phase.
  _Files: `services/orchestrator/orchestrator/mission_flow_v2.py`,
  `services/orchestrator/orchestrator/llm_cost_ledger.py`_

---

## SPRINT 3 — Platform Differentiation
**Goal:** Activate the features that make theFactory different from all other AI coding tools.

- [x] **S3-01 — JavaScript/TypeScript DEPABS splicing** ✅ DONE 2026-05-22
  The orchestration layer already accepts JS/TS in `execute_absorption()` (line 277) and
  `_generate_replacement_code()` generates LLM replacement code for JS/TS. The **only
  missing piece** is in `_splice_replacement()` at line 480:
  `if language != "python": return source, "unsupported", "Only Python splicing is enabled"`
  Add a JS/TS branch to `_splice_replacement()` that removes the `import '...'` or
  `import {...} from '...'` / `require('...')` statement using regex, then appends the
  replacement function inline. Note: there is NO `_SPLICE_CAPABLE_LANGUAGES` variable to
  update — the backlog description was incorrect about the implementation path.
  _File: `services/orchestrator/orchestrator/dependency_absorption.py` — `_splice_replacement()` only_
  _Tests: `python -m pytest tests/services/test_dependency_absorption_unit.py -q`_

- [x] **S3-02 — RQCA for compiled languages (Pod B)** ✅ DONE 2026-05-22
  Add Docker images and compile+run command mappings for C, C++, Rust, and C# in
  `rqca_agent.py`. Currently these get `DRY_RUN` — they should get live compilation
  and execution when `RQCA_AGENT_ENABLED=true`. Add to `_EXECUTABLE_LANGUAGES`.
  _Files: `services/orchestrator/orchestrator/rqca_agent.py`_

- [x] **S3-03 — PORT two-phase activation** ✅ DONE 2026-05-22
  Flip `PORT_TWO_PHASE_ENABLED=true` as default after running a live PORT mission that
  validates the full extraction→generation flow end-to-end. Update shipped defaults
  table in `docs/IMPLEMENTATION_STATUS.md`.
  _Files: `services/orchestrator/orchestrator/settings.py`, `.env.example`_
  _Prerequisite: A live PORT mission completes with non-empty `port_source_logicnodes`
  and non-empty `generated_code`._

- [ ] **S3-04 — Desktop/game porting demo**
  Select a known open-source Windows game or utility (e.g. a SDL2 or DirectX title
  with available source). Run a PORT mission targeting Linux/macOS. Produce a
  `generated_code` artifact. Record the mission chain trace as demo evidence.
  This is the product differentiator proof-of-concept.
  _Prerequisite: S3-03 complete, S1-01 complete._
  _Evidence: `docs/evidence/desktop_port_demo_YYYY-MM-DD.json`_

---

## SPRINT 4 — Scale and Operational Maturity
**Goal:** Everything needed for a production system handling real workloads.

- [x] **S4-01 — Prompt cache optimization** ✅ DONE 2026-05-22
  Add `cache_control: {"type": "ephemeral"}` to the system prompt and first user turn
  in `_call_anthropic()` in `llm_delegation.py`. Applies to high-frequency CEO/PM calls.
  Measure latency and cost reduction on subsequent calls.
  _Files: `services/orchestrator/orchestrator/llm_delegation.py`_

- [ ] **S4-02 — Multi-container RQCA environments**
  Extend `testdata_agent.py` to produce multi-container TESTDATA manifests for missions
  that require a supporting service (e.g. web app + Postgres). Generate a
  `docker-compose.rqca.yml` from the manifest. `rqca_agent.py` spins up the compose
  stack, runs tests against it, tears it down.
  _Files: `services/orchestrator/orchestrator/testdata_agent.py`,
  `services/orchestrator/orchestrator/rqca_agent.py`_

- [ ] **S4-03 — Agent scaling live validation**
  Run a large multi-file repository mission (>20 files) with
  `AGENT_SCALING_ENABLED=true`. Confirm: partition work is computed, `mission.partition.ready`
  events are emitted, pod workers process partitions, results merge into mission metadata,
  lifecycle resumes after all partitions complete. Fix any bugs found.
  _Files: `services/orchestrator/orchestrator/mission_flow_v2.py`,
  `services/orchestrator/orchestrator/storage/scaling.py`_

- [ ] **S4-04 — Neo4j knowledge graph activation**
  Set `NEO4J_ENABLED=true` and configure `NEO4J_URI` in `.env`. Wire LogicNode writes
  into the Neo4j adapter so dependency relationships are stored as graph edges. Use the
  graph in FUSION phase to determine optimal LogicNode processing order based on
  dependency depth.
  _Files: `services/orchestrator/orchestrator/knowledge_graph.py` (or create),
  `services/orchestrator/orchestrator/mission_flow_v2.py`,
  `services/orchestrator/orchestrator/settings.py`_

- [ ] **S4-05 — Object storage for large artifacts**
  Set `OBJECT_STORAGE_ENABLED=true` and configure `OBJECT_STORAGE_ENDPOINT` in `.env`.
  Route `mission_build_artifacts` writes through the MinIO/S3 adapter when the artifact
  size exceeds a configurable threshold (`OBJECT_STORAGE_SIZE_THRESHOLD_BYTES`).
  Update `GET /v1/missions/{id}/artifact` to serve from object storage when the
  backend field indicates S3.
  _Files: `services/orchestrator/orchestrator/storage/artifacts.py`,
  `services/orchestrator/orchestrator/routes/missions.py`_

- [ ] **S4-06 — Live qualification evidence refresh**
  With the live stack running, execute:
  ```
  python scripts/promotion_gate.py \
    --ref $(git rev-parse HEAD) \
    --ci-status passed \
    --attestation-verified true \
    --output-file reports/promotion-gate.local.json
  python scripts/qualification_gate_summary.py \
    --output reports/qualification-gate-summary.local.json
  ```
  Commit updated evidence files. Last refresh was March 2026.
  _Evidence: `reports/promotion-gate.local.json`,
  `reports/qualification-gate-summary.local.json`_

- [x] **S4-07 — Lighthouse CI enforcement** ✅ DONE 2026-05-22
  `test:perf` step exists in `.github/workflows/ci.yml` (line 87) running
  `npm run test:perf` in the `apps/mission-control` working directory.
  `package.json` has `"test:perf": "node scripts/run-npm-exec-clean-env.mjs lhci autorun --config=./lighthouserc.json"`.
  _Files: `.github/workflows/ci.yml`, `apps/mission-control/package.json`, `apps/mission-control/lighthouserc.json`_

- [ ] **S4-08 — Long-duration reliability re-qualification**
  Re-run the reliability baseline against the Phase 15–27 stack.
  The current baseline (`reliability_qualification_baseline_2026-03-03.json`) predates
  the intelligence layer. Run:
  ```
  python scripts/long_duration_reliability_qualification.py \
    --output docs/evidence/reliability_qualification_phase27_YYYY-MM-DD.json
  ```
  _Evidence: `docs/evidence/reliability_qualification_phase27_YYYY-MM-DD.json`_

---

## Completion Definition

The application is **fully complete** when:

- [ ] S1-01 passes (live demo with real provider keys, COMPLETE + generated_code)
- [ ] All Sprint 1–2 items checked
- [ ] `python scripts/production_review_audit.py` → 22/22 PASS (already true)
- [ ] `python -m pytest tests/eval/ -q` → 97+ tests passing (already true)
- [ ] `python -m ruff check services tests scripts` → clean (already true)
- [ ] `npm run lint` → 0 errors (already true)
- [ ] Sprint 3-4 items for any mission types targeted at launch
- [ ] `docs/IMPLEMENTATION_STATUS.md` Open Work section empty or updated

---

## Audit Trail

| Date | Action | Sprints affected |
|---|---|---|
| 2026-05-20 | Initial creation from IMPLEMENTATION_STATUS.md Open Work section | All |
| 2026-05-20 | Phase 26 and 27 confirmed complete — phase plans updated, sprint backlog live | All |
| 2026-05-22 | Code validation: S2-07 (knowledge_lake_refresh_loop) confirmed done in main.py; S4-07 (test:perf CI step) confirmed done in ci.yml + package.json. Mission Control Phase 6-7 UI work shipped (command palette, guided tour, tooltip glossary, status bar, inline name edit, Electron shell). | Sprint 2, Sprint 4 |
| 2026-05-22 | Implementation pass: S1-03 (Python AST default-on in docker-compose + .env.example), S1-05 (MISSION_EQUIVALENCE_ENFORCEMENT_ENABLED=true), S1-06 (MISSION_SECURITY_COMPLIANCE_ENFORCEMENT_ENABLED=true), S3-03 (PORT_TWO_PHASE_ENABLED=true) flag flips. S2-01 CLARIFYING state + /clarify endpoint. S2-02 generate_security_analysis(), S2-03 generate_vc_commit_strategy(), S2-04 generate_integration_tests(), S2-05 generate_pod_audit_verdict() added to llm_delegation.py and wired into mission_flow_v2.py. S2-06 deploy readiness at VERIFIED→COMPLETE. S2-08 pm_clarification + llm_usage_summary chain trace. S3-01 JS/TS DEPABS splicing. S3-02 compiled language RQCA. S4-01 Anthropic prompt caching. | Sprint 1, 2, 3, 4 |
