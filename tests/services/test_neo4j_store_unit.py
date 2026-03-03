import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

neo4j_store = importlib.import_module("orchestrator.neo4j_store")
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

    assert len(calls) == 3
    assert "mission_id_unique" in calls[0]
    assert "knowledge_composite_unique" in calls[1]
    assert "audit_composite_unique" in calls[2]


def test_upsert_knowledge_uses_expected_query_and_payload(monkeypatch) -> None:
    statements: list[tuple[str, dict[str, object] | None]] = []
    monkeypatch.setattr(neo4j_store, "ensure_schema", lambda _settings: None)

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


def test_neo4j_ready_returns_false_when_disabled() -> None:
    assert neo4j_store.neo4j_ready(_settings(neo4j_enabled=False)) is False


def test_neo4j_ready_returns_false_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        neo4j_store,
        "ensure_schema",
        lambda _settings: (_ for _ in ()).throw(RuntimeError("down")),
    )

    assert neo4j_store.neo4j_ready(_settings()) is False
