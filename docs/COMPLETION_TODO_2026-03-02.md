# theFactory Completion TODO (2026-03-02)

## Goal
Reach a defensible **100% production-ready** state based on current canonical documentation and implementation audit.

## P0 - Production Readiness Blockers
- [x] Enforce signed release attestations and promotion gates in CI/CD.
Acceptance: release artifacts are signed, attested, and promotion is blocked without verification.
Evidence targets: `docs/GAP_ANALYSIS.md`, `docs/PRODUCTION_PHASE_PLAN.md`, `docs/PRODUCTION_REVIEW_AUDIT.md`.
Phase 7 status (2026-03-03): CI release-trust job now generates/verifies provenance attestation and enforces fail-closed promotion policy.

- [x] Implement end-to-end distributed tracing plus alert-to-pager/on-call routing.
Acceptance: traces correlate gateway/orchestrator/workers, alert routes are tested, and runbooks updated.
Evidence targets: `docs/ROADMAP.md`, `docs/OBSERVABILITY_STACK.md`, `docs/OPERATIONS_RUNBOOK.md`.
Phase 8 status (2026-03-03): OpenTelemetry tracing baseline enabled for gateway/orchestrator with Jaeger OTLP export, Alertmanager pager routing configured via `PAGER_WEBHOOK_URL`, and audit control `OBS-009` added.

- [ ] Run long-duration load/resilience qualification and publish capacity baselines.
Acceptance: soak/failure scenarios are executed, thresholds documented, and remediation actions tracked.
Evidence targets: `docs/GAP_ANALYSIS.md`, `docs/PRODUCTION_PHASE_PLAN.md`.

- [x] Add migration framework for schema evolution (versioned migrations + rollback path).
Acceptance: schema changes are migration-based, reproducible, and tested on clean + upgraded databases.
Evidence targets: `services/orchestrator/orchestrator/storage.py`, `tests/services/test_storage_unit.py`.
Phase 1 status (2026-03-02): implemented with versioned SQL migrations + checksum tracking in `schema_migrations`.

- [ ] Establish Mission Control automated tests (unit + integration + critical e2e).
Acceptance: CI executes UI tests for mission lifecycle, operations views, settings/vault, and error states.
Evidence targets: `apps/mission-control/package.json`, `docs/TESTING_QUALITY_GATES.md`.
Phase 2-3 status (2026-03-02): baseline unit test harness added with Vitest and API client tests, and CI now runs Mission Control lint + unit tests; integration/e2e coverage still pending.

## P1 - Important Hardening and Completeness
- [ ] Replace placeholder builder preview UX with functional diff/preview rendering.
Acceptance: builder output is visualized with concrete change preview behavior.
Evidence targets: `apps/mission-control/app/(shell)/builder/page.tsx`.

- [ ] Convert repo import simulation into real Git provider integration flow.
Acceptance: live repository ingestion path with robust error handling replaces sample-file simulation.
Evidence targets: `apps/mission-control/app/(shell)/repo/page.tsx`.

- [ ] Add integration tests using real dependencies (Redis/Postgres/service wiring) for mission intake and state flow.
Acceptance: at least one full mission path is validated without mocked data-plane backends.
Evidence targets: `tests/services/`, `coverage.xml`.

- [ ] Add automated validation for critical operational scripts (backup/DR/perf/audit).
Acceptance: script regressions are detected by CI smoke tests.
Evidence targets: `scripts/`, `.github/workflows/ci.yml`.
Phase 5-6 status (2026-03-02): unit coverage added for `scripts/production_review_audit.py` and `scripts/perf_smoke.py`; backup/DR script test coverage is still pending.

- [ ] Complete data-system roadmap activation/reconciliation (Qdrant active path, Neo4j/object-storage scope decision).
Acceptance: either implemented with tests or formally deferred with documented rationale.
Evidence targets: `docs/AGENT_SEMANTIC_BUS_DATA_SYSTEMS_PLAN.md`, `docs/ROADMAP.md`.

## P2 - Documentation and Strategy Alignment
- [ ] Resolve documentation port/runtime contradictions for Mission Control.
Acceptance: `README.md`, design docs, compose/env defaults all agree on launch URL/port.
Phase 4 status (2026-03-02): canonical README now documents both valid modes (Docker host `3100`, direct Next dev `3000`); remaining work is updating any legacy/design artifacts still phrased as a single-port assumption.

- [ ] Publish explicit legacy-roadmap reconciliation note.
Acceptance: legacy advanced goals are marked as adopted, deferred, or deprecated in canonical docs.
Evidence targets: `legacy documentation/04_Product_Roadmap_Phasing_Strategy.md`, `docs/ROADMAP.md`.

## Suggested Execution Order
1. Finish all P0 items.
2. Parallelize P1 UI completion and integration-testing improvements.
3. Close P2 documentation/strategy cleanup after P0/P1 decisions are made.

## Exit Criteria
- [ ] All P0 acceptance criteria passed and documented.
- [x] At least 80% service coverage maintained with critical-module thresholds intact.
Current verified baseline (2026-03-02): 88.13% global coverage, all required 100% module thresholds passing.
- [ ] Mission Control has automated regression protection for core operator journeys.
- [ ] Updated audit report confirms no remaining critical production blockers.
