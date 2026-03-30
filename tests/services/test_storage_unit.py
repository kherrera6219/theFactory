import importlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

storage = importlib.import_module("orchestrator.storage")
orchestrator_models = importlib.import_module("orchestrator.models")
orchestrator_settings = importlib.import_module("orchestrator.settings")

MissionRecord = orchestrator_models.MissionRecord
MissionState = orchestrator_models.MissionState
Settings = orchestrator_settings.Settings


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
        transition_step_seconds=1.0,
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


class FakeCursor:
    def __init__(
        self,
        *,
        fetchone_results: list[Any] | None = None,
        fetchall_results: list[Any] | None = None,
    ) -> None:
        self.fetchone_results = list(fetchone_results or [])
        self.fetchall_results = list(fetchall_results or [])
        self.executed: list[tuple[str, Any]] = []

    def execute(self, query: str, params: Any = None) -> None:
        self.executed.append((query, params))

    def fetchone(self) -> Any:
        if self.fetchone_results:
            return self.fetchone_results.pop(0)
        return None

    def fetchall(self) -> Any:
        if self.fetchall_results:
            return self.fetchall_results.pop(0)
        return []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeConn:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> FakeCursor:
        return self._cursor

    def __enter__(self) -> "FakeConn":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def _patch_db(monkeypatch, cursors: list[FakeCursor]) -> list[FakeCursor]:
    queue = list(cursors)
    used: list[FakeCursor] = []

    def _db_connect(_: Settings) -> FakeConn:
        cursor = queue.pop(0)
        used.append(cursor)
        return FakeConn(cursor)

    monkeypatch.setattr(storage, "db_connect", _db_connect)
    return used


def _mission_record(state: MissionState = MissionState.queued) -> MissionRecord:
    return MissionRecord(
        mission_id="mission-1",
        prompt="Build API",
        requested_target_language="python",
        metadata={"source": "test"},
        state=state,
        created_at="2026-03-01T00:00:00+00:00",
    )


def test_db_connect_raises_when_psycopg_missing(monkeypatch) -> None:
    monkeypatch.setattr(storage, "psycopg", None)
    with pytest.raises(RuntimeError):
        storage.db_connect(_settings())


def test_ensure_db_schema_executes_queries(monkeypatch) -> None:
    cursor = FakeCursor()
    used = _patch_db(monkeypatch, [cursor])
    storage.ensure_db_schema(_settings())
    assert used
    assert len(cursor.executed) >= 3
    assert "schema_migrations" in cursor.executed[0][0]
    assert "SELECT version, checksum FROM schema_migrations" in cursor.executed[1][0]
    assert cursor.executed[-1][1][0] == "003"


def test_row_and_json_helpers() -> None:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    assert storage._to_iso(now).endswith("+00:00")
    assert storage._to_iso("2026-03-01") == "2026-03-01"

    assert storage._json_to_dict('{"a":1}') == {"a": 1}
    assert storage._json_to_dict({"b": 2}) == {"b": 2}
    assert storage._json_to_dict(123) == {}

    row = ("mission-1", "Build API", "python", {"x": 1}, "QUEUED", now)
    record = storage.row_to_mission(row)
    assert record.mission_id == "mission-1"
    assert record.state == MissionState.queued


def test_review_approval_roundtrip(monkeypatch) -> None:
    now = datetime(2026, 3, 29, tzinfo=UTC)
    row = (
        "repo-approval-f1234567890abcde",
        "repo",
        "f1234567890abcdef",
        "Repository review approved for mission launch.",
        {"request_id": "repo-review-001"},
        "digest-001",
        "postgres",
        now,
        now,
    )
    _patch_db(
        monkeypatch,
        [
            FakeCursor(fetchone_results=[row]),
            FakeCursor(fetchone_results=[row]),
        ],
    )

    created = storage.upsert_review_approval(
        _settings(),
        "repo-approval-f1234567890abcde",
        "repo",
        "f1234567890abcdef",
        "Repository review approved for mission launch.",
        {"request_id": "repo-review-001"},
        "digest-001",
        "postgres",
        "2026-03-29T00:00:00+00:00",
    )
    fetched = storage.get_review_approval(_settings(), "repo-approval-f1234567890abcde")

    assert created["approval_id"] == "repo-approval-f1234567890abcde"
    assert created["storage_backend"] == "postgres"
    assert fetched is not None
    assert fetched["receipt_digest"] == "digest-001"


def test_upsert_fetch_list_and_count(monkeypatch) -> None:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    row = ("mission-1", "Build API", "python", {"source": "test"}, "QUEUED", now)
    cursors = [
        FakeCursor(),
        FakeCursor(fetchone_results=[row]),
        FakeCursor(fetchall_results=[[row]]),
        FakeCursor(fetchone_results=[(3,)]),
        FakeCursor(fetchone_results=[None]),
    ]
    used = _patch_db(monkeypatch, cursors)

    settings = _settings()
    mission = _mission_record()
    storage.upsert_mission(settings, mission, "1-0")

    fetched = storage.fetch_mission(settings, "mission-1")
    assert fetched is not None
    assert fetched.mission_id == "mission-1"

    listed = storage.list_missions(settings, 10)
    assert len(listed) == 1
    assert listed[0].mission_id == "mission-1"

    assert storage.count_missions(settings) == 3
    assert storage.count_missions(settings) == 0

    first_upsert_params = used[0].executed[0][1]
    assert first_upsert_params[0] == "mission-1"
    assert first_upsert_params[-1] == "1-0"


def test_list_missions_in_states(monkeypatch) -> None:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    row = ("mission-2", "Build API", "python", {"source": "test"}, "RUNNING", now)
    _patch_db(monkeypatch, [FakeCursor(fetchall_results=[[row]])])

    results = storage.list_missions_in_states(
        _settings(),
        [MissionState.running, MissionState.verified],
        25,
    )
    assert len(results) == 1
    assert results[0].mission_id == "mission-2"

    assert storage.list_missions_in_states(_settings(), [], 25) == []


def test_insert_and_list_mission_events(monkeypatch) -> None:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    rows = [
        ("mission-1", "INTAKE", "QUEUED", "MISSION_QUEUED", now),
        ("mission-1", None, "RUNNING", "MISSION_RUNNING", now),
    ]
    _patch_db(
        monkeypatch,
        [
            FakeCursor(),
            FakeCursor(fetchall_results=[rows]),
        ],
    )
    settings = _settings()

    storage.insert_mission_event(
        settings,
        "mission-1",
        MissionState.intake,
        MissionState.queued,
        "MISSION_QUEUED",
    )
    events = storage.list_mission_events(settings, "mission-1", 10)
    assert len(events) == 2
    assert events[0].previous_state == MissionState.intake
    assert events[1].previous_state is None


def test_transition_mission_state_success_and_noop(monkeypatch) -> None:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    row = ("mission-1", "Build API", "python", {"source": "test"}, "RUNNING", now)
    _patch_db(
        monkeypatch,
        [
            FakeCursor(fetchone_results=[row]),
            FakeCursor(fetchone_results=[None]),
        ],
    )
    calls: list[tuple[MissionState | None, MissionState, str]] = []

    def _insert_event(
        _settings_obj: Settings,
        _mission_id: str,
        previous_state: MissionState | None,
        new_state: MissionState,
        event_type: str,
    ) -> None:
        calls.append((previous_state, new_state, event_type))

    monkeypatch.setattr(storage, "insert_mission_event", _insert_event)
    settings = _settings()

    record = storage.transition_mission_state(
        settings,
        "mission-1",
        MissionState.queued,
        MissionState.running,
        "MISSION_RUNNING",
    )
    assert record is not None
    assert calls[0][1] == MissionState.running

    none_record = storage.transition_mission_state(
        settings,
        "mission-1",
        None,
        MissionState.failed,
        "MISSION_FAILED",
    )
    assert none_record is None


def test_pod_assignment_success_and_conflict(monkeypatch) -> None:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    success_row = ("mission-1", "podA", {"reason": "match"}, now, now)
    _patch_db(
        monkeypatch,
        [
            FakeCursor(fetchone_results=[success_row]),
            FakeCursor(fetchone_results=[None]),
            FakeCursor(fetchone_results=[None]),
        ],
    )
    settings = _settings()

    success = storage.upsert_pod_assignment(
        settings,
        "mission-1",
        "podA",
        {"reason": "match"},
        "2026-03-01T00:00:00+00:00",
    )
    assert success["pod_name"] == "podA"

    monkeypatch.setattr(
        storage,
        "get_pod_assignment",
        lambda *_: {
            "mission_id": "mission-1",
            "pod_name": "podB",
            "metadata": {},
            "assigned_at": "2026-03-01T00:00:00+00:00",
            "updated_at": "2026-03-01T00:00:00+00:00",
        },
    )
    with pytest.raises(storage.PodAssignmentConflictError):
        storage.upsert_pod_assignment(
            settings,
            "mission-1",
            "podA",
            {},
            "2026-03-01T00:00:00+00:00",
        )

    monkeypatch.setattr(storage, "get_pod_assignment", lambda *_: None)
    with pytest.raises(RuntimeError):
        storage.upsert_pod_assignment(
            settings,
            "mission-1",
            "podA",
            {},
            "2026-03-01T00:00:00+00:00",
        )


def test_get_pod_assignment_present_and_missing(monkeypatch) -> None:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    _patch_db(
        monkeypatch,
        [
            FakeCursor(fetchone_results=[("mission-1", "podA", {"k": 1}, now, now)]),
            FakeCursor(fetchone_results=[None]),
        ],
    )
    settings = _settings()
    found = storage.get_pod_assignment(settings, "mission-1")
    assert found is not None
    assert found["pod_name"] == "podA"
    assert storage.get_pod_assignment(settings, "mission-1") is None


def test_logicnode_knowledge_and_audit_roundtrip(monkeypatch) -> None:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    _patch_db(
        monkeypatch,
        [
            FakeCursor(fetchone_results=[("mission-1", "node-1", {"a": 1}, now)]),
            FakeCursor(fetchall_results=[[("mission-1", "node-1", {"a": 1}, now)]]),
            FakeCursor(fetchone_results=[("mission-1", "k-1", {"text": "x"}, now)]),
            FakeCursor(fetchall_results=[[("mission-1", "k-1", {"text": "x"}, now)]]),
            FakeCursor(fetchone_results=[("mission-1", "a-1", "PASS", {"score": 1}, now)]),
            FakeCursor(fetchall_results=[[("mission-1", "a-1", "PASS", {"score": 1}, now)]]),
        ],
    )
    settings = _settings()

    node = storage.upsert_logicnode(settings, "mission-1", "node-1", {"a": 1}, now.isoformat())
    assert node["node_id"] == "node-1"
    assert storage.list_logicnodes(settings, "mission-1", 10)[0]["node_id"] == "node-1"

    knowledge = storage.upsert_knowledge(
        settings,
        "mission-1",
        "k-1",
        {"text": "x"},
        now.isoformat(),
    )
    assert knowledge["knowledge_id"] == "k-1"
    assert storage.list_knowledge(settings, "mission-1", 10)[0]["knowledge_id"] == "k-1"

    audit = storage.upsert_audit_report(
        settings,
        "mission-1",
        "a-1",
        "PASS",
        {"score": 1},
        now.isoformat(),
    )
    assert audit["audit_id"] == "a-1"
    assert storage.list_audit_reports(settings, "mission-1", 10)[0]["audit_id"] == "a-1"


def test_build_artifact_roundtrip(monkeypatch) -> None:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    artifact_row = (
        "mission-1",
        "source-bundle-package",
        "source_bundle_package",
        "package",
        "SUCCESS",
        "database",
        "database://missions/mission-1/build-artifacts/source-bundle-package",
        "abc123",
        128,
        {"file_count": 1},
        {"verified": True},
        "build complete",
        "print('ok')",
        now,
        now,
    )
    _patch_db(
        monkeypatch,
        [
            FakeCursor(fetchone_results=[artifact_row]),
            FakeCursor(fetchall_results=[[artifact_row]]),
            FakeCursor(fetchone_results=[artifact_row]),
        ],
    )
    settings = _settings()

    artifact = storage.upsert_build_artifact(
        settings,
        "mission-1",
        "source-bundle-package",
        "source_bundle_package",
        "package",
        "SUCCESS",
        "database",
        "database://missions/mission-1/build-artifacts/source-bundle-package",
        "abc123",
        128,
        {"file_count": 1},
        {"verified": True},
        "build complete",
        "print('ok')",
        now.isoformat(),
    )
    assert artifact["artifact_id"] == "source-bundle-package"
    assert artifact["artifact_text"] == "print('ok')"

    listed = storage.list_build_artifacts(settings, "mission-1", 10)
    assert listed[0]["artifact_id"] == "source-bundle-package"
    assert listed[0]["artifact_text"] is None

    found = storage.get_build_artifact(settings, "mission-1", "source-bundle-package")
    assert found is not None
    assert found["digest_sha256"] == "abc123"


def test_storage_operations_views_and_summaries(monkeypatch) -> None:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    _patch_db(
        monkeypatch,
        [
            FakeCursor(fetchall_results=[[("RUNNING", 2), ("FAILED", 1)]]),
            FakeCursor(
                fetchall_results=[
                    [("mission-1", "QUEUED", "RUNNING", "MISSION_RUNNING", now)]
                ]
            ),
            FakeCursor(
                fetchall_results=[
                    [("mission-1", "podA", {"source": "test"}, now, now)]
                ]
            ),
            FakeCursor(
                fetchall_results=[
                    [("mission-1", "node-1", {"intent": "x"}, now)]
                ]
            ),
            FakeCursor(
                fetchall_results=[
                    [("mission-1", "audit-1", "PASS", {"score": 1}, now)]
                ]
            ),
            FakeCursor(
                fetchall_results=[
                    [
                        ("payroll", 3, now, 1, 1),
                        ("benefits", 2, now, 0, 2),
                    ]
                ]
            ),
        ],
    )
    settings = _settings()

    counts = storage.mission_state_counts(settings)
    assert counts == {"RUNNING": 2, "FAILED": 1}

    events = storage.list_recent_mission_events(settings, 10)
    assert len(events) == 1
    assert events[0].new_state == MissionState.running

    assignments = storage.list_pod_assignments(settings, 10)
    assert len(assignments) == 1
    assert assignments[0]["pod_name"] == "podA"

    logicnodes = storage.list_recent_logicnodes(settings, 10)
    assert logicnodes[0]["node_id"] == "node-1"

    audits = storage.list_recent_audit_reports(settings, 10)
    assert audits[0]["audit_id"] == "audit-1"

    projects = storage.summarize_projects(settings, 10)
    assert projects[0]["status"] == "paused"
    assert projects[1]["status"] == "completed"


def test_agent_heartbeat_and_event_views(monkeypatch) -> None:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    first_upsert_row = (
        "AGENT-01-PM",
        "RUNNING",
        2,
        60,
        ["mission-1"],
        {"source": "test"},
        now,
        now,
    )
    second_upsert_row = (
        "AGENT-01-PM",
        "RUNNING",
        1,
        40,
        ["mission-1"],
        {"source": "test"},
        now,
        now,
    )
    _patch_db(
        monkeypatch,
        [
            FakeCursor(fetchone_results=[None, first_upsert_row]),
            FakeCursor(fetchone_results=[("RUNNING",), second_upsert_row]),
            FakeCursor(fetchone_results=[first_upsert_row]),
            FakeCursor(fetchall_results=[[first_upsert_row]]),
            FakeCursor(
                fetchall_results=[
                    [
                        (
                            1,
                            "AGENT-01-PM",
                            "IDLE",
                            "RUNNING",
                            "AGENT_STATE_CHANGED",
                            {"queue_depth": 2},
                            now,
                        )
                    ]
                ]
            ),
        ],
    )
    settings = _settings()

    inserted = storage.upsert_agent_heartbeat(
        settings,
        "AGENT-01-PM",
        "RUNNING",
        2,
        60,
        ["mission-1"],
        {"source": "test"},
        now.isoformat(),
    )
    assert inserted["state_changed"] is True
    assert inserted["state"] == "RUNNING"

    updated = storage.upsert_agent_heartbeat(
        settings,
        "AGENT-01-PM",
        "RUNNING",
        1,
        40,
        ["mission-1"],
        {"source": "test"},
        now.isoformat(),
    )
    assert updated["state_changed"] is False

    heartbeat = storage.get_agent_heartbeat(settings, "AGENT-01-PM")
    assert heartbeat is not None
    assert heartbeat["agent_id"] == "AGENT-01-PM"

    listed = storage.list_agent_heartbeats(settings, 5)
    assert listed[0]["queue_depth"] == 2

    events = storage.list_recent_agent_events(settings, 5)
    assert events[0]["event_type"] == "AGENT_STATE_CHANGED"
