"""knowledge_lake.py — PostgreSQL-backed query layer for the Knowledge Lake.

PostgreSQL (``mission_knowledge`` table) is the single source of truth: the IS
Agent writes bootstrap/attachment docs there via ``storage.upsert_knowledge``,
and the query functions in this module read them back via
``storage.list_knowledge``.  This closes the historical write/read split where
IS-Agent wrote to PostgreSQL but the query layer read from Qdrant (a separate,
never-synced store).

Qdrant is reserved for semantic similarity search: when a real embedding is
available (``KNOWLEDGE_EMBEDDING_PROVIDER`` set to ``gemini`` or ``openai``)
``index_documentation`` ALSO writes to Qdrant so vector search can be layered
on later.  When no provider is configured, PostgreSQL keyword search is the
only retrieval path.

- ``query_documentation`` — keyword search over indexed docs (PostgreSQL),
  with optional Qdrant vector pre-search when embeddings are configured
- ``is_stocked``          — check whether a mission has knowledge entries
- ``index_documentation`` — upsert a documentation chunk (PostgreSQL + Qdrant)
- ``get_language_context`` — merged text for prompt injection (PostgreSQL)
- ``embed_text``          — configurable real-embedding helper

All functions are safe to call when storage is unavailable — they return
empty/False results and log a warning rather than raising.
"""
from __future__ import annotations

import logging
import os
from typing import Any
from urllib.request import urlopen  # noqa: S310 — patched in tests; only http/https used

# PostgreSQL is the source of truth for knowledge reads/writes. ``list_knowledge``
# and ``upsert_knowledge`` are re-exported into this module's namespace so the
# query functions below resolve them as module globals (tests patch them here).
from .storage import list_knowledge, upsert_knowledge

LOGGER = logging.getLogger(__name__)

# Sentinel mission_id used for global Knowledge Lake entries (shared across missions)
_KNOWLEDGE_LAKE_ID = "__knowledge_lake__"

# Maximum characters returned by get_language_context to avoid bloating prompts
_MAX_CONTEXT_CHARS = 8_000


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_stocked(
    *,
    settings: Any,
    mission_id: str | None = None,
    language: str | None = None,
) -> bool:
    """Return True if the Knowledge Lake has entries for the given scope.

    Reads from PostgreSQL (``mission_knowledge``).  When *language* is provided,
    checks the global lake for that language's bootstrap doc.  When only
    *mission_id* is provided, checks whether the mission has any knowledge rows.
    """
    scope_id = _KNOWLEDGE_LAKE_ID if language else (mission_id or _KNOWLEDGE_LAKE_ID)
    try:
        records = list_knowledge(settings, scope_id, limit=50)
    except Exception as exc:
        LOGGER.warning(
            "knowledge_lake.is_stocked error for mission=%s language=%s: %s",
            mission_id, language, exc,
        )
        return False

    if language:
        knowledge_id = f"docs.{language.strip().lower()}.bootstrap"
        return any(
            isinstance(r, dict) and r.get("knowledge_id") == knowledge_id
            for r in records
        )
    return any(isinstance(r, dict) for r in records)


def query_documentation(
    *,
    settings: Any,
    language: str,
    concept: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Semantic search over Knowledge Lake docs for *language* and *concept*.

    Returns a list of matching records ordered by relevance (descending).
    Each record: ``{"knowledge_id": str, "content": dict, "score": float}``.

    Falls back to a PostgreSQL keyword filter when Qdrant vector search is
    unavailable or returns no results.
    """
    language_key = language.strip().lower()
    concept_key = concept.strip().lower()

    # Attempt vector similarity search first, but only when a real embedding
    # provider is configured AND Qdrant is enabled — otherwise the vectors are
    # deterministic hashes and similarity is meaningless, so skip straight to
    # PostgreSQL keyword search.
    if _semantic_search_enabled(settings):
        results = _vector_search(
            settings=settings,
            language_key=language_key,
            concept_key=concept_key,
            top_k=top_k,
        )
        if results:
            return results

    # PostgreSQL keyword search over the global knowledge lake.
    return _keyword_search(
        settings=settings,
        language_key=language_key,
        concept_key=concept_key,
        top_k=top_k,
    )


def index_documentation(
    *,
    settings: Any,
    language: str,
    library: str,
    content: str,
) -> bool:
    """Upsert a documentation chunk into the Knowledge Lake.

    PostgreSQL is the source of truth, so the chunk is always written there.
    When a real embedding provider is configured AND Qdrant is enabled, the
    same chunk is also mirrored to Qdrant for semantic similarity search.

    Returns True when the PostgreSQL write succeeds, False on failure. The
    Qdrant mirror is best-effort and never fails the call.
    """
    language_key = language.strip().lower()
    library_key = library.strip().lower().replace(" ", "_")
    knowledge_id = f"docs.{language_key}.{library_key}"

    import hashlib
    from datetime import UTC, datetime

    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    payload = {
        "language": language_key,
        "library": library_key,
        "kind": "documentation",
        "combined_text": content,
        "hash": content_hash,
    }
    created_at = datetime.now(UTC).isoformat()
    try:
        upsert_knowledge(
            settings,
            _KNOWLEDGE_LAKE_ID,
            knowledge_id,
            payload,
            created_at,
        )
        LOGGER.debug("knowledge_lake.index_documentation: upserted %s", knowledge_id)
    except Exception as exc:
        LOGGER.warning(
            "knowledge_lake.index_documentation failed for %s/%s: %s",
            language, library, exc,
        )
        return False

    _mirror_to_qdrant(
        settings=settings,
        knowledge_id=knowledge_id,
        payload=payload,
        created_at=created_at,
    )
    return True


def get_language_context(*, settings: Any, language: str) -> str | None:
    """Return merged documentation text for *language* suitable for prompt injection.

    Queries the global Knowledge Lake (PostgreSQL ``mission_knowledge``) for
    bootstrap docs of the target language and returns a truncated string.
    Returns None when nothing is indexed or storage is unavailable.
    """
    language_key = language.strip().lower()
    knowledge_id = f"docs.{language_key}.bootstrap"

    try:
        records = list_knowledge(settings, _KNOWLEDGE_LAKE_ID, limit=10)
    except Exception as exc:
        LOGGER.warning("knowledge_lake.get_language_context list error: %s", exc)
        return None

    parts: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("knowledge_id") != knowledge_id:
            continue
        content = record.get("content")
        if not isinstance(content, dict):
            continue
        text = str(content.get("combined_text") or "").strip()
        if text:
            parts.append(text)

    if not parts:
        return None

    merged = "\n\n".join(parts)
    if len(merged) > _MAX_CONTEXT_CHARS:
        merged = merged[:_MAX_CONTEXT_CHARS] + "\n...[truncated]"
    return merged


# Agent identity used when the IS-Agent broadcasts on the Sigma lane. Must match
# the Protocol Bus AGENT_ID_PATTERN (^AGENT-\d{2}-[A-Z0-9-]+$) and is echoed in
# the X-Agent-Id header, which the bus requires to equal the envelope sender.
_IS_AGENT_ID = "AGENT-06-IS"


def broadcast_knowledge_ready(
    *,
    settings: Any,
    languages: list[str],
    mission_id: str,
) -> bool:
    """Publish a Protocol Sigma knowledge_ready event to the Protocol Bus.

    Sends a schema-valid ``SendMessageRequest`` whose ``payload`` conforms to the
    bus ``SigmaPayload`` model (``schema_version``/``knowledge_type``/
    ``embedding_ref``/``relevance_scope``/``content``). The IS-Agent broadcasts on
    the ``protocol:sigma:broadcast`` lane so any subscriber (e.g. the orchestrator
    Sigma consumer) can react to freshly-stocked knowledge.

    Returns True if the event was accepted (HTTP < 300).  The mission proceeds
    regardless — this is fire-and-forget telemetry.
    """
    if not languages:
        return False

    bus_url = _protocol_bus_url(settings)
    if not bus_url:
        LOGGER.debug(
            "knowledge_lake.broadcast_knowledge_ready: Protocol Bus URL not configured, skipping"
        )
        return False

    import json
    import uuid
    from datetime import UTC, datetime
    from urllib.request import Request

    ordered_languages = sorted(languages)
    sigma_payload = {
        "schema_version": "v1",
        "knowledge_type": "documentation",
        # embedding_ref is reserved for future semantic routing; today it carries
        # the global Knowledge Lake scope id so consumers can locate the source.
        "embedding_ref": _KNOWLEDGE_LAKE_ID,
        "relevance_scope": f"mission:{mission_id}",
        "content": {
            "mission_id": mission_id,
            "languages": ordered_languages,
            "knowledge_ready": True,
            "vector_store_ref": _KNOWLEDGE_LAKE_ID,
            "content_summary": (
                f"Bootstrap docs indexed for: {', '.join(ordered_languages)}"
            ),
            "indexed_at": datetime.now(UTC).isoformat(),
        },
    }
    request_body = {
        "schema_version": "v1",
        "protocol": "sigma",
        "sender": _IS_AGENT_ID,
        "recipient": "broadcast",
        "correlation_id": f"sigma-{mission_id}-{uuid.uuid4()}",
        "priority": "normal",
        "payload": sigma_payload,
    }

    try:
        body = json.dumps(request_body, separators=(",", ":")).encode("utf-8")
        req = Request(
            f"{bus_url.rstrip('/')}/send",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": _protocol_bus_api_key(settings),
                "X-Agent-Id": _IS_AGENT_ID,
            },
        )
        with urlopen(req, timeout=5.0) as resp:  # nosec B310
            status = resp.status
        if status < 300:
            LOGGER.info(
                "knowledge_lake: Sigma knowledge_ready published for mission %s languages=%s",
                mission_id, ordered_languages,
            )
            return True
        LOGGER.warning(
            "knowledge_lake: Sigma publish returned HTTP %s for mission %s",
            status, mission_id,
        )
        return False
    except Exception as exc:
        LOGGER.warning(
            "knowledge_lake: Sigma publish failed for mission %s: %s",
            mission_id, exc,
        )
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _qdrant_enabled(settings: Any) -> bool:
    return bool(getattr(settings, "qdrant_enabled", False))


def _embedding_provider(settings: Any) -> str:
    """Return the configured embedding provider, normalized to lower-case.

    ``none`` and the legacy ``deterministic`` value both mean "no real
    embeddings" — only ``gemini`` / ``openai`` produce semantically meaningful
    vectors worth indexing in Qdrant.
    """
    provider = str(
        getattr(settings, "knowledge_embedding_provider", "none") or "none"
    ).strip().lower()
    return provider


def _embedding_key_available(settings: Any) -> bool:
    """Return True when a non-empty API key exists for the configured provider."""
    dedicated = str(getattr(settings, "knowledge_embedding_api_key", "") or "").strip()
    if dedicated:
        return True
    provider = _embedding_provider(settings)
    if provider == "gemini":
        return bool(os.getenv("GEMINI_API_KEY", "").strip())
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY", "").strip())
    return False


def _semantic_search_enabled(settings: Any) -> bool:
    """True only when a real embedding provider, Qdrant, and a valid API key are all available."""
    return (
        _qdrant_enabled(settings)
        and _embedding_provider(settings) in {"gemini", "openai"}
        and _embedding_key_available(settings)
    )


async def embed_text(text: str, settings: Any) -> list[float] | None:
    """Return a real embedding vector for *text*, or None when unavailable.

    Provider is selected by ``KNOWLEDGE_EMBEDDING_PROVIDER``:

    - ``gemini`` → Gemini embedding API
    - ``openai`` → OpenAI embedding API
    - ``none`` / ``deterministic`` (default) → returns None (Qdrant indexing is
      skipped and callers fall back to PostgreSQL keyword search)

    Network calls are delegated to ``knowledge_embeddings`` and run in a thread
    so this coroutine never blocks the event loop. Returns None on any failure.
    """
    provider = _embedding_provider(settings)
    if provider not in {"gemini", "openai"}:
        return None

    cleaned = str(text or "").strip()
    if not cleaned:
        return None

    vector_size = int(getattr(settings, "qdrant_vector_size", 64) or 64)
    try:
        import asyncio

        from .knowledge_embeddings import _gemini_embedding, _openai_embedding

        embed_fn = _gemini_embedding if provider == "gemini" else _openai_embedding
        vector = await asyncio.to_thread(
            embed_fn, settings, text=cleaned, dimensions=vector_size
        )
        return vector or None
    except Exception as exc:
        LOGGER.warning("knowledge_lake.embed_text (%s) failed: %s", provider, exc)
        return None


def _mirror_to_qdrant(
    *,
    settings: Any,
    knowledge_id: str,
    payload: dict[str, Any],
    created_at: str,
) -> None:
    """Best-effort mirror of a knowledge chunk to Qdrant for semantic search.

    Only runs when a real embedding provider is configured and Qdrant is
    enabled. Never raises — Qdrant is a secondary index, not the source of
    truth, so a mirror failure must not fail the PostgreSQL write.
    """
    if not _semantic_search_enabled(settings):
        return
    try:
        from .qdrant_store import upsert_knowledge as qdrant_upsert

        qdrant_upsert(settings, _KNOWLEDGE_LAKE_ID, knowledge_id, payload, created_at)
        LOGGER.debug("knowledge_lake: mirrored %s to Qdrant", knowledge_id)
    except Exception as exc:
        LOGGER.warning("knowledge_lake: Qdrant mirror failed for %s: %s", knowledge_id, exc)


def _protocol_bus_url(settings: Any) -> str | None:
    """Resolve the Protocol Bus base URL.

    Prefers ``protocol_bus_url`` and falls back to the legacy ``mcp_url`` attr so
    callers and tests that still set the old name keep working.
    """
    url = str(
        getattr(settings, "protocol_bus_url", "")
        or getattr(settings, "mcp_url", "")
        or ""
    ).strip()
    return url or None


def _protocol_bus_api_key(settings: Any) -> str:
    """Resolve the Protocol Bus shared API key (``protocol_bus_api_key``).

    Falls back to the legacy ``mcp_api_key`` attr for backward compatibility.
    """
    return str(
        getattr(settings, "protocol_bus_api_key", "")
        or getattr(settings, "mcp_api_key", "")
        or ""
    )


def _vector_search(
    *,
    settings: Any,
    language_key: str,
    concept_key: str,
    top_k: int,
) -> list[dict[str, Any]]:
    """Query Qdrant /query endpoint with a deterministic concept vector."""
    try:
        from .knowledge_embeddings import vector_for_content
        from .qdrant_store import _request_json, ensure_collection

        ensure_collection(settings)
        query_vector = vector_for_content(
            settings,
            mission_id=_KNOWLEDGE_LAKE_ID,
            knowledge_id=f"query.{language_key}.{concept_key}",
            content={"language": language_key, "concept": concept_key},
            vector_size=settings.qdrant_vector_size,
        )
        response = _request_json(
            settings,
            "POST",
            f"/collections/{settings.qdrant_collection}/points/search",
            payload={
                "vector": query_vector,
                "limit": top_k,
                "with_payload": True,
                "filter": {
                    "must": [
                        {"key": "mission_id", "match": {"value": _KNOWLEDGE_LAKE_ID}},
                        {"key": "content.language", "match": {"value": language_key}},
                    ]
                },
            },
        )
        results = response.get("result", [])
        if not isinstance(results, list) or not results:
            return []

        output: list[dict[str, Any]] = []
        for hit in results:
            if not isinstance(hit, dict):
                continue
            payload = hit.get("payload") or {}
            content = payload.get("content") or {}
            if isinstance(content, str):
                import json as _json
                try:
                    content = _json.loads(content)
                except Exception:
                    content = {}
            output.append({
                "knowledge_id": str(payload.get("knowledge_id", "")),
                "content": content,
                "score": float(hit.get("score", 0.0)),
            })
        return output

    except Exception as exc:
        LOGGER.debug("knowledge_lake._vector_search error: %s", exc)
        return []


def _keyword_search(
    *,
    settings: Any,
    language_key: str,
    concept_key: str,
    top_k: int,
) -> list[dict[str, Any]]:
    """Scroll-based keyword overlap fallback when vector search yields nothing."""
    try:
        records = list_knowledge(settings, _KNOWLEDGE_LAKE_ID, limit=200)
    except Exception as exc:
        LOGGER.debug("knowledge_lake._keyword_search list error: %s", exc)
        return []

    import re as _re
    _tok = _re.compile(r"\w+")

    scored: list[tuple[float, dict[str, Any]]] = []
    concept_tokens = set(_tok.findall(concept_key.lower()))

    for record in records:
        if not isinstance(record, dict):
            continue
        content = record.get("content") or {}
        if not isinstance(content, dict):
            continue
        if str(content.get("language") or "").lower() != language_key:
            continue

        combined_text = str(content.get("combined_text") or "").lower()
        knowledge_id = str(record.get("knowledge_id") or "").lower()
        text_tokens = set(_tok.findall(combined_text))
        overlap = len(concept_tokens & text_tokens)
        id_overlap = len(concept_tokens & set(_tok.findall(knowledge_id)))
        score = (overlap + id_overlap * 2) / max(len(concept_tokens), 1)

        if score > 0:
            scored.append((score, {
                "knowledge_id": record.get("knowledge_id", ""),
                "content": content,
                "score": round(score, 4),
            }))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:top_k]]
