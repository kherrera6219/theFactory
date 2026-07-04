# Testing & Quality Gates

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Canonical  
Audience: Operators, developers, maintainers, and auditors

## Table of Contents

- [Test Pyramid](#test-pyramid)
- [Running Tests](#running-tests)
- [Coverage Policy](#coverage-policy)
- [Core Module Gates (100%)](#core-module-gates-100)
- [Frontend Testing](#frontend-testing)
- [Security & SAST](#security--sast)
- [Production Audit (22 checks)](#production-audit-22-checks)
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
      │  Frontend Unit Tests (Vitest)   │  63 tests — API routes,
      │                                 │  API client, vault flows, helpers
      └─────────────────────────────────┘
     ┌───────────────────────────────────────┐
     │  Backend Unit & Service Tests (pytest) │  Full multi-service suite covering
     │                                        │  orchestration, routing, auth,
     │                                        │  data plane, DR scripts, and helpers
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

**Latest local sweep (2026-07-03):** `1348 passed, 5 skipped` (`pytest tests/services/ --ignore=tests/services/test_agent_base_unit.py`)

### Core Module Gates

The following files are individually gated by `scripts/check_coverage_thresholds.py` after pytest:

| File | Rationale |
|------|-----------|
| `services/orchestrator/orchestrator/protocol.py` | Envelope validation — must be exhaustive |
| `services/orchestrator/orchestrator/runtime.py` | Mission state machine — maintain a high-confidence baseline on the large runtime surface |
| `services/orchestrator/orchestrator/agent_personas.py` | 41-agent persona data integrity |
| `services/orchestrator/orchestrator/agent_integrations.py` | Protocol and LLM assignment logic |
| `services/orchestrator/orchestrator/agent_registry.py` | Runtime agent state management |
| `services/protocol-bus-mcp/protocol_bus/mcp_server.py` | 6-protocol routing and DLQ |
| `services/pod-worker/pod_worker/main.py` | Mission routing and agent binding enforcement |
| `services/audit-worker/audit_worker/main.py` | Verification stream processing |

| File | Coverage floor |
|------|----------------|
| `services/orchestrator/orchestrator/protocol.py` | `100%` |
| `services/orchestrator/orchestrator/agent_personas.py` | `100%` |
| `services/orchestrator/orchestrator/agent_integrations.py` | `100%` |
| `services/orchestrator/orchestrator/agent_registry.py` | `100%` |
| `services/protocol-bus-mcp/protocol_bus/mcp_server.py` | `100%` |
| `services/audit-worker/audit_worker/main.py` | `90%` |
| `services/pod-worker/pod_worker/main.py` | `80%` |
| `services/orchestrator/orchestrator/runtime.py` | `80%` (measured: 100% line / 99% branch) |

These floors preserve exhaustive coverage for narrow protocol/configuration modules and enforce maintained baselines for the larger runtime/worker entry points, which are covered primarily through broader service tests.

### Why Mixed Floors on Core Files

These files implement enterprise-critical runtime guarantees:

- Strict protocol and envelope validation
- Authenticated sender and API-key enforcement
- Bounded recipient routing controls
- Graceful error handling (no leaking of internal errors)
- Retry/timeout behavior for internal service calls
- Deterministic Redis lifecycle and readiness behavior

The smaller modules remain at `100%` because they are deterministic configuration and contract surfaces. The larger runtime/worker entry points keep explicit floors that reflect the current, reproducible CI baseline while still preventing silent regression. The `runtime.py` floor was raised from `60%` to `80%` after dedicated branch-coverage tests brought measured coverage to 100% line / 99% branch; the floor stays below measured to absorb minor branch noise without flaking CI.

### Recent Test Additions

**Orchestrator runtime branch coverage.** 12 new branch-coverage tests were added to `tests/services/test_runtime_*.py` covering:
- Intake DLQ paths (poison message → DLQ + `xack`)
- NOGROUP self-heal vs. re-raise on non-NOGROUP `ResponseError`
- `ConnectionError` → retry with `sleep(1.0)`
- Idempotent existing-mission skip
- Chain-prep failure paths
- Running-checkpoint insert failure

**Protocol bus MCP server.** `tests/services/test_semantic_bus_dedup.py` and `tests/services/test_semantic_bus_mcp.py` were updated and expanded to 40 tests at 100% coverage on `mcp_server.py`, covering: replay 409, dedup → 503, backpressure → 503, and multi-channel rejection.

**Agent persona/registry drift guard.** `tests/services/test_agent_personas_registry.py` was added with 8 tests enforcing no future drift between the agent registry and persona definitions.

---

## Frontend Testing

### Vitest Unit Tests (63 tests)

Located in `apps/mission-control/` alongside components. Cover:
- API client request/response handling
- SSE client connection and event parsing
- `smelt-cycle.ts` — 7-phase lifecycle mapping
- Component render output for key views

The suite grew from 45 to 63 tests; the 5 most recent additions cover gateway status propagation and unreachable-backend `503` handling.

### Playwright E2E (23 tests across 7 journey groups)

Located in `apps/mission-control/e2e/`.

| Journey | What is Tested |
|---------|---------------|
| Mission lifecycle | Create → poll → state transitions → completion |
| Operations views | Agent roster (41 agents), summary stats |
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

SBOM: Generated by `anchore/sbom-action` in CI → `sbom.spdx.json` and
`sbom.cdx.json`.

---

## Production Audit (23 checks)

```bash
make audit
# or
python scripts/production_review_audit.py
```

Current baseline: **22/23 passing** with `INF-008` open. If any `CRITICAL` check fails, CI returns exit code 1.

The table below lists a representative subset of the gated checks; run the audit for the full enumeration.

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
For local failure-injection evidence on Windows, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/reliability_qualification.ps1 `
  -InjectOrchestratorRestart `
  -OutputFile docs/evidence/reliability_qualification_baseline_YYYY-MM-DD.json
```

**What it tests:**
1. Sustained request load over configurable duration
2. Gateway and orchestrator readiness endpoint monitoring throughout
3. Controlled orchestrator restart injection
4. Recovery time measurement
5. Final state validation and capped failure diagnostics

**Pass criteria:**
- Success rate ≥ 95%
- p95 latency ≤ threshold
- Readiness failures and consecutive readiness failures stay within thresholds
- Recovery within 60 seconds
- Transient mission-create failures during injected orchestrator restart remain within
  threshold; API gateway retries `orchestrator unavailable` create attempts with
  `MISSION_CREATE_UPSTREAM_MAX_ATTEMPTS` / `MISSION_CREATE_UPSTREAM_RETRY_DELAY_SECONDS`

**Evidence:** `docs/evidence/reliability_qualification_baseline_*.json`

Evidence reports must identify the target `base_url`, configured
`readiness_endpoints`, `readiness_failure_counts_by_endpoint`, and capped
`mission_error_samples` / `readiness_failure_samples` when failures occur.
Verify the current evidence shape before accepting it:

```bash
python scripts/verify_reliability_evidence.py --evidence-file docs/evidence/reliability_qualification_baseline_YYYY-MM-DD.json
```

---

## CI Pipeline Overview

`.github/workflows/ci.yml` runs on every push and PR:

Production-signal rule: on `main` pushes and release tags, production-critical
jobs should run and pass rather than appear as skipped. Dependency failures are
reported as explicit release-trust failures so the check surface sends a clear
signal to operators, reviewers, and future partners.

| Stage | Steps |
|-------|-------|
| **Lint** | `ruff check services scripts tests` |
| **Backend Tests** | `pytest --cov --cov-fail-under=80` + `check_coverage_thresholds.py` |
| **Production Audit** | `python scripts/production_review_audit.py` |
| **Docker Build** | Build all service images; runs independently on production pushes/tags |
| **Mission Control Lint** | `npm run lint` in `apps/mission-control` |
| **Mission Control Unit Tests** | `npm run test` (Vitest) |
| **Playwright Install** | `playwright install --with-deps chromium` |
| **Mission Control E2E** | `npm run test:e2e` (Playwright, 23 tests across 7 journey groups) |
| **Electron E2E Smoke** | Runs on `main` pushes, release tags, and manual dispatch |
| **SBOM** | `anchore/sbom-action` → `sbom.spdx.json` + `sbom.cdx.json`; runs independently on production pushes/tags |
| **Release Trust** | Runs on `main` pushes and release tags; fails explicitly if lint/test, Docker build, or SBOM gates fail |

`security.yml` runs independently on main/develop push + all PRs:

| Stage | Steps |
|-------|-------|
| **Python SCA + SAST** | `pip-audit` + `bandit -r services scripts -ll` |
| **Container Scan** | `trivy-action` filesystem scan |
| **Secret Scan** | `gitleaks/gitleaks-action@v2` |
