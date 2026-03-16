import asyncio
import importlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api-gateway"))

api_gateway_main = importlib.import_module("api_gateway.main")


class _FakeRedis:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)

    async def xread(self, **_kwargs: Any) -> Any:
        if self.responses:
            current = self.responses.pop(0)
            if isinstance(current, Exception):
                raise current
            return current
        raise asyncio.CancelledError


def test_decode_state_stream_event_parses_payload_and_envelope() -> None:
    fields = {
        "event_type": "MISSION_RUNNING",
        "mission_id": "mission-1",
        "state": "RUNNING",
        "created_at": "2026-03-04T00:00:00+00:00",
        "payload": json.dumps(
            {
                "mission_id": "mission-1",
                "event_type": "MISSION_RUNNING",
                "state": "RUNNING",
                "created_at": "2026-03-04T00:00:00+00:00",
            }
        ),
        "envelope": json.dumps({"topic": "fusion.requested", "producer": "orchestrator"}),
    }

    decoded = api_gateway_main._decode_state_stream_event("10-0", fields)
    assert decoded["stream_id"] == "10-0"
    assert decoded["event_type"] == "MISSION_RUNNING"
    assert decoded["mission_id"] == "mission-1"
    assert decoded["state"] == "RUNNING"
    assert decoded["topic"] == "fusion.requested"
    assert decoded["producer"] == "orchestrator"


def test_is_stream_event_allowed_filters_agent_and_mission() -> None:
    mission_event = {"event_type": "MISSION_RUNNING", "mission_id": "mission-1"}
    agent_event = {"event_type": "AGENT_HEARTBEAT", "mission_id": None}

    assert api_gateway_main._is_stream_event_allowed(
        mission_event,
        mission_id="mission-1",
        include_agent_events=True,
    )
    assert not api_gateway_main._is_stream_event_allowed(
        mission_event,
        mission_id="mission-2",
        include_agent_events=True,
    )
    assert not api_gateway_main._is_stream_event_allowed(
        agent_event,
        mission_id=None,
        include_agent_events=False,
    )


def test_state_stream_sse_generator_emits_connected_and_filtered_event() -> None:
    fields = {
        "event_type": "MISSION_COMPLETE",
        "mission_id": "mission-1",
        "state": "COMPLETE",
        "created_at": "2026-03-04T00:00:00+00:00",
        "payload": json.dumps(
            {
                "mission_id": "mission-1",
                "event_type": "MISSION_COMPLETE",
                "state": "COMPLETE",
                "created_at": "2026-03-04T00:00:00+00:00",
            }
        ),
        "envelope": json.dumps({"topic": "mission.state.complete", "producer": "orchestrator"}),
    }
    agent_only_fields = {
        "event_type": "AGENT_HEARTBEAT",
        "agent_id": "AGENT-01-PM",
        "payload": json.dumps({"agent_id": "AGENT-01-PM", "event_type": "AGENT_HEARTBEAT"}),
        "envelope": json.dumps({"topic": "agent.heartbeat", "producer": "orchestrator-runtime"}),
    }
    fake_redis = _FakeRedis(
        responses=[
            [
                (
                    "missions.state",
                    [
                        ("11-0", agent_only_fields),
                        ("12-0", fields),
                    ],
                )
            ],
            asyncio.CancelledError(),
        ]
    )

    async def _collect() -> list[str]:
        blocks: list[str] = []
        generator = api_gateway_main._state_stream_sse_generator(
            fake_redis,
            mission_id="mission-1",
            include_agent_events=False,
            last_event_id=None,
        )
        try:
            async for block in generator:
                blocks.append(block)
                if len(blocks) >= 2:
                    break
        finally:
            await generator.aclose()
        return blocks

    blocks = asyncio.run(_collect())
    assert blocks[0].startswith("event: connected")
    assert "event: state_event" in blocks[1]
    assert '"event_type":"MISSION_COMPLETE"' in blocks[1]
    assert '"event_type":"AGENT_HEARTBEAT"' not in blocks[1]


def test_state_stream_sse_generator_reports_read_failure_event() -> None:
    fake_redis = _FakeRedis(responses=[RuntimeError("redis read failed"), asyncio.CancelledError()])

    async def _collect_one() -> list[str]:
        blocks: list[str] = []
        generator = api_gateway_main._state_stream_sse_generator(
            fake_redis,
            mission_id=None,
            include_agent_events=True,
            last_event_id=None,
        )
        try:
            async for block in generator:
                blocks.append(block)
                if "event: stream_error" in block:
                    break
        finally:
            await generator.aclose()
        return blocks

    blocks = asyncio.run(_collect_one())
    assert any("event: stream_error" in block for block in blocks)
    assert any('"detail":"stream read failure"' in block for block in blocks)
