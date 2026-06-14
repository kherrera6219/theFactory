"""Unit tests for knowledge_lake.py.

Covers: _embedding_key_available, _semantic_search_enabled, is_stocked,
index_documentation, _mirror_to_qdrant, query_documentation routing,
_vector_search (RETRIEVAL_QUERY task-type regression), _keyword_search,
and get_language_context.
"""
import importlib
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

knowledge_lake = importlib.import_module("orchestrator.knowledge_lake")
knowledge_embeddings = importlib.import_module("orchestrator.knowledge_embeddings")
qdrant_store = importlib.import_module("orchestrator.qdrant_store")
orchestrator_settings = importlib.import_module("orchestrator.settings")

Settings = orchestrator_settings.Settings


def _settings(**overrides: Any) -> Settings:
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
        knowledge_embedding_provider="gemini",
        qdrant_enabled=True,
        qdrant_vector_size=8,
        qdrant_collection="mission_knowledge",
    )
    return Settings(**{**base.__dict__, **overrides})


# ---------------------------------------------------------------------------
# _embedding_key_available
# ---------------------------------------------------------------------------

def test_embedding_key_available_dedicated_key_wins(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    settings = _settings(knowledge_embedding_api_key="dedicated-key", knowledge_embedding_provider="gemini")
    assert knowledge_lake._embedding_key_available(settings) is True


def test_embedding_key_available_falls_back_to_gemini_env(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "global-gemini-key")
    settings = _settings(knowledge_embedding_api_key="", knowledge_embedding_provider="gemini")
    assert knowledge_lake._embedding_key_available(settings) is True


def test_embedding_key_available_falls_back_to_openai_env(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "global-openai-key")
    settings = _settings(knowledge_embedding_api_key="", knowledge_embedding_provider="openai")
    assert knowledge_lake._embedding_key_available(settings) is True


def test_embedding_key_available_returns_false_when_no_key(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = _settings(knowledge_embedding_api_key="", knowledge_embedding_provider="gemini")
    assert knowledge_lake._embedding_key_available(settings) is False


def test_embedding_key_available_deterministic_provider_always_false(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "some-key")
    settings = _settings(knowledge_embedding_api_key="", knowledge_embedding_provider="deterministic")
    assert knowledge_lake._embedding_key_available(settings) is False


# ---------------------------------------------------------------------------
# _semantic_search_enabled
# ---------------------------------------------------------------------------

def test_semantic_search_enabled_all_conditions_met(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    settings = _settings(knowledge_embedding_provider="gemini", qdrant_enabled=True)
    assert knowledge_lake._semantic_search_enabled(settings) is True


def test_semantic_search_disabled_when_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = _settings(knowledge_embedding_provider="gemini", qdrant_enabled=True, knowledge_embedding_api_key="")
    assert knowledge_lake._semantic_search_enabled(settings) is False


def test_semantic_search_disabled_when_deterministic_provider(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    settings = _settings(knowledge_embedding_provider="deterministic", qdrant_enabled=True)
    assert knowledge_lake._semantic_search_enabled(settings) is False


def test_semantic_search_disabled_when_qdrant_off(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    settings = _settings(knowledge_embedding_provider="gemini", qdrant_enabled=False)
    assert knowledge_lake._semantic_search_enabled(settings) is False


def test_semantic_search_enabled_with_openai_and_dedicated_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = _settings(
        knowledge_embedding_provider="openai",
        qdrant_enabled=True,
        knowledge_embedding_api_key="dedicated-embedding-key",
    )
    assert knowledge_lake._semantic_search_enabled(settings) is True


# ---------------------------------------------------------------------------
# is_stocked
# ---------------------------------------------------------------------------

def test_is_stocked_returns_true_when_rows_exist(monkeypatch) -> None:
    monkeypatch.setattr(
        knowledge_lake, "list_knowledge",
        lambda _s, _m, limit: [{"knowledge_id": "docs.python.bootstrap", "content": {}}],
    )
    assert knowledge_lake.is_stocked(settings=_settings(), mission_id="mission-1") is True


def test_is_stocked_returns_false_when_no_rows(monkeypatch) -> None:
    monkeypatch.setattr(knowledge_lake, "list_knowledge", lambda *_a, **_k: [])
    assert knowledge_lake.is_stocked(settings=_settings(), mission_id="mission-1") is False


def test_is_stocked_language_matches_bootstrap_knowledge_id(monkeypatch) -> None:
    monkeypatch.setattr(
        knowledge_lake, "list_knowledge",
        lambda _s, _m, limit: [
            {"knowledge_id": "docs.python.bootstrap", "content": {}},
            {"knowledge_id": "docs.javascript.bootstrap", "content": {}},
        ],
    )
    assert knowledge_lake.is_stocked(settings=_settings(), language="python") is True
    assert knowledge_lake.is_stocked(settings=_settings(), language="PYTHON") is True
    assert knowledge_lake.is_stocked(settings=_settings(), language="rust") is False


def test_is_stocked_returns_false_on_storage_error(monkeypatch) -> None:
    def _raise(*_a, **_k):
        raise RuntimeError("db down")
    monkeypatch.setattr(knowledge_lake, "list_knowledge", _raise)
    assert knowledge_lake.is_stocked(settings=_settings(), mission_id="mission-1") is False


# ---------------------------------------------------------------------------
# index_documentation
# ---------------------------------------------------------------------------

def test_index_documentation_writes_to_postgres(monkeypatch) -> None:
    calls: list[tuple] = []

    def _fake_upsert(settings, mission_id, knowledge_id, payload, created_at):
        calls.append((mission_id, knowledge_id, payload))

    monkeypatch.setattr(knowledge_lake, "upsert_knowledge", _fake_upsert)
    monkeypatch.setattr(knowledge_lake, "_mirror_to_qdrant", lambda **_k: None)

    result = knowledge_lake.index_documentation(
        settings=_settings(),
        language="Python",
        library="FastAPI",
        content="FastAPI is a modern web framework.",
    )

    assert result is True
    assert len(calls) == 1
    mission_id, knowledge_id, payload = calls[0]
    assert mission_id == knowledge_lake._KNOWLEDGE_LAKE_ID
    assert knowledge_id == "docs.python.fastapi"
    assert payload["combined_text"] == "FastAPI is a modern web framework."
    assert payload["language"] == "python"
    assert payload["library"] == "fastapi"
    assert payload["kind"] == "documentation"


def test_index_documentation_normalises_library_name(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_upsert(settings, mission_id, knowledge_id, payload, created_at):
        calls.append(knowledge_id)

    monkeypatch.setattr(knowledge_lake, "upsert_knowledge", _fake_upsert)
    monkeypatch.setattr(knowledge_lake, "_mirror_to_qdrant", lambda **_k: None)

    knowledge_lake.index_documentation(
        settings=_settings(), language="Python", library="My Library", content="docs."
    )
    assert calls == ["docs.python.my_library"]


def test_index_documentation_calls_mirror(monkeypatch) -> None:
    monkeypatch.setattr(knowledge_lake, "upsert_knowledge", lambda *_a: None)
    mirror_calls: list[str] = []

    def _fake_mirror(*, settings, knowledge_id, payload, created_at):
        mirror_calls.append(knowledge_id)

    monkeypatch.setattr(knowledge_lake, "_mirror_to_qdrant", _fake_mirror)

    knowledge_lake.index_documentation(
        settings=_settings(), language="python", library="requests", content="HTTP library."
    )
    assert mirror_calls == ["docs.python.requests"]


def test_index_documentation_returns_false_on_postgres_failure(monkeypatch) -> None:
    def _raise(*_a):
        raise RuntimeError("connection refused")
    monkeypatch.setattr(knowledge_lake, "upsert_knowledge", _raise)

    result = knowledge_lake.index_documentation(
        settings=_settings(), language="python", library="requests", content="HTTP library."
    )
    assert result is False


# ---------------------------------------------------------------------------
# _mirror_to_qdrant
# ---------------------------------------------------------------------------

def test_mirror_to_qdrant_skips_when_semantic_disabled(monkeypatch) -> None:
    monkeypatch.setattr(knowledge_lake, "_semantic_search_enabled", lambda _s: False)
    qdrant_calls: list[str] = []
    monkeypatch.setattr(qdrant_store, "upsert_knowledge", lambda *_a: qdrant_calls.append("called"))

    knowledge_lake._mirror_to_qdrant(
        settings=_settings(),
        knowledge_id="docs.python.django",
        payload={"combined_text": "Django."},
        created_at="2026-01-01T00:00:00Z",
    )
    assert qdrant_calls == []


def test_mirror_to_qdrant_calls_qdrant_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(knowledge_lake, "_semantic_search_enabled", lambda _s: True)
    qdrant_calls: list[str] = []
    monkeypatch.setattr(qdrant_store, "upsert_knowledge", lambda *_a: qdrant_calls.append("called"))

    knowledge_lake._mirror_to_qdrant(
        settings=_settings(),
        knowledge_id="docs.python.django",
        payload={"combined_text": "Django."},
        created_at="2026-01-01T00:00:00Z",
    )
    assert qdrant_calls == ["called"]


def test_mirror_to_qdrant_swallows_qdrant_error(monkeypatch) -> None:
    monkeypatch.setattr(knowledge_lake, "_semantic_search_enabled", lambda _s: True)
    def _raise(*_a):
        raise RuntimeError("qdrant down")
    monkeypatch.setattr(qdrant_store, "upsert_knowledge", _raise)

    # Must not raise — Qdrant is best-effort
    knowledge_lake._mirror_to_qdrant(
        settings=_settings(),
        knowledge_id="docs.python.flask",
        payload={"combined_text": "Flask."},
        created_at="2026-01-01T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# query_documentation — routing
# ---------------------------------------------------------------------------

def test_query_documentation_uses_vector_search_when_semantic_enabled(monkeypatch) -> None:
    monkeypatch.setattr(knowledge_lake, "_semantic_search_enabled", lambda _s: True)
    vector_results = [{"knowledge_id": "docs.python.requests", "content": {}, "score": 0.9}]
    monkeypatch.setattr(knowledge_lake, "_vector_search",
        lambda *, settings, language_key, concept_key, top_k: vector_results)
    keyword_calls: list[str] = []
    monkeypatch.setattr(knowledge_lake, "_keyword_search",
        lambda **_k: keyword_calls.append("called") or [])

    results = knowledge_lake.query_documentation(
        settings=_settings(), language="python", concept="http requests"
    )
    assert results == vector_results
    assert keyword_calls == []


def test_query_documentation_falls_back_to_keyword_when_vector_empty(monkeypatch) -> None:
    monkeypatch.setattr(knowledge_lake, "_semantic_search_enabled", lambda _s: True)
    monkeypatch.setattr(knowledge_lake, "_vector_search", lambda **_k: [])
    keyword_results = [{"knowledge_id": "docs.python.requests", "content": {}, "score": 0.5}]
    monkeypatch.setattr(knowledge_lake, "_keyword_search", lambda **_k: keyword_results)

    results = knowledge_lake.query_documentation(
        settings=_settings(), language="python", concept="http requests"
    )
    assert results == keyword_results


def test_query_documentation_skips_vector_search_when_semantic_disabled(monkeypatch) -> None:
    monkeypatch.setattr(knowledge_lake, "_semantic_search_enabled", lambda _s: False)
    vector_calls: list[str] = []
    monkeypatch.setattr(knowledge_lake, "_vector_search",
        lambda **_k: vector_calls.append("called") or [])
    keyword_results = [{"knowledge_id": "docs.python.stdlib", "content": {}, "score": 0.3}]
    monkeypatch.setattr(knowledge_lake, "_keyword_search", lambda **_k: keyword_results)

    results = knowledge_lake.query_documentation(
        settings=_settings(), language="python", concept="os path"
    )
    assert results == keyword_results
    assert vector_calls == []


# ---------------------------------------------------------------------------
# _vector_search — RETRIEVAL_QUERY task-type regression
# ---------------------------------------------------------------------------

def test_vector_search_passes_retrieval_query_task_type_and_natural_language_content(monkeypatch) -> None:
    """Regression: _vector_search must pass task_type=RETRIEVAL_QUERY and
    content={"combined_text": concept_key} — previously it passed a JSON dict
    and RETRIEVAL_DOCUMENT, causing semantically wrong query embeddings."""
    captured: list[dict] = []

    def _fake_vector_for_content(
        settings, *, mission_id, knowledge_id, content, vector_size, task_type="RETRIEVAL_DOCUMENT"
    ) -> list[float]:
        captured.append({"content": content, "task_type": task_type})
        return [0.1] * vector_size

    monkeypatch.setattr(knowledge_embeddings, "vector_for_content", _fake_vector_for_content)
    monkeypatch.setattr(qdrant_store, "ensure_collection", lambda _s: None)
    monkeypatch.setattr(qdrant_store, "_request_json", lambda _s, _m, _p, payload: {
        "result": [{
            "payload": {
                "knowledge_id": "docs.python.requests",
                "content": {"combined_text": "HTTP lib"},
                "mission_id": "__knowledge_lake__",
            },
            "score": 0.95,
        }]
    })

    results = knowledge_lake._vector_search(
        settings=_settings(),
        language_key="python",
        concept_key="http requests",
        top_k=3,
    )

    assert len(captured) == 1, "vector_for_content should be called exactly once"
    assert captured[0]["task_type"] == "RETRIEVAL_QUERY", (
        "_vector_search must use RETRIEVAL_QUERY so Gemini returns similarity-optimised vectors"
    )
    assert captured[0]["content"] == {"combined_text": "http requests"}, (
        "_vector_search must embed the concept as natural-language text, not a JSON-serialised dict"
    )
    assert len(results) == 1
    assert results[0]["score"] == 0.95
    assert results[0]["knowledge_id"] == "docs.python.requests"


def test_vector_search_returns_empty_on_qdrant_error(monkeypatch) -> None:
    monkeypatch.setattr(knowledge_embeddings, "vector_for_content", lambda *_a, **_k: [0.1] * 8)
    monkeypatch.setattr(qdrant_store, "ensure_collection", lambda _s: None)

    def _raise(*_a, **_k):
        raise RuntimeError("qdrant unavailable")

    monkeypatch.setattr(qdrant_store, "_request_json", _raise)

    results = knowledge_lake._vector_search(
        settings=_settings(), language_key="python", concept_key="http", top_k=3
    )
    assert results == []


def test_vector_search_returns_empty_when_result_not_list(monkeypatch) -> None:
    monkeypatch.setattr(knowledge_embeddings, "vector_for_content", lambda *_a, **_k: [0.1] * 8)
    monkeypatch.setattr(qdrant_store, "ensure_collection", lambda _s: None)
    monkeypatch.setattr(qdrant_store, "_request_json", lambda *_a, **_k: {"result": None})

    results = knowledge_lake._vector_search(
        settings=_settings(), language_key="python", concept_key="http", top_k=3
    )
    assert results == []


# ---------------------------------------------------------------------------
# _keyword_search
# ---------------------------------------------------------------------------

def test_keyword_search_scores_and_ranks_by_token_overlap(monkeypatch) -> None:
    records = [
        {
            "knowledge_id": "docs.python.requests",
            "content": {"language": "python", "combined_text": "http requests client library get post"},
        },
        {
            "knowledge_id": "docs.python.flask",
            "content": {"language": "python", "combined_text": "flask web framework routing"},
        },
        {
            "knowledge_id": "docs.javascript.fetch",
            "content": {"language": "javascript", "combined_text": "fetch http requests"},
        },
    ]
    monkeypatch.setattr(knowledge_lake, "list_knowledge", lambda *_a, **_k: records)

    results = knowledge_lake._keyword_search(
        settings=_settings(), language_key="python", concept_key="http requests", top_k=5
    )

    ids = [r["knowledge_id"] for r in results]
    assert "docs.python.requests" in ids
    assert "docs.javascript.fetch" not in ids  # wrong language filtered out
    assert ids[0] == "docs.python.requests"  # highest token overlap


def test_keyword_search_respects_top_k(monkeypatch) -> None:
    records = [
        {"knowledge_id": f"docs.python.lib{i}", "content": {"language": "python", "combined_text": f"python lib{i} library"}}
        for i in range(10)
    ]
    monkeypatch.setattr(knowledge_lake, "list_knowledge", lambda *_a, **_k: records)

    results = knowledge_lake._keyword_search(
        settings=_settings(), language_key="python", concept_key="python library", top_k=3
    )
    assert len(results) <= 3


def test_keyword_search_returns_empty_when_no_overlap(monkeypatch) -> None:
    records = [
        {"knowledge_id": "docs.python.requests", "content": {"language": "python", "combined_text": "http client library"}},
    ]
    monkeypatch.setattr(knowledge_lake, "list_knowledge", lambda *_a, **_k: records)

    results = knowledge_lake._keyword_search(
        settings=_settings(), language_key="python", concept_key="database orm migrations", top_k=5
    )
    assert results == []


def test_keyword_search_returns_empty_on_storage_error(monkeypatch) -> None:
    def _raise(*_a, **_k):
        raise RuntimeError("db down")
    monkeypatch.setattr(knowledge_lake, "list_knowledge", _raise)

    results = knowledge_lake._keyword_search(
        settings=_settings(), language_key="python", concept_key="requests", top_k=3
    )
    assert results == []


# ---------------------------------------------------------------------------
# get_language_context
# ---------------------------------------------------------------------------

def test_get_language_context_returns_combined_text(monkeypatch) -> None:
    monkeypatch.setattr(
        knowledge_lake, "list_knowledge",
        lambda _s, _m, limit: [
            {"knowledge_id": "docs.python.bootstrap", "content": {"combined_text": "Python stdlib docs."}},
        ],
    )
    result = knowledge_lake.get_language_context(settings=_settings(), language="Python")
    assert result == "Python stdlib docs."


def test_get_language_context_normalises_language_key(monkeypatch) -> None:
    def _fake_list(settings, mission_id, limit):
        return [{"knowledge_id": "docs.javascript.bootstrap", "content": {"combined_text": "JS docs."}}]

    monkeypatch.setattr(knowledge_lake, "list_knowledge", _fake_list)
    result = knowledge_lake.get_language_context(settings=_settings(), language="JavaScript")
    assert result == "JS docs."


def test_get_language_context_returns_none_when_not_indexed(monkeypatch) -> None:
    monkeypatch.setattr(knowledge_lake, "list_knowledge", lambda *_a, **_k: [])
    assert knowledge_lake.get_language_context(settings=_settings(), language="python") is None


def test_get_language_context_truncates_long_content(monkeypatch) -> None:
    long_text = "x" * 10_000
    monkeypatch.setattr(
        knowledge_lake, "list_knowledge",
        lambda _s, _m, limit: [
            {"knowledge_id": "docs.python.bootstrap", "content": {"combined_text": long_text}},
        ],
    )
    result = knowledge_lake.get_language_context(settings=_settings(), language="python")
    assert result is not None
    assert len(result) <= knowledge_lake._MAX_CONTEXT_CHARS + len("\n...[truncated]")
    assert result.endswith("...[truncated]")


def test_get_language_context_ignores_non_bootstrap_records(monkeypatch) -> None:
    monkeypatch.setattr(
        knowledge_lake, "list_knowledge",
        lambda _s, _m, limit: [
            {"knowledge_id": "docs.python.requests", "content": {"combined_text": "HTTP lib."}},
            {"knowledge_id": "docs.python.bootstrap", "content": {"combined_text": "Bootstrap text."}},
        ],
    )
    result = knowledge_lake.get_language_context(settings=_settings(), language="python")
    assert result == "Bootstrap text."


def test_get_language_context_returns_none_on_storage_error(monkeypatch) -> None:
    def _raise(*_a, **_k):
        raise RuntimeError("db down")
    monkeypatch.setattr(knowledge_lake, "list_knowledge", _raise)
    assert knowledge_lake.get_language_context(settings=_settings(), language="python") is None
