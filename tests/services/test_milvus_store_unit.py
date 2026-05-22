import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

milvus_store = importlib.import_module("orchestrator.milvus_store")
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
        milvus_uri="http://milvus:19530",
        milvus_token="",
        milvus_enabled=True,
        milvus_collection="mission_knowledge",
        milvus_vector_size=8,
        milvus_timeout_seconds=1.0,
    )
    return Settings(**{**base.__dict__, **overrides})


class _FakeMilvusClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.created = False
        self.create_calls: list[dict[str, object]] = []
        self.upsert_calls: list[dict[str, object]] = []
        self.query_rows: list[dict[str, object]] = []

    def has_collection(self, *, collection_name: str) -> bool:
        _ = collection_name
        return self.created

    def create_collection(self, **kwargs) -> None:
        self.created = True
        self.create_calls.append(kwargs)

    def upsert(self, **kwargs) -> None:
        self.upsert_calls.append(kwargs)

    def query(self, **kwargs):
        _ = kwargs
        return self.query_rows


def test_ensure_collection_creates_when_missing(monkeypatch) -> None:
    milvus_store._COLLECTION_CACHE.clear()
    milvus_store._CLIENT_CACHE.clear()
    client = _FakeMilvusClient()
    monkeypatch.setattr(milvus_store, "MilvusClient", lambda **kwargs: client)

    milvus_store.ensure_collection(_settings())
    milvus_store.ensure_collection(_settings())

    assert len(client.create_calls) == 1
    assert client.create_calls[0]["collection_name"] == "mission_knowledge"
    assert client.create_calls[0]["dimension"] == 8


def test_upsert_knowledge_builds_payload(monkeypatch) -> None:
    client = _FakeMilvusClient()
    monkeypatch.setattr(milvus_store, "ensure_collection", lambda _settings: None)
    monkeypatch.setattr(milvus_store, "_client", lambda _settings: client)

    milvus_store.upsert_knowledge(
        _settings(milvus_vector_size=16),
        "mission-1",
        "knowledge-1",
        {"title": "Node", "score": 1},
        "2026-03-03T00:00:00+00:00",
    )

    assert len(client.upsert_calls) == 1
    payload = client.upsert_calls[0]
    assert payload["collection_name"] == "mission_knowledge"
    point = payload["data"][0]
    assert point["mission_id"] == "mission-1"
    assert point["knowledge_id"] == "knowledge-1"
    assert point["embedding_provider"] == "deterministic"
    assert point["embedding_model"] == "deterministic-hash-v1"
    assert point["embedding_dimensions"] == 16
    assert len(point["vector"]) == 16


def test_list_knowledge_parses_rows_and_sorts_by_created_at(monkeypatch) -> None:
    client = _FakeMilvusClient()
    client.query_rows = [
        {
            "mission_id": "mission-1",
            "knowledge_id": "k-old",
            "content": {"value": "old"},
            "created_at": "2026-03-03T00:00:00+00:00",
        },
        {
            "mission_id": "mission-1",
            "knowledge_id": "k-new",
            "content": '{"value":"new"}',
            "created_at": "2026-03-03T01:00:00+00:00",
        },
    ]
    monkeypatch.setattr(milvus_store, "ensure_collection", lambda _settings: None)
    monkeypatch.setattr(milvus_store, "_client", lambda _settings: client)

    records = milvus_store.list_knowledge(_settings(), "mission-1", 10)

    assert [record["knowledge_id"] for record in records] == ["k-new", "k-old"]
    assert records[0]["content"] == {"value": "new"}
    assert records[1]["content"] == {"value": "old"}


def test_milvus_ready_returns_false_when_disabled() -> None:
    assert milvus_store.milvus_ready(_settings(milvus_enabled=False)) is False


def test_milvus_ready_returns_false_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        milvus_store,
        "ensure_collection",
        lambda _settings: (_ for _ in ()).throw(RuntimeError("down")),
    )

    assert milvus_store.milvus_ready(_settings()) is False


def test_milvus_ready_sets_ready_on_success(monkeypatch) -> None:
    monkeypatch.setattr(milvus_store, "ensure_collection", lambda _settings: None)
    assert milvus_store.milvus_ready(_settings()) is True
