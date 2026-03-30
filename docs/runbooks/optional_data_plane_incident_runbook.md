# Incident Runbook — Optional Data-Plane (Neo4j / Object Storage)

Document version: 2026.03.29  
Last updated: 2026-03-29  
Status: Canonical  
Audience: Operators, developers, maintainers, and auditors

**Applies to:** Alerts `Neo4jAdapterNotReady`, `ObjectStorageAdapterNotReady`, `Neo4jMirrorWriteErrorRateHigh`, `ObjectStorageMirrorWriteErrorRateHigh`, `Neo4jMirrorWriteLatencyP95High`, `ObjectStorageMirrorWriteLatencyP95High`
**Impact:** Optional — core mission flow is unaffected when these adapters are down. Only graph queries and artifact retention are degraded.

---

## Alert Summary

| Alert | Severity | Condition | SLO Impact |
|-------|----------|-----------|-----------|
| `Neo4jAdapterNotReady` | HIGH | Neo4j readiness gauge = 0 for > 2 min | Knowledge graph queries return 501 |
| `ObjectStorageAdapterNotReady` | HIGH | Object storage readiness gauge = 0 for > 2 min | Artifact retention disabled |
| `Neo4jMirrorWriteErrorRateHigh` | HIGH | Mirror write error rate > 5% for > 5 min | LogicNodes not mirrored to graph |
| `ObjectStorageMirrorWriteErrorRateHigh` | HIGH | Mirror write error rate > 5% for > 5 min | Artifacts not written to object store |
| `Neo4jMirrorWriteLatencyP95High` | HIGH | p95 latency > 2s for > 5 min | Slow graph writes, backpressure risk |
| `ObjectStorageMirrorWriteLatencyP95High` | HIGH | p95 latency > 2s for > 5 min | Slow artifact writes, backpressure risk |

---

## Step 1 — Confirm Alert and Scope

```bash
# Check which adapters are affected
curl http://localhost:8101/health | jq '.neo4j_ready, .object_storage_ready'

# Check adapter metrics
curl http://localhost:8101/metrics | grep "orchestrator_optional_adapter_"

# Check feature flags
docker compose -f deploy/docker-compose.yaml exec orchestrator \
  printenv NEO4J_ENABLED OBJECT_STORAGE_ENABLED
```

---

## Step 2 — Diagnose the Adapter

### Neo4j Not Ready

```bash
# Check if Neo4j container is running
docker compose -f deploy/docker-compose.yaml ps neo4j

# Check Neo4j logs
docker compose -f deploy/docker-compose.yaml logs neo4j --tail 100

# Test connectivity from orchestrator
docker compose -f deploy/docker-compose.yaml exec orchestrator \
  curl -s http://neo4j:7474/db/data/ | head -50
```

Common causes:
- Neo4j container OOMkilled (check resources)
- Memory heap limit exceeded (increase `NEO4J_dbms_memory_heap_max__size`)
- Authentication failure (check `NEO4J_AUTH` match)
- Volume full (check disk space)

### Object Storage Not Ready

```bash
# Check MinIO/S3 container
docker compose -f deploy/docker-compose.yaml ps minio

# Check MinIO logs
docker compose -f deploy/docker-compose.yaml logs minio --tail 100

# Test MinIO endpoint
curl http://localhost:9000/minio/health/live
```

Common causes:
- MinIO container not started (start extended profile)
- S3 endpoint unreachable (check `OBJECT_STORAGE_ENDPOINT` in `.env`)
- Bad credentials (check `OBJECT_STORAGE_ACCESS_KEY`, `OBJECT_STORAGE_SECRET_KEY`)

---

## Step 3 — Remediate

### Restart Adapter Service

```bash
# Restart Neo4j
docker compose -f deploy/docker-compose.yaml restart neo4j

# Restart MinIO
docker compose -f deploy/docker-compose.yaml restart minio
```

### Restart Orchestrator (after adapter is back)

```bash
docker compose -f deploy/docker-compose.yaml restart orchestrator
```

The orchestrator re-checks adapter readiness on startup. The health endpoint should show `neo4j_ready: true` within 30 seconds.

### Disable the Adapter Temporarily (if broken and blocking)

```bash
# Temporarily disable and restart orchestrator
NEO4J_ENABLED=false docker compose -f deploy/docker-compose.yaml up -d orchestrator
```

Core mission flow will continue; only graph-dependent features degrade.

---

## Step 4 — Run Live Qualification

After recovery, run disruption tests to validate:

```bash
LIVE_ENABLE_DISRUPTION_TESTS=true make test-live-extended
```

These tests validate Neo4j and MinIO disruption recovery behavior.

---

## Step 5 — Verify Recovery

```bash
# Adapter readiness back up
curl http://localhost:8101/health | jq '.neo4j_ready, .object_storage_ready'

# Error rate back to baseline
curl http://localhost:8101/metrics | grep "mirror_writes_total"

# Check alert resolved in Alertmanager
curl http://localhost:9093/api/v2/alerts | jq '[.[] | select(.status.state == "firing")]'
```

---

## Escalation

If adapter does not recover within 30 minutes of container restart:
1. Check host disk and memory resources
2. Review Docker Engine log for OOM events
3. Consider disabling the adapter and continuing on core path
4. File an incident report with the adapter error logs

---

## Related

- Alert config: `deploy/monitoring/prometheus/rules/thefactory-alerts.yml`
- Metrics reference: `docs/OBSERVABILITY_STACK.md`
- Live qualification: `tests/services/test_live_neo4j_minio_disruption.py`
