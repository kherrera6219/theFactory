from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query, Request

from .. import milvus_store, neo4j_store, object_store, qdrant_store, storage
from ..agent_integrations import build_agent_integrations_snapshot
from ..auth import AuthContext
from ..models import MissionRecord
from ._deps import INTERNAL_AUTH_DEP

LOGGER = logging.getLogger(__name__)

router = APIRouter()


@router.get("/internal/operations/summary")
async def get_operations_summary(
    request: Request,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    _main._initialize_app_state(app)
    redis_ready, db_ready = await _main.ensure_runtime_ready(app)
    state_counts = await asyncio.to_thread(storage.mission_state_counts, app.state.settings)
    pod_assignments = await asyncio.to_thread(storage.list_pod_assignments, app.state.settings, 500)

    pod_counts: dict[str, int] = {}
    for record in pod_assignments:
        pod_name = str(record.get("pod_name", "unknown"))
        pod_counts[pod_name] = pod_counts.get(pod_name, 0) + 1

    protocol_ready = bool(getattr(app.state, "protocol_ready", False))
    consumer_task = getattr(app.state, "consumer_task", None)
    consumer_running = consumer_task is not None and not consumer_task.done()
    qdrant_ready = await asyncio.to_thread(qdrant_store.qdrant_ready, app.state.settings)
    milvus_ready = await asyncio.to_thread(milvus_store.milvus_ready, app.state.settings)
    neo4j_ready = await asyncio.to_thread(neo4j_store.neo4j_ready, app.state.settings)
    object_storage_ready = await asyncio.to_thread(
        object_store.object_storage_ready, app.state.settings
    )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "runtime": {
            "redis_ready": redis_ready,
            "db_ready": db_ready,
            "qdrant_ready": qdrant_ready,
            "milvus_ready": milvus_ready,
            "neo4j_ready": neo4j_ready,
            "object_storage_ready": object_storage_ready,
            "protocol_ready": protocol_ready,
            "consumer_running": consumer_running,
            **_main._langgraph_runtime_payload(app),
        },
        "mission_state_counts": state_counts,
        "pod_assignment_counts": pod_counts,
        "active_lifecycle_tasks": len(getattr(app.state, "lifecycle_tasks", {})),
    }


@router.get("/internal/operations/agents")
async def get_operations_agents(
    request: Request,
    mission_limit: int = Query(default=1000, ge=50, le=5000),
    assignment_limit: int = Query(default=1000, ge=50, le=5000),
    event_limit: int = Query(default=300, ge=50, le=2000),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    _main._initialize_app_state(app)
    redis_ready, db_ready = await _main.ensure_runtime_ready(app)
    protocol_ready = bool(getattr(app.state, "protocol_ready", False))
    consumer_task = getattr(app.state, "consumer_task", None)
    consumer_running = consumer_task is not None and not consumer_task.done()
    qdrant_ready = await asyncio.to_thread(qdrant_store.qdrant_ready, app.state.settings)
    milvus_ready = await asyncio.to_thread(milvus_store.milvus_ready, app.state.settings)
    neo4j_ready = await asyncio.to_thread(neo4j_store.neo4j_ready, app.state.settings)
    object_storage_ready = await asyncio.to_thread(
        object_store.object_storage_ready, app.state.settings
    )

    missions: list[MissionRecord] = []
    pod_assignments: list[dict[str, Any]] = []
    recent_events: list[Any] = []
    agent_heartbeats: list[dict[str, Any]] = []
    runtime_error: str | None = None

    if db_ready:
        try:
            missions = await asyncio.to_thread(
                storage.list_missions,
                app.state.settings,
                mission_limit,
            )
            pod_assignments = await asyncio.to_thread(
                storage.list_pod_assignments,
                app.state.settings,
                assignment_limit,
            )
            recent_events = await asyncio.to_thread(
                storage.list_recent_mission_events,
                app.state.settings,
                event_limit,
            )
            agent_heartbeats = await asyncio.to_thread(
                storage.list_agent_heartbeats,
                app.state.settings,
                500,
            )
        except Exception as exc:
            db_ready = False
            runtime_error = str(exc)

    runtime = {
        "redis_ready": redis_ready,
        "db_ready": db_ready,
        "qdrant_ready": qdrant_ready,
        "milvus_ready": milvus_ready,
        "neo4j_ready": neo4j_ready,
        "object_storage_ready": object_storage_ready,
        "protocol_ready": protocol_ready,
        "consumer_running": consumer_running,
        **_main._langgraph_runtime_payload(app),
    }
    snapshot = _main._build_operations_agents_snapshot(
        generated_at=datetime.now(UTC),
        runtime=runtime,
        missions=missions,
        pod_assignments=pod_assignments,
        recent_events=recent_events,
        agent_heartbeats=agent_heartbeats,
    )
    if runtime_error:
        snapshot["runtime_error"] = runtime_error
    return snapshot


@router.get("/internal/operations/agent-integrations")
async def get_operations_agent_integrations(
    request: Request,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    return build_agent_integrations_snapshot()


@router.get("/internal/operations/events")
async def get_operations_events(
    request: Request,
    limit: int = Query(default=200, ge=1, le=1000),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    events = await asyncio.to_thread(storage.list_recent_mission_events, app.state.settings, limit)
    return [event.model_dump() for event in events]


@router.get("/internal/operations/agent-events")
async def get_operations_agent_events(
    request: Request,
    limit: int = Query(default=200, ge=1, le=1000),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    return await asyncio.to_thread(storage.list_recent_agent_events, app.state.settings, limit)


@router.get("/internal/operations/logicnodes")
async def get_operations_logicnodes(
    request: Request,
    limit: int = Query(default=200, ge=1, le=1000),
    mission_id: str | None = Query(default=None, min_length=1),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    if mission_id:
        await _main._fetch_existing_mission(app, mission_id)
        return await asyncio.to_thread(
            storage.list_logicnodes,
            app.state.settings,
            mission_id,
            limit,
        )
    return await asyncio.to_thread(storage.list_recent_logicnodes, app.state.settings, limit)


@router.get("/internal/operations/pod-assignments")
async def get_operations_pod_assignments(
    request: Request,
    limit: int = Query(default=200, ge=1, le=1000),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    return await asyncio.to_thread(storage.list_pod_assignments, app.state.settings, limit)


@router.get("/internal/operations/projects")
async def get_operations_projects(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    return await asyncio.to_thread(storage.summarize_projects, app.state.settings, limit)


@router.get("/internal/operations/alerts")
async def get_operations_alerts(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    import orchestrator.main as _main

    app = request.app
    _main._initialize_app_state(app)
    redis_ready, db_ready = await _main.ensure_runtime_ready(app)
    state_counts = await asyncio.to_thread(storage.mission_state_counts, app.state.settings)
    recent_events = await asyncio.to_thread(
        storage.list_recent_mission_events,
        app.state.settings,
        500,
    )
    blocked_completion_count = sum(
        1
        for event in recent_events
        if getattr(event, "event_type", "") == "MISSION_COMPLETION_BLOCKED"
    )
    protocol_ready = bool(getattr(app.state, "protocol_ready", False))
    consumer_task = getattr(app.state, "consumer_task", None)
    consumer_running = consumer_task is not None and not consumer_task.done()
    return _main._build_operational_alerts(
        redis_ready=redis_ready,
        db_ready=db_ready,
        protocol_ready=protocol_ready,
        consumer_running=consumer_running,
        state_counts=state_counts,
        blocked_completion_count=blocked_completion_count,
        limit=limit,
    )
