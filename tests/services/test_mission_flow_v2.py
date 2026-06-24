"""Tests for mission_flow_v2.py — 11-phase v2 lifecycle engine."""
from __future__ import annotations

import asyncio
import importlib
import inspect
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
orchestrator_mission_flow_v2 = importlib.import_module("orchestrator.mission_flow_v2")
orchestrator_models = importlib.import_module("orchestrator.models")
orchestrator_is_agent = importlib.import_module("orchestrator.is_agent")

V1_TRANSITIONS = orchestrator_mission_flow_v2.V1_TRANSITIONS
V2_EVENT_TO_PHASE = orchestrator_mission_flow_v2.V2_EVENT_TO_PHASE
V2_PHASE_ORDER = orchestrator_mission_flow_v2.V2_PHASE_ORDER
V2_TRANSITIONS = orchestrator_mission_flow_v2.V2_TRANSITIONS
advance_mission_lifecycle_v2 = orchestrator_mission_flow_v2.advance_mission_lifecycle_v2
v2_map_state_to_v1 = orchestrator_mission_flow_v2.v2_map_state_to_v1
v2_phase_index = orchestrator_mission_flow_v2.v2_phase_index
MissionState = orchestrator_models.MissionState
V2_STATES = orchestrator_models.V2_STATES


@pytest.fixture(autouse=True)
def _deterministic_pm_contract(monkeypatch):
    llm_delegation = importlib.import_module("orchestrator.llm_delegation")
    monkeypatch.setattr(llm_delegation, "OPENAI_API_KEY", "")
    monkeypatch.setattr(llm_delegation, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(llm_delegation, "GEMINI_API_KEY", "")

    async def _generate_pm_feature_contract(**_kwargs):
        return {
            "schema_version": "feature_contract.v1",
            "title": "Test mission",
            "summary": "Execute the deterministic test mission.",
            "intake_status": "ready",
            "ambiguity_score": 0.0,
            "functional_requirements": ["Complete the requested test behavior."],
            "acceptance_criteria": ["The test behavior completes successfully."],
            "risk_notes": [],
            "clarifying_questions": [],
            "source": "test",
        }

    monkeypatch.setattr(
        orchestrator_mission_flow_v2,
        "generate_pm_feature_contract",
        _generate_pm_feature_contract,
    )


def test_advance_mission_lifecycle_v2_resets_llm_contextvars() -> None:
    src = textwrap.dedent(inspect.getsource(advance_mission_lifecycle_v2))

    assert "_llm_current_mission_id.set(mission_id)" in src
    assert "_llm_current_settings.set(settings)" in src
    assert "finally:" in src
    assert "_llm_current_mission_id.reset(_t1)" in src
    assert "_llm_current_settings.reset(_t2)" in src

def test_build_mission_charter_validates_against_schema() -> None:
    charter = orchestrator_mission_flow_v2.build_mission_charter(
        mission_id="mission-1",
        prompt="Build a Python CSV reader",
        requested_target_language="python",
        feature_contract={
            "summary": "Build a Python CSV reader",
            "functional_requirements": ["Read CSV rows"],
            "acceptance_criteria": ["Returns a list of dictionaries"],
            "risk_notes": ["Validate input path"],
            "source": "fallback",
        },
        mission_type="BUILD_NEW",
        depth_mode="STANDARD",
        output_mode="FULL_BUILD",
    )

    assert charter["schema"] == "mission_charter.v1"
    assert charter["schema_version"] == "1.0.0"
    assert charter["mission_type"] == "BUILD_NEW"
    assert charter["target_outcome"] == "Build a Python CSV reader"
    assert charter["success_criteria"] == ["Returns a list of dictionaries"]
    assert charter["statement_of_work"]["objective"] == "Build a Python CSV reader"
    assert charter["product_requirements"]["functional_requirements"] == ["Read CSV rows"]
    assert charter["phased_build_plan"][0]["owner_agent_id"] == "AGENT-01-PM"
    assert charter["risk_register"][0]["risk"] == "Validate input path"
    assert charter["test_strategy"]["acceptance_tests"] == ["Returns a list of dictionaries"]


def test_mission_charter_schema_validation_rejects_missing_required_field() -> None:
    with pytest.raises(ValueError, match="missing required fields"):
        orchestrator_mission_flow_v2.validate_mission_charter_schema(
            {"schema": "mission_charter.v1"}
        )


def test_run_fetch_phase_mirrors_docs_to_global_and_mission_knowledge(monkeypatch) -> None:
    writes: list[tuple[str, str, dict[str, Any]]] = []

    def _list_knowledge(_settings: Any, _mission_id: str, limit: int = 200) -> list[dict[str, Any]]:
        _ = limit
        return []

    def _upsert_knowledge(
        _settings: Any,
        mission_id: str,
        knowledge_id: str,
        content: dict[str, Any],
        _created_at: str,
    ) -> dict[str, Any]:
        writes.append((mission_id, knowledge_id, content))
        return {"knowledge_id": knowledge_id}

    fake_storage = SimpleNamespace(
        list_knowledge=_list_knowledge,
        upsert_knowledge=_upsert_knowledge,
    )
    monkeypatch.setitem(sys.modules, "orchestrator.storage", fake_storage)

    result = asyncio.run(
        orchestrator_is_agent.run_fetch_phase(
            mission_id="mission-1",
            required_languages=["python"],
            settings=object(),
        )
    )

    assert result["indexed_languages"] == ["python"]
    assert result["refreshed_languages"] == ["python"]
    assert result["unchanged_languages"] == []
    assert result["knowledge_ids"] == ["docs.python.bootstrap"]
    assert result["embedding_provider"] == "deterministic"
    assert {write[0] for write in writes} == {"__knowledge_lake__", "mission-1"}
    assert all(write[2]["kind"] == "bootstrap_documentation" for write in writes)


def test_run_fetch_phase_skips_global_refresh_when_hash_is_current(monkeypatch) -> None:
    writes: list[tuple[str, str, dict[str, Any]]] = []
    current = orchestrator_is_agent._bootstrap_content_for_language("python")

    def _list_knowledge(_settings: Any, _mission_id: str, limit: int = 200) -> list[dict[str, Any]]:
        _ = limit
        return [
            {
                "mission_id": "__knowledge_lake__",
                "knowledge_id": "docs.python.bootstrap",
                "content": {"hash": current["hash"]},
            }
        ]

    def _upsert_knowledge(
        _settings: Any,
        mission_id: str,
        knowledge_id: str,
        content: dict[str, Any],
        _created_at: str,
    ) -> dict[str, Any]:
        writes.append((mission_id, knowledge_id, content))
        return {"knowledge_id": knowledge_id}

    fake_storage = SimpleNamespace(
        list_knowledge=_list_knowledge,
        upsert_knowledge=_upsert_knowledge,
    )
    monkeypatch.setitem(sys.modules, "orchestrator.storage", fake_storage)

    result = asyncio.run(
        orchestrator_is_agent.run_fetch_phase(
            mission_id="mission-1",
            required_languages=["python"],
            settings=object(),
        )
    )

    assert result["refreshed_languages"] == []
    assert result["unchanged_languages"] == ["python"]
    assert [write[0] for write in writes] == ["mission-1"]


# ------------------------------------------------------------------
# Transition table structure
# ------------------------------------------------------------------


class TestV2Transitions:
    def test_has_10_transitions(self) -> None:
        assert len(V2_TRANSITIONS) == 10

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

    def test_v2_state_set_covers_transition_chain(self) -> None:
        transition_states = {
            state
            for source, target, _event_type in V2_TRANSITIONS
            for state in (source, target)
        }
        assert transition_states <= V2_STATES


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
    def test_has_12_phases(self) -> None:
        assert len(V2_PHASE_ORDER) == 13

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
    def test_covers_all_13_events(self) -> None:
        assert len(V2_EVENT_TO_PHASE) == 14

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
            (MissionState.fetch, MissionState.queued),
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

    def test_complete_is_11(self) -> None:
        assert v2_phase_index(MissionState.complete) == 12

    def test_failed_is_minus_1(self) -> None:
        assert v2_phase_index(MissionState.failed) == -1

    def test_running_is_7(self) -> None:
        assert v2_phase_index(MissionState.running) == 8


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


@pytest.mark.asyncio
async def test_prepare_pm_intake_generates_aim_for_source_analysis_mission() -> None:
    app = _make_app_state()
    settings = _make_settings()
    validator = MagicMock()
    mission = _make_mission()
    mission.metadata = {
        "mission_type": "ANALYZE_ONLY",
        "source_code": "## FILE app.py\nprint('a')\n",
    }
    _state, fetch_mission, update_metadata, _transition_mission_state, _insert_mission_event = (
        _make_stateful_storage(mission)
    )
    feature_contract = {
        "schema_version": "feature_contract.v1",
        "title": "Review source",
        "summary": "Analyze supplied source",
        "functional_requirements": ["Inventory source"],
        "acceptance_criteria": ["AIM is produced"],
        "risk_notes": [],
        "source": "fallback",
    }
    generated_aim = {
        "schema_version": "aim.v1",
        "aim_id": "aim-test-m1",
        "mission_id": "test-m1",
        "repository_summary": "One Python file.",
        "primary_language": "python",
        "detected_languages": ["python"],
        "total_functions": 0,
        "total_classes": 0,
        "complexity_assessment": "low",
        "human_approval_recommended": False,
        "source": "fallback",
        "extraction_summary": {"files_analyzed": 1},
    }

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.fetch_mission = fetch_mission
        mock_storage.update_mission_metadata = update_metadata
        with patch(
            "orchestrator.mission_flow_v2.generate_pm_feature_contract",
            AsyncMock(return_value=feature_contract),
        ), patch(
            "orchestrator.mission_flow_v2.generate_aim",
            AsyncMock(return_value=generated_aim),
        ) as aim_mock, patch(
            "orchestrator.mission_flow_v2.record_audit_event",
            AsyncMock(),
        ):
            result = await orchestrator_mission_flow_v2._prepare_pm_intake(
                app=app,
                settings=settings,
                validator=validator,
                emit_state_event_fn=AsyncMock(),
                mission_id="test-m1",
            )

    assert result is True
    aim_mock.assert_awaited_once()
    assert mission.metadata["application_intelligence_map"]["aim_id"] == "aim-test-m1"
    assert any(
        event["event_type"] == "MISSION_AIM_GENERATED"
        for event in mission.metadata["chain_trace"]
    )
    assert "aim" in mission.metadata["mission_artifacts"]


@pytest.mark.asyncio
async def test_prepare_pm_intake_high_ambiguity_enters_clarifying() -> None:
    """High ambiguity (>=0.7) must transition QUEUED -> CLARIFYING and emit
    MISSION_CLARIFYING, then return False to pause the lifecycle."""
    app = _make_app_state()
    settings = _make_settings()
    validator = MagicMock()
    mission = _make_mission(state=MissionState.queued)
    mission.metadata = {"mission_type": "BUILD_NEW"}
    state, fetch_mission, update_metadata, transition_mission_state, _insert = (
        _make_stateful_storage(mission)
    )
    ambiguous_contract = {
        "schema_version": "feature_contract.v1",
        "title": "Ambiguous",
        "summary": "Underspecified request",
        "ambiguity_score": 0.85,
        "clarifying_questions": ["Which language?", "What scope?"],
        "source": "llm",
    }
    emit_fn = AsyncMock()

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.fetch_mission = fetch_mission
        mock_storage.update_mission_metadata = update_metadata
        mock_storage.transition_mission_state = transition_mission_state
        with patch(
            "orchestrator.mission_flow_v2.generate_pm_feature_contract",
            AsyncMock(return_value=ambiguous_contract),
        ):
            result = await orchestrator_mission_flow_v2._prepare_pm_intake(
                app=app,
                settings=settings,
                validator=validator,
                emit_state_event_fn=emit_fn,
                mission_id="test-m1",
            )

    # Preparer returns False to pause the lifecycle for clarification.
    assert result is False
    # Transition used the actual current state (QUEUED), not PM_INTAKE.
    assert (
        MissionState.queued.value,
        MissionState.clarifying.value,
        "MISSION_CLARIFYING",
    ) in state["transitions"]
    # The clarifying event was published with the correct kwargs shape.
    emit_fn.assert_awaited_once()
    _, kwargs = emit_fn.call_args
    assert kwargs["event_type"] == "MISSION_CLARIFYING"
    assert "mission" in kwargs and "redis_client" in kwargs
    assert mission.metadata["last_ambiguity_score"] == 0.85
    assert mission.metadata["clarifying_questions"] == ["Which language?", "What scope?"]


@pytest.mark.asyncio
async def test_prepare_equivalence_report_records_nonblocking_report() -> None:
    app = _make_app_state()
    settings = _make_settings()
    mission = _make_mission(state=MissionState.verified)
    mission.metadata = {
        "generated_output": {
            "source": "llm",
            "generated_code": "def read_csv(path):\n    return []\n",
            "filename": "solution.py",
            "language": "python",
        },
        "feature_contract": {"acceptance_criteria": ["Returns rows"]},
    }
    build_artifacts = [
        {
            "artifact_id": "generated-code-output",
            "artifact_type": "generated_code",
            "status": "SUCCESS",
            "digest_sha256": "abc123",
            "verification": {"verified": True, "verification_method": "sha256"},
        }
    ]

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.list_build_artifacts = lambda *_args: build_artifacts
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission
        )
        with patch("orchestrator.mission_flow_v2.record_audit_event", AsyncMock()):
            updated, ready, report = await orchestrator_mission_flow_v2._prepare_equivalence_report(
                app=app,
                settings=settings,
                mission=mission,
            )

    assert updated is mission
    assert ready is True
    assert report["passed"] is True
    assert mission.metadata["equivalence_report"]["report_id"] == "equivalence-test-m1"
    assert any(
        event["event_type"] == "MISSION_EQUIVALENCE_VERIFIED"
        for event in mission.metadata["chain_trace"]
    )


@pytest.mark.asyncio
async def test_prepare_equivalence_report_blocks_when_enforced() -> None:
    app = _make_app_state()
    settings = _make_settings()
    settings.mission_equivalence_enforcement_enabled = True
    mission = _make_mission(state=MissionState.verified)
    mission.metadata = {
        "generated_output": {
            "source": "llm",
            "generated_code": "def read_csv(path):\n    return []\n",
            "filename": "solution.py",
            "language": "python",
        }
    }

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.list_build_artifacts = lambda *_args: []
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission
        )
        with patch("orchestrator.mission_flow_v2.record_audit_event", AsyncMock()):
            _updated, ready, report = (
                await orchestrator_mission_flow_v2._prepare_equivalence_report(
                    app=app,
                    settings=settings,
                    mission=mission,
                )
            )

    assert ready is False
    assert report["blocking"] is True
    assert any(
        event["event_type"] == "MISSION_EQUIVALENCE_BLOCKED"
        for event in mission.metadata["chain_trace"]
    )


@pytest.mark.asyncio
async def test_prepare_security_compliance_report_records_pass() -> None:
    app = _make_app_state()
    settings = _make_settings()
    mission = _make_mission(state=MissionState.verified)
    mission.metadata = {
        "generated_output": {
            "source": "llm",
            "generated_code": "def read_csv(path):\n    return []\n",
            "filename": "solution.py",
            "language": "python",
        },
        "equivalence_report": {"report_id": "equivalence-test-m1", "passed": True},
    }

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission
        )
        with patch("orchestrator.mission_flow_v2.record_audit_event", AsyncMock()):
            updated, ready, report = (
                await orchestrator_mission_flow_v2._prepare_security_compliance_report(
                    app=app,
                    settings=settings,
                    mission=mission,
                )
            )

    assert updated is mission
    assert ready is True
    assert report["passed"] is True
    assert mission.metadata["security_compliance_report"]["report_id"] == (
        "security-compliance-test-m1"
    )
    assert any(
        event["event_type"] == "MISSION_SECURITY_COMPLIANCE_PASSED"
        for event in mission.metadata["chain_trace"]
    )


@pytest.mark.asyncio
async def test_prepare_security_compliance_report_blocks_when_enforced() -> None:
    app = _make_app_state()
    settings = _make_settings()
    settings.mission_security_compliance_enforcement_enabled = True
    mission = _make_mission(state=MissionState.verified)
    mission.metadata = {
        "generated_output": {
            "source": "llm",
            "generated_code": "API_KEY = 'sk-test-secret-value-123456'\n",
            "filename": "solution.py",
            "language": "python",
        },
        "equivalence_report": {"report_id": "equivalence-test-m1", "passed": True},
    }

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission
        )
        with patch("orchestrator.mission_flow_v2.record_audit_event", AsyncMock()):
            _updated, ready, report = (
                await orchestrator_mission_flow_v2._prepare_security_compliance_report(
                    app=app,
                    settings=settings,
                    mission=mission,
                )
            )

    assert ready is False
    assert report["blocking"] is True
    assert any(
        event["event_type"] == "MISSION_SECURITY_COMPLIANCE_BLOCKED"
        for event in mission.metadata["chain_trace"]
    )


@pytest.mark.asyncio
async def test_prepare_dependency_absorption_reports_records_plan() -> None:
    app = _make_app_state()
    settings = _make_settings()
    mission = _make_mission(state=MissionState.verified)
    mission.metadata = {
        "generated_output": {"dependencies": ["left-pad"]},
        "equivalence_report": {"report_id": "equivalence-test-m1", "passed": True},
        "security_compliance_report": {
            "report_id": "security-compliance-test-m1",
            "passed": True,
            "blocking": False,
        },
    }

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission
        )
        with patch("orchestrator.mission_flow_v2.record_audit_event", AsyncMock()):
            updated, ready, report = (
                await orchestrator_mission_flow_v2._prepare_dependency_absorption_reports(
                    app=app,
                    settings=settings,
                    mission=mission,
                )
            )

    assert updated is mission
    assert ready is True
    assert report["status"] == "planned"
    assert mission.metadata["dependency_inventory"]["dependency_count"] == 1
    assert mission.metadata["dependency_classification_report"]["classifications"][0][
        "decision"
    ] == "absorb"
    assert any(
        event["event_type"] == "MISSION_DEPENDENCY_INVENTORY_CREATED"
        for event in mission.metadata["chain_trace"]
    )
    assert any(
        event["event_type"] == "MISSION_DEPENDENCY_ABSORPTION_PLANNED"
        for event in mission.metadata["chain_trace"]
    )


@pytest.mark.asyncio
async def test_prepare_dependency_absorption_reports_blocks_bad_license() -> None:
    app = _make_app_state()
    settings = _make_settings()
    mission = _make_mission(state=MissionState.verified)
    mission.metadata = {
        "application_intelligence_map": {"detected_dependencies": ["copyleft-helper"]},
        "dependency_licenses": {"copyleft-helper": "GPL-3.0"},
    }

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission
        )
        with patch("orchestrator.mission_flow_v2.record_audit_event", AsyncMock()):
            _updated, ready, report = (
                await orchestrator_mission_flow_v2._prepare_dependency_absorption_reports(
                    app=app,
                    settings=settings,
                    mission=mission,
                )
            )

    assert ready is False
    assert report["blocking"] is True
    assert any(
        event["event_type"] == "MISSION_DEPENDENCY_ABSORPTION_BLOCKED"
        for event in mission.metadata["chain_trace"]
    )


@pytest.mark.asyncio
async def test_prepare_fusion_regenerates_when_existing_output_is_fallback() -> None:
    mission = _make_mission(state=MissionState.fusion)
    mission.metadata = {
        "mission_contract": {"contract_summary": "Build a CSV reader"},
        "pod_group_standards": {
            "podA": {
                "canonical_logicnodes": [
                    {
                        "domain": "parsing",
                        "concept": "csv_reader",
                        "intent": "Read CSV rows",
                    }
                ]
            }
        },
        "generated_output": {
            "source": "fallback",
            "generated_code": "print('fallback')",
        },
        "assigned_specialist_agent_id": "AGENT-14-PYTHON",
    }
    master_stream = {
        "master_logic_stream": [
            {
                "node_id": "unified-001",
                "domain": "parsing",
                "concept": "csv_reader",
                "canonical_intent": "Read CSV rows",
                "source_pods": ["podA"],
                "dependency_order": 1,
            }
        ],
        "total_unified_nodes": 1,
        "eliminated_across_pods": 0,
        "ready_for_codegen": True,
        "source": "fallback",
    }
    generated_output = {
        "source": "llm",
        "generated_code": "def read_csv(path):\n    return []\n",
        "filename": "solution.py",
        "language": "python",
    }

    with (
        patch.object(
            orchestrator_mission_flow_v2,
            "generate_master_logic_stream",
            new=AsyncMock(return_value=master_stream),
        ),
        patch.object(
            orchestrator_mission_flow_v2,
            "generate_code_from_contract",
            new=AsyncMock(return_value=generated_output),
        ) as generate_code,
        patch.object(
            orchestrator_mission_flow_v2.storage,
            "update_mission_metadata",
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission,
        ),
    ):
        updated = await orchestrator_mission_flow_v2._prepare_fusion(
            app=_make_app_state(),
            settings=_make_settings(),
            validator=MagicMock(),
            emit_state_event_fn=AsyncMock(),
            mission=mission,
        )

    assert updated is mission
    assert mission.metadata["master_logic_stream"] == master_stream
    assert mission.metadata["generated_output"] == generated_output
    assert generate_code.await_count == 1
    assert any(
        event["event_type"] == "MISSION_LOGIC_FOLDED"
        for event in mission.metadata["chain_trace"]
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
            mock_storage.list_build_artifacts = lambda *_args: [
                {
                    "artifact_id": "generated-code-output",
                    "artifact_type": "generated_code",
                    "manifest": {"filename": "solution.py", "language": "python"},
                    "artifact_text": "def read_csv(path):\n    return []\n",
                }
            ]

            with patch(
                "orchestrator.mission_flow_v2.generate_pm_feature_contract",
                AsyncMock(
                    return_value={
                        "schema_version": "feature_contract.v1",
                        "title": "CSV reader",
                        "summary": "Build a Python CSV reader",
                        "functional_requirements": ["Read CSV rows"],
                        "acceptance_criteria": ["Returns a list of dicts"],
                        "risk_notes": [],
                        "ambiguity_score": 0.0,
                        "source": "fallback",
                    }
                ),
            ), patch(
                "orchestrator.mission_flow_v2.generate_ceo_delegation",
                AsyncMock(
                    return_value={
                        "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                        "specialist_agent_id": "AGENT-14-PYTHON",
                        "source": "llm",
                        "llm_route": "primary",
                        "model_provider": "openai",
                        "model": "gpt-5.5",
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
                        "model": "gpt-5.5",
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
                        "model": "gpt-5.5",
                    }
                ),
            ), patch(
                "orchestrator.mission_flow_v2.generate_pod_group_standard",
                AsyncMock(
                    return_value={
                        "schema_version": "pod_group_standard.v1",
                        "pod": "podA",
                        "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                        "mission_id": "test-m1",
                        "canonical_logicnodes": [
                            {
                                "standard_node_id": "standard-node-01-parsing-csv-reader",
                                "domain": "parsing",
                                "concept": "csv_reader",
                                "intent": "Read CSV rows",
                                "source_node_ids": ["node-1"],
                                "languages": ["python"],
                            }
                        ],
                        "eliminated_duplicates": 0,
                        "summary": "Canonical pod standard.",
                        "source": "fallback",
                        "model_provider": "openai",
                        "model": "gpt-5.5",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    }
                ),
            ), patch(
                "orchestrator.mission_flow_v2.generate_pm_delivery_summary",
                AsyncMock(
                    return_value={
                        "delivery_title": "Delivered CSV reader",
                        "delivery_summary": "Mission complete.",
                        "criteria_met": ["Returns CSV rows"],
                        "criteria_unmet": [],
                        "usage_notes": "Download generated code.",
                        "recommendations": [],
                        "primary_artifact_type": "generated_code",
                        "source": "fallback",
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

        assert len(state["transitions"]) == 10
        assert state["transitions"][0] == (
            "QUEUED", "PM_INTAKE", "MISSION_PM_INTAKE"
        )
        assert state["transitions"][-1] == (
            "VERIFIED", "COMPLETE", "MISSION_COMPLETE"
        )

        prepare_fn.assert_not_awaited()
        # completion_fn called once (for verified->complete)
        completion_fn.assert_awaited_once()
        assert emit_fn.await_count == 12
        emitted_events = [call.kwargs["event_type"] for call in emit_fn.await_args_list]
        assert emitted_events[:4] == [
            "MISSION_PM_INTAKE",
            "MISSION_FETCH",
            "MISSION_CEO_DELEGATED",
            "MISSION_POD_MANAGER_ASSIGNED",
        ]
        assert "MISSION_POD_GROUP_STANDARD_PRODUCED" in emitted_events
        assert mission.metadata["ceo_delegation"]["pod_manager_agent_id"] == "AGENT-12-PODA-MGR"
        assert mission.metadata["specialist_plan"]["specialist_agent_id"] == "AGENT-14-PYTHON"
        assert mission.metadata["pod_group_standards"]["podA"]["canonical_logicnodes"]
        assert mission.metadata["delivery_summary"]["delivery_title"] == "Delivered CSV reader"
        assert any(
            event["event_type"] == "MISSION_DELIVERED"
            for event in mission.metadata["chain_trace"]
        )
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
                "orchestrator.mission_flow_v2.generate_pm_feature_contract",
                AsyncMock(
                    return_value={
                        "schema_version": "feature_contract.v1",
                        "title": "CSV reader",
                        "summary": "Build a Python CSV reader",
                        "functional_requirements": ["Read CSV rows"],
                        "acceptance_criteria": ["Returns a list of dicts"],
                        "risk_notes": [],
                        "ambiguity_score": 0.0,
                        "source": "fallback",
                    }
                ),
            ), patch(
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

        # Lifecycle halts before the verified→complete transition fires;
        # all 9 prior normal-path transitions are recorded.
        assert len(state["transitions"]) == 9
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

    assert len(state["transitions"]) == 6
    emitted_events = [call.kwargs["event_type"] for call in emit_fn.await_args_list]
    assert "MISSION_RUNNING" in emitted_events
    assert "MISSION_GATING" not in emitted_events
    assert app.state.redis.xadd.await_count == 2


# ---------------------------------------------------------------------------
# VALID_TRANSITIONS centralization contract
# ---------------------------------------------------------------------------


class TestValidTransitionsContract:
    """Assert V2_TRANSITIONS (and V1_TRANSITIONS) only use state pairs that are
    listed in models.VALID_TRANSITIONS, making that dict the single source of
    truth for allowable state machine moves."""

    VALID_TRANSITIONS = orchestrator_models.VALID_TRANSITIONS

    def test_v2_transitions_respect_valid_transitions(self):
        """Every (from, to) pair in V2_TRANSITIONS must be in VALID_TRANSITIONS."""
        violations: list[str] = []
        for from_state, to_state, event_type in V2_TRANSITIONS:
            allowed = self.VALID_TRANSITIONS.get(from_state, set())
            if to_state not in allowed:
                violations.append(
                    f"V2_TRANSITIONS has {from_state.value!r} → {to_state.value!r} "
                    f"(event {event_type!r}) but VALID_TRANSITIONS does not permit it"
                )
        assert not violations, "\n".join(violations)

    def test_v1_transitions_respect_valid_transitions(self):
        """Every (from, to) pair in V1_TRANSITIONS must be in VALID_TRANSITIONS."""
        violations: list[str] = []
        for from_state, to_state, event_type in V1_TRANSITIONS:
            allowed = self.VALID_TRANSITIONS.get(from_state, set())
            if to_state not in allowed:
                violations.append(
                    f"V1_TRANSITIONS has {from_state.value!r} → {to_state.value!r} "
                    f"(event {event_type!r}) but VALID_TRANSITIONS does not permit it"
                )
        assert not violations, "\n".join(violations)

    def test_valid_transitions_covers_all_mission_states(self):
        """Every MissionState must appear as a key in VALID_TRANSITIONS."""
        missing = [
            state
            for state in MissionState
            if state not in self.VALID_TRANSITIONS
        ]
        assert not missing, f"States not in VALID_TRANSITIONS: {[s.value for s in missing]}"

    def test_valid_transitions_target_states_are_known(self):
        """Every destination state in VALID_TRANSITIONS must be a valid MissionState."""
        known = set(MissionState)
        bad: list[str] = []
        for from_state, to_states in self.VALID_TRANSITIONS.items():
            for to_state in to_states:
                if to_state not in known:
                    bad.append(
                        "VALID_TRANSITIONS["
                        f"{from_state.value!r}] contains unknown state {to_state!r}"
                    )
        assert not bad, "\n".join(bad)
