# Phase 30 Validation - Auth Mode + Dedicated Profile Baseline (2026-03-04)

## Objective
Execute the accepted ADR decisions by implementing:
1. Gateway auth-mode abstraction for API key and JWT/OIDC flows.
2. Dedicated-agent compose profile scaffolding for trigger-based topology expansion.

## Implementation
- Gateway auth mode:
  - `services/api-gateway/api_gateway/main.py`
  - Added `AUTH_MODE=api_key|hybrid|oidc`
  - Added OIDC validation controls (`OIDC_*`) and claim-role enforcement for mutation route authorization.
  - Added forwarding policy:
    - API-key mode forwards caller key.
    - OIDC and bearer-hybrid mode forward `INTERNAL_SERVICE_API_KEY` after gateway validation.
- Dedicated profile scaffolding:
  - `deploy/docker-compose.yaml`
  - Added `--profile dedicated-agents` manager-worker services with per-pod `AGENT_BINDING`.
- Config and dependency updates:
  - `.env.example`
  - `services/api-gateway/requirements.txt` (`PyJWT[crypto]`)
- Regression coverage:
  - `tests/services/test_api_gateway_auth_mode_unit.py`

## Validation Commands and Results
1. `python -m pytest -q tests/services/test_api_gateway_auth_mode_unit.py tests/security/test_state_mutation_auth.py`
   - Result: pass
2. `python -m pytest -q tests/services/test_production_foundations.py`
   - Result: pass
3. `python -m ruff check services/api-gateway/api_gateway/main.py tests/services/test_api_gateway_auth_mode_unit.py`
   - Result: pass
4. `docker compose -f deploy/docker-compose.yaml config`
   - Result: pass
5. `npm --prefix apps/mission-control run lint`
   - Result: pass
6. `npm --prefix apps/mission-control run test`
   - Result: pass
7. `python scripts/production_review_audit.py`
   - Result: pass (`12/12`)
8. `python scripts/check_coverage_thresholds.py --coverage-file coverage.xml --global-threshold 80 ...`
   - Result: pass
9. `powershell -ExecutionPolicy Bypass -File scripts/debug_sweep.ps1`
   - Result: pass when `PYTHONPATH` includes `services/pod-worker` for optional pod-worker concept extraction tests present in active workspace.
