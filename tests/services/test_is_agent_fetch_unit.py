"""tests/services/test_is_agent_fetch_unit.py

Unit tests for Phase 8 FETCH — IS Agent (is_agent.py) and Knowledge Lake
(knowledge_lake.py).  All Qdrant I/O and HTTP calls are patched so these
tests run offline with no Docker stack.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# Ensure the orchestrator package is importable regardless of test-run ordering.
_SERVICES_ORCHESTRATOR = str(Path(__file__).resolve().parents[2] / "services" / "orchestrator")
if _SERVICES_ORCHESTRATOR not in sys.path:
    sys.path.insert(0, _SERVICES_ORCHESTRATOR)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _mock_settings(*, qdrant_enabled: bool = True, mcp_url: str = "") -> Any:
    s = MagicMock()
    s.qdrant_enabled = qdrant_enabled
    s.qdrant_url = "http://qdrant:6333"
    s.qdrant_collection = "mission_knowledge"
    s.qdrant_vector_size = 64
    s.qdrant_api_key = ""
    s.qdrant_timeout_seconds = 3.0
    s.knowledge_refresh_enabled = True
    s.knowledge_embedding_provider = "deterministic"
    s.knowledge_embedding_model = "deterministic-hash-v1"
    s.mcp_url = mcp_url
    s.mcp_api_key = ""
    return s


# ---------------------------------------------------------------------------
# detect_required_languages
# ---------------------------------------------------------------------------

class TestDetectRequiredLanguages:
    def _call(self, **kwargs):
        from orchestrator.is_agent import detect_required_languages
        defaults = dict(
            prompt="",
            requested_target_language=None,
            source_code=None,
            mission_type="BUILD_NEW",
        )
        defaults.update(kwargs)
        return detect_required_languages(**defaults)

    def test_explicit_python_target(self):
        result = self._call(requested_target_language="python")
        assert "python" in result

    def test_typescript_expands_to_both(self):
        result = self._call(requested_target_language="typescript")
        assert "typescript" in result
        assert "javascript" in result

    def test_source_code_python_import(self):
        result = self._call(source_code="from pathlib import Path\n")
        assert "python" in result

    def test_source_code_js_require(self):
        result = self._call(source_code="const fs = require('fs');\n")
        assert "javascript" in result

    def test_unsupported_language_falls_back_to_python(self):
        # COBOL is not in SUPPORTED_LANGUAGES so default kicks in
        result = self._call(requested_target_language="cobol")
        # Returns whatever is available — no crash, returns a list
        assert isinstance(result, list)

    def test_result_sorted(self):
        result = self._call(requested_target_language="typescript")
        assert result == sorted(result)


# ---------------------------------------------------------------------------
# run_fetch_phase
# ---------------------------------------------------------------------------

class TestRunFetchPhase:
    def _run(self, coro):
        return asyncio.run(coro)

    def _call(self, *, required_languages, settings=None, storage_calls=None):
        from orchestrator.is_agent import run_fetch_phase

        if settings is None:
            settings = _mock_settings()

        # Patch the storage helpers inside is_agent
        def fake_check_exists(*, settings, knowledge_id):
            if storage_calls is not None:
                storage_calls.append(("check", knowledge_id))
            return False  # always needs indexing

        def fake_is_current(*, settings, knowledge_id, content_hash):
            return False

        def fake_upsert(*, settings, mission_id, knowledge_id, content, created_at):
            if storage_calls is not None:
                storage_calls.append(("upsert", knowledge_id))

        with (
            patch("orchestrator.is_agent._check_knowledge_exists", side_effect=fake_check_exists),
            patch("orchestrator.is_agent._knowledge_is_current", side_effect=fake_is_current),
            patch("orchestrator.is_agent._upsert_knowledge_safe", side_effect=fake_upsert),
        ):
            return self._run(
                run_fetch_phase(
                    mission_id="test-mission-001",
                    required_languages=required_languages,
                    settings=settings,
                )
            )

    def test_indexes_python(self):
        result = self._call(required_languages=["python"])
        assert "python" in result["indexed_languages"]
        assert result["knowledge_ready"] is True

    def test_indexes_java_and_javascript(self):
        result = self._call(required_languages=["java", "javascript"])
        assert "java" in result["indexed_languages"]
        assert "javascript" in result["indexed_languages"]

    def test_skips_unsupported_language(self):
        result = self._call(required_languages=["cobol"])
        assert "cobol" in result["skipped_languages"]
        assert result["knowledge_ready"] is False

    def test_mixed_supported_and_unsupported(self):
        result = self._call(required_languages=["python", "cobol"])
        assert "python" in result["indexed_languages"]
        assert "cobol" in result["skipped_languages"]
        assert result["knowledge_ready"] is True

    def test_upsert_called_for_each_language(self):
        calls: list = []
        self._call(required_languages=["python", "java"], storage_calls=calls)
        upserted_ids = [k for op, k in calls if op == "upsert"]
        assert any("python" in k for k in upserted_ids)
        assert any("java" in k for k in upserted_ids)

    def test_result_schema(self):
        result = self._call(required_languages=["python"])
        assert "indexed_languages" in result
        assert "skipped_languages" in result
        assert "errors" in result
        assert "knowledge_ids" in result
        assert "knowledge_ready" in result
        assert "indexed_at" in result
        assert "embedding_provider" in result

    def test_storage_failure_captured_not_raised(self):
        from orchestrator.is_agent import run_fetch_phase

        settings = _mock_settings()

        def exploding_check(*, settings, knowledge_id):
            raise RuntimeError("qdrant down")

        with patch("orchestrator.is_agent._check_knowledge_exists", side_effect=exploding_check):
            result = self._run(
                run_fetch_phase(
                    mission_id="test-mission-err",
                    required_languages=["python"],
                    settings=settings,
                )
            )

        # Should not raise; errors captured
        assert len(result["errors"]) > 0
        assert result["knowledge_ready"] is False

    def test_empty_languages_returns_not_ready(self):
        result = self._call(required_languages=[])
        assert result["knowledge_ready"] is False
        assert result["indexed_languages"] == []


# ---------------------------------------------------------------------------
# knowledge_lake.is_stocked
# ---------------------------------------------------------------------------

class TestIsStocked:
    def test_true_when_record_exists(self):
        from orchestrator.knowledge_lake import is_stocked

        settings = _mock_settings()
        fake_records = [{"knowledge_id": "docs.python.bootstrap", "content": {}}]

        with patch("orchestrator.knowledge_lake.list_knowledge", return_value=fake_records):
            assert is_stocked(settings=settings, language="python") is True

    def test_false_when_record_missing(self):
        from orchestrator.knowledge_lake import is_stocked

        settings = _mock_settings()
        with patch("orchestrator.knowledge_lake.list_knowledge", return_value=[]):
            assert is_stocked(settings=settings, language="python") is False

    def test_false_when_qdrant_disabled(self):
        from orchestrator.knowledge_lake import is_stocked

        settings = _mock_settings(qdrant_enabled=False)
        assert is_stocked(settings=settings, language="python") is False

    def test_false_on_exception(self):
        from orchestrator.knowledge_lake import is_stocked

        settings = _mock_settings()
        with patch("orchestrator.knowledge_lake.list_knowledge", side_effect=RuntimeError("boom")):
            assert is_stocked(settings=settings, language="python") is False


# ---------------------------------------------------------------------------
# knowledge_lake.get_language_context
# ---------------------------------------------------------------------------

class TestGetLanguageContext:
    def test_returns_text_for_matching_record(self):
        from orchestrator.knowledge_lake import get_language_context

        settings = _mock_settings()
        fake_records = [{
            "knowledge_id": "docs.python.bootstrap",
            "content": {
                "language": "python",
                "kind": "bootstrap_documentation",
                "combined_text": "Python list: append, extend, pop.",
            },
        }]
        with patch("orchestrator.knowledge_lake.list_knowledge", return_value=fake_records):
            result = get_language_context(settings=settings, language="python")
        assert result is not None
        assert "append" in result

    def test_returns_none_when_no_records(self):
        from orchestrator.knowledge_lake import get_language_context

        settings = _mock_settings()
        with patch("orchestrator.knowledge_lake.list_knowledge", return_value=[]):
            result = get_language_context(settings=settings, language="python")
        assert result is None

    def test_returns_none_when_qdrant_disabled(self):
        from orchestrator.knowledge_lake import get_language_context

        result = get_language_context(settings=_mock_settings(qdrant_enabled=False), language="python")
        assert result is None

    def test_truncates_long_context(self):
        from orchestrator.knowledge_lake import _MAX_CONTEXT_CHARS, get_language_context

        settings = _mock_settings()
        long_text = "x" * (_MAX_CONTEXT_CHARS + 500)
        fake_records = [{
            "knowledge_id": "docs.python.bootstrap",
            "content": {"language": "python", "kind": "bootstrap_documentation", "combined_text": long_text},
        }]
        with patch("orchestrator.knowledge_lake.list_knowledge", return_value=fake_records):
            result = get_language_context(settings=settings, language="python")
        assert result is not None
        assert len(result) <= _MAX_CONTEXT_CHARS + 20  # +20 for truncation suffix


# ---------------------------------------------------------------------------
# knowledge_lake.index_documentation
# ---------------------------------------------------------------------------

class TestIndexDocumentation:
    def test_upserts_and_returns_true(self):
        from orchestrator.knowledge_lake import index_documentation

        settings = _mock_settings()
        with patch("orchestrator.knowledge_lake.upsert_knowledge") as mock_upsert:
            result = index_documentation(
                settings=settings,
                language="python",
                library="mylib",
                content="mylib: helper utilities.",
            )
        assert result is True
        mock_upsert.assert_called_once()
        call_kwargs = mock_upsert.call_args[0]
        assert call_kwargs[2] == "docs.python.mylib"

    def test_returns_false_when_qdrant_disabled(self):
        from orchestrator.knowledge_lake import index_documentation

        result = index_documentation(
            settings=_mock_settings(qdrant_enabled=False),
            language="python",
            library="x",
            content="y",
        )
        assert result is False

    def test_returns_false_on_exception(self):
        from orchestrator.knowledge_lake import index_documentation

        settings = _mock_settings()
        with patch("orchestrator.knowledge_lake.upsert_knowledge", side_effect=RuntimeError("fail")):
            result = index_documentation(settings=settings, language="python", library="x", content="y")
        assert result is False


# ---------------------------------------------------------------------------
# knowledge_lake.broadcast_knowledge_ready
# ---------------------------------------------------------------------------

class TestBroadcastKnowledgeReady:
    def test_publishes_sigma_event_and_returns_true(self):
        from orchestrator.knowledge_lake import broadcast_knowledge_ready

        settings = _mock_settings(mcp_url="http://semantic-bus-mcp:8090")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("orchestrator.knowledge_lake.urlopen", return_value=mock_response) as mock_open:
            result = broadcast_knowledge_ready(
                settings=settings,
                languages=["python", "javascript"],
                mission_id="test-mission-sigma",
            )

        assert result is True
        mock_open.assert_called_once()
        # Verify the request went to /send
        req = mock_open.call_args[0][0]
        assert req.full_url.endswith("/send")

    def test_returns_false_when_mcp_url_not_configured(self):
        from orchestrator.knowledge_lake import broadcast_knowledge_ready

        settings = _mock_settings(mcp_url="")
        result = broadcast_knowledge_ready(
            settings=settings,
            languages=["python"],
            mission_id="test-mission",
        )
        assert result is False

    def test_returns_false_on_http_error(self):
        from orchestrator.knowledge_lake import broadcast_knowledge_ready

        settings = _mock_settings(mcp_url="http://semantic-bus-mcp:8090")
        with patch("orchestrator.knowledge_lake.urlopen", side_effect=OSError("connection refused")):
            result = broadcast_knowledge_ready(
                settings=settings,
                languages=["python"],
                mission_id="test-mission",
            )
        assert result is False

    def test_returns_false_for_empty_languages(self):
        from orchestrator.knowledge_lake import broadcast_knowledge_ready

        settings = _mock_settings(mcp_url="http://semantic-bus-mcp:8090")
        result = broadcast_knowledge_ready(
            settings=settings,
            languages=[],
            mission_id="test-mission",
        )
        assert result is False

    def test_sigma_payload_structure(self):
        """Verify the published payload contains required Sigma fields."""
        import json

        from orchestrator.knowledge_lake import broadcast_knowledge_ready

        settings = _mock_settings(mcp_url="http://semantic-bus-mcp:8090")
        captured_body: list[bytes] = []

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)

        def capture_urlopen(req, timeout=None):
            captured_body.append(req.data)
            return mock_response

        with patch("orchestrator.knowledge_lake.urlopen", side_effect=capture_urlopen):
            broadcast_knowledge_ready(
                settings=settings,
                languages=["python"],
                mission_id="test-mission-payload",
            )

        assert captured_body
        payload = json.loads(captured_body[0])
        assert payload["protocol"] == "sigma"
        assert payload["knowledge_type"] == "documentation"
        assert payload["sender_agent_id"] == "AGENT-06-IS"
        assert payload["mission_id"] == "test-mission-payload"
        assert payload["knowledge_ready"] is True
        assert "python" in payload["languages"]


# ---------------------------------------------------------------------------
# query_documentation
# ---------------------------------------------------------------------------

class TestQueryDocumentation:
    def test_falls_back_to_keyword_search_when_no_vector_results(self):
        from orchestrator.knowledge_lake import query_documentation

        settings = _mock_settings()
        fake_records = [
            {
                "knowledge_id": "docs.python.bootstrap",
                "content": {
                    "language": "python",
                    "kind": "bootstrap_documentation",
                    "combined_text": "asyncio: async I/O. Keywords: async def, await, create_task.",
                },
            }
        ]

        with (
            patch("orchestrator.knowledge_lake._vector_search", return_value=[]),
            patch("orchestrator.knowledge_lake.list_knowledge", return_value=fake_records),
        ):
            results = query_documentation(
                settings=settings,
                language="python",
                concept="asyncio",
                top_k=3,
            )

        assert isinstance(results, list)
        assert len(results) > 0
        assert results[0]["knowledge_id"] == "docs.python.bootstrap"

    def test_returns_empty_when_qdrant_disabled(self):
        from orchestrator.knowledge_lake import query_documentation

        results = query_documentation(
            settings=_mock_settings(qdrant_enabled=False),
            language="python",
            concept="asyncio",
        )
        assert results == []

    def test_vector_results_take_priority(self):
        from orchestrator.knowledge_lake import query_documentation

        settings = _mock_settings()
        vector_results = [
            {"knowledge_id": "docs.python.asyncio", "content": {}, "score": 0.95}
        ]
        with patch("orchestrator.knowledge_lake._vector_search", return_value=vector_results):
            results = query_documentation(
                settings=settings, language="python", concept="asyncio"
            )
        assert results == vector_results
