# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased]

### Added
- Versioned orchestrator migration framework:
  - `services/orchestrator/orchestrator/migrations.py`
  - `services/orchestrator/orchestrator/migrations/V001_initial_runtime_schema.sql`
  - checksum-tracked `schema_migrations` table enforcement
- Mission Control frontend unit test baseline:
  - Vitest + jsdom test tooling in `apps/mission-control`
  - initial API client tests in `apps/mission-control/app/lib/api-client.test.ts`
- Release trust and promotion controls:
  - promotion policy in `deploy/promotion-policy.json`
  - policy evaluator in `scripts/promotion_gate.py`
  - CI release-trust job with provenance attestation and verification
  - release trust documentation in `docs/RELEASE_TRUST_PROMOTION_GATE.md`
- Long-duration reliability qualification tooling:
  - `scripts/reliability_qualification.py`
  - `scripts/reliability_qualification.ps1`
  - baseline evidence in `docs/evidence/reliability_qualification_baseline_2026-03-03.json`
  - reliability runbook in `docs/LONG_DURATION_RELIABILITY_QUALIFICATION.md`
- Mission Control e2e regression tooling:
  - Playwright config in `apps/mission-control/playwright.config.ts`
  - critical-path e2e suite in `apps/mission-control/e2e/mission-control.spec.ts`
- Semantic Bus MCP service (`services/semantic-bus-mcp`) with:
  - six-protocol payload validation (alpha/beta/delta/sigma/omega/rho)
  - `/send`, `/health`, `/readyz`, `/metrics`, and `/dlq` endpoints
  - payload size enforcement and sender identity checks
- Infrastructure hardening updates in `deploy/docker-compose.yaml`:
  - restart policies, log rotation, healthchecks, resource controls
  - dedicated `hgr-network`
  - optional extended data plane services (MinIO/Milvus profile)
  - Jaeger and semantic-bus-mcp service definitions
- Redis runtime config at `deploy/redis/redis.conf`.
- Worker metrics endpoints in pod-worker and audit-worker.
- Worker readiness endpoints:
  - `services/pod-worker`: `/readyz`
  - `services/audit-worker`: `/readyz`
- Monitoring scrape and alert expansions for MCP and workers.
- New governance and onboarding docs:
  - `docs/DATA_CLASSIFICATION_POLICY.md`
  - `docs/DEVELOPER_ONBOARDING_GUIDE.md`
  - `docs/API_INTEGRATION_GUIDE.md`
  - `docs/runbooks/semantic_bus_incident_runbook.md`
- Core coverage validation utility:
  - `scripts/check_coverage_thresholds.py`
- Core agent/runtime test suite expansion:
  - `tests/services/test_agent_core_unit.py`
  - targeted branch tests for protocol/runtime, semantic-bus, pod-worker, and audit-worker paths
- Testing policy documentation:
  - `docs/TESTING_QUALITY_GATES.md`
- Qdrant knowledge integration baseline:
  - `services/orchestrator/orchestrator/qdrant_store.py`
  - `tests/services/test_qdrant_store_unit.py`
  - phase evidence in `docs/evidence/phase16_data_system_activation_validation_2026-03-03.md`
- Neo4j optional graph integration baseline:
  - `services/orchestrator/orchestrator/neo4j_store.py`
  - `tests/services/test_neo4j_store_unit.py`
  - phase evidence in `docs/evidence/phase17_neo4j_feature_flag_validation_2026-03-03.md`

### Changed
- `.env.example` expanded with Redis password, MCP, MinIO, Milvus, Jaeger, and per-worker service key variables.
- `deploy/docker-compose.yaml` healthchecks migrated from `wget` to runtime-native probes (`python`/`node`) for slim images.
- `scripts/debug_sweep.ps1` expanded to validate MCP (`/health`, `/readyz`, `/metrics`) in addition to core services.
- Worker and MCP shutdown paths hardened for both async and sync Redis client close semantics.
- `docs/DOCUMENTATION_INDEX.md` updated with new operations/compliance docs.
- `Makefile` and `.github/workflows/ci.yml` now enforce 100% coverage for core multi-agent communication/runtime modules while preserving global `>= 80%` coverage.
- `services/orchestrator/orchestrator/storage.py` now applies versioned SQL migrations instead of inline table DDL.
- Added migration unit coverage in `tests/services/test_migrations_unit.py` and updated schema bootstrap tests.
- `.github/workflows/ci.yml` now runs Mission Control `npm run lint` and `npm run test` as part of CI validation.
- `Makefile` now exposes `make test-ui` for Mission Control lint/test execution.
- `README.md` now explicitly distinguishes Mission Control Docker host port (`3100`) from direct Next.js dev port (`3000`).
- Added operational script unit tests in `tests/scripts/test_production_review_audit.py`.
- Added performance-smoke script unit tests in `tests/scripts/test_perf_smoke.py`.
- Added promotion gate unit tests in `tests/scripts/test_promotion_gate.py`.
- `scripts/production_review_audit.py` now includes critical check `REL-001` for release trust controls.
- `scripts/production_review_audit.py` now includes reliability evidence check `PERF-010`.
- `scripts/production_review_audit.py` now includes Mission Control e2e gate check `UI-011`.
- `Makefile` now exposes `make promotion-gate` for local policy evaluation.
- `Makefile` now exposes `make reliability` for sustained-load qualification.
- `Makefile` now exposes `make test-ui-e2e` for Mission Control Playwright execution.
- `.github/workflows/ci.yml` now runs Mission Control Playwright e2e tests with Chromium install.
- Orchestrator internal knowledge endpoints now mirror to and retrieve from Qdrant (with PostgreSQL fallback), and runtime readiness payloads now include Qdrant dependency state.
- `.env.example` and `deploy/docker-compose.yaml` now expose Qdrant runtime controls (`QDRANT_ENABLED`, `QDRANT_COLLECTION`, `QDRANT_VECTOR_SIZE`, `QDRANT_TIMEOUT_SECONDS`, `QDRANT_API_KEY`).
- Orchestrator now supports feature-flagged Neo4j graph mirroring/query paths with readiness reporting, plus gateway route `GET /v1/missions/{mission_id}/knowledge-graph`.
- `.env.example` and `deploy/docker-compose.yaml` now expose `NEO4J_*` runtime controls and optional profiled Neo4j service wiring.
