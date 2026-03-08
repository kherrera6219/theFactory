# Updated TODO From Word-Doc Audit (2026-03-03)

Update (2026-03-08):
- Canonical mission-flow reconciliation published at `docs/MISSION_FLOW_V1_1_CANONICAL_2026-03-07.md`.
- Root Word artifact aligned via `HGR_Mission_Flow_v1_1.docx`.
- Additional implementation backlog (below) captures app changes required to enforce this flow at runtime.

## P0 - Mission-Flow Runtime Conformance (New)
- [ ] Enforce strict PM -> CEO mission routing with dedicated bindings.
Acceptance:
- Dedicated-agent runtime profile includes explicit binding enforcement for interface/executive chain (`AGENT-01-PM`, `AGENT-02-CEO`) and downstream pod manager routing.
- Mission intake metadata (`agent_id`/`selected_agent_id`) is validated and scheduler-tested for deterministic routing.
- Mission Control clearly shows the enforced chain per mission.

- [ ] Resolve internal service-key mismatch between pod workers and orchestrator internal mutation routes.
Acceptance:
- All pod workers can authenticate to orchestrator internal mutation endpoints with configured service keys.
- Pod assignment and LogicNode persistence succeed during live mission runs.
- Health/operations surfaces include explicit signal when internal auth mismatch blocks worker writes.

- [ ] Add mission completion integrity guardrails.
Acceptance:
- Mission cannot auto-transition to `COMPLETE` if required execution artifacts are missing (for example, zero pod assignments and zero LogicNodes) unless explicitly policy-exempt.
- Alert/event emitted when lifecycle progression is blocked by missing artifact criteria.

## P1 - High Impact Product Gaps (New)
- [ ] Add end-to-end tests proving real execution artifacts for dedicated and shared topologies.
Acceptance:
- Integration tests validate non-zero pod assignments and LogicNode/audit evidence before completion on representative missions.
- Tests cover both default condensed workers and `--profile dedicated-agents`.

- [ ] Add runtime diagnostics for chain-of-command visibility.
Acceptance:
- Operations API exposes per-mission chain trace (PM intake, CEO delegation, pod manager assignment, audit checkpoints).
- Mission Control mission detail shows the same chain deterministically from emitted events.

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
- [ ] Frontend GAP-* remediation reconciliation (`HolyGrail_Frontend_Design_3.docx` sections 9-12).
Acceptance:
- Accessibility, performance, and frontend security controls are mapped to implemented tests and runbooks.

- [ ] Compliance evidence automation expansion (SOC2/CMMC checklist mapping).
Acceptance:
- Existing audit scripts include machine-readable evidence collection for mapped controls.

## Completed During This Iteration
- [x] Phase 23: LangGraph lifecycle baseline (feature-flagged, fail-open fallback).
- [x] Phase 24: Postgres checkpointer baseline for LangGraph lifecycle.
- [x] Phase 25: Word-doc reconciliation and LangGraph runtime visibility in health/readiness/operations.
- [x] Phase 26: Lifecycle recovery rehydration and live postgres checkpoint restart qualification.
- [x] Phase 27: Mission Control live transport baseline with SSE + fallback validation.
- [x] Phase 28: Smelt-cycle runtime reconciliation with deterministic 7-phase timeline mapping.
- [x] Phase 29: 35-agent topology + security-model ADR decision package.
