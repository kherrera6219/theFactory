from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from pydantic import ValidationError

from . import build_artifacts as build_artifact_support
from . import storage
from .lifecycle_interface import get_lifecycle_engine
from .mission_flow import (
    CEO_AGENT_ID,
    PM_AGENT_ID,
    append_chain_event,
    completion_policy_exempt,
    resolve_pod_manager_agent_id,
    resolve_specialist_agent_id,
    with_chain_defaults,
)
from .models import MissionRecord, MissionState
from .protocol import EnvelopeValidator, ProtocolValidationError
from .settings import Settings

try:
    import redis.asyncio as redis
except ModuleNotFoundError:
    redis = None

try:
    from redis.exceptions import ResponseError, TimeoutError as RedisTimeoutError
except ModuleNotFoundError:

    class ResponseError(Exception):
        pass

    class RedisTimeoutError(Exception):
        pass


LOGGER = logging.getLogger(__name__)
RUNNING_PHASE_CHECKPOINT_EVENTS: tuple[str, ...] = (
    "MISSION_GATING",
    "MISSION_FUSION",
)


def _normalize_metadata(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _state_event_agent_routing(mission: MissionRecord, event_type: str) -> dict[str, Any]:
    metadata = _normalize_metadata(mission.metadata)
    pod_manager_agent_id = str(
        metadata.get("assigned_pod_manager_agent_id")
        or metadata.get("expected_pod_manager_agent_id")
        or resolve_pod_manager_agent_id(mission.requested_target_language)
    ).strip()
    specialist_agent_id = str(
        metadata.get("assigned_specialist_agent_id")
        or metadata.get("expected_specialist_agent_id")
        or resolve_specialist_agent_id(mission.requested_target_language)
    ).strip()

    routed_agent_id = ""
    if event_type == "MISSION_PM_INTAKE":
        routed_agent_id = PM_AGENT_ID
    elif event_type in {"MISSION_CEO_DELEGATED", "MISSION_COMPLETION_BLOCKED"}:
        routed_agent_id = CEO_AGENT_ID
    elif event_type == "MISSION_POD_MANAGER_ASSIGNED":
        routed_agent_id = pod_manager_agent_id
    elif event_type in {
        "MISSION_SPECIALIST_ASSIGNED",
        "MISSION_SPECIALIST_PLANNED",
        "MISSION_RUNNING",
        "MISSION_GATING",
        "MISSION_FUSION",
        "MISSION_VERIFIED",
        "MISSION_COMPLETE",
        "MISSION_FAILED",
    }:
        routed_agent_id = specialist_agent_id

    if not routed_agent_id:
        return {}

    return {
        "agent_id": routed_agent_id,
        "selected_agent_id": routed_agent_id,
        "target_agent_id": routed_agent_id,
        "assigned_pod_manager_agent_id": pod_manager_agent_id,
        "assigned_specialist_agent_id": specialist_agent_id,
    }


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

    # Fallback: single-orchestrator deployments write logicnodes/assignments
    # into the metadata JSON rather than the normalised tables.  Accept either.
    if not has_assignment or not has_logicnodes:
        _meta = mission.metadata if isinstance(mission.metadata, dict) else {}
        def _has_chain_event(meta: dict, evt: str) -> bool:
            return any(
                e.get("event_type") == evt
                for e in meta.get("chain_trace", [])
                if isinstance(e, dict)
            )

        if not has_assignment:
            has_assignment = bool(
                _meta.get("assigned_pod_manager_agent_id")
                or _meta.get("assigned_specialist_agent_id")
                or _has_chain_event(_meta, "MISSION_SPECIALIST_ASSIGNED")
            )
        if not has_logicnodes:
            has_logicnodes = bool(
                _meta.get("pod_group_standards")
                or _meta.get("master_logic_stream")
                or _has_chain_event(_meta, "MISSION_LOGIC_FOLDED")
            )
    build_artifact_required = build_artifact_support.mission_requires_build_artifact(
        mission.metadata
    )
    if build_artifact_required:
        records = await asyncio.to_thread(
            storage.list_build_artifacts,
            settings,
            mission.mission_id,
            10,
        )
        has_successful_build = build_artifact_support.has_successful_build_artifact(records)
        return has_successful_build and (has_assignment or has_logicnodes), {
            "policy_exempt": False,
            "build_artifact_required": True,
            "build_artifact_count": len(records),
            "build_artifact_status": build_artifact_support.latest_build_artifact_status(records),
            "has_successful_build_artifact": has_successful_build,
            "has_pod_assignment": has_assignment,
            "logicnode_count": len(logicnodes),
        }

    return has_assignment or has_logicnodes, {
        "policy_exempt": False,
        "build_artifact_required": False,
        "has_pod_assignment": has_assignment,
        "logicnode_count": len(logicnodes),
    }


async def _ensure_verified_build_artifact(
    *,
    settings: Settings,
    mission: MissionRecord,
) -> MissionRecord:
    if not build_artifact_support.mission_requires_build_artifact(mission.metadata):
        return mission

    artifact_record = build_artifact_support.build_source_bundle_artifact(
        mission_id=mission.mission_id,
        requested_target_language=mission.requested_target_language,
        metadata=mission.metadata if isinstance(mission.metadata, dict) else {},
    )
    await asyncio.to_thread(
        storage.upsert_build_artifact,
        settings,
        mission.mission_id,
        artifact_record["artifact_id"],
        artifact_record["artifact_type"],
        artifact_record["stage"],
        artifact_record["status"],
        artifact_record["storage_backend"],
        artifact_record["storage_ref"],
        artifact_record["digest_sha256"],
        artifact_record["size_bytes"],
        artifact_record["manifest"],
        artifact_record["verification"],
        artifact_record["build_log"],
        artifact_record["artifact_text"],
        artifact_record["created_at"],
    )

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    selected_agent_id = str(
        metadata.get("selected_agent_id")
        or metadata.get("assigned_specialist_agent_id")
        or CEO_AGENT_ID
    ).strip()
    build_artifact_support.record_build_artifact_metadata(
        metadata,
        agent_id=selected_agent_id or CEO_AGENT_ID,
        artifact_record=artifact_record,
    )
    updated = await asyncio.to_thread(
        storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission


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
        "created_at": (
            mission.created_at.isoformat()
            if isinstance(mission.created_at, datetime)
            else str(mission.created_at)
        ),
    }
    payload.update(_state_event_agent_routing(mission, event_type))
    await redis_client.xadd(
        settings.state_stream,
        {
            "envelope": json.dumps(envelope),
            "payload": json.dumps(payload),
            # Legacy compatibility fields.
            "event_type": event_type,
            "mission_id": mission.mission_id,
            "state": mission.state.value,
            "created_at": (
                mission.created_at.isoformat()
                if isinstance(mission.created_at, datetime)
                else str(mission.created_at)
            ),
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


def _owned_consumer_groups(settings: Settings) -> tuple[tuple[str, str], ...]:
    """Stream/consumer-group pairs the orchestrator owns and is responsible for reaping.

    DLQ streams (``factory:dlq:*``) are intentionally excluded — they are
    unidirectional and have no consumer groups to reap.
    """
    return ((settings.intake_stream, settings.consumer_group),)


def _consumer_field(consumer: Any, key: str, default: Any) -> Any:
    if isinstance(consumer, dict):
        if key in consumer:
            return consumer[key]
        return consumer.get(key.encode(), default)
    return default


async def _reap_group(
    settings: Settings,
    redis_client: Any,
    stream: str,
    group: str,
) -> None:
    try:
        consumers = await redis_client.xinfo_consumers(stream, group)
    except ResponseError as exc:
        # Group/stream may not exist yet (e.g. before first intake); nothing to reap.
        if "NOGROUP" in str(exc) or "no such key" in str(exc).lower():
            return
        raise

    current_consumer = settings.consumer_name
    for consumer in consumers or []:
        name = _consumer_field(consumer, "name", "")
        if isinstance(name, bytes):
            name = name.decode()
        name = str(name)
        idle = int(_consumer_field(consumer, "idle", 0) or 0)
        pending = int(_consumer_field(consumer, "pending", 0) or 0)

        if idle <= settings.stale_consumer_idle_ms:
            continue
        if name == current_consumer:
            # Never reap the consumer this process is actively using.
            continue

        if pending > 0:
            # Reassign the dead consumer's pending entries to the live consumer so
            # they get reprocessed, then drop the stale consumer.
            try:
                await redis_client.xautoclaim(
                    stream,
                    group,
                    current_consumer,
                    min_idle_time=settings.stale_consumer_idle_ms,
                    start_id="0-0",
                )
            except ResponseError as exc:
                LOGGER.warning(
                    "xautoclaim failed for stale consumer %s on %s/%s: %s",
                    name,
                    stream,
                    group,
                    exc,
                )
                continue

        try:
            await redis_client.xgroup_delconsumer(stream, group, name)
        except ResponseError as exc:
            LOGGER.warning(
                "failed to delete stale consumer %s on %s/%s: %s",
                name,
                stream,
                group,
                exc,
            )
            continue

        LOGGER.info(
            "reaped stale consumer %s on %s/%s (idle=%dms, pending=%d)",
            name,
            stream,
            group,
            idle,
            pending,
        )


async def reap_stale_consumers(settings: Settings, redis_client: Any) -> None:
    """Remove dead consumers that accumulate across container restarts.

    Each restart with a hostname-derived consumer name leaves a stale consumer
    in the PEL. This sweeps groups the orchestrator owns, reassigning any
    pending entries via XAUTOCLAIM before deleting the stale consumer.
    """
    for stream, group in _owned_consumer_groups(settings):
        try:
            await _reap_group(settings, redis_client, stream, group)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOGGER.warning(
                "stale-consumer reap failed for %s/%s: %s", stream, group, exc
            )


async def stale_consumer_reap_loop(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    while True:
        redis_ready = bool(getattr(app.state, "redis_ready", False))
        redis_client = getattr(app.state, "redis", None)
        if redis_ready and redis_client is not None:
            try:
                await reap_stale_consumers(settings, redis_client)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("stale consumer reap iteration failed")
        await asyncio.sleep(settings.stale_consumer_reap_interval_seconds)


async def _write_intake_dlq(
    settings: Settings,
    redis_client: Any,
    entry_id: str,
    fields: dict[str, Any],
    error: str,
) -> None:
    try:
        await redis_client.xadd(
            settings.intake_dlq_stream,
            {
                "error": error,
                "entry_id": entry_id,
                "envelope": fields.get("envelope", ""),
                "payload": fields.get("payload", ""),
                "ts": datetime.now(UTC).isoformat(),
            },
            maxlen=settings.intake_dlq_max_len,
            approximate=True,
        )
    except Exception as dlq_exc:
        LOGGER.error(
            "failed to write intake entry %s to DLQ %s: %s",
            entry_id,
            settings.intake_dlq_stream,
            dlq_exc,
        )


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

                        existing = await asyncio.to_thread(
                            storage.fetch_mission,
                            settings,
                            payload_json["mission_id"],
                        )
                        if existing is not None:
                            continue

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
                        await _write_intake_dlq(
                            settings,
                            redis_client,
                            entry_id,
                            fields,
                            str(exc),
                        )
                    finally:
                        await redis_client.xack(
                            settings.intake_stream,
                            settings.consumer_group,
                            entry_id,
                        )
        except asyncio.CancelledError:
            raise
        except ResponseError as exc:
            if "NOGROUP" in str(exc):
                LOGGER.warning(
                    "intake stream group %s missing for %s; recreating",
                    settings.consumer_group,
                    settings.intake_stream,
                )
                await ensure_consumer_group(settings, redis_client)
                app.state.redis_ready = True
                continue
            raise
        except RedisTimeoutError as exc:
            LOGGER.debug("intake stream read timed out while idle: %s", exc)
            app.state.redis_ready = True
            continue
        except Exception:
            app.state.redis_ready = False
            LOGGER.exception("intake consumer loop failed; retrying")
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
    from .llm_delegation import current_mission_id, current_settings

    settings: Settings = app.state.settings
    token_mid = current_mission_id.set(mission_id)
    token_set = current_settings.set(settings)
    try:
        engine = get_lifecycle_engine(settings)
        await engine.advance(app, mission_id)
    finally:
        current_mission_id.reset(token_mid)
        current_settings.reset(token_set)


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
                try:
                    await reap_stale_consumers(settings, redis_client)
                except Exception:
                    LOGGER.exception("startup stale-consumer reap failed")
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
