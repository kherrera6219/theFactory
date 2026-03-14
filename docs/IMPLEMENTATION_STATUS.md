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
- The shipped default runtime now routes through the v2 lifecycle implementation, even though some older ADRs still describe v1.1 as the default.

### Audit flow

- The audit worker consumes `missions.state`, not a separate `missions.audit` stream.
- Audit results are persisted through the orchestrator audit-report path into `mission_audit_reports`.
- The worker publishes verification/build-related events, but the current implementation is not yet a full artifact-packaging pipeline.

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
- The Builder diff preview is still inferred from preview-plan signals and synthetic diff generation, not a true repository patch/apply workflow.
- Repo review approval is still UI-local state rather than a persisted server-side approval record.
- The chat intake page still hardcodes `requested_target_language` to `python`.
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

1. Decide whether mission creation should remain queue-first/eventually consistent or move to read-after-write consistency. Immediate `GET /v1/missions/{id}` can still briefly return `404` while the intake event is being consumed, although Mission Control now retries that path.
2. Replace the synthetic Builder preview path with a true repository-context diff/apply pipeline. Repo intake/review/launch is now substantially real, but Builder still is not.
3. Persist repo review approval server-side if that approval is meant to be an auditable contract rather than UI-only state.
4. Align audit/event documentation with the actual `missions.state` and `mission_audit_reports` implementation, or deepen the code to match the older design.
5. Update Mission Control data-plane surfaces to reflect live optional-adapter readiness.
6. Reconcile language-count and extraction/routing claims across docs with the current 20-key routing matrix.
7. Either implement a real build/package artifact path or remove stronger-than-implemented "binary ready" semantics.
8. Remove remaining hardcoded language assumptions from non-repo Mission Control intake paths, especially chat launch.
