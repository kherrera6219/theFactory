# Release Trust and Promotion Gate

Last updated: 2026-03-03

## Purpose

Define and enforce signed release-trust controls so promotions fail closed unless provenance attestation and policy checks pass.

## Controls Implemented

1. CI release-trust job in `.github/workflows/ci.yml`:
   - Runs after `lint-test`, `docker-build`, and `sbom`.
   - Limited to `refs/heads/main` and semantic version tags (`refs/tags/v*`).
   - Builds and uploads `reports/release-manifest.json`.
   - Generates provenance attestation with `actions/attest-build-provenance@v2`.
   - Verifies attestation with `gh attestation verify`.
   - Evaluates promotion policy using `scripts/promotion_gate.py`.
   - Uploads release-trust evidence artifacts.

2. Promotion policy file:
   - `deploy/promotion-policy.json`
   - Enforces fail-closed behavior.
   - Requires successful CI status and attestation verification.
   - Restricts promotion refs to `main` and semantic version tags.

3. Promotion policy evaluator:
   - `scripts/promotion_gate.py`
   - Writes machine-readable decision output (`promotion-decision.json`).
   - Returns non-zero on policy violations to block promotion.

## Evidence Artifacts

- `release-manifest` artifact:
  - repository/ref/commit/run metadata
  - artifact hash inventory
- `attestation-verification.txt`:
  - attestation verification output
- `promotion-decision.json`:
  - allow/deny decision and rejection reasons

## Local Validation

- Evaluate policy locally:
  - `make promotion-gate`
- Run release-trust script tests:
  - `python -m pytest tests/scripts/test_promotion_gate.py`

## Audit Integration

- `scripts/production_review_audit.py` includes `REL-001` (critical):
  - verifies attestation + promotion-gate workflow controls and policy file presence.
