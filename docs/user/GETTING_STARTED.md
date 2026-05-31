# Getting Started

Document version: 2026.04.14  
Last updated: 2026-04-14  
Status: Canonical  
Audience: Operators and developers

## Who This Is For

This guide is for operators and developers using Mission Control to submit, review, and monitor missions in `theFactory`.

## Prerequisites

- Docker Desktop with Compose support
- Python 3.11 or newer
- Node.js 20 or newer
- a populated `.env` file derived from [`.env.example`](../../.env.example)

## Start The Stack

From the repository root:

```powershell
docker compose -f deploy/docker-compose.yaml up -d
```

Mission Control runs at `http://localhost:3100` in the Docker stack.

If you run the Next.js app directly with `npm run dev`, Mission Control runs at `http://localhost:3000`.

The API Gateway runs at `http://localhost:8100`.

## First Success Path

1. Open Mission Control at `http://localhost:3100`.
2. Unlock Mission Control with `MISSION_CONTROL_ADMIN_KEY`.
3. Visit `Settings` and confirm any required provider or GitHub credentials are loaded.
4. Open `Chat` if you want PM-style mission intake from a prompt and optional attached files.
5. Open `Builder` if you want a grounded local-workspace review before launch.
6. Open `Repo Import` if you want to review selected GitHub files and turn that review into a mission bundle.
7. Launch the mission and switch to `Missions` or the mission detail page to watch live state changes.
8. For source-bundle missions, confirm the `Build Artifacts` section on the mission detail page shows a successful packaged artifact before treating the mission as release-ready.

## Main Screens

- `Home`: high-level platform and health summary
- `Chat`: PM-driven mission drafting and launch flow
- `Missions`: recent missions and mission state transitions
- `Agents`: live roster, workload, and heartbeat telemetry
- `LogicNodes`: extracted graph fragments and mission-linked nodes
- `Protocol Bus`: protocol traffic and live event inspection
- `Databases`: optional data-plane adapter health and summary
- `Repo Import`: grounded GitHub review and launch flow
- `Settings`: preferences, vault slots, and integration state

## Grounded Review Flows

Two review flows are intentionally gated before mission execution:

- `Builder review`: packages a local workspace preview and produces a review fingerprint
- `Repo review`: fetches selected GitHub files, builds a grounded source bundle, and produces a review fingerprint

Both flows require an active operator session and a durable approval record before the final mission launch step. Mission Control re-validates the stored approval receipt immediately before launch and rejects expired or tampered approvals.

## Troubleshooting

- If Mission Control loads but data panels fail, check `http://localhost:8100/health`.
- If agent or mission live updates stall, verify the gateway SSE endpoint at `http://localhost:8100/v1/stream/state`.
- If review flows fail, confirm required API keys are present in `Settings`.
- If Mission Control cannot be unlocked, confirm `MISSION_CONTROL_ADMIN_KEY` and `MISSION_CONTROL_SESSION_SECRET` are set for the Mission Control process.
- If review approvals fail, confirm `ORCHESTRATOR_INTERNAL_BASE_URL`, `INTERNAL_SERVICE_API_KEY`, and `APPROVAL_HMAC_SECRET` are set for Mission Control.
- If scripted vault access fails, confirm the request includes `x-vault-admin-key` and that `VAULT_ADMIN_KEY` is configured.
- If startup fails after the recent auth hardening changes, confirm service API keys are explicitly set in your environment instead of relying on Compose fallbacks.
- If a source-bundle mission remains `VERIFIED` and does not advance to `COMPLETE`, inspect the mission detail `Build Artifacts` section or call `GET /v1/missions/{mission_id}/build-artifacts` to confirm packaging status.

## Next References

- Architecture overview: [../ARCHITECTURE.md](../ARCHITECTURE.md)
- Runtime status: [../IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md)
- Developer onboarding: [../DEVELOPER_ONBOARDING_GUIDE.md](../DEVELOPER_ONBOARDING_GUIDE.md)
- Operations runbook: [../OPERATIONS_RUNBOOK.md](../OPERATIONS_RUNBOOK.md)
