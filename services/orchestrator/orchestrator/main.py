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

from . import neo4j_store, object_store, qdrant_store, storage
from .agent_integrations import build_agent_integration_record, build_agent_integrations_snapshot
from .agent_registry import AGENT_REGISTRY, normalize_language
from .auth import AuthContext, require_roles
from .data_plane_metrics import observe_optional_adapter_mirror_write
from .models import (
    AgentHeartbeatUpsert,
    AuditReportUpsert,
    KnowledgeUpsert,
    LogicNodeUpsert,
    MissionCreate,
    MissionEvent,
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
LIFECYCLE_RECOVERY_RETRY_SECONDS = max(
    1.0,
    float(os.getenv("LIFECYCLE_RECOVERY_RETRY_SECONDS", "2.0")),
)
LIFECYCLE_RECOVERY_MAX_MISSIONS = max(
    100,
    int(os.getenv("LIFECYCLE_RECOVERY_MAX_MISSIONS", "2000")),
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


def _build_operational_alerts(
    *,
    redis_ready: bool,
    db_ready: bool,
    protocol_ready: bool,
    consumer_running: bool,
    state_counts: dict[str, int],
    blocked_completion_count: int,
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


def _build_mission_chain_trace(
    *,
    mission: MissionRecord,
    pod_assignment: dict[str, Any] | None,
    logicnodes: list[dict[str, Any]],
    events: list[MissionEvent],
) -> dict[str, Any]:
    metadata = mission.metadata if isinstance(mission.metadata, dict) else {}
    raw_trace = metadata.get("chain_trace")
    chain_trace = (
        [record for record in raw_trace if isinstance(record, dict)]
        if isinstance(raw_trace, list)
        else []
    )
    has_pod_assigned = any(
        str(record.get("event_type", "")).upper()
        in {"MISSION_POD_ASSIGNED", "MISSION_POD_MANAGER_ASSIGNED"}
        for record in chain_trace
    )
    if pod_assignment and not has_pod_assigned:
        chain_trace.append(
            {
                "event_type": "MISSION_POD_ASSIGNED",
                "agent_id": str(metadata.get("assigned_pod_manager_agent_id", "")),
                "ts": str(pod_assignment.get("updated_at", mission.created_at)),
                "details": {"pod_name": pod_assignment.get("pod_name")},
            }
        )
    has_logicnode_event = any(
        str(record.get("event_type", "")).upper() == "MISSION_LOGICNODE_WRITTEN"
        for record in chain_trace
    )
    if logicnodes and not has_logicnode_event:
        chain_trace.append(
            {
                "event_type": "MISSION_LOGICNODE_WRITTEN",
                "agent_id": str(metadata.get("assigned_specialist_agent_id", "")),
                "ts": str(logicnodes[0].get("created_at", mission.created_at)),
                "details": {"logicnode_count": len(logicnodes)},
            }
        )
    if not any(
        str(record.get("event_type", "")).upper() == "MISSION_COMPLETION_BLOCKED"
        for record in chain_trace
    ):
        blocked_event = next(
            (record for record in events if record.event_type == "MISSION_COMPLETION_BLOCKED"),
            None,
        )
        if blocked_event is not None:
            chain_trace.append(
                {
                    "event_type": "MISSION_COMPLETION_BLOCKED",
                    "agent_id": str(metadata.get("executive_agent_id", "")),
                    "ts": blocked_event.ts,
                    "details": {"source": "mission-events"},
                }
            )

    chain_trace = sorted(
        chain_trace,
        key=lambda record: str(record.get("ts", "")),
    )
    return {
        "mission_id": mission.mission_id,
        "routing_enforced": bool(metadata.get("routing_enforced", False)),
        "routing_version": metadata.get("routing_version"),
        "selected_agent_id": metadata.get("selected_agent_id"),
        "intake_agent_id": metadata.get("intake_agent_id"),
        "executive_agent_id": metadata.get("executive_agent_id"),
        "assigned_pod_manager_agent_id": metadata.get("assigned_pod_manager_agent_id"),
        "assigned_specialist_agent_id": metadata.get("assigned_specialist_agent_id"),
        "pod_assignment": pod_assignment,
        "logicnode_count": len(logicnodes),
        "events": chain_trace,
    }


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


async def _recover_inflight_lifecycle_tasks(app: FastAPI) -> bool:
    _initialize_app_state(app)
    settings = app.state.settings
    if not settings.auto_transition_enabled:
        app.state.lifecycle_recovery_bootstrapped = True
        app.state.lifecycle_recovery_recovered_count = 0
        app.state.lifecycle_recovery_scanned_count = 0
        app.state.lifecycle_recovery_last_at = datetime.now(UTC).isoformat()
        app.state.lifecycle_recovery_last_error = None
        return True

    redis_ready, db_ready = await ensure_runtime_ready(app)
    protocol_ready = bool(getattr(app.state, "protocol_ready", False))
    if not db_ready or not protocol_ready:
        if not db_ready:
            app.state.lifecycle_recovery_last_error = "database unavailable"
        elif not protocol_ready:
            app.state.lifecycle_recovery_last_error = "protocol unavailable"
        return False

    _ = redis_ready  # keep visible in local flow for easier diagnostics during qualification.
    recoverable_states = [
        MissionState.queued,
        MissionState.running,
        MissionState.verified,
    ]
    missions = await asyncio.to_thread(
        storage.list_missions_in_states,
        settings,
        recoverable_states,
        LIFECYCLE_RECOVERY_MAX_MISSIONS,
    )

    recovered = 0
    for mission in missions:
        task = app.state.lifecycle_tasks.get(mission.mission_id)
        if task is not None and not task.done():
            continue
        start_lifecycle_task(app, mission.mission_id)
        recovered += 1

    app.state.lifecycle_recovery_bootstrapped = True
    app.state.lifecycle_recovery_recovered_count = recovered
    app.state.lifecycle_recovery_scanned_count = len(missions)
    app.state.lifecycle_recovery_last_at = datetime.now(UTC).isoformat()
    app.state.lifecycle_recovery_last_error = None
    return True


async def lifecycle_recovery_loop(app: FastAPI) -> None:
    while True:
        try:
            recovered = await _recover_inflight_lifecycle_tasks(app)
            if recovered:
                return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            app.state.lifecycle_recovery_last_error = str(exc)
            LOGGER.exception("lifecycle recovery loop iteration failed")
        await asyncio.sleep(LIFECYCLE_RECOVERY_RETRY_SECONDS)


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

    qdrant_ready: bool | None = None
    if app.state.settings.qdrant_enabled:
        qdrant_ready = await asyncio.to_thread(qdrant_store.qdrant_ready, app.state.settings)
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
        "redis_url": app.state.settings.redis_url,
        "postgres_url": app.state.settings.postgres_url,
        "qdrant_url": app.state.settings.qdrant_url if app.state.settings.qdrant_enabled else None,
        "neo4j_url": app.state.settings.neo4j_url if app.state.settings.neo4j_enabled else None,
        "object_storage_endpoint": (
            app.state.settings.object_storage_endpoint
            if app.state.settings.object_storage_enabled
            else None
        ),
        "redis_healthy": redis_healthy,
        "db_ready": db_ready,
        "qdrant_ready": qdrant_ready,
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
        "neo4j_ready": neo4j_ready,
        "object_storage_ready": object_storage_ready,
        "protocol_ready": protocol_ready,
        "consumer_running": consumer_running,
        **_langgraph_runtime_payload(app),
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


@app.get("/internal/missions/{mission_id}/chain-trace")
async def get_chain_trace(
    mission_id: str,
    event_limit: int = Query(default=200, ge=1, le=1000),
    logicnode_limit: int = Query(default=200, ge=1, le=2000),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    await _ensure_db_ready(app)
    mission = await _fetch_existing_mission(app, mission_id)
    assignment = await asyncio.to_thread(storage.get_pod_assignment, app.state.settings, mission_id)
    logicnodes = await asyncio.to_thread(
        storage.list_logicnodes,
        app.state.settings,
        mission_id,
        logicnode_limit,
    )
    events = await asyncio.to_thread(
        storage.list_mission_events,
        app.state.settings,
        mission_id,
        event_limit,
    )
    return _build_mission_chain_trace(
        mission=mission,
        pod_assignment=assignment,
        logicnodes=logicnodes,
        events=events,
    )


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
    record = await asyncio.to_thread(
        storage.upsert_knowledge,
        app.state.settings,
        payload.mission_id,
        payload.knowledge_id,
        payload.content,
        created_at,
    )
    if app.state.settings.qdrant_enabled:
        try:
            await asyncio.to_thread(
                qdrant_store.upsert_knowledge,
                app.state.settings,
                payload.mission_id,
                payload.knowledge_id,
                payload.content,
                created_at,
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to upsert qdrant knowledge for mission %s/%s: %s",
                payload.mission_id,
                payload.knowledge_id,
                exc,
            )
    if app.state.settings.neo4j_enabled:
        try:
            await _run_optional_mirror_write(
                adapter="neo4j",
                artifact="knowledge",
                fn=neo4j_store.upsert_knowledge,
                args=(
                    app.state.settings,
                    payload.mission_id,
                    payload.knowledge_id,
                    payload.content,
                    created_at,
                ),
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to upsert neo4j knowledge for mission %s/%s: %s",
                payload.mission_id,
                payload.knowledge_id,
                exc,
            )
    return record


@app.get("/internal/missions/{mission_id}/knowledge")
async def get_knowledge(
    mission_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    await _ensure_db_ready(app)
    await _fetch_existing_mission(app, mission_id)
    if app.state.settings.qdrant_enabled:
        try:
            records = await asyncio.to_thread(
                qdrant_store.list_knowledge,
                app.state.settings,
                mission_id,
                limit,
            )
            if records:
                return records
        except Exception as exc:
            LOGGER.warning("failed to query qdrant knowledge for mission %s: %s", mission_id, exc)
    return await asyncio.to_thread(storage.list_knowledge, app.state.settings, mission_id, limit)


@app.get("/internal/missions/{mission_id}/knowledge-graph")
async def get_knowledge_graph(
    mission_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    await _ensure_db_ready(app)
    await _fetch_existing_mission(app, mission_id)
    if not app.state.settings.neo4j_enabled:
        return []
    try:
        return await asyncio.to_thread(
            neo4j_store.list_mission_graph,
            app.state.settings,
            mission_id,
            limit,
        )
    except Exception as exc:
        LOGGER.warning("failed to query neo4j graph for mission %s: %s", mission_id, exc)
        return []


@app.post("/internal/audit-reports")
async def upsert_audit_report(
    payload: AuditReportUpsert,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    await _ensure_db_ready(app)
    await _fetch_existing_mission(app, payload.mission_id)

    created_at = payload.created_at or datetime.now(UTC).isoformat()
    record = await asyncio.to_thread(
        storage.upsert_audit_report,
        app.state.settings,
        payload.mission_id,
        payload.audit_id,
        payload.status,
        payload.report,
        created_at,
    )
    if app.state.settings.neo4j_enabled:
        try:
            await _run_optional_mirror_write(
                adapter="neo4j",
                artifact="audit_report",
                fn=neo4j_store.upsert_audit_report,
                args=(
                    app.state.settings,
                    payload.mission_id,
                    payload.audit_id,
                    payload.status,
                    payload.report,
                    created_at,
                ),
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to upsert neo4j audit report for mission %s/%s: %s",
                payload.mission_id,
                payload.audit_id,
                exc,
            )
    if app.state.settings.object_storage_enabled:
        try:
            await _run_optional_mirror_write(
                adapter="object_storage",
                artifact="audit_report",
                fn=object_store.put_audit_report,
                args=(
                    app.state.settings,
                    payload.mission_id,
                    payload.audit_id,
                    payload.status,
                    payload.report,
                    created_at,
                ),
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to store audit artifact in object storage for mission %s/%s: %s",
                payload.mission_id,
                payload.audit_id,
                exc,
            )
    return record


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


@app.get("/internal/missions/{mission_id}/audit-artifacts")
async def get_audit_artifacts(
    mission_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    await _ensure_db_ready(app)
    await _fetch_existing_mission(app, mission_id)
    if not app.state.settings.object_storage_enabled:
        return []
    try:
        return await asyncio.to_thread(
            object_store.list_audit_artifacts,
            app.state.settings,
            mission_id,
            limit,
        )
    except Exception as exc:
        LOGGER.warning(
            "failed to list object-storage audit artifacts for mission %s: %s",
            mission_id,
            exc,
        )
        return []


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
    qdrant_ready = await asyncio.to_thread(qdrant_store.qdrant_ready, app.state.settings)
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
            "neo4j_ready": neo4j_ready,
            "object_storage_ready": object_storage_ready,
            "protocol_ready": protocol_ready,
            "consumer_running": consumer_running,
            **_langgraph_runtime_payload(app),
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
    qdrant_ready = await asyncio.to_thread(qdrant_store.qdrant_ready, app.state.settings)
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
        "neo4j_ready": neo4j_ready,
        "object_storage_ready": object_storage_ready,
        "protocol_ready": protocol_ready,
        "consumer_running": consumer_running,
        **_langgraph_runtime_payload(app),
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
    return _build_operational_alerts(
        redis_ready=redis_ready,
        db_ready=db_ready,
        protocol_ready=protocol_ready,
        consumer_running=consumer_running,
        state_counts=state_counts,
        blocked_completion_count=blocked_completion_count,
        limit=limit,
    )
