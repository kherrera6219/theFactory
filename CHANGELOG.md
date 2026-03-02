# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased]

### Added
- Versioned orchestrator migration framework:
  - `services/orchestrator/orchestrator/migrations.py`
  - `services/orchestrator/orchestrator/migrations/V001_initial_runtime_schema.sql`
  - checksum-tracked `schema_migrations` table enforcement
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

### Changed
- `.env.example` expanded with Redis password, MCP, MinIO, Milvus, Jaeger, and per-worker service key variables.
- `deploy/docker-compose.yaml` healthchecks migrated from `wget` to runtime-native probes (`python`/`node`) for slim images.
- `scripts/debug_sweep.ps1` expanded to validate MCP (`/health`, `/readyz`, `/metrics`) in addition to core services.
- Worker and MCP shutdown paths hardened for both async and sync Redis client close semantics.
- `docs/DOCUMENTATION_INDEX.md` updated with new operations/compliance docs.
- `Makefile` and `.github/workflows/ci.yml` now enforce 100% coverage for core multi-agent communication/runtime modules while preserving global `>= 80%` coverage.
- `services/orchestrator/orchestrator/storage.py` now applies versioned SQL migrations instead of inline table DDL.
- Added migration unit coverage in `tests/services/test_migrations_unit.py` and updated schema bootstrap tests.
