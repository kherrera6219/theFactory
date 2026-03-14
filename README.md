<div align="center">

# 🏭 theFactory

**HolyGrail Multi-Agent Software Refinery**

*A local-first AI orchestration platform with a real multi-service control plane, a 35-agent registry, and a condensed default runtime for mission intake, delegation, language processing, and audit handoff.*

[![CI](https://github.com/holygrail/theFactory/actions/workflows/ci.yml/badge.svg)](https://github.com/holygrail/theFactory/actions/workflows/ci.yml)
[![Security](https://github.com/holygrail/theFactory/actions/workflows/security.yml/badge.svg)](https://github.com/holygrail/theFactory/actions/workflows/security.yml)
[![Coverage](https://img.shields.io/badge/coverage-86%25-brightgreen)](docs/evidence/)
[![Audit](https://img.shields.io/badge/production%20audit-17%2F17-brightgreen)](scripts/production_review_audit.py)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![Next.js](https://img.shields.io/badge/Next.js-16-black)](apps/mission-control/package.json)
[![License](https://img.shields.io/badge/license-proprietary-lightgrey)](#)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Implementation Status](docs/IMPLEMENTATION_STATUS.md)
- [Architecture](#architecture)
- [35-Agent Runtime Model](#35-agent-runtime-model)
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

## Overview

**theFactory** is the HolyGrail runtime implementation of a 35-agent multi-agent software refinery. It is designed as a Windows-friendly, Docker-based monorepo that provides:

Current implementation status: [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md)

- **End-to-end mission orchestration** — intake, delegation, specialist processing, verification, and completion
- **Semantic bus architecture** — six-protocol Redis Streams event plane (`alpha`/`beta`/`delta`/`sigma`/`omega`/`rho`)
- **35-agent control model** — canonical registry across interface, executive, support, and pod-specialist tiers; default runtime is condensed rather than fully isolated per-agent
- **Language-aware code analysis** — regex-based extraction engine for 20 languages across 4 pod groups
- **Multiple lifecycle engines** — shipped defaults currently enable mission-flow v2, with optional LangGraph and legacy fallback paths
- **Full production observability** — Prometheus, Grafana, Loki, Jaeger OTLP, Alertmanager
- **Enterprise-grade security** — dual-mode auth (API key + JWT/OIDC), per-role key isolation, SAST/SCA/secret scanning in CI

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
│  LangGraph StateGraph · Mission lifecycle · Pod assignment      │
│  35-agent registry · Operations APIs · Qdrant/Neo4j/S3 plane   │
└──┬──────┬──────────┬───────────────┬───────────────────────────┘
   │      │ Redis    │               │
   │   Streams   ┌──▼────────────────▼──┐
   │      │      │   SEMANTIC BUS MCP    │
   │      │      │   :8102               │
   │      │      │   6-protocol routing  │
   │      │      └───────────────────────┘
   │      │
┌──▼──────▼──────────────────────────────────────────────────────┐
│                      POD WORKERS                               │
│  Pod A  (Python/JS/Ruby/PHP)  — Dynamic Languages              │
│  Pod B  (C/C++/Rust/Zig)      — Systems Languages              │
│  Pod C  (Java/C#/Scala/Kotlin)— Enterprise Languages           │
│  Pod D  (MATLAB/R/Julia/Mathematica) — Mathematical Languages  │
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
  Neo4j             ─ optional graph adapter (feature-flagged)
  MinIO/S3          ─ optional object storage (legal-hold, 90-day retention)

OBSERVABILITY PLANE
  Prometheus · Grafana · Loki · Promtail · Alertmanager · Jaeger OTLP
```

### Smelt-Cycle: 7-Phase Mission Progression

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

## 35-Agent Runtime Model

The orchestrator maintains a canonical registry of **35 specialist agents** organized across four tiers:

| Tier | Agents | Role |
|------|--------|------|
| **Interface** | AGENT-01-PM | Project Manager — mission intake and PM→CEO handoff |
| **Executive** | AGENT-02-CEO | Chief Executor — mission delegation to pod managers |
| **Support Ring** | AGENT-03 through AGENT-11 | Broker, Accountant, Security, IS, VC, Compliance, HW, Tester, Deploy |
| **Pod A** (Dynamic) | Manager, Audit, Python, JavaScript/TypeScript, Ruby, PHP Specialists | Dynamic language refinery |
| **Pod B** (Systems) | Manager, Audit, C, C++, Rust, Zig Specialists | Systems language refinery |
| **Pod C** (Enterprise) | Manager, Audit, Java, C#, Scala, Kotlin Specialists | Enterprise language refinery |
| **Pod D** (Mathematical) | Manager, Audit, MATLAB, R, Julia, Mathematica Specialists | Mathematical language refinery |

### Agent Runtime State

Each agent exposes:

```json
{
  "agent_id": "AGENT-01-PM",
  "state": "IDLE | ACTIVE | RUNNING | VERIFYING | ERROR | PAUSED",
  "queue_depth": 0,
  "active_mission_id": null,
  "llm_recommendation": {
    "provider": "openai",
    "model": "gpt-4o",
    "thinking": "standard",
    "fallback_model": "gpt-4o-mini"
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

### LLM Provider Assignment (35 Agents)

| Provider | Count | Key ENV Variables |
|----------|-------|-------------------|
| **Anthropic** | 12 agents | `ANTHROPIC_API_KEY_ARCH`, `ANTHROPIC_API_KEY_PY`, etc. |
| **OpenAI** | 14 agents | `OPENAI_API_KEY_CEO`, `OPENAI_API_KEY_CTO`, etc. |
| **Google Gemini** | 9 agents | `GOOGLE_API_KEY_MATLAB`, `GOOGLE_API_KEY_JULIA`, etc. |

Full matrix: [`docs/AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md`](docs/AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md)

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

Pod workers run a static-analysis extraction engine that detects computational concepts in source code before LogicNode creation. No AST parsing or LLM calls required for this phase.

| Pod | Languages | Concept Prefix | Patterns |
|-----|-----------|---------------|---------|
| A — Dynamic | Python, JavaScript/TypeScript, Ruby, PHP | `DYN-` | ~68 |
| B — Systems | C, C++, Rust, Zig | `SYS-` | ~54 |
| C — Enterprise | Java, C#, Scala, Kotlin | `ENT-` | ~35 |
| D — Mathematical | MATLAB, R, Julia, Mathematica | `MATH-` | ~75 |
| **Total** | **16 languages** (TypeScript aliases to JavaScript specialist) | | **232 patterns** |

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
| `semantic-bus-mcp` | 8102 | FastAPI | 6-protocol semantic bus with DLQ |
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
| `GET` | `/v1/missions/{id}/events` | reader+ | Mission event stream |
| `POST` | `/v1/missions/{id}/state` | mutate/admin | Emit state transition event |
| `GET` | `/v1/missions/{id}/knowledge-graph` | reader+ | Neo4j graph (feature-flagged) |
| `GET` | `/v1/missions/{id}/audit-artifacts` | reader+ | Object storage artifacts (feature-flagged) |

#### Operations
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/operations/summary` | Runtime health summary |
| `GET` | `/v1/operations/agents` | All 35 agent runtime states |
| `GET` | `/v1/operations/agent-integrations` | Agent protocol/LLM/persona profiles |

#### Live Transport
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/stream/state` | SSE stream with `mission_id` filter, `Last-Event-ID` resume, keepalive |

### Semantic Bus MCP (`http://localhost:8102`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/send` | Send validated bus message (alpha/beta/delta/sigma/omega/rho) |
| `GET` | `/dlq` | Inspect dead-letter queue |
| `GET` | `/health` · `/readyz` · `/metrics` | Standard probes |

### OpenAPI Exports
- [`docs/openapi/api-gateway.v1.json`](docs/openapi/api-gateway.v1.json)
- [`docs/openapi/orchestrator.v1.json`](docs/openapi/orchestrator.v1.json)

---

## Mission Control UI

**Access:**
- Docker stack: `http://localhost:3100`
- Direct dev server: `http://localhost:3000` (`npm run dev`)

**Features:**

| View | Description |
|------|-------------|
| Dashboard | Runtime-wide health, mission counts, agent status summary |
| Missions | Mission table with lifecycle state and phase stepper |
| Mission Detail | Live event timeline, Smelt-cycle phase stepper (SSE-driven), chain-of-command |
| Agents | 35-agent roster grid with persona drill-down |
| Semantic Bus | Live message stream with windowed rendering |
| Operations | Internal health, readiness, and metrics |
| Builder | Repository intake (4-step: import → file select → diff review/apply gate → mission config) |
| Settings / Vault | Provider key management, environment config |

**Technology:**
- Next.js 16 App Router, TypeScript (strict mode)
- Dark SLATE design system (`#0F172A` base, Refinery Violet `#8B5CF6` accent)
- Inter (display) + JetBrains Mono (code) fonts per Style Guide
- 31-token CSS variable system driven by `generated-tokens.css`
- Responsive: 1440px (wide desktop) + 1024px (standard desktop) + 768px (tablet)
- SSE live transport with `stream|poll|paused` mode diagnostics
- Windowed rendering for high-volume agent and semantic bus views

---

## Data Systems

| System | Status | Purpose |
|--------|--------|---------|
| **PostgreSQL** | ✅ Active | Missions, events, pod assignments, LogicNodes, knowledge, audits, agent heartbeats |
| **Redis** | ✅ Active | Streams (event bus), rate limiting, idempotency keys, heartbeat telemetry |
| **Qdrant** | ✅ Active | Live knowledge retrieval and indexing (PostgreSQL fallback) |
| **Milvus** | ⚙️ Feature-flagged | Optional vector-store path for extended knowledge retrieval |
| **Neo4j** | ⚙️ Feature-flagged | Relationship-heavy mission/audit graph queries |
| **MinIO/S3** | ⚙️ Feature-flagged | Immutable artifact retention, legal-hold, 90-day policy |

**Schema governance:** Versioned SQL migrations with checksum-tracked `schema_migrations` table (`V001_...` naming).

**Traceability Ledger:** `ledger/schema.sql` — artifacts, sources, custody chain, audit runs tables.

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

- Rate limiting: 120 req/min per key (Redis sliding-window), `X-RateLimit-*` headers
- Idempotency: SHA256-keyed mission creation with 24h TTL
- Security headers: `X-Frame-Options DENY`, `X-Content-Type-Options nosniff`, `Referrer-Policy no-referrer`, `Permissions-Policy`
- Per-service API key isolation: each worker has its own `SERVICE_API_KEY`
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

### 2. Start Core Stack

```bash
docker compose -f deploy/docker-compose.yaml up -d --build
```

### 3. Verify Health

```bash
# Gateway
curl http://localhost:8100/health

# Orchestrator
curl http://localhost:8101/health

# Semantic Bus MCP
curl http://localhost:8102/health

# Mission Control UI
open http://localhost:3100
```

### 4. Start Monitoring Stack (optional)

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
| Semantic Bus MCP | `8102` |
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

# Run production audit (17/17 checks)
make audit

# Debug sweep
make sweep

# Run performance smoke
make perf

# Reliability qualification (1-hour sustained load)
make reliability
```

### Frontend (Next.js / Mission Control)

```bash
cd apps/mission-control

npm install
npm run dev        # Dev server (http://localhost:3000)
npm run build      # Production build
npm run lint       # ESLint
npm run test       # Vitest unit tests
npm run test:e2e   # Playwright critical-path E2E
```

### Full Make Reference

| Command | Description |
|---------|-------------|
| `make up` | Build and start core stack |
| `make down` | Stop stack and remove volumes |
| `make validate` | Validate schema contracts |
| `make lint` | Ruff on backend, tests, and scripts |
| `make test` | Pytest with coverage gates (≥80% global, 100% core) |
| `make test-ui` | Mission Control lint + unit tests |
| `make test-ui-e2e` | Playwright E2E regression suite |
| `make test-fast` | Pytest without coverage |
| `make test-live-extended` | Live Neo4j/MinIO disruption recovery tests |
| `make audit` | Production checklist audit |
| `make promotion-gate` | Release promotion policy evaluation |
| `make openapi` | Export OpenAPI specs |
| `make predeploy` | Pre-deployment checks |
| `make backup` | PostgreSQL backup |
| `make dr` | Disaster-recovery drill |
| `make perf` | Performance smoke test |
| `make reliability` | Sustained-load reliability qualification |
| `make sweep` | Debug/code sweep |
| `make monitor-up/down` | Start/stop monitoring stack |

---

## Testing & Quality Gates

| Gate | Target | Enforcement |
|------|--------|-------------|
| Global Python coverage | ≥ 80% | CI + `make test` |
| Core module coverage | 100% | `scripts/check_coverage_thresholds.py` |
| Production audit | 13/13 checks | `scripts/production_review_audit.py` |
| Frontend lint | 0 errors | CI |
| Frontend unit tests | currently passing | `apps/mission-control` Vitest |
| Frontend E2E | currently passing | Playwright critical-path regression suite |
| Bandit SAST | 0 high/crit | `security.yml` |
| Trivy container scan | 0 critical | `security.yml` |
| gitleaks secret scan | 0 findings | `security.yml` |
| pip-audit SCA | 0 known vulns | `security.yml` |
| Release attestation | signed provenance | CI release gate |

**Current status (2026-03-13):** backend `python -m pytest -q` is green and Mission Control Playwright is green. See [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) for the remaining product-completion gaps.

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

# API Authentication
ORCHESTRATOR_ADMIN_API_KEY=<admin-key>
ORCHESTRATOR_READONLY_API_KEY=<viewer-key>
ORCHESTRATOR_API_KEYS=operator-key=mutate,read
INTERNAL_SERVICE_API_KEY=<internal-key>
AUTH_MODE=api_key                  # api_key | hybrid | oidc

# OIDC (when AUTH_MODE=hybrid|oidc)
OIDC_ISSUER_URL=https://your-idp/.well-known/openid-configuration
OIDC_AUDIENCE=holygrail-api

# Lifecycle
MISSION_FLOW_V2_ENABLED=true       # shipped default runtime path
LANGGRAPH_ENABLED=false            # optional alternative lifecycle engine
LANGGRAPH_CHECKPOINTER=none        # none | memory | postgres
LANGGRAPH_FAIL_OPEN=true

# Feature Flags
QDRANT_ENABLED=true
NEO4J_ENABLED=false
OBJECT_STORAGE_ENABLED=false
MILVUS_ENABLED=false

# Observability
OTEL_TRACING_ENABLED=true
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://jaeger:4318/v1/traces

# LLM Providers
LLM_PROVIDER=offline               # offline | openai | anthropic | gemini
ANTHROPIC_API_KEY_ARCH=sk-ant-...
OPENAI_API_KEY_CEO=sk-...
GOOGLE_API_KEY_MATLAB=...

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

### Default (Condensed Workers)

```bash
docker compose -f deploy/docker-compose.yaml up -d --build
```

All pod work runs through shared pod-worker instances. Suitable for development and standard production.

### Dedicated Agents

```bash
docker compose -f deploy/docker-compose.yaml --profile dedicated-agents up -d --build
```

Spawns dedicated manager-worker containers per pod with `AGENT_BINDING` enforcement. Each worker only processes missions assigned to its bound agent ID.

**ADR:** [`docs/ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md`](docs/ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md)

### Full Dedicated Runtime

```bash
docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents up -d --build
```

Adds dedicated `agent-runtime` containers for PM, CEO, support, pod-audit, and specialist roles. This profile enables strict per-agent bindings and the full isolated 35-agent runtime topology.

### Monitoring Stack

```bash
docker compose -f deploy/docker-compose.monitoring.yaml up -d
```

Starts Prometheus, Grafana, Loki, Promtail, Alertmanager, and Jaeger.

### Optional Data Plane

```bash
docker compose -f deploy/docker-compose.yaml --profile extended-data-plane up -d
```

Adds Milvus, MinIO object storage, and Neo4j connection support for feature-flagged data-plane adapters.

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
│   ├── semantic-bus-mcp/         # 6-protocol semantic bus
│   ├── dashboard/                # Lightweight ops status UI
│   └── agent-runtime/            # Full dedicated single-agent runtime
├── schemas/                      # Event envelope, LogicNode, RIR contracts
├── protocol/                     # Semantic bus topic catalog
├── ledger/                       # Traceability ledger schema
├── assets/design-tokens/         # CSS design token source of truth
├── deploy/                       # Docker Compose stacks + monitoring config
├── docs/                         # Architecture, ADRs, runbooks, evidence
│   ├── ADR_*.md                  # Architectural Decision Records
│   ├── evidence/                 # Phase validation evidence (through phase 39)
│   └── runbooks/                 # Incident and operational runbooks
├── scripts/                      # Audit, validation, DR, perf, sweep tools
└── tests/                        # Backend, security, and script tests
```

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) | Current shipped defaults, known gaps, and validation snapshot |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System architecture and topology |
| [`docs/ARCHITECTURE_DIAGRAMS.md`](docs/ARCHITECTURE_DIAGRAMS.md) | System, runtime, deployment, and multi-agent diagrams |
| [`docs/DIAGRAM_STANDARDS.md`](docs/DIAGRAM_STANDARDS.md) | Enterprise diagram set and standards basis |
| [`docs/DOCUMENTATION_INDEX.md`](docs/DOCUMENTATION_INDEX.md) | Full documentation map |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Product roadmap |
| [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md) | Operational procedures |
| [`docs/DEPLOYMENT_DR_PLAYBOOK.md`](docs/DEPLOYMENT_DR_PLAYBOOK.md) | Deployment and disaster recovery |
| [`docs/OBSERVABILITY_STACK.md`](docs/OBSERVABILITY_STACK.md) | Monitoring and alerting guide |
| [`docs/TESTING_QUALITY_GATES.md`](docs/TESTING_QUALITY_GATES.md) | Test strategy and coverage gates |
| [`docs/RELEASE_TRUST_PROMOTION_GATE.md`](docs/RELEASE_TRUST_PROMOTION_GATE.md) | Release attestation policy |
| [`docs/AGENT_SERVICE_KEY_ISOLATION.md`](docs/AGENT_SERVICE_KEY_ISOLATION.md) | Per-agent worker key isolation and remaining security work |
| [`docs/GAP_ANALYSIS.md`](docs/GAP_ANALYSIS.md) | Gap analysis and disposition |
| [`docs/DEVELOPER_ONBOARDING_GUIDE.md`](docs/DEVELOPER_ONBOARDING_GUIDE.md) | New developer onboarding |
| [`docs/API_INTEGRATION_GUIDE.md`](docs/API_INTEGRATION_GUIDE.md) | API integration reference |
| [`docs/DATA_CLASSIFICATION_POLICY.md`](docs/DATA_CLASSIFICATION_POLICY.md) | Data classification policy |
| [`docs/SMELT_CYCLE_RUNTIME_MAPPING_2026-03-04.md`](docs/SMELT_CYCLE_RUNTIME_MAPPING_2026-03-04.md) | 7-phase smelt-cycle runtime mapping |
| [`docs/ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md`](docs/ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md) | Agent topology ADR |
| [`docs/ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md`](docs/ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md) | Security model ADR |
| [`AGENTS.md`](AGENTS.md) | AI coding agent developer guidelines |
| [`CHANGELOG.md`](CHANGELOG.md) | Full change history |

---

## Current Status

**The codebase is substantial and mostly wired, but it is not fully converged today. The shipped defaults, tests, UI assertions, and some dated docs still need reconciliation.**

| Domain | Status |
|--------|--------|
| Infrastructure & DevOps | ✅ Complete |
| Security & Auth | ✅ Complete |
| Observability | ✅ Complete |
| Testing & CI | ✅ Backend pytest and Mission Control Playwright are green |
| Data Systems | ⚠️ Core path complete, optional-adapter/status docs still lag |
| Mission Control UI | ⚠️ Real operator UI, but builder/repo flows remain partially synthetic |
| Language Extraction Engine | ✅ Complete |
| Mission Lifecycle | ⚠️ Multiple engines implemented; queue-first create/read behavior remains eventually consistent |
| CEO→Pod Delegation Chain | ✅ Complete baseline |
| LLM API Call Wiring | ✅ Complete (provider-aware routing with fallback) |

**Current completion work:**
- Decide whether mission creation should remain queue-first/eventually consistent or move to read-after-write consistency
- Replace synthetic builder/repo-review behavior with a true repository diff/apply workflow
- Align audit/data-plane docs and Mission Control surfaces with the shipped implementation
- Expand or reduce language-routing claims so docs and runtime specialist coverage match

---

> **Local-first design:** theFactory is engineered to run fully offline with no external platform dependencies. All secrets stay in `.env` and local vault endpoints. Do not commit credentials or provider keys.
