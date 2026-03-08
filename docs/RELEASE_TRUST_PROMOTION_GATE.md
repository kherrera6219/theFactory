# Release Trust and Promotion Gate

Last updated: 2026-03-08

## Purpose

Define and enforce signed release-trust controls so promotions fail closed unless provenance attestation and policy checks pass.

## Controls Implemented

1. CI release-trust job in `.github/workflows/ci.yml`:
   - Runs after `lint-test`, `docker-build`, and `sbom`.
   - Limited to `refs/heads/main` and semantic version tags (`refs/tags/v*`).
   - Builds and uploads `reports/release-manifest.json`.
   - Generates provenance attestation with `actions/attest-build-provenance@v2`.
   - Verifies attestation with `gh attestation verify`.
   - Exports a machine-readable agent model inventory.
   - Summarizes qualification evidence against policy thresholds.
   - Evaluates promotion policy using `scripts/promotion_gate.py`.
   - Uploads release-trust evidence artifacts.

2. Promotion policy file:
   - `deploy/promotion-policy.json`
   - Enforces fail-closed behavior.
   - Requires successful CI status and attestation verification.
   - Requires production-approved model routes.
   - Requires qualification evidence to satisfy configured freshness and consecutive-pass thresholds.
   - Restricts promotion refs to `main` and semantic version tags.

3. Promotion policy evaluator:
   - `scripts/promotion_gate.py`
   - Writes machine-readable decision output (`promotion-decision.json`).
   - Returns non-zero on policy violations to block promotion.

4. Supporting gate inputs:
   - `scripts/export_agent_model_inventory.py`
   - `scripts/qualification_gate_summary.py`
   - `.github/workflows/qualification.yml` (weekly qualification cadence)

## Evidence Artifacts

- `release-manifest` artifact:
  - repository/ref/commit/run metadata
  - artifact hash inventory
- `attestation-verification.txt`:
  - attestation verification output
- `promotion-decision.json`:
  - allow/deny decision and rejection reasons
- `agent-model-inventory.json`:
  - per-agent primary/fallback model lifecycle and production-approval status
- `qualification-gate-summary.json`:
  - suite freshness, pass windows, and threshold evaluation

## Local Validation

- Evaluate policy locally:
  - `make promotion-gate`
- Export model inventory locally:
  - `python scripts/export_agent_model_inventory.py`
- Rebuild qualification summary locally:
  - `make qualification-summary`
- Run release-trust script tests:
  - `python -m pytest tests/scripts/test_promotion_gate.py`

## Audit Integration

- `scripts/production_review_audit.py` includes `REL-001` (critical):
  - verifies attestation + promotion-gate workflow controls and policy file presence.
