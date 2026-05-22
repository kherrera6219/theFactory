# BLUEPRINT_SPEC.md
## Unified Logic Refinery - Implementation Blueprint
Version: 1.1.0  
Last Updated: 2026-02-28

## 1. System Objective

Build a local-first software refinery that accepts mission intents, routes them through
specialist pods, validates lifecycle progress, and exposes operational visibility via
API and UI surfaces.

## 2. Runtime Topology

- API Gateway (`services/api-gateway`): external contract boundary and mission intake.
- Orchestrator (`services/orchestrator`): mission lifecycle state machine, persistence,
  internal data APIs.
- Pod workers (`services/pod-worker`): routing/assignment and logic/knowledge writes.
- Audit worker (`services/audit-worker`): audit report creation and release signal events.
- Dashboard (`services/dashboard`): lightweight operational shell.
- Mission Control (`apps/mission-control`): user-facing mission submission and timeline UI.
- Data plane: Redis (streams), Postgres (mission state store), Qdrant (reserved endpoint).

## 3. Canonical Contracts

- Event envelope: `schemas/event.envelope.schema.json`
- Logic node: `schemas/logicnode.schema.json`
- Refined IR function/module: `schemas/rir.fn.schema.json`, `schemas/rir.module.schema.json`
- Topic catalog: `protocol/topics.yaml`

All emitted envelope messages must contain:
- `event_id`, `topic`, `timestamp`, `producer`, `correlation_id`, `payload_ref`, `schema`, `priority`

## 4. Mission Lifecycle

1. Gateway accepts `POST /v1/missions`.
2. Mission intake payload + envelope is appended to `missions.intake`.
3. Orchestrator consumer validates envelope/payload, persists mission in Postgres.
4. Mission transitions:
   - `INTAKE -> QUEUED -> RUNNING -> VERIFIED -> COMPLETE`
5. State events are emitted to `missions.state`.
6. Pod worker consumes `MISSION_RUNNING`, writes:
   - pod assignment
   - logic node
   - knowledge record
7. Audit worker consumes verification/failure events, writes audit report and release signals.

## 5. Authorization Model

- Auth is API key role-based (`x-api-key`).
- Mutating public endpoint:
  - `POST /v1/missions/{mission_id}/state` requires mutate/admin role.
- Internal orchestrator endpoints require internal/admin/worker role.
- Direct orchestrator mission creation (`POST /missions`) is internal-only.
- Default local keys are documented in `.env.example`.

## 6. Operational Guarantees (Current Baseline)

- Envelope schema/topic validation at gateway, orchestrator, and workers.
- Postgres-backed mission timeline and artifact records.
- Conflict-safe pod assignment: once assigned to a pod, mission assignment is not
  overwritten by another pod.
- Debug/code sweep automation in `scripts/debug_sweep.ps1`.
- Security CI checks present in `.github/workflows/security.yml`.

## 7. Known Next Targets

- Replace timer-based lifecycle simulation with real pod completion signals.
- Add push-based mission updates (websocket/SSE) to Mission Control.
- Expand Qdrant-backed knowledge retrieval from reserved to active data path.
