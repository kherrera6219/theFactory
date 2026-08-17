<div align="center">

# 🏭 theFactory

**An AI software factory — not a code-completion tool.**

*theFactory is a local-first, event-driven AI software factory for building, modernizing, debugging, securing, porting, validating, and optimizing applications through task-activated specialist agents, multi-provider model routing, dependency absorption, isolated workspaces, ephemeral runtime test environments, AI runtime QC, and audit-ready evidence.*

[![CI](https://github.com/kherrera6219/theFactory/actions/workflows/ci.yml/badge.svg)](https://github.com/kherrera6219/theFactory/actions/workflows/ci.yml)
[![Security](https://github.com/kherrera6219/theFactory/actions/workflows/security.yml/badge.svg)](https://github.com/kherrera6219/theFactory/actions/workflows/security.yml)
[![Coverage Gate](https://img.shields.io/badge/coverage%20gate-80%25%2B-blue)](docs/TESTING_QUALITY_GATES.md)
[![Audit](https://img.shields.io/badge/repo%20audit-hygiene%20script-blue)](scripts/production_review_audit.py)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![Next.js](https://img.shields.io/badge/Next.js-16-black)](apps/mission-control/package.json)
[![License](https://img.shields.io/badge/license-AGPL--3.0%20%2F%20Commercial-blue)](LICENSE)

</div>

> **Version:** 1.3.0 · **Last updated:** 2026-08-17 · **Status:** Active development — feature-complete against the v1.3 mission-pipeline scope
>
> **Development status:** the infrastructure, security model, protocol bus, data plane, operator UI, and test surface are mature and CI-verified. Live BUILD_NEW missions have reached `COMPLETE` (Go S1-01, chat-driven PyQt6, stdlib Snake). Default LLM route is **Gemini 3.7 Flash**. Runtime QC runs generated tests when they exist; a bare launch (`started_only`) or syntax-only compile is **ADVISORY**, never a PASS.
>
> The **semantic engine is partially realised**: LogicNodes carry AST-recovered types, Refined-IR carries real op streams and side-effect-derived purity, and behavioural equivalence executes generated code in a hardened sandbox — but type recovery is real only for **Python, Java, and Haskell**. Other languages produce honestly-labelled templated output. BUILD_NEW is a sequential specialist prompt-chain, not a four-pod fan-out.
>
> Deliberately **not** built, by recorded decision: the four-pod parallel comprehension model, the Doc 30 LogicNode Registry, binary/LLVM output, and the 0.0001% equivalence tolerance. Per-area verdicts are in [`docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md`](docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md).
>
> **Not production-ready.** Remaining work: the rest of the live-proof matrix (PORT/transform through Chat SOW, failure injection, provider fallback) and a live EDCP bus exercise. Sandbox `docker.sock` now lives on `sandbox-runner`, not the orchestrator. See [`docs/WORK_QUEUE.md`](docs/WORK_QUEUE.md) and [`docs/CURRENT_TODO.md`](docs/CURRENT_TODO.md).


---

## Table of Contents

- [What theFactory Is](#what-thefactory-is)
- [theFactory vs. Vibe Coding](#thefactory-vs-vibe-coding)
- [Mission Lifecycle (At a Glance)](#mission-lifecycle-at-a-glance)
- [Overview](#overview)
- [Implementation Status](docs/IMPLEMENTATION_STATUS.md)
- [Architecture](#architecture)
- [41-Agent Runtime Model](#41-agent-runtime-model)
- [Mission Lifecycle](#mission-lifecycle)
- [Language Extraction Engine](#language-extraction-engine)
- [Services](#services)
- [API Reference](#api-reference)
- [Mission Control UI](#mission-control-ui)
- [Data Systems](#data-systems)
- [Security & Auth](#security--auth)
- [Observability](#observability)
- [Quick Start](#quick-start)
- [Development](#development)
- [Testing & Quality Gates](#testing--quality-gates)
- [Configuration](#configuration)
- [Deployment Profiles](#deployment-profiles)
- [Documentation Index](#documentation-index)

---

## What theFactory Is

theFactory is a **local-first, event-driven AI software factory in active development**. It is designed to accept natural-language missions and deliver working software through a governed orchestration pipeline staffed by task-activated specialist agents.

It is **not** a code-completion tool, a chat-to-code assistant, or a single-prompt generator. The goal is a complete software production system that produces requirements, architecture, code, tests, runtime environments, runtime validation, and audit-ready evidence as part of each mission. The intake → generate → QC → deliver path has been run live; it is a governed sequential LLM factory, not a 41-process smelter, and it is not a production release.

Read more in [`docs/00_PRODUCT_OVERVIEW.md`](docs/00_PRODUCT_OVERVIEW.md) and [`docs/WHAT_THEFACTORY_IS_AND_IS_NOT.md`](docs/WHAT_THEFACTORY_IS_AND_IS_NOT.md).

### Core Doctrines

1. **Not vibe coding.** Full software production lifecycles, not single-prompt drops.
2. **Agents are task-activated.** A registry of available roles is not a permanent workforce.
3. **Dependencies are liabilities until proven necessary.** See [`docs/DEPENDENCY_ABSORPTION_DOCTRINE.md`](docs/DEPENDENCY_ABSORPTION_DOCTRINE.md).
4. **Smart coding.** Generate only what the application actually needs.
5. **Workspaces are isolated by default.** The factory never modifies the source directly.
6. **Nothing ships without evidence.** The production target is that every completed mission produces a verifiable audit trail.
7. **Sensitive code stays local.** See [`docs/SENSITIVE_CODE_HANDLING_POLICY.md`](docs/SENSITIVE_CODE_HANDLING_POLICY.md).

---

## theFactory vs. Vibe Coding

| Normal Vibe Coding | theFactory |
|---|---|
| Fast prompt-to-code | Full software production lifecycle |
| One model, one chat loop | Task-activated agent workforce |
| Often adds dependencies quickly | Eliminates dependencies unless necessary |
| Preview-first | Requirements, architecture, tests, runtime QC |
| Weak traceability | Mission events, artifacts, audit evidence |
| Demo-focused | Production-readiness target |
| Runs on your machine | Operates in isolated, disposable workspaces |
| No audit trail | Full chain-of-custody evidence bundle |
| Trust the LLM | Verify with tests and runtime QC |
| Ship the dependency tree | Shrink the dependency tree |

Both approaches have their place. theFactory is being built for the heavier software-production work that simple prompt-to-code workflows cannot reliably ship by themselves.

---

## Mission Lifecycle (At a Glance)

```
PM intake
  → requirements
  → architecture
  → mission plan
  → agent activation
  → code, docs, tests, build
  → dependency absorption
  → isolated workspace
  → disposable test environment
  → runtime QC
  → audit evidence
  → release handoff
```

For the implemented lifecycle (Mission Flow v2 with optional clarification pause) see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/ARCHITECTURE_DATA_FLOWS.md`](docs/ARCHITECTURE_DATA_FLOWS.md), and [`docs/MISSION_FLOW_V2.md`](docs/MISSION_FLOW_V2.md).

---

## Overview

**theFactory** is the HolyGrail runtime implementation of a 41-agent multi-agent software refinery. It is designed as a Windows-friendly, Docker-based monorepo that provides:

Current implementation status: [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md)

The list below describes implemented, CI-verified subsystems across theFactory:

- **Core Software Engine** — 11-phase Mission Flow v2 (default), 41-agent canonical registry, 6 Redis protocols (`alpha`/`beta`/`delta`/`sigma`/`omega`/`rho`). Real AST extractors for **Python, JS/TS, and Java**. Go, Haskell, OCaml, and Julia files are regex parsers shipped under an AST filename — they are not language ASTs.
- **Semantic LogicNodes & Refined-IR** — LogicNodes carry AST-recovered `types.in`/`types.out`; Refined-IR carries real statement-level op streams, side-effect-derived purity, and executable equivalence vectors. Each module labels itself `ast_v1` or `templated_v1`, so a consumer can always tell a real projection from a synthetic one. Type recovery covers **Python, Java, and Haskell**; other languages emit honestly-empty types. BUILD_NEW missions do not extract LogicNodes from source they just invented.
- **Runtime QC** — RQCA on by default. Generated integration tests, when present, are the sandbox command. Unmet third-party deps in a `--network=none` sandbox are `DRY_RUN`, never PASS. `started_only` and syntax-only success are ADVISORY. Compose default is `RQCA_ENFORCEMENT_ENABLED=true` (FAIL blocks; advisory verdicts do not).
- **Behavioural Equivalence Verification** — executes generated artifacts against their equivalence vectors inside a hardened Docker sandbox (`--network=none`, `--read-only`, `--cap-drop=ALL`, no-new-privileges) shared with runtime QC. Opt-in, advisory, Python only; a vector that merely ran is reported as `executed_without_error`, never `passed`. BUILD_NEW skips this (no Refined-IR to project from).
- **Downstream Deployment Handshake Exporters** — REST endpoints (`/v1/missions/{id}/export/helm` and `/v1/missions/{id}/export/github-actions`) generating gzipped Kubernetes Helm Charts and GitHub Actions CI/CD workflows.
- **Gemini 3.7 Flash Primary Model Integration** — Default route for all agents (`GEMINI_MODEL=gemini-3.7-flash`). Vault, gateway allow-list, compose, and cost ledger match. OpenAI and Anthropic remain selectable non-default routes.
- **Desktop Electron Packaging** — Standalone Next.js server bundle; the packaged app talks to the backend through `/api/gateway` (same operator session as the browser). Docker Desktop & WSL2 daemon preflight lives in `electron/diagnostics.ts`.
- **Audit & Quality Gates** — `production_review_audit.py` is a **hygiene** script (static file/string checks), not a live-mission certificate. Backend coverage floor is 80%; `runtime.py` is at 100% line / 99% branch. Mission Control Vitest suite is 146 tests. Do not treat a green audit badge as “zero vulnerabilities.”
- **Multi-modal Context Ingestion** — Native support for PDF, Word, Markdown, and image diagrams converted via IS-Agent & provider layer.
- **Protocol Bus Architecture** — Six-protocol Redis Streams event plane with DLQ, 409 replay detection, and fail-closed Redis error handling.
- **41-Agent Control Model** — Canonical registry across interface, executive, support, and pod-specialist tiers; supports condensed, dedicated, and full-dedicated runtime topologies.
- **Observability & Data Plane** — Complete integration across PostgreSQL, Redis, Qdrant, Milvus, Neo4j, MinIO, Jaeger OTLP, Prometheus, Grafana, Loki, and Alertmanager.


---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         EXTERNAL CLIENTS                        │
│               (Mission Control UI / API consumers)              │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS / REST
┌───────────────────────────▼─────────────────────────────────────┐
│                        API GATEWAY :8100                        │
│  Auth (api_key|hybrid|oidc) · Rate limiting · Security headers  │
│  Idempotency · SSE live transport · OpenAPI contracts           │
└───────────┬───────────────────────────────────────┬─────────────┘
            │ internal REST                         │ SSE stream
┌───────────▼───────────────────────────────────────▼─────────────┐
│                      ORCHESTRATOR :8101                         │
│  Mission Flow v2 (default) · LangGraph optional, off            │
│  41-agent registry · Operations APIs · Qdrant/Neo4j/S3 plane   │
└──┬──────┬──────────┬───────────────┬───────────────────────────┘
   │      │ Redis    │               │
   │   Streams   ┌──▼────────────────▼──┐
   │      │      │   PROTOCOL BUS MCP    │
   │      │      │   :8102               │
   │      │      │   6-protocol routing  │
   │      │      └───────────────────────┘
   │      │
┌──▼──────▼──────────────────────────────────────────────────────┐
│                      POD WORKERS                               │
│  Pod A  (Python/JS/Ruby/PHP)  — Dynamic Languages              │
│  Pod B  (C/C++/Rust/Zig/Go)   — Systems Languages              │
│  Pod C  (Java/C#/Scala/Kotlin)— Enterprise Languages           │
│  Pod D  (MATLAB/R/Julia/Mathematica/Haskell/OCaml)             │
│                    — Mathematical & Functional Languages       │
│  Each: language extraction → LogicNode creation → KB write     │
└──────────────────────────┬─────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────┐
│                     AUDIT WORKER                               │
│  Verification stream processing · Completion handoff           │
└────────────────────────────────────────────────────────────────┘

DATA PLANE
  PostgreSQL :5433  ─ missions, events, assignments, logicnodes, audits
  Redis :6380       ─ streams, rate limiting, idempotency, heartbeats
  Qdrant :6334      ─ active knowledge retrieval (PG fallback)
  Milvus :19530     ─ extended vector store (on by default)
  Neo4j :7474       ─ knowledge graph adapter (on by default)
  MinIO/S3 :9000    ─ object storage (legal-hold, 90-day retention; on by default)

OBSERVABILITY PLANE
  Prometheus · Grafana · Loki · Promtail · Alertmanager · Jaeger OTLP
```

### Smelt-Cycle: Operator-Visible Checkpoint Events

The operator-facing mission model surfaces 7 key checkpoint events. These map to the condensed smelt-cycle phase model visible in Mission Control and audit reports.

> **Note:** The shipped default runtime is the **11-phase Mission Flow v2 engine** (`mission_flow_v2.py`). It expands the coarse `QUEUED → RUNNING → VERIFIED → COMPLETE` arc into 11 internal phases that include PM intake, CEO delegation, pod assignment, and specialist assignment steps before RUNNING. The 7 events below are the operator-visible subset of those phases.

| Phase | Event | Description |
|-------|-------|-------------|
| 1 | MISSION_INTAKE | Mission received and deduplicated at gateway |
| 2 | MISSION_QUEUED | Persisted to orchestrator, awaiting scheduling |
| 3 | MISSION_GATING | Executive tier gates and delegates mission |
| 4 | MISSION_RUNNING | Pod workers processing language artifacts |
| 5 | MISSION_FUSION | Results merged, verification initiated |
| 6 | MISSION_VERIFIED | Audit worker confirms artifact integrity |
| 7 | MISSION_COMPLETE | Mission closed with full evidence chain |

---

## 41-Agent Runtime Model

The orchestrator maintains a canonical registry of **41 specialist agents** organized across four tiers:

| Tier | Count | Agents | Role |
|------|-------|--------|------|
| **Interface** | 1 | AGENT-01-PM | Project Manager — mission intake and PM→CEO handoff |
| **Executive** | 1 | AGENT-02-CEO | Chief Executor — mission delegation to pod managers |
| **Support Ring** | 12 | AGENT-03–11 plus AGENT-39–41 | Broker, Accountant, Security, IS, VC, Compliance, HW, Tester, Deploy, DEPABS, TESTDATA, RQCA |
| **Pod Managers** | 4 | Pod A/B/C/D Managers | Pod-level mission coordination |
| **Pod Auditors** | 4 | Pod A/B/C/D Auditors | Pod-level verification |
| **Specialists** | 19 | Language specialists across all pods | Language-specific code analysis and generation |
| **Total** | **41** | | |

**Support Ring detail:** Broker, Accountant, Security, IS, VC, Compliance, HW, Tester, Deploy (AGENT-03–11), plus DEPABS, TESTDATA, and RQCA (AGENT-39–41).

**Specialist language implementations (19):** Python, JavaScript/TypeScript (TypeScript aliases to JavaScript — 20 routed keys, 19 specialist implementations), Ruby, PHP (Pod A); C, C++, Rust, Zig, Go (Pod B); Java, C#, Scala, Kotlin (Pod C); MATLAB, R, Julia, Mathematica, Haskell, OCaml (Pod D).

### Agent Runtime State

Each agent exposes:

```json
{
  "agent_id": "AGENT-01-PM",
  "state": "IDLE | ACTIVE | RUNNING | VERIFYING | ERROR | PAUSED",
  "queue_depth": 0,
  "active_mission_id": null,
  "llm_recommendation": {
    "provider": "gemini",
    "model": "gemini-3.7-flash",
    "mode": "thinking",
    "thinking_level": "high"
  },
  "persona_profile": {
    "job_role": "...",
    "education_certifications": "...",
    "traits_skills": "...",
    "methods_procedures": "...",
    "tools": "...",
    "master_instruction": "...",
    "protocol": "...",
    "api_configuration": "...",
    "standards_alignment": "NIST AI RMF · ISO/IEC 42001 · OWASP ASVS",
    "evidence_sources": "..."
  }
}
```

Agent persona definitions are unified records: `agent_personas.py` uses a single `AgentPersona` dataclass per agent, and a test enforces that every registry agent has a corresponding persona entry.

### LLM Provider Assignment

Runtime persona and delegation metadata currently support provider-aware recommendations across:

- **Anthropic**
- **OpenAI**
- **Google Gemini**

Current runtime default: all 41 agents route to Gemini 3.7 Flash
(`gemini-3.7-flash`) with high thinking. Mission Control Settings exposes three
operator-selectable vault-slot model routes for testing: ChatGPT 5.5, Claude
Opus 4.8, and Gemini 3.7 Flash. OpenAI and Anthropic remain supported provider
routes, but they are not the default assignment for any agent.


The live runtime exposes recommended provider/model metadata through:

- `GET /internal/operations/agent-integrations`
- `GET /v1/operations/agent-integrations`

Reference matrix: [`docs/AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md`](docs/AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md)

---

## Mission Lifecycle

External mission states remain:

```
QUEUED ─→ RUNNING ─→ VERIFIED ─→ COMPLETE
            │                       ↑
            └──── FAILED ───────────┘
```

Lifecycle engine behavior in the shipped defaults:

- **Mission Flow v2 is enabled by default** via `MISSION_FLOW_V2_ENABLED=true`
- **LangGraph is optional** via `LANGGRAPH_ENABLED=true` and is disabled by default
- **Legacy lifecycle fallback** remains available when both newer paths are disabled or fail open
- **Postgres checkpointer** (`LANGGRAPH_CHECKPOINTER=postgres`) is available when LangGraph is enabled
- **Startup rehydration** exists for in-flight missions

---

## Language Extraction Engine

Pod workers run a hybrid AST + regex static-analysis extraction engine that detects computational concepts and structural code definitions before LogicNode creation. Concrete AST extractors are live across multi-pod language families:
- **Python** (`PYTHON_AST_EXTRACTOR_ENABLED=true`) — uses stdlib `ast` module; zero false positives for structural fields.
- **JavaScript/TypeScript** (`JS_AST_EXTRACTOR_ENABLED=true`) — uses `esprima`; strips TS syntax before parsing.
- **Java** (`JAVA_AST_EXTRACTOR_ENABLED=true`) — uses `javalang`; extracts packages, imports, classes, constructors, methods, annotations.
- **Go / Haskell / OCaml / Julia** — regex structural parsers in `*_ast_extractor.py` files. They are **not** language ASTs. Types stay honestly empty except where noted above.


No LLM calls are required for this phase.

| Pod | Languages | Concept Prefix | Patterns |
|-----|-----------|---------------|---------|
| A — Dynamic | Python, JavaScript/TypeScript, Ruby, PHP | `DYN-` | ~68 |
| B — Systems | C, C++, Rust, Zig, Go | `SYS-` | ~54 |
| C — Enterprise | Java, C#, Scala, Kotlin | `ENT-` | ~35 |
| D — Mathematical | MATLAB, R, Julia, Mathematica, Haskell, OCaml | `MATH-` | ~75 |
| **Total** | **20 routed language keys** (19 specialist implementations; TypeScript aliases to JavaScript) | | **232 patterns** |

All 19 specialist implementations are fully concrete `SpecialistAgent` subclasses, including Go, Haskell, and OCaml.

Each extracted concept becomes a **LogicNode** with:
- `concept_id` (e.g. `DYN-006-001` for async function, `SYS-011-001` for Rust `Result<T>`)
- `confidence` score (0.0–1.0)
- `source_line` number and evidence snippet
- `domain`, `intent`, and `language`

---

## Services

| Service | Port | Tech | Description |
|---------|------|------|-------------|
| `api-gateway` | 8100 | FastAPI | Public API boundary, auth, rate limiting, SSE transport |
| `orchestrator` | 8101 | FastAPI | Mission state machine, agent registry, operations APIs |
| `protocol-bus-mcp` | 8102 | FastAPI | 6-protocol typed message bus with DLQ, replay detection, and fail-closed Redis error handling |
| `pod-worker` | — | FastAPI | Language-aware pod stream worker (4 pod variants) |
| `audit-worker` | — | FastAPI | Verification stream processing |
| `dashboard` | 8180 | FastAPI | Lightweight operational status UI |
| `agent-runtime` | — | FastAPI | Dedicated single-agent runtime used by the full dedicated topology |
| `mission-control` | 3100 | Next.js 16 | Primary operator console |

---

## API Reference

### Gateway (`http://localhost:8100`)

#### Health & Observability
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Full health with dependency states |
| `GET` | `/readyz` | Kubernetes-style readiness probe |
| `GET` | `/metrics` | Prometheus metrics endpoint |

#### Mission Management
| Method | Path | Auth Required | Description |
|--------|------|--------------|-------------|
| `POST` | `/v1/missions` | mutate/admin | Create mission (idempotency key supported) |
| `GET` | `/v1/missions` | reader+ | List missions with filters |
| `GET` | `/v1/missions/{id}` | reader+ | Get mission detail |
| `GET` | `/v1/missions/{id}/events` | reader+ | Mission event log |
| `POST` | `/v1/missions/{id}/state` | mutate/admin | Emit state transition event |
| `GET` | `/v1/missions/{id}/pod-assignment` | reader+ | Active pod assignment record |
| `GET` | `/v1/missions/{id}/chain-trace` | reader+ | Agent chain-of-command trace |
| `GET` | `/v1/missions/{id}/logicnodes` | reader+ | Extracted LogicNode records |
| `GET` | `/v1/missions/{id}/knowledge` | reader+ | Knowledge records for mission |
| `GET` | `/v1/missions/{id}/audit-reports` | reader+ | Audit report records |
| `GET` | `/v1/missions/{id}/audit-artifacts` | reader+ | Object storage artifacts (feature-flagged) |
| `GET` | `/v1/missions/{id}/knowledge-graph` | reader+ | Neo4j graph (feature-flagged) |
| `GET` | `/v1/missions/{id}/build-artifacts` | reader+ | Build/package artifact records |
| `GET` | `/v1/missions/{id}/build-artifacts/{artifact_id}` | reader+ | Single build artifact detail |

#### Builder
| Method | Path | Auth Required | Description |
|--------|------|--------------|-------------|
| `POST` | `/v1/builder/preview` | mutate/admin | LLM-grounded builder preview (OpenAI/Anthropic/Gemini) |

#### Operations
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/operations/summary` | Runtime health summary |
| `GET` | `/v1/operations/agents` | All 41 agent runtime states |
| `GET` | `/v1/operations/agent-integrations` | Agent protocol/LLM/persona profiles |
| `GET` | `/v1/operations/events` | Recent mission events across all missions |
| `GET` | `/v1/operations/agent-events` | Recent agent-scoped events |
| `GET` | `/v1/operations/logicnodes` | Recent LogicNode records across all missions |
| `GET` | `/v1/operations/pod-assignments` | Active pod assignments |
| `GET` | `/v1/operations/projects` | Project-level mission groupings |
| `GET` | `/v1/operations/alerts` | Active runtime alerts |

#### Live Transport
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/stream/state` | SSE stream with `mission_id` filter, `Last-Event-ID` resume, keepalive |

### Protocol Bus MCP (`http://localhost:8102`)

The protocol bus is a six-protocol typed message bus. Routing is lexical/channel-based. `SigmaPayload.embedding_ref` is reserved for future semantic routing but is not currently implemented.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/send` | Send validated bus message (alpha/beta/delta/sigma/omega/rho); returns HTTP 409 on replay detection, HTTP 503 on Redis unavailability |
| `GET` | `/dlq` | Inspect dead-letter queue |
| `GET` | `/health` · `/readyz` · `/metrics` | Standard probes |

**Hardened behavior:** Replay detection returns HTTP 409. Redis unavailability (dedup/backpressure) returns HTTP 503 — errors do not fail silently. Backpressure checks all channels, not just the first.

### OpenAPI Exports
- [`docs/openapi/api-gateway.v1.json`](docs/openapi/api-gateway.v1.json)
- [`docs/openapi/orchestrator.v1.json`](docs/openapi/orchestrator.v1.json)

---

## Mission Control UI

**Access:**
- Docker stack: `http://localhost:3100`
- Direct dev server: `http://localhost:3000` (`npm run dev`)
- Local Mission Control starts unlocked through `OPERATOR_SESSION_BYPASS=true` in the default Docker profile.
  Locked deployment profiles can disable bypass and require an operator session.
- PM Agent chat, repo review, builder review, and mission-state changes also require the
  `OPERATOR-API-KEY` vault slot to be configured so Mission Control can forward
  authenticated requests to the local API Gateway.

**Features:**

| View | Description |
|------|-------------|
| Home / Dashboard | Runtime-wide health, mission counts, and operator launch context |
| Chat | PM-agent intake conversation with attached-file language inference |
| Missions | Mission table with lifecycle state and phase stepper |
| Mission Detail | Live event timeline, Smelt-cycle phase stepper (SSE-driven), chain-of-command, LogicNode/knowledge drill-down, and build-artifact visibility |
| Agents | 41-agent roster grid with persona drill-down and windowed live logs |
| LogicNodes | Logic artifact explorer with mission filtering, confidence summaries, and source lineage |
| Protocol Bus | Live message stream with `stream|poll|paused` transport diagnostics and windowed rendering |
| Projects | Project portfolio, mission rollups, and project-level audit timeline |
| Alerts | Incident and alert center with acknowledge/resolve workflow |
| Performance | Runtime readiness, dependency health, and mission-state capacity snapshot |
| Builder | Grounded local-workspace review with patch contract, durable approval gate, launch-time approval verification, and mission launch bundle |
| Repo Import | Local ZIP import, archive-hash review gate, launch-time approval verification, and mission scoping with bundled source context |
| Databases | Shared data-system readiness and diagnostics |
| Settings | Provider key management, vault-backed secrets, and local environment controls |

Primary shell navigation is grouped as **Workflow** (Home, Chat, Builder, Missions, Projects, Mission History), **Observability** (Agents, LogicNodes, Protocol Bus, Alerts, Performance), and **Configuration** (Databases, Repo Import, Audit Log, Settings). `/dashboard` is a Home alias; `/history`, `/logic-nodes`, and `/repo-import` redirect to the canonical routes.

**Agent runtime labels:**

Mission Control shows 41 logical agents. In the default condensed runtime,
specialist, pod-manager, and pod-audit agents run through shared pod-worker
containers and appear as `WORKER`. Interface, executive, and support agents are
orchestrator-managed control roles; the orchestrator emits their runtime
heartbeats and the UI labels them `MANAGED`. This is expected and does not mean
those agents are broken or fake. A fully isolated per-agent container topology
is optional future/deployment scope, not the default local product path.

**Additional operator experience features (Phase 6-7, shipped 2026-05-22):**

| Feature | Description |
|---------|-------------|
| Command Palette | `Ctrl+K` fuzzy-search for missions, agents, LogicNodes, and nav links; keyboard badge display |
| Tooltip Glossary | 20 domain terms (all Smelt-Cycle phases, MissionFlow v2 phases, key concepts) with hover tooltips on phase stepper and mission detail |
| Guided Tour | 6-step first-visit spotlight tour; reopenable via `Ctrl+G`; localStorage-persisted |
| Status Bar | Live services-health count, active mission count, last-sync timestamp; polls every 15s |
| Inline Mission Name Edit | Click-to-edit mission name in Mission Detail header; persisted via PATCH API |
| Electron Desktop Shell | Custom frameless titlebar with platform-aware window controls; system tray with mission status; local repo browsing via native file dialog; auto-update infrastructure (`electron-updater`); full IPC bridge with contextBridge security |

**Technology:**
- Next.js 16 App Router, TypeScript (strict mode, fully typed at network boundary — no `any` at API client layer)
- Dark SLATE design system (`#0F172A` base, Refinery Violet `#8B5CF6` accent)
- Inter (display) + JetBrains Mono (code) fonts per Style Guide
- Generated CSS custom-property token system sourced from `assets/design-tokens/tokens.json` and emitted to `app/generated-tokens.css`
- Responsive breakpoints include 1440px wide desktop, 1024px standard desktop, and a 920px tablet/mobile collapse
- SSE live transport with `stream|poll|paused` mode diagnostics
- Signed `HttpOnly` operator session cookie for sensitive Mission Control server routes
- Windowed rendering for high-volume agent and protocol bus views
- Gateway proxy forwards real HTTP status codes (404→404, 500→500, 503→503); a CI step regenerates OpenAPI types and fails if they drift
- Electron-ready: `electron/main.ts`, `electron/preload.ts`, `electron/tray.ts`, `electron/updater.ts`; `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false`

---

## Data Systems

| System | Status | Purpose |
|--------|--------|---------|
| **PostgreSQL** | ✅ Active | Missions, events, pod assignments, LogicNodes, knowledge, audits, agent heartbeats |
| **Redis** | ✅ Active | Streams (event bus), rate limiting, idempotency keys, heartbeat telemetry |
| **Qdrant** | ✅ Active | Knowledge retrieval and indexing; PostgreSQL keyword fallback when no embedding key |
| **Milvus** | ✅ Active | Extended vector store; `MILVUS_ENABLED=true` by default |
| **Neo4j** | ✅ Active | Knowledge graph; `NEO4J_ENABLED=true` by default |
| **MinIO/S3** | ✅ Active | Artifact retention / legal-hold; `OBJECT_STORAGE_ENABLED=true` by default |

**Schema governance:** Versioned SQL migrations with checksum-tracked `schema_migrations` table (`V001_...` naming).

**Traceability Ledger:** Active runtime ledger tables are Postgres migrations under `services/orchestrator/orchestrator/migrations/` including `V005_project_audit_event_schema.sql`, `V007_llm_usage_ledger_schema.sql`, and `V009_immutable_audit.sql`.

---

## Security & Auth

### Authentication Modes

| Mode | `AUTH_MODE` value | Use case |
|------|-------------------|---------|
| API Key (default) | `api_key` | Local deployments, CI, service-to-service |
| Hybrid | `hybrid` | API key or JWT/OIDC bearer accepted |
| OIDC | `oidc` | JWT/OIDC required for mutations; API key for internal paths |

**ADR:** [`docs/ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md`](docs/ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md)

### RBAC Roles

| Role | Capabilities |
|------|-------------|
| `admin` | Full access including diagnostics |
| `mutate` | Mission mutations + operations reads |
| `read` | Read-only mission/operations access |
| `worker` | Internal pod/audit worker service calls |
| `internal` | Internal service-to-service calls |

### Security Controls

- Rate limiting: writes 120 req/min per key; reads 600 req/min (`API_READ_RATE_LIMIT_PER_MINUTE`) so Mission Control polling does not starve mission creation. Redis sliding-window, `X-RateLimit-*` headers
- `AUTH_MODE` is fail-fast in every environment (no silent fallback to `api_key`). `scripts/check_env.py` validates `AUTH_MODE` and rejects an empty `SANDBOX_WORKSPACE_HOST_ROOT=` assignment
- Idempotency: SHA256-keyed mission creation with 24h TTL
- Security headers: `X-Frame-Options DENY`, `X-Content-Type-Options nosniff`, `Referrer-Policy no-referrer`, `Permissions-Policy`
- Service API key isolation supports both shared and strict modes; condensed local defaults can share worker keys, while dedicated profiles can bind per-service and per-agent keys with `AGENT_SERVICE_KEY_MODE=strict`
- SBOM generation: `anchore/sbom-action` → `sbom.spdx.json` in CI
- Container security: all images run as non-root users
- SAST: Bandit, Trivy, gitleaks, pip-audit in `security.yml`
- Dedicated worker binding: `AGENT_BINDING` env var enforces which agent IDs a worker processes

---

## Observability

### Metrics & Alerting

| Component | Details |
|-----------|---------|
| **Prometheus** | Scrapes all services + optional data-plane adapters |
| **Grafana** | Provisioned dashboard with data-plane SLO panels |
| **Alertmanager** | Pager webhook routing for `severity: critical|high` alerts |
| **Loki + Promtail** | Centralized log aggregation |
| **Jaeger** | OTLP distributed traces (api-gateway + orchestrator + pod-worker) |
| **Structured logging** | Stdlib `JsonFormatter` in `shared_runtime/logging_config.py`; `LOG_FORMAT=json` in prod emits one JSON record per line (service, level, ts, message, trace_id) |

### Pod Worker Metrics

| Metric | Labels | Description |
|--------|--------|-------------|
| `pod_worker_concepts_extracted_total` | `pod_name`, `language` | Concept extraction counter |
| `pod_worker_extraction_latency_seconds` | `pod_name` | Extraction timing histogram |
| `pod_worker_binding_skips_total` | `pod_name`, `reason` | Agent binding skip counter |
| `pod_worker_internal_auth_rejections_total` | `pod_name` | 401/403 rejection counter |

### Data-Plane SLO Alerts

| Alert | Condition |
|-------|-----------|
| `Neo4jAdapterNotReady` | Neo4j readiness gauge = 0 |
| `ObjectStorageAdapterNotReady` | Object storage readiness gauge = 0 |
| `Neo4jMirrorWriteErrorRateHigh` | Mirror write error rate > 5% |
| `ObjectStorageMirrorWriteLatencyP95High` | p95 latency > 2s |

Runbook: [`docs/runbooks/optional_data_plane_incident_runbook.md`](docs/runbooks/optional_data_plane_incident_runbook.md)

---

## Quick Start

### Prerequisites
- Docker Desktop (Windows)
- `make` (via Git Bash or WSL, or run commands directly)
- Node.js 20+ (for Mission Control development)
- Python 3.11+ (for backend development)

### 1. Environment Setup

```bash
cp .env.example .env
# Edit .env — add provider API keys and service secrets
```

### 2. Generate Local TLS Dev Certificates

```bash
make tls-certs
```

This generates local-only PostgreSQL and Redis TLS material under `deploy/.local/postgres-certs` and `deploy/.local/redis-certs`. Private keys are intentionally gitignored and must not be committed.

### 3. Start the Stack

On Windows, `start_app.bat` is the usual path (runs `scripts/check_env.py`, then compose). It starts the **full-dedicated** topology unless you pass `--condensed`. Do not start condensed against a live full-dedicated stack — the script refuses that mismatch.

```bash
make up

# Equivalent raw command:
docker compose --env-file .env -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents up -d --build

# For the lighter condensed-worker stack:
make up-condensed
```

### 4. Verify Health

```bash
# Gateway
curl http://localhost:8100/health

# Orchestrator
curl http://localhost:8101/health

# Protocol Bus MCP
curl http://localhost:8102/health
```

Then browse to `http://localhost:3100`.

### 5. Start Monitoring Stack (optional)

```bash
make monitor-up
# Grafana: http://localhost:3001
# Prometheus: http://localhost:9090
```

### Default Host Ports

| Service | Port |
|---------|------|
| API Gateway | `8100` |
| Orchestrator | `8101` |
| Protocol Bus MCP | `8102` |
| Dashboard | `8180` |
| Mission Control | `3100` |
| Redis | `6380` |
| PostgreSQL | `5433` |
| Qdrant | `6334` |
| Grafana | `3001` |
| Prometheus | `9090` |

---

## Development

### Backend (Python / FastAPI)

```bash
# Run full test suite with coverage
make test

# Lint
make lint

# Run repo audit checks (current baseline: 23/23)
make audit

# Debug sweep
make sweep

# Run performance smoke
make perf

# Reliability qualification (1-hour sustained load)
make reliability

# Documentation validation
python scripts/validate_documentation.py
```

### Frontend (Next.js / Mission Control)

```bash
cd apps/mission-control

npm install
npm run dev        # Dev server (http://localhost:3000)
npm run build      # Production build
npm run lint       # tsc --noEmit (there is no ESLint config)
npm run test       # Vitest unit tests
npm run test:e2e   # Playwright critical-path E2E
```

### Full Make Reference

| Command | Description |
|---------|-------------|
| `make up` | Build and start the full-dedicated runtime topology |
| `make down` | Stop stack — **volumes preserved** |
| `make down-wipe` | Stop stack **and delete all volumes** (mission DB, knowledge stores, operator vault). Irreversible |
| `make up-full-dedicated` | Alias for the default full-dedicated runtime topology |
| `make down-full-dedicated` | Alias for the default full-dedicated runtime shutdown (volumes preserved) |
| `make up-condensed` | Build and start the lightweight condensed worker topology |
| `make down-condensed` | Stop the condensed worker topology — **volumes preserved** |
| `make down-condensed-wipe` | Stop the condensed topology **and delete all volumes**. Irreversible |
| `make validate` | Validate schema contracts |
| `make lint` | Ruff on backend, tests, and scripts |
| `make test` | Pytest with coverage gates (≥80% global, strict per-module floors on critical runtime files) |
| `make test-ui` | Mission Control lint + unit tests |
| `make test-ui-e2e` | Playwright E2E regression suite |
| `make test-fast` | Pytest without coverage |
| `make test-live-extended` | Live Neo4j/MinIO disruption recovery tests |
| `make eval-ai` | Focused AI delegation regression gate |
| `make demo` | Validate the Phase 18 reproducible demo mission manifest |
| `make audit` | Production checklist audit |
| `make promotion-gate` | Release promotion policy evaluation |
| `make release-evidence-verify` | Validate local release-trust evidence bundle |
| `make qualification-summary` | Export the latest qualification-gate summary evidence |
| `make dora-metrics` | Export the latest DORA metrics summary evidence |
| `make agent-keys` | Generate agent-scoped service API keys |
| `make tls-certs` | Generate local PostgreSQL and Redis dev TLS certificates |
| `make compose-validate` | Render and validate all compose overlays |
| `make openapi` | Export OpenAPI specs |
| `make predeploy` | Pre-deployment checks |
| `make backup` | PostgreSQL backup |
| `make backup-verify` | Validate backup manifest and checksum evidence |
| `make dr` | Disaster-recovery drill |
| `make perf` | Performance smoke test |
| `make reliability` | Sustained-load reliability qualification |
| `make langgraph-recovery` | Run LangGraph/PostgreSQL recovery qualification |
| `make dedicated-canary` | Run dedicated-agent canary qualification |
| `make dedicated-canary-trend` | Export dedicated-agent canary trend evidence |
| `make oidc-matrix` | Run operator-route auth matrix qualification |
| `make langgraph-v2-prototype` | Run the LangGraph-v2 prototype qualification matrix |
| `make sweep` | Debug/code sweep |
| `make monitor-up` | Start the monitoring stack |
| `make monitor-down` | Stop the monitoring stack and remove volumes |

---

## Testing & Quality Gates

| Gate | Target | Enforcement |
|------|--------|-------------|
| Global Python coverage | ≥ 80% | CI + `make test` |
| Critical module coverage | Strict per-file floors (`80%`–`100%`); `runtime.py` floor is `80%` (currently at 100% line / 99% branch) | `scripts/check_coverage_thresholds.py` |
| Production audit | 23/23 checks pass; `INF-008` closed | `scripts/production_review_audit.py` |
| Frontend lint | 0 errors | CI |
| Frontend unit tests | currently passing | `apps/mission-control` Vitest |
| Frontend E2E | currently passing | Playwright critical-path regression suite |
| Bandit SAST | 0 high/crit | `security.yml` |
| Trivy container scan | 0 critical | `security.yml` |
| gitleaks secret scan | 0 findings | `security.yml` |
| pip-audit SCA | 0 known vulns | `security.yml` |
| Release attestation | signed provenance | CI release gate |
| OpenAPI type drift | 0 drift | CI regenerates types; fails on divergence |

The main CI workflow must remain valid GitHub Actions YAML before any gate can run. Artifact download retries are not configured with unsupported step keys; if retry behavior is needed, it should be implemented through an explicit retry action or shell retry wrapper.

### Reproducible Demo Missions

Phase 18 demo coverage is defined in `scripts/demo_missions.py`. `make demo`
performs the CI-safe manifest validation and writes
`docs/evidence/phase18_demo_missions_latest.json`. A live stack run uses:

```bash
python scripts/demo_missions.py --live --gateway-base-url http://localhost:8100
```

The live run is the launch-demo proof point. It requires a running stack and
provider-key configuration when generated LLM output is part of the claim.

**Validation snapshot (2026-08-17):** Live BUILD_NEW evidence includes Go `mission-f8a5accf` (`docs/evidence/s1_01_live_generation_go_20260811.json`), chat-driven PyQt6 `mission-e42fd7e2`, and stdlib Snake `mission-911a6b3f`. Honesty/QC follow-up is on `main` (PR #460). PM SOW, Chat ZIP import, file-tree delivery, quoted-vs-actual cost, and `sandbox-runner` are on `main` (PR #462). Coverage gates (line ≥80%, branch ≥70%, privilege-path floors) landed in PR #463 (`dd13785`). Full-dedicated stack rebuilt 2026-08-17; `sandbox-runner` is healthy. Older Phase 13 / non-ASCII smokes remain on disk. `production_review_audit.py` 23/23 is a hygiene check, not a release certificate. Still open: PORT/transform live proof through Chat SOW, failure injection, provider fallback, and EDCP live-bus.

---

## Configuration

### Key Environment Variables

```bash
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<secret>
POSTGRES_DB=ulr

# Redis
REDIS_URL=rediss://:password@redis:6380/0?ssl_cert_reqs=required&ssl_ca_certs=/run/redis-certs/ca.crt

# API Authentication — generate all keys with: openssl rand -hex 32
# REQUIRED: no trivial or blank values in production
ORCHESTRATOR_ADMIN_API_KEY=<generate with openssl rand -hex 32>
ORCHESTRATOR_READONLY_API_KEY=<generate with openssl rand -hex 32>
ORCHESTRATOR_API_KEYS=<your-operator-key>=mutate,read
INTERNAL_SERVICE_API_KEY=<generate with openssl rand -hex 32>

# Mission Control local operator session (apps/mission-control)
OPERATOR_SESSION_BYPASS=true
MISSION_CONTROL_BYPASS_AUTH=true      # legacy alias for OPERATOR_SESSION_BYPASS
MISSION_CONTROL_ADMIN_KEY=<optional only when bypass is false>
MISSION_CONTROL_SESSION_SECRET=<optional only when bypass is false>
MISSION_CONTROL_SESSION_TTL_SECONDS=28800
MISSION_CONTROL_SESSION_SECURE=false

# Mission Control durable review approval validation (apps/mission-control)
ORCHESTRATOR_INTERNAL_BASE_URL=http://localhost:8101
APPROVAL_HMAC_SECRET=<generate with openssl rand -hex 32>
APPROVAL_TTL_SECONDS=86400

# Mission Control vault endpoint break-glass key for scripted /api/vault access (optional)
VAULT_ADMIN_KEY=<generate with openssl rand -hex 32>
AUTH_MODE=api_key                  # api_key | hybrid | oidc

# Knowledge embeddings
# UI setup slot: KNOWLEDGE-EMBEDDING-API-KEY in Mission Control Settings
# Runtime env consumed by orchestrator containers:
KNOWLEDGE_EMBEDDING_PROVIDER=gemini
KNOWLEDGE_EMBEDDING_API_KEY=<same key or dedicated embedding key>
KNOWLEDGE_EMBEDDING_MODEL=gemini-embedding-001
KNOWLEDGE_EMBEDDING_TIMEOUT_SECONDS=10.0

# OIDC (when AUTH_MODE=hybrid|oidc)
OIDC_ISSUER_URL=https://your-idp/.well-known/openid-configuration
OIDC_AUDIENCE=holygrail-api

# Lifecycle
MISSION_FLOW_V2_ENABLED=true       # shipped default runtime path
LANGGRAPH_ENABLED=false            # optional alternative lifecycle engine
LANGGRAPH_CHECKPOINTER=none        # none | memory | postgres
LANGGRAPH_FAIL_OPEN=true           # defaults to true outside prod; set to false in staging/prod to avoid masking engine failures

# Feature Flags
QDRANT_ENABLED=true
NEO4J_ENABLED=true
OBJECT_STORAGE_ENABLED=true
MILVUS_ENABLED=true

# Observability
OTEL_TRACING_ENABLED=true
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://jaeger:4318/v1/traces

# LLM Providers
LLM_PROVIDER=gemini                # gemini default; UI model choices: gpt-5.5 | claude-opus-4-8 | gemini-3.7-flash
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-3.7-flash
GEMINI_THINKING_LEVEL=high
OPENAI_MODEL=gpt-5.5
OPENAI_REASONING_EFFORT=high
ANTHROPIC_MODEL=claude-opus-4-8

# Runtime QC (compose defaults)
RQCA_AGENT_ENABLED=true
RQCA_ENFORCEMENT_ENABLED=true      # FAIL blocks; started_only / syntax-only / DRY_RUN do not
# Leave SANDBOX_WORKSPACE_HOST_ROOT unset so Compose can default it.
# An empty KEY= assignment remounts an empty host directory.

# Agent Scaling (experimental)
AGENT_SCALING_ENABLED=false
AGENT_SCALING_MAX_INSTANCES=4
AGENT_SCALING_ITEMS_PER_INSTANCE=3

# Pod Worker
POD_NAME=podA                      # podA | podB | podC | podD
SUPPORTED_LANGUAGES=python,typescript,javascript,ruby,php
AGENT_BINDING=                     # e.g. AGENT-14-PYTHON for dedicated mode
AGENT_SERVICE_KEY_MODE=shared      # shared | strict
MCP_API_KEY=mcp-local-key
```

Full reference: [`.env.example`](.env.example)

---

## Deployment Profiles

### Default (Full Dedicated Runtime)

```bash
make up

# Equivalent raw compose command
docker compose --env-file .env -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents up -d --build
```

Starts the full isolated 41-agent runtime topology by default, including the full data plane (PostgreSQL, Redis, Qdrant, Milvus, Neo4j, MinIO) — all backend adapters are on by default.

### Condensed Workers

```bash
make up-condensed

# Equivalent raw compose command
docker compose --env-file .env -f deploy/docker-compose.yaml up -d --build
```

All pod work runs through shared pod-worker instances. Suitable for lightweight development.

### Dedicated Agents

```bash
docker compose --env-file .env -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents up -d --build
```

Spawns dedicated manager-worker containers per pod with `AGENT_BINDING` enforcement. Each worker only processes missions assigned to its bound agent ID.

**ADR:** [`docs/ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md`](docs/ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md)

### Full Dedicated Runtime

```bash
make up-full-dedicated

# Equivalent raw compose command
docker compose --env-file .env -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents up -d --build
```

Alias for the default startup topology. Adds dedicated `agent-runtime` containers for PM, CEO, support, and pod-audit roles plus dedicated specialist workers for all 20 routed language keys, including Go, Haskell, and OCaml. The overlay provisions the full isolated 41-agent runtime topology on top of the shared baseline stack.

### Monitoring Stack

```bash
docker compose -f deploy/docker-compose.monitoring.yaml up -d
```

Starts Prometheus, Grafana, Loki, Promtail, Alertmanager, and Jaeger.

### Core Data Plane & Internal Databases

Milvus, Neo4j, and MinIO containers start automatically as part of the base compose stack and their application integrations are **on by default**. Disable any of them via `MILVUS_ENABLED=false`, `NEO4J_ENABLED=false`, or `OBJECT_STORAGE_ENABLED=false` in your `.env` file if you want a lighter local stack.

---

## Repository Layout

```
theFactory/
├── apps/
│   └── mission-control/          # Next.js 16 operator console
├── services/
│   ├── api-gateway/              # Public API, SSE transport, auth
│   ├── orchestrator/             # Mission state machine, agent registry
│   ├── pod-worker/               # Language extraction + LogicNode workers
│   ├── audit-worker/             # Verification stream processor
│   ├── protocol-bus-mcp/         # 6-protocol typed message bus
│   ├── dashboard/                # Lightweight ops status UI
│   └── agent-runtime/            # Full dedicated single-agent runtime
├── schemas/                      # Event envelope, LogicNode, RIR contracts
├── protocol/                     # Protocol bus topic catalog
├── ledger/                       # Traceability ledger schema
├── assets/design-tokens/         # CSS design token source of truth
├── deploy/                       # Docker Compose stacks + monitoring config
├── docs/                         # Canonical live documentation
│   ├── ADR_*.md                  # Architectural Decision Records
│   ├── api/                      # API entry point and interactive-doc guidance
│   ├── user/                     # Operator/tutorial documentation
│   ├── evidence/                 # Qualification and release evidence
│   ├── runbooks/                 # Incident and operational runbooks
│   └── archive/                  # Superseded and source-material documentation
├── scripts/                      # Audit, validation, DR, perf, sweep, and docs maintenance tools
└── tests/                        # Backend, security, and script tests
```

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [`docs/00_PRODUCT_OVERVIEW.md`](docs/00_PRODUCT_OVERVIEW.md) | Five-minute product orientation |
| [`docs/WHAT_THEFACTORY_IS_AND_IS_NOT.md`](docs/WHAT_THEFACTORY_IS_AND_IS_NOT.md) | Canonical positioning and scope boundaries |
| [`docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md`](docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md) | **Governing verdict document** — Implemented / Superseded / Deferred per design area. Outranks the archived design corpus |
| [`docs/MISSION_TAXONOMY.md`](docs/MISSION_TAXONOMY.md) | Mission types, depth modes, output modes, and data classifications — what each value actually does, and which are inert |
| [`docs/DESIGN_TRACEABILITY.md`](docs/DESIGN_TRACEABILITY.md) | Design document 01–64 → status → implementing module → evidence |
| [`docs/LOGICNODE_SCHEMA.md`](docs/LOGICNODE_SCHEMA.md) | LogicNode schema v2 and the two Refined-IR projection paths (`ast_v1` vs `templated_v1`) |
| [`docs/PROTOCOL_ENVELOPES.md`](docs/PROTOCOL_ENVELOPES.md) | The two envelope transports, their priority vocabularies, and the correlation contract — **read before writing a bus consumer** |
| [`docs/DEPENDENCY_ABSORPTION_DOCTRINE.md`](docs/DEPENDENCY_ABSORPTION_DOCTRINE.md) | Dependency absorption doctrine, decision hierarchy, safety blocks |
| [`docs/APPLICATION_INTELLIGENCE_MAP.md`](docs/APPLICATION_INTELLIGENCE_MAP.md) | Application Intelligence Map artifact and consumers |
| [`docs/RUNTIME_QC_AND_TEST_ENVIRONMENTS.md`](docs/RUNTIME_QC_AND_TEST_ENVIRONMENTS.md) | Ephemeral test environments and AI runtime QC |
| [`docs/SENSITIVE_CODE_HANDLING_POLICY.md`](docs/SENSITIVE_CODE_HANDLING_POLICY.md) | Source code classification, provider routing, redaction |
| [`docs/SCHEMA_REGISTRY_AND_VERSIONING.md`](docs/SCHEMA_REGISTRY_AND_VERSIONING.md) | Schema registry, versioning rules, compatibility |
| [`docs/LICENSE_STRATEGY.md`](docs/LICENSE_STRATEGY.md) | Dual AGPL-3.0/Commercial license strategy and CLA requirement |
| [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) | Current shipped defaults, known gaps, and validation snapshot |
| [`docs/WORK_QUEUE.md`](docs/WORK_QUEUE.md) | Ordered next work — start here for “what is actually next” |
| [`docs/CURRENT_TODO.md`](docs/CURRENT_TODO.md) | Session-level current status and active queue |
| [`docs/HANDOFF_CURRENT.md`](docs/HANDOFF_CURRENT.md) | Cold-start handoff for maintainers and coding agents |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System architecture and topology |
| [`docs/ARCHITECTURE_DIAGRAMS.md`](docs/ARCHITECTURE_DIAGRAMS.md) | System, runtime, deployment, and multi-agent diagrams |
| [`docs/ARCHITECTURE_DATA_FLOWS.md`](docs/ARCHITECTURE_DATA_FLOWS.md) | Mission, approval, artifact, identity, and telemetry flows |
| [`docs/REPOSITORY_BUILD_MAP_2026-06-13.md`](docs/REPOSITORY_BUILD_MAP_2026-06-13.md) | Generated complete repository file and folder map |
| [`docs/DOCUMENTATION_STANDARDS.md`](docs/DOCUMENTATION_STANDARDS.md) | Documentation quality, versioning, and archive rules |
| [`docs/DIAGRAM_STANDARDS.md`](docs/DIAGRAM_STANDARDS.md) | Enterprise diagram set and standards basis |
| [`docs/DOCUMENTATION_INDEX.md`](docs/DOCUMENTATION_INDEX.md) | Full documentation map |
| [`docs/api/README.md`](docs/api/README.md) | API entry point, Swagger locations, and versioned OpenAPI files |
| [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md) | Operational procedures |
| [`docs/DEPLOYMENT_DR_PLAYBOOK.md`](docs/DEPLOYMENT_DR_PLAYBOOK.md) | Deployment and disaster recovery |
| [`docs/OBSERVABILITY_STACK.md`](docs/OBSERVABILITY_STACK.md) | Monitoring and alerting guide |
| [`docs/TESTING_QUALITY_GATES.md`](docs/TESTING_QUALITY_GATES.md) | Test strategy and coverage gates |
| [`docs/RELEASE_TRUST_PROMOTION_GATE.md`](docs/RELEASE_TRUST_PROMOTION_GATE.md) | Release attestation policy |
| [`docs/AGENT_SERVICE_KEY_ISOLATION.md`](docs/AGENT_SERVICE_KEY_ISOLATION.md) | Per-agent worker key isolation and remaining security work |
| [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md) | Day-to-day engineering workflow |
| [`docs/DEVELOPER_ONBOARDING_GUIDE.md`](docs/DEVELOPER_ONBOARDING_GUIDE.md) | New developer onboarding |
| [`docs/user/GETTING_STARTED.md`](docs/user/GETTING_STARTED.md) | First-success local startup and operator onboarding |
| [`docs/user/OPERATOR_GUIDE.md`](docs/user/OPERATOR_GUIDE.md) | Mission Control operator instructions |
| [`docs/API_INTEGRATION_GUIDE.md`](docs/API_INTEGRATION_GUIDE.md) | API integration reference |
| [`docs/DATA_CLASSIFICATION_POLICY.md`](docs/DATA_CLASSIFICATION_POLICY.md) | Data classification policy |
| [`docs/archive/README.md`](docs/archive/README.md) | Archive policy and archived source-material index |
| [`docs/ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md`](docs/ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md) | Agent topology ADR |
| [`docs/ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md`](docs/ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md) | Security model ADR |
| [`AGENTS.md`](AGENTS.md) | AI coding agent developer guidelines |
| [`CHANGELOG.md`](CHANGELOG.md) | Full change history |

---

## Current Status

Current state (2026-08-17): **active development, feature-complete against the
v1.3 mission-pipeline scope.** Infrastructure, security, the protocol bus, the
data plane, the operator UI, and the test surface are mature and CI-verified.
The semantic engine is partially realised and honestly labelled. Live BUILD_NEW
missions have reached `COMPLETE`. The system is **not production-ready**.

| Maturity Area | Status | Status Details |
| --- | --- | --- |
| **Core Software Engine** | **Complete for v1.3 scope** | Mission Flow v2 default, 41-agent registry, 6 Redis protocols, real AST for Python/JS/TS/Java, regex parsers for Go/Haskell/OCaml/Julia, Helm & GitHub Actions exporters, Gemini 3.7 Flash default route. |
| **Semantic depth** | **Partially realised; remainder scoped out** | Real AST-recovered types, op streams, purity, and behavioural equivalence — type recovery for **Python, Java, and Haskell**. Other languages emit honestly-labelled `templated_v1` output. BUILD_NEW does not extract LogicNodes. See the [reconciliation ADR](docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md). |
| **Live mission evidence** | **S1-01 captured; matrix still open** | Go `mission-f8a5accf`, chat PyQt6 `mission-e42fd7e2`, Snake `mission-911a6b3f`. Still owed: PORT/transform, failure injection, provider fallback. EDCP is in code, off, not live-bus proven. |
| **Runtime QC honesty** | **Shipped (PR #460)** | Generated tests are the sandbox command. `started_only` / syntax-only are ADVISORY. Unmet offline deps are DRY_RUN. Compose default `RQCA_ENFORCEMENT_ENABLED=true`. |
| **Audit & Quality Standards** | **Hygiene green, not a release certificate** | `production_review_audit.py` is a static file/string check. Coverage floor 80%; `runtime.py` 100% line / 99% branch. Mission Control 146 Vitest tests. Do not cite 23/23 or “0 SAST findings” as release evidence. |
| **Desktop Packaging Path** | **Web path is primary** | `start_app.bat` launches Docker + browser. Electron uses `/api/gateway`. Installer signing and uninstall hooks remain open. |
| **CI & Release Pipeline** | **Mostly green** | Lint/test, CodeQL, Docker builds, and the promotion gate run in Actions. Bandit can still fail on pre-existing findings; Dependabot currently reports open high-severity alerts. |

---


> **Local-first design:** theFactory is engineered to run fully offline with no external platform dependencies. All secrets stay in `.env` and local vault endpoints. Do not commit credentials or provider keys.
