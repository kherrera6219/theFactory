# Implementation Status

Last updated: 2026-03-14

This document is the canonical current-state snapshot for theFactory. Use it as the source of truth for shipped defaults, active runtime behavior, and known gaps. Date-stamped ADRs, roadmap phases, audits, and completion checklists remain useful historical records, but some of them no longer describe the current default runtime exactly.

## Shipped Defaults

- `MISSION_FLOW_V2_ENABLED=true` by default in `.env.example`, `deploy/docker-compose.yaml`, and `services/orchestrator/orchestrator/settings.py`.
- `LANGGRAPH_ENABLED=false` by default. The LangGraph lifecycle remains optional and is not the shipped default path.
- `services/orchestrator/orchestrator/runtime.py` executes mission flow in this order:
  1. v2 lifecycle when `MISSION_FLOW_V2_ENABLED=true`
  2. LangGraph lifecycle when v2 is disabled and `LANGGRAPH_ENABLED=true`
  3. legacy lifecycle fallback

## Runtime Topology

- The orchestrator maintains a 38-agent registry with persona and integration metadata.
- The default deployment is still the condensed topology:
  - API Gateway
  - Orchestrator
  - shared pod-worker instances
  - audit-worker
  - Mission Control
- The fully isolated per-agent runtime exists, but only through optional dedicated profiles in `deploy/docker-compose.yaml` and `deploy/docker-compose.full-dedicated-agents.yaml`.
- In the condensed topology, some interface, executive, and support-agent heartbeats are synthesized by the orchestrator rather than emitted by separate long-running worker processes.

## Current Control-Plane Behavior

### Mission lifecycle

- Canonical external mission states remain `QUEUED -> RUNNING -> VERIFIED -> COMPLETE | FAILED`.
- Smelt-cycle checkpoint events are still the operator-facing phase model.
- The shipped default runtime routes through the v2 lifecycle implementation.
- `POST /v1/missions` now persists through the orchestrator before returning `201 Created`, so the mission record is queryable immediately after create.
- Dynamic scaling is now wired end-to-end behind `AGENT_SCALING_ENABLED`: the orchestrator computes partition work, emits `mission.partition.ready`, pod-workers execute partitions, results are merged into mission metadata, and lifecycle resumes once all partitions complete.

### Audit flow

- The audit worker consumes `missions.state`, not a separate `missions.audit` stream.
- Audit results are persisted through the orchestrator audit-report path into `mission_audit_reports`.
- `MISSION_COMPLETE` now maps to `mission.state.complete`; the runtime no longer claims a bundle artifact exists just because lifecycle reached `COMPLETE`.
- A real build/package artifact pipeline is still not implemented.

### Data plane

- PostgreSQL is deployed as a single application database by default (`POSTGRES_DB=ulr`).
- Primary tables are created by `services/orchestrator/orchestrator/migrations/V001_initial_runtime_schema.sql`.
- Redis Streams remain the event backbone:
  - `missions.intake`
  - `missions.state`
  - `missions.pod.A|B|C|D`
  - `agents.heartbeats`
- Qdrant is active in the core compose stack.
- Neo4j and object storage remain optional feature-flagged adapters.

## Mission Control Status

- Mission Control is a real Next.js operator console with missions, operations, semantic-bus, builder, and repo-intake views.
- The repository import path is real GitHub metadata/tree ingestion.
- Repository review is now server-backed: Mission Control fetches selected GitHub file content, builds a review artifact with a stable fingerprint, infers `requested_target_language`, and launches repo missions with a real `source_code` bundle.
- Builder review is now server-backed against the local workspace: it selects real files, emits a stable `builder_fingerprint`, produces a grounded patch contract plus `source_code` bundle, and can launch missions from that approved artifact.
- Review approval is now persisted server-side for both Builder and repository review flows via local approval receipt records before mission launch.
- The chat intake page now infers `requested_target_language` from attached files and prompt hints instead of hardcoding `python`.
- The databases page and some UX copy still lag live backend readiness details.

## Language Extraction Status

- Specialist routing currently covers 20 language keys across four pods. TypeScript is accepted as a routed key but aliases to the JavaScript specialist.
- Go, Haskell, and OCaml are now fully supported with dedicated agents and compose routing.
- Some documentation artifacts still carry older language-count claims and need reconciliation to the current routing matrix.

## Validation Snapshot

As of 2026-03-14:

- `python -m pytest -q` is green.
- `apps/mission-control` TypeScript check is green (`npm run lint`).
- `apps/mission-control` unit tests are green (`npm test`).
- `apps/mission-control` Playwright is green (`npm run test:e2e`).

The repository should therefore be treated as a substantial and internally consistent baseline, but not yet a fully complete product release.

## Open Gaps For Completion

1. Align audit/event documentation with the actual `missions.state`, `mission.state.complete`, and `mission_audit_reports` implementation.
2. Update the remaining Mission Control data-plane surfaces and copy to reflect live optional-adapter readiness.
3. Reconcile language-count and extraction/routing claims across docs with the current 20-key routing matrix.
4. Implement a real build/package artifact path before introducing bundle-ready semantics again.
