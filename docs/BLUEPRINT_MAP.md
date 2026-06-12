# theFactory Architecture Blueprint & File Map

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
├── TODO.md                    # Audited and completed technical debt items list
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
│   ├── mission_flow_v2/       # Granular 7-phase Smelt-Cycle execution
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
