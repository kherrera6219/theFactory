# API Integration Guide

**Last updated:** 2026-03-07
**Base URLs:** Gateway `http://localhost:8100` · Semantic Bus MCP `http://localhost:8102`
**OpenAPI specs:** [`docs/openapi/api-gateway.v1.json`](openapi/api-gateway.v1.json) · [`docs/openapi/orchestrator.v1.json`](openapi/orchestrator.v1.json)

---

## Table of Contents

- [Authentication](#authentication)
- [Rate Limits](#rate-limits)
- [Mission API](#mission-api)
- [Operations API](#operations-api)
- [Live Transport (SSE)](#live-transport-sse)
- [Semantic Bus MCP](#semantic-bus-mcp)
- [Dedicated-Agent Routing](#dedicated-agent-routing)
- [Error Codes](#error-codes)
- [SDK & Client Examples](#sdk--client-examples)

---

## Authentication

### Auth Modes

The gateway supports three authentication modes controlled by `AUTH_MODE`:

| Mode | Header | Description |
|------|--------|-------------|
| `api_key` (default) | `x-api-key: <key>` | API key for all mutation routes |
| `hybrid` | `x-api-key` or `Authorization: Bearer <jwt>` | API key or JWT/OIDC accepted |
| `oidc` | `Authorization: Bearer <jwt>` | JWT/OIDC required for mutations |

### RBAC Roles

| Role | Key Variable | Permissions |
|------|-------------|------------|
| `admin` | `ADMIN_API_KEY` | Full access (all routes + diagnostics) |
| `operator` | `GATEWAY_API_KEY` | Mission mutations + operations reads |
| `reader` | `READER_API_KEY` | Read-only access (GET routes only) |
| `worker` | `INTERNAL_SERVICE_API_KEY` | Internal pod/audit worker calls |

### API Key Header

```http
POST /v1/missions HTTP/1.1
x-api-key: your-operator-key
Content-Type: application/json
```

### JWT/OIDC Bearer (hybrid or oidc mode)

```http
POST /v1/missions HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiJ9...
Content-Type: application/json
```

Configure OIDC:
```bash
OIDC_ISSUER_URL=https://your-idp/.well-known/openid-configuration
OIDC_AUDIENCE=holygrail-api
```

---

## Rate Limits

| Limit | Value | Scope |
|-------|-------|-------|
| Requests per minute | 120 | Per API key (sliding window) |
| Mission payload size | 1 MB | Per request |
| Idempotency key TTL | 24 hours | Per key |

**Response headers on rate-limited requests:**
```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1709856000
Retry-After: 60
```

---

## Mission API

### Create Mission

```http
POST /v1/missions
x-api-key: <operator-key>
Idempotency-Key: <unique-key>
Content-Type: application/json

{
  "prompt": "Build a REST API for user authentication",
  "requested_target_language": "python",
  "metadata": {
    "source": "api",
    "selected_agent_id": "AGENT-12-PODA-MGR",
    "priority": "high"
  }
}
```

**Response `201 Created`:**
```json
{
  "mission_id": "mission-uuid-here",
  "state": "QUEUED",
  "created_at": "2026-03-07T19:00:00Z"
}
```

> **Idempotency:** Include `Idempotency-Key` header for replay-safe creation. Duplicate requests within 24h return the original mission ID.

### List Missions

```http
GET /v1/missions?state=RUNNING&limit=20&offset=0
x-api-key: <any-key>
```

**Query parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `state` | string | Filter by state: `QUEUED`, `RUNNING`, `VERIFIED`, `COMPLETE`, `FAILED` |
| `limit` | int | Results per page (default: 20, max: 100) |
| `offset` | int | Pagination offset |

### Get Mission Detail

```http
GET /v1/missions/{mission_id}
x-api-key: <any-key>
```

**Response:**
```json
{
  "mission_id": "mission-uuid",
  "state": "RUNNING",
  "prompt": "Build a REST API...",
  "requested_target_language": "python",
  "created_at": "2026-03-07T19:00:00Z",
  "updated_at": "2026-03-07T19:01:30Z",
  "metadata": { "source": "api" },
  "pod_assignments": [
    { "pod": "podA", "language": "python", "assigned_at": "..." }
  ]
}
```

### Get Mission Events

```http
GET /v1/missions/{mission_id}/events?limit=50
x-api-key: <any-key>
```

Returns all lifecycle events for a mission, ordered by timestamp. Use for timeline reconstruction and Smelt-cycle phase mapping.

### Emit State Transition

```http
POST /v1/missions/{mission_id}/state
x-api-key: <operator-key>
Content-Type: application/json

{
  "new_state": "FAILED",
  "expected_state": "RUNNING",
  "reason": "Manual operator cancellation"
}
```

> **Note:** `expected_state` is optional but recommended for optimistic concurrency.

### Get Knowledge Graph (feature-flagged)

```http
GET /v1/missions/{mission_id}/knowledge-graph
x-api-key: <any-key>
```

Returns Neo4j graph data for the mission. Returns `501 Not Implemented` if `NEO4J_ENABLED=false`.

### Get Audit Artifacts (feature-flagged)

```http
GET /v1/missions/{mission_id}/audit-artifacts
x-api-key: <any-key>
```

Returns object storage artifact references. Returns `501 Not Implemented` if `OBJECT_STORAGE_ENABLED=false`.

---

## Operations API

### Runtime Summary

```http
GET /v1/operations/summary
x-api-key: <any-key>
```

Returns system-wide health: mission counts by state, agent counts by state, uptime.

### Agent Registry (all 35 agents)

```http
GET /v1/operations/agents
x-api-key: <any-key>
```

**Response structure:**
```json
{
  "total_agents": 35,
  "agents": [
    {
      "agent_id": "AGENT-01-PM",
      "state": "IDLE",
      "queue_depth": 0,
      "active_mission_id": null,
      "heartbeat_age_seconds": 45,
      "persona_profile": {
        "job_role": "...",
        "standards_alignment": "NIST AI RMF · ISO/IEC 42001"
      }
    }
  ]
}
```

### Agent Integrations (protocol + LLM + persona)

```http
GET /v1/operations/agent-integrations
x-api-key: <any-key>
```

Returns per-agent LLM provider/model recommendations, protocol assignments, data-system assignments, and full persona profiles with standards evidence metadata.

---

## Live Transport (SSE)

Subscribe to real-time mission state using Server-Sent Events:

```http
GET /v1/stream/state?mission_id={id}
x-api-key: <any-key>
Accept: text/event-stream
```

**JavaScript client:**

```javascript
const source = new EventSource(
  `http://localhost:8100/v1/stream/state?mission_id=${missionId}`,
  { headers: { 'x-api-key': 'your-key' } }
);

source.addEventListener('mission_state', (event) => {
  const data = JSON.parse(event.data);
  console.log('State:', data.state);
});

source.addEventListener('mission_event', (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data.event_type, data.payload);
});

source.onerror = () => {
  // Fall back to polling
};
```

**Features:**
- `Last-Event-ID` header for stream resume on reconnect
- Keepalive frames every 15s (`: keepalive` comment events)
- `mission_id` filter — only receives events for the specified mission
- `stream|poll|paused` mode diagnostics in Mission Control UI

---

## Semantic Bus MCP

### Send Message

```http
POST /send
x-api-key: <mcp-key>
x-agent-id: AGENT-02-CEO
Content-Type: application/json

{
  "schema_version": "v1",
  "protocol": "alpha",
  "sender": "AGENT-02-CEO",
  "recipient": "AGENT-12-PODA-MGR",
  "priority": "high",
  "payload": {
    "schema_version": "v1",
    "priority": "high",
    "target_pod": "podA",
    "directive_type": "mission_assignment",
    "directive": {
      "mission_id": "mission-uuid"
    }
  }
}
```

**Protocols:**

| Protocol | Sender Tier | Recipient Tier | Purpose |
|----------|-------------|---------------|---------|
| `alpha` | CEO | Pod Managers | Mission assignment directives |
| `beta` | Pod Workers | CEO | Mission progress reports |
| `delta` | Pods | Specialists | Specialist delegation |
| `sigma` | Any | Operations | Status and health signals |
| `omega` | Audit | Orchestrator | Verification results |
| `rho` | System | System | Internal control messages |

### Inspect Dead-Letter Queue

```http
GET /dlq?protocol=alpha
x-api-key: <mcp-key>
```

Returns messages that failed schema validation or routing.

---

## Dedicated-Agent Routing

When using the `--profile dedicated-agents` compose profile, pod workers enforce `AGENT_BINDING`.

### How Routing Works

A dedicated worker processes a mission only if its bound agent ID matches the resolved mission agent. Resolution order:

1. State payload keys: `agent_id`, `target_agent_id`, `selected_agent_id`, `assigned_agent_id`
2. Mission `metadata` keys: `metadata.agent_id`, `metadata.target_agent_id`, `metadata.selected_agent_id`, `metadata.assigned_agent_id`
3. Orchestrator mission metadata fallback (GET `/missions/{id}`)

**Recommended pattern — include agent in mission metadata at creation:**

```bash
curl -X POST http://localhost:8100/v1/missions \
  -H "x-api-key: your-key" \
  -H "Idempotency-Key: my-mission-001" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze this Python module",
    "requested_target_language": "python",
    "metadata": {
      "selected_agent_id": "AGENT-14-PY"
    }
  }'
```

---

## Error Codes

| HTTP Status | Code | When |
|-------------|------|------|
| `400` | Bad Request | Malformed JSON or invalid request shape |
| `401` | Unauthorized | Missing or invalid API key / JWT |
| `403` | Forbidden | Key lacks required role for operation |
| `404` | Not Found | Mission ID does not exist |
| `409` | Conflict | State transition not valid from current state |
| `413` | Payload Too Large | Body exceeds 1MB limit |
| `422` | Unprocessable Entity | Schema validation failure |
| `429` | Too Many Requests | Rate limit exceeded (check `Retry-After` header) |
| `501` | Not Implemented | Feature flag disabled (Neo4j / object storage) |
| `503` | Service Unavailable | Dependency unavailable (typically Redis or Postgres) |

---

## SDK & Client Examples

### curl — Create and Poll a Mission

```bash
# Create
MISSION=$(curl -s -X POST http://localhost:8100/v1/missions \
  -H "x-api-key: dev-key-mutate" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Build auth service","requested_target_language":"python"}')

MISSION_ID=$(echo $MISSION | jq -r '.mission_id')
echo "Mission: $MISSION_ID"

# Poll until complete
while true; do
  STATE=$(curl -s http://localhost:8100/v1/missions/$MISSION_ID | jq -r '.state')
  echo "State: $STATE"
  [[ "$STATE" == "COMPLETE" || "$STATE" == "FAILED" ]] && break
  sleep 5
done
```

### Python — Full Mission Flow

```python
import httpx
import time

GATEWAY = "http://localhost:8100"
API_KEY = "dev-key-mutate"

def create_mission(prompt: str, language: str) -> str:
    resp = httpx.post(
        f"{GATEWAY}/v1/missions",
        headers={"x-api-key": API_KEY, "Idempotency-Key": prompt[:32]},
        json={"prompt": prompt, "requested_target_language": language},
    )
    resp.raise_for_status()
    return resp.json()["mission_id"]

def wait_for_completion(mission_id: str, timeout: int = 120) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = httpx.get(
            f"{GATEWAY}/v1/missions/{mission_id}",
            headers={"x-api-key": API_KEY},
        )
        data = resp.json()
        if data["state"] in ("COMPLETE", "FAILED"):
            return data
        time.sleep(5)
    raise TimeoutError(f"Mission {mission_id} did not complete within {timeout}s")

# Usage
mission_id = create_mission("Build a REST API", "python")
result = wait_for_completion(mission_id)
print(f"Mission {mission_id}: {result['state']}")
```
