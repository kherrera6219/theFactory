from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from .. import milvus_store, neo4j_store, object_store, qdrant_store, storage
from ..agent_integrations import build_agent_integration_record, build_agent_integrations_snapshot
from ..agent_registry import AGENT_REGISTRY, normalize_language
from ..auth import AuthContext
from ..heartbeat_service import (
    AGENT_HEARTBEAT_STALE_SECONDS,
    _state_for_agent,
    _workload_for_agent,
)
from ..models import AlertStateUpdate, MissionRecord
from ._deps import INTERNAL_AUTH_DEP, MUTATION_AUTH_DEP

LOGGER = logging.getLogger(__name__)

router = APIRouter()

# Alerts are recomputed fresh from live health signals on every request (see
# _build_operational_alerts) — there is no incident-record table to persist
# acknowledge/resolve state against. Overlaying a Redis-backed ack, keyed by
# the alert's stable alert_id and expiring after ALERT_ACK_TTL_SECONDS, lets
# an operator's "Acknowledge"/"Mark Resolved" survive a refresh without
# permanently silencing a still-broken condition forever.
ALERT_ACK_REDIS_PREFIX = "alert:ack"
ALERT_ACK_TTL_SECONDS = int(os.getenv("ALERT_ACK_TTL_SECONDS", "86400"))

# Every alert_id _build_operational_alerts can ever emit — fetched up front so
# an ack made while a condition is transiently absent (e.g. acknowledging a
# consumer-restart blip right as it recovers) still applies if it recurs
# before the TTL expires.
KNOWN_ALERT_IDS = (
    "runtime-redis-unavailable",
    "runtime-db-unavailable",
    "runtime-protocol-not-ready",
    "runtime-consumer-not-running",
    "missions-failed-present",
    "missions-completion-blocked",
)


def _alert_ack_redis_key(alert_id: str) -> str:
    return f"{ALERT_ACK_REDIS_PREFIX}:{alert_id}"


async def _load_alert_ack_states(redis_client: Any, alert_ids: list[str]) -> dict[str, str]:
    if redis_client is None or not alert_ids:
        return {}
    states: dict[str, str] = {}
    for alert_id in alert_ids:
        try:
            raw = await redis_client.get(_alert_ack_redis_key(alert_id))
        except Exception as exc:  # pragma: no cover - defensive, matches idempotency pattern
            LOGGER.warning("failed to read alert ack state for %s: %s", alert_id, exc)
            continue
        if raw:
            states[alert_id] = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
    return states


async def _save_alert_ack_state(redis_client: Any, alert_id: str, state: str) -> None:
    await redis_client.set(
        _alert_ack_redis_key(alert_id),
        state,
        ex=ALERT_ACK_TTL_SECONDS,
    )


# ---------------------------------------------------------------------------
# Operations snapshot helpers (moved from main.py)
# ---------------------------------------------------------------------------


def _normalize_pod_name(value: str) -> str:
    return value.strip().lower().replace(" ", "").replace("-", "").replace("_", "")


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = value
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _build_operational_alerts(
    *,
    redis_ready: bool,
    db_ready: bool,
    protocol_ready: bool,
    consumer_running: bool,
    state_counts: dict[str, int],
    blocked_completion_count: int,
    limit: int,
    ack_states: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    now = datetime.now(UTC).isoformat()

    if not redis_ready:
        alerts.append(
            {
                "alert_id": "runtime-redis-unavailable",
                "severity": "critical",
                "state": "open",
                "title": "Redis unavailable",
                "source": "orchestrator-runtime",
                "created_at": now,
                "recommendation": (
                    "Restore Redis connectivity before accepting new mission intake load."
                ),
            }
        )
    if not db_ready:
        alerts.append(
            {
                "alert_id": "runtime-db-unavailable",
                "severity": "critical",
                "state": "open",
                "title": "Postgres unavailable",
                "source": "orchestrator-runtime",
                "created_at": now,
                "recommendation": (
                    "Restore database access before mission lifecycle transitions continue."
                ),
            }
        )
    if not protocol_ready:
        alerts.append(
            {
                "alert_id": "runtime-protocol-not-ready",
                "severity": "high",
                "state": "open",
                "title": "Protocol validator not ready",
                "source": "orchestrator-runtime",
                "created_at": now,
                "recommendation": "Verify protocol/topic definitions and schema loading paths.",
            }
        )
    if not consumer_running:
        alerts.append(
            {
                "alert_id": "runtime-consumer-not-running",
                "severity": "high",
                "state": "open",
                "title": "Intake consumer not running",
                "source": "orchestrator-runtime",
                "created_at": now,
                "recommendation": (
                    "Restart the intake consumer group and inspect runtime self-heal logs."
                ),
            }
        )

    failed_count = int(state_counts.get("FAILED", 0))
    if failed_count > 0:
        alerts.append(
            {
                "alert_id": "missions-failed-present",
                "severity": "medium",
                "state": "open",
                "title": "Failed missions present",
                "source": "mission-lifecycle",
                "created_at": now,
                "recommendation": (
                    f"Review {failed_count} failed mission(s) and replay or remediate as needed."
                ),
            }
        )
    if blocked_completion_count > 0:
        alerts.append(
            {
                "alert_id": "missions-completion-blocked",
                "severity": "high",
                "state": "open",
                "title": "Mission completion blocked by missing artifacts",
                "source": "mission-lifecycle",
                "created_at": now,
                "recommendation": (
                    "Review mission chain trace and ensure pod assignment or LogicNode "
                    "evidence exists before completion."
                ),
            }
        )

    if ack_states:
        for alert in alerts:
            acked_state = ack_states.get(alert["alert_id"])
            if acked_state:
                alert["state"] = acked_state

    return alerts[:limit]


def _build_operations_agents_snapshot(
    *,
    generated_at: datetime,
    runtime: dict[str, bool],
    missions: list[MissionRecord],
    pod_assignments: list[dict[str, Any]],
    recent_events: list[Any],
    agent_heartbeats: list[dict[str, Any]],
) -> dict[str, Any]:
    from ..models import MissionState  # local import avoids re-declaring at module level

    active_states = {MissionState.queued, MissionState.running, MissionState.verified}
    active_missions = [mission for mission in missions if mission.state in active_states]
    active_mission_ids = {mission.mission_id for mission in active_missions}
    verified_mission_ids = {
        mission.mission_id for mission in missions if mission.state == MissionState.verified
    }
    complete_mission_ids = {
        mission.mission_id for mission in missions if mission.state == MissionState.complete
    }
    mission_by_id = {mission.mission_id: mission for mission in missions}

    assignment_by_mission: dict[str, str] = {}
    active_ids_by_pod: dict[str, list[str]] = defaultdict(list)
    for assignment in pod_assignments:
        mission_id = str(assignment.get("mission_id", ""))
        pod_key = _normalize_pod_name(str(assignment.get("pod_name", "")))
        if not mission_id or not pod_key:
            continue
        assignment_by_mission[mission_id] = pod_key
        if mission_id in active_mission_ids:
            active_ids_by_pod[pod_key].append(mission_id)

    specialist_lookup: dict[tuple[str, str], str] = {}
    specialist_missions: dict[str, list[str]] = {}
    for agent in AGENT_REGISTRY:
        if agent.category != "specialist":
            continue
        specialist_missions[agent.agent_id] = []
        pod_key = _normalize_pod_name(agent.pod)
        for specialty in agent.specialties:
            specialist_lookup[(pod_key, normalize_language(specialty))] = agent.agent_id

    for mission_id in sorted(active_mission_ids):
        pod_key = assignment_by_mission.get(mission_id)
        if not pod_key:
            continue
        mission = mission_by_id.get(mission_id)
        if mission is None:
            continue
        normalized_language = normalize_language(mission.requested_target_language)
        specialist_id = specialist_lookup.get((pod_key, normalized_language))
        if specialist_id is None and pod_key == "poda":
            specialist_id = "AGENT-14-PYTHON"
        if specialist_id is not None:
            specialist_missions.setdefault(specialist_id, []).append(mission_id)

    pod_active_counts = {pod: len(ids) for pod, ids in active_ids_by_pod.items()}
    recent_complete_events = 0
    for event in recent_events:
        if hasattr(event, "new_state"):
            new_state = getattr(event, "new_state", "")
            candidate = getattr(new_state, "value", new_state)
        elif isinstance(event, dict):
            candidate = event.get("new_state", "")
        else:
            candidate = ""
        if str(candidate).upper() == "COMPLETE":
            recent_complete_events += 1
    deployment_backlog = max(len(complete_mission_ids), recent_complete_events)

    sorted_active_ids = sorted(active_mission_ids)
    sorted_verified_ids = sorted(verified_mission_ids)
    sorted_complete_ids = sorted(complete_mission_ids)
    heartbeat_map = {
        str(record.get("agent_id", "")): record
        for record in agent_heartbeats
        if isinstance(record, dict) and str(record.get("agent_id", ""))
    }
    integration_map = {
        record["agent_id"]: record
        for record in (build_agent_integration_record(agent) for agent in AGENT_REGISTRY)
    }

    agents_payload: list[dict[str, Any]] = []
    for agent in AGENT_REGISTRY:
        pod_key = _normalize_pod_name(agent.pod)
        live_record = heartbeat_map.get(agent.agent_id)
        integration_record = integration_map.get(agent.agent_id, {})
        persona_profile = integration_record.get("persona_profile", {})
        heartbeat_age_seconds: int | None = None
        heartbeat_source = "heuristic"

        if agent.category in {"interface", "executive"}:
            queue_depth = len(active_mission_ids)
            related_missions = sorted_active_ids
        elif agent.category == "support":
            if agent.short_code == "HW":
                related_missions = sorted(active_ids_by_pod.get("podb", []))
                queue_depth = len(related_missions)
            elif agent.short_code == "TESTER":
                related_missions = sorted_verified_ids
                queue_depth = len(related_missions)
            elif agent.short_code == "DEPLOY":
                related_missions = sorted_complete_ids
                queue_depth = deployment_backlog
            else:
                related_missions = sorted_active_ids
                queue_depth = len(related_missions)
        elif agent.category in {"pod_manager", "pod_audit"}:
            related_missions = sorted(active_ids_by_pod.get(pod_key, []))
            queue_depth = len(related_missions)
        else:
            related_missions = sorted(specialist_missions.get(agent.agent_id, []))
            queue_depth = len(related_missions)

        if live_record is not None:
            heartbeat_source = "live"
            state = str(live_record.get("state", "IDLE")).upper()
            queue_depth = max(0, int(live_record.get("queue_depth", 0)))
            workload_pct = min(100, max(0, int(live_record.get("workload_pct", 0))))
            live_missions = live_record.get("active_mission_ids", [])
            if isinstance(live_missions, list):
                related_missions = [
                    mission_id
                    for mission_id in (str(value) for value in live_missions)
                    if mission_id
                ][:25]
            heartbeat_iso = str(live_record.get("last_heartbeat", generated_at.isoformat()))
            heartbeat_dt = _parse_iso_datetime(heartbeat_iso)
            if heartbeat_dt is not None:
                heartbeat_age_seconds = max(0, int((generated_at - heartbeat_dt).total_seconds()))
                if heartbeat_age_seconds > AGENT_HEARTBEAT_STALE_SECONDS:
                    heartbeat_source = "stale"
                    if state not in {"ERROR", "PAUSED"}:
                        state = "PAUSED"
        else:
            state = _state_for_agent(
                category=agent.category,
                short_code=agent.short_code,
                queue_depth=queue_depth,
                runtime=runtime,
            )
            workload_pct = _workload_for_agent(
                category=agent.category,
                state=state,
                queue_depth=queue_depth,
            )
            heartbeat_iso = (generated_at - timedelta(seconds=(agent.index % 9) * 3)).isoformat()
            heartbeat_age_seconds = None

        agents_payload.append(
            {
                "index": agent.index,
                "agent_id": agent.agent_id,
                "short_code": agent.short_code,
                "name": agent.name,
                "tier": agent.tier,
                "pod": agent.pod,
                "role": agent.role,
                "category": agent.category,
                "specialties": list(agent.specialties),
                "state": state,
                "queue_depth": queue_depth,
                "workload_pct": workload_pct,
                "last_heartbeat_iso": heartbeat_iso,
                "active_mission_ids": related_missions[:25],
                "runtime_class": agent.runtime_class,
                "heartbeat_source": heartbeat_source,
                "heartbeat_age_seconds": heartbeat_age_seconds,
                "persona_profile": persona_profile if isinstance(persona_profile, dict) else {},
            }
        )

    state_counts: dict[str, int] = defaultdict(int)
    tier_counts: dict[str, int] = defaultdict(int)
    pod_counts: dict[str, int] = defaultdict(int)
    for record in agents_payload:
        state_counts[str(record["state"])] += 1
        tier_counts[str(record["tier"])] += 1
        pod_counts[str(record["pod"])] += 1

    return {
        "generated_at": generated_at.isoformat(),
        "total_agents": len(agents_payload),
        "runtime": runtime,
        "mission_backlog": {
            "active": len(active_mission_ids),
            "verified": len(verified_mission_ids),
            "complete": len(complete_mission_ids),
            "assigned_active": sum(pod_active_counts.values()),
        },
        "tier_counts": dict(sorted(tier_counts.items())),
        "pod_counts": dict(sorted(pod_counts.items())),
        "state_counts": dict(sorted(state_counts.items())),
        "agents": agents_payload,
    }


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
    
    # Optional adapter readiness with enabled/disabled awareness (return None if disabled)
    qdrant_ready = await asyncio.to_thread(qdrant_store.qdrant_ready, app.state.settings) if app.state.settings.qdrant_enabled else None
    milvus_ready = await asyncio.to_thread(milvus_store.milvus_ready, app.state.settings) if app.state.settings.milvus_enabled else None
    neo4j_ready = await asyncio.to_thread(neo4j_store.neo4j_ready, app.state.settings) if app.state.settings.neo4j_enabled else None
    object_storage_ready = await asyncio.to_thread(
        object_store.object_storage_ready, app.state.settings
    ) if app.state.settings.object_storage_enabled else None

    # Observability readiness
    jaeger_ready = None
    if os.getenv("OTEL_TRACING_ENABLED", "true").lower() in {"1", "true", "yes", "on"}:
        jaeger_ready = False
        import socket
        try:
            with socket.create_connection(("jaeger", 4318), timeout=0.5):
                jaeger_ready = True
        except Exception:
            jaeger_ready = False

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "topology_mode": app.state.settings.topology_mode,
        "runtime": {
            "redis_ready": redis_ready,
            "db_ready": db_ready,
            "qdrant_ready": qdrant_ready,
            "milvus_ready": milvus_ready,
            "neo4j_ready": neo4j_ready,
            "object_storage_ready": object_storage_ready,
            "jaeger_ready": jaeger_ready,
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
    snapshot = _build_operations_agents_snapshot(
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


@router.get("/internal/operations/projects/{project_id}/audit-events")
async def get_project_audit_events(
    request: Request,
    project_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    mission_id: str | None = Query(default=None, min_length=1),
    agent_id: str | None = Query(default=None, min_length=1),
    tool_name: str | None = Query(default=None, min_length=1),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    return await asyncio.to_thread(
        storage.list_project_agent_action_events,
        app.state.settings,
        project_id,
        limit,
        mission_id=mission_id,
        agent_id=agent_id,
        tool_name=tool_name,
    )


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
    redis_client = getattr(app.state, "redis", None) if redis_ready else None
    ack_states = await _load_alert_ack_states(redis_client, list(KNOWN_ALERT_IDS))
    return _build_operational_alerts(
        redis_ready=redis_ready,
        db_ready=db_ready,
        protocol_ready=protocol_ready,
        consumer_running=consumer_running,
        state_counts=state_counts,
        blocked_completion_count=blocked_completion_count,
        limit=limit,
        ack_states=ack_states,
    )


@router.post("/internal/operations/alerts/{alert_id}/state")
async def update_operations_alert_state(
    request: Request,
    alert_id: str,
    payload: AlertStateUpdate,
    _: AuthContext = MUTATION_AUTH_DEP,
) -> dict[str, Any]:
    """Persist an operator's acknowledge/resolve action on a synthetic alert.

    These alerts have no incident-record table (see _build_operational_alerts) —
    this only silences re-alerting for this alert_id in the operations feed
    until it clears or ALERT_ACK_TTL_SECONDS elapses, whichever comes first.
    """
    import orchestrator.main as _main

    app = request.app
    _main._initialize_app_state(app)
    redis_ready, _ = await _main.ensure_runtime_ready(app)
    redis_client = getattr(app.state, "redis", None)
    if not redis_ready or redis_client is None:
        raise HTTPException(status_code=503, detail="redis is not available to persist alert state")

    await _save_alert_ack_state(redis_client, alert_id, payload.state)
    return {"alert_id": alert_id, "state": payload.state}


@router.post("/v1/maintenance/prune-audit")
async def prune_audit(
    request: Request,
    retention_days: int | None = Query(default=None, ge=1, le=3650),
    _: AuthContext = MUTATION_AUTH_DEP,
) -> dict[str, Any]:
    """Delete audit rows older than the retention window.

    Invokes the SECURITY DEFINER ``prune_audit_tables()`` SQL function so it keeps
    working after DELETE is revoked from the application role (immutable audit).
    ``retention_days`` overrides the configured AUDIT_RETENTION_DAYS for this run.
    """
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    effective_days = retention_days or app.state.settings.audit_retention_days
    results = await asyncio.to_thread(
        storage.prune_audit_tables,
        app.state.settings,
        effective_days,
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "retention_days": effective_days,
        "total_rows_deleted": sum(int(item["rows_deleted"]) for item in results),
        "tables": results,
    }
