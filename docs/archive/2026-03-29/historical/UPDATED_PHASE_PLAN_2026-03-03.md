# Updated Phase Plan (2026-03-03)

> Historical note (2026-03-29): This document predates the current 38-agent runtime. Treat any `35-agent` references below as historical planning terminology unless explicitly updated in a newer canonical document.

## Objective
Define the post-Phase-18 execution plan from current production baseline to next maturity targets, using current canonical docs and reconciled legacy requirements.

## Execution Update (2026-03-08)
- Production audit now passes `14/14` controls (includes `GRC-012` compliance evidence mapping).
- Mission runtime now enforces:
  - PM intake metadata normalization,
  - CEO -> pod/specialist chain trace persistence and API/UI visibility,
  - completion guardrail blocking `COMPLETE` when artifacts are absent.
- LangGraph delegation path now includes real provider-aware CEO delegation calls (with deterministic fallback).
- Infrastructure hardening additions are active:
  - OTel tracing hooks in pod-worker/audit-worker/semantic-bus/dashboard,
  - Redis TLS wiring in compose + redis config,
  - container read-only/tmpfs/ulimit hardening for stateless services.
- New live artifact qualification harness added:
  - `scripts/mission_artifact_qualification.py`
  - `scripts/mission_artifact_qualification.ps1`
  - unit coverage in `tests/scripts/test_mission_artifact_qualification.py`
- Roadmap follow-up qualification automation added:
  - operator-route auth matrix runner (`scripts/operator_route_auth_matrix_qualification.py`)
  - multi-language dedicated canary trend runner (`scripts/dedicated_agent_canary_trend.py`)
  - v1.1 baseline + v2 prototype matrix runner (`scripts/langgraph_v2_prototype_matrix.py`)

## Next Phases (From Current Baseline)

## Phase 35 - Dedicated and Shared Live Artifact Qualification Evidence
Scope:
- Run `mission_artifact_qualification.py` against both shared default topology and `--profile dedicated-agents`.
- Capture pass/fail evidence in `docs/evidence/` with mission IDs, chain trace, assignment/logicnode counts.

Exit Criteria:
- Both profile runs produce `passed=true`.
- Evidence includes command lines, timestamps, and profile labels.

Status:
- Complete (executed 2026-03-08).
- Evidence: `docs/evidence/phase35_mission_artifact_runtime_integrity_validation_2026-03-08.md`,
  `docs/evidence/mission_artifact_qualification_shared_2026-03-08.json`,
  `docs/evidence/mission_artifact_qualification_dedicated_2026-03-08.json`.

## Phase 36 - v2 Mission-Flow Adoption Design Package
Scope:
- Define explicit migration from canonical v1.1 states to any future v2 state-machine model.
- Specify API/schema compatibility strategy for mission events and Mission Control timeline rendering.
- Publish go/no-go criteria for enabling v2 graph path behind feature flag.

Exit Criteria:
- ADR/design doc includes rollback plan, compatibility matrix, and testing requirements.
- No ambiguous "active runtime" claims remain in docs.

Status:
- Complete (executed 2026-03-08).
- Evidence:
  - `docs/ADR_V2_MISSION_FLOW_ADOPTION_DESIGN_2026-03-08.md`

## Current Validated Baseline
- Core platform phases through Phase 18 are complete (mission runtime, CI/security, tracing, reliability qualification, UI e2e, Qdrant/Neo4j/object-storage optional adapters).
- Latest quality gates: global service coverage `86.00%`, required core-module `100%` thresholds passing, production audit `13/13`, debug sweep passing.
- Execution update (2026-03-04): Phase 27 (Mission Control live SSE transport + polling fallback diagnostics) is complete and validated.
- Execution update (2026-03-04): Phase 28 (Smelt-cycle runtime reconciliation with deterministic 7-phase mapping) is complete and validated.
- Execution update (2026-03-04): Phase 29 (35-agent topology and security-model ADR decision package) is complete and validated.
- Execution update (2026-03-04): Phase 30 (auth-mode and dedicated-profile ADR execution baseline) is complete and validated.
- Execution update (2026-03-04): Phase 31 (dedicated-agent scheduler binding enforcement for `AGENT_BINDING`) is complete and validated.
- Execution update (2026-03-04): Phase 32 (Phase 19 objective: optional data-plane observability and SLO controls) is complete and validated.
- Execution update (2026-03-04): Phase 33 (Phase 20 objective: extended data-plane live qualification) is complete and validated.
- Execution update (2026-03-04): Phase 34 (Phase 21 objective: Mission Control advanced operator UX) is complete and validated.
- Execution update (2026-03-08): Phase 35 (artifact runtime integrity qualification) is complete and validated.
- Execution update (2026-03-08): Phase 36 (v2 mission-flow adoption design package) is complete and validated.
- Execution update (2026-03-08): Phase 37 (strategic deferred-scope ADR, operator OIDC policy extension, dedicated canary guardrails) is complete and validated.
- Execution update (2026-03-08): Phase 38 (qualification matrix automation and prototype continuation harnesses) is complete and validated.

## Remaining Work (Prioritized)

## Phase 19 - Optional Data-Plane Observability and SLO Controls
Scope:
- Add metrics for Neo4j and object-storage adapters (ready state, write latency, error rate, mirror-write success rate).
- Add alert rules and runbook links for adapter failure/degradation.
- Add dashboard panels for optional data-plane health and SLO trend lines.

Exit Criteria:
- Metrics exposed on `/metrics` and scraped by Prometheus.
- Alert rules trigger correctly in controlled fault tests.
- Runbook steps cover triage/recovery for both adapters.

Status:
- Complete (executed as Phase 32 on 2026-03-04).

## Phase 20 - Extended Data-Plane Live Qualification
Scope:
- Add live integration suite using compose `extended-data-plane` profile.
- Validate end-to-end `knowledge-graph` and `audit-artifacts` paths against live Neo4j/MinIO.
- Add disruption tests (temporary adapter outage + recovery expectations).

Exit Criteria:
- Tests pass with live adapters and skip safely when stack is unavailable.
- Evidence artifact published with throughput/latency/error observations.

Status:
- Complete (executed as Phase 33 on 2026-03-04).
- Evidence: `docs/evidence/phase33_extended_data_plane_live_qualification_validation_2026-03-04.md`.

## Phase 21 - Mission Control Advanced Operator UX
Scope:
- Implement file-level repo mission diff-review/apply gate workflow.
- Add virtualization/lazy rendering for high-volume Semantic Bus and agent-log views.
- Preserve current e2e baseline and add new e2e coverage for these flows.

Exit Criteria:
- No regression on existing e2e suite.
- New UX paths have deterministic e2e tests.
- High-volume UI views stay responsive under synthetic load.

Status:
- Complete (executed as Phase 34 on 2026-03-04).
- Evidence: `docs/evidence/phase34_mission_control_advanced_operator_ux_validation_2026-03-04.md`.

## Phase 22 - Strategic Deferred-Scope Decision Package
Scope:
- Convert deferred legacy items into explicit decision records (self-update, cloud multi-tenant, marketplace, distributed execution, language expansion).
- Define adopt/defer/deprecate rationale, trigger conditions, and security/governance prerequisites.

Exit Criteria:
- Canonical ADR-style decision set published.
- Roadmap and reconciliation docs reference one authoritative decision table.

Status:
- Complete (executed 2026-03-08).
- Evidence:
  - `docs/ADR_STRATEGIC_DEFERRED_SCOPE_DECISIONS_2026-03-08.md`

## Phase 23 - LangGraph Orchestration Adoption (Optional but Planned)
Scope:
- Add feature-flagged LangGraph mission lifecycle path in orchestrator with fail-open fallback to legacy transitions.
- Support checkpointer mode selection (`none` and `memory` in baseline), thread-id conventions, and operational logging.
- Add unit tests for graph execution, fallback behavior, and checkpointer configuration.

Exit Criteria:
- `LANGGRAPH_ENABLED=true` can drive mission state transitions (`QUEUED -> RUNNING -> VERIFIED -> COMPLETE`) using LangGraph.
- `LANGGRAPH_FAIL_OPEN=true` safely falls back to legacy lifecycle on graph failure.
- Regression coverage remains above global threshold and required module thresholds.

## Phase 24 - LangGraph Postgres Checkpointer Baseline
Scope:
- Add Async Postgres checkpointer mode (`LANGGRAPH_CHECKPOINTER=postgres`) with optional one-time setup gate.
- Add `checkpoint_ns` support through runtime config to isolate mission-lifecycle checkpoints.
- Validate fail-open behavior and regression coverage for postgres mode.

Exit Criteria:
- Postgres checkpointer path runs when enabled and dependency is available.
- Optional setup path is idempotent at app runtime level.
- Global coverage and required core-module thresholds continue passing.

## Phase 25 - Word-Doc Requirement Reconciliation
Scope:
- Audit all in-repo Word documents and map requirements to the canonical implementation baseline.
- Publish a reconciled TODO/backlog with explicit priority and measurable acceptance criteria.
- Add runtime visibility fields for LangGraph mode in operations/health surfaces for operator diagnostics.

Exit Criteria:
- Audit report and updated TODO are published in `docs/`.
- LangGraph runtime mode is visible in health/readiness/operations payloads.
- Regression tests and quality gates pass.

## Phase 26 - LangGraph Live Postgres Recovery Qualification
Scope:
- Add startup lifecycle rehydration for in-flight mission records after orchestrator restart.
- Add lifecycle recovery telemetry fields to health/readiness/operations runtime payloads.
- Add repeatable live qualification script with orchestrator restart injection while `LANGGRAPH_CHECKPOINTER=postgres` is enabled.

Exit Criteria:
- Mission lifecycle reaches `COMPLETE` through orchestrator restart/disruption with postgres checkpointer enabled.
- Recovery evidence includes pass/fail criteria and timings.
- Regression tests, coverage thresholds, and debug sweep continue to pass.

## Phase 27 - Mission Control Live Transport Baseline
Scope:
- Add API Gateway SSE state-stream endpoint with mission filtering, keepalive, and stream-resume support.
- Add EventSource-based live transport in Mission Control mission detail, Semantic Bus, and agent operations views.
- Keep polling fallback active with explicit operator diagnostics (transport mode, stream events, stream errors, fallback ticks).

Exit Criteria:
- Critical Mission Control views support live push transport without removing polling compatibility.
- Unit/service/frontend tests cover stream parsing, filtering, and fallback behavior.
- Full quality-gate and debug sweep validation pass.

## Phase 28 - Smelt-Cycle Runtime Reconciliation
Scope:
- Add deterministic runtime checkpoints for Smelt-cycle mid-phases while preserving canonical mission state machine.
- Reconcile Mission Control stepper/timeline rendering to mapped runtime events.
- Publish canonical mapping policy and add regression tests.

Exit Criteria:
- Mission timeline supports deterministic progression across all seven Smelt-cycle phases.
- Legacy and LangGraph lifecycle paths both emit checkpoint telemetry.
- Regression tests, coverage thresholds, and debug sweep continue to pass.

## Phase 29 - Topology and Security ADR Decision Package
Scope:
- Publish canonical decision record for 35-agent runtime topology (condensed baseline vs dedicated-agent expansion).
- Publish canonical decision record for security model (API-key baseline vs JWT/OIDC enterprise mode).
- Reconcile roadmap and TODO artifacts to close these Word-doc audit gaps.

Exit Criteria:
- ADR documents include rationale, explicit decision, trigger criteria, and implementation path.
- Canonical backlog/docs reflect completed decision-package status.
- Validation sweep confirms no regression in quality gates.

## Phase 30 - ADR Execution Baseline
Scope:
- Implement API Gateway `AUTH_MODE` abstraction (`api_key`, `hybrid`, `oidc`) with OIDC claim-role enforcement for mutation routes.
- Add compose dedicated-agent profile scaffolding for trigger-based topology expansion.
- Add regression tests and integration documentation updates.

Exit Criteria:
- Gateway mutation route supports auth mode switching with deterministic behavior and tests.
- Compose provides `--profile dedicated-agents` manager-worker baseline without affecting default runtime.
- Quality gates and debug sweep pass.

## Phase 31 - Dedicated-Agent Scheduler Binding Enforcement
Scope:
- Implement pod-worker scheduler binding policy for `AGENT_BINDING` services in dedicated topology profile.
- Resolve mission target agent from payload metadata plus orchestrator mission metadata fallback.
- Add binding skip telemetry and regression tests.

Exit Criteria:
- Dedicated worker runtime only processes missions with matching bound agent IDs.
- Binding mismatch/unresolved scenarios are observable via metrics and tests.
- Global and required-module coverage thresholds, production audit, and debug sweep continue to pass.

## Validation Protocol (applies after each phase)
1. `python -m ruff check services tests scripts`
2. `python -m pytest --cov=services --cov-report=term-missing --cov-report=xml --cov-fail-under=80`
3. `python scripts/check_coverage_thresholds.py --coverage-file coverage.xml --global-threshold 80 ...`
4. `python scripts/production_review_audit.py`
5. `powershell -ExecutionPolicy Bypass -File scripts/debug_sweep.ps1`
6. Update docs/evidence + phase log + changelog, then commit/push.

## Recommended Execution Order
1. Maintain recurring live qualification evidence refresh (shared + dedicated profiles).
2. Expand live OIDC route-policy integration tests in dedicated staging.
3. Continue optional v2 runtime prototyping behind feature flag without changing canonical v1.1 production default.


