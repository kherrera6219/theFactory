"""Tests for mission_flow_v2.py — 11-phase v2 lifecycle engine."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
orchestrator_mission_flow_v2 = importlib.import_module("orchestrator.mission_flow_v2")
orchestrator_models = importlib.import_module("orchestrator.models")

V1_TRANSITIONS = orchestrator_mission_flow_v2.V1_TRANSITIONS
V2_EVENT_TO_PHASE = orchestrator_mission_flow_v2.V2_EVENT_TO_PHASE
V2_PHASE_ORDER = orchestrator_mission_flow_v2.V2_PHASE_ORDER
V2_TRANSITIONS = orchestrator_mission_flow_v2.V2_TRANSITIONS
advance_mission_lifecycle_v2 = orchestrator_mission_flow_v2.advance_mission_lifecycle_v2
v2_map_state_to_v1 = orchestrator_mission_flow_v2.v2_map_state_to_v1
v2_phase_index = orchestrator_mission_flow_v2.v2_phase_index
MissionState = orchestrator_models.MissionState

# ------------------------------------------------------------------
# Transition table structure
# ------------------------------------------------------------------


class TestV2Transitions:
    def test_has_9_transitions(self) -> None:
        assert len(V2_TRANSITIONS) == 9

    def test_starts_from_queued(self) -> None:
        assert V2_TRANSITIONS[0][0] == MissionState.queued

    def test_ends_at_complete(self) -> None:
        assert V2_TRANSITIONS[-1][1] == MissionState.complete

    def test_chain_is_contiguous(self) -> None:
        """Each transition's target state is the next transition's source."""
        for i in range(len(V2_TRANSITIONS) - 1):
            assert V2_TRANSITIONS[i][1] == V2_TRANSITIONS[i + 1][0], (
                f"Gap: {V2_TRANSITIONS[i][1]} != {V2_TRANSITIONS[i+1][0]}"
            )

    def test_all_event_types_unique(self) -> None:
        events = [t[2] for t in V2_TRANSITIONS]
        assert len(events) == len(set(events))


class TestV1Transitions:
    def test_has_3_transitions(self) -> None:
        assert len(V1_TRANSITIONS) == 3

    def test_starts_from_queued_ends_at_complete(self) -> None:
        assert V1_TRANSITIONS[0][0] == MissionState.queued
        assert V1_TRANSITIONS[-1][1] == MissionState.complete


# ------------------------------------------------------------------
# Phase order
# ------------------------------------------------------------------


class TestV2PhaseOrder:
    def test_has_11_phases(self) -> None:
        assert len(V2_PHASE_ORDER) == 11

    def test_starts_intake_ends_complete(self) -> None:
        assert V2_PHASE_ORDER[0] == MissionState.intake
        assert V2_PHASE_ORDER[-1] == MissionState.complete

    def test_all_transition_states_in_phase_order(self) -> None:
        phase_set = set(V2_PHASE_ORDER)
        for expected, new, _ in V2_TRANSITIONS:
            assert expected in phase_set, f"{expected} not in V2_PHASE_ORDER"
            assert new in phase_set, f"{new} not in V2_PHASE_ORDER"


# ------------------------------------------------------------------
# Event-to-phase mapping
# ------------------------------------------------------------------


class TestV2EventToPhase:
    def test_covers_all_11_events(self) -> None:
        assert len(V2_EVENT_TO_PHASE) == 11

    def test_all_v2_phase_order_values_mapped(self) -> None:
        mapped_phases = set(V2_EVENT_TO_PHASE.values())
        for phase in V2_PHASE_ORDER:
            assert phase in mapped_phases, f"{phase} not mapped"


# ------------------------------------------------------------------
# v2_map_state_to_v1
# ------------------------------------------------------------------


class TestV2MapStateToV1:
    @pytest.mark.parametrize(
        "v2_state,expected_v1",
        [
            (MissionState.intake, MissionState.intake),
            (MissionState.queued, MissionState.queued),
            (MissionState.pm_intake, MissionState.queued),
            (MissionState.ceo_delegated, MissionState.queued),
            (MissionState.pod_assigned, MissionState.queued),
            (MissionState.specialist_assigned, MissionState.queued),
            (MissionState.running, MissionState.running),
            (MissionState.gating, MissionState.running),
            (MissionState.fusion, MissionState.running),
            (MissionState.verified, MissionState.verified),
            (MissionState.complete, MissionState.complete),
            (MissionState.failed, MissionState.failed),
        ],
    )
    def test_maps_correctly(
        self, v2_state: MissionState, expected_v1: MissionState
    ) -> None:
        assert v2_map_state_to_v1(v2_state) == expected_v1


# ------------------------------------------------------------------
# v2_phase_index
# ------------------------------------------------------------------


class TestV2PhaseIndex:
    def test_intake_is_0(self) -> None:
        assert v2_phase_index(MissionState.intake) == 0

    def test_complete_is_10(self) -> None:
        assert v2_phase_index(MissionState.complete) == 10

    def test_failed_is_minus_1(self) -> None:
        assert v2_phase_index(MissionState.failed) == -1

    def test_running_is_6(self) -> None:
        assert v2_phase_index(MissionState.running) == 6


# ------------------------------------------------------------------
# advance_mission_lifecycle_v2 (integration with mocks)
# ------------------------------------------------------------------


def _make_app_state() -> MagicMock:
    app = MagicMock()
    app.state.redis_ready = True
    app.state.redis = AsyncMock()
    return app


def _make_settings() -> MagicMock:
    settings = MagicMock()
    settings.mission_flow_v2_enabled = True
    settings.transition_step_seconds = 0.0
    return settings


def _make_mission(
    mission_id: str = "test-m1",
    state: MissionState = MissionState.queued,
) -> MagicMock:
    mission = MagicMock()
    mission.mission_id = mission_id
    mission.state = state
    mission.prompt = "test prompt"
    mission.requested_target_language = "python"
    mission.metadata = {}
    mission.created_at = "2026-01-01T00:00:00Z"
    return mission


def _make_stateful_storage(mission: MagicMock) -> tuple[dict[str, Any], Any, Any, Any, Any]:
    transition_log: list[tuple[str, str, str]] = []
    event_log: list[str] = []

    def fetch_mission(_settings: Any, _mission_id: str) -> MagicMock:
        return mission

    def update_mission_metadata(
        _settings: Any,
        _mission_id: str,
        metadata: dict[str, Any],
    ) -> MagicMock:
        mission.metadata = dict(metadata)
        return mission

    def transition_mission_state(
        _settings: Any,
        _mission_id: str,
        expected: MissionState,
        new: MissionState,
        event: str,
    ) -> MagicMock:
        transition_log.append((expected.value, new.value, event))
        mission.state = new
        return mission

    def insert_mission_event(
        _settings: Any,
        _mission_id: str,
        _previous_state: MissionState,
        _new_state: MissionState,
        event_type: str,
    ) -> None:
        event_log.append(event_type)

    state = {"transitions": transition_log, "events": event_log}
    return (
        state,
        fetch_mission,
        update_mission_metadata,
        transition_mission_state,
        insert_mission_event,
    )


class TestAdvanceMissionLifecycleV2:
    @pytest.mark.asyncio
    async def test_full_11_phase_run(self) -> None:
        """Run through all 9 transitions with mocked storage."""
        app = _make_app_state()
        settings = _make_settings()
        validator = MagicMock()

        mission = _make_mission()
        emit_fn = AsyncMock()
        prepare_fn = AsyncMock(return_value=True)
        completion_fn = AsyncMock(return_value=(True, {}))
        state, fetch_mission, update_metadata, transition_mission_state, insert_mission_event = (
            _make_stateful_storage(mission)
        )

        with patch(
            "orchestrator.mission_flow_v2.storage"
        ) as mock_storage:
            mock_storage.transition_mission_state = transition_mission_state
            mock_storage.fetch_mission = fetch_mission
            mock_storage.update_mission_metadata = update_metadata
            mock_storage.insert_mission_event = insert_mission_event

            with patch(
                "orchestrator.mission_flow_v2.generate_ceo_delegation",
                AsyncMock(
                    return_value={
                        "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                        "specialist_agent_id": "AGENT-14-PYTHON",
                        "source": "llm",
                        "llm_route": "primary",
                        "model_provider": "anthropic",
                        "model": "claude-3-5-sonnet",
                    }
                ),
            ), patch(
                "orchestrator.mission_flow_v2.generate_pod_manager_delegation",
                AsyncMock(
                    return_value={
                        "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                        "specialist_agent_id": "AGENT-14-PYTHON",
                        "source": "llm",
                        "llm_route": "primary",
                        "model_provider": "openai",
                        "model": "gpt-5.2-mini",
                    }
                ),
            ), patch(
                "orchestrator.mission_flow_v2.generate_specialist_plan",
                AsyncMock(
                    return_value={
                        "specialist_agent_id": "AGENT-14-PYTHON",
                        "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                        "plan_summary": "Implement and verify the requested change.",
                        "deliverables": ["Patch", "LogicNodes"],
                        "risk_notes": ["Watch for regression drift."],
                        "source": "llm",
                        "llm_route": "primary",
                        "model_provider": "openai",
                        "model": "gpt-5.2-mini",
                    }
                ),
            ):
                await advance_mission_lifecycle_v2(
                    app=app,
                    mission_id="test-m1",
                    settings=settings,
                    validator=validator,
                    emit_state_event_fn=emit_fn,
                    prepare_chain_fn=prepare_fn,
                    completion_check_fn=completion_fn,
                )

        assert len(state["transitions"]) == 9
        assert state["transitions"][0] == (
            "QUEUED", "PM_INTAKE", "MISSION_PM_INTAKE"
        )
        assert state["transitions"][-1] == (
            "VERIFIED", "COMPLETE", "MISSION_COMPLETE"
        )

        prepare_fn.assert_not_awaited()
        # completion_fn called once (for verified->complete)
        completion_fn.assert_awaited_once()
        assert emit_fn.await_count == 10
        emitted_events = [call.kwargs["event_type"] for call in emit_fn.await_args_list]
        assert emitted_events[:5] == [
            "MISSION_PM_INTAKE",
            "MISSION_CEO_DELEGATED",
            "MISSION_POD_MANAGER_ASSIGNED",
            "MISSION_SPECIALIST_ASSIGNED",
            "MISSION_SPECIALIST_PLANNED",
        ]
        assert mission.metadata["ceo_delegation"]["pod_manager_agent_id"] == "AGENT-12-PODA-MGR"
        assert mission.metadata["specialist_plan"]["specialist_agent_id"] == "AGENT-14-PYTHON"
        assert "specialist_planned" in mission.metadata["mission_artifacts"]

    @pytest.mark.asyncio
    async def test_packages_source_bundle_before_completion(self) -> None:
        app = _make_app_state()
        settings = _make_settings()
        validator = MagicMock()

        mission = _make_mission()
        mission.metadata = {
            "source_code": "## FILE app.py\nprint('a')\n",
            "source": "builder",
        }
        emit_fn = AsyncMock()
        prepare_fn = AsyncMock(return_value=True)
        completion_fn = AsyncMock(return_value=(True, {}))
        state, fetch_mission, update_metadata, transition_mission_state, insert_mission_event = (
            _make_stateful_storage(mission)
        )
        build_upserts: list[tuple[Any, ...]] = []

        with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
            mock_storage.transition_mission_state = transition_mission_state
            mock_storage.fetch_mission = fetch_mission
            mock_storage.update_mission_metadata = update_metadata
            mock_storage.insert_mission_event = insert_mission_event
            mock_storage.upsert_build_artifact = lambda *args: build_upserts.append(args) or {
                "artifact_id": "source-bundle-package",
                "status": "SUCCESS",
            }

            with patch(
                "orchestrator.mission_flow_v2.generate_ceo_delegation",
                AsyncMock(
                    return_value={
                        "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                        "specialist_agent_id": "AGENT-14-PYTHON",
                    }
                ),
            ), patch(
                "orchestrator.mission_flow_v2.generate_pod_manager_delegation",
                AsyncMock(
                    return_value={
                        "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                        "specialist_agent_id": "AGENT-14-PYTHON",
                    }
                ),
            ), patch(
                "orchestrator.mission_flow_v2.generate_specialist_plan",
                AsyncMock(
                    return_value={
                        "specialist_agent_id": "AGENT-14-PYTHON",
                        "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                        "plan_summary": "Implement and verify the requested change.",
                        "deliverables": ["Patch"],
                        "risk_notes": ["Watch for regression drift."],
                    }
                ),
            ):
                await advance_mission_lifecycle_v2(
                    app=app,
                    mission_id="test-m1",
                    settings=settings,
                    validator=validator,
                    emit_state_event_fn=emit_fn,
                    prepare_chain_fn=prepare_fn,
                    completion_check_fn=completion_fn,
                )

        assert build_upserts
        assert build_upserts[0][2] == "source-bundle-package"
        assert "build_packaged" in mission.metadata["mission_artifacts"]

    @pytest.mark.asyncio
    async def test_stops_when_pm_intake_persistence_fails(self) -> None:
        app = _make_app_state()
        settings = _make_settings()
        validator = MagicMock()
        mission = _make_mission()
        emit_fn = AsyncMock()
        prepare_fn = AsyncMock(return_value=False)
        completion_fn = AsyncMock(return_value=(True, {}))

        with patch(
            "orchestrator.mission_flow_v2.storage"
        ) as mock_storage:
            mock_storage.fetch_mission = lambda *_args: mission
            mock_storage.update_mission_metadata = lambda *_args: None
            mock_storage.transition_mission_state = MagicMock(return_value=None)
            mock_storage.insert_mission_event = lambda *args, **kwargs: None

            with patch(
                "orchestrator.mission_flow_v2.generate_ceo_delegation",
                AsyncMock(return_value={}),
            ):
                await advance_mission_lifecycle_v2(
                    app=app,
                    mission_id="test-m1",
                    settings=settings,
                    validator=validator,
                    emit_state_event_fn=emit_fn,
                    prepare_chain_fn=prepare_fn,
                    completion_check_fn=completion_fn,
                )

        mock_storage.transition_mission_state.assert_not_called()
        prepare_fn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stops_on_completion_blocked(self) -> None:
        """When artifacts aren't ready, lifecycle halts at VERIFIED."""
        app = _make_app_state()
        settings = _make_settings()
        validator = MagicMock()
        mission = _make_mission()

        emit_fn = AsyncMock()
        prepare_fn = AsyncMock(return_value=True)
        completion_fn = AsyncMock(
            return_value=(False, {"has_pod_assignment": False})
        )
        state, fetch_mission, update_metadata, transition_mission_state, insert_mission_event = (
            _make_stateful_storage(mission)
        )

        with patch(
            "orchestrator.mission_flow_v2.storage"
        ) as mock_storage:
            mock_storage.transition_mission_state = transition_mission_state
            mock_storage.fetch_mission = fetch_mission
            mock_storage.update_mission_metadata = update_metadata
            mock_storage.insert_mission_event = insert_mission_event

            with patch(
                "orchestrator.mission_flow_v2.generate_ceo_delegation",
                AsyncMock(
                    return_value={
                        "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                        "specialist_agent_id": "AGENT-14-PYTHON",
                    }
                ),
            ), patch(
                "orchestrator.mission_flow_v2.generate_pod_manager_delegation",
                AsyncMock(
                    return_value={
                        "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                        "specialist_agent_id": "AGENT-14-PYTHON",
                    }
                ),
            ), patch(
                "orchestrator.mission_flow_v2.generate_specialist_plan",
                AsyncMock(
                    return_value={
                        "specialist_agent_id": "AGENT-14-PYTHON",
                        "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                        "plan_summary": "Fallback plan",
                        "deliverables": ["Patch"],
                        "risk_notes": ["Watch"],
                    }
                ),
            ):
                await advance_mission_lifecycle_v2(
                    app=app,
                    mission_id="test-m1",
                    settings=settings,
                    validator=validator,
                    emit_state_event_fn=emit_fn,
                    prepare_chain_fn=prepare_fn,
                    completion_check_fn=completion_fn,
                )

        assert len(state["transitions"]) == 8
        assert "MISSION_COMPLETION_BLOCKED" in mission.metadata["last_chain_event_type"]
        prepare_fn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stops_on_transition_failure(self) -> None:
        """When storage returns None, lifecycle halts."""
        app = _make_app_state()
        settings = _make_settings()
        validator = MagicMock()
        emit_fn = AsyncMock()
        prepare_fn = AsyncMock(return_value=True)
        completion_fn = AsyncMock(return_value=(True, {}))

        call_count = 0
        mission = _make_mission()

        def fetch_mission(_settings: Any, _mission_id: str) -> MagicMock:
            return mission

        def update_metadata(
            _settings: Any,
            _mission_id: str,
            metadata: dict[str, Any],
        ) -> MagicMock:
            mission.metadata = dict(metadata)
            return mission

        def mock_transition(
            _s: Any, _mid: str,
            expected: MissionState, new: MissionState, event: str,
        ) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                return None  # fail on 3rd transition
            mission.state = new
            return mission

        with patch(
            "orchestrator.mission_flow_v2.storage"
        ) as mock_storage:
            mock_storage.transition_mission_state = mock_transition
            mock_storage.fetch_mission = fetch_mission
            mock_storage.update_mission_metadata = update_metadata
            mock_storage.insert_mission_event = lambda *args, **kwargs: None

            with patch(
                "orchestrator.mission_flow_v2.generate_ceo_delegation",
                AsyncMock(
                    return_value={
                        "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                        "specialist_agent_id": "AGENT-14-PYTHON",
                    }
                ),
            ), patch(
                "orchestrator.mission_flow_v2.generate_pod_manager_delegation",
                AsyncMock(
                    return_value={
                        "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                        "specialist_agent_id": "AGENT-14-PYTHON",
                    }
                ),
            ):
                await advance_mission_lifecycle_v2(
                    app=app,
                    mission_id="test-m1",
                    settings=settings,
                    validator=validator,
                    emit_state_event_fn=emit_fn,
                    prepare_chain_fn=prepare_fn,
                    completion_check_fn=completion_fn,
                )

        assert call_count == 3
        assert emit_fn.await_count == 2  # only 2 successful emits
        prepare_fn.assert_not_awaited()


# ------------------------------------------------------------------
# MissionState enum v2 values exist
# ------------------------------------------------------------------


class TestMissionStateV2Enum:
    def test_pm_intake_exists(self) -> None:
        assert MissionState.pm_intake.value == "PM_INTAKE"

    def test_ceo_delegated_exists(self) -> None:
        assert MissionState.ceo_delegated.value == "CEO_DELEGATED"

    def test_pod_assigned_exists(self) -> None:
        assert MissionState.pod_assigned.value == "POD_ASSIGNED"

    def test_specialist_assigned_exists(self) -> None:
        s = MissionState.specialist_assigned
        assert s.value == "SPECIALIST_ASSIGNED"

    def test_gating_exists(self) -> None:
        assert MissionState.gating.value == "GATING"

    def test_fusion_exists(self) -> None:
        assert MissionState.fusion.value == "FUSION"

    def test_v1_states_still_exist(self) -> None:
        """Ensure v1.1 states are unmodified."""
        assert MissionState.intake.value == "INTAKE"
        assert MissionState.queued.value == "QUEUED"
        assert MissionState.running.value == "RUNNING"
        assert MissionState.verified.value == "VERIFIED"
        assert MissionState.complete.value == "COMPLETE"
        assert MissionState.failed.value == "FAILED"


# ------------------------------------------------------------------
# Feature flag in Settings
# ------------------------------------------------------------------


class TestSettingsV2Flag:
    def test_default_is_false(self) -> None:
        from orchestrator.settings import load_settings

        with patch.dict(
            "os.environ",
            {"MISSION_FLOW_V2_ENABLED": "false"},
            clear=False,
        ):
            settings = load_settings()
            assert settings.mission_flow_v2_enabled is False

    def test_enabled_when_true(self) -> None:
        from orchestrator.settings import load_settings

        with patch.dict(
            "os.environ",
            {"MISSION_FLOW_V2_ENABLED": "true"},
            clear=False,
        ):
            settings = load_settings()
            assert settings.mission_flow_v2_enabled is True


@pytest.mark.asyncio
async def test_scaling_emits_partition_events_and_waits_for_results() -> None:
    app = _make_app_state()
    settings = _make_settings()
    settings.agent_scaling_enabled = True
    settings.agent_scaling_items_per_instance = 1
    settings.agent_scaling_max_instances = 4
    settings.max_stream_len = 100
    settings.default_priority = "NORMAL"
    settings.producer_name = "orchestrator"
    settings.state_stream = "missions.state"
    validator = MagicMock()
    validator.validate = MagicMock()

    mission = _make_mission()
    mission.metadata = {
        "source_code": "## FILE app.py\nprint('a')\n\n## FILE worker.py\nprint('b')\n",
    }
    emit_fn = AsyncMock()
    completion_fn = AsyncMock(return_value=(True, {}))
    state, fetch_mission, update_metadata, transition_mission_state, insert_mission_event = (
        _make_stateful_storage(mission)
    )

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.transition_mission_state = transition_mission_state
        mock_storage.fetch_mission = fetch_mission
        mock_storage.update_mission_metadata = update_metadata
        mock_storage.insert_mission_event = insert_mission_event

        with patch(
            "orchestrator.mission_flow_v2.generate_ceo_delegation",
            AsyncMock(
                return_value={
                    "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                    "specialist_agent_id": "AGENT-14-PYTHON",
                }
            ),
        ), patch(
            "orchestrator.mission_flow_v2.generate_pod_manager_delegation",
            AsyncMock(
                return_value={
                    "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                    "specialist_agent_id": "AGENT-14-PYTHON",
                }
            ),
        ), patch(
            "orchestrator.mission_flow_v2.generate_specialist_plan",
            AsyncMock(
                return_value={
                    "specialist_agent_id": "AGENT-14-PYTHON",
                    "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                    "plan_summary": "Split work by file.",
                    "deliverables": ["Patch"],
                    "risk_notes": ["Watch"],
                }
            ),
        ):
            await advance_mission_lifecycle_v2(
                app=app,
                mission_id="test-m1",
                settings=settings,
                validator=validator,
                emit_state_event_fn=emit_fn,
                prepare_chain_fn=AsyncMock(return_value=True),
                completion_check_fn=completion_fn,
            )

    assert len(state["transitions"]) == 5
    emitted_events = [call.kwargs["event_type"] for call in emit_fn.await_args_list]
    assert "MISSION_RUNNING" in emitted_events
    assert "MISSION_GATING" not in emitted_events
    assert app.state.redis.xadd.await_count == 2
