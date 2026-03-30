from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .settings import Settings

_COLLECTION_CACHE: set[str] = set()


def _cache_key(settings: Settings) -> str:
    return (
        f"{settings.qdrant_url.rstrip('/')}:"
        f"{settings.qdrant_collection}:"
        f"{settings.qdrant_vector_size}"
    )


def _request_json(
    settings: Settings,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = _validated_http_url(settings.qdrant_url, path, service="qdrant")
    body: bytes | None = None
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    request = Request(url, data=body, method=method, headers=headers)
    with urlopen(request, timeout=settings.qdrant_timeout_seconds) as response:  # nosec B310
        raw = response.read().decode("utf-8")
    if not raw:
        return {}
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def _validated_http_url(base_url: str, path: str, *, service: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{service} url must use http or https")
    if not path.startswith("/"):
        raise ValueError("request path must start with '/'")
    return f"{base_url.rstrip('/')}{path}"


def _vector_for_content(
    settings: Settings,
    mission_id: str,
    knowledge_id: str,
    content: dict[str, Any],
) -> list[float]:
    seed = (
        f"{mission_id}:{knowledge_id}:"
        f"{json.dumps(content, sort_keys=True, separators=(',', ':'))}"
    ).encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    vector: list[float] = []
    while len(vector) < settings.qdrant_vector_size:
        for byte in digest:
            vector.append((byte / 255.0) * 2.0 - 1.0)
            if len(vector) >= settings.qdrant_vector_size:
                break
        digest = hashlib.sha256(digest).digest()
    return vector


def _point_payload_to_record(payload: dict[str, Any]) -> dict[str, Any]:
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
    if not settings.qdrant_enabled:
        return

    cache_key = _cache_key(settings)
    if cache_key in _COLLECTION_CACHE:
        return

    path = f"/collections/{settings.qdrant_collection}"
    try:
        _request_json(settings, "GET", path)
    except Exception:
        _request_json(
            settings,
            "PUT",
            path,
            payload={"vectors": {"size": settings.qdrant_vector_size, "distance": "Cosine"}},
        )

    _COLLECTION_CACHE.add(cache_key)


def qdrant_ready(settings: Settings) -> bool:
    if not settings.qdrant_enabled:
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

    point_id = f"{mission_id}:{knowledge_id}"
    vector = _vector_for_content(settings, mission_id, knowledge_id, content)
    payload = {
        "mission_id": mission_id,
        "knowledge_id": knowledge_id,
        "content": content,
        "created_at": created_at,
    }
    _request_json(
        settings,
        "PUT",
        f"/collections/{settings.qdrant_collection}/points?wait=true",
        payload={
            "points": [
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": payload,
                }
            ]
        },
    )


def list_knowledge(settings: Settings, mission_id: str, limit: int) -> list[dict[str, Any]]:
    ensure_collection(settings)

    query_limit = max(1, min(limit, 500))
    response = _request_json(
        settings,
        "POST",
        f"/collections/{settings.qdrant_collection}/points/scroll",
        payload={
            "filter": {"must": [{"key": "mission_id", "match": {"value": mission_id}}]},
            "limit": query_limit,
            "with_payload": True,
            "with_vector": False,
        },
    )
    result = response.get("result", {})
    points = result.get("points", []) if isinstance(result, dict) else []

    records: list[dict[str, Any]] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        payload = point.get("payload", {})
        if not isinstance(payload, dict):
            continue
        record = _point_payload_to_record(payload)
        if not record["mission_id"]:
            record["mission_id"] = mission_id
        if not record["knowledge_id"]:
            record["knowledge_id"] = str(point.get("id", ""))
        records.append(record)

    records.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return records[:query_limit]
