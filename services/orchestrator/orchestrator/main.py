from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from shared_runtime.errors import ErrorSeverity, FactoryError
from shared_runtime.logging_config import configure_logging

from . import milvus_store, neo4j_store, object_store, qdrant_store, storage
from .agent_integrations import build_agent_integration_record
from .agent_registry import (  # noqa: F401  (used by callers via _main)
    AGENT_REGISTRY,
    normalize_language,
)
from .auth import require_roles
from .data_plane_metrics import observe_optional_adapter_mirror_write
from .heartbeat_service import (
    AGENT_AUTOFILL_NON_POD_HEARTBEATS,
    AGENT_HEARTBEAT_INTERVAL_SECONDS,
    AGENT_HEARTBEAT_STALE_SECONDS,  # noqa: F401
)
from .lifecycle_recovery import lifecycle_recovery_loop
from .models import (
    AgentHeartbeatUpsert,  # noqa: F401
    MissionRecord,
    MissionState,
)
from .orchestrator_metrics import REQUEST_COUNTER, REQUEST_LATENCY
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
    stale_consumer_reap_loop,
    start_lifecycle_task,  # noqa: F401  (re-exported for route modules)
)
from .settings import load_settings
from .tracing import configure_tracing, current_trace_id

configure_logging("orchestrator")
LOGGER = logging.getLogger(__name__)

SETTINGS = load_settings()
MUTATION_AUTH = require_roles(SETTINGS, {"mutate", "admin", "worker"})
INTERNAL_AUTH = require_roles(SETTINGS, {"internal", "admin", "worker"})
READ_AUTH = require_roles(SETTINGS, {"read", "mutate", "admin", "worker", "internal"})
MUTATION_AUTH_DEP = Depends(MUTATION_AUTH)
INTERNAL_AUTH_DEP = Depends(INTERNAL_AUTH)
READ_AUTH_DEP = Depends(READ_AUTH)


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
    if getattr(app.state, "protocol_bus_consumer_task", None) is None:
        app.state.protocol_bus_consumer_task = None
    if getattr(app.state, "protocol_bus_consumer", None) is None:
        app.state.protocol_bus_consumer = None
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
        except Exception as exc:  # pragma: no cover - deployment misconfiguration
            # A malformed/unreadable schema or topics file must not crash the
            # process at import or startup — degrade to not-ready and let the
            # self-heal loop retry so the orchestrator can still serve /health.
            app.state.protocol_ready = False
            app.state.protocol_error = f"{type(exc).__name__}: {exc}"
            LOGGER.error("failed to load envelope validator at startup: %s", exc)

    # Warm the LogicNode schema validator once so the /internal/logicnodes
    # write boundary validates many nodes without re-reading the schema file.
    if getattr(app.state, "logicnode_schema_ready", None) is None:
        from .logicnode_schema import _load_validator

        try:
            _load_validator(str(app.state.settings.logicnode_schema_path))
            app.state.logicnode_schema_ready = True
        except Exception as exc:  # pragma: no cover - deployment misconfiguration
            app.state.logicnode_schema_ready = False
            LOGGER.error("failed to load logicnode schema at startup: %s", exc)


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


async def knowledge_lake_refresh_loop(app: FastAPI) -> None:
    """Periodically refresh bootstrap docs for all supported languages in the knowledge lake."""
    from .is_agent import SUPPORTED_LANGUAGES, run_fetch_phase  # noqa: PLC0415
    while True:
        try:
            settings = app.state.settings
            interval = getattr(settings, "knowledge_refresh_interval_seconds", 3600)
            await asyncio.sleep(interval)
            
            _, db_ready = await ensure_runtime_ready(app)
            if not db_ready:
                continue

            LOGGER.info("Starting background auto-refresh for knowledge lake bootstrap documents.")
            await run_fetch_phase(
                mission_id="system-knowledge-lake",
                required_languages=list(SUPPORTED_LANGUAGES),
                settings=settings,
            )
            LOGGER.info(
                "Background auto-refresh for knowledge lake bootstrap documents completed."
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("knowledge lake refresh loop iteration failed")


# Agent identity the orchestrator uses when subscribing to the Protocol Bus.
# AGENT-03-BROKER is the message-broker agent in the registry — the natural
# orchestrator-side consumer identity for the typed protocol lanes.
ORCHESTRATOR_BUS_AGENT_ID = "AGENT-03-BROKER"


async def _handle_sigma_knowledge_ready(message: dict[str, Any]) -> None:
    """Sigma lane handler: confirm Knowledge Lake availability on a ready event.

    The IS-Agent broadcasts a Sigma ``knowledge_ready`` event after FETCH indexes
    bootstrap docs. On receipt we re-check ``is_stocked`` against PostgreSQL (the
    source of truth) and log confirmed availability so a silent write/broadcast
    divergence surfaces in the logs rather than only on the producer side.
    """
    from .knowledge_lake import is_stocked  # noqa: PLC0415

    payload = message.get("payload") or {}
    content = payload.get("content") if isinstance(payload, dict) else None
    content = content if isinstance(content, dict) else {}
    mission_id = str(content.get("mission_id") or "")
    languages = content.get("languages")
    languages = languages if isinstance(languages, list) else []

    if not mission_id:
        LOGGER.debug("Sigma knowledge_ready event without mission_id; ignoring")
        return

    settings = app.state.settings
    stocked = await asyncio.to_thread(is_stocked, settings=settings, mission_id=mission_id)
    if stocked:
        LOGGER.info(
            "Sigma knowledge_ready confirmed: mission=%s languages=%s knowledge present in lake",
            mission_id,
            languages,
        )
    else:
        LOGGER.warning(
            "Sigma knowledge_ready received for mission=%s but no rows found in storage "
            "(possible write/broadcast divergence)",
            mission_id,
        )


async def protocol_bus_consumer_loop(app: FastAPI) -> None:
    """Run the Protocol Bus consumer, restarting it if the Redis client rotates.

    Subscribes the orchestrator to the Sigma lane (knowledge-ready events). The
    consumer is resilient: it waits for the async Redis client to be ready and
    restarts on transient failures without crashing the lifespan.
    """
    from .protocol_bus_consumer import ProtocolBusConsumer  # noqa: PLC0415

    settings = app.state.settings
    if not getattr(settings, "protocol_bus_consumer_enabled", True):
        LOGGER.info("Protocol Bus consumer disabled via PROTOCOL_BUS_CONSUMER_ENABLED")
        return

    handlers = {"sigma": _handle_sigma_knowledge_ready}

    while True:
        try:
            redis_ready, _ = await ensure_runtime_ready(app)
            redis_client = getattr(app.state, "redis", None)
            if not redis_ready or redis_client is None:
                await asyncio.sleep(2.0)
                continue

            consumer = ProtocolBusConsumer(
                redis_client=redis_client,
                agent_id=ORCHESTRATOR_BUS_AGENT_ID,
                handlers=handlers,
                use_consumer_group=bool(
                    getattr(settings, "event_driven_control_plane_enabled", False)
                ),
                consumer_group="protocol-bus-orchestrator",
                consumer_name=ORCHESTRATOR_BUS_AGENT_ID,
            )
            app.state.protocol_bus_consumer = consumer
            await consumer.start()
            # start() only returns when the consumer stops (e.g. all lanes
            # errored out); loop back to re-establish after a short pause.
            await asyncio.sleep(2.0)
        except asyncio.CancelledError:
            consumer = getattr(app.state, "protocol_bus_consumer", None)
            if consumer is not None:
                consumer.stop()
            raise
        except Exception:
            LOGGER.exception("protocol bus consumer loop iteration failed")
            await asyncio.sleep(2.0)


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


def _normalize_pod_name(value: str) -> str:
    return value.strip().lower().replace(" ", "").replace("-", "").replace("_", "")


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


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
                "runtime_class": agent.runtime_class,
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
    asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=20))
    _initialize_app_state(app)

    try:
        storage.init_connection_pool(app.state.settings)
    except Exception:
        # Fail open: if the pool cannot be created at boot (dependency missing
        # or DB unreachable), readiness stays false via ensure_runtime_ready and
        # the self-heal loop retries. Storage calls surface the error lazily.
        LOGGER.warning("connection pool initialization failed at startup", exc_info=True)

    try:
        await ensure_runtime_ready(app)
    except Exception:
        # ensure_runtime_ready is internally fail-open, but never let a startup
        # readiness probe crash the lifespan — the self-heal loop retries.
        LOGGER.warning("initial ensure_runtime_ready failed at startup", exc_info=True)

    # Load versioned prompt assets into registry. Non-fatal: a missing or
    # malformed prompt-assets directory must degrade (no prompts registered)
    # rather than crash startup.
    from .prompt_registry import load_prompt_assets  # noqa: PLC0415
    try:
        await asyncio.to_thread(load_prompt_assets)
    except Exception:
        LOGGER.warning("prompt asset loading failed at startup", exc_info=True)

    app.state.lifecycle_recovery_task = asyncio.create_task(lifecycle_recovery_loop(app))
    app.state.self_heal_task = asyncio.create_task(runtime_self_heal_loop(app))
    app.state.agent_heartbeat_task = asyncio.create_task(agent_heartbeat_loop(app))
    app.state.knowledge_refresh_task = asyncio.create_task(knowledge_lake_refresh_loop(app))
    app.state.stale_consumer_reap_task = asyncio.create_task(stale_consumer_reap_loop(app))
    app.state.protocol_bus_consumer_task = asyncio.create_task(
        protocol_bus_consumer_loop(app)
    )

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

    knowledge_refresh_task = getattr(app.state, "knowledge_refresh_task", None)
    if knowledge_refresh_task is not None:
        knowledge_refresh_task.cancel()
        with suppress(asyncio.CancelledError):
            await knowledge_refresh_task

    stale_consumer_reap_task = getattr(app.state, "stale_consumer_reap_task", None)
    if stale_consumer_reap_task is not None:
        stale_consumer_reap_task.cancel()
        with suppress(asyncio.CancelledError):
            await stale_consumer_reap_task

    protocol_bus_consumer_task = getattr(app.state, "protocol_bus_consumer_task", None)
    if protocol_bus_consumer_task is not None:
        protocol_bus_consumer_task.cancel()
        with suppress(asyncio.CancelledError):
            await protocol_bus_consumer_task

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

    storage.close_connection_pool()


app = FastAPI(title="HolyGrail Orchestrator", version="0.3.0", lifespan=lifespan)
configure_tracing(app, service_name="orchestrator")
_initialize_app_state(app)


# Map standard-error severities to HTTP status codes (Local-First Error Handling Standard).
_SEVERITY_STATUS = {
    ErrorSeverity.INFO: 200,
    ErrorSeverity.WARNING: 400,
    ErrorSeverity.RECOVERABLE: 400,
    ErrorSeverity.CRITICAL: 500,
    ErrorSeverity.FATAL: 500,
}


@app.exception_handler(FactoryError)
async def _factory_error_handler(request: Request, exc: FactoryError) -> JSONResponse:
    """Render a FactoryError as the secret-free user payload; log the full object.

    The user payload ({user_message, recovery_action, error_code}) is what Mission
    Control's parseError() upgrades into the four-line standard display. The full
    standard object (with developer_message) goes to structured logs only.
    """
    if exc.correlation_id is None:
        exc.correlation_id = _request_correlation_id(request)
    LOGGER.warning("FactoryError %s: %s", exc.error_code, exc.to_dict())
    status = _SEVERITY_STATUS.get(exc.severity, 500)
    return JSONResponse(status_code=status, content={"detail": exc.to_user_payload()})


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

    jaeger_ready = None
    if os.getenv("OTEL_TRACING_ENABLED", "true").lower() in {"1", "true", "yes", "on"}:
        jaeger_ready = False
        # Simple reachability check for Jaeger OTLP port
        import socket
        try:
            with socket.create_connection(("jaeger", 4318), timeout=0.5):
                jaeger_ready = True
        except Exception:
            jaeger_ready = False

    # Cross-reference AGENT_REGISTRY against recent heartbeats so missing agents
    # are visible at the /health endpoint rather than only surfacing when a mission stalls.
    agents_with_heartbeat: list[str] = []
    agents_missing_heartbeat: list[str] = []
    if db_ready:
        try:
            heartbeats = await asyncio.to_thread(
                storage.list_agent_heartbeats, app.state.settings, limit=200
            )
            live_ids = {
                str(h.get("agent_id", "")) for h in heartbeats if isinstance(h, dict)
            }
            for _agent in AGENT_REGISTRY:
                if _agent.agent_id in live_ids:
                    agents_with_heartbeat.append(_agent.agent_id)
                else:
                    agents_missing_heartbeat.append(_agent.agent_id)
            if agents_missing_heartbeat:
                LOGGER.debug(
                    "health check: %d/%d agents have no recent heartbeat: %s",
                    len(agents_missing_heartbeat),
                    len(AGENT_REGISTRY),
                    agents_missing_heartbeat[:10],
                )
        except Exception as exc:
            LOGGER.debug("health check: agent heartbeat query failed: %s", exc)

    return {
        "ok": True,
        "service": "orchestrator",
        "redis_healthy": redis_healthy,
        "db_ready": db_ready,
        "qdrant_ready": qdrant_ready,
        "milvus_ready": milvus_ready,
        "neo4j_ready": neo4j_ready,
        "neo4j_url": app.state.settings.neo4j_url if app.state.settings.neo4j_enabled else None,
        "object_storage_ready": object_storage_ready,
        "object_storage_endpoint": app.state.settings.object_storage_endpoint if app.state.settings.object_storage_enabled else None,
        "jaeger_ready": jaeger_ready,
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
        "agents_total": len(AGENT_REGISTRY),
        "agents_with_heartbeat": len(agents_with_heartbeat),
        "agents_missing_heartbeat": len(agents_missing_heartbeat),
        "agents_missing_ids": agents_missing_heartbeat if agents_missing_heartbeat else None,
        **_langgraph_runtime_payload(app),
    }


@app.get("/livez")
async def livez() -> dict[str, Any]:
    """Liveness probe — returns 200 as soon as the process can serve a request.

    This is the signal the Docker healthcheck and the ``depends_on`` chain gate
    on. Unlike ``/health`` — which additionally issues live readiness probes to
    the optional backends (Qdrant/Milvus/Neo4j/object storage) plus several DB
    queries, making it slow under cold-start contention and prone to exceeding
    the healthcheck timeout — ``/livez`` performs no blocking probes. It only
    reflects cached core-dependency state. ``/health`` and ``/readyz`` keep their
    full payloads; ``/readyz`` remains the strict readiness signal that gates on
    optional-backend reachability.
    """
    _initialize_app_state(app)
    return {
        "ok": True,
        "service": "orchestrator",
        "live": True,
        "db_ready": bool(getattr(app.state, "db_ready", False)),
        "redis_ready": bool(getattr(app.state, "redis_ready", False)),
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
