# Contributing to theFactory

Document version: 2026.04.17  
Last updated: 2026-04-17  
Status: Canonical

Thank you for contributing to theFactory (HolyGrail Multi-Agent Software Refinery).

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Setup](#local-setup)
- [Branch Naming](#branch-naming)
- [Commit Format](#commit-format)
- [Pull Request Process](#pull-request-process)
- [Code Quality Gates](#code-quality-gates)
- [Testing](#testing)
- [Security](#security)

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 22+ |
| Docker | 24+ |
| Docker Compose | v2 |
| Git | 2.40+ |

---

## Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/kherrera6219/thefactory.git
cd thefactory

# 2. Copy environment file and fill in all CHANGE_ME values
cp .env.example .env
# Generate secrets: openssl rand -hex 32

# 3. Install Python dev dependencies
pip install -r requirements-dev.txt
pip install -r services/api-gateway/requirements.txt
pip install -r services/orchestrator/requirements.txt
pip install -r services/pod-worker/requirements.txt
pip install -r services/audit-worker/requirements.txt
pip install -r services/protocol-bus-mcp/requirements.txt

# 4. Install Mission Control dependencies
cd apps/mission-control && npm ci && cd ../..

# 5. Start the stack
docker compose -f deploy/docker-compose.yaml up -d

# 6. Run all tests
pytest --cov=services --cov-fail-under=80
cd apps/mission-control && npm test
```

---

## Branch Naming

```
<type>/<short-description>

Types:
  feat      — new feature or capability
  fix       — bug fix
  docs      — documentation only
  refactor  — code change that is not a fix or feature
  test      — adding or fixing tests
  chore     — build, CI, dependency updates
  security  — security-only fix

Examples:
  feat/langgraph-v2-checkpointer
  fix/vault-auth-missing
  docs/developer-onboarding-guide
  security/harden-api-keys
```

---

## Commit Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

[optional body — explain WHY not WHAT]

[optional footer: Breaking Change, Closes #issue]
```

**Examples:**

```
feat(orchestrator): add mission-flow v2 specialist_assigned phase

fix(api-gateway): remove hardcoded worker-key default

Closes #42

security(vault): require VAULT_ADMIN_KEY on all vault API routes

BREAKING CHANGE: /api/vault now requires x-vault-admin-key header
```

- **Subject**: 72 characters max, present tense, no period
- **Scope**: service name (`orchestrator`, `api-gateway`, `mission-control`, etc.)
- **Body**: explain _why_ the change is made, not _what_

---

## Pull Request Process

1. **Open a draft PR early** — get early feedback on approach before investing heavily
2. **Link related issues** — `Closes #<issue>` in PR description
3. **Self-review first** — review your own diff before requesting review
4. **Fill in the PR template** — all checklist items must be addressed
5. **Squash commits** — keep the merge commit history clean
6. **Do not force-push to `main`** — always use PRs

### PR Checklist

- [ ] All CI checks pass (lint, tests, build, security scan)
- [ ] Coverage does not regress below line 80%, branch 70%, mixed 80%, or module thresholds
- [ ] New environment variables added to `.env.example` with `CHANGE_ME_` placeholders
- [ ] Any new API endpoints have auth guards and are tested
- [ ] Secrets removed or replaced with env variable references
- [ ] Breaking API contract changes documented in PR description
- [ ] Relevant docs updated

---

## Code Quality Gates

The CI pipeline enforces:

| Gate | Tool | Threshold |
|------|------|-----------|
| Python lint | `ruff` | Zero errors |
| TypeScript lint | `tsc --noEmit` | Zero errors |
| Python tests | `pytest` | line ≥80%, branch ≥70%, mixed ≥80% |
| Critical module coverage | `check_coverage_thresholds.py` | Every critical file ≥80% (some protocol files 90–100%) |
| SAST | `bandit` | Zero high/critical |
| Dependency audit | `pip-audit`, `npm audit` | Zero high/critical CVEs |
| Secret scan | `gitleaks` | Zero secrets |
| Container CVEs | `trivy` | Zero high/critical |
| Performance budget | Lighthouse CI | Pass |
| E2E tests | Playwright | Pass |

---

## Testing

```bash
# Python unit + integration tests
pytest

# With coverage report
pytest --cov=services --cov-report=term-missing

# TypeScript unit tests
cd apps/mission-control && npm test

# E2E tests (requires running stack)
cd apps/mission-control && npm run test:e2e

# Performance budget
cd apps/mission-control && npm run test:perf

# Load tests (requires running stack)
cd tests/load && locust -f locustfile.py
```

All tests must pass before merging. Do not write tests that assert buggy behavior to inflate coverage.

---

## Security

- **Never commit secrets** — all credentials belong in `.env` (gitignored) or a secret manager
- **All API keys** must be generated with `openssl rand -hex 32` — no human-readable values
- **Report vulnerabilities** via the process described in [SECURITY.md](SECURITY.md)
- **Sign release tags** — release tags must be GPG-signed

---

## Code of Conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/) Code of Conduct. Be respectful, constructive, and professional in all interactions.
