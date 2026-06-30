"""Tests for llm_delegation.providers PBLA Rho emission (PBLA-04)."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

providers = importlib.import_module("orchestrator.llm_delegation.providers")
protocol_bus_emissions = importlib.import_module("orchestrator.protocol_bus_emissions")

_send_rho_traffic_control = providers._send_rho_traffic_control
EMISSION_KEY = protocol_bus_emissions.EMISSION_KEY
PBLA_TRAFFIC_TELEMETRY = protocol_bus_emissions.PBLA_TRAFFIC_TELEMETRY


@pytest.mark.asyncio
async def test_send_rho_stamps_discriminator_and_resolves_settings() -> None:
    sentinel_settings = object()
    send_mock = MagicMock(return_value=True)
    with patch("orchestrator.protocol_bus_producer.send_rho_control", send_mock), patch(
        "orchestrator.settings.load_settings", return_value=sentinel_settings
    ):
        await _send_rho_traffic_control(
            rate_limit_action="retry_backoff",
            agent_target="AGENT-14-PYTHON",
            metadata={"call_context": "specialist codegen", "status_code": 429},
        )

    send_mock.assert_called_once()
    kwargs = send_mock.call_args.kwargs
    # Settings resolved via load_settings(), not threaded from the transport layer.
    assert kwargs["settings"] is sentinel_settings
    assert kwargs["sender"] == "AGENT-03-BROKER"  # bus-valid Rho owner
    assert kwargs["recipient"] == "broadcast"
    assert kwargs["token_budget"] == 0
    assert kwargs["rate_limit_action"] == "retry_backoff"
    assert kwargs["agent_target"] == "AGENT-14-PYTHON"
    metadata = kwargs["metadata"]
    assert metadata[EMISSION_KEY] == PBLA_TRAFFIC_TELEMETRY
    assert metadata["call_context"] == "specialist codegen"
    assert metadata["status_code"] == 429
    # No deterministic correlation_id is passed — the producer mints a unique one
    # so distinct rate-limit events are each recorded, not deduped.
    assert "correlation_id" not in kwargs or kwargs["correlation_id"] is None


@pytest.mark.asyncio
async def test_send_rho_swallows_producer_failure() -> None:
    send_mock = MagicMock(side_effect=RuntimeError("bus down"))
    with patch("orchestrator.protocol_bus_producer.send_rho_control", send_mock), patch(
        "orchestrator.settings.load_settings", return_value=object()
    ):
        # Must not raise — Rho telemetry can never disrupt the LLM retry path.
        await _send_rho_traffic_control(
            rate_limit_action="retry_backoff",
            agent_target="unknown",
        )
    send_mock.assert_called_once()


@pytest.mark.asyncio
async def test_send_rho_swallows_settings_failure() -> None:
    send_mock = MagicMock(return_value=True)
    with patch("orchestrator.protocol_bus_producer.send_rho_control", send_mock), patch(
        "orchestrator.settings.load_settings", side_effect=RuntimeError("no env")
    ):
        # Even a settings-resolution failure must be swallowed.
        await _send_rho_traffic_control(
            rate_limit_action="retry_backoff",
            agent_target="unknown",
        )
    send_mock.assert_not_called()
