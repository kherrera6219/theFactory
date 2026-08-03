# Architecture — theFactory

Document version: 2026.05.30  
Last updated: 2026-05-30  
Status: Canonical  
Audience: Operators, developers, maintainers, and auditors

Companion diagrams: [`ARCHITECTURE_DIAGRAMS.md`](ARCHITECTURE_DIAGRAMS.md)

---

## Table of Contents

- [System Overview](#system-overview)
- [Runtime Topology](#runtime-topology)
- [Service Responsibilities](#service-responsibilities)
- [Mission Lifecycle](#mission-lifecycle)
- [41-Agent Model](#41-agent-model)
- [Language Extraction Engine](#language-extraction-engine)
- [Data Plane](#data-plane)
- [Event Bus Architecture](#event-bus-architecture)
- [LangGraph State Machine](#langgraph-state-machine)
- [Security Architecture](#security-architecture)
- [Observability Architecture](#observability-architecture)
- [Contract Artifacts](#contract-artifacts)
- [Design Decisions (ADRs)](#design-decisions-adrs)

---

## System Overview

theFactory is a **41-agent multi-agent software refinery** built on a microservice architecture. Missions (software build requests) enter through the API Gateway, are delegated through an agent hierarchy, processed by language-specialist pod workers, and completed with audit evidence.

The system is organized into three planes:

| Plane | Components |
|-------|-----------|
| **Control Plane** | API Gateway, Orchestrator, Mission Control UI |
| **Data Plane** | PostgreSQL, Redis, Qdrant, Neo4j, Milvus, MinIO/S3 |
| **Observability Plane** | Prometheus, Grafana, Loki, Promtail, Alertmanager, Jaeger |

---

## Runtime Topology

```
╔══════════════════════════════════════════════════════════════════╗
║                     MISSION CONTROL UI                          ║
║              Next.js 16 · TypeScript · SSE Transport            ║
║ Home · Chat · Missions · Agents · Protocol Bus · Builder/Repo   ║
╚══════════════════════╤═══════════════════════════════════════════╝
                       │ REST + SSE
╔══════════════════════▼═══════════════════════════════════════════╗
║                      API GATEWAY :8100                          ║
║  FastAPI · Auth (api_key|hybrid|oidc) · Rate limiting           ║
║  Idempotency (SHA-256/Redis) · Security headers · OTEL traces   ║
╚══════════╤═══════════════════════════════╤═════════════════════╝
           │ Internal REST                 │ Redis Streams
╔══════════▼═════════════════════════════╗ │
║         ORCHESTRATOR :8101             ║ │
║  FastAPI · LangGraph StateGraph        ║ │
║  Postgres checkpointer (optional)      ║ │
║  41-agent registry + persona profiles  ║ │
║  Qdrant/Milvus/Neo4j/S3 adapter plane  ║ │
║  Operations APIs · OTEL traces         ║ │
╚══════════╤═════════════════════════════╝ │
           │ Redis Streams          ╔══════▼══════════════════════╗
           │                       ║   PROTOCOL BUS MCP :8102    ║
           │                       ║   6-protocol validation      ║
           │                       ║   alpha/beta/delta/           ║
           │                       ║   sigma/omega/rho            ║
           │                       ╚═════════════════════════════╝
╔══════════▼═════════════════════════════════════════════════════╗
║                     POD WORKERS                               ║
║  Pod A · Python / JavaScript / Ruby / PHP                     ║
║  Pod B · C / C++ / Rust / Zig / Go                            ║
║  Pod C · Java / C# / Scala / Kotlin                           ║
║  Pod D · MATLAB / R / Julia / Mathematica / Haskell / OCaml   ║
║  Language extraction → LogicNode creation → KB write         ║
╚══════════════════════════════════════════════════════════════╝
╔══════════════════════════════════════════════════════════════╗
║                 AUDIT WORKER                                 ║
║  Verification stream · Completion handoff · Evidence chain   ║
╚══════════════════════════════════════════════════════════════╝
```

---

## Service Responsibilities

### API Gateway (`services/api-gateway`, `:8100`)

- **Mission intake:** `POST /v1/missions` with SHA-256 idempotency (24h TTL, Redis-backed)
- **Auth enforcement:** `AUTH_MODE=api_key|hybrid|oidc`, per-role key validation (admin/operator/reader/worker)
- **Rate limiting:** 120 req/min sliding window per API key (Redis)
- **Live transport:** `GET /v1/stream/state` — SSE with `mission_id` filter, `Last-Event-ID` resume, keepalive
- **Correlation propagation:** accepts `x-request-id|x-correlation-id` and returns `X-Correlation-Id` on proxied responses
- **Security headers:** `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`
- **OTel tracing:** Jaeger OTLP export
- **Proxy:** Forwards `GET /v1/operations/*` to orchestrator internal APIs

### Orchestrator (`services/orchestrator`, `:8101`)

- **Mission state machine:** `QUEUED → RUNNING → VERIFIED → COMPLETE | FAILED`
- **Lifecycle engines:** shipped defaults currently execute mission-flow v2 first, with optional LangGraph and legacy fallback
- **Project identity:** every mission now carries a durable `project_id` resolved at intake and persisted on the mission record
- **Agent registry:** Canonical 41-agent dataset with runtime telemetry + 8-part persona profiles
- **Pod assignment:** Routes missions to pod streams based on `requested_target_language`
- **Build/package artifacts:** source-bundle missions package a durable Postgres-backed build artifact at `VERIFIED` with digest, manifest, build log, and retrieval metadata
- **Durable review approvals:** Builder and repo review approvals persist as orchestrator-backed approval records rather than local filesystem receipts
- **Agent action ledger:** append-only `agent_action_events` records execution starts/completions, tool usage, persisted outputs, mission mutations, and trace correlation per project, mission, and agent
- **Operations APIs:** `/internal/operations/summary|agents|agent-integrations|projects/{project_id}/audit-events`
- **Data-plane adapters:** Qdrant (active), Milvus/Neo4j/object storage (feature-flagged)
- **OTel tracing:** Jaeger OTLP export

### Protocol Bus MCP (`services/protocol-bus-mcp`, `:8102`)

A six-protocol typed message bus with DLQ, replay detection (409 on duplicate correlation-id), and fail-closed Redis error handling (503 on Redis unavailability).

- **Protocol routing:** Validates and routes alpha/beta/delta/sigma/omega/rho bus messages
- **Schema enforcement:** JSON Schema validation of event envelopes per `schemas/event.envelope.schema.json`
- **Replay detection:** Duplicate correlation-id returns `409`
- **Fail-closed Redis handling:** Redis unavailability returns `503`
- **Dead-letter queue:** `GET /dlq?protocol=<name>` — inspects failed messages
- **Sender validation:** `x-agent-id` must match message `sender` field

### Pod Workers (`services/pod-worker`)

- **Language extraction:** Regex-first static analysis (232 patterns, 20 routed language keys) with optional Python AST structural extraction behind `PYTHON_AST_EXTRACTOR_ENABLED`
- **LogicNode creation:** Per-concept node creation in knowledge base
- **Agent binding:** `AGENT_BINDING` env var — dedicated workers process only matching missions
- **Metrics:** `pod_worker_concepts_extracted_total`, `pod_worker_extraction_latency_seconds`, `pod_worker_binding_skips_total`, `pod_worker_internal_auth_rejections_total`
- **OTel tracing:** Jaeger OTLP export

### Audit Worker (`services/audit-worker`)

- **Verification stream:** Processes `missions.state` Redis stream
- **Completion handoff:** Persists audit reports through orchestrator audit-report APIs
- **Evidence chain:** Writes audit records to `mission_audit_reports`; object-storage mirroring remains optional

### Dashboard (`services/dashboard`, `:8180`)

- **Lightweight status UI:** FastAPI + HTML operational status surface
- **Health aggregation:** Proxies health from all downstream services

### Agent Runtime (`services/agent-runtime`)

- **Dedicated topology worker:** Consumes mission-state events for a single `WORKER_AGENT_ID`
- **Profile scope:** Enabled by the full dedicated runtime overlay and per-agent container bindings
- **Telemetry:** Emits per-agent heartbeats, execution metrics, and OTel traces

### Mission Control (`apps/mission-control`, `:3100`)

- **Operator console:** Full Next.js 16 App Router application
- **Primary operator surfaces:** Home/dashboard, chat intake, missions, projects, agents, protocol bus, databases, repo import, and settings
- **Grounded review flows:** Workspace builder review and GitHub repo review with durable approval records and mission launch bundles
- **Project audit timeline:** `Projects` shows per-project audit history with event, mission, agent, service, tool, and duration drill-down backed by the gateway/orchestrator audit APIs
- **Live transport:** SSE EventSource + polling fallback with `stream|poll|paused` mode indicator
- **Windowed rendering:** Virtual scrolling for Protocol Bus and agent roster views (high-volume)

---

## Mission Lifecycle

### Smelt-Cycle — 7-Phase Progression

| Phase | Event | Trigger |
|-------|-------|---------|
| 1 | `MISSION_INTAKE` | `POST /v1/missions` received and deduplicated |
| 2 | `MISSION_QUEUED` | Persisted to PostgreSQL, stream event published |
| 3 | `MISSION_GATING` | CEO agent gates and delegates the mission |
| 4 | `MISSION_RUNNING` | Pod workers active — extraction and LogicNode writes |
| 5 | `MISSION_FUSION` | Pods complete — results merged, verification initiated |
| 6 | `MISSION_VERIFIED` | Audit worker confirms artifact integrity |
| 7 | `MISSION_COMPLETE` | Mission closed with full evidence chain |

### State Machine (LangGraph)

```
QUEUED ──► RUNNING ──► VERIFIED ──► COMPLETE
             │                         ▲
             └──────► FAILED ──────────┘
```

- **Checkpointer:** Postgres (`LANGGRAPH_CHECKPOINTER=postgres`) or memory (default)
- **Fail-open:** `LANGGRAPH_FAIL_OPEN=true` — graph failure falls back to legacy lifecycle
- **Startup rehydration:** In-flight missions recovered on orchestrator restart
- **Default selection:** LangGraph is not the default shipped runtime path while `MISSION_FLOW_V2_ENABLED=true`
- **Completion gate:** when mission metadata includes `source_code`, `COMPLETE` requires both orchestration evidence and a successful stored build artifact

---

## 41-Agent Model

### Tier Structure

| Tier | Agents | Count |
|------|--------|-------|
| Interface | AGENT-01-PM (Project Manager) | 1 |
| Executive | AGENT-02-CEO (Chief Executor) | 1 |
| Support Ring | AGENT-03 through AGENT-14 — Broker, Accountant, Security, IS, VC, Compliance, HW, Tester, Deploy, DEPABS, TESTDATA, RQCA | 12 |
| Pod A (Dynamic) | Manager, Audit, Python, JS, Ruby, PHP Specialists | 6 |
| Pod B (Systems) | Manager, Audit, C, C++, Rust, Zig, Go Specialists | 7 |
| Pod C (Enterprise) | Manager, Audit, Java, C#, Scala, Kotlin Specialists | 6 |
| Pod D (Mathematical & Functional) | Manager, Audit, MATLAB, R, Julia, Mathematica, Haskell, OCaml Specialists | 8 |
| **Total** | | **41** |

### Agent Runtime State Model

Each agent exposes two parallel representations:

**Operational Profile:** runtime state · queue depth · heartbeat age · active mission assignment

**Persona Profile (8-part):**
1. `job_role` — functional title and scope
2. `education_certifications` — credential framework
3. `traits_skills` — competency model
4. `methods_procedures` — workflow patterns
5. `tools` — technology stack
6. `master_instruction` — primary behavioral directive
7. `protocol` — communication and interaction rules
8. `api_configuration` — LLM provider/model/parameter config

**Extensions:** `standards_alignment` (NIST AI RMF · ISO/IEC 42001 · OWASP ASVS) · `evidence_sources`

Implementation: `services/orchestrator/orchestrator/agent_personas.py` — each agent is now backed by a single unified `AgentPersona` dataclass record rather than parallel per-field dicts.

---

## Language Extraction Engine

Regex-first static analysis with no LLM required for this stage. Python can switch to AST-backed structural extraction behind `PYTHON_AST_EXTRACTOR_ENABLED=true`; JavaScript/TypeScript and Java AST modules remain stubbed and are not part of the shipped runtime path.

| Pod | Languages | Concept Prefix | Patterns |
|-----|-----------|---------------|---------|
| A — Dynamic | Python, JavaScript, Ruby, PHP | `DYN-` | ~68 |
| B — Systems | C, C++, Rust, Zig, Go | `SYS-` | ~54 |
| C — Enterprise | Java, C#, Scala, Kotlin | `ENT-` | ~35 |
| D — Mathematical | MATLAB, R, Julia, Mathematica, Haskell, OCaml | `MATH-` | ~75 |
| **Total** | **20 routed language keys** (TypeScript aliases to JavaScript) | | **232 patterns** |

Concept ID format: `{PREFIX}-{DOMAIN:3d}-{CONCEPT:3d}` — e.g. `DYN-006-001` (async function)

Implementation: `services/pod-worker/pod_worker/concept_catalog.py` · `language_extractor.py`

Go, Haskell, and OCaml now ship as full concrete `SpecialistAgent` subclasses rather than fallback stubs, so specialist routing covers their extracted languages directly.

---

## Data Plane

| System | Port | Status | Purpose |
|--------|------|--------|---------|
| PostgreSQL | 5433 | ✅ Active | Primary persistence — single application database with versioned migrations |
| Redis | 6380 | ✅ Active | Streams, rate limiting, idempotency, heartbeats |
| Qdrant | 6334 | ✅ Active | Knowledge retrieval and vector indexing (PG fallback) |
| Milvus | 19530 | ✅ Active | Extended vector-store path for retrieval flows; `MILVUS_ENABLED=true` by default |
| Neo4j | 7474 | ✅ Active | Graph queries for mission/audit relationships; `NEO4J_ENABLED=true` by default |
| MinIO/S3 | 9000 | ✅ Active | Immutable artifact retention (legal-hold, 90-day policy); `OBJECT_STORAGE_ENABLED=true` by default |

### Database Schema (PostgreSQL)

The default compose stack provisions one Postgres database (`POSTGRES_DB`, default `ulr`). Core tables are created by versioned migrations under `services/orchestrator/orchestrator/migrations/`, including:

- `missions`
- `mission_state_events`
- `mission_pod_assignments`
- `mission_logicnodes`
- `mission_knowledge`
- `mission_audit_reports`
- `mission_build_artifacts`
- `review_approvals`
- `schema_migrations`

### Redis Streams

| Stream | Purpose |
|--------|---------|
| `missions.intake` | New mission routing to orchestrator |
| `missions.state` | Lifecycle state change events |
| `missions.pod.{A\|B\|C\|D}` | Pod-specific work queues |
| `agents.heartbeats` | Agent telemetry heartbeats |

The default runtime does not use a separate `missions.audit` stream.

---

## Event Bus Architecture

The Protocol Bus MCP enforces a **6-protocol message taxonomy**:

| Protocol | Direction | Purpose |
|----------|-----------|---------|
| `alpha` | CEO → Pod Managers | Mission assignment directives |
| `beta` | Pod Workers → CEO | Mission progress reports |
| `delta` | Pods ↔ Specialists | Specialist delegation |
| `sigma` | Any → Operations | Status and health signals |
| `omega` | Audit → Orchestrator | Verification results |
| `rho` | System → System | Internal control messages |

All messages must conform to `schemas/event.envelope.schema.json`.

---

## LangGraph State Machine

```python
# Graph structure (services/orchestrator/orchestrator/langgraph_lifecycle.py)
graph = StateGraph(MissionState)
graph.add_node("gate", gate_node)       # QUEUED → GATING → RUNNING
graph.add_node("process", process_node) # RUNNING → FUSION
graph.add_node("verify", verify_node)   # FUSION → VERIFIED → COMPLETE | FAILED
graph.add_conditional_edges("gate", route_after_gate)
graph.add_conditional_edges("process", route_after_process)
```

**Feature flags:**
- `LANGGRAPH_ENABLED=false` (default) — zero-risk, uses legacy lifecycle
- `LANGGRAPH_CHECKPOINTER=postgres` — Postgres-backed checkpointing
- `LANGGRAPH_FAIL_OPEN=true` — graceful fallback on graph errors
- `MISSION_FLOW_V2_ENABLED=true` — shipped default runtime path in current compose/env/settings defaults

---

## Security Architecture

See [`ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md`](ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md) for the full decision record.

### Auth Modes

| Mode | Description |
|------|-------------|
| `api_key` | API key required for all mutations (default) |
| `hybrid` | API key or JWT/OIDC bearer accepted |
| `oidc` | JWT/OIDC bearer required for mutations; API key for internal paths |

### Defense Layers

1. **Network boundary:** API Gateway is the sole public-facing service
2. **Rate limiting:** 120 req/min per key (Redis sliding window)
3. **RBAC:** admin · operator · reader · worker role tiers
4. **Idempotency:** SHA-256 replay-safe mission creation
5. **SAST/SCA:** Bandit · Trivy · gitleaks · pip-audit in CI
6. **Container security:** All images run as non-root users
7. **SBOM generation:** `sbom.spdx.json` via `anchore/sbom-action` in CI

---

## Observability Architecture

| Component | Port | Purpose |
|-----------|------|---------|
| Prometheus | 9090 | Metrics collection and alerting |
| Grafana | 3001 | Dashboards and visualization |
| Alertmanager | 9093 | Alert routing (pager webhook for critical/high) |
| Loki | 3101 | Log aggregation |
| Promtail | — | Log shipping agent |
| Jaeger | 16686 | Distributed trace visualization |

**Instrumented services:** api-gateway · orchestrator · pod-worker · audit-worker · protocol-bus-mcp · dashboard · agent-runtime (full-dedicated profile)

---

## Contract Artifacts

| Artifact | Purpose |
|---------|---------|
| `schemas/event.envelope.schema.json` | Protocol bus message envelope contract |
| `schemas/logicnode.schema.json` | Language-agnostic LogicNode contract |
| `schemas/rir.module.schema.json` | Refined-IR module contract |
| `schemas/rir.fn.schema.json` | Refined-IR function contract |
| `protocol/topics.yaml` | Protocol bus topic catalog |
| `services/orchestrator/orchestrator/migrations/V005_project_audit_event_schema.sql`, `V007_llm_usage_ledger_schema.sql`, `V009_immutable_audit.sql` | Active Postgres audit, LLM usage, and immutable ledger table definitions |
| `docs/openapi/api-gateway.v1.json` | Gateway OpenAPI spec |
| `docs/openapi/orchestrator.v1.json` | Orchestrator OpenAPI spec |

---

## Design Decisions (ADRs)

| ADR | Decision |
|-----|---------|
| [`ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md`](ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md) | Dual-mode auth: API keys default + JWT/OIDC enterprise path |
| [`ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md`](ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md) | Condensed workers default; dedicated-agent profiles are available as optional expansion modes |
