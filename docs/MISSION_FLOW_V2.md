# Mission Flow v2 — Internals Reference

Document version: 2026.06.18
Last updated: 2026-06-18

**Version:** 2026.06.11  
**Code package:** `services/orchestrator/orchestrator/mission_flow_v2/`  
**Status:** Default production engine as of ADR_MISSION_FLOW_V2_STATUS_2026-03-08  
**Audience:** Developers, Architects

---

> **Current implementation note (2026-06-18):** the normal ready path does not emit `MISSION_CLARIFYING`. `MISSION_CLARIFYING` is now reserved for true high-ambiguity PM intake that pauses the mission for operator clarification. A ready mission proceeds `MISSION_PM_INTAKE -> MISSION_FETCH`.

## Overview

Mission Flow v2 (`mission_flow_v2/`) is the default state machine engine that drives every mission from intake to delivery. It replaced the monolithic `mission_flow.py` (v1) and is the engine selected unless `USE_LANGGRAPH_ENGINE=true` is set in the environment, in which case `langgraph_lifecycle.py` is used instead.

The package is split into seven focused modules:

| File | Size | Role |
|---|---|---|
| `__init__.py` | 4.4 KB | Public API — exports `run_mission_flow`, `MissionFlowContext`, engine selector |
| `base.py` | 13.6 KB | `MissionFlowContext` dataclass and all shared helpers used across phase modules |
| `lifecycle.py` | 17.0 KB | Top-level orchestration loop — selects engine, runs phases in sequence, handles recovery |
| `transitions.py` | 3.8 KB | Guard table and `transition()` helper — enforces the valid state machine edges |
| `phases_intake.py` | 29.7 KB | Phases 1–4: INTAKE, CLARIFY, PLAN, DELEGATE |
| `phases_build.py` | 31.0 KB | Phases 5–8: BUILD, VERIFY, AUDIT, ABSORB |
| `phases_runtime.py` | 20.8 KB | Phase 9: RUNTIME — pod worker coordination, LogicNode streaming, equivalence check |
| `phases_delivery.py` | 13.5 KB | Phases 10–11: DELIVER, COMPLETE — artifact assembly, evidence bundle, SSE close |

---

## The MissionFlow V2 State Machine

Ready missions follow the normal MissionFlow V2 path without a clarification hop. Missions pause in CLARIFYING only when PM intake flags true ambiguity; otherwise the persisted transition path proceeds from PM_INTAKE directly to FETCH.

```text
QUEUED -> PM_INTAKE -> FETCH -> CEO_DELEGATED -> POD_ASSIGNED -> SPECIALIST_ASSIGNED -> RUNNING -> GATING -> FUSION -> VERIFIED -> COMPLETE

Optional pause: QUEUED -> CLARIFYING when PM intake flags high ambiguity.
FAILED remains terminal from guard/error paths.
```

### Phase Summary

| # | Phase | Module | What happens |
|---|---|---|---|
| 1 | **INTAKE** | `phases_intake.py` | Validates the raw `MissionCreate` payload; assigns mission ID; extracts language hints; emits `MISSION_ACCEPTED` event |
| 2 | **CLARIFY** | `phases_intake.py` | Optional phase — if PM agent flags ambiguity, pauses and requests clarification from the operator via SSE; resumes when `MissionClarifyRequest` is received |
| 3 | **PLAN** | `phases_intake.py` | PM agent + CEO agent produce a structured execution plan: pod assignment, depth mode, estimated token budget, AIM invocation |
| 4 | **DELEGATE** | `phases_intake.py` | CEO agent delegates to one or more Pod Managers; publishes to the `alpha` stream on the Protocol Bus; sets active pod workers |
| 5 | **BUILD** | `phases_build.py` | Pod workers execute the plan; language extraction runs (232 regex patterns, 20 language keys); LogicNodes are created and streamed back on the `beta` stream |
| 6 | **VERIFY** | `phases_build.py` | Equivalence verifier runs — proves behavioral equivalence between mission intent and produced artifacts; emits verification evidence |
| 7 | **AUDIT** | `phases_build.py` | Audit worker consumes the `sigma` stream; constructs the chain-of-custody evidence bundle; commits audit events |
| 8 | **ABSORB** | `phases_build.py` | DEPABS agent runs dependency absorption — eliminates unnecessary dependencies from the artifact set; re-verifies after absorption |
| 9 | **RUNTIME** | `phases_runtime.py` | RQCA agent performs runtime QC; IS agent runs integration compliance checks; pod workers finalize LogicNode graph |
| 10 | **DELIVER** | `phases_delivery.py` | Assembles final artifact package (code, tests, docs, audit evidence); writes to object store; emits `MISSION_DELIVERED` event via SSE |
| 11 | **COMPLETE** | `phases_delivery.py` | Persists completion metadata; closes SSE stream; updates LLM cost ledger; marks mission `COMPLETE` in the database |

---

## MissionFlowContext

Defined in `base.py`. This is the single shared state object threaded through every phase function. It is constructed once in `lifecycle.py` at the start of a mission and mutated in place.

```python
@dataclass
class MissionFlowContext:
    # Identity
    mission_id: str
    mission_record: MissionRecord

    # Infrastructure handles (injected by lifecycle.py)
    db_pool: asyncpg.Pool
    redis: aioredis.Redis
    object_store: ObjectStore
    qdrant: QdrantStore
    neo4j: Neo4jStore
    milvus: MilvusStore
    llm: DelegationRouter          # from llm_delegation package
    prompt_registry: PromptRegistry

    # Runtime accumulator fields (mutated by phase functions)
    plan: Optional[ExecutionPlan] = None
    assigned_pods: list[str] = field(default_factory=list)
    logicnodes: list[LogicNode] = field(default_factory=list)
    artifacts: list[BuildArtifact] = field(default_factory=list)
    audit_events: list[AuditEvent] = field(default_factory=list)
    verification_result: Optional[VerificationResult] = None
    absorption_result: Optional[AbsorptionResult] = None
    delivery_package: Optional[DeliveryPackage] = None

    # SSE transport
    sse_queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    # Cost tracking
    token_ledger: dict[str, int] = field(default_factory=dict)
```

**Key rules:**
- Phase functions receive `ctx: MissionFlowContext` and must only mutate its accumulator fields, never its identity or infrastructure fields.
- `ctx.sse_queue` is the live transport to the operator. Any phase may push `ServerSentEvent` objects to it; the API Gateway drains and forwards them.
- Infrastructure handles are injected once by `lifecycle.py` at startup and are read-only from phase functions' perspective.

---

## lifecycle.py — The Orchestration Loop

`lifecycle.py` is the top-level coordinator. Its public function `run_mission_flow(ctx)` is called by `runtime.py` and does the following:

1. **Engine selection** — checks `settings.USE_LANGGRAPH_ENGINE`; if true, delegates to `langgraph_lifecycle.py` and returns. Otherwise, continues with v2.
2. **Recovery check** — calls `_check_recovery(ctx)` to see if the mission was already in progress (e.g., after a service restart). If so, rehydrates `ctx` from the database and resumes from the last completed phase rather than re-running from INTAKE.
3. **Phase loop** — calls each phase function in order, passing `ctx`. Each call returns a `PhaseResult(status, next_phase)` or raises `PhaseError`.
4. **Transition enforcement** — after each phase, calls `transitions.transition(current, next)` to assert the edge is valid before proceeding.
5. **Error handling** — any unhandled exception from a phase is caught, the mission is marked `FAILED`, the error is emitted to `ctx.sse_queue`, and the function returns. CLARIFY phase can also pause by returning `PhaseResult(status=WAITING)`, which causes the loop to suspend and register a resume callback.
6. **Completion** — after COMPLETE, `lifecycle.py` drains `ctx.sse_queue` and closes it.

### Recovery Logic

On restart, `lifecycle.py` queries the mission's last persisted `current_phase` from PostgreSQL. It then skips all phases before that checkpoint and resumes from the next unexecuted phase. Each phase is designed to be **idempotent on retry** — if a phase was partially executed before a crash, re-running it from scratch is safe because it checks for pre-existing records (e.g., LogicNodes already written to DB) before creating duplicates.

---

## transitions.py — Guard Table

`transitions.py` defines the complete valid-edge map of the state machine as a `dict[Phase, set[Phase]]`. The `transition(from_phase, to_phase)` helper raises `InvalidTransitionError` if the requested edge is not in the map.

Valid edges (abridged):

```
INTAKE   → {CLARIFY, PLAN}          # PLAN if no ambiguity; CLARIFY if PM flags it
CLARIFY  → {PLAN, FAILED}           # FAILED if operator rejects or timeout
PLAN     → {DELEGATE, FAILED}
DELEGATE → {BUILD, FAILED}
BUILD    → {VERIFY, FAILED}
VERIFY   → {AUDIT, FAILED}
AUDIT    → {ABSORB, FAILED}
ABSORB   → {RUNTIME, FAILED}
RUNTIME  → {DELIVER, FAILED}
DELIVER  → {COMPLETE, FAILED}
COMPLETE → {}                        # terminal
FAILED   → {}                        # terminal
```

The only branching points are INTAKE (CLARIFY vs PLAN) and any phase to FAILED. All other transitions are deterministic.

---

## phases_intake.py — Phases 1–4

### Phase 1: INTAKE

- Validates `MissionRecord` fields (non-empty prompt, valid `MissionType`, `DataClassification` tier check against `security_compliance.py`).
- Generates a deterministic `mission_id` (UUIDv5 of org + timestamp + prompt hash).
- Writes the mission record to PostgreSQL with status `INTAKE`.
- Initializes `ctx.token_ledger`.
- Emits SSE event `{type: "phase", phase: "INTAKE", status: "complete"}`.

### Phase 2: CLARIFY

- Calls `AGENT-01-PM` with the raw mission prompt to get a clarification assessment.
- If confidence ≥ threshold (default 0.85): skips clarification, returns `PhaseResult(PLAN)`.
- If confidence < threshold: emits a `{type: "clarify_request", questions: [...]}` SSE event and returns `PhaseResult(WAITING)`. The loop suspends. When the operator submits a `MissionClarifyRequest`, `lifecycle.py` resumes by injecting the answers into `ctx.mission_record.clarification_responses` and calling this phase again.
- Maximum 2 clarification rounds before proceeding regardless of confidence.

### Phase 3: PLAN

- `AGENT-01-PM` produces a structured `ExecutionPlan`: pod selection, sub-task decomposition, `DepthMode`, token budget, and AIM invocation flag.
- If `plan.requires_aim`, calls `aim_generator.py` to generate the Application Intelligence Map and attaches it to `ctx.plan.aim`.
- Writes the plan to PostgreSQL.
- Emits SSE `{type: "plan", ...plan_summary}`.

### Phase 4: DELEGATE

- `AGENT-02-CEO` reviews the plan and resolves final pod assignment(s).
- Publishes a `DelegateMessage` to the `alpha` Protocol Bus stream for each assigned pod.
- Populates `ctx.assigned_pods`.
- Emits SSE `{type: "delegate", pods: [...]}`.

---

## phases_build.py — Phases 5–8

### Phase 5: BUILD

- Subscribes to the `beta` stream on the Protocol Bus to receive `LogicNode` objects streamed by pod workers as they complete language extraction.
- Concurrently monitors the `omega` stream for worker heartbeats (timeouts handled by `heartbeat_service.py`).
- Accumulates all received `LogicNode` objects into `ctx.logicnodes`.
- Builds and writes `BuildArtifact` records to the object store as workers deliver code, tests, and docs.
- Phase completes when all assigned pods publish a `BUILD_COMPLETE` message on the `delta` stream.

### Phase 6: VERIFY

- Invokes `equivalence_verifier.py` with `ctx.artifacts` and `ctx.mission_record`.
- The verifier produces a `VerificationResult` with a pass/fail flag and supporting evidence.
- On failure: mission moves to FAILED with `verification_result` attached to the failure record for operator review.
- On success: `ctx.verification_result` is set and the evidence is queued for the audit bundle.

### Phase 7: AUDIT

- Publishes all accumulated `AuditEvent` objects to the `sigma` stream.
- The audit worker (external process) consumes the stream and writes the chain-of-custody evidence bundle.
- `phases_build.py` waits for an `AUDIT_COMPLETE` message on the `rho` stream (acknowledgement from the audit worker).
- All LLM call metadata from `ctx.token_ledger` is committed to `llm_cost_ledger.py` here.

### Phase 8: ABSORB

- Passes `ctx.artifacts` to `dependency_absorption.py` (`DEPABS` agent).
- DEPABS scores every dependency across 5 axes (necessity, replaceability, security risk, license risk, bundle weight) and eliminates those below threshold.
- Writes the `AbsorptionResult` (eliminated deps, retained deps, score breakdown) to `ctx.absorption_result`.
- Runs a lightweight re-verification pass to confirm elimination did not break behavioral equivalence.

---

## phases_runtime.py — Phase 9

### Phase 9: RUNTIME

- `RQCA` agent (`rqca_agent.py`) performs runtime QC: static analysis, security pattern scan, test coverage check, and performance budget check.
- `IS` agent (`is_agent.py`) runs integration compliance: checks all external integrations against the integration catalog, verifies compliance with protocol standards.
- Pod workers finalize the LogicNode graph: applies taxonomy tags, computes inter-node edges, writes the complete graph to Neo4j via `neo4j_store.py`.
- Embeddings for all LogicNodes are generated by `knowledge_embeddings.py` and written to Qdrant and Milvus.
- All runtime findings are appended to `ctx.audit_events` for the evidence bundle.

---

## phases_delivery.py — Phases 10–11

### Phase 10: DELIVER

- Assembles the `DeliveryPackage`: code artifacts, test suite, auto-generated documentation, the AIM (if generated), the equivalence verification report, the DEPABS absorption report, and the full audit evidence bundle.
- Writes the package as a versioned archive to the object store.
- Emits a `{type: "delivery", package_url: ..., manifest: {...}}` SSE event — this is the primary operator-facing result.
- Writes the `storage_artifacts` delivery record.

### Phase 11: COMPLETE

- Marks the mission `COMPLETE` in PostgreSQL.
- Closes `ctx.sse_queue` with a terminal `{type: "complete", mission_id: ...}` event.
- Flushes the final LLM cost ledger entry.
- Emits Prometheus metrics: `mission_completed_total`, `mission_duration_seconds`, `mission_logicnodes_extracted_total`.

---

## Engine Selection: v2 vs LangGraph

`lifecycle.py` selects the execution engine at startup based on `settings.USE_LANGGRAPH_ENGINE` (env var `USE_LANGGRAPH_ENGINE`, default `false`).

| Setting | Engine | Notes |
|---|---|---|
| `USE_LANGGRAPH_ENGINE=false` (default) | `mission_flow_v2/` | Deterministic, production-hardened V2 state machine with optional clarification pause |
| `USE_LANGGRAPH_ENGINE=true` | `langgraph_lifecycle.py` | Graph-based, supports non-linear flows, experimental for v1.2.0 |

The LangGraph engine targets feature parity with v2 but has not yet completed the full QA cycle for production workloads. See `docs/LLM_DELEGATION.md` and `ADR_MISSION_FLOW_V2_STATUS_2026-03-08.md` for the promotion timeline.

---

## v1 Legacy (`mission_flow.py`)

`mission_flow.py` (v1) is retained as a fallback for emergency use only. It is a monolithic single-file implementation of a 7-phase flow that predates the pod worker architecture. It is not reachable via normal configuration; activating it requires a code change. It will be removed in v1.3.0.

---

## Related Documentation

| Doc | Topic |
|---|---|
| [ADR_MISSION_FLOW_V2_STATUS_2026-03-08.md](ADR_MISSION_FLOW_V2_STATUS_2026-03-08.md) | ADR promoting v2 to default |
| [ADR_V2_MISSION_FLOW_ADOPTION_DESIGN_2026-03-08.md](ADR_V2_MISSION_FLOW_ADOPTION_DESIGN_2026-03-08.md) | v2 design and adoption rationale |
| [RUNTIME_AND_AGENT_BASE.md](RUNTIME_AND_AGENT_BASE.md) | `runtime.py` — how `run_mission_flow()` is called from the execution engine |
| [EQUIVALENCE_VERIFIER.md](EQUIVALENCE_VERIFIER.md) | Phase 6 VERIFY — deep dive on equivalence verification |
| [DEPENDENCY_ABSORPTION_DOCTRINE.md](DEPENDENCY_ABSORPTION_DOCTRINE.md) | Phase 8 ABSORB — DEPABS doctrine and implementation |
| [LLM_DELEGATION.md](LLM_DELEGATION.md) | LLM routing used by all phase agents |
| [AGENT_PROTOCOL_BUS_DATA_SYSTEMS_PLAN.md](AGENT_PROTOCOL_BUS_DATA_SYSTEMS_PLAN.md) | Protocol Bus streams (alpha/beta/delta/sigma/omega/rho) used throughout the pipeline |
| [MODELS_AND_DOMAIN_SCHEMA.md](MODELS_AND_DOMAIN_SCHEMA.md) | `MissionState`, `VALID_TRANSITIONS`, `MissionRecord`, all Pydantic models |
