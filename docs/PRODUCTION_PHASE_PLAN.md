# Production Phase Plan (2026-02-28)

This plan reconciles `C:\software\Holygrail` source documentation with current `theFactory` implementation status and external production standards.

## Inputs Reviewed

- HolyGrail source docs:
  - Roadmap and architecture (`04`, `05`, `07`)
  - CI/CD, observability, security (`24`, `25`, `26`)
  - Production deployment, backup/DR, incident response (`32`, `34`, `36`, `40`)
  - Testing and API references (`41`-`46`, `49`, `50`, `52`)
- External standards (official sources):
  - OWASP API Security Top 10 (2023)
  - NIST SP 800-218 (SSDF)
  - NIST SP 800-61r3 (Incident Response)
  - OpenTelemetry + Prometheus instrumentation guidance
  - Kubernetes readiness/liveness/startup probe guidance
  - Kubernetes Pod Security Standards
  - SLSA supply-chain framework
  - OpenAPI 3.1 specification

## Gap Snapshot

Current repo baseline is solid for local orchestration; this phased plan closes the next production-control layer incrementally.

## Next Phases

## Phase 1 - Runtime Hardening Foundation (In Progress)

Status (2026-03-01): Baseline complete.

Objective: establish safe production runtime behavior at service edge and control plane.

Deliverables:
- Gateway and orchestrator readiness endpoints (`/readyz`).
- Prometheus metrics endpoints (`/metrics`) and HTTP instrumentation middleware.
- Mission intake idempotency (`Idempotency-Key`) with Redis-backed dedupe.
- Pod-worker reliability fix: avoid acknowledging transiently failed stream events.
- Focused regression tests for readiness, idempotency, and worker ack behavior.

Exit criteria:
- All core services expose health + readiness + metrics contracts.
- Duplicate mission retries with the same idempotency key are deterministic.
- Transient worker failures do not drop stream entries.
- Test suite passes with new production-foundation scenarios.

## Phase 2 - CI/CD and Supply Chain Enforcement

Status (2026-03-01): Baseline complete.

Objective: enforce build/release integrity controls aligned to SSDF + SLSA goals.

Deliverables:
- Coverage gates, matrix test jobs, artifact retention, and branch protections.
- Security gates: SAST, dependency scan, image scan, secrets scan, license check.
- SBOM generation + signed build artifacts/attestations.
- Staged release workflow with smoke validation and rollback hooks.

Exit criteria:
- Pipeline blocks on critical vulnerabilities and failing quality gates.
- Reproducible, attestable artifacts for deployable services.

## Phase 3 - Observability and Incident Operations

Status (2026-03-01): Baseline scaffold complete.

Objective: operational visibility and actionable incident response.

Deliverables:
- Prometheus/Grafana/Loki/trace pipeline bootstrap and dashboards.
- Service-level SLOs, alert rules, and paging thresholds.
- Runbook automation for high-severity incidents.

Exit criteria:
- P0/P1 alert routes validated in non-prod.
- Golden signals (latency, traffic, errors, saturation) visible per service.

## Phase 4 - API Security and Access Control Maturity

Status (2026-03-01): Baseline controls complete.

Objective: close API and auth gaps to production standard.

Deliverables:
- Token-based auth strategy and role scoping hardening.
- Rate limiting, abuse controls, and tighter boundary validation.
- OpenAPI contract publication and contract-test enforcement.

Exit criteria:
- OWASP API Top-10 controls demonstrably covered by tests and checks.
- External API behavior versioned and contract-tested.

## Phase 5 - Deployment, Backup, and DR Verification

Status (2026-03-01): Baseline runbooks/scripts complete.

Objective: resilient production rollout and recoverability.

Deliverables:
- Deployment scripts for preflight checks and controlled rollout strategy.
- Backup automation with retention policy and encrypted storage paths.
- Restore drills and RTO/RPO measurement scripts.

Exit criteria:
- Repeatable deploy + rollback drill in staging.
- Recovery drill meets defined RTO/RPO targets.

## Phase 6 - Performance and Scale Qualification

Status (2026-03-01): Baseline smoke validation complete.

Objective: verify throughput/latency under realistic workload.

Deliverables:
- Load/perf benchmarks with pass/fail thresholds.
- Capacity planning model and scaling playbooks.
- Bottleneck remediation backlog with measured impact.

Exit criteria:
- Benchmarks meet baseline mission throughput and p95 latency targets.
- Capacity thresholds and runbooks are documented.
