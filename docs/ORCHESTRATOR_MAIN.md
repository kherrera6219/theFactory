# Orchestrator Service — `main.py` Reference

Document version: 2026.06.13
Last updated: 2026-06-27
Status: Canonical
Audience: Developers and operators

**File:** `services/orchestrator/orchestrator/main.py`  
**FastAPI app title:** `HolyGrail Orchestrator`  
**FastAPI version:** `0.3.0`  
**Last documented:** 2026-06-11

---

## Overview

`main.py` is the entry point for the Orchestrator service (`:8101`). It is responsible for:

- Declaring the FastAPI application instance and its lifespan context manager
- Bootstrapping all background tasks at startup and tearing them down at shutdown
- Registering the three route modules (`missions`, `internal`, `operations`)
- Providing the three direct endpoints (`/health`, `/readyz`, `/metrics`)
- Exposing shared auth dependency objects consumed by every route module
- Defining the `FactoryError` exception handler (Local-First Error Handling Standard)
- Emitting per-request Prometheus metrics via HTTP middleware
- Injecting `X-Correlation-Id` and `X-Trace-Id` into every response

The file is intentionally large (~44 KB) because it owns all startup/shutdown state and the agent snapshot builder. Route business logic lives in `routes/`.

---

## Application State (`app.state`)

The `_initialize_app_state()` helper runs at startup and before every `/health` call, guaranteeing all keys are present before any route code reads them. All keys are idempotent — existing values are never overwritten.

| Key | Type | Description |
|-----|------|-------------|
| `settings` | `Settings` | Loaded once via `load_settings()`; shared read-only across all routes |
| `redis` | `aioredis.Redis \| None` | Async Redis client; `None` until `ensure_runtime_ready()` succeeds |
| `redis_ready` | `bool` | True when Redis ping passes |
| `db_ready` | `bool` | True when PostgreSQL connection pool is live |
| `consumer_task` | `Task \| None` | Main Redis Streams consumer (mission intake) |
| `self_heal_task` | `Task \| None` | `runtime_self_heal_loop` — re-establishes Redis/DB on failure |
| `agent_heartbeat_task` | `Task \| None` | `agent_heartbeat_loop` — autofills non-pod agent heartbeats |
| `knowledge_refresh_task` | `Task \| None` | `knowledge_lake_refresh_loop` — periodic bootstrap doc refresh |
| `stale_consumer_reap_task` | `Task \| None` | `stale_consumer_reap_loop` — removes stale Redis consumer groups |
| `protocol_bus_consumer_task` | `Task \| None` | `protocol_bus_consumer_loop` — Sigma lane subscriber |
| `protocol_bus_consumer` | `ProtocolBusConsumer \| None` | Live consumer instance; used by the loop for graceful stop |
| `lifecycle_recovery_task` | `Task \| None` | `lifecycle_recovery_loop` — rehydrates in-flight missions after restart |
| `lifecycle_tasks` | `dict[str, Task]` | Per-mission lifecycle tasks keyed by `mission_id` |
| `lifecycle_recovery_bootstrapped` | `bool` | True after the first full recovery scan completes |
| `lifecycle_recovery_recovered_count` | `int` | Count of missions rehydrated in the last scan |
| `lifecycle_recovery_scanned_count` | `int` | Count of missions inspected in the last scan |
| `lifecycle_recovery_last_at` | `str \| None` | ISO-8601 timestamp of the last completed scan |
| `lifecycle_recovery_last_error` | `str \| None` | Last unhandled exception from the recovery loop |
| `startup_lock` | `asyncio.Lock` | Prevents concurrent startup races |
| `protocol_ready` | `bool` | True when `EnvelopeValidator` loads without error |
| `protocol_error` | `str \| None` | Error message from last `EnvelopeValidator` load attempt |
| `envelope_validator` | `EnvelopeValidator \| None` | Validates all protocol bus envelope shapes |
| `logicnode_schema_ready` | `bool` | True when the LogicNode JSON schema loaded successfully |
| `langgraph_postgres_checkpointer_setup_done` | `bool` | Set by LangGraph lifecycle when Postgres checkpointer is ready |

---

## Lifespan Sequence

The `lifespan` async context manager (FastAPI 0.93+ pattern) owns all startup and shutdown logic.

### Startup Order

1. **ThreadPoolExecutor** — default executor set to 20 workers (`asyncio.get_running_loop().set_default_executor(...)`)
2. **`_initialize_app_state(app)`** — fills all `app.state` keys with safe defaults
3. **`storage.init_connection_pool()`** — creates the SQLAlchemy PG pool; fail-open if unreachable
4. **`ensure_runtime_ready(app)`** — initial Redis + DB probe; fail-open, self-heal retries
5. **`load_prompt_assets()`** — loads versioned prompt assets into `PromptRegistry`; fail-open (see `PROMPT_REGISTRY_AND_ASSETS.md`)
6. **`lifecycle_recovery_loop`** task created
7. **`runtime_self_heal_loop`** task created
8. **`agent_heartbeat_loop`** task created
9. **`knowledge_lake_refresh_loop`** task created
10. **`stale_consumer_reap_loop`** task created
11. **`protocol_bus_consumer_loop`** task created

### Shutdown Order

Shutdown cancels tasks in a specific order to prevent data loss:

1. `lifecycle_recovery_task`
2. `agent_heartbeat_task`
3. `knowledge_refresh_task`
4. `stale_consumer_reap_task`
5. `protocol_bus_consumer_task` (stops the `ProtocolBusConsumer` instance first)
6. `self_heal_task`
7. `consumer_task` (main intake consumer — last to stop)
8. All per-mission `lifecycle_tasks` cancelled and awaited
9. Redis client `aclose()`
10. `storage.close_connection_pool()`

> **Note:** All cancellations use `suppress(asyncio.CancelledError)` to ensure a clean exit even if a task has already finished.

---

## Background Tasks

### `agent_heartbeat_loop(app)`

Runs on the `AGENT_HEARTBEAT_INTERVAL_SECONDS` cadence (default: 30 s). Autofills heartbeat records for all **non-pod** agents (interface, executive, support tiers) whose heartbeats are not emitted by the workers themselves. Can be disabled via `AGENT_AUTOFILL_NON_POD_HEARTBEATS=false`.

**Logic:**
1. Lists up to 2 000 most recent missions
2. Builds `AgentHeartbeatUpsert` payloads via `_build_non_pod_heartbeat_payloads()`
3. Calls `_upsert_agent_heartbeat()` for each agent, which writes to PostgreSQL and emits an `AGENT_HEARTBEAT` or `AGENT_STATE_CHANGED` event on the Redis state stream

### `knowledge_lake_refresh_loop(app)`

Sleeps for `knowledge_refresh_interval_seconds` (default: 3 600 s / 1 h), then calls `run_fetch_phase()` for all supported languages to keep bootstrap documents fresh. Non-fatal: skips the refresh if the DB is not ready.

### `protocol_bus_consumer_loop(app)`

Subscribes the orchestrator to the **Sigma lane** of the Protocol Bus as `AGENT-03-BROKER`. Handles `knowledge_ready` events by cross-checking `is_stocked()` against PostgreSQL and logging divergence. Restarts automatically on transient Redis failures.

Disable with env var: `PROTOCOL_BUS_CONSUMER_ENABLED=false`

### `lifecycle_recovery_loop(app)`

Rehydrates missions that were `queued` or `running` when the process last exited. Controlled by:

| Env Var | Default | Description |
|---------|---------|-------------|
| `LIFECYCLE_RECOVERY_RETRY_SECONDS` | `2.0` | Sleep between scan iterations |
| `LIFECYCLE_RECOVERY_MAX_MISSIONS` | `2000` | Max missions scanned per iteration |

### `runtime_self_heal_loop(app)` / `stale_consumer_reap_loop(app)`

Imported from `runtime.py`. `self_heal_loop` re-establishes Redis and DB connections on failure. `stale_consumer_reap_loop` removes Redis consumer group entries for pods that have not sent a heartbeat within the stale window.

---

## Auth Dependency Objects

Four pre-built `Depends(...)` objects are constructed at module load time from `Settings` and re-used across all route modules:

| Name | Required Roles | Intended Use |
|------|---------------|--------------|
| `MUTATION_AUTH_DEP` | `mutate`, `admin`, `worker` | State-changing operations (create, transition, update) |
| `INTERNAL_AUTH_DEP` | `internal`, `admin`, `worker` | Worker-to-orchestrator callbacks (LogicNode writes, heartbeats) |
| `READ_AUTH_DEP` | `read`, `mutate`, `admin`, `worker`, `internal` | All read operations |

Route modules import these from `main` via the re-export pattern in `routes/_deps.py`.

---

## Direct Endpoints

These three endpoints are defined directly in `main.py` (not in a route module).

### `GET /health`

Liveness + status probe. Always returns `200 OK`. Performs live pings to every enabled store and reports individual readiness flags. Safe to call at any time — will not return `503`.

**Response fields (selected):**

| Field | Type | Description |
|-------|------|-------------|
| `ok` | `bool` | Always `true` |
| `service` | `str` | `"orchestrator"` |
| `redis_healthy` | `bool` | Live ping result |
| `db_ready` | `bool` | PostgreSQL connection pool status |
| `qdrant_ready` | `bool \| null` | Only present when `QDRANT_ENABLED=true` |
| `milvus_ready` | `bool \| null` | Only present when `MILVUS_ENABLED=true` |
| `neo4j_ready` | `bool \| null` | Only present when `NEO4J_ENABLED=true` |
| `object_storage_ready` | `bool \| null` | Only present when `OBJECT_STORAGE_ENABLED=true` |
| `jaeger_ready` | `bool` | TCP reachability check on `jaeger:4318` |
| `mission_count` | `int` | Total missions in PostgreSQL |
| `intake_stream` | `str` | Redis stream name for mission intake |
| `state_stream` | `str` | Redis stream name for state events |
| `auto_transition_enabled` | `bool` | Whether automatic phase transitions are active |
| `active_lifecycle_tasks` | `int` | Count of live per-mission lifecycle tasks |
| `agent_heartbeat_task_running` | `bool` | Whether the heartbeat autofill loop is alive |
| `protocol_ready` | `bool` | EnvelopeValidator load status |
| `lifecycle_recovery_bootstrapped` | `bool` | Whether the first recovery scan has completed |
| `lifecycle_recovery_recovered_count` | `int` | Missions recovered in the last scan |
| `langgraph_enabled` | `bool` | Feature flag from settings |

### `GET /readyz`

Kubernetes readiness probe. Returns `200 OK` only when **all** of the following are true:

- `redis_ready`
- `db_ready`
- `protocol_ready`
- `consumer_running` (main intake consumer task is alive)
- All enabled optional stores (`qdrant`, `milvus`, `neo4j`, `object_storage`) report ready

Returns `503 Service Unavailable` with a detail body listing every individual flag when any check fails.

### `GET /metrics`

Exposes Prometheus metrics in the standard text format (`text/plain; version=0.0.4`). No auth required. Consumed by the Prometheus scraper configured in `docker-compose.yml`.

---

## HTTP Middleware

### Request Metrics Middleware

Wraps every request. Records:

- `REQUEST_COUNTER` — labels: `method`, `path` (matched route template), `status_code`
- `REQUEST_LATENCY` — histogram, labels: `method`, `path`

Injects two response headers:

| Header | Source |
|--------|--------|
| `X-Correlation-Id` | From `x-request-id` or `x-correlation-id` request header; generated as UUID hex if absent |
| `X-Trace-Id` | From OpenTelemetry span context if tracing is enabled |

---

## Error Handling

### `FactoryError` Handler

All `FactoryError` exceptions (from `shared_runtime.errors`) are caught by `_factory_error_handler`. The handler:

1. Attaches a `correlation_id` to the error if absent (from the request headers)
2. Logs the full error object (including `developer_message`) at WARNING level
3. Returns a JSON response with only the **user-safe payload** (`user_message`, `recovery_action`, `error_code`) — developer details are never sent to the client

HTTP status code mapping:

| Severity | Status Code |
|----------|-------------|
| `INFO` | 200 |
| `WARNING` | 400 |
| `RECOVERABLE` | 400 |
| `CRITICAL` | 500 |
| `FATAL` | 500 |

---

## Agent State and Workload Heuristics

Two private functions define the default state/workload logic used when no live heartbeat record exists in PostgreSQL.

### `_state_for_agent(category, short_code, queue_depth, runtime)`

| Condition | Assigned State |
|-----------|---------------|
| DB not ready | `ERROR` |
| Protocol not ready AND category in `{executive, pod_manager, pod_audit}` | `ERROR` |
| Redis not ready AND short_code in `{BROKER, IS, CEO}` | `ERROR` |
| Consumer not running AND category in `{executive, pod_manager}` | `PAUSED` |
| `queue_depth == 0` | `IDLE` |
| category is `pod_audit` OR short_code in `{SECURITY, COMPLIANCE, TESTER}` | `VERIFYING` |
| category in `{interface, executive, pod_manager}` | `RUNNING` |
| Fallback | `ACTIVE` |

### `_workload_for_agent(category, state, queue_depth)`

Base workload scores by state: `RUNNING=42`, `VERIFYING=36`, `ACTIVE=34`. Per-mission multipliers by category:

| Category | Multiplier |
|----------|----------|
| `specialist` | 16 |
| `interface` | 14 |
| `executive` | 12 |
| `pod_manager` | 12 |
| `pod_audit` | 11 |
| `support` | 9 |
| default | 10 |

Final value is clamped to `[0, 100]`.

---

## Agent Telemetry Events

`_emit_agent_telemetry_event()` publishes structured events to the Redis state stream (`app.state.settings.state_stream`) using the Protocol Bus envelope format.

**Event types emitted:**

| Trigger | Topic | Event Type |
|---------|-------|------------|
| State changed since last heartbeat | `agent.state.changed` | `AGENT_STATE_CHANGED` |
| Periodic heartbeat (no state change) | `agent.heartbeat` | `AGENT_HEARTBEAT` |

Events with `state == ERROR` are published at `priority: HIGH`. All others use `priority: NORMAL`.

---

## Route Modules

`main.py` mounts three routers at the end of the file:

| Module | File | Size | Description |
|--------|------|------|-------------|
| `missions_router` | `routes/missions.py` | ~12 KB | Mission CRUD, state transitions, SSE stream |
| `internal_router` | `routes/internal.py` | ~44 KB | Worker callbacks: LogicNodes, heartbeats, artifacts, audit events |
| `operations_router` | `routes/operations.py` | ~25 KB | Operator dashboard: agent snapshot, pod status, knowledge lake |

For full endpoint listings for each router, see `ORCHESTRATOR_ROUTES_MISSIONS.md`, `ORCHESTRATOR_ROUTES_INTERNAL.md`, and `ORCHESTRATOR_ROUTES_OPERATIONS.md` (forthcoming — tracked in the Coverage Gap Tracker).

---

## Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LIFECYCLE_RECOVERY_RETRY_SECONDS` | `2.0` | Sleep between lifecycle recovery scan iterations |
| `LIFECYCLE_RECOVERY_MAX_MISSIONS` | `2000` | Max missions scanned per recovery iteration |
| `AGENT_AUTOFILL_NON_POD_HEARTBEATS` | `true` | Enable/disable the heartbeat autofill loop |
| `PROTOCOL_BUS_CONSUMER_ENABLED` | `true` | Enable/disable the Sigma lane consumer |
| `OTEL_TRACING_ENABLED` | `true` | Enable OpenTelemetry tracing and Jaeger reachability check in `/health` |

All other settings are declared in `settings.py` and loaded via `load_settings()`.

---

## Refactoring Notes

`main.py` at ~44 KB is large for a FastAPI entry point. The following items are candidates for future extraction if the file continues to grow:

- `_build_operations_agents_snapshot()` (~120 lines) → `routes/operations.py` or a dedicated `agent_snapshot.py` helper
- `agent_heartbeat_loop()` + `_build_non_pod_heartbeat_payloads()` + `_upsert_agent_heartbeat()` + `_emit_agent_telemetry_event()` → `heartbeat_service.py` (already exists — this logic could move there)
- `knowledge_lake_refresh_loop()` → `knowledge_lake.py`
- `protocol_bus_consumer_loop()` + `_handle_sigma_knowledge_ready()` → `protocol_bus_consumer.py`

The route modules (`routes/`) are already well-decomposed. The remaining complexity in `main.py` is the startup/shutdown machinery and the agent heuristic functions — these are appropriately placed here.
