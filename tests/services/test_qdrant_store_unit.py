import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

qdrant_store = importlib.import_module("orchestrator.qdrant_store")
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
        qdrant_enabled=True,
        qdrant_collection="mission_knowledge",
        qdrant_vector_size=8,
        qdrant_timeout_seconds=1.0,
    )
    return Settings(**{**base.__dict__, **overrides})


def test_ensure_collection_creates_when_missing(monkeypatch) -> None:
    qdrant_store._COLLECTION_CACHE.clear()
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def _request(settings: Settings, method: str, path: str, payload=None):
        _ = settings
        calls.append((method, path, payload))
        if method == "GET":
            raise RuntimeError("missing collection")
        return {"status": "ok"}

    monkeypatch.setattr(qdrant_store, "_request_json", _request)

    qdrant_store.ensure_collection(_settings())

    assert calls[0][0] == "GET"
    assert calls[1][0] == "PUT"
    assert calls[1][1] == "/collections/mission_knowledge"
    assert calls[1][2] == {"vectors": {"size": 8, "distance": "Cosine"}}


def test_request_json_sends_api_key_header(monkeypatch) -> None:
    headers_seen: dict[str, str] = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def read(self) -> bytes:
            return b"{}"

    def _urlopen(request, timeout):
        _ = timeout
        for key, value in request.header_items():
            headers_seen[key.lower()] = value
        return _Response()

    monkeypatch.setattr(qdrant_store, "urlopen", _urlopen)

    qdrant_store._request_json(
        _settings(qdrant_api_key="test-qdrant-key"),
        "GET",
        "/collections/mission_knowledge",
    )

    assert headers_seen.get("api-key") == "test-qdrant-key"


def test_request_json_rejects_non_http_urls() -> None:
    try:
        qdrant_store._request_json(
            _settings(qdrant_url="file:///tmp/qdrant"),
            "GET",
            "/collections/mission_knowledge",
        )
    except ValueError as exc:
        assert "http or https" in str(exc)
    else:
        raise AssertionError("expected qdrant url validation failure")


def test_upsert_knowledge_builds_qdrant_point_payload(monkeypatch) -> None:
    calls: list[tuple[str, str, dict[str, object] | None]] = []
    monkeypatch.setattr(qdrant_store, "ensure_collection", lambda _settings: None)

    def _request(settings: Settings, method: str, path: str, payload=None):
        _ = settings
        calls.append((method, path, payload))
        return {"status": "ok"}

    monkeypatch.setattr(qdrant_store, "_request_json", _request)

    qdrant_store.upsert_knowledge(
        _settings(qdrant_vector_size=16),
        "mission-1",
        "knowledge-1",
        {"title": "Node", "score": 1},
        "2026-03-03T00:00:00+00:00",
    )

    assert len(calls) == 1
    method, path, payload = calls[0]
    assert method == "PUT"
    assert path == "/collections/mission_knowledge/points?wait=true"
    assert isinstance(payload, dict)
    points = payload["points"]
    assert len(points) == 1
    point = points[0]
    assert point["id"] == "mission-1:knowledge-1"
    assert point["payload"]["mission_id"] == "mission-1"
    assert len(point["vector"]) == 16


def test_list_knowledge_parses_points_and_sorts_by_created_at(monkeypatch) -> None:
    monkeypatch.setattr(qdrant_store, "ensure_collection", lambda _settings: None)

    def _request(settings: Settings, method: str, path: str, payload=None):
        _ = settings, method, path, payload
        return {
            "result": {
                "points": [
                    {
                        "id": "mission-1:k-old",
                        "payload": {
                            "mission_id": "mission-1",
                            "knowledge_id": "k-old",
                            "content": {"value": "old"},
                            "created_at": "2026-03-03T00:00:00+00:00",
                        },
                    },
                    {
                        "id": "mission-1:k-new",
                        "payload": {
                            "mission_id": "mission-1",
                            "knowledge_id": "k-new",
                            "content": '{"value":"new"}',
                            "created_at": "2026-03-03T01:00:00+00:00",
                        },
                    },
                ]
            }
        }

    monkeypatch.setattr(qdrant_store, "_request_json", _request)

    records = qdrant_store.list_knowledge(_settings(), "mission-1", 10)

    assert [record["knowledge_id"] for record in records] == ["k-new", "k-old"]
    assert records[0]["content"] == {"value": "new"}
    assert records[1]["content"] == {"value": "old"}


def test_qdrant_ready_returns_false_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        qdrant_store,
        "ensure_collection",
        lambda _settings: (_ for _ in ()).throw(RuntimeError("down")),
    )

    assert qdrant_store.qdrant_ready(_settings()) is False
