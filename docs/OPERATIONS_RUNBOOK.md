# Operations Runbook

Last updated: 2026-03-04

## Core Health Checks

1. `docker compose -f deploy/docker-compose.yaml ps`
2. `curl http://localhost:8100/health`
3. `curl http://localhost:8101/health`
4. `curl http://localhost:8180/health`
5. `curl http://localhost:3100`
6. `curl http://localhost:8100/readyz`
7. `curl http://localhost:8101/readyz`
8. `curl http://localhost:8100/metrics | head`
9. `curl http://localhost:8101/metrics | head`

## Monitoring Stack

1. Start:
   - `docker compose -f deploy/docker-compose.monitoring.yaml up -d`
2. Open:
   - Prometheus: `http://localhost:9090`
   - Grafana: `http://localhost:3001`
   - Loki: `http://localhost:3101`
   - Alertmanager: `http://localhost:9093`
   - Jaeger: `http://localhost:16686`
3. Stop:
   - `docker compose -f deploy/docker-compose.monitoring.yaml down -v`

## Tracing and Pager Checks

1. Verify tracing is enabled for core services:
   - `curl http://localhost:8100/readyz`
   - `curl http://localhost:8101/readyz`
2. Verify Jaeger UI is reachable:
   - `curl http://localhost:16686`
3. Verify Alertmanager is healthy:
   - `curl http://localhost:9093/-/ready`
4. Verify pager webhook configuration in monitoring stack:
   - `docker compose -f deploy/docker-compose.monitoring.yaml exec alertmanager printenv PAGER_WEBHOOK_URL`

## Mission Pipeline Smoke Test

1. Submit mission:
   - `curl -X POST http://localhost:8100/v1/missions -H "Content-Type: application/json" -H "Idempotency-Key: runbook-mission-001" -d "{\"prompt\":\"Build a policy API\",\"requested_target_language\":\"python\",\"metadata\":{\"source\":\"runbook\"}}"`
2. Poll mission:
   - `curl http://localhost:8100/v1/missions/<mission_id>`
3. Fetch events:
   - `curl http://localhost:8100/v1/missions/<mission_id>/events?limit=20`
4. Verify DB state:
   - `docker exec deploy-postgres-1 psql -U postgres -d ulr -c "select mission_id, state, updated_at from missions order by updated_at desc limit 5;"`
5. Verify idempotency replay:
   - Repeat step 1 with same `Idempotency-Key` and confirm `mission_id` is unchanged.

## Agent Runtime and Persona Validation

1. Check runtime snapshot includes all agents:
   - `curl http://localhost:8100/v1/operations/agents | jq ".total_agents"`
   - expected: `35`
2. Validate persona profile object exists:
   - `curl http://localhost:8100/v1/operations/agents | jq ".agents[0].persona_profile | keys"`
3. Validate standards/evidence extension fields:
   - `curl http://localhost:8100/v1/operations/agents | jq ".agents[0].persona_profile.standards_alignment | length"`
   - `curl http://localhost:8100/v1/operations/agents | jq ".agents[0].persona_profile.evidence_sources | length"`
4. Validate integration metadata:
   - `curl http://localhost:8100/v1/operations/agent-integrations | jq ".persona_profile_framework, .persona_profile_extensions, .standards_evidence_last_verified"`

## Auth Checks

1. Valid mutation:
   - `curl -X POST http://localhost:8100/v1/missions/<mission_id>/state -H "x-api-key: operator-key" -H "Content-Type: application/json" -d "{\"new_state\":\"FAILED\",\"expected_state\":\"RUNNING\"}"`
2. Unauthorized mutation:
   - `curl -X POST http://localhost:8100/v1/missions/<mission_id>/state -H "x-api-key: viewer-key" -H "Content-Type: application/json" -d "{\"new_state\":\"FAILED\"}"`

## Recovery Steps

1. Restart stack:
   - `docker compose -f deploy/docker-compose.yaml down`
   - `docker compose -f deploy/docker-compose.yaml up -d --build`
2. Investigate Postgres or migration failures:
   - `docker compose -f deploy/docker-compose.yaml logs orchestrator --tail 200`
   - `docker compose -f deploy/docker-compose.yaml logs postgres --tail 200`
3. Investigate stream consumption stalls:
   - `docker compose -f deploy/docker-compose.yaml exec redis redis-cli XINFO GROUPS missions.intake`
   - `docker compose -f deploy/docker-compose.yaml exec redis redis-cli XINFO GROUPS missions.state`

## Disaster Recovery Baseline

1. Snapshot:
   - `docker exec deploy-postgres-1 pg_dump -U postgres ulr > ulr-backup.sql`
2. Restore:
   - `docker exec -i deploy-postgres-1 psql -U postgres -d ulr < ulr-backup.sql`
3. Retention policy:
   - Daily backups for 14 days.
   - Weekly backups for 8 weeks.

## Optional Data-Plane Checks

1. Confirm feature flags:
   - `docker compose -f deploy/docker-compose.yaml exec orchestrator printenv NEO4J_ENABLED OBJECT_STORAGE_ENABLED`
2. Confirm adapter readiness in health:
   - `curl http://localhost:8101/health | jq ".neo4j_ready, .object_storage_ready"`
3. Confirm optional adapter telemetry exists:
   - `curl http://localhost:8101/metrics | rg "orchestrator_optional_adapter_"`
4. If adapter alerts fire, follow:
   - `docs/runbooks/optional_data_plane_incident_runbook.md`

## Automation Scripts

1. Predeploy checks:
   - `powershell -ExecutionPolicy Bypass -File scripts/pre_deploy_check.ps1`
2. Backup:
   - `powershell -ExecutionPolicy Bypass -File scripts/backup_postgres.ps1`
   - dry-run validation: `powershell -ExecutionPolicy Bypass -File scripts/backup_postgres.ps1 -DryRun`
3. Restore:
   - `powershell -ExecutionPolicy Bypass -File scripts/restore_postgres.ps1 -BackupFile backups/<file>.sql`
4. DR drill:
   - `powershell -ExecutionPolicy Bypass -File scripts/dr_drill.ps1`
   - dry-run validation: `powershell -ExecutionPolicy Bypass -File scripts/dr_drill.ps1 -DryRun`
5. Perf smoke:
   - `powershell -ExecutionPolicy Bypass -File scripts/perf_smoke.ps1`
6. Long-duration reliability qualification:
   - `powershell -ExecutionPolicy Bypass -File scripts/reliability_qualification.ps1 -InjectOrchestratorRestart`
7. Debug/code sweep:
   - `powershell -ExecutionPolicy Bypass -File scripts/debug_sweep.ps1`
8. Mission Control end-to-end regression:
   - `cd apps/mission-control && npm run test:e2e`
   - validates mission lifecycle, operations persona view, settings/vault, builder preview, repo intake, and error-state handling
9. Live mission-flow integration:
   - `python -m pytest -q tests/services/test_live_mission_flow_integration.py`
