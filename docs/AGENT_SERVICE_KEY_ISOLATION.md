# Agent Service Key Isolation

Document version: 2026.04.15  
Last updated: 2026-04-15  
Status: Canonical  
Audience: Maintainers, operators, and security reviewers

## Purpose

Internal worker mutations to orchestrator can now use agent-scoped control-plane keys instead of a
single shared `worker-key`.

## Canonical Env Pattern

- `AGENT_<NN>_<CODE>_SERVICE_API_KEY`
- Examples:
  - `AGENT_10_TESTER_SERVICE_API_KEY`
  - `AGENT_14_PYTHON_SERVICE_API_KEY`
  - `AGENT_30_PODD_MGR_SERVICE_API_KEY`

Runtime services also support:

- `AGENT_SERVICE_KEY_MODE=shared|strict`
- `AGENT_SERVICE_API_KEYS=AGENT-14-PYTHON=key-a;AGENT-15-JAVASCRIPT=key-b`

`shared` falls back to the service-level key when an agent-specific key is missing. `strict`
rejects the mutation path if the active agent has no dedicated key.

## Current Runtime Behavior

- `pod-worker` resolves the active mission `agent_id` and selects the matching dedicated key for
  `/internal/pod-assignment`, `/internal/logicnodes`, and `/internal/knowledge`.
- `audit-worker` uses `WORKER_AGENT_ID` and the matching dedicated key for
  `/internal/audit-reports`.
- Orchestrator automatically accepts configured agent-scoped service keys with
  `worker, mutate, internal, read` roles.
- `pod-worker` and `audit-worker` now recreate their Redis consumer groups after a Redis restart,
  so strict dedicated workers recover without a manual container restart.

## Compose Profiles

- Base compose keeps `AGENT_SERVICE_KEY_MODE=shared` for safe local startup.
- `deploy/docker-compose.prod.yaml` sets worker services to `AGENT_SERVICE_KEY_MODE=strict`.
- `deploy/docker-compose.full-dedicated-agents.yaml` now binds each dedicated runtime container to
  its own `AGENT_<NN>_<CODE>_SERVICE_API_KEY` value.

## Local Key Provisioning

- Generate a local ignored env file:
  - `python scripts/generate_agent_service_keys.py`
- Default output:
  - `.env.agent-service-keys.local`
- Generated env entries include:
  - `AGENT_SERVICE_KEY_MODE`
  - `INTERNAL_SERVICE_API_KEY`
  - `AGENT_<NN>_<CODE>_SERVICE_API_KEY` for every canonical agent
- Use it with the strict full dedicated stack:
  - `docker compose --env-file .env.agent-service-keys.local -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents up -d --build`

## Live Qualification Evidence

- Strict full-dedicated qualification passed on 2026-03-09:
  - `docs/evidence/mission_artifact_qualification_full_dedicated_strict_2026-03-09.json`
  - `docs/evidence/dedicated_agent_canary_full_dedicated_strict_2026-03-09.json`
- Strict full-dedicated qualification was refreshed on 2026-04-15 after the dedicated Go/Haskell/OCaml worker addition and gateway internal-auth wiring fix:
  - `docs/evidence/mission_artifact_qualification_full_dedicated_local_2026-04-15.json`
  - `docs/evidence/dedicated_agent_canary_full_dedicated_local_2026-04-15.json`
- The current full dedicated topology provisions all dedicated worker groups, including:
  - `dedicated-workers-podA`
  - `dedicated-workers-podB`
  - `dedicated-workers-podC`
  - `dedicated-workers-podD`
  - `dedicated-agent-14-python` through `dedicated-agent-38-ocaml`

## Remaining Work

- Rotate and revoke agent service keys through Vault-backed automation.
- Add qualification evidence that exercises key revocation and recovery end-to-end.
