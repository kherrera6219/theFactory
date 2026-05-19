"""Knowledge-lake embedding configuration and vector generation."""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

DEFAULT_EMBEDDING_PROVIDER = "deterministic"
DEFAULT_EMBEDDING_MODEL = "deterministic-hash-v1"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-large"
GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"


def embedding_config(settings: Any, *, vector_size: int) -> dict[str, Any]:
    provider = str(
        getattr(settings, "knowledge_embedding_provider", DEFAULT_EMBEDDING_PROVIDER)
        or DEFAULT_EMBEDDING_PROVIDER
    ).strip().lower()
    if provider not in {"deterministic", "openai", "gemini"}:
        provider = DEFAULT_EMBEDDING_PROVIDER

    configured_model = str(getattr(settings, "knowledge_embedding_model", "") or "").strip()
    model = configured_model or _default_model(provider)
    return {
        "provider": provider,
        "model": model,
        "dimensions": vector_size,
        "source": "provider" if provider != "deterministic" else "deterministic",
    }


def vector_for_content(
    settings: Any,
    *,
    mission_id: str,
    knowledge_id: str,
    content: dict[str, Any],
    vector_size: int,
) -> list[float]:
    config = embedding_config(settings, vector_size=vector_size)
    text = _content_text(content)
    if config["provider"] == "openai":
        vector = _openai_embedding(settings, text=text, dimensions=vector_size)
        if vector is not None:
            return _fit_dimensions(vector, vector_size)
    return _deterministic_vector(
        mission_id=mission_id,
        knowledge_id=knowledge_id,
        content=content,
        vector_size=vector_size,
    )


def payload_embedding_metadata(settings: Any, *, vector_size: int) -> dict[str, Any]:
    config = embedding_config(settings, vector_size=vector_size)
    return {
        "embedding_provider": config["provider"],
        "embedding_model": config["model"],
        "embedding_dimensions": config["dimensions"],
    }


def _default_model(provider: str) -> str:
    if provider == "openai":
        return OPENAI_EMBEDDING_MODEL
    if provider == "gemini":
        return GEMINI_EMBEDDING_MODEL
    return DEFAULT_EMBEDDING_MODEL


def _content_text(content: dict[str, Any]) -> str:
    combined = content.get("combined_text")
    if isinstance(combined, str) and combined.strip():
        return combined
    return json.dumps(content, sort_keys=True, separators=(",", ":"))


def _openai_embedding(settings: Any, *, text: str, dimensions: int) -> list[float] | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    base_url = str(
        getattr(settings, "knowledge_embedding_openai_base_url", "")
        or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    ).rstrip("/")
    if not _valid_http_base(base_url):
        return None

    model = str(
        getattr(settings, "knowledge_embedding_model", "") or OPENAI_EMBEDDING_MODEL
    ).strip()
    payload = {
        "model": model,
        "input": text,
        "dimensions": dimensions,
    }
    request = Request(
        f"{base_url}/embeddings",
        data=json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    timeout = max(
        1.0,
        float(getattr(settings, "knowledge_embedding_timeout_seconds", 10.0) or 10.0),
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310
            body = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError):
        return None

    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list) or not data:
        return None
    first = data[0]
    if not isinstance(first, dict) or not isinstance(first.get("embedding"), list):
        return None
    vector = []
    for item in first["embedding"]:
        try:
            vector.append(float(item))
        except (TypeError, ValueError):
            return None
    return vector or None


def _valid_http_base(base_url: str) -> bool:
    parsed = urlparse(base_url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _fit_dimensions(vector: list[float], vector_size: int) -> list[float]:
    if len(vector) == vector_size:
        return vector
    if len(vector) > vector_size:
        return vector[:vector_size]
    return [*vector, *([0.0] * (vector_size - len(vector)))]


def _deterministic_vector(
    *,
    mission_id: str,
    knowledge_id: str,
    content: dict[str, Any],
    vector_size: int,
) -> list[float]:
    seed = (
        f"{mission_id}:{knowledge_id}:"
        f"{json.dumps(content, sort_keys=True, separators=(',', ':'))}"
    ).encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    vector: list[float] = []
    while len(vector) < vector_size:
        for byte in digest:
            vector.append((byte / 255.0) * 2.0 - 1.0)
            if len(vector) >= vector_size:
                break
        digest = hashlib.sha256(digest).digest()
    return vector
