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

- [x] Run long-duration load/resilience qualification and publish capacity baselines.
Acceptance: soak/failure scenarios are executed, thresholds documented, and remediation actions tracked.
Evidence targets: `docs/GAP_ANALYSIS.md`, `docs/PRODUCTION_PHASE_PLAN.md`.
Phase 10 status (2026-03-03): sustained-load reliability qualification baseline executed with injected orchestrator restart and recovery verification; evidence stored at `docs/evidence/reliability_qualification_baseline_2026-03-03.json`.

- [x] Add migration framework for schema evolution (versioned migrations + rollback path).
Acceptance: schema changes are migration-based, reproducible, and tested on clean + upgraded databases.
Evidence targets: `services/orchestrator/orchestrator/storage.py`, `tests/services/test_storage_unit.py`.
Phase 1 status (2026-03-02): implemented with versioned SQL migrations + checksum tracking in `schema_migrations`.

- [x] Establish Mission Control automated tests (unit + integration + critical e2e).
Acceptance: CI executes UI tests for mission lifecycle, operations views, settings/vault, and error states.
Evidence targets: `apps/mission-control/package.json`, `docs/TESTING_QUALITY_GATES.md`.
Phase 11 status (2026-03-03): Playwright e2e suite added for mission lifecycle, operations views, settings/vault, and error-state regression flows; CI now runs `npm run test:e2e` after Playwright browser install.

## P1 - Important Hardening and Completeness
- [x] Replace placeholder builder preview UX with functional diff/preview rendering.
Acceptance: builder output is visualized with concrete change preview behavior.
Evidence targets: `apps/mission-control/app/(shell)/builder/page.tsx`.
Phase 12 status (2026-03-03): builder workspace now renders concrete file-impact cards and unified diff previews inferred from live preview-plan signals; covered by Playwright regression.

- [x] Convert repo import simulation into real Git provider integration flow.
Acceptance: live repository ingestion path with robust error handling replaces sample-file simulation.
Evidence targets: `apps/mission-control/app/(shell)/repo/page.tsx`.
Phase 12 status (2026-03-03): repository intake now calls `/api/repo/import` with GitHub metadata/tree integration, vault/env token support, input validation, file-size caps, and structured error handling; covered by Vitest + Playwright.

- [x] Add integration tests using real dependencies (Redis/Postgres/service wiring) for mission intake and state flow.
Acceptance: at least one full mission path is validated without mocked data-plane backends.
Evidence targets: `tests/services/`, `coverage.xml`.
Phase 15 status (2026-03-03): added `tests/services/test_live_mission_flow_integration.py` to validate live gateway/orchestrator readiness plus mission intake/state/event progression against real Redis/Postgres-backed runtime when stack is available.

- [x] Add automated validation for critical operational scripts (backup/DR/perf/audit).
Acceptance: script regressions are detected by CI smoke tests.
Evidence targets: `scripts/`, `.github/workflows/ci.yml`.
Phase 5-6 status (2026-03-02): unit coverage added for `scripts/production_review_audit.py` and `scripts/perf_smoke.py`; backup/DR script test coverage was pending.
Phase 13 status (2026-03-03): backup and DR scripts now support `-DryRun` regression paths with CI-testable PowerShell execution coverage in `tests/scripts/test_backup_dr_scripts.py`.

- [x] Complete data-system roadmap activation/reconciliation (Qdrant active path, Neo4j/object-storage scope decision).
Acceptance: either implemented with tests or formally deferred with documented rationale.
Evidence targets: `docs/AGENT_SEMANTIC_BUS_DATA_SYSTEMS_PLAN.md`, `docs/ROADMAP.md`.
Phase 16 status (2026-03-03): orchestrator knowledge path now actively mirrors/retrieves via Qdrant with tested fallback behavior, runtime readiness visibility, and optional `QDRANT_API_KEY` hardening; Neo4j/object-storage tracks are formally deferred as optional expansion scopes.

## P2 - Documentation and Strategy Alignment
- [x] Resolve documentation port/runtime contradictions for Mission Control.
Acceptance: `README.md`, design docs, compose/env defaults all agree on launch URL/port.
Phase 4 status (2026-03-02): canonical README now documents both valid modes (Docker host `3100`, direct Next dev `3000`); remaining work was updating legacy/design artifacts still phrased as a single-port assumption.
Phase 14 status (2026-03-03): canonical runtime port policy is now explicitly reconciled in `docs/LEGACY_ROADMAP_RECONCILIATION_2026-03-03.md` and linked from canonical roadmap/index docs.

- [x] Publish explicit legacy-roadmap reconciliation note.
Acceptance: legacy advanced goals are marked as adopted, deferred, or deprecated in canonical docs.
Evidence targets: `legacy documentation/04_Product_Roadmap_Phasing_Strategy.md`, `docs/ROADMAP.md`.
Phase 14 status (2026-03-03): published explicit disposition matrix in `docs/LEGACY_ROADMAP_RECONCILIATION_2026-03-03.md` and aligned roadmap references.

## Suggested Execution Order
1. Finish all P0 items.
2. Complete remaining P1 data-system activation/reconciliation work.
3. Re-run full audit and evidence refresh for final completion sign-off.

## Exit Criteria
- [x] All P0 acceptance criteria passed and documented.
- [x] At least 80% service coverage maintained with critical-module thresholds intact.
Current verified baseline (2026-03-03): 86.75% global coverage, all required 100% module thresholds passing.
- [x] Mission Control has automated regression protection for core operator journeys.
- [x] Updated audit report confirms no remaining critical production blockers.
