# Orchestrator Models Reference

Document version: 2026.06.13
Last updated: 2026-06-27
Status: Canonical
Audience: Developers and operators

**File:** `services/orchestrator/orchestrator/models.py`  
**Last documented:** 2026-06-11

---

## Overview

`models.py` is the **schema source of truth** for the entire Orchestrator service. It defines all enumerations, state machine rules, and Pydantic models used by routes, storage, runtime, and the protocol bus. No SQLAlchemy ORM classes live here — persistence mapping is handled in the `storage_*.py` modules. Every model here is a pure Pydantic `BaseModel` or a `str`-backed `Enum`.

The file is organized into three sections:

1. **Domain Models** — enumerations, state machine, and event type catalogue
2. **Database & Storage Models** — shapes of records read from and written to PostgreSQL
3. **API Request/Response Models** — shapes of inbound API payloads and outbound records

---

## Domain Models

### `MissionType`

Declares what kind of work a mission performs. Set at intake and used by the CEO agent to select the appropriate pod and specialist.

| Value | Description |
|-------|-------------|
| `BUILD_NEW` | Greenfield software build from a natural language prompt |
| `IMPORT_MODERNIZE` | Modernize an imported legacy codebase |
| `PORT` | Port existing code to a new language or framework |
| `DEBUG_REPAIR` | Diagnose and fix failing or broken code |
| `SECURITY_HARDEN` | Harden an existing codebase against known vulnerability patterns |
| `REDUCE_DEPENDENCIES` | Run the Dependency Absorption doctrine against a codebase |
| `RUN_QC` | Execute the quality and compliance verification pass only |
| `ARCHITECTURE_DOCS` | Generate architecture documentation from existing code |
| `ANALYZE_ONLY` | Read and analyze code without producing output artifacts |
| `SELF_ANALYZE` | Factory self-analysis — the system analyzes its own codebase |

---

### `DepthMode`

Controls how deeply each phase of the pipeline executes — how many agents are activated, how many verification passes run, and the rigor of the audit trail.

| Value | Use Case |
|-------|----------|
| `SPRINT` | Fastest pass; minimal verification; for rapid prototyping |
| `STANDARD` | Default for most missions |
| `PRODUCTION` | Full verification chain; all audit evidence collected |
| `REGULATED` | Stricter than PRODUCTION; compliance evidence mapped to SOC2/ISO controls |
| `AUTONOMOUS_LONG_RUN` | Unbounded runtime; used for large self-directed build campaigns |

---

### `OutputMode`

Controls what artifacts the pipeline produces at the end of a mission.

| Value | Description |
|-------|-------------|
| `ANALYZE_ONLY` | Report only; no code output |
| `PLAN_ONLY` | Execution plan only; no code written |
| `PATCH_PROPOSAL` | Proposed diff/patch, not applied |
| `APPLY_PATCH` | Patch proposed and applied |
| `FULL_BUILD` | Complete code output with tests and docs |
| `DEPENDENCY_REDUCTION` | Outputs a dependency-reduced version of the input |
| `RUN_QC` | QC report and compliance artifacts only |
| `FULL_TRANSFORMATION` | Full code output plus transformation audit trail |

---

### `DataClassification`

Mission-level data sensitivity tier. Affects which agents can process the mission, which LLM providers are permitted (`local_only` enforcement in `llm_delegation/`), and which compliance controls are required.

| Value | Tier | Description |
|-------|------|-------------|
| `TIER_0_PUBLIC` | 0 | Public data; no restrictions |
| `TIER_1_INTERNAL` | 1 | Internal use only |
| `TIER_2_SENSITIVE` | 2 | Sensitive; restricted provider routing |
| `TIER_3_REGULATED` | 3 | Regulated data; local-only LLM enforcement |

---

### `MissionState`

The complete set of states a mission can occupy. States are grouped by which flow engine activates them.

#### V1 States (`V1_STATES`)

| State | Description |
|-------|-------------|
| `INTAKE` | Mission received by the API; pre-validation |
| `QUEUED` | Validated and waiting for an engine to pick it up |
| `GATING` | Pre-execution quality gate check |
| `RUNNING` | Active code execution by pod workers |
| `FUSION` | Output fusion and reconciliation across pod workers |
| `VERIFIED` | Audit and equivalence verification complete |
| `COMPLETE` | Mission fully delivered; terminal state |
| `FAILED` | Terminal failure; no further transitions |

#### V2-Only States (`V2_STATES`, requires `MISSION_FLOW_V2_ENABLED=true`)

| State | Description |
|-------|-------------|
| `PM_INTAKE` | PM Agent (AGENT-01) processing natural language intent |
| `FETCH` | IS Agent (Phase 8) preloading Knowledge Lake bootstrap docs for required languages |
| `CEO_DELEGATED` | CEO Agent has evaluated and delegated to a pod manager |
| `POD_ASSIGNED` | A specific pod has been assigned to the mission |
| `SPECIALIST_ASSIGNED` | A language specialist within the pod has been assigned |
| `CLARIFYING` | Pipeline paused; PM Agent is awaiting operator clarification input |

> **Note:** `CLARIFYING` is the only state with a backward edge — it transitions back to `PM_INTAKE` after the operator submits a `MissionClarifyRequest`. All other states are forward-only except `FAILED`.

---

### `VALID_TRANSITIONS`

The complete state machine transition table. The runtime enforces this at every state-change call — any transition not in this map raises an error.

```
INTAKE → QUEUED
QUEUED → PM_INTAKE | GATING | RUNNING | FAILED

# V2 routing chain
PM_INTAKE   → FETCH | CEO_DELEGATED | CLARIFYING | FAILED
CLARIFYING  → PM_INTAKE | FETCH | FAILED          ← only backward edge
FETCH       → CEO_DELEGATED | FAILED
CEO_DELEGATED → POD_ASSIGNED | FAILED
POD_ASSIGNED  → SPECIALIST_ASSIGNED | FAILED
SPECIALIST_ASSIGNED → RUNNING | FAILED

# Shared execution path
GATING  → RUNNING | FUSION | FAILED
RUNNING → GATING | FUSION | VERIFIED | FAILED
FUSION  → VERIFIED | FAILED
VERIFIED → COMPLETE | FAILED

# Terminals
COMPLETE → (none)
FAILED   → (none)
```

---

### `EventType`

A `Literal` type union of all valid strings that can appear as `event_type` on a `MissionEvent`. Used for static type checking and as the canonical event catalogue for the audit trail.

Events are grouped into four categories:

**State-transition events** — one per `MissionState` value, e.g. `MISSION_PM_INTAKE`, `MISSION_RUNNING`, `MISSION_COMPLETE`

**Delegation / planning events:**

| Event | Trigger |
|-------|--------|
| `MISSION_POD_MANAGER_ASSIGNED` | CEO assigns a pod manager |
| `MISSION_SPECIALIST_PLANNED` | Pod manager selects a language specialist |
| `MISSION_SCALING_DECIDED` | Scaling decision made for the mission |
| `MISSION_AIM_GENERATED` | Application Intelligence Map produced |

**Operational / lifecycle events:**

| Event | Trigger |
|-------|--------|
| `MISSION_LOGICNODE_WRITTEN` | A LogicNode batch written to storage |
| `MISSION_COMPLETION_BLOCKED` | Completion gate check failed |
| `MISSION_DELIVERED` | Final delivery confirmed |

**Intelligence-layer agent events (Sprint 2):**

| Event | Emitting Agent |
|-------|---------------|
| `MISSION_CLARIFICATION_RECEIVED` | PM Agent |
| `MISSION_CLARIFICATION_APPLIED` | PM Agent |
| `MISSION_POD_AUDIT_COMPLETE` | Pod Audit agents |
| `MISSION_SECURITY_ANALYSIS_COMPLETE` | SECURITY agent |
| `MISSION_VC_COMMIT_STRATEGY_READY` | Version Control agent |
| `MISSION_INTEGRATION_TESTS_GENERATED` | TESTER agent |
| `MISSION_DEPLOY_READINESS_ASSESSED` | DEPLOY agent |
| `MISSION_POD_GROUP_STANDARD_PRODUCED` | Pod audit agents |
| `MISSION_BUILD_ARTIFACT_WRITTEN` | Pod workers |
| `MISSION_DEPABS_EXECUTED` | DEPABS agent |
| `MISSION_RUNTIME_QC_COMPLETE` | RQCA agent |
| `MISSION_EQUIVALENCE_VERIFIED` | Equivalence Verifier |
| `MISSION_SECURITY_COMPLIANCE_PASSED` | COMPLIANCE agent |
| `MISSION_SECURITY_COMPLIANCE_WARNED` | COMPLIANCE agent |
| `MISSION_TESTDATA_MANIFEST_READY` | Test Data agent |
| `AGENT_STATE_CHANGED` | Orchestrator heartbeat loop |

---

## Database & Storage Models

These models represent records as they exist in PostgreSQL. They are produced by the `storage_*.py` modules and consumed by routes and runtime.

### `MissionAttachment`

A reference to a file stored in object storage that was submitted as mission context (PRD, spec, legacy source file, etc.).

| Field | Type | Description |
|-------|------|-------------|
| `file_id` | `str` | Unique identifier for the attachment |
| `filename` | `str` | Original filename |
| `content_type` | `str` | MIME type |
| `size_bytes` | `int` | File size; defaults to `0` |
| `purpose` | `str \| None` | One of: `reference`, `PRD`, `spec`, `legacy_source` |
| `created_at` | `datetime` | Upload timestamp |
| `object_key` | `str \| None` | Explicit object-storage key for the raw bytes |
| `content` | `str \| None` | Extracted document text; populated during intake processing |

---

### `MissionRecord`

The canonical in-memory representation of a mission record. Returned by `storage.fetch_mission()` and passed through the runtime and lifecycle modules.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mission_id` | `str` | ✅ | Unique mission identifier (caller-assigned) |
| `prompt` | `str` | ✅ | Original natural language mission prompt |
| `state` | `MissionState` | ✅ | Current state machine state |
| `created_at` | `datetime` | ✅ | Mission creation timestamp |
| `requested_target_language` | `str \| None` | — | Target programming language (e.g. `python`, `go`) |
| `mission_type` | `MissionType \| None` | — | Mission classification |
| `depth_mode` | `DepthMode \| None` | — | Execution depth |
| `output_mode` | `OutputMode \| None` | — | Output artifact mode |
| `data_classification` | `DataClassification \| None` | — | Data sensitivity tier |
| `attachments` | `list[MissionAttachment]` | — | Attached context files |
| `risk_assessment` | `dict \| None` | — | Risk evaluation produced during PM intake |
| `global_style_directives` | `list[str]` | — | Operator-supplied style/constraint directives |
| `metadata` | `dict` | — | Freeform key-value store for agent-written context |
| `project_id` | `str \| None` | — | Optional project namespace grouping |

---

### `MissionEvent`

A single state-transition record written to the `mission_events` PostgreSQL table and emitted on the Redis state stream.

| Field | Type | Description |
|-------|------|-------------|
| `mission_id` | `str` | Parent mission |
| `previous_state` | `MissionState \| None` | State before the transition; `None` for the initial INTAKE event |
| `new_state` | `MissionState` | State after the transition |
| `event_type` | `EventType` | Event type string from the catalogue above |
| `ts` | `datetime` | Transition timestamp |

---

### `AgentActionEventRecord`

The immutable audit ledger record for a single agent action. Forms the chain-of-custody evidence bundle. Records are append-only — never updated.

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | `str` | Unique event identifier (UUID) |
| `project_id` | `str` | Project namespace |
| `mission_id` | `str` | Parent mission |
| `agent_id` | `str` | Agent that performed the action |
| `service_name` | `str` | Service that emitted the event |
| `event_type` | `str` | Action classification string |
| `status` | `str` | `SUCCESS`, `FAILURE`, `WARNING`, etc. |
| `object_type` | `str \| None` | Type of object acted upon (e.g. `logicnode`, `artifact`) |
| `object_id` | `str \| None` | ID of object acted upon |
| `tool_name` | `str \| None` | Tool or method invoked |
| `trace_id` | `str \| None` | OpenTelemetry trace ID |
| `span_id` | `str \| None` | OpenTelemetry span ID |
| `correlation_id` | `str \| None` | Request correlation ID |
| `parent_event_id` | `str \| None` | Parent event for causal chaining |
| `started_at` | `datetime` | Action start time |
| `ended_at` | `datetime \| None` | Action end time |
| `duration_ms` | `int \| None` | Computed duration in milliseconds |
| `payload_summary` | `dict` | Non-sensitive summary of the action payload |
| `content_sha256` | `str \| None` | SHA-256 of content acted upon |
| `blob_ref` | `str \| None` | Reference to full payload in object storage |
| `prev_event_digest_sha256` | `str \| None` | Digest of the previous event in chain — enables tamper detection |
| `event_digest_sha256` | `str` | SHA-256 of this event's canonical JSON representation |
| `created_at` | `datetime` | Record creation timestamp |

> **Chain integrity:** `prev_event_digest_sha256` links each record to the previous one, forming a hash chain. Any tampering with a historical record breaks all subsequent digests.

---

### `ReviewApprovalUpsert`

Request body for submitting a human-review approval decision.

| Field | Validation |
|-------|----------|
| `scope` | `"builder"` or `"repo"` |
| `fingerprint` | `min_length=12`, `max_length=200` |
| `summary` | `min_length=3`, `max_length=400` |
| `approved_at` | Optional |
| `expires_at` | Optional |
| `hmac_digest` | Optional; `min_length=16`, `max_length=128` |
| `metadata` | Freeform |

---

## API Request / Response Models

These models validate inbound API request bodies and shape outbound response payloads.

### `MissionCreate`

Request body for `POST /missions`. The caller supplies a `mission_id` — the orchestrator does not auto-generate IDs.

| Field | Validation | Notes |
|-------|-----------|-------|
| `mission_id` | `min_length=1` | Caller-assigned; must be unique |
| `prompt` | `min_length=3` | Natural language mission description |
| `requested_target_language` | Optional | Normalized to lowercase by `normalize_language()` |
| `mission_type` | Optional `MissionType` | Defaults resolved by PM Agent if omitted |
| `depth_mode` | Optional `DepthMode` | Defaults to `STANDARD` if omitted |
| `output_mode` | Optional `OutputMode` | Defaults to `FULL_BUILD` if omitted |
| `data_classification` | Optional `DataClassification` | Affects LLM provider routing |
| `attachments` | `list[MissionAttachment]` | Up to N files uploaded via Gateway |
| `global_style_directives` | `list[str]` | Operator constraints applied to all agents |
| `metadata` | `dict` | Freeform operator-supplied context |
| `project_id` | Optional | Groups missions into a project namespace |
| `created_at` | Optional `datetime` | If omitted, set to `datetime.utcnow()` at write time |

---

### `MissionStateUpdate`

Request body for `PATCH /missions/{mission_id}/state`. Enforces the `VALID_TRANSITIONS` table.

| Field | Description |
|-------|-------------|
| `new_state` | Target state to transition to |
| `expected_state` | If provided, the transition is rejected unless the current state matches — prevents lost-update races |

---

### `MissionClarifyRequest`

Request body for `POST /missions/{mission_id}/clarify`. Resolves a mission stuck in `CLARIFYING` state by supplying operator clarification text. The text is stored in `metadata["pm_clarification"]` and the mission transitions back to `PM_INTAKE`.

| Field | Validation |
|-------|----------|
| `clarification` | `min_length=3`, `max_length=2000` |

---

### `PodAssignmentUpsert`

Internal request body (worker → orchestrator) for recording a pod assignment decision.

| Field | Validation |
|-------|----------|
| `mission_id` | `min_length=1` |
| `pod_name` | `min_length=1` — one of `Pod A`, `Pod B`, `Pod C`, `Pod D` |
| `metadata` | Freeform assignment metadata |
| `assigned_at` | Optional; set to `utcnow()` at write time if omitted |

---

### `LogicNodeUpsert`

Internal request body for writing a LogicNode — a tagged semantic concept extracted from mission analysis (e.g. `DYN-006-001` async function with confidence score and source line).

| Field | Validation |
|-------|----------|
| `mission_id` | `min_length=1` |
| `node_id` | `min_length=1` — e.g. `DYN-006-001` |
| `node` | Full LogicNode payload dict |
| `created_at` | Optional |

---

### `KnowledgeUpsert`

Internal request body for writing a Knowledge Lake entry.

| Field | Validation |
|-------|----------|
| `mission_id` | `min_length=1` |
| `knowledge_id` | `min_length=1` |
| `content` | Knowledge content dict |
| `created_at` | Optional |

---

### `AuditReportUpsert`

Internal request body for writing an audit report record.

| Field | Validation |
|-------|----------|
| `mission_id` | `min_length=1` |
| `audit_id` | `min_length=1` |
| `status` | `min_length=1` — e.g. `PASS`, `WARN`, `FAIL` |
| `report` | Full audit report dict |
| `created_at` | Optional |

---

### `AgentActionEventUpsert`

Inbound payload from workers writing to the audit ledger. Validated and converted to `AgentActionEventRecord` by the storage layer, which computes `event_digest_sha256` and `prev_event_digest_sha256`.

Key fields beyond the shared set in `AgentActionEventRecord`:

| Field | Notes |
|-------|-------|
| `event_id` | Optional; storage generates a UUID if absent |
| `content_sha256` | SHA-256 of the content acted upon; required for artifact events |
| `blob_ref` | Object storage reference for full payload when `payload_summary` is insufficient |

---

### `AgentHeartbeatUpsert`

Inbound heartbeat payload from pod workers. Written to the `agent_heartbeats` PostgreSQL table and triggers a Redis state stream event.

| Field | Validation | Description |
|-------|-----------|-------------|
| `agent_id` | `min_length=1` | Agent identifier (e.g. `AGENT-14-PYTHON`) |
| `state` | `min_length=1` | Agent state string (e.g. `ACTIVE`, `IDLE`, `ERROR`) |
| `queue_depth` | `ge=0` | Number of missions currently in this agent's queue |
| `workload_pct` | `ge=0, le=100` | Estimated workload percentage (0–100) |
| `active_mission_ids` | `list[str]` | Up to 25 mission IDs currently being worked |
| `metadata` | `dict` | Agent-supplied metadata (tier, pod, role, source) |
| `last_heartbeat` | Optional `datetime` | Defaults to `utcnow()` at write time if omitted |

---

## Design Rules

- **Never import from domain modules into `models.py`** — circular imports. `models.py` has zero dependencies on any other orchestrator module.
- **Enum values are the stored strings** — all enums extend `str, Enum` so `.value` is the exact string stored in PostgreSQL and emitted on the protocol bus.
- **`VALID_TRANSITIONS` is enforced at the storage layer** — `storage_missions.update_mission_state()` validates every transition against this map before the SQL write.
- **Charter fields are stored in `metadata_json`** — `MissionType`, `DepthMode`, `OutputMode`, and `DataClassification` are embedded as `__key__` entries in `metadata_json`, not as dedicated columns. See `SCHEMA_REGISTRY_AND_VERSIONING.md` for rationale.
- **`CLARIFYING` is the only backward edge** — all other non-terminal transitions are strictly forward.
