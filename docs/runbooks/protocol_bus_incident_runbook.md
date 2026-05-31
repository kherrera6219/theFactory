# Incident Runbook — Protocol Bus

Document version: 2026.05.30  
Last updated: 2026-05-30  
Status: Canonical  
Audience: Operators, developers, maintainers, and auditors

**Applies to:** Protocol Bus MCP service (`:8102`), Redis Streams-based event routing, protocol message failures
**Impact:** When the protocol bus is degraded, agent-to-agent protocol messages fail or are dropped to the DLQ. Core mission HTTP flow continues unaffected.

---

## Alert Summary

| Symptom | Severity | Signs |
|---------|----------|-------|
| Protocol Bus MCP down | HIGH | `http://localhost:8102/health` returns non-200 or no response |
| Protocol validation failures | MEDIUM | Messages appear in DLQ (`GET /dlq?protocol=<name>`) |
| Redis stream stall | HIGH | Consumer group lag growing; agents not receiving messages |
| DLQ growing | MEDIUM | `/dlq` returns increasing message count across protocols |
| Replay rejection (409) | LOW | `POST /send` returns 409 — duplicate correlation-id within TTL window. Expected behavior, not an incident unless the rate is high. |
| Redis unavailability causing 503 | HIGH | `POST /send` returns 503 with "Dedup service unavailable" or "Backpressure service unavailable" — Redis is unreachable. Treat as a Redis incident. |

---

## Step 0 — New Behavior Reference

As of PR #188, the protocol bus now:
- Returns HTTP 409 when a duplicate correlation-id is detected within the replay TTL window
- Returns HTTP 503 (not silently pass) when Redis is unreachable for dedup or backpressure checks
- Checks backpressure depth on ALL resolved channels, not just the first

These are improvements. A 503 means Redis is down; a 409 means a legitimate replay rejection.

---

## Step 1 — Confirm Status

```bash
# Check service health
curl http://localhost:8102/health

# Check container status
docker compose -f deploy/docker-compose.yaml ps protocol-bus-mcp

# Check recent logs
docker compose -f deploy/docker-compose.yaml logs protocol-bus-mcp --tail 100
```

---

## Step 2 — Check Redis Streams

```bash
# List all stream consumer groups
docker compose -f deploy/docker-compose.yaml exec redis \
  redis-cli XINFO GROUPS missions.intake

docker compose -f deploy/docker-compose.yaml exec redis \
  redis-cli XINFO GROUPS missions.state

# Check pending message count (lag)
docker compose -f deploy/docker-compose.yaml exec redis \
  redis-cli XPENDING missions.state protocol-bus-group - + 10

# Check stream length
docker compose -f deploy/docker-compose.yaml exec redis \
  redis-cli XLEN missions.state
```

**High lag (> 100 pending)** indicates the protocol bus is not consuming. Restart the consumer.

**Zero-length streams with healthy lag** may indicate the stream keys were flushed — check for Redis restarts.

---

## Step 3 — Check DLQ

```bash
# Check DLQ for each protocol
for proto in alpha beta delta sigma omega rho; do
  echo "=== $proto ==="
  curl -s "http://localhost:8102/dlq?protocol=$proto" | jq 'length'
done
```

### Interpret DLQ Results

| DLQ Count | Likely Cause |
|-----------|-------------|
| 0 | No failures — MCP is routing successfully |
| 1-5 | Isolated message format errors — check sender logic |
| > 10 | Systematic validation failure — schema or sender mismatch |
| Growing | MCP consuming but failing — investigate validation errors |

---

## Step 4 — Diagnose Protocol Failures

```bash
# Inspect DLQ messages for specific protocol
curl http://localhost:8102/dlq?protocol=alpha | jq '.[0]'
```

Check for:
- Missing required fields (`schema_version`, `protocol`, `sender`, `recipient`, `priority`, `payload`)
- `x-agent-id` header mismatch with message `sender` field
- Invalid protocol value (must be `alpha|beta|delta|sigma|omega|rho`)
- Payload not matching protocol schema

Reference: `schemas/event.envelope.schema.json`

---

## Step 5 — Remediate

### Restart Protocol Bus MCP

```bash
docker compose -f deploy/docker-compose.yaml restart protocol-bus-mcp
```

After restart:
```bash
curl http://localhost:8102/health
curl http://localhost:8102/readyz
```

### Drain and Replay DLQ (if messages are valid but routing failed)

```bash
# Get DLQ messages
curl http://localhost:8102/dlq?protocol=alpha > /tmp/dlq-alpha.json

# Replay each message
# Note: Manual replay is a POST to /send with the same payload and correct headers
```

### Redis Stream Recovery (if stream was flushed or corrupt)

```bash
# Force consumer group reset (use ONLY if stream is confirmed clean)
docker compose -f deploy/docker-compose.yaml exec redis \
  redis-cli XGROUP SETID missions.state protocol-bus-group '$'

# Restart all consumers
docker compose -f deploy/docker-compose.yaml restart protocol-bus-mcp pod-worker audit-worker
```

---

## Step 6 — Verify Recovery

```bash
# Health and readiness
curl http://localhost:8102/health
curl http://localhost:8102/readyz

# Send a test message
curl -X POST http://localhost:8102/send \
  -H "x-api-key: mcp-local-key" \
  -H "x-agent-id: AGENT-02-CEO" \
  -H "Content-Type: application/json" \
  -d '{
    "schema_version": "v1",
    "protocol": "sigma",
    "sender": "AGENT-02-CEO",
    "recipient": "AGENT-01-PM",
    "priority": "low",
    "payload": {"schema_version": "v1", "priority": "low", "status": "runbook-test"}
  }'

# Confirm DLQ is clear
curl http://localhost:8102/dlq?protocol=sigma | jq 'length'
```

---

## Escalation

If protocol bus does not recover within 15 minutes:
1. Check Redis cluster health: `docker compose logs redis --tail 200`
2. Check for memory pressure: `docker stats`
3. Consider temporary bypass: agents can fall back to direct REST if bus is unavailable
4. Document the incident and DLQ payload samples for postmortem

---

## Related

- Protocol schemas: `schemas/event.envelope.schema.json`
- Topic catalog: `protocol/topics.yaml`
- MCP API docs: `docs/API_INTEGRATION_GUIDE.md#protocol-bus-mcp`
- Observability: `docs/OBSERVABILITY_STACK.md`
