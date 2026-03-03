from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from . import storage
from .agent_integrations import build_agent_integration_record, build_agent_integrations_snapshot
from .agent_registry import AGENT_REGISTRY, normalize_language
from .auth import AuthContext, require_roles
from .models import (
    AgentHeartbeatUpsert,
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

AGENT_HEARTBEAT_INTERVAL_SECONDS = max(
    2.0,
    float(os.getenv("AGENT_HEARTBEAT_INTERVAL_SECONDS", "5")),
)
AGENT_HEARTBEAT_STALE_SECONDS = max(
    10,
    int(os.getenv("AGENT_HEARTBEAT_STALE_SECONDS", "45")),
)
AGENT_AUTOFILL_NON_POD_HEARTBEATS = (
    os.getenv("AGENT_AUTOFILL_NON_POD_HEARTBEATS", "true").strip().lower()
    in {"1", "true", "yes", "on"}
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
    if getattr(app.state, "agent_heartbeat_task", None) is None:
        app.state.agent_heartbeat_task = None
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


def _build_operational_alerts(
    *,
    redis_ready: bool,
    db_ready: bool,
    protocol_ready: bool,
    consumer_running: bool,
    state_counts: dict[str, int],
    limit: int,
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

    return alerts[:limit]


def _normalize_pod_name(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    return normalized


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


async def _emit_agent_telemetry_event(
    app: FastAPI,
    *,
    record: dict[str, Any],
    event_type: str,
) -> None:
    validator = getattr(app.state, "envelope_validator", None)
    redis_client = getattr(app.state, "redis", None)
    protocol_ready = bool(getattr(app.state, "protocol_ready", False))
    redis_ready = bool(getattr(app.state, "redis_ready", False))
    if validator is None or redis_client is None or not protocol_ready or not redis_ready:
        return

    topic = "agent.state.changed" if event_type == "AGENT_STATE_CHANGED" else "agent.heartbeat"
    metadata = record.get("metadata", {})
    producer = "orchestrator-runtime"
    if isinstance(metadata, dict):
        candidate = metadata.get("producer")
        if isinstance(candidate, str) and candidate.strip():
            producer = candidate.strip()

    event_ts = datetime.now(UTC).isoformat()
    agent_id = str(record.get("agent_id", ""))
    envelope = {
        "event_id": f"evt-{uuid.uuid4()}",
        "topic": topic,
        "timestamp": event_ts,
        "producer": producer,
        "correlation_id": agent_id,
        "payload_ref": f"registry://agents/{agent_id}/runtime/{event_type.lower()}",
        "schema": "agents.telemetry.v1",
        "priority": "HIGH" if str(record.get("state", "")).upper() == "ERROR" else "NORMAL",
    }

    try:
        validator.validate(envelope)
    except Exception as exc:
        LOGGER.warning("failed to validate agent telemetry envelope for %s: %s", agent_id, exc)
        return

    payload = {
        "agent_id": agent_id,
        "event_type": event_type,
        "state": str(record.get("state", "IDLE")).upper(),
        "queue_depth": int(record.get("queue_depth", 0)),
        "workload_pct": int(record.get("workload_pct", 0)),
        "active_mission_ids": record.get("active_mission_ids", []),
        "last_heartbeat": record.get("last_heartbeat", event_ts),
        "metadata": metadata if isinstance(metadata, dict) else {},
    }
    await redis_client.xadd(
        app.state.settings.state_stream,
        {
            "envelope": json.dumps(envelope),
            "payload": json.dumps(payload),
            "event_type": event_type,
            "agent_id": agent_id,
            "state": payload["state"],
        },
        maxlen=app.state.settings.max_stream_len,
        approximate=True,
    )


async def _upsert_agent_heartbeat(
    app: FastAPI,
    payload: AgentHeartbeatUpsert,
    *,
    emit_stream_event: bool,
) -> dict[str, Any]:
    last_heartbeat = payload.last_heartbeat or datetime.now(UTC).isoformat()
    record = await asyncio.to_thread(
        storage.upsert_agent_heartbeat,
        app.state.settings,
        payload.agent_id,
        payload.state,
        payload.queue_depth,
        payload.workload_pct,
        payload.active_mission_ids,
        payload.metadata,
        last_heartbeat,
    )
    if emit_stream_event:
        event_type = (
            "AGENT_STATE_CHANGED"
            if bool(record.get("state_changed"))
            else "AGENT_HEARTBEAT"
        )
        try:
            await _emit_agent_telemetry_event(app, record=record, event_type=event_type)
        except Exception as exc:
            LOGGER.warning(
                "failed to emit agent telemetry event for %s: %s",
                payload.agent_id,
                exc,
            )
    return record


def _build_non_pod_heartbeat_payloads(
    *,
    runtime: dict[str, bool],
    missions: list[MissionRecord],
) -> list[AgentHeartbeatUpsert]:
    active_states = {MissionState.queued, MissionState.running, MissionState.verified}
    active_missions = [mission for mission in missions if mission.state in active_states]
    verified_missions = [mission for mission in missions if mission.state == MissionState.verified]
    complete_missions = [mission for mission in missions if mission.state == MissionState.complete]
    active_ids = sorted({mission.mission_id for mission in active_missions})
    verified_ids = sorted({mission.mission_id for mission in verified_missions})
    complete_ids = sorted({mission.mission_id for mission in complete_missions})

    systems_languages = {"go", "rust", "c", "cpp", "zig"}
    systems_ids: list[str] = []
    for mission in active_missions:
        normalized_language = normalize_language(mission.requested_target_language)
        if normalized_language in systems_languages:
            systems_ids.append(mission.mission_id)
    systems_ids = sorted(set(systems_ids))

    payloads: list[AgentHeartbeatUpsert] = []
    for agent in AGENT_REGISTRY:
        if agent.category not in {"interface", "executive", "support"}:
            continue

        if agent.category in {"interface", "executive"}:
            related = active_ids
        elif agent.short_code == "TESTER":
            related = verified_ids
        elif agent.short_code == "DEPLOY":
            related = complete_ids
        elif agent.short_code == "HW":
            related = systems_ids
        else:
            related = active_ids

        queue_depth = len(related)
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
        payloads.append(
            AgentHeartbeatUpsert(
                agent_id=agent.agent_id,
                state=state,
                queue_depth=queue_depth,
                workload_pct=workload_pct,
                active_mission_ids=related[:25],
                metadata={
                    "source": "orchestrator-autofill",
                    "producer": "orchestrator-autofill",
                    "tier": agent.tier,
                    "pod": agent.pod,
                    "category": agent.category,
                    "role": agent.role,
                },
            )
        )
    return payloads


async def agent_heartbeat_loop(app: FastAPI) -> None:
    while True:
        try:
            if not AGENT_AUTOFILL_NON_POD_HEARTBEATS:
                await asyncio.sleep(AGENT_HEARTBEAT_INTERVAL_SECONDS)
                continue

            _initialize_app_state(app)
            _, db_ready = await ensure_runtime_ready(app)
            if not db_ready:
                await asyncio.sleep(AGENT_HEARTBEAT_INTERVAL_SECONDS)
                continue

            missions = await asyncio.to_thread(storage.list_missions, app.state.settings, 2000)
            consumer_task = getattr(app.state, "consumer_task", None)
            runtime = {
                "redis_ready": bool(getattr(app.state, "redis_ready", False)),
                "db_ready": bool(getattr(app.state, "db_ready", False)),
                "protocol_ready": bool(getattr(app.state, "protocol_ready", False)),
                "consumer_running": bool(consumer_task is not None and not consumer_task.done()),
            }
            payloads = _build_non_pod_heartbeat_payloads(runtime=runtime, missions=missions)
            for payload in payloads:
                await _upsert_agent_heartbeat(app, payload, emit_stream_event=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("agent heartbeat loop iteration failed")

        await asyncio.sleep(AGENT_HEARTBEAT_INTERVAL_SECONDS)


def _state_for_agent(
    *,
    category: str,
    short_code: str,
    queue_depth: int,
    runtime: dict[str, bool],
) -> str:
    if not runtime["db_ready"]:
        return "ERROR"
    if not runtime["protocol_ready"] and category in {"executive", "pod_manager", "pod_audit"}:
        return "ERROR"
    if not runtime["redis_ready"] and short_code in {"BROKER", "IS", "CEO"}:
        return "ERROR"
    if not runtime["consumer_running"] and category in {"executive", "pod_manager"}:
        return "PAUSED"
    if queue_depth <= 0:
        return "IDLE"
    if category == "pod_audit" or short_code in {"SECURITY", "COMPLIANCE", "TESTER"}:
        return "VERIFYING"
    if category in {"interface", "executive", "pod_manager"}:
        return "RUNNING"
    return "ACTIVE"


def _workload_for_agent(*, category: str, state: str, queue_depth: int) -> int:
    if state == "ERROR":
        return 0
    if state == "PAUSED":
        return min(100, max(12, queue_depth * 8))
    if queue_depth <= 0:
        return 6

    multipliers = {
        "interface": 14,
        "executive": 12,
        "support": 9,
        "pod_manager": 12,
        "pod_audit": 11,
        "specialist": 16,
    }
    base = {"RUNNING": 42, "VERIFYING": 36, "ACTIVE": 34}.get(state, 28)
    return min(100, base + queue_depth * multipliers.get(category, 10))


def _build_operations_agents_snapshot(
    *,
    generated_at: datetime,
    runtime: dict[str, bool],
    missions: list[MissionRecord],
    pod_assignments: list[dict[str, Any]],
    recent_events: list[Any],
    agent_heartbeats: list[dict[str, Any]],
) -> dict[str, Any]:
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    _initialize_app_state(app)

    await ensure_runtime_ready(app)
    app.state.self_heal_task = asyncio.create_task(runtime_self_heal_loop(app))
    app.state.agent_heartbeat_task = asyncio.create_task(agent_heartbeat_loop(app))

    yield

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
configure_tracing(app, service_name="orchestrator")
_initialize_app_state(app)


@app.middleware("http")
async def _request_metrics(request, call_next):
    started = time.perf_counter()
    method = request.method
    status_code = "500"
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
        "agent_heartbeat_task_running": bool(
            agent_heartbeat_task is not None and not agent_heartbeat_task.done()
        ),
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


@app.post("/internal/agents/heartbeat")
async def upsert_agent_heartbeat(
    payload: AgentHeartbeatUpsert,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    await _ensure_db_ready(app)
    return await _upsert_agent_heartbeat(app, payload, emit_stream_event=True)


@app.get("/internal/operations/summary")
async def get_operations_summary(
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    _initialize_app_state(app)
    redis_ready, db_ready = await ensure_runtime_ready(app)
    state_counts = await asyncio.to_thread(storage.mission_state_counts, app.state.settings)
    pod_assignments = await asyncio.to_thread(storage.list_pod_assignments, app.state.settings, 500)

    pod_counts: dict[str, int] = {}
    for record in pod_assignments:
        pod_name = str(record.get("pod_name", "unknown"))
        pod_counts[pod_name] = pod_counts.get(pod_name, 0) + 1

    protocol_ready = bool(getattr(app.state, "protocol_ready", False))
    consumer_task = getattr(app.state, "consumer_task", None)
    consumer_running = consumer_task is not None and not consumer_task.done()

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "runtime": {
            "redis_ready": redis_ready,
            "db_ready": db_ready,
            "protocol_ready": protocol_ready,
            "consumer_running": consumer_running,
        },
        "mission_state_counts": state_counts,
        "pod_assignment_counts": pod_counts,
        "active_lifecycle_tasks": len(getattr(app.state, "lifecycle_tasks", {})),
    }


@app.get("/internal/operations/agents")
async def get_operations_agents(
    mission_limit: int = Query(default=1000, ge=50, le=5000),
    assignment_limit: int = Query(default=1000, ge=50, le=5000),
    event_limit: int = Query(default=300, ge=50, le=2000),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    _initialize_app_state(app)
    redis_ready, db_ready = await ensure_runtime_ready(app)
    protocol_ready = bool(getattr(app.state, "protocol_ready", False))
    consumer_task = getattr(app.state, "consumer_task", None)
    consumer_running = consumer_task is not None and not consumer_task.done()

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
        "protocol_ready": protocol_ready,
        "consumer_running": consumer_running,
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


@app.get("/internal/operations/agent-integrations")
async def get_operations_agent_integrations(
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    return build_agent_integrations_snapshot()


@app.get("/internal/operations/events")
async def get_operations_events(
    limit: int = Query(default=200, ge=1, le=1000),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    await _ensure_db_ready(app)
    events = await asyncio.to_thread(storage.list_recent_mission_events, app.state.settings, limit)
    return [event.model_dump() for event in events]


@app.get("/internal/operations/agent-events")
async def get_operations_agent_events(
    limit: int = Query(default=200, ge=1, le=1000),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    await _ensure_db_ready(app)
    return await asyncio.to_thread(storage.list_recent_agent_events, app.state.settings, limit)


@app.get("/internal/operations/logicnodes")
async def get_operations_logicnodes(
    limit: int = Query(default=200, ge=1, le=1000),
    mission_id: str | None = Query(default=None, min_length=1),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    await _ensure_db_ready(app)
    if mission_id:
        await _fetch_existing_mission(app, mission_id)
        return await asyncio.to_thread(
            storage.list_logicnodes,
            app.state.settings,
            mission_id,
            limit,
        )
    return await asyncio.to_thread(storage.list_recent_logicnodes, app.state.settings, limit)


@app.get("/internal/operations/pod-assignments")
async def get_operations_pod_assignments(
    limit: int = Query(default=200, ge=1, le=1000),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    await _ensure_db_ready(app)
    return await asyncio.to_thread(storage.list_pod_assignments, app.state.settings, limit)


@app.get("/internal/operations/projects")
async def get_operations_projects(
    limit: int = Query(default=100, ge=1, le=500),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    await _ensure_db_ready(app)
    return await asyncio.to_thread(storage.summarize_projects, app.state.settings, limit)


@app.get("/internal/operations/alerts")
async def get_operations_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    _initialize_app_state(app)
    redis_ready, db_ready = await ensure_runtime_ready(app)
    state_counts = await asyncio.to_thread(storage.mission_state_counts, app.state.settings)
    protocol_ready = bool(getattr(app.state, "protocol_ready", False))
    consumer_task = getattr(app.state, "consumer_task", None)
    consumer_running = consumer_task is not None and not consumer_task.done()
    return _build_operational_alerts(
        redis_ready=redis_ready,
        db_ready=db_ready,
        protocol_ready=protocol_ready,
        consumer_running=consumer_running,
        state_counts=state_counts,
        limit=limit,
    )
