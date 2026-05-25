"""knowledge_lake.py — Qdrant-backed semantic query layer for the Knowledge Lake.

Provides the high-level interface used by the IS Agent and pod workers to
query documentation context from Qdrant.  The low-level Qdrant I/O lives in
``qdrant_store.py``; this module adds:

- ``query_documentation`` — semantic similarity search over indexed docs
- ``is_stocked``          — check whether a language's bootstrap docs exist
- ``index_documentation`` — upsert a documentation chunk with embedding
- ``get_language_context`` — convenience wrapper returning merged text for extraction

All functions are safe to call when Qdrant is unavailable — they return
empty/False results and log a warning rather than raising.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.request import urlopen  # noqa: S310 — patched in tests; only http/https used

from .qdrant_store import list_knowledge, upsert_knowledge

LOGGER = logging.getLogger(__name__)

# Sentinel mission_id used for global Knowledge Lake entries (shared across missions)
_KNOWLEDGE_LAKE_ID = "__knowledge_lake__"

# Maximum characters returned by get_language_context to avoid bloating prompts
_MAX_CONTEXT_CHARS = 8_000


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_stocked(*, settings: Any, language: str) -> bool:
    """Return True if bootstrap documentation for *language* is indexed in Qdrant."""
    if not _qdrant_enabled(settings):
        return False
    knowledge_id = f"docs.{language.strip().lower()}.bootstrap"
    try:
        records = list_knowledge(settings, _KNOWLEDGE_LAKE_ID, limit=50)
        return any(
            isinstance(r, dict) and r.get("knowledge_id") == knowledge_id
            for r in records
        )
    except Exception as exc:
        LOGGER.warning("knowledge_lake.is_stocked error for %s: %s", language, exc)
        return False


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

    Falls back to a scroll-based keyword filter when Qdrant vector search is
    unavailable or returns no results.
    """
    if not _qdrant_enabled(settings):
        return []

    language_key = language.strip().lower()
    concept_key = concept.strip().lower()

    # Attempt vector similarity search first
    results = _vector_search(
        settings=settings,
        language_key=language_key,
        concept_key=concept_key,
        top_k=top_k,
    )
    if results:
        return results

    # Fallback: scroll global knowledge lake and score by keyword overlap
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

    Returns True on success, False on failure.
    """
    if not _qdrant_enabled(settings):
        return False

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
    try:
        upsert_knowledge(
            settings,
            _KNOWLEDGE_LAKE_ID,
            knowledge_id,
            payload,
            datetime.now(UTC).isoformat(),
        )
        LOGGER.debug("knowledge_lake.index_documentation: upserted %s", knowledge_id)
        return True
    except Exception as exc:
        LOGGER.warning(
            "knowledge_lake.index_documentation failed for %s/%s: %s",
            language, library, exc,
        )
        return False


def get_language_context(*, settings: Any, language: str) -> str | None:
    """Return merged documentation text for *language* suitable for prompt injection.

    Queries the global Knowledge Lake for bootstrap docs of the target language
    and returns a truncated string.  Returns None when nothing is indexed or
    Qdrant is unavailable.
    """
    if not _qdrant_enabled(settings):
        return None

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


def broadcast_knowledge_ready(
    *,
    settings: Any,
    languages: list[str],
    mission_id: str,
) -> bool:
    """Publish a Protocol Sigma knowledge_ready event to the semantic bus.

    Returns True if the event was published successfully.  The mission
    proceeds regardless — this is fire-and-forget telemetry.
    """
    if not languages:
        return False

    mcp_url = _mcp_url(settings)
    if not mcp_url:
        LOGGER.debug("knowledge_lake.broadcast_knowledge_ready: MCP URL not configured, skipping")
        return False

    import json
    import uuid
    from datetime import UTC, datetime
    from urllib.request import Request

    payload = {
        "protocol": "sigma",
        "sender_agent_id": "AGENT-06-IS",
        "correlation_id": str(uuid.uuid4()),
        "mission_id": mission_id,
        "knowledge_type": "documentation",
        "content_summary": f"Bootstrap docs indexed for: {', '.join(sorted(languages))}",
        "vector_store_ref": _KNOWLEDGE_LAKE_ID,
        "languages": sorted(languages),
        "knowledge_ready": True,
        "indexed_at": datetime.now(UTC).isoformat(),
    }

    try:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        req = Request(
            f"{mcp_url.rstrip('/')}/send",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": str(getattr(settings, "mcp_api_key", "") or ""),
            },
        )
        with urlopen(req, timeout=5.0) as resp:  # nosec B310
            status = resp.status
        if status < 300:
            LOGGER.info(
                "knowledge_lake: Sigma knowledge_ready published for mission %s languages=%s",
                mission_id, languages,
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


def _mcp_url(settings: Any) -> str | None:
    url = str(getattr(settings, "mcp_url", "") or "").strip()
    return url or None


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
