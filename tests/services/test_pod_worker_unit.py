import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

pod_worker_main = importlib.import_module("pod_worker.main")


class DummyResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeRedis:
    def __init__(self) -> None:
        self.xadd_calls: list[tuple[str, dict[str, str]]] = []

    async def xadd(self, stream: str, fields: dict[str, str], **kwargs) -> str:
        self.xadd_calls.append((stream, fields))
        return "1-0"


def test_parse_date_time() -> None:
    parsed = pod_worker_main._parse_date_time("2026-03-01T00:00:00Z")
    assert parsed.tzinfo is not None
    with pytest.raises(ValueError):
        pod_worker_main._parse_date_time("2026-03-01T00:00:00")


def test_validate_envelope_and_build(monkeypatch) -> None:
    schema = {
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
    monkeypatch.setattr(pod_worker_main, "_load_event_schema", lambda: schema)
    monkeypatch.setattr(pod_worker_main, "_load_topics", lambda: {"cluster.assigned.podA"})

    envelope = {
        "event_id": "evt-1",
        "topic": "cluster.assigned.podA",
        "timestamp": "2026-03-01T00:00:00+00:00",
        "producer": "pod-worker-podA",
        "correlation_id": "mission-1",
        "payload_ref": "registry://missions/mission-1",
        "schema": "pod.assignment.v1",
        "priority": "NORMAL",
    }
    pod_worker_main._validate_envelope(envelope)

    envelope["priority"] = "LOW"
    with pytest.raises(pod_worker_main.ProtocolValidationError):
        pod_worker_main._validate_envelope(envelope)

    monkeypatch.setattr(pod_worker_main, "_validate_envelope", lambda e: None)
    built = pod_worker_main._build_envelope(
        "cluster.assigned.podA",
        "mission-1",
        "registry://missions/mission-1",
        "pod.assignment.v1",
    )
    assert built["topic"] == "cluster.assigned.podA"


def test_publish_event(monkeypatch) -> None:
    redis_client = FakeRedis()
    monkeypatch.setattr(
        pod_worker_main,
        "_build_envelope",
        lambda **kwargs: {"event_id": "evt-1", "topic": kwargs["topic"]},
    )

    asyncio.run(
        pod_worker_main._publish_event(
            redis_client,
            "cluster.assigned.podA",
            "mission-1",
            {"mission_id": "mission-1"},
        )
    )
    assert redis_client.xadd_calls


def test_ensure_group_busygroup_and_error(monkeypatch) -> None:
    class BusyRedis:
        async def xgroup_create(self, **kwargs):
            raise pod_worker_main.ResponseError("BUSYGROUP already exists")

    asyncio.run(pod_worker_main._ensure_group(BusyRedis()))

    class ErrorRedis:
        async def xgroup_create(self, **kwargs):
            raise pod_worker_main.ResponseError("other error")

    with pytest.raises(pod_worker_main.ResponseError):
        asyncio.run(pod_worker_main._ensure_group(ErrorRedis()))


def test_has_assignment() -> None:
    async def _not_found(*_args, **_kwargs):
        return DummyResponse(404)

    async def _error(*_args, **_kwargs):
        return DummyResponse(500)

    async def _ok(*_args, **_kwargs):
        return DummyResponse(200, {"pod_name": "podA"})

    pod_worker_main._request = _not_found
    assert asyncio.run(pod_worker_main._has_assignment("mission-1")) is False
    pod_worker_main._request = _error
    assert asyncio.run(pod_worker_main._has_assignment("mission-1")) is False
    pod_worker_main._request = _ok
    assert asyncio.run(pod_worker_main._has_assignment("mission-1")) is True


def test_handle_running_mission_branches(monkeypatch) -> None:
    redis_client = FakeRedis()
    payload = {
        "mission_id": "mission-1",
        "requested_target_language": "python",
        "state": "RUNNING",
    }

    async def _has_assignment_false(_mission_id: str) -> bool:
        return False

    calls: list[tuple[str, str]] = []

    async def _request(method: str, path: str, **kwargs):
        calls.append((method, path))
        if path == "/internal/pod-assignment":
            return DummyResponse(200, {"ok": True})
        return DummyResponse(200, {"ok": True})

    published: list[str] = []

    async def _publish(redis_obj, topic: str, mission_id: str, payload_obj: dict[str, Any]):
        published.append(topic)

    monkeypatch.setattr(pod_worker_main, "_has_assignment", _has_assignment_false)
    monkeypatch.setattr(pod_worker_main, "_request", _request)
    monkeypatch.setattr(pod_worker_main, "_publish_event", _publish)

    asyncio.run(pod_worker_main._handle_running_mission(redis_client, payload))
    assert ("POST", "/internal/pod-assignment") in calls
    assert len(published) == 2

    async def _request_conflict(method: str, path: str, **kwargs):
        if path == "/internal/pod-assignment":
            return DummyResponse(409)
        return DummyResponse(200)

    published.clear()
    monkeypatch.setattr(pod_worker_main, "_request", _request_conflict)
    asyncio.run(pod_worker_main._handle_running_mission(redis_client, payload))
    assert published == []

    asyncio.run(pod_worker_main._handle_running_mission(redis_client, {"mission_id": ""}))
    asyncio.run(
        pod_worker_main._handle_running_mission(
            redis_client,
            {"mission_id": "mission-1", "requested_target_language": "rust"},
        )
    )


def test_health_function() -> None:
    class PingRedis:
        async def ping(self) -> bool:
            return True

    pod_worker_main.app.state.redis = PingRedis()
    pod_worker_main.app.state.processed = 3
    pod_worker_main.app.state.errors = 1
    result = asyncio.run(pod_worker_main.health())
    assert result["ok"] is True
    assert result["processed"] == 3


def test_loaders_raise_when_files_missing(monkeypatch, tmp_path: Path) -> None:
    missing_schema = tmp_path / "missing-schema.json"
    missing_topics = tmp_path / "missing-topics.yaml"
    monkeypatch.setattr(pod_worker_main, "EVENT_SCHEMA_PATH", missing_schema)
    monkeypatch.setattr(pod_worker_main, "TOPICS_PATH", missing_topics)

    with pytest.raises(pod_worker_main.ProtocolValidationError):
        pod_worker_main._load_event_schema()
    with pytest.raises(pod_worker_main.ProtocolValidationError):
        pod_worker_main._load_topics()
