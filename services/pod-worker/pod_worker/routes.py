"""Health, readiness, and Prometheus metrics routes for Pod Workers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


def build_pod_worker_router() -> APIRouter:
    from pod_worker import main as worker_main

    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, Any]:
        ready = False
        redis_client = getattr(worker_main.app.state, "redis", None)
        if redis_client is not None:
            try:
                ready = bool(await redis_client.ping())
            except Exception:
                ready = False
        return {
            "ok": ready,
            "service": "pod-worker",
            "pod_name": worker_main.POD_NAME,
            "supported_languages": sorted(worker_main.SUPPORTED_LANGUAGES),
            "state_stream": worker_main.STATE_STREAM,
            "group": worker_main.CONSUMER_GROUP,
            "consumer": worker_main.CONSUMER_NAME,
            "worker_agent_id": worker_main._effective_worker_agent_id(),
            "agent_binding": list(worker_main.AGENT_BINDINGS),
            "agent_service_key_mode": worker_main.AGENT_SERVICE_KEY_MODE,
            "configured_agent_service_keys": len(worker_main._configured_agent_service_key_map()),
            "processed": worker_main.app.state.processed,
            "errors": worker_main.app.state.errors,
            "internal_auth_failures": worker_main.INTERNAL_AUTH_FAILURES,
            "last_internal_auth_status": worker_main.LAST_INTERNAL_AUTH_STATUS,
        }

    @router.get("/readyz")
    async def readyz() -> dict[str, Any]:
        redis_client = getattr(worker_main.app.state, "redis", None)
        if redis_client is None:
            raise HTTPException(status_code=503, detail="redis unavailable")
        try:
            ready = bool(await redis_client.ping())
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"redis unavailable: {exc}") from exc
        if not ready:
            raise HTTPException(status_code=503, detail="redis unavailable")
        return {"ready": True, "service": "pod-worker", "pod_name": worker_main.POD_NAME}

    @router.get("/metrics")
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return router
