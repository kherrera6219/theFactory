# Microsoft Enterprise Operations & Disaster Recovery Playbook — theFactory / HGR

**Document version:** 2026.06.12  
**Last updated:** 2026-06-12  
**Status:** Approved / Canonical  
**Audience:** DevOps Engineers, Site Reliability Engineers (SRE), Operations Administrators  
**Security Classification:** Restricted — Internal Use Only

---

## 1. Operations & Logging Topology

theFactory is monitored via distributed OpenTelemetry (OTel) traces and structured JSON logging. System logs and trace events are forwarded through the following paths:

- **Logs Location**: Docker stdout/stderr captured by Promtail/Loki.
- **Trace Export**: Jaeger OTLP port `:4317` (internal) / HTTP `:16686` (operator dashboard).
- **Correlation Propagation**: Every operation carries a `X-Correlation-Id`. Traces within Qdrant, Neo4j, PostgreSQL, and Redis can be correlated to a single upstream operator request using this identifier.

---

## 2. Backup and Recovery Procedures

### 2.1. PostgreSQL State & Checkpoint Database
PostgreSQL is the single source of truth for mission lifecycles and agent slot states.

#### Backup Execution (Automated Cron / Manual)
Run a transactionally consistent snapshot of the database:
```bash
# Dump PostgreSQL schema and data via PgBouncer or direct port
docker exec -t deploy-postgres-1 pg_dump -U factory_user -d factory_db -F c -b -v -f /backups/postgres_snapshot_$(date +%F).bak
```

#### Recovery / Restore Execution
To restore state in the event of failure or database corruption:
```bash
# Drop, recreate, and restore from custom archive
docker exec -t deploy-postgres-1 dropdb -U factory_user factory_db
docker exec -t deploy-postgres-1 createdb -U factory_user -O factory_user factory_db
docker exec -t deploy-postgres-1 pg_restore -U factory_user -d factory_db -v /backups/postgres_snapshot_YYYY-MM-DD.bak
```

---

### 2.2. Redis Streams & Cache
Redis manages sliding window rate limits, idempotency cache locks, and event streams.

#### Snapshot Backup
Redis persists state automatically using Append-Only Files (AOF) and Redis Database (RDB) snapshots.
```bash
# Force a synchronous RDB dump
docker exec -t deploy-redis-1 redis-cli -p 6380 SAVE
# Copy dump out of container
docker cp deploy-redis-1:/data/dump.rdb /backups/redis_snapshot_$(date +%F).rdb
```

#### Recovery Procedure
Stop Redis, copy the `dump.rdb` back into place, and restart:
```bash
docker stop deploy-redis-1
cp /backups/redis_snapshot_YYYY-MM-DD.rdb /deploy/redis/data/dump.rdb
docker start deploy-redis-1
```

---

## 3. Disaster Recovery (DR) Protocol

### RTO and RPO Targets
- **Recovery Time Objective (RTO)**: ≤ 30 minutes (Evidenced recovery baseline: **37.13s**).
- **Recovery Point Objective (RPO)**: ≤ 1 hour.

### 3.1. Disaster Recovery Scenario: Full Node Outage
1. **Provision Node**: Spin up equivalent Linux / Windows host server.
2. **TLS Key Provisioning**: Generate database and caching TLS keys:
   ```bash
   make tls-certs
   ```
3. **Environment Setup**: Load `.env.example` to `.env` and verify key configurations (e.g. `PGBOUNCER_HOST_PORT=5434`).
4. **Deploy Stack**: Launch compose stack:
   ```bash
   docker compose -f deploy/docker-compose.yaml --env-file .env up -d
   ```
5. **Database Restore**: Apply latest PostgreSQL and Redis backups (see Section 2).

---

## 4. Incident Response Runbooks

### 4.1. Incident 1: Protocol Bus Backpressure / 503 Errors
*Symptom*: Clients receive `FACTORY-BUS-503X` or gateway rate-limiting blocks.

#### Diagnostics
Check Redis Stream lengths:
```bash
docker exec -t deploy-redis-1 redis-cli -p 6380 XLEN alpha
docker exec -t deploy-redis-1 redis-cli -p 6380 XLEN beta
```
If any stream exceeds 10,000 events, pod-worker consumption has stalled.

#### Remediation
1. Verify pod-worker health and logs:
   ```bash
   docker compose -f deploy/docker-compose.yaml ps
   docker logs deploy-pod-worker-1 --tail 100
   ```
2. Restart workers if stalled:
   ```bash
   docker compose -f deploy/docker-compose.yaml restart pod-worker
   ```

---

### 4.2. Incident 2: PostgreSQL Port Bind Failures
*Symptom*: `deploy-postgres-1` or PgBouncer containers fail to start.

#### Diagnostics
Check system port allocation:
```powershell
Get-NetTCPConnection -LocalPort 5432 -ErrorAction SilentlyContinue
```
If port 5432 is occupied by a host PostgreSQL instance, the Docker port allocation will bind-fail.

#### Remediation
1. Edit `.env` in the root workspace.
2. Change the host port binding configuration:
   ```ini
   PGBOUNCER_HOST_PORT=5434
   ```
3. Re-launch the stack:
   ```bash
   docker compose -f deploy/docker-compose.yaml --env-file .env up -d
   ```

---

### 4.3. Incident 3: Qdrant Semantic Sync Mismatch
*Symptom*: Code generation phases fallback to hash-based routing due to knowledge retrieval failures.

#### Diagnostics
Verify Qdrant service response:
```bash
curl -s http://localhost:6333/readyz
```

#### Remediation
If Qdrant is online but data-drift has occurred, trigger an active rebuild of the index:
1. Trigger a fresh intake mission to re-index the relevant source docs.
2. Run the offline evals to confirm semantic boost behaves correctly:
   ```bash
   make eval
   ```
