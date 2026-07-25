# Mission Control

Document version: 2026.06.14
Last updated: 2026-06-14
Status: Canonical

Mission Control is the Next.js operator console for theFactory.

It is designed for local-first Windows operation and provides real-time visibility into missions, agents, protocol-bus activity, and runtime controls.

## Responsibilities

- Display global runtime and mission health.
- Provide mission operations and status workflows.
- Visualize 41-agent topology and telemetry.
- Render full agent persona profiles with governance evidence.
- Surface protocol bus and artifact-level observability.
- Manage local runtime preferences, vault-backed integration secrets, and
  per-slot model metadata for the approved 3-model catalog.
- Surface agent model keys and Knowledge Embedding Key setup paths. Local Mission
  Control starts unlocked; the internal service key is stack configuration, not
  a user-facing vault row.

## Run Locally

1. Install dependencies:
   - `npm install`
2. Set environment:
   - `.env.local` (or inherited root env) with `NEXT_PUBLIC_API_BASE_URL`
   - `ORCHESTRATOR_INTERNAL_BASE_URL` for durable review approval persistence
   - `INTERNAL_SERVICE_API_KEY` matching the orchestrator internal service key
   - `APPROVAL_HMAC_SECRET` for signed approval records and launch-time integrity checks
   - `OPERATOR_SESSION_BYPASS=true` for the default local unlocked operator console
3. Start dev server:
   - `npm run dev`
4. Build production bundle:
   - `npm run build`
5. Start the server build:
   - `npm run start`
6. Lint:
   - `npm run lint`

`npm run dev`, `npm run build`, and `npm run start` set
`NEXT_BUILD_TARGET=docker`, which keeps server routes such as
`/api/gateway/[...path]`, `/api/vault`, and `/api/pm/feature-contract`
available. Static export builds are only for Electron packaging; they must be
served from `out/` rather than started with `next start`.

## Environment

- `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8100`)
- `ORCHESTRATOR_INTERNAL_BASE_URL` (default `http://localhost:8101`)
- `INTERNAL_SERVICE_API_KEY` (required for internal service-to-service calls and review approval persistence)
- `APPROVAL_HMAC_SECRET` (required for review approval signing and verification)
- `APPROVAL_TTL_SECONDS` (default `86400`)
- `OPERATOR_SESSION_BYPASS` (default `true` in the local Docker profile; keeps Mission Control unlocked from startup)
- `MISSION_CONTROL_BYPASS_AUTH` (legacy alias for the same local bypass behavior)
- `MISSION_CONTROL_ADMIN_KEY` (optional only when running a locked deployment profile)
- `MISSION_CONTROL_SESSION_SECRET` (optional signing secret for locked deployment profiles)
- `MISSION_CONTROL_SESSION_TTL_SECONDS` (default `28800`)
- `MISSION_CONTROL_SESSION_SECURE` (`true` for HTTPS production deployments)
- `VAULT_ADMIN_KEY` (optional break-glass header auth for scripted `/api/vault` access)
- Vault model metadata:
  - Supported UI model routes: `gpt-5.5`, `claude-opus-4-8`,
    `gemini-3.6-flash`
  - Runtime default: all 41 agents use `gemini-3.6-flash` with high thinking

- Required vault slots for local mission testing:
  - Agent API key slots (`AGENT-01-PM-API-KEY` through `AGENT-41-RQCA-API-KEY`)
    for the approved 3-model catalog.
  - `KNOWLEDGE-EMBEDDING-API-KEY`: tracks the key intended for semantic
    knowledge-lake embeddings; mirror this value to
    `KNOWLEDGE_EMBEDDING_API_KEY` in the orchestrator container environment
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
- `/agents`: 41-agent runtime grid with persona detail.
- `/logicnodes`: artifact explorer.
- `/protocol-bus`: protocol/event monitor.
- `/databases`: data-plane status.
- `/repo`: repo scope and source controls.
- `/settings`: runtime preferences and secret-slot management.

## Agent Persona UI

Agent detail includes:

- Runtime telemetry (state, queue, workload, missions).
- Runtime class:
  - `WORKER` means the agent runs through the shared pod-worker runtime.
  - `MANAGED` means the orchestrator manages the control/support role and emits
    its heartbeat. This is expected for interface, executive, and support agents
    in the default condensed local topology.
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
  - POST save slot secret plus provider/model metadata
  - DELETE clear slot
- `/api/vault/test`:
  - validate provider key formats or test checks
- `/api/review/approve`:
  - persist review approvals through orchestrator-backed durable storage before mission launch
- `/api/review/verify`:
  - re-validate approval integrity and expiry before the mission launch call is sent
- `/api/operator/mission-state`:
  - safely forward mission state transitions using server-side key resolution

## Security and Accessibility Notes

- TypeScript strict mode is enabled.
- A Content-Security-Policy is enforced via a `<meta http-equiv>` tag in the root layout (`app/layout.tsx`). Static Electron export builds use `output: export`, where `next.config.mjs` `headers()` is ignored, so the CSP ships as a meta tag instead.
- API consumption uses timeout-based request guards and resilient parsing.
- Mission Control local operation starts unlocked through `OPERATOR_SESSION_BYPASS=true`.
  Locked deployment profiles can disable bypass and require a signed operator session.
- Review approvals fail closed if the orchestrator internal base URL, service API key, or approval HMAC secret is missing.
- Accessibility includes semantic tables, captions, skip-navigation support, and keyboard focus visibility.
- Local operation mode intentionally avoids external account-login and operator-unlock requirements.

## Related Backend Endpoints

- `GET /v1/operations/agents`
- `GET /v1/operations/agent-integrations`
- `GET /v1/operations/summary`
- `GET /v1/missions`
- `GET /v1/missions/{mission_id}`
- `GET /v1/missions/{mission_id}/events`
- `POST /v1/missions`
- `POST /v1/missions/{mission_id}/state`
