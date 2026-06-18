# theFactory — Event-Driven Control Plane (EDCP) Phase Plan

Document version: 2026.06.18-a
Last updated: 2026-06-18
Status: In progress — EDCP-01 complete, EDCP-02 pending
Audience: Maintainers

**Created:** 2026-06-14
**Authoritative status doc:** `docs/IMPLEMENTATION_STATUS.md` (the archived
`docs/archive/2026-06-13/SPRINT_BACKLOG.md` is historical only)

---

## Purpose

Today a mission runs as a single synchronous in-process pipeline. The function
`advance_mission_lifecycle_v2` (`mission_flow_v2/lifecycle.py`) walks a `for`
loop over `V2_TRANSITIONS` and calls each agent stage as a direct function
through a `stage_preparers` dict. PM → CEO → pod manager → specialist is a call
stack, not a conversation over the bus.

The Protocol Bus exists (six typed lanes, MCP `/send`, Pydantic envelopes) but
is **telemetry, not command**: `protocol_bus_producer.py` ships only
`send_alpha_directive`, every send is fire-and-forget, and the orchestrator
consumer (`main.py: protocol_bus_consumer_loop`) handles exactly one lane
(`{"sigma": _handle_sigma_knowledge_ready}`).

This plan inverts that — one handoff seam at a time — so the bus becomes the
command backbone and `missions.state` becomes a read-only projection, matching
the target architecture from the 2026-06-14 communication review.

---

## Hard prerequisites

1. **S1-01 must pass before load-bearing handoff inversion.** A live BUILD_NEW
   mission must reach `COMPLETE` with non-empty `generated_code` before EDCP-02
   or later phases make bus events the sole trigger for mission progression.
   Do not invert control flow on a pipeline that has not yet been proven to
   produce real output end to end.
2. **Bus durability gap is fixed by EDCP-01.** `ProtocolBusConsumer` now has an
   opt-in Redis consumer-group mode (`XGROUP CREATE` / `XREADGROUP` / `XACK`)
   behind `EVENT_DRIVEN_CONTROL_PLANE_ENABLED=false` by default. The legacy
   `XREAD` path remains the default until a later EDCP phase flips control-flow
   behavior.

---

## Guiding principles

- **Strangler pattern.** The working direct-call loop stays intact. Each phase
  moves a single seam onto the bus and is independently revertable.
- **One flag.** `EVENT_DRIVEN_CONTROL_PLANE_ENABLED`
  (`settings.event_driven_control_plane_enabled`, default `false`). Every phase ships with the flag off
  changing nothing at runtime — consistent with the existing flag discipline
  (`AGENT_SCALING_ENABLED`, `MISSION_*_ENFORCEMENT_ENABLED`, all `=false`/gated
  by default).
- **Dual-write before cutover.** A phase first *also* publishes the event
  (flag-independent, additive), then — only under the flag — removes the
  in-loop direct call so the consumed event becomes the sole trigger.
- **Blast radius grows outward.** Phases 1–2 are entirely inside the
  orchestrator process; the pod-worker and audit-worker are not touched until
  Phase 3.

---

## Current-state evidence (grounded in code, 2026-06-14)

| Concern | File / function | Current behavior |
|---|---|---|
| Mission driver | `mission_flow_v2/lifecycle.py` → `advance_mission_lifecycle_v2` | One `for` loop over `V2_TRANSITIONS`; agents are entries in `stage_preparers` called directly and sequentially |
| PM intake | `mission_flow_v2/phases_intake.py` → `_prepare_pm_intake` (~L250) | Produces `feature_contract` + `mission_charter` into mission metadata; gates only when `ambiguity_score >= 0.7`; **never publishes to the bus**; returns `True` so the loop falls straight into CEO |
| CEO trigger | `phases_intake.py` → `_prepare_ceo_delegation` (mapped from `MissionState.fetch`) | Direct function call reached by the loop, not an event consumer |
| CEO → pod manager | `phases_build.py` → `_prepare_pod_assignment` (~L50) + `_send_alpha_delegation_directive` (~L175) | Real assignment is a direct call; an Alpha directive is emitted **fire-and-forget** alongside it ("a bus outage must never block mission flow") — shadow telemetry |
| Support ring gates | `lifecycle.py` → `_advance_verified_to_complete` | `_prepare_security_compliance_report`, `_prepare_dependency_absorption_reports`, `_prepare_runtime_qc`, deploy readiness — all direct calls; stamp agent IDs but are not event-tasked workers |
| Producer | `protocol_bus_producer.py` | Only `send_protocol_message` + `send_alpha_directive`; no Beta/Delta/Sigma/Omega/Rho helpers |
| Consumer | `protocol_bus_consumer.py` → `ProtocolBusConsumer._consume_lane` | `XREAD` from `$`, no consumer groups, no ack/redelivery; per-lane via the `handlers` dict keys |
| Orchestrator consumer wiring | `main.py` → `protocol_bus_consumer_loop` (~L491), `ORCHESTRATOR_BUS_AGENT_ID="AGENT-03-BROKER"` (~L450) | `handlers = {"sigma": _handle_sigma_knowledge_ready}`; guarded by `PROTOCOL_BUS_CONSUMER_ENABLED` |
| State stream as work channel | `phases_intake.py` → `_emit_partition_work_items` | `xadd`s partition work items onto `settings.state_stream` (`missions.state`); pod-worker triggers off `MISSION_POD_MANAGER_ASSIGNED` / `MISSION_RUNNING` / `MISSION_PARTITION_READY` |

---

## Lane decision: the PM → CEO handoff

Of the six lanes, none is a clean semantic fit for an internal PM→CEO planning
handoff (Alpha is CEO-down, Omega is human-facing). Adding a 7th protocol is
heavyweight (see `54_Protocol_Extension_Guide.md`). **Decision for this plan:**
the handoff rides **Omega** as a distinct `message_type: mission_charter_ready`,
recipient = `AGENT-03-BROKER` (the orchestrator's consumer identity), reusing
the existing consumer with one added handler key. This keeps Omega as "the PM
agent's lane" while the human-facing Omega traffic uses other message types.
**Open for Kevin to confirm** — alternative is a dedicated internal control
topic if conflating with Omega is undesirable.

---

## EDCP-01 — Bus durability + missing lane senders (foundation) — COMPLETE

**Goal:** Make the bus *capable* of carrying commands. No flow changes.

**Status:** Complete as of 2026-06-14. Runtime behavior is unchanged with
`EVENT_DRIVEN_CONTROL_PLANE_ENABLED=false`.

**Files & functions**
- `protocol_bus_consumer.py` → `ProtocolBusConsumer._consume_lane`: added a
  consumer-group mode (`XGROUP CREATE` / `XREADGROUP` / `XACK`) with a persisted
  last-id, selectable per consumer. Keep `XREAD`-from-`$` as the default until
  the flag flips.
- `protocol_bus_producer.py`: added `send_omega_message` (handoff/status),
  `send_beta_result`, `send_delta_audit`. Additive; nothing calls them yet.
- `settings.py` + `.env.example`: added `EVENT_DRIVEN_CONTROL_PLANE_ENABLED=false`.

**Exit criteria**

| # | Criterion |
|---|---|
| 1 | Consumer can run in group mode and resumes after a simulated restart without dropping a published message (unit test with a fake/real Redis) |
| 2 | New producer helpers build bus-valid envelopes for Omega/Beta/Delta (schema validation passes) |
| 3 | `EVENT_DRIVEN_CONTROL_PLANE_ENABLED` present, default `false`; flag off ⇒ no behavioral change |
| 4 | `python -m ruff check services tests scripts` clean; existing tests green |

**Validation:** `test_protocol_bus_consumer.py` and
`test_orchestrator_agent_key_mode.py` pass; Ruff passes for touched Python
files.

**Rollback:** none needed — purely additive.

---

## EDCP-02 — PM → CEO seam (first real inversion, highest value)

**Goal:** PM publishes the approved charter to the bus; CEO is triggered by
consuming it instead of by the loop.

**Files & functions**
- `phases_intake.py` → `_prepare_pm_intake`: after `mission_charter` is built,
  also publish an Omega `mission_charter_ready` message (recipient
  `AGENT-03-BROKER`) carrying the charter. Dual-write; still returns `True`.
- `main.py` → `protocol_bus_consumer_loop`: add `"omega": _handle_charter_ready`
  to the `handlers` dict. The handler invokes `_prepare_ceo_delegation` for the
  mission id in the message.
- `lifecycle.py` → `advance_mission_lifecycle_v2`: when the flag is on, remove
  the `MissionState.fetch: _prepare_ceo_delegation` entry from `stage_preparers`
  so the loop pauses at `fetch` and the consumed event resumes the mission.
  Flag off ⇒ dict unchanged ⇒ identical behavior.

**Exit criteria**

| # | Criterion |
|---|---|
| 1 | With flag off: mission flow byte-for-byte unchanged; all current tests green |
| 2 | With flag on: publishing `mission_charter_ready` causes `_prepare_ceo_delegation` to run and the mission to advance past `fetch` |
| 3 | With flag on and the consumer down, mission does not silently complete CEO stage (proves the seam is load-bearing, not shadow) |
| 4 | New integration test covers the publish→consume→delegate path |

**Rollback:** flip flag to `false`; the in-loop CEO call is restored.

**Note:** the SOW / PRD / phased-build-plan documents (separate content track)
become enriched fields on the `mission_charter_ready` payload here — they do not
change the control-flow mechanics of this phase.

---

## EDCP-03 — CEO → pod manager seam (crosses into pod-worker)

**Goal:** Promote the existing shadow Alpha directive to the actual trigger, and
have the pod-worker consume Alpha instead of the state stream.

Split into two shippable items because it spans two services:

### EDCP-03a — CEO publishes load-bearing Alpha
- `phases_build.py` → `_prepare_pod_assignment` / `_send_alpha_delegation_directive`:
  under the flag, the Alpha publish is no longer fire-and-forget for the
  assignment hop — failure to publish blocks progression (the bus is now the
  command path).

### EDCP-03b — pod-worker consumes Alpha
- `services/pod-worker/pod_worker/main.py`: add an Alpha-lane consumer (subscribe
  as the pod-manager agent id) that starts specialist work on directive receipt.
  Under the flag, stop triggering off `missions.state` `MISSION_POD_MANAGER_ASSIGNED`.

**Exit criteria**

| # | Criterion |
|---|---|
| 1 | Flag off: pod-worker still triggers off `missions.state` exactly as today |
| 2 | Flag on: a real Alpha directive starts pod work; suppressing the state-stream event no longer prevents work |
| 3 | Durable: pod-worker restart mid-mission resumes from the bus (relies on EDCP-01 group mode) |
| 4 | `npm run lint` (if any TS touched) + `ruff` clean; pod-worker tests green |

**Rollback:** flag off restores state-stream triggering in both services.

---

## EDCP-04 — Support ring as Alpha/Delta participants

**Goal:** Replace in-orchestrator gate functions with CEO-issued Alpha
directives that support agents consume, replying on Delta. Largest surface,
lowest urgency → last of the inversion work.

**Files & functions**
- `lifecycle.py` → `_advance_verified_to_complete`: under the flag, replace the
  direct calls to `_prepare_security_compliance_report`,
  `_prepare_dependency_absorption_reports`, `_prepare_runtime_qc` (and deploy
  readiness) with: CEO publishes Alpha to the relevant support agent; the gate
  advances on the matching Delta `verified` reply.
- Support agent consumers (Security/Compliance/Tester/DepAbs) gain Alpha
  handlers + Delta replies.

**Exit criteria**

| # | Criterion |
|---|---|
| 1 | Flag off: gates run as direct calls exactly as today |
| 2 | Flag on: each gate is satisfied by a Delta `verified` reply, not a direct return |
| 3 | A failing Delta (`failed` / `correction_required`) blocks completion and is visible in the chain trace |
| 4 | `tests/eval/` green (touches mission_flow_v2) |

**Rollback:** flag off restores direct-call gates.

---

## EDCP-05 — Demote `missions.state` to a pure projection

**Goal:** Once commands ride the bus, `missions.state` is written only as an
observability/audit projection and triggers no work.

**Files & functions**
- `phases_intake.py` → `_emit_partition_work_items`: stop using
  `settings.state_stream` as a work channel; partition work is dispatched via
  the bus.
- `pod-worker`: remove remaining state-stream work triggers; state events become
  read-only for the UI/audit.

**Exit criteria**

| # | Criterion |
|---|---|
| 1 | No service consumes `missions.state` for *work* — only for projection/observability |
| 2 | UI mission timeline and audit trail unchanged (still fed by state events) |
| 3 | Full live BUILD_NEW mission completes end-to-end with the flag on |

**Rollback:** flag off reverts to state-stream work dispatch.

---

## Sequencing rationale

1. **EDCP-01 before anything** — durability is the enabling change; without
   consumer groups no consumer can be load-bearing.
2. **EDCP-02 next** — cheapest high-value seam, entirely inside the orchestrator
   process, directly realizes "PM talks to CEO over the bus."
3. **EDCP-03** — the first cross-service hop (orchestrator → pod-worker); larger
   blast radius, split a/b.
4. **EDCP-04** — broad support-ring conversion; many handlers, least urgent.
5. **EDCP-05** — cleanup that resolves the state-stream double-duty problem,
   only safe once commands already ride the bus.

Phases 1–2 do not touch the pod-worker or audit-worker at all.

## Open decisions / risks

- **Lane for the PM→CEO handoff** (Omega vs a dedicated control topic) — see the
  Lane decision section; confirm before EDCP-02.
- **Consumer identity.** The orchestrator consumes as `AGENT-03-BROKER`. If the
  CEO should consume under its own identity, decide before EDCP-02 wiring.
- **Single-orchestrator vs. distributed.** This plan keeps one orchestrator
  process that both publishes and consumes; it makes the *seams* event-driven
  without yet splitting agents into separate runtime processes. Splitting agents
  into their own services is a later, separate effort.
- **`IMPLEMENTATION_STATUS.md`** must be updated as each EDCP item lands — it,
  not the archived sprint backlog, is the authoritative status list.

## Validation commands (per the repo conventions)

- Python touched: `python -m ruff check services tests scripts`
- TypeScript touched: `npm run lint`
- `mission_flow_v2` / `llm_delegation` touched: `python -m pytest tests/eval/ -q`
- Commit format: `feat: EDCP-NN — [item title]`
