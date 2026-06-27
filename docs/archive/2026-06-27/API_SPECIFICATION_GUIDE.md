# Microsoft Enterprise Standard API Specification — theFactory / HGR

**Document version:** 2026.06.12  
**Last updated:** 2026-06-12  
**Status:** Approved / Canonical  
**Audience:** Integration Engineers, Application Developers, Security Architects  
**Security Classification:** Restricted — Internal Use Only

---

## 1. Overview & Base URLs

theFactory exposes its public API surface through the API Gateway, which handles rate limiting, authentication, and request correlation. Internal operations APIs are hosted on the Orchestrator and are accessible only within the private virtual network.

| Component | Network Context | Default Base URL |
|---|---|---|
| **API Gateway** | Public / External | `http://localhost:8100` |
| **Orchestrator** | Private / Internal | `http://localhost:8101` |
| **Protocol Bus MCP** | Private / Internal | `http://localhost:8102` |

---

## 2. Authentication & Authorization

All public API requests must include authentication credentials. The gateway supports three authentication modes configured via the `AUTH_MODE` environment variable.

### 2.1. API Key Mode (`AUTH_MODE=api_key`)
Requests must supply a valid key in the `x-api-key` custom header. Per-key permissions map to gateway roles (admin, operator, reader, worker).
```http
x-api-key: hgr_live_6380a9bc4f3d2e...
```

### 2.2. OIDC Bearer Mode (`AUTH_MODE=oidc`)
Requests must supply a standard OAuth 2.0 JWT access token in the `Authorization` header.
```http
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 2.3. Hybrid Mode (`AUTH_MODE=hybrid`)
Accepts either API keys (`x-api-key`) or JWT Bearer tokens, resolving permissions dynamically.

---

## 3. Global Request & Response Headers

### 3.1. Correlation ID Propagation
Every client request should supply a correlation identifier. If missing, the gateway automatically generates one.
- **Request Headers**: `x-request-id` or `x-correlation-id`
- **Response Header**: `X-Correlation-Id`

### 3.2. Idempotency Gating
Write operations (`POST /v1/missions`) accept an idempotency key to prevent double-execution of resource creation.
- **Request Header**: `Idempotency-Key: <unique-uuid-or-hash>`
- **Behavior**: The gateway caches the initial response in Redis with a 24-hour Time-To-Live (TTL). Repeated requests with the same key instantly return the cached response.

---

## 4. Standard Error Payloads (`FactoryError`)

Errors returned by theFactory conform to the Local-First Error Handling Standard. They return a structured JSON payload containing recovery and correlation metadata:

```json
{
  "error_id": "err-5abf19df-81e7-40fc-8102-de07fb6380a9",
  "error_code": "FACTORY-RESOURCE-4041",
  "severity": "CRITICAL",
  "category": "RESOURCE_NOT_FOUND",
  "component": "ORCHESTRATOR",
  "operation": "get_mission_details",
  "user_message": "The requested mission could not be found.",
  "developer_message": "Mission ID mission-123 does not match any record in storage.",
  "recovery_action": "Check the mission ID and try again, or query active missions.",
  "timestamp": "2026-06-12T03:00:00Z",
  "correlation_id": "corr-30d6d4f-83b3-4f11-1d89-25923bc6e40f"
}
```

### 4.1. Error Categories & Codes
- **FACTORY-AUTH-401X**: Authentication or token signature validation failures.
- **FACTORY-RESOURCE-404X**: Requested entities (missions, agents, artifacts) do not exist.
- **FACTORY-BUS-503X**: Protocol Bus MCP backpressure or Redis Stream connection failures.
- **FACTORY-LLM-502X**: LLM provider API timeout or quota exhaustions.

---

## 5. API Catalog

### 5.1. Create Mission
Ingests requirements and initializes a new software smelt cycle.

- **HTTP Method**: `POST`
- **Path**: `/v1/missions`
- **Headers**:
  - `Content-Type: application/json`
  - `Idempotency-Key: <key>`
- **Request Body**:
```json
{
  "mission_id": "mission-998b8666",
  "prompt": "Write a Python function to compute the top K frequent elements in an array. Include unit tests.",
  "requested_target_language": "python",
  "metadata": {
    "mission_type": "BUILD_NEW",
    "depth_mode": "STANDARD",
    "output_mode": "FULL_BUILD"
  }
}
```
- **Success Response (201 Created)**:
```json
{
  "mission_id": "mission-998b8666",
  "state": "PM_INTAKE",
  "created_at": "2026-06-12T03:00:00Z"
}
```

---

### 5.2. Get Mission Details
Queries the current state, metadata, and history of a mission.

- **HTTP Method**: `GET`
- **Path**: `/v1/missions/{id}`
- **Success Response (200 OK)**:
```json
{
  "mission_id": "mission-998b8666",
  "state": "COMPLETE",
  "prompt": "Write a Python function to compute...",
  "requested_target_language": "python",
  "created_at": "2026-06-12T03:00:00Z",
  "metadata": {
    "ambiguity_score": 0.05,
    "deploy_readiness": {
      "verdict": "READY",
      "checks_passed": true
    }
  }
}
```

---

### 5.3. Update Mission Metadata
Updates metadata fields such as the mission name.

- **HTTP Method**: `PATCH`
- **Path**: `/v1/missions/{id}`
- **Request Body**:
```json
{
  "name": "Top-K Frequent Elements Optimizer"
}
```
- **Success Response (200 OK)**:
```json
{
  "mission_id": "mission-998b8666",
  "name": "Top-K Frequent Elements Optimizer",
  "updated_at": "2026-06-12T03:01:00Z"
}
```

---

### 5.4. PM Clarification Response
Submits clarifying instructions if a mission enters the `CLARIFYING` state.

- **HTTP Method**: `POST`
- **Path**: `/v1/missions/{id}/clarify`
- **Request Body**:
```json
{
  "clarification_text": "Optimize the execution speed using a heap-based algorithm."
}
```
- **Success Response (200 OK)**:
```json
{
  "mission_id": "mission-998b8666",
  "state": "PM_INTAKE",
  "transitioned_at": "2026-06-12T03:02:00Z"
}
```

---

### 5.5. Get Token Cost Telemetry
Retrieves LLM token consumption and cost accumulation details.

- **HTTP Method**: `GET`
- **Path**: `/v1/missions/{id}/token-usage`
- **Success Response (200 OK)**:
```json
{
  "mission_id": "mission-998b8666",
  "usage_summary": {
    "total_input_tokens": 15420,
    "total_output_tokens": 4200,
    "total_cost_usd": 0.1642,
    "calls_count": 14
  }
}
```

---

### 5.6. Retrieve Build Artifacts
Retrieves compiled code or verification reports.

- **HTTP Method**: `GET`
- **Path**: `/v1/missions/{id}/artifact`
- **Query Parameters**:
  - `artifact_type`: `generated_code` | `security_compliance_report` | `equivalence_report`
- **Success Response (200 OK)**:
```json
{
  "mission_id": "mission-998b8666",
  "artifact_type": "generated_code",
  "content_hash": "sha256-5abf19df040b647...",
  "signature_record": {
    "algorithm": "ECDSA-P256-SHA256",
    "signature": "MEUCIQ...",
    "public_key": "-----BEGIN PUBLIC KEY-----\n..."
  },
  "content": "def top_k_frequent(nums, k):\n    ..."
}
```

---

### 5.7. Real-Time State Stream (SSE)
Establishes a Server-Sent Events (SSE) channel to monitor live mission state transitions.

- **HTTP Method**: `GET`
- **Path**: `/v1/stream/state`
- **Headers**:
  - `Accept: text/event-stream`
- **Optional Request Parameters**:
  - `Last-Event-ID`: Resume stream from a specific event index.
- **SSE Payload Format**:
```event
event: mission_state_changed
id: 1042
data: {"mission_id": "mission-998b8666", "state": "SMELT", "timestamp": "2026-06-12T03:00:15Z"}

event: keepalive
data: {}
```

---

### 5.8. Health & Readiness Probes

- **Check Gateway Health**: `GET http://localhost:8100/health` (HTTP 200)
- **Check Orchestrator Readiness**: `GET http://localhost:8101/readyz` (Checks Postgres, Qdrant, and Redis connection loops. Returns HTTP 200 if healthy, HTTP 503 if dependencies are offline).
