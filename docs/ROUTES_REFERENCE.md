# Routes Reference

**Source files:**  
- `services/orchestrator/orchestrator/routes/missions.py` (~12 KB)  
- `services/orchestrator/orchestrator/routes/operations.py` (~25 KB)  
- `services/orchestrator/orchestrator/routes/internal.py` (~44 KB)  
**Registered in:** `main.py` via `app.include_router()`

---

## Overview

The orchestrator's HTTP surface is split into three route modules, each with a distinct caller profile and auth requirement.

| Module | Prefix | Caller | Auth Required | Summary |
|---|---|---|---|---|
| `missions.py` | `/missions` | External clients, Mission Control UI | Yes — API key | Mission CRUD and state lifecycle endpoints |
| `operations.py` | `/ops` | Mission Control UI, operators | Yes — API key | Dashboard data — agent snapshot, pod status, knowledge lake, project aggregation |
| `internal.py` | `/internal` | Pod workers, audit worker, pod manager agents | Yes — internal service key | Worker callback endpoints — LogicNodes, heartbeats, artifacts, audit reports |

See `API_INTEGRATION_GUIDE.md` for full request/response examples. See `ORCHESTRATOR_MAIN.md` for how routers are registered and the auth dependency wiring.

---

## `routes/missions.py` — Mission Lifecycle

All endpoints require the standard operator API key (injected via `require_api_key` dependency).

### Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/missions` | Create a new mission. Accepts `MissionCreate`. Transitions to `INTAKE`, then enqueues to `QUEUED` and signals the runtime. |
| `GET` | `/missions` | List recent missions. Query param: `limit` (default 50). |
| `GET` | `/missions/{mission_id}` | Fetch a single mission record. |
| `PATCH` | `/missions/{mission_id}/state` | Update mission state. Accepts `MissionStateUpdate`. Validates against `VALID_TRANSITIONS`. |
| `POST` | `/missions/{mission_id}/clarify` | Submit operator clarification for a `CLARIFYING`-state mission. Accepts `MissionClarifyRequest`. Stores text in `metadata["pm_clarification"]` and transitions back to `PM_INTAKE`. |
| `GET` | `/missions/{mission_id}/events` | Get the state event history for a mission. Query param: `limit`. |
| `POST` | `/missions/{mission_id}/attachments` | Upload a file attachment to a mission (multipart form data). Stored in object storage; reference written to `mission.attachments`. |
| `DELETE` | `/missions/{mission_id}/attachments/{file_id}` | Remove an attachment from a mission. |
| `GET` | `/missions/{mission_id}/logicnodes` | List LogicNodes produced for a mission. |
| `GET` | `/missions/{mission_id}/artifacts` | List build artifacts for a mission. |
| `GET` | `/missions/{mission_id}/audit` | Fetch the latest audit report for a mission. |

### Clarification Flow

When PM Agent detects ambiguous intent, it transitions the mission to `CLARIFYING` and emits a `MISSION_CLARIFYING` event. The operator posts to `/missions/{id}/clarify` with the resolution text. The route stores it and transitions back to `PM_INTAKE` — PM Agent re-reads `metadata["pm_clarification"]` and continues chartering.

---

## `routes/operations.py` — Operator Dashboard Data

All endpoints require the standard operator API key. These endpoints power the Mission Control UI's operations views.

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/ops/health` | System health summary — service status, DB connectivity, Redis connectivity, active mission count |
| `GET` | `/ops/agents` | Agent snapshot — all 41 agents with current state, last heartbeat, and assigned mission |
| `GET` | `/ops/agents/{agent_id}` | Single-agent detail — heartbeat, recent action events, current mission |
| `GET` | `/ops/pods` | Pod status summary — all 4 pods with assigned workers and active missions |
| `GET` | `/ops/pods/{pod_id}` | Single-pod detail — workers, recent missions, throughput |
| `GET` | `/ops/projects` | Project aggregation — mission counts and status breakdown per project |
| `GET` | `/ops/missions/states` | Mission state count map — `{state: count}` for all states |
| `GET` | `/ops/missions/recent-events` | Recent mission state events across all missions |
| `GET` | `/ops/knowledge` | Knowledge lake summary — fragment counts by language tag |
| `GET` | `/ops/knowledge/{language}` | Knowledge fragments for a specific language |
| `GET` | `/ops/metrics` | Prometheus metrics exposition endpoint |
| `GET` | `/ops/logicnodes/recent` | Most recently written LogicNodes across all missions |
| `GET` | `/ops/audit/recent` | Most recent audit reports across all missions |
| `GET` | `/ops/scaling/partitions/{mission_id}` | Partition result status for a scaled mission |

### Agent Snapshot

`GET /ops/agents` queries `storage_agents.list_agent_heartbeats()` and joins against the agent registry (`agent_registry.py`) to annotate each heartbeat with the agent's tier, pod assignment, and persona name. Agents with no heartbeat record (not yet started) are included with state `IDLE`.

---

## `routes/internal.py` — Worker Callbacks

Internal endpoints called exclusively by pod workers, pod managers, and the audit worker. Authenticated with the internal service key (`X-Internal-Key` header) rather than the operator API key — these are separate credentials; see `AGENT_SERVICE_KEY_ISOLATION.md`.

At ~44 KB, this is the largest route module. It handles the full inbound data stream from running agents.

### LogicNode Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/internal/missions/{mission_id}/logicnodes` | Single LogicNode write from a pod worker. Calls `storage.upsert_logicnode()`. |
| `POST` | `/internal/missions/{mission_id}/logicnodes/batch` | Batch LogicNode write (up to 500 per call). Calls `storage.upsert_logicnodes_batch()`. |

### Heartbeat Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/internal/agents/{agent_id}/heartbeat` | Agent liveness signal. Calls `storage.upsert_agent_heartbeat()`. Accepted every 10 seconds by healthy agents. |
| `POST` | `/internal/agents/{agent_id}/events` | Agent action event write. Calls `storage.insert_agent_action_event()`. |

### Artifact Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/internal/missions/{mission_id}/artifacts` | Write a build artifact (binary or text, stored in object storage with DB reference). |
| `POST` | `/internal/missions/{mission_id}/audit` | Write or update an audit report. Calls `storage.upsert_audit_report()`. |
| `POST` | `/internal/missions/{mission_id}/review-approval` | Write a human or automated review approval. |
| `POST` | `/internal/missions/{mission_id}/qc-report` | Write a Runtime QC report from `rqca_agent.py`. |
| `POST` | `/internal/missions/{mission_id}/testdata-manifest` | Write the test data manifest from `testdata_agent.py`. |

### State Transition Callbacks

| Method | Path | Description |
|---|---|---|
| `POST` | `/internal/missions/{mission_id}/transition` | Worker-initiated state transition. Validates against `VALID_TRANSITIONS`. Used by pod managers and audit workers to advance mission state without requiring operator API access. |
| `POST` | `/internal/missions/{mission_id}/partition-result` | Record a partition result from a scaled agent instance. Calls `storage.record_partition_result()`. |

### Knowledge Lake Callbacks

| Method | Path | Description |
|---|---|---|
| `POST` | `/internal/knowledge` | Write a knowledge fragment to the knowledge lake. |
| `POST` | `/internal/knowledge/batch` | Batch write knowledge fragments. |

---

## Auth Model Summary

| Route module | Header | Credential source | Enforced by |
|---|---|---|---|
| `missions.py` | `X-API-Key` | `Settings.api_key` | `require_api_key` dependency |
| `operations.py` | `X-API-Key` | `Settings.api_key` | `require_api_key` dependency |
| `internal.py` | `X-Internal-Key` | `Settings.internal_service_key` | `require_internal_key` dependency |

See `ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md` for the rationale for API key auth in v1.2.0 and the OIDC upgrade path.
