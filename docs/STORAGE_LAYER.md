# Storage Layer Reference

Document version: 2026.06.13
Last updated: 2026-06-27
Status: Canonical
Audience: Developers and operators

**Files:** `services/orchestrator/orchestrator/storage_core.py` and all `storage_*.py` modules  
**Last documented:** 2026-06-13

---

## Overview

The orchestrator's storage layer is organized as a **thin-module pattern**: a shared infrastructure module (`storage_core.py`) provides the connection pool, migration runner, JSON serialization helpers, and the one custom exception — and every domain area has its own `storage_<domain>.py` module that imports from core without creating circular dependencies.

All writes go through PostgreSQL (via `psycopg` + `psycopg-pool`). Redis is used for state streams and heartbeat fan-out only — it is not the system of record for anything.

The public surface is re-exported through `storage.py` — callers always import from `storage`, never from the domain files directly.

```
storage_core.py         — connection pool, migrations, JSON helpers, PodAssignmentConflictError
storage_missions.py     — mission CRUD + state machine + event log (table: mission_state_events)
storage_pods.py         — pod assignments (table: mission_pod_assignments) + project summaries
storage_logicnodes.py   — LogicNode records + knowledge lake entries (table: mission_knowledge)
storage_artifacts.py    — audit reports, review approvals, build artifacts, testdata, RQCA reports
storage_agents.py       — agent heartbeats + action event audit ledger
storage.py              — re-export façade (callers import from here, not from domain files)
```

---

## `storage_core.py` — Shared Infrastructure

### Connection Strategy

The layer uses **two separate connection paths** for two different use cases:

| Path | Function | DSN Used | When |
|------|----------|----------|------|
| Pool | `get_connection()` | `settings.postgres_url` (PgBouncer) | All normal storage operations |
| Direct | `db_connect()` | `settings.migration_postgres_url` (Postgres direct) | Schema migrations only |

The split exists because schema migrations take a **session-level advisory lock** (`pg_advisory_lock`). In PgBouncer transaction-pool mode the bouncer reassigns the backend connection between statements and runs `DISCARD ALL`, which silently releases advisory locks mid-migration. The direct connection bypasses the bouncer for the duration of the migration run only.

> **PgBouncer safety:** Both connection paths disable server-side prepared statements (`prepare_threshold=None`). Named prepared statements are connection-scoped and would not survive PgBouncer's connection reassignment.

---

### Connection Pool

```python
init_connection_pool(settings: Settings) -> ConnectionPool
```

Initializes the module-level `_pool` singleton (idempotent — safe to call multiple times). Called once during service startup in `main.py`.

| Pool Parameter | Value | Source |
|---|---|---|
| `min_size` | `settings.db_pool_min_size` | `DB_POOL_MIN_SIZE` env var |
| `max_size` | `settings.db_pool_max_size` | `DB_POOL_MAX_SIZE` env var |
| `max_waiting` | `20` | Hardcoded |
| `timeout` | `30s` | Hardcoded |

```python
@contextmanager
def get_connection() -> Iterator[Any]
```

Context manager. Borrows a connection from the pool for the duration of the block and returns it on exit. Raises `RuntimeError` if the pool was not initialized. All storage domain modules use this — never `db_connect()`.

```python
close_connection_pool() -> None
```

Closes the pool and resets `_pool` to `None`. Called in `main.py`'s shutdown handler.

---

### Schema Migration

```python
ensure_db_schema(settings: Settings) -> None
```

Runs `migrations.apply_migrations(settings, connect=db_connect)` using the direct connection. After migrations complete, it bootstraps the `__knowledge_lake__` system mission — a synthetic `MissionRecord` with `mission_id="__knowledge_lake__"`, state `COMPLETE` — to prevent foreign key violations when the IS Agent pre-indexes language documentation entries into the Knowledge Lake before any real mission exists.

The bootstrap is idempotent — it catches and warns on conflict rather than raising.

---

### JSON & Datetime Helpers

| Helper | Signature | Purpose |
|--------|-----------|--------|
| `_to_iso` | `(Any) -> str` | Converts `datetime` to UTC ISO string; falls back to `str()` |
| `_json_to_dict` | `(Any) -> dict` | Safely parses JSON strings or passes through dicts; returns `{}` on empty/null |
| `_json_to_list` | `(Any) -> list` | Safely parses JSON strings or passes through lists; returns `[]` on empty/null |
| `FactoryJsonEncoder` | `JSONEncoder` | Extends the stdlib encoder to serialize `datetime` (UTC ISO) and Pydantic models via `model_dump()` |
| `factory_json_dumps` | `(Any) -> str` | Canonical serializer used throughout; produces sorted-key, compact JSON for deterministic SHA-256 hashing |

> **Why `sort_keys=True`?** Deterministic key ordering ensures the SHA-256 digest of a payload is stable regardless of Python dict insertion order. This is required for the `event_digest_sha256` and `content_sha256` fields in the audit chain to be reproducible.

---

### `PodAssignmentConflictError`

```python
class PodAssignmentConflictError(Exception):
    existing_assignment: dict[str, Any]
```

Raised by `storage_pod_assignments.upsert_pod_assignment()` when a mission is already assigned to a different pod and a second assignment is attempted. The `existing_assignment` dict carries the current assignment for the caller to inspect.

---

## Domain Storage Modules

Each module follows the same pattern: stateless functions that accept `settings: Settings` as their first argument and use `get_connection()` internally. None of them import from each other — only from `storage_core`.

### `storage_missions.py`

Manages the `missions` PostgreSQL table.

| Function | Description |
|----------|-------------|
| `upsert_mission(settings, record, source_stream_id)` | INSERT OR UPDATE a `MissionRecord`; writes a `MISSION_INTAKE` event on first insert |
| `fetch_mission(settings, mission_id)` | Returns a `MissionRecord` or `None` if not found |
| `list_missions(settings, state, limit, offset)` | Returns a list of `MissionRecord` filtered by state |
| `update_mission_state(settings, mission_id, new_state, expected_state, event_type)` | Enforces `VALID_TRANSITIONS`; uses `expected_state` for optimistic locking; emits a `MissionEvent` on success |
| `update_mission_metadata(settings, mission_id, metadata)` | Merges new keys into `metadata` JSON column; does not overwrite existing keys |

The `CLARIFYING` state has a special case: `update_mission_state` with `new_state=CLARIFYING` also writes the clarification prompt text into `metadata["pm_clarification_prompt"]` so the PM Agent can read it when the mission transitions back to `PM_INTAKE`.

---

### `storage_missions.py` — Mission CRUD and Event Log

Manages the `missions` and `mission_state_events` PostgreSQL tables. State events are
**append-only** — no updates or deletes.

| Function | Description |
|----------|-------------|
| `upsert_mission(settings, record, source_stream_id)` | INSERT OR UPDATE a `MissionRecord`; writes a `MISSION_INTAKE` event on first insert |
| `fetch_mission(settings, mission_id)` | Returns a `MissionRecord` or `None` if not found |
| `list_missions(settings, state, limit, offset)` | Returns a list of `MissionRecord` filtered by state |
| `update_mission_state(settings, mission_id, new_state, expected_state, event_type)` | Enforces `VALID_TRANSITIONS`; uses `expected_state` for optimistic locking; emits a `MissionEvent` on success |
| `update_mission_metadata(settings, mission_id, metadata)` | Merges new keys into `metadata` JSON column; does not overwrite existing keys |
| `insert_mission_event(settings, mission_id, ...)` | Appends a row to `mission_state_events` |
| `list_mission_events(settings, mission_id, limit)` | Returns events for a mission in ascending `ts` order |
| `transition_mission_state(settings, mission_id, ...)` | Atomic state transition with event write |

The `CLARIFYING` state has a special case: `update_mission_state` with `new_state=CLARIFYING` also writes the clarification prompt text into `metadata["pm_clarification_prompt"]` so the PM Agent can read it when the mission transitions back to `PM_INTAKE`.

---

### `storage_pods.py` — Pod Assignments

Manages the `mission_pod_assignments` table (one row per mission, unique constraint on `mission_id`).

| Function | Description |
|----------|-------------|
| `upsert_pod_assignment(settings, upsert)` | Writes or updates a pod assignment; raises `PodAssignmentConflictError` if a different pod is already assigned |
| `get_pod_assignment(settings, mission_id)` | Returns the current pod assignment dict or `None` |
| `list_pod_assignments(settings, limit)` | Returns all pod assignments |
| `summarize_projects(settings, limit)` | Returns project-level mission groupings from the `missions` table |

---

### `storage_logicnodes.py` — LogicNodes and Knowledge Lake

Manages the `logic_nodes` and `mission_knowledge` PostgreSQL tables.

**LogicNode functions** — tagged semantic concepts extracted from source code during pod worker analysis (e.g. `DYN-006-001 async function, confidence=0.94, line=47`):

| Function | Description |
|----------|-------------|
| `upsert_logicnode(settings, upsert)` | Inserts or updates a `LogicNodeUpsert`; validates the node dict against the registered JSON schema |
| `upsert_logicnodes_batch(settings, upserts)` | Batch upsert of multiple LogicNodes in one transaction |
| `list_logicnodes(settings, mission_id, limit)` | Returns logic nodes for a mission |
| `list_recent_logicnodes(settings, limit)` | Returns recent logic nodes across all missions |

**Knowledge Lake functions** — pre-indexed language documentation used by the IS Agent during FETCH:

| Function | Description |
|----------|-------------|
| `upsert_knowledge(settings, mission_id, knowledge_id, content, created_at)` | Inserts or updates a knowledge entry in `mission_knowledge` |
| `upsert_knowledge_batch(settings, entries)` | Batch upsert of multiple knowledge entries |
| `list_knowledge(settings, mission_id, limit)` | Lists all knowledge entries for a mission |

> The `__knowledge_lake__` synthetic mission (bootstrapped by `ensure_db_schema`) acts as the parent for all language-level global knowledge entries, keeping them accessible without requiring a real mission context.

---

### `storage_artifacts.py` — Audit Reports, Review Approvals, and Build Artifacts

Manages `audit_reports`, `review_approvals`, `build_artifacts`, testdata manifests, and runtime QC reports.

**Audit reports:**

| Function | Description |
|----------|-------------|
| `upsert_audit_report(settings, upsert)` | Writes or updates a pod or RQCA audit report |
| `list_audit_reports(settings, mission_id, limit)` | Lists all audit reports for a mission |
| `list_recent_audit_reports(settings, limit)` | Lists recent audit reports across all missions |

**Review approvals** (`review_approvals` table) — written when a human operator resolves a `HUMAN_REVIEW` escalation gate:

| Function | Description |
|----------|-------------|
| `upsert_review_approval(settings, upsert)` | Writes a `ReviewApprovalUpsert`; computes `receipt_digest` from the approval content |
| `get_review_approval(settings, approval_id)` | Looks up an approval by ID |

**Build artifacts** — the tangible outputs of each mission phase (generated code, tests, docs, compliance reports):

| Function | Description |
|----------|-------------|
| `upsert_build_artifact(settings, mission_id, ...)` | Inserts or updates a `MissionBuildArtifactRecord` |
| `list_build_artifacts(settings, mission_id, limit)` | Lists build artifacts for a mission |
| `get_build_artifact(settings, mission_id, artifact_id)` | Returns a single artifact or `None` |
| `insert_testdata_manifest(settings, ...)` | Writes a testdata manifest record |
| `get_testdata_manifest(settings, mission_id)` | Returns the testdata manifest or `None` |
| `insert_runtime_qc_report(settings, ...)` | Writes a runtime QC (RQCA) report |
| `get_runtime_qc_report(settings, mission_id)` | Returns the RQCA report or `None` |

---

### `storage_agents.py` — Agent Heartbeats and Action Event Audit Ledger

Manages `agent_runtime_heartbeats`, `agent_runtime_events`, and `agent_action_events` tables.

**Heartbeats** — one row per agent ID, updated on each heartbeat; used by the dashboard to display live agent status:

| Function | Description |
|----------|-------------|
| `upsert_agent_heartbeat(settings, upsert)` | Inserts or updates an agent heartbeat row in `agent_runtime_heartbeats` |
| `get_agent_heartbeat(settings, agent_id)` | Returns the current heartbeat dict for an agent or `None` |
| `list_agent_heartbeats(settings, limit)` | Returns all heartbeats |
| `list_recent_agent_events(settings, limit)` | Returns recent runtime events from `agent_runtime_events` |

**Audit ledger** — the `agent_action_events` table is a **hash-chained, append-only** record of every significant action taken by every agent:

| Function | Description |
|----------|-------------|
| `insert_agent_action_event(settings, record)` | Appends a new `AgentActionEventRecord`; computes `event_digest_sha256` and `prev_event_digest_sha256` using `factory_json_dumps` before insert |
| `create_agent_action_event(settings, ...)` | Higher-level wrapper that constructs the record and calls `insert_agent_action_event` |
| `list_mission_agent_action_events(settings, mission_id, ...)` | Returns audit ledger entries for a mission |
| `list_project_agent_action_events(settings, ...)` | Returns audit ledger entries across a project |
| `prune_audit_tables(settings, retention_days)` | Deletes audit rows older than the retention window |

`insert_agent_action_event` is the **only write path to the audit ledger**. It fetches the digest of the most recent event for the same `mission_id` before inserting, creating the hash chain. This is done inside a single `get_connection()` block to prevent races on the `prev_event_digest_sha256` field.

---

## Error Handling Conventions

| Scenario | Behavior |
|----------|----------|
| Mission not found | Returns `None` — callers must check |
| Invalid state transition | `ValueError` with transition details |
| Pod assignment conflict | `PodAssignmentConflictError` with existing assignment |
| Pool not initialized | `RuntimeError` from `get_connection()` |
| `psycopg` not installed | `RuntimeError` from `db_connect()` |
| JSON parse failure | `_json_to_dict` / `_json_to_list` return `{}` / `[]` — never raises |
| Knowledge lake bootstrap conflict | Warning log; execution continues |

---

## Settings Reference

All storage configuration comes from `settings.py` environment variables:

| Setting | Env Var | Description |
|---------|---------|-------------|
| `postgres_url` | `POSTGRES_URL` | PgBouncer DSN for pooled storage operations |
| `migration_postgres_url` | `MIGRATION_POSTGRES_URL` | Direct Postgres DSN for schema migrations |
| `db_pool_min_size` | `DB_POOL_MIN_SIZE` | Minimum pool connections (default: `2`) |
| `db_pool_max_size` | `DB_POOL_MAX_SIZE` | Maximum pool connections (default: `10`) |

---

## Rules and Constraints

- **Never call `db_connect()` for normal operations** — reserved for migrations only. All agent and route code must use `get_connection()`.
- **`prepare_threshold=None` on all connections** — required for PgBouncer transaction-pool compatibility.
- **`factory_json_dumps()` for all JSONB writes** — ensures consistent sorting and UTC datetime serialization for reproducible SHA-256 hashes.
- **`write_agent_action_event()` is the only audit ledger write path** — do not insert directly into `agent_action_events`.
