import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "semantic-bus-mcp"))

mcp_main = importlib.import_module("semantic_bus.mcp_server")
app = mcp_main.app


class FakeRedis:
    def __init__(self) -> None:
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self.raise_on_ping: Exception | None = None
        self.raise_on_stream: str | None = None

    async def ping(self) -> bool:
        if self.raise_on_ping is not None:
            raise self.raise_on_ping
        return True

    async def xadd(
        self,
        stream: str,
        fields: dict[str, str],
        maxlen: int | None = None,
        approximate: bool = False,
    ) -> str:
        _ = maxlen
        _ = approximate
        if self.raise_on_stream and stream.startswith(self.raise_on_stream):
            raise RuntimeError("xadd failure")
        entries = self.streams.setdefault(stream, [])
        entry_id = f"{len(entries) + 1}-0"
        entries.append((entry_id, fields))
        return entry_id

    async def xrevrange(self, stream: str, count: int = 50) -> list[tuple[str, dict[str, str]]]:
        entries = self.streams.get(stream, [])
        return list(reversed(entries[-count:]))


def _alpha_payload() -> dict[str, Any]:
    return {
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
            "directive": {"mission_id": "mission-1"},
        },
    }


def test_send_message_success() -> None:
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": "mcp-local-key"},
            json=_alpha_payload(),
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["protocol"] == "alpha"
    assert payload["channels"] == ["protocol:alpha:AGENT-12-PODA-MGR"]
    assert payload["message_id"].startswith("msg-")


def test_send_message_rejects_oversized_payload(monkeypatch) -> None:
    monkeypatch.setattr(mcp_main, "MAX_MESSAGE_BYTES", 32)
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": "mcp-local-key"},
            json={
                "schema_version": "v1",
                "protocol": "omega",
                "sender": "AGENT-01-PM",
                "recipient": "AGENT-02-CEO",
                "payload": {
                    "schema_version": "v1",
                    "feature_contract": {},
                    "visual_blueprint": {},
                    "user_intent": "x" * 500,
                },
            },
        )
    assert response.status_code == 413


def test_send_message_rejects_sender_mismatch() -> None:
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={"x-agent-id": "AGENT-99-FAKE", "x-api-key": "mcp-local-key"},
            json=_alpha_payload(),
        )
    assert response.status_code == 403
    assert "sender identity mismatch" in response.json()["detail"]


def test_send_message_rejects_invalid_protocol_payload() -> None:
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={"x-agent-id": "AGENT-14-PYTHON", "x-api-key": "mcp-local-key"},
            json={
                "schema_version": "v1",
                "protocol": "beta",
                "sender": "AGENT-14-PYTHON",
                "recipient": "AGENT-12-PODA-MGR",
                "payload": {
                    "schema_version": "v1",
                    "logicnode_id": "node-1",
                    "confidence_score": 2.5,
                    "source_language": "python",
                    "payload": {},
                },
            },
        )
    assert response.status_code == 422


def test_health_endpoint_with_ready_redis() -> None:
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["service"] == "semantic-bus-mcp"


def test_readyz_endpoint_with_ready_redis() -> None:
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_parse_datetime_and_recipient_helpers() -> None:
    parsed = mcp_main._parse_datetime("2026-03-01T00:00:00Z")
    assert parsed.tzinfo is not None
    with pytest.raises(ValueError):
        mcp_main._parse_datetime("2026-03-01T00:00:00")
    assert mcp_main._normalized_recipients(" AGENT-01-PM ") == ["AGENT-01-PM"]
    assert mcp_main._normalized_recipients(["A", "A", "broadcast"]) == ["A", "broadcast"]
    with pytest.raises(mcp_main.HTTPException):
        mcp_main._normalized_recipients("   ")
    channels = mcp_main._resolve_channels("alpha", ["broadcast", "AGENT-01-PM"])
    assert channels == ["protocol:alpha:AGENT-01-PM", "protocol:alpha:broadcast"]


def test_validate_protocol_payload_helper() -> None:
    payload = mcp_main._validate_protocol_payload(
        "rho",
        {
            "schema_version": "v1",
            "token_budget": 100,
            "rate_limit_action": "throttle",
            "agent_target": "AGENT-02-CEO",
            "metadata": {},
        },
    )
    assert payload["token_budget"] == 100
    with pytest.raises(ValueError):
        mcp_main._validate_protocol_payload("invalid", {})


def test_readyz_endpoint_failure_modes() -> None:
    with TestClient(app) as client:
        app.state.redis = None
        app.state.redis_ready = False
        response = client.get("/readyz")
    assert response.status_code == 503

    redis_client = FakeRedis()
    redis_client.raise_on_ping = RuntimeError("down")
    with TestClient(app) as client:
        app.state.redis = redis_client
        app.state.redis_ready = True
        response = client.get("/readyz")
    assert response.status_code == 503


def test_health_endpoint_handles_ping_failure() -> None:
    redis_client = FakeRedis()
    redis_client.raise_on_ping = RuntimeError("down")
    with TestClient(app) as client:
        app.state.redis = redis_client
        app.state.redis_ready = True
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_dlq_endpoint_validation_and_success() -> None:
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.get("/dlq", params={"protocol": "invalid"})
        assert response.status_code == 422

        app.state.redis_ready = False
        response = client.get("/dlq", params={"protocol": "alpha"})
        assert response.status_code == 503

        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        asyncio.run(
            app.state.redis.xadd(
                "dlq:alpha",
                {"error": "boom", "payload": "{\"a\":1}", "ts": "2026-03-01T00:00:00+00:00"},
            )
        )
        response = client.get("/dlq", params={"protocol": "alpha"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["protocol"] == "alpha"
    assert payload["count"] == 1


def test_send_message_rejects_invalid_json() -> None:
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": "mcp-local-key"},
            content="{",
        )
    assert response.status_code == 400


def test_send_message_rejects_invalid_api_key() -> None:
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": "wrong"},
            json=_alpha_payload(),
        )
    assert response.status_code == 403
    assert "invalid mcp api key" in response.json()["detail"]


def test_send_message_rejects_when_redis_unavailable() -> None:
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = False
        response = client.post(
            "/send",
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": "mcp-local-key"},
            json=_alpha_payload(),
        )
    assert response.status_code == 503


def test_send_message_publish_failure_writes_dlq() -> None:
    redis_client = FakeRedis()
    redis_client.raise_on_stream = "protocol:alpha"
    with TestClient(app) as client:
        app.state.redis = redis_client
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": "mcp-local-key"},
            json=_alpha_payload(),
        )
    assert response.status_code == 503
    assert "dlq:alpha" in redis_client.streams


def test_send_message_multi_recipient_route() -> None:
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        payload = _alpha_payload()
        payload["recipient"] = ["AGENT-12-PODA-MGR", "broadcast", "AGENT-12-PODA-MGR"]
        response = client.post(
            "/send",
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": "mcp-local-key"},
            json=payload,
        )
    assert response.status_code == 200
    channels = response.json()["channels"]
    assert "protocol:alpha:broadcast" in channels
