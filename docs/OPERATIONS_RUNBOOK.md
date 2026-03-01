# Operations Runbook

## Core health checks

1. `docker compose -f deploy/docker-compose.yaml ps`
2. `curl http://localhost:8100/health`
3. `curl http://localhost:8101/health`
4. `curl http://localhost:8180/health`
5. `curl http://localhost:3100`
6. `curl http://localhost:8100/readyz`
7. `curl http://localhost:8101/readyz`
8. `curl http://localhost:8100/metrics | head`
9. `curl http://localhost:8101/metrics | head`

## Monitoring stack

1. Start monitoring bundle:
   - `docker compose -f deploy/docker-compose.monitoring.yaml up -d`
2. Open tools:
   - Prometheus: `http://localhost:9090`
   - Grafana: `http://localhost:3001`
   - Loki API: `http://localhost:3101`
3. Stop monitoring bundle:
   - `docker compose -f deploy/docker-compose.monitoring.yaml down -v`

## Mission pipeline smoke test

1. Submit mission:
   - `curl -X POST http://localhost:8100/v1/missions -H "Content-Type: application/json" -H "Idempotency-Key: runbook-mission-001" -d "{\"prompt\":\"Build a policy API\",\"requested_target_language\":\"python\",\"metadata\":{\"source\":\"runbook\"}}"`
2. Poll mission:
   - `curl http://localhost:8100/v1/missions/<mission_id>`
3. Fetch events:
   - `curl http://localhost:8100/v1/missions/<mission_id>/events?limit=20`
4. Verify DB state:
   - `docker exec deploy-postgres-1 psql -U postgres -d ulr -c "select mission_id, state, updated_at from missions order by updated_at desc limit 5;"`
5. Verify idempotent replay returns same mission:
   - Repeat step 1 with the same `Idempotency-Key`; confirm `mission_id` is unchanged.

## Auth checks

1. Valid mutation:
   - `curl -X POST http://localhost:8100/v1/missions/<mission_id>/state -H "x-api-key: operator-key" -H "Content-Type: application/json" -d "{\"new_state\":\"FAILED\",\"expected_state\":\"RUNNING\"}"`
2. Unauthorized mutation:
   - `curl -X POST http://localhost:8100/v1/missions/<mission_id>/state -H "x-api-key: viewer-key" -H "Content-Type: application/json" -d "{\"new_state\":\"FAILED\"}"`

## Recovery steps

1. Restart services:
   - `docker compose -f deploy/docker-compose.yaml down`
   - `docker compose -f deploy/docker-compose.yaml up -d --build`
2. If Postgres migrations fail, inspect:
   - `docker compose -f deploy/docker-compose.yaml logs orchestrator --tail 200`
   - `docker compose -f deploy/docker-compose.yaml logs postgres --tail 200`
3. If stream consumers stall, inspect groups:
   - `docker compose -f deploy/docker-compose.yaml exec redis redis-cli XINFO GROUPS missions.intake`
   - `docker compose -f deploy/docker-compose.yaml exec redis redis-cli XINFO GROUPS missions.state`

## Disaster recovery baseline

1. Snapshot DB:
   - `docker exec deploy-postgres-1 pg_dump -U postgres ulr > ulr-backup.sql`
2. Restore DB:
   - `docker exec -i deploy-postgres-1 psql -U postgres -d ulr < ulr-backup.sql`
3. Retention policy:
   - Keep daily backups for 14 days, weekly for 8 weeks.

## Deployment and DR automation scripts

1. Pre-deployment checks:
   - `powershell -ExecutionPolicy Bypass -File scripts/pre_deploy_check.ps1`
2. Backup database:
   - `powershell -ExecutionPolicy Bypass -File scripts/backup_postgres.ps1`
3. Restore database:
   - `powershell -ExecutionPolicy Bypass -File scripts/restore_postgres.ps1 -BackupFile backups/<file>.sql`
4. DR drill:
   - `powershell -ExecutionPolicy Bypass -File scripts/dr_drill.ps1`
5. Performance smoke:
   - `powershell -ExecutionPolicy Bypass -File scripts/perf_smoke.ps1`
