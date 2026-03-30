# Phase 29 Validation - Topology and Security ADR Decision Package (2026-03-04)

## Objective
Close the final two Word-doc reconciliation gaps by publishing canonical decisions for:
1. 35-agent runtime topology model.
2. Security architecture model (API keys vs JWT/OIDC).

## Published Artifacts
- `docs/ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md`
- `docs/ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md`

## Decision Outcomes
- Topology ADR: accepted hybrid strategy (condensed worker baseline plus trigger-based dedicated-agent expansion path).
- Security ADR: accepted dual-mode auth strategy (`api_key`, `hybrid`, `oidc`) with backward-compatible migration plan.

## Canonical Backlog Reconciliation
- Updated:
  - `docs/ROADMAP.md`
  - `docs/archive/2026-03-29/historical/UPDATED_TODO_FROM_WORD_AUDIT_2026-03-03.md`
  - `docs/COMPLETION_TODO_2026-03-02.md`
  - `docs/UPDATED_PHASE_PLAN_2026-03-03.md`
  - `docs/DOCUMENTATION_INDEX.md`

## Validation Commands and Results
1. `npm --prefix apps/mission-control run lint`
   - Result: pass
2. `npm --prefix apps/mission-control run test`
   - Result: pass
3. `python -m pytest -q tests/services/test_runtime_unit.py tests/services/test_langgraph_lifecycle_unit.py`
   - Result: pass
4. `python scripts/production_review_audit.py`
   - Result: pass (`12/12`)
5. `python scripts/check_coverage_thresholds.py --coverage-file coverage.xml --global-threshold 80 ...`
   - Result: pass
6. `powershell -ExecutionPolicy Bypass -File scripts/debug_sweep.ps1`
   - Result: pass when `PYTHONPATH` includes `services/pod-worker` for optional pod-worker concept-extraction tests present in working tree.
