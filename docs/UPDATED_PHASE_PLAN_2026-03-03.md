# Updated Phase Plan (2026-03-03)

## Objective
Define the post-Phase-18 execution plan from current production baseline to next maturity targets, using current canonical docs and reconciled legacy requirements.

## Current Validated Baseline
- Core platform phases through Phase 18 are complete (mission runtime, CI/security, tracing, reliability qualification, UI e2e, Qdrant/Neo4j/object-storage optional adapters).
- Latest quality gates: global service coverage `84.95%`, required core-module `100%` thresholds passing, production audit `12/12`, debug sweep passing.

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

## Phase 20 - Extended Data-Plane Live Qualification
Scope:
- Add live integration suite using compose `extended-data-plane` profile.
- Validate end-to-end `knowledge-graph` and `audit-artifacts` paths against live Neo4j/MinIO.
- Add disruption tests (temporary adapter outage + recovery expectations).

Exit Criteria:
- Tests pass with live adapters and skip safely when stack is unavailable.
- Evidence artifact published with throughput/latency/error observations.

## Phase 21 - Mission Control Advanced Operator UX
Scope:
- Implement file-level repo mission diff-review/apply gate workflow.
- Add virtualization/lazy rendering for high-volume Semantic Bus and agent-log views.
- Preserve current e2e baseline and add new e2e coverage for these flows.

Exit Criteria:
- No regression on existing e2e suite.
- New UX paths have deterministic e2e tests.
- High-volume UI views stay responsive under synthetic load.

## Phase 22 - Strategic Deferred-Scope Decision Package
Scope:
- Convert deferred legacy items into explicit decision records (self-update, cloud multi-tenant, marketplace, distributed execution, language expansion).
- Define adopt/defer/deprecate rationale, trigger conditions, and security/governance prerequisites.

Exit Criteria:
- Canonical ADR-style decision set published.
- Roadmap and reconciliation docs reference one authoritative decision table.

## Phase 23 - LangGraph Orchestration Adoption (Optional but Planned)
Scope:
- Add feature-flagged LangGraph mission lifecycle path in orchestrator with fail-open fallback to legacy transitions.
- Support checkpointer mode selection (`none` and `memory` in baseline), thread-id conventions, and operational logging.
- Add unit tests for graph execution, fallback behavior, and checkpointer configuration.

Exit Criteria:
- `LANGGRAPH_ENABLED=true` can drive mission state transitions (`QUEUED -> RUNNING -> VERIFIED -> COMPLETE`) using LangGraph.
- `LANGGRAPH_FAIL_OPEN=true` safely falls back to legacy lifecycle on graph failure.
- Regression coverage remains above global threshold and required module thresholds.

## Validation Protocol (applies after each phase)
1. `python -m ruff check services tests scripts`
2. `python -m pytest --cov=services --cov-report=term-missing --cov-report=xml --cov-fail-under=80`
3. `python scripts/check_coverage_thresholds.py --coverage-file coverage.xml --global-threshold 80 ...`
4. `python scripts/production_review_audit.py`
5. `powershell -ExecutionPolicy Bypass -File scripts/debug_sweep.ps1`
6. Update docs/evidence + phase log + changelog, then commit/push.

## Recommended Execution Order
1. Phase 19
2. Phase 20
3. Phase 21
4. Phase 22
5. Phase 23
