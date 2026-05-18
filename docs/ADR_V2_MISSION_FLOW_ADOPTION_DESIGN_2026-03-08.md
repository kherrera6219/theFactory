# ADR: v2 Mission-Flow Adoption Design Package (2026-03-08)

Supersession note (2026-03-13): this design package captured the earlier "v1.1 default, v2 gated" migration plan. The current shipped defaults now enable `MISSION_FLOW_V2_ENABLED=true`. Use [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) for the current runtime-default summary.

Date: 2026-03-08  
Document version: 2026.03.08  
Last updated: 2026-03-13  
Status: Accepted (Design baseline, feature-flag gated)  
Owner: mission-runtime architecture

## Goal

Define a controlled migration path from canonical v1.1 mission lifecycle behavior to future v2 state-machine behavior without breaking current APIs, telemetry, or Mission Control UX.

## Migration Strategy

1. Keep v1.1 as default runtime behavior.
2. Gate v2 execution path behind explicit feature flag (`MISSION_FLOW_V2_ENABLED`).
3. Preserve existing API contracts during mixed-mode operation.
4. Require qualification evidence before expanding v2 traffic.

## Compatibility Matrix

| Surface | v1.1 Behavior | v2 Behavior (Target) | Compatibility Policy |
| --- | --- | --- | --- |
| Mission state API (`/missions/{id}`) | Existing terminal and in-flight states | Additional internal microstates possible | API returns stable canonical states; microstates remain metadata/events only |
| Mission events (`/events`, chain trace) | PM/CEO/pod/specialist + smelt checkpoints | Additional v2 orchestration checkpoints | New event types are additive; existing event types remain unchanged |
| Mission Control stepper | 7-phase mapped from state/events | 7-phase mapped with richer sub-phase telemetry | Stepper contract remains 7-phase; v2 sub-phases map into existing phase model |
| Completion integrity gate | Block `COMPLETE` without assignment/logicnode artifacts | Same gate required | Gate remains mandatory in both engines |

## Enablement Gates

v2 can be enabled only when:

1. Unit and integration coverage for v2 path passes quality gates.
2. Live canary evidence shows non-zero assignment/logicnode artifacts and no unexpected `MISSION_COMPLETION_BLOCKED`.
3. Mission Control timeline behavior remains deterministic across mixed v1.1/v2 missions.

## Rollback Plan

1. Disable `MISSION_FLOW_V2_ENABLED`.
2. Restart orchestrator to force v1.1-only lifecycle handling.
3. Re-run mission artifact qualification and dedicated canary checks.
4. Keep previously persisted mission evidence; do not mutate historical event records.

## Testing Requirements

1. Contract tests for event compatibility and mission-state payload stability.
2. Mixed-mode live integration tests validating both engines can coexist.
3. Regression checks for Mission Control event timeline and smelt-cycle mapping.

## Consequences

- v2 adoption is now explicit, test-gated, and reversible.
- Documentation and runtime claims remain unambiguous.
- Operator-facing APIs remain stable during incremental adoption.
