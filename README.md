# theFactory

Local-first implementation of the HolyGrail multi-agent software refinery.

This monorepo contains the runtime services, frontend, contracts, and operational tooling for a 35-agent orchestration system that turns mission prompts into verified software artifacts through a semantic-bus workflow.

## What This Application Is

theFactory is a Windows-friendly, Docker-based application stack with:

- Multi-service runtime (API gateway, orchestrator, workers, dashboard, mission control).
- Semantic bus event flow over Redis Streams.
- Mission lifecycle persistence and telemetry in PostgreSQL.
- 35-agent runtime registry with:
  - role and workload telemetry,
  - provider/model recommendations,
  - complete 8-part persona profiles,
  - standards-aligned evidence mappings (NIST, OWASP, ISO/IEC).
- Mission Control UI for operations, agent topology, settings, semantic bus views, and diagnostics.

## System Topology

Core services:

- `services/api-gateway` (FastAPI): public API boundary and intake.
- `services/orchestrator` (FastAPI): mission state machine, pod coordination, operations APIs.
- `services/semantic-bus-mcp` (FastAPI): protocol validation/routing for alpha-beta-delta-sigma-omega-rho bus messages.
- `services/pod-worker` (FastAPI worker runtime): pod routing and artifact processing for pod A/B/C/D.
- `services/audit-worker`: audit stream processing and verification handoff.
- `services/dashboard` (FastAPI + HTML): lightweight operational dashboard.
- `apps/mission-control` (Next.js): operator console and runtime control UI.
- Optional dedicated manager-worker profile (`--profile dedicated-agents`) for trigger-based topology expansion.

Data and event plane:

- Redis Streams: mission/event transport and heartbeat/event telemetry.
- PostgreSQL: missions, events, pod assignments, logicnodes, knowledge, audits, agent heartbeats.
- Qdrant: active knowledge retrieval/index path with PostgreSQL fallback.
- Neo4j: optional feature-flagged graph adapter for relationship-heavy mission knowledge/audit queries.
- Object storage: optional feature-flagged adapter for immutable large-artifact retention.

## 35-Agent Runtime Model

The orchestrator maintains a canonical 35-agent registry covering:

- User interface tier.
- Executive tier.
- Support ring.
- Pod A/B/C/D manager, audit, and specialist agents.

Each agent now exposes:

- Runtime state (`IDLE`, `ACTIVE`, `RUNNING`, `VERIFYING`, `ERROR`, `PAUSED`).
- Queue/workload and mission assignment telemetry.
- LLM recommendation strategy (provider/model/thinking profile + fallback where applicable).
- `persona_profile` with:
  - `job_role`
  - `education_certifications`
  - `traits_skills`
  - `methods_procedures`
  - `tools`
  - `master_instruction`
  - `protocol`
  - `api_configuration`
  - `standards_alignment` (extension)
  - `evidence_sources` (extension)

## Key API Surfaces

Gateway (`http://localhost:8100` by default):

- `GET /health`
- `GET /readyz`
- `GET /metrics`
- `POST /v1/missions`
- `GET /v1/missions`
- `GET /v1/missions/{mission_id}`
- `GET /v1/missions/{mission_id}/events`
- `GET /v1/missions/{mission_id}/knowledge-graph`
- `GET /v1/missions/{mission_id}/audit-artifacts`
- `POST /v1/missions/{mission_id}/state`
- `GET /v1/operations/summary`
- `GET /v1/operations/agents`
- `GET /v1/operations/agent-integrations`

Orchestrator (`http://localhost:8101` by default):

- `GET /health`
- `GET /readyz`
- `GET /metrics`
- `GET /internal/operations/summary`
- `GET /internal/operations/agents`
- `GET /internal/operations/agent-integrations`

Semantic Bus MCP (`http://localhost:8102` by default):

- `GET /health`
- `GET /readyz`
- `GET /metrics`
- `POST /send`
- `GET /dlq`

OpenAPI exports:

- `docs/openapi/api-gateway.v1.json`
- `docs/openapi/orchestrator.v1.json`

## Mission Control UI

Mission Control access:

- Docker stack default (external host port): `http://localhost:3100`
- Direct Next.js dev server (`npm run dev`): `http://localhost:3000`

Mission Control provides:

- Dashboard and mission lifecycle views.
- Agent grid and drill-down detail (including full 8-part persona + standards evidence).
- Semantic bus and logicnode/event views.
- Runtime settings and local vault-based key management:
  - `/api/vault`
  - `/api/vault/test`
  - `/api/operator/mission-state`

## Repository Layout

- `apps/mission-control`: Next.js operator application.
- `services/api-gateway`: external API and LLM builder routing.
- `services/orchestrator`: mission orchestration and operations APIs.
- `services/pod-worker`: pod stream workers.
- `services/audit-worker`: audit stream worker.
- `services/dashboard`: operations status dashboard.
- `schemas`: message/artifact contracts.
- `protocol`: semantic-bus topic catalog.
- `ledger`: traceability ledger schema.
- `deploy`: Docker Compose stacks.
- `scripts`: validation, export, audit, DR/perf/debug tooling.
- `tests`: service and production-foundation tests.
- `docs`: architecture, standards, runbooks, plans, and audits.

## Quick Start

1. Copy env template:
   - `cp .env.example .env`
2. Start stack:
   - `docker compose -f deploy/docker-compose.yaml up -d --build`
3. Verify:
   - Gateway: `http://localhost:8100/health`
   - Orchestrator: `http://localhost:8101/health`
   - Semantic Bus MCP: `http://localhost:8102/health`
   - Dashboard: `http://localhost:8180/health`
   - Mission Control: `http://localhost:3100`

Default host ports:

- Gateway: `8100`
- Orchestrator: `8101`
- Semantic Bus MCP: `8102`
- Dashboard: `8180`
- Mission Control: `3100`
- Redis: `6380`
- PostgreSQL: `5433`
- Qdrant: `6334`

## Development Commands

Using `make`:

- `make up`: build/start core stack.
- `make down`: stop stack and remove volumes.
- `make validate`: validate schema files.
- `make lint`: run `ruff` on backend/test/scripts.
- `make test`: run full pytest with global coverage gate (`>= 80%`) plus 100% coverage gates for core multi-agent communication/runtime modules.
- `make test-ui`: run Mission Control lint + unit tests.
- `make test-ui-e2e`: run Mission Control Playwright e2e regression suite.
- `make test-fast`: run pytest without coverage reporting.
- `make audit`: run production checklist audit script.
- `make promotion-gate`: evaluate local release promotion policy and write decision artifact.
- `make openapi`: export OpenAPI documents.
- `make predeploy`: run pre-deploy checks.
- `make backup`: run PostgreSQL backup script.
- `make dr`: run DR drill script.
- `make perf`: run performance smoke script.
- `make reliability`: run sustained-load reliability qualification with readiness/recovery checks.
- `make sweep`: run debugging/code sweep script.
- `make monitor-up` / `make monitor-down`: control monitoring stack.

Frontend app commands:

- `cd apps/mission-control`
- `npm install`
- `npm run dev`
- `npm run build`
- `npm run lint`
- `npm run test`
- `npm run test:e2e`

## Security, Auth, and Operational Controls

- Mutating mission state requires `x-api-key` with mutate/admin role.
- Gateway auth mode supports:
  - `AUTH_MODE=api_key` (default),
  - `AUTH_MODE=hybrid` (JWT/OIDC bearer or API key),
  - `AUTH_MODE=oidc` (JWT/OIDC bearer required for operator mutations).
- Internal orchestrator writes use internal service keys.
- Mission intake supports `Idempotency-Key` for replay-safe creation semantics.
- Gateway applies rate limiting and strict security headers.
- Runtime includes readiness and metrics endpoints.
- Docker images use non-root runtime users.
- Production audit automation exists in `scripts/production_review_audit.py`.

## Provider and Model Governance

Live provider support:

- OpenAI
- Anthropic
- Gemini
- Offline deterministic fallback mode

Provider/model strategy documentation:

- `docs/AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md`

Persona standards and external evidence mapping:

- `docs/AGENT_PERSONA_STANDARDS_EVIDENCE_2026-03-02.md`

## Documentation Map

Core docs:

- `docs/DOCUMENTATION_INDEX.md`
- `docs/ARCHITECTURE.md`
- `docs/TESTING_QUALITY_GATES.md`
- `docs/ROADMAP.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/PRODUCTION_PHASE_PLAN.md`
- `docs/PRODUCTION_REVIEW_AUDIT.md`
- `docs/RELEASE_TRUST_PROMOTION_GATE.md`
- `docs/GAP_ANALYSIS.md`
- `docs/LEGACY_ROADMAP_RECONCILIATION_2026-03-03.md`
- `docs/PRODUCTION_STANDARDS_REFERENCES.md`

Agent-specific docs:

- `docs/AGENT_SEMANTIC_BUS_DATA_SYSTEMS_PLAN.md`
- `docs/AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md`
- `docs/AGENT_PERSONA_STANDARDS_EVIDENCE_2026-03-02.md`

## Current Status

- Core phased implementation is complete through production-foundation baseline.
- Multi-agent telemetry, integrations, and persona standards evidence are active in operations APIs and Mission Control.
- Core multi-agent communication/runtime files now enforce 100% coverage via CI and `make test`.
- Mission Control lint, unit, and critical e2e regression coverage are now enforced in CI.
- Remaining maturity work is focused on optional data-plane observability/SLO controls and advanced Mission Control operator UX hardening.

## Notes

- Local Windows mode is supported; the app intentionally does not require a full external user-login system for local operator use.
- Secrets should remain in `.env` and local vault endpoints; do not commit credentials or provider keys.
