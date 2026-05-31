"""Tests for protocol-bus-mcp replay detection, deduplication and backpressure.

Issue #188: replay detection is wired into the /send handler (returns 409 on a
duplicate correlation_id), and dedup/backpressure now fail closed (HTTP 503) on
Redis errors instead of silently disabling themselves.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "protocol-bus-mcp"))

mcp_main = importlib.import_module("protocol_bus.mcp_server")
app = mcp_main.app

from shared_runtime import protocol as protocol_guard  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_replay_guard():
    """Replay guard is a process-local singleton — reset between tests so a
    correlation_id used in one test does not trip replay detection in another."""
    protocol_guard.reset_replay_guard()
    yield
    protocol_guard.reset_replay_guard()


# ---------------------------------------------------------------------------
# Extended FakeRedis — adds set() NX/EX and xlen() for dedup/backpressure tests
# ---------------------------------------------------------------------------

class FakeRedisWithDedup:
    """Fake Redis that supports SET NX EX and XLEN for dedup/backpressure tests."""

    def __init__(self) -> None:
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self._kv: dict[str, str] = {}  # for SET NX EX

    async def ping(self) -> bool:
        return True

    async def set(
        self,
        key: str,
        value: str,
        *,
        nx: bool = False,
        ex: int | None = None,
    ) -> bool | None:
        """Mimic Redis SET NX. Returns True on new key, None if key already existed."""
        if nx and key in self._kv:
            return None  # Redis returns None when NX condition fails
        self._kv[key] = value
        return True

    async def xadd(
        self,
        stream: str,
        fields: dict[str, str],
        maxlen: int | None = None,
        approximate: bool = False,
    ) -> str:
        entries = self.streams.setdefault(stream, [])
        entry_id = f"{len(entries) + 1}-0"
        entries.append((entry_id, fields))
        return entry_id

    async def xlen(self, stream: str) -> int:
        return len(self.streams.get(stream, []))

    async def xrevrange(
        self, stream: str, count: int = 50
    ) -> list[tuple[str, dict[str, str]]]:
        entries = self.streams.get(stream, [])
        return list(reversed(entries[-count:]))


def _alpha_payload(correlation_id: str | None = None) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": "v1",
        "protocol": "alpha",
        "sender": "AGENT-02-CEO",
        "recipient": "AGENT-12-PODA-MGR",
        "priority": "high",
        "payload": {
            "schema_version": "v1",
            "priority": "high",
            "target_pod": "podA",
            "directive_type": "mission_assignment",
            "directive": {"mission_id": "m-001"},
        },
    }
    if correlation_id is not None:
        base["correlation_id"] = correlation_id
    return base


# ---------------------------------------------------------------------------
# Replay detection tests (issue #188)
# ---------------------------------------------------------------------------

class TestReplayDetection:
    def test_first_send_accepted(self):
        with TestClient(app) as client:
            app.state.redis = FakeRedisWithDedup()
            app.state.redis_ready = True
            response = client.post(
                "/send",
                headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
                json=_alpha_payload(correlation_id="corr-replay-unique"),
            )
        assert response.status_code == 200

    def test_duplicate_correlation_id_returns_409(self):
        fake = FakeRedisWithDedup()
        with TestClient(app) as client:
            app.state.redis = fake
            app.state.redis_ready = True
            headers = {"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY}

            r1 = client.post(
                "/send", headers=headers, json=_alpha_payload(correlation_id="corr-replay-dup")
            )
            assert r1.status_code == 200

            # Same correlation_id replayed — rejected before publishing
            r2 = client.post(
                "/send", headers=headers, json=_alpha_payload(correlation_id="corr-replay-dup")
            )
        assert r2.status_code == 409
        assert "replay detected" in r2.json().get("detail", "")
        # The replayed message must NOT have been written to the stream a second time.
        stream_entries = fake.streams.get("protocol:alpha:AGENT-12-PODA-MGR", [])
        assert len(stream_entries) == 1

    def test_different_correlation_ids_both_accepted(self):
        fake = FakeRedisWithDedup()
        with TestClient(app) as client:
            app.state.redis = fake
            app.state.redis_ready = True
            headers = {"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY}

            r1 = client.post("/send", headers=headers, json=_alpha_payload(correlation_id="corr-a"))
            r2 = client.post("/send", headers=headers, json=_alpha_payload(correlation_id="corr-b"))

        assert r1.status_code == 200
        assert r2.status_code == 200
        stream_entries = fake.streams.get("protocol:alpha:AGENT-12-PODA-MGR", [])
        assert len(stream_entries) == 2


# ---------------------------------------------------------------------------
# Deduplication tests (Redis SET NX EX) — must fail closed on Redis errors
# ---------------------------------------------------------------------------

class TestMessageDeduplication:
    def test_dedup_key_stored_in_redis(self):
        fake = FakeRedisWithDedup()
        corr = "corr-stored-key"
        with TestClient(app) as client:
            app.state.redis = fake
            app.state.redis_ready = True
            client.post(
                "/send",
                headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
                json=_alpha_payload(correlation_id=corr),
            )
        assert f"mcp:dedup:{corr}" in fake._kv

    def test_cross_process_dedup_returns_200_idempotent(self):
        """A correlation_id unseen by THIS process's replay guard but already
        recorded in Redis (e.g. handled by another instance) is deduplicated:
        the handler returns 200 with deduplicated=True and does not republish."""
        fake = FakeRedisWithDedup()
        corr = "corr-cross-process"
        # Simulate another instance having already recorded this correlation_id.
        fake._kv[f"mcp:dedup:{corr}"] = "1"
        with TestClient(app) as client:
            app.state.redis = fake
            app.state.redis_ready = True
            response = client.post(
                "/send",
                headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
                json=_alpha_payload(correlation_id=corr),
            )
        assert response.status_code == 200
        assert response.json().get("deduplicated") is True
        assert fake.streams.get("protocol:alpha:AGENT-12-PODA-MGR", []) == []

    def test_dedup_redis_failure_raises_503(self):
        """A Redis failure on the dedup guard must fail closed (503), not silently
        proceed without deduplication."""
        fake = FakeRedisWithDedup()

        async def _raise_set(*_args, **_kwargs):
            raise RuntimeError("Redis unavailable")

        fake.set = _raise_set

        with TestClient(app) as client:
            app.state.redis = fake
            app.state.redis_ready = True
            response = client.post(
                "/send",
                headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
                json=_alpha_payload(correlation_id="corr-dedup-fail"),
            )
        assert response.status_code == 503
        assert response.json().get("detail") == "Dedup service unavailable"
        # Nothing should have been published.
        assert fake.streams.get("protocol:alpha:AGENT-12-PODA-MGR", []) == []


# ---------------------------------------------------------------------------
# Backpressure tests — fail closed on Redis errors, check ALL channels
# ---------------------------------------------------------------------------

class TestBackpressure:
    def test_accepts_message_below_limit(self, monkeypatch):
        monkeypatch.setattr(mcp_main, "BACKPRESSURE_QUEUE_LIMIT", 100)
        fake = FakeRedisWithDedup()
        for i in range(50):
            fake.streams.setdefault("protocol:alpha:AGENT-12-PODA-MGR", []).append(
                (f"{i}-0", {"data": "x"})
            )
        with TestClient(app) as client:
            app.state.redis = fake
            app.state.redis_ready = True
            response = client.post(
                "/send",
                headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
                json=_alpha_payload(correlation_id="bp-below"),
            )
        assert response.status_code == 200

    def test_rejects_message_over_limit(self, monkeypatch):
        monkeypatch.setattr(mcp_main, "BACKPRESSURE_QUEUE_LIMIT", 5)
        fake = FakeRedisWithDedup()
        for i in range(10):
            fake.streams.setdefault("protocol:alpha:AGENT-12-PODA-MGR", []).append(
                (f"{i}-0", {"data": "x"})
            )
        with TestClient(app) as client:
            app.state.redis = fake
            app.state.redis_ready = True
            response = client.post(
                "/send",
                headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
                json=_alpha_payload(correlation_id="bp-over"),
            )
        assert response.status_code == 503
        assert "backpressure" in response.json().get("detail", "")
        assert response.headers.get("Retry-After") == "5"

    def test_rejects_when_any_channel_over_limit(self, monkeypatch):
        """Multi-recipient send must check ALL resolved channels: if ANY channel
        is over the limit, the request is rejected with 503."""
        monkeypatch.setattr(mcp_main, "BACKPRESSURE_QUEUE_LIMIT", 5)
        fake = FakeRedisWithDedup()
        # First channel well below limit, second channel over the limit.
        fake.streams["protocol:alpha:AGENT-12-PODA-MGR"] = [
            (f"{i}-0", {"data": "x"}) for i in range(2)
        ]
        fake.streams["protocol:alpha:AGENT-13-PODB-MGR"] = [
            (f"{i}-0", {"data": "x"}) for i in range(10)
        ]
        payload = _alpha_payload(correlation_id="bp-multi-over")
        payload["recipient"] = ["AGENT-12-PODA-MGR", "AGENT-13-PODB-MGR"]
        with TestClient(app) as client:
            app.state.redis = fake
            app.state.redis_ready = True
            response = client.post(
                "/send",
                headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
                json=payload,
            )
        assert response.status_code == 503
        assert "backpressure" in response.json().get("detail", "")

    def test_accepts_when_all_channels_below_limit(self, monkeypatch):
        monkeypatch.setattr(mcp_main, "BACKPRESSURE_QUEUE_LIMIT", 100)
        fake = FakeRedisWithDedup()
        fake.streams["protocol:alpha:AGENT-12-PODA-MGR"] = [
            (f"{i}-0", {"data": "x"}) for i in range(10)
        ]
        fake.streams["protocol:alpha:AGENT-13-PODB-MGR"] = [
            (f"{i}-0", {"data": "x"}) for i in range(20)
        ]
        payload = _alpha_payload(correlation_id="bp-multi-below")
        payload["recipient"] = ["AGENT-12-PODA-MGR", "AGENT-13-PODB-MGR"]
        with TestClient(app) as client:
            app.state.redis = fake
            app.state.redis_ready = True
            response = client.post(
                "/send",
                headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
                json=payload,
            )
        assert response.status_code == 200

    def test_backpressure_redis_failure_raises_503(self, monkeypatch):
        """If the backpressure depth check raises, the request must fail closed
        (503) rather than failing open and allowing a silent flood."""
        monkeypatch.setattr(mcp_main, "BACKPRESSURE_QUEUE_LIMIT", 5)
        fake = FakeRedisWithDedup()

        async def _raise_xlen(*_args, **_kwargs):
            raise RuntimeError("Redis unavailable")

        fake.xlen = _raise_xlen

        with TestClient(app) as client:
            app.state.redis = fake
            app.state.redis_ready = True
            response = client.post(
                "/send",
                headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
                json=_alpha_payload(correlation_id="bp-fail"),
            )
        assert response.status_code == 503
        assert response.json().get("detail") == "Backpressure service unavailable"
        # Nothing should have been published.
        assert fake.streams.get("protocol:alpha:AGENT-12-PODA-MGR", []) == []
