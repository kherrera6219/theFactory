"""Contract test for the shared PBLA emission discriminators.

These constants are a cross-module contract: PBLA producers
(``orchestrator/mission_flow_v2`` + ``llm_delegation``) stamp them, and EDCP
consumers (``orchestrator/main.py``) filter on them. Pinning the values here
makes any rename a deliberate, reviewed change rather than a silent drift that
would let PBLA shadow telemetry be mistaken for a load-bearing command/reply.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ORCH = str(Path(__file__).resolve().parents[2] / "services" / "orchestrator")
if _ORCH not in sys.path:
    sys.path.insert(0, _ORCH)

from orchestrator import protocol_bus_emissions as pbe  # noqa: E402


def test_discriminator_values_are_pinned() -> None:
    # If you change a value here, you must change it on the EDCP consumer side
    # too — that is the whole point of this test.
    assert pbe.EMISSION_KEY == "emission"
    assert pbe.OMEGA_MESSAGE_TYPE_KEY == "message_type"
    assert pbe.PBLA_POD_AUDIT_TELEMETRY == "pbla_pod_audit_telemetry"
    assert pbe.PBLA_DELIVERY_HANDOFF == "pbla_delivery_handoff"
    assert pbe.PBLA_SPECIALIST_RESULT == "pbla_specialist_result"
    assert pbe.PBLA_TRAFFIC_TELEMETRY == "pbla_traffic_telemetry"


def test_pbla_emissions_contains_all_four() -> None:
    assert pbe.PBLA_EMISSIONS == frozenset(
        {
            pbe.PBLA_POD_AUDIT_TELEMETRY,
            pbe.PBLA_DELIVERY_HANDOFF,
            pbe.PBLA_SPECIALIST_RESULT,
            pbe.PBLA_TRAFFIC_TELEMETRY,
        }
    )
    assert len(pbe.PBLA_EMISSIONS) == 4


def test_is_pbla_emission_filters_correctly() -> None:
    assert pbe.is_pbla_emission(pbe.PBLA_POD_AUDIT_TELEMETRY) is True
    assert pbe.is_pbla_emission(pbe.PBLA_DELIVERY_HANDOFF) is True
    # A genuine EDCP message type / unrelated value is not a PBLA emission.
    assert pbe.is_pbla_emission("mission_charter_ready") is False
    assert pbe.is_pbla_emission(None) is False
    assert pbe.is_pbla_emission("") is False
