# Phase 38 Validation - Qualification Matrix Automation (2026-03-08)

Document version: 2026.03.08
Last updated: 2026-03-08
Status: Historical Evidence

## Scope

Implement remaining roadmap-follow-up automation:

1. Operator-route auth qualification matrix across `api_key`, `hybrid`, `oidc`.
2. Repeated dedicated-agent canary trend qualification across language routes.
3. Optional LangGraph v2 prototype continuation runner while preserving v1.1 baseline.

## Implemented Artifacts

- `scripts/operator_route_auth_matrix_qualification.py`
- `scripts/operator_route_auth_matrix_qualification.ps1`
- `scripts/dedicated_agent_canary_trend.py`
- `scripts/dedicated_agent_canary_trend.ps1`
- `scripts/langgraph_v2_prototype_matrix.py`
- `scripts/langgraph_v2_prototype_matrix.ps1`
- `docs/runbooks/qualification_matrix_runbook.md`
- `tests/scripts/test_operator_route_auth_matrix_qualification.py`
- `tests/scripts/test_dedicated_agent_canary_trend.py`
- `tests/scripts/test_langgraph_v2_prototype_matrix.py`

## Validation Commands

1. `python -m pytest -q tests/scripts/test_operator_route_auth_matrix_qualification.py`
2. `python -m pytest -q tests/scripts/test_dedicated_agent_canary_trend.py tests/scripts/test_langgraph_v2_prototype_matrix.py`
3. `python -m ruff check scripts/operator_route_auth_matrix_qualification.py scripts/dedicated_agent_canary_trend.py scripts/langgraph_v2_prototype_matrix.py tests/scripts/test_operator_route_auth_matrix_qualification.py tests/scripts/test_dedicated_agent_canary_trend.py tests/scripts/test_langgraph_v2_prototype_matrix.py`
4. `python scripts/production_review_audit.py`
5. `powershell -ExecutionPolicy Bypass -File scripts/debug_sweep.ps1`
6. `python scripts/operator_route_auth_matrix_qualification.py --output-file docs/evidence/operator_route_oidc_matrix_2026-03-08.json`
7. `python scripts/dedicated_agent_canary_trend.py --output-file docs/evidence/dedicated_agent_canary_trend_2026-03-08.json --history-file docs/evidence/dedicated_agent_canary_trend_history.jsonl`
8. `python scripts/langgraph_v2_prototype_matrix.py --allow-prototype-failure --output-file docs/evidence/langgraph_v2_prototype_matrix_2026-03-08.json`

## Validation Results

- Script unit tests: pass (`10/10`).
- Ruff lint checks: pass.
- Production review audit: pass (`14/14`).
- Debug sweep: pass (schemas, full tests, compose config, service health/readiness/metrics checks).
- Live operator auth matrix: pass (`api_key`, `hybrid`, `oidc`).
- Live dedicated canary trend: pass (`python`, `rust`, `kotlin`, `julia`; pass rate `100%`).
- Live baseline/prototype matrix: pass (`v1_1_baseline=true`, `langgraph_v2_prototype=true`).

## Evidence Files

- `docs/evidence/operator_route_oidc_matrix_2026-03-08.json`
- `docs/evidence/dedicated_agent_canary_trend_2026-03-08.json`
- `docs/evidence/dedicated_agent_canary_trend_history.jsonl`
- `docs/evidence/langgraph_v2_prototype_matrix_2026-03-08.json`

## Outcome

- Roadmap open follow-up items are operationalized with repeatable automation and evidence output paths.
- New commands exposed via Makefile:
  - `make oidc-matrix`
  - `make dedicated-canary-trend`
  - `make langgraph-v2-prototype`
- v1.1 remains canonical production default; v2 prototype execution stays explicitly feature-flagged.
