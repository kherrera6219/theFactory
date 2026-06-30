"""Tests for mission_flow_v2.phases_build PBLA Delta emission (PBLA-01)."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

phases_build = importlib.import_module("orchestrator.mission_flow_v2.phases_build")
protocol_bus_emissions = importlib.import_module("orchestrator.protocol_bus_emissions")

_map_verdict_to_audit_result = phases_build._map_verdict_to_audit_result
_send_delta_audit_verdict = phases_build._send_delta_audit_verdict
EMISSION_KEY = protocol_bus_emissions.EMISSION_KEY
PBLA_POD_AUDIT_TELEMETRY = protocol_bus_emissions.PBLA_POD_AUDIT_TELEMETRY


@pytest.mark.parametrize(
    "verdict,expected",
    [
        ("PASS", "pass"),
        ("FAIL", "fail"),
        ("WARN", "warning"),
        ("passed", "pass"),
        ("approved", "pass"),
        ("rejected", "fail"),
        ("", "warning"),
        (None, "warning"),
        ("anything-else", "warning"),
    ],
)
def test_map_verdict_to_audit_result(verdict, expected) -> None:
    assert _map_verdict_to_audit_result(verdict) == expected


@pytest.mark.asyncio
async def test_send_delta_audit_verdict_maps_and_stamps_discriminator() -> None:
    send_mock = MagicMock(return_value=True)
    pod_audit = {
        "agent_id": "AGENT-13-PODA-AUDIT",
        "verdict": "FAIL",
        "quality_score": 0.42,
        "source": "llm",
    }
    with patch("orchestrator.protocol_bus_producer.send_delta_audit", send_mock):
        await _send_delta_audit_verdict(
            settings=object(),
            mission_id="mission-abc",
            pod_name="podA",
            pod_manager_agent_id="AGENT-12-PODA-MGR",
            pod_audit=pod_audit,
        )

    send_mock.assert_called_once()
    kwargs = send_mock.call_args.kwargs
    assert kwargs["sender"] == "AGENT-13-PODA-AUDIT"
    assert kwargs["recipient"] == "broadcast"
    assert kwargs["audit_result"] == "fail"
    assert kwargs["verification_method"] == "llm"
    assert kwargs["tolerance_score"] == pytest.approx(0.42)
    assert kwargs["correlation_id"] == "delta-mission-abc-podA"
    findings = kwargs["findings"]
    assert findings[EMISSION_KEY] == PBLA_POD_AUDIT_TELEMETRY
    assert findings["pod"] == "podA"
    assert findings["mission_id"] == "mission-abc"


@pytest.mark.asyncio
async def test_send_delta_audit_verdict_falls_back_to_pod_manager_sender() -> None:
    send_mock = MagicMock(return_value=True)
    pod_audit = {"verdict": "PASS", "quality_score": None}  # no agent_id; None score
    with patch("orchestrator.protocol_bus_producer.send_delta_audit", send_mock):
        await _send_delta_audit_verdict(
            settings=object(),
            mission_id="m1",
            pod_name="podB",
            pod_manager_agent_id="AGENT-18-PODB-MGR",
            pod_audit=pod_audit,
        )

    kwargs = send_mock.call_args.kwargs
    assert kwargs["sender"] == "AGENT-18-PODB-MGR"
    assert kwargs["audit_result"] == "pass"
    # None quality_score must coerce to a valid [0,1] float, not crash.
    assert kwargs["tolerance_score"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_send_delta_audit_verdict_swallows_producer_failure() -> None:
    send_mock = MagicMock(side_effect=RuntimeError("bus down"))
    with patch("orchestrator.protocol_bus_producer.send_delta_audit", send_mock):
        # Must not raise — a bus outage can never block mission progression.
        await _send_delta_audit_verdict(
            settings=object(),
            mission_id="m2",
            pod_name="podC",
            pod_manager_agent_id="AGENT-24-PODC-MGR",
            pod_audit={"verdict": "WARN", "quality_score": 0.9},
        )
    send_mock.assert_called_once()
