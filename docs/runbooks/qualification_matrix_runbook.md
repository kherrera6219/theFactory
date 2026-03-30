# Qualification Matrix Runbook

Document version: 2026.03.29  
Last updated: 2026-03-29  
Status: Canonical  
Audience: Operators, developers, maintainers, and auditors

## Purpose

Execute recurring roadmap follow-up qualifications:

1. Operator-route auth matrix across `api_key`, `hybrid`, and `oidc`.
2. Dedicated-agent canary trend evidence across multiple language routes.
3. Optional v2 prototype matrix while preserving v1.1 baseline.
4. Live mission artifact / chain-of-command qualification.

## Preconditions

1. Core stack is reachable (`api-gateway`, `orchestrator`, `redis`, `postgres`, `qdrant`).
2. `python` and `docker` are available on the host.
3. `.env` has `OIDC_SHARED_SECRET` if OIDC matrix tokens should match local config.
4. For dedicated-agent canary runs, start the dedicated manager profile: `docker compose -f deploy/docker-compose.yaml --profile dedicated-agents up -d`

## Commands

1. Operator-route OIDC matrix:
   - `powershell -ExecutionPolicy Bypass -File scripts/operator_route_auth_matrix_qualification.ps1`
   - or `make oidc-matrix`
2. Dedicated canary trend:
   - `powershell -ExecutionPolicy Bypass -File scripts/dedicated_agent_canary_trend.ps1`
   - or `make dedicated-canary-trend`
3. v1.1 baseline + v2 prototype matrix:
   - `powershell -ExecutionPolicy Bypass -File scripts/langgraph_v2_prototype_matrix.ps1`
   - or `make langgraph-v2-prototype`
4. Mission artifact qualification:
   - `python scripts/mission_artifact_qualification.py`
5. Qualification gate summary:
   - `python scripts/qualification_gate_summary.py --policy-file deploy/promotion-policy.json`
   - or `make qualification-summary`

## Evidence Outputs

1. `docs/evidence/operator_route_oidc_matrix_latest.json`
2. `docs/evidence/dedicated_agent_canary_trend_latest.json`
3. `docs/evidence/dedicated_agent_canary_trend_history.jsonl`
4. `docs/evidence/operator_route_oidc_matrix_history.jsonl`
5. `docs/evidence/langgraph_v2_prototype_matrix_latest.json`
6. `docs/evidence/langgraph_v2_prototype_matrix_history.jsonl`
7. `docs/evidence/mission_artifact_qualification_latest.json`
8. `docs/evidence/mission_artifact_qualification_history.jsonl`
9. `docs/evidence/qualification_gate_summary_latest.json`

## Failure Triage

1. Matrix 401/403 mismatch:
   - verify `AUTH_MODE`, `OIDC_*`, and gateway `/health`.
2. Canary trend failure:
   - inspect per-language report in `docs/evidence/canary-runs`.
3. Prototype matrix baseline failure:
   - treat as release-risk; run `scripts/debug_sweep.ps1` and `tests/services/test_live_mission_flow_integration.py`.
4. Mission artifact qualification failure:
   - inspect chain trace, pod assignment, and LogicNode evidence for the generated mission.
5. Qualification summary failure:
   - inspect stale or failed suite entries before re-running `make promotion-gate`
