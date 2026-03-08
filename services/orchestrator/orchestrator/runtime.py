from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from pydantic import ValidationError

from . import storage
from .langgraph_lifecycle import maybe_advance_mission_lifecycle
from .mission_flow import (
    CEO_AGENT_ID,
    PM_AGENT_ID,
    append_chain_event,
    completion_policy_exempt,
    resolve_pod_manager_agent_id,
    resolve_specialist_agent_id,
    with_chain_defaults,
)
from .mission_flow_v2 import advance_mission_lifecycle_v2
from .models import MissionRecord, MissionState
from .protocol import EnvelopeValidator, ProtocolValidationError
from .settings import Settings

try:
    import redis.asyncio as redis
except ModuleNotFoundError:
    redis = None

try:
    from redis.exceptions import ResponseError
except ModuleNotFoundError:

    class ResponseError(Exception):
        pass


LOGGER = logging.getLogger(__name__)
RUNNING_PHASE_CHECKPOINT_EVENTS: tuple[str, ...] = (
    "MISSION_GATING",
    "MISSION_FUSION",
)


def _normalize_metadata(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


async def _prepare_mission_chain_for_running(
    *,
    app: FastAPI,
    settings: Settings,
    validator: EnvelopeValidator,
    mission_id: str,
) -> bool:
    mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    pod_manager_agent_id = resolve_pod_manager_agent_id(mission.requested_target_language)
    specialist_agent_id = resolve_specialist_agent_id(mission.requested_target_language)
    metadata["assigned_pod_manager_agent_id"] = pod_manager_agent_id
    metadata["assigned_specialist_agent_id"] = specialist_agent_id
    metadata["agent_id"] = pod_manager_agent_id
    metadata["selected_agent_id"] = pod_manager_agent_id

    existing_event_types = {
        str(entry.get("event_type", ""))
        for entry in metadata.get("chain_trace", [])
        if isinstance(entry, dict)
    }
    added_event_types: list[str] = []

    if "MISSION_PM_INTAKE" not in existing_event_types:
        append_chain_event(
            metadata,
            event_type="MISSION_PM_INTAKE",
            agent_id=PM_AGENT_ID,
            details={"source": "orchestrator-normalization"},
        )
        added_event_types.append("MISSION_PM_INTAKE")

    if "MISSION_CEO_DELEGATED" not in existing_event_types:
        append_chain_event(
            metadata,
            event_type="MISSION_CEO_DELEGATED",
            agent_id=CEO_AGENT_ID,
            details={"target_agent_id": pod_manager_agent_id},
        )
        added_event_types.append("MISSION_CEO_DELEGATED")

    if "MISSION_POD_MANAGER_ASSIGNED" not in existing_event_types:
        append_chain_event(
            metadata,
            event_type="MISSION_POD_MANAGER_ASSIGNED",
            agent_id=pod_manager_agent_id,
            details={"specialist_agent_id": specialist_agent_id},
        )
        added_event_types.append("MISSION_POD_MANAGER_ASSIGNED")

    if "MISSION_SPECIALIST_ASSIGNED" not in existing_event_types:
        append_chain_event(
            metadata,
            event_type="MISSION_SPECIALIST_ASSIGNED",
            agent_id=specialist_agent_id,
            details={"pod_manager_agent_id": pod_manager_agent_id},
        )
        added_event_types.append("MISSION_SPECIALIST_ASSIGNED")

    record = await asyncio.to_thread(
        storage.update_mission_metadata,
        settings,
        mission_id,
        metadata,
    )
    if record is None:
        return False

    for event_type in added_event_types:
        await asyncio.to_thread(
            storage.insert_mission_event,
            settings,
            mission_id,
            MissionState.queued,
            MissionState.queued,
            event_type,
        )

        redis_ready = bool(getattr(app.state, "redis_ready", False))
        redis_client = getattr(app.state, "redis", None)
        if not redis_ready or redis_client is None:
            continue
        try:
            await emit_state_event(
                settings=settings,
                validator=validator,
                redis_client=redis_client,
                mission=record,
                event_type=event_type,
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to emit chain event %s for mission %s: %s",
                event_type,
                mission_id,
                exc,
            )
    return True


async def _completion_artifacts_ready(
    *,
    settings: Settings,
    mission: MissionRecord,
) -> tuple[bool, dict[str, Any]]:
    if completion_policy_exempt(mission.metadata):
        return True, {"policy_exempt": True}

    assignment = await asyncio.to_thread(storage.get_pod_assignment, settings, mission.mission_id)
    logicnodes = await asyncio.to_thread(storage.list_logicnodes, settings, mission.mission_id, 1)
    has_assignment = bool(assignment)
    has_logicnodes = bool(logicnodes)
    return has_assignment or has_logicnodes, {
        "policy_exempt": False,
        "has_pod_assignment": has_assignment,
        "logicnode_count": len(logicnodes),
    }


async def emit_state_event(
    settings: Settings,
    validator: EnvelopeValidator,
    redis_client: Any,
    mission: MissionRecord,
    event_type: str,
) -> None:
    envelope = validator.build_state_envelope(mission, event_type)
    payload = {
        "mission_id": mission.mission_id,
        "state": mission.state.value,
        "event_type": event_type,
        "requested_target_language": mission.requested_target_language,
        "created_at": mission.created_at,
    }
    await redis_client.xadd(
        settings.state_stream,
        {
            "envelope": json.dumps(envelope),
            "payload": json.dumps(payload),
            # Legacy compatibility fields.
            "event_type": event_type,
            "mission_id": mission.mission_id,
            "state": mission.state.value,
            "created_at": mission.created_at,
        },
        maxlen=settings.max_stream_len,
        approximate=True,
    )


async def _emit_running_phase_checkpoints(
    *,
    app: FastAPI,
    settings: Settings,
    validator: EnvelopeValidator,
    mission: MissionRecord,
) -> None:
    for event_type in RUNNING_PHASE_CHECKPOINT_EVENTS:
        try:
            await asyncio.to_thread(
                storage.insert_mission_event,
                settings,
                mission.mission_id,
                MissionState.running,
                MissionState.running,
                event_type,
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to persist running checkpoint %s for mission %s: %s",
                event_type,
                mission.mission_id,
                exc,
            )
            continue

        redis_ready = bool(getattr(app.state, "redis_ready", False))
        redis_client = getattr(app.state, "redis", None)
        if not redis_ready or redis_client is None:
            continue

        try:
            await emit_state_event(
                settings=settings,
                validator=validator,
                redis_client=redis_client,
                mission=mission,
                event_type=event_type,
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to emit running checkpoint %s for mission %s: %s",
                event_type,
                mission.mission_id,
                exc,
            )


async def ensure_consumer_group(settings: Settings, redis_client: Any) -> None:
    try:
        await redis_client.xgroup_create(
            settings.intake_stream,
            settings.consumer_group,
            id="0",
            mkstream=True,
        )
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def consume_intake_stream(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    validator: EnvelopeValidator = app.state.envelope_validator
    redis_client = app.state.redis

    while True:
        try:
            streams = await redis_client.xreadgroup(
                groupname=settings.consumer_group,
                consumername=settings.consumer_name,
                streams={settings.intake_stream: ">"},
                count=20,
                block=5000,
            )
            if not streams:
                continue

            for _, entries in streams:
                for entry_id, fields in entries:
                    try:
                        payload_raw = fields.get("payload", "{}")
                        payload_json = json.loads(payload_raw)
                        validator.parse_intake_envelope(fields, payload_json)

                        mission = MissionRecord(
                            mission_id=payload_json["mission_id"],
                            prompt=payload_json["prompt"],
                            requested_target_language=payload_json.get("requested_target_language"),
                            metadata=_normalize_metadata(payload_json.get("metadata")),
                            state=MissionState.queued,
                            created_at=payload_json.get("created_at")
                            or datetime.now(UTC).isoformat(),
                        )

                        await asyncio.to_thread(storage.upsert_mission, settings, mission, entry_id)
                        await asyncio.to_thread(
                            storage.insert_mission_event,
                            settings,
                            mission.mission_id,
                            MissionState.intake,
                            MissionState.queued,
                            "MISSION_QUEUED",
                        )

                        try:
                            await emit_state_event(
                                settings=settings,
                                validator=validator,
                                redis_client=redis_client,
                                mission=mission,
                                event_type="MISSION_QUEUED",
                            )
                        except Exception as exc:
                            # Never block intake on outbound stream emission errors.
                            LOGGER.warning(
                                "failed to emit queued event for mission %s: %s",
                                mission.mission_id,
                                exc,
                            )

                        start_lifecycle_task(app, mission.mission_id)
                    except (
                        json.JSONDecodeError,
                        ValidationError,
                        ProtocolValidationError,
                        KeyError,
                        ValueError,
                    ) as exc:
                        LOGGER.warning("discarding invalid intake event %s: %s", entry_id, exc)
                    finally:
                        await redis_client.xack(
                            settings.intake_stream,
                            settings.consumer_group,
                            entry_id,
                        )
        except asyncio.CancelledError:
            raise
        except Exception:
            app.state.redis_ready = False
            await asyncio.sleep(1.0)


def start_lifecycle_task(app: FastAPI, mission_id: str) -> None:
    settings: Settings = app.state.settings
    if not settings.auto_transition_enabled:
        return

    lifecycle_tasks = app.state.lifecycle_tasks
    task = lifecycle_tasks.get(mission_id)
    if task is not None and not task.done():
        return

    new_task = asyncio.create_task(advance_mission_lifecycle(app, mission_id))
    lifecycle_tasks[mission_id] = new_task

    def _cleanup(_: asyncio.Task[Any]) -> None:
        lifecycle_tasks.pop(mission_id, None)

    new_task.add_done_callback(_cleanup)


async def advance_mission_lifecycle(app: FastAPI, mission_id: str) -> None:
    settings: Settings = app.state.settings
    validator: EnvelopeValidator = app.state.envelope_validator

    # ---- v2 11-phase engine (feature-flagged) ----
    if settings.mission_flow_v2_enabled:
        await advance_mission_lifecycle_v2(
            app=app,
            mission_id=mission_id,
            settings=settings,
            validator=validator,
            emit_state_event_fn=emit_state_event,
            prepare_chain_fn=_prepare_mission_chain_for_running,
            completion_check_fn=_completion_artifacts_ready,
        )
        return

    # ---- LangGraph engine (feature-flagged) ----
    langgraph_handled = await maybe_advance_mission_lifecycle(
        app=app,
        mission_id=mission_id,
        settings=settings,
        validator=validator,
        emit_state_event_fn=emit_state_event,
    )
    if langgraph_handled:
        return

    # ---- Legacy v1.1 engine ----
    transitions = [
        (MissionState.queued, MissionState.running, "MISSION_RUNNING"),
        (MissionState.running, MissionState.verified, "MISSION_VERIFIED"),
        (MissionState.verified, MissionState.complete, "MISSION_COMPLETE"),
    ]

    for expected_state, new_state, event_type in transitions:
        if expected_state == MissionState.queued and new_state == MissionState.running:
            prepared = await _prepare_mission_chain_for_running(
                app=app,
                settings=settings,
                validator=validator,
                mission_id=mission_id,
            )
            if not prepared:
                return

        if expected_state == MissionState.verified and new_state == MissionState.complete:
            mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
            if mission is None:
                return
            artifacts_ready, artifact_details = await _completion_artifacts_ready(
                settings=settings,
                mission=mission,
            )
            if not artifacts_ready:
                metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
                append_chain_event(
                    metadata,
                    event_type="MISSION_COMPLETION_BLOCKED",
                    agent_id=CEO_AGENT_ID,
                    details=artifact_details,
                )
                updated = await asyncio.to_thread(
                    storage.update_mission_metadata,
                    settings,
                    mission_id,
                    metadata,
                )
                if updated is not None:
                    mission = updated
                await asyncio.to_thread(
                    storage.insert_mission_event,
                    settings,
                    mission_id,
                    MissionState.verified,
                    MissionState.verified,
                    "MISSION_COMPLETION_BLOCKED",
                )
                redis_ready = bool(getattr(app.state, "redis_ready", False))
                redis_client = getattr(app.state, "redis", None)
                if redis_ready and redis_client is not None:
                    try:
                        await emit_state_event(
                            settings=settings,
                            validator=validator,
                            redis_client=redis_client,
                            mission=mission,
                            event_type="MISSION_COMPLETION_BLOCKED",
                        )
                    except Exception as exc:
                        LOGGER.warning(
                            "failed to emit completion block event for mission %s: %s",
                            mission_id,
                            exc,
                        )
                return

        await asyncio.sleep(settings.transition_step_seconds)

        record = await asyncio.to_thread(
            storage.transition_mission_state,
            settings,
            mission_id,
            expected_state,
            new_state,
            event_type,
        )
        if record is None:
            return

        redis_ready = bool(getattr(app.state, "redis_ready", False))
        redis_client = getattr(app.state, "redis", None)
        if redis_ready and redis_client is not None:
            try:
                await emit_state_event(
                    settings=settings,
                    validator=validator,
                    redis_client=redis_client,
                    mission=record,
                    event_type=event_type,
                )
            except Exception as exc:
                LOGGER.warning(
                    "failed to emit transition event %s for mission %s: %s",
                    event_type,
                    mission_id,
                    exc,
                )

        if event_type == "MISSION_RUNNING":
            await _emit_running_phase_checkpoints(
                app=app,
                settings=settings,
                validator=validator,
                mission=record,
            )


async def ensure_runtime_ready(app: FastAPI) -> tuple[bool, bool]:
    settings: Settings = app.state.settings
    protocol_ready = bool(getattr(app.state, "protocol_ready", False))

    lock = getattr(app.state, "startup_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        app.state.startup_lock = lock

    if getattr(app.state, "lifecycle_tasks", None) is None:
        app.state.lifecycle_tasks = {}

    if getattr(app.state, "redis_ready", None) is None:
        app.state.redis_ready = False

    if getattr(app.state, "db_ready", None) is None:
        app.state.db_ready = False

    async with lock:
        redis_client = getattr(app.state, "redis", None)
        redis_ready = bool(getattr(app.state, "redis_ready", False))
        db_ready = bool(getattr(app.state, "db_ready", False))

        if redis is not None and redis_client is None:
            redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            app.state.redis = redis_client

        if redis_client is not None and not redis_ready:
            try:
                redis_ready = bool(await redis_client.ping())
            except Exception:
                redis_ready = False
            app.state.redis_ready = redis_ready

        if not db_ready:
            try:
                await asyncio.to_thread(storage.ensure_db_schema, settings)
                db_ready = True
            except Exception:
                db_ready = False
            app.state.db_ready = db_ready

        consumer_task = getattr(app.state, "consumer_task", None)
        consumer_running = consumer_task is not None and not consumer_task.done()

        if (
            protocol_ready
            and redis_ready
            and db_ready
            and not consumer_running
            and redis_client is not None
        ):
            try:
                await ensure_consumer_group(settings, redis_client)
                app.state.consumer_task = asyncio.create_task(consume_intake_stream(app))
            except Exception:
                app.state.consumer_task = None

        return redis_ready, db_ready


async def runtime_self_heal_loop(app: FastAPI) -> None:
    while True:
        try:
            await ensure_runtime_ready(app)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("runtime self-heal iteration failed")
        await asyncio.sleep(2.0)
