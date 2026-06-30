# Agent Runtime Split Plan (Stage 3 — STUB)

Document version: 2026.06.30
Last updated: 2026-06-30
Status: Stub — not scheduled
Audience: Maintainers and AI coding agents

> **This is a stub.** It captures the shape, prerequisites, and open questions of
> Stage 3 of the Protocol Bus program so the whole program is documented, but it
> is **not scheduled** and intentionally not specified to the line. Do not start
> implementation from this document — it needs a grounding pass against the live
> code first. See `PROTOCOL_BUS_PROGRAM_ROADMAP.md` for context.

---

## Purpose

Turn the 41 agents from in-process function calls into **independent runtime
processes** that consume work and reply under their own bus identity. After
EDCP makes the *seams* event-driven inside one orchestrator process, this stage
distributes the *participants* so the per-agent rows in
`docs/AGENT_PROTOCOL_BUS_DATA_SYSTEMS_PLAN.md` (Bus Role / Data Systems per
agent) describe real processes, not labels.

## Current state (grounded, 2026-06-30)

- "Agents" are synchronous functions: `generate_pod_audit_verdict`,
  `generate_pm_delivery_summary`, the CEO/PM/pod-manager stage preparers in
  `mission_flow_v2/`. Agent IDs are labels stamped on envelopes and chain-trace
  events.
- A real `agent-runtime` service already exists
  (`services/agent-runtime/agent_runtime/main.py`) and runs agent logic via
  `orchestrator.agent_base.make_agent`, but it triggers off the
  `missions.state` Redis stream through a consumer group — **not** off the
  protocol-bus lanes, and **not** under a per-agent identity.
- `pod-worker` and `audit-worker` are the other worker processes; they also
  trigger off `missions.state`.

## Hard prerequisites

1. **EDCP through at least EDCP-04** must be complete — the support ring and
   pod hops must already be event-driven seams before participants are split.
2. **`EVENT_DRIVEN_CONTROL_PLANE_ENABLED=true` proven on a live mission** — do
   not distribute processes onto a control plane that has not run load-bearing
   end to end.
3. **Per-agent HMAC signing decision.** `protocol-bus-mcp` already supports
   opt-in per-agent HMAC (`AGENT_HMAC_SIGNING_ENABLED`, `AGENT_HMAC_SECRET_*`).
   Splitting agents into processes is the natural point to turn this on, so each
   process authenticates as itself. Decide secret distribution before starting.

## Candidate phases (high level — to be refined)

- **3a — Consumer identity per agent.** Replace the single
  `ORCHESTRATOR_BUS_AGENT_ID="AGENT-03-BROKER"` consumer identity with per-agent
  identities for the agents being split, so each consumes `protocol:{lane}:{its
  own id}` rather than sharing the broker's channels.
- **3b — Pod-worker / audit-worker as bus participants.** Move pod-worker and
  audit-worker from `missions.state` triggering to Alpha/Delta lane consumption
  under their pod-manager / QC-audit identities (this overlaps EDCP-03b/04 —
  reconcile the boundary).
- **3c — Promote `agent-runtime` to a first-class participant host.** Use the
  existing `agent-runtime` service to host the support-ring agents (Security,
  Compliance, Tester, Accountant, Broker) as bus consumers/repliers instead of
  in-orchestrator gate functions.
- **3d — Distribute the executive/PM tier.** CEO and PM consume/reply under
  their own identities; the orchestrator retains only projection/observability
  duties.

## Open questions

- How many of the 41 agents genuinely need their own process vs. a shared host
  process keyed by identity? (Cost vs. isolation.)
- Does splitting introduce ordering/idempotency requirements the current
  fire-and-forget + dedup model does not cover?
- How does the Mission Control operations snapshot (`/v1/operations/agents`,
  heartbeat/state telemetry) change when agents are real processes?
- Reconcile overlap with EDCP-03/04 so the two plans do not both claim the
  pod-worker / support-ring conversion.

## Out of scope

- Routing-semantics changes (that is Stage 4, the Semantic Bus).
- Any control-flow inversion not already delivered by EDCP.
