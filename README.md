# theFactory

Holy Grail application monorepo.

This repository is the active build target for the Holy Grail system: a local-first, agent-driven software refinery with a semantic bus, orchestration layer, and mission control surfaces.

## Monorepo layout

- `services/api-gateway`: External API entry point (FastAPI)
- `services/orchestrator`: Mission orchestration service (FastAPI)
- `services/dashboard`: Operational dashboard service (FastAPI + HTML)
- `services/pod-worker`: Specialist pod routing worker (deployed as podA/podB/podC/podD)
- `services/audit-worker`: Audit handoff and release-event worker
- `apps/mission-control`: Next.js user-facing mission console
- `schemas`: JSON contracts (LogicNode, Refined IR, event envelopes)
- `protocol`: Semantic bus topic catalog
- `ledger`: Traceability ledger schema
- `deploy`: Docker Compose local stack
- `examples`: Example contract payloads
- `scripts`: Validation and bootstrap scripts
- `docs`: Architecture and delivery planning notes
- `tests`: Service-level test scaffold

## Quick start

1. Copy environment file:
   - `cp .env.example .env`
2. Bring up core services:
   - `docker compose -f deploy/docker-compose.yaml up -d --build`
3. Check health:
   - API gateway: `http://localhost:8100/health`
   - API gateway readiness: `http://localhost:8100/readyz`
   - API gateway metrics: `http://localhost:8100/metrics`
   - Orchestrator: `http://localhost:8101/health`
   - Orchestrator readiness: `http://localhost:8101/readyz`
   - Orchestrator metrics: `http://localhost:8101/metrics`
   - Dashboard: `http://localhost:8180/health`
   - Mission Control: `http://localhost:3100`

Default host ports are configured in `.env.example` and can be changed in `.env`.

## Development commands

- `make up`: start local stack
- `make down`: stop stack
- `make validate`: validate schema JSON files
- `make test`: run pytest suite
- `make lint`: run ruff checks
- `make openapi`: export OpenAPI contracts
- `make predeploy`: run deployment preflight checks
- `make backup`: create PostgreSQL backup
- `make dr`: run DR drill script
- `make perf`: run performance smoke test
- `make monitor-up`: start Prometheus/Grafana/Loki stack
- `make monitor-down`: stop monitoring stack
- `make sweep`: run debug/code sweep script

## Security and auth

- State mutation endpoint requires `x-api-key` with mutate/admin role:
  - `POST /v1/missions/{mission_id}/state`
- Direct orchestrator mission creation is internal-only and requires `x-api-key`:
  - `POST /missions`
- Default local keys are configured in `.env.example`:
  - `admin-key`
  - `operator-key`
  - `worker-key`
  - `viewer-key`

## Current phase status

- Phase 1 complete: foundation scaffold + local stack + contracts.
- Phase 2 complete: intake bus, persistence, lifecycle transitions, protocol envelope validation.
- Phase 3 complete: pod/audit worker services, specialist routing handoffs, logicnode/knowledge/audit integration.
- Phase 4 complete: CI + security workflow, auth controls, regression/security/load scaffolds, debug sweep tooling.
- Phase 5 complete (baseline): runtime hardening (`/readyz`, `/metrics`, mission idempotency, worker reliability hardening).
- Phase 6 complete (baseline): CI/CD hardening, observability/deploy/DR/perf automation scaffolds.

## Next targets

1. Enforce signed release attestations and environment promotion policy in CI.
2. Add distributed tracing and pager/webhook integrations in observability.
3. Expand long-duration load qualification and capacity baselines.
