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
Phase 16 status (2026-03-03): orchestrator knowledge path now actively mirrors/retrieves via Qdrant with tested fallback behavior, runtime readiness visibility, and optional `QDRANT_API_KEY` hardening.
Phase 17-18 status (2026-03-03): Neo4j and object-storage optional expansion tracks are now implemented behind feature flags with regression coverage and evidence (`phase17_neo4j_feature_flag_validation_2026-03-03.md`, `phase18_object_storage_validation_2026-03-03.md`).

- [x] Implement live mission transport path (WebSocket/SSE) for mission-critical Mission Control surfaces.
Acceptance: Mission detail, Semantic Bus, and agent-state operations views support push transport with deterministic polling fallback.
Evidence targets: `services/api-gateway/api_gateway/main.py`, `apps/mission-control/app/(shell)/missions/[id]/page.tsx`, `docs/evidence/phase27_mission_control_live_transport_validation_2026-03-04.md`.
Phase 27 status (2026-03-04): complete. Added SSE stream endpoint plus EventSource transport integration and fallback diagnostics.

- [x] Reconcile 7-phase Smelt-cycle model to runtime lifecycle events with deterministic timeline mapping.
Acceptance: canonical runtime telemetry supports 7-phase Mission Control progression with test-covered deterministic mapping.
Evidence targets: `services/orchestrator/orchestrator/runtime.py`, `services/orchestrator/orchestrator/langgraph_lifecycle.py`, `apps/mission-control/app/lib/smelt-cycle.ts`, `docs/SMELT_CYCLE_RUNTIME_MAPPING_2026-03-04.md`.
Phase 28 status (2026-03-04): complete. Added runtime checkpoint events (`MISSION_GATING`, `MISSION_FUSION`) and deterministic timeline rendering in Mission Control.

- [x] Define and publish 35-agent runtime topology decision (condensed vs dedicated-per-agent execution model).
Acceptance: adopt/defer decision, trigger criteria, and migration path are documented in canonical ADR form.
Evidence targets: `docs/ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md`, `docs/ROADMAP.md`.
Phase 29 status (2026-03-04): complete. Hybrid strategy accepted (condensed baseline + trigger-based dedicated expansion path).

- [x] Publish security-model ADR for API-key baseline versus JWT/OIDC enterprise architecture.
Acceptance: explicit decision and implementation path are documented with backward-compatible rollout policy.
Evidence targets: `docs/ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md`, `docs/API_INTEGRATION_GUIDE.md`.
Phase 29 status (2026-03-04): complete. Dual-mode auth strategy accepted (`api_key`, `hybrid`, `oidc`) with enterprise rollout plan.

- [x] Implement ADR execution baseline for security and topology decisions.
Acceptance: gateway `AUTH_MODE` (`api_key|hybrid|oidc`) is implemented with regression coverage and dedicated-agent compose profile scaffolding exists for trigger-based expansion.
Evidence targets: `services/api-gateway/api_gateway/main.py`, `tests/services/test_api_gateway_auth_mode_unit.py`, `deploy/docker-compose.yaml`.
Phase 30 status (2026-03-04): complete. Added gateway auth abstraction plus `--profile dedicated-agents` manager-worker scaffolding.

- [x] Enforce dedicated-agent scheduler routing policy for `AGENT_BINDING` workers.
Acceptance: pod-worker runtime gates dedicated workers to configured agent IDs with regression coverage and runtime telemetry.
Evidence targets: `services/pod-worker/pod_worker/main.py`, `tests/services/test_pod_worker_unit.py`, `docs/evidence/phase31_dedicated_agent_binding_scheduler_validation_2026-03-04.md`.
Phase 31 status (2026-03-04): complete. `AGENT_BINDING` routing policy is enforced with mission metadata fallback resolution and validated quality gates.

- [x] Add optional data-plane observability and SLO controls for Neo4j/object-storage adapters.
Acceptance: readiness, operation latency/error, and mirror-write success/failure telemetry are emitted; alerting and runbook mapping are in place.
Evidence targets: `services/orchestrator/orchestrator/data_plane_metrics.py`, `deploy/monitoring/prometheus/rules/thefactory-alerts.yml`, `docs/runbooks/optional_data_plane_incident_runbook.md`, `docs/evidence/phase32_optional_data_plane_observability_validation_2026-03-04.md`.
Phase 32 status (2026-03-04): complete. Added adapter metrics instrumentation, Grafana/Prometheus observability controls, and incident runbook linkage.

- [x] Add live extended-data-plane qualification for optional Neo4j/object-storage paths.
Acceptance: live suite validates roundtrip mirror behavior and disruption recovery, while safely skipping when extended stack is unavailable.
Evidence targets: `tests/services/test_live_extended_data_plane_integration.py`, `deploy/docker-compose.yaml`, `docs/evidence/phase33_extended_data_plane_live_qualification_validation_2026-03-04.md`.
Phase 33 status (2026-03-04): complete. Added live roundtrip/disruption suite, `make test-live-extended`, and compose hardening fixes for MinIO image/healthcheck.

- [x] Adopt LangGraph mission lifecycle orchestration path with production-safe fallback.
Acceptance: orchestrator can execute mission state transitions through LangGraph when enabled, and fail-open fallback preserves runtime safety.
Evidence targets: `services/orchestrator/orchestrator/langgraph_lifecycle.py`, `tests/services/test_langgraph_lifecycle_unit.py`, `docs/UPDATED_PHASE_PLAN_2026-03-03.md`.
Phase 23 status (2026-03-03): implementation baseline added behind `LANGGRAPH_*` feature flags.
Phase 24 status (2026-03-03): postgres checkpointer baseline added (`LANGGRAPH_CHECKPOINTER=postgres`) with setup/idempotence controls and regression coverage.
Phase 26 status (2026-03-04): completed live restart/disruption qualification with postgres checkpoint persistence, added startup lifecycle rehydration, and published evidence at `docs/evidence/phase26_langgraph_postgres_live_recovery_qualification_2026-03-03.json`.

## P2 - Documentation and Strategy Alignment
- [x] Resolve documentation port/runtime contradictions for Mission Control.
Acceptance: `README.md`, design docs, compose/env defaults all agree on launch URL/port.
Phase 4 status (2026-03-02): canonical README now documents both valid modes (Docker host `3100`, direct Next dev `3000`); remaining work was updating legacy/design artifacts still phrased as a single-port assumption.
Phase 14 status (2026-03-03): canonical runtime port policy is now explicitly reconciled in `docs/LEGACY_ROADMAP_RECONCILIATION_2026-03-03.md` and linked from canonical roadmap/index docs.

- [x] Publish explicit legacy-roadmap reconciliation note.
Acceptance: legacy advanced goals are marked as adopted, deferred, or deprecated in canonical docs.
Evidence targets: `legacy documentation/04_Product_Roadmap_Phasing_Strategy.md`, `docs/ROADMAP.md`.
Phase 14 status (2026-03-03): published explicit disposition matrix in `docs/LEGACY_ROADMAP_RECONCILIATION_2026-03-03.md` and aligned roadmap references.

- [x] Reconcile in-repo Word-document requirements with canonical implementation backlog.
Acceptance: all `.docx` artifacts are audited and converted into an actionable prioritized TODO with explicit next phases.
Evidence targets: `docs/WORD_DOC_AUDIT_2026-03-03.md`, `docs/UPDATED_TODO_FROM_WORD_AUDIT_2026-03-03.md`.
Phase 25 status (2026-03-03): complete; remaining gaps promoted into canonical roadmap targets.

## Suggested Execution Order
1. Finish all P0 items.
2. Complete remaining P1 data-system activation/reconciliation work.
3. Re-run full audit and evidence refresh for final completion sign-off.

## Exit Criteria
- [x] All P0 acceptance criteria passed and documented.
- [x] At least 80% service coverage maintained with critical-module thresholds intact.
Current verified baseline (2026-03-04): 86.00% global coverage, all required 100% module thresholds passing.
- [x] Mission Control has automated regression protection for core operator journeys.
- [x] Updated audit report confirms no remaining critical production blockers.
