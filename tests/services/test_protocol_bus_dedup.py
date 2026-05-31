"""Tests for protocol-bus-mcp replay detection, deduplication and backpressure.

Issue #188: replay detection is wired into the /send handler (returns 409 on a
duplicate correlation_id), and dedup/backpressure now fail closed (HTTP 503) on
Redis errors instead of silently disabling themselves.
"""
from __future__ import annotations

import asyncio
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

# ---------------------------------------------------------------------------
# Extended FakeRedis — adds set() NX/EX and xlen() for dedup/backpressure tests.
# A single FakeRedisWithDedup instance models the shared distributed Redis: both
# the replay guard (replay: keys) and the dedup guard (mcp:dedup: keys) read and
# write the same key space, so replay detection holds across instances.
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

    async def scan(
        self,
        cursor: int = 0,
        match: str | None = None,
        count: int = 500,
    ) -> tuple[int, list[str]]:
        _ = count
        import fnmatch

        keys = list(self._kv)
        if match is not None:
            keys = [k for k in keys if fnmatch.fnmatch(k, match)]
        return 0, keys

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self._kv:
                del self._kv[key]
                removed += 1
        return removed

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

    def test_cross_process_replay_detected_via_shared_redis(self):
        """The replay guard is backed by shared Redis, not a per-process dict, so
        a correlation_id first seen by one Protocol Bus instance is detected as a
        replay by a *different* instance that shares the same Redis."""
        shared_redis = FakeRedisWithDedup()
        headers = {"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY}
        corr = "corr-cross-instance-replay"

        # Instance A handles the original message.
        with TestClient(app) as client_a:
            app.state.redis = shared_redis
            app.state.redis_ready = True
            r1 = client_a.post(
                "/send", headers=headers, json=_alpha_payload(correlation_id=corr)
            )
        assert r1.status_code == 200
        assert f"{protocol_guard.REPLAY_KEY_PREFIX}{corr}" in shared_redis._kv

        # Instance B (a fresh app lifecycle, but the SAME Redis) sees the replay.
        with TestClient(app) as client_b:
            app.state.redis = shared_redis
            app.state.redis_ready = True
            r2 = client_b.post(
                "/send", headers=headers, json=_alpha_payload(correlation_id=corr)
            )
        assert r2.status_code == 409
        assert "replay detected" in r2.json().get("detail", "")

    def test_replay_redis_failure_raises_503(self):
        """A Redis failure during replay detection must fail closed (503), not
        silently skip the guard and let a replay through."""
        fake = FakeRedisWithDedup()

        async def _raise_on_replay_set(key, value, **kwargs):
            if key.startswith(protocol_guard.REPLAY_KEY_PREFIX):
                raise RuntimeError("Redis unavailable")
            return None

        fake.set = _raise_on_replay_set

        with TestClient(app) as client:
            app.state.redis = fake
            app.state.redis_ready = True
            response = client.post(
                "/send",
                headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
                json=_alpha_payload(correlation_id="corr-replay-fail"),
            )
        assert response.status_code == 503
        assert response.json().get("detail") == "Replay detection service unavailable"
        assert fake.streams.get("protocol:alpha:AGENT-12-PODA-MGR", []) == []


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
        real_set = fake.set

        async def _raise_on_dedup_set(key, value, **kwargs):
            # Let the replay guard's SET succeed; fail only the dedup SET so this
            # test exercises the dedup failure path specifically.
            if key.startswith("mcp:dedup:"):
                raise RuntimeError("Redis unavailable")
            return await real_set(key, value, **kwargs)

        fake.set = _raise_on_dedup_set

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


# ---------------------------------------------------------------------------
# Unit tests for the Redis-backed replay guard in shared_runtime.protocol
# ---------------------------------------------------------------------------

class TestRedisReplayGuard:
    def test_first_call_records_key_second_call_raises(self):
        redis = FakeRedisWithDedup()

        async def _run():
            await protocol_guard.check_replay("corr-unit-1", redis, ttl_seconds=300)
            assert f"{protocol_guard.REPLAY_KEY_PREFIX}corr-unit-1" in redis._kv
            with pytest.raises(protocol_guard.ReplayDetectedError):
                await protocol_guard.check_replay("corr-unit-1", redis, ttl_seconds=300)

        asyncio.run(_run())

    def test_shared_redis_detects_cross_client_replay(self):
        """Two independent clients sharing one Redis: the second sees the replay."""
        shared = FakeRedisWithDedup()

        async def _run():
            await protocol_guard.check_replay("corr-shared", shared, ttl_seconds=300)
            with pytest.raises(protocol_guard.ReplayDetectedError):
                await protocol_guard.check_replay("corr-shared", shared, ttl_seconds=300)

        asyncio.run(_run())

    def test_reset_replay_guard_clears_only_replay_keys(self):
        redis = FakeRedisWithDedup()

        async def _run():
            await protocol_guard.check_replay("corr-reset", redis, ttl_seconds=300)
            redis._kv["mcp:dedup:keep-me"] = "1"
            await protocol_guard.reset_replay_guard(redis)
            assert f"{protocol_guard.REPLAY_KEY_PREFIX}corr-reset" not in redis._kv
            # Non-replay keys are untouched.
            assert "mcp:dedup:keep-me" in redis._kv
            # After reset, the same correlation_id is accepted as new again.
            await protocol_guard.check_replay("corr-reset", redis, ttl_seconds=300)

        asyncio.run(_run())
