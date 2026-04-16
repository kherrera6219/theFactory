"""proxy.py — Orchestrator reverse-proxy helpers for the API Gateway."""
from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import HTTPException

from .auth import _require_internal_service_api_key
from .config import ORCHESTRATOR_URL

LOGGER = logging.getLogger(__name__)


async def _proxy_get(path: str, *, params: dict[str, Any] | None = None) -> Any:
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(f"{ORCHESTRATOR_URL}{path}", params=params)
    except Exception as exc:
        LOGGER.warning("orchestrator query failed for %s: %s", path, exc)
        raise HTTPException(status_code=502, detail="orchestrator unavailable") from exc
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="resource not found")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="orchestrator query failed")
    return response.json()


async def _proxy_get_internal(path: str, *, params: dict[str, Any] | None = None) -> Any:
    internal_key = _require_internal_service_api_key()
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(
                f"{ORCHESTRATOR_URL}{path}",
                params=params,
                headers={"x-api-key": internal_key},
            )
    except Exception as exc:
        LOGGER.warning("orchestrator internal query failed for %s: %s", path, exc)
        raise HTTPException(status_code=502, detail="orchestrator unavailable") from exc
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="resource not found")
    if response.status_code in {401, 403}:
        raise HTTPException(status_code=502, detail="orchestrator internal auth rejected request")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="orchestrator internal query failed")
    return response.json()


async def _proxy_post_internal(path: str, *, json_body: dict[str, Any]) -> Any:
    internal_key = _require_internal_service_api_key()
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.post(
                f"{ORCHESTRATOR_URL}{path}",
                json=json_body,
                headers={"x-api-key": internal_key},
            )
    except Exception as exc:
        LOGGER.warning("orchestrator internal mutation failed for %s: %s", path, exc)
        raise HTTPException(status_code=502, detail="orchestrator unavailable") from exc
    if response.status_code in {401, 403}:
        raise HTTPException(status_code=502, detail="orchestrator internal auth rejected request")
    if response.status_code >= 400:
        try:
            payload = response.json()
        except Exception:
            payload = {}
        detail = payload.get("detail") if isinstance(payload, dict) else None
        raise HTTPException(
            status_code=502,
            detail=str(detail or "orchestrator internal write failed"),
        )
    return response.json()
