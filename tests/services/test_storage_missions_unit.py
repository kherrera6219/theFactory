import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

# Force absolute imports for the test environment
ROOT = Path(r"C:\software\Holygrail\theFactory")
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

import orchestrator.storage_missions as storage_missions
from orchestrator.models import (
    DataClassification,
    DepthMode,
    MissionRecord,
    MissionState,
    MissionType,
    OutputMode,
)
from orchestrator.settings import Settings


def _make_dummy_settings(**overrides) -> Settings:
    base = {
        "redis_url": "redis://localhost",
        "postgres_url": "postgresql://localhost",
        "intake_stream": "missions.intake",
        "state_stream": "missions.state",
        "max_stream_len": 1000,
        "consumer_group": "orchestrator",
        "consumer_name": "orchestrator-test",
        "auto_transition_enabled": True,
        "transition_step_seconds": 1.0,
        "intake_topic": "intake.feature_contract.created",
        "default_priority": "NORMAL",
        "producer_name": "orchestrator",
        "event_schema_path": Path("."),
        "topics_path": Path("."),
        "admin_api_key": "",
        "internal_service_api_key": "",
        "readonly_api_key": "",
        "extra_api_keys": ""
    }
    base.update(overrides)
    return Settings(**base)

def test_charter_fields_from_metadata():
    metadata = {
        "__mission_type__": "BUILD_NEW",
        "__depth_mode__": "STANDARD",
        "__output_mode__": "FULL_BUILD",
        "__data_classification__": "TIER_1_INTERNAL"
    }
    fields = storage_missions._charter_fields_from_metadata(metadata)
    assert fields["mission_type"] == MissionType.build_new
    assert fields["depth_mode"] == DepthMode.standard
    assert fields["output_mode"] == OutputMode.full_build
    assert fields["data_classification"] == DataClassification.tier_1_internal

def test_charter_fields_invalid():
    metadata = {"__mission_type__": "INVALID"}
    fields = storage_missions._charter_fields_from_metadata(metadata)
    assert fields["mission_type"] is None

def test_embed_charter_fields():
    record = MissionRecord(
        mission_id="m1",
        prompt="test",
        state=MissionState.queued,
        created_at=datetime.now(UTC).isoformat(),
        mission_type=MissionType.build_new,
        depth_mode=DepthMode.standard,
        lifecycle_engine="mission_flow_v2",
    )
    metadata = {}
    storage_missions._embed_charter_fields(metadata, record)
    assert metadata["__mission_type__"] == "BUILD_NEW"
    assert metadata["__depth_mode__"] == "STANDARD"
    assert metadata["lifecycle_engine"] == "mission_flow_v2"

def test_row_to_mission():
    # mission_id, prompt, requested_target_language, metadata_json, project_id, state, created_at
    row = (
        "m1", "prompt", "rust", 
        json.dumps({"__mission_type__": "BUILD_NEW", "lifecycle_engine": "mission_flow_v2"}),
        "p1", "QUEUED", datetime(2026, 1, 1, tzinfo=UTC)
    )
    mission = storage_missions.row_to_mission(row)
    assert mission.mission_id == "m1"
    assert mission.state == MissionState.queued
    assert mission.mission_type == MissionType.build_new
    assert mission.project_id == "p1"
    assert mission.lifecycle_engine == "mission_flow_v2"

@patch("orchestrator.storage_missions.get_connection")
def test_fetch_mission(mock_connect):
    mock_conn = MagicMock()
    mock_connect.return_value.__enter__.return_value = mock_conn
    
    # Setup the mock cursor and its context manager
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    
    # row format matches row_to_mission
    mock_cursor.fetchone.return_value = (
        "m1", "prompt", "rust", "{}", "p1", "QUEUED", datetime(2026, 1, 1, tzinfo=UTC)
    )
    
    settings = _make_dummy_settings()
    mission = storage_missions.fetch_mission(settings, "m1")
    assert mission is not None
    assert mission.mission_id == "m1"

@patch("orchestrator.storage_missions.get_connection")
def test_count_missions(mock_connect):
    mock_conn = MagicMock()
    mock_connect.return_value.__enter__.return_value = mock_conn

    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (10,)

    settings = _make_dummy_settings()
    assert storage_missions.count_missions(settings) == 10


@patch("orchestrator.storage_missions.get_connection")
def test_insert_mission_event_records_transition_metric(mock_connect):
    mock_conn = MagicMock()
    mock_connect.return_value.__enter__.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    from orchestrator.orchestrator_metrics import MISSION_TRANSITIONS_TOTAL

    settings = _make_dummy_settings(mission_flow_v2_enabled=True)
    before = MISSION_TRANSITIONS_TOTAL.labels(
        from_state="QUEUED", to_state="RUNNING", engine="v2"
    )._value.get()

    storage_missions.insert_mission_event(
        settings, "m1", MissionState.queued, MissionState.running, "MISSION_RUNNING"
    )

    after = MISSION_TRANSITIONS_TOTAL.labels(
        from_state="QUEUED", to_state="RUNNING", engine="v2"
    )._value.get()
    assert after == before + 1


@patch("orchestrator.storage_missions.get_connection")
def test_insert_mission_event_self_loop_not_counted(mock_connect):
    mock_conn = MagicMock()
    mock_connect.return_value.__enter__.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    from orchestrator.orchestrator_metrics import MISSION_TRANSITIONS_TOTAL

    settings = _make_dummy_settings(mission_flow_v2_enabled=True)
    before = MISSION_TRANSITIONS_TOTAL.labels(
        from_state="RUNNING", to_state="RUNNING", engine="v2"
    )._value.get()

    # Checkpoint event: previous == new. Must not be counted as a transition.
    storage_missions.insert_mission_event(
        settings, "m1", MissionState.running, MissionState.running, "MISSION_GATING"
    )

    after = MISSION_TRANSITIONS_TOTAL.labels(
        from_state="RUNNING", to_state="RUNNING", engine="v2"
    )._value.get()
    assert after == before


def test_resolve_engine_label():
    assert storage_missions._resolve_engine_label(
        _make_dummy_settings(mission_flow_v2_enabled=True)
    ) == "v2"
    assert storage_missions._resolve_engine_label(
        _make_dummy_settings(mission_flow_v2_enabled=False, langgraph_enabled=True)
    ) == "langgraph"
    assert storage_missions._resolve_engine_label(
        _make_dummy_settings(mission_flow_v2_enabled=False, langgraph_enabled=False)
    ) == "legacy"
