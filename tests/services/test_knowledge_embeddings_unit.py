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
    config = knowledge_embeddings.embedding_config(_settings(), vector_size=64)

    assert config["provider"] == "gemini"
    assert config["model"] == "text-embedding-004"
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
