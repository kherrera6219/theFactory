# Agent Scaling and Heartbeat

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Canonical
Audience: Operators, developers

This document was rewritten on 2026-07-03 — the previous version described `AgentScaler`/`HeartbeatService` classes, a Redis-TTL-keyed dead-agent state machine, and config keys (`SCALING_POLL_INTERVAL_SEC`, `HEARTBEAT_TTL_SEC`, etc.) that never existed. Both real modules are function-based, not class-based, and simpler than previously documented.

## Agent Scaling — `services/orchestrator/orchestrator/agent_scaling.py`

Feature-flagged via `agent_scaling_enabled` (`AGENT_SCALING_ENABLED`, default `false`). When enabled, the pod-manager stage of Mission Flow v2 (`_prepare_specialist_plan` in `phases_build.py`) evaluates the workload and records a `ScalingDecision` in mission metadata; pod-worker replicas then claim individual partitions and execute in parallel, merged before the QC/audit gate.

Key functions and types:

```python
SCALABLE_AGENT_IDS: frozenset[str]        # the 19 coding specialist agents (Pods A-D)
ABSOLUTE_MAX_INSTANCES: Final[int] = 8    # hard ceiling regardless of config

def is_scalable_agent(agent_id: str) -> bool: ...
def compute_scaling_decision(*, agent_id, workload_items, max_instances=4, items_per_instance=3) -> ScalingDecision: ...
def partition_workload(items, instance_count) -> tuple[WorkPartition, ...]: ...
def merge_partition_results(...) -> MergedResult: ...
def all_partitions_complete(...) -> bool: ...
def record_partition_result(...) -> None: ...
```

- `compute_scaling_decision()` is a pure function: given a workload item list and the configured `agent_scaling_max_instances`/`agent_scaling_items_per_instance` settings, it decides an `instance_count` (capped at `ABSOLUTE_MAX_INSTANCES = 8`) and splits the items into `WorkPartition`s via `partition_workload()`. If the agent isn't in `SCALABLE_AGENT_IDS` or the workload is small enough to fit in one instance, it returns a single-instance decision.
- The `ScalingDecision` is embedded into mission metadata via `embed_scaling_decision()`. `_prepare_specialist_plan` guards against re-computing it on re-entry (checking whether `metadata["scaling_decision"]` already exists) — recomputing would mint fresh random `partition_id`s and orphan already-emitted partition work.
- Pod-worker replicas report back via `record_partition_result()`; `all_partitions_complete()` and `merge_partition_results()` combine them once every partition has reported.

There is no separate `AgentScaler` class, no scaling-poll-interval setting, and no `SCALING_*` env vars — the whole mechanism is driven by the pod-manager phase handler calling these functions directly.

## Agent Heartbeat — `services/orchestrator/orchestrator/heartbeat_service.py`

Two distinct heartbeat sources feed the same storage table (`agent_heartbeats`):

1. **Real per-agent heartbeats** — pod-worker and agent-runtime processes call `POST /internal/agents/heartbeat` directly with their own state.
2. **Autofill for non-pod agents** — `agent_heartbeat_loop(app)`, a background task started at orchestrator startup, runs every `AGENT_HEARTBEAT_INTERVAL_SECONDS` (default `5`, floor `2`) and synthesizes heartbeats for every agent in `AGENT_REGISTRY` whose `category` is `interface`/`executive`/`support` (i.e. agents that don't run as their own pod-worker process and so have no other way to report state). This can be disabled via `AGENT_AUTOFILL_NON_POD_HEARTBEATS` (default `true`).

For the autofill path:
- `_build_non_pod_heartbeat_payloads()` derives each agent's `queue_depth` from mission counts relevant to its role (active missions for interface/executive agents, verified missions for the Tester, complete missions for Deploy, systems-language missions for the Hardware-awareness agent).
- `_state_for_agent()` derives a deterministic `state` (`ERROR`/`PAUSED`/`IDLE`/`VERIFYING`/`RUNNING`/`ACTIVE`) from `queue_depth` plus runtime readiness flags (`db_ready`, `protocol_ready`, `redis_ready`, `consumer_running`) — e.g. any agent reports `ERROR` if the database isn't ready, `PAUSED` if the orchestrator's own consumer loop isn't running.
- `_workload_for_agent()` derives a `workload_pct` (0-100) from `state` and `queue_depth` via per-category multipliers — this is a display heuristic, not a measured load metric.
- Every upsert triggers `_emit_agent_telemetry_event()`, which validates and publishes an `agent.heartbeat`/`agent.state.changed` envelope onto the `alpha` Protocol Bus stream (topic derived from event type) — but only when the app's envelope validator, Redis client, and both `protocol_ready`/`redis_ready` flags are available; otherwise it silently skips emission (heartbeat storage still happens either way).

`AGENT_HEARTBEAT_STALE_SECONDS` (default `45`, floor `10`) is the threshold used elsewhere to decide whether a stored heartbeat is stale. The module itself validates at import time that this is at least 3× `AGENT_HEARTBEAT_INTERVAL_SECONDS` (and at least 20s), logging a warning if not, since agent-runtime's own heartbeat interval defaults to 15s (vs. the orchestrator's 5s) — a stale threshold shorter than 3× the longest real interval would make legitimately-alive pod/specialist agents appear spuriously stale.

There is no separate `HeartbeatService` class, no per-agent `.tick()` method, no Redis TTL keys, and no DEGRADED/DEAD state machine beyond the `state` values listed above.

## Related Docs

- `RUNTIME_AND_AGENT_BASE.md` — the runtime execution engine that hosts `agent_heartbeat_loop` as one of its background tasks
- `MISSION_FLOW_V2.md` — where `compute_scaling_decision`/`_prepare_specialist_plan` fit into the mission lifecycle
