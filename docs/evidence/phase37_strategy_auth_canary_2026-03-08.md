# Phase 37 Validation — Strategy ADR + Operator OIDC + Dedicated Canary (2026-03-08)

## Scope

1. Close deferred-scope governance gap with canonical decision package.
2. Extend OIDC route policy beyond mutation endpoint to operator telemetry routes.
3. Add dedicated-agent canary qualification tooling with rollback guardrails.

## Implemented

- Strategic deferred-scope ADR:
  - `docs/ADR_STRATEGIC_DEFERRED_SCOPE_DECISIONS_2026-03-08.md`
- v2 adoption design package ADR:
  - `docs/ADR_V2_MISSION_FLOW_ADOPTION_DESIGN_2026-03-08.md`
- API Gateway route-policy expansion:
  - `services/api-gateway/api_gateway/main.py`
  - new controls: `OIDC_OPERATOR_ROLE`, `OIDC_ENFORCE_OPERATOR_ROUTES`
  - enforced on `/v1/operations/*` and `/v1/stream/state` in OIDC/hybrid policies
- Dedicated canary rollout tooling:
  - `scripts/dedicated_agent_canary_rollout.py`
  - `scripts/dedicated_agent_canary_rollout.ps1`
  - `make dedicated-canary`
  - `docs/runbooks/dedicated_agent_canary_runbook.md`

## Tests and Sweep

Commands:

1. `python -m pytest -q tests/services/test_api_gateway_auth_mode_unit.py`
2. `python -m pytest -q tests/scripts/test_dedicated_agent_canary_rollout.py`
3. `python -m pytest -q tests/scripts/test_mission_artifact_qualification.py`
4. `python -m pytest -q tests/services/test_live_mission_flow_integration.py`
5. `python scripts/production_review_audit.py`

Outcome:

- All targeted tests passed.
- Production review audit passed with all controls.
- Documentation and roadmap/phase-plan artifacts updated to remove these items from pending status.
