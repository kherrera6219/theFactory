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

        async def post(self, *_args: Any, **_kwargs: Any) -> FakeResponse:
            return FakeResponse(self._status_code)

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
    assert asyncio.run(audit_worker_main.readyz())["ready"] is True

    audit_worker_main.app.state.redis = DownRedis()
    payload = asyncio.run(audit_worker_main.health())
    assert payload["ok"] is False
    with pytest.raises(audit_worker_main.HTTPException):
        asyncio.run(audit_worker_main.readyz())

    audit_worker_main.app.state.redis = None
    with pytest.raises(audit_worker_main.HTTPException):
        asyncio.run(audit_worker_main.readyz())
