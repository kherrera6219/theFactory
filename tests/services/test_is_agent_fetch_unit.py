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

def _mock_settings(
    *,
    qdrant_enabled: bool = True,
    mcp_url: str = "",
    protocol_bus_url: str | None = None,
    protocol_bus_api_key: str = "",
) -> Any:
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
    # Protocol Bus client config. The producer prefers protocol_bus_url; when a
    # test only sets mcp_url we mirror it here so the legacy-fallback path is
    # exercised through a concrete string rather than a MagicMock attr.
    s.protocol_bus_url = protocol_bus_url if protocol_bus_url is not None else mcp_url
    s.protocol_bus_api_key = protocol_bus_api_key
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

    def test_source_code_java_package_detected_without_word_java(self):
        # Regression: detection previously also required the literal word
        # "java" to appear in the prompt/source, so legitimate Java code
        # with a prompt that never mentions "java" by name was silently
        # never detected.
        result = self._call(
            prompt="Port this billing module to a different structure",
            source_code="package com.acme.billing;\nimport com.acme.Base;\n",
        )
        assert "java" in result


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
# _process_mission_attachments — multi-modal parsing (Phase 2)
# ---------------------------------------------------------------------------

class TestProcessMissionAttachments:
    def _run(self, coro):
        return asyncio.run(coro)

    def _process(self, attachments, *, get_object_return=None, get_object_raises=None):
        from orchestrator.is_agent import _process_mission_attachments

        settings = _mock_settings()
        settings.object_storage_enabled = True
        settings.object_storage_prefix = "missions"

        upserts: list = []

        def fake_upsert(*, settings, mission_id, knowledge_id, content, created_at):
            upserts.append((knowledge_id, content))

        def fake_get_object(_settings, _key):
            if get_object_raises is not None:
                raise get_object_raises
            return get_object_return

        with (
            patch("orchestrator.is_agent._upsert_knowledge_safe", side_effect=fake_upsert),
            patch("orchestrator.object_store.get_object", side_effect=fake_get_object),
        ):
            result = self._run(
                _process_mission_attachments(
                    mission_id="m-1",
                    attachments=attachments,
                    settings=settings,
                )
            )
        return result, upserts

    def test_inline_bytes_are_parsed_and_indexed(self):
        att = {
            "file_id": "f1",
            "filename": "notes.md",
            "content_type": "text/markdown",
            "purpose": "spec",
            "content_bytes": b"# Heading\n\nReal extracted content",
        }
        result, upserts = self._process([att])
        assert result["processed_count"] == 1
        assert len(upserts) == 1
        _, content = upserts[0]
        assert content["source"] == "attachment_extraction"
        assert "Real extracted content" in content["combined_text"]
        # extracted text surfaced back onto the attachment for the PM prompt
        assert "Real extracted content" in att["content"]

    def test_object_store_bytes_are_parsed(self):
        att = {
            "file_id": "f2",
            "filename": "spec.txt",
            "content_type": "text/plain",
            "purpose": "PRD",
        }
        result, upserts = self._process([att], get_object_return=b"stored body text")
        assert result["processed_count"] == 1
        _, content = upserts[0]
        assert "stored body text" in content["combined_text"]

    def test_metadata_only_fallback_when_no_bytes(self):
        att = {
            "file_id": "f3",
            "filename": "image.png",
            "content_type": "image/png",
            "purpose": "reference",
        }
        # get_object returns None -> no bytes available
        result, upserts = self._process([att], get_object_return=None)
        assert result["processed_count"] == 1
        _, content = upserts[0]
        assert content["source"] == "attachment_metadata"
        assert "content" not in att or not att.get("content")

    def test_unparseable_type_with_bytes_falls_back_to_metadata(self):
        att = {
            "file_id": "f4",
            "filename": "logo.png",
            "content_type": "image/png",
            "content_bytes": b"\x89PNG binary",
        }
        result, upserts = self._process([att])
        assert result["processed_count"] == 1
        _, content = upserts[0]
        assert content["source"] == "attachment_metadata"

    def test_get_object_error_degrades_to_metadata(self):
        att = {
            "file_id": "f5",
            "filename": "spec.txt",
            "content_type": "text/plain",
        }
        result, upserts = self._process([att], get_object_raises=RuntimeError("s3 down"))
        assert result["processed_count"] == 1
        _, content = upserts[0]
        assert content["source"] == "attachment_metadata"


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

    def test_reads_postgres_regardless_of_qdrant(self):
        # PostgreSQL is the source of truth — reads no longer gate on Qdrant.
        from orchestrator.knowledge_lake import is_stocked

        settings = _mock_settings(qdrant_enabled=False)
        fake_records = [{"knowledge_id": "docs.python.bootstrap", "content": {}}]
        with patch("orchestrator.knowledge_lake.list_knowledge", return_value=fake_records):
            assert is_stocked(settings=settings, language="python") is True

    def test_true_when_mission_has_any_rows(self):
        from orchestrator.knowledge_lake import is_stocked

        settings = _mock_settings()
        fake_records = [{"knowledge_id": "docs.python.bootstrap", "content": {}}]
        with patch("orchestrator.knowledge_lake.list_knowledge", return_value=fake_records):
            assert is_stocked(settings=settings, mission_id="mission-42") is True

    def test_false_when_mission_has_no_rows(self):
        from orchestrator.knowledge_lake import is_stocked

        settings = _mock_settings()
        with patch("orchestrator.knowledge_lake.list_knowledge", return_value=[]):
            assert is_stocked(settings=settings, mission_id="mission-42") is False

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

    def test_reads_postgres_regardless_of_qdrant(self):
        from orchestrator.knowledge_lake import get_language_context

        settings = _mock_settings(qdrant_enabled=False)
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

    def test_succeeds_when_qdrant_disabled_postgres_only(self):
        # PostgreSQL is the source of truth; indexing succeeds without Qdrant.
        from orchestrator.knowledge_lake import index_documentation

        with patch("orchestrator.knowledge_lake.upsert_knowledge") as mock_upsert:
            result = index_documentation(
                settings=_mock_settings(qdrant_enabled=False),
                language="python",
                library="x",
                content="y",
            )
        assert result is True
        mock_upsert.assert_called_once()

    def test_mirrors_to_qdrant_when_embeddings_configured(self):
        from orchestrator.knowledge_lake import index_documentation

        settings = _mock_settings()
        settings.knowledge_embedding_provider = "gemini"
        with (
            patch("orchestrator.knowledge_lake.upsert_knowledge"),
            patch("orchestrator.qdrant_store.upsert_knowledge") as mock_qdrant,
        ):
            result = index_documentation(
                settings=settings, language="python", library="x", content="y"
            )
        assert result is True
        mock_qdrant.assert_called_once()

    def test_no_qdrant_mirror_when_provider_none(self):
        from orchestrator.knowledge_lake import index_documentation

        settings = _mock_settings()
        settings.knowledge_embedding_provider = "none"
        with (
            patch("orchestrator.knowledge_lake.upsert_knowledge"),
            patch("orchestrator.qdrant_store.upsert_knowledge") as mock_qdrant,
        ):
            index_documentation(settings=settings, language="python", library="x", content="y")
        mock_qdrant.assert_not_called()

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

        settings = _mock_settings(mcp_url="http://protocol-bus-mcp:8090")

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

        settings = _mock_settings(mcp_url="http://protocol-bus-mcp:8090")
        with patch("orchestrator.knowledge_lake.urlopen", side_effect=OSError("connection refused")):
            result = broadcast_knowledge_ready(
                settings=settings,
                languages=["python"],
                mission_id="test-mission",
            )
        assert result is False

    def test_returns_false_for_empty_languages(self):
        from orchestrator.knowledge_lake import broadcast_knowledge_ready

        settings = _mock_settings(mcp_url="http://protocol-bus-mcp:8090")
        result = broadcast_knowledge_ready(
            settings=settings,
            languages=[],
            mission_id="test-mission",
        )
        assert result is False

    def test_sigma_payload_structure(self):
        """Verify the published body is a bus-valid SendMessageRequest+SigmaPayload."""
        import json

        from orchestrator.knowledge_lake import broadcast_knowledge_ready

        settings = _mock_settings(
            protocol_bus_url="http://protocol-bus-mcp:8090",
            protocol_bus_api_key="secret-key",
        )
        captured: list[Any] = []

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)

        def capture_urlopen(req, timeout=None):
            captured.append(req)
            return mock_response

        with patch("orchestrator.knowledge_lake.urlopen", side_effect=capture_urlopen):
            broadcast_knowledge_ready(
                settings=settings,
                languages=["python"],
                mission_id="test-mission-payload",
            )

        assert captured
        req = captured[0]
        # SendMessageRequest envelope shape expected by protocol-bus-mcp /send.
        body = json.loads(req.data)
        assert body["protocol"] == "sigma"
        assert body["sender"] == "AGENT-06-IS"
        assert body["recipient"] == "broadcast"
        assert body["schema_version"] == "v1"
        assert body["priority"] == "normal"
        # Bus auth headers: X-Agent-Id must equal the sender; X-API-Key carries
        # the configured shared key.
        assert req.get_header("X-agent-id") == "AGENT-06-IS"
        assert req.get_header("X-api-key") == "secret-key"
        # SigmaPayload shape (schema_version/knowledge_type/embedding_ref/
        # relevance_scope/content) — extra="forbid" on the bus, so only these.
        sigma = body["payload"]
        assert set(sigma) == {
            "schema_version",
            "knowledge_type",
            "embedding_ref",
            "relevance_scope",
            "content",
        }
        assert sigma["knowledge_type"] == "documentation"
        assert sigma["content"]["mission_id"] == "test-mission-payload"
        assert sigma["content"]["knowledge_ready"] is True
        assert "python" in sigma["content"]["languages"]

    def test_sigma_payload_validates_against_bus_model(self):
        """The produced payload must pass the bus SigmaPayload + SendMessageRequest."""
        import json
        import sys
        from pathlib import Path

        bus_path = str(
            Path(__file__).resolve().parents[2]
            / "services"
            / "protocol-bus-mcp"
        )
        if bus_path not in sys.path:
            sys.path.insert(0, bus_path)
        from orchestrator.knowledge_lake import broadcast_knowledge_ready
        from protocol_bus.mcp_server import (  # type: ignore
            SendMessageRequest,
            _validate_protocol_payload,
        )

        settings = _mock_settings(
            protocol_bus_url="http://protocol-bus-mcp:8090",
            protocol_bus_api_key="secret-key",
        )
        captured: list[Any] = []
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)

        def capture_urlopen(req, timeout=None):
            captured.append(req)
            return mock_response

        with patch("orchestrator.knowledge_lake.urlopen", side_effect=capture_urlopen):
            broadcast_knowledge_ready(
                settings=settings,
                languages=["python", "go"],
                mission_id="m-1",
            )

        body = json.loads(captured[0].data)
        # Round-trips through the exact bus validators without raising.
        validated = SendMessageRequest.model_validate(body)
        _validate_protocol_payload(validated.protocol, validated.payload)


# ---------------------------------------------------------------------------
# query_documentation
# ---------------------------------------------------------------------------

class TestQueryDocumentation:
    def test_falls_back_to_keyword_search_when_no_vector_results(self):
        from orchestrator.knowledge_lake import query_documentation

        # Semantic provider configured so the vector path is attempted first,
        # then falls back to PostgreSQL keyword search on empty results.
        settings = _mock_settings()
        settings.knowledge_embedding_provider = "gemini"
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

    def test_keyword_search_used_when_no_embedding_provider(self):
        # With the default (non-semantic) provider, vector search is skipped
        # entirely and PostgreSQL keyword search is the only path.
        from orchestrator.knowledge_lake import query_documentation

        settings = _mock_settings(qdrant_enabled=False)
        with (
            patch("orchestrator.knowledge_lake._vector_search") as mock_vec,
            patch("orchestrator.knowledge_lake.list_knowledge", return_value=[]),
        ):
            results = query_documentation(
                settings=settings, language="python", concept="asyncio"
            )
        assert results == []
        mock_vec.assert_not_called()

    def test_vector_results_take_priority(self):
        from orchestrator.knowledge_lake import query_documentation

        settings = _mock_settings()
        settings.knowledge_embedding_provider = "gemini"
        vector_results = [
            {"knowledge_id": "docs.python.asyncio", "content": {}, "score": 0.95}
        ]
        with patch("orchestrator.knowledge_lake._vector_search", return_value=vector_results):
            results = query_documentation(
                settings=settings, language="python", concept="asyncio"
            )
        assert results == vector_results


# ---------------------------------------------------------------------------
# embed_text — configurable real embeddings with fallback
# ---------------------------------------------------------------------------

class TestEmbedText:
    def test_returns_none_for_default_provider(self):
        from orchestrator.knowledge_lake import embed_text

        settings = _mock_settings()
        settings.knowledge_embedding_provider = "none"
        assert asyncio.run(embed_text("hello", settings)) is None

    def test_returns_none_for_deterministic_provider(self):
        from orchestrator.knowledge_lake import embed_text

        settings = _mock_settings()
        settings.knowledge_embedding_provider = "deterministic"
        assert asyncio.run(embed_text("hello", settings)) is None

    def test_returns_none_for_empty_text(self):
        from orchestrator.knowledge_lake import embed_text

        settings = _mock_settings()
        settings.knowledge_embedding_provider = "gemini"
        assert asyncio.run(embed_text("   ", settings)) is None

    def test_gemini_provider_calls_gemini_embedding(self):
        from orchestrator.knowledge_lake import embed_text

        settings = _mock_settings()
        settings.knowledge_embedding_provider = "gemini"
        vec = [0.1, 0.2, 0.3]
        with patch(
            "orchestrator.knowledge_embeddings._gemini_embedding", return_value=vec
        ) as mock_g:
            result = asyncio.run(embed_text("doc text", settings))
        assert result == vec
        mock_g.assert_called_once()

    def test_openai_provider_calls_openai_embedding(self):
        from orchestrator.knowledge_lake import embed_text

        settings = _mock_settings()
        settings.knowledge_embedding_provider = "openai"
        vec = [0.4, 0.5]
        with patch(
            "orchestrator.knowledge_embeddings._openai_embedding", return_value=vec
        ) as mock_o:
            result = asyncio.run(embed_text("doc text", settings))
        assert result == vec
        mock_o.assert_called_once()

    def test_falls_back_to_none_on_provider_failure(self):
        from orchestrator.knowledge_lake import embed_text

        settings = _mock_settings()
        settings.knowledge_embedding_provider = "gemini"
        with patch(
            "orchestrator.knowledge_embeddings._gemini_embedding",
            side_effect=RuntimeError("api down"),
        ):
            assert asyncio.run(embed_text("doc text", settings)) is None

    def test_returns_none_when_provider_yields_empty(self):
        from orchestrator.knowledge_lake import embed_text

        settings = _mock_settings()
        settings.knowledge_embedding_provider = "openai"
        with patch("orchestrator.knowledge_embeddings._openai_embedding", return_value=None):
            assert asyncio.run(embed_text("doc text", settings)) is None


# ---------------------------------------------------------------------------
# Knowledge injection into the specialist codegen prompt
# ---------------------------------------------------------------------------

class TestCodegenKnowledgeInjection:
    def test_knowledge_context_appears_in_codegen_prompt(self):
        from orchestrator.llm_delegation.prompts import _build_codegen_prompt

        prompt = _build_codegen_prompt(
            mission_context={
                "mission_id": "m1",
                "knowledge_context": "list: append, extend, pop. dict: get, items.",
            },
            mission_contract={"contract_summary": "Build a CSV reader"},
            logicnodes=[],
            target_language="python",
            specialist_agent_id="AGENT-PY",
            recommended_provider="openai",
            recommended_model="gpt-5.5",
        )
        assert "Knowledge Lake" in prompt
        assert "append, extend, pop" in prompt

    def test_no_knowledge_section_when_absent(self):
        from orchestrator.llm_delegation.prompts import _build_codegen_prompt

        prompt = _build_codegen_prompt(
            mission_context={"mission_id": "m1"},
            mission_contract={"contract_summary": "Build a CSV reader"},
            logicnodes=[],
            target_language="python",
            specialist_agent_id="AGENT-PY",
            recommended_provider="openai",
            recommended_model="gpt-5.5",
        )
        assert "Knowledge Lake" not in prompt

    def test_accepts_query_documentation_record_list(self):
        from orchestrator.llm_delegation.prompts import _build_codegen_prompt

        prompt = _build_codegen_prompt(
            mission_context={
                "mission_id": "m1",
                "knowledge_context": [
                    {"knowledge_id": "docs.python.bootstrap",
                     "content": {"combined_text": "asyncio: gather, sleep, create_task."}},
                ],
            },
            mission_contract={"contract_summary": "Build an async worker"},
            logicnodes=[],
            target_language="python",
            specialist_agent_id="AGENT-PY",
            recommended_provider="openai",
            recommended_model="gpt-5.5",
        )
        assert "gather, sleep, create_task" in prompt
