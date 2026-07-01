# Protocol Bus Mission Battery Plan

Document version: 2026.06.30
Last updated: 2026-06-30
Status: Active plan
Audience: Maintainers, operators, and AI coding agents

Live-validation companion to `PROTOCOL_BUS_LANE_ACTIVATION_PLAN.md` (PBLA). PBLA
made all six lanes produce; this plan is the mission battery that exercises them
against a running stack and, incidentally, drives real work through every one of
the 41 registered agents. Use with `CURRENT_TODO.md` and `HANDOFF_CURRENT.md`.

---

## Why a battery instead of one mission

A single mission only ever routes through one pod (one pod manager, one pod
audit agent, one specialist). To touch all 4 pods and all 19 language
specialists, distinct missions are required — one per language is the natural
unit, since `resolve_pod_manager_agent_id` / `resolve_specialist_agent_id`
(`orchestrator/mission_flow.py`) route deterministically off
`requested_target_language`.

## Agent-to-mission coverage map (grounded in code, 2026-06-30)

| Pod | Pod Manager | Pod Audit | Languages → Specialist |
|---|---|---|---|
| A | AGENT-12-PODA-MGR | AGENT-13-PODA-AUDIT | python→14, javascript/typescript→15, ruby→16, php→17 |
| B | AGENT-18-PODB-MGR | AGENT-19-PODB-AUDIT | go→36, rust→22, c→20, cpp→21, zig→23 |
| C | AGENT-24-PODC-MGR | AGENT-25-PODC-AUDIT | java→26, csharp→27, kotlin→29, scala→28 |
| D | AGENT-30-PODD-MGR | AGENT-31-PODD-AUDIT | matlab→32, r→33, julia→34, mathematica→35, haskell→37, ocaml→38 |

19 distinct languages → 19 distinct specialist agents (`typescript` aliases to
the JavaScript specialist, so it is not a 20th agent). One `BUILD_NEW` /
`FULL_BUILD` mission per language, run to `COMPLETE`, exercises:

- **AGENT-01-PM** (intake, every mission)
- **AGENT-02-CEO** (delegation, every mission) — emits **Alpha** to the pod manager
- the mission's **pod manager** and **pod audit** agent — pod audit emits **Delta** (PBLA-01)
- the mission's **specialist** — fused codegen emits **Beta** (PBLA-03)
- **AGENT-05-SECURITY**, **AGENT-07-VC** (delivery phase, fixed agent ids,
  `phases_delivery.py`) on every mission that reaches delivery
- **AGENT-06-IS** (knowledge-lake broadcast, fetch phase) — emits **Sigma**
- PM's delivery handoff emits **Omega** (PBLA-02)

That is 1 (PM) + 1 (CEO) + 4 (pod managers) + 4 (pod audits) + 19 (specialists)
+ 2 (Security, VC) + 1 (IS) = **32 of 41 agents exercised with real work**, and
all of **Alpha/Sigma/Delta/Omega/Beta** produced as a side effect of ordinary
mission completion.

### The remaining 9 agents — honest gaps, not oversights

| Agent | Why not exercised by this battery |
|---|---|
| AGENT-03-BROKER | Rho only fires on a real provider 429 (`llm_delegation/providers.py`, PBLA-04) — conditional, not guaranteed by any mission prompt. See "Rho verification" below. |
| AGENT-04-ACCOUNTANT | Not wired to any mission-flow call site as of 2026-06-30 — budget telemetry is heartbeat-only in the current build. |
| AGENT-09-HW | Same — heartbeat-only, no mission-flow call site. |
| AGENT-08-COMPLIANCE, AGENT-10-TESTER, AGENT-11-DEPLOY | Wired in `mission_flow_v2` (`lifecycle.py: _advance_verified_to_complete`) but only invoked for missions that reach the COMPLETE gate with those checks active — the language battery below reaches delivery, so include a chain-trace check for these three; if absent, that is itself useful evidence about which gate a given mission stopped at. |
| AGENT-39-DEPABS, AGENT-40-TESTDATA, AGENT-41-RQCA | Feature-flagged off by default in `deploy/docker-compose.yaml` (`DEPABS_EXECUTION_ENABLED`, `TESTDATA_AGENT_ENABLED`, `RQCA_AGENT_ENABLED` all `false`). Not reachable via mission work without flipping those flags — an operator decision, not something this battery does silently. Noted as a follow-up, not attempted here. |

All 41 agents already receive periodic heartbeats regardless of mission
activity (`main.py: agent_heartbeat_loop`) — that loop is unconditional and is
not what this battery is trying to prove. This battery is about **real work**,
not heartbeat presence.

---

## The battery: 20 missions

19 `BUILD_NEW` / `FULL_BUILD` missions (one per language, small self-contained
function prompts to keep LLM cost and runtime low) + 1 combined
`IMPORT_MODERNIZE` + `DEBUG_REPAIR` mission (proves the alternate mission-type
path, per the existing `demo_missions.py` pattern) = 20.

| # | Language | Pod | Mission type |
|---|---|---|---|
| 1 | python | A | BUILD_NEW |
| 2 | javascript | A | BUILD_NEW |
| 3 | ruby | A | BUILD_NEW |
| 4 | php | A | BUILD_NEW |
| 5 | go | B | BUILD_NEW |
| 6 | rust | B | BUILD_NEW |
| 7 | c | B | BUILD_NEW |
| 8 | cpp | B | BUILD_NEW |
| 9 | zig | B | BUILD_NEW |
| 10 | java | C | BUILD_NEW |
| 11 | csharp | C | BUILD_NEW |
| 12 | kotlin | C | BUILD_NEW |
| 13 | scala | C | BUILD_NEW |
| 14 | matlab | D | BUILD_NEW |
| 15 | r | D | BUILD_NEW |
| 16 | julia | D | BUILD_NEW |
| 17 | mathematica | D | BUILD_NEW |
| 18 | haskell | D | BUILD_NEW |
| 19 | ocaml | D | BUILD_NEW |
| 20 | python | A | IMPORT_MODERNIZE + DEBUG_REPAIR |

### Per-mission pass criteria

- Mission reaches `COMPLETE` (or a documented, non-crashing terminal state).
- Chain trace contains `MISSION_PM_INTAKE`, `MISSION_CEO_DELEGATED`,
  `MISSION_POD_MANAGER_ASSIGNED`, `MISSION_SPECIALIST_ASSIGNED`,
  `MISSION_POD_AUDIT_COMPLETE` with `agent_id` matching the expected pod audit
  agent for that language's pod.
- No exception/traceback in the orchestrator log attributable to the mission's
  `mission_id` during its run.

### Battery-level (bus) pass criteria

Captured once before and once after the full battery via
`protocol-bus-mcp` `/metrics` (`protocol_bus_mcp_messages_queued_total{protocol=…}`)
and `/dlq?protocol=…`:

- `messages_queued_total` increments for **alpha**, **delta**, **omega**,
  **beta**, **sigma** (5 of 6 — rho is separate, see below).
- `dlq_writes_total` does **not** increment for any protocol (zero DLQ writes).
- At least one Delta message's `findings.emission == "pbla_pod_audit_telemetry"`
  and one Omega message's `feature_contract.message_type ==
  "pbla_delivery_handoff"` and one Beta message's `payload.emission ==
  "pbla_specialist_result"` are confirmed by reading the corresponding
  `protocol:{lane}:broadcast` (or `protocol:beta:{pod_manager}`) Redis stream —
  proving the PBLA-00 discriminator contract round-trips through the real bus,
  not just the unit-test mocks.

---

## Rho verification (separate from the mission battery)

Rho (PBLA-04) only emits on a real HTTP 429 from an LLM provider
(`_post_with_retry` in `llm_delegation/providers.py`) — no mission prompt can
force that deterministically without either a genuinely rate-limited provider
key or mutating live provider configuration, which this plan deliberately does
**not** do against a shared running stack.

Instead, Rho gets a **targeted, isolated live-delivery smoke test**: invoke the
already unit-tested `_send_rho_traffic_control` helper directly (e.g. via
`docker exec` into the orchestrator container running a short Python snippet)
so it makes a real HTTP round trip to the live `protocol-bus-mcp`, without
touching the provider retry path or any environment variable. This proves the
Rho producer→bus wiring end-to-end on the real stack, clearly labeled in the
evidence as a **direct helper invocation**, not organic mission-driven traffic.
Organic Rho traffic remains a live-operations follow-up (only observable when a
real rate limit is hit in production use).

---

## Execution

Runner: `scripts/protocol_bus_mission_battery.py` (`--live`, mirrors
`scripts/demo_missions.py`'s request/poll/report shape). Submits the 20
missions sequentially against the API gateway, polls each to a terminal state,
checks chain-trace agent coverage, and writes a combined evidence report.

```
python scripts/protocol_bus_mission_battery.py --live \
  --gateway-base-url http://127.0.0.1:8100 \
  --output-file docs/evidence/protocol_bus_mission_battery_latest.json
```

Bus-side evidence (metrics deltas, DLQ counts, sampled discriminator payloads,
and the Rho direct-invocation result) is captured separately around the run and
folded into the same evidence file.

## Definition of done

- [ ] All 20 missions submitted and reach a terminal state
- [ ] Chain-trace agent-coverage check passes for all 19 language missions
      (pod manager / pod audit / specialist agent ids match the expected mapping)
- [ ] Bus metrics show queued increments for alpha/delta/omega/beta/sigma with
      zero DLQ writes across the battery
- [ ] At least one sampled Delta/Omega/Beta message confirms its PBLA
      discriminator
- [ ] Rho direct-invocation smoke test confirms a real bus round trip
- [ ] Evidence written to `docs/evidence/protocol_bus_mission_battery_latest.json`
- [ ] `CURRENT_TODO.md` / `HANDOFF_CURRENT.md` updated with the result
