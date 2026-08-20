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


base = importlib.import_module("orchestrator.mission_flow_v2.base")


def test_restate_chain_event_overwrites_a_stale_outcome_record() -> None:
    """A successful retry must correct the record the failed attempt wrote.

    Regression for mission-128c77fd, whose trace permanently advertised
    ``source=fallback, code_length_chars=0`` even though the mission went on to
    deliver 14 KB of real code from the fusion-stage retry.
    """
    metadata = {
        "chain_trace": [
            {"event_type": "MISSION_SPECIALIST_ASSIGNED", "agent_id": "AGENT-15-JAVASCRIPT"},
            {
                "event_type": "GENERATED_OUTPUT_CREATED",
                "agent_id": "AGENT-15-JAVASCRIPT",
                "details": {"source": "fallback", "code_length_chars": 0},
            },
        ]
    }

    restated = base._restate_chain_event(
        metadata,
        event_type="GENERATED_OUTPUT_CREATED",
        agent_id="AGENT-15-JAVASCRIPT",
        details={"source": "llm", "code_length_chars": 14074, "filename": "index.html"},
    )

    assert restated is True
    records = [
        r for r in metadata["chain_trace"] if r["event_type"] == "GENERATED_OUTPUT_CREATED"
    ]
    assert len(records) == 1, "restating must not append a duplicate"
    assert records[0]["details"]["source"] == "llm"
    assert records[0]["details"]["code_length_chars"] == 14074
    assert records[0]["restated"] is True
    assert metadata["last_chain_event_type"] == "GENERATED_OUTPUT_CREATED"


def test_restate_chain_event_reports_missing_records() -> None:
    assert (
        base._restate_chain_event(
            {"chain_trace": []},
            event_type="GENERATED_OUTPUT_CREATED",
            agent_id="AGENT-15-JAVASCRIPT",
            details={"source": "llm"},
        )
        is False
    )
