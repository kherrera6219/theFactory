# Operations Runbook

Last updated: 2026-03-09

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
   - `curl -H "x-api-key: operator-key" http://localhost:8100/v1/operations/agents | jq ".total_agents"`
   - expected: `35`
2. Validate persona profile object exists:
   - `curl -H "x-api-key: operator-key" http://localhost:8100/v1/operations/agents | jq ".agents[0].persona_profile | keys"`
3. Validate standards/evidence extension fields:
   - `curl -H "x-api-key: operator-key" http://localhost:8100/v1/operations/agents | jq ".agents[0].persona_profile.standards_alignment | length"`
   - `curl -H "x-api-key: operator-key" http://localhost:8100/v1/operations/agents | jq ".agents[0].persona_profile.evidence_sources | length"`
4. Validate integration metadata:
   - `curl -H "x-api-key: operator-key" http://localhost:8100/v1/operations/agent-integrations | jq ".persona_profile_framework, .persona_profile_extensions, .standards_evidence_last_verified"`

## Auth Checks

1. Valid mutation:
   - `curl -X POST http://localhost:8100/v1/missions/<mission_id>/state -H "x-api-key: operator-key" -H "Content-Type: application/json" -d "{\"new_state\":\"FAILED\",\"expected_state\":\"RUNNING\"}"`
2. Unauthorized mutation:
   - `curl -X POST http://localhost:8100/v1/missions/<mission_id>/state -H "x-api-key: viewer-key" -H "Content-Type: application/json" -d "{\"new_state\":\"FAILED\"}"`
3. OIDC operator-route check (`AUTH_MODE=oidc`):
   - Missing bearer token should fail:
     - `curl -i http://localhost:8100/v1/operations/summary`
   - Valid bearer token with `OIDC_OPERATOR_ROLE` should pass:
     - `curl -i http://localhost:8100/v1/operations/summary -H "Authorization: Bearer <token-with-observe-role>"`

## Agent Service Key Checks

1. Verify strict mode in production overlay:
   - `docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.prod.yaml config | rg AGENT_SERVICE_KEY_MODE`
2. Verify pod worker reports configured agent keys:
   - `docker compose -f deploy/docker-compose.yaml exec pod-a-worker python -c "import json, urllib.request; print(json.loads(urllib.request.urlopen('http://localhost:8201/health').read())['configured_agent_service_keys'])"`
3. Verify audit worker agent identity:
   - `docker compose -f deploy/docker-compose.yaml exec audit-worker python -c "import json, urllib.request; payload=json.loads(urllib.request.urlopen('http://localhost:8202/health').read()); print(payload['worker_agent_id'], payload['agent_service_key_mode'])"`
4. Reference:
   - `docs/AGENT_SERVICE_KEY_ISOLATION.md`

## Dedicated-Agent Topology Checks

1. Validate the full topology resolves:
   - `docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents config`
2. Start the full topology:
   - `make dedicated-full-up`
3. Stop the full topology:
   - `make dedicated-full-down`
4. Validate PM/CEO/specialist services exist:
   - `docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents config | rg "agent-01-pm|agent-02-ceo|agent-35-mathematica"`

## Redis TLS Checks

1. Verify runtime compose resolved CA-validated Redis URLs:
   - `docker compose -f deploy/docker-compose.yaml config | rg "ssl_cert_reqs=required|ssl_ca_certs"`
2. Verify Redis server healthcheck uses CA validation:
   - `docker compose -f deploy/docker-compose.yaml config | rg "redis-cli --tls --cacert"`
3. Verify runtime containers received client cert mount:
   - `docker compose -f deploy/docker-compose.yaml config | rg "/run/redis-certs/ca.crt"`

## Postgres TLS Checks

1. Verify compose resolved `verify-full`:
   - `docker compose -f deploy/docker-compose.yaml config | rg "sslmode=verify-full|sslrootcert=/run/postgres-certs/ca.crt"`
2. Verify Postgres cert mounts exist:
   - `docker compose -f deploy/docker-compose.yaml config | rg "/run/postgres-certs|docker-entrypoint-init-tls.sh"`
3. Regenerate local cert material when required:
   - `python scripts/generate_postgres_tls_certs.py`

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
5. Run live qualification (when extended profile is active):
   - `LIVE_ENABLE_DISRUPTION_TESTS=true make test-live-extended`
6. Verify Milvus readiness when enabled:
   - `curl http://localhost:8101/health | jq ".milvus_uri, .milvus_ready"`

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
10. Dedicated-agent canary qualification:
   - `powershell -ExecutionPolicy Bypass -File scripts/dedicated_agent_canary_rollout.ps1`
   - or `make dedicated-canary`
11. Operator-route auth matrix qualification (`api_key`, `hybrid`, `oidc`):
   - `powershell -ExecutionPolicy Bypass -File scripts/operator_route_auth_matrix_qualification.ps1`
   - or `make oidc-matrix`
12. Dedicated-agent canary trend qualification (multi-language):
   - `powershell -ExecutionPolicy Bypass -File scripts/dedicated_agent_canary_trend.ps1`
   - or `make dedicated-canary-trend`
13. LangGraph v2 prototype matrix (v1.1 baseline + feature-flag prototype):
   - `powershell -ExecutionPolicy Bypass -File scripts/langgraph_v2_prototype_matrix.ps1`
   - or `make langgraph-v2-prototype`
14. DORA metrics summary:
   - `python scripts/dora_metrics_summary.py --output-file docs/evidence/dora_metrics_latest.json`
