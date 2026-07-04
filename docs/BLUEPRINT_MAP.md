# theFactory Architecture Blueprint & File Map

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Canonical
Audience: Developers and operators

This document serves as the canonical blueprint and file map of **theFactory** repository, detailing components, routing architectures, and data structures. This map is updated phase-by-phase during the repository audit.

---

## 1. Control Plane & UI (Phase 1 Audit)

### 1.1. Mission Control UI (`apps/mission-control/`)
The Next.js App Router operator interface.

```
apps/mission-control/
├── app/                       # Next.js App Router Root
│   ├── (shell)/               # Authed layouts and page routes
│   │   ├── agents/            # Renders 41-agent roster, queue depths, and personas
│   │   ├── alerts/            # Renders system alerts and notifications
│   │   ├── audit/             # Logs audit trials and compliance mapping
│   │   ├── builder/           # Renders workspace build previews and approvals
│   │   ├── chat/              # Conversational operator prompt intake
│   │   ├── dashboard/         # System overview, health status, and live SSE gauges
│   │   ├── databases/         # Health monitoring for 7 database engines
│   │   ├── logicnodes/        # Visualizes extracted LogicNode clusters
│   │   ├── missions/          # Detailed Smelt-Cycle state-event streams
│   │   ├── performance/       # SLO burn budgets and latency panel charts
│   │   ├── projects/          # Project timeline and audit traces
│   │   ├── protocol-bus/      # Live virtualized view of 6 bus streams
│   │   ├── repo/              # Repository imports and Git sync setups
│   │   ├── settings/          # System preferences and key vault management
│   │   ├── layout.tsx         # Left navigation and operator shell
│   │   └── page.tsx           # Redirects to /dashboard
│   ├── api/                   # Serverless route handlers (Next.js Route Handlers)
│   │   ├── gateway/           # [...path] catch-all proxy to local API Gateway (:8100)
│   │   ├── session/           # Operator session creation and unlock handlers
│   │   ├── vault/             # Encrypted operator local key storage
│   │   └── .../               # builder, operator, pm, repo, review APIs
│   ├── components/            # Shared UI components (casing strictly lowercase)
│   │   ├── panel.tsx          # Panel wrapper (Windows-casing verified)
│   │   ├── status.tsx         # System status badges
│   │   └── ...                # command-palette, global-search, tooltips, etc.
│   ├── lib/                   # Client-side utility functions and types
│   │   ├── types/             # OpenAPI-generated TypeScript types (gen:api)
│   │   ├── api-client.ts      # Strongly typed fetch client (no 'any' types)
│   │   ├── security.ts        # Input sanitization and API URL safety checks
│   │   └── ...
│   ├── globals.css            # Base styles and theme variables
│   └── layout.tsx             # Root document wrapper (strict TS enabled)
├── dist/                      # Production build output
├── electron/                  # Electron desktop packaging wrapper
├── public/                    # Static UI assets (icons, images)
├── scripts/                   # Next.js build and sync utilities
├── package.json               # Vitest, Playwright, next, electron configurations
└── tsconfig.json              # Strict TS rules (forceConsistentCasingInFileNames: true)
```

**Wiring & Connections**:
- **Gateway Proxy**: Client API calls route through `app/api/gateway/[...path]/route.ts`, forwarding headers/bodies to the API Gateway (`MISSION_API_BASE_URL` or `http://localhost:8100`).
- **SSE Transport**: Establish direct client connection `GET /v1/stream/state` via Server-Sent Events, monitored on the main dashboard.

---

### 1.2. API Gateway (`services/api-gateway/`)
Public network boundaries and API request proxy.

```
services/api-gateway/
├── api_gateway/               # Source package
│   ├── __init__.py
│   ├── main.py                # Core entry point (FastAPI app)
│   └── tracing.py             # OpenTelemetry instrumentation (FastAPI + httpx)
├── Dockerfile                 # Pinned python:3.11-slim-bookworm image
└── requirements.txt           # fastapi, uvicorn, httpx, opentelemetry, redis dependencies
```

**Wiring & Core Components**:
- **Authentication**: `AUTH_MODE` (api_key | hybrid | oidc) validated in `_require_api_key_role`. Uses constant-time check (`hmac.compare_digest`) against every key.
- **Rate Limiting**: sliding window rate limiter (120 req/min) backed by Redis. Rate-limit keys are HMAC hashed to protect client credentials.
- **SSE Stream**: Server-Sent Events stream `GET /v1/stream/state` with client-resumption support (`Last-Event-ID`).
- **Proxy**: Proxy routes forward traffic to `ORCHESTRATOR_INTERNAL_BASE_URL` (:8101).

---

### 1.3. Repository Root & Configurations
Shared repo configuration and metadata documentation.

```
theFactory/
├── config/
│   └── agent_api_keys.yaml    # Per-agent LLM credentials and provider override models (clean template)
├── Makefile                   # Docker, linting, testing, and operations task manager
├── pyproject.toml             # Python package dependencies and Ruff configs
├── requirements-dev.txt       # Dev-specific python packages (ruff, pytest)
├── AGENTS.md                  # Canonical multi-agent definitions and lifecycle engine overview
├── MIGRATION.md               # Renaming specifications (e.g. semantic-bus -> protocol-bus)
├── docs/CURRENT_TODO.md        # Active TODO list and outstanding production-readiness work
└── .env.example               # Pgbouncer, PostgreSQL TLS, Redis TLS environment templates
```

**Hardened Properties**:
- **VCS Cleanness**: Git history and root configs are audited and verified clean of all private credentials.
- **Ruff Linting**: Max line length is set to 100 with strict style rules.

---

## 2. State & Orchestration (Phase 2 Audit)

### 2.1. Orchestrator Service (`services/orchestrator/`)
The core workflow engine and transaction manager.

```
services/orchestrator/
├── orchestrator/              # Source package
│   ├── llm_delegation/        # LLM interaction layer (split per provider)
│   │   ├── __init__.py        # Exports call_llm and prompt formatting dispatchers
│   │   ├── providers.py       # API clients for OpenAI, Anthropic, and Gemini
│   │   ├── fallbacks.py       # Offline/timeout mock response generators
│   │   ├── health.py          # LLM API healthchecks and token budgets
│   │   └── ...                # prompts, text, metrics, normalizers
│   ├── mission_flow_v2/       # Granular 11-phase v2 lifecycle engine
│   │   ├── __init__.py        # Main v2 runner and gate logic
│   │   ├── phases_intake.py   # INTAKE and FETCH transitions
│   │   ├── phases_build.py    # SMELT, GATING, and FUSION transitions
│   │   ├── phases_delivery.py # SQUEEZE and DELIVERY transitions
│   │   ├── phases_runtime.py  # Runtime execution and callback handling
│   │   └── base.py            # Base phase logic and context helpers
│   ├── routes/                # HTTP API route endpoints
│   ├── storage.py             # Façade layer re-exporting submodules
│   ├── storage_core.py        # Connection pooling and PgBouncer prepared-stmt bypass
│   ├── storage_missions.py    # Mission CRUD, state event logging, and transitions
│   ├── storage_pods.py        # Pod work assignments and scaling results
│   ├── storage_logicnodes.py  # Language-agnostic LogicNode writes (Neo4j mirror)
│   ├── storage_artifacts.py   # Build artifact metadata and offloads
│   ├── storage_agents.py      # Heartbeats and cryptographically chained event ledger
│   ├── lifecycle_interface.py # stateless LifecycleEngine Protocol selector
│   ├── agent_registry.py      # Declarative source of truth for 41 agents
│   ├── agent_personas.py      # 8-part persona dataclass definitions
│   ├── main.py                # App entrypoint (Uvicorn router)
│   └── settings.py            # App configurations and adapter flags
├── Dockerfile                 # Multi-stage container run as non-root
└── requirements.txt           # fastapi, psycopg, redis, boto3, jmespath, neo4j
```

**Wiring & Infrastructure**:
- **Database Connection Pool**: Managed in `storage_core.py` using `psycopg_pool.ConnectionPool` with `autocommit=True` and `prepare_threshold=None` (PgBouncer compatibility).
- **Dual-write adapter sync**: Writes to PostgreSQL tables primary, and mirrors write-back async/best-effort to Neo4j (`storage_logicnodes.py`) and object storage (`storage_artifacts.py`) if enabled.

---

### 2.2. Shared Runtime (`shared_runtime/`)
Common security, logging, and cryptographic primitives.

```
shared_runtime/
├── agent_auth.py              # HMAC signature authentication checks
├── agent_keys.py              # Cryptographic key loading and verification
├── atomic_io.py               # Atomic write (tempfile -> verify -> replace)
├── crypto_keystore.py         # DPAPI-protected keystore (fallback to plain)
├── crypto_signing.py          # ECDSA P-256 keypair generation and signing
├── errors.py                  # Standard error codes and FactoryError class
├── logging_config.py          # Structured JSON logging formatters
├── pii_guard.py               # Redaction patterns for private/sensitive keys
├── prompt_guard.py            # OWASP LLM01 injection scanning
└── protocol.py                # Envelope schema validation (shared schema)
```

**Security & Error Handling**:
- **ECDSA P-256 Signing**: Signing key pair is protected using DPAPI on Windows and standard storage on Unix. Used to sign and verify compliance and artifact bundles.
- **Prompt Guard**: Regulated by `PROMPT_GUARD_BLOCK_ENABLED` and `PROMPT_GUARD_BLOCK_LEVEL`. If triggered, injection result is logged and blocked securely.
- **Errors standard**: Centralized error model (`FactoryError`) for consistent frontend parsing.

---

## 3. Worker & Bus Services (Phase 3 Audit)

### 3.1. Pod Worker Service (`services/pod-worker/`)
Static analysis, semantic routing, and LogicNode creation.

```
services/pod-worker/
├── pod_worker/                # Source package
│   ├── main.py                # Consumer loops (XREADGROUP), smelting, and DB writes
│   ├── language_extractor.py  # Router and regex-based concept extractors (20 languages)
│   ├── concept_catalog.py     # 232 static analysis concept patterns
│   ├── ast_extractor.py       # Python AST-backed extractor
│   ├── java_ast_extractor.py  # Java AST javalang parser
│   ├── js_ast_extractor.py    # JavaScript/TypeScript esprima parser
│   ├── refined_ir.py          # Data models for functions and classes
│   └── tracing.py             # OpenTelemetry tracing configuration
├── Dockerfile                 # Multi-stage build with non-root user (copies orchestrator files)
└── requirements.txt           # fastapi, redis, esprima, javalang, opentelemetry
```

**Smelting Flow**:
- **AST Parsing**: Enabled via flags (e.g. `PYTHON_AST_EXTRACTOR_ENABLED=true`). Falls back silently to regex if parsing fails (robustness).
- **Fallback Node**: If extraction returns no results, it writes a standard fallback node (`_routing_stub_logicnode`) so the pipeline does not stall.

---

### 3.2. Audit Worker Service (`services/audit-worker/`)
State stream auditing and report compiling.

```
services/audit-worker/
├── audit_worker/              # Source package
│   ├── main.py                # State stream consumer, verification checks, and report submission
│   └── tracing.py             # OpenTelemetry tracing configuration
├── Dockerfile                 # Multi-stage lean runtime run as non-root
└── requirements.txt           # fastapi, redis, httpx, opentelemetry
```

---

### 3.3. Protocol Bus MCP (`services/protocol-bus-mcp/`)
Reliable message broker and lexical router.

```
services/protocol-bus-mcp/
├── protocol_bus/              # Source package
│   ├── mcp_server.py          # Message endpoints, schema validations, and reliability gates
│   └── tracing.py             # OpenTelemetry tracing configuration
├── Dockerfile                 # Lean runtime run as non-root
└── requirements.txt           # fastapi, redis, uvicorn, prometheus-client
```

**Resilience Gates**:
- **Replay Protection**: Rejects duplicate correlation IDs, failing closed (503) if Redis is unavailable.
- **Deduplication**: Message-level `SET NX EX` check (5-minute TTL).
- **Backpressure**: Rejects requests if any channel queue depth exceeds 10,000 (returns 503 with `Retry-After: 5`).
- **DLQ Routing**: Discards malformed publishes to the `dlq:<protocol>` Redis stream.

---

### 3.4. Agent Runtime Service (`services/agent-runtime/`)
Dedicated worker agent execution loop.

```
services/agent-runtime/
├── agent_runtime/             # Source package
│   ├── main.py                # Heartbeat daemon, stream listener, and circuit breaker
│   └── tracing.py             # OpenTelemetry tracing configuration
├── Dockerfile                 # Dedicated container setup
└── requirements.txt           # uvicorn, redis, httpx, opentelemetry
```

**Wiring**:
- **Circuit Breaker**: Trips and fails fast if the orchestrator is unreachable, preventing CPU spin loops.

---

### 3.5. Operations Dashboard (`services/dashboard/`)
Lightweight operational health monitor.

```
services/dashboard/
├── dashboard/                 # Source package
│   ├── main.py                # FastAPI server (HTML UI / snapshot proxier)
│   └── tracing.py             # OpenTelemetry tracing configuration
├── Dockerfile                 # Multi-stage lean runtime
└── requirements.txt           # fastapi, httpx, uvicorn, opentelemetry
```

---

## 4. Architectural Cross-Cutting Observations (Phase 4)

During the detailed folder-by-folder audit, several cross-cutting design patterns and structural optimizations were analyzed:

### 4.1. DRY (Don't Repeat Yourself) vs. Service Isolation
- **Findings**:
  - The module `tracing.py` (which configures OpenTelemetry for FastAPI and httpx) is replicated identically across four services: `agent-runtime`, `pod-worker`, `audit-worker`, and `dashboard`.
  - In a standard python project, this boilerplate is a candidate for consolidation.
  - **Refactoring Potential**: Since the `shared_runtime` package is already copied into almost every container's Dockerfile (e.g. `COPY shared_runtime /app/shared_runtime`), this tracing code could be safely moved to a centralized module `shared_runtime/tracing.py` and imported by each service, eliminating duplicate boilerplate while maintaining strict container isolation.

### 4.2. Code Sharing Boundaries
- **Findings**:
  - To preserve the Single Source of Truth (SSOT) for the 41-agent registries and persona profiles, `pod-worker` imports the agent creation helper (`make_agent`) directly from the orchestrator package.
  - At container build time, the Dockerfile handles this dependency via `COPY services/orchestrator/orchestrator /app/orchestrator`.
  - This is an acceptable container build coupling that prevents duplicating LLM delegation and agent metadata definitions across different code folders.

### 4.3. Dual-Write Consistency & Fallbacks
- **Findings**:
  - The orchestrator and pod workers write primary transactional state directly to PostgreSQL.
  - Mirroring write-back to Neo4j (graph relations) and Qdrant (vector knowledge lake) runs on an async, best-effort path wrapped in try/except blocks. If Neo4j or Qdrant goes offline, the system degrades gracefully without crashing the core smelt pipeline.

---

## 5. Maintenance & Legacy Pruning (Phase 4)

- **Legacy Folder Removal**: 
  - Audited and deleted the empty `services/semantic-bus-mcp/` folder.
  - This folder was a leftover from the communication bus renaming (#190) from `semantic-bus` to `protocol-bus` (lexical routing channels).
  - This clean-up prevents developers from checking out or referencing stale service directories.
