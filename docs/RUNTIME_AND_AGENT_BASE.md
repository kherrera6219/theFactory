# Runtime Engine and Agent Base Class Reference

Document version: 2026.06.13
Last updated: 2026-06-27
Audience: Developers and operators

**Version:** 2026.06.11  
**Code files:** `services/orchestrator/orchestrator/runtime.py` (27 KB) and `services/orchestrator/orchestrator/agent_base.py` (30 KB)  
**Status:** Production — shipped in every deployment

---

## Overview

These two files form the execution backbone of every mission in theFactory.

- **`runtime.py`** is the orchestrator's event engine. It owns the Redis Streams intake consumer loop, the lifecycle task scheduler, state-event emission, stale-consumer reaping, and the self-heal loop that keeps all of the above continuously alive.
- **`agent_base.py`** is the class hierarchy every one of the 41 registered agents inherits from. It defines the three-method lifecycle contract (`execute`, `validate`, `report`), the three result types those methods return, the six category subclasses, the nineteen language-specialist concrete classes, and the `make_agent()` factory function.

Neither file should be modified independently — changes to `runtime.py` must be cross-checked against `lifecycle_interface.py` and `mission_flow_v2/`, and changes to `agent_base.py` must be cross-checked against `agent_registry.py` and `agent_personas.py`.

---

## Part 1 — `runtime.py`: The Execution Engine

### Responsibilities

| Responsibility | Function | Notes |
|---|---|---|
| Intake consumer loop | `consume_intake_stream()` | Reads from `factory:intake` Redis Stream |
| Lifecycle task scheduling | `start_lifecycle_task()` | One `asyncio.Task` per active mission |
| Mission lifecycle advancement | `advance_mission_lifecycle()` | Delegates to `lifecycle_interface.get_lifecycle_engine()` |
| State event emission | `emit_state_event()` | Publishes to `factory:state` Redis Stream |
| Chain event backfill | `_prepare_mission_chain_for_running()` | Fills missing PM→CEO→Pod→Specialist events on recovery |
| Completion artifact check | `_completion_artifacts_ready()` | Validates LogicNodes + build artifacts exist before COMPLETE |
| Build artifact generation | `_ensure_verified_build_artifact()` | Produces a verified source-bundle artifact if required |
| Running-phase checkpoints | `_emit_running_phase_checkpoints()` | Emits `MISSION_GATING` + `MISSION_FUSION` inside RUNNING state |
| Consumer group bootstrap | `ensure_consumer_group()` | Creates `factory:intake` consumer group on startup |
| Stale consumer reaping | `reap_stale_consumers()` / `stale_consumer_reap_loop()` | XAUTOCLAIM then XGROUP DELCONSUMER for idle consumers |
| Runtime health | `ensure_runtime_ready()` | Ping Redis, ensure DB schema, start consumer task |
| Self-heal loop | `runtime_self_heal_loop()` | Calls `ensure_runtime_ready()` every 2 seconds |

---

### The Intake Consumer Loop

`consume_intake_stream()` runs as a persistent `asyncio.Task` stored at `app.state.consumer_task`. It reads up to 20 messages at a time from the `factory:intake` Redis Stream using `XREADGROUP` with a 5-second block timeout.

**Per-message processing:**

```
XREADGROUP →
  1. Parse payload JSON
  2. Validate envelope via EnvelopeValidator.parse_intake_envelope()
  3. Check for duplicate: storage.fetch_mission() — skip if already known
  4. Create MissionRecord(state=queued)
  5. storage.upsert_mission() + insert_mission_event(MISSION_QUEUED)
  6. emit_state_event(MISSION_QUEUED) — non-blocking, failures are warned not raised
  7. start_lifecycle_task(mission_id)
  8. XACK — always, even on validation failure
```

**Invalid messages** (JSON decode error, Pydantic ValidationError, ProtocolValidationError, missing keys) are written to the Dead Letter Queue (`factory:dlq:intake`) via `_write_intake_dlq()` and then ACKed. They are never retried automatically.

**Consumer group recovery:** If the consumer group is missing at runtime (e.g. Redis restart), a `BUSYGROUP`-safe `XGROUP CREATE` is issued and the loop continues.

---

### Lifecycle Task Scheduling

`start_lifecycle_task(app, mission_id)` creates one `asyncio.Task` per mission via `asyncio.create_task(advance_mission_lifecycle(...))`. Key rules:

- Only one task per `mission_id` at a time. If the task exists and is not done, a new one is not created.
- The task registers a `done_callback` that removes it from `app.state.lifecycle_tasks` on completion.
- Tasks are only created when `settings.auto_transition_enabled` is `True`.

`advance_mission_lifecycle()` sets two `contextvars` context tokens (`current_mission_id`, `current_settings`) before calling into the lifecycle engine. This makes mission context available to the `llm_delegation` layer without threading it through every call frame. The tokens are reset in a `finally` block regardless of outcome.

---

### State Event Emission

`emit_state_event()` publishes a structured message to the `factory:state` Redis Stream. Every message includes:

- An `envelope` field (JSON) produced by `EnvelopeValidator.build_state_envelope()`
- A `payload` field (JSON) with `mission_id`, `state`, `event_type`, `requested_target_language`, `created_at`
- Agent routing fields: `agent_id`, `selected_agent_id`, `target_agent_id`, `assigned_pod_manager_agent_id`, `assigned_specialist_agent_id` — populated by `_state_event_agent_routing()`
- Legacy flat fields (`event_type`, `mission_id`, `state`, `created_at`) for backwards compatibility with consumers that read raw stream fields

The stream is trimmed to `settings.max_stream_len` entries (approximate) on every write.

**Agent routing table** (used by `_state_event_agent_routing()`):

| Event Type | Routed To |
|---|---|
| `MISSION_PM_INTAKE` | PM Agent (`AGENT-01-PM`) |
| `MISSION_CEO_DELEGATED`, `MISSION_COMPLETION_BLOCKED` | CEO Agent (`AGENT-02-CEO`) |
| `MISSION_POD_MANAGER_ASSIGNED` | Pod Manager for the mission's language |
| `MISSION_SPECIALIST_ASSIGNED`, `MISSION_RUNNING`, `MISSION_GATING`, `MISSION_FUSION`, `MISSION_VERIFIED`, `MISSION_COMPLETE`, `MISSION_FAILED` | Language Specialist Agent |

---

### Stale Consumer Reaping

Each orchestrator restart registers a new hostname-derived consumer name in Redis. Old names accumulate with pending entries, creating a growing Pending Entries List (PEL). The reaper cleans this up:

1. `XINFO CONSUMERS` — list all consumers in the group
2. For each consumer idle > `settings.stale_consumer_idle_ms` (and not the current consumer):
   - If it has pending entries: `XAUTOCLAIM` to transfer them to the live consumer
   - `XGROUP DELCONSUMER` to remove the stale entry
3. Runs at startup (inside `ensure_runtime_ready()`) and then on a loop via `stale_consumer_reap_loop()` every `settings.stale_consumer_reap_interval_seconds`

DLQ streams (`factory:dlq:*`) are intentionally excluded — they are unidirectional write-only streams with no consumer groups to reap.

---

### Runtime Self-Heal Loop

`runtime_self_heal_loop()` calls `ensure_runtime_ready()` every 2 seconds. `ensure_runtime_ready()` does the following on each call under an async lock:

1. Lazily creates a Redis connection if none exists
2. Pings Redis and sets `app.state.redis_ready`
3. Calls `storage.ensure_db_schema()` if DB is not yet ready, sets `app.state.db_ready`
4. If all conditions are met (`protocol_ready AND redis_ready AND db_ready`) and no consumer task is running, bootstraps the consumer group and spawns `consume_intake_stream()`

This means the system self-recovers from Redis restarts, DB restarts, and container startup races without operator intervention.

---

### Chain Event Backfill

`_prepare_mission_chain_for_running()` is called during lifecycle recovery to patch missions that entered the RUNNING state before their PM → CEO → Pod → Specialist chain events were recorded. It checks the `chain_trace` list in mission metadata and appends any missing events:

- `MISSION_PM_INTAKE`
- `MISSION_CEO_DELEGATED`
- `MISSION_POD_MANAGER_ASSIGNED`
- `MISSION_SPECIALIST_ASSIGNED`

Each backfilled event is persisted to the `mission_events` table and emitted to the state stream.

---

### Completion Gating

`_completion_artifacts_ready()` is the gate before a mission advances to `MISSION_COMPLETE`. It returns `(ready: bool, evidence: dict)` and checks:

1. **Policy exempt?** — some missions opt out via metadata flag `completion_policy_exempt`
2. **Pod assignment** — `storage.get_pod_assignment()` must return a record
3. **LogicNodes** — `storage.list_logicnodes()` must return at least one node
4. **Fallback** — for single-orchestrator deployments, checks metadata JSON fields (`assigned_pod_manager_agent_id`, `master_logic_stream`, `MISSION_LOGIC_FOLDED` chain event) if the normalized tables are empty
5. **Build artifact** — if `mission_requires_build_artifact()` is true, a successful build artifact must also exist

The returned `evidence` dict is embedded in the mission metadata for audit.

---

## Part 2 — `agent_base.py`: The Agent Class Hierarchy

### Result Types

All three lifecycle methods return structured, serializable result objects. Every field is accessible as a plain Python attribute and via `.to_dict()`.

#### `AgentResult`

Returned by `execute()`. Represents the outcome of an agent's primary task.

| Field | Type | Description |
|---|---|---|
| `agent_id` | `str` | The agent that produced this result |
| `mission_id` | `str` | The mission this result belongs to |
| `status` | `str` | `"ok"` \| `"partial"` \| `"failed"` |
| `artifacts` | `list[dict]` | Produced artifacts (LogicNodes, plans, etc.) |
| `metadata` | `dict` | Supplementary execution metadata |
| `errors` | `list[str]` | Error messages if status is not `"ok"` |

#### `ValidationResult`

Returned by `validate()`. Represents artifact quality verification.

| Field | Type | Description |
|---|---|---|
| `agent_id` | `str` | The agent that performed validation |
| `mission_id` | `str` | The mission being validated |
| `passed` | `bool` | Whether all checks passed |
| `findings` | `list[str]` | Human-readable validation finding messages |
| `blocking` | `bool` | Whether failures should block mission advancement |

#### `AgentReport`

Returned by `report()`. The audit-ready evidence record for an agent's contribution.

| Field | Type | Description |
|---|---|---|
| `agent_id` | `str` | The reporting agent |
| `mission_id` | `str` | The mission this report covers |
| `summary` | `str` | Human-readable summary of what happened |
| `evidence` | `list[dict]` | List of `AgentResult.to_dict()` and `ValidationResult.to_dict()` |
| `verdict` | `str` | `"PASS"` \| `"FAIL"` \| `"PARTIAL"` |

---

### BaseAgent Abstract Class

`BaseAgent` is the abstract root of the hierarchy. It must not be instantiated directly.

**Constructor:** `BaseAgent(definition: AgentDefinition)` — stores the immutable definition and creates a per-agent logger at `agent_base.<agent_id>`.

**Read-only identity properties:**

| Property | Source | Example |
|---|---|---|
| `.definition` | `AgentDefinition` dataclass | Full config record |
| `.agent_id` | `definition.agent_id` | `"AGENT-05-PYTHON"` |
| `.category` | `definition.category` | `"specialist"` |
| `.pod` | `definition.pod` | `"POD-A"` |
| `.tier` | `definition.tier` | `"specialist"` |

**`.capabilities()` → `dict`** — returns a summary of the agent's identity and specialties. Used by the registry for capability queries.

**Abstract lifecycle methods (must override):**

```python
def execute(self, mission_id: str, payload: dict) -> AgentResult: ...
def validate(self, mission_id: str, artifacts: list[dict]) -> ValidationResult: ...
def report(self, mission_id: str, result: AgentResult, validation: ValidationResult) -> AgentReport: ...
```

**Protected builder helpers** (call in subclass implementations):

```python
self._make_result(mission_id, *, status, artifacts, metadata, errors) -> AgentResult
self._make_validation(mission_id, *, passed, findings, blocking) -> ValidationResult
self._make_report(mission_id, *, summary, evidence, verdict) -> AgentReport
```

These helpers automatically inject `self.agent_id` and `mission_id` into every result object, so subclasses do not need to repeat them.

---

### The Six Category Subclasses

```
BaseAgent
├── InterfaceAgent        PM — mission intake and delivery validation
├── ExecutiveAgent        CEO — cross-pod orchestration and delegation
├── SupportAgent          Support ring (12 agents)
├── PodManagerAgent       Pod sub-managers (4 agents)
├── PodAuditAgent         Pod QC/Audit agents (4 agents)
└── SpecialistAgent       Language specialists (19 agents)
```

#### `InterfaceAgent` (PM)
Produces an `intake_contract` artifact containing the full mission payload. Validation checks that `mission_id` is present on every artifact. Report summarizes the artifact count and validation outcome.

#### `ExecutiveAgent` (CEO)
Produces a `delegation_plan` artifact with `pod_manager_agent_id`, `specialist_agent_id`, and `rationale`. Validation is **blocking** — a delegation plan with missing routing IDs returns `blocking=True` and fails the mission.

#### `SupportAgent`
Covers 12 support agents: BROKER, ACCOUNTANT, SECURITY, IS, VC, COMPLIANCE, HW, TESTER, DEPLOY, DEPABS, TESTDATA, RQCA. Produces a generic `support_action` artifact tagged with the agent's `role` from its `AgentDefinition`.

#### `PodManagerAgent`
Produces a `pod_fusion_plan` artifact containing the pod identifier, source language, and specialist agent ID. Validation is non-blocking — a missing `specialist_agent_id` is recorded as a finding but does not set `blocking=True`.

#### `PodAuditAgent`
Audits LogicNode artifacts passed in `payload["logicnodes"]`. Each node is checked for a `node_id` field. Produces a `pod_audit_verdict` artifact. Validation is **blocking** — a FAIL verdict sets `blocking=True`.

#### `SpecialistAgent`
The most complex category. See the Specialist Agent section below.

---

### Specialist Agents

`SpecialistAgent` handles the LogicNode extraction lifecycle for all 19 language specialists. Subclasses set two class attributes:

- `language_key: str` — the language identifier (e.g. `"python"`, `"rust"`)
- `extraction_guidance: str` — language-specific note embedded in reports

**`execute()` flow:**

1. Checks `payload["logicnodes"]` — if pre-built LogicNodes are provided (e.g. from pod-worker), they are used directly without re-extraction
2. Otherwise calls `_extract_logicnodes(mission_id, source_payload, language)`
3. Returns a `logicnode_set` artifact containing the count and node list

**`validate()` checks:**
- At least one LogicNode was extracted
- Every node is a `dict` with both `node_id` and `concept` fields

**`_extract_logicnodes()` — the inline fallback extractor:**

When the pod-worker has not pre-populated LogicNodes, `SpecialistAgent` uses a regex-based inline extractor. It searches for three pattern domains:

| Domain | Pattern | Matches |
|---|---|---|
| `function` | `\b(?:def\|function\|fn\|func)\s+(name)` | Function/method definitions |
| `class` | `\b(?:class\|struct\|enum\|interface)\s+(name)` | Type definitions |
| `module_dependency` | `\b(?:import\|from\|using\|require)\s+(name)` | Import statements |

Nodes are deduplicated by `(domain, concept.lower())`. The extractor caps at 20 nodes. If no patterns match, it produces a single fallback `source_behavior` node describing the full payload.

Each node has the structure:
```json
{
  "node_id": "<mission_id>:<language>:<index>",
  "domain": "function | class | module_dependency | source_behavior",
  "concept": "<matched name>",
  "intent": "Preserve <domain> behavior for <concept>.",
  "language": "<language>",
  "source": "specialist_agent",
  "agent_id": "<agent_id>"
}
```

**The 19 Language Specialist Classes:**

| Class | Language Key | Pod | Extraction Guidance Summary |
|---|---|---|---|
| `PythonAgent` | `python` | A | PEP 8, typing, packaging |
| `JavaScriptAgent` | `javascript` | A | ECMAScript/TypeScript async safety |
| `RubyAgent` | `ruby` | A | Object model, Rails conventions |
| `PhpAgent` | `php` | A | Modern PHP, framework-safe patterns |
| `CAgent` | `c` | B | Deterministic memory, low-level systems |
| `CppAgent` | `cpp` | B | RAII, template hygiene, safe abstractions |
| `RustAgent` | `rust` | B | Ownership correctness, lifetime safety |
| `ZigAgent` | `zig` | B | Explicit allocation, compile-time behavior |
| `GoAgent` | `go` | B | Goroutine/channel safety, idiomatic simplicity |
| `JavaAgent` | `java` | C | JVM patterns, enterprise reliability |
| `CSharpAgent` | `csharp` | C | .NET architecture, async correctness |
| `ScalaAgent` | `scala` | C | Functional-object hybrid, type-level correctness |
| `KotlinAgent` | `kotlin` | C | Null safety, coroutine concurrency |
| `HaskellAgent` | `haskell` | C | Purely functional, lazy evaluation, type-class rigor |
| `OcamlAgent` | `ocaml` | C | Strong static inference, module system |
| `MatlabAgent` | `matlab` | D | Numerical stability, matrix-oriented workflows |
| `RAgent` | `r` | D | Statistical reproducibility, analytical model integrity |
| `JuliaAgent` | `julia` | D | High-performance numerical kernels, multiple dispatch |
| `MathematicaAgent` | `mathematica` | D | Symbolic computation, formal expression handling |

---

### The `make_agent()` Factory

`make_agent(agent_id: str) -> BaseAgent` is the canonical way to instantiate an agent. It resolves the correct class in two steps:

1. Look up the `AgentDefinition` in `_AGENT_ID_TO_DEFINITION` (pre-built from `AGENT_REGISTRY` at import time)
2. For `category == "specialist"`: resolve the language-specific class from `_SPECIALIST_BY_LANGUAGE` using `definition.specialties[0]`; fall back to `SpecialistAgent` if no class is registered
3. For all other categories: resolve from `_CATEGORY_CLASS` by category string

Raises `ValueError` if `agent_id` is not in the registry.

`make_specialist_for_language(language: str) -> SpecialistAgent | None` is a secondary factory that finds the first `AgentDefinition` in the registry matching the language specialty. Returns `None` if no specialist is registered for that language.

---

## Integration Map

| Consumer | Uses from `runtime.py` | Uses from `agent_base.py` |
|---|---|---|
| `main.py` | `ensure_runtime_ready()`, `runtime_self_heal_loop()`, `start_lifecycle_task()`, `emit_state_event()` | — |
| `lifecycle_interface.py` | `_prepare_mission_chain_for_running()`, `_completion_artifacts_ready()`, `_ensure_verified_build_artifact()` | — |
| `mission_flow.py` / `mission_flow_v2/` | `emit_state_event()` | `make_agent()` |
| `agent_registry.py` | — | `AgentResult`, `ValidationResult`, `AgentReport`, `BaseAgent` |
| `pod-worker` service | — | `make_agent()`, `make_specialist_for_language()` |
| `audit_events.py` | — | `AgentReport.to_dict()` |
| `rqca_agent.py` | — | `SupportAgent` (subclass) |

---

## Adding a New Agent

1. **Register it in `agent_registry.py`** — add an `AgentDefinition` with a unique `agent_id`, correct `category`, `pod`, `tier`, and `specialties`
2. **Add a persona in `agent_personas.py`** — full persona dataclass required
3. **Choose the base class:**
   - New language specialist → subclass `SpecialistAgent`, set `language_key` and `extraction_guidance`, add to `_SPECIALIST_BY_LANGUAGE`
   - New support agent → subclass `SupportAgent`, override `execute()` with domain-specific logic
   - New category → subclass `BaseAgent` directly, implement all three abstract methods, add to `_CATEGORY_CLASS`
4. **Add to `make_agent()` routing** if a new category was introduced
5. **Write tests** — `tests/unit/test_agent_base.py` covers the full lifecycle contract

---

## Common Failure Modes

| Symptom | Root Cause in These Files | Resolution |
|---|---|---|
| Mission stuck in `queued` forever | `auto_transition_enabled=False` or `start_lifecycle_task()` not called | Check settings; verify `consumer_task` is running via `/health` |
| `ValueError: Unknown agent_id` | `agent_id` not in `AGENT_REGISTRY` | Add `AgentDefinition` to `agent_registry.py` |
| Missing chain events in audit trace | Recovery path skipped `_prepare_mission_chain_for_running()` | Triggered by advancing a mission to RUNNING without intake flow |
| Stale consumers growing indefinitely | `stale_consumer_reap_loop()` not running | Check `stale_consumer_reap_interval_seconds` setting |
| `logicnode_set` artifact with 0 nodes | Source payload was empty or unparseable | Check `_extract_logicnodes()` — will produce a fallback node if source is non-empty |
| `blocking=True` ValidationResult blocking mission | CEO delegation plan missing routing IDs or Pod Audit FAIL | Inspect `chain_trace` in mission metadata for the blocking agent's report |
