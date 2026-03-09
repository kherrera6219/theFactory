# Architecture — theFactory

**Last updated:** 2026-03-09
**Status:** Production baseline with roadmap phases 1-39 complete

---

## Table of Contents

- [System Overview](#system-overview)
- [Runtime Topology](#runtime-topology)
- [Service Responsibilities](#service-responsibilities)
- [Mission Lifecycle](#mission-lifecycle)
- [35-Agent Model](#35-agent-model)
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

theFactory is a **35-agent multi-agent software refinery** built on a microservice architecture. Missions (software build requests) enter through the API Gateway, are delegated through an agent hierarchy, processed by language-specialist pod workers, and completed with full audit evidence.

The system is organized into three planes:

| Plane | Components |
|-------|-----------|
| **Control Plane** | API Gateway, Orchestrator, Mission Control UI |
| **Data Plane** | PostgreSQL, Redis, Qdrant, Milvus (optional), Neo4j (optional), MinIO/S3 (optional) |
| **Observability Plane** | Prometheus, Grafana, Loki, Promtail, Alertmanager, Jaeger |

---

## Runtime Topology

```
╔══════════════════════════════════════════════════════════════════╗
║                     MISSION CONTROL UI                          ║
║              Next.js 16 · TypeScript · SSE Transport            ║
║   Dashboard · Missions · Agents · Semantic Bus · Builder        ║
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
║  35-agent registry + persona profiles  ║ │
║  Qdrant/Milvus/Neo4j/S3 adapter plane  ║ │
║  Operations APIs · OTEL traces         ║ │
╚══════════╤═════════════════════════════╝ │
           │ Redis Streams          ╔══════▼══════════════════════╗
           │                       ║   SEMANTIC BUS MCP :8102    ║
           │                       ║   6-protocol validation      ║
           │                       ║   alpha/beta/delta/           ║
           │                       ║   sigma/omega/rho            ║
           │                       ╚═════════════════════════════╝
╔══════════▼═════════════════════════════════════════════════════╗
║                     POD WORKERS                               ║
║  Pod A · Python / JavaScript / Ruby / PHP                     ║
║  Pod B · C / C++ / Rust                                       ║
║  Pod C · Java / C# / Scala / Kotlin                           ║
║  Pod D · MATLAB / R / Julia / Mathematica                     ║
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
- **Security headers:** `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`
- **OTel tracing:** Jaeger OTLP export
- **Proxy:** Forwards `GET /v1/operations/*` to orchestrator internal APIs

### Orchestrator (`services/orchestrator`, `:8101`)

- **Mission state machine:** `QUEUED → RUNNING → VERIFIED → COMPLETE | FAILED`
- **LangGraph integration:** Feature-flagged StateGraph with 3 nodes, conditional edges, fail-open fallback
- **Agent registry:** Canonical 35-agent dataset with runtime telemetry + 8-part persona profiles
- **Pod assignment:** Routes missions to pod streams based on `requested_target_language`
- **Operations APIs:** `/internal/operations/summary|agents|agent-integrations`
- **Data-plane adapters:** Qdrant (active), Milvus/Neo4j/object storage (feature-flagged)
- **OTel tracing:** Jaeger OTLP export

### Semantic Bus MCP (`services/semantic-bus-mcp`, `:8102`)

- **Protocol routing:** Validates and routes alpha/beta/delta/sigma/omega/rho bus messages
- **Schema enforcement:** JSON Schema validation of event envelopes per `schemas/event.envelope.schema.json`
- **Dead-letter queue:** `GET /dlq?protocol=<name>` — inspects failed messages
- **Sender validation:** `x-agent-id` must match message `sender` field

### Pod Workers (`services/pod-worker`)

- **Language extraction:** Regex-based static analysis (169 patterns, 16 languages)
- **LogicNode creation:** Per-concept node creation in knowledge base
- **Agent binding:** `AGENT_BINDING` env var — dedicated workers process only matching missions
- **Metrics:** `pod_worker_concepts_extracted_total`, `pod_worker_extraction_latency_seconds`, `pod_worker_binding_skips_total`, `pod_worker_internal_auth_rejections_total`
- **OTel tracing:** Jaeger OTLP export

### Audit Worker (`services/audit-worker`)

- **Verification stream:** Processes `missions.audit` Redis stream
- **Completion handoff:** Updates mission to `VERIFIED` state with artifact references
- **Evidence chain:** Writes audit records with full traceability to `audit_artifacts` table

### Dashboard (`services/dashboard`, `:8180`)

- **Lightweight status UI:** FastAPI + HTML operational status surface
- **Health aggregation:** Proxies health from all downstream services

### Agent Runtime (`services/agent-runtime`)

- **Dedicated topology worker:** Consumes mission-state events for a single `WORKER_AGENT_ID`
- **Profile scope:** Enabled by the full dedicated runtime overlay and per-agent container bindings
- **Telemetry:** Emits per-agent heartbeats, execution metrics, and OTel traces

### Mission Control (`apps/mission-control`, `:3100`)

- **Operator console:** Full Next.js 16 App Router application
- **Live transport:** SSE EventSource + polling fallback with `stream|poll|paused` mode indicator
- **Builder:** 4-step repository intake (import → file select → diff review/apply gate → mission config)
- **Windowed rendering:** Virtual scrolling for Semantic Bus and agent roster views (high-volume)

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

---

## 35-Agent Model

### Tier Structure

| Tier | Agents | Count |
|------|--------|-------|
| Interface | AGENT-01-PM (Project Manager) | 1 |
| Executive | AGENT-02-CEO (Chief Executor) | 1 |
| Support Ring | CTO, Architect, Security, QA, DevOps, Documentation | 6 |
| Pod A (Dynamic) | Manager, Audit, Python, JS, Ruby, PHP Specialists | 6 |
| Pod B (Systems) | Manager, Audit, C, C++, Rust Specialists | 5 |
| Pod C (Enterprise) | Manager, Audit, Java, C#, Scala, Kotlin Specialists | 6 |
| Pod D (Mathematical) | Manager, Audit, MATLAB, R, Julia, Mathematica Specialists | 6 |
| **Total** | | **35** |

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

Implementation: `services/orchestrator/orchestrator/agent_personas.py`

---

## Language Extraction Engine

Regex-based static analysis — no AST, no LLM required for this stage.

| Pod | Languages | Concept Prefix | Patterns |
|-----|-----------|---------------|---------|
| A — Dynamic | Python, JavaScript, Ruby, PHP | `DYN-` | ~68 |
| B — Systems | C, C++, Rust | `SYS-` | ~36 |
| C — Enterprise | Java, C#, Scala, Kotlin | `ENT-` | ~35 |
| D — Mathematical | MATLAB, R, Julia, Mathematica | `MATH-` | ~30 |
| **Total** | **16 languages** | | **169 patterns** |

Concept ID format: `{PREFIX}-{DOMAIN:3d}-{CONCEPT:3d}` — e.g. `DYN-006-001` (async function)

Implementation: `services/pod-worker/pod_worker/concept_catalog.py` · `language_extractor.py`

---

## Data Plane

| System | Port | Status | Purpose |
|--------|------|--------|---------|
| PostgreSQL | 5433 | ✅ Active | Primary persistence — 8 databases, versioned migrations |
| Redis | 6380 | ✅ Active | Streams, rate limiting, idempotency, heartbeats |
| Qdrant | 6334 | ✅ Active | Knowledge retrieval and vector indexing (PG fallback) |
| Milvus | 19530 | ⚙️ Feature-flagged | Optional vector-store path for extended retrieval flows |
| Neo4j | — | ⚙️ Feature-flagged | Graph queries for mission/audit relationships |
| MinIO/S3 | — | ⚙️ Feature-flagged | Immutable artifact retention (legal-hold, 90-day policy) |

### Database Schema (PostgreSQL)

| Database | Purpose |
|----------|---------|
| `knowledge_lake` | Mission-extracted knowledge and LogicNodes |
| `state_graph` | Mission lifecycle state and events |
| `logicnode_registry` | Canonical LogicNode records |
| `traceability_ledger` | Audit artifact and custody chain |
| `model_store` | ML/embedding model metadata |

### Redis Streams

| Stream | Purpose |
|--------|---------|
| `missions.intake` | New mission routing to orchestrator |
| `missions.state` | Lifecycle state change events |
| `missions.pod.{A\|B\|C\|D}` | Pod-specific work queues |
| `missions.audit` | Verification/audit stream |
| `agents.heartbeats` | Agent telemetry heartbeats |

---

## Event Bus Architecture

The Semantic Bus MCP enforces a **6-protocol message taxonomy**:

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
- `MISSION_FLOW_V2_ENABLED=false` — optional 11-phase runtime prototype; production remains v1.1 canonical

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

**Instrumented services:** api-gateway · orchestrator · pod-worker · audit-worker · semantic-bus-mcp · dashboard · agent-runtime (full-dedicated profile)

---

## Contract Artifacts

| Artifact | Purpose |
|---------|---------|
| `schemas/event.envelope.schema.json` | Semantic bus message envelope contract |
| `schemas/logicnode.schema.json` | Language-agnostic LogicNode contract |
| `schemas/rir.module.schema.json` | Refined-IR module contract |
| `schemas/rir.fn.schema.json` | Refined-IR function contract |
| `protocol/topics.yaml` | Semantic bus topic catalog |
| `ledger/schema.sql` | Traceability ledger table definitions |
| `docs/openapi/api-gateway.v1.json` | Gateway OpenAPI spec |
| `docs/openapi/orchestrator.v1.json` | Orchestrator OpenAPI spec |

---

## Design Decisions (ADRs)

| ADR | Decision |
|-----|---------|
| [`ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md`](ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md) | Dual-mode auth: API keys default + JWT/OIDC enterprise path |
| [`ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md`](ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md) | Condensed workers default; dedicated-agent profiles are available as optional expansion modes |
