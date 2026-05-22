from __future__ import annotations

import hashlib
import json
from typing import Any

from .knowledge_embeddings import payload_embedding_metadata, vector_for_content
from .settings import Settings

try:
    from pymilvus import MilvusClient
except Exception:  # pragma: no cover - exercised in environments without pymilvus installed.
    MilvusClient = None

_COLLECTION_CACHE: set[str] = set()
_CLIENT_CACHE: dict[str, Any] = {}


def _cache_key(settings: Settings) -> str:
    return (
        f"{settings.milvus_uri.rstrip('/')}:"
        f"{settings.milvus_collection}:"
        f"{settings.milvus_vector_size}"
    )


def _client(settings: Settings) -> Any:
    if MilvusClient is None:
        raise RuntimeError("pymilvus dependency is not installed")

    cache_key = _cache_key(settings)
    client = _CLIENT_CACHE.get(cache_key)
    if client is not None:
        return client

    kwargs: dict[str, Any] = {"uri": settings.milvus_uri}
    if settings.milvus_token:
        kwargs["token"] = settings.milvus_token
    if settings.milvus_timeout_seconds > 0:
        kwargs["timeout"] = settings.milvus_timeout_seconds
    client = MilvusClient(**kwargs)
    _CLIENT_CACHE[cache_key] = client
    return client


def _vector_for_content(
    settings: Settings,
    mission_id: str,
    knowledge_id: str,
    content: dict[str, Any],
) -> list[float]:
    return vector_for_content(
        settings,
        mission_id=mission_id,
        knowledge_id=knowledge_id,
        content=content,
        vector_size=settings.milvus_vector_size,
    )


def _point_id(mission_id: str, knowledge_id: str) -> int:
    digest = hashlib.sha256(f"{mission_id}:{knowledge_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _escape_filter_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _payload_to_record(payload: dict[str, Any]) -> dict[str, Any]:
    content = payload.get("content")
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            content_dict = parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            content_dict = {}
    elif isinstance(content, dict):
        content_dict = content
    else:
        content_dict = {}

    return {
        "mission_id": str(payload.get("mission_id", "")),
        "knowledge_id": str(payload.get("knowledge_id", "")),
        "content": content_dict,
        "created_at": str(payload.get("created_at", "")),
    }


def ensure_collection(settings: Settings) -> None:
    if not settings.milvus_enabled:
        return

    cache_key = _cache_key(settings)
    if cache_key in _COLLECTION_CACHE:
        return

    client = _client(settings)
    if not client.has_collection(collection_name=settings.milvus_collection):
        client.create_collection(
            collection_name=settings.milvus_collection,
            dimension=settings.milvus_vector_size,
            metric_type="COSINE",
            consistency_level="Strong",
        )
    _COLLECTION_CACHE.add(cache_key)


def milvus_ready(settings: Settings) -> bool:
    if not settings.milvus_enabled:
        return False
    try:
        ensure_collection(settings)
    except Exception:
        return False
    return True


def upsert_knowledge(
    settings: Settings,
    mission_id: str,
    knowledge_id: str,
    content: dict[str, Any],
    created_at: str,
) -> None:
    ensure_collection(settings)
    client = _client(settings)
    client.upsert(
        collection_name=settings.milvus_collection,
        data=[
            {
                "id": _point_id(mission_id, knowledge_id),
                "vector": _vector_for_content(settings, mission_id, knowledge_id, content),
                "mission_id": mission_id,
                "knowledge_id": knowledge_id,
                "content": json.dumps(content, sort_keys=True),
                "created_at": created_at,
                **payload_embedding_metadata(settings, vector_size=settings.milvus_vector_size),
            }
        ],
    )


def list_knowledge(settings: Settings, mission_id: str, limit: int) -> list[dict[str, Any]]:
    ensure_collection(settings)
    client = _client(settings)
    query_limit = max(1, min(limit, 500))
    rows = client.query(
        collection_name=settings.milvus_collection,
        filter=f'mission_id == "{_escape_filter_value(mission_id)}"',
        output_fields=["mission_id", "knowledge_id", "content", "created_at"],
        limit=query_limit,
    )

    records: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        record = _payload_to_record(row)
        if not record["mission_id"]:
            record["mission_id"] = mission_id
        records.append(record)

    records.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return records[:query_limit]
