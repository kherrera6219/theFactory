# ADR - 35-Agent Runtime Topology (2026-03-04)

> Historical note (2026-03-29): This document predates the current 38-agent runtime. Treat any `35-agent` references below as historical planning terminology unless explicitly updated in a newer canonical document.

## Status
Accepted

## Context
- The platform has a canonical 35-agent registry with full persona/telemetry coverage.
- Runtime execution today is condensed into shared pod workers (A/B/C/D) plus orchestrator routing.
- Design docs historically referenced dedicated per-agent containers; this creates a topology mismatch versus the live baseline.

## Decision
Adopt a **hybrid topology strategy**:
- Baseline runtime remains the current condensed worker model for default/local/single-tenant deployment.
- Dedicated per-agent containers are deferred as an **on-demand expansion mode**, triggered by explicit scale, isolation, or compliance thresholds.

## Rationale
- Current condensed topology is validated in production gates and supports operational simplicity.
- Immediate full 35-container expansion increases orchestration, resource, and incident surface area without demonstrated baseline necessity.
- A trigger-based migration path preserves future scale/isolation readiness without destabilizing the current runtime.

## Trigger Criteria for Dedicated-Agent Expansion
Any one of:
1. Sustained per-agent queue-depth saturation (`>= 20`) for 15 minutes in production telemetry.
2. p95 mission lifecycle latency exceeds SLO by 25% for three consecutive release windows.
3. Regulated tenancy requires hard process/container isolation per agent or pod role.
4. Repeated incident class shows noisy-neighbor contention in shared workers.

## Migration Path
1. Add compose profile for dedicated agent workers (`--profile dedicated-agents`) and per-agent stream routing keys.
2. Introduce scheduler policy to bind selected agents to dedicated workers while others remain condensed.
3. Roll out by pod domain (A -> B -> C -> D), with rollback to condensed routing.
4. Promote to default only after stability and cost/SLO validation.

## Consequences
- Near-term: no runtime disruption; documentation and governance align with actual deployed topology.
- Medium-term: clear, measurable activation path for full isolation when justified.


