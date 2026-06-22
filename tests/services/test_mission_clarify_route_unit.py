from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from orchestrator.models import MissionClarifyRequest, MissionRecord, MissionState
from orchestrator.routes import missions as mission_routes


@pytest.mark.asyncio
async def test_clarify_mission_requeues_and_restarts_lifecycle() -> None:
    app = SimpleNamespace(
        state=SimpleNamespace(
            settings=object(),
            redis=AsyncMock(),
            redis_ready=True,
            protocol_ready=True,
            envelope_validator=MagicMock(),
        )
    )
    request = SimpleNamespace(app=app)
    mission = MissionRecord(
        mission_id="mission-clarify-1",
        prompt="Build the app",
        requested_target_language="python",
        metadata={"chain_trace": []},
        state=MissionState.clarifying,
        created_at=datetime.now(UTC),
    )
    updated_metadata: dict[str, Any] = {}

    def update_mission_metadata(_settings: Any, _mission_id: str, metadata: dict[str, Any]) -> MissionRecord:
        updated_metadata.update(metadata)
        return mission.model_copy(update={"metadata": metadata})

    def transition_mission_state(
        _settings: Any,
        _mission_id: str,
        expected_state: MissionState,
        new_state: MissionState,
        event_type: str,
    ) -> MissionRecord:
        assert expected_state == MissionState.clarifying
        assert new_state == MissionState.queued
        assert event_type == "MISSION_CLARIFICATION_APPLIED"
        return mission.model_copy(update={"state": new_state, "metadata": dict(updated_metadata)})

    with patch("orchestrator.main._ensure_db_ready", AsyncMock(return_value=(True, True))), patch(
        "orchestrator.main._fetch_existing_mission", AsyncMock(return_value=mission)
    ), patch("orchestrator.main.emit_state_event", AsyncMock()) as emit_state_event, patch(
        "orchestrator.main.start_lifecycle_task"
    ) as start_lifecycle_task, patch.object(
        mission_routes.storage,
        "update_mission_metadata",
        side_effect=update_mission_metadata,
    ), patch.object(
        mission_routes.storage,
        "transition_mission_state",
        side_effect=transition_mission_state,
    ), patch.object(mission_routes, "record_audit_event", AsyncMock()):
        result = await mission_routes.clarify_mission(
            request,
            "mission-clarify-1",
            MissionClarifyRequest(clarification="Use Kivy and package for Android."),
            None,
        )

    assert result.state == MissionState.queued
    assert updated_metadata["pm_clarification"] == "Use Kivy and package for Android."
    assert updated_metadata["user_intent"] == "finalize_plan"
    assert any(
        event.get("event_type") == "MISSION_CLARIFICATION_RECEIVED"
        for event in updated_metadata.get("chain_trace", [])
    )
    emit_state_event.assert_awaited_once()
    assert emit_state_event.await_args.args[4] == "MISSION_CLARIFICATION_APPLIED"
    start_lifecycle_task.assert_called_once_with(app, "mission-clarify-1")


@pytest.mark.asyncio
async def test_prepare_pm_intake_passes_operator_clarification_to_pm_contract() -> None:
    import importlib

    mission_flow_v2 = importlib.import_module("orchestrator.mission_flow_v2")
    app = SimpleNamespace(state=SimpleNamespace(redis_ready=False, redis=None))
    settings = object()
    mission = MissionRecord(
        mission_id="mission-clarify-2",
        prompt="Build the app",
        requested_target_language="python",
        metadata={
            "mission_type": "BUILD_NEW",
            "pm_clarification": "Use Kivy and package with Buildozer.",
        },
        state=MissionState.queued,
        created_at=datetime.now(UTC),
    )

    def fetch_mission(_settings: Any, _mission_id: str) -> MissionRecord:
        return mission

    def update_mission_metadata(_settings: Any, _mission_id: str, metadata: dict[str, Any]) -> MissionRecord:
        mission.metadata = dict(metadata)
        return mission

    feature_contract = {
        "schema_version": "feature_contract.v1",
        "title": "Mobile strategy game",
        "summary": "Build a Python mobile game.",
        "functional_requirements": ["Build the game"],
        "acceptance_criteria": ["Runs locally"],
        "risk_notes": [],
        "ambiguity_score": 0.0,
        "source": "llm",
    }
    generate_contract = AsyncMock(return_value=feature_contract)

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.fetch_mission = fetch_mission
        mock_storage.update_mission_metadata = update_mission_metadata
        mock_storage.insert_mission_event = MagicMock()
        with patch(
            "orchestrator.mission_flow_v2.generate_pm_feature_contract",
            generate_contract,
        ), patch("orchestrator.mission_flow_v2.record_audit_event", AsyncMock()):
            result = await mission_flow_v2._prepare_pm_intake(
                app=app,
                settings=settings,
                validator=MagicMock(),
                emit_state_event_fn=AsyncMock(),
                mission_id="mission-clarify-2",
            )

    assert result is True
    generate_contract.assert_awaited_once()
    assert generate_contract.await_args.kwargs["conversation_context"] == {
        "operator_clarification": "Use Kivy and package with Buildozer."
    }
