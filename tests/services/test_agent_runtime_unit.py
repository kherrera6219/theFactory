import asyncio
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

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
