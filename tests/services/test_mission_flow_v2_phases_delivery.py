"""Tests for mission_flow_v2.phases_delivery PBLA Omega emission (PBLA-02)."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

phases_delivery = importlib.import_module("orchestrator.mission_flow_v2.phases_delivery")
protocol_bus_emissions = importlib.import_module("orchestrator.protocol_bus_emissions")

_send_omega_handoff = phases_delivery._send_omega_handoff
OMEGA_MESSAGE_TYPE_KEY = protocol_bus_emissions.OMEGA_MESSAGE_TYPE_KEY
PBLA_DELIVERY_HANDOFF = protocol_bus_emissions.PBLA_DELIVERY_HANDOFF


@pytest.mark.asyncio
async def test_send_omega_handoff_stamps_discriminator_and_intent() -> None:
    send_mock = MagicMock(return_value=True)
    with patch("orchestrator.protocol_bus_producer.send_omega_message", send_mock):
        await _send_omega_handoff(
            settings=object(),
            mission_id="mission-xyz",
            pm_agent_id="AGENT-01-PM",
            delivery_summary={"delivery_title": "Neon Pong delivered"},
            feature_contract={"format": "single-html"},
        )

    send_mock.assert_called_once()
    kwargs = send_mock.call_args.kwargs
    assert kwargs["sender"] == "AGENT-01-PM"
    assert kwargs["recipient"] == "broadcast"
    assert kwargs["user_intent"] == "Neon Pong delivered"
    assert kwargs["correlation_id"] == "omega-mission-xyz"
    fc = kwargs["feature_contract"]
    assert fc[OMEGA_MESSAGE_TYPE_KEY] == PBLA_DELIVERY_HANDOFF
    # Existing feature_contract content is preserved alongside the discriminator.
    assert fc["format"] == "single-html"


@pytest.mark.asyncio
async def test_send_omega_handoff_user_intent_fallback_chain() -> None:
    send_mock = MagicMock(return_value=True)
    # No delivery_title -> summary; then nothing -> "mission handoff".
    with patch("orchestrator.protocol_bus_producer.send_omega_message", send_mock):
        await _send_omega_handoff(
            settings=object(),
            mission_id="m1",
            pm_agent_id="AGENT-01-PM",
            delivery_summary={"summary": "fallback summary"},
            feature_contract=None,
        )
        assert send_mock.call_args.kwargs["user_intent"] == "fallback summary"

        send_mock.reset_mock()
        await _send_omega_handoff(
            settings=object(),
            mission_id="m1",
            pm_agent_id="AGENT-01-PM",
            delivery_summary={},
            feature_contract=None,
        )
        kwargs = send_mock.call_args.kwargs
        assert kwargs["user_intent"] == "mission handoff"
        # A None feature_contract still yields just the discriminator.
        assert kwargs["feature_contract"] == {OMEGA_MESSAGE_TYPE_KEY: PBLA_DELIVERY_HANDOFF}


@pytest.mark.asyncio
async def test_send_omega_handoff_swallows_producer_failure() -> None:
    send_mock = MagicMock(side_effect=RuntimeError("bus down"))
    with patch("orchestrator.protocol_bus_producer.send_omega_message", send_mock):
        # Must not raise — a bus outage can never block delivery.
        await _send_omega_handoff(
            settings=object(),
            mission_id="m2",
            pm_agent_id="AGENT-01-PM",
            delivery_summary={"delivery_title": "x"},
            feature_contract={},
        )
    send_mock.assert_called_once()
