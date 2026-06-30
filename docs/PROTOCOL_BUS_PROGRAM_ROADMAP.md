# Protocol Bus Program Roadmap

Document version: 2026.06.30
Last updated: 2026-06-30
Status: Active roadmap
Audience: Maintainers, operators, and AI coding agents

This roadmap is the umbrella that ties together the staged effort to evolve
theFactory's Protocol Bus from a telemetry sidecar into a genuine
agent-coordination backbone. Use it with `CURRENT_TODO.md` and
`HANDOFF_CURRENT.md`. Each stage below has (or will have) its own detailed plan.

---

## Why a staged program

Today the runtime is a single synchronous orchestrator state machine. The
function `advance_mission_lifecycle_v2` (`mission_flow_v2/lifecycle.py`) walks a
`for` loop over `V2_TRANSITIONS` and calls each agent stage as a direct
in-process function. Agent IDs (`AGENT-02-CEO`, `AGENT-13-PODA-AUDIT`, …) are
labels stamped on chain-trace events and bus envelopes, **not** addresses of
running processes. The Protocol Bus (`protocol-bus-mcp`, six Pydantic-validated
lanes) exists and is hardened, but only one lane is a closed produce→consume
loop today (Sigma, via `main.py: protocol_bus_consumer_loop`).

Getting from there to "the agents actually coordinate over the bus, and routing
is semantic" is too large and too risky for one initiative. It is broken into
four stages, each independently shippable, each leaving the system working:

| Stage | Initiative | What it delivers | Makes the bus… | Status |
|---|---|---|---|---|
| 1 | **PBLA** — `PROTOCOL_BUS_LANE_ACTIVATION_PLAN.md` | Real producers on all six lanes (Delta/Omega/Beta/Rho added to existing Alpha/Sigma) | …**observable** (telemetry on every lane) | Not started |
| 2 | **EDCP** — `EDCP_PHASE_PLAN.md` | Consumers + control-flow inversion, one seam at a time, behind one flag | …**load-bearing** (command backbone) | EDCP-01 complete; EDCP-02 pending |
| 3 | **Agent Runtime Split** — `AGENT_RUNTIME_SPLIT_PLAN.md` | Agents become independent runtime processes consuming/replying under their own identity | …**distributed** (real actor model) | Stub / not scheduled |
| 4 | **Semantic Bus** — `SEMANTIC_BUS_PLAN.md` | Dispatch by embedding similarity instead of lexical channel strings | …**semantic** (intent-routed) | Stub / not scheduled |

---

## The dependency chain (read top-down)

1. **PBLA must precede EDCP's load-bearing cutovers.** EDCP inverts each handoff
   from a direct call to a consumed bus event. Doing that against lanes that
   already carry real producer traffic is far lower risk — the consumer can be
   validated against live messages before the in-loop call is removed. PBLA is
   essentially the "dual-write" half of EDCP done ahead of time, for all six
   lanes at once. (EDCP-01, already complete, shipped the *producer helpers* and
   consumer-group durability; PBLA adds the *callers*; EDCP-02→05 add the
   *consumers* and flip control flow.)
2. **EDCP must precede the Agent Runtime Split.** There is no value in splitting
   agents into separate processes until the seams between them are already
   event-driven. EDCP deliberately keeps a single orchestrator process that both
   publishes and consumes; Stage 3 only makes sense once those seams exist.
3. **Stages 2–3 must precede the Semantic Bus.** Semantic routing replaces the
   routing layer; that layer must first be owned by the bus (EDCP) and exercised
   by independent consumers (Stage 3) before similarity-based dispatch is
   meaningful or safe. It also depends on the knowledge-lake embedding path
   (S1-01 / Qdrant) being production-real.

```
PBLA (producers)  ──▶  EDCP (consumers + control inversion)  ──▶  Agent Runtime Split  ──▶  Semantic Bus
   observable               load-bearing                            distributed              semantic
```

---

## Cross-stage couplings to watch

- **Omega carries two message shapes.** PBLA-02 puts a PM→user *delivery
  handoff* on Omega; EDCP-02 puts a PM→CEO `mission_charter_ready` *charter* on
  Omega (recipient `AGENT-03-BROKER`). They differ by mission phase and
  correlation_id but share the lane — keep their `message_type`/payload shapes
  distinct so neither plan's Omega changes constrain the other's.
- **Consumer identity.** The orchestrator consumes as `AGENT-03-BROKER` today.
  Stage 3 reopens the question of whether each agent should consume under its own
  identity; EDCP's "Open decisions" section already flags this.
- **The single flag.** `EVENT_DRIVEN_CONTROL_PLANE_ENABLED`
  (`settings.event_driven_control_plane_enabled`, default `false`) gates EDCP's
  load-bearing behavior. PBLA is flag-independent (pure additive telemetry).
  Stage 3+ will likely need their own gating flags rather than overloading this
  one.

---

## What is in scope for each stage (one-line scope guard)

- **PBLA:** producers only. No consumers, no control-flow change, no agent split,
  no routing change.
- **EDCP:** consumers + seam-by-seam control inversion inside one orchestrator
  process. No agent-process split.
- **Agent Runtime Split:** process/identity topology only. No routing-semantics
  change.
- **Semantic Bus:** routing layer only, built on the prior three.

Keeping these guards crisp is what keeps each stage revertible and low-risk.
