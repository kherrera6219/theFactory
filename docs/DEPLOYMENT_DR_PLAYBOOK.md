# Deployment, Backup & Disaster Recovery Playbook

Document version: 2026.07.03  
Last updated: 2026-07-03  
Status: Canonical  
Audience: Operators, maintainers, incident responders, and release owners

## Table of Contents

- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Deployment Procedure](#deployment-procedure)
- [Rollback Procedure](#rollback-procedure)
- [Backup Procedures](#backup-procedures)
- [Restore Procedures](#restore-procedures)
- [Disaster Recovery Playbook](#disaster-recovery-playbook)
- [Service Failure Playbooks](#service-failure-playbooks)
- [LangGraph Recovery Qualification](#langgraph-recovery-qualification)
- [Reliability Qualification](#reliability-qualification)
- [Mission Control E2E Verification](#mission-control-e2e-verification)
- [Automation Scripts Reference](#automation-scripts-reference)

---

## Pre-Deployment Checklist

Before any deployment, run the full preflight check:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/pre_deploy_check.ps1
```

This validates:
- [ ] Docker Compose file syntax
- [ ] Schema file validity
- [ ] Service health/readiness endpoints reachable
- [ ] OpenAPI export completes successfully
- [ ] Environment template variables present

Also run:

```bash
make audit          # All 23/23 production audit checks must pass
make promotion-gate # Promotion policy must yield APPROVED
```

The promotion gate writes `reports/promotion-decision.local.json`. If the decision is `BLOCKED`, do not proceed.

---

## Deployment Procedure

### Standard Deployment (Core Stack)

```bash
# 1. Stop current stack
docker compose -f deploy/docker-compose.yaml down

# 2. Pull latest images / rebuild
docker compose -f deploy/docker-compose.yaml build --no-cache

# 3. Start stack
docker compose -f deploy/docker-compose.yaml up -d

# 4. Wait for health (all services should show healthy within 60s)
docker compose -f deploy/docker-compose.yaml ps

# 5. Verify endpoints
curl http://localhost:8100/health
curl http://localhost:8101/health
curl http://localhost:8102/health
curl http://localhost:8180/health
```

### Dedicated-Agent Profile Deployment

```bash
docker compose -f deploy/docker-compose.yaml --profile dedicated-agents up -d --build
```

Per-agent binding is controlled by `AGENT_BINDING` in each worker container's environment.

### Monitoring Stack Deployment

```bash
docker compose -f deploy/docker-compose.monitoring.yaml up -d
```

Verify:
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001` (admin/admin on first login)
- Alertmanager: `http://localhost:9093`
- Jaeger: `http://localhost:16686`

### Zero-Downtime Deployment (Planned)

Currently, the stack requires a brief ~30s downtime window on restart. For production multi-instance deployments, use a load balancer with rolling container replacement.

---

## Rollback Procedure

```bash
# 1. Stop current stack
docker compose -f deploy/docker-compose.yaml down

# 2. Checkout previous release tag
git checkout <previous-tag>

# 3. Restore database if migration was applied (see Restore section)
powershell -ExecutionPolicy Bypass -File scripts/restore_postgres.ps1 \
  -BackupFile backups/<pre-deploy-backup>.sql

# 4. Rebuild and restart
docker compose -f deploy/docker-compose.yaml up -d --build

# 5. Validate
curl http://localhost:8100/health
make audit
```

> **Important:** Always take a backup (`make backup`) immediately before deploying. Label it with the commit SHA.

---

## Backup Procedures

### PostgreSQL Backup

```powershell
# Standard backup (creates backups/ulr_YYYYMMDD_HHMMSS.sql)
powershell -ExecutionPolicy Bypass -File scripts/backup_postgres.ps1

# CI/dry-run validation (no actual dump, validates connectivity)
powershell -ExecutionPolicy Bypass -File scripts/backup_postgres.ps1 -DryRun
```

Via make:
```bash
make backup
```

### Backup Retention Policy

| Frequency | Retention |
|-----------|-----------|
| Daily | 14 days |
| Weekly | 8 weeks |
| Pre-deployment | Indefinite (label with commit SHA) |

### Backup Storage

Backups are written to `backups/` in the repository root. For production:
- Copy backups to an off-host location (MinIO, S3, network share)
- Do **not** commit backup files to Git

---

## Restore Procedures

### Full PostgreSQL Restore

```powershell
powershell -ExecutionPolicy Bypass -File scripts/restore_postgres.ps1 \
  -BackupFile backups/ulr_YYYYMMDD_HHMMSS.sql
```

### Manual Restore (emergency)

```bash
# 1. Stop all services (to prevent writes during restore)
docker compose -f deploy/docker-compose.yaml stop api-gateway orchestrator pod-worker

# 2. Drop and recreate database
docker exec deploy-postgres-1 psql -U postgres -c "DROP DATABASE IF EXISTS ulr;"
docker exec deploy-postgres-1 psql -U postgres -c "CREATE DATABASE ulr;"

# 3. Restore from backup
docker exec -i deploy-postgres-1 psql -U postgres -d ulr < backups/<backup-file>.sql

# 4. Verify row counts
docker exec deploy-postgres-1 psql -U postgres -d ulr \
  -c "SELECT table_name, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC;"

# 5. Restart services
docker compose -f deploy/docker-compose.yaml up -d
```

### Validate Restore

```bash
curl http://localhost:8100/health
curl http://localhost:8101/health
# Submit a test mission and confirm it stores correctly
```

---

## Disaster Recovery Playbook

### RTO / RPO Targets

| Metric | Target | How Achieved |
|--------|--------|-------------|
| **RTO** (Recovery Time Objective) | 30 minutes | Pre-built images + scripted restore |
| **RPO** (Recovery Point Objective) | 24 hours | Daily automated backups |
| **MTTR** (Mean Time to Recovery) | 15 minutes | Automated DR drill script with step-by-step playbook |

### DR Drill Execution

Run monthly to validate the playbook:

```powershell
# Full drill (requires running stack)
powershell -ExecutionPolicy Bypass -File scripts/dr_drill.ps1

# CI-safe dry-run (validates script logic without real disruption)
powershell -ExecutionPolicy Bypass -File scripts/dr_drill.ps1 -DryRun
```

The drill validates:
1. Service readiness before disruption
2. Fresh backup creation and file integrity check
3. Database readability post-backup
4. Recovery confirmation

### Phase 17 Evidence Bundle

For release hardening, pair the DR report with a fresh qualification summary and
Phase 17 evidence bundle:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dr_drill.ps1 -DryRun -Timestamp phase17_YYYYMMDD
python scripts/qualification_gate_summary.py --output-file docs/evidence/qualification_gate_summary_phase17_YYYY-MM-DD.json
python scripts/phase17_release_hardening_evidence.py `
  --dr-report-file reports/dr-drill-latest.json `
  --qualification-summary-file docs/evidence/qualification_gate_summary_phase17_YYYY-MM-DD.json `
  --output-file docs/evidence/phase17_dr_release_hardening_YYYY-MM-DD.json
```

`qualification_gate_summary.py` is allowed to return non-zero when required live
evidence is stale. That is the expected fail-closed release posture; do not
promote until the qualification suites are rerun and the promotion gate is
approved.

### Total Stack Loss — Step-by-Step

| Step | Action | Command |
|------|--------|---------|
| 1 | Verify host is reachable | `ping <host>` |
| 2 | Check Docker service | `docker info` |
| 3 | Clone/update repository | `git clone ... && cd theFactory` |
| 4 | Configure environment | `cp .env.example .env` then edit |
| 5 | Start stack | `docker compose -f deploy/docker-compose.yaml up -d --build` |
| 6 | Restore database | `scripts/restore_postgres.ps1 -BackupFile <latest>` |
| 7 | Verify health | `curl http://localhost:8100/health` |
| 8 | Run audit | `make audit` |
| 9 | Submit test mission | See Operations Runbook |
| 10 | Restore monitoring | `docker compose -f deploy/docker-compose.monitoring.yaml up -d` |

---

## Service Failure Playbooks

### Gateway Unreachable (`:8100`)

```bash
docker compose -f deploy/docker-compose.yaml logs api-gateway --tail 100
docker compose -f deploy/docker-compose.yaml restart api-gateway
```

Common causes: Redis unavailable · Port conflict · Invalid `.env` configuration

### Orchestrator Crash

```bash
docker compose -f deploy/docker-compose.yaml logs orchestrator --tail 200
# Check for migration failures or LangGraph errors
docker compose -f deploy/docker-compose.yaml restart orchestrator
```

If LangGraph is enabled and causing issues:
```bash
# Temporarily disable and restart
LANGGRAPH_ENABLED=false docker compose -f deploy/docker-compose.yaml up -d orchestrator
```

### Redis Stream Stall (Pod Workers Not Processing)

```bash
# Check consumer group lag
docker compose -f deploy/docker-compose.yaml exec redis \
  redis-cli XINFO GROUPS missions.intake

docker compose -f deploy/docker-compose.yaml exec redis \
  redis-cli XINFO GROUPS missions.state

# Restart workers
docker compose -f deploy/docker-compose.yaml restart pod-worker audit-worker
```

### Database Migration Failure

```bash
docker compose -f deploy/docker-compose.yaml logs orchestrator --tail 200 | grep -i migration
# Check for SQL errors, version conflicts, or permission issues
# If safe, manually apply the failing migration:
docker exec deploy-postgres-1 psql -U postgres -d <db> -f /path/to/migration.sql
```

---

## LangGraph Recovery Qualification

Run to validate Postgres checkpointer survives orchestrator restart:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/langgraph_postgres_recovery_qualification.ps1
```

Via make:
```bash
make langgraph-recovery
```

The script:
1. Starts orchestrator with `LANGGRAPH_ENABLED=true LANGGRAPH_CHECKPOINTER=postgres`
2. Submits a mission and confirms state entry
3. Injects orchestrator container restart
4. Validates mission recovery and completion
5. Writes JSON evidence to `docs/evidence/`

Previous qualification: `docs/evidence/phase26_langgraph_postgres_live_recovery_qualification_2026-03-03.json`

---

## Reliability Qualification

Run monthly or before major releases to validate sustained-load behavior:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/reliability_qualification.ps1 -InjectOrchestratorRestart
```

Via make:
```bash
make reliability
```

The script:
- Runs time-based sustained load (configurable duration)
- Monitors readiness endpoints throughout
- Injects a controlled disruption (orchestrator restart)
- Validates recovery within acceptable window
- Emits JSON evidence: `docs/evidence/reliability_qualification_baseline_*.json`

**Pass criteria:** Success rate ≥ 95% · p95 latency ≤ configured threshold · Recovery within 60s

---

## Mission Control E2E Verification

After any deployment, run the critical-path E2E suite:

```bash
cd apps/mission-control
npm run test:e2e
```

Or via make:
```bash
make test-ui-e2e
```

**6 journeys validated:**
1. Mission lifecycle (create → poll → complete)
2. Operations views (agent roster, summary)
3. Settings and vault key management
4. Builder preview (diff render)
5. Repository intake (GitHub metadata import)
6. Error-state handling (auth failure, 503)

---

## Automation Scripts Reference

| Script | Make Target | What It Does |
|--------|-------------|-------------|
| `scripts/pre_deploy_check.ps1` | `make predeploy` | Preflight validation suite |
| `scripts/backup_postgres.ps1` | `make backup` | PostgreSQL backup |
| `scripts/restore_postgres.ps1` | — | PostgreSQL restore from file |
| `scripts/dr_drill.ps1` | `make dr` | Disaster recovery drill |
| `scripts/perf_smoke.ps1` | `make perf` | Performance smoke test |
| `scripts/reliability_qualification.ps1` | `make reliability` | Sustained-load reliability test |
| `scripts/langgraph_postgres_recovery_qualification.ps1` | `make langgraph-recovery` | LangGraph checkpoint recovery test |
| `scripts/debug_sweep.ps1` | `make sweep` | Debug and code sweep |
| `scripts/production_review_audit.py` | `make audit` | 23-check production audit |
| `scripts/promotion_gate.py` | `make promotion-gate` | Release promotion policy evaluation |
