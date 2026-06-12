# Models and Domain Schema

**Source file:** `services/orchestrator/orchestrator/models.py`  
**Size:** ~13 KB  
**Role:** Single source of truth for every domain enum, state machine, event type, Pydantic model, and valid transition map used across the entire orchestrator.

---

## Overview

`models.py` is the canonical schema layer. Every other orchestrator module imports from it — never the reverse. It contains zero I/O logic; it is pure data shape definitions. Any change here has blast radius across the entire system and must be treated as a breaking change if existing values are removed or renamed.

---

## Enumerations

### `MissionType`

Describes the category of work the mission is performing.

| Value | Description |
|---|---|
| `BUILD_NEW` | Build a new software artifact from a natural-language prompt |
| `IMPORT_MODERNIZE` | Import and modernize an existing codebase |
| `PORT` | Port code from one language or framework to another |
| `DEBUG_REPAIR` | Diagnose and repair a failing or broken codebase |
| `SECURITY_HARDEN` | Apply security hardening to an existing codebase |
| `REDUCE_DEPENDENCIES` | Execute a Dependency Absorption pass |
| `RUN_QC` | Execute a Runtime QC pass without producing new code |
| `ARCHITECTURE_DOCS` | Generate architecture documentation from a codebase |
| `ANALYZE_ONLY` | Static analysis only — no code changes |
| `SELF_ANALYZE` | The factory analyzes itself |

### `DepthMode`

Controls how deeply the pipeline processes a mission — directly impacts LLM call count, verification rounds, and wall time.

| Value | Profile | Typical Use |
|---|---|---|
| `SPRINT` | Fast, shallow | Prototypes, local dev |
| `STANDARD` | Balanced | Default for most missions |
| `PRODUCTION` | Deep, verified | Production-bound deliverables |
| `REGULATED` | Full audit trail | Compliance-sensitive environments |
| `AUTONOMOUS_LONG_RUN` | Unbounded depth | Multi-hour autonomous missions |

### `OutputMode`

Controls what the mission produces at completion.

| Value | Description |
|---|---|
| `ANALYZE_ONLY` | No output files; report only |
| `PLAN_ONLY` | Plan document only |
| `PATCH_PROPOSAL` | Proposed patch without application |
| `APPLY_PATCH` | Applies the patch in-place |
| `FULL_BUILD` | Complete build artifact set |
| `DEPENDENCY_REDUCTION` | Reduced dependency manifest |
| `RUN_QC` | QC report only |
| `FULL_TRANSFORMATION` | All output types combined |

### `DataClassification`

Enforces data handling requirements. Tier value is embedded in `metadata_json` and enforced by `security_compliance.py`.

| Value | Tier | Description |
|---|---|---|
| `TIER_0_PUBLIC` | 0 | Public-domain input; no restrictions |
| `TIER_1_INTERNAL` | 1 | Internal use only |
| `TIER_2_SENSITIVE` | 2 | Sensitive; encrypted at rest and in transit |
| `TIER_3_REGULATED` | 3 | Regulated data; full audit trail required; triggers `local_only` agent enforcement |

See `DATA_CLASSIFICATION_POLICY.md` for the full handling matrix.

---

## Mission State Machine

### `MissionState`

All valid mission states. The active engine (v2, LangGraph, or legacy v1) determines the path used through these states.

```
INTAKE → QUEUED

  V2 path:   QUEUED → PM_INTAKE → [CLARIFYING →] FETCH → CEO_DELEGATED
                     → POD_ASSIGNED → SPECIALIST_ASSIGNED → RUNNING
                     → GATING → FUSION → VERIFIED → COMPLETE
                                                   ↘ FAILED (any state)

  V1 path:   QUEUED → GATING → RUNNING → VERIFIED → COMPLETE
```

| State | Engine | Description |
|---|---|---|
| `INTAKE` | Both | Mission record created, not yet queued |
| `QUEUED` | Both | Awaiting engine pickup |
| `PM_INTAKE` | V2 only | PM Agent (AGENT-01-PM) parsing intent and chartering |
| `CLARIFYING` | V2 only | PM paused; awaiting operator clarification via `/clarify` |
| `FETCH` | V2 only | IS Agent preloading knowledge lake for the target language |
| `CEO_DELEGATED` | V2 only | CEO Agent (AGENT-02-CEO) has delegated to a pod manager |
| `POD_ASSIGNED` | V2 only | Pod manager assigned; pod workers being allocated |
| `SPECIALIST_ASSIGNED` | V2 only | Specialist agent assigned; ready to execute |
| `RUNNING` | Both | Active execution in progress |
| `GATING` | Both | Quality gate in progress |
| `FUSION` | Both | Output fusion and final assembly |
| `VERIFIED` | Both | Equivalence verification passed |
| `COMPLETE` | Both | Mission complete; all artifacts persisted |
| `FAILED` | Both | Terminal failure; error in `metadata_json` |

### `V1_STATES` and `V2_STATES`

Two named `frozenset` constants that define which states are valid for each engine version. Used by `storage_missions.py` and `mission_flow_v2/` for state validation assertions.

### `VALID_TRANSITIONS`

A `dict[MissionState, set[MissionState]]` that encodes the complete allowed transition graph. Every call to `transition_mission_state()` in `storage_missions.py` validates against this map before issuing the SQL `UPDATE`. An attempt to move to a state not in the allowed set raises a `ValueError` before touching the database.

```python
# Example: legal next states from RUNNING
VALID_TRANSITIONS[MissionState.running] == {
    MissionState.gating,
    MissionState.fusion,
    MissionState.verified,
    MissionState.failed,
}
```

---

## Event Types

### `EventType`

A `Literal` union of all valid `event_type` strings that can appear on a `MissionEvent`, be emitted by `runtime.py`, `mission_flow_v2/`, or `langgraph_lifecycle.py`, and be persisted to the `mission_state_events` table.

Event type categories:

| Category | Examples |
|---|---|
| **State-transition events** | `MISSION_INTAKE`, `MISSION_PM_INTAKE`, `MISSION_COMPLETE`, `MISSION_FAILED` |
| **Delegation / planning** | `MISSION_POD_MANAGER_ASSIGNED`, `MISSION_AIM_GENERATED`, `MISSION_SCALING_DECIDED` |
| **Operational** | `MISSION_LOGICNODE_WRITTEN`, `MISSION_DELIVERED`, `MISSION_COMPLETION_BLOCKED` |
| **Intelligence-layer** | `MISSION_SECURITY_ANALYSIS_COMPLETE`, `MISSION_INTEGRATION_TESTS_GENERATED`, `MISSION_DEPABS_EXECUTED` |
| **Agent lifecycle** | `AGENT_STATE_CHANGED` |

All 38 event type strings are defined in `models.py`. Any new event type emitted anywhere in the system must first be added here.

---

## Pydantic Models

### Database & Storage Models

#### `MissionAttachment`

Refers to a file in object storage that provides mission context (PRD, spec, legacy source).

| Field | Type | Description |
|---|---|---|
| `file_id` | `str` | Unique attachment identifier |
| `filename` | `str` | Original filename |
| `content_type` | `str` | MIME type |
| `size_bytes` | `int` | File size in bytes |
| `purpose` | `str \| None` | `reference`, `PRD`, `spec`, or `legacy_source` |
| `object_key` | `str \| None` | Explicit object-storage key for the file bytes |
| `content` | `str \| None` | Extracted text populated during intake |

#### `MissionRecord`

The canonical in-memory representation of a persisted mission row. Returned by all `storage_missions` read functions.

| Field | Type | Notes |
|---|---|---|
| `mission_id` | `str` | Primary key |
| `prompt` | `str` | Original natural-language prompt |
| `requested_target_language` | `str \| None` | e.g., `"python"`, `"go"` |
| `mission_type` | `MissionType \| None` | Deserialized from `metadata_json.__mission_type__` |
| `depth_mode` | `DepthMode \| None` | Deserialized from `metadata_json.__depth_mode__` |
| `output_mode` | `OutputMode \| None` | Deserialized from `metadata_json.__output_mode__` |
| `data_classification` | `DataClassification \| None` | Deserialized from `metadata_json.__data_classification__` |
| `attachments` | `list[MissionAttachment]` | File context attached at intake |
| `risk_assessment` | `dict \| None` | Security risk assessment result |
| `global_style_directives` | `list[str]` | Cross-mission coding style constraints |
| `metadata` | `dict` | Full `metadata_json` JSONB blob |
| `project_id` | `str \| None` | Resolved project namespace |
| `state` | `MissionState` | Current pipeline state |
| `created_at` | `datetime` | UTC creation timestamp |

**Charter field embedding:** `mission_type`, `depth_mode`, `output_mode`, and `data_classification` are stored inside `metadata_json` under double-underscore keys (e.g., `__mission_type__`) rather than as dedicated columns. `storage_missions.py` handles serialization/deserialization transparently.

#### `MissionEvent`

A single state-transition event row from `mission_state_events`.

| Field | Type | Description |
|---|---|---|
| `mission_id` | `str` | Foreign key to `missions` |
| `previous_state` | `MissionState \| None` | State before transition (`None` for initial intake) |
| `new_state` | `MissionState` | State after transition |
| `event_type` | `EventType` | Typed event string from the `EventType` literal |
| `ts` | `datetime` | UTC timestamp of the event |

---

### API Request/Response Models

#### `MissionCreate`

Request body for `POST /missions`. All fields except `mission_id` and `prompt` are optional at intake — the PM Agent fills them in during `PM_INTAKE`.

#### `MissionStateUpdate`

Request body for `PATCH /missions/{id}/state`. Accepts `new_state` and an optional `expected_state` for optimistic concurrency (if `expected_state` is provided, the SQL update is conditional on the current DB state matching).

#### `MissionClarifyRequest`

Request body for `POST /missions/{id}/clarify`. Operator-supplied text (3–2000 chars) that resolves a `CLARIFYING`-state mission. The text is stored in `metadata["pm_clarification"]` and the mission is transitioned back to `PM_INTAKE`.

#### `PodAssignmentUpsert`

Request body for pod assignment upsert endpoints. Carries pod ID, worker count, scaling parameters, and assigned agent IDs.

---

## Design Rules

- **Never import from domain modules into `models.py`** — this would create circular imports. `models.py` has no dependencies on any other orchestrator module.
- **Enum values are the stored strings** — all enums extend `str, Enum` so their `.value` is the exact string stored in PostgreSQL and emitted on the bus.
- **`VALID_TRANSITIONS` is enforced at the storage layer** — the transition map in `models.py` is authoritative; `storage_missions.transition_mission_state()` validates every transition against it before the SQL write.
- **Charter fields are stored in `metadata_json`** — `MissionType`, `DepthMode`, `OutputMode`, and `DataClassification` are embedded in `metadata_json` as `__key__` entries, not as separate columns. This was a deliberate schema-stability decision documented in `SCHEMA_REGISTRY_AND_VERSIONING.md`.
