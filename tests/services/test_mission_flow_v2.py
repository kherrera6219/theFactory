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
orchestrator_mission_flow_v2_base = importlib.import_module("orchestrator.mission_flow_v2.base")
orchestrator_mission_flow_v2_runtime = importlib.import_module(
    "orchestrator.mission_flow_v2.phases_runtime"
)
orchestrator_mission_flow_v2_lifecycle = importlib.import_module(
    "orchestrator.mission_flow_v2.lifecycle"
)
orchestrator_mission_flow_v2_intake = importlib.import_module(
    "orchestrator.mission_flow_v2.phases_intake"
)
orchestrator_mission_flow_v2_build = importlib.import_module(
    "orchestrator.mission_flow_v2.phases_build"
)
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


def test_mission_flow_base_helpers_normalize_settings_and_schema_errors() -> None:
    settings = SimpleNamespace(
        enabled_yes=" yes ",
        disabled_no="off",
        invalid_bool="maybe",
        count_string="42",
        count_float=7.9,
        count_blank="",
        count_bool=True,
        count_bad="abc",
    )

    assert orchestrator_mission_flow_v2_base._setting_bool(settings, "enabled_yes") is True
    assert orchestrator_mission_flow_v2_base._setting_bool(settings, "disabled_no", True) is False
    assert orchestrator_mission_flow_v2_base._setting_bool(settings, "invalid_bool", True) is True
    assert orchestrator_mission_flow_v2_base._setting_bool(settings, "missing", False) is False
    assert orchestrator_mission_flow_v2_base._setting_int(settings, "count_string", 1) == 42
    assert orchestrator_mission_flow_v2_base._setting_int(settings, "count_float", 1) == 7
    assert orchestrator_mission_flow_v2_base._setting_int(settings, "count_blank", 3) == 3
    assert orchestrator_mission_flow_v2_base._setting_int(settings, "count_bool", 4) == 4
    assert orchestrator_mission_flow_v2_base._setting_int(settings, "count_bad", 5) == 5

    assert orchestrator_mission_flow_v2_base._extract_support_agent_flags(
        {"rationale": "Security and dependency review with tests"}, "BUILD_NEW"
    ) == ["AGENT-05-SECURITY", "AGENT-39-DEPABS", "AGENT-10-TESTER"]
    assert orchestrator_mission_flow_v2_base._extract_cross_pod_flags(
        {
            "clusters": [
                {"pod_manager_agent_id": "AGENT-12-PODA-MGR"},
                {"pod_manager_agent_id": "AGENT-18-PODB-MGR"},
            ]
        }
    ) == ["AGENT-12-PODA-MGR", "AGENT-18-PODB-MGR"]
    assert orchestrator_mission_flow_v2_base._workload_items_from_source_bundle(
        "## FILE app.py\nprint('a')\n## FILE app.py\nprint('b')\n## FILE lib/util.py\n"
    ) == ["app.py", "lib/util.py"]
    assert orchestrator_mission_flow_v2_base._scaling_workload_items(
        {}, {"deliverables": [" API ", "", "Tests"]}
    ) == ["API", "Tests"]
    assert orchestrator_mission_flow_v2_base._extension_for_language("ruby") == "txt"

    for bad_charter, message in [
        (
            {
                **orchestrator_mission_flow_v2.build_mission_charter(
                    mission_id="mission-1",
                    prompt="Build a Python CSV reader",
                    requested_target_language="python",
                    feature_contract={"summary": "Build a Python CSV reader"},
                    mission_type="BUILD_NEW",
                    depth_mode="STANDARD",
                    output_mode="FULL_BUILD",
                ),
                "schema": "wrong",
            },
            "must be",
        ),
        (
            {
                **orchestrator_mission_flow_v2.build_mission_charter(
                    mission_id="mission-2",
                    prompt="Build a Python CSV reader",
                    requested_target_language="python",
                    feature_contract={"summary": "Build a Python CSV reader"},
                    mission_type="BUILD_NEW",
                    depth_mode="STANDARD",
                    output_mode="FULL_BUILD",
                ),
                "mission_type": "UNKNOWN",
            },
            "unsupported value",
        ),
        (
            {
                **orchestrator_mission_flow_v2.build_mission_charter(
                    mission_id="mission-3",
                    prompt="Build a Python CSV reader",
                    requested_target_language="python",
                    feature_contract={"summary": "Build a Python CSV reader"},
                    mission_type="BUILD_NEW",
                    depth_mode="STANDARD",
                    output_mode="FULL_BUILD",
                ),
                "human_approval_required": "yes",
            },
            "invalid type",
        ),
    ]:
        with pytest.raises(ValueError, match=message):
            orchestrator_mission_flow_v2.validate_mission_charter_schema(bad_charter)


def test_build_mission_charter_modes_and_defaults() -> None:
    charter = orchestrator_mission_flow_v2.build_mission_charter(
        mission_id="mission-10",
        prompt="short",
        requested_target_language=None,
        feature_contract={
            "summary": "tiny",
            "functional_requirements": ["Ship a report"],
            "acceptance_criteria": ["Report exists"],
            "risk_assessment": {"complexity": "HIGH"},
            "human_approval_required": False,
        },
        mission_type="reduce_dependencies",
        depth_mode="regulated",
        output_mode="plan_only",
    )

    assert charter["target_outcome"] == "Complete the requested mission."
    assert charter["mission_mode"] == 6
    assert charter["depth_mode"] == "deep_audit"
    assert charter["output_mode"] == "report_only"
    assert charter["human_approval_required"] is True
    assert "operator_approval" in charter["approval_gates_required"]
    assert charter["definition_of_done"]["requires_dependency_absorption"] is True


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
async def test_prepare_specialist_plan_codegen_uses_port_knowledge_and_scaling() -> None:
    app = _make_app_state()
    settings = _make_settings()
    settings.agent_scaling_enabled = True
    settings.port_two_phase_enabled = True
    settings.agent_scaling_max_instances = 3
    settings.agent_scaling_items_per_instance = 1
    mission = _make_mission(state=MissionState.specialist_assigned)
    mission.metadata = {
        "mission_type": "PORT",
        "port_phase": "generation",
        "port_target_language": "python",
        "port_source_language": "javascript",
        "port_source_logicnodes": [{"node_id": "node-1"}, {"node_id": "node-2"}],
        "assigned_pod_manager_agent_id": "AGENT-12-PODA-MGR",
        "assigned_specialist_agent_id": "AGENT-14-PYTHON",
        "ceo_delegation": {"specialist_agent_id": "AGENT-14-PYTHON"},
        "mission_contract": {"contract_summary": "Port code", "acceptance_criteria": []},
    }
    captured_codegen_context: dict[str, Any] = {}
    audit_event = AsyncMock()

    async def _generate_code_from_contract(**kwargs):
        captured_codegen_context.update(kwargs["mission_context"])
        return {
            "source": "llm",
            "filename": "ported.py",
            "language": "python",
            "generated_code": "print('ported')",
            "code_length_chars": 15,
            "model_provider": "openai",
            "model": "gpt-test",
        }

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.fetch_mission = lambda _settings, _mission_id: mission
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission
        )
        mock_storage.insert_mission_event = MagicMock()
        with patch.object(
            orchestrator_mission_flow_v2,
            "generate_specialist_plan",
            new=AsyncMock(
                return_value={
                    "source": "llm",
                    "deliverables": ["port file a", "port file b", "port file c"],
                    "risk_notes": [],
                    "llm_route": "primary",
                    "model_provider": "openai",
                    "model": "gpt-test",
                }
            ),
        ), patch.object(
            orchestrator_mission_flow_v2,
            "generate_code_from_contract",
            new=AsyncMock(side_effect=_generate_code_from_contract),
        ), patch(
            "orchestrator.mission_flow_v2.phases_build.knowledge_lake.get_language_context",
            return_value="python docs context",
        ), patch("orchestrator.mission_flow_v2.record_audit_event", audit_event):
            prepared = await orchestrator_mission_flow_v2_build._prepare_specialist_plan(
                app=app,
                settings=settings,
                validator=MagicMock(),
                emit_state_event_fn=AsyncMock(),
                mission_id=mission.mission_id,
            )

    assert prepared is True
    assert captured_codegen_context["knowledge_context"] == "python docs context"
    assert captured_codegen_context["port_source_logicnodes"] == [{"node_id": "node-1"}, {"node_id": "node-2"}]
    assert mission.metadata["generated_output"]["filename"] == "ported.py"
    assert mission.metadata["scaling_active"] is True
    assert mission.metadata["scaling_partition_events_emitted"] is False
    event_types = [event["event_type"] for event in mission.metadata["chain_trace"]]
    assert "GENERATED_OUTPUT_CREATED" in event_types
    assert "MISSION_PORT_GENERATION_COMPLETE" in event_types
    assert "MISSION_SCALING_DECIDED" in event_types
    assert audit_event.await_count >= 2


@pytest.mark.asyncio
async def test_resolve_attachment_content_parses_inline_and_degrades_storage_failures() -> None:
    settings = _make_settings()
    parsed_inputs: list[tuple[bytes, str, str]] = []

    def _load_attachment_bytes(att: Any, _settings: Any, _mission_id: str, _file_id: str) -> bytes:
        if getattr(att, "file_id", "") == "broken":
            raise RuntimeError("object store down")
        return b"raw doc"

    def _parse_document(raw: bytes, content_type: str, filename: str) -> str:
        parsed_inputs.append((raw, content_type, filename))
        return f"parsed:{filename}"

    attachments = [
        {
            "file_id": "inline",
            "filename": "inline.md",
            "content_type": "text/markdown",
            "purpose": "brief",
            "content": " Inline text ",
        },
        SimpleNamespace(
            file_id="stored",
            filename="requirements.pdf",
            content_type="application/pdf",
            purpose="reference",
        ),
        SimpleNamespace(
            file_id="broken",
            filename="broken.pdf",
            content_type="application/pdf",
            purpose="reference",
        ),
    ]

    with patch("orchestrator.is_agent._load_attachment_bytes", side_effect=_load_attachment_bytes), patch(
        "orchestrator.document_parser.parse_document", side_effect=_parse_document
    ):
        resolved = await orchestrator_mission_flow_v2_intake._resolve_attachment_content(
            mission_id="mission-attachments",
            attachments=attachments,
            settings=settings,
        )

    assert resolved[0]["content"] == "Inline text"
    assert resolved[1]["content"] == "parsed:requirements.pdf"
    assert resolved[2]["content"] == ""
    assert parsed_inputs == [(b"raw doc", "application/pdf", "requirements.pdf")]


@pytest.mark.asyncio
async def test_prepare_pm_intake_clarification_emits_warning_when_event_emit_fails() -> None:
    app = _make_app_state()
    settings = _make_settings()
    mission = _make_mission()
    mission.metadata = {"conversation_context": "bad-context", "pm_clarification": "Use the v2 path"}
    clarifying_record = _make_mission(state=MissionState.clarifying)
    emit_fn = AsyncMock(side_effect=RuntimeError("redis down"))

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.fetch_mission = lambda _settings, _mission_id: mission
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission
        )
        mock_storage.transition_mission_state = MagicMock(return_value=clarifying_record)
        with patch.object(
            orchestrator_mission_flow_v2,
            "generate_pm_feature_contract",
            new=AsyncMock(
                return_value={
                    "schema_version": "feature_contract.v1",
                    "title": "Needs clarification",
                    "summary": "Ambiguous request",
                    "ambiguity_score": 0.95,
                    "clarifying_questions": ["Which runtime?"],
                    "source": "test",
                }
            ),
        ):
            ready = await orchestrator_mission_flow_v2_intake._prepare_pm_intake(
                app=app,
                settings=settings,
                validator=MagicMock(),
                emit_state_event_fn=emit_fn,
                mission_id=mission.mission_id,
            )

    assert ready is False
    assert mission.metadata["last_ambiguity_score"] == 0.95
    assert mission.metadata["clarifying_questions"] == ["Which runtime?"]
    mock_storage.transition_mission_state.assert_called_once()
    emit_fn.assert_awaited_once()


@pytest.mark.asyncio
async def test_prepare_fetch_phase_broadcasts_when_knowledge_ready_and_stocked() -> None:
    app = _make_app_state()
    settings = _make_settings()
    mission = _make_mission(state=MissionState.fetch)
    mission.metadata = {"mission_type": "BUILD_NEW"}
    emit_fn = AsyncMock()
    fetch_result = {
        "indexed_languages": ["python"],
        "skipped_languages": [],
        "errors": [],
        "knowledge_ids": ["docs.python.bootstrap"],
        "knowledge_ready": True,
        "refreshed_languages": ["python"],
        "unchanged_languages": [],
        "embedding_provider": "deterministic",
        "embedding_model": "hash-v1",
    }

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.fetch_mission = lambda _settings, _mission_id: mission
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission
        )
        mock_storage.insert_mission_event = MagicMock()
        with patch("orchestrator.is_agent.detect_required_languages", return_value=["python"]), patch(
            "orchestrator.is_agent.run_fetch_phase", new=AsyncMock(return_value=fetch_result)
        ), patch("orchestrator.knowledge_lake.is_stocked", return_value=True), patch(
            "orchestrator.knowledge_lake.broadcast_knowledge_ready"
        ) as broadcast:
            ready = await orchestrator_mission_flow_v2_intake._prepare_fetch_phase(
                app=app,
                settings=settings,
                validator=MagicMock(),
                emit_state_event_fn=emit_fn,
                mission_id=mission.mission_id,
            )

    assert ready is True
    assert mission.metadata["knowledge_lake_ready"] is True
    assert mission.metadata["knowledge_lake_stocked"] is True
    broadcast.assert_called_once()
    assert any(
        event["event_type"] == "MISSION_FETCH_COMPLETE"
        for event in mission.metadata["chain_trace"]
    )


@pytest.mark.asyncio
async def test_prepare_ceo_delegation_records_contract_clusters_and_port_setup() -> None:
    app = _make_app_state()
    settings = _make_settings()
    settings.port_two_phase_enabled = True
    mission = _make_mission(state=MissionState.ceo_delegated)
    mission.metadata = {
        "mission_type": "PORT",
        "feature_contract": {"summary": "Port this service"},
        "mission_charter": {"charter_id": "charter-1"},
    }
    mission_contract = {
        "source": "llm",
        "output_format": "code",
        "logicnode_requirements": ["node-a"],
        "acceptance_criteria": ["runs"],
        "contract_summary": "Port service",
        "model_provider": "openai",
        "model": "gpt-test",
    }
    logic_clusters = {
        "source": "llm",
        "clusters": [
            {
                "cluster_id": "cluster-a",
                "pod_manager_agent_id": "AGENT-12-PODA-MGR",
            }
        ],
        "model_provider": "openai",
        "model": "gpt-test",
    }
    audit_event = AsyncMock()

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.fetch_mission = lambda _settings, _mission_id: mission
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission
        )
        mock_storage.insert_mission_event = MagicMock()
        with patch.object(
            orchestrator_mission_flow_v2,
            "generate_ceo_delegation",
            new=AsyncMock(
                return_value={
                    "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                    "specialist_agent_id": "AGENT-14-PYTHON",
                    "rationale": "Security and tests required",
                    "source": "llm",
                    "llm_route": "primary",
                    "model_provider": "openai",
                    "model": "gpt-test",
                }
            ),
        ), patch.object(
            orchestrator_mission_flow_v2_intake,
            "generate_mission_contract",
            new=AsyncMock(return_value=mission_contract),
        ), patch.object(
            orchestrator_mission_flow_v2_intake,
            "generate_logic_clusters",
            new=AsyncMock(return_value=logic_clusters),
        ), patch.object(
            orchestrator_mission_flow_v2_intake,
            "_setup_port_two_phase",
            side_effect=lambda metadata, _mission, _clusters: metadata.update({"port_phase": "extraction"}),
        ) as setup_port, patch("orchestrator.mission_flow_v2.record_audit_event", audit_event):
            ready = await orchestrator_mission_flow_v2_intake._prepare_ceo_delegation(
                app=app,
                settings=settings,
                validator=MagicMock(),
                emit_state_event_fn=AsyncMock(),
                mission_id=mission.mission_id,
            )

    assert ready is True
    assert mission.metadata["selected_agent_id"] == "AGENT-12-PODA-MGR"
    assert mission.metadata["mission_contract"] == mission_contract
    assert mission.metadata["logic_clusters"] == logic_clusters
    assert mission.metadata["port_phase"] == "extraction"
    setup_port.assert_called_once()
    event_types = [event["event_type"] for event in mission.metadata["chain_trace"]]
    assert "MISSION_CEO_DELEGATED" in event_types
    assert "MISSION_CONTRACT_GENERATED" in event_types
    assert "LOGIC_CLUSTERS_DECOMPOSED" in event_types
    assert "CEO_REASONING_SUMMARY" in event_types
    assert audit_event.await_count == 3


@pytest.mark.asyncio
async def test_produce_pod_group_standard_records_thin_coverage_and_pod_audit() -> None:
    app = _make_app_state()
    settings = _make_settings()
    mission = _make_mission(state=MissionState.gating)
    mission.metadata = {
        "assigned_pod_manager_agent_id": "AGENT-12-PODA-MGR",
        "mission_contract": {"contract_summary": "Build runtime"},
        "generated_output": {"filename": "app.py"},
    }
    standard = {
        "canonical_logicnodes": [{"node_id": "node-a"}],
        "eliminated_duplicates": 1,
        "coverage_verdict": {
            "coverage_thin": True,
            "raw_logicnode_count": 1,
            "canonical_logicnode_count": 1,
            "expected_minimum_canonical_logicnodes": 2,
            "findings": ["needs one more node"],
        },
        "source": "llm",
        "llm_route": "primary",
        "model_provider": "openai",
        "model": "gpt-test",
    }
    pod_audit = {
        "agent_id": "AGENT-10-TESTER",
        "verdict": "pass",
        "quality_score": 0.91,
        "source": "test",
    }
    emit_fn = AsyncMock()

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.list_logicnodes = MagicMock(return_value=[{"node_id": "node-a"}, "bad-node"])
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission
        )
        mock_storage.insert_mission_event = MagicMock()
        with patch.object(
            orchestrator_mission_flow_v2,
            "generate_pod_group_standard",
            new=AsyncMock(return_value=standard),
        ), patch.object(
            orchestrator_mission_flow_v2_build,
            "generate_pod_audit_verdict",
            new=AsyncMock(return_value=pod_audit),
        ), patch("orchestrator.mission_flow_v2.record_audit_event", AsyncMock()) as audit_event:
            updated = await orchestrator_mission_flow_v2_build._produce_pod_group_standard(
                app=app,
                settings=settings,
                validator=MagicMock(),
                emit_state_event_fn=emit_fn,
                mission=mission,
            )

    assert updated is mission
    assert mission.metadata["pod_group_standards"]["podA"] == standard
    assert mission.metadata["pod_audit_verdicts"]["podA"] == pod_audit
    event_types = [event["event_type"] for event in mission.metadata["chain_trace"]]
    assert "MISSION_POD_GROUP_STANDARD_PRODUCED" in event_types
    assert "MISSION_POD_STANDARD_THIN_COVERAGE" in event_types
    assert "MISSION_POD_AUDIT_COMPLETE" in event_types
    assert audit_event.await_count == 1
    emit_fn.assert_awaited_once()


def test_write_artifact_to_disk_sanitizes_generated_and_source_bundle_paths(tmp_path: Path) -> None:
    settings = SimpleNamespace(delivery_dir=str(tmp_path))

    orchestrator_mission_flow_v2_build._write_artifact_to_disk(
        settings,
        "mission-files",
        {
            "artifact_type": "generated_code",
            "artifact_text": "print('safe')\n",
            "manifest": {"filename": "../unsafe.py"},
        },
    )
    orchestrator_mission_flow_v2_build._write_artifact_to_disk(
        settings,
        "mission-files",
        {
            "artifact_type": "source_bundle_package",
            "artifact_text": "## FILE app/main.py\nprint('app')\n## FILE ../secret.py\nprint('secret')\n",
            "manifest": {},
        },
    )
    orchestrator_mission_flow_v2_build._write_artifact_to_disk(
        settings,
        "mission-inline",
        {
            "artifact_type": "source_bundle_package",
            "artifact_text": "plain source",
            "manifest": {"filename": "inline.py"},
        },
    )

    assert (tmp_path / "mission-files" / "unsafe.py").read_text(encoding="utf-8") == "print('safe')\n"
    assert (tmp_path / "mission-files" / "app" / "main.py").read_text(encoding="utf-8") == "print('app')\n"
    assert (tmp_path / "mission-files" / "secret.py").read_text(encoding="utf-8") == "print('secret')\n"
    assert (tmp_path / "mission-inline" / "inline.py").read_text(encoding="utf-8") == "plain source"


@pytest.mark.asyncio
async def test_prepare_dependency_absorption_reports_skips_without_evidence() -> None:
    mission = _make_mission(state=MissionState.verified)
    mission.metadata = {}

    updated, ready, report = (
        await orchestrator_mission_flow_v2._prepare_dependency_absorption_reports(
            app=_make_app_state(),
            settings=_make_settings(),
            mission=mission,
        )
    )

    assert updated is mission
    assert ready is True
    assert report == {"skipped": True, "reason": "no dependency evidence"}


@pytest.mark.asyncio
async def test_prepare_runtime_qc_skips_when_generated_output_missing() -> None:
    settings = _make_settings()
    mission = _make_mission(state=MissionState.verified)
    mission.metadata = {}
    inserted_events: list[str] = []

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission
        )
        mock_storage.insert_mission_event = (
            lambda _settings, _mission_id, _previous, _new, event_type: inserted_events.append(
                event_type
            )
        )
        updated, ready, report = await orchestrator_mission_flow_v2_runtime._prepare_runtime_qc(
            app=_make_app_state(),
            settings=settings,
            mission=mission,
        )

    assert updated is mission
    assert ready is True
    assert report["skipped"] is True
    assert report["reason"] == "no generated output"
    assert inserted_events == ["MISSION_RUNTIME_QC_SKIPPED"]
    assert any(
        event["event_type"] == "MISSION_RUNTIME_QC_SKIPPED"
        for event in mission.metadata["chain_trace"]
    )


@pytest.mark.asyncio
async def test_prepare_runtime_qc_records_complete_report_and_blocks_on_enforced_fail() -> None:
    settings = _make_settings()
    settings.testdata_agent_enabled = True
    settings.rqca_agent_enabled = True
    settings.rqca_enforcement_enabled = True
    mission = _make_mission(state=MissionState.verified)
    mission.metadata = {
        "generated_output": {
            "generated_code": "print('hello')",
            "filename": "solution.py",
            "language": "python",
        },
        "mission_contract": {"acceptance_criteria": ["prints hello"]},
    }
    persisted_reports: list[tuple[dict[str, Any], dict[str, Any]]] = []
    manifest = {
        "base_image": "python:3.12",
        "timeout_seconds": 30,
        "synthetic_inputs": [{"stdin": ""}],
        "source": "test",
    }
    execution = {
        "verdict": "PASS",
        "execution_type": "subprocess",
        "source": "test",
        "deployment_safe": True,
    }
    assessment = {"qc_verdict": "FAIL", "deployment_safe": False}

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission
        )
        mock_storage.insert_testdata_manifest = MagicMock()
        mock_storage.insert_runtime_qc_report = (
            lambda _settings, _mission_id, report, qc: persisted_reports.append(
                (report, qc)
            )
        )
        with patch.object(
            orchestrator_mission_flow_v2_runtime,
            "generate_testdata_manifest",
            new=AsyncMock(return_value=manifest),
        ), patch.object(
            orchestrator_mission_flow_v2_runtime,
            "run_runtime_qc",
            new=AsyncMock(return_value=execution),
        ), patch.object(
            orchestrator_mission_flow_v2_runtime,
            "generate_rqca_assessment",
            new=AsyncMock(return_value=assessment),
        ), patch("orchestrator.mission_flow_v2.record_audit_event", AsyncMock()):
            updated, ready, report = await orchestrator_mission_flow_v2_runtime._prepare_runtime_qc(
                app=_make_app_state(),
                settings=settings,
                mission=mission,
            )

    assert updated is mission
    assert ready is False
    assert report["qc_assessment"] == assessment
    assert mission.metadata["testdata_manifest"] == manifest
    assert persisted_reports == [(execution, assessment)]
    assert any(
        event["event_type"] == "MISSION_TESTDATA_MANIFEST_READY"
        for event in mission.metadata["chain_trace"]
    )
    assert any(
        event["event_type"] == "MISSION_RUNTIME_QC_COMPLETE"
        for event in mission.metadata["chain_trace"]
    )


@pytest.mark.asyncio
async def test_prepare_runtime_qc_generates_manifest_then_skips_when_rqca_disabled() -> None:
    settings = _make_settings()
    settings.testdata_agent_enabled = True
    settings.rqca_agent_enabled = False
    mission = _make_mission(state=MissionState.verified)
    mission.metadata = {
        "generated_output": {"generated_code": "print('hello')", "language": "python"},
        "mission_contract": {"acceptance_criteria": ["prints hello"]},
        "integration_tests": {"tests": []},
    }
    inserted_events: list[str] = []
    manifest = {
        "base_image": "python:3.12",
        "timeout_seconds": 30,
        "synthetic_inputs": [{"stdin": ""}],
        "source": "testdata-agent",
    }

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission
        )

        def _insert_manifest_fail(*_args):
            raise RuntimeError("testdata store down")

        mock_storage.insert_testdata_manifest = _insert_manifest_fail
        mock_storage.insert_mission_event = (
            lambda _settings, _mission_id, _previous, _new, event_type: inserted_events.append(
                event_type
            )
        )
        with patch.object(
            orchestrator_mission_flow_v2_runtime,
            "generate_testdata_manifest",
            new=AsyncMock(return_value=manifest),
        ) as generate_manifest:
            updated, ready, report = await orchestrator_mission_flow_v2_runtime._prepare_runtime_qc(
                app=_make_app_state(),
                settings=settings,
                mission=mission,
            )

    assert updated is mission
    assert ready is True
    assert report["skipped"] is True
    assert report["reason"] == "RQCA disabled"
    assert mission.metadata["testdata_manifest"] == manifest
    assert generate_manifest.await_count == 1
    assert inserted_events == ["MISSION_RUNTIME_QC_SKIPPED"]
    assert any(
        event["event_type"] == "MISSION_TESTDATA_MANIFEST_READY"
        for event in mission.metadata["chain_trace"]
    )


@pytest.mark.asyncio
async def test_prepare_depabs_execution_persists_generated_output_and_survives_packaging_failure() -> None:
    settings = _make_settings()
    settings.depabs_execution_enabled = True
    mission = _make_mission(state=MissionState.verified)
    mission.metadata = {
        "source_code": "import requests\nprint(requests.__version__)\n",
        "dependency_inventory": {"dependencies": [{"name": "requests"}]},
        "dependency_survival_justifications": [],
        "dependency_absorption_report": {
            "report_id": "depabs-report-1",
            "status": "planned",
            "blocking": False,
            "planned_replacements": [{"dependency": "requests"}],
        },
    }
    execution = {
        "status": "complete",
        "absorption_count": 1,
        "modified_source": "print('absorbed')\n",
        "splices": [{"library": "requests", "status": "ok"}],
    }
    audit_event = AsyncMock()

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission
        )
        with patch.object(
            orchestrator_mission_flow_v2_runtime,
            "execute_absorption",
            new=AsyncMock(return_value=execution),
        ), patch.object(
            orchestrator_mission_flow_v2_runtime,
            "_ensure_verified_build_artifact",
            new=AsyncMock(side_effect=RuntimeError("artifact store down")),
        ) as ensure_artifact, patch("orchestrator.mission_flow_v2.record_audit_event", audit_event):
            updated = await orchestrator_mission_flow_v2_runtime._prepare_depabs_execution(
                app=_make_app_state(),
                settings=settings,
                mission=mission,
            )

    assert updated is mission
    assert mission.metadata["depabs_execution"] == execution
    assert mission.metadata["generated_output"]["source"] == "depabs_execution"
    assert mission.metadata["generated_output"]["generated_code"] == "print('absorbed')\n"
    assert mission.metadata["sbom_delta"]["removed"] == ["requests"]
    assert mission.metadata["sbom_delta"]["reduction_percent"] == 100.0
    assert ensure_artifact.await_count == 1
    assert audit_event.await_count == 1
    assert any(
        event["event_type"] == "MISSION_DEPABS_EXECUTED"
        for event in mission.metadata["chain_trace"]
    )


@pytest.mark.asyncio
async def test_prepare_fusion_orders_nodes_by_neo4j_depth_and_continues_on_codegen_error() -> None:
    settings = _make_settings()
    settings.neo4j_enabled = True
    mission = _make_mission(state=MissionState.fusion)
    mission.metadata = {
        "mission_contract": {"contract_summary": "Build ordered graph"},
        "pod_group_standards": {
            "node-a": {"canonical_logicnodes": [{"node_id": "node-a"}]},
            "node-b": {"canonical_logicnodes": [{"node_id": "node-b"}]},
            "node-c": {"canonical_logicnodes": [{"node_id": "node-c"}]},
        },
        "assigned_specialist_agent_id": "AGENT-14-PYTHON",
    }
    captured_order: list[str] = []
    master_stream = {
        "master_logic_stream": [{"node_id": "node-b"}],
        "total_unified_nodes": 1,
        "eliminated_across_pods": 0,
        "ready_for_codegen": True,
        "source": "llm",
    }

    async def _generate_master_logic_stream(*, pod_group_standards, mission_contract, mission_context):
        _ = mission_contract, mission_context
        captured_order.extend(pod_group_standards.keys())
        return master_stream

    with (
        patch(
            "orchestrator.neo4j_store.list_logicnodes_by_depth",
            return_value=[{"node_id": "node-b"}, {"node_id": "node-a"}],
        ),
        patch.object(
            orchestrator_mission_flow_v2,
            "generate_master_logic_stream",
            new=AsyncMock(side_effect=_generate_master_logic_stream),
        ),
        patch.object(
            orchestrator_mission_flow_v2,
            "generate_code_from_contract",
            new=AsyncMock(side_effect=RuntimeError("codegen down")),
        ),
        patch.object(
            orchestrator_mission_flow_v2.storage,
            "update_mission_metadata",
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission,
        ),
    ):
        updated = await orchestrator_mission_flow_v2._prepare_fusion(
            app=_make_app_state(),
            settings=settings,
            validator=MagicMock(),
            emit_state_event_fn=AsyncMock(),
            mission=mission,
        )

    assert updated is mission
    assert captured_order == ["node-b", "node-a", "node-c"]
    assert "generated_output" not in mission.metadata
    assert mission.metadata["master_logic_stream"] == master_stream
    assert any(
        event["event_type"] == "MISSION_LOGIC_FOLDED"
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


@pytest.mark.asyncio
async def test_advance_verified_to_complete_records_completion_block_and_emit_failure() -> None:
    mission = _make_mission(state=MissionState.verified)
    app = _make_app_state()
    app.state.redis_ready = True
    app.state.redis = object()
    inserted_events: list[str] = []
    emit_fn = AsyncMock(side_effect=RuntimeError("redis down"))

    async def _completion_check(*, settings, mission):
        _ = settings, mission
        return False, {"missing": ["delivery_summary"]}

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.fetch_mission = lambda _settings, _mission_id: mission
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: setattr(mission, "metadata", metadata)
            or mission
        )
        mock_storage.insert_mission_event = (
            lambda _settings, _mission_id, _previous, _new, event_type: inserted_events.append(
                event_type
            )
        )
        result = await orchestrator_mission_flow_v2_lifecycle._advance_verified_to_complete(
            app=app,
            settings=_make_settings(),
            validator=MagicMock(),
            emit_state_event_fn=emit_fn,
            mission_id=mission.mission_id,
            completion_check_fn=_completion_check,
        )

    assert result is False
    assert inserted_events == ["MISSION_COMPLETION_BLOCKED"]
    assert emit_fn.await_count == 1
    assert mission.metadata["chain_trace"][-1]["event_type"] == "MISSION_COMPLETION_BLOCKED"


@pytest.mark.asyncio
async def test_advance_verified_to_complete_stops_on_equivalence_security_depabs_and_runtime_blocks() -> None:
    settings = _make_settings()
    app = _make_app_state()
    validator = MagicMock()

    async def _completion_check(*, settings, mission):
        _ = settings, mission
        return True, {}

    scenarios = [
        (
            "MISSION_EQUIVALENCE_BLOCKED",
            {"report_id": "eq-1"},
            (False, True, True, True),
        ),
        (
            "MISSION_SECURITY_COMPLIANCE_BLOCKED",
            {"report_id": "sec-1"},
            (True, False, True, True),
        ),
        (
            "MISSION_DEPENDENCY_ABSORPTION_BLOCKED",
            {"report_id": "dep-1"},
            (True, True, False, True),
        ),
        (
            "MISSION_RUNTIME_QC_BLOCKED",
            {"verdict": "FAIL"},
            (True, True, True, False),
        ),
    ]

    for expected_event, report, readiness in scenarios:
        mission = _make_mission(state=MissionState.verified)
        inserted_events: list[str] = []
        eq_ready, sec_ready, dep_ready, runtime_ready = readiness
        with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
            mock_storage.fetch_mission = lambda _settings, _mission_id, _mission=mission: _mission
            mock_storage.insert_mission_event = (
                lambda _settings, _mission_id, _previous, _new, event_type, _events=inserted_events: _events.append(
                    event_type
                )
            )
            mock_storage.update_mission_metadata = (
                lambda _settings, _mission_id, metadata, _mission=mission: setattr(_mission, "metadata", metadata)
                or _mission
            )
            with patch.object(
                orchestrator_mission_flow_v2_lifecycle,
                "_prepare_equivalence_report",
                new=AsyncMock(return_value=(mission, eq_ready, report)),
            ), patch.object(
                orchestrator_mission_flow_v2_lifecycle,
                "_prepare_security_compliance_report",
                new=AsyncMock(return_value=(mission, sec_ready, report)),
            ), patch.object(
                orchestrator_mission_flow_v2_lifecycle,
                "_prepare_dependency_absorption_reports",
                new=AsyncMock(return_value=(mission, dep_ready, report)),
            ), patch.object(
                orchestrator_mission_flow_v2_lifecycle,
                "_prepare_depabs_execution",
                new=AsyncMock(return_value=mission),
            ), patch.object(
                orchestrator_mission_flow_v2_lifecycle,
                "_prepare_runtime_qc",
                new=AsyncMock(return_value=(mission, runtime_ready, report)),
            ):
                result = await orchestrator_mission_flow_v2_lifecycle._advance_verified_to_complete(
                    app=app,
                    settings=settings,
                    validator=validator,
                    emit_state_event_fn=AsyncMock(),
                    mission_id=mission.mission_id,
                    completion_check_fn=_completion_check,
                )

        assert result is False
        assert expected_event in inserted_events


@pytest.mark.asyncio
async def test_advance_verified_to_complete_records_deploy_readiness_and_delivery_summary() -> None:
    mission = _make_mission(state=MissionState.verified)
    settings = _make_settings()
    deploy_report = {"ready": False, "blockers": ["manual approval"], "source": "test"}
    updated_metadata: list[dict[str, Any]] = []

    async def _completion_check(*, settings, mission):
        _ = settings, mission
        return True, {}

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.fetch_mission = lambda _settings, _mission_id: mission
        mock_storage.list_build_artifacts = lambda _settings, _mission_id, _limit: []
        mock_storage.update_mission_metadata = (
            lambda _settings, _mission_id, metadata: updated_metadata.append(metadata) or mission
        )
        with patch.object(
            orchestrator_mission_flow_v2_lifecycle,
            "_prepare_equivalence_report",
            new=AsyncMock(return_value=(mission, True, {"report_id": "eq-1"})),
        ), patch.object(
            orchestrator_mission_flow_v2_lifecycle,
            "_prepare_security_compliance_report",
            new=AsyncMock(return_value=(mission, True, {"report_id": "sec-1"})),
        ), patch.object(
            orchestrator_mission_flow_v2_lifecycle,
            "_prepare_dependency_absorption_reports",
            new=AsyncMock(return_value=(mission, True, {"report_id": "dep-1"})),
        ), patch.object(
            orchestrator_mission_flow_v2_lifecycle,
            "_prepare_depabs_execution",
            new=AsyncMock(return_value=mission),
        ), patch.object(
            orchestrator_mission_flow_v2_lifecycle,
            "_prepare_runtime_qc",
            new=AsyncMock(return_value=(mission, True, {"verdict": "PASS"})),
        ), patch.object(
            orchestrator_mission_flow_v2_lifecycle,
            "build_deploy_readiness_assessment",
            return_value=deploy_report,
        ), patch.object(
            orchestrator_mission_flow_v2_lifecycle,
            "_prepare_delivery_summary",
            new=AsyncMock(return_value=mission),
        ) as delivery_summary:
            result = await orchestrator_mission_flow_v2_lifecycle._advance_verified_to_complete(
                app=_make_app_state(),
                settings=settings,
                validator=MagicMock(),
                emit_state_event_fn=AsyncMock(),
                mission_id=mission.mission_id,
                completion_check_fn=_completion_check,
            )

    assert result is True
    assert delivery_summary.await_count == 1
    assert updated_metadata[-1]["deploy_readiness"] == deploy_report
    assert any(
        event["event_type"] == "MISSION_DEPLOY_READINESS_ASSESSED"
        for event in updated_metadata[-1]["chain_trace"]
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
