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


def _record_embedding_usage(
    settings: Any,
    mission_id: str,
    provider: str,
    model: str,
    text: str,
    succeeded: bool,
) -> None:
    try:
        import asyncio

        from .llm_cost_ledger import record_llm_usage

        tokens = max(1, len(text) // 4)
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(
                    record_llm_usage(
                        settings=settings,
                        mission_id=mission_id,
                        agent_id="system-knowledge-lake",
                        provider=provider,
                        model=model,
                        input_tokens=tokens,
                        output_tokens=0,
                        call_succeeded=succeeded,
                        routing_source="knowledge-lake-embedding",
                    )
                )
        except RuntimeError:
            pass
    except Exception:
        pass


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
        _record_embedding_usage(
            settings,
            mission_id,
            config["provider"],
            config["model"],
            text,
            vector is not None,
        )
        if vector is not None:
            return _fit_dimensions(vector, vector_size)
    if config["provider"] == "gemini":
        vector = _gemini_embedding(settings, text=text, dimensions=vector_size)
        _record_embedding_usage(
            settings,
            mission_id,
            config["provider"],
            config["model"],
            text,
            vector is not None,
        )
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
    api_key = (
        str(getattr(settings, "knowledge_embedding_api_key", "") or "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )
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



def _gemini_embedding(settings: Any, *, text: str, dimensions: int) -> list[float] | None:
    api_key = (
        str(getattr(settings, "knowledge_embedding_api_key", "") or "").strip()
        or os.getenv("GEMINI_API_KEY", "").strip()
    )
    if not api_key:
        return None
    base_url = str(
        getattr(settings, "knowledge_embedding_gemini_base_url", "")
        or os.getenv(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta",
        )
    ).rstrip("/")
    if not _valid_http_base(base_url):
        return None
    model = str(
        getattr(settings, "knowledge_embedding_model", "") or GEMINI_EMBEDDING_MODEL
    ).strip()
    payload = {
        "model": model,
        "content": {"parts": [{"text": text}]},
        "task_type": "RETRIEVAL_DOCUMENT",
    }
    if dimensions and dimensions != 768:
        payload["output_dimensionality"] = dimensions
    url = f"{base_url}/models/{model}:embedContent?key={api_key}"
    request = Request(
        url,
        data=json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
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
    embedding = body.get("embedding") if isinstance(body, dict) else None
    if not isinstance(embedding, dict):
        return None
    values = embedding.get("values")
    if not isinstance(values, list) or not values:
        return None
    vector = []
    for item in values:
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
