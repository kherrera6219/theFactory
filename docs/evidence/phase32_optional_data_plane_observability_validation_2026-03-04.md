# Phase 32 Validation - Optional Data-Plane Observability and SLO Controls (2026-03-04)

Document version: 2026.03.04
Last updated: 2026-03-04
Status: Historical Evidence

## Objective
Implement production-grade observability controls for optional Neo4j and object-storage adapters, including readiness/error/latency metrics, alerting, dashboards, and runbook linkage.

## Implementation
- Added optional adapter telemetry module:
  - `services/orchestrator/orchestrator/data_plane_metrics.py`
- Instrumented adapter operation paths:
  - `services/orchestrator/orchestrator/neo4j_store.py`
  - `services/orchestrator/orchestrator/object_store.py`
- Instrumented mirror-write flows at orchestrator endpoints:
  - `services/orchestrator/orchestrator/main.py`
- Added observability controls:
  - Prometheus rules: `deploy/monitoring/prometheus/rules/thefactory-alerts.yml`
  - Grafana panels: `deploy/monitoring/grafana/provisioning/dashboards/json/thefactory-overview.json`
  - Incident runbook: `docs/runbooks/optional_data_plane_incident_runbook.md`
- Added audit guardrail:
  - `OBS-010` in `scripts/production_review_audit.py`
  - regression tests in `tests/scripts/test_production_review_audit.py`

## Validation Commands and Results
1. `python -m ruff check services/orchestrator/orchestrator/data_plane_metrics.py services/orchestrator/orchestrator/main.py services/orchestrator/orchestrator/neo4j_store.py services/orchestrator/orchestrator/object_store.py scripts/production_review_audit.py tests/services/test_neo4j_store_unit.py tests/services/test_object_store_unit.py tests/services/test_orchestrator_endpoints_extra.py tests/scripts/test_production_review_audit.py`
   - Result: pass
2. `python -m pytest --cov=services --cov-report=term-missing --cov-report=xml --cov-fail-under=80`
   - Result: pass (`319 passed`, global coverage `86.00%`)
3. `python scripts/check_coverage_thresholds.py`
   - Result: pass (`Global coverage: 86.00%`, threshold `80.00%`)
4. `python scripts/production_review_audit.py`
   - Result: pass (`13/13`, including `OBS-010`)
5. `docker compose -f deploy/docker-compose.monitoring.yaml config`
   - Result: pass
6. `python -c "import json, pathlib; json.loads(pathlib.Path('deploy/monitoring/grafana/provisioning/dashboards/json/thefactory-overview.json').read_text(encoding='utf-8')); print('dashboard json ok')"`
   - Result: pass (`dashboard json ok`)
7. `npm --prefix apps/mission-control run lint`
   - Result: pass
8. `npm --prefix apps/mission-control run test`
   - Result: pass (`3 files`, `21 tests`)
9. `powershell -ExecutionPolicy Bypass -File scripts/debug_sweep.ps1` (with `PYTHONPATH=services/pod-worker`)
   - Result: pass

## Runtime Observation
- Non-blocking existing environment issue remains in debug-sweep logs:
  - Jaeger OTLP DNS resolution errors (`host='jaeger'`) when Jaeger is not present in the running stack.
