import asyncio
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

pod_worker_main = importlib.import_module("pod_worker.main")


class FakeWorkerRedis:
    def __init__(self, entries):
        self.entries = entries
        self.acked: list[str] = []
        self.read_calls = 0

    async def xreadgroup(self, **kwargs):
        self.read_calls += 1
        if self.read_calls == 1:
            return [("missions.state", self.entries)]
        raise asyncio.CancelledError

    async def xack(self, stream: str, group: str, entry_id: str) -> int:
        self.acked.append(entry_id)
        return 1


def _build_app(redis_client: FakeWorkerRedis) -> SimpleNamespace:
    return SimpleNamespace(
        state=SimpleNamespace(
            redis=redis_client,
            processed=0,
            errors=0,
        )
    )


def test_consumer_acknowledges_invalid_message() -> None:
    redis_client = FakeWorkerRedis(entries=[("1-0", {})])
    app = _build_app(redis_client)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(pod_worker_main._consumer_loop(app))

    assert app.state.errors == 1
    assert redis_client.acked == ["1-0"]


def test_consumer_keeps_message_unacked_on_runtime_failure(monkeypatch) -> None:
    async def _raise_runtime_error(redis_obj, payload):
        raise RuntimeError("transient failure")

    monkeypatch.setattr(pod_worker_main, "_validate_envelope", lambda envelope: None)
    monkeypatch.setattr(pod_worker_main, "_handle_running_mission", _raise_runtime_error)

    fields = {
        "envelope": json.dumps({"topic": "cluster.assigned.podA"}),
        "payload": json.dumps({"event_type": "MISSION_RUNNING", "mission_id": "mission-1"}),
    }
    redis_client = FakeWorkerRedis(entries=[("1-0", fields)])
    app = _build_app(redis_client)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(pod_worker_main._consumer_loop(app))

    assert app.state.errors == 1
    assert redis_client.acked == []


def test_consumer_processes_running_mission_and_acks(monkeypatch) -> None:
    async def _handle(redis_obj, payload):
        _ = redis_obj
        _ = payload
        return None

    monkeypatch.setattr(pod_worker_main, "_validate_envelope", lambda envelope: None)
    monkeypatch.setattr(pod_worker_main, "_handle_running_mission", _handle)

    fields = {
        "envelope": json.dumps({"topic": "cluster.assigned.podA"}),
        "payload": json.dumps({"event_type": "MISSION_RUNNING", "mission_id": "mission-1"}),
    }
    redis_client = FakeWorkerRedis(entries=[("1-0", fields)])
    app = _build_app(redis_client)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(pod_worker_main._consumer_loop(app))

    assert app.state.processed == 1
    assert redis_client.acked == ["1-0"]


def test_consumer_acks_non_running_events_without_processing(monkeypatch) -> None:
    monkeypatch.setattr(pod_worker_main, "_validate_envelope", lambda envelope: None)
    fields = {
        "envelope": json.dumps({"topic": "cluster.assigned.podA"}),
        "payload": json.dumps({"event_type": "MISSION_COMPLETE", "mission_id": "mission-1"}),
    }
    redis_client = FakeWorkerRedis(entries=[("1-0", fields)])
    app = _build_app(redis_client)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(pod_worker_main._consumer_loop(app))

    assert app.state.processed == 0
    assert app.state.errors == 0
    assert redis_client.acked == ["1-0"]


def test_consumer_handles_empty_records_then_cancel(monkeypatch) -> None:
    monkeypatch.setattr(pod_worker_main, "_validate_envelope", lambda envelope: None)

    class EmptyThenCancelRedis(FakeWorkerRedis):
        async def xreadgroup(self, **kwargs):
            self.read_calls += 1
            if self.read_calls == 1:
                return []
            raise asyncio.CancelledError

    redis_client = EmptyThenCancelRedis(entries=[])
    app = _build_app(redis_client)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(pod_worker_main._consumer_loop(app))

    assert redis_client.acked == []


def test_consumer_recreates_missing_group(monkeypatch) -> None:
    recreated: list[str] = []

    class MissingGroupThenCancelRedis(FakeWorkerRedis):
        async def xreadgroup(self, **kwargs):
            self.read_calls += 1
            if self.read_calls == 1:
                raise pod_worker_main.ResponseError(
                    "NOGROUP No such key 'missions.state' "
                    "or consumer group 'dedicated-workers-podA'"
                )
            raise asyncio.CancelledError

    async def _ensure_group(redis_obj) -> None:
        recreated.append(redis_obj.__class__.__name__)

    monkeypatch.setattr(pod_worker_main, "_ensure_group", _ensure_group)
    redis_client = MissingGroupThenCancelRedis(entries=[])
    app = _build_app(redis_client)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(pod_worker_main._consumer_loop(app))

    assert recreated == ["MissingGroupThenCancelRedis"]
