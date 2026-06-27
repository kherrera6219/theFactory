# Port Coordinator and LogicNode Schema

Last updated: 2026-06-27

Document version: 2026.06.11  
Status: Canonical  
Audience: Developers and architects

---

## Port Coordinator

### Overview

`port_coordinator.py` (9 KB, `services/orchestrator/orchestrator/port_coordinator.py`) manages the allocation and lifecycle of ephemeral internal ports used by agent workers, test runners, and the pod-worker service mesh. It prevents port collisions across concurrently running mission processes and provides a release mechanism so ports are reclaimed when a mission completes or a process dies.

### Code Location

```
services/orchestrator/orchestrator/port_coordinator.py   # 9 KB
```

### How It Works

`PortCoordinator` maintains a Redis-backed allocation table. When any process needs an ephemeral port:

1. It calls `PortCoordinator.acquire(owner_id, purpose)` — returns an available port in the configured range.
2. The allocation is recorded in Redis as `port_alloc:<port>` → `{owner_id, purpose, acquired_at}`.
3. When the process is done, it calls `PortCoordinator.release(port)` — the Redis key is deleted.
4. A background reaper runs every `PORT_REAPER_INTERVAL_SEC` and releases any allocations whose `owner_id` no longer has a live heartbeat (dead-agent cleanup).

### Configuration (`settings.py` keys)

| Key | Default | Description |
|---|---|---|
| `PORT_RANGE_START` | `20000` | First port in the ephemeral allocation range |
| `PORT_RANGE_END` | `29999` | Last port in the range |
| `PORT_REAPER_INTERVAL_SEC` | `30` | How often the reaper checks for orphaned allocations |
| `PORT_TTL_SEC` | `300` | Max time a port can be held without a heartbeat renewal |

### Operational Notes

- Port allocation state is visible via `redis-cli hgetall port_alloc:*`.
- In dev/local setups with `docker compose`, the range must not overlap with host-mapped service ports (8100–8102, 8180, 3100).
- Orphaned ports after a hard crash are automatically reclaimed by the reaper on next cycle.

---

## LogicNode Schema

### Overview

`logicnode_schema.py` (3 KB, `services/orchestrator/orchestrator/logicnode_schema.py`) defines the canonical schema for **LogicNodes** — the core semantic unit that the pod workers extract from source code during language analysis. LogicNodes are tagged semantic concepts with confidence scores and source-location metadata. They are the primary currency of the Knowledge Lake and the Equivalence Verifier.

### Code Location

```
services/orchestrator/orchestrator/logicnode_schema.py   # 3 KB
services/orchestrator/orchestrator/storage_logicnodes.py # 7 KB  — persistence layer
```

### LogicNode Dataclass

```python
@dataclass
class LogicNode:
    node_id: str                      # e.g. "DYN-006-001"
    tag: str                          # e.g. "async_function", "class_definition"
    language_key: str                 # e.g. "DYN" (Python/JS), "SYS" (Go/Rust), "ENT" (Java)
    confidence: float                 # 0.0–1.0, from static analysis engine
    source_file: str                  # relative path within the mission workspace
    source_line_start: int
    source_line_end: int
    content_hash: str                 # SHA-256 of the extracted content
    metadata: dict                    # arbitrary key-value annotations
    mission_id: str
    created_at: datetime
```

### Node ID Convention

The `node_id` follows the pattern `<LANGUAGE_KEY>-<TAG_INDEX>-<SEQUENCE>`:

- `DYN-006-001` → Dynamic Pod (Python/JS), tag index 6 (async function), first instance
- `SYS-012-003` → Systems Pod (Go/Rust), tag index 12 (interface definition), third instance
- `ENT-031-007` → Enterprise Pod (Java/Kotlin), tag index 31 (annotation processor), seventh instance
- `MTH-044-001` → Mathematical Pod, tag index 44 (statistical model), first instance

### Storage Layer (`storage_logicnodes.py`)

`storage_logicnodes.py` (7 KB) provides the PostgreSQL CRUD layer for LogicNodes:

- `upsert(node: LogicNode)` — inserts or updates by `node_id` + `mission_id`
- `get(node_id: str, mission_id: str) → LogicNode`
- `list_by_mission(mission_id: str) → list[LogicNode]`
- `list_by_tag(tag: str, mission_id: str) → list[LogicNode]`
- `delete_by_mission(mission_id: str)` — bulk eviction at mission tombstone

LogicNodes are also written to Qdrant/Milvus via the Knowledge Lake after PostgreSQL persistence, so they are available for semantic queries.

### Tag Taxonomy

The full tag taxonomy (232 patterns across 20 language keys) is defined in `agent_registry.py` and referenced by the pod workers during extraction. Tags are stable identifiers — once assigned an index, they are never renumbered. New tags are always appended.
