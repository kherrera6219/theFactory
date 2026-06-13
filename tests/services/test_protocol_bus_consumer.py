"""Tests for the orchestrator Protocol Bus consumer and Alpha producer.

Phase 3 — Protocol Bus activation:
  - ``ProtocolBusConsumer`` tails the Redis streams written by protocol-bus-mcp
    and dispatches decoded messages to per-protocol handlers.
  - ``send_alpha_directive`` POSTs a bus-valid AlphaPayload (CEO → Pod Manager).

All Redis and HTTP I/O is faked so these run offline.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

_ORCH = str(Path(__file__).resolve().parents[2] / "services" / "orchestrator")
if _ORCH not in sys.path:
    sys.path.insert(0, _ORCH)


# ---------------------------------------------------------------------------
# Fake async Redis modelling protocol-bus-mcp XADD output.
# ---------------------------------------------------------------------------

class FakeStreamRedis:
    """Minimal async Redis supporting xread over pre-seeded streams.

    Seeded entries are delivered exactly once per channel cursor, after which
    xread blocks (returns empty) so the consumer settles. ``stop_after`` lets a
    test halt the consumer once the expected entries are drained.
    """

    def __init__(self, seeded: dict[str, list[tuple[str, dict[str, str]]]]):
        # seeded: {channel: [(entry_id, fields), ...]}
        self._seeded = seeded
        self.read_calls = 0

    async def ping(self) -> bool:
        return True

    async def xread(self, streams: dict[str, str], count: int = 20, block: int = 0):
        self.read_calls += 1
        result: list[tuple[str, list[tuple[str, dict[str, str]]]]] = []
        for channel, last_id in streams.items():
            pending = self._undelivered(channel, last_id)
            if pending:
                result.append((channel, pending))
        if result:
            return result
        # No more data: emulate a blocking read that times out.
        await asyncio.sleep(0)
        return []

    def _undelivered(self, channel: str, last_id: str):
        entries = self._seeded.get(channel, [])
        if last_id == "$":
            # "$" = only entries after now; on the FIRST poll we still want to
            # deliver seeded entries to simulate "published after start".
            return list(entries)
        out = []
        for entry_id, fields in entries:
            if entry_id > last_id:
                out.append((entry_id, fields))
        return out


class TimeoutThenDataRedis(FakeStreamRedis):
    def __init__(self, seeded: dict[str, list[tuple[str, dict[str, str]]]], timeout_error: Exception):
        super().__init__(seeded)
        self._timeout_error = timeout_error
        self._timed_out = False

    async def xread(self, streams: dict[str, str], count: int = 20, block: int = 0):
        if not self._timed_out:
            self._timed_out = True
            raise self._timeout_error
        return await super().xread(streams, count=count, block=block)


def _envelope_entry(protocol: str, content: dict[str, Any], sender: str = "AGENT-06-IS"):
    envelope = {
        "message_id": "msg-1",
        "schema_version": "v1",
        "protocol": protocol,
        "sender": sender,
        "recipient": "broadcast",
        "correlation_id": "corr-1",
        "priority": "normal",
        "timestamp": "2026-05-31T00:00:00+00:00",
        "payload": {"content": content},
    }
    return (
        "1-0",
        {
            "envelope": json.dumps(envelope),
            "payload": json.dumps({"content": content}),
            "sender": sender,
        },
    )


# ---------------------------------------------------------------------------
# ProtocolBusConsumer
# ---------------------------------------------------------------------------

class TestProtocolBusConsumer:
    def test_dispatches_message_to_handler(self):
        from orchestrator.protocol_bus_consumer import ProtocolBusConsumer

        channel = "protocol:sigma:broadcast"
        entry = _envelope_entry("sigma", {"mission_id": "m-9", "languages": ["python"]})
        redis = FakeStreamRedis({channel: [entry]})

        received: list[dict[str, Any]] = []

        async def handler(message: dict[str, Any]) -> None:
            received.append(message)
            # Stop after the first message so start() returns.
            consumer.stop()

        consumer = ProtocolBusConsumer(
            redis_client=redis,
            agent_id="AGENT-03-BROKER",
            handlers={"sigma": handler},
            block_ms=1,
        )

        async def _run():
            await asyncio.wait_for(consumer.start(), timeout=2.0)

        asyncio.run(_run())

        assert len(received) == 1
        msg = received[0]
        assert msg["channel"] == channel
        assert msg["sender"] == "AGENT-06-IS"
        assert msg["payload"]["content"]["mission_id"] == "m-9"
        assert msg["envelope"]["protocol"] == "sigma"

    def test_only_subscribes_lanes_with_handlers(self):
        from orchestrator.protocol_bus_consumer import ProtocolBusConsumer

        consumer = ProtocolBusConsumer(
            redis_client=FakeStreamRedis({}),
            agent_id="AGENT-03-BROKER",
            handlers={"sigma": MagicMock(), "bogus": MagicMock()},
        )
        # "bogus" is not an allowed protocol and must be dropped.
        assert set(consumer.handlers) == {"sigma"}

    def test_start_noop_without_redis(self):
        from orchestrator.protocol_bus_consumer import ProtocolBusConsumer

        async def handler(message):  # pragma: no cover - never called
            raise AssertionError("handler should not run")

        consumer = ProtocolBusConsumer(
            redis_client=None,
            agent_id="AGENT-03-BROKER",
            handlers={"sigma": handler},
        )
        asyncio.run(consumer.start())
        assert consumer.running is False

    def test_handler_exception_is_swallowed(self):
        from orchestrator.protocol_bus_consumer import ProtocolBusConsumer

        channel = "protocol:sigma:broadcast"
        entry = _envelope_entry("sigma", {"mission_id": "boom"})
        redis = FakeStreamRedis({channel: [entry]})

        calls = {"n": 0}

        async def handler(message: dict[str, Any]) -> None:
            calls["n"] += 1
            consumer.stop()
            raise RuntimeError("handler boom")

        consumer = ProtocolBusConsumer(
            redis_client=redis,
            agent_id="AGENT-03-BROKER",
            handlers={"sigma": handler},
            block_ms=1,
        )

        async def _run():
            await asyncio.wait_for(consumer.start(), timeout=2.0)

        # Must not raise — the lane loop swallows handler errors.
        asyncio.run(_run())
        assert calls["n"] == 1

    def test_invalid_envelope_is_dropped(self):
        from orchestrator.protocol_bus_consumer import ProtocolBusConsumer

        channel = "protocol:sigma:broadcast"
        bad = ("1-0", {"envelope": "{not json", "payload": "{}", "sender": "x"})
        good = _envelope_entry("sigma", {"mission_id": "ok"})
        # Same id so cursor advances; deliver bad first then stop on good via a
        # separate channel to keep ids monotonic.
        redis = FakeStreamRedis(
            {
                channel: [("1-0", bad[1]), ("2-0", good[1])],
            }
        )

        received: list[dict[str, Any]] = []

        async def handler(message: dict[str, Any]) -> None:
            received.append(message)
            consumer.stop()

        consumer = ProtocolBusConsumer(
            redis_client=redis,
            agent_id="AGENT-03-BROKER",
            handlers={"sigma": handler},
            block_ms=1,
        )

        asyncio.run(asyncio.wait_for(consumer.start(), timeout=2.0))
        # Only the good entry reaches the handler; the malformed one is dropped.
        assert len(received) == 1
        assert received[0]["payload"]["content"]["mission_id"] == "ok"

    def test_stream_timeout_is_idle_poll(self):
        from orchestrator.protocol_bus_consumer import ProtocolBusConsumer, RedisTimeoutError

        channel = "protocol:sigma:broadcast"
        entry = _envelope_entry("sigma", {"mission_id": "after-timeout"})
        redis = TimeoutThenDataRedis(
            {channel: [entry]},
            RedisTimeoutError("Timeout reading from redis:6380"),
        )

        received: list[dict[str, Any]] = []

        async def handler(message: dict[str, Any]) -> None:
            received.append(message)
            consumer.stop()

        consumer = ProtocolBusConsumer(
            redis_client=redis,
            agent_id="AGENT-03-BROKER",
            handlers={"sigma": handler},
            block_ms=1,
        )

        asyncio.run(asyncio.wait_for(consumer.start(), timeout=2.0))

        assert redis.read_calls == 1
        assert len(received) == 1
        assert received[0]["payload"]["content"]["mission_id"] == "after-timeout"


# ---------------------------------------------------------------------------
# Alpha producer
# ---------------------------------------------------------------------------

def _producer_settings() -> Any:
    s = MagicMock()
    s.protocol_bus_url = "http://protocol-bus-mcp:8090"
    s.protocol_bus_api_key = "alpha-secret"
    return s


class TestAlphaProducer:
    def test_send_alpha_directive_posts_valid_payload(self):
        from orchestrator.protocol_bus_producer import send_alpha_directive

        captured: list[Any] = []
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = lambda s: resp
        resp.__exit__ = MagicMock(return_value=False)

        def capture(req, timeout=None):
            captured.append(req)
            return resp

        with patch("orchestrator.protocol_bus_producer.urlopen", side_effect=capture):
            ok = send_alpha_directive(
                settings=_producer_settings(),
                sender="AGENT-02-CEO",
                recipient="AGENT-12-PODA-MGR",
                target_pod="podA",
                directive_type="pod_manager_delegation",
                directive={"mission_id": "m-1"},
            )

        assert ok is True
        req = captured[0]
        assert req.full_url.endswith("/send")
        assert req.get_header("X-agent-id") == "AGENT-02-CEO"
        assert req.get_header("X-api-key") == "alpha-secret"
        body = json.loads(req.data)
        assert body["protocol"] == "alpha"
        assert body["sender"] == "AGENT-02-CEO"
        assert body["recipient"] == "AGENT-12-PODA-MGR"
        alpha = body["payload"]
        assert set(alpha) == {
            "schema_version",
            "priority",
            "target_pod",
            "directive_type",
            "directive",
            "global_style_directives",
        }
        assert alpha["target_pod"] == "podA"
        assert alpha["directive_type"] == "pod_manager_delegation"

    def test_alpha_payload_validates_against_bus_model(self):
        bus_path = str(
            Path(__file__).resolve().parents[2] / "services" / "protocol-bus-mcp"
        )
        if bus_path not in sys.path:
            sys.path.insert(0, bus_path)
        from orchestrator.protocol_bus_producer import send_alpha_directive
        from protocol_bus.mcp_server import (  # type: ignore
            SendMessageRequest,
            _validate_protocol_payload,
        )

        captured: list[Any] = []
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = lambda s: resp
        resp.__exit__ = MagicMock(return_value=False)

        def capture(req, timeout=None):
            captured.append(req)
            return resp

        with patch("orchestrator.protocol_bus_producer.urlopen", side_effect=capture):
            send_alpha_directive(
                settings=_producer_settings(),
                sender="AGENT-02-CEO",
                recipient="AGENT-18-PODB-MGR",
                target_pod="podB",
                directive_type="pod_manager_delegation",
                directive={"mission_id": "m-2", "specialist_agent_id": "AGENT-36-GO"},
            )

        body = json.loads(captured[0].data)
        validated = SendMessageRequest.model_validate(body)
        _validate_protocol_payload(validated.protocol, validated.payload)

    def test_send_returns_false_without_url(self):
        from orchestrator.protocol_bus_producer import send_alpha_directive

        s = MagicMock()
        s.protocol_bus_url = ""
        s.mcp_url = ""
        s.protocol_bus_api_key = ""
        ok = send_alpha_directive(
            settings=s,
            sender="AGENT-02-CEO",
            recipient="AGENT-12-PODA-MGR",
            target_pod="podA",
            directive_type="pod_manager_delegation",
            directive={},
        )
        assert ok is False

    def test_send_returns_false_on_network_error(self):
        from orchestrator.protocol_bus_producer import send_alpha_directive

        with patch(
            "orchestrator.protocol_bus_producer.urlopen",
            side_effect=OSError("connection refused"),
        ):
            ok = send_alpha_directive(
                settings=_producer_settings(),
                sender="AGENT-02-CEO",
                recipient="AGENT-12-PODA-MGR",
                target_pod="podA",
                directive_type="pod_manager_delegation",
                directive={},
            )
        assert ok is False
