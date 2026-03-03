# Production Phase Plan

Last updated: 2026-03-03

This plan reconciles `C:\software\Holygrail` source design documents with current `theFactory` implementation status and external production standards.

## Inputs Reviewed

- HolyGrail source docs:
  - architecture, roadmap, protocols, and data design
  - CI/CD, observability, security, deployment, DR, testing references
- External standards:
  - OWASP API Top 10 and ASVS
  - NIST CSF 2.0, NIST AI RMF 1.0
  - NIST SP 800-218 (SSDF), SP 800-61 Rev.3
  - ISO/IEC 27001:2022, ISO/IEC 42001:2023
  - OpenTelemetry, Prometheus, OpenAPI, SLSA

## Gap Snapshot

Baseline runtime is stable for local orchestration and operations. The current phases focus on production-grade governance, reliability, and verification depth.

## Phases

## Phase 1 - Runtime Hardening Foundation

Status: Complete (baseline, 2026-03-01)

Deliverables:

- Gateway/orchestrator readiness endpoints (`/readyz`).
- Metrics endpoints (`/metrics`) and request instrumentation.
- Mission idempotency (`Idempotency-Key`) with Redis dedupe.
- Worker reliability fix for transient stream processing failures.
- Focused regression tests.

## Phase 2 - CI/CD and Supply Chain Enforcement

Status: Baseline complete (2026-03-01)

Deliverables:

- Coverage gates, test matrix, artifact retention.
- Security checks (SAST/dependency/image/secret/license scans).
- SBOM generation and release hardening baseline.

## Phase 3 - Observability and Incident Operations

Status: Baseline scaffold complete (2026-03-01)

Deliverables:

- Monitoring stack bootstrap and dashboards.
- Alert rules and incident runbook automation.

## Phase 4 - API Security and Access Control Maturity

Status: Baseline controls complete (2026-03-01)

Deliverables:

- Role-scoped key enforcement and boundary validation.
- Rate limiting and request hardening.
- OpenAPI publication and API contract consistency.

## Phase 5 - Deployment, Backup, and DR Verification

Status: Baseline scripts/runbooks complete (2026-03-01)

Deliverables:

- Preflight/deployment checks.
- Backup and restore automation.
- DR drill scripts and restore validation path.

## Phase 6 - Performance and Scale Qualification

Status: Baseline smoke validation complete (2026-03-01)

Deliverables:

- Performance smoke test automation.
- Capacity planning and bottleneck backlog scaffolding.

## Phase 7 - Agent Persona Governance and Evidence

Status: Complete (2026-03-02)

Deliverables:

- Full 8-part persona profiles in runtime operations APIs for all 35 agents.
- Persona profile rendering in Mission Control Agent detail views.
- Standards extension fields:
  - `standards_alignment`
  - `evidence_sources`
- Source-linked standards evidence with verification metadata.
- Test coverage for persona schema integrity and evidence linkage.

## Next Phases

## Phase 8 - Release Trust and Promotion Controls

Status: Baseline complete (2026-03-03)

Objective: enforce signed artifact attestations and promotion gates.

Exit criteria:

- Release artifacts have verifiable signatures.
- Promotion gates fail closed on policy violations.

## Phase 9 - Full Observability Integration

Status: Baseline complete (2026-03-03)

Objective: tracing + incident routing maturity.

Exit criteria:

- Distributed traces across core mission paths.
- Alert routing into operational incident channels.

## Phase 10 - Long-Duration Reliability Qualification

Status: Baseline complete (2026-03-03)

Objective: sustained workload certification.

Exit criteria:

- Long-duration load and recovery tests pass target thresholds.
- Capacity and resilience envelopes are documented and reproducible.

## Phase 11 - Mission Control Integration and E2E Regression

Status: Baseline complete (2026-03-03)

Objective: automate critical operator-journey UI regression coverage.

Exit criteria:

- Mission lifecycle, operations views, settings/vault, and error states are exercised in e2e runs.
- CI executes Mission Control e2e tests in addition to lint and unit gates.
