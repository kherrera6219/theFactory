# Dedicated-Agent Canary Runbook

Document version: 2026.07.03  
Last updated: 2026-07-03  
Status: Canonical  
Audience: Operators, developers, maintainers, and auditors

## Purpose

Run a repeatable canary mission that validates dedicated-agent routing contract integrity before broader rollout.

## Preconditions

1. Stack is healthy (`/readyz` on gateway + orchestrator).
2. Dedicated-agent profile is active when validating dedicated workers. **Always pair both
   compose files** — running the base file alone without the overlay has caused real
   restart-cascade incidents in this project (see `docs/OPERATIONS_RUNBOOK.md`):
   - `docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents up -d`
3. Mission Control/gateway auth mode is configured for the environment under test.

## Execute Canary

PowerShell:
- `powershell -ExecutionPolicy Bypass -File scripts/dedicated_agent_canary_rollout.ps1`

Make target:
- `make dedicated-canary`

Direct Python with explicit output artifact:
- `python scripts/dedicated_agent_canary_rollout.py --language python --output-file docs/evidence/dedicated_agent_canary_rollout_latest.json`

## Pass Criteria

1. Mission reaches `COMPLETE`.
2. Chain trace includes PM, CEO, pod-manager, and specialist assignment events.
3. Mission metadata shows `routing_enforced=true` with expected PM/CEO fields.
4. Non-empty pod assignment and LogicNode artifacts exist.
5. Report includes `rollback_recommended=false`.

## Rollback Guardrails

Rollback immediately if any canary report contains:

1. `rollback_recommended=true`
2. Missing chain events or missing execution artifacts
3. `MISSION_COMPLETION_BLOCKED` during canary mission

Rollback action:

1. Disable dedicated profile services:
   - `docker compose -f deploy/docker-compose.yaml down`
   - `docker compose -f deploy/docker-compose.yaml up -d`
2. Re-run baseline qualification:
   - `python scripts/mission_artifact_qualification.py --profile-label shared-workers`
