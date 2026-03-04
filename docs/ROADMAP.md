# Build Roadmap

Last updated: 2026-03-04

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
  - Neo4j/object storage were tagged as optional expansion tracks beyond the core baseline.
- Status: Complete (baseline, 2026-03-03).

## Phase 17: Neo4j Optional Graph Adapter

- Added feature-flagged Neo4j adapter:
  - `services/orchestrator/orchestrator/neo4j_store.py`
- Enabled best-effort mirror writes for graph workloads:
  - knowledge upserts mirror into Neo4j when `NEO4J_ENABLED=true`
  - audit report upserts mirror into Neo4j when `NEO4J_ENABLED=true`
- Added graph retrieval APIs:
  - `GET /internal/missions/{mission_id}/knowledge-graph`
  - `GET /v1/missions/{mission_id}/knowledge-graph`
- Expanded runtime visibility:
  - Neo4j readiness surfaced in orchestrator health/readiness/operations runtime payloads.
- Added compose/env scaffolding:
  - Neo4j service profile and `NEO4J_*` environment controls in compose and `.env.example`.
- Added regression coverage:
  - `tests/services/test_neo4j_store_unit.py`
  - updated endpoint and gateway contract tests.
- Status: Complete (baseline, 2026-03-03).

## Phase 18: Object-Storage Retention and Legal-Hold Adapter

- Added feature-flagged object-storage adapter:
  - `services/orchestrator/orchestrator/object_store.py`
- Added immutable audit artifact mirroring path:
  - `POST /internal/audit-reports` now mirrors audit report JSON into object storage when enabled.
- Added retention/legal-hold controls:
  - retention-until metadata derived from `OBJECT_STORAGE_RETENTION_DAYS`
  - legal-hold policy activated for failed/rejected audit states when enabled
  - fallback write behavior for buckets without object-lock support
- Added artifact retrieval APIs:
  - `GET /internal/missions/{mission_id}/audit-artifacts`
  - `GET /v1/missions/{mission_id}/audit-artifacts`
- Added compose/env and dependency support:
  - object-storage `OBJECT_STORAGE_*` controls in `.env.example` and compose
  - `boto3` dependency in orchestrator requirements
- Added regression coverage:
  - `tests/services/test_object_store_unit.py`
  - updated endpoint/gateway regression tests
- Status: Complete (baseline, 2026-03-03).

## Phase 23: LangGraph Orchestration Adoption

- Added feature-flagged LangGraph lifecycle engine:
  - `services/orchestrator/orchestrator/langgraph_lifecycle.py`
- Runtime integration:
  - `services/orchestrator/orchestrator/runtime.py` now attempts LangGraph execution first and falls back to legacy lifecycle transitions when disabled/unavailable/failing (fail-open configurable).
- Added environment controls:
  - `LANGGRAPH_ENABLED`
  - `LANGGRAPH_FAIL_OPEN`
  - `LANGGRAPH_CHECKPOINTER`
  - `LANGGRAPH_THREAD_PREFIX`
- Added regression coverage:
  - `tests/services/test_langgraph_lifecycle_unit.py`
  - updated `tests/services/test_runtime_unit.py`
- Status: Complete (implementation baseline, 2026-03-03).

## Phase 24: LangGraph Postgres Checkpointer Baseline

- Added Async Postgres checkpointer support for LangGraph lifecycle:
  - `LANGGRAPH_CHECKPOINTER=postgres`
  - `LANGGRAPH_CHECKPOINTER_POSTGRES_URL` (optional override)
  - `LANGGRAPH_CHECKPOINTER_SETUP` (optional one-time setup)
  - `LANGGRAPH_CHECKPOINT_NAMESPACE`
- Runtime behavior:
  - Mission lifecycle graph now supports postgres-backed checkpoint persistence via `AsyncPostgresSaver`.
  - Checkpointer setup is guarded to run once per app runtime when enabled.
  - Existing fail-open fallback behavior to legacy lifecycle is preserved.
- Added regression coverage:
  - expanded `tests/services/test_langgraph_lifecycle_unit.py` for postgres dependency/usage/setup behavior.
- Status: Complete (baseline implementation + validation, 2026-03-03).

## Phase 25: Word-Doc Reconciliation and LangGraph Runtime Visibility

- Audited all in-repo Word docs and published reconciled findings:
  - `docs/WORD_DOC_AUDIT_2026-03-03.md`
  - `docs/UPDATED_TODO_FROM_WORD_AUDIT_2026-03-03.md`
- Added LangGraph runtime telemetry visibility in orchestrator runtime surfaces:
  - `/health`
  - `/readyz`
  - `/internal/operations/summary`
  - `/internal/operations/agents`
- Added regression assertions for the new runtime fields.
- Status: Complete (audit + runtime visibility baseline, 2026-03-03).

## Phase 26: LangGraph Postgres Live Recovery Qualification

- Added startup lifecycle rehydration for in-flight mission states (`QUEUED`, `RUNNING`, `VERIFIED`) after orchestrator restart.
- Added recovery telemetry fields to runtime payload surfaces:
  - `lifecycle_recovery_bootstrapped`
  - `lifecycle_recovery_recovered_count`
  - `lifecycle_recovery_scanned_count`
  - `lifecycle_recovery_last_at`
  - `lifecycle_recovery_last_error`
- Added live qualification automation:
  - `scripts/langgraph_postgres_recovery_qualification.py`
  - `scripts/langgraph_postgres_recovery_qualification.ps1`
  - `make langgraph-recovery`
- Validation evidence:
  - `docs/evidence/phase26_langgraph_postgres_live_recovery_qualification_2026-03-03.json`
- Status: Complete (live restart/disruption qualification passed, 2026-03-04).

## Phase 27: Mission Control Live Transport for Critical Views

- Added API Gateway SSE endpoint for live state-stream transport:
  - `GET /v1/stream/state`
  - supports mission filtering, optional agent-event inclusion, keepalive, and `Last-Event-ID` resume.
- Added Mission Control EventSource transport for:
  - mission detail view,
  - Semantic Bus view,
  - agent operations view.
- Added fallback design:
  - explicit polling fallback path remains active when stream is unavailable,
  - UI diagnostics now report transport mode, stream events seen, stream errors, and poll fallback ticks.
- Added regression coverage:
  - `tests/services/test_api_gateway_live_stream_unit.py`
  - updated `tests/services/test_production_foundations.py`
  - updated `apps/mission-control/app/lib/api-client.test.ts`
- Validation evidence:
  - `docs/evidence/phase27_mission_control_live_transport_validation_2026-03-04.md`
- Status: Complete (live transport baseline validated, 2026-03-04).

## Phase 28: Smelt-Cycle Runtime Reconciliation

- Added deterministic runtime checkpoint events to complete 7-phase telemetry:
  - `MISSION_GATING`
  - `MISSION_FUSION`
- Checkpoint events are emitted in both lifecycle engines:
  - legacy runtime transition loop
  - LangGraph lifecycle path
- Mission Control phase stepper now derives current phase from event history (with state + LogicNode fallback for older missions).
- Mission timeline now surfaces phase labels for mapped mission events.
- Canonical mapping policy published:
  - `docs/SMELT_CYCLE_RUNTIME_MAPPING_2026-03-04.md`
- Regression coverage:
  - `tests/services/test_runtime_unit.py`
  - `tests/services/test_langgraph_lifecycle_unit.py`
  - `apps/mission-control/app/lib/smelt-cycle.test.ts`
- Validation evidence:
  - `docs/evidence/phase28_smelt_cycle_runtime_reconciliation_validation_2026-03-04.md`
- Status: Complete (deterministic 7-phase runtime mapping validated, 2026-03-04).

## Phase 29: Topology and Security ADR Decision Package

- Published canonical runtime-topology ADR:
  - `docs/ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md`
  - Decision: retain condensed worker baseline, activate dedicated-per-agent topology only via trigger-based expansion path.
- Published canonical security-model ADR:
  - `docs/ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md`
  - Decision: dual-mode auth strategy (`api_key`, `hybrid`, `oidc`) with JWT/OIDC enterprise path while preserving internal service-key flows.
- Updated canonical backlog and phase plans to mark these two Word-doc reconciliation gaps as complete.
- Validation evidence:
  - `docs/evidence/phase29_topology_and_security_adr_validation_2026-03-04.md`
- Status: Complete (decision package published, 2026-03-04).

## Phase 30: ADR Execution Baseline (Auth Mode + Dedicated Profile)

- Implemented gateway auth-mode abstraction:
  - `AUTH_MODE=api_key|hybrid|oidc`
  - OIDC/JWT bearer validation path with claim-based role enforcement for mutation endpoints.
  - OIDC and bearer-hybrid mode now forward `INTERNAL_SERVICE_API_KEY` to orchestrator after gateway-side role validation.
- Added auth runtime controls:
  - `OIDC_ISSUER_URL`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL`, `OIDC_SHARED_SECRET`,
  - `OIDC_REQUIRED_ROLE`, claim mapping controls, algorithm controls, and token leeway.
- Added dedicated topology scaffolding in compose:
  - `--profile dedicated-agents`
  - per-pod dedicated manager worker services (`pod-a/b/c/d-dedicated-mgr-worker`) with `AGENT_BINDING`.
- Added regression coverage:
  - `tests/services/test_api_gateway_auth_mode_unit.py`
- Updated security/integration docs:
  - `docs/API_INTEGRATION_GUIDE.md`
  - `README.md`
- Validation evidence:
  - `docs/evidence/phase30_auth_mode_and_dedicated_profile_validation_2026-03-04.md`
- Status: Complete (execution baseline implemented and validated, 2026-03-04).

## Phase 31: Dedicated-Agent Scheduler Binding Enforcement

- Implemented dedicated-agent scheduler policy in pod-worker runtime:
  - `AGENT_BINDING` is now parsed and enforced during mission-running handling.
  - Dedicated workers process missions only when resolved mission agent matches configured binding.
  - Mission agent resolution supports payload fields, payload metadata, and orchestrator mission metadata fallback.
- Added dedicated-binding runtime telemetry and visibility:
  - `pod_worker_binding_skips_total{pod_name,reason}` metric.
  - pod-worker `/health` now includes `agent_binding`.
- Added regression coverage:
  - `tests/services/test_pod_worker_unit.py`
  - `tests/services/test_runtime_unit.py` (coverage-gate maintenance for required modules).
- Validation evidence:
  - `docs/evidence/phase31_dedicated_agent_binding_scheduler_validation_2026-03-04.md`
- Status: Complete (binding policy implemented and validated, 2026-03-04).

## Phase 32: Optional Data-Plane Observability and SLO Controls

- Added optional-adapter telemetry metrics in orchestrator runtime:
  - `orchestrator_optional_adapter_enabled{adapter}`
  - `orchestrator_optional_adapter_ready{adapter}`
  - `orchestrator_optional_adapter_operations_total{adapter,operation,status}`
  - `orchestrator_optional_adapter_operation_latency_seconds{adapter,operation}`
  - `orchestrator_optional_adapter_mirror_writes_total{adapter,artifact,status}`
  - `orchestrator_optional_adapter_mirror_write_latency_seconds{adapter,artifact}`
- Instrumented Neo4j and object-storage adapter operations and readiness paths.
- Instrumented mirror-write paths for:
  - Neo4j knowledge mirror writes,
  - Neo4j audit-report mirror writes,
  - object-storage audit artifact writes.
- Expanded monitoring controls:
  - New Prometheus alert group `thefactory-optional-data-plane` with readiness, error-rate, and p95-latency alerts.
  - New Grafana overview panels for optional adapter readiness, mirror-write error rate, and mirror-write p95 latency.
- Added runbook:
  - `docs/runbooks/optional_data_plane_incident_runbook.md`
- Validation evidence:
  - `docs/evidence/phase32_optional_data_plane_observability_validation_2026-03-04.md`
- Status: Complete (observability baseline implemented and validated, 2026-03-04).

## Phase 33: Extended Data-Plane Live Qualification

- Added live extended data-plane qualification suite:
  - `tests/services/test_live_extended_data_plane_integration.py`
- Qualification coverage:
  - end-to-end optional mirror-write roundtrip checks for Neo4j (`knowledge-graph`) and object-storage (`audit-artifacts`),
  - skip-safe behavior when live stack/adapters are unavailable,
  - disruption/recovery scenario with temporary Neo4j/MinIO outage and post-recovery verification.
- Added local execution target:
  - `make test-live-extended`
- Resolved runtime qualification blockers:
  - MinIO image tag corrected to valid release (`RELEASE.2025-09-07T16-13-09Z`),
  - MinIO healthcheck switched from unavailable `wget` to `curl`.
- Validation evidence:
  - `docs/evidence/phase33_extended_data_plane_live_qualification_validation_2026-03-04.md`
- Status: Complete (extended data-plane live qualification implemented and validated, 2026-03-04).

## Next Roadmap Targets

1. Implement advanced Mission Control operator UX gaps from imported design specs:
   - repo diff-review/apply gate for file-level mission outputs,
   - virtualization of Semantic Bus and agent-log high-volume views.
2. Publish explicit Phase 4+ strategic decision package for deferred legacy items (self-update, cloud multi-tenant, marketplace, distributed execution).
3. Extend OIDC auth mode beyond mutation endpoint to broader operator/public route policies and runbook playbooks.
4. Run dedicated-agent canary rollout with mission metadata contract instrumentation and rollback guardrails.
