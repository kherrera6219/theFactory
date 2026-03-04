import asyncio
import builtins
import importlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

orchestrator_models = importlib.import_module("orchestrator.models")
orchestrator_runtime = importlib.import_module("orchestrator.runtime")
orchestrator_settings = importlib.import_module("orchestrator.settings")

MissionRecord = orchestrator_models.MissionRecord
MissionState = orchestrator_models.MissionState
Settings = orchestrator_settings.Settings
runtime = orchestrator_runtime


def _settings() -> Settings:
    root = ROOT
    return Settings(
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
        event_schema_path=root / "schemas" / "event.envelope.schema.json",
        topics_path=root / "protocol" / "topics.yaml",
        admin_api_key="admin-key",
        internal_service_api_key="worker-key",
        readonly_api_key="viewer-key",
        extra_api_keys="operator-key=mutate,read",
    )


def _mission_record(state: MissionState) -> MissionRecord:
    return MissionRecord(
        mission_id="mission-1",
        prompt="Build API",
        requested_target_language="python",
        metadata={"source": "test"},
        state=state,
        created_at="2026-03-01T00:00:00+00:00",
    )


class FakeRedis:
    def __init__(self) -> None:
        self.xadd_calls: list[tuple[str, dict[str, Any]]] = []
        self.xgroup_calls: list[tuple[Any, ...]] = []
        self.xack_calls: list[tuple[str, str, str]] = []
        self.xreadgroup_responses: list[Any] = []
        self.ping_value: bool = True

    async def xadd(self, stream: str, payload: dict[str, Any], **kwargs) -> str:
        self.xadd_calls.append((stream, payload))
        return "1-0"

    async def xgroup_create(self, *args, **kwargs) -> None:
        self.xgroup_calls.append((args, kwargs))

    async def xreadgroup(self, **kwargs) -> Any:
        if self.xreadgroup_responses:
            response = self.xreadgroup_responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        raise asyncio.CancelledError

    async def xack(self, stream: str, group: str, entry_id: str) -> int:
        self.xack_calls.append((stream, group, entry_id))
        return 1

    async def ping(self) -> bool:
        if isinstance(self.ping_value, Exception):
            raise self.ping_value
        return self.ping_value


class FakeEnvelopeValidator:
    def build_state_envelope(self, mission: MissionRecord, event_type: str) -> dict[str, Any]:
        return {
            "event_id": "evt-1",
            "topic": "fusion.requested",
            "timestamp": "2026-03-01T00:00:00+00:00",
            "producer": "orchestrator",
            "correlation_id": mission.mission_id,
            "payload_ref": f"registry://missions/{mission.mission_id}",
            "schema": "missions.state.v1",
            "priority": "NORMAL",
            "event_type": event_type,
        }

    def parse_intake_envelope(self, fields: dict[str, Any], payload: dict[str, Any]) -> None:
        return None


@dataclass
class FakeTask:
    done_state: bool = False

    def done(self) -> bool:
        return self.done_state

    def add_done_callback(self, fn) -> None:
        self._callback = fn


def _app_state(**kwargs):
    defaults = {
        "settings": _settings(),
        "envelope_validator": FakeEnvelopeValidator(),
        "redis": FakeRedis(),
        "redis_ready": True,
        "db_ready": True,
        "consumer_task": None,
        "lifecycle_tasks": {},
        "startup_lock": asyncio.Lock(),
        "protocol_ready": True,
    }
    defaults.update(kwargs)
    return SimpleNamespace(state=SimpleNamespace(**defaults))


def test_normalize_metadata() -> None:
    assert runtime._normalize_metadata({"a": 1}) == {"a": 1}
    assert runtime._normalize_metadata("x") == {}


def test_emit_state_event() -> None:
    redis_client = FakeRedis()
    runtime_settings = _settings()
    mission = _mission_record(MissionState.running)
    asyncio.run(
        runtime.emit_state_event(
            runtime_settings, FakeEnvelopeValidator(), redis_client, mission, "MISSION_RUNNING"
        )
    )
    assert redis_client.xadd_calls
    stream, payload = redis_client.xadd_calls[0]
    assert stream == runtime_settings.state_stream
    assert payload["mission_id"] == "mission-1"


def test_emit_running_phase_checkpoints_skips_stream_when_redis_unavailable(monkeypatch) -> None:
    app = _app_state(redis=None, redis_ready=False)
    mission = _mission_record(MissionState.running)
    runtime_settings = _settings()

    async def _to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    inserted: list[str] = []
    emitted: list[str] = []

    monkeypatch.setattr(runtime.asyncio, "to_thread", _to_thread)
    monkeypatch.setattr(
        runtime.storage,
        "insert_mission_event",
        lambda _settings_obj, _mission_id, _prev, _new, event_type: inserted.append(event_type),
    )

    async def _emit_state_event(**kwargs):
        emitted.append(kwargs["event_type"])

    monkeypatch.setattr(runtime, "emit_state_event", _emit_state_event)

    asyncio.run(
        runtime._emit_running_phase_checkpoints(
            app=app,
            settings=runtime_settings,
            validator=FakeEnvelopeValidator(),
            mission=mission,
        )
    )
    assert inserted == ["MISSION_GATING", "MISSION_FUSION"]
    assert emitted == []


def test_emit_running_phase_checkpoints_emit_failure_is_swallowed(monkeypatch) -> None:
    app = _app_state(redis=FakeRedis(), redis_ready=True)
    mission = _mission_record(MissionState.running)
    runtime_settings = _settings()

    async def _to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(runtime.asyncio, "to_thread", _to_thread)
    monkeypatch.setattr(runtime.storage, "insert_mission_event", lambda *_args: None)

    async def _emit_fail(**_kwargs):
        raise RuntimeError("emit failure")

    monkeypatch.setattr(runtime, "emit_state_event", _emit_fail)

    asyncio.run(
        runtime._emit_running_phase_checkpoints(
            app=app,
            settings=runtime_settings,
            validator=FakeEnvelopeValidator(),
            mission=mission,
        )
    )


def test_ensure_consumer_group_busygroup(monkeypatch) -> None:
    class BusyGroup(runtime.ResponseError):
        pass

    class BusyRedis(FakeRedis):
        async def xgroup_create(self, *args, **kwargs) -> None:
            raise BusyGroup("BUSYGROUP already exists")

    asyncio.run(runtime.ensure_consumer_group(_settings(), BusyRedis()))

    class ErrorRedis(FakeRedis):
        async def xgroup_create(self, *args, **kwargs) -> None:
            raise BusyGroup("other failure")

    with pytest.raises(BusyGroup):
        asyncio.run(runtime.ensure_consumer_group(_settings(), ErrorRedis()))


def test_consume_intake_stream_happy_path(monkeypatch) -> None:
    redis_client = FakeRedis()
    payload = {
        "mission_id": "mission-1",
        "prompt": "Build API",
        "requested_target_language": "python",
        "metadata": {"source": "test"},
        "created_at": "2026-03-01T00:00:00+00:00",
    }
    redis_client.xreadgroup_responses = [
        [("missions.intake", [("1-0", {"payload": json.dumps(payload), "envelope": "{}"})])],
        asyncio.CancelledError(),
    ]
    app = _app_state(redis=redis_client, lifecycle_tasks={})

    async def _to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    upsert_calls: list[str] = []
    event_calls: list[str] = []
    lifecycle_calls: list[str] = []

    monkeypatch.setattr(runtime.asyncio, "to_thread", _to_thread)
    monkeypatch.setattr(
        runtime.storage,
        "upsert_mission",
        lambda *_args: upsert_calls.append("upsert"),
    )
    monkeypatch.setattr(
        runtime.storage,
        "insert_mission_event",
        lambda *_args: event_calls.append("event"),
    )
    monkeypatch.setattr(
        runtime,
        "emit_state_event",
        lambda **kwargs: asyncio.sleep(0),
    )
    monkeypatch.setattr(
        runtime,
        "start_lifecycle_task",
        lambda _app, mission_id: lifecycle_calls.append(mission_id),
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runtime.consume_intake_stream(app))

    assert upsert_calls == ["upsert"]
    assert event_calls == ["event"]
    assert lifecycle_calls == ["mission-1"]
    assert redis_client.xack_calls == [("missions.intake", "orchestrator", "1-0")]


def test_consume_intake_stream_invalid_payload_is_acked(monkeypatch) -> None:
    redis_client = FakeRedis()
    redis_client.xreadgroup_responses = [
        [("missions.intake", [("1-0", {"payload": "{}", "envelope": "{}"})])],
        asyncio.CancelledError(),
    ]

    class InvalidValidator(FakeEnvelopeValidator):
        def parse_intake_envelope(self, fields: dict[str, Any], payload: dict[str, Any]) -> None:
            raise runtime.ProtocolValidationError("invalid")

    app = _app_state(redis=redis_client, envelope_validator=InvalidValidator(), lifecycle_tasks={})

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runtime.consume_intake_stream(app))

    assert redis_client.xack_calls == [("missions.intake", "orchestrator", "1-0")]


def test_consume_intake_stream_empty_then_cancel() -> None:
    redis_client = FakeRedis()
    redis_client.xreadgroup_responses = [[], asyncio.CancelledError()]
    app = _app_state(redis=redis_client, lifecycle_tasks={})

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runtime.consume_intake_stream(app))

    assert redis_client.xack_calls == []


def test_consume_intake_stream_emit_failure_does_not_block_intake(monkeypatch) -> None:
    redis_client = FakeRedis()
    payload = {
        "mission_id": "mission-1",
        "prompt": "Build API",
        "requested_target_language": "python",
        "metadata": {"source": "test"},
        "created_at": "2026-03-01T00:00:00+00:00",
    }
    redis_client.xreadgroup_responses = [
        [("missions.intake", [("1-0", {"payload": json.dumps(payload), "envelope": "{}"})])],
        asyncio.CancelledError(),
    ]
    app = _app_state(redis=redis_client, lifecycle_tasks={})

    async def _to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(runtime.asyncio, "to_thread", _to_thread)
    monkeypatch.setattr(runtime.storage, "upsert_mission", lambda *_args: None)
    monkeypatch.setattr(runtime.storage, "insert_mission_event", lambda *_args: None)

    async def _emit_fail(**_kwargs):
        raise RuntimeError("emit down")

    started: list[str] = []

    monkeypatch.setattr(runtime, "emit_state_event", _emit_fail)
    monkeypatch.setattr(runtime, "start_lifecycle_task", lambda _app, mid: started.append(mid))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runtime.consume_intake_stream(app))

    assert started == ["mission-1"]
    assert redis_client.xack_calls == [("missions.intake", "orchestrator", "1-0")]


def test_start_lifecycle_task_branches(monkeypatch) -> None:
    app = _app_state(lifecycle_tasks={})
    app.state.settings = _settings()
    app.state.settings = Settings(
        **{
            **app.state.settings.__dict__,
            "auto_transition_enabled": False,
        }
    )
    runtime.start_lifecycle_task(app, "mission-1")
    assert app.state.lifecycle_tasks == {}

    app.state.settings = _settings()
    app.state.lifecycle_tasks = {"mission-1": FakeTask(done_state=False)}
    runtime.start_lifecycle_task(app, "mission-1")
    assert "mission-1" in app.state.lifecycle_tasks

    created: list[FakeTask] = []

    def _create_task(_coro) -> FakeTask:
        _coro.close()
        task = FakeTask(done_state=False)
        created.append(task)
        return task

    monkeypatch.setattr(runtime.asyncio, "create_task", _create_task)
    app.state.lifecycle_tasks = {}
    runtime.start_lifecycle_task(app, "mission-2")
    assert created
    assert "mission-2" in app.state.lifecycle_tasks


def test_start_lifecycle_task_cleanup_callback(monkeypatch) -> None:
    app = _app_state(lifecycle_tasks={})
    created: list[FakeTask] = []

    def _create_task(_coro) -> FakeTask:
        _coro.close()
        task = FakeTask(done_state=False)
        created.append(task)
        return task

    monkeypatch.setattr(runtime.asyncio, "create_task", _create_task)
    runtime.start_lifecycle_task(app, "mission-cleanup")
    assert "mission-cleanup" in app.state.lifecycle_tasks
    created[0]._callback(created[0])
    assert "mission-cleanup" not in app.state.lifecycle_tasks


def test_advance_mission_lifecycle_returns_when_langgraph_handles(monkeypatch) -> None:
    app = _app_state(lifecycle_tasks={})
    app.state.settings = Settings(**{**_settings().__dict__, "langgraph_enabled": True})

    async def _langgraph(**_kwargs) -> bool:
        return True

    async def _sleep(_):
        raise AssertionError("legacy lifecycle sleep should not execute")

    monkeypatch.setattr(runtime, "maybe_advance_mission_lifecycle", _langgraph)
    monkeypatch.setattr(runtime.asyncio, "sleep", _sleep)
    monkeypatch.setattr(
        runtime.storage,
        "transition_mission_state",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("legacy transition path should not execute")
        ),
    )

    asyncio.run(runtime.advance_mission_lifecycle(app, "mission-1"))


def test_advance_mission_lifecycle_emits(monkeypatch) -> None:
    app = _app_state(lifecycle_tasks={})
    app.state.settings = _settings()
    app.state.redis_ready = True
    app.state.redis = FakeRedis()
    app.state.envelope_validator = FakeEnvelopeValidator()

    async def _sleep(_):
        return None

    async def _to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(runtime.asyncio, "sleep", _sleep)
    monkeypatch.setattr(runtime.asyncio, "to_thread", _to_thread)
    monkeypatch.setattr(
        runtime.storage,
        "transition_mission_state",
        lambda _settings_obj, mission_id, expected_state, new_state, _event_type: _mission_record(
            new_state
        ),
    )
    checkpoint_events: list[str] = []

    def _insert_checkpoint(
        _settings_obj,
        _mission_id,
        _previous_state,
        _new_state,
        event_type,
    ) -> None:
        checkpoint_events.append(event_type)

    monkeypatch.setattr(
        runtime.storage,
        "insert_mission_event",
        _insert_checkpoint,
    )
    emitted: list[str] = []

    async def _emit(**kwargs):
        emitted.append(kwargs["event_type"])

    monkeypatch.setattr(runtime, "emit_state_event", _emit)

    asyncio.run(runtime.advance_mission_lifecycle(app, "mission-1"))
    assert emitted == [
        "MISSION_RUNNING",
        "MISSION_GATING",
        "MISSION_FUSION",
        "MISSION_VERIFIED",
        "MISSION_COMPLETE",
    ]
    assert checkpoint_events == ["MISSION_GATING", "MISSION_FUSION"]


def test_advance_mission_lifecycle_stops_on_missing_transition(monkeypatch) -> None:
    app = _app_state(lifecycle_tasks={})
    app.state.settings = _settings()

    async def _sleep(_):
        return None

    async def _to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(runtime.asyncio, "sleep", _sleep)
    monkeypatch.setattr(runtime.asyncio, "to_thread", _to_thread)
    monkeypatch.setattr(runtime.storage, "transition_mission_state", lambda *_: None)

    called = {"emit": False}

    async def _emit(**kwargs):
        called["emit"] = True

    monkeypatch.setattr(runtime, "emit_state_event", _emit)
    asyncio.run(runtime.advance_mission_lifecycle(app, "mission-1"))
    assert called["emit"] is False


def test_advance_mission_lifecycle_skips_emit_when_redis_not_ready(monkeypatch) -> None:
    app = _app_state(redis_ready=False, redis=FakeRedis(), lifecycle_tasks={})
    app.state.settings = _settings()

    async def _sleep(_):
        return None

    async def _to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(runtime.asyncio, "sleep", _sleep)
    monkeypatch.setattr(runtime.asyncio, "to_thread", _to_thread)
    monkeypatch.setattr(
        runtime.storage,
        "transition_mission_state",
        lambda _settings_obj, mission_id, expected_state, new_state, _event_type: _mission_record(
            new_state
        ),
    )
    called = {"emit": False}

    async def _emit(**_kwargs):
        called["emit"] = True

    monkeypatch.setattr(runtime, "emit_state_event", _emit)
    asyncio.run(runtime.advance_mission_lifecycle(app, "mission-1"))
    assert called["emit"] is False


def test_advance_mission_lifecycle_emit_exception_is_swallowed(monkeypatch) -> None:
    app = _app_state(redis_ready=True, redis=FakeRedis(), lifecycle_tasks={})
    app.state.settings = _settings()

    async def _sleep(_):
        return None

    async def _to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(runtime.asyncio, "sleep", _sleep)
    monkeypatch.setattr(runtime.asyncio, "to_thread", _to_thread)
    monkeypatch.setattr(
        runtime.storage,
        "transition_mission_state",
        lambda _settings_obj, mission_id, expected_state, new_state, _event_type: _mission_record(
            new_state
        ),
    )
    monkeypatch.setattr(
        runtime,
        "emit_state_event",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("emit fail")),
    )

    asyncio.run(runtime.advance_mission_lifecycle(app, "mission-1"))


def test_ensure_runtime_ready_success(monkeypatch) -> None:
    redis_client = FakeRedis()
    app = _app_state(
        redis=None,
        redis_ready=False,
        db_ready=False,
        consumer_task=None,
        lifecycle_tasks=None,
        startup_lock=None,
        protocol_ready=True,
    )

    class RedisModule:
        @staticmethod
        def from_url(url: str, decode_responses: bool = True) -> FakeRedis:
            return redis_client

    monkeypatch.setattr(runtime, "redis", RedisModule)

    async def _to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(runtime.asyncio, "to_thread", _to_thread)
    monkeypatch.setattr(runtime.storage, "ensure_db_schema", lambda *_: None)
    monkeypatch.setattr(runtime, "ensure_consumer_group", lambda *_: asyncio.sleep(0))
    monkeypatch.setattr(runtime, "consume_intake_stream", lambda _app: asyncio.sleep(0))

    def _create_task(_coro) -> FakeTask:
        _coro.close()
        return FakeTask(done_state=False)

    monkeypatch.setattr(runtime.asyncio, "create_task", _create_task)

    redis_ready, db_ready = asyncio.run(runtime.ensure_runtime_ready(app))
    assert redis_ready is True
    assert db_ready is True
    assert app.state.consumer_task is not None


def test_ensure_runtime_ready_failure_paths(monkeypatch) -> None:
    redis_client = FakeRedis()
    redis_client.ping_value = RuntimeError("redis down")
    app = _app_state(
        redis=redis_client,
        redis_ready=False,
        db_ready=False,
        consumer_task=None,
        protocol_ready=True,
    )

    async def _to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(runtime.asyncio, "to_thread", _to_thread)

    def _ensure_db_schema(*_args):
        raise RuntimeError("db down")

    monkeypatch.setattr(runtime.storage, "ensure_db_schema", _ensure_db_schema)

    redis_ready, db_ready = asyncio.run(runtime.ensure_runtime_ready(app))
    assert redis_ready is False
    assert db_ready is False
    assert app.state.consumer_task is None


def test_ensure_runtime_ready_sets_defaults_and_handles_consumer_start_failure(monkeypatch) -> None:
    redis_client = FakeRedis()
    app = _app_state(
        redis=redis_client,
        redis_ready=None,
        db_ready=None,
        consumer_task=None,
        lifecycle_tasks=None,
        startup_lock=None,
        protocol_ready=True,
    )

    async def _to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(runtime.asyncio, "to_thread", _to_thread)
    monkeypatch.setattr(runtime.storage, "ensure_db_schema", lambda *_: None)

    async def _ensure_group_fail(*_args, **_kwargs):
        raise RuntimeError("group fail")

    monkeypatch.setattr(runtime, "ensure_consumer_group", _ensure_group_fail)
    redis_ready, db_ready = asyncio.run(runtime.ensure_runtime_ready(app))
    assert redis_ready is True
    assert db_ready is True
    assert app.state.consumer_task is None
    assert app.state.lifecycle_tasks == {}
    assert app.state.startup_lock is not None


def test_ensure_runtime_ready_skips_ping_and_db_when_already_ready(monkeypatch) -> None:
    redis_client = FakeRedis()
    app = _app_state(
        redis=redis_client,
        redis_ready=True,
        db_ready=True,
        consumer_task=FakeTask(done_state=False),
        protocol_ready=False,
    )
    touched = {"to_thread": 0}

    async def _to_thread(fn, *args, **kwargs):
        touched["to_thread"] += 1
        return fn(*args, **kwargs)

    monkeypatch.setattr(runtime.asyncio, "to_thread", _to_thread)
    redis_ready, db_ready = asyncio.run(runtime.ensure_runtime_ready(app))
    assert redis_ready is True
    assert db_ready is True
    assert touched["to_thread"] == 0


def test_runtime_self_heal_loop(monkeypatch) -> None:
    calls = {"count": 0}

    async def _ensure(_app):
        calls["count"] += 1
        raise RuntimeError("transient")

    async def _sleep(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(runtime, "ensure_runtime_ready", _ensure)
    monkeypatch.setattr(runtime.asyncio, "sleep", _sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runtime.runtime_self_heal_loop(_app_state()))
    assert calls["count"] == 1


def test_runtime_module_import_fallback_without_redis(monkeypatch) -> None:
    module_path = ROOT / "services" / "orchestrator" / "orchestrator" / "runtime.py"
    real_import = builtins.__import__

    def _blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "redis.asyncio" or name == "redis.exceptions":
            raise ModuleNotFoundError(name)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)
    spec = importlib.util.spec_from_file_location("orchestrator.runtime_no_redis", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.redis is None
    assert issubclass(module.ResponseError, Exception)
