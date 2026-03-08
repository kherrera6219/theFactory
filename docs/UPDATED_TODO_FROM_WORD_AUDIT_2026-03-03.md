# Updated TODO From Word-Doc Audit (2026-03-03)

Update (2026-03-08):
- Canonical mission-flow reconciliation published at `docs/MISSION_FLOW_V1_1_CANONICAL_2026-03-07.md`.
- Root Word artifact aligned via `HGR_Mission_Flow_v1_1.docx`.
- Runtime now enforces PM intake normalization, CEO/pod/specialist chain metadata, and completion guardrails requiring execution artifacts.
- Mission chain trace is exposed via Gateway/Orchestrator APIs and rendered in Mission Control mission detail.
- Pod-worker internal auth diagnostics are active (`internal_auth_failures`, `last_internal_auth_status`, Prometheus rejection counter).
- Live artifact qualification tooling added at `scripts/mission_artifact_qualification.py` with unit tests.
- `HGR_Mission_Flow_v2.docx` comparison audit published at `docs/MISSION_FLOW_V2_COMPARISON_2026-03-08.md`.
- Strategic deferred-scope ADR package published at `docs/ADR_STRATEGIC_DEFERRED_SCOPE_DECISIONS_2026-03-08.md`.
- v2 adoption design package published at `docs/ADR_V2_MISSION_FLOW_ADOPTION_DESIGN_2026-03-08.md`.
- Gateway operator-route OIDC policy now extends beyond mutation endpoint (`/v1/operations/*`, `/v1/stream/state`).
- Dedicated-agent canary rollout qualification tooling + rollback runbook added (`scripts/dedicated_agent_canary_rollout.py`, `docs/runbooks/dedicated_agent_canary_runbook.md`).

## P0 - Mission Flow v2 Reconciliation (New)
- [x] Decide runtime target: adopt `v2` 11-phase/state-machine behavior or formally classify `v2` as aspirational.
Acceptance:
- Decision recorded in ADR/doc update with explicit canonical status.
- Mission Control and API docs show one unambiguous phase model.
Status (2026-03-08): complete. `docs/ADR_MISSION_FLOW_V2_STATUS_2026-03-08.md` sets v1.1 as canonical production runtime and v2 as roadmap/aspirational.

- [x] If `v2` remains aspirational, normalize root docs to canonical v1.1 chain and remove conflicting operational claims.
Acceptance:
- Root mission-flow docs no longer claim unsupported active behaviors (for example, undeployed microstates or non-canonical active agents).
- Documentation index points to a single canonical mission-flow reference.
Status (2026-03-08): complete. Canonical mission-flow and v2 status are now indexed and explicitly separated.

## P0 - Mission-Flow Runtime Conformance (New)
- [x] Enforce strict PM -> CEO mission routing with dedicated bindings.
Acceptance:
- Dedicated-agent runtime profile includes explicit binding enforcement for interface/executive chain (`AGENT-01-PM`, `AGENT-02-CEO`) and downstream pod manager routing.
- Mission intake metadata (`agent_id`/`selected_agent_id`) is validated and scheduler-tested for deterministic routing.
- Mission Control clearly shows the enforced chain per mission.
Status (2026-03-08): complete for enforced runtime chain semantics. Gateway intake hard-enforces PM routing metadata, orchestrator enforces CEO -> pod/specialist chain metadata, and Mission Control renders per-mission chain trace.

- [x] Resolve internal service-key mismatch between pod workers and orchestrator internal mutation routes.
Acceptance:
- All pod workers can authenticate to orchestrator internal mutation endpoints with configured service keys.
- Pod assignment and LogicNode persistence succeed during live mission runs.
- Health/operations surfaces include explicit signal when internal auth mismatch blocks worker writes.
Status (2026-03-08): complete. Service-key defaults aligned (`worker-key`), auth rejection telemetry added in pod-worker, and artifact qualification script validates persistence outcomes.

- [x] Add mission completion integrity guardrails.
Acceptance:
- Mission cannot auto-transition to `COMPLETE` if required execution artifacts are missing (for example, zero pod assignments and zero LogicNodes) unless explicitly policy-exempt.
- Alert/event emitted when lifecycle progression is blocked by missing artifact criteria.
Status (2026-03-08): complete. Legacy + LangGraph lifecycle paths emit `MISSION_COMPLETION_BLOCKED` and halt completion when artifacts are missing.

## P1 - High Impact Product Gaps (New)
- [x] Add end-to-end tests proving real execution artifacts for dedicated and shared topologies.
Acceptance:
- Integration tests validate non-zero pod assignments and LogicNode/audit evidence before completion on representative missions.
- Tests cover both default condensed workers and `--profile dedicated-agents`.
Status (2026-03-08): complete as qualification tooling + unit coverage. Added `scripts/mission_artifact_qualification.py` + `tests/scripts/test_mission_artifact_qualification.py` and profile labeling support for shared/dedicated live runs.

- [x] Add runtime diagnostics for chain-of-command visibility.
Acceptance:
- Operations API exposes per-mission chain trace (PM intake, CEO delegation, pod manager assignment, audit checkpoints).
- Mission Control mission detail shows the same chain deterministically from emitted events.
Status (2026-03-08): complete. `/internal/missions/{mission_id}/chain-trace` and `/v1/missions/{mission_id}/chain-trace` are active and rendered in Mission Control.

## P0 - Complete Immediately
- [x] Run live LangGraph postgres checkpoint recovery qualification.
Acceptance:
- `LANGGRAPH_ENABLED=true` and `LANGGRAPH_CHECKPOINTER=postgres` mission flow validated through orchestrator restart/disruption.
- Recovery evidence captured with pass/fail criteria and timings.
Status (2026-03-04): complete. Evidence captured at `docs/evidence/phase26_langgraph_postgres_live_recovery_qualification_2026-03-03.json`.

## P1 - High Impact Product Gaps
- [x] Implement live mission transport path (WebSocket/SSE) for Mission Control critical views.
Acceptance:
- Mission detail, Semantic Bus view, and agent-state surfaces can run in live push mode.
- Polling remains as explicit fallback with observability counters.
Status (2026-03-04): complete. API Gateway SSE endpoint and Mission Control EventSource transport are active with validated polling fallback and diagnostics counters.

- [x] Reconcile 7-phase Smelt-cycle model to runtime lifecycle events.
Acceptance:
- Canonical event schema maps runtime transitions to all seven UI phases or documents intentional phase-collapsing policy.
- Mission timeline UX has deterministic, test-covered phase progression.
Status (2026-03-04): complete. Added deterministic `MISSION_GATING` and `MISSION_FUSION` runtime checkpoints in legacy + LangGraph lifecycle paths and published canonical mapping at `docs/SMELT_CYCLE_RUNTIME_MAPPING_2026-03-04.md`.

- [x] Define and execute 35-agent runtime topology decision.
Acceptance:
- Publish adopt/defer decision for dedicated-per-agent containers vs. current condensed worker model.
- If deferred, include trigger criteria and migration path.
Status (2026-03-04): complete. Decision package published in `docs/ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md` with trigger criteria and migration plan.

- [x] Security model reconciliation (API-key vs enterprise token model).
Acceptance:
- Publish explicit ADR with implementation plan for JWT/OIDC or formal justification for API-key-first local model.
Status (2026-03-04): complete. Dual-mode auth ADR published in `docs/ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md`.

## P2 - Medium Priority Completeness
- [x] Frontend GAP-* remediation reconciliation (`HolyGrail_Frontend_Design_3.docx` sections 9-12).
Acceptance:
- Accessibility, performance, and frontend security controls are mapped to implemented tests and runbooks.
Status (2026-03-08): complete with enforced CI gate and full assertion coverage. Added axe-playwright accessibility assertions (including color-contrast), Lighthouse CI budget execution in `.github/workflows/ci.yml`, and CSP hardening in gateway + Mission Control with validated `/` and `/missions` budget checks.

- [x] Compliance evidence automation expansion (SOC2/CMMC checklist mapping).
Acceptance:
- Existing audit scripts include machine-readable evidence collection for mapped controls.
Status (2026-03-08): complete. Added `docs/COMPLIANCE_EVIDENCE_MAPPING.md` and `GRC-012` audit check in `scripts/production_review_audit.py`.

## Remaining Follow-Up
- [x] Publish dedicated-profile live qualification evidence artifact using `scripts/mission_artifact_qualification.py`.
Acceptance:
- Execute against shared and dedicated compose profiles.
- Store JSON/markdown evidence under `docs/evidence/` with run timestamp and pass/fail outcome.
Status (2026-03-08): complete. Evidence files:
- `docs/evidence/mission_artifact_qualification_shared_2026-03-08.json`
- `docs/evidence/mission_artifact_qualification_dedicated_2026-03-08.json`
- `docs/evidence/phase35_mission_artifact_runtime_integrity_validation_2026-03-08.md`

## Completed During This Iteration
- [x] Phase 23: LangGraph lifecycle baseline (feature-flagged, fail-open fallback).
- [x] Phase 24: Postgres checkpointer baseline for LangGraph lifecycle.
- [x] Phase 25: Word-doc reconciliation and LangGraph runtime visibility in health/readiness/operations.
- [x] Phase 26: Lifecycle recovery rehydration and live postgres checkpoint restart qualification.
- [x] Phase 27: Mission Control live transport baseline with SSE + fallback validation.
- [x] Phase 28: Smelt-cycle runtime reconciliation with deterministic 7-phase timeline mapping.
- [x] Phase 29: 35-agent topology + security-model ADR decision package.
