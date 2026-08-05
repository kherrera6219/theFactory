import importlib
import sys
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

storage = importlib.import_module("orchestrator.storage")
orchestrator_models = importlib.import_module("orchestrator.models")
orchestrator_settings = importlib.import_module("orchestrator.settings")
storage_agents = importlib.import_module("orchestrator.storage_agents")
storage_artifacts = importlib.import_module("orchestrator.storage_artifacts")
storage_core = importlib.import_module("orchestrator.storage_core")
storage_logicnodes = importlib.import_module("orchestrator.storage_logicnodes")
storage_missions = importlib.import_module("orchestrator.storage_missions")
storage_object_store = importlib.import_module("orchestrator.object_store")
storage_pods = importlib.import_module("orchestrator.storage_pods")

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
        self.transaction_calls = 0

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


class _FakeTxn:
    def __enter__(self) -> "_FakeTxn":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeConn:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> FakeCursor:
        return self._cursor

    def transaction(self) -> "_FakeTxn":
        self._cursor.transaction_calls += 1
        return _FakeTxn()

    def __enter__(self) -> "FakeConn":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeTxnConn(FakeConn):
    def __init__(self, cursor: FakeCursor) -> None:
        super().__init__(cursor)
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _patch_db(monkeypatch, cursors: list[FakeCursor]) -> list[FakeCursor]:
    queue = list(cursors)
    used: list[FakeCursor] = []

    def _next_conn() -> FakeConn:
        cursor = queue.pop(0)
        used.append(cursor)
        return FakeConn(cursor)

    def _db_connect(_: Settings) -> FakeConn:
        return _next_conn()

    @contextmanager
    def _get_connection():
        yield _next_conn()

    # db_connect is still used by ensure_db_schema/migrations; get_connection
    # backs all storage operations now that they borrow from the pool.
    monkeypatch.setattr(storage_core, "db_connect", _db_connect)
    monkeypatch.setattr(storage, "db_connect", _db_connect)
    for module in (
        storage,
        storage_core,
        storage_missions,
        storage_pods,
        storage_logicnodes,
        storage_artifacts,
        storage_agents,
    ):
        monkeypatch.setattr(module, "get_connection", _get_connection)
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
    monkeypatch.setattr(storage_core, "psycopg", None)
    with pytest.raises(RuntimeError):
        storage.db_connect(_settings())


def test_ensure_db_schema_executes_queries(monkeypatch) -> None:
    cursor = FakeCursor()
    used = _patch_db(monkeypatch, [cursor])
    storage.ensure_db_schema(_settings())
    assert used
    assert len(cursor.executed) >= 3
    # Migrations are bracketed by a session-level advisory lock/unlock.
    assert "pg_advisory_lock" in cursor.executed[0][0]
    assert any("schema_migrations" in query for query, _ in cursor.executed)
    assert any(
        "SELECT version, checksum FROM schema_migrations" in query
        for query, _ in cursor.executed
    )
    assert any("pg_advisory_unlock" in query for query, _ in cursor.executed)


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
        "hmac-001",
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
        "2026-03-30T00:00:00+00:00",
        "hmac-001",
    )
    fetched = storage.get_review_approval(_settings(), "repo-approval-f1234567890abcde")

    assert created["approval_id"] == "repo-approval-f1234567890abcde"
    assert created["storage_backend"] == "postgres"
    assert created["expires_at"] == "2026-03-29T00:00:00+00:00"
    assert created["hmac_digest"] == "hmac-001"
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
    success_cursor = FakeCursor(fetchone_results=[row])
    noop_cursor = FakeCursor(fetchone_results=[None])
    _patch_db(monkeypatch, [success_cursor, noop_cursor])
    settings = _settings()

    record = storage.transition_mission_state(
        settings,
        "mission-1",
        MissionState.queued,
        MissionState.running,
        "MISSION_RUNNING",
    )
    assert record is not None
    # Two executes on the same cursor: the state UPDATE and the event INSERT (atomic).
    assert len(success_cursor.executed) == 2
    event_params = success_cursor.executed[1][1]
    assert event_params[0] == "mission-1"
    assert event_params[1] == MissionState.queued.value
    assert event_params[2] == MissionState.running.value
    assert event_params[3] == "MISSION_RUNNING"

    none_record = storage.transition_mission_state(
        settings,
        "mission-1",
        None,
        MissionState.failed,
        "MISSION_FAILED",
    )
    assert none_record is None


def test_persist_intake_mission_writes_mission_and_event_atomically(monkeypatch) -> None:
    cursor = FakeCursor(fetchone_results=[("mission-1",)])
    _patch_db(monkeypatch, [cursor])

    created = storage.persist_intake_mission(_settings(), _mission_record(), "1-0")

    assert created is True
    assert cursor.transaction_calls == 1
    assert len(cursor.executed) == 2
    assert "INSERT INTO missions" in cursor.executed[0][0]
    assert cursor.executed[0][1][-1] == "1-0"
    assert "INSERT INTO mission_state_events" in cursor.executed[1][0]
    assert cursor.executed[1][1] == (
        "mission-1",
        MissionState.intake.value,
        MissionState.queued.value,
        "MISSION_QUEUED",
    )


def test_persist_intake_mission_does_not_mutate_duplicate(monkeypatch) -> None:
    cursor = FakeCursor(fetchone_results=[None])
    _patch_db(monkeypatch, [cursor])

    created = storage.persist_intake_mission(_settings(), _mission_record(), "1-0")

    assert created is False
    assert cursor.transaction_calls == 1
    assert len(cursor.executed) == 1
    assert "ON CONFLICT (mission_id) DO NOTHING" in cursor.executed[0][0]


def test_prune_audit_tables_maps_results_and_passes_retention(monkeypatch) -> None:
    cursor = FakeCursor(
        fetchall_results=[
            [
                ("mission_state_events", 5),
                ("agent_runtime_events", 0),
                ("agent_action_events", 2),
                ("llm_usage_events", 7),
            ]
        ]
    )
    used = _patch_db(monkeypatch, [cursor])

    results = storage.prune_audit_tables(_settings(), retention_days=30)

    assert results == [
        {"table_name": "mission_state_events", "rows_deleted": 5},
        {"table_name": "agent_runtime_events", "rows_deleted": 0},
        {"table_name": "agent_action_events", "rows_deleted": 2},
        {"table_name": "llm_usage_events", "rows_deleted": 7},
    ]
    query, params = used[0].executed[0]
    assert "prune_audit_tables(%s)" in query
    assert params == (30,)


def test_prune_audit_tables_defaults_to_settings_and_clamps(monkeypatch) -> None:
    cursor = FakeCursor(fetchall_results=[[]])
    used = _patch_db(monkeypatch, [cursor])

    results = storage.prune_audit_tables(_settings())

    assert results == []
    assert used[0].executed[0][1] == (90,)


def test_list_project_agent_action_events_casts_nullable_filters(monkeypatch) -> None:
    cursor = FakeCursor(fetchall_results=[[]])
    used = _patch_db(monkeypatch, [cursor])

    results = storage.list_project_agent_action_events(
        _settings(),
        "project-1",
        200,
    )

    assert results == []
    query, params = used[0].executed[0]
    assert "%s::text IS NULL OR mission_id = %s" in query
    assert "%s::text IS NULL OR agent_id = %s" in query
    assert "%s::text IS NULL OR tool_name = %s" in query
    assert params == ("project-1", None, None, None, None, None, None, 200)


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
        storage_pods,
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

    monkeypatch.setattr(storage_pods, "get_pod_assignment", lambda *_: None)
    with pytest.raises(RuntimeError):
        storage.upsert_pod_assignment(
            settings,
            "mission-1",
            "podA",
            {},
            "2026-03-01T00:00:00+00:00",
        )


def test_pod_assignment_claim_may_supersede_a_provisional_row(monkeypatch) -> None:
    """A worker claim takes over an orchestrator-written row on any pod."""
    now = datetime(2026, 3, 1, tzinfo=UTC)
    cursor = FakeCursor(
        fetchone_results=[("mission-1", "podA", {"assigned_by": "pod-worker"}, now, now)]
    )
    used = _patch_db(monkeypatch, [cursor])

    record = storage.upsert_pod_assignment(
        _settings(),
        "mission-1",
        "podA",
        {"assigned_by": "pod-worker"},
        "2026-03-01T00:00:00+00:00",
    )

    assert record["metadata"] == {"assigned_by": "pod-worker"}
    query, params = used[0].executed[0]
    # Same pod, or any pod when the existing row is provisional.
    assert "mission_pod_assignments.pod_name = EXCLUDED.pod_name" in query
    assert "mission_pod_assignments.metadata_json->>'assigned_by' = %(provisional)s" in query
    assert params["provisional"] == "orchestrator"


def test_provisional_pod_assignment_never_overwrites_a_claim(monkeypatch) -> None:
    """The orchestrator's provisional write only updates provisional rows."""
    existing = {
        "mission_id": "mission-1",
        "pod_name": "podA",
        "metadata": {"assigned_by": "pod-worker"},
        "assigned_at": "2026-03-01T00:00:00+00:00",
        "updated_at": "2026-03-01T00:00:00+00:00",
    }
    used = _patch_db(monkeypatch, [FakeCursor(fetchone_results=[None])])
    monkeypatch.setattr(storage_pods, "get_pod_assignment", lambda *_: existing)

    with pytest.raises(storage.PodAssignmentConflictError) as excinfo:
        storage.upsert_pod_assignment(
            _settings(),
            "mission-1",
            "podA",
            {"assigned_by": "orchestrator"},
            "2026-03-01T00:00:00+00:00",
            provisional=True,
        )

    assert excinfo.value.existing_assignment["metadata"]["assigned_by"] == "pod-worker"
    query, _params = used[0].executed[0]
    # No same-pod escape hatch: a provisional write must not be able to downgrade
    # a claim just because it happens to name the same pod.
    assert "mission_pod_assignments.pod_name = EXCLUDED.pod_name" not in query
    assert "mission_pod_assignments.metadata_json->>'assigned_by' = %(provisional)s" in query


def test_is_provisional_assignment_reads_record_or_metadata() -> None:
    assert storage.is_provisional_assignment({"metadata": {"assigned_by": "orchestrator"}})
    assert storage.is_provisional_assignment({"assigned_by": "Orchestrator"})
    assert not storage.is_provisional_assignment({"metadata": {"assigned_by": "pod-worker"}})
    assert not storage.is_provisional_assignment({"pod_name": "podA"})
    assert not storage.is_provisional_assignment("podA")


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


def test_build_artifact_object_storage_offload_and_fallback(monkeypatch) -> None:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    settings = replace(
        _settings(),
        object_storage_enabled=True,
        object_storage_size_threshold_bytes=4,
        object_storage_prefix="factory",
    )
    artifact_row = (
        "mission-1",
        "artifact-1",
        "source",
        "package",
        "SUCCESS",
        "s3",
        "factory/mission-1/artifacts/artifact-1.txt",
        "abc123",
        128,
        {"file_count": 1},
        {"verified": True},
        "build complete",
        None,
        now,
        now,
    )
    captured: dict[str, Any] = {}

    def _put_object(_settings_obj, *, key, body, content_type, metadata):
        captured.update(
            {
                "key": key,
                "body": body,
                "content_type": content_type,
                "metadata": metadata,
            }
        )

    monkeypatch.setattr(storage_object_store, "put_object", _put_object)
    _patch_db(monkeypatch, [FakeCursor(fetchone_results=[artifact_row])])

    artifact = storage.upsert_build_artifact(
        settings,
        "mission-1",
        "artifact-1",
        "source",
        "package",
        "SUCCESS",
        "database",
        None,
        "abc123",
        128,
        {"file_count": 1},
        {"verified": True},
        "build complete",
        "print('large enough')",
        now.isoformat(),
    )

    assert artifact["storage_backend"] == "s3"
    assert artifact["storage_ref"] == "factory/mission-1/artifacts/artifact-1.txt"
    assert artifact["artifact_text"] is None
    assert captured["body"] == b"print('large enough')"

    fallback_row = (
        "mission-1",
        "artifact-2",
        "source",
        "package",
        "SUCCESS",
        "database",
        None,
        "def456",
        1,
        {},
        {},
        "",
        "inline → ok",
        now,
        now,
    )

    def _raise_put_object(*_args, **_kwargs):
        raise RuntimeError("s3 unavailable")

    monkeypatch.setattr(storage_object_store, "put_object", _raise_put_object)
    _patch_db(monkeypatch, [FakeCursor(fetchone_results=[fallback_row])])
    fallback = storage.upsert_build_artifact(
        settings,
        "mission-1",
        "artifact-2",
        "source",
        "package",
        "SUCCESS",
        "database",
        None,
        "def456",
        -10,
        {},
        {},
        "",
        "inline → ok",
        now.isoformat(),
    )
    assert fallback["storage_backend"] == "database"
    assert fallback["artifact_text"] == "inline → ok"
    readback = fallback["manifest"]["encoding_trace"]["storage_readback"]
    assert readback["length_chars"] == len("inline → ok")
    assert readback["size_bytes"] == len("inline → ok".encode("utf-8"))
    assert readback["non_ascii_count"] == 1


def test_get_build_artifact_returns_none_when_missing(monkeypatch) -> None:
    _patch_db(monkeypatch, [FakeCursor(fetchone_results=[None])])
    assert storage.get_build_artifact(_settings(), "mission-1", "missing") is None


def test_testdata_manifest_and_runtime_qc_roundtrip(monkeypatch) -> None:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    manifest_row = (
        "mission-1",
        {"language": "python", "base_image": "python:3.12", "test_framework": "pytest"},
        "python",
        "python:3.12",
        "pytest",
        "generated",
        now,
    )
    qc_row = (
        "mission-1",
        "container",
        "PASS",
        "APPROVED",
        0,
        "python",
        "main.py",
        "python:3.12",
        "ok",
        "",
        {"execution_type": "container", "verdict": "PASS"},
        {"qc_verdict": "APPROVED"},
        now,
        now,
        now,
    )
    _patch_db(
        monkeypatch,
        [
            FakeCursor(fetchone_results=[manifest_row]),
            FakeCursor(fetchone_results=[manifest_row]),
            FakeCursor(fetchone_results=[None]),
            FakeCursor(fetchone_results=[qc_row]),
            FakeCursor(fetchone_results=[qc_row]),
            FakeCursor(fetchone_results=[None]),
        ],
    )
    settings = _settings()

    inserted_manifest = storage.insert_testdata_manifest(
        settings,
        "mission-1",
        {
            "language": " python ",
            "base_image": " python:3.12 ",
            "test_framework": " pytest ",
            "source": " generated ",
        },
    )
    assert inserted_manifest["language"] == "python"
    assert storage.get_testdata_manifest(settings, "mission-1")["base_image"] == "python:3.12"
    assert storage.get_testdata_manifest(settings, "missing") is None

    inserted_qc = storage.insert_runtime_qc_report(
        settings,
        "mission-1",
        {
            "execution_type": "container",
            "verdict": "PASS",
            "exit_code": 0,
            "language": "python",
            "filename": "main.py",
            "base_image": "python:3.12",
            "stdout_preview": "ok",
            "stderr_preview": "",
            "started_at": now.isoformat(),
            "completed_at": now.isoformat(),
        },
        {"qc_verdict": "APPROVED"},
    )
    assert inserted_qc["qc_verdict"] == "APPROVED"
    assert storage.get_runtime_qc_report(settings, "mission-1")["verdict"] == "PASS"
    assert storage.get_runtime_qc_report(settings, "missing") is None


def test_locked_mission_metadata_update_branches(monkeypatch) -> None:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    row = ("mission-1", "Build API", "python", {"source": "test"}, "QUEUED", now)
    updated_row = ("mission-1", "Build API", "python", {"updated": True}, "QUEUED", now)

    missing_conn = FakeTxnConn(FakeCursor(fetchone_results=[None]))
    fallback_conn = FakeTxnConn(FakeCursor(fetchone_results=[row, updated_row]))
    none_update_conn = FakeTxnConn(FakeCursor(fetchone_results=[row, None]))
    queue = [missing_conn, fallback_conn, none_update_conn]

    monkeypatch.setattr(
        storage_missions,
        "psycopg",
        SimpleNamespace(connect=lambda *_args, **_kwargs: queue.pop(0)),
    )

    assert (
        storage_missions._locked_mission_metadata_update(
            _settings(), "missing", lambda *_: {}
        )
        is None
    )
    assert missing_conn.closed is True

    updated = storage_missions._locked_mission_metadata_update(
        _settings(),
        "mission-1",
        lambda metadata, _mission: ["not-a-dict", metadata],
    )
    assert updated is not None
    assert updated.metadata == {"updated": True}
    assert fallback_conn.closed is True

    assert (
        storage_missions._locked_mission_metadata_update(
            _settings(),
            "mission-1",
            lambda metadata, _mission: metadata,
        )
        is None
    )
    assert none_update_conn.closed is True


def test_locked_mission_metadata_update_requires_psycopg(monkeypatch) -> None:
    monkeypatch.setattr(storage_missions, "psycopg", None)
    with pytest.raises(RuntimeError, match="psycopg"):
        storage_missions._locked_mission_metadata_update(
            _settings(), "mission-1", lambda *_: {}
        )


def test_record_partition_result_updates_counts_and_merge(monkeypatch) -> None:
    captured: dict[str, Any] = {}
    merged_result = SimpleNamespace(
        merged_at="2026-03-01T01:00:00+00:00",
        to_dict=lambda: {"logicnodes": [{"node_id": "merged"}]},
    )

    def _locked_update(_settings_obj, _mission_id, updater):
        metadata = {
            "partition_results": {
                "part-1": {
                    "partition_id": "part-1",
                    "instance_index": 0,
                    "agent_id": "AGENT-14-PYTHON",
                    "logicnodes": [{"node_id": "n1"}],
                    "artifacts": [{"artifact_id": "a1"}],
                    "report": {"status": "ok"},
                    "completed_at": "2026-03-01T00:00:00+00:00",
                }
            }
        }
        mission = _mission_record()
        captured["metadata"] = updater(metadata, mission)
        return mission

    monkeypatch.setattr(storage_missions, "_locked_mission_metadata_update", _locked_update)
    monkeypatch.setattr(storage_missions, "all_partitions_complete", lambda _metadata: True)
    monkeypatch.setattr(storage_missions, "merge_partition_results", lambda _results: merged_result)

    record = storage.record_partition_result(
        _settings(),
        "mission-1",
        {
            "partition_id": "part-2",
            "instance_index": 1,
            "agent_id": "AGENT-14-PYTHON",
            "logicnodes": [{"node_id": "n2"}, "skip"],
            "artifacts": [{"artifact_id": "a2"}, "skip"],
            "report": {"status": "ok"},
            "completed_at": "2026-03-01T01:00:00+00:00",
        },
    )

    assert record is not None
    assert captured["metadata"]["partition_result_count"] == 2
    assert captured["metadata"]["scaling_merge_complete"] is True
    assert captured["metadata"]["merged_partition_result"] == {
        "logicnodes": [{"node_id": "merged"}]
    }
    assert captured["metadata"]["scaling_completed_at"] == "2026-03-01T01:00:00+00:00"


def test_record_partition_result_marks_merge_incomplete(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _locked_update(_settings_obj, _mission_id, updater):
        metadata = {"partition_results": {}}
        captured["metadata"] = updater(metadata, _mission_record())
        return _mission_record()

    monkeypatch.setattr(storage_missions, "_locked_mission_metadata_update", _locked_update)
    monkeypatch.setattr(storage_missions, "all_partitions_complete", lambda _metadata: False)

    storage.record_partition_result(
        _settings(),
        "mission-1",
        {"partition_id": "part-1", "completed_at": "2026-03-01T00:00:00+00:00"},
    )

    assert captured["metadata"]["scaling_merge_complete"] is False
    assert captured["metadata"]["last_partition_result_at"] == "2026-03-01T00:00:00+00:00"


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


def test_agent_action_event_digest_insert_create_and_views(monkeypatch) -> None:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    event_row = (
        "aevt-1",
        "project-1",
        "mission-1",
        "AGENT-14-PYTHON",
        "orchestrator",
        "TOOL_CALL",
        "SUCCESS",
        "artifact",
        "artifact-1",
        "pytest",
        "trace-1",
        "span-1",
        "corr-1",
        None,
        now,
        now,
        0,
        {"files": 1},
        "content-digest",
        "s3://bucket/object",
        "prev-digest",
        "event-digest",
        now,
    )
    created_row = (
        "aevt-created",
        "project-1",
        "mission-1",
        "AGENT-14-PYTHON",
        "orchestrator",
        "BUILD",
        "SUCCESS",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        now,
        now,
        0,
        {},
        None,
        None,
        None,
        "created-digest",
        now,
    )
    _patch_db(
        monkeypatch,
        [
            FakeCursor(fetchone_results=[("prev-digest",), event_row]),
            FakeCursor(fetchone_results=[None, created_row]),
            FakeCursor(fetchall_results=[[event_row]]),
            FakeCursor(fetchall_results=[[event_row]]),
        ],
    )
    settings = _settings()
    record = orchestrator_models.AgentActionEventRecord(
        event_id="aevt-1",
        project_id="project-1",
        mission_id="mission-1",
        agent_id="AGENT-14-PYTHON",
        service_name="orchestrator",
        event_type="TOOL_CALL",
        status="SUCCESS",
        object_type="artifact",
        object_id="artifact-1",
        tool_name="pytest",
        trace_id="trace-1",
        span_id="span-1",
        correlation_id="corr-1",
        parent_event_id=None,
        started_at=now,
        ended_at=now,
        duration_ms=None,
        payload_summary={"files": 1},
        content_sha256="content-digest",
        blob_ref="s3://bucket/object",
        prev_event_digest_sha256=None,
        event_digest_sha256="pending",
        created_at=now,
    )

    inserted = storage.insert_agent_action_event(settings, record)
    assert inserted["event_id"] == "aevt-1"
    assert inserted["prev_event_digest_sha256"] == "prev-digest"
    assert inserted["duration_ms"] == 0

    created = storage.create_agent_action_event(
        settings,
        project_id="project-1",
        mission_id="mission-1",
        agent_id="AGENT-14-PYTHON",
        service_name="orchestrator",
        event_type="BUILD",
        started_at=now,
        ended_at=now,
        payload_summary=None,
    )
    assert created["event_id"] == "aevt-created"
    assert created["payload_summary"] == {}

    mission_events = storage.list_mission_agent_action_events(settings, "mission-1", 10)
    assert mission_events[0]["event_digest_sha256"] == "event-digest"

    project_events = storage.list_project_agent_action_events(
        settings,
        "project-1",
        10,
        mission_id="mission-1",
        agent_id="AGENT-14-PYTHON",
        tool_name="pytest",
    )
    assert project_events[0]["tool_name"] == "pytest"

    assert storage_agents._normalize_payload_summary(["not", "a", "dict"]) == {}
    assert storage_agents._event_duration_ms("bad", now) is None
    assert storage_agents._content_digest(
        record.model_copy(update={"content_sha256": None, "payload_summary": {}, "blob_ref": "blob"})
    )


def test_insert_agent_action_event_acquires_advisory_lock_before_reading_prev_digest(
    monkeypatch,
) -> None:
    """Regression: without a lock, two concurrent writers for the same
    project_id could both read the same prev_digest and both chain a new
    event onto it, forking the tamper-evident hash chain with no error.
    The read-then-chain critical section must be serialized per project_id.
    """
    now = datetime(2026, 3, 1, tzinfo=UTC)
    event_row = (
        "aevt-1", "project-1", "mission-1", "AGENT-14-PYTHON", "orchestrator",
        "TOOL_CALL", "SUCCESS", None, None, None, None, None, None, None,
        now, now, 0, {}, None, None, "prev-digest", "event-digest", now,
    )
    cursor = FakeCursor(fetchone_results=[("prev-digest",), event_row])
    _patch_db(monkeypatch, [cursor])
    settings = _settings()
    record = orchestrator_models.AgentActionEventRecord(
        event_id="aevt-1",
        project_id="project-1",
        mission_id="mission-1",
        agent_id="AGENT-14-PYTHON",
        service_name="orchestrator",
        event_type="TOOL_CALL",
        status="SUCCESS",
        started_at=now,
        ended_at=now,
        payload_summary={},
        event_digest_sha256="pending",
        created_at=now,
    )

    storage.insert_agent_action_event(settings, record)

    queries = [entry[0] for entry in cursor.executed]
    lock_index = next(i for i, q in enumerate(queries) if "pg_advisory_xact_lock" in q)
    select_index = next(i for i, q in enumerate(queries) if "SELECT event_digest_sha256" in q)
    insert_index = next(i for i, q in enumerate(queries) if "INSERT INTO agent_action_events" in q)
    assert lock_index < select_index < insert_index
    lock_params = cursor.executed[lock_index][1]
    assert lock_params == ("project-1",)
