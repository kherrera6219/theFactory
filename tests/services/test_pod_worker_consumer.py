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
