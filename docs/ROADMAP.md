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

## Next Roadmap Targets

1. Establish Mission Control integration/e2e regression coverage for core operator journeys.
2. Activate Qdrant in active retrieval paths and define SLOs.
