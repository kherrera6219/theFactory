# Storage Layer

**Source files:** `services/orchestrator/orchestrator/storage_core.py`, `storage.py`, `storage_missions.py`, `storage_agents.py`, `storage_artifacts.py`, `storage_logicnodes.py`, `storage_pods.py`  
**Role:** The complete persistence layer for the orchestrator. Provides PostgreSQL CRUD, connection pooling, schema migration, and all domain-specific read/write operations behind a single re-export façade.

---

## Architecture

The storage layer is split into domain modules for maintainability. A single façade file (`storage.py`) re-exports every public symbol so all callers use `from . import storage; storage.fetch_mission(...)` without needing to know which domain module a function lives in.

```
storage.py (façade — re-exports everything)
├── storage_core.py       — DB connection pool, migration entry point, JSON/datetime helpers
├── storage_missions.py   — Mission CRUD, state-event log, partition-result recording
├── storage_pods.py       — Pod assignments, project aggregation
├── storage_logicnodes.py — LogicNode and knowledge-fragment persistence
├── storage_artifacts.py  — Audit reports, review approvals, build artifacts
└── storage_agents.py     — Agent heartbeats and runtime event log
```

---

## `storage_core.py` — DB Infrastructure

### Connection Strategy

The orchestrator uses two connection paths:

| Path | Function | Used by | Notes |
|---|---|---|---|
| **Direct connection** | `db_connect()` | Schema migrations only | Connects directly to PostgreSQL (not via PgBouncer). Takes a session-level advisory lock that requires a stable session. |
| **Connection pool** | `get_connection()` | All storage operations | `psycopg_pool` pool behind PgBouncer. `autocommit=True`, `prepare_threshold=None` (disables server-side prepared statements for PgBouncer transaction-pool compatibility). |

> **Why two paths?** PgBouncer in transaction-pool mode reassigns the backend and issues `DISCARD ALL` between statements, which silently releases advisory locks mid-migration. Migrations must bypass the bouncer.

### Pool Management

```python
init_connection_pool(settings)  # Call once at startup (idempotent)
close_connection_pool()         # Call at shutdown

with get_connection() as conn:  # Borrow a connection for a block
    with conn.cursor() as cur:
        cur.execute(...)
```

`init_connection_pool()` is called in `main.py`'s lifespan startup. `close_connection_pool()` is called on shutdown. Both are safe to call multiple times.

### Schema Migrations

```python
ensure_db_schema(settings)
```

Runs all pending Alembic migrations (via `migrations.apply_migrations()`) then bootstraps the `__knowledge_lake__` system mission used as the foreign-key anchor for global knowledge-lake entries.

### Helpers

| Function | Description |
|---|---|
| `_to_iso(value)` | Convert `datetime` to UTC ISO-8601 string |
| `_json_to_dict(value)` | Safely deserialize a JSONB column to `dict` |
| `_json_to_list(value)` | Safely deserialize a JSONB column to `list` |
| `FactoryJsonEncoder` | `json.JSONEncoder` subclass that handles `datetime` and Pydantic models |
| `factory_json_dumps(payload)` | Consistently serialize to sorted, compact JSON using `FactoryJsonEncoder` |

### `PodAssignmentConflictError`

Raised by `storage_pods.upsert_pod_assignment()` when a mission is already assigned to a different pod. Callers inspect `exc.existing_assignment` to retrieve the conflicting record.

---

## `storage_missions.py` — Mission Persistence

### Mission CRUD

| Function | Description |
|---|---|
| `upsert_mission(settings, record, source_stream_id)` | Insert or update a mission row. Embeds charter fields into `metadata_json`. Resolves `project_id` if not set. |
| `fetch_mission(settings, mission_id)` | Fetch a single mission by ID. Returns `None` if not found. |
| `update_mission_metadata(settings, mission_id, metadata)` | Update `metadata_json` and re-resolve `project_id`. Returns updated `MissionRecord`. |
| `list_missions(settings, limit)` | List most recent missions, ordered by `created_at DESC`. |
| `list_missions_in_states(settings, states, limit)` | List missions currently in any of the given states, ordered by `created_at ASC` (FIFO for queue pickup). |
| `count_missions(settings)` | Count all missions. |
| `mission_state_counts(settings)` | Return a `{state: count}` dict for all states. |

### State Transitions

```python
transition_mission_state(
    settings, mission_id,
    expected_state,  # None = unconditional
    new_state,
    event_type
) -> MissionRecord | None
```

Executes atomically within a single PostgreSQL transaction:
1. `UPDATE missions SET state = %s WHERE mission_id = %s [AND state = %s]`
2. `INSERT INTO mission_state_events ...`

If `expected_state` is provided, the update is conditional — if the current state does not match, the function returns `None` without raising. This is optimistic concurrency for parallel agent writes.

### Event Log

| Function | Description |
|---|---|
| `insert_mission_event(...)` | Write a state event and emit Prometheus metrics via `orchestrator_metrics.record_mission_transition()`. Skips metric emission for self-loop events (checkpoint vs. real transition). |
| `list_mission_events(settings, mission_id, limit)` | Get event history for a mission. |
| `list_recent_mission_events(settings, limit)` | Get the most recent events across all missions. |

### Charter Field Embedding

`MissionType`, `DepthMode`, `OutputMode`, and `DataClassification` are stored in `metadata_json` under `__mission_type__`, `__depth_mode__`, `__output_mode__`, `__data_classification__` keys. `_embed_charter_fields()` writes them on upsert; `_charter_fields_from_metadata()` reads them on row hydration in `row_to_mission()`.

### Partition Results (Agent Scaling)

```python
record_partition_result(settings, mission_id, result: dict)
```

Used by scaled parallel agents to record their partition's output. Uses `_locked_mission_metadata_update()` — a direct (non-pooled) connection with row-level `SELECT FOR UPDATE` to safely merge concurrent partition results into `metadata_json`. When `all_partitions_complete()` returns `True`, `merge_partition_results()` is called and the merged result is written as `merged_partition_result`.

---

## `storage_pods.py` — Pod Assignments

| Function | Description |
|---|---|
| `upsert_pod_assignment(settings, record)` | Insert or update a pod assignment. Raises `PodAssignmentConflictError` if a different pod is already assigned to the same mission. |
| `get_pod_assignment(settings, mission_id)` | Fetch a mission's current pod assignment. |
| `list_pod_assignments(settings, limit)` | List all pod assignments. |
| `summarize_projects(settings)` | Aggregate mission counts per project — used by the operations dashboard. |

---

## `storage_logicnodes.py` — LogicNode and Knowledge Persistence

LogicNodes are the core semantic artifacts produced by pod workers — typed, tagged knowledge fragments with confidence scores and source line references.

| Function | Description |
|---|---|
| `upsert_logicnode(settings, node)` | Persist a single LogicNode. |
| `upsert_logicnodes_batch(settings, nodes)` | Batch upsert for pod worker bulk writes. |
| `list_logicnodes(settings, mission_id, limit)` | List LogicNodes for a mission. |
| `list_recent_logicnodes(settings, limit)` | List most recently created LogicNodes across all missions. |
| `upsert_knowledge(settings, fragment)` | Persist a knowledge-lake fragment (language-indexed reusable knowledge). |
| `upsert_knowledge_batch(settings, fragments)` | Batch upsert for knowledge fragments. |
| `list_knowledge(settings, language, limit)` | Retrieve knowledge fragments for a given language tag. |

---

## `storage_artifacts.py` — Audit and Build Artifacts

Persists the evidence bundle components produced by the audit worker and pod workers.

| Function | Group | Description |
|---|---|---|
| `upsert_audit_report(...)` | Audit | Insert or update a structured audit report for a mission |
| `list_audit_reports(settings, mission_id)` | Audit | List audit reports for a mission |
| `list_recent_audit_reports(settings, limit)` | Audit | List most recent audit reports across all missions |
| `upsert_review_approval(...)` | Review | Persist a human or automated review approval record |
| `get_review_approval(settings, mission_id)` | Review | Fetch the review approval for a mission |
| `upsert_build_artifact(...)` | Build | Persist a build artifact (compiled output, test results, coverage report) |
| `list_build_artifacts(settings, mission_id)` | Build | List build artifacts for a mission |
| `get_build_artifact(settings, mission_id, artifact_type)` | Build | Fetch a specific artifact type |
| `insert_testdata_manifest(...)` | TestData | Persist a test data manifest generated by the testdata agent |
| `get_testdata_manifest(settings, mission_id)` | TestData | Fetch the test data manifest for a mission |
| `insert_runtime_qc_report(...)` | QC | Persist a Runtime QC report from `rqca_agent.py` |
| `get_runtime_qc_report(settings, mission_id)` | QC | Fetch the QC report for a mission |

---

## `storage_agents.py` — Agent Heartbeats and Event Log

Provides persistence for the agent observability layer — heartbeats (liveness signals) and the agent action event log (audit trail of what each agent did).

| Function | Description |
|---|---|
| `upsert_agent_heartbeat(settings, heartbeat)` | Update an agent's liveness record with current state and timestamp |
| `get_agent_heartbeat(settings, agent_id)` | Fetch a single agent's heartbeat record |
| `list_agent_heartbeats(settings)` | List all agent heartbeats — used by the operations dashboard agent snapshot |
| `create_agent_action_event(...)` | Construct an `AgentActionEvent` model |
| `insert_agent_action_event(settings, event)` | Persist an agent action event |
| `list_recent_agent_events(settings, limit)` | List most recent agent events across all agents |
| `list_mission_agent_action_events(settings, mission_id, limit)` | List all events for agents working on a specific mission |
| `list_project_agent_action_events(settings, project_id, limit)` | List all events for a project (cross-mission) |
| `prune_audit_tables(settings, older_than_days)` | Delete heartbeat and event records older than N days — called by the background maintenance task in `main.py` |

---

## Data Flow: Write Path

```
Agent / Route handler
    │
    ▼
storage.upsert_mission() / storage.transition_mission_state() / ...
    │
    ▼
Domain module (storage_missions, storage_pods, ...)
    │  Validates against VALID_TRANSITIONS (for state updates)
    │  Embeds charter fields (for mission upserts)
    ▼
get_connection() → PgBouncer → PostgreSQL
    │
    ▼
Prometheus metrics emitted (for state transitions)
```

## Data Flow: Schema Migration Path

```
main.py lifespan startup
    │
    ▼
ensure_db_schema(settings)
    │
    ├── db_connect() → PostgreSQL (direct, not via PgBouncer)
    │   └── migrations.apply_migrations() — advisory lock, run pending migrations
    │
    └── upsert_mission() — bootstrap __knowledge_lake__ system mission
```

---

## Rules and Constraints

- **Never call `db_connect()` for normal operations** — it bypasses the pool and is reserved for migrations only. All agent and route code must use `get_connection()`.
- **`prepare_threshold=None` on all connections** — required for PgBouncer transaction-pool compatibility. Never set a non-None prepare threshold.
- **`factory_json_dumps()` for all JSONB writes** — ensures consistent sorting and UTC datetime serialization.
- **`prune_audit_tables()` is called by the background task in `main.py`** — do not call it directly from agent code.
- **`record_partition_result()` uses a direct (non-pooled) connection** — this is intentional; `SELECT FOR UPDATE` on the mission row requires a full transaction connection, not an autocommit pooled one.
