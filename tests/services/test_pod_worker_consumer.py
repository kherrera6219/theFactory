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
    def __init__(self, entries, *, xadd_error: Exception | None = None):
        self.entries = entries
        self.acked: list[str] = []
        self.dlq_writes: list[dict] = []
        self.read_calls = 0
        self._xadd_error = xadd_error

    async def xreadgroup(self, **kwargs):
        self.read_calls += 1
        if self.read_calls == 1:
            return [("missions.state", self.entries)]
        raise asyncio.CancelledError

    async def xack(self, stream: str, group: str, entry_id: str) -> int:
        self.acked.append(entry_id)
        return 1

    async def xadd(self, stream: str, fields: dict, **kwargs) -> str:
        if self._xadd_error is not None:
            raise self._xadd_error
        self.dlq_writes.append(fields)
        return f"{len(self.dlq_writes)}-0"


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


def test_consumer_dlqs_and_acks_message_on_unexpected_runtime_failure(monkeypatch) -> None:
    # Regression: an exception outside the four explicitly-handled types used
    # to be neither acknowledged nor DLQ'd. Since nothing in this consumer
    # loop ever XCLAIMs/XAUTOCLAIMs pending entries, that permanently
    # orphaned the message in the consumer group's PEL -- never processed
    # again, never visible in the DLQ, no operator signal beyond one log
    # line. It must now land in the DLQ and be acknowledged.
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
    assert redis_client.acked == ["1-0"]
    assert len(redis_client.dlq_writes) == 1
    assert redis_client.dlq_writes[0]["entry_id"] == "1-0"
    assert "transient failure" in redis_client.dlq_writes[0]["error"]


def test_consumer_keeps_message_unacked_when_dlq_write_fails(monkeypatch) -> None:
    # Regression: acknowledging (XACK) the original entry regardless of
    # whether the DLQ write actually succeeded silently loses the message
    # forever if Redis is briefly unavailable during the DLQ xadd -- the
    # entry is removed from the pending-entries list without ever landing
    # in the DLQ, with only a log line as a trace. It must stay unacknowledged
    # so it remains visible via XPENDING.
    async def _raise_runtime_error(redis_obj, payload):
        raise RuntimeError("transient failure")

    monkeypatch.setattr(pod_worker_main, "_validate_envelope", lambda envelope: None)
    monkeypatch.setattr(pod_worker_main, "_handle_running_mission", _raise_runtime_error)

    fields = {
        "envelope": json.dumps({"topic": "cluster.assigned.podA"}),
        "payload": json.dumps({"event_type": "MISSION_RUNNING", "mission_id": "mission-1"}),
    }
    redis_client = FakeWorkerRedis(
        entries=[("1-0", fields)], xadd_error=ConnectionError("redis blip")
    )
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


def test_pod_manager_assignment_skips_missing_mission_id() -> None:
    asyncio.run(
        pod_worker_main._handle_pod_manager_assignment(None, {"mission_id": ""})
    )


def test_pod_manager_assignment_skips_unsupported_language(monkeypatch) -> None:
    monkeypatch.setattr(
        pod_worker_main, "_mission_targets_supported_language", lambda lang: False
    )
    asyncio.run(
        pod_worker_main._handle_pod_manager_assignment(
            None,
            {"mission_id": "m-1", "requested_target_language": "cobol"},
        )
    )


def test_pod_manager_assignment_skips_binding_mismatch(monkeypatch) -> None:
    async def _no_match(mission_id, payload) -> bool:
        return False

    monkeypatch.setattr(
        pod_worker_main, "_mission_targets_supported_language", lambda lang: True
    )
    monkeypatch.setattr(pod_worker_main, "_mission_matches_agent_binding", _no_match)
    asyncio.run(
        pod_worker_main._handle_pod_manager_assignment(
            None,
            {"mission_id": "m-1", "requested_target_language": "python"},
        )
    )


def test_pod_manager_assignment_skips_unbound_agent(monkeypatch) -> None:
    async def _match(mission_id, payload) -> bool:
        return True

    async def _snapshot(mission_id):
        return {"metadata": {}}

    monkeypatch.setattr(
        pod_worker_main, "_mission_targets_supported_language", lambda lang: True
    )
    monkeypatch.setattr(pod_worker_main, "_mission_matches_agent_binding", _match)
    monkeypatch.setattr(pod_worker_main, "_fetch_mission_snapshot", _snapshot)
    monkeypatch.setattr(pod_worker_main, "_agent_id_from_payload", lambda payload: None)
    monkeypatch.setattr(pod_worker_main, "_agent_id_from_metadata", lambda metadata: None)

    async def _no_agent(mission_id):
        return None

    monkeypatch.setattr(pod_worker_main, "_fetch_mission_agent_id", _no_agent)
    monkeypatch.setattr(
        pod_worker_main, "_default_agent_id_for_event", lambda event, lang: None
    )
    asyncio.run(
        pod_worker_main._handle_pod_manager_assignment(
            None,
            {"mission_id": "m-1", "requested_target_language": "python"},
        )
    )


def test_pod_manager_assignment_returns_when_already_assigned(monkeypatch) -> None:
    heartbeats: list[str] = []

    async def _match(mission_id, payload) -> bool:
        return True

    async def _snapshot(mission_id):
        return {"metadata": {}}

    async def _heartbeat(**kwargs) -> bool:
        heartbeats.append(kwargs.get("state", ""))
        return True

    async def _assigned(mission_id) -> bool:
        return True

    monkeypatch.setattr(
        pod_worker_main, "_mission_targets_supported_language", lambda lang: True
    )
    monkeypatch.setattr(pod_worker_main, "_mission_matches_agent_binding", _match)
    monkeypatch.setattr(pod_worker_main, "_fetch_mission_snapshot", _snapshot)
    monkeypatch.setattr(
        pod_worker_main, "_agent_id_from_payload", lambda payload: "AGENT-15-PY"
    )
    monkeypatch.setattr(pod_worker_main, "_post_agent_heartbeat", _heartbeat)
    monkeypatch.setattr(pod_worker_main, "_has_assignment", _assigned)
    asyncio.run(
        pod_worker_main._handle_pod_manager_assignment(
            None,
            {"mission_id": "m-1", "requested_target_language": "python"},
        )
    )

    assert heartbeats == ["RUNNING"]


def test_pod_manager_assignment_full_pipeline(monkeypatch) -> None:
    heartbeats: list[str] = []
    audit_events: list[str] = []
    published: list[str] = []
    requests: list[tuple[str, str]] = []

    async def _match(mission_id, payload) -> bool:
        return True

    async def _snapshot(mission_id):
        return {"metadata": {"assigned_specialist_agent_id": "AGENT-16-PY"}}

    async def _heartbeat(**kwargs) -> bool:
        heartbeats.append(kwargs.get("state", ""))
        return True

    async def _not_assigned(mission_id) -> bool:
        return False

    async def _request(method, path, **kwargs):
        requests.append((method, path))
        return SimpleNamespace(status_code=200, json=lambda: {})

    async def _emit_audit(**kwargs) -> None:
        audit_events.append(kwargs.get("event_type", ""))

    async def _publish(redis_obj, channel, mission_id, payload) -> None:
        published.append(channel)

    def _pipeline(**kwargs):
        return {
            "agent": SimpleNamespace(category="pod_manager"),
            "result": {},
            "validation": {"ok": True},
            "report": {"summary": "done"},
            "logicnodes": [],
        }

    monkeypatch.setattr(
        pod_worker_main, "_mission_targets_supported_language", lambda lang: True
    )
    monkeypatch.setattr(pod_worker_main, "_mission_matches_agent_binding", _match)
    monkeypatch.setattr(pod_worker_main, "_fetch_mission_snapshot", _snapshot)
    monkeypatch.setattr(
        pod_worker_main, "_agent_id_from_payload", lambda payload: "AGENT-15-PY"
    )
    monkeypatch.setattr(pod_worker_main, "_post_agent_heartbeat", _heartbeat)
    monkeypatch.setattr(pod_worker_main, "_has_assignment", _not_assigned)
    monkeypatch.setattr(pod_worker_main, "_request", _request)
    monkeypatch.setattr(pod_worker_main, "_emit_audit_event", _emit_audit)
    monkeypatch.setattr(pod_worker_main, "_publish_event", _publish)
    monkeypatch.setattr(pod_worker_main, "_run_agent_pipeline", _pipeline)

    asyncio.run(
        pod_worker_main._handle_pod_manager_assignment(
            None,
            {"mission_id": "m-1", "requested_target_language": "python"},
        )
    )

    assert heartbeats == ["RUNNING", "ACTIVE"]
    assert "AGENT_EXECUTION_STARTED" in audit_events
    assert "AGENT_EXECUTION_COMPLETED" in audit_events
    assert "AGENT_REPORT_PERSISTED" in audit_events
    assert any(channel.startswith("cluster.assigned.") for channel in published)


def test_pod_manager_assignment_skips_on_assignment_conflict(monkeypatch) -> None:
    async def _match(mission_id, payload) -> bool:
        return True

    async def _snapshot(mission_id):
        return {"metadata": {}}

    async def _heartbeat(**kwargs) -> bool:
        return True

    async def _not_assigned(mission_id) -> bool:
        return False

    async def _request(method, path, **kwargs):
        return SimpleNamespace(status_code=409, json=lambda: {})

    monkeypatch.setattr(
        pod_worker_main, "_mission_targets_supported_language", lambda lang: True
    )
    monkeypatch.setattr(pod_worker_main, "_mission_matches_agent_binding", _match)
    monkeypatch.setattr(pod_worker_main, "_fetch_mission_snapshot", _snapshot)
    monkeypatch.setattr(
        pod_worker_main, "_agent_id_from_payload", lambda payload: "AGENT-15-PY"
    )
    monkeypatch.setattr(pod_worker_main, "_post_agent_heartbeat", _heartbeat)
    monkeypatch.setattr(pod_worker_main, "_has_assignment", _not_assigned)
    monkeypatch.setattr(pod_worker_main, "_request", _request)

    asyncio.run(
        pod_worker_main._handle_pod_manager_assignment(
            None,
            {"mission_id": "m-1", "requested_target_language": "python"},
        )
    )
