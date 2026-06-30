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

Call it right after `pod_audits[pod_name] = pod_audit` is set, before the
function returns.

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
            user_intent=str(delivery_summary.get("summary", "mission handoff")),
            feature_contract=feature_contract or {},
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

**Why third:** insertion point is not yet confirmed to the line — needs a
short read of `phases_runtime.py` before writing code.

### Investigation step (do first)

`view services/orchestrator/orchestrator/mission_flow_v2/phases_runtime.py`
and identify which of the `MISSION_*` chain events (candidates around lines
84, 200, 214, 262, 332, 385, 411) corresponds to specialist/LogicNode
completion as opposed to other build-stage transitions. Confirm the
specialist's generated-output dict has (or can be made to have) a
`logicnode_id`, `confidence_score`, and `source_language` — these may need
light normalization if the specialist generator doesn't already emit them
in that shape.

### Exact change (pattern, pending confirmed insertion point)

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
            payload=payload or {},
            correlation_id=f"beta-{mission_id}-{logicnode_id}",
        )
    except Exception:
        LOGGER.warning(
            "Beta result dispatch failed for mission %s (non-blocking)",
            mission_id,
        )
```

### New tests

Add to the relevant `phases_runtime` test module once the insertion point
is confirmed: mock `send_beta_result`, assert call with correct
`logicnode_id`/`confidence_score`/`source_language` mapping from the
specialist's actual output structure.

### Validation

Same shape as PBLA-01/02, checked against `protocol:beta:{pod_manager_agent_id}`.

### Definition of done

- [ ] Insertion point in `phases_runtime.py` confirmed by direct read
- [ ] `_send_beta_production_result` implemented and called at that point
- [ ] Live mission produces Beta entries on the bus, zero DLQ writes
- [ ] `IMPLEMENTATION_STATUS.md` updated

---

## Phase PBLA-04 — Rho (Traffic / Rate-Limit Control)

**Why last:** the only lane without an obvious existing insertion point —
needs the most investigation, lowest urgency of the four.

### Investigation step (do first)

`view services/orchestrator/orchestrator/llm_delegation/providers.py` and
the API Broker logic in `services/api-gateway/` to find where rate-limit
decisions, provider fallback, or token-budget enforcement currently happen
without any bus emission. Unlike Delta/Omega/Beta, there is no existing
chain-event analog to anchor this to — it may need a new call site inside
the provider-selection or fallback-handling logic rather than inside
`mission_flow_v2`.

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
    from .protocol_bus_producer import send_rho_control  # noqa: PLC0415

    try:
        await asyncio.to_thread(
            send_rho_control,
            settings=settings,
            sender=broker_agent_id,
            recipient="broadcast",
            token_budget=token_budget,
            rate_limit_action=rate_limit_action,
            agent_target=agent_target,
            metadata=metadata or {},
        )
    except Exception:
        LOGGER.warning(
            "Rho traffic-control dispatch failed (non-blocking): target=%s",
            agent_target,
        )
```

### New tests

Add once the insertion point is confirmed: mock `send_rho_control`, assert
it's called on rate-limit/fallback events with correct `rate_limit_action`
and `agent_target`.

### Validation

Same shape as the prior three phases, checked against `protocol:rho:broadcast`.

### Definition of done

- [ ] Insertion point identified in provider/broker logic
- [ ] `_send_rho_traffic_control` implemented and wired
- [ ] Live mission (or synthetic rate-limit trigger) produces Rho entries,
      zero DLQ writes
- [ ] `IMPLEMENTATION_STATUS.md` updated

---

## Closing Validation — All Six Lanes Live

After PBLA-01 through PBLA-04 are complete, run a single combined check:

```bash
python scripts/demo_missions.py --live
```

Then confirm via protocol-bus-mcp that all six `protocol:{lane}:*` streams
show traffic for that one mission run — not just Alpha and Sigma. This is
the evidence artifact for "all six lanes are live," parallel in form to the
existing S1-01 evidence in `docs/evidence/`. Suggested location:
`docs/evidence/protocol_bus_six_lane_smoke_latest.json`.

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

**Delta verdict vocabulary mismatch.** `DeltaPayload.audit_result` is a
strict `Literal["pass", "fail", "warning"]`, but pod audit verdicts may use
different vocabulary internally. `_map_verdict_to_audit_result()` in
PBLA-01 handles this — confirm the actual verdict strings produced by
`generate_pod_audit_verdict()` before finalizing the mapping, since an
unmapped value silently falling through to `"warning"` could mask real
failures if the mapping is incomplete.

**Omega payload scope discipline.** Resist the temptation to add new
fields to `OmegaPayload` for handoff metadata. The producer code already
documents this as an intentional EDCP-02 deferral — adding fields now
creates a schema that EDCP-02 then has to either keep or break.

**Sequencing relative to EDCP.** This plan does not change control flow —
it only adds telemetry. It is safe to run before, during, or after EDCP-01
through EDCP-05 without coordination risk, but running it first gives EDCP
real traffic on all six lanes to test against from the start.
