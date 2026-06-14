"""heartbeat_service.py — Agent heartbeat autofill loop and state-computation helpers.

Responsibilities
----------------
- Emit synthetic heartbeats for non-pod agents (interface / executive / support)
  on a configurable interval (``AGENT_HEARTBEAT_INTERVAL_SECONDS``).
- Compute deterministic ``state`` and ``workload_pct`` for each agent based on
  queue depth and runtime readiness flags.
- Write heartbeat records to storage and emit Redis stream events.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI

from . import storage
from .agent_registry import AGENT_REGISTRY, normalize_language
from .models import AgentHeartbeatUpsert, MissionRecord, MissionState
from .runtime import ensure_runtime_ready

LOGGER = logging.getLogger(__name__)

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

# agent-runtime sends heartbeats on the same AGENT_HEARTBEAT_INTERVAL_SECONDS env var
# but defaults to 15 s (vs the orchestrator's 5 s default). The stale threshold must
# exceed the maximum possible interval to prevent agents from appearing spuriously stale.
_MIN_SAFE_STALE_SECONDS = max(AGENT_HEARTBEAT_INTERVAL_SECONDS * 3, 20)
if AGENT_HEARTBEAT_STALE_SECONDS < _MIN_SAFE_STALE_SECONDS:
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "AGENT_HEARTBEAT_STALE_SECONDS=%d is less than 3× the orchestrator heartbeat "
        "interval (%gs). pod/specialist agents using a longer heartbeat interval "
        "(default 15 s) may appear spuriously stale. Recommend >= %d s.",
        AGENT_HEARTBEAT_STALE_SECONDS,
        AGENT_HEARTBEAT_INTERVAL_SECONDS,
        int(_MIN_SAFE_STALE_SECONDS),
    )


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

            from .main import _initialize_app_state  # lazy to avoid circular import

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
