# Phase 40 Evidence: Supply Chain Integrity and Secret Hygiene

Document version: 2026.03.03
Last updated: 2026-03-03
Status: Historical Evidence

Date: 2026-03-29

## Summary

Phase 40 hardened the repository-local supply chain and release-trust path.

- GitHub Actions workflows now run with explicit minimal top-level permissions and `actions/checkout` disables credential persistence.
- Release evidence can now be validated locally with `scripts/verify_release_evidence.py` and `make release-evidence-verify`.
- Release trust and security documentation now describe the required repo settings, attestation expectations, and the remaining manual blockers.
- Compose environment documentation now states that live secrets must be injected and that development TLS material must be generated locally rather than tracked.

## Repository-Local Changes

- `.github/workflows/ci.yml`
  - Added explicit top-level `permissions: contents: read`
  - Added `persist-credentials: false` to checkout
- `.github/workflows/security.yml`
  - Added explicit top-level `permissions: contents: read`
  - Added `persist-credentials: false` to checkout
- `.github/workflows/qualification.yml`
  - Added explicit top-level `permissions: contents: read`
  - Added `persist-credentials: false` to checkout
- `scripts/verify_release_evidence.py`
  - Added offline validation for release manifest, attestation verification output, promotion decision, and optional SBOM evidence
- `tests/scripts/test_verify_release_evidence.py`
  - Added focused regression coverage for the release evidence validator
- `Makefile`
  - Added `release-evidence-verify`
- `README.md`
  - Added the release-evidence verification command to the common command set
- `SECURITY.md`
  - Added release-trust verification guidance and documented the remaining git-history cleanup blocker
- `docs/RELEASE_TRUST_PROMOTION_GATE.md`
  - Added local validation flow and repository administration requirements
- `docs/COMPOSE_ENVIRONMENT_PROFILES.md`
  - Added release evidence validation, secret injection requirements, and developer TLS generation expectations

## Mandatory Sweep Results

### Core sweep

- `python -m pytest -q`
  - PASS
- `python -m pytest --cov=services --cov-report=term-missing --cov-report=xml --cov-fail-under=80`
  - PASS
  - Result: `81.37%` services coverage
  - Result: `692 passed, 5 skipped`

### Frontend sweep

- `cd apps/mission-control && npm run lint`
  - PASS
- `cd apps/mission-control && npm test`
  - PASS
  - Result: `8` files, `37` tests

### Runtime/config sweep

- `docker compose -f deploy/docker-compose.yaml config -q`
  - PASS
- `python -m ruff check services tests scripts`
  - VARIANCE
  - Reason: pre-existing repository-wide lint debt in untouched files. No Phase 40 files introduced new ruff violations.

### Targeted Phase 40 regressions

- `python -m pytest -q tests/scripts/test_verify_release_evidence.py tests/scripts/test_promotion_gate.py`
  - PASS
  - Result: `11 passed`

## Manual Checklist

- No new secrets, tokens, or private keys were introduced in tracked files during this phase.
- Release workflow permissions are now explicit and minimal at the workflow level.
- Release verification now has a local fail-closed command path for evidence validation.
- Updated docs match the implemented repo-local release trust behavior.

## Out-of-Band Requirements

These items are required for Phase 40 completion but cannot be fully remediated from the working tree alone.

- Scrub the previously committed TLS private keys from git history and rotate any affected material.
- Enable GitHub secret scanning and push protection at the repository or organization level.
- Enforce branch protection and required status checks for CI, security, and release-trust workflows.
- Require attestation verification in the production release promotion process.

## Runbook Links

- `docs/RELEASE_TRUST_PROMOTION_GATE.md`
- `SECURITY.md`
- `docs/COMPOSE_ENVIRONMENT_PROFILES.md`
