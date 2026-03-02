# Mission Control

Next.js application for the HolyGrail user-facing mission console.

## Commands

- `npm install`
- `npm run dev`
- `npm run build`
- `npm run start`

## Environment

- `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8100`)
- Builder preview endpoint expected at `${NEXT_PUBLIC_API_BASE_URL}/v1/builder/preview`

## Application Routes

- `/`: home launch pad and system health overview
- `/chat`: PM Agent chat intake with feature contract confirmation
- `/missions`: mission control center and mission history
- `/missions/[id]`: mission cockpit with phase stepper and live mission signals
- `/agents`: agent and pod monitoring grid
- `/logicnodes`: logic artifact explorer
- `/semantic-bus`: protocol/event stream monitor
- `/databases`: five-database health and runtime diagnostics
- `/repo`: GitHub repository import, file scoping, and mission configuration
- `/settings`: local runtime preferences and key handling

## Standards and Hardening Notes

- TypeScript strict mode is enabled (`tsconfig.json`).
- Security headers are set via `next.config.mjs` (CSP, clickjacking, referrer, permissions, CORP/COOP).
- Accessibility features include skip navigation, aria-live announcements, keyboard focus styling, and semantic tables/captions.
- Mission submission uses idempotency headers and resilient retry/stale-state handling.
- Builder preview supports deterministic local generation and optional live LLM-backed output.
- Local Windows mode is supported without account-login pages.
- Provider/GitHub/operator secrets are managed through local server routes (`/api/vault`, `/api/vault/test`, `/api/operator/mission-state`) and are not persisted in browser storage.
- Keyboard shortcuts are available with `Ctrl+?` and include mission/navigation actions for operator workflows.
