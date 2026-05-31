"""Tests for protocol-bus-mcp deduplication and backpressure — Phase 3."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "protocol-bus-mcp"))

mcp_main = importlib.import_module("protocol_bus.mcp_server")
app = mcp_main.app


# ---------------------------------------------------------------------------
# Extended FakeRedis — adds set() NX/EX and xlen() for Phase 3 features
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
# Deduplication tests
# ---------------------------------------------------------------------------

class TestMessageDeduplication:
    def test_first_send_accepted(self):
        with TestClient(app) as client:
            app.state.redis = FakeRedisWithDedup()
            app.state.redis_ready = True
            response = client.post(
                "/send",
                headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
                json=_alpha_payload(correlation_id="corr-unique-001"),
            )
        assert response.status_code == 200
        assert response.json().get("deduplicated") is not True

    def test_duplicate_correlation_id_returns_200_deduplicated(self):
        fake = FakeRedisWithDedup()
        with TestClient(app) as client:
            app.state.redis = fake
            app.state.redis_ready = True
            headers = {"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY}

            # First send — accepted
            r1 = client.post(
                "/send",
                headers=headers,
                json=_alpha_payload(correlation_id="corr-dup-001"),
            )
            assert r1.status_code == 200
            assert r1.json().get("deduplicated") is not True

            # Second send with same correlation_id — deduplicated
            r2 = client.post(
                "/send",
                headers=headers,
                json=_alpha_payload(correlation_id="corr-dup-001"),
            )
            assert r2.status_code == 200
            assert r2.json().get("deduplicated") is True

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
        assert r1.json().get("deduplicated") is not True
        assert r2.json().get("deduplicated") is not True
        # Both were written to stream
        stream_entries = fake.streams.get("protocol:alpha:AGENT-12-PODA-MGR", [])
        assert len(stream_entries) == 2

    def test_dedup_degraded_gracefully_when_set_raises(self, monkeypatch):
        """If Redis SET raises an exception, message should still be delivered."""
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
                json=_alpha_payload(correlation_id="corr-degrade"),
            )
        # Should succeed despite dedup failure (best-effort dedup)
        assert response.status_code == 200

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


# ---------------------------------------------------------------------------
# Backpressure tests
# ---------------------------------------------------------------------------

class TestBackpressure:
    def test_accepts_message_below_limit(self, monkeypatch):
        monkeypatch.setattr(mcp_main, "BACKPRESSURE_QUEUE_LIMIT", 100)
        fake = FakeRedisWithDedup()
        # Add 50 entries — below limit
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
        # Pre-populate stream beyond limit
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

    def test_backpressure_degraded_gracefully_when_xlen_raises(self, monkeypatch):
        """If xlen raises, backpressure check is best-effort — message should still go."""
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
                json=_alpha_payload(correlation_id="bp-degrade"),
            )
        assert response.status_code == 200
