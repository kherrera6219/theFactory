# Protocol Bus Lane Activation Plan

Document version: 2026.06.30
Last updated: 2026-06-30
Status: Active plan
Audience: Maintainers, operators, and AI coding agents

## Standalone Initiative — Not Part of the EDCP Phase Plan

**Owner:** Kevin
**Prerequisite:** None — independent of S1-01 and EDCP-01 through EDCP-05.
Can run before, after, or in parallel with either.

Use this plan with `CURRENT_TODO.md` and `HANDOFF_CURRENT.md`.

---

## Context

The Protocol Bus (`protocol-bus-mcp`) is fully built: all six lanes — Alpha,
Beta, Delta, Sigma, Omega, Rho — exist as strict Pydantic-validated message
types (`AlphaPayload` ... `RhoPayload` in `mcp_server.py`), each routed to its
own Redis Streams channel, with HMAC sender verification, replay detection,
per-channel dedup, backpressure, and a DLQ per protocol. The consumer side
(`ProtocolBusConsumer`) already supports both legacy `XREAD` and durable
consumer-group mode, anticipating EDCP's eventual move to bus-driven control.

The gap is not infrastructure — it's adoption. A repo-wide trace of every
`send_*` function in `protocol_bus_producer.py` shows only two of six lanes
have live callers in the mission pipeline:

| Lane | Producer function | Live caller? | Location |
|---|---|---|---|
| Alpha | `send_alpha_directive` | Yes | `phases_build.py` — CEO → Pod Manager delegation |
| Sigma | `send_sigma_knowledge` | Yes | `phases_intake.py` via `knowledge_lake.broadcast_knowledge_ready` |
| Delta | `send_delta_audit` | **No** | — |
| Omega | `send_omega_message` | **No** | — |
| Beta | `send_beta_result` | **No** | — |
| Rho | `send_rho_control` | **No** | — |

This plan adds the four missing call sites. Each phase follows the exact
pattern Alpha and Sigma already prove in production: a private
`_send_<lane>_<event>()` helper, a local import of the relevant `send_*`
function, dispatch via `asyncio.to_thread`, and a try/except that logs and
swallows so a bus outage can never block mission progression. No new
infrastructure, no schema changes, no new pattern — this is wiring, not design.

**Why standalone and not folded into EDCP:** EDCP inverts control flow onto
the bus. That migration is easier and lower-risk if all six lanes are already
populated with real traffic before EDCP-01 starts cutting state-machine logic
over to bus-driven dispatch. Treating lane activation as its own initiative
keeps EDCP's scope limited to control-flow inversion, and gives EDCP test
fixtures real lane traffic to validate against from day one.

---

## Where PBLA Sits in the Larger Bus Program (scope boundary)

PBLA on its own does **not** make the agents "talk over the bus." It makes the
four dark lanes *observable* (real producers, traffic on the streams), not
*load-bearing* (nothing consumes them, no control flow changes). Today the
runtime is a single synchronous orchestrator state machine
(`mission_flow_v2/lifecycle.py` walks `V2_TRANSITIONS` and calls each agent
stage as a direct in-process function); agent IDs are labels stamped on bus
envelopes and chain-trace events, not addresses of running processes. Only Sigma
is a closed produce→consume loop today (`main.py: protocol_bus_consumer_loop`
registers exactly one handler, `{"sigma": _handle_sigma_knowledge_ready}`).

Getting to a genuinely bus-driven, agent-coordinated system is a **staged
program**, of which PBLA is deliberately only the first, lowest-risk step:

1. **PBLA (this plan) — producers / telemetry.** Light up all six lanes with
   real traffic. Fire-and-forget; no behavior change. *Prerequisite for, but
   intentionally separate from, everything below.*
2. **EDCP (separate plan, `docs/archive/2026-06-27/EDCP_Phase_Plan.md`) —
   consumers + control-flow inversion.** This is what actually makes the bus a
   command backbone. EDCP-01 (already complete) shipped the producer helpers and
   the consumer-group durability mode behind `EVENT_DRIVEN_CONTROL_PLANE_ENABLED`
   (default `false`). EDCP-02→05 add consumer handlers and, under the flag,
   remove the in-loop direct calls seam by seam (PM→CEO, CEO→pod, support-ring
   gates), finally demoting `missions.state` to a read-only projection. **Without
   EDCP, PBLA's four new lanes stay write-only.**
3. **Agents as independent runtime processes — later, separate effort.** EDCP
   keeps a single orchestrator process that both publishes and consumes; it makes
   the *seams* event-driven without splitting agents into their own services. A
   real distributed actor model (the `agent-runtime` service scaffolding, each of
   the 41 agents consuming/replying under its own identity) is explicitly out of
   scope for both PBLA and EDCP and would be its own initiative.
4. **Semantic bus — future capability, not yet designed in theFactory.** Routing
   today is purely lexical (`protocol:{lane}:{recipient}` channel strings). The
   `SigmaPayload.embedding_ref` field exists but is reserved — "not computed,
   stored, or matched today" (`mcp_server.py`). True semantic routing (dispatch
   by embedding similarity, per the Holygrail
   `20_Semantic_Bus_Implementation_Guide.md`) depends on the knowledge-lake
   embedding path (S1-01 / Qdrant) and on EDCP already owning the routing layer.
   It is the most speculative step and should not be attempted before 1–3 land.

**Scope decision for this plan:** PBLA stays narrow — producers only, no
consumers, no agent-process split, no semantic routing. Each later stage is
tracked separately so PBLA stays revertible and low-risk.

---

## Forward-Compatibility Requirement (applies to every PBLA phase)

PBLA is *not* zero-coupling telemetry, and this is the most important thing the
implementation must get right. **The consumer tails both channels of a lane:**
`ProtocolBusConsumer._consume_lane` reads `protocol:{lane}:{agent_id}` **and**
`protocol:{lane}:broadcast` and feeds both to the same per-lane handler
(`protocol_bus_consumer.py`). Consequence: when EDCP later adds a load-bearing
consumer on a lane PBLA broadcasts to, **that consumer will also receive PBLA's
shadow telemetry** — it cannot avoid it by listening on a different channel.

Therefore every PBLA emission **must stamp a stable discriminator** in its
free-form dict field so a future consumer can filter telemetry from command/reply
traffic. This is mandatory for correctness, not hygiene:

| Lane | PBLA recipient | Discriminator field | Value |
|---|---|---|---|
| Delta (PBLA-01) | `broadcast` | `findings.emission` | `pbla_pod_audit_telemetry` |
| Omega (PBLA-02) | `broadcast` | `feature_contract.message_type` | `pbla_delivery_handoff` |
| Beta (PBLA-03) | `{pod_manager}` (directed) | `payload.emission` | `pbla_specialist_result` |
| Rho (PBLA-04) | `broadcast` | `metadata.emission` | `pbla_traffic_telemetry` |

These values are defined once in `orchestrator/protocol_bus_emissions.py`
(**PBLA-00**, below) and imported by both producers (here) and EDCP consumers —
the literals shown in PBLA-01..04 are illustrative of that shared constant.

The matching obligation lands on EDCP: **EDCP-02's Omega charter handler and
EDCP-04's Delta reply handler must filter on these discriminators** (ignore
`pbla_*` emissions) so PBLA's shadow traffic never gets mistaken for a charter or
a verified reply. Beta is lowest risk because it is directed to the pod manager,
not broadcast, but stamp it anyway for symmetry.

**Omega specifically:** PBLA-02 broadcasts (`protocol:omega:broadcast`); EDCP-02's
charter is directed to `AGENT-03-BROKER` (`protocol:omega:AGENT-03-BROKER`). But
because the orchestrator's Omega consumer (identity `AGENT-03-BROKER`) tails the
broadcast channel too, it *will* see PBLA-02's handoffs — so the
`message_type` discriminator on the charter handler is load-bearing, not
optional.

---

## Phase PBLA-00 — Foundation: shared emission-discriminator contract

**Why first (before PBLA-01):** the `pbla_*` discriminators are a contract
between PBLA's producers (this plan) and EDCP's consumers (Stage 2). If each side
hard-codes the strings as literals they will drift. Define them once, in a module
both the orchestrator producers and the future EDCP consumers import.

### Exact change

**New file:** `services/orchestrator/orchestrator/protocol_bus_emissions.py`

```python
"""Shared emission discriminators for Protocol Bus telemetry (PBLA).

These constants are the contract that lets a load-bearing EDCP consumer filter
PBLA's shadow telemetry out of a lane it shares (consumers tail the broadcast
channel as well as their directed channel). Producers (PBLA) stamp them;
consumers (EDCP) match them. Do not inline these strings anywhere else.
"""
from __future__ import annotations

# Dict key under which the discriminator is stamped, per lane payload field.
EMISSION_KEY = "emission"                 # delta.findings / beta.payload / rho.metadata
OMEGA_MESSAGE_TYPE_KEY = "message_type"   # omega.feature_contract

# Discriminator values — one per PBLA emission.
PBLA_POD_AUDIT_TELEMETRY = "pbla_pod_audit_telemetry"   # PBLA-01 Delta
PBLA_DELIVERY_HANDOFF = "pbla_delivery_handoff"         # PBLA-02 Omega
PBLA_SPECIALIST_RESULT = "pbla_specialist_result"       # PBLA-03 Beta
PBLA_TRAFFIC_TELEMETRY = "pbla_traffic_telemetry"       # PBLA-04 Rho

# Convenience set for consumer-side filtering ("is this a PBLA shadow emission?").
PBLA_EMISSIONS = frozenset({
    PBLA_POD_AUDIT_TELEMETRY,
    PBLA_DELIVERY_HANDOFF,
    PBLA_SPECIALIST_RESULT,
    PBLA_TRAFFIC_TELEMETRY,
})
```

Each PBLA phase imports the relevant constant instead of the literal shown in its
code block (the literals in PBLA-01..04 below are illustrative). EDCP-02/04
import `OMEGA_MESSAGE_TYPE_KEY` / `EMISSION_KEY` + `PBLA_EMISSIONS` to filter.

### New tests

`tests/services/test_protocol_bus_emissions.py` — a trivial contract test that
pins the constant values (so a rename is a deliberate, reviewed change) and
asserts `PBLA_EMISSIONS` contains all four.

### Definition of done

- [x] `protocol_bus_emissions.py` added with the four constants + `PBLA_EMISSIONS`
      (plus an `is_pbla_emission()` consumer-side helper)
- [ ] PBLA-01..04 import from it rather than inlining strings (done as each lane lands)
- [x] Contract test pins the values
      (`tests/services/test_protocol_bus_emissions.py` — 3 tests pass)
- [x] EDCP plan references the same module for its consumer-side filter

---

## Phase PBLA-01 — Delta (Audit Verdicts)

**Why first:** fully grounded — exact insertion point confirmed, payload
fields already exist in the data being persisted. Lowest risk, fastest win.

### Exact change

**File:** `services/orchestrator/orchestrator/mission_flow_v2/phases_build.py`

Insert immediately after `generate_pod_audit_verdict()` returns (~line 690),
alongside the existing `MISSION_POD_AUDIT_COMPLETE` chain-event append:

```python
async def _send_delta_audit_verdict(
    *,
    settings: Any,
    mission_id: str,
    pod_name: str,
    pod_manager_agent_id: str,
    pod_audit: dict[str, Any],
) -> None:
    """Broadcast the pod audit verdict as a Protocol Delta message.

    Non-blocking: failures are swallowed by the producer and by this
    wrapper so mission progression is never affected by a bus outage.
    """
    from ..protocol_bus_producer import send_delta_audit  # noqa: PLC0415

    try:
        await asyncio.to_thread(
            send_delta_audit,
            settings=settings,
            sender=pod_audit.get("agent_id", pod_manager_agent_id),
            recipient="broadcast",
            audit_result=_map_verdict_to_audit_result(pod_audit.get("verdict")),
            verification_method=str(pod_audit.get("source", "pod_audit")),
            tolerance_score=float(pod_audit.get("quality_score") or 0.0),
            findings={
                # Mandatory telemetry discriminator — see "Forward-Compatibility
                # Requirement". A future EDCP Delta consumer on the broadcast
                # channel must be able to tell PBLA shadow telemetry apart from
                # load-bearing verified/correction replies.
                "emission": "pbla_pod_audit_telemetry",
                "mission_id": mission_id,
                "pod": pod_name,
                "verdict": pod_audit.get("verdict"),
            },
            correlation_id=f"delta-{mission_id}-{pod_name}",
        )
    except Exception:
        LOGGER.warning(
            "Delta audit dispatch failed for mission %s pod %s (non-blocking)",
            mission_id, pod_name,
        )


def _map_verdict_to_audit_result(verdict: Any) -> str:
    """DeltaPayload.audit_result is Literal['pass', 'fail', 'warning'] —
    map the pod audit verdict vocabulary onto that set."""
    value = str(verdict or "").strip().lower()
    if value in ("pass", "passed", "approved", "verified"):
        return "pass"
    if value in ("fail", "failed", "rejected"):
        return "fail"
    return "warning"
```

**Placement (code-verified 2026-06-30):** call it **inside** the existing
`if not _chain_event_exists(metadata, "MISSION_POD_AUDIT_COMPLETE"):` guard
(`phases_build.py` ~L700), alongside the `MISSION_POD_AUDIT_COMPLETE` chain-event
append — not before it. This function (`_finalize_pod_group_standard`) can re-run
for the same mission+pod on resume/retry; emitting inside the idempotency guard
makes Delta fire exactly once per pod per mission instead of relying on the bus's
dedup/replay window (default 300s) to suppress repeats. `pod_manager_agent_id`
is in scope at that point.

**Sender confirmed valid:** `pod_audit["agent_id"]` resolves to the QC agent id
(`AGENT-13-PODA-AUDIT` / `AGENT-19-PODB-AUDIT` / `AGENT-25-PODC-AUDIT`, default
`AGENT-13-PODA-AUDIT` — see `_POD_AUDIT_AGENTS` in `generators_artifacts.py`), all
of which match the bus `AGENT_ID_PATTERN`. No sender-validation risk.

**Scope boundary — this covers the orchestrator-side verdict only.** There is a
*second* audit surface: the standalone `audit-worker` service runs its own audit
and POSTs results to `{ORCHESTRATOR_URL}/internal/audit-reports` over HTTP — it
emits no bus traffic. PBLA-01 deliberately does **not** touch it. Making the
audit-worker a load-bearing Delta participant is EDCP-04's job (support ring on
Alpha/Delta), not PBLA's. Do not expand PBLA-01 to the audit-worker.

### New tests

`tests/services/test_mission_flow_v2_phases_build.py` — add a test that mocks
`protocol_bus_producer.send_delta_audit` and asserts it is called once per
pod audit with the correct `audit_result` mapping for `pass`/`fail`/anything
else → `warning`.

### Validation

1. `pytest tests/services/test_mission_flow_v2_phases_build.py -v`
2. Live: run one mission to `COMPLETE`, then check
   `GET /dlq?protocol=delta` on protocol-bus-mcp returns empty.
3. Confirm `protocol:delta:broadcast` Redis stream has at least one entry
   matching the mission's pod count.

### Definition of done

- [ ] `_send_delta_audit_verdict` implemented and called from `phases_build.py`
- [ ] Verdict mapping covers pass/fail/warning correctly under test
- [ ] Live mission produces Delta entries on the bus, zero DLQ writes
- [ ] `IMPLEMENTATION_STATUS.md` updated to note Delta lane is live

---

## Phase PBLA-02 — Omega (PM ↔ User Handoff)

### Exact change

**File:** `services/orchestrator/orchestrator/mission_flow_v2/phases_delivery.py`

Insert after the `pm_delivery_summary` generation (~line 63):

```python
async def _send_omega_handoff(
    *,
    settings: Any,
    mission_id: str,
    pm_agent_id: str,
    delivery_summary: dict[str, Any],
    feature_contract: dict[str, Any] | None,
) -> None:
    """Broadcast the PM delivery handoff as a Protocol Omega message.

    Per the existing EDCP-02 deferral noted in protocol_bus_producer.py,
    Omega's schema is intentionally user-intent shaped today. Internal
    handoff metadata rides inside feature_contract rather than getting a
    new payload field — do not extend OmegaPayload for this.
    """
    from ..protocol_bus_producer import send_omega_message  # noqa: PLC0415

    try:
        await asyncio.to_thread(
            send_omega_message,
            settings=settings,
            sender=pm_agent_id,
            recipient="broadcast",
            user_intent=str(
                delivery_summary.get("delivery_title")
                or delivery_summary.get("summary")
                or "mission handoff"
            ),
            feature_contract={
                # Mandatory discriminator (see "Forward-Compatibility
                # Requirement"). EDCP-02's charter handler filters on this so a
                # PBLA delivery handoff is never mistaken for a
                # mission_charter_ready charter on the shared Omega broadcast.
                "message_type": "pbla_delivery_handoff",
                **(feature_contract or {}),
            },
            correlation_id=f"omega-{mission_id}",
        )
    except Exception:
        LOGGER.warning(
            "Omega handoff dispatch failed for mission %s (non-blocking)",
            mission_id,
        )
```

### New tests

Add to `tests/services/test_mission_flow_v2_phases_delivery.py`: mock
`send_omega_message`, assert it's called once at delivery with
`user_intent` populated from the delivery summary.

### Validation

Same shape as PBLA-01: unit test, then live mission check against
`protocol:omega:broadcast` and `/dlq?protocol=omega`.

### Definition of done

- [ ] `_send_omega_handoff` implemented and called from `phases_delivery.py`
- [ ] Confirmed no new OmegaPayload fields introduced (stays within
      existing `feature_contract` field per EDCP-02 deferral note)
- [ ] Live mission produces Omega entries on the bus, zero DLQ writes
- [ ] `IMPLEMENTATION_STATUS.md` updated

---

## Phase PBLA-03 — Beta (Specialist/LogicNode Results)

**Why third:** insertion point confirmed (2026-06-30), but two of the three
required Beta fields are absent from the specialist output and must be
synthesized — slightly more than pure wiring.

### Insertion point (confirmed in code)

**File:** `services/orchestrator/orchestrator/mission_flow_v2/phases_runtime.py`,
in `_prepare_fusion`, **immediately after** `metadata["generated_output"] =
generated_output` (~L568), inside the `if ... ready_for_codegen and not
mission_has_generated_output(...)` block so it fires only when the specialist
actually generated code.

**Field availability (verified against `_normalize_codegen_result` in
`llm_delegation/normalizers.py`):** `generated_output` (schema
`generated_output.v1`) contains `language`, `specialist_agent_id`,
`model_provider`, `model`, `source`, `code_length_chars` — **but no
`logicnode_id` and no `confidence_score`.** So:

- `source_language` ← `generated_output["language"]` (present).
- `sender` ← `generated_output["specialist_agent_id"]` (present, bus-valid).
- `recipient` (pod manager) ← `metadata["assigned_pod_manager_agent_id"]`
  (set in the build phase; fall back to `resolve_pod_manager_agent_id(...)`).
  `pod_manager_agent_id` is **not** a local in `_prepare_fusion` — read it from
  metadata. **Required import (verified missing 2026-06-30):** `phases_runtime.py`
  imports `resolve_specialist_agent_id` and `_validate_agent_id` but **not**
  `resolve_pod_manager_agent_id` — add it to the existing
  `from ..mission_flow import (...)` block (it is defined in `mission_flow.py`,
  already imported the same way by `phases_build.py`).
- `logicnode_id` ← **synthesize** a stable id, e.g.
  `f"ln-{mission.mission_id}-fused"` (the fused codegen is not a single
  LogicNode; use `master_stream["total_unified_nodes"]` in the payload for
  count context).
- `confidence_score` ← **synthesize** from `generated_output["source"]`
  (`"llm"` → e.g. `0.85`, `"fallback"`/`"error"` → e.g. `0.3`). Must be in
  `[0.0, 1.0]` or `BetaPayload` rejects it (422 → DLQ). Do not pass a raw model
  score without clamping.

### Exact change (grounded)

```python
async def _send_beta_production_result(
    *,
    settings: Any,
    mission_id: str,
    specialist_agent_id: str,
    pod_manager_agent_id: str,
    logicnode_id: str,
    confidence_score: float,
    source_language: str,
    payload: dict[str, Any] | None = None,
) -> None:
    from ..protocol_bus_producer import send_beta_result  # noqa: PLC0415

    try:
        await asyncio.to_thread(
            send_beta_result,
            settings=settings,
            sender=specialist_agent_id,
            recipient=pod_manager_agent_id,
            logicnode_id=logicnode_id,
            confidence_score=confidence_score,
            source_language=source_language,
            payload={
                # PBLA_SPECIALIST_RESULT from protocol_bus_emissions (PBLA-00).
                # Beta is directed to the pod manager (not broadcast), so
                # collision risk is low, but stamp for symmetry.
                "emission": "pbla_specialist_result",
                "unified_node_count": payload.get("unified_node_count") if payload else None,
                **(payload or {}),
            },
            correlation_id=f"beta-{mission_id}-{logicnode_id}",
        )
    except Exception:
        LOGGER.warning(
            "Beta result dispatch failed for mission %s (non-blocking)",
            mission_id,
        )
```

Call site (inside `_prepare_fusion`, right after `metadata["generated_output"]
= generated_output`), showing the required synthesis:

```python
_pod_mgr = _validate_agent_id(
    metadata.get("assigned_pod_manager_agent_id"),
    fallback=resolve_pod_manager_agent_id(mission.requested_target_language),
)
_confidence = 0.85 if generated_output.get("source") == "llm" else 0.3
await _send_beta_production_result(
    settings=settings,
    mission_id=mission.mission_id,
    specialist_agent_id=generated_output.get("specialist_agent_id", specialist_agent_id),
    pod_manager_agent_id=_pod_mgr,
    logicnode_id=f"ln-{mission.mission_id}-fused",
    confidence_score=_confidence,
    source_language=str(generated_output.get("language") or "python"),
    payload={"unified_node_count": master_stream.get("total_unified_nodes")},
)
```

### New tests

Add to `tests/services/test_mission_flow_v2_phases_runtime.py` (or the existing
fusion test module): mock `send_beta_result`, assert one call on a successful
codegen with `source_language` from `generated_output["language"]`,
`confidence_score` in `[0,1]`, and the synthesized `logicnode_id`; assert it is
NOT called when codegen is skipped (`ANALYZE_ONLY` / not `ready_for_codegen`).

### Validation

Same shape as PBLA-01/02, checked against `protocol:beta:{pod_manager_agent_id}`.

### Definition of done

- [x] Insertion point confirmed (`_prepare_fusion`, after generated_output set)
- [ ] `confidence_score`/`logicnode_id` synthesis implemented and clamped to `[0,1]`
- [ ] `_send_beta_production_result` implemented and called at that point
- [ ] Live mission produces Beta entries on the bus, zero DLQ writes
- [ ] `IMPLEMENTATION_STATUS.md` updated

---

## Phase PBLA-04 — Rho (Traffic / Rate-Limit Control)

**Why last:** candidate sites confirmed (2026-06-30), but there is a real
structural blocker (`settings` is not in scope at the provider layer) that must
be decided before coding. Lowest urgency of the four.

### Candidate sites (confirmed in code) and the blocker

`services/orchestrator/orchestrator/llm_delegation/providers.py` already has the
two natural Rho events, both already adjacent to existing telemetry:

1. **Rate-limit / backoff** — `_post_with_retry` (~L96) retries on HTTP 429 and
   5xx (`if response.status_code == 429 or >= 500`). A Rho emission with
   `rate_limit_action="retry_backoff"` belongs here.
2. **Provider fallback / error** — `_call_provider` (~L398) has a `finally` block
   that already records provider health and `record_llm_request(...)` telemetry,
   and `agent_target` is available there via `current_agent_id.get()`. A Rho
   emission with `rate_limit_action="provider_error"` / `"fallback"` belongs in
   that `finally`, beside the existing metric.

**Blocker — `settings` is not available at the provider layer.** These are
module-level transport helpers; they have no `settings` object, but
`send_rho_control` needs it for the bus URL/API key. Resolve one of:

- **(a, recommended) Emit one layer up.** `_call_with_recommendation` /
  `_call_with_agent_system` sit above `_call_provider` and are closer to call
  sites that *do* have settings; pass settings down or emit there on a
  fallback/error result. Lowest blast radius, keeps providers.py settings-free.
- **(b) Module-level bus accessor.** Add a tiny settings/`bus config`
  accessor that reads `PROTOCOL_BUS_URL` / `MCP_API_KEY` from env directly
  (the producer already falls back to env-style attrs), used only by the Rho
  path. Avoids threading settings but adds a second config source.
- **(c) Defer Rho to a higher-level signal.** Emit Rho from the orchestrator
  where provider-fallback outcomes are already surfaced (e.g. when a mission
  records a degraded/fallback result), not from inside the transport loop.

`token_budget` has no real source in this path today — pass a best-effort
estimate or `0`, and carry the real signal (`provider`, `model`, `status`) in
`metadata`. Decide (a)/(b)/(c) before writing the helper; the example below
assumes the helper receives `settings` from whichever site is chosen.

### Exact change (helper pattern — call site per decision above)

### Exact change (pattern, pending confirmed insertion point)

```python
async def _send_rho_traffic_control(
    *,
    settings: Any,
    broker_agent_id: str,
    token_budget: int,
    rate_limit_action: str,
    agent_target: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    # Import path is location-dependent: the producer lives at
    # orchestrator/protocol_bus_producer.py. Use `..protocol_bus_producer` from a
    # module inside a subpackage (mission_flow_v2/ or llm_delegation/), and
    # `.protocol_bus_producer` only from a module directly under orchestrator/.
    # Confirm the correct depth once the Rho call-site module is chosen.
    from ..protocol_bus_producer import send_rho_control  # noqa: PLC0415

    try:
        await asyncio.to_thread(
            send_rho_control,
            settings=settings,
            sender=broker_agent_id,
            recipient="broadcast",
            token_budget=token_budget,
            rate_limit_action=rate_limit_action,
            agent_target=agent_target,
            metadata={
                # Discriminator (see "Forward-Compatibility Requirement").
                "emission": "pbla_traffic_telemetry",
                **(metadata or {}),
            },
        )
    except Exception:
        LOGGER.warning(
            "Rho traffic-control dispatch failed (non-blocking): target=%s",
            agent_target,
        )
```

### New tests

Mock `send_rho_control`; drive a 429 (or a forced provider error) through the
chosen call site and assert one Rho emission with `rate_limit_action` set and
`agent_target` from `current_agent_id.get()`. Because the trigger is a provider
error rather than the normal mission path, this test will likely live in the
provider/transport test module, not a mission_flow_v2 one.

### Validation

Same shape as the prior three phases, checked against `protocol:rho:broadcast`.
A clean mission may emit **zero** Rho messages (no rate-limit hit) — unlike
Delta/Beta, Rho traffic is conditional, so validate with a synthetic 429 or a
forced-fallback run, not a happy-path mission.

### Definition of done

- [x] Candidate sites confirmed (`_post_with_retry` 429 path; `_call_provider`
      finally) and the `settings`-scope blocker documented
- [ ] Settings-availability decision (a/b/c above) made and recorded
- [ ] `_send_rho_traffic_control` implemented and wired at the chosen site
- [ ] Synthetic rate-limit/fallback run produces Rho entries, zero DLQ writes
- [ ] `IMPLEMENTATION_STATUS.md` updated

---

## Phase PBLA-05 — Lane observability surfacing (optional, do last)

**Why optional:** PBLA-01..04 already make lane traffic observable via the bus
`/metrics` endpoint and raw streams (see Closing Validation). PBLA-05 only
decides whether to surface per-lane activity in the app's own operations view so
an operator sees "all six lanes live" without scraping Redis. Pure
read/observability — no new producers.

### Investigation step (do first)

The orchestrator already builds an operations snapshot
(`main.py: _build_operations_agents_snapshot`, exposed at
`/v1/operations/agents` and `/v1/operations/agent-integrations`) and the bus
already exports `protocol_bus_mcp_messages_queued_total{protocol}` at `/metrics`.
Decide whether lane-activity belongs in the existing operations snapshot or stays
a metrics-only concern. Do not add a new persistence path for this.

### Candidate change (only if surfacing is wanted)

- Read the six `protocol_bus_mcp_messages_queued_total{protocol}` counters (or
  `XLEN protocol:{lane}:*`) when assembling the operations snapshot, and add a
  `lane_activity` block (per-lane queued count + last-seen) to the operations
  payload.
- Optionally render it in the Mission Control agents/operations panel that
  already shows agent integration data.

### Definition of done

- [ ] Decision recorded: surface in operations snapshot, or metrics-only
- [ ] If surfaced: `lane_activity` added to the operations payload (read-only)
      with a regression test; Mission Control optionally renders it
- [ ] No new producer or persistence path introduced

---

## Closing Validation — All Six Lanes Live

After PBLA-00 through PBLA-04 are complete, run a single combined check:

```bash
python scripts/demo_missions.py --live
```

Then confirm via protocol-bus-mcp that all six `protocol:{lane}:*` streams
show traffic for that one mission run — not just Alpha and Sigma. This is
the evidence artifact for "all six lanes are live," parallel in form to the
existing S1-01 evidence in `docs/evidence/`. Suggested location:
`docs/evidence/protocol_bus_six_lane_smoke_latest.json`.

**Two evidence paths — use both.** Raw stream inspection
(`XLEN protocol:{lane}:broadcast`, `GET /dlq?protocol={lane}`) proves per-lane
delivery. The bus *also* already exports a Prometheus counter
`protocol_bus_mcp_messages_queued_total{protocol=...}` (and
`..._dlq_writes_total`) at `GET /metrics` on protocol-bus-mcp — scraping that
before/after the run is a lower-friction way to assert all six protocols
incremented and no DLQ writes occurred. Capture both in the evidence file.

Update `docs/IMPLEMENTATION_STATUS.md`'s Current Proof Points table with a
new row once this passes.

---

## Risk Notes

**Bus outage must never affect mission progression.** Every helper in this
plan follows the existing fire-and-forget contract: `send_protocol_message`
in `protocol_bus_producer.py` already returns `False` rather than raising,
and every `_send_*` wrapper here additionally wraps the `asyncio.to_thread`
call in its own try/except. This is intentional duplication, matching the
existing Alpha/Sigma helpers — do not remove either layer of protection.

**Delta verdict vocabulary — confirmed (2026-06-30).** `DeltaPayload.audit_result`
is a strict `Literal["pass", "fail", "warning"]`. The actual verdict vocabulary
produced by `generate_pod_audit_verdict()` is `{"PASS", "FAIL", "WARN"}` (see
`llm_delegation/generators_artifacts.py` — the value is upper-cased and
constrained to that set). `_map_verdict_to_audit_result()` lower-cases first, so
PASS→`pass`, FAIL→`fail`, WARN→`warning` all map correctly; the fallthrough is
not reachable by any real verdict value. Also confirmed: `quality_score` is
already clamped to `[0.0, 1.0]` at the source, so `tolerance_score`
(`Field(ge=0.0, le=1.0)`) can never overflow and trigger a 422/DLQ write. The
mapping no longer carries an open risk — keep the fallthrough only as a defensive
default if the audit vocabulary is ever extended.

**Omega payload scope discipline.** Resist the temptation to add new
fields to `OmegaPayload` for handoff metadata. The producer code already
documents this as an intentional EDCP-02 deferral — adding fields now
creates a schema that EDCP-02 then has to either keep or break.

**Deterministic correlation_ids interact with bus dedup/replay.** Each helper
uses a deterministic id (`delta-{mission_id}-{pod_name}`, `omega-{mission_id}`,
`beta-{mission_id}-{logicnode_id}`). The bus rejects a repeat of the same
correlation_id within the dedup TTL (default 300s) — replay → 409, dedup → 200
`deduplicated`. Across distinct pods/missions these ids are already unique, so
this is fine. The only repeat case is the *same* phase re-running for the *same*
mission within the TTL (resume/retry); emitting inside the
`MISSION_POD_AUDIT_COMPLETE` idempotency guard (PBLA-01) already prevents that
for Delta. For Omega/Beta, a retried emission is simply swallowed as a dedup —
acceptable for telemetry. Do **not** switch to per-call random correlation_ids
to "fix" this: that would defeat the bus's idempotency and double-count traffic.

**Forward coupling is real — see "Forward-Compatibility Requirement".** PBLA is
not zero-coupling: because consumers tail the broadcast channel, the `pbla_*`
discriminators stamped here become a contract EDCP-02/04 consumers must filter
on. This is the one place PBLA constrains a later stage.

**Sequencing relative to EDCP.** This plan does not change control flow —
it only adds telemetry. It is safe to run before, during, or after EDCP-01
through EDCP-05 without coordination risk, but running it first gives EDCP
real traffic on all six lanes to test against from the start.
