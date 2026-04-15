# Repository Guidelines — theFactory / Holy Grail Refinery (HGR)

## Project Identity

theFactory is a multi-agent AI software manufacturing system. The orchestrator drives missions through a 7-phase Smelt Cycle using 38 registered agents across 4 specialist pods (A–D), an executive tier, and an interface tier. Six Redis-based protocols coordinate inter-agent communication (ALPHA, BETA, DELTA, SIGMA, OMEGA, RHO).

## Project Structure & Module Organization
- `apps/mission-control`: Next.js operator UI (routes under `app/`, unit tests, and Playwright e2e).
- `services/`: backend services (`api-gateway`, `orchestrator`, `pod-worker`, `audit-worker`, `semantic-bus-mcp`, `dashboard`).
- `scripts/`: operational tooling (audit, perf, reliability, backup/DR, debug sweep, OpenAPI export).
- `tests/`: Python tests split by domain (`tests/services`, `tests/scripts`).
- `deploy/`: Docker Compose stacks and monitoring config.
- `docs/`: canonical plans, audits, runbooks, and roadmap status.

## Runtime Model

### Topology modes

| Mode | Description | Compose profile |
|---|---|---|
| `condensed` | Shared pod-worker containers + synthesized heartbeats for non-pod agents (default) | _(default)_ |
| `dedicated` | One container per pod manager | `dedicated-agents` |
| `full-dedicated` | One container per language specialist | `full-dedicated-agents` |

Set via `TOPOLOGY_MODE` env var (default: `condensed`). The `runtime_class` field on each `AgentDefinition` reflects this: `shared_worker` for specialist/pod_manager/pod_audit categories, `synthesized_heartbeat` for interface/executive/support.

### Lifecycle engines

| Engine | Flag | Notes |
|---|---|---|
| `MissionFlowV2Engine` | `MISSION_FLOW_V2_ENABLED=true` (default) | 11-phase granular state machine |
| `LangGraphEngine` | `LANGGRAPH_ENABLED=true` + v2 disabled | EXPERIMENTAL — falls back to legacy if dep missing |
| `LegacyV1Engine` | both disabled | COMPATIBILITY SHIM — coarse 3-transition v1.1 |

Factory: `get_lifecycle_engine(settings)` in `orchestrator/lifecycle_interface.py`.

### Extraction engine

The pod-worker extracts concepts from source code using regex by default. Set `PYTHON_AST_EXTRACTOR_ENABLED=true` to enable AST-backed extraction for Python (zero false positives for structural fields; regex still runs for concept detection).

## Build, Test, and Development Commands
- `make up` / `make down`: start/stop the full local Docker stack.
- `make tls-certs`: generate local PostgreSQL and Redis TLS certs before first stack startup.
- `make lint`: run Ruff checks on `services`, `tests`, and `scripts`.
- `make test`: run backend pytest with coverage gates.
- `make test-ui`: run Mission Control TypeScript lint + Vitest unit tests.
- `make test-ui-e2e`: run Mission Control Playwright e2e suite.
- `make validate`: full gate — lint + schema validation + pytest + npm lint/test.
- `make audit`: run production checklist audit script.
- `make sweep`: run schema/tests/health/readiness/metrics debug sweep.
- UI local dev: `cd apps/mission-control && npm run dev`.

## Coding Style & Naming Conventions
- Python: 4-space indentation, `snake_case` for functions/files, `PascalCase` for classes.
- TypeScript/React: follow existing 2-space style, `PascalCase` components, `camelCase` helpers/hooks.
- Keep route files consistent with Next App Router conventions (`page.tsx`, `layout.tsx`, `route.ts`).
- Lint rules: Ruff (`E,F,I,B`) with max line length `100`; Mission Control uses strict TypeScript (`tsc --noEmit`).

## Testing Guidelines
- Frameworks: `pytest` (backend/scripts), `vitest` (UI unit), `playwright` (UI e2e).
- Naming: Python `test_*.py`; UI unit `*.test.ts`; e2e `*.spec.ts`.
- Coverage policy: backend global `>=80%` plus enforced per-module floors for critical runtime files via `scripts/check_coverage_thresholds.py`.
- Before merge: `make lint`, `make test`, `make test-ui`, `make test-ui-e2e`, `make audit`.

## Commit & Pull Request Guidelines
- Follow observed history style: imperative, scoped subjects like `phase11: ...` or `chore: ...`.
- Keep commits focused to one phase/change set and include matching doc updates in `docs/` when behaviour changes.
- PRs should include: problem/solution summary, linked task/issue, validation commands run, and UI screenshots for frontend changes.

## Security & Configuration Tips
- Start from `.env.example`; never commit secrets or real API keys.
- PostgreSQL and Redis private keys are generated locally with `make tls-certs` and must never be committed.
  - Docker containers use `/run/secrets/` or volume mounts for certs. Local dev uses `deploy/.local/`.
- Use Mission Control vault endpoints for local key handling (`/api/vault`, `/api/vault/test`).
- Avoid committing generated artifacts unless intentionally required (e.g. `coverage.xml`, `tsconfig.tsbuildinfo`).

## High-sensitivity files

| File | Risk | Notes |
|---|---|---|
| `services/orchestrator/orchestrator/storage.py` | High | 1 400+ lines, 7 domains — Phase 6 split target |
| `services/orchestrator/orchestrator/main.py` | High | 1 000+ lines — HeartbeatService and ReviewPolicy extraction planned |
| `services/orchestrator/orchestrator/runtime.py` | Medium | Now delegates to `lifecycle_interface.py` |
| `services/orchestrator/orchestrator/agent_registry.py` | Medium | Source of truth for all 38 agent definitions |

See `docs/codex/DEFINITION_OF_DONE.md` and `docs/codex/REVIEW_CHECKLIST.md` for change gates.
