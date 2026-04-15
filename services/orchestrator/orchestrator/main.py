from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from . import milvus_store, neo4j_store, object_store, qdrant_store, storage
from .agent_registry import AGENT_REGISTRY, normalize_language  # noqa: F401  (used by callers via _main)
from .auth import require_roles
from .data_plane_metrics import observe_optional_adapter_mirror_write
from .heartbeat_service import (
    AGENT_HEARTBEAT_STALE_SECONDS,  # noqa: F401
    _upsert_agent_heartbeat,
    agent_heartbeat_loop,
)
from .lifecycle_recovery import lifecycle_recovery_loop
from .models import (
    AgentHeartbeatUpsert,  # noqa: F401
    MissionEvent,
    MissionRecord,
    MissionState,
)
from .protocol import EnvelopeValidator, ProtocolValidationError
from .review_policy import (
    REVIEW_APPROVAL_STORAGE_BACKEND,  # noqa: F401
    _review_approval_digest,  # noqa: F401
    _review_approval_id,  # noqa: F401
    _review_approval_record_path,  # noqa: F401
    _sanitize_review_text,  # noqa: F401
)
from .runtime import (
    emit_state_event as _emit_state_event,
)
from .runtime import (
    ensure_runtime_ready,
    runtime_self_heal_loop,
    start_lifecycle_task,
)
from .settings import load_settings
from .tracing import configure_tracing, current_trace_id

LOGGER = logging.getLogger(__name__)

SETTINGS = load_settings()
MUTATION_AUTH = require_roles(SETTINGS, {"mutate", "admin", "worker"})
INTERNAL_AUTH = require_roles(SETTINGS, {"internal", "admin", "worker"})
MUTATION_AUTH_DEP = Depends(MUTATION_AUTH)
INTERNAL_AUTH_DEP = Depends(INTERNAL_AUTH)

REQUEST_COUNTER = Counter(
    "orchestrator_http_requests_total",
    "Total HTTP requests served by orchestrator",
    ("method", "path", "status_code"),
)
REQUEST_LATENCY = Histogram(
    "orchestrator_http_request_duration_seconds",
    "HTTP request latency in seconds for orchestrator",
    ("method", "path"),
)

LIFECYCLE_RECOVERY_RETRY_SECONDS = max(
    1.0,
    float(os.getenv("LIFECYCLE_RECOVERY_RETRY_SECONDS", "2.0")),
)
LIFECYCLE_RECOVERY_MAX_MISSIONS = max(
    100,
    int(os.getenv("LIFECYCLE_RECOVERY_MAX_MISSIONS", "2000")),
)
emit_state_event = _emit_state_event


def _initialize_app_state(app: FastAPI) -> None:
    if getattr(app.state, "settings", None) is None:
        app.state.settings = SETTINGS
    if getattr(app.state, "redis", None) is None:
        app.state.redis = None
    if getattr(app.state, "redis_ready", None) is None:
        app.state.redis_ready = False
    if getattr(app.state, "db_ready", None) is None:
        app.state.db_ready = False
    if getattr(app.state, "consumer_task", None) is None:
        app.state.consumer_task = None
    if getattr(app.state, "self_heal_task", None) is None:
        app.state.self_heal_task = None
    if getattr(app.state, "agent_heartbeat_task", None) is None:
        app.state.agent_heartbeat_task = None
    if getattr(app.state, "lifecycle_recovery_task", None) is None:
        app.state.lifecycle_recovery_task = None
    if getattr(app.state, "lifecycle_tasks", None) is None:
        app.state.lifecycle_tasks = {}
    if getattr(app.state, "lifecycle_recovery_bootstrapped", None) is None:
        app.state.lifecycle_recovery_bootstrapped = False
    if getattr(app.state, "lifecycle_recovery_recovered_count", None) is None:
        app.state.lifecycle_recovery_recovered_count = 0
    if getattr(app.state, "lifecycle_recovery_scanned_count", None) is None:
        app.state.lifecycle_recovery_scanned_count = 0
    if getattr(app.state, "lifecycle_recovery_last_at", None) is None:
        app.state.lifecycle_recovery_last_at = None
    if getattr(app.state, "lifecycle_recovery_last_error", None) is None:
        app.state.lifecycle_recovery_last_error = None
    if getattr(app.state, "startup_lock", None) is None:
        app.state.startup_lock = asyncio.Lock()
    if getattr(app.state, "protocol_ready", None) is None:
        app.state.protocol_ready = False
    if getattr(app.state, "protocol_error", None) is None:
        app.state.protocol_error = None
    if getattr(app.state, "envelope_validator", None) is None:
        app.state.envelope_validator = None

    if not app.state.protocol_ready and app.state.envelope_validator is None:
        try:
            app.state.envelope_validator = EnvelopeValidator.load(app.state.settings)
            app.state.protocol_ready = True
            app.state.protocol_error = None
        except ProtocolValidationError as exc:
            app.state.protocol_ready = False
            app.state.protocol_error = str(exc)


async def _ensure_db_ready(app: FastAPI) -> tuple[bool, bool]:
    _initialize_app_state(app)
    redis_ready, db_ready = await ensure_runtime_ready(app)
    if not db_ready:
        raise HTTPException(status_code=503, detail="orchestrator database is unavailable")
    return redis_ready, db_ready


async def _run_optional_mirror_write(
    *,
    adapter: str,
    artifact: str,
    fn: Any,
    args: tuple[Any, ...],
) -> None:
    started = time.perf_counter()
    success = False
    try:
        await asyncio.to_thread(fn, *args)
        success = True
    finally:
        observe_optional_adapter_mirror_write(
            adapter=adapter,
            artifact=artifact,
            duration_seconds=time.perf_counter() - started,
            success=success,
        )


async def _fetch_existing_mission(app: FastAPI, mission_id: str) -> MissionRecord:
    mission = await asyncio.to_thread(storage.fetch_mission, app.state.settings, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="mission not found")
    return mission


def _langgraph_runtime_payload(app: FastAPI) -> dict[str, Any]:
    settings = app.state.settings
    return {
        "langgraph_enabled": settings.langgraph_enabled,
        "langgraph_fail_open": settings.langgraph_fail_open,
        "langgraph_checkpointer": settings.langgraph_checkpointer,
        "langgraph_checkpointer_setup": settings.langgraph_checkpointer_setup,
        "langgraph_checkpoint_namespace": settings.langgraph_checkpoint_namespace or None,
        "langgraph_postgres_checkpointer_setup_done": bool(
            getattr(app.state, "langgraph_postgres_checkpointer_setup_done", False)
        ),
        "lifecycle_recovery_bootstrapped": bool(
            getattr(app.state, "lifecycle_recovery_bootstrapped", False)
        ),
        "lifecycle_recovery_recovered_count": int(
            getattr(app.state, "lifecycle_recovery_recovered_count", 0)
        ),
        "lifecycle_recovery_scanned_count": int(
            getattr(app.state, "lifecycle_recovery_scanned_count", 0)
        ),
        "lifecycle_recovery_last_at": getattr(app.state, "lifecycle_recovery_last_at", None),
        "lifecycle_recovery_last_error": getattr(
            app.state,
            "lifecycle_recovery_last_error",
            None,
        ),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    _initialize_app_state(app)

    await ensure_runtime_ready(app)
    app.state.lifecycle_recovery_task = asyncio.create_task(lifecycle_recovery_loop(app))
    app.state.self_heal_task = asyncio.create_task(runtime_self_heal_loop(app))
    app.state.agent_heartbeat_task = asyncio.create_task(agent_heartbeat_loop(app))

    yield

    lifecycle_recovery_task = getattr(app.state, "lifecycle_recovery_task", None)
    if lifecycle_recovery_task is not None:
        lifecycle_recovery_task.cancel()
        with suppress(asyncio.CancelledError):
            await lifecycle_recovery_task

    agent_heartbeat_task = getattr(app.state, "agent_heartbeat_task", None)
    if agent_heartbeat_task is not None:
        agent_heartbeat_task.cancel()
        with suppress(asyncio.CancelledError):
            await agent_heartbeat_task

    self_heal_task = getattr(app.state, "self_heal_task", None)
    if self_heal_task is not None:
        self_heal_task.cancel()
        with suppress(asyncio.CancelledError):
            await self_heal_task

    consumer_task = getattr(app.state, "consumer_task", None)
    if consumer_task is not None:
        consumer_task.cancel()
        with suppress(asyncio.CancelledError):
            await consumer_task

    lifecycle_tasks = getattr(app.state, "lifecycle_tasks", {})
    for task in list(lifecycle_tasks.values()):
        cancel = getattr(task, "cancel", None)
        if callable(cancel):
            cancel()
    for task in list(lifecycle_tasks.values()):
        if not hasattr(task, "__await__"):
            continue
        with suppress(asyncio.CancelledError):
            await task

    if app.state.redis is not None:
        aclose = getattr(app.state.redis, "aclose", None)
        if callable(aclose):
            await aclose()
        else:
            await app.state.redis.close()


app = FastAPI(title="HolyGrail Orchestrator", version="0.3.0", lifespan=lifespan)
configure_tracing(app, service_name="orchestrator")
_initialize_app_state(app)


def _request_correlation_id(request) -> str:
    header = (
        request.headers.get("x-request-id")
        or request.headers.get("x-correlation-id")
        or ""
    ).strip()
    if header:
        return header[:128]
    return uuid.uuid4().hex


@app.middleware("http")
async def _request_metrics(request, call_next):
    started = time.perf_counter()
    method = request.method
    status_code = "500"
    correlation_id = _request_correlation_id(request)
    request.state.correlation_id = correlation_id
    response: Response | None = None
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        return response
    finally:
        route = request.scope.get("route")
        path = route.path if route is not None else request.url.path
        REQUEST_COUNTER.labels(method=method, path=path, status_code=status_code).inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(time.perf_counter() - started)
        if response is not None:
            response.headers["X-Correlation-Id"] = correlation_id
            trace_id = current_trace_id()
            if trace_id:
                response.headers["X-Trace-Id"] = trace_id


@app.get("/health")
async def health() -> dict[str, Any]:
    _initialize_app_state(app)
    redis_ready, db_ready = await ensure_runtime_ready(app)
    redis_client = getattr(app.state, "redis", None)
    agent_heartbeat_task = getattr(app.state, "agent_heartbeat_task", None)

    mission_count = 0
    if db_ready:
        try:
            mission_count = await asyncio.to_thread(storage.count_missions, app.state.settings)
        except Exception:
            db_ready = False

    redis_healthy = False
    if redis_ready and redis_client is not None:
        try:
            redis_healthy = bool(await redis_client.ping())
        except Exception:
            redis_ready = False
            redis_healthy = False

    qdrant_ready: bool | None = None
    if app.state.settings.qdrant_enabled:
        qdrant_ready = await asyncio.to_thread(qdrant_store.qdrant_ready, app.state.settings)
    milvus_ready: bool | None = None
    if app.state.settings.milvus_enabled:
        milvus_ready = await asyncio.to_thread(milvus_store.milvus_ready, app.state.settings)
    neo4j_ready: bool | None = None
    if app.state.settings.neo4j_enabled:
        neo4j_ready = await asyncio.to_thread(neo4j_store.neo4j_ready, app.state.settings)
    object_storage_ready: bool | None = None
    if app.state.settings.object_storage_enabled:
        object_storage_ready = await asyncio.to_thread(
            object_store.object_storage_ready, app.state.settings
        )

    return {
        "ok": True,
        "service": "orchestrator",
        "redis_healthy": redis_healthy,
        "db_ready": db_ready,
        "qdrant_ready": qdrant_ready,
        "milvus_ready": milvus_ready,
        "neo4j_ready": neo4j_ready,
        "object_storage_ready": object_storage_ready,
        "mission_count": mission_count,
        "intake_stream": app.state.settings.intake_stream,
        "state_stream": app.state.settings.state_stream,
        "auto_transition_enabled": app.state.settings.auto_transition_enabled,
        "transition_step_seconds": app.state.settings.transition_step_seconds,
        "active_lifecycle_tasks": len(getattr(app.state, "lifecycle_tasks", {})),
        "agent_heartbeat_task_running": bool(
            agent_heartbeat_task is not None and not agent_heartbeat_task.done()
        ),
        "protocol_ready": bool(getattr(app.state, "protocol_ready", False)),
        "protocol_error": getattr(app.state, "protocol_error", None),
        **_langgraph_runtime_payload(app),
    }


@app.get("/readyz")
async def readyz() -> dict[str, Any]:
    _initialize_app_state(app)
    redis_ready, db_ready = await ensure_runtime_ready(app)
    qdrant_ready: bool | None = None
    if app.state.settings.qdrant_enabled:
        qdrant_ready = await asyncio.to_thread(qdrant_store.qdrant_ready, app.state.settings)
    milvus_ready: bool | None = None
    if app.state.settings.milvus_enabled:
        milvus_ready = await asyncio.to_thread(milvus_store.milvus_ready, app.state.settings)
    neo4j_ready: bool | None = None
    if app.state.settings.neo4j_enabled:
        neo4j_ready = await asyncio.to_thread(neo4j_store.neo4j_ready, app.state.settings)
    object_storage_ready: bool | None = None
    if app.state.settings.object_storage_enabled:
        object_storage_ready = await asyncio.to_thread(
            object_store.object_storage_ready, app.state.settings
        )
    protocol_ready = bool(getattr(app.state, "protocol_ready", False))
    consumer_task = getattr(app.state, "consumer_task", None)
    consumer_running = consumer_task is not None and not consumer_task.done()
    ready = redis_ready and db_ready and protocol_ready and consumer_running
    if app.state.settings.qdrant_enabled:
        ready = ready and bool(qdrant_ready)
    if app.state.settings.milvus_enabled:
        ready = ready and bool(milvus_ready)
    if app.state.settings.neo4j_enabled:
        ready = ready and bool(neo4j_ready)
    if app.state.settings.object_storage_enabled:
        ready = ready and bool(object_storage_ready)
    if not ready:
        raise HTTPException(
            status_code=503,
            detail={
                "ready": False,
                "service": "orchestrator",
                "redis_ready": redis_ready,
                "db_ready": db_ready,
                "qdrant_ready": qdrant_ready,
                "milvus_ready": milvus_ready,
                "neo4j_ready": neo4j_ready,
                "object_storage_ready": object_storage_ready,
                "protocol_ready": protocol_ready,
                "consumer_running": consumer_running,
                **_langgraph_runtime_payload(app),
            },
        )

    return {
        "ready": True,
        "service": "orchestrator",
        "redis_ready": redis_ready,
        "db_ready": db_ready,
        "qdrant_ready": qdrant_ready,
        "milvus_ready": milvus_ready,
        "neo4j_ready": neo4j_ready,
        "object_storage_ready": object_storage_ready,
        "protocol_ready": protocol_ready,
        "consumer_running": consumer_running,
        **_langgraph_runtime_payload(app),
    }


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


from .routes.internal import router as internal_router  # noqa: E402
from .routes.missions import router as missions_router  # noqa: E402
from .routes.operations import router as operations_router  # noqa: E402

app.include_router(missions_router)
app.include_router(internal_router)
app.include_router(operations_router)
