# Developer Onboarding Guide

Document version: 2026.08.17  
Last updated: 2026-08-17  
Status: Canonical  
Audience: Contributors, maintainers, and new developers

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Stack Setup](#stack-setup)
- [Verify the Stack](#verify-the-stack)
- [Run Tests](#run-tests)
- [Development Workflow](#development-workflow)
- [Codebase Tour](#codebase-tour)
- [Configuration Reference](#configuration-reference)
- [Troubleshooting](#troubleshooting)
- [Day-1 Checklist](#day-1-checklist)

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Docker Desktop | Latest | Windows with Compose v2 built in |
| Python | 3.11+ | For backend development and scripts |
| Node.js | 20+ | For Mission Control frontend |
| npm | 10+ | Bundled with Node.js 20 |
| Git | Any | With access to this repository |
| PowerShell | 5.1+ | For operational scripts (Windows built-in) |
| `make` | Any | Via Git Bash, WSL, or install via `winget install GnuWin32.Make` |

> **Note:** All Docker commands should be run from a terminal with Docker Desktop running. Git Bash is recommended for `make` commands on Windows.

---

## Environment Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd theFactory
```

### 2. Create Your Environment File

```bash
cp .env.example .env
```

Open `.env` and configure the required values:

```bash
# Minimum required for local stack:
POSTGRES_PASSWORD=CHANGE_ME_local_dev_postgres_password_32chars
REDIS_PASSWORD=CHANGE_ME_local_dev_redis_password_32chars
GATEWAY_API_KEY=dev-key-mutate
INTERNAL_SERVICE_API_KEY=dev-internal-key
MCP_API_KEY=mcp-local-key

# Add provider keys for LLM features (optional for initial setup):
ANTHROPIC_API_KEY_ARCH=sk-ant-...
OPENAI_API_KEY_CEO=sk-...
```

> **Security:** Never commit `.env`. It is `.gitignore`d. Keep provider keys in this file only.

### 3. Install Python Dependencies (for local development)

```bash
pip install -r services/api-gateway/requirements.txt
pip install -r services/orchestrator/requirements.txt
pip install -r services/pod-worker/requirements.txt
pip install -r requirements-dev.txt  # pytest, ruff, etc.
```

### 4. Install Frontend Dependencies

```bash
cd apps/mission-control
npm install
cd ../..
```

---

## Stack Setup

### Generate Local TLS Dev Certificates

```bash
make tls-certs
```

This generates local-only PostgreSQL and Redis TLS certificates and private keys under `deploy/.local/postgres-certs` and `deploy/.local/redis-certs`. Those private keys are gitignored and must remain local.

If you already started the stack before regenerating certs or after a cert-path change, recreate the affected containers so Docker refreshes the bind mounts:

```bash
docker compose -f deploy/docker-compose.yaml down -v
docker compose -f deploy/docker-compose.yaml up -d --build
```

### Start Core Stack

```bash
docker compose -f deploy/docker-compose.yaml up -d --build
```

This starts: api-gateway · orchestrator · pod-worker · audit-worker · protocol-bus-mcp · dashboard · redis · postgres · qdrant

**First startup takes 2–5 minutes** while images build and database migrations run.

### Start Monitoring Stack (optional, recommended)

```bash
docker compose -f deploy/docker-compose.monitoring.yaml up -d
```

This adds: Prometheus · Grafana · Loki · Promtail · Alertmanager · Jaeger

### Check Container Status

```bash
docker compose -f deploy/docker-compose.yaml ps
```

All services should show `healthy` or `running`. If any show `unhealthy`, check their logs (see [Troubleshooting](#troubleshooting)).

---

## Verify the Stack

Run these in order. All should return 200 with valid JSON.

```bash
# Gateway
curl http://localhost:8100/health

# Orchestrator
curl http://localhost:8101/health

# Protocol Bus MCP (formerly Semantic Bus MCP)
curl http://localhost:8102/health

# Dashboard
curl http://localhost:8180/health
```

Open in browser:
- **Mission Control UI:** `http://localhost:3100`
- **Grafana** (if monitoring started): `http://localhost:3001` (admin/admin)
- **Jaeger:** `http://localhost:16686`

### Submit a Test Mission

```bash
curl -X POST http://localhost:8100/v1/missions \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev-key-mutate" \
  -H "Idempotency-Key: onboarding-test-001" \
  -d '{"prompt":"Build a hello world service","requested_target_language":"python","metadata":{"source":"onboarding"}}'
```

You should receive a mission ID. Poll it:

```bash
curl http://localhost:8100/v1/missions/<mission_id>
```

---

## Run Tests

### Backend Tests (with coverage)

```bash
make test
```

Runs pytest with `--cov-fail-under=80` plus `scripts/check_coverage_thresholds.py`.
Gates: **line ≥80%**, **branch ≥70%**, **mixed ≥80%**, plus per-module floors
on privilege / money / PORT files (`sandbox_exec` 90%, `sow_store` 90%,
`port_coordinator` 80%, `rqca_agent` 70%). A mixed score above 80% cannot
hide a line score below 80%. Latest sweep (2026-08-17): line **85.80%**,
branch **72.82%**, mixed **82.72%**.

### Fast Tests (no coverage)

```bash
make test-fast
```

### Frontend Unit Tests

```bash
make test-ui
```

Runs ESLint + 21 Vitest unit tests in `apps/mission-control`.

### End-to-End Tests (requires running stack)

```bash
make test-ui-e2e
```

Runs 6 Playwright critical-path journeys: mission lifecycle · operations views · settings/vault · builder preview · repo intake · error states.

### Production Audit (13 automated checks)

```bash
make audit
```

All 17 checks should pass: `17/17 checks passed`.

### Lint Backend

```bash
make lint
```

---

## Development Workflow

### Backend Service Development

Services are in `services/<service-name>/`. Each is an independent FastAPI application.

```bash
# Run a service locally (without Docker)
cd services/api-gateway
pip install -r requirements.txt
uvicorn api_gateway.main:app --reload --port 8100
```

All services share the same code patterns:
- `main.py` — FastAPI app, lifespan, routes
- `tracing.py` — OTel configure_tracing helper (api-gateway, orchestrator, pod-worker have this)
- `requirements.txt` — service dependencies

### Frontend Development

```bash
cd apps/mission-control
npm run dev
# http://localhost:3000 (dev) or http://localhost:3100 (Docker)
```

The frontend uses:
- **Next.js 16** App Router (TypeScript strict mode)
- **Design system:** 31-token CSS variable system via `app/generated-tokens.css`
- **Live transport:** SSE EventSource client in `lib/sse-client.ts`
- **State:** React hooks, no global state library

### Adding a New API Endpoint

1. Add route to `services/<service>/main.py`
2. Add test to `tests/services/test_<service>_unit.py`
3. Update `docs/openapi/<service>.v1.json` via `make openapi`
4. Confirm `make lint` and `make test` still pass

### Making a Database Migration

Migrations live in `services/orchestrator/orchestrator/migrations/`. Filename format: `V{NNN}_{description}.sql`.

---

## Codebase Tour

```
theFactory/
├── apps/mission-control/           ← Next.js operator console
│   ├── app/                        ← App Router pages and layouts
│   │   ├── (shell)/               ← Layout shell (sidebar, header)
│   │   ├── missions/              ← Mission list + detail views
│   │   ├── agents/                ← 41-agent roster + detail
│   │   ├── protocol-bus/          ← Live Protocol Bus view
│   │   ├── builder/               ← Repository intake flow
│   │   └── settings/              ← Vault and config
│   ├── lib/                       ← API client, SSE client, helpers
│   └── e2e/                       ← Playwright test specs
│
├── services/
│   ├── api-gateway/api_gateway/   ← Gateway service (main.py, tracing.py)
│   ├── orchestrator/orchestrator/ ← Orchestrator (main.py, runtime.py, agent_personas.py)
│   ├── pod-worker/pod_worker/     ← Pod worker (main.py, language_extractor.py, concept_catalog.py)
│   ├── audit-worker/audit_worker/ ← Audit worker
│   ├── protocol-bus-mcp/          ← Protocol Bus MCP
│   └── dashboard/                 ← Dashboard service
│
├── tests/
│   ├── services/                  ← Unit and integration tests
│   └── scripts/                   ← Script regression tests
│
├── deploy/
│   ├── docker-compose.yaml        ← Core stack
│   ├── docker-compose.monitoring.yaml ← Observability stack
│   └── monitoring/                ← Prometheus, Grafana, Alertmanager configs
│
├── schemas/                       ← JSON Schema contracts
├── protocol/                      ← Protocol Bus topic catalog
├── scripts/                       ← Operational and audit scripts
├── docs/                          ← All documentation
└── assets/design-tokens/          ← CSS design token source of truth
```

### Key Source Files

| File | What it does |
|------|-------------|
| `services/orchestrator/orchestrator/agent_personas.py` | 41-agent persona profile dataset; uses a unified `AgentPersona` dataclass (no parallel dict maintenance needed when adding agents) |
| `services/orchestrator/orchestrator/agent_registry.py` | Agent runtime state and registry |
| `services/orchestrator/orchestrator/runtime.py` | Mission lifecycle state machine |
| `services/orchestrator/orchestrator/langgraph_lifecycle.py` | LangGraph StateGraph |
| `services/pod-worker/pod_worker/concept_catalog.py` | 169-pattern extraction catalog |
| `services/pod-worker/pod_worker/language_extractor.py` | Extraction engine base classes |
| `services/api-gateway/api_gateway/main.py` | Gateway API, auth, SSE transport |
| `apps/mission-control/app/globals.css` | Design system CSS variables |

---

## Configuration Reference

See `.env.example` for all variables. Critical ones:

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_MODE` | `api_key` | `api_key` \| `hybrid` \| `oidc` |
| `GATEWAY_API_KEY` | — | Mutate/admin access key |
| `INTERNAL_SERVICE_API_KEY` | — | Service-to-service key used by workers and Mission Control review approval persistence |
| `LANGGRAPH_ENABLED` | `false` | Enable LangGraph state machine |
| `LANGGRAPH_CHECKPOINTER` | `memory` | `memory` \| `postgres` |
| `LANGGRAPH_FAIL_OPEN` | `true` | Fallback to legacy lifecycle on error |
| `POD_NAME` | `podA` | Pod worker identity (`podA` \| `podB` \| `podC` \| `podD`) |
| `AGENT_BINDING` | `""` | Dedicated worker agent binding (e.g. `AGENT-14-PY`) |
| `NEO4J_ENABLED` | `true` | Enable Neo4j graph adapter (on by default) |
| `OBJECT_STORAGE_ENABLED` | `true` | Enable MinIO/S3 adapter (on by default) |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8100` | Gateway URL for Mission Control |
| `ORCHESTRATOR_INTERNAL_BASE_URL` | `http://localhost:8101` | Orchestrator internal URL for Mission Control review approval persistence |
| `APPROVAL_HMAC_SECRET` | — | HMAC secret used by Mission Control to sign and verify durable review approvals |
| `APPROVAL_TTL_SECONDS` | `86400` | Review approval lifetime in seconds |
| `MISSION_CONTROL_ADMIN_KEY` | — | Local operator unlock key for privileged Mission Control routes |
| `MISSION_CONTROL_SESSION_SECRET` | — | Signing secret for Mission Control operator sessions |
| `MISSION_CONTROL_SESSION_TTL_SECONDS` | `28800` | Mission Control operator session lifetime in seconds |

---

## Troubleshooting

### Redis Unavailable

```bash
docker compose -f deploy/docker-compose.yaml ps redis
docker compose -f deploy/docker-compose.yaml logs redis --tail 50
```

Most common cause: port 6380 already in use. Update `REDIS_PORT` in `.env`.

If the logs mention missing files under `/usr/local/etc/redis/certs` or `/run/redis-certs`, regenerate local TLS material with `make tls-certs` and recreate the stack so old bind mounts are discarded.

### Gateway Returns 503

Orchestrator or Redis is not healthy. Check:

```bash
docker compose -f deploy/docker-compose.yaml logs orchestrator --tail 100
curl http://localhost:8101/readyz
```

### Database Migration Failure

```bash
docker compose -f deploy/docker-compose.yaml logs orchestrator --tail 200 | grep -i migration
```

If migrations fail, the orchestrator will exit. Check for SQL errors or permission issues.

If Postgres logs mention missing files under `/run/postgres-certs`, regenerate local TLS material with `make tls-certs` and recreate the stack so the updated cert mount is applied.

### Frontend API Errors (CORS / 404)

Ensure `NEXT_PUBLIC_API_BASE_URL` in `.env` matches where the gateway is running. For Docker stack: `http://localhost:8100`.

### Port Conflicts

Default ports sometimes conflict with local services. Override in `.env`:
```bash
GATEWAY_PORT=8100
ORCHESTRATOR_PORT=8101
```

### Coverage Gate Failure

If `make test` fails with coverage errors:
```bash
make test 2>&1 | grep -E "FAILED|coverage"
python scripts/check_coverage_thresholds.py
```

---

## Day-1 Checklist

- [ ] Docker Desktop running, `docker compose ps` shows all services healthy
- [ ] `curl http://localhost:8100/health` returns `{"status":"healthy"}`
- [ ] Test mission submitted and polled successfully
- [ ] `make test` passes — line ≥80%, branch ≥70%, mixed ≥80%
- [ ] `make audit` passes — 17/17 checks
- [ ] Mission Control UI opens at `http://localhost:3100`
- [ ] Agent roster shows 41 agents at `http://localhost:8100/v1/operations/agents`
- [ ] `make lint` passes — 0 ruff errors
- [ ] Read [`ARCHITECTURE.md`](ARCHITECTURE.md) for system topology
- [ ] Read [`AGENTS.md`](../AGENTS.md) for AI agent developer guidelines
