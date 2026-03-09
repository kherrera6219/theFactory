import asyncio
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "audit-worker"))

audit_worker_main = importlib.import_module("audit_worker.main")


def _schema() -> dict[str, Any]:
    return {
        "required": [
            "event_id",
            "topic",
            "timestamp",
            "producer",
            "correlation_id",
            "payload_ref",
            "schema",
            "priority",
        ],
        "additionalProperties": False,
        "properties": {
            "event_id": {"type": "string"},
            "topic": {"type": "string"},
            "timestamp": {"type": "string"},
            "producer": {"type": "string"},
            "correlation_id": {"type": "string"},
            "payload_ref": {"type": "string"},
            "schema": {"type": "string"},
            "priority": {"type": "string", "enum": ["NORMAL", "HIGH"]},
        },
    }


def _valid_envelope() -> dict[str, Any]:
    return {
        "event_id": "evt-1",
        "topic": "artifact.rir.verified",
        "timestamp": "2026-03-01T00:00:00+00:00",
        "producer": "audit-worker",
        "correlation_id": "mission-1",
        "payload_ref": "registry://missions/mission-1",
        "schema": "audit.report.v1",
        "priority": "NORMAL",
    }


def test_parse_date_time() -> None:
    parsed = audit_worker_main._parse_date_time("2026-03-01T00:00:00Z")
    assert parsed.tzinfo is not None
    with pytest.raises(ValueError):
        audit_worker_main._parse_date_time("2026-03-01T00:00:00")


def test_service_api_key_resolution_prefers_agent_specific_values(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_10_TESTER_SERVICE_API_KEY", "tester-agent-key")
    monkeypatch.setattr(audit_worker_main, "AGENT_SERVICE_API_KEYS", "")
    monkeypatch.setattr(audit_worker_main, "AGENT_SERVICE_KEY_MODE", "shared")

    assert audit_worker_main._service_api_key_for_agent("AGENT-10-TESTER") == "tester-agent-key"
    assert audit_worker_main._service_api_key_for_agent("AGENT-31-PODD-AUDIT") == "worker-key"


def test_service_api_key_resolution_raises_in_strict_mode(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_10_TESTER_SERVICE_API_KEY", raising=False)
    monkeypatch.setattr(audit_worker_main, "AGENT_SERVICE_API_KEYS", "")
    monkeypatch.setattr(audit_worker_main, "AGENT_SERVICE_KEY_MODE", "strict")

    with pytest.raises(RuntimeError):
        audit_worker_main._service_api_key_for_agent("AGENT-10-TESTER")


def test_loaders_and_validate_envelope_success(monkeypatch, tmp_path: Path) -> None:
    schema_path = tmp_path / "event.envelope.schema.json"
    topics_path = tmp_path / "topics.yaml"
    schema_path.write_text(json.dumps(_schema()), encoding="utf-8")
    topics_path.write_text("- artifact.rir.verified\n- artifact.rir.rejected\n", encoding="utf-8")
    monkeypatch.setattr(audit_worker_main, "EVENT_SCHEMA_PATH", schema_path)
    monkeypatch.setattr(audit_worker_main, "TOPICS_PATH", topics_path)

    loaded_schema = audit_worker_main._load_event_schema()
    loaded_topics = audit_worker_main._load_topics()
    assert "required" in loaded_schema
    assert "artifact.rir.verified" in loaded_topics
    audit_worker_main._validate_envelope(_valid_envelope())


def test_loaders_missing_and_empty_topics(tmp_path: Path, monkeypatch) -> None:
    missing_schema = tmp_path / "missing-schema.json"
    missing_topics = tmp_path / "missing-topics.yaml"
    monkeypatch.setattr(audit_worker_main, "EVENT_SCHEMA_PATH", missing_schema)
    monkeypatch.setattr(audit_worker_main, "TOPICS_PATH", missing_topics)

    with pytest.raises(audit_worker_main.ProtocolValidationError):
        audit_worker_main._load_event_schema()
    with pytest.raises(audit_worker_main.ProtocolValidationError):
        audit_worker_main._load_topics()

    topics_path = tmp_path / "topics.yaml"
    topics_path.write_text("topics:\n  none: true\n", encoding="utf-8")
    monkeypatch.setattr(audit_worker_main, "TOPICS_PATH", topics_path)
    with pytest.raises(audit_worker_main.ProtocolValidationError):
        audit_worker_main._load_topics()


def test_validate_envelope_failures(monkeypatch) -> None:
    monkeypatch.setattr(audit_worker_main, "_load_event_schema", lambda: _schema())
    monkeypatch.setattr(audit_worker_main, "_load_topics", lambda: {"artifact.rir.verified"})

    envelope = _valid_envelope()
    del envelope["event_id"]
    with pytest.raises(audit_worker_main.ProtocolValidationError):
        audit_worker_main._validate_envelope(envelope)

    envelope = _valid_envelope()
    envelope["topic"] = "unknown.topic"
    with pytest.raises(audit_worker_main.ProtocolValidationError):
        audit_worker_main._validate_envelope(envelope)

    envelope = _valid_envelope()
    envelope["payload_ref"] = "http://bad-ref"
    with pytest.raises(audit_worker_main.ProtocolValidationError):
        audit_worker_main._validate_envelope(envelope)

    envelope = _valid_envelope()
    envelope["priority"] = "LOW"
    with pytest.raises(audit_worker_main.ProtocolValidationError):
        audit_worker_main._validate_envelope(envelope)

    envelope = _valid_envelope()
    envelope["timestamp"] = "2026-03-01T00:00:00"
    with pytest.raises(audit_worker_main.ProtocolValidationError):
        audit_worker_main._validate_envelope(envelope)

    envelope = _valid_envelope()
    envelope["extra_field"] = "boom"
    with pytest.raises(audit_worker_main.ProtocolValidationError):
        audit_worker_main._validate_envelope(envelope)

    envelope = _valid_envelope()
    envelope["producer"] = 123
    with pytest.raises(audit_worker_main.ProtocolValidationError):
        audit_worker_main._validate_envelope(envelope)


def test_validate_envelope_with_additional_properties_allowed(monkeypatch) -> None:
    schema = _schema()
    schema["additionalProperties"] = True
    monkeypatch.setattr(audit_worker_main, "_load_event_schema", lambda: schema)
    monkeypatch.setattr(audit_worker_main, "_load_topics", lambda: {"artifact.rir.verified"})
    envelope = _valid_envelope()
    envelope["unexpected"] = "allowed"
    audit_worker_main._validate_envelope(envelope)


class FakeRedis:
    def __init__(self, responses: list[Any] | None = None) -> None:
        self.responses = list(responses or [])
        self.xadd_calls: list[tuple[str, dict[str, str]]] = []
        self.xack_calls: list[tuple[str, str, str]] = []
        self.group_error: Exception | None = None
        self._read_calls = 0

    async def ping(self) -> bool:
        return True

    async def xgroup_create(self, **kwargs: Any) -> None:
        _ = kwargs
        if self.group_error is not None:
            raise self.group_error

    async def xadd(self, stream: str, fields: dict[str, str], **kwargs: Any) -> str:
        _ = kwargs
        self.xadd_calls.append((stream, fields))
        return "1-0"

    async def xreadgroup(self, **kwargs: Any) -> Any:
        _ = kwargs
        self._read_calls += 1
        if self.responses:
            response = self.responses.pop(0)
            if isinstance(response, BaseException):
                raise response
            return response
        raise asyncio.CancelledError

    async def xack(self, stream: str, group: str, entry_id: str) -> int:
        self.xack_calls.append((stream, group, entry_id))
        return 1


class FakeTask:
    def __init__(self) -> None:
        self.cancel_called = False

    def cancel(self) -> None:
        self.cancel_called = True

    def __await__(self):
        async def _cancelled():
            raise asyncio.CancelledError

        return _cancelled().__await__()


def test_build_and_publish_event(monkeypatch) -> None:
    redis_client = FakeRedis()
    monkeypatch.setattr(audit_worker_main, "_validate_envelope", lambda _envelope: None)
    envelope = audit_worker_main._build_envelope(
        "artifact.rir.verified",
        "mission-1",
        "registry://missions/mission-1",
        "audit.report.v1",
    )
    assert envelope["topic"] == "artifact.rir.verified"

    asyncio.run(
        audit_worker_main._publish_event(
            redis_client,
            "artifact.rir.verified",
            "mission-1",
            {"mission_id": "mission-1"},
        )
    )
    assert redis_client.xadd_calls


def test_ensure_group_busygroup_and_error() -> None:
    busy = FakeRedis()
    busy.group_error = audit_worker_main.ResponseError("BUSYGROUP already exists")
    asyncio.run(audit_worker_main._ensure_group(busy))

    failing = FakeRedis()
    failing.group_error = audit_worker_main.ResponseError("other")
    with pytest.raises(audit_worker_main.ResponseError):
        asyncio.run(audit_worker_main._ensure_group(failing))


def test_post_audit_success_and_failure(monkeypatch) -> None:
    captured_headers: list[dict[str, Any]] = []

    class FakeResponse:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code

    class FakeClient:
        def __init__(self, status_code: int) -> None:
            self._status_code = status_code

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *_args: Any, **kwargs: Any) -> FakeResponse:
            captured_headers.append(kwargs.get("headers", {}))
            return FakeResponse(self._status_code)

    monkeypatch.setenv("AGENT_10_TESTER_SERVICE_API_KEY", "tester-agent-key")
    monkeypatch.setattr(audit_worker_main.httpx, "AsyncClient", lambda timeout: FakeClient(200))
    assert (
        asyncio.run(
            audit_worker_main._post_audit(
                mission_id="mission-1",
                status="PASS",
                summary="summary",
                report={"result": "PASS"},
            )
        )
        is True
    )
    assert captured_headers[0]["x-api-key"] == "tester-agent-key"
    assert captured_headers[0]["x-agent-id"] == "AGENT-10-TESTER"

    monkeypatch.setattr(audit_worker_main.httpx, "AsyncClient", lambda timeout: FakeClient(500))
    assert (
        asyncio.run(
            audit_worker_main._post_audit(
                mission_id="mission-1",
                status="FAIL",
                summary="summary",
                report={"result": "FAIL"},
            )
        )
        is False
    )

    class ErrorClient(FakeClient):
        async def post(self, *_args: Any, **_kwargs: Any) -> FakeResponse:
            raise audit_worker_main.httpx.HTTPError("network down")

    monkeypatch.setattr(audit_worker_main.httpx, "AsyncClient", lambda timeout: ErrorClient(500))
    assert (
        asyncio.run(
            audit_worker_main._post_audit(
                mission_id="mission-1",
                status="FAIL",
                summary="summary",
                report={"result": "FAIL"},
            )
        )
        is False
    )


def test_consumer_loop_branches(monkeypatch) -> None:
    verified = {
        "envelope": json.dumps({"topic": "artifact.rir.verified"}),
        "payload": json.dumps({"event_type": "MISSION_VERIFIED", "mission_id": "mission-1"}),
    }
    failed = {
        "envelope": json.dumps({"topic": "artifact.rir.rejected"}),
        "payload": json.dumps({"event_type": "MISSION_FAILED", "mission_id": "mission-2"}),
    }
    complete = {
        "envelope": json.dumps({"topic": "binary.build.ready"}),
        "payload": json.dumps({"event_type": "MISSION_COMPLETE", "mission_id": "mission-3"}),
    }
    invalid = {
        "envelope": json.dumps({"topic": "artifact.rir.verified"}),
        "payload": json.dumps({"event_type": "MISSION_VERIFIED", "mission_id": ""}),
    }

    redis_client = FakeRedis(
        responses=[
            [("missions.state", [("1-0", verified)])],
            [("missions.state", [("2-0", failed)])],
            [("missions.state", [("3-0", complete)])],
            [("missions.state", [("4-0", invalid)])],
            asyncio.CancelledError(),
        ]
    )

    async def _post_audit(*_args: Any, **_kwargs: Any) -> bool:
        return True

    published: list[str] = []

    async def _publish_event(
        _redis_client: Any, topic: str, _mission_id: str, _payload: dict[str, Any]
    ) -> None:
        published.append(topic)

    monkeypatch.setattr(audit_worker_main, "_validate_envelope", lambda _envelope: None)
    monkeypatch.setattr(audit_worker_main, "_post_audit", _post_audit)
    monkeypatch.setattr(audit_worker_main, "_publish_event", _publish_event)

    app = SimpleNamespace(state=SimpleNamespace(redis=redis_client, processed=0, errors=0))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(audit_worker_main._consumer_loop(app))

    assert app.state.processed == 3
    assert app.state.errors == 1
    assert len(redis_client.xack_calls) == 4
    assert published == ["artifact.rir.verified", "artifact.rir.rejected", "binary.build.ready"]


def test_consumer_loop_handles_missing_fields(monkeypatch) -> None:
    redis_client = FakeRedis(
        responses=[[("missions.state", [("1-0", {})])], asyncio.CancelledError()]
    )
    monkeypatch.setattr(audit_worker_main, "_validate_envelope", lambda _envelope: None)
    app = SimpleNamespace(state=SimpleNamespace(redis=redis_client, processed=0, errors=0))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(audit_worker_main._consumer_loop(app))

    assert app.state.processed == 0
    assert app.state.errors == 1
    assert redis_client.xack_calls == [("missions.state", "audit-workers", "1-0")]


def test_consumer_loop_skips_publish_when_post_audit_returns_false(monkeypatch) -> None:
    verified = {
        "envelope": json.dumps({"topic": "artifact.rir.verified"}),
        "payload": json.dumps({"event_type": "MISSION_VERIFIED", "mission_id": "mission-1"}),
    }
    failed = {
        "envelope": json.dumps({"topic": "artifact.rir.rejected"}),
        "payload": json.dumps({"event_type": "MISSION_FAILED", "mission_id": "mission-2"}),
    }
    complete = {
        "envelope": json.dumps({"topic": "binary.build.ready"}),
        "payload": json.dumps({"event_type": "MISSION_COMPLETE", "mission_id": "mission-3"}),
    }
    redis_client = FakeRedis(
        responses=[
            [("missions.state", [("1-0", verified), ("2-0", failed), ("3-0", complete)])],
            asyncio.CancelledError(),
        ]
    )
    monkeypatch.setattr(audit_worker_main, "_validate_envelope", lambda _envelope: None)
    monkeypatch.setattr(
        audit_worker_main,
        "_post_audit",
        lambda *_args, **_kwargs: asyncio.sleep(0),
    )
    published: list[str] = []

    async def _publish_event(
        _redis_client: Any, topic: str, _mission_id: str, _payload: dict[str, Any]
    ) -> None:
        published.append(topic)

    monkeypatch.setattr(audit_worker_main, "_publish_event", _publish_event)

    app = SimpleNamespace(state=SimpleNamespace(redis=redis_client, processed=0, errors=0))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(audit_worker_main._consumer_loop(app))

    assert app.state.processed == 3
    assert app.state.errors == 0
    assert published == ["binary.build.ready"]


def test_consumer_loop_processes_unknown_event_without_publish(monkeypatch) -> None:
    unknown = {
        "envelope": json.dumps({"topic": "artifact.rir.verified"}),
        "payload": json.dumps({"event_type": "MISSION_RUNNING", "mission_id": "mission-1"}),
    }
    redis_client = FakeRedis(
        responses=[[("missions.state", [("1-0", unknown)])], asyncio.CancelledError()]
    )
    monkeypatch.setattr(audit_worker_main, "_validate_envelope", lambda _envelope: None)
    monkeypatch.setattr(
        audit_worker_main,
        "_publish_event",
        lambda *_args, **_kwargs: asyncio.sleep(0),
    )
    app = SimpleNamespace(state=SimpleNamespace(redis=redis_client, processed=0, errors=0))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(audit_worker_main._consumer_loop(app))

    assert app.state.processed == 1
    assert app.state.errors == 0
    assert redis_client.xack_calls == [("missions.state", "audit-workers", "1-0")]


def test_consumer_loop_handles_empty_records(monkeypatch) -> None:
    redis_client = FakeRedis(responses=[[], asyncio.CancelledError()])
    monkeypatch.setattr(audit_worker_main, "_validate_envelope", lambda _envelope: None)
    app = SimpleNamespace(state=SimpleNamespace(redis=redis_client, processed=0, errors=0))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(audit_worker_main._consumer_loop(app))

    assert redis_client.xack_calls == []


def test_consumer_loop_recreates_missing_group(monkeypatch) -> None:
    redis_client = FakeRedis(
        responses=[
            audit_worker_main.ResponseError(
                "NOGROUP No such key 'missions.state' or consumer group 'audit-workers'"
            ),
            asyncio.CancelledError(),
        ]
    )
    recreated: list[FakeRedis] = []

    async def _ensure_group(redis_obj: FakeRedis) -> None:
        recreated.append(redis_obj)

    monkeypatch.setattr(audit_worker_main, "_ensure_group", _ensure_group)
    app = SimpleNamespace(state=SimpleNamespace(redis=redis_client, processed=0, errors=0))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(audit_worker_main._consumer_loop(app))

    assert recreated == [redis_client]


def test_health_and_readyz_branches() -> None:
    class PingRedis:
        async def ping(self) -> bool:
            return True

    class DownRedis:
        async def ping(self) -> bool:
            raise RuntimeError("down")

    audit_worker_main.app.state.redis = PingRedis()
    audit_worker_main.app.state.processed = 7
    audit_worker_main.app.state.errors = 2
    payload = asyncio.run(audit_worker_main.health())
    assert payload["ok"] is True
    assert payload["processed"] == 7
    assert payload["worker_agent_id"] == "AGENT-10-TESTER"
    assert "agent_service_key_mode" in payload
    assert asyncio.run(audit_worker_main.readyz())["ready"] is True

    audit_worker_main.app.state.redis = DownRedis()
    payload = asyncio.run(audit_worker_main.health())
    assert payload["ok"] is False
    with pytest.raises(audit_worker_main.HTTPException):
        asyncio.run(audit_worker_main.readyz())

    audit_worker_main.app.state.redis = None
    with pytest.raises(audit_worker_main.HTTPException):
        asyncio.run(audit_worker_main.readyz())

    class FalseRedis:
        async def ping(self) -> bool:
            return False

    audit_worker_main.app.state.redis = FalseRedis()
    with pytest.raises(audit_worker_main.HTTPException):
        asyncio.run(audit_worker_main.readyz())


def test_metrics_endpoint() -> None:
    response = asyncio.run(audit_worker_main.metrics())
    assert response.status_code == 200
    assert response.media_type


def test_health_when_redis_not_configured() -> None:
    audit_worker_main.app.state.redis = None
    audit_worker_main.app.state.processed = 0
    audit_worker_main.app.state.errors = 0
    payload = asyncio.run(audit_worker_main.health())
    assert payload["ok"] is False


def test_lifespan_shutdown_paths(monkeypatch) -> None:
    class RedisWithAclose:
        def __init__(self) -> None:
            self.closed = False

        async def ping(self) -> bool:
            return True

        async def aclose(self) -> None:
            self.closed = True

    redis_client = RedisWithAclose()
    fake_task = FakeTask()

    class RedisModule:
        @staticmethod
        def from_url(url: str, decode_responses: bool = True):
            _ = url
            _ = decode_responses
            return redis_client

    async def _ensure_group(_redis):
        return None

    def _create_task(coro):
        coro.close()
        return fake_task

    monkeypatch.setattr(audit_worker_main, "redis", RedisModule)
    monkeypatch.setattr(audit_worker_main, "_ensure_group", _ensure_group)
    monkeypatch.setattr(audit_worker_main.asyncio, "create_task", _create_task)

    app = SimpleNamespace(state=SimpleNamespace())

    async def _run():
        async with audit_worker_main.lifespan(app):
            assert app.state.consumer_task is fake_task

    asyncio.run(_run())
    assert fake_task.cancel_called is True
    assert redis_client.closed is True


def test_lifespan_close_awaitable(monkeypatch) -> None:
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
    fake_task = FakeTask()

    class RedisModule:
        @staticmethod
        def from_url(url: str, decode_responses: bool = True):
            _ = url
            _ = decode_responses
            return redis_client

    async def _ensure_group(_redis):
        return None

    def _create_task(coro):
        coro.close()
        return fake_task

    monkeypatch.setattr(audit_worker_main, "redis", RedisModule)
    monkeypatch.setattr(audit_worker_main, "_ensure_group", _ensure_group)
    monkeypatch.setattr(audit_worker_main.asyncio, "create_task", _create_task)

    app = SimpleNamespace(state=SimpleNamespace())

    async def _run():
        async with audit_worker_main.lifespan(app):
            pass

    asyncio.run(_run())
    assert redis_client.closed is True


def test_lifespan_shutdown_with_no_task_and_no_close(monkeypatch) -> None:
    class RedisNoClose:
        async def ping(self) -> bool:
            return True

    redis_client = RedisNoClose()

    class RedisModule:
        @staticmethod
        def from_url(url: str, decode_responses: bool = True):
            _ = url
            _ = decode_responses
            return redis_client

    async def _ensure_group(_redis):
        return None

    def _create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(audit_worker_main, "redis", RedisModule)
    monkeypatch.setattr(audit_worker_main, "_ensure_group", _ensure_group)
    monkeypatch.setattr(audit_worker_main.asyncio, "create_task", _create_task)

    app = SimpleNamespace(state=SimpleNamespace())

    async def _run():
        async with audit_worker_main.lifespan(app):
            assert app.state.consumer_task is None

    asyncio.run(_run())


def test_lifespan_shutdown_with_sync_close(monkeypatch) -> None:
    class RedisSyncClose:
        def __init__(self) -> None:
            self.closed = False

        async def ping(self) -> bool:
            return True

        def close(self) -> None:
            self.closed = True

    redis_client = RedisSyncClose()

    class RedisModule:
        @staticmethod
        def from_url(url: str, decode_responses: bool = True):
            _ = url
            _ = decode_responses
            return redis_client

    async def _ensure_group(_redis):
        return None

    def _create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(audit_worker_main, "redis", RedisModule)
    monkeypatch.setattr(audit_worker_main, "_ensure_group", _ensure_group)
    monkeypatch.setattr(audit_worker_main.asyncio, "create_task", _create_task)

    app = SimpleNamespace(state=SimpleNamespace())

    async def _run():
        async with audit_worker_main.lifespan(app):
            pass

    asyncio.run(_run())
    assert redis_client.closed is True
