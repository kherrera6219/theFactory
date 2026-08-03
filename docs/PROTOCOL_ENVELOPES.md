# Protocol Envelopes

Document version: 2026.08.01
Last updated: 2026-08-01
Status: Canonical
Audience: Maintainers, AI coding agents, and anyone building a bus consumer

theFactory runs **two envelope transports**. They are not variants of one design —
they carry different fields, use different priority vocabularies, and correlate
differently. This document states both contracts explicitly, because the
divergence was previously undocumented and is a live hazard for anyone writing a
consumer (audit §4.8, closed by UPG-22).

**Read this before building any Protocol Bus consumer**, including the Phase 6
EDCP Delta consumer.

---

## 1. The two transports at a glance

| | **Event envelope** | **Bus message envelope** |
|---|---|---|
| Schema | `schemas/event.envelope.schema.json` | `MessageEnvelope` in `services/protocol-bus-mcp/protocol_bus/mcp_server.py` |
| Written by | `EnvelopeValidator.build_state_envelope` / `parse_intake_envelope` (`orchestrator/protocol.py`), `phases_intake.py` | `POST /send` on protocol-bus-mcp, called via `orchestrator/protocol_bus_producer.py` |
| Validated by | `shared_runtime.protocol.validate_envelope` — used by orchestrator, api-gateway, pod-worker, audit-worker, agent-runtime | Pydantic models, `extra="forbid"`, `strict=True` |
| Carries | Mission **state transitions** and intake | The **six protocol lanes** (alpha, beta, delta, sigma, omega, rho) |
| Transport | Redis streams, topic from `protocol/topics.yaml` | Redis streams, channel resolved per protocol/recipient |
| Priority | `NORMAL` \| `HIGH` (canonical), plus the bus vocabulary accepted additively | `low` \| `normal` \| `high` \| `critical` |
| Delivery | Validated on read; a failure raises `ProtocolValidationError` | Fire-and-forget from the producer's side |

Neither matches design Doc 07 §2, whose envelope (`ttl`, `metadata.mission_id`,
`metadata.retry_count`, `metadata.trace_id`) was **Superseded** —
see [ADR_DESIGN_RECONCILIATION_2026-08-01.md](ADR_DESIGN_RECONCILIATION_2026-08-01.md) row 5.

---

## 2. Event envelope

Required fields, all of them (`additionalProperties: false`):

| Field | Notes |
|---|---|
| `event_id` | `evt-<uuid4>` |
| `topic` | Must be a member of `protocol/topics.yaml`. Enforced outside the schema |
| `timestamp` | RFC 3339, **timezone required** — enforced explicitly, not only by `format` |
| `producer` | `settings.producer_name` |
| `correlation_id` | **The bare `mission_id`.** See §4 |
| `payload_ref` | Must match `^registry://` |
| `schema` | e.g. `missions.state.v1`, `missions.intake.v1`, `missions.partition.v1` |
| `priority` | See §3 |

The envelope carries **no payload** — only a `payload_ref` pointing at where the
data lives. This is deliberate and should not be changed to inline payloads.

## 3. Priority — the reconciled vocabulary (UPG-22)

The two transports historically disagreed, and the event schema rejected the
bus's vocabulary outright. That was **a live failure mode, not a cosmetic
mismatch**: `DEFAULT_EVENT_PRIORITY` is operator-settable and was written through
unvalidated, so setting it to `normal` — the natural thing to type, since the bus
`/send` API uses lowercase — made **every mission state envelope fail
validation**.

The fix is additive in both directions:

- `schemas/event.envelope.schema.json` now accepts **all six** values, so no
  previously-valid envelope became invalid and no in-flight event is rejected.
- Writers normalise through `shared_runtime.protocol.to_event_priority`, so what
  is written stays in the canonical `NORMAL`/`HIGH` vocabulary.
- An unrecognised value raises `ProtocolValidationError` at the write site rather
  than silently downgrading priority.

### Mapping

| Bus value | Event value | | Event value | Bus value |
|---|---|---|---|---|
| `low` | `NORMAL` | | `NORMAL` | `normal` |
| `normal` | `NORMAL` | | `HIGH` | `high` |
| `high` | `HIGH` | | | |
| `critical` | `HIGH` | | | |

`low` and `critical` have **no event-envelope equivalent** and survive only on the
bus transport. Round-tripping `critical` through the event vocabulary yields
`high`, not `critical` — the mapping is lossy in that direction by design, because
the event transport has never distinguished more than two levels.

### Helpers

```python
from shared_runtime.protocol import (
    EVENT_PRIORITIES,      # ("NORMAL", "HIGH")
    BUS_PRIORITIES,        # ("low", "normal", "high", "critical")
    to_event_priority,     # any vocabulary -> NORMAL | HIGH
    to_bus_priority,       # any vocabulary -> low | normal | high | critical
)
```

Both are idempotent on already-canonical values, which is what keeps existing
configurations byte-identical.

**Nothing routes on priority today.** It is recorded, never dispatched on. Any
future change that makes priority load-bearing must first decide which vocabulary
is authoritative — this document reconciles representation, not semantics.

---

## 4. The correlation contract — read this carefully

**The two transports do not share a correlation value, and cannot be joined by
equality.**

| Transport | `correlation_id` | Example |
|---|---|---|
| Event envelope | The **bare** `mission_id` | `mission-ac933664-bda8-4acf-b265-10171c2ccdf6` |
| Bus — Alpha | `alpha-{mission_id}-{pod_manager_agent_id}` | `alpha-mission-ac93…-AGENT-12-PODA-MGR` |
| Bus — Delta | `delta-{mission_id}-{pod_name}` | `delta-mission-ac93…-Pod A` |
| Bus — Beta | `beta-{mission_id}-{logicnode_id}` | `beta-mission-ac93…-node-17` |
| Bus — Omega | `omega-{mission_id}` | `omega-mission-ac93…` |
| Bus — default | `{protocol}-{uuid4}` when no `correlation_id` is passed | `sigma-3f9a…` |

### Why the bus value is composite — do not "simplify" it

On the bus, `correlation_id` is **not only a correlation key**. It is also:

1. the **replay-rejection key** (`mcp_server.py:624` → `protocol_guard.check_replay`), and
2. the **deduplication key** (`mcp_server.py:650`, `mcp:dedup:{correlation_id}`).

If a bus producer sent the bare `mission_id`, the *second* Alpha emission for that
mission would be seen as a replay of the first and **silently dropped** within the
TTL window. The qualifier suffix is what makes each emission distinct. Changing
these to a bare `mission_id` would introduce message loss, not tidier correlation.

### How to actually correlate

To find bus traffic for a mission, match on the **embedded** `mission_id`
(substring or prefix parse), not equality:

```python
# Correct
bus_events = [e for e in events if mission_id in e["correlation_id"]]

# Wrong — matches nothing on the bus transport
bus_events = [e for e in events if e["correlation_id"] == mission_id]
```

> **Note for the Phase 6 EDCP Delta consumer.** A consumer that looks up a mission
> by `correlation_id == mission_id` will find nothing and appear to work (no
> matches, no error). Parse the `delta-{mission_id}-{pod_name}` form, or pass an
> explicit mission reference in the payload.

Design Doc 07 §2 put `mission_id` in `metadata.mission_id` — a dedicated field
distinct from the correlation/idempotency key. That was the better design; it was
not built, and this document records the built behaviour rather than the intended
one.

---

## 5. Invariants — do not weaken

- `additionalProperties: false` stays on the event envelope.
- Timestamps require a timezone; the explicit `parse_date_time` check stays,
  because `jsonschema`'s `date-time` format assertion only fully applies when the
  optional `rfc3339-validator` package is installed.
- `payload_ref` keeps its `^registry://` pattern. The envelope carries a
  reference, never inline payload data.
- Priority changes must remain additive. Narrowing the enum would reject in-flight
  events, since `additionalProperties: false` leaves no escape hatch.
- The bus's per-protocol payload models keep `extra="forbid"` and `strict=True`.

## 6. Related

- [ADR_DESIGN_RECONCILIATION_2026-08-01.md](ADR_DESIGN_RECONCILIATION_2026-08-01.md) — row 5, why the Doc 07 envelope is Superseded
- [UPGRADE_RECONCILIATION_PLAN_2026-08-01.md](UPGRADE_RECONCILIATION_PLAN_2026-08-01.md) — UPG-22
- [PROTOCOL_BUS_PROGRAM_ROADMAP.md](PROTOCOL_BUS_PROGRAM_ROADMAP.md) — the four-stage bus programme
- [EDCP_PHASE_PLAN.md](EDCP_PHASE_PLAN.md) — consumers and control-flow inversion
- Contract tests: `tests/services/test_envelope_schema_contract.py`,
  `tests/services/test_envelope_priority_normalisation_unit.py`
