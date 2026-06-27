# Agent Scaling and Heartbeat

Last updated: 2026-06-27

Document version: 2026.06.11  
Status: Canonical  
Audience: Operators and developers

## Overview

Two modules govern the runtime health and capacity of the 41-agent pool:

- **`agent_scaling.py`** (11 KB) — dynamic concurrency management; scales agent worker slots up and down based on mission queue depth and resource utilisation.
- **`heartbeat_service.py`** (10 KB) — periodic liveness tracking; each agent instance emits a heartbeat tick that the service aggregates to determine agent health and trigger recovery on missed beats.

## Code Locations

```
services/orchestrator/orchestrator/agent_scaling.py     # 11 KB
services/orchestrator/orchestrator/heartbeat_service.py # 10 KB
```

## Agent Scaling

### How It Works

`AgentScaler` runs as a background asyncio task that samples the Redis mission queue depth and the current active worker count every `SCALING_POLL_INTERVAL_SEC` seconds. It applies a simple PID-style controller:

```
active_workers  = count of agents with heartbeat age < HEARTBEAT_STALE_SEC
queue_depth     = len(pending missions in Redis queue)
target_workers  = clamp(queue_depth × SCALE_FACTOR, MIN_WORKERS, MAX_WORKERS)
delta           = target_workers − active_workers

if delta > 0: spawn delta new agent worker coroutines
if delta < 0: gracefully drain and stop abs(delta) idle workers
```

### Configuration (`settings.py` keys)

| Key | Default | Description |
|---|---|---|
| `SCALING_POLL_INTERVAL_SEC` | `15` | How often the scaler re-evaluates |
| `SCALE_FACTOR` | `1.5` | Workers spawned per queued mission |
| `MIN_WORKERS` | `2` | Floor — always at least this many agents active |
| `MAX_WORKERS` | `16` | Ceiling — hard cap on concurrent agents |
| `SCALE_DOWN_GRACE_SEC` | `30` | How long an idle worker waits before stopping |

### Observability

- Grafana panel: **Agent Pool Size** — tracks `active_workers` and `target_workers` over time.
- Metric: `orchestrator_agent_pool_size{state="active|idle|draining"}` (Prometheus gauge).

## Heartbeat Service

### How It Works

Each agent instance calls `HeartbeatService.tick(agent_id)` at the end of every work loop iteration. The service writes the current timestamp to Redis under `heartbeat:<agent_id>` with a TTL of `HEARTBEAT_TTL_SEC`.

A background checker runs every `HEARTBEAT_CHECK_INTERVAL_SEC` and scans all known agent IDs:

- **Fresh** (`age < HEARTBEAT_STALE_SEC`): agent is healthy, no action.
- **Stale** (`HEARTBEAT_STALE_SEC ≤ age < HEARTBEAT_DEAD_SEC`): agent is flagged as `DEGRADED`. A warning log and Prometheus alert fire.
- **Dead** (`age ≥ HEARTBEAT_DEAD_SEC` or key expired): agent is marked `DEAD`. The lifecycle recovery module is notified to reassign any in-flight mission steps the agent held.

### Configuration (`settings.py` keys)

| Key | Default | Description |
|---|---|---|
| `HEARTBEAT_TICK_INTERVAL_SEC` | `5` | How often each agent calls tick() |
| `HEARTBEAT_TTL_SEC` | `30` | Redis key TTL for heartbeat entry |
| `HEARTBEAT_STALE_SEC` | `15` | Age at which agent is flagged DEGRADED |
| `HEARTBEAT_DEAD_SEC` | `30` | Age at which agent is marked DEAD |
| `HEARTBEAT_CHECK_INTERVAL_SEC` | `10` | How often the background checker runs |

### Recovery on Dead Agent

When an agent is marked `DEAD`:

1. `HeartbeatService` notifies `lifecycle_recovery.py` with the dead agent's ID and last known mission step.
2. `lifecycle_recovery.py` queries PostgreSQL for any mission steps assigned to that agent.
3. Affected steps are reset to `PENDING` and re-queued for a healthy agent to pick up.
4. A `AGENT_DEAD_RECOVERED` audit event is emitted.

### Operational Notes

- Heartbeat Redis keys are prefixed `heartbeat:` and visible via `redis-cli keys 'heartbeat:*'`.
- If `HEARTBEAT_ENABLED=false` (dev/test only), the heartbeat service is a no-op and no recovery logic runs.
- Dead-agent recovery time is included in the DR RTO measurement (target: < 45 seconds end-to-end).
