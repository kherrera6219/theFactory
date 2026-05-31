import importlib
import json
import sys
from pathlib import Path

import pytest

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


def test_ensure_collection_creates_mission_id_payload_index(monkeypatch) -> None:
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

    index_calls = [
        (method, path, payload)
        for method, path, payload in calls
        if path.startswith("/collections/mission_knowledge/index")
    ]
    assert index_calls == [
        (
            "PUT",
            "/collections/mission_knowledge/index?wait=true",
            {"field_name": "mission_id", "field_schema": "keyword"},
        )
    ]


def test_ensure_collection_payload_index_is_idempotent(monkeypatch) -> None:
    qdrant_store._COLLECTION_CACHE.clear()

    def _request(settings: Settings, method: str, path: str, payload=None):
        _ = settings, payload
        if method == "GET":
            return {"status": "ok"}
        if path.startswith("/collections/mission_knowledge/index"):
            raise RuntimeError("index already exists")
        return {"status": "ok"}

    monkeypatch.setattr(qdrant_store, "_request_json", _request)

    # Must not raise even when the index already exists on the server.
    qdrant_store.ensure_collection(_settings())


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


def test_request_json_rejects_paths_without_leading_slash() -> None:
    with pytest.raises(ValueError, match="must start"):
        qdrant_store._request_json(_settings(), "GET", "collections/mission_knowledge")


def test_request_json_returns_empty_for_blank_and_non_dict_bodies(monkeypatch) -> None:
    class _Response:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def read(self) -> bytes:
            return self._body

    bodies = iter([b"", b"[]"])
    monkeypatch.setattr(qdrant_store, "urlopen", lambda *_args, **_kwargs: _Response(next(bodies)))

    assert qdrant_store._request_json(_settings(), "GET", "/collections/mission_knowledge") == {}
    assert qdrant_store._request_json(_settings(), "GET", "/collections/mission_knowledge") == {}


def test_vector_for_content_is_stable_and_respects_size() -> None:
    settings = _settings(qdrant_vector_size=4)
    first = qdrant_store._vector_for_content(settings, "mission-1", "knowledge-1", {"x": 1})
    second = qdrant_store._vector_for_content(settings, "mission-1", "knowledge-1", {"x": 1})
    assert first == second
    assert len(first) == 4


def test_point_payload_to_record_handles_invalid_content_types() -> None:
    assert qdrant_store._point_payload_to_record({"content": "{not-json}"})["content"] == {}
    assert qdrant_store._point_payload_to_record({"content": 123})["content"] == {}


def test_upsert_knowledge_builds_qdrant_point_payload(monkeypatch) -> None:
    calls: list[tuple[str, str, dict[str, object] | None]] = []
    monkeypatch.setattr(qdrant_store, "ensure_collection", lambda _settings: None)

    def _request(settings: Settings, method: str, path: str, payload=None):
        _ = settings
        calls.append((method, path, payload))
        return {"status": "ok"}

    monkeypatch.setattr(qdrant_store, "_request_json", _request)

    qdrant_store.upsert_knowledge(
        # Explicitly use deterministic so the test does not depend on the
        # global default and does not need a live Gemini key.
        _settings(
            qdrant_vector_size=16,
            knowledge_embedding_provider="deterministic",
            knowledge_embedding_model="deterministic-hash-v1",
        ),
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
    assert point["payload"]["embedding_provider"] == "deterministic"
    assert point["payload"]["embedding_model"] == "deterministic-hash-v1"
    assert point["payload"]["embedding_dimensions"] == 16
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


def test_list_knowledge_fills_missing_ids_and_skips_bad_points(monkeypatch) -> None:
    monkeypatch.setattr(qdrant_store, "ensure_collection", lambda _settings: None)
    monkeypatch.setattr(
        qdrant_store,
        "_request_json",
        lambda *_args, **_kwargs: {
            "result": {
                "points": [
                    {"id": "mission-1:k-1", "payload": {"content": json.dumps({"value": 1})}},
                    {"id": "mission-1:k-2", "payload": "bad-payload"},
                    "bad-point",
                ]
            }
        },
    )

    assert qdrant_store.list_knowledge(_settings(), "mission-1", 10) == [
        {
            "mission_id": "mission-1",
            "knowledge_id": "mission-1:k-1",
            "content": {"value": 1},
            "created_at": "",
        }
    ]


def test_qdrant_ready_returns_false_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        qdrant_store,
        "ensure_collection",
        lambda _settings: (_ for _ in ()).throw(RuntimeError("down")),
    )

    assert qdrant_store.qdrant_ready(_settings()) is False


def test_qdrant_ready_returns_false_when_disabled() -> None:
    assert qdrant_store.qdrant_ready(_settings(qdrant_enabled=False)) is False


def test_qdrant_ready_returns_true_on_success(monkeypatch) -> None:
    monkeypatch.setattr(qdrant_store, "ensure_collection", lambda _settings: None)
    assert qdrant_store.qdrant_ready(_settings()) is True
