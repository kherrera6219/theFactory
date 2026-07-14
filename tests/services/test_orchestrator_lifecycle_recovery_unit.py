import asyncio
import importlib
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

orchestrator_main = importlib.import_module("orchestrator.main")
orchestrator_models = importlib.import_module("orchestrator.models")
orchestrator_lifecycle = importlib.import_module("orchestrator.lifecycle_recovery")

MissionRecord = orchestrator_models.MissionRecord
MissionState = orchestrator_models.MissionState
app = orchestrator_main.app


class _RunningTask:
    def done(self) -> bool:
        return False


def _mission(mission_id: str, state: MissionState) -> MissionRecord:
    return MissionRecord(
        mission_id=mission_id,
        prompt="Build API",
        requested_target_language="python",
        metadata={"source": "test"},
        state=state,
        created_at="2026-03-01T00:00:00+00:00",
    )


def test_recover_inflight_marks_bootstrapped_when_auto_transition_disabled() -> None:
    app.state.settings = replace(app.state.settings, auto_transition_enabled=False)
    app.state.lifecycle_recovery_bootstrapped = False
    app.state.lifecycle_recovery_last_error = "stale"

    recovered = asyncio.run(orchestrator_lifecycle._recover_inflight_lifecycle_tasks(app))

    assert recovered is True
    assert app.state.lifecycle_recovery_bootstrapped is True
    assert app.state.lifecycle_recovery_recovered_count == 0
    assert app.state.lifecycle_recovery_scanned_count == 0
    assert app.state.lifecycle_recovery_last_error is None


def test_recover_inflight_returns_false_when_runtime_not_ready(monkeypatch) -> None:
    app.state.settings = replace(app.state.settings, auto_transition_enabled=True)
    app.state.protocol_ready = True
    app.state.lifecycle_recovery_bootstrapped = False

    async def _runtime_not_ready(_app):
        return False, False

    monkeypatch.setattr(orchestrator_lifecycle, "ensure_runtime_ready", _runtime_not_ready)

    recovered = asyncio.run(orchestrator_lifecycle._recover_inflight_lifecycle_tasks(app))

    assert recovered is False
    assert app.state.lifecycle_recovery_bootstrapped is not True
    assert app.state.lifecycle_recovery_last_error == "database unavailable"


def test_recover_inflight_returns_false_when_protocol_unavailable(monkeypatch) -> None:
    app.state.settings = replace(app.state.settings, auto_transition_enabled=True)
    app.state.protocol_ready = False
    app.state.lifecycle_recovery_bootstrapped = False

    async def _runtime_ready(_app):
        return True, True

    monkeypatch.setattr(orchestrator_lifecycle, "ensure_runtime_ready", _runtime_ready)

    recovered = asyncio.run(orchestrator_lifecycle._recover_inflight_lifecycle_tasks(app))

    assert recovered is False
    assert app.state.lifecycle_recovery_last_error == "protocol unavailable"


def test_recover_inflight_starts_lifecycle_for_pending_missions(monkeypatch) -> None:
    app.state.settings = replace(app.state.settings, auto_transition_enabled=True)
    app.state.protocol_ready = True
    app.state.lifecycle_tasks = {"mission-1": _RunningTask()}

    async def _runtime_ready(_app):
        return True, True

    monkeypatch.setattr(orchestrator_lifecycle, "ensure_runtime_ready", _runtime_ready)
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_missions_in_states",
        lambda *_: [
            _mission("mission-1", MissionState.running),
            _mission("mission-2", MissionState.queued),
            _mission("mission-3", MissionState.verified),
        ],
    )

    started: list[str] = []
    monkeypatch.setattr(
        orchestrator_lifecycle,
        "start_lifecycle_task",
        lambda _app, mission_id: started.append(mission_id),
    )

    recovered = asyncio.run(orchestrator_lifecycle._recover_inflight_lifecycle_tasks(app))

    assert recovered is True
    assert started == ["mission-2", "mission-3"]
    assert app.state.lifecycle_recovery_bootstrapped is True
    assert app.state.lifecycle_recovery_recovered_count == 2
    assert app.state.lifecycle_recovery_scanned_count == 3
    assert app.state.lifecycle_recovery_last_error is None


def test_recover_inflight_queries_every_resumable_v2_state(monkeypatch) -> None:
    app.state.settings = replace(app.state.settings, auto_transition_enabled=True)
    app.state.protocol_ready = True
    app.state.lifecycle_tasks = {}

    async def _runtime_ready(_app):
        return True, True

    captured_states: list[MissionState] = []

    def _list_missions(_settings, states, _limit):
        captured_states.extend(states)
        return []

    monkeypatch.setattr(orchestrator_lifecycle, "ensure_runtime_ready", _runtime_ready)
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_missions_in_states",
        _list_missions,
    )

    recovered = asyncio.run(orchestrator_lifecycle._recover_inflight_lifecycle_tasks(app))

    assert recovered is True
    assert captured_states == [
        MissionState.queued,
        MissionState.pm_intake,
        MissionState.fetch,
        MissionState.ceo_delegated,
        MissionState.pod_assigned,
        MissionState.specialist_assigned,
        MissionState.running,
        MissionState.gating,
        MissionState.fusion,
        MissionState.verified,
    ]
    assert MissionState.clarifying not in captured_states
    assert MissionState.complete not in captured_states
    assert MissionState.failed not in captured_states


def test_lifecycle_recovery_loop_retries_until_success(monkeypatch) -> None:
    attempts = {"count": 0}

    async def _recover(_app):
        attempts["count"] += 1
        return attempts["count"] >= 2

    sleeps: list[float] = []

    async def _sleep(seconds: float):
        sleeps.append(seconds)
        return None

    monkeypatch.setattr(orchestrator_lifecycle, "_recover_inflight_lifecycle_tasks", _recover)
    monkeypatch.setattr(orchestrator_lifecycle.asyncio, "sleep", _sleep)

    asyncio.run(orchestrator_lifecycle.lifecycle_recovery_loop(SimpleNamespace(state=SimpleNamespace())))

    assert attempts["count"] == 2
    assert sleeps == [orchestrator_main.LIFECYCLE_RECOVERY_RETRY_SECONDS]
