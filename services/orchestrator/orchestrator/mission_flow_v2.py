"""
mission_flow_v2.py — 11-phase Mission Flow v2 lifecycle engine.

Provides the expanded state-machine that replaces v1.1's coarse
``QUEUED → RUNNING → VERIFIED → COMPLETE`` with 11 granular phases.

Gated behind ``MISSION_FLOW_V2_ENABLED=true``.  When disabled the
legacy/LangGraph v1.1 engines handle mission progression as before.

Phase order
-----------
1. INTAKE          (gateway receipt)
2. QUEUED          (persisted + queued)
3. PM_INTAKE       (PM intent translation)
4. CEO_DELEGATED   (CEO delegation plan)
5. POD_ASSIGNED    (pod manager assigned)
6. SPECIALIST_ASSIGNED (specialist assigned)
7. RUNNING         (extraction active)
8. GATING          (QC gating pass)
9. FUSION          (artifact fusion)
10. VERIFIED       (verification gate)
11. COMPLETE       (delivered)
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from . import build_artifacts as build_artifact_support
from . import storage
from .agent_registry import AGENT_REGISTRY
from .agent_scaling import (
    all_partitions_complete,
    compute_scaling_decision,
    embed_scaling_decision,
    is_scalable_agent,
    scaling_decision_from_metadata,
)
from .llm_delegation import (
    generate_ceo_delegation,
    generate_pod_manager_delegation,
    generate_specialist_plan,
)
from .mission_flow import (
    CEO_AGENT_ID,
    PM_AGENT_ID,
    append_chain_event,
    resolve_pod_manager_agent_id,
    resolve_specialist_agent_id,
    with_chain_defaults,
)
from .models import MissionState

LOGGER = logging.getLogger(__name__)
VALID_AGENT_IDS = frozenset(agent.agent_id for agent in AGENT_REGISTRY)
RUNTIME_PHASES = frozenset(
    {
        MissionState.running,
        MissionState.gating,
        MissionState.fusion,
        MissionState.verified,
        MissionState.complete,
    }
)
_SOURCE_BUNDLE_FILE_PATTERN = re.compile(r"^## FILE (.+)$", re.MULTILINE)


def _setting_bool(settings: Any, name: str, default: bool = False) -> bool:
    raw = getattr(settings, name, default)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return bool(raw)
    if isinstance(raw, str):
        candidate = raw.strip().lower()
        if candidate in {"1", "true", "yes", "on"}:
            return True
        if candidate in {"0", "false", "no", "off", ""}:
            return False
    return default


def _setting_int(settings: Any, name: str, default: int) -> int:
    raw = getattr(settings, name, default)
    if isinstance(raw, bool):
        return default
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    if isinstance(raw, str):
        candidate = raw.strip()
        if not candidate:
            return default
        try:
            return int(candidate)
        except ValueError:
            return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _chain_event_exists(metadata: dict[str, Any], event_type: str) -> bool:
    return any(
        isinstance(record, dict) and str(record.get("event_type", "")).upper() == event_type
        for record in metadata.get("chain_trace", [])
    )


def _record_artifact(
    metadata: dict[str, Any],
    *,
    stage: str,
    event_type: str,
    agent_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    artifacts = metadata.get("mission_artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
    artifacts[stage] = {
        "event_type": event_type,
        "agent_id": agent_id,
        "recorded_at": datetime.now(UTC).isoformat(),
        "details": details or {},
    }
    metadata["mission_artifacts"] = artifacts


def _validate_agent_id(candidate: Any, *, fallback: str) -> str:
    normalized = str(candidate or "").strip().upper()
    if normalized in VALID_AGENT_IDS:
        return normalized
    return fallback


def _mission_context(mission: Any, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "mission_id": mission.mission_id,
        "prompt": mission.prompt,
        "requested_target_language": mission.requested_target_language,
        "source": metadata.get("source"),
        "routing_version": metadata.get("routing_version"),
        "routing_enforced": metadata.get("routing_enforced"),
    }


def _workload_items_from_source_bundle(source_code: Any) -> list[str]:
    if not isinstance(source_code, str) or not source_code.strip():
        return []

    items: list[str] = []
    for match in _SOURCE_BUNDLE_FILE_PATTERN.finditer(source_code):
        candidate = str(match.group(1)).strip()
        if candidate and candidate not in items:
            items.append(candidate)
    return items


def _scaling_workload_items(metadata: dict[str, Any], specialist_plan: dict[str, Any]) -> list[str]:
    source_items = _workload_items_from_source_bundle(metadata.get("source_code"))
    if source_items:
        return source_items

    workload_items = [
        str(item).strip()
        for item in specialist_plan.get("deliverables", [])
        if str(item).strip()
    ]
    return workload_items or ["default_workload"]


async def _emit_partition_work_items(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    mission: Any,
) -> Any:
    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    decision = scaling_decision_from_metadata(metadata)
    if decision is None or decision.instance_count <= 1:
        return mission
    if metadata.get("scaling_partition_events_emitted"):
        return mission

    redis_ready = bool(getattr(app.state, "redis_ready", False))
    redis_client = getattr(app.state, "redis", None)
    if not redis_ready or redis_client is None:
        return mission

    specialist_agent_id = _validate_agent_id(
        metadata.get("assigned_specialist_agent_id"),
        fallback=resolve_specialist_agent_id(mission.requested_target_language),
    )
    pod_manager_agent_id = _validate_agent_id(
        metadata.get("assigned_pod_manager_agent_id"),
        fallback=resolve_pod_manager_agent_id(mission.requested_target_language),
    )

    emitted_count = 0
    for partition in decision.partitions:
        envelope = {
            "event_id": f"evt-{uuid.uuid4()}",
            "topic": "mission.partition.ready",
            "timestamp": datetime.now(UTC).isoformat(),
            "producer": settings.producer_name,
            "correlation_id": mission.mission_id,
            "payload_ref": (
                f"registry://missions/{mission.mission_id}/partitions/{partition.partition_id}"
            ),
            "schema": "missions.partition.v1",
            "priority": settings.default_priority,
        }
        try:
            validator.validate(envelope)
        except Exception as exc:
            LOGGER.warning(
                "v2: failed to validate partition envelope for mission %s/%s: %s",
                mission.mission_id,
                partition.partition_id,
                exc,
            )
            return mission

        payload = {
            "mission_id": mission.mission_id,
            "state": mission.state.value,
            "event_type": "MISSION_PARTITION_READY",
            "requested_target_language": mission.requested_target_language,
            "agent_id": specialist_agent_id,
            "selected_agent_id": specialist_agent_id,
            "assigned_specialist_agent_id": specialist_agent_id,
            "assigned_pod_manager_agent_id": pod_manager_agent_id,
            "partition": partition.to_dict(),
        }
        await redis_client.xadd(
            settings.state_stream,
            {
                "envelope": json.dumps(envelope),
                "payload": json.dumps(payload),
                "event_type": "MISSION_PARTITION_READY",
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
        emitted_count += 1

    metadata["scaling_partition_events_emitted"] = True
    metadata["scaling_partition_events_emitted_at"] = datetime.now(UTC).isoformat()
    metadata["scaling_partition_event_count"] = emitted_count
    updated = await asyncio.to_thread(
        storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission


async def _persist_metadata(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission_id: str,
    metadata: dict[str, Any],
    emit_event_type: str | None = None,
    event_state: MissionState | None = None,
) -> Any | None:
    record = await asyncio.to_thread(
        storage.update_mission_metadata,
        settings,
        mission_id,
        metadata,
    )
    if record is None or emit_event_type is None or event_state is None:
        return record

    await asyncio.to_thread(
        storage.insert_mission_event,
        settings,
        mission_id,
        event_state,
        event_state,
        emit_event_type,
    )

    redis_ready = bool(getattr(app.state, "redis_ready", False))
    redis_client = getattr(app.state, "redis", None)
    if not redis_ready or redis_client is None:
        return record

    try:
        await emit_state_event_fn(
            settings=settings,
            validator=validator,
            redis_client=redis_client,
            mission=record,
            event_type=emit_event_type,
        )
    except Exception as exc:
        LOGGER.warning(
            "v2: failed to emit auxiliary event %s for mission %s: %s",
            emit_event_type,
            mission_id,
            exc,
        )
    return record


async def _prepare_pm_intake(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission_id: str,
) -> bool:
    mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    metadata["selected_agent_id"] = PM_AGENT_ID
    metadata["agent_id"] = PM_AGENT_ID

    if not _chain_event_exists(metadata, "MISSION_PM_INTAKE"):
        append_chain_event(
            metadata,
            event_type="MISSION_PM_INTAKE",
            agent_id=PM_AGENT_ID,
            details={"source": metadata.get("source", "mission-flow-v2")},
        )
    _record_artifact(
        metadata,
        stage="pm_intake",
        event_type="MISSION_PM_INTAKE",
        agent_id=PM_AGENT_ID,
        details={"source": metadata.get("source", "mission-flow-v2")},
    )
    return (
        await _persist_metadata(
            app=app,
            settings=settings,
            validator=validator,
            emit_state_event_fn=emit_state_event_fn,
            mission_id=mission_id,
            metadata=metadata,
        )
        is not None
    )


async def _prepare_ceo_delegation(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission_id: str,
) -> bool:
    mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    mission_context = _mission_context(mission, metadata)
    delegation = await generate_ceo_delegation(
        mission_context=mission_context,
        requested_target_language=mission.requested_target_language,
    )
    pod_manager_agent_id = _validate_agent_id(
        delegation.get("pod_manager_agent_id"),
        fallback=resolve_pod_manager_agent_id(mission.requested_target_language),
    )
    specialist_agent_id = _validate_agent_id(
        delegation.get("specialist_agent_id"),
        fallback=resolve_specialist_agent_id(mission.requested_target_language),
    )
    normalized = dict(delegation)
    normalized["pod_manager_agent_id"] = pod_manager_agent_id
    normalized["specialist_agent_id"] = specialist_agent_id

    metadata["ceo_delegation"] = normalized
    metadata["selected_agent_id"] = pod_manager_agent_id
    metadata["agent_id"] = pod_manager_agent_id

    if not _chain_event_exists(metadata, "MISSION_CEO_DELEGATED"):
        append_chain_event(
            metadata,
            event_type="MISSION_CEO_DELEGATED",
            agent_id=CEO_AGENT_ID,
            details={
                "target_agent_id": pod_manager_agent_id,
                "specialist_agent_id": specialist_agent_id,
                "source": normalized.get("source"),
                "llm_route": normalized.get("llm_route"),
                "model_provider": normalized.get("model_provider"),
                "model": normalized.get("model"),
            },
        )
    _record_artifact(
        metadata,
        stage="ceo_delegated",
        event_type="MISSION_CEO_DELEGATED",
        agent_id=CEO_AGENT_ID,
        details={
            "target_agent_id": pod_manager_agent_id,
            "specialist_agent_id": specialist_agent_id,
            "source": normalized.get("source"),
            "llm_route": normalized.get("llm_route"),
            "model_provider": normalized.get("model_provider"),
            "model": normalized.get("model"),
        },
    )
    return (
        await _persist_metadata(
            app=app,
            settings=settings,
            validator=validator,
            emit_state_event_fn=emit_state_event_fn,
            mission_id=mission_id,
            metadata=metadata,
        )
        is not None
    )


async def _prepare_pod_assignment(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission_id: str,
) -> bool:
    mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    ceo_delegation = (
        metadata.get("ceo_delegation") if isinstance(metadata.get("ceo_delegation"), dict) else {}
    )
    pod_manager_agent_id = _validate_agent_id(
        ceo_delegation.get("pod_manager_agent_id"),
        fallback=resolve_pod_manager_agent_id(mission.requested_target_language),
    )
    default_specialist_agent_id = _validate_agent_id(
        ceo_delegation.get("specialist_agent_id"),
        fallback=resolve_specialist_agent_id(mission.requested_target_language),
    )

    pod_manager_delegation = await generate_pod_manager_delegation(
        mission_context={
            **_mission_context(mission, metadata),
            "ceo_delegation": ceo_delegation,
        },
        requested_target_language=mission.requested_target_language,
        pod_manager_agent_id=pod_manager_agent_id,
        default_specialist_agent_id=default_specialist_agent_id,
    )
    specialist_agent_id = _validate_agent_id(
        pod_manager_delegation.get("specialist_agent_id"),
        fallback=default_specialist_agent_id,
    )
    normalized = dict(pod_manager_delegation)
    normalized["pod_manager_agent_id"] = pod_manager_agent_id
    normalized["specialist_agent_id"] = specialist_agent_id

    metadata["pod_manager_delegation"] = normalized
    metadata["assigned_pod_manager_agent_id"] = pod_manager_agent_id
    metadata["assigned_specialist_agent_id"] = specialist_agent_id
    metadata["selected_agent_id"] = pod_manager_agent_id
    metadata["agent_id"] = pod_manager_agent_id

    if not _chain_event_exists(metadata, "MISSION_POD_MANAGER_ASSIGNED"):
        append_chain_event(
            metadata,
            event_type="MISSION_POD_MANAGER_ASSIGNED",
            agent_id=pod_manager_agent_id,
            details={
                "specialist_agent_id": specialist_agent_id,
                "source": normalized.get("source"),
                "llm_route": normalized.get("llm_route"),
                "model_provider": normalized.get("model_provider"),
                "model": normalized.get("model"),
            },
        )
    _record_artifact(
        metadata,
        stage="pod_assigned",
        event_type="MISSION_POD_MANAGER_ASSIGNED",
        agent_id=pod_manager_agent_id,
        details={
            "specialist_agent_id": specialist_agent_id,
            "source": normalized.get("source"),
            "llm_route": normalized.get("llm_route"),
            "model_provider": normalized.get("model_provider"),
            "model": normalized.get("model"),
        },
    )
    return (
        await _persist_metadata(
            app=app,
            settings=settings,
            validator=validator,
            emit_state_event_fn=emit_state_event_fn,
            mission_id=mission_id,
            metadata=metadata,
        )
        is not None
    )


async def _prepare_specialist_assignment(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission_id: str,
) -> bool:
    mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    pod_manager_agent_id = _validate_agent_id(
        metadata.get("assigned_pod_manager_agent_id"),
        fallback=resolve_pod_manager_agent_id(mission.requested_target_language),
    )
    specialist_agent_id = _validate_agent_id(
        metadata.get("assigned_specialist_agent_id"),
        fallback=resolve_specialist_agent_id(mission.requested_target_language),
    )

    metadata["assigned_pod_manager_agent_id"] = pod_manager_agent_id
    metadata["assigned_specialist_agent_id"] = specialist_agent_id
    metadata["selected_agent_id"] = specialist_agent_id
    metadata["agent_id"] = specialist_agent_id

    if not _chain_event_exists(metadata, "MISSION_SPECIALIST_ASSIGNED"):
        append_chain_event(
            metadata,
            event_type="MISSION_SPECIALIST_ASSIGNED",
            agent_id=specialist_agent_id,
            details={"pod_manager_agent_id": pod_manager_agent_id},
        )
    _record_artifact(
        metadata,
        stage="specialist_assigned",
        event_type="MISSION_SPECIALIST_ASSIGNED",
        agent_id=specialist_agent_id,
        details={"pod_manager_agent_id": pod_manager_agent_id},
    )
    return (
        await _persist_metadata(
            app=app,
            settings=settings,
            validator=validator,
            emit_state_event_fn=emit_state_event_fn,
            mission_id=mission_id,
            metadata=metadata,
        )
        is not None
    )


async def _prepare_specialist_plan(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission_id: str,
) -> bool:
    mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    pod_manager_agent_id = _validate_agent_id(
        metadata.get("assigned_pod_manager_agent_id"),
        fallback=resolve_pod_manager_agent_id(mission.requested_target_language),
    )
    specialist_agent_id = _validate_agent_id(
        metadata.get("assigned_specialist_agent_id"),
        fallback=resolve_specialist_agent_id(mission.requested_target_language),
    )
    specialist_plan = await generate_specialist_plan(
        mission_context={
            **_mission_context(mission, metadata),
            "ceo_delegation": metadata.get("ceo_delegation"),
            "pod_manager_delegation": metadata.get("pod_manager_delegation"),
        },
        requested_target_language=mission.requested_target_language,
        specialist_agent_id=specialist_agent_id,
        pod_manager_agent_id=pod_manager_agent_id,
    )
    normalized = dict(specialist_plan)
    normalized["specialist_agent_id"] = specialist_agent_id
    normalized["pod_manager_agent_id"] = pod_manager_agent_id
    metadata["specialist_plan"] = normalized
    metadata["selected_agent_id"] = specialist_agent_id
    metadata["agent_id"] = specialist_agent_id

    should_emit = not _chain_event_exists(metadata, "MISSION_SPECIALIST_PLANNED")
    if should_emit:
        append_chain_event(
            metadata,
            event_type="MISSION_SPECIALIST_PLANNED",
            agent_id=specialist_agent_id,
            details={
                "pod_manager_agent_id": pod_manager_agent_id,
                "source": normalized.get("source"),
                "llm_route": normalized.get("llm_route"),
                "model_provider": normalized.get("model_provider"),
                "model": normalized.get("model"),
            },
        )
    _record_artifact(
        metadata,
        stage="specialist_planned",
        event_type="MISSION_SPECIALIST_PLANNED",
        agent_id=specialist_agent_id,
        details={
            "pod_manager_agent_id": pod_manager_agent_id,
            "source": normalized.get("source"),
            "llm_route": normalized.get("llm_route"),
            "model_provider": normalized.get("model_provider"),
            "model": normalized.get("model"),
        },
    )

    # Compute scaling decision when feature is enabled.
    if _setting_bool(settings, "agent_scaling_enabled", False) and is_scalable_agent(
        specialist_agent_id
    ):
        workload_items = _scaling_workload_items(metadata, normalized)
        scaling = compute_scaling_decision(
            agent_id=specialist_agent_id,
            workload_items=workload_items,
            max_instances=_setting_int(settings, "agent_scaling_max_instances", 4),
            items_per_instance=_setting_int(settings, "agent_scaling_items_per_instance", 3),
        )
        embed_scaling_decision(metadata, scaling)
        metadata["scaling_partition_events_emitted"] = False
        if not _chain_event_exists(metadata, "MISSION_SCALING_DECIDED"):
            append_chain_event(
                metadata,
                event_type="MISSION_SCALING_DECIDED",
                agent_id=specialist_agent_id,
                details={
                    "instance_count": scaling.instance_count,
                    "reason": scaling.reason,
                    "scaling_version": scaling.scaling_version,
                },
            )
        _record_artifact(
            metadata,
            stage="scaling_decided",
            event_type="MISSION_SCALING_DECIDED",
            agent_id=specialist_agent_id,
            details=scaling.to_dict(),
        )

    return (
        await _persist_metadata(
            app=app,
            settings=settings,
            validator=validator,
            emit_state_event_fn=emit_state_event_fn,
            mission_id=mission_id,
            metadata=metadata,
            emit_event_type="MISSION_SPECIALIST_PLANNED" if should_emit else None,
            event_state=MissionState.specialist_assigned if should_emit else None,
        )
        is not None
    )


async def _persist_runtime_phase_artifact(
    *,
    settings: Any,
    mission: Any,
    event_type: str,
) -> Any:
    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    selected_agent_id = _validate_agent_id(
        metadata.get("selected_agent_id"),
        fallback=metadata.get("assigned_specialist_agent_id") or CEO_AGENT_ID,
    )
    _record_artifact(
        metadata,
        stage=mission.state.value.lower(),
        event_type=event_type,
        agent_id=selected_agent_id,
        details={"state": mission.state.value},
    )
    updated = await asyncio.to_thread(
        storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission


async def _ensure_verified_build_artifact(
    *,
    settings: Any,
    mission: Any,
) -> Any:
    if not build_artifact_support.mission_requires_build_artifact(mission.metadata):
        return mission

    artifact_record = build_artifact_support.dispatch_build_artifact(
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
    selected_agent_id = _validate_agent_id(
        metadata.get("selected_agent_id"),
        fallback=metadata.get("assigned_specialist_agent_id") or CEO_AGENT_ID,
    )
    build_artifact_support.record_build_artifact_metadata(
        metadata,
        agent_id=selected_agent_id,
        artifact_record=artifact_record,
    )
    updated = await asyncio.to_thread(
        storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission

# ------------------------------------------------------------------
# V2 transition table (ordered)
# ------------------------------------------------------------------

V2_TRANSITIONS: tuple[tuple[MissionState, MissionState, str], ...] = (
    (MissionState.queued, MissionState.pm_intake, "MISSION_PM_INTAKE"),
    (MissionState.pm_intake, MissionState.ceo_delegated, "MISSION_CEO_DELEGATED"),
    (
        MissionState.ceo_delegated,
        MissionState.pod_assigned,
        "MISSION_POD_MANAGER_ASSIGNED",
    ),
    (
        MissionState.pod_assigned,
        MissionState.specialist_assigned,
        "MISSION_SPECIALIST_ASSIGNED",
    ),
    (
        MissionState.specialist_assigned,
        MissionState.running,
        "MISSION_RUNNING",
    ),
    (MissionState.running, MissionState.gating, "MISSION_GATING"),
    (MissionState.gating, MissionState.fusion, "MISSION_FUSION"),
    (MissionState.fusion, MissionState.verified, "MISSION_VERIFIED"),
    (MissionState.verified, MissionState.complete, "MISSION_COMPLETE"),
)

V1_TRANSITIONS: tuple[tuple[MissionState, MissionState, str], ...] = (
    (MissionState.queued, MissionState.running, "MISSION_RUNNING"),
    (MissionState.running, MissionState.verified, "MISSION_VERIFIED"),
    (MissionState.verified, MissionState.complete, "MISSION_COMPLETE"),
)

# Ordered list of all 11 v2 phases (for deterministic progression).
V2_PHASE_ORDER: tuple[MissionState, ...] = (
    MissionState.intake,
    MissionState.queued,
    MissionState.pm_intake,
    MissionState.ceo_delegated,
    MissionState.pod_assigned,
    MissionState.specialist_assigned,
    MissionState.running,
    MissionState.gating,
    MissionState.fusion,
    MissionState.verified,
    MissionState.complete,
)

# Maps v2 event types to the phases they represent.
V2_EVENT_TO_PHASE: dict[str, MissionState] = {
    "MISSION_INTAKE": MissionState.intake,
    "MISSION_QUEUED": MissionState.queued,
    "MISSION_PM_INTAKE": MissionState.pm_intake,
    "MISSION_CEO_DELEGATED": MissionState.ceo_delegated,
    "MISSION_POD_MANAGER_ASSIGNED": MissionState.pod_assigned,
    "MISSION_SPECIALIST_ASSIGNED": MissionState.specialist_assigned,
    "MISSION_RUNNING": MissionState.running,
    "MISSION_GATING": MissionState.gating,
    "MISSION_FUSION": MissionState.fusion,
    "MISSION_VERIFIED": MissionState.verified,
    "MISSION_COMPLETE": MissionState.complete,
}


# ------------------------------------------------------------------
# Backward-compatible v1.1 mapping
# ------------------------------------------------------------------

_V2_TO_V1_MAP: dict[MissionState, MissionState] = {
    MissionState.intake: MissionState.intake,
    MissionState.queued: MissionState.queued,
    MissionState.pm_intake: MissionState.queued,
    MissionState.ceo_delegated: MissionState.queued,
    MissionState.pod_assigned: MissionState.queued,
    MissionState.specialist_assigned: MissionState.queued,
    MissionState.running: MissionState.running,
    MissionState.gating: MissionState.running,
    MissionState.fusion: MissionState.running,
    MissionState.verified: MissionState.verified,
    MissionState.complete: MissionState.complete,
    MissionState.failed: MissionState.failed,
}


def v2_map_state_to_v1(state: MissionState) -> MissionState:
    """Map a v2 state to its canonical v1.1 equivalent.

    This allows APIs to expose backward-compatible state values
    when the consumer does not understand v2 microstates.
    """
    return _V2_TO_V1_MAP.get(state, state)


def v2_phase_index(state: MissionState) -> int:
    """Return the zero-based phase index for a v2 state.

    Returns -1 for states not in the v2 phase model (e.g. ``FAILED``).
    """
    try:
        return V2_PHASE_ORDER.index(state)
    except ValueError:
        return -1


# ------------------------------------------------------------------
# V2 lifecycle driver (legacy path, no LangGraph)
# ------------------------------------------------------------------


async def advance_mission_lifecycle_v2(
    *,
    app: Any,
    mission_id: str,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    prepare_chain_fn: Any,
    completion_check_fn: Any,
) -> None:
    """Drive a mission through all 11 v2 phases.

    This is the legacy (non-LangGraph) v2 driver. It mirrors the
    structure of ``runtime.advance_mission_lifecycle`` but uses the
    full v2 transition table.

    Parameters
    ----------
    app : FastAPI
        Application instance with ``app.state`` references.
    mission_id : str
        Mission to advance.
    settings : Settings
        Application settings (must have ``mission_flow_v2_enabled=True``).
    validator : EnvelopeValidator
        Protocol envelope validator.
    emit_state_event_fn : callable
        Async function to emit state events to Redis streams.
    prepare_chain_fn : callable
        Legacy compatibility hook. The v2 driver now performs its own
        PM, CEO, pod-manager, and specialist stage preparation.
    completion_check_fn : callable
        Async function ``(settings, mission) → (bool, dict)``
        that checks whether completion artifacts are ready.
    """

    stage_preparers = {
        MissionState.queued: _prepare_pm_intake,
        MissionState.pm_intake: _prepare_ceo_delegation,
        MissionState.ceo_delegated: _prepare_pod_assignment,
        MissionState.pod_assigned: _prepare_specialist_assignment,
        MissionState.specialist_assigned: _prepare_specialist_plan,
    }

    _ = prepare_chain_fn

    for expected_state, new_state, event_type in V2_TRANSITIONS:
        preparer = stage_preparers.get(expected_state)
        if preparer is not None:
            prepared = await preparer(
                app=app,
                settings=settings,
                validator=validator,
                emit_state_event_fn=emit_state_event_fn,
                mission_id=mission_id,
            )
            if not prepared:
                return

        if expected_state == MissionState.running and new_state == MissionState.gating:
            mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
            if mission is None:
                return
            metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
            if metadata.get("scaling_active"):
                if not metadata.get("scaling_partition_events_emitted"):
                    mission = await _emit_partition_work_items(
                        app=app,
                        settings=settings,
                        validator=validator,
                        mission=mission,
                    )
                    metadata = with_chain_defaults(
                        mission.metadata,
                        mission.requested_target_language,
                    )
                if not all_partitions_complete(metadata):
                    return

        # Completion gate before COMPLETE
        if (
            expected_state == MissionState.verified
            and new_state == MissionState.complete
        ):
            mission = await asyncio.to_thread(
                storage.fetch_mission, settings, mission_id
            )
            if mission is None:
                return
            ready, details = await completion_check_fn(
                settings=settings, mission=mission
            )
            if not ready:
                metadata = with_chain_defaults(
                    mission.metadata,
                    mission.requested_target_language,
                )
                append_chain_event(
                    metadata,
                    event_type="MISSION_COMPLETION_BLOCKED",
                    agent_id=CEO_AGENT_ID,
                    details=details,
                )
                await asyncio.to_thread(
                    storage.update_mission_metadata,
                    settings,
                    mission_id,
                    metadata,
                )
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
                        await emit_state_event_fn(
                            settings=settings,
                            validator=validator,
                            redis_client=redis_client,
                            mission=mission,
                            event_type="MISSION_COMPLETION_BLOCKED",
                        )
                    except Exception as exc:
                        LOGGER.warning(
                            "v2: failed to emit completion block event for mission %s: %s",
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

        if new_state in RUNTIME_PHASES:
            record = await _persist_runtime_phase_artifact(
                settings=settings,
                mission=record,
                event_type=event_type,
            )
            if new_state == MissionState.verified:
                try:
                    record = await _ensure_verified_build_artifact(
                        settings=settings,
                        mission=record,
                    )
                except Exception as exc:
                    LOGGER.warning(
                        "v2: failed to package verified build artifact for mission %s: %s",
                        mission_id,
                        exc,
                    )
            if new_state == MissionState.running:
                record = await _emit_partition_work_items(
                    app=app,
                    settings=settings,
                    validator=validator,
                    mission=record,
                )

        redis_ready = bool(getattr(app.state, "redis_ready", False))
        redis_client = getattr(app.state, "redis", None)
        if redis_ready and redis_client is not None:
            try:
                await emit_state_event_fn(
                    settings=settings,
                    validator=validator,
                    redis_client=redis_client,
                    mission=record,
                    event_type=event_type,
                )
            except Exception as exc:
                LOGGER.warning(
                    "v2: failed to emit %s for mission %s: %s",
                    event_type,
                    mission_id,
                    exc,
                )
