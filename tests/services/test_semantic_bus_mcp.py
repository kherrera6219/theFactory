import asyncio
import builtins
import importlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "semantic-bus-mcp"))

mcp_main = importlib.import_module("semantic_bus.mcp_server")
app = mcp_main.app

from shared_runtime import protocol as protocol_guard  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_replay_guard():
    protocol_guard.reset_replay_guard()
    yield
    protocol_guard.reset_replay_guard()


class FakeRedis:
    def __init__(self) -> None:
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self._kv: dict[str, str] = {}
        self.raise_on_ping: Exception | None = None
        self.raise_on_stream: str | None = None

    async def ping(self) -> bool:
        if self.raise_on_ping is not None:
            raise self.raise_on_ping
        return True

    async def set(
        self,
        key: str,
        value: str,
        *,
        nx: bool = False,
        ex: int | None = None,
    ) -> bool | None:
        if nx and key in self._kv:
            return None
        self._kv[key] = value
        return True

    async def xlen(self, stream: str) -> int:
        return len(self.streams.get(stream, []))

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
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
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
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
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
            headers={"x-agent-id": "AGENT-99-FAKE", "x-api-key": mcp_main.MCP_API_KEY},
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
            headers={"x-agent-id": "AGENT-14-PYTHON", "x-api-key": mcp_main.MCP_API_KEY},
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
    assert mcp_main._normalized_recipients(
        ["AGENT-01-PM", "AGENT-01-PM", "broadcast"]
    ) == ["AGENT-01-PM", "broadcast"]
    with pytest.raises(mcp_main.HTTPException):
        mcp_main._normalized_recipients(["A"])
    with pytest.raises(mcp_main.HTTPException):
        mcp_main._normalized_recipients("A")
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
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
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
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
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
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
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
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
            json=payload,
        )
    assert response.status_code == 200
    channels = response.json()["channels"]
    assert "protocol:alpha:broadcast" in channels


def test_normalized_recipients_extra_validation_branches(monkeypatch) -> None:
    with pytest.raises(mcp_main.HTTPException):
        mcp_main._normalized_recipients([])

    monkeypatch.setattr(mcp_main, "MAX_RECIPIENTS", 1)
    with pytest.raises(mcp_main.HTTPException):
        mcp_main._normalized_recipients(["AGENT-01-PM", "AGENT-02-CEO"])


def test_write_dlq_no_redis_is_noop() -> None:
    asyncio.run(mcp_main._write_dlq(None, "alpha", {"sample": True}, "boom"))


def test_health_and_readyz_additional_branches() -> None:
    with TestClient(app) as client:
        app.state.redis = None
        app.state.redis_ready = False
        payload = client.get("/health").json()
        assert payload["ok"] is False

    class FalseRedis:
        async def ping(self) -> bool:
            return False

    with TestClient(app) as client:
        app.state.redis = FalseRedis()
        app.state.redis_ready = True
        response = client.get("/readyz")
    assert response.status_code == 503


def test_metrics_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"]


def test_send_message_rejects_invalid_sender_id() -> None:
    payload = _alpha_payload()
    payload["sender"] = "bad-sender"
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={"x-agent-id": "bad-sender", "x-api-key": mcp_main.MCP_API_KEY},
            json=payload,
        )
    assert response.status_code == 422


def test_send_message_request_validation_error() -> None:
    payload = _alpha_payload()
    del payload["sender"]
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
            json=payload,
        )
    assert response.status_code == 422


def test_send_message_protocol_value_error_path(monkeypatch) -> None:
    payload = _alpha_payload()

    def _raise_value_error(_protocol: str, _payload: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("unsupported protocol branch")

    monkeypatch.setattr(mcp_main, "_validate_protocol_payload", _raise_value_error)
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
            json=payload,
        )
    assert response.status_code == 422


def test_lifespan_handles_redis_absent_and_close_paths(monkeypatch) -> None:
    app_state = SimpleNamespace(state=SimpleNamespace())
    monkeypatch.setattr(mcp_main, "redis", None)

    async def _run_none():
        async with mcp_main.lifespan(app_state):
            assert app_state.state.redis is None

    asyncio.run(_run_none())

    class RedisWithClose:
        def __init__(self) -> None:
            self.closed = False

        async def ping(self) -> bool:
            return True

        def close(self):
            async def _close():
                self.closed = True

            return _close()

    redis_client = RedisWithClose()

    class RedisModule:
        @staticmethod
        def from_url(url: str, decode_responses: bool = True):
            _ = url
            _ = decode_responses
            return redis_client

    monkeypatch.setattr(mcp_main, "redis", RedisModule)
    app_state = SimpleNamespace(state=SimpleNamespace())

    async def _run_close():
        async with mcp_main.lifespan(app_state):
            pass

    asyncio.run(_run_close())
    assert redis_client.closed is True


def test_lifespan_handles_sync_close(monkeypatch) -> None:
    class RedisWithSyncClose:
        def __init__(self) -> None:
            self.closed = False

        async def ping(self) -> bool:
            return True

        def close(self) -> None:
            self.closed = True

    redis_client = RedisWithSyncClose()

    class RedisModule:
        @staticmethod
        def from_url(url: str, decode_responses: bool = True):
            _ = url
            _ = decode_responses
            return redis_client

    monkeypatch.setattr(mcp_main, "redis", RedisModule)
    app_state = SimpleNamespace(state=SimpleNamespace())

    async def _run_close():
        async with mcp_main.lifespan(app_state):
            pass

    asyncio.run(_run_close())
    assert redis_client.closed is True


def test_lifespan_handles_aclose(monkeypatch) -> None:
    class RedisWithAclose:
        def __init__(self) -> None:
            self.closed = False

        async def ping(self) -> bool:
            return True

        async def aclose(self) -> None:
            self.closed = True

    redis_client = RedisWithAclose()

    class RedisModule:
        @staticmethod
        def from_url(url: str, decode_responses: bool = True):
            _ = url
            _ = decode_responses
            return redis_client

    monkeypatch.setattr(mcp_main, "redis", RedisModule)
    app_state = SimpleNamespace(state=SimpleNamespace())

    async def _run():
        async with mcp_main.lifespan(app_state):
            pass

    asyncio.run(_run())
    assert redis_client.closed is True


def test_semantic_bus_module_import_fallback_without_redis(monkeypatch) -> None:
    module_path = ROOT / "services" / "semantic-bus-mcp" / "semantic_bus" / "mcp_server.py"
    real_import = builtins.__import__

    class _DummyMetric:
        def labels(self, **_kwargs):
            return self

        def inc(self):
            return None

        def observe(self, _value):
            return None

    def _blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "redis.asyncio":
            raise ModuleNotFoundError(name)
        if name == "prometheus_client":
            def _counter(*_args, **_kwargs):
                return _DummyMetric()

            def _histogram(*_args, **_kwargs):
                return _DummyMetric()

            def _generate_latest():
                return b""

            class _DummyPrometheus:
                CONTENT_TYPE_LATEST = "text/plain"
                Counter = staticmethod(_counter)
                Histogram = staticmethod(_histogram)
                generate_latest = staticmethod(_generate_latest)

            return _DummyPrometheus
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)
    spec = importlib.util.spec_from_file_location("semantic_bus.mcp_server_no_redis", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.redis is None


def test_semantic_bus_module_import_enforces_explicit_production_api_key(monkeypatch) -> None:
    module_path = ROOT / "services" / "semantic-bus-mcp" / "semantic_bus" / "mcp_server.py"
    module_name = "semantic_bus.mcp_server_production_guard"
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with pytest.raises(RuntimeError, match="MCP_API_KEY must be explicitly set in production"):
        spec.loader.exec_module(module)


def test_semantic_bus_module_import_accepts_explicit_api_key_without_warning(monkeypatch) -> None:
    module_path = ROOT / "services" / "semantic-bus-mcp" / "semantic_bus" / "mcp_server.py"
    module_name = "semantic_bus.mcp_server_with_explicit_key"
    real_import = builtins.__import__
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("MCP_API_KEY", "stable-test-key")
    sys.modules.pop(module_name, None)

    class _DummyMetric:
        def labels(self, **_kwargs):
            return self

        def inc(self):
            return None

        def observe(self, _value):
            return None

    def _patched_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "prometheus_client":
            def _counter(*_args, **_kwargs):
                return _DummyMetric()

            def _histogram(*_args, **_kwargs):
                return _DummyMetric()

            def _generate_latest():
                return b""

            class _DummyPrometheus:
                CONTENT_TYPE_LATEST = "text/plain"
                Counter = staticmethod(_counter)
                Histogram = staticmethod(_histogram)
                generate_latest = staticmethod(_generate_latest)

            return _DummyPrometheus
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _patched_import)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    messages: list[str] = []

    def _capture(message: str, *args) -> None:
        messages.append(message % args if args else message)

    monkeypatch.setattr(module.LOGGER, "error", _capture)

    class RedisWithAclose:
        def __init__(self) -> None:
            self.closed = False

        async def ping(self) -> bool:
            return True

        async def aclose(self) -> None:
            self.closed = True

    redis_client = RedisWithAclose()

    class RedisModule:
        @staticmethod
        def from_url(url: str, decode_responses: bool = True):
            _ = url
            _ = decode_responses
            return redis_client

    monkeypatch.setattr(module, "redis", RedisModule)
    app_state = SimpleNamespace(state=SimpleNamespace())

    async def _run() -> None:
        async with module.lifespan(app_state):
            assert app_state.state.redis_ready is True

    asyncio.run(_run())
    assert messages == []
    assert redis_client.closed is True
