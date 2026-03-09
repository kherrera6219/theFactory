# Smelt-Cycle Runtime Mapping (2026-03-04)

## Objective
Provide a deterministic mapping from backend lifecycle telemetry to the Mission Control 7-phase Smelt-cycle UX.

## Canonical Phase Model
1. `INTAKE`
2. `FETCH`
3. `SMELT`
4. `GATING`
5. `FUSION`
6. `SQUEEZE`
7. `DELIVERY`

## Runtime Event-to-Phase Mapping
- `MISSION_QUEUED` -> `FETCH`
- `MISSION_RUNNING` -> `SMELT`
- `MISSION_GATING` -> `GATING`
- `MISSION_FUSION` -> `FUSION`
- `MISSION_VERIFIED` -> `SQUEEZE`
- `MISSION_COMPLETE` -> `DELIVERY`
- `MISSION_FAILED` -> `DELIVERY`

## Reconciliation Policy
- Legacy coarse state transitions (`QUEUED -> RUNNING -> VERIFIED -> COMPLETE`) remain authoritative for mission state.
- Two deterministic checkpoint events are emitted while mission state remains `RUNNING`:
  - `MISSION_GATING`
  - `MISSION_FUSION`
- Mission Control computes phase progress from the highest observed mapped event in the mission timeline.
- Backward compatibility: for older missions without checkpoint events, Mission Control applies fallback inference from mission state plus LogicNode counts.

## Implementation References
- Lifecycle checkpoint emission:
  - `services/orchestrator/orchestrator/runtime.py`
  - `services/orchestrator/orchestrator/langgraph_lifecycle.py`
- Mission Control mapping helper:
  - `apps/mission-control/app/lib/smelt-cycle.ts`
- Mission detail timeline rendering:
  - `apps/mission-control/app/(shell)/missions/[id]/page.tsx`
