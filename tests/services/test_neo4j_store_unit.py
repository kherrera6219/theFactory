import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

neo4j_store = importlib.import_module("orchestrator.neo4j_store")
data_plane_metrics = importlib.import_module("orchestrator.data_plane_metrics")
Settings = importlib.import_module("orchestrator.settings").Settings


def _settings(**overrides: object) -> Settings:
    base = Settings(
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
        event_schema_path=ROOT / "schemas" / "event.envelope.schema.json",
        topics_path=ROOT / "protocol" / "topics.yaml",
        admin_api_key="admin-key",
        internal_service_api_key="worker-key",
        readonly_api_key="viewer-key",
        extra_api_keys="",
        qdrant_url="http://qdrant:6333",
        qdrant_api_key="",
        qdrant_enabled=True,
        qdrant_collection="mission_knowledge",
        qdrant_vector_size=8,
        qdrant_timeout_seconds=1.0,
        neo4j_url="http://neo4j:7474",
        neo4j_enabled=True,
        neo4j_username="neo4j",
        neo4j_password="pass",
        neo4j_database="neo4j",
        neo4j_timeout_seconds=1.0,
    )
    return Settings(**{**base.__dict__, **overrides})


def test_ensure_schema_creates_constraints_once(monkeypatch) -> None:
    neo4j_store._SCHEMA_CACHE.clear()
    calls: list[str] = []

    def _execute(settings: Settings, statement: str, parameters=None):
        _ = settings, parameters
        calls.append(statement)
        return []

    monkeypatch.setattr(neo4j_store, "_execute_cypher", _execute)

    settings = _settings()
    neo4j_store.ensure_schema(settings)
    neo4j_store.ensure_schema(settings)

    assert len(calls) == 4
    assert "mission_id_unique" in calls[0]
    assert "knowledge_composite_unique" in calls[1]
    assert "audit_composite_unique" in calls[2]
    assert "logicnode_composite_unique" in calls[3]


def test_request_json_rejects_non_http_urls() -> None:
    try:
        neo4j_store._request_json(
            _settings(neo4j_url="file:///tmp/neo4j"),
            "/db/neo4j/tx/commit",
            {"statements": []},
        )
    except ValueError as exc:
        assert "http or https" in str(exc)
    else:
        raise AssertionError("expected neo4j url validation failure")


def test_validated_http_url_rejects_missing_slash() -> None:
    try:
        neo4j_store._validated_http_url(
            "https://neo4j.example",
            "db/neo4j/tx/commit",
            service="neo4j",
        )
    except ValueError as exc:
        assert "must start with '/'" in str(exc)
    else:
        raise AssertionError("expected path validation failure")


def test_request_json_builds_basic_auth_and_parses_dict(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        @staticmethod
        def read() -> bytes:
            return b'{"results": [], "errors": []}'

    def _urlopen(request, timeout: float):
        captured["full_url"] = request.full_url
        captured["timeout"] = timeout
        captured["authorization"] = request.get_header("Authorization")
        captured["content_type"] = request.get_header("Content-type")
        captured["body"] = request.data
        return _Response()

    monkeypatch.setattr(neo4j_store, "urlopen", _urlopen)
    payload = {"statements": [{"statement": "RETURN 1"}]}
    result = neo4j_store._request_json(_settings(), "/db/neo4j/tx/commit", payload)

    assert result == {"results": [], "errors": []}
    assert captured["full_url"] == "http://neo4j:7474/db/neo4j/tx/commit"
    assert captured["timeout"] == 1.0
    assert str(captured["authorization"]).startswith("Basic ")
    assert captured["content_type"] == "application/json"
    assert json.loads(captured["body"].decode("utf-8")) == payload


def test_request_json_returns_empty_for_blank_or_non_dict_response(monkeypatch) -> None:
    class _Response:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def read(self) -> bytes:
            return self._body

    bodies = iter([b"", b"[]"])
    monkeypatch.setattr(neo4j_store, "urlopen", lambda *_args, **_kwargs: _Response(next(bodies)))

    assert (
        neo4j_store._request_json(_settings(), "/db/neo4j/tx/commit", {"statements": []}) == {}
    )
    assert (
        neo4j_store._request_json(_settings(), "/db/neo4j/tx/commit", {"statements": []}) == {}
    )


def test_execute_cypher_raises_for_neo4j_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        neo4j_store,
        "_request_json",
        lambda *_args, **_kwargs: {"errors": [{"code": "Neo.ClientError", "message": "boom"}]},
    )

    try:
        neo4j_store._execute_cypher(_settings(), "RETURN 1")
    except RuntimeError as exc:
        assert "Neo.ClientError: boom" in str(exc)
    else:
        raise AssertionError("expected neo4j error")


def test_query_rows_skips_malformed_entries(monkeypatch) -> None:
    monkeypatch.setattr(
        neo4j_store,
        "_execute_cypher",
        lambda *_args, **_kwargs: [
            {
                "columns": ["kind", "value"],
                "data": [
                    {"row": ["alpha", 1]},
                    {"row": "not-a-list"},
                    "not-a-dict",
                    {"row": ["beta"]},
                ],
            }
        ],
    )

    assert neo4j_store._query_rows(_settings(), "RETURN 1") == [
        {"kind": "alpha", "value": 1},
        {"kind": "beta"},
    ]


def test_upsert_knowledge_uses_expected_query_and_payload(monkeypatch) -> None:
    statements: list[tuple[str, dict[str, object] | None]] = []
    monkeypatch.setattr(neo4j_store, "ensure_schema", lambda _settings: None)
    before = data_plane_metrics.OPTIONAL_ADAPTER_OPERATIONS_TOTAL.labels(
        adapter="neo4j",
        operation="upsert_knowledge",
        status="success",
    )._value.get()

    def _execute(settings: Settings, statement: str, parameters=None):
        _ = settings
        statements.append((statement, parameters))
        return []

    monkeypatch.setattr(neo4j_store, "_execute_cypher", _execute)

    neo4j_store.upsert_knowledge(
        _settings(),
        "mission-1",
        "k-1",
        {"title": "doc"},
        "2026-03-03T00:00:00+00:00",
    )

    assert len(statements) == 1
    statement, parameters = statements[0]
    assert "MERGE (m:Mission" in statement
    assert "MERGE (k:Knowledge" in statement
    assert parameters is not None
    assert parameters["mission_id"] == "mission-1"
    assert parameters["knowledge_id"] == "k-1"
    after = data_plane_metrics.OPTIONAL_ADAPTER_OPERATIONS_TOTAL.labels(
        adapter="neo4j",
        operation="upsert_knowledge",
        status="success",
    )._value.get()
    assert after >= before + 1


def test_upsert_audit_report_uses_expected_payload(monkeypatch) -> None:
    statements: list[tuple[str, dict[str, object] | None]] = []
    monkeypatch.setattr(neo4j_store, "ensure_schema", lambda _settings: None)

    def _execute(settings: Settings, statement: str, parameters=None):
        _ = settings
        statements.append((statement, parameters))
        return []

    monkeypatch.setattr(neo4j_store, "_execute_cypher", _execute)

    neo4j_store.upsert_audit_report(
        _settings(),
        "mission-1",
        "audit-1",
        "PASS",
        {"score": 100},
        "2026-03-03T00:00:00+00:00",
    )

    statement, parameters = statements[0]
    assert "MERGE (a:AuditReport" in statement
    assert parameters is not None
    assert parameters["status"] == "PASS"
    assert json.loads(parameters["report_json"]) == {"score": 100}


def test_list_mission_graph_parses_rows(monkeypatch) -> None:
    monkeypatch.setattr(neo4j_store, "ensure_schema", lambda _settings: None)
    monkeypatch.setattr(
        neo4j_store,
        "_query_rows",
        lambda *_: [
            {
                "relation_type": "HAS_KNOWLEDGE",
                "target_labels": ["Knowledge"],
                "target_properties": {"knowledge_id": "k-1"},
            },
            {
                "relation_type": "HAS_AUDIT_REPORT",
                "target_labels": ["AuditReport"],
                "target_properties": {"audit_id": "a-1"},
            },
        ],
    )

    rows = neo4j_store.list_mission_graph(_settings(), "mission-1", 10)

    assert rows[0]["relation_type"] == "HAS_KNOWLEDGE"
    assert rows[1]["target_properties"]["audit_id"] == "a-1"


def test_list_mission_graph_filters_invalid_row_shapes(monkeypatch) -> None:
    monkeypatch.setattr(neo4j_store, "ensure_schema", lambda _settings: None)
    monkeypatch.setattr(
        neo4j_store,
        "_query_rows",
        lambda *_: [
            {
                "relation_type": "HAS_KNOWLEDGE",
                "target_labels": "bad-shape",
                "target_properties": "bad-shape",
            },
            "not-a-dict",
        ],
    )

    assert neo4j_store.list_mission_graph(_settings(), "mission-1", 999) == [
        {
            "relation_type": "HAS_KNOWLEDGE",
            "target_labels": [],
            "target_properties": {},
        }
    ]


def test_neo4j_ready_returns_false_when_disabled() -> None:
    assert neo4j_store.neo4j_ready(_settings(neo4j_enabled=False)) is False
    assert (
        data_plane_metrics.OPTIONAL_ADAPTER_ENABLED.labels(adapter="neo4j")._value.get() == 0
    )
    assert data_plane_metrics.OPTIONAL_ADAPTER_READY.labels(adapter="neo4j")._value.get() == 0


def test_neo4j_ready_returns_false_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        neo4j_store,
        "ensure_schema",
        lambda _settings: (_ for _ in ()).throw(RuntimeError("down")),
    )

    assert neo4j_store.neo4j_ready(_settings()) is False
    assert data_plane_metrics.OPTIONAL_ADAPTER_READY.labels(adapter="neo4j")._value.get() == 0


def test_neo4j_ready_sets_ready_on_success(monkeypatch) -> None:
    monkeypatch.setattr(neo4j_store, "ensure_schema", lambda _settings: None)
    monkeypatch.setattr(neo4j_store, "_query_rows", lambda *_: [{"ok": 1}])
    assert neo4j_store.neo4j_ready(_settings()) is True
    assert data_plane_metrics.OPTIONAL_ADAPTER_ENABLED.labels(adapter="neo4j")._value.get() == 1
    assert data_plane_metrics.OPTIONAL_ADAPTER_READY.labels(adapter="neo4j")._value.get() == 1


def test_neo4j_ready_returns_false_when_probe_not_ok(monkeypatch) -> None:
    monkeypatch.setattr(neo4j_store, "ensure_schema", lambda _settings: None)
    monkeypatch.setattr(neo4j_store, "_query_rows", lambda *_: [{"ok": 0}])
    assert neo4j_store.neo4j_ready(_settings()) is False
