# Operations Runbook

Document version: 2026.07.01  
Last updated: 2026-07-01  
Status: Canonical  
Audience: Operators, maintainers, and on-call responders

## Compose File Pairing — Read This Before Restarting Anything

If this deployment is running the full-dedicated-agent topology (41 per-language
agent containers, `TOPOLOGY_MODE=full-dedicated`), **always** recreate or restart
services with both compose files together:

```
docker compose --env-file .env -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml ...
```

`docker-compose.full-dedicated-agents.yaml` is an **overlay only** — it patches
the `orchestrator` service's environment and adds the 41 `agent-XX-*` services,
but does not redefine `api-gateway`, `mission-control`, or the pod workers.
Running a command against `deploy/docker-compose.yaml` **alone** (e.g. a quick
`docker compose -f deploy/docker-compose.yaml up -d orchestrator` to pick up an
image rebuild) will recreate that service under the *base* topology/environment,
desyncing it from the 41 dedicated agent containers that were never touched and
still expect the overlay's environment (e.g. `TOPOLOGY_MODE`). This has already
caused one full restart-cascade incident (401s on agent heartbeats, degraded PM
fallback output, `INTERNAL_SERVICE_API_KEY`/Postgres credential confusion) — see
`docs/STACK_REMEDIATION_PLAN_2026-07-01.md` for the full incident writeup.

The single-file examples elsewhere in this document (`Core Health Checks`, etc.)
are safe for **read-only** commands (`ps`, `logs`, `config`, `curl`). Prefer
`make up-full-dedicated` / `make down-full-dedicated` (see `Dedicated-Agent
Topology Checks` below) for any command that creates, recreates, or restarts
containers — they already pass the correct two-file combination and
`--env-file .env`.

## Core Health Checks

1. `docker compose -f deploy/docker-compose.yaml ps`
2. `curl http://localhost:8100/health`
3. `curl http://localhost:8101/health`
4. `curl http://localhost:8102/health`  # Protocol Bus MCP (formerly Semantic Bus MCP)
5. `curl http://localhost:8180/health`
6. `curl http://localhost:3100`
7. `curl http://localhost:8100/readyz`
8. `curl http://localhost:8101/readyz`
9. `curl http://localhost:8100/metrics | head`
10. `curl http://localhost:8101/metrics | head`

## Protocol Bus

> Formerly **Semantic Bus**. The service is `protocol-bus-mcp` (was `semantic-bus-mcp`).

1. Health check:
   - `curl http://localhost:8102/health`
2. Logs:
   - `docker compose -f deploy/docker-compose.yaml logs protocol-bus-mcp --tail 100`
3. Restart the bus:
   - `docker compose -f deploy/docker-compose.yaml restart protocol-bus-mcp`
4. Expected `POST /send` behavior:
   - Returns **409** on a duplicate correlation-id. This is replay detection — expected behavior, not an incident.
   - Returns **503** when Redis is unreachable. The bus now fails closed (this was previously a silent pass).
     - Treat a 503 as a **Redis incident**, not a bus incident — check Redis health and recovery steps before touching `protocol-bus-mcp`.

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
   - expected: `41`
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
2. Generate local dedicated key material for full-topology qualification:
   - `python scripts/generate_agent_service_keys.py --force`
   - output: `.env.agent-service-keys.local`
   - includes `INTERNAL_SERVICE_API_KEY` plus per-agent service keys for strict dedicated launches
3. Verify pod worker reports configured agent keys:
   - `docker compose -f deploy/docker-compose.yaml exec pod-a-worker python -c "import json, urllib.request; print(json.loads(urllib.request.urlopen('http://localhost:8201/health').read())['configured_agent_service_keys'])"`
4. Verify audit worker agent identity:
   - `docker compose -f deploy/docker-compose.yaml exec audit-worker python -c "import json, urllib.request; payload=json.loads(urllib.request.urlopen('http://localhost:8202/health').read()); print(payload['worker_agent_id'], payload['agent_service_key_mode'])"`
5. Reference:
   - `docs/AGENT_SERVICE_KEY_ISOLATION.md`

## Dedicated-Agent Topology Checks

1. Validate the full topology resolves:
   - `docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents config`
2. Start the full topology:
   - `make up-full-dedicated`
3. Stop the full topology:
   - `make down-full-dedicated`
4. Validate PM/CEO/specialist services exist:
   - `docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents config | rg "agent-01-pm|agent-02-ceo|agent-35-mathematica|agent-36-go|agent-37-haskell|agent-38-ocaml"`
5. Run strict local full-dedicated qualification:
   - `docker compose --env-file .env.agent-service-keys.local -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents up -d --build`
   - `python scripts/mission_artifact_qualification.py --profile-label full-dedicated-strict --output-file docs/evidence/mission_artifact_qualification_full_dedicated_strict_<date>.json --history-file docs/evidence/mission_artifact_qualification_history.jsonl`
   - `python scripts/dedicated_agent_canary_rollout.py --profile-label full-dedicated-strict --output-file docs/evidence/dedicated_agent_canary_full_dedicated_strict_<date>.json`
6. Verify dedicated worker consumer groups exist after startup or Redis restart:
   - `docker exec deploy-orchestrator-1 python -c "import os, redis; r=redis.Redis.from_url(os.environ['REDIS_URL'], decode_responses=True); print(r.xinfo_groups('missions.state'))"`
7. Current dedicated coverage note:
   - The overlay now provisions dedicated PM/CEO/support/pod-audit containers plus specialist workers across the full 41-agent runtime, including Go, Haskell, and OCaml.

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

## PgBouncer Connection Pooling

The orchestrator connects to Postgres through the `pgbouncer` sidecar
(transaction pooling mode), not directly. PgBouncer holds the `verify-full` TLS
connection to the real Postgres; the orchestrator → PgBouncer hop stays on the
internal `hgr-network` (`sslmode=disable` in `POSTGRES_URL`).

1. Confirm services target the bouncer, not Postgres directly:
   - `docker compose -f deploy/docker-compose.yaml config | rg "@pgbouncer:"`
2. Confirm PgBouncer → Postgres uses verify-full TLS:
   - `docker compose -f deploy/docker-compose.yaml config | rg "PGBOUNCER_SERVER_TLS_SSLMODE|PGBOUNCER_SERVER_TLS_CA_FILE"`
3. Check the bouncer is healthy:
   - `docker compose -f deploy/docker-compose.yaml exec pgbouncer pg_isready -h localhost`
4. Transaction-mode constraints (verified absent from the codebase): no
   `SET`/session state, no `LISTEN`/`NOTIFY`, no server-side prepared statements.
   All psycopg connect sites set `prepare_threshold=None` to keep this guarantee —
   do not remove that when editing `storage_core.py`, `storage_missions.py`, or
   `migrations.py`.

## Immutable Audit Log and Retention

Audit tables (`mission_state_events`, `agent_runtime_events`,
`agent_action_events`, `llm_usage_events`, `mission_audit_reports`) are
append-only and tamper-evident:

- **Immutability (V009):** `DELETE` is revoked from the application role on
  `mission_audit_reports`, `agent_action_events`, and `llm_usage_events`. The
  REVOKEs are wrapped in a `DO ... EXCEPTION WHEN insufficient_privilege` block,
  so if the migration runs under a least-privileged role that cannot revoke,
  boot does not fail — a DBA must then apply the REVOKEs out of band as a
  superuser/owner:
  - `REVOKE DELETE ON mission_audit_reports, agent_action_events, llm_usage_events FROM <app_role>;`
- **Retention (V008):** `prune_audit_tables(retention_days)` is `SECURITY
  DEFINER`, so it deletes aged rows with the owner's privileges even after the
  REVOKE above. Default window is `AUDIT_RETENTION_DAYS` (90).
- **Run retention:**
  - `make prune-audit` (override with `RETENTION_DAYS=30 make prune-audit`)
  - or `curl -X POST -H "x-api-key: $ORCHESTRATOR_ADMIN_API_KEY" "http://localhost:8101/v1/maintenance/prune-audit?retention_days=90"`
- Schedule `make prune-audit` from cron/systemd-timer; it is idempotent and safe
  to run repeatedly.

## Recovery Steps

1. Restart stack:
   - `docker compose -f deploy/docker-compose.yaml down`
   - `docker compose -f deploy/docker-compose.yaml up -d --build`
2. Recreate containers after TLS material or cert-mount changes:
   - `make tls-certs`
   - `docker compose -f deploy/docker-compose.yaml down -v`
   - `docker compose -f deploy/docker-compose.yaml up -d --build`
   - for the dedicated overlay: `docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents up -d --build --force-recreate`
3. Investigate Postgres or migration failures:
   - `docker compose -f deploy/docker-compose.yaml logs orchestrator --tail 200`
   - `docker compose -f deploy/docker-compose.yaml logs postgres --tail 200`
4. Investigate stream consumption stalls:
   - `docker compose -f deploy/docker-compose.yaml exec redis redis-cli XINFO GROUPS missions.intake`
   - `docker compose -f deploy/docker-compose.yaml exec redis redis-cli XINFO GROUPS missions.state`
   - If Redis was restarted, verify dedicated worker groups were recreated automatically before recycling containers.

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
   - artifact verification:
     - `python scripts/verify_backup_artifacts.py --backup-file backups/<file>.sql --manifest-file backups/<file>.sql.json --output-file reports/backup-verification.local.json`
   - outputs:
     - backup SQL file
     - `<file>.sql.sha256`
     - `<file>.sql.json` manifest with timestamp, size, and digest
3. Restore:
   - `powershell -ExecutionPolicy Bypass -File scripts/restore_postgres.ps1 -BackupFile backups/<file>.sql`
4. DR drill:
   - `powershell -ExecutionPolicy Bypass -File scripts/dr_drill.ps1`
   - dry-run validation: `powershell -ExecutionPolicy Bypass -File scripts/dr_drill.ps1 -DryRun`
   - latest drill report: `reports/dr-drill-latest.json`
5. Perf smoke:
   - `powershell -ExecutionPolicy Bypass -File scripts/perf_smoke.ps1`
6. Long-duration reliability qualification:
   - `powershell -ExecutionPolicy Bypass -File scripts/reliability_qualification.ps1 -InjectOrchestratorRestart`
   - current evidence artifact: `docs/evidence/reliability_qualification_baseline_YYYY-MM-DD.json`
   - verify the JSON includes `base_url`, `readiness_endpoints`, `readiness_failure_counts_by_endpoint`, `mission_error_samples`, `readiness_failure_samples`, `recovery_probe`, and `failure_injection`
   - evidence verifier: `python scripts/verify_reliability_evidence.py --evidence-file docs/evidence/reliability_qualification_baseline_YYYY-MM-DD.json`
   - tune thresholds with `-MaxReadinessFailures`, `-MaxConsecutiveReadinessFailures`, `-RecoveryTimeoutSeconds`, and `-RecoveryConsecutiveSuccesses` when qualifying slower staging environments
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

## Release Environments & Approvals

The `Build & Release` workflow (`.github/workflows/release.yml`) runs on `v*` tag
pushes and is gated by two GitHub Environments. The workflow declares the
environments, but the protection rules (reviewers, wait timers, secrets) must be
configured once in **repo Settings → Environments**.

| Environment | Job | Purpose | Required configuration |
|---|---|---|---|
| `staging` | `staging-validation` | Pre-production validation of the release candidate (tag format / signing checks) before any artifact is published. | Optional required reviewers or a wait timer. Add staging-only secrets here. |
| `production` | `release` | Builds and publishes the Electron installers to the GitHub Release. Runs only after `staging-validation` succeeds. | **Required reviewers (at least one)** so the tag push pauses for manual approval before publishing. Scope `CSC_LINK` / `CSC_KEY_PASSWORD` code-signing secrets here. |

Setup steps (one-time, in GitHub UI):

1. Settings → Environments → **New environment** → name it `production`.
   - Enable **Required reviewers** and add the release approvers.
   - (Recommended) Enable **Deployment branch and tag rules**, restricting to `v*` tags.
   - Add production-only secrets (e.g. code-signing certs) here, not as repo secrets.
2. Repeat for `staging`. Required reviewers are optional; use a wait timer if you
   want a soak period before promotion.
3. After configuration, a `v*` tag push will: run `staging-validation`, then pause
   the `release` job pending approval from a `production` reviewer. Approve from the
   Actions run page to publish.

Until reviewers are added, the environments exist but impose no gate — configure
them before relying on the approval flow.
