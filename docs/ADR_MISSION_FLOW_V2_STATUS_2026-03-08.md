# ADR: Mission Flow v2 Runtime Status (2026-03-08)

Supersession note (2026-03-13): this ADR records the earlier v1.1-default decision posture. The current shipped defaults in `.env.example`, compose, and orchestrator settings now enable `MISSION_FLOW_V2_ENABLED=true`. Use [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) for the current runtime-default summary.

## Status
Accepted

## Context
`HGR_Mission_Flow_v2.docx` describes an expanded 11-phase, microstate-heavy mission pipeline.  
Current production runtime uses canonical v1.1 mission states (`QUEUED -> RUNNING -> VERIFIED -> COMPLETE`) with deterministic Smelt-cycle checkpoint events and strict PM/CEO/pod chain metadata.

Recent implementation closed critical runtime gaps:
- PM intake normalization and chain metadata enforcement.
- CEO delegation + pod/specialist assignment telemetry in LangGraph path.
- Completion integrity guardrails requiring execution artifacts.
- Chain trace API and Mission Control rendering.

## Decision
Production runtime remains **v1.1 canonical**.  
Mission Flow v2 is treated as a **roadmap/aspirational design reference**, not active runtime truth.

## Why
1. v2 introduces non-trivial new lifecycle semantics (11 phases, per-agent microstates, additional hard quality gates) that require schema, storage, API, UI, and migration changes.
2. Current runtime now meets production control requirements without introducing a destabilizing lifecycle migration.
3. Canonical v1.1 alignment keeps operational behavior deterministic and testable while preserving compatibility with existing Mission Control and audit tooling.

## Consequences
- API/UI/runtime docs must reference v1.1 as the only authoritative operational mission model.
- v2 features are tracked as explicit future phases with measurable exit criteria.
- New controls must continue to enforce:
  - PM -> CEO -> pod/specialist chain traceability
  - artifact-gated mission completion
  - internal service-auth diagnostics and qualification evidence

## Adoption Gate for Full v2 Runtime
Before enabling a v2 state machine in production:
1. Define canonical mission-state schema migration and compatibility policy.
2. Implement v2 graph nodes/events behind a feature flag with fail-open/fail-closed controls.
3. Add dedicated integration/e2e qualification for shared and dedicated topologies.
4. Update Mission Control timeline rendering and operations diagnostics for v2 microstates.
