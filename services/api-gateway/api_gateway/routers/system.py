"""System routes: health, readyz, metrics, and index."""

from __future__ import annotations

from typing import Any, Callable, Coroutine

from fastapi import APIRouter, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


def build_system_router(
    *,
    dependency_status_fn: Callable[[], Coroutine[Any, Any, dict[str, bool]]],
    health_payload_fn: Callable[[dict[str, bool]], dict[str, Any]],
) -> APIRouter:
    router = APIRouter(tags=["system"])

    @router.get("/health")
    async def health() -> dict[str, Any]:
        dependency_status = await dependency_status_fn()
        return health_payload_fn(dependency_status)

    @router.get("/readyz")
    async def readyz() -> dict[str, Any]:
        dependency_status = await dependency_status_fn()
        ready = all(dependency_status.values())
        if not ready:
            raise HTTPException(
                status_code=503,
                detail={
                    "ready": False,
                    "service": "api-gateway",
                    **dependency_status,
                },
            )
        return {
            "ready": True,
            "service": "api-gateway",
            **dependency_status,
        }

    @router.get("/metrics")
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @router.get("/")
    def index() -> dict[str, str]:
        return {"name": "HolyGrail API Gateway", "status": "ready"}

    return router
