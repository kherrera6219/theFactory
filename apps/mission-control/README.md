# Mission Control

Mission Control is the Next.js operator console for theFactory.

It is designed for local-first Windows operation and provides real-time visibility into missions, agents, semantic-bus activity, and runtime controls.

## Responsibilities

- Display global runtime and mission health.
- Provide mission operations and status workflows.
- Visualize 35-agent topology and telemetry.
- Render full agent persona profiles with governance evidence.
- Surface semantic bus and artifact-level observability.
- Manage local runtime preferences and vault-backed integration secrets.

## Run Locally

1. Install dependencies:
   - `npm install`
2. Set environment:
   - `.env.local` (or inherited root env) with `NEXT_PUBLIC_API_BASE_URL`
3. Start dev server:
   - `npm run dev`
4. Build production bundle:
   - `npm run build`
5. Start production server:
   - `npm run start`
6. Lint:
   - `npm run lint`

## Environment

- `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8100`)
- Optional HashiCorp Vault KV backend:
  - `VAULT_ADDR`
  - `VAULT_TOKEN` or `VAULT_ROLE_ID` + `VAULT_SECRET_ID`
  - `VAULT_NAMESPACE`
  - `VAULT_KV_MOUNT` (default `secret`)
  - `VAULT_KV_PREFIX` (default `thefactory/mission-control`)

Mission Control expects Gateway routes under:

- `/v1/*` for mission and operations endpoints.

## Key Routes

- `/`: launch overview.
- `/dashboard`: runtime summary and status.
- `/chat`: PM-style intake surface.
- `/missions`: mission list and controls.
- `/missions/[id]`: mission cockpit detail.
- `/agents`: 35-agent runtime grid with persona detail.
- `/logicnodes`: artifact explorer.
- `/semantic-bus`: protocol/event monitor.
- `/databases`: data-plane status.
- `/repo`: repo scope and source controls.
- `/settings`: runtime preferences and secret-slot management.

## Agent Persona UI

Agent detail includes:

- Runtime telemetry (state, queue, workload, missions).
- 8-part persona structure:
  - job role
  - education/certifications
  - traits/skills
  - methods/procedures
  - tools
  - master instruction
  - protocol profile
  - API configuration
- Governance extension fields:
  - standards alignment mappings
  - evidence source links and verification dates

## Local API Routes (Server Side)

- `/api/vault`:
  - GET vault slot metadata
  - POST save slot secret
  - DELETE clear slot
- `/api/vault/test`:
  - validate provider key formats or test checks
- `/api/operator/mission-state`:
  - safely forward mission state transitions using server-side key resolution

## Security and Accessibility Notes

- TypeScript strict mode is enabled.
- Security headers are set via `next.config.mjs`.
- API consumption uses timeout-based request guards and resilient parsing.
- Accessibility includes semantic tables, captions, skip-navigation support, and keyboard focus visibility.
- Local operation mode intentionally avoids external account-login requirements.

## Related Backend Endpoints

- `GET /v1/operations/agents`
- `GET /v1/operations/agent-integrations`
- `GET /v1/operations/summary`
- `GET /v1/missions`
- `GET /v1/missions/{mission_id}`
- `GET /v1/missions/{mission_id}/events`
- `POST /v1/missions`
- `POST /v1/missions/{mission_id}/state`
