"""Tests for mission_flow_v2.py — 11-phase v2 lifecycle engine."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from orchestrator.mission_flow_v2 import (
    V1_TRANSITIONS,
    V2_EVENT_TO_PHASE,
    V2_PHASE_ORDER,
    V2_TRANSITIONS,
    advance_mission_lifecycle_v2,
    v2_map_state_to_v1,
    v2_phase_index,
)
from orchestrator.models import MissionState

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

        recorded_transitions: list[tuple[str, str, str]] = []

        def mock_transition(
            _settings: Any,
            _mid: str,
            expected: MissionState,
            new: MissionState,
            event: str,
        ) -> MagicMock:
            recorded_transitions.append(
                (expected.value, new.value, event)
            )
            m = _make_mission(state=new)
            return m

        with patch(
            "orchestrator.mission_flow_v2.storage"
        ) as mock_storage:
            mock_storage.transition_mission_state = mock_transition
            mock_storage.fetch_mission = lambda s, mid: mission
            mock_storage.update_mission_metadata = (
                lambda s, mid, meta: mission
            )
            mock_storage.insert_mission_event = (
                lambda *a, **kw: None
            )

            await advance_mission_lifecycle_v2(
                app=app,
                mission_id="test-m1",
                settings=settings,
                validator=validator,
                emit_state_event_fn=emit_fn,
                prepare_chain_fn=prepare_fn,
                completion_check_fn=completion_fn,
            )

        assert len(recorded_transitions) == 9
        assert recorded_transitions[0] == (
            "QUEUED", "PM_INTAKE", "MISSION_PM_INTAKE"
        )
        assert recorded_transitions[-1] == (
            "VERIFIED", "COMPLETE", "MISSION_COMPLETE"
        )

        # prepare_chain_fn called once (for first transition)
        prepare_fn.assert_awaited_once()
        # completion_fn called once (for verified->complete)
        completion_fn.assert_awaited_once()
        # emit_fn called once per transition
        assert emit_fn.await_count == 9

    @pytest.mark.asyncio
    async def test_stops_on_failed_prepare(self) -> None:
        app = _make_app_state()
        settings = _make_settings()
        validator = MagicMock()
        emit_fn = AsyncMock()
        prepare_fn = AsyncMock(return_value=False)
        completion_fn = AsyncMock(return_value=(True, {}))

        with patch(
            "orchestrator.mission_flow_v2.storage"
        ) as mock_storage:
            mock_storage.transition_mission_state = MagicMock(
                return_value=None
            )

            await advance_mission_lifecycle_v2(
                app=app,
                mission_id="test-m1",
                settings=settings,
                validator=validator,
                emit_state_event_fn=emit_fn,
                prepare_chain_fn=prepare_fn,
                completion_check_fn=completion_fn,
            )

        # No transitions should have occurred
        mock_storage.transition_mission_state.assert_not_called()

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

        transition_count = 0

        def mock_transition(
            _s: Any, _mid: str,
            expected: MissionState, new: MissionState, event: str,
        ) -> MagicMock:
            nonlocal transition_count
            transition_count += 1
            return _make_mission(state=new)

        with patch(
            "orchestrator.mission_flow_v2.storage"
        ) as mock_storage:
            mock_storage.transition_mission_state = mock_transition
            mock_storage.fetch_mission = lambda s, mid: mission
            mock_storage.update_mission_metadata = (
                lambda s, mid, meta: mission
            )
            mock_storage.insert_mission_event = (
                lambda *a, **kw: None
            )

            await advance_mission_lifecycle_v2(
                app=app,
                mission_id="test-m1",
                settings=settings,
                validator=validator,
                emit_state_event_fn=emit_fn,
                prepare_chain_fn=prepare_fn,
                completion_check_fn=completion_fn,
            )

        # 8 transitions (up to VERIFIED), the 9th (COMPLETE) blocked
        assert transition_count == 8

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

        def mock_transition(
            _s: Any, _mid: str,
            expected: MissionState, new: MissionState, event: str,
        ) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                return None  # fail on 3rd transition
            return _make_mission(state=new)

        with patch(
            "orchestrator.mission_flow_v2.storage"
        ) as mock_storage:
            mock_storage.transition_mission_state = mock_transition

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
