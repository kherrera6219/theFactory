# Orchestrator Route Modules Reference

Document version: 2026.06.13
Last updated: 2026-06-27
Status: Canonical

**Package:** `services/orchestrator/orchestrator/routes/`  
**Version:** 2026.06.11  
**Audience:** Developers, Integrators

This document covers all three FastAPI route modules registered on the orchestrator (port `:8101`). Each module is an `APIRouter` mounted in `main.py`. Shared authentication dependencies live in `_deps.py`.

---

## Auth Dependency Summary

All three route modules import from `routes/_deps.py`, which wraps `auth.py`.

| Dependency constant | Auth requirement | Who uses it |
|---|---|---|
| `READ_AUTH_DEP` | Valid service API key, read scope | Public-facing mission reads |
| `MUTATION_AUTH_DEP` | Valid service API key, write scope | State transitions, clarification, pruning |
| `INTERNAL_AUTH_DEP` | Internal service-to-service key | Worker callbacks, operations, internal writes |

All endpoints that omit an explicit auth dependency still use one via a `dependencies=[...]` keyword. No endpoint is unauthenticated.

---

## `routes/missions.py` — Mission CRUD and Lifecycle

**Router prefix:** none (endpoints rooted at `/`)  
**Source:** `services/orchestrator/orchestrator/routes/missions.py` (12 KB)

This module owns the full mission record lifecycle visible to operators and the API Gateway. Every mutating endpoint records an audit event via `record_audit_event()` and emits a Redis Streams state event when the protocol bus is ready.

### Endpoints

#### `POST /missions`

| Field | Value |
|---|---|
| Auth | `INTERNAL_AUTH_DEP` |
| Request body | `MissionCreate` |
| Response | `MissionRecord` |
| Side effects | Writes mission record to Postgres, inserts `MISSION_QUEUED` event, emits Redis state event, records `MISSION_CREATED` audit event, starts lifecycle task |

Creates a new mission record in `QUEUED` state. The call chain is:
1. `project_identity.resolve_project_id()` — resolves or generates the project identity
2. `storage.upsert_mission()` — persists the record
3. `storage.insert_mission_event()` — records the intake → queued transition
4. `emit_state_event()` — publishes to Redis Streams (non-fatal if bus unavailable)
5. `start_lifecycle_task()` — hands the mission to the runtime engine

**`MissionCreate` fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `mission_id` | `str` | Yes | Caller-assigned UUID |
| `prompt` | `str` | Yes | Natural-language mission description |
| `requested_target_language` | `str \| None` | No | Target language hint (e.g. `"python"`) |
| `mission_type` | `MissionType \| None` | No | `BUILD_NEW`, `MIGRATE`, `REFACTOR`, `AUDIT` |
| `depth_mode` | `DepthMode \| None` | No | `STANDARD`, `DEEP`, `SURFACE` |
| `output_mode` | `OutputMode \| None` | No | `FULL_BUILD`, `PLAN_ONLY`, `PATCH` |
| `data_classification` | `DataClassification \| None` | No | `TIER_1` through `TIER_3` |
| `metadata` | `dict \| None` | No | Caller metadata passed through to the chain |
| `project_id` | `str \| None` | No | Explicit project ID override |
| `created_at` | `str \| None` | No | ISO 8601 timestamp; defaults to now |

---

#### `GET /missions/{mission_id}`

| Field | Value |
|---|---|
| Auth | `READ_AUTH_DEP` |
| Response | `MissionRecord` |
| Errors | `404` if not found |

Returns the full mission record including all metadata. The `metadata` field contains the entire chain-of-custody for the mission (delegations, LogicNodes summary, artifacts, chain trace events).

---

#### `GET /missions`

| Field | Value |
|---|---|
| Auth | `READ_AUTH_DEP` |
| Query params | `limit` (int, 1–200, default 20) |
| Response | `list[MissionRecord]` |

Returns the most recent `limit` missions ordered by creation time descending.

---

#### `GET /missions/{mission_id}/events`

| Field | Value |
|---|---|
| Auth | `READ_AUTH_DEP` |
| Query params | `limit` (int, 1–500, default 50) |
| Response | `list[dict]` — serialised `MissionEvent` objects |
| Errors | `404` if mission not found |

Returns the mission's state transition event log. Each event records the `from_state`, `to_state`, `event_type`, and timestamp. Useful for understanding lifecycle progress.

---

#### `GET /missions/{mission_id}/runtime-qc`

| Field | Value |
|---|---|
| Auth | None (public read) |
| Response | Redacted QC summary dict |
| Errors | `404` if report not found |

Returns a sanitised view of the Runtime QC report — `verdict`, `qc_verdict`, `deployment_safe`, `stdout_preview`, `language`, `filename`. The `stderr_preview` field is always `null` for security. The full internal report is available at `GET /internal/missions/{mission_id}/runtime-qc`.

---

#### `POST /missions/{mission_id}/state`

| Field | Value |
|---|---|
| Auth | `MUTATION_AUTH_DEP` |
| Request body | `MissionStateUpdate` |
| Response | `MissionRecord` |
| Errors | `409` if state transition rejected (optimistic lock) |

Performs a guarded state transition. The `expected_state` field acts as an optimistic lock — if the mission is not in the expected state, a `409` is returned and no change is made. Emits a Redis state event and records a `MISSION_STATE_UPDATED` audit event.

**`MissionStateUpdate` fields:**

| Field | Type | Required |
|---|---|---|
| `new_state` | `MissionState` | Yes |
| `expected_state` | `MissionState \| None` | No — if omitted, no lock check |

---

#### `POST /missions/{mission_id}/clarify`

| Field | Value |
|---|---|
| Auth | `MUTATION_AUTH_DEP` |
| Request body | `MissionClarifyRequest` |
| Response | `MissionRecord` |
| Errors | `409` if mission is not in `CLARIFYING` state |

Supplies operator clarification to a mission blocked in `CLARIFYING` state. Stores the text in `metadata["pm_clarification"]`, appends a `MISSION_CLARIFICATION_RECEIVED` chain event, and transitions the mission back to `PM_INTAKE` so `AGENT-01-PM` re-processes intent with the additional context.

**`MissionClarifyRequest` fields:**

| Field | Type | Required |
|---|---|---|
| `clarification` | `str` | Yes |

---

#### `GET /missions/{mission_id}/token-usage`

| Field | Value |
|---|---|
| Auth | `INTERNAL_AUTH_DEP` |
| Response | Aggregated token usage and estimated cost dict from `llm_cost_ledger` |

Returns per-agent and total LLM token consumption for a mission, with estimated USD cost using current provider rate tables.

---

## `routes/operations.py` — Dashboard and Ops Endpoints

**Router prefix:** none (endpoints rooted at `/internal/operations/` and `/v1/maintenance/`)  
**Source:** `services/orchestrator/orchestrator/routes/operations.py` (25 KB)

This module powers the Mission Control dashboard and the ops API. It provides runtime health snapshots, agent status boards, event streams, LogicNode and pod assignment views, project audit trails, and operational alerts. It also exposes the audit pruning maintenance endpoint.

All endpoints in this module require `INTERNAL_AUTH_DEP` except where noted.

### Helper Functions (module-level)

Three significant helpers are defined at module level and called by the endpoint handlers:

| Function | Purpose |
|---|---|
| `_build_operational_alerts(...)` | Generates the alert list from runtime flags and mission state counts. Produces `critical`/`high`/`medium` severity alerts for Redis down, Postgres down, protocol not ready, consumer stopped, failed missions, and completion-blocked missions. |
| `_build_operations_agents_snapshot(...)` | Assembles the full 41-agent status snapshot — routes missions to agents by pod/specialty, merges live heartbeat data where available, falls back to heuristic state/workload for agents with no live heartbeat. |
| `_normalize_pod_name(value)` | Normalises pod names to lowercase with no separators for consistent lookup (e.g. `"Pod A"` → `"poda"`). |

### Endpoints

#### `GET /internal/operations/summary`

Returns a lightweight runtime health snapshot including:
- `runtime` — readiness flags for Redis, Postgres, Qdrant, Milvus, Neo4j, object storage, Jaeger, protocol validator, intake consumer, and LangGraph
- `mission_state_counts` — count of missions in each `MissionState`
- `pod_assignment_counts` — count of pod assignments per pod
- `active_lifecycle_tasks` — number of currently running lifecycle coroutines
- `topology_mode` — the configured deployment topology

Store readiness flags return `null` when the store is disabled (not `false`), allowing callers to distinguish "disabled" from "down".

---

#### `GET /internal/operations/agents`

Returns the full 41-agent status snapshot. Query params:

| Param | Default | Range | Purpose |
|---|---|---|---|
| `mission_limit` | 1000 | 50–5000 | Max missions loaded for agent routing |
| `assignment_limit` | 1000 | 50–5000 | Max pod assignments loaded |
| `event_limit` | 300 | 50–2000 | Max recent events loaded |

Response top-level keys: `generated_at`, `total_agents`, `runtime`, `mission_backlog` (active/verified/complete/assigned_active counts), `tier_counts`, `pod_counts`, `state_counts`, `agents` (array of 41 agent records).

Each agent record includes: `index`, `agent_id`, `short_code`, `name`, `tier`, `pod`, `role`, `category`, `specialties`, `state`, `queue_depth`, `workload_pct`, `last_heartbeat_iso`, `active_mission_ids` (up to 25), `runtime_class`, `heartbeat_source` (`"live"` / `"stale"` / `"heuristic"`), `heartbeat_age_seconds`, `persona_profile`.

---

#### `GET /internal/operations/agent-integrations`

Returns the full agent integrations snapshot from `agent_integrations.build_agent_integrations_snapshot()` — a read-only view of every agent's integration catalog entry.

---

#### `GET /internal/operations/events`

| Query param | Default | Range |
|---|---|---|
| `limit` | 200 | 1–1000 |

Returns recent mission state transition events across all missions.

---

#### `GET /internal/operations/agent-events`

| Query param | Default | Range |
|---|---|---|
| `limit` | 200 | 1–1000 |

Returns recent agent action events (audit events emitted by agents) across all missions.

---

#### `GET /internal/operations/logicnodes`

| Query param | Default | Range | Notes |
|---|---|---|---|
| `limit` | 200 | 1–1000 | |
| `mission_id` | `null` | — | If provided, scopes to that mission only |

Returns LogicNodes. When `mission_id` is provided, returns that mission's nodes. Without it, returns the most recent nodes across all missions.

---

#### `GET /internal/operations/pod-assignments`

| Query param | Default | Range |
|---|---|---|
| `limit` | 200 | 1–1000 |

Returns recent pod assignment records showing which mission was assigned to which pod.

---

#### `GET /internal/operations/projects`

| Query param | Default | Range |
|---|---|---|
| `limit` | 100 | 1–500 |

Returns a project summary list from `storage.summarize_projects()`. Each entry groups missions by `project_id`.

---

#### `GET /internal/operations/projects/{project_id}/audit-events`

| Query param | Default | Range | Notes |
|---|---|---|---|
| `limit` | 200 | 1–1000 | |
| `mission_id` | `null` | — | Filter to a specific mission within the project |
| `agent_id` | `null` | — | Filter to a specific agent |
| `tool_name` | `null` | — | Filter to a specific tool |

Returns audit events for a project with optional filters. Backed by `storage.list_project_agent_action_events()`.

---

#### `GET /internal/operations/alerts`

| Query param | Default | Range |
|---|---|---|
| `limit` | 50 | 1–200 |

Returns the current operational alert list. Alert severities: `critical`, `high`, `medium`. Each alert has `alert_id`, `severity`, `state`, `title`, `source`, `created_at`, and `recommendation`.

Alert conditions checked:
- Redis unavailable → `critical`
- Postgres unavailable → `critical`
- Protocol validator not ready → `high`
- Intake consumer not running → `high`
- Failed missions present → `medium`
- Missions blocked at completion → `high`

---

#### `POST /v1/maintenance/prune-audit`

| Field | Value |
|---|---|
| Auth | `MUTATION_AUTH_DEP` |
| Query param | `retention_days` (int, 1–3650, optional — overrides `AUDIT_RETENTION_DAYS` setting) |
| Response | `{ generated_at, retention_days, total_rows_deleted, tables }` |

Deletes audit rows older than the retention window by invoking the `prune_audit_tables()` SECURITY DEFINER SQL function. Using a SQL function means this works even after `DELETE` is revoked from the application role, preserving the immutable-audit guarantee.

---

## `routes/internal.py` — Worker Callback Endpoints

**Router prefix:** none (endpoints rooted at `/internal/`)  
**Source:** `services/orchestrator/orchestrator/routes/internal.py` (44 KB)

This is the largest route module. It exposes the endpoints that pod workers, audit workers, and other services call to write mission artifacts back into the orchestrator. Every endpoint requires `INTERNAL_AUTH_DEP`. Every mutating endpoint records an audit event.

### Helper Functions (module-level)

| Function | Purpose |
|---|---|
| `_build_mission_chain_trace(...)` | Assembles the full chain-trace response — merges metadata delegations, pod assignment, LogicNode events, mission events, build artifacts, and scaling state into a single structured document |
| `_route_provenance_snapshot(payload, role)` | Extracts routing provenance (LLM route, model, agent IDs, rationale) from a delegation payload dict for CEO, pod manager, or specialist roles |
| `_artifact_summary(metadata)` | Extracts the `mission_artifacts` dict from mission metadata |
| `_scaling_summary(metadata)` | Extracts the scaling decision, partition counts, and merge status from mission metadata |
| `_agent_id_from_metadata(metadata)` | Resolves an agent ID from a metadata dict by checking 6 priority-ordered keys |
| `_agent_id_from_node(node)` | Resolves an agent ID from a LogicNode dict or its nested payload |

### Endpoints

#### `POST /internal/pod-assignment`

Request: `PodAssignmentUpsert` (`mission_id`, `pod_name`, `metadata`, `assigned_at?`)  
Response: pod assignment record dict  
Error: `409` if another pod worker already claimed the mission (`PodAssignmentConflictError`)

The **claim** endpoint: called by a pod worker when it accepts execution of a mission, writing `metadata.assigned_by = "pod-worker"`. Writes the pod assignment to Postgres and records a `MISSION_POD_ASSIGNMENT_WRITTEN` audit event.

The orchestrator writes the same table directly (never through this route) when the delegation chain emits `MISSION_POD_MANAGER_ASSIGNED`, with `metadata.assigned_by = "orchestrator"`. A claim through this route supersedes such a provisional row; see [Two writers, one row](STORAGE_LAYER.md#two-writers-one-row).

---

#### `POST /internal/pm/feature-contract`

Request: `{ prompt, mission_type?, depth_mode?, output_mode?, requested_target_language?, mission_id? }`  
Response: `{ feature_contract, mission_charter, source, model_provider, model }`

Calls `llm_delegation.generate_pm_feature_contract()` followed by `mission_flow_v2.build_mission_charter()`. Returns both the PM's feature contract and the derived mission charter. The `source` field indicates whether the contract was produced by an LLM (`"llm"`) or generated from a fallback template (`"fallback"`).

---

#### `GET /internal/broker/provider-health`

Response: provider health summary from `llm_delegation.get_provider_health_summary()`  

Returns the current health status and latency stats for all configured LLM providers.

---

#### `GET /internal/missions/{mission_id}/pod-assignment`

Returns the pod assignment record for a mission. `404` if not yet assigned — which, once the delegation chain has emitted `MISSION_POD_MANAGER_ASSIGNED`, should not happen. Check `metadata.assigned_by` to tell a routed mission (`orchestrator`) from one a pod is executing (`pod-worker`).

---

#### `GET /internal/missions/{mission_id}/chain-trace`

| Query param | Default | Range |
|---|---|---|
| `event_limit` | 200 | 1–1000 |
| `logicnode_limit` | 200 | 1–2000 |
| `build_artifact_limit` | 20 | 1–200 |

Returns the full chain-trace document for a mission. This is the primary audit and debugging endpoint. The response includes:
- Routing provenance (CEO, pod manager, specialist delegation details with LLM route and model)
- Pod assignment
- LogicNode count
- Artifact summary and build artifact list
- Scaling state (active/complete, partition results, merged result)
- Feature contract, mission charter, mission contract
- Logic clusters, pod group standards
- Fetch result, AIM, equivalence report, security compliance report
- Dependency inventory, classification, absorption, and SBOM delta
- Testdata manifest, runtime QC report
- Chronologically sorted chain event trace

---

#### `GET /internal/missions/{mission_id}/testdata-manifest`

Returns the testdata manifest for a mission. Falls back to `metadata["testdata_manifest"]` if not in dedicated storage. `404` if absent.

---

#### `GET /internal/missions/{mission_id}/runtime-qc`

Returns the full (internal) Runtime QC report. Falls back to `metadata["runtime_qc_report"]`. `404` if absent. Distinct from the public `GET /missions/{id}/runtime-qc` which returns a sanitised view.

---

#### `POST /internal/audit-events`

Request: `AgentActionEventUpsert`  
Response: audit event record dict

Called by any service or agent to write an audit event into the chain-of-custody. Fields include `mission_id`, `agent_id`, `service_name`, `event_type`, `status`, `object_type`, `object_id`, `tool_name`, `correlation_id`, `parent_event_id`, `started_at`, `ended_at`, `payload_summary`, `content_sha256`, `blob_ref`.

---

#### `GET /internal/missions/{mission_id}/audit-events`

| Query param | Default | Range |
|---|---|---|
| `limit` | 100 | 1–1000 |

Returns all audit events for a mission from `storage.list_mission_agent_action_events()`.

---

#### `POST /internal/logicnodes`

Request: `LogicNodeUpsert` (`mission_id`, `node_id`, `node` dict, `created_at?`)  
Response: persisted logicnode record  

The write boundary for LogicNodes. Validates the `node` dict against `schemas/logicnode.schema.json` before persistence. Validation is **non-fatal** — an invalid node is logged with its errors and still persisted so a single malformed extraction does not abort the mission. The `validation_errors` list is included in the response when present. Emits a `MISSION_LOGICNODE_WRITTEN` audit event with status `ERROR` or `SUCCESS`.

---

#### `GET /internal/missions/{mission_id}/logicnodes`

| Query param | Default | Range |
|---|---|---|
| `limit` | 50 | 1–500 |

Returns the LogicNodes for a mission.

---

#### `POST /internal/knowledge`

Request: `KnowledgeUpsert` (`mission_id`, `knowledge_id`, `content` dict, `created_at?`)  
Response: persisted knowledge record

Writes a knowledge fragment to all enabled stores in parallel:
1. **Postgres** — always written (primary store)
2. **Qdrant** — written if `QDRANT_ENABLED=true`
3. **Milvus** — written if `MILVUS_ENABLED=true`
4. **Neo4j** — written if `NEO4J_ENABLED=true`

Write failures to vector/graph stores are logged as warnings but do not fail the request.

---

#### `GET /internal/missions/{mission_id}/knowledge`

| Query param | Default | Range |
|---|---|---|
| `limit` | 50 | 1–500 |

Returns knowledge fragments with store priority: Qdrant first (if enabled and returns data), then Milvus, then Postgres fallback.

---

#### `GET /internal/missions/{mission_id}/knowledge-graph`

Returns mission knowledge graph edges from Neo4j. Returns `[]` if Neo4j is disabled or unavailable.

---

#### `POST /internal/audit-reports`

Request: `AuditReportUpsert` (`mission_id`, `audit_id`, `status`, `report` dict, `created_at?`)  
Response: persisted audit report record

**Digital signature enforcement:** If `report["signature_record"]` is present, the payload is verified using `shared_runtime.crypto_signing.verify_payload()`. In `production` environment, a missing signature raises `422`. Mirrors to Neo4j and object storage (S3) when enabled. Records a `MISSION_AUDIT_REPORT_WRITTEN` audit event with content SHA-256.

---

#### `POST /internal/review-approvals`

Request: `ReviewApprovalUpsert` (`scope`, `fingerprint` ≥12 chars, `summary` ≥3 chars, `metadata?`, `approved_at?`, `expires_at?`, `hmac_digest?`)  
Response: `ReviewApprovalRecord` with computed `approval_id` and `record_path`

Writes a review approval record with a computed HMAC receipt digest for tamper evidence. `approval_id` is derived from `scope` + `fingerprint`.

---

#### `GET /internal/review-approvals/{approval_id}`

Returns a single review approval by ID. `404` if not found.

---

#### `GET /internal/missions/{mission_id}/audit-reports`

| Query param | Default | Range |
|---|---|---|
| `limit` | 50 | 1–500 |

Returns all audit reports for a mission.

---

#### `GET /internal/missions/{mission_id}/audit-artifacts`

Returns audit artifacts from object storage (S3). Returns `[]` if object storage is disabled.

---

#### `GET /internal/missions/{mission_id}/build-artifacts`

| Query param | Default | Range |
|---|---|---|
| `limit` | 50 | 1–500 |

Returns build artifact records as `list[MissionBuildArtifactRecord]`.

---

#### `GET /internal/missions/{mission_id}/build-artifacts/{artifact_id}`

Returns a single build artifact. **S4-05 presigned redirect:** If `storage_backend == "s3"` and `storage_ref` is set, returns a `302` redirect to a presigned S3 download URL instead of embedding the artifact in the response body, keeping large artifacts out of the API payload.

For artifacts with a `verification.signature_record`, verifies the digital signature inline and adds `verification.verified: bool` to the response.

---

#### `POST /internal/missions/{mission_id}/partition-results`

Request: `{ partition_id, agent_id, instance_index?, logicnodes?, artifacts?, report?, completed_at? }`  
Response: `{ mission_id, state, partition_id, partition_result_count, scaling_complete, merged_partition_result, target_language }`

Called by scaled specialist instances to write their partial results. When all partitions are complete (`scaling_merge_complete` is set in metadata), automatically triggers a new lifecycle task to continue mission processing from the merge point.

---

#### `POST /internal/agents/heartbeat`

Request: `AgentHeartbeatUpsert` (`agent_id`, `state`, `queue_depth`, `workload_pct`, `active_mission_ids?`, `metadata?`)  
Response: heartbeat record dict with `state_changed: bool`

Persists an agent heartbeat. When the agent state changes or `active_mission_ids` is non-empty, records an `AGENT_HEARTBEAT_UPDATED` audit event for up to the first 10 active missions.

---

#### `GET /internal/prompt-registry`

Returns all registered versioned prompt assets from `prompt_registry.list_prompts()`. See [PROMPT_REGISTRY_AND_ASSETS.md](PROMPT_REGISTRY_AND_ASSETS.md) for the full prompt system reference.

---

#### `POST /internal/maintenance/diagnostics`

Request: optional `mission_id` query param  
Response: `{ ok: true, bundle_path }`

Triggers `system_maintenance.get_maintenance_manager().create_diagnostic_bundle()`. Produces a sanitised diagnostic bundle (no secrets, no PII) suitable for support escalation.

---

#### `POST /internal/maintenance/backup`

Response: `{ ok: true, backup_path }`  
Error: `500` if backup path starts with `"ERROR"`

Triggers a full stateful backup via `system_maintenance.get_maintenance_manager().run_full_backup()`.

---

## Cross-References

| Related doc | What it adds |
|---|---|
| [API_INTEGRATION_GUIDE.md](API_INTEGRATION_GUIDE.md) | Full request/response examples with curl and Python SDK usage |
| [ORCHESTRATOR_MAIN.md](ORCHESTRATOR_MAIN.md) | How route modules are mounted in `main.py`, middleware stack, lifespan |
| [MODELS_AND_DOMAIN_SCHEMA.md](MODELS_AND_DOMAIN_SCHEMA.md) | Full schema for all Pydantic request/response models (`MissionCreate`, `MissionRecord`, `MissionState`, etc.) |
| [LLM_DELEGATION.md](LLM_DELEGATION.md) | `generate_pm_feature_contract()` used in `POST /internal/pm/feature-contract` |
| [PROMPT_REGISTRY_AND_ASSETS.md](PROMPT_REGISTRY_AND_ASSETS.md) | `list_prompts()` used in `GET /internal/prompt-registry` |
| [MISSION_FLOW_V2.md](MISSION_FLOW_V2.md) | `build_mission_charter()` used in `POST /internal/pm/feature-contract` |
| [LOGICNODE_SCHEMA.md](LOGICNODE_SCHEMA.md) | LogicNode schema validation applied in `POST /internal/logicnodes` |
| [STORAGE_LAYER.md](STORAGE_LAYER.md) | All `storage.*` functions called by route handlers |
