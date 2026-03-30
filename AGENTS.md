# Repository Guidelines

## Project Structure & Module Organization
- `apps/mission-control`: Next.js operator UI (routes under `app/`, unit tests, and Playwright e2e).
- `services/`: backend services (`api-gateway`, `orchestrator`, `pod-worker`, `audit-worker`, `semantic-bus-mcp`, `dashboard`).
- `scripts/`: operational tooling (audit, perf, reliability, backup/DR, debug sweep, OpenAPI export).
- `tests/`: Python tests split by domain (`tests/services`, `tests/scripts`).
- `deploy/`: Docker Compose stacks and monitoring config.
- `docs/`: canonical plans, audits, runbooks, and roadmap status.

## Build, Test, and Development Commands
- `make up` / `make down`: start/stop the full local Docker stack.
- `make tls-certs`: generate local PostgreSQL and Redis TLS certs before first stack startup.
- `make lint`: run Ruff checks on `services`, `tests`, and `scripts`.
- `make test`: run backend pytest with coverage gates.
- `make test-ui`: run Mission Control TypeScript lint + Vitest unit tests.
- `make test-ui-e2e`: run Mission Control Playwright e2e suite.
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
- Coverage policy: backend global `>=80%` plus enforced `100%` thresholds for critical runtime files via `scripts/check_coverage_thresholds.py`.
- Before merge, run at least: `make lint`, `make test`, `make test-ui`, `make test-ui-e2e`, and `make audit`.

## Commit & Pull Request Guidelines
- Follow observed history style: imperative, scoped subjects like `phase11: ...` or `chore: ...`.
- Keep commits focused to one phase/change set and include matching doc updates in `docs/` when behavior changes.
- PRs should include: problem/solution summary, linked task/issue, validation commands run, and UI screenshots for frontend changes.

## Security & Configuration Tips
- Start from `.env.example`; never commit secrets or real API keys.
- PostgreSQL and Redis private keys are generated locally with `make tls-certs` and must never be committed.
- Use Mission Control vault endpoints for local key handling (`/api/vault`, `/api/vault/test`).
- Avoid committing generated artifacts unless intentionally required (for example `coverage.xml`, `tsconfig.tsbuildinfo`).
