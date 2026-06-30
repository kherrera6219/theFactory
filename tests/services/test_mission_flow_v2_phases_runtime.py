"""Tests for mission_flow_v2.phases_runtime PBLA Beta emission (PBLA-03)."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

phases_runtime = importlib.import_module("orchestrator.mission_flow_v2.phases_runtime")
protocol_bus_emissions = importlib.import_module("orchestrator.protocol_bus_emissions")

_send_beta_production_result = phases_runtime._send_beta_production_result
EMISSION_KEY = protocol_bus_emissions.EMISSION_KEY
PBLA_SPECIALIST_RESULT = protocol_bus_emissions.PBLA_SPECIALIST_RESULT


@pytest.mark.asyncio
async def test_send_beta_result_maps_and_stamps_discriminator() -> None:
    send_mock = MagicMock(return_value=True)
    with patch("orchestrator.protocol_bus_producer.send_beta_result", send_mock):
        await _send_beta_production_result(
            settings=object(),
            mission_id="mission-9",
            specialist_agent_id="AGENT-14-PYTHON",
            pod_manager_agent_id="AGENT-12-PODA-MGR",
            logicnode_id="ln-mission-9-fused",
            confidence_score=0.85,
            source_language="python",
            payload={"unified_node_count": 7},
        )

    send_mock.assert_called_once()
    kwargs = send_mock.call_args.kwargs
    assert kwargs["sender"] == "AGENT-14-PYTHON"
    assert kwargs["recipient"] == "AGENT-12-PODA-MGR"  # directed, not broadcast
    assert kwargs["logicnode_id"] == "ln-mission-9-fused"
    assert kwargs["source_language"] == "python"
    assert kwargs["confidence_score"] == pytest.approx(0.85)
    assert kwargs["correlation_id"] == "beta-mission-9-ln-mission-9-fused"
    payload = kwargs["payload"]
    assert payload[EMISSION_KEY] == PBLA_SPECIALIST_RESULT
    assert payload["unified_node_count"] == 7


@pytest.mark.parametrize(
    "raw,expected",
    [(1.5, 1.0), (-0.2, 0.0), (0.42, 0.42), (1.0, 1.0), (0.0, 0.0)],
)
@pytest.mark.asyncio
async def test_send_beta_result_clamps_confidence(raw, expected) -> None:
    send_mock = MagicMock(return_value=True)
    with patch("orchestrator.protocol_bus_producer.send_beta_result", send_mock):
        await _send_beta_production_result(
            settings=object(),
            mission_id="m",
            specialist_agent_id="AGENT-14-PYTHON",
            pod_manager_agent_id="AGENT-12-PODA-MGR",
            logicnode_id="ln-m-fused",
            confidence_score=raw,
            source_language="python",
        )
    assert send_mock.call_args.kwargs["confidence_score"] == pytest.approx(expected)


@pytest.mark.asyncio
async def test_send_beta_result_swallows_producer_failure() -> None:
    send_mock = MagicMock(side_effect=RuntimeError("bus down"))
    with patch("orchestrator.protocol_bus_producer.send_beta_result", send_mock):
        # Must not raise — a bus outage can never block fusion/codegen.
        await _send_beta_production_result(
            settings=object(),
            mission_id="m2",
            specialist_agent_id="AGENT-20-C",
            pod_manager_agent_id="AGENT-18-PODB-MGR",
            logicnode_id="ln-m2-fused",
            confidence_score=0.5,
            source_language="c",
        )
    send_mock.assert_called_once()
