"""Shared emission discriminators for Protocol Bus telemetry (PBLA).

These constants are the contract that lets a load-bearing EDCP consumer filter
PBLA's shadow telemetry out of a lane it shares. The Protocol Bus consumer tails
both the directed channel (``protocol:{lane}:{agent_id}``) and the broadcast
channel (``protocol:{lane}:broadcast``) for a lane and feeds both to the same
handler, so any future EDCP consumer also receives PBLA's broadcast telemetry —
it cannot avoid it by listening on a different channel.

Producers (PBLA-01..04) stamp the relevant discriminator into the free-form dict
field of their payload; consumers (EDCP-02/04) match on it to ignore ``pbla_*``
emissions. Both sides import these names from here so the strings cannot drift.
Do not inline these literals anywhere else.
"""
from __future__ import annotations

# Dict key under which the discriminator is stamped, per lane payload field.
EMISSION_KEY = "emission"  # delta.findings / beta.payload / rho.metadata
OMEGA_MESSAGE_TYPE_KEY = "message_type"  # omega.feature_contract

# Discriminator values — one per PBLA emission.
PBLA_POD_AUDIT_TELEMETRY = "pbla_pod_audit_telemetry"  # PBLA-01 Delta
PBLA_DELIVERY_HANDOFF = "pbla_delivery_handoff"  # PBLA-02 Omega
PBLA_SPECIALIST_RESULT = "pbla_specialist_result"  # PBLA-03 Beta
PBLA_TRAFFIC_TELEMETRY = "pbla_traffic_telemetry"  # PBLA-04 Rho

# Convenience set for consumer-side filtering ("is this a PBLA shadow emission?").
PBLA_EMISSIONS = frozenset(
    {
        PBLA_POD_AUDIT_TELEMETRY,
        PBLA_DELIVERY_HANDOFF,
        PBLA_SPECIALIST_RESULT,
        PBLA_TRAFFIC_TELEMETRY,
    }
)


def is_pbla_emission(value: str | None) -> bool:
    """Return True if *value* is one of the PBLA telemetry discriminators.

    Consumer-side helper: an EDCP handler reads its discriminator field (e.g.
    ``findings.get(EMISSION_KEY)`` for Delta, or
    ``feature_contract.get(OMEGA_MESSAGE_TYPE_KEY)`` for Omega) and passes it
    here to decide whether to ignore the message as PBLA shadow telemetry.
    """
    return value in PBLA_EMISSIONS
