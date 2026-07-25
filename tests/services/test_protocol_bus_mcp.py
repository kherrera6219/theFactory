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
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "protocol-bus-mcp"))

mcp_main = importlib.import_module("protocol_bus.mcp_server")
app = mcp_main.app


class FakeRedis:
    """In-memory async Redis double.

    Shared instances simulate a single distributed Redis backing multiple
    Protocol Bus processes — replay detection must hold across them.
    """

    def __init__(self) -> None:
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self._kv: dict[str, str] = {}
        self.raise_on_ping: Exception | None = None
        self.raise_on_stream: str | None = None
        self.raise_on_set: Exception | None = None

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
        if self.raise_on_set is not None:
            raise self.raise_on_set
        if nx and key in self._kv:
            return None
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
    assert payload["service"] == "protocol-bus-mcp"


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


def test_lane_stats_endpoint_reports_all_lanes_and_dlq_depth() -> None:
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        asyncio.run(
            app.state.redis.xadd(
                "dlq:beta",
                {"error": "boom", "payload": "{}", "ts": "2026-03-01T00:00:00+00:00"},
            )
        )
        response = client.get("/lane-stats")
    assert response.status_code == 200
    payload = response.json()
    assert payload["redis_ready"] is True
    assert set(payload["lanes"].keys()) == set(mcp_main.ALLOWED_PROTOCOLS)
    assert payload["lanes"]["beta"]["dlq_depth"] == 1
    assert payload["lanes"]["alpha"]["dlq_depth"] == 0
    for lane_payload in payload["lanes"].values():
        assert lane_payload["messages_queued_total"] >= 0
        assert lane_payload["dlq_writes_total"] >= 0
        assert lane_payload["messages_deduplicated_total"] >= 0
        assert lane_payload["messages_replayed_total"] >= 0


def test_lane_stats_endpoint_without_redis_reports_none_dlq_depth() -> None:
    with TestClient(app) as client:
        app.state.redis = None
        app.state.redis_ready = False
        response = client.get("/lane-stats")
    assert response.status_code == 200
    payload = response.json()
    assert payload["redis_ready"] is False
    for lane_payload in payload["lanes"].values():
        assert lane_payload["dlq_depth"] is None


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


def test_lifespan_logs_development_session_key_warning(monkeypatch) -> None:
    app_state = SimpleNamespace(state=SimpleNamespace())
    messages: list[str] = []

    def _capture(message: str, *args) -> None:
        messages.append(message % args if args else message)

    monkeypatch.setattr(mcp_main, "redis", None)
    monkeypatch.setattr(mcp_main, "_MCP_API_KEY_RAW", "")
    monkeypatch.setattr(
        mcp_main,
        "_DEV_SESSION_NOTICE",
        "MCP_API_KEY is not set. A random session key has been generated.",
        raising=False,
    )
    monkeypatch.setattr(mcp_main.LOGGER, "error", _capture)

    async def _run() -> None:
        async with mcp_main.lifespan(app_state):
            assert app_state.state.redis is None

    asyncio.run(_run())
    assert any("MCP_API_KEY is not set" in message for message in messages)


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


def test_protocol_bus_module_import_fallback_without_redis(monkeypatch) -> None:
    module_path = ROOT / "services" / "protocol-bus-mcp" / "protocol_bus" / "mcp_server.py"
    real_import = builtins.__import__
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("MCP_API_KEY", raising=False)

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
    spec = importlib.util.spec_from_file_location("protocol_bus.mcp_server_no_redis", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.redis is None
    assert module._MCP_API_KEY_RAW == ""
    assert "MCP_API_KEY is not set" in module._DEV_SESSION_NOTICE


def test_message_dedup_ttl_env_accepts_legacy_compose_alias(monkeypatch) -> None:
    monkeypatch.delenv("MCP_DEDUP_TTL_SECONDS", raising=False)
    monkeypatch.setenv("MESSAGE_DEDUP_TTL_SECONDS", "600")
    assert mcp_main._message_dedup_ttl_seconds() == 600

    monkeypatch.setenv("MCP_DEDUP_TTL_SECONDS", "900")
    assert mcp_main._message_dedup_ttl_seconds() == 900


def test_protocol_bus_module_import_enforces_explicit_production_api_key(monkeypatch) -> None:
    module_path = ROOT / "services" / "protocol-bus-mcp" / "protocol_bus" / "mcp_server.py"
    module_name = "protocol_bus.mcp_server_production_guard"
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with pytest.raises(RuntimeError, match="MCP_API_KEY must be explicitly set in production"):
        spec.loader.exec_module(module)


def test_protocol_bus_module_import_accepts_explicit_api_key_without_warning(monkeypatch) -> None:
    module_path = ROOT / "services" / "protocol-bus-mcp" / "protocol_bus" / "mcp_server.py"
    module_name = "protocol_bus.mcp_server_with_explicit_key"
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
    assert module.MCP_API_KEY == "stable-test-key"

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


# ---------------------------------------------------------------------------
# Per-agent HMAC signing (Phase 3)
# ---------------------------------------------------------------------------
def test_agent_hmac_secret_env_resolution(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_HMAC_SECRET_02_CEO", "  topsecret-value  ")
    assert mcp_main._agent_hmac_secret("AGENT-02-CEO") == "topsecret-value"
    assert mcp_main._agent_hmac_secret("AGENT-99-NOPE") is None


def test_agent_hmac_secret_without_agent_prefix(monkeypatch) -> None:
    # An id that does not start with "AGENT-" skips the prefix-stripping branch.
    monkeypatch.setenv("AGENT_HMAC_SECRET_CUSTOM_ID", "  another-secret  ")
    assert mcp_main._agent_hmac_secret("custom-id") == "another-secret"


def test_event_envelope_validates_timestamp() -> None:
    envelope = mcp_main.EventEnvelope(
        event_id="evt-1",
        topic="protocol.alpha",
        timestamp="2026-03-01T00:00:00Z",
        producer="AGENT-02-CEO",
        correlation_id="corr-1",
        payload_ref="registry://alpha/1",
        schema="alpha.v1",
        priority="HIGH",
    )
    assert envelope.event_id == "evt-1"
    with pytest.raises(ValidationError):
        mcp_main.EventEnvelope(
            event_id="evt-2",
            topic="protocol.alpha",
            timestamp="2026-03-01T00:00:00",
            producer="AGENT-02-CEO",
            correlation_id="corr-2",
            payload_ref="registry://alpha/2",
            schema="alpha.v1",
            priority="HIGH",
        )


def test_send_rejects_missing_signature_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(mcp_main, "AGENT_HMAC_SIGNING_ENABLED", True)
    monkeypatch.setenv("AGENT_HMAC_SECRET_02_CEO", "secret-with-good-entropy-1234")
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
            json=_alpha_payload(),
        )
    assert response.status_code == 401
    assert "missing agent signature" in response.json()["detail"]


def test_send_rejects_when_signing_enabled_but_no_secret_configured(monkeypatch) -> None:
    # Signature header present, but the sender has no AGENT_HMAC_SECRET_* configured.
    monkeypatch.setattr(mcp_main, "AGENT_HMAC_SIGNING_ENABLED", True)
    monkeypatch.delenv("AGENT_HMAC_SECRET_02_CEO", raising=False)
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={
                "x-agent-id": "AGENT-02-CEO",
                "x-api-key": mcp_main.MCP_API_KEY,
                "x-agent-signature": "9999999999:deadbeef",
            },
            json=_alpha_payload(),
        )
    assert response.status_code == 401
    assert "agent signing secret not configured" in response.json()["detail"]


def test_send_rejects_invalid_signature_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(mcp_main, "AGENT_HMAC_SIGNING_ENABLED", True)
    monkeypatch.setenv("AGENT_HMAC_SECRET_02_CEO", "secret-with-good-entropy-1234")
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={
                "x-agent-id": "AGENT-02-CEO",
                "x-api-key": mcp_main.MCP_API_KEY,
                "x-agent-signature": "9999999999:deadbeef",
            },
            json=_alpha_payload(),
        )
    assert response.status_code == 401
    assert "invalid agent signature" in response.json()["detail"]


def test_send_accepts_valid_signature_when_enabled(monkeypatch) -> None:
    from shared_runtime.agent_auth import sign_agent_message

    secret = "secret-with-good-entropy-1234"
    monkeypatch.setattr(mcp_main, "AGENT_HMAC_SIGNING_ENABLED", True)
    monkeypatch.setenv("AGENT_HMAC_SECRET_02_CEO", secret)
    body = _alpha_payload()
    sig = sign_agent_message("AGENT-02-CEO", secret, body["payload"])
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={
                "x-agent-id": "AGENT-02-CEO",
                "x-api-key": mcp_main.MCP_API_KEY,
                "x-agent-signature": sig,
            },
            json=body,
        )
    assert response.status_code == 200


def test_send_ignores_signature_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(mcp_main, "AGENT_HMAC_SIGNING_ENABLED", False)
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
            json=_alpha_payload(),
        )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Backpressure gate (Phase 4)
# ---------------------------------------------------------------------------
def test_send_message_returns_503_when_backpressure_limit_exceeded(monkeypatch) -> None:
    """When any channel's queue depth exceeds BACKPRESSURE_QUEUE_LIMIT the
    /send endpoint must reject the request with 503 and a Retry-After header."""
    monkeypatch.setattr(mcp_main, "BACKPRESSURE_QUEUE_LIMIT", -1)
    with TestClient(app) as client:
        app.state.redis = FakeRedis()
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
            json=_alpha_payload(),
        )
    assert response.status_code == 503
    assert "backpressure limit exceeded" in response.json()["detail"]
    assert response.headers.get("retry-after") == "5"


def test_send_message_returns_503_when_backpressure_xlen_raises() -> None:
    """When xlen raises during the backpressure check the endpoint must fail
    closed with 503 rather than silently letting the message through."""

    class XlenFailingRedis(FakeRedis):
        async def xlen(self, stream: str) -> int:
            raise RuntimeError("simulated xlen failure")

    with TestClient(app) as client:
        app.state.redis = XlenFailingRedis()
        app.state.redis_ready = True
        response = client.post(
            "/send",
            headers={"x-agent-id": "AGENT-02-CEO", "x-api-key": mcp_main.MCP_API_KEY},
            json=_alpha_payload(),
        )
    assert response.status_code == 503
    assert "Backpressure service unavailable" in response.json()["detail"]
