# Testing & Quality Gates

Document version: 2026.03.29  
Last updated: 2026-03-29  
Status: Canonical  
Audience: Operators, developers, maintainers, and auditors

## Table of Contents

- [Test Pyramid](#test-pyramid)
- [Running Tests](#running-tests)
- [Coverage Policy](#coverage-policy)
- [Core Module Gates (100%)](#core-module-gates-100)
- [Frontend Testing](#frontend-testing)
- [Security & SAST](#security--sast)
- [Production Audit (13 checks)](#production-audit-13-checks)
- [Release Promotion Gate](#release-promotion-gate)
- [Reliability Qualification](#reliability-qualification)
- [CI Pipeline Overview](#ci-pipeline-overview)

---

## Test Pyramid

```
        ┌─────────────────────┐
        │   E2E (Playwright)  │  7 journeys — mission lifecycle,
        │       7 tests       │  operations, vault, builder, intake, errors, a11y
        └─────────────────────┘
       ┌───────────────────────────┐
       │  Integration Tests        │  Live mission flow, Neo4j/MinIO
       │  (skip-safe when offline) │  disruption recovery
       └───────────────────────────┘
      ┌─────────────────────────────────┐
      │  Frontend Unit Tests (Vitest)   │  45 tests — API routes,
      │                                 │  API client, vault flows, helpers
      └─────────────────────────────────┘
     ┌───────────────────────────────────────┐
     │  Backend Unit & Service Tests (pytest) │  709 passing tests across all services,
     │                                        │  extraction engine, concept catalog,
     │                                        │  auth, bindings, DR scripts
     └───────────────────────────────────────┘
```

---

## Running Tests

### Backend Tests

```bash
# Full suite with coverage (recommended before any commit)
make test

# Fast (no coverage)
make test-fast

# Specific service
python -m pytest tests/services/test_api_gateway_unit.py -q

# Specific test file
python -m pytest tests/services/test_language_extractor.py -v

# Live integration (skips safely when stack is offline)
python -m pytest tests/services/test_live_mission_flow_integration.py -q

# Extended live tests (Neo4j/MinIO disruption recovery)
LIVE_ENABLE_DISRUPTION_TESTS=true make test-live-extended
```

### Frontend Tests

```bash
# Lint + unit tests
make test-ui

# E2E regression suite (requires running stack at localhost:8100 + localhost:3100)
make test-ui-e2e

# Focused AI evaluation gate
make eval-ai

# Direct commands
cd apps/mission-control
npm run lint
npm run test        # Vitest
npm run test:e2e    # Playwright
```

---

## Coverage Policy

### Global Gate

```
services/ total coverage ≥ 80%
```

Enforced by:
- `make test` — `pytest --cov-fail-under=80`
- `ci.yml` — `Test with Coverage` step

**Current:** 81.75%

### Core Module Gates (100%)

The following files are **individually gated at 100%** coverage:

| File | Rationale |
|------|-----------|
| `services/orchestrator/orchestrator/protocol.py` | Envelope validation — must be exhaustive |
| `services/orchestrator/orchestrator/runtime.py` | Mission state machine — zero untested transitions |
| `services/orchestrator/orchestrator/agent_personas.py` | 38-agent persona data integrity |
| `services/orchestrator/orchestrator/agent_integrations.py` | Protocol and LLM assignment logic |
| `services/orchestrator/orchestrator/agent_registry.py` | Runtime agent state management |
| `services/semantic-bus-mcp/semantic_bus/mcp_server.py` | 6-protocol routing and DLQ |
| `services/pod-worker/pod_worker/main.py` | Mission routing and agent binding enforcement |
| `services/audit-worker/audit_worker/main.py` | Verification stream processing |

These are checked by `scripts/check_coverage_thresholds.py`, which runs after pytest and fails CI if any file drops below 100%.

### Why 100% on Core Files

These files implement enterprise-critical runtime guarantees:

- Strict protocol and envelope validation
- Authenticated sender and API-key enforcement
- Bounded recipient routing controls
- Graceful error handling (no leaking of internal errors)
- Retry/timeout behavior for internal service calls
- Deterministic Redis lifecycle and readiness behavior

---

## Frontend Testing

### Vitest Unit Tests (45 tests)

Located in `apps/mission-control/` alongside components. Cover:
- API client request/response handling
- SSE client connection and event parsing
- `smelt-cycle.ts` — 7-phase lifecycle mapping
- Component render output for key views

### Playwright E2E (7 journeys)

Located in `apps/mission-control/e2e/`.

| Journey | What is Tested |
|---------|---------------|
| Mission lifecycle | Create → poll → state transitions → completion |
| Operations views | Agent roster (38 agents), summary stats |
| Settings / Vault | Key storage, retrieval, vault API |
| Builder preview | Diff rendering, file selection |
| Repository intake | GitHub metadata import, file tree selection |
| Error states | Auth failure (401/403), service unavailable (503), not found |
| Accessibility regression | Mission flow pages pass keyboard and landmark checks |

### AI Eval Regression

The release baseline includes a focused AI regression gate for delegation and prompt-safety behavior:

```bash
make eval-ai
# Windows fallback when make is unavailable
python -m pytest -q tests/eval/test_llm_delegation_golden.py
```

**Run in CI:** Playwright browsers installed via `playwright install --with-deps chromium` in `.github/workflows/ci.yml`.

---

## Security & SAST

Run via `security.yml` CI workflow (triggers on push to `main`/`develop` + all PRs).

| Tool | Scope | Failure Condition |
|------|-------|------------------|
| **pip-audit** | Python dependency SCA | Any known CVE |
| **Bandit** | Python SAST | High/critical severity findings |
| **Trivy** | Container filesystem scan | Critical vulnerabilities |
| **gitleaks** | Secret scanning | Any credential pattern found |

```bash
# Run manually
pip install pip-audit bandit
pip-audit
bandit -r services scripts -ll

# Container scan (requires Docker)
trivy fs .

# Secret scan
gitleaks detect --source .
```

SBOM: Generated by `anchore/sbom-action` in CI → `sbom.spdx.json`.

---

## Production Audit (13 checks)

```bash
make audit
# or
python scripts/production_review_audit.py
```

All 13 checks must pass. If any `CRITICAL` check fails, CI returns exit code 1.

| Check ID | Priority | What is Verified |
|----------|----------|-----------------|
| `TST-001` | HIGH | Coverage gate ≥ 80% in CI and pyproject.toml |
| `SEC-001` | CRITICAL | Security workflow: pip-audit, bandit, trivy, gitleaks |
| `SEC-005` | HIGH | All service Dockerfiles set non-root USER |
| `INF-007` | CRITICAL | `.env.example` has all required DB and key variables |
| `COM-003` | CRITICAL | `protocol/topics.yaml` and core schemas exist |
| `DOC-005` | HIGH | Operations runbook, DR playbook, observability stack, gap analysis present |
| `API-002` | HIGH | Mission Control TypeScript strict mode + App Router tsx files |
| `UI-011` | HIGH | Mission Control `test:e2e` script + CI step + Playwright install |
| `STY-001` | MEDIUM | Design token artifacts (`tokens.json`, `tokens.css`) present |
| `REL-001` | CRITICAL | Release attestation + promotion gate controls configured |
| `OBS-009` | HIGH | Jaeger wiring + pager alert routing in Alertmanager |
| `OBS-010` | HIGH | Optional data-plane observability (alerts, runbook, Grafana dashboard) |
| `PERF-010` | HIGH | Reliability qualification scripts + evidence present |

---

## Release Promotion Gate

```bash
make promotion-gate
```

Runs `scripts/promotion_gate.py` against `deploy/promotion-policy.json`.

Writes: `reports/promotion-decision.local.json`

**Gate criteria:**
- Coverage ≥ threshold
- All production audit checks pass
- No critical security findings
- Release attestation signed

If the decision is `BLOCKED`, investigate the reasons in the output JSON before releasing.

---

## Reliability Qualification

```bash
make reliability
```

Runs sustained-load qualification. Required before major releases.

**What it tests:**
1. Sustained request load over configurable duration
2. Readiness endpoint monitoring throughout
3. Controlled orchestrator restart injection
4. Recovery time measurement
5. Final state validation

**Pass criteria:**
- Success rate ≥ 95%
- p95 latency ≤ threshold
- Recovery within 60 seconds

**Evidence:** `docs/evidence/reliability_qualification_baseline_*.json`

---

## CI Pipeline Overview

`.github/workflows/ci.yml` runs on every push and PR:

| Stage | Steps |
|-------|-------|
| **Lint** | `ruff check services scripts tests` |
| **Backend Tests** | `pytest --cov --cov-fail-under=80` + `check_coverage_thresholds.py` |
| **Production Audit** | `python scripts/production_review_audit.py` |
| **Docker Build** | Build all service images |
| **Mission Control Lint** | `npm run lint` in `apps/mission-control` |
| **Mission Control Unit Tests** | `npm run test` (Vitest) |
| **Playwright Install** | `playwright install --with-deps chromium` |
| **Mission Control E2E** | `npm run test:e2e` (Playwright, 6 journeys) |
| **SBOM** | `anchore/sbom-action` → `sbom.spdx.json` |

`security.yml` runs independently on main/develop push + all PRs:

| Stage | Steps |
|-------|-------|
| **Python SCA + SAST** | `pip-audit` + `bandit -r services scripts -ll` |
| **Container Scan** | `trivy-action` filesystem scan |
| **Secret Scan** | `gitleaks/gitleaks-action@v2` |
