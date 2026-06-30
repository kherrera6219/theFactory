import asyncio
import importlib
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "agent-runtime"))

agent_runtime_main = importlib.import_module("agent_runtime.main")


class DummyResponse:
    def __init__(self, status_code: int, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def reset_agent_runtime_circuit() -> None:
    agent_runtime_main._CIRCUIT.state = agent_runtime_main._CircuitBreaker.CLOSED
    agent_runtime_main._CIRCUIT._failures = 0
    agent_runtime_main._CIRCUIT._opened_at = 0.0


def test_event_types_for_agent_roles() -> None:
    pm = agent_runtime_main.make_agent("AGENT-01-PM")
    ceo = agent_runtime_main.make_agent("AGENT-02-CEO")
    tester = agent_runtime_main.make_agent("AGENT-10-TESTER")
    pod_audit = agent_runtime_main.make_agent("AGENT-13-PODA-AUDIT")
    deploy = agent_runtime_main.make_agent("AGENT-11-DEPLOY")

    assert agent_runtime_main._event_types_for_agent(pm) == {"MISSION_QUEUED"}
    assert agent_runtime_main._event_types_for_agent(ceo) == {"MISSION_PM_INTAKE"}
    assert agent_runtime_main._event_types_for_agent(tester) == {
        "MISSION_VERIFIED",
        "MISSION_FAILED",
    }
    assert agent_runtime_main._event_types_for_agent(pod_audit) == {
        "MISSION_VERIFIED",
        "MISSION_FAILED",
    }
    assert agent_runtime_main._event_types_for_agent(deploy) == {"MISSION_COMPLETE"}


def test_hw_agent_filters_non_system_languages() -> None:
    agent = agent_runtime_main.make_agent("AGENT-09-HW")
    assert agent_runtime_main._agent_supports_language(agent, "rust") is True
    assert agent_runtime_main._agent_supports_language(agent, "python") is False


def test_pod_name_matches_for_pod_audit() -> None:
    pod_audit = agent_runtime_main.make_agent("AGENT-13-PODA-AUDIT")
    assert (
        agent_runtime_main._pod_name_matches(pod_audit, {"pod_name": "poda"}) is True
    )
    assert (
        agent_runtime_main._pod_name_matches(pod_audit, {"pod_name": "podb"}) is False
    )
    assert agent_runtime_main._pod_name_matches(pod_audit, None) is False


def test_run_agent_pipeline_returns_report_payload() -> None:
    agent = agent_runtime_main.make_agent("AGENT-01-PM")
    pipeline = agent_runtime_main._run_agent_pipeline(
        agent,
        mission_id="mission-1",
        payload={"prompt": "hello"},
    )
    assert pipeline["report"].to_dict()["verdict"] == "PASS"


def test_process_event_for_support_agent(monkeypatch) -> None:
    monkeypatch.setattr(agent_runtime_main, "WORKER_AGENT_ID", "AGENT-03-BROKER")

    async def _fetch_mission_snapshot(_mission_id: str):
        return {
            "mission_id": "mission-1",
            "requested_target_language": "python",
            "metadata": {},
        }

    async def _fetch_pod_assignment(_mission_id: str):
        return {"pod_name": "poda"}

    async def _fetch_logicnodes(_mission_id: str):
        return []

    posted: list[str] = []

    async def _post_agent_heartbeat(**kwargs):
        posted.append(f"heartbeat:{kwargs['state']}")
        return True

    async def _persist_pipeline_output(**kwargs):
        posted.append(f"persist:{kwargs['agent'].agent_id}")

    monkeypatch.setattr(agent_runtime_main, "_fetch_mission_snapshot", _fetch_mission_snapshot)
    monkeypatch.setattr(agent_runtime_main, "_fetch_pod_assignment", _fetch_pod_assignment)
    monkeypatch.setattr(agent_runtime_main, "_fetch_logicnodes", _fetch_logicnodes)
    monkeypatch.setattr(agent_runtime_main, "_post_agent_heartbeat", _post_agent_heartbeat)
    monkeypatch.setattr(agent_runtime_main, "_persist_pipeline_output", _persist_pipeline_output)

    processed = asyncio.run(
        agent_runtime_main._process_event(
            {"mission_id": "mission-1", "event_type": "MISSION_RUNNING"}
        )
    )
    assert processed is True
    assert posted == ["heartbeat:RUNNING", "persist:AGENT-03-BROKER", "heartbeat:ACTIVE"]


def test_consumer_acks_invalid_message(monkeypatch) -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.acked: list[str] = []
            self.calls = 0

        async def xreadgroup(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return [("missions.state", [("1-0", {})])]
            raise asyncio.CancelledError

        async def xack(self, stream: str, group: str, entry_id: str) -> int:
            self.acked.append(entry_id)
            return 1

    redis_client = FakeRedis()
    app = SimpleNamespace(state=SimpleNamespace(redis=redis_client, processed=0, errors=0))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(agent_runtime_main._consumer_loop(app))

    assert app.state.errors == 1
    assert redis_client.acked == ["1-0"]


def test_consumer_recreates_missing_group(monkeypatch) -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.calls = 0

        async def xreadgroup(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise agent_runtime_main.ResponseError("NOGROUP no such key")
            raise asyncio.CancelledError

    recreated: list[bool] = []

    async def _ensure_group(_redis):
        recreated.append(True)

    monkeypatch.setattr(agent_runtime_main, "_ensure_group", _ensure_group)
    redis_client = FakeRedis()
    app = SimpleNamespace(state=SimpleNamespace(redis=redis_client, processed=0, errors=0))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(agent_runtime_main._consumer_loop(app))

    assert recreated == [True]


def test_health_payload(monkeypatch) -> None:
    monkeypatch.setattr(agent_runtime_main, "WORKER_AGENT_ID", "AGENT-01-PM")

    class PingRedis:
        async def ping(self) -> bool:
            return True

    agent_runtime_main.app.state.redis = PingRedis()
    agent_runtime_main.app.state.processed = 2
    agent_runtime_main.app.state.errors = 1
    payload = asyncio.run(agent_runtime_main.health())
    assert payload["ok"] is True
    assert payload["worker_agent_id"] == "AGENT-01-PM"
    assert payload["processed"] == 2


def test_worker_agent_requires_binding(monkeypatch) -> None:
    monkeypatch.setattr(agent_runtime_main, "WORKER_AGENT_ID", "")
    with pytest.raises(RuntimeError, match="WORKER_AGENT_ID is required"):
        agent_runtime_main._worker_agent()


def test_request_retries_until_success(monkeypatch) -> None:
    real_sleep = asyncio.sleep
    monkeypatch.setattr(agent_runtime_main, "WORKER_AGENT_ID", "AGENT-03-BROKER")
    monkeypatch.setattr(agent_runtime_main, "SERVICE_API_KEY", "svc-key")
    monkeypatch.setattr(agent_runtime_main, "REQUEST_MAX_RETRIES", 3)
    monkeypatch.setattr(agent_runtime_main, "ORCHESTRATOR_URL", "http://orchestrator.test")
    monkeypatch.setattr(
        agent_runtime_main.asyncio,
        "sleep",
        lambda *_args, **_kwargs: real_sleep(0),
    )

    calls: list[tuple[str, str, dict[str, str]]] = []
    responses = [DummyResponse(500), DummyResponse(200, {"ok": True})]

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method, url, json=None, params=None, headers=None):
            calls.append((method, url, headers or {}))
            return responses.pop(0)

    monkeypatch.setattr(agent_runtime_main.httpx, "AsyncClient", lambda timeout: FakeAsyncClient())

    response = asyncio.run(agent_runtime_main._request("GET", "/missions/mission-1"))
    assert response.status_code == 200
    assert calls[0][1] == "http://orchestrator.test/missions/mission-1"
    assert calls[0][2]["x-api-key"] == "svc-key"
    assert calls[0][2]["x-agent-id"] == "AGENT-03-BROKER"


def test_request_returns_last_response_or_last_error(monkeypatch) -> None:
    real_sleep = asyncio.sleep
    monkeypatch.setattr(agent_runtime_main, "WORKER_AGENT_ID", "AGENT-03-BROKER")
    monkeypatch.setattr(agent_runtime_main, "REQUEST_MAX_RETRIES", 2)
    monkeypatch.setattr(
        agent_runtime_main.asyncio,
        "sleep",
        lambda *_args, **_kwargs: real_sleep(0),
    )

    class ResponseClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, *args, **kwargs):
            return DummyResponse(503)

    monkeypatch.setattr(agent_runtime_main.httpx, "AsyncClient", lambda timeout: ResponseClient())
    response = asyncio.run(agent_runtime_main._request("GET", "/health"))
    assert response.status_code == 503

    class ErrorClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, *args, **kwargs):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(agent_runtime_main.httpx, "AsyncClient", lambda timeout: ErrorClient())
    with pytest.raises(httpx.ConnectError):
        asyncio.run(agent_runtime_main._request("GET", "/health"))

    with pytest.raises(ValueError, match="path must start"):
        asyncio.run(agent_runtime_main._request("GET", "health"))


def test_fetch_helpers_and_safe_to_dict(monkeypatch) -> None:
    async def _request(method, path, **kwargs):
        if path.endswith("/pod-assignment"):
            return DummyResponse(200, {"pod_name": "podA"})
        if path == "/v1/operations/logicnodes":
            return DummyResponse(200, [{"node_id": "n-1"}, "ignore-me"])
        return DummyResponse(200, {"mission_id": "mission-1"})

    monkeypatch.setattr(agent_runtime_main, "_request", _request)

    assert asyncio.run(agent_runtime_main._fetch_mission_snapshot("mission-1")) == {
        "mission_id": "mission-1"
    }
    assert asyncio.run(agent_runtime_main._fetch_pod_assignment("mission-1")) == {
        "pod_name": "podA"
    }
    assert asyncio.run(agent_runtime_main._fetch_logicnodes("mission-1")) == [{"node_id": "n-1"}]

    async def _bad_request(method, path, **kwargs):
        return DummyResponse(500, ["wrong-shape"])

    monkeypatch.setattr(agent_runtime_main, "_request", _bad_request)
    assert asyncio.run(agent_runtime_main._fetch_mission_snapshot("mission-1")) is None
    assert asyncio.run(agent_runtime_main._fetch_pod_assignment("mission-1")) is None
    assert asyncio.run(agent_runtime_main._fetch_logicnodes("mission-1")) == []

    class Dictable:
        def to_dict(self):
            return {"ok": True}

    class BadDictable:
        def to_dict(self):
            return "not-a-dict"

    assert agent_runtime_main._safe_to_dict(Dictable()) == {"ok": True}
    assert agent_runtime_main._safe_to_dict(BadDictable()) == {}


def test_post_agent_heartbeat_and_persist_pipeline_output(monkeypatch) -> None:
    calls: list[tuple[str, str, dict[str, object] | None]] = []
    monkeypatch.setattr(agent_runtime_main, "WORKER_AGENT_ID", "AGENT-13-PODA-AUDIT")

    async def _request(method, path, **kwargs):
        calls.append((method, path, kwargs.get("json_body")))
        return DummyResponse(200)

    monkeypatch.setattr(agent_runtime_main, "_request", _request)
    assert asyncio.run(
        agent_runtime_main._post_agent_heartbeat(
            state="RUNNING", mission_id="mission-1", metadata={"source": "test"}
        )
    ) is True

    class Payload:
        def __init__(self, payload):
            self._payload = payload

        def to_dict(self):
            return self._payload

    audit_agent = agent_runtime_main.make_agent("AGENT-13-PODA-AUDIT")
    pipeline = {
        "report": Payload({"verdict": "PASS", "summary": "ok"}),
        "validation": Payload({"issues": []}),
        "result": Payload({"artifact": "x"}),
    }
    asyncio.run(
        agent_runtime_main._persist_pipeline_output(
            agent=audit_agent, mission_id="mission-1", pipeline=pipeline
        )
    )
    assert any(path == "/internal/audit-reports" for _, path, _ in calls)

    calls.clear()
    knowledge_agent = agent_runtime_main.make_agent("AGENT-03-BROKER")
    asyncio.run(
        agent_runtime_main._persist_pipeline_output(
            agent=knowledge_agent, mission_id="mission-1", pipeline=pipeline
        )
    )
    assert any(path == "/internal/knowledge" for _, path, _ in calls)


@pytest.mark.parametrize(
    ("payload", "mission_payload", "pod_assignment", "expected"),
    [
        (
            {},
            {"mission_id": "mission-1", "requested_target_language": "python"},
            {"pod_name": "poda"},
            False,
        ),
        (
            {"mission_id": "mission-1", "event_type": "MISSION_FAILED"},
            {"mission_id": "mission-1", "requested_target_language": "python"},
            {"pod_name": "poda"},
            False,
        ),
        (
            {"mission_id": "mission-1", "event_type": "MISSION_RUNNING"},
            None,
            {"pod_name": "poda"},
            False,
        ),
        (
            {"mission_id": "mission-1", "event_type": "MISSION_RUNNING"},
            {"mission_id": "mission-1", "requested_target_language": "python"},
            {"pod_name": "poda"},
            False,
        ),
        (
            {"mission_id": "mission-1", "event_type": "MISSION_VERIFIED"},
            {"mission_id": "mission-1", "requested_target_language": "python"},
            {"pod_name": "podb"},
            False,
        ),
    ],
)
def test_process_event_short_circuits(
    monkeypatch,
    payload,
    mission_payload,
    pod_assignment,
    expected,
) -> None:
    worker_id = "AGENT-09-HW" if mission_payload else "AGENT-03-BROKER"
    if payload.get("event_type") == "MISSION_VERIFIED":
        worker_id = "AGENT-13-PODA-AUDIT"
    monkeypatch.setattr(agent_runtime_main, "WORKER_AGENT_ID", worker_id)

    async def _fetch_mission_snapshot(_mission_id):
        return mission_payload

    async def _fetch_pod_assignment(_mission_id):
        return pod_assignment

    monkeypatch.setattr(agent_runtime_main, "_fetch_mission_snapshot", _fetch_mission_snapshot)
    monkeypatch.setattr(agent_runtime_main, "_fetch_pod_assignment", _fetch_pod_assignment)
    monkeypatch.setattr(
        agent_runtime_main,
        "_fetch_logicnodes",
        lambda _mission_id: asyncio.sleep(0, result=[]),
    )
    monkeypatch.setattr(
        agent_runtime_main,
        "_post_agent_heartbeat",
        lambda **_: asyncio.sleep(0, result=True),
    )
    monkeypatch.setattr(
        agent_runtime_main,
        "_persist_pipeline_output",
        lambda **_: asyncio.sleep(0),
    )

    assert asyncio.run(agent_runtime_main._process_event(payload)) is expected


def test_process_event_for_pod_audit_fetches_logicnodes(monkeypatch) -> None:
    monkeypatch.setattr(agent_runtime_main, "WORKER_AGENT_ID", "AGENT-13-PODA-AUDIT")

    async def _fetch_mission_snapshot(_mission_id):
        return {"mission_id": "mission-1", "requested_target_language": "python"}

    async def _fetch_pod_assignment(_mission_id):
        return {"pod_name": "poda"}

    logicnode_calls: list[str] = []
    persisted: list[dict[str, object]] = []

    async def _fetch_logicnodes(_mission_id):
        logicnode_calls.append(_mission_id)
        return [{"node_id": "n-1"}]

    async def _post_agent_heartbeat(**kwargs):
        return True

    async def _persist_pipeline_output(**kwargs):
        persisted.append(kwargs["pipeline"])

    monkeypatch.setattr(agent_runtime_main, "_fetch_mission_snapshot", _fetch_mission_snapshot)
    monkeypatch.setattr(agent_runtime_main, "_fetch_pod_assignment", _fetch_pod_assignment)
    monkeypatch.setattr(agent_runtime_main, "_fetch_logicnodes", _fetch_logicnodes)
    monkeypatch.setattr(agent_runtime_main, "_post_agent_heartbeat", _post_agent_heartbeat)
    monkeypatch.setattr(agent_runtime_main, "_persist_pipeline_output", _persist_pipeline_output)

    assert asyncio.run(
        agent_runtime_main._process_event(
            {"mission_id": "mission-1", "event_type": "MISSION_VERIFIED"}
        )
    ) is True
    assert logicnode_calls == ["mission-1"]
    assert persisted


def test_ensure_group_handles_busygroup_and_other_errors() -> None:
    class BusyRedis:
        async def xgroup_create(self, **kwargs):
            raise agent_runtime_main.ResponseError("BUSYGROUP Consumer Group name already exists")

    asyncio.run(agent_runtime_main._ensure_group(BusyRedis()))

    class FailingRedis:
        async def xgroup_create(self, **kwargs):
            raise agent_runtime_main.ResponseError("other failure")

    with pytest.raises(agent_runtime_main.ResponseError):
        asyncio.run(agent_runtime_main._ensure_group(FailingRedis()))


def test_consumer_loop_handles_processed_and_runtime_error(monkeypatch) -> None:
    class FakeRedis:
        def __init__(self):
            self.acked: list[str] = []
            self.calls = 0

        async def xreadgroup(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return [
                    (
                        "missions.state",
                        [
                            ("1-0", {"envelope": "{}", "payload": '{"mission_id":"mission-1"}'}),
                            ("2-0", {"envelope": "{}", "payload": '{"mission_id":"mission-2"}'}),
                        ],
                    )
                ]
            raise asyncio.CancelledError

        async def xack(self, stream: str, group: str, entry_id: str) -> int:
            self.acked.append(entry_id)
            return 1

    outcomes = [True, RuntimeError("boom")]

    async def _process_event(payload):
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(agent_runtime_main, "_validate_envelope", lambda envelope: None)
    monkeypatch.setattr(agent_runtime_main, "_process_event", _process_event)
    redis_client = FakeRedis()
    app = SimpleNamespace(state=SimpleNamespace(redis=redis_client, processed=0, errors=0))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(agent_runtime_main._consumer_loop(app))

    assert app.state.processed == 1
    assert app.state.errors == 1
    assert redis_client.acked == ["1-0"]


def test_consumer_loop_keeps_failed_processing_entry_unacked(monkeypatch) -> None:
    class FakeRedis:
        def __init__(self):
            self.acked: list[str] = []
            self.calls = 0

        async def xreadgroup(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return [
                    (
                        "missions.state",
                        [
                            (
                                "1-0",
                                {
                                    "envelope": "{}",
                                    "payload": (
                                        '{"mission_id":"mission-1",'
                                        '"event_type":"MISSION_RUNNING"}'
                                    ),
                                },
                            )
                        ],
                    )
                ]
            raise asyncio.CancelledError

        async def xack(self, stream: str, group: str, entry_id: str) -> int:
            self.acked.append(entry_id)
            return 1

    async def _process_event(_payload):
        raise RuntimeError("worker processing down")

    monkeypatch.setattr(agent_runtime_main, "_validate_envelope", lambda envelope: None)
    monkeypatch.setattr(agent_runtime_main, "_process_event", _process_event)
    redis_client = FakeRedis()
    app = SimpleNamespace(state=SimpleNamespace(redis=redis_client, processed=0, errors=0))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(agent_runtime_main._consumer_loop(app))

    assert app.state.processed == 0
    assert app.state.errors == 1
    assert redis_client.acked == []


def test_heartbeat_loop_logs_failures_and_rethrows_cancel(monkeypatch, caplog) -> None:
    monkeypatch.setattr(agent_runtime_main, "WORKER_AGENT_ID", "AGENT-03-BROKER")

    async def _post_agent_heartbeat(**kwargs):
        raise RuntimeError("heartbeat failed")

    async def _cancel_sleep(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(agent_runtime_main, "_post_agent_heartbeat", _post_agent_heartbeat)
    monkeypatch.setattr(agent_runtime_main.asyncio, "sleep", _cancel_sleep)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(agent_runtime_main._heartbeat_loop(SimpleNamespace()))

    assert "failed to emit agent-runtime heartbeat" in caplog.text


@pytest.mark.asyncio
async def test_lifespan_initializes_and_closes(monkeypatch) -> None:
    class FakeRedis:
        def __init__(self):
            self.closed = False

        async def ping(self):
            return True

        async def aclose(self):
            self.closed = True

    redis_client = FakeRedis()
    monkeypatch.setattr(agent_runtime_main, "WORKER_AGENT_ID", "AGENT-03-BROKER")
    monkeypatch.setattr(agent_runtime_main.redis, "from_url", lambda *args, **kwargs: redis_client)
    monkeypatch.setattr(agent_runtime_main, "_ensure_group", lambda _redis: asyncio.sleep(0))

    async def _loop(_app):
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise

    monkeypatch.setattr(agent_runtime_main, "_consumer_loop", _loop)
    monkeypatch.setattr(agent_runtime_main, "_heartbeat_loop", _loop)

    app = SimpleNamespace(state=SimpleNamespace())
    async with agent_runtime_main.lifespan(app):
        assert app.state.redis is redis_client
        assert app.state.consumer_task is not None
        assert app.state.heartbeat_task is not None

    assert redis_client.closed is True


@pytest.mark.asyncio
async def test_lifespan_requires_worker_agent_binding(monkeypatch) -> None:
    monkeypatch.setattr(agent_runtime_main, "WORKER_AGENT_ID", "")

    app = SimpleNamespace(state=SimpleNamespace())
    with pytest.raises(RuntimeError, match="WORKER_AGENT_ID is required"):
        async with agent_runtime_main.lifespan(app):
            pass


def test_health_and_readyz_failure_paths(monkeypatch) -> None:
    monkeypatch.setattr(agent_runtime_main, "WORKER_AGENT_ID", "AGENT-01-PM")

    class FailingRedis:
        async def ping(self):
            raise RuntimeError("offline")

    agent_runtime_main.app.state.redis = FailingRedis()
    agent_runtime_main.app.state.processed = 0
    agent_runtime_main.app.state.errors = 0
    payload = asyncio.run(agent_runtime_main.health())
    assert payload["ok"] is False

    agent_runtime_main.app.state.redis = None
    with pytest.raises(agent_runtime_main.HTTPException) as missing_redis:
        asyncio.run(agent_runtime_main.readyz())
    assert missing_redis.value.status_code == 503

    agent_runtime_main.app.state.redis = FailingRedis()
    with pytest.raises(agent_runtime_main.HTTPException) as failing_redis:
        asyncio.run(agent_runtime_main.readyz())
    assert failing_redis.value.status_code == 503

    class FalseRedis:
        async def ping(self):
            return False

    agent_runtime_main.app.state.redis = FalseRedis()
    with pytest.raises(agent_runtime_main.HTTPException) as false_redis:
        asyncio.run(agent_runtime_main.readyz())
    assert false_redis.value.status_code == 503

    class HealthyRedis:
        async def ping(self):
            return True

    agent_runtime_main.app.state.redis = HealthyRedis()
    ready = asyncio.run(agent_runtime_main.readyz())
    assert ready["ready"] is True
