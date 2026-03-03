import asyncio
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

orchestrator_langgraph = importlib.import_module("orchestrator.langgraph_lifecycle")
orchestrator_models = importlib.import_module("orchestrator.models")
orchestrator_settings = importlib.import_module("orchestrator.settings")

MissionRecord = orchestrator_models.MissionRecord
MissionState = orchestrator_models.MissionState
Settings = orchestrator_settings.Settings
langgraph_lifecycle = orchestrator_langgraph


def _settings(**overrides: Any) -> Settings:
    base = Settings(
        redis_url="redis://redis:6379/0",
        postgres_url="postgresql://postgres:postgres@postgres:5432/ulr",
        intake_stream="missions.intake",
        state_stream="missions.state",
        max_stream_len=1000,
        consumer_group="orchestrator",
        consumer_name="orchestrator-test",
        auto_transition_enabled=True,
        transition_step_seconds=0.01,
        intake_topic="intake.feature_contract.created",
        default_priority="NORMAL",
        producer_name="orchestrator",
        event_schema_path=ROOT / "schemas" / "event.envelope.schema.json",
        topics_path=ROOT / "protocol" / "topics.yaml",
        admin_api_key="admin-key",
        internal_service_api_key="worker-key",
        readonly_api_key="viewer-key",
        extra_api_keys="",
    )
    return Settings(**{**base.__dict__, **overrides})


def _mission_record(state: MissionState) -> MissionRecord:
    return MissionRecord(
        mission_id="mission-1",
        prompt="Build API",
        requested_target_language="python",
        metadata={"source": "test"},
        state=state,
        created_at="2026-03-01T00:00:00+00:00",
    )


def _app_state(**overrides: Any) -> Any:
    defaults = {
        "redis_ready": True,
        "redis": object(),
    }
    defaults.update(overrides)
    return SimpleNamespace(state=SimpleNamespace(**defaults))


class FakeCompiledGraph:
    def __init__(self, nodes: dict[str, Any], conditionals: dict[str, Any], end_token: Any) -> None:
        self._nodes = nodes
        self._conditionals = conditionals
        self._end_token = end_token
        self.calls: list[tuple[dict[str, Any], dict[str, Any] | None]] = []

    async def ainvoke(
        self,
        state: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append((state, config))
        current = "queued_to_running"
        while True:
            state = await self._nodes[current](state)
            if current in self._conditionals:
                next_node = self._conditionals[current](state)
                if next_node == self._end_token:
                    break
                current = next_node
                continue
            break
        return state


class FakeStateGraph:
    last_instance: "FakeStateGraph | None" = None

    def __init__(self, _state_type: Any) -> None:
        self.nodes: dict[str, Any] = {}
        self.conditionals: dict[str, Any] = {}
        self.edges: list[tuple[Any, Any]] = []
        self.checkpointer: Any = None
        self.compiled = FakeCompiledGraph(self.nodes, self.conditionals, langgraph_lifecycle.END)
        FakeStateGraph.last_instance = self

    def add_node(self, name: str, fn: Any) -> None:
        self.nodes[name] = fn

    def add_edge(self, start: Any, end: Any) -> None:
        self.edges.append((start, end))

    def add_conditional_edges(self, name: str, router: Any) -> None:
        self.conditionals[name] = router

    def compile(self, checkpointer: Any = None) -> FakeCompiledGraph:
        self.checkpointer = checkpointer
        return self.compiled


def test_maybe_advance_returns_false_when_disabled() -> None:
    advanced = asyncio.run(
        langgraph_lifecycle.maybe_advance_mission_lifecycle(
            app=_app_state(),
            mission_id="mission-1",
            settings=_settings(langgraph_enabled=False),
            validator=object(),
            emit_state_event_fn=lambda **_kwargs: asyncio.sleep(0),
        )
    )
    assert advanced is False


def test_maybe_advance_returns_false_when_dependency_missing(monkeypatch) -> None:
    monkeypatch.setattr(langgraph_lifecycle, "StateGraph", None)
    advanced = asyncio.run(
        langgraph_lifecycle.maybe_advance_mission_lifecycle(
            app=_app_state(),
            mission_id="mission-1",
            settings=_settings(langgraph_enabled=True),
            validator=object(),
            emit_state_event_fn=lambda **_kwargs: asyncio.sleep(0),
        )
    )
    assert advanced is False


def test_maybe_advance_executes_graph_and_emits(monkeypatch) -> None:
    monkeypatch.setattr(langgraph_lifecycle, "StateGraph", FakeStateGraph)
    monkeypatch.setattr(
        langgraph_lifecycle.storage,
        "transition_mission_state",
        lambda _settings_obj, _mission_id, _expected, new_state, _event: _mission_record(new_state),
    )

    emitted: list[str] = []

    async def _emit(**kwargs) -> None:
        emitted.append(kwargs["event_type"])

    settings = _settings(
        langgraph_enabled=True,
        langgraph_checkpointer="none",
        langgraph_thread_prefix="mission-thread",
    )
    advanced = asyncio.run(
        langgraph_lifecycle.maybe_advance_mission_lifecycle(
            app=_app_state(redis_ready=True, redis=object()),
            mission_id="mission-1",
            settings=settings,
            validator=object(),
            emit_state_event_fn=_emit,
        )
    )
    assert advanced is True
    assert emitted == ["MISSION_RUNNING", "MISSION_VERIFIED", "MISSION_COMPLETE"]

    assert FakeStateGraph.last_instance is not None
    invoke_state, invoke_config = FakeStateGraph.last_instance.compiled.calls[0]
    assert invoke_state["mission_id"] == "mission-1"
    assert invoke_config == {"configurable": {"thread_id": "mission-thread:mission-1"}}


def test_maybe_advance_halts_when_transition_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(langgraph_lifecycle, "StateGraph", FakeStateGraph)
    monkeypatch.setattr(
        langgraph_lifecycle.storage,
        "transition_mission_state",
        lambda *_args: None,
    )

    emitted: list[str] = []
    advanced = asyncio.run(
        langgraph_lifecycle.maybe_advance_mission_lifecycle(
            app=_app_state(),
            mission_id="mission-1",
            settings=_settings(langgraph_enabled=True),
            validator=object(),
            emit_state_event_fn=(
                lambda **kwargs: emitted.append(kwargs["event_type"]) or asyncio.sleep(0)
            ),
        )
    )
    assert advanced is True
    assert emitted == []


def test_resolve_checkpointer_memory_mode_singleton(monkeypatch) -> None:
    class Saver:
        instances = 0

        def __init__(self) -> None:
            Saver.instances += 1

    monkeypatch.setattr(langgraph_lifecycle, "InMemorySaver", Saver)
    monkeypatch.setattr(langgraph_lifecycle, "_MEMORY_CHECKPOINTER", None)

    settings = _settings(langgraph_checkpointer="memory")
    first = langgraph_lifecycle._resolve_checkpointer(settings)
    second = langgraph_lifecycle._resolve_checkpointer(settings)

    assert first is second
    assert Saver.instances == 1


def test_maybe_advance_fail_open_and_fail_closed(monkeypatch) -> None:
    class RaisingCompiledGraph:
        async def ainvoke(
            self,
            _state: dict[str, Any],
            config: dict[str, Any] | None = None,
        ) -> None:
            raise RuntimeError("graph down")

    class RaisingStateGraph(FakeStateGraph):
        def compile(self, checkpointer: Any = None) -> RaisingCompiledGraph:
            self.checkpointer = checkpointer
            return RaisingCompiledGraph()

    monkeypatch.setattr(langgraph_lifecycle, "StateGraph", RaisingStateGraph)
    monkeypatch.setattr(
        langgraph_lifecycle.storage,
        "transition_mission_state",
        lambda _settings_obj, _mission_id, _expected, new_state, _event: _mission_record(new_state),
    )

    fail_open = asyncio.run(
        langgraph_lifecycle.maybe_advance_mission_lifecycle(
            app=_app_state(),
            mission_id="mission-1",
            settings=_settings(langgraph_enabled=True, langgraph_fail_open=True),
            validator=object(),
            emit_state_event_fn=lambda **_kwargs: asyncio.sleep(0),
        )
    )
    assert fail_open is False

    with pytest.raises(RuntimeError):
        asyncio.run(
            langgraph_lifecycle.maybe_advance_mission_lifecycle(
                app=_app_state(),
                mission_id="mission-1",
                settings=_settings(langgraph_enabled=True, langgraph_fail_open=False),
                validator=object(),
                emit_state_event_fn=lambda **_kwargs: asyncio.sleep(0),
            )
        )
