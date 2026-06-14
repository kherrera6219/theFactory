import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

knowledge_embeddings = importlib.import_module("orchestrator.knowledge_embeddings")
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
    )
    return Settings(**{**base.__dict__, **overrides})


def test_embedding_config_defaults_to_gemini() -> None:
    # S1-04: default provider was intentionally changed from "deterministic" to "gemini".
    # S5-03: with knowledge_embedding_model defaulting to "" (no hardcoded model),
    # embedding_config falls through to the per-provider default → gemini-embedding-001
    # (the actual model available on the API; text-embedding-004 was dead).
    config = knowledge_embeddings.embedding_config(_settings(), vector_size=64)

    assert config["provider"] == "gemini"
    assert config["model"] == "gemini-embedding-001"
    assert config["dimensions"] == 64


def test_vector_for_content_is_stable_without_provider_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = _settings(
        knowledge_embedding_provider="openai",
        knowledge_embedding_model="text-embedding-3-large",
    )

    first = knowledge_embeddings.vector_for_content(
        settings,
        mission_id="mission-1",
        knowledge_id="knowledge-1",
        content={"combined_text": "hello"},
        vector_size=8,
    )
    second = knowledge_embeddings.vector_for_content(
        settings,
        mission_id="mission-1",
        knowledge_id="knowledge-1",
        content={"combined_text": "hello"},
        vector_size=8,
    )

    assert first == second
    assert len(first) == 8


def test_openai_embedding_uses_dimensions_and_vector(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    requests: list[dict[str, object]] = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return json.dumps({"data": [{"embedding": [0.1, 0.2, 0.3]}]}).encode()

    def _fake_urlopen(request, timeout: float):
        requests.append(
            {
                "url": request.full_url,
                "body": json.loads(request.data.decode()),
                "timeout": timeout,
            }
        )
        return _FakeResponse()

    monkeypatch.setattr(knowledge_embeddings, "urlopen", _fake_urlopen)
    vector = knowledge_embeddings.vector_for_content(
        _settings(
            knowledge_embedding_provider="openai",
            knowledge_embedding_model="text-embedding-3-large",
        ),
        mission_id="mission-1",
        knowledge_id="knowledge-1",
        content={"combined_text": "hello"},
        vector_size=3,
    )

    assert vector == [0.1, 0.2, 0.3]
    assert requests[0]["url"].endswith("/embeddings")
    assert requests[0]["body"]["dimensions"] == 3


# ---------------------------------------------------------------------------
# Gemini happy path
# ---------------------------------------------------------------------------

def test_gemini_embedding_happy_path(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    requests: list[dict] = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def read(self) -> bytes:
            return json.dumps({"embedding": {"values": [0.5, 0.6, 0.7]}}).encode()

    def _fake_urlopen(request, timeout: float):
        requests.append({
            "url": request.full_url,
            "body": json.loads(request.data.decode()),
            "timeout": timeout,
        })
        return _FakeResponse()

    monkeypatch.setattr(knowledge_embeddings, "urlopen", _fake_urlopen)
    vector = knowledge_embeddings.vector_for_content(
        _settings(
            knowledge_embedding_provider="gemini",
            knowledge_embedding_model="gemini-embedding-001",
        ),
        mission_id="mission-1",
        knowledge_id="knowledge-1",
        content={"combined_text": "test text"},
        vector_size=3,
    )

    assert vector == [0.5, 0.6, 0.7]
    assert "embedContent" in requests[0]["url"]
    assert requests[0]["body"]["task_type"] == "RETRIEVAL_DOCUMENT"


def test_gemini_task_type_forwarded_to_api(monkeypatch) -> None:
    """task_type must be sent in the Gemini request body — RETRIEVAL_QUERY for search."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    captured_bodies: list[dict] = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def read(self) -> bytes:
            return json.dumps({"embedding": {"values": [0.1, 0.2, 0.3]}}).encode()

    def _fake_urlopen(request, timeout: float):
        captured_bodies.append(json.loads(request.data.decode()))
        return _FakeResponse()

    monkeypatch.setattr(knowledge_embeddings, "urlopen", _fake_urlopen)

    knowledge_embeddings.vector_for_content(
        _settings(knowledge_embedding_provider="gemini"),
        mission_id="m",
        knowledge_id="k",
        content={"combined_text": "query text"},
        vector_size=3,
        task_type="RETRIEVAL_QUERY",
    )

    assert len(captured_bodies) == 1
    assert captured_bodies[0]["task_type"] == "RETRIEVAL_QUERY"


def test_knowledge_embedding_api_key_overrides_gemini_env(monkeypatch) -> None:
    """KNOWLEDGE_EMBEDDING_API_KEY takes precedence over GEMINI_API_KEY."""
    monkeypatch.setenv("GEMINI_API_KEY", "global-gemini-key")
    captured_urls: list[str] = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def read(self) -> bytes:
            return json.dumps({"embedding": {"values": [0.1, 0.2]}}).encode()

    def _fake_urlopen(request, timeout: float):
        captured_urls.append(request.full_url)
        return _FakeResponse()

    monkeypatch.setattr(knowledge_embeddings, "urlopen", _fake_urlopen)
    knowledge_embeddings.vector_for_content(
        _settings(
            knowledge_embedding_provider="gemini",
            knowledge_embedding_api_key="dedicated-key",
        ),
        mission_id="m",
        knowledge_id="k",
        content={"combined_text": "text"},
        vector_size=2,
    )

    assert len(captured_urls) == 1
    assert "dedicated-key" in captured_urls[0]
    assert "global-gemini-key" not in captured_urls[0]


def test_knowledge_embedding_api_key_overrides_openai_env(monkeypatch) -> None:
    """KNOWLEDGE_EMBEDDING_API_KEY takes precedence over OPENAI_API_KEY."""
    monkeypatch.setenv("OPENAI_API_KEY", "global-openai-key")
    captured_headers: list[dict] = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def read(self) -> bytes:
            return json.dumps({"data": [{"embedding": [0.1, 0.2]}]}).encode()

    def _fake_urlopen(request, timeout: float):
        captured_headers.append(dict(request.headers))
        return _FakeResponse()

    monkeypatch.setattr(knowledge_embeddings, "urlopen", _fake_urlopen)
    knowledge_embeddings.vector_for_content(
        _settings(
            knowledge_embedding_provider="openai",
            knowledge_embedding_model="text-embedding-3-large",
            knowledge_embedding_api_key="dedicated-openai-key",
        ),
        mission_id="m",
        knowledge_id="k",
        content={"combined_text": "text"},
        vector_size=2,
    )

    assert len(captured_headers) == 1
    auth = captured_headers[0].get("Authorization") or captured_headers[0].get("authorization") or ""
    assert "dedicated-openai-key" in auth
    assert "global-openai-key" not in auth
