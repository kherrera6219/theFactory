# Updated TODO From Word-Doc Audit (2026-03-03)

## P0 - Complete Immediately
- [x] Run live LangGraph postgres checkpoint recovery qualification.
Acceptance:
- `LANGGRAPH_ENABLED=true` and `LANGGRAPH_CHECKPOINTER=postgres` mission flow validated through orchestrator restart/disruption.
- Recovery evidence captured with pass/fail criteria and timings.
Status (2026-03-04): complete. Evidence captured at `docs/evidence/phase26_langgraph_postgres_live_recovery_qualification_2026-03-03.json`.

## P1 - High Impact Product Gaps
- [ ] Implement live mission transport path (WebSocket/SSE) for Mission Control critical views.
Acceptance:
- Mission detail, Semantic Bus view, and agent-state surfaces can run in live push mode.
- Polling remains as explicit fallback with observability counters.

- [ ] Reconcile 7-phase Smelt-cycle model to runtime lifecycle events.
Acceptance:
- Canonical event schema maps runtime transitions to all seven UI phases or documents intentional phase-collapsing policy.
- Mission timeline UX has deterministic, test-covered phase progression.

- [ ] Define and execute 35-agent runtime topology decision.
Acceptance:
- Publish adopt/defer decision for dedicated-per-agent containers vs. current condensed worker model.
- If deferred, include trigger criteria and migration path.

- [ ] Security model reconciliation (API-key vs enterprise token model).
Acceptance:
- Publish explicit ADR with implementation plan for JWT/OIDC or formal justification for API-key-first local model.

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
