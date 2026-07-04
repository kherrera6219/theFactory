# Disaster Recovery Validation Runbook

Document version: 2026.07.03  
Last updated: 2026-07-03  
Status: Canonical  
Audience: Platform Engineering, maintainers, and on-call responders

**Owner:** Platform Engineering  
**Review Cycle:** Quarterly

---

## Overview

This runbook documents the procedures and success criteria for validating theFactory's disaster recovery capabilities. All drills must be executed and evidenced before a production release promotion.

**RTO Target:** Full stack cold-start in ≤ 30 minutes (matches `docs/DEPLOYMENT_DR_PLAYBOOK.md`'s canonical RTO/RPO table; this runbook's own MTTR sub-target for the automated drill script is 15 minutes — the two numbers are not interchangeable)
**RPO Target:** Zero mission data loss (PostgreSQL WAL-based)

---

## Drill 1 — PostgreSQL Backup and Point-in-Time Restore

### Prerequisites
- Docker Compose stack running (`make up`)
- At least one mission in COMPLETE state
- `pg_dump` accessible in the postgres container

### Procedure

```bash
# Step 1: Record mission count before backup
docker compose exec postgres psql -U postgres ulr -c "SELECT COUNT(*) FROM missions;"
# Save output to docs/evidence/dr/drill-1-before-count.txt

# Step 2: Create backup
docker compose exec postgres pg_dump -U postgres ulr > /tmp/ulr_backup_$(date +%Y%m%d_%H%M%S).sql
# Save to docs/evidence/dr/drill-1-backup.sql

# Step 3: Verify backup integrity
wc -l /tmp/ulr_backup_*.sql
# Should be > 50 lines (non-empty)

# Step 4: Simulate restore (test DB)
docker compose exec postgres psql -U postgres -c "CREATE DATABASE ulr_restore_test;"
docker compose exec postgres psql -U postgres ulr_restore_test < /tmp/ulr_backup_*.sql
docker compose exec postgres psql -U postgres ulr_restore_test -c "SELECT COUNT(*) FROM missions;"
# Count must match Step 1

# Step 5: Cleanup
docker compose exec postgres psql -U postgres -c "DROP DATABASE ulr_restore_test;"
```

### Success Criteria
- [ ] Backup file created and non-empty
- [ ] Mission count matches before/after restore
- [ ] No errors in restore output
- [ ] Restore completed in < 5 minutes

### Evidence
Save to: `docs/evidence/dr/drill-1-postgres-restore-YYYYMMDD.md`

---

## Drill 2 — Full Stack Cold-Start

### Prerequisites
- No running containers (clean state)
- `.env` file configured with valid credentials
- `make` available

### Procedure

```bash
# Step 1: Record start time
date | tee /tmp/dr-drill2-start.txt

# Step 2: Stop everything (if running). Always pair both compose files even
# for a teardown -- a base-file-only `down -v` leaves dedicated-agent overlay
# containers orphaned instead of stopping them, which has caused a real
# restart-cascade incident in this project (see docs/OPERATIONS_RUNBOOK.md).
docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml down -v 2>/dev/null || true

# Step 3: Cold start
make up

# Step 4: Wait for health checks
sleep 30

# Step 5: Verify API gateway health
curl -f http://localhost:8100/health | python3 -m json.tool
# Should return: {"status": "healthy", ...}

# Step 6: Verify orchestrator health
curl -f http://localhost:8101/health | python3 -m json.tool

# Step 7: Create test mission
curl -s -X POST http://localhost:8100/v1/missions \
  -H "Content-Type: application/json" \
  -H "x-api-key: $ORCHESTRATOR_ADMIN_API_KEY" \
  -d '{"prompt": "DR validation mission"}' | python3 -m json.tool

# Step 8: Record end time and calculate elapsed
date | tee /tmp/dr-drill2-end.txt
```

### Success Criteria
- [ ] All containers healthy within 5 minutes of `make up`
- [ ] API gateway responds to `/health` with 200
- [ ] Orchestrator responds to `/health` with 200
- [ ] Test mission created successfully (state: INTAKE or QUEUED)
- [ ] Total elapsed time ≤ 15 minutes

### Evidence
Save to: `docs/evidence/dr/drill-2-cold-start-YYYYMMDD.md`

---

## Drill 3 — Orchestrator Failure + LangGraph Checkpoint Recovery

### Prerequisites
- LangGraph enabled (`LANGGRAPH_ENABLED=true`, `LANGGRAPH_CHECKPOINTER=postgres`)
- One mission in RUNNING or QUEUED state

### Procedure

```bash
# Step 1: Create a mission and wait for RUNNING
MISSION_ID=$(curl -s -X POST http://localhost:8100/v1/missions \
  -H "Content-Type: application/json" \
  -H "x-api-key: $ORCHESTRATOR_ADMIN_API_KEY" \
  -d '{"prompt": "DR checkpoint recovery test", "requested_target_language": "python"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['mission_id'])")
echo "Mission: $MISSION_ID"

# Step 2: Verify initial state
curl -s http://localhost:8100/v1/missions/$MISSION_ID | python3 -m json.tool

# Step 3: Kill the orchestrator container
docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml stop orchestrator
echo "Orchestrator stopped at $(date)"

# Step 4: Wait 10 seconds
sleep 10

# Step 5: Restart orchestrator
docker compose start orchestrator
sleep 15

# Step 6: Verify mission resumed (should not be FAILED)
curl -s http://localhost:8100/v1/missions/$MISSION_ID | python3 -m json.tool
# State should be RUNNING, QUEUED, or COMPLETE — NOT FAILED
```

### Success Criteria
- [ ] Orchestrator restarts cleanly (< 30 seconds)
- [ ] Mission does NOT transition to FAILED during outage
- [ ] After restart, mission resumes processing or is in a valid terminal state
- [ ] No data loss in PostgreSQL checkpoint store

### Evidence
Save to: `docs/evidence/dr/drill-3-checkpoint-recovery-YYYYMMDD.md`

---

## Drill 4 — Redis Failure + Stream Recovery

### Prerequisites
- Redis running with data in `missions.intake` or `missions.state` streams

### Procedure

```bash
# Step 1: Check stream lengths
docker compose exec redis redis-cli XLEN missions.intake
docker compose exec redis redis-cli XLEN missions.state

# Step 2: Create a mission (queues to Redis intake)
curl -s -X POST http://localhost:8100/v1/missions \
  -H "Content-Type: application/json" \
  -H "x-api-key: $ORCHESTRATOR_ADMIN_API_KEY" \
  -d '{"prompt": "Redis recovery DR test"}' | python3 -m json.tool

# Step 3: Stop Redis
docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml stop redis
echo "Redis stopped at $(date)"

# Step 4: Attempt mission creation — should get a graceful error (not crash)
curl -v -X POST http://localhost:8100/v1/missions \
  -H "Content-Type: application/json" \
  -H "x-api-key: $ORCHESTRATOR_ADMIN_API_KEY" \
  -d '{"prompt": "Mission during Redis outage"}'
# Expected: 503 or 500 with human-readable error

# Step 5: Restart Redis
docker compose start redis
sleep 10

# Step 6: Verify health restored
curl -f http://localhost:8100/health | python3 -m json.tool
```

### Success Criteria
- [ ] API Gateway returns graceful error (not unhandled exception) during Redis outage
- [ ] After Redis restart, `/health` returns healthy
- [ ] Previously queued missions are resumed (XAUTOCLAIM handling)
- [ ] No permanent data loss

### Evidence
Save to: `docs/evidence/dr/drill-4-redis-recovery-YYYYMMDD.md`

---

## Evidence Template

Each drill must produce a markdown evidence file with:

```markdown
# DR Drill [N] — [Name] Evidence

**Date:** YYYY-MM-DD HH:MM UTC
**Operator:** [name]
**Environment:** local / staging / production

## Command Outputs

[Paste terminal output here]

## Timings

- Start: HH:MM:SS
- First healthy response: HH:MM:SS
- Completion: HH:MM:SS
- Total elapsed: X minutes Y seconds

## Success Criteria Checklist

- [x] Criterion 1
- [x] Criterion 2
- [ ] Criterion 3 — FAILED (explain)

## Verdict

PASS / PARTIAL / FAIL

## Notes

[Any observations, deviations, or follow-up items]
```

---

## Schedule

**Stale as of 2026-07-03:** the "Next Due" dates below are all in the past with no
recorded "Last Run" — this table has not been kept current with actual drill execution.
Confirm current status with whoever owns DR drills before treating any row as accurate,
and update this table (or replace the static dates with a rolling "N days since last run"
convention) once real drill history is available.

| Drill | Frequency | Last Run | Next Due | Status |
|-------|-----------|----------|----------|--------|
| 1 — PG Backup/Restore | Monthly | — | 2026-04-30 | NOT RUN (stale) |
| 2 — Cold Start | Before each release | — | Before next tag | NOT RUN (stale) |
| 3 — Checkpoint Recovery | Quarterly | — | 2026-06-30 | NOT RUN (stale) |
| 4 — Redis Recovery | Quarterly | — | 2026-06-30 | NOT RUN (stale) |

---

## References

- `deploy/docker-compose.yaml` — base stack configuration
- `docs/DEPLOYMENT_DR_PLAYBOOK.md` — deployment and recovery guidance
- `docs/evidence/dr/` — evidence archive directory
- `Makefile` targets: `make up`, `make down`, `make test`
