# Build Roadmap

Last updated: 2026-03-03

## Phase 1: Foundation

- Monorepo scaffold and local Docker stack.
- Service health endpoints.
- Core contract validation scripts.
- Status: Complete.

## Phase 2: Core Execution

- Mission intake over API gateway.
- Orchestrator persistence and transitions.
- Protocol envelope publication/consumption.
- Mission event timeline endpoint and UI polling.
- Status: Complete.

## Phase 3: Pod Expansion

- Pod A/B/C/D service registration.
- Specialist routing and audit handoffs.
- Knowledge/LogicNode integration pathways.
- Status: Complete (initial implementation baseline).

## Phase 4: Hardening

- CI/CD enforcement baseline.
- Security/load/regression suites.
- Disaster recovery and operational readiness scaffolding.
- Status: Complete (baseline).

## Phase 5: Production Foundation

- `readyz` and `metrics` runtime contracts.
- Mission idempotency and retry-safe semantics.
- Worker stream reliability hardening under transient failure.
- Status: Complete (baseline, 2026-03-01).

## Phase 6: Production Maturity

- CI/CD supply-chain hardening trajectory.
- Observability and incident-ops scaffolding.
- Deployment/DR/performance automation baseline.
- Status: In progress (baseline scaffold complete, 2026-03-01).

## Phase 7: Agent Persona and Governance Alignment

- Full 8-part persona profiles for all 35 agents in operations APIs.
- Mission Control agent-detail rendering for persona profile data.
- Standards/evidence extension:
  - NIST CSF 2.0
  - NIST AI RMF 1.0
  - NIST SP 800-218 (SSDF)
  - NIST SP 800-53 Rev.5/5.2 update reference
  - NIST SP 800-61 Rev.3
  - OWASP Top 10 (2021)
  - OWASP ASVS v5
  - ISO/IEC 27001:2022
  - ISO/IEC 42001:2023
- Status: Complete (2026-03-02).

## Phase 8: Release Trust and Promotion Controls

- Signed release-manifest attestation generation and verification in CI.
- Fail-closed promotion policy enforcement for `main` and semantic version tags.
- Promotion decision artifacts generated for auditability.
- Status: Complete (baseline, 2026-03-03).

## Phase 9: Observability and Incident Routing

- OpenTelemetry tracing baseline wired for gateway/orchestrator mission-path APIs.
- Alertmanager pager webhook routing for high/critical alerts via `PAGER_WEBHOOK_URL`.
- Audit controls include release-trust and observability checks (`REL-001`, `OBS-009`).
- Status: Complete (baseline, 2026-03-03).

## Phase 10: Long-Duration Reliability Qualification

- Sustained-load qualification automation with readiness monitoring and recovery probe.
- Optional injected orchestrator restart scenario in qualification flow.
- Baseline evidence captured in `docs/evidence/reliability_qualification_baseline_2026-03-03.json`.
- Audit control expanded with reliability evidence verification (`PERF-010`).
- Status: Complete (baseline, 2026-03-03).

## Phase 11: Mission Control Integration and E2E Regression

- Playwright e2e suite for mission lifecycle, operations views, settings/vault flows, and error states.
- CI runs Mission Control e2e tests with Chromium browser provisioning.
- Audit control expanded with Mission Control e2e gate verification (`UI-011`).
- Status: Complete (baseline, 2026-03-03).

## Phase 12: Builder and Repository Intake Productionization

- Builder workspace upgraded from placeholder rendering to actionable file-impact and diff preview output.
- Repository intake upgraded from simulated file lists to real GitHub metadata/tree import flow.
- New hardening controls include repository URL/branch/subdirectory validation, file-size filtering, max-file clamping, vault/env GitHub token support, and structured error responses.
- Added regression coverage:
  - Vitest unit tests for repo import parsing/filtering helpers.
  - Playwright flows for builder diff preview and repo-import mission launch.
- Status: Complete (baseline, 2026-03-03).

## Phase 13: Operational Script Regression Hardening

- Added dry-run execution support for:
  - `scripts/backup_postgres.ps1`
  - `scripts/dr_drill.ps1`
- Added backup artifact integrity guardrails (missing/truncated backup failure).
- Added script regression tests:
  - `tests/scripts/test_backup_dr_scripts.py`
  - validates backup and DR drills in dry-run mode without live runtime dependency requirements.
- Status: Complete (baseline, 2026-03-03).

## Phase 14: Legacy Roadmap and Port Reconciliation

- Published canonical reconciliation note:
  - `docs/LEGACY_ROADMAP_RECONCILIATION_2026-03-03.md`
- Resolved Mission Control runtime-port ambiguity in canonical planning:
  - Docker-host default `3100`
  - direct Next.js dev `3000`
- Legacy advanced roadmap scope is now explicitly tagged as:
  - adopted (core phases),
  - deferred (advanced cloud/marketplace/expansion/R&D items),
  - deprecated (legacy financial projections as execution commitments).
- Status: Complete (baseline, 2026-03-03).

## Phase 15: Live Dependency Mission-Flow Integration Tests

- Added live integration suite:
  - `tests/services/test_live_mission_flow_integration.py`
- Coverage includes:
  - gateway/orchestrator readiness validation against running runtime,
  - health verification for Redis/Postgres dependency status,
  - real mission intake (`POST /v1/missions`) with polling of mission state and event timeline.
- Tests auto-skip when live stack is unavailable, enabling safe execution in non-runtime environments.
- Status: Complete (baseline, 2026-03-03).

## Phase 16: Data-System Activation and Reconciliation

- Activated Qdrant in orchestrator knowledge retrieval flow:
  - `POST /internal/knowledge` writes to PostgreSQL and mirrors to Qdrant (best effort).
  - `GET /internal/missions/{mission_id}/knowledge` prefers Qdrant and falls back to PostgreSQL.
- Expanded runtime visibility:
  - Qdrant readiness surfaced in `/health`, `/readyz`, and operations runtime snapshots.
- Added Qdrant security hardening:
  - optional `QDRANT_API_KEY` support for outbound Qdrant API calls.
- Added regression coverage:
  - `tests/services/test_qdrant_store_unit.py`
  - updated `tests/services/test_orchestrator_endpoints_extra.py`
  - updated `tests/services/test_production_foundations.py`
- Reconciled scope decisions:
  - Neo4j/object storage remain formally deferred optional expansions for current baseline.
- Status: Complete (baseline, 2026-03-03).

## Next Roadmap Targets

1. Optional expansion track: introduce Neo4j adapter behind feature flag when relationship-heavy retrieval becomes a runtime requirement.
2. Optional expansion track: introduce object-storage adapter with retention/legal-hold controls when immutable large-artifact demand exceeds current evidence storage model.
