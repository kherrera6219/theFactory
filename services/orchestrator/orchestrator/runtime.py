from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from pydantic import ValidationError

from . import storage
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


def _normalize_metadata(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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

    transitions = [
        (MissionState.queued, MissionState.running, "MISSION_RUNNING"),
        (MissionState.running, MissionState.verified, "MISSION_VERIFIED"),
        (MissionState.verified, MissionState.complete, "MISSION_COMPLETE"),
    ]

    for expected_state, new_state, event_type in transitions:
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
                "failed to emit transition event %s for mission %s: %s",
                event_type,
                mission_id,
                exc,
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
