# Qualification Matrix Runbook

Last updated: 2026-03-08

## Purpose

Execute recurring roadmap follow-up qualifications:

1. Operator-route auth matrix across `api_key`, `hybrid`, and `oidc`.
2. Dedicated-agent canary trend evidence across multiple language routes.
3. Optional v2 prototype matrix while preserving v1.1 baseline.

## Preconditions

1. Core stack is reachable (`api-gateway`, `orchestrator`, `redis`, `postgres`, `qdrant`).
2. `python` and `docker` are available on the host.
3. `.env` has `OIDC_SHARED_SECRET` if OIDC matrix tokens should match local config.

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

## Evidence Outputs

1. `docs/evidence/operator_route_oidc_matrix_latest.json`
2. `docs/evidence/dedicated_agent_canary_trend_latest.json`
3. `docs/evidence/dedicated_agent_canary_trend_history.jsonl`
4. `docs/evidence/langgraph_v2_prototype_matrix_latest.json`

## Failure Triage

1. Matrix 401/403 mismatch:
   - verify `AUTH_MODE`, `OIDC_*`, and gateway `/health`.
2. Canary trend failure:
   - inspect per-language report in `docs/evidence/canary-runs`.
3. Prototype matrix baseline failure:
   - treat as release-risk; run `scripts/debug_sweep.ps1` and `tests/services/test_live_mission_flow_integration.py`.
