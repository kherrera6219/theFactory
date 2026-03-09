# Agent Service Key Isolation

Last updated: 2026-03-09

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

## Compose Profiles

- Base compose keeps `AGENT_SERVICE_KEY_MODE=shared` for safe local startup.
- `deploy/docker-compose.prod.yaml` sets worker services to `AGENT_SERVICE_KEY_MODE=strict`.

## Remaining Work

- Rotate and revoke agent service keys through Vault-backed automation.
- Extend strict isolation to the full 35 dedicated-agent topology once that profile exists.
- Add qualification evidence that exercises key revocation and recovery end-to-end.
