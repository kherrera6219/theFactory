from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from . import storage
from .auth import AuthContext, require_roles
from .models import (
    AuditReportUpsert,
    KnowledgeUpsert,
    LogicNodeUpsert,
    MissionCreate,
    MissionRecord,
    MissionState,
    MissionStateUpdate,
    PodAssignmentUpsert,
)
from .protocol import EnvelopeValidator, ProtocolValidationError
from .runtime import (
    emit_state_event,
    ensure_runtime_ready,
    runtime_self_heal_loop,
    start_lifecycle_task,
)
from .settings import load_settings

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
    if getattr(app.state, "lifecycle_tasks", None) is None:
        app.state.lifecycle_tasks = {}
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


async def _fetch_existing_mission(app: FastAPI, mission_id: str) -> MissionRecord:
    mission = await asyncio.to_thread(storage.fetch_mission, app.state.settings, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="mission not found")
    return mission


@asynccontextmanager
async def lifespan(app: FastAPI):
    _initialize_app_state(app)

    await ensure_runtime_ready(app)
    app.state.self_heal_task = asyncio.create_task(runtime_self_heal_loop(app))

    yield

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
        task.cancel()
    for task in list(lifecycle_tasks.values()):
        with suppress(asyncio.CancelledError):
            await task

    if app.state.redis is not None:
        aclose = getattr(app.state.redis, "aclose", None)
        if callable(aclose):
            await aclose()
        else:
            await app.state.redis.close()


app = FastAPI(title="HolyGrail Orchestrator", version="0.3.0", lifespan=lifespan)
_initialize_app_state(app)


@app.middleware("http")
async def _request_metrics(request, call_next):
    started = time.perf_counter()
    method = request.method
    status_code = "500"
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        return response
    finally:
        route = request.scope.get("route")
        path = route.path if route is not None else request.url.path
        REQUEST_COUNTER.labels(method=method, path=path, status_code=status_code).inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(time.perf_counter() - started)


@app.get("/health")
async def health() -> dict[str, Any]:
    _initialize_app_state(app)
    redis_ready, db_ready = await ensure_runtime_ready(app)
    redis_client = getattr(app.state, "redis", None)

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

    return {
        "ok": True,
        "service": "orchestrator",
        "redis_url": app.state.settings.redis_url,
        "postgres_url": app.state.settings.postgres_url,
        "redis_healthy": redis_healthy,
        "db_ready": db_ready,
        "mission_count": mission_count,
        "intake_stream": app.state.settings.intake_stream,
        "state_stream": app.state.settings.state_stream,
        "auto_transition_enabled": app.state.settings.auto_transition_enabled,
        "transition_step_seconds": app.state.settings.transition_step_seconds,
        "active_lifecycle_tasks": len(getattr(app.state, "lifecycle_tasks", {})),
        "protocol_ready": bool(getattr(app.state, "protocol_ready", False)),
        "protocol_error": getattr(app.state, "protocol_error", None),
    }


@app.get("/readyz")
async def readyz() -> dict[str, Any]:
    _initialize_app_state(app)
    redis_ready, db_ready = await ensure_runtime_ready(app)
    protocol_ready = bool(getattr(app.state, "protocol_ready", False))
    consumer_task = getattr(app.state, "consumer_task", None)
    consumer_running = consumer_task is not None and not consumer_task.done()
    ready = redis_ready and db_ready and protocol_ready and consumer_running
    if not ready:
        raise HTTPException(
            status_code=503,
            detail={
                "ready": False,
                "service": "orchestrator",
                "redis_ready": redis_ready,
                "db_ready": db_ready,
                "protocol_ready": protocol_ready,
                "consumer_running": consumer_running,
            },
        )

    return {
        "ready": True,
        "service": "orchestrator",
        "redis_ready": redis_ready,
        "db_ready": db_ready,
        "protocol_ready": protocol_ready,
        "consumer_running": consumer_running,
    }


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/missions")
async def create_mission(
    payload: MissionCreate,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> MissionRecord:
    redis_ready, _ = await _ensure_db_ready(app)
    redis_client = getattr(app.state, "redis", None)

    record = MissionRecord(
        mission_id=payload.mission_id,
        prompt=payload.prompt,
        requested_target_language=payload.requested_target_language,
        metadata=payload.metadata,
        state=MissionState.queued,
        created_at=payload.created_at or datetime.now(UTC).isoformat(),
    )

    await asyncio.to_thread(storage.upsert_mission, app.state.settings, record, None)
    await asyncio.to_thread(
        storage.insert_mission_event,
        app.state.settings,
        record.mission_id,
        MissionState.intake,
        MissionState.queued,
        "MISSION_QUEUED",
    )

    if redis_ready and redis_client is not None and app.state.protocol_ready:
        try:
            await emit_state_event(
                app.state.settings,
                app.state.envelope_validator,
                redis_client,
                record,
                "MISSION_QUEUED",
            )
        except Exception as exc:
            LOGGER.warning("failed to emit queued state event for %s: %s", record.mission_id, exc)

    start_lifecycle_task(app, record.mission_id)
    return record


@app.get("/missions/{mission_id}")
async def get_mission(mission_id: str) -> MissionRecord:
    await _ensure_db_ready(app)
    return await _fetch_existing_mission(app, mission_id)


@app.get("/missions")
async def list_missions(limit: int = Query(default=20, ge=1, le=200)) -> list[MissionRecord]:
    await _ensure_db_ready(app)
    return await asyncio.to_thread(storage.list_missions, app.state.settings, limit)


@app.get("/missions/{mission_id}/events")
async def get_mission_events(
    mission_id: str,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    await _ensure_db_ready(app)
    await _fetch_existing_mission(app, mission_id)
    events = await asyncio.to_thread(
        storage.list_mission_events, app.state.settings, mission_id, limit
    )
    return [event.model_dump() for event in events]


@app.post("/missions/{mission_id}/state")
async def update_mission_state(
    mission_id: str,
    payload: MissionStateUpdate,
    _: AuthContext = MUTATION_AUTH_DEP,
) -> MissionRecord:
    redis_ready, _ = await _ensure_db_ready(app)
    redis_client = getattr(app.state, "redis", None)

    event_type = f"MISSION_{payload.new_state.value}"
    record = await asyncio.to_thread(
        storage.transition_mission_state,
        app.state.settings,
        mission_id,
        payload.expected_state,
        payload.new_state,
        event_type,
    )
    if record is None:
        raise HTTPException(status_code=409, detail="state transition rejected")

    if redis_ready and redis_client is not None and app.state.protocol_ready:
        try:
            await emit_state_event(
                app.state.settings,
                app.state.envelope_validator,
                redis_client,
                record,
                event_type,
            )
        except Exception as exc:
            LOGGER.warning("failed to emit state event for %s: %s", record.mission_id, exc)

    return record


@app.post("/internal/pod-assignment")
async def upsert_pod_assignment(
    payload: PodAssignmentUpsert,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    await _ensure_db_ready(app)
    await _fetch_existing_mission(app, payload.mission_id)

    assigned_at = payload.assigned_at or datetime.now(UTC).isoformat()
    try:
        return await asyncio.to_thread(
            storage.upsert_pod_assignment,
            app.state.settings,
            payload.mission_id,
            payload.pod_name,
            payload.metadata,
            assigned_at,
        )
    except storage.PodAssignmentConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "mission already assigned to a different pod",
                "assignment": exc.existing_assignment,
            },
        ) from exc


@app.get("/internal/missions/{mission_id}/pod-assignment")
async def get_pod_assignment(
    mission_id: str,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    await _ensure_db_ready(app)
    await _fetch_existing_mission(app, mission_id)
    record = await asyncio.to_thread(storage.get_pod_assignment, app.state.settings, mission_id)
    if record is None:
        raise HTTPException(status_code=404, detail="pod assignment not found")
    return record


@app.post("/internal/logicnodes")
async def upsert_logicnode(
    payload: LogicNodeUpsert,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    await _ensure_db_ready(app)
    await _fetch_existing_mission(app, payload.mission_id)

    created_at = payload.created_at or datetime.now(UTC).isoformat()
    return await asyncio.to_thread(
        storage.upsert_logicnode,
        app.state.settings,
        payload.mission_id,
        payload.node_id,
        payload.node,
        created_at,
    )


@app.get("/internal/missions/{mission_id}/logicnodes")
async def get_logicnodes(
    mission_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    await _ensure_db_ready(app)
    await _fetch_existing_mission(app, mission_id)
    return await asyncio.to_thread(storage.list_logicnodes, app.state.settings, mission_id, limit)


@app.post("/internal/knowledge")
async def upsert_knowledge(
    payload: KnowledgeUpsert,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    await _ensure_db_ready(app)
    await _fetch_existing_mission(app, payload.mission_id)

    created_at = payload.created_at or datetime.now(UTC).isoformat()
    return await asyncio.to_thread(
        storage.upsert_knowledge,
        app.state.settings,
        payload.mission_id,
        payload.knowledge_id,
        payload.content,
        created_at,
    )


@app.get("/internal/missions/{mission_id}/knowledge")
async def get_knowledge(
    mission_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    await _ensure_db_ready(app)
    await _fetch_existing_mission(app, mission_id)
    return await asyncio.to_thread(storage.list_knowledge, app.state.settings, mission_id, limit)


@app.post("/internal/audit-reports")
async def upsert_audit_report(
    payload: AuditReportUpsert,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    await _ensure_db_ready(app)
    await _fetch_existing_mission(app, payload.mission_id)

    created_at = payload.created_at or datetime.now(UTC).isoformat()
    return await asyncio.to_thread(
        storage.upsert_audit_report,
        app.state.settings,
        payload.mission_id,
        payload.audit_id,
        payload.status,
        payload.report,
        created_at,
    )


@app.get("/internal/missions/{mission_id}/audit-reports")
async def get_audit_reports(
    mission_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    await _ensure_db_ready(app)
    await _fetch_existing_mission(app, mission_id)
    return await asyncio.to_thread(
        storage.list_audit_reports, app.state.settings, mission_id, limit
    )
