# Phase 33 Validation - Extended Data-Plane Live Qualification (2026-03-04)

## Objective
Execute the Phase 20 objective by validating live Neo4j/MinIO optional data-plane paths and disruption recovery under the compose `extended-data-plane` profile.

## Implementation
- Added live qualification suite:
  - `tests/services/test_live_extended_data_plane_integration.py`
  - coverage:
    - end-to-end optional mirror-write roundtrip validation,
    - skip-safe gating when live stack/adapters are unavailable,
    - disruption/recovery flow (`LIVE_ENABLE_DISRUPTION_TESTS=true`) for temporary Neo4j/MinIO outages.
- Added local execution target:
  - `make test-live-extended`
- Hardened compose extended profile runtime:
  - `deploy/docker-compose.yaml`
  - MinIO image tag corrected to valid release `RELEASE.2025-09-07T16-13-09Z`.
  - MinIO healthcheck migrated to `curl` (container-available) from `wget`.

## Validation Commands and Results
1. `python -m ruff check tests/services/test_live_extended_data_plane_integration.py`
   - Result: pass
2. `NEO4J_ENABLED=true OBJECT_STORAGE_ENABLED=true docker compose -f deploy/docker-compose.yaml --profile extended-data-plane up -d --build --force-recreate api-gateway orchestrator neo4j minio` (with host-port overrides for local collisions)
   - Result: pass (services healthy; orchestrator reports `neo4j_ready=true`, `object_storage_ready=true`)
3. `LIVE_ENABLE_DISRUPTION_TESTS=true python -m pytest -q tests/services/test_live_extended_data_plane_integration.py`
   - Result: pass (`2 passed`)
4. `python -m pytest --cov=services --cov-report=term-missing --cov-report=xml --cov-fail-under=80`
   - Result: pass (`320 passed`, `1 skipped`, global coverage `86.00%`)
5. `python scripts/check_coverage_thresholds.py`
   - Result: pass (`Global coverage: 86.00%`, threshold `80.00%`)
6. `python scripts/production_review_audit.py`
   - Result: pass (`13/13`)
7. `npm --prefix apps/mission-control run lint`
   - Result: pass
8. `npm --prefix apps/mission-control run test`
   - Result: pass (`3 files`, `21 tests`)
9. `powershell -ExecutionPolicy Bypass -File scripts/debug_sweep.ps1` (with `PYTHONPATH=services/pod-worker`)
   - Result: pass

## Runtime Observations
- During qualification, stale local container images caused gateway `404` on newer routes; resolved by rebuilding `api-gateway` and `orchestrator` with current source.
- Existing non-blocking tracing environment issue remains:
  - Jaeger OTLP DNS-resolution errors in orchestrator logs when `jaeger` hostname is unavailable on the active network.
