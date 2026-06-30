from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from .. import storage
from ..audit_events import record_audit_event
from ..auth import AuthContext
from ..lifecycle_interface import get_lifecycle_engine_name
from ..models import (
    MissionClarifyRequest,
    MissionCreate,
    MissionRecord,
    MissionState,
    MissionStateUpdate,
)
from ..project_identity import resolve_project_id, with_project_identity
from ._deps import INTERNAL_AUTH_DEP, MUTATION_AUTH_DEP, READ_AUTH_DEP

LOGGER = logging.getLogger(__name__)

router = APIRouter()


@router.post("/missions")
async def create_mission(
    request: Request,
    payload: MissionCreate,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> MissionRecord:
    import orchestrator.main as _main

    app = request.app
    redis_ready, _ = await _main._ensure_db_ready(app)
    redis_client = getattr(app.state, "redis", None)
    metadata = with_project_identity(payload.metadata, mission_id=payload.mission_id)
    metadata["lifecycle_engine"] = get_lifecycle_engine_name(app.state.settings)
    project_id = payload.project_id or resolve_project_id(metadata, mission_id=payload.mission_id)

    record = MissionRecord(
        mission_id=payload.mission_id,
        prompt=payload.prompt,
        requested_target_language=payload.requested_target_language,
        mission_type=payload.mission_type,
        depth_mode=payload.depth_mode,
        output_mode=payload.output_mode,
        data_classification=payload.data_classification,
        metadata=metadata,
        project_id=project_id,
        lifecycle_engine=metadata["lifecycle_engine"],
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
            await _main.emit_state_event(
                app.state.settings,
                app.state.envelope_validator,
                redis_client,
                record,
                "MISSION_QUEUED",
            )
        except Exception as exc:
            LOGGER.warning("failed to emit queued state event for %s: %s", record.mission_id, exc)

    await record_audit_event(
        app,
        mission_id=record.mission_id,
        mission=record,
        agent_id=str(
            metadata.get("agent_id") or metadata.get("selected_agent_id") or "AGENT-01-PM"
        ),
        service_name="orchestrator",
        event_type="MISSION_CREATED",
        object_type="mission",
        object_id=record.mission_id,
        payload_summary={
            "project_id": project_id,
            "requested_target_language": record.requested_target_language,
            "mission_type": record.mission_type.value if record.mission_type else None,
            "depth_mode": record.depth_mode.value if record.depth_mode else None,
            "output_mode": record.output_mode.value if record.output_mode else None,
            "data_classification": (
                record.data_classification.value if record.data_classification else None
            ),
            "source": metadata.get("source"),
            "project_name": metadata.get("project_name"),
        },
    )

    _main.start_lifecycle_task(app, record.mission_id)
    return record


@router.get("/missions/{mission_id}", dependencies=[READ_AUTH_DEP])
async def get_mission(request: Request, mission_id: str) -> MissionRecord:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    return await _main._fetch_existing_mission(app, mission_id)


@router.get("/missions", dependencies=[READ_AUTH_DEP])
async def list_missions(
    request: Request,
    limit: int = Query(default=20, ge=1, le=200),
) -> list[MissionRecord]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    return await asyncio.to_thread(storage.list_missions, app.state.settings, limit)


@router.get("/missions/{mission_id}/events", dependencies=[READ_AUTH_DEP])
async def get_mission_events(
    request: Request,
    mission_id: str,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    await _main._fetch_existing_mission(app, mission_id)
    events = await asyncio.to_thread(
        storage.list_mission_events, app.state.settings, mission_id, limit
    )
    return [event.model_dump() for event in events]


@router.get("/missions/{mission_id}/runtime-qc", dependencies=[READ_AUTH_DEP])
async def get_public_runtime_qc(request: Request, mission_id: str) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    mission = await _main._fetch_existing_mission(app, mission_id)
    record = await asyncio.to_thread(storage.get_runtime_qc_report, app.state.settings, mission_id)
    if record is None:
        metadata = mission.metadata if isinstance(mission.metadata, dict) else {}
        report = metadata.get("runtime_qc_report")
        if not isinstance(report, dict):
            raise HTTPException(status_code=404, detail="runtime QC report not found")
        record = {
            "mission_id": mission_id,
            "execution_result": report,
            "qc_assessment": report.get("qc_assessment") if isinstance(report, dict) else {},
        }
    execution = record.get("execution_result") if isinstance(record, dict) else {}
    if not isinstance(execution, dict):
        execution = {}
    qc_assessment = record.get("qc_assessment") if isinstance(record, dict) else {}
    if not isinstance(qc_assessment, dict):
        qc_assessment = {}
    return {
        "mission_id": mission_id,
        "verdict": execution.get("verdict") or record.get("verdict"),
        "execution_type": execution.get("execution_type") or record.get("execution_type"),
        "qc_verdict": qc_assessment.get("qc_verdict") or record.get("qc_verdict"),
        "deployment_safe": qc_assessment.get("deployment_safe"),
        "stdout_preview": execution.get("stdout_preview") or record.get("stdout_preview"),
        "stderr_preview": None,
        "language": execution.get("language") or record.get("language"),
        "filename": execution.get("filename") or record.get("filename"),
    }


@router.post("/missions/{mission_id}/state")
async def update_mission_state(
    request: Request,
    mission_id: str,
    payload: MissionStateUpdate,
    _: AuthContext = MUTATION_AUTH_DEP,
) -> MissionRecord:
    import orchestrator.main as _main

    app = request.app
    redis_ready, _ = await _main._ensure_db_ready(app)
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
            await _main.emit_state_event(
                app.state.settings,
                app.state.envelope_validator,
                redis_client,
                record,
                event_type,
            )
        except Exception as exc:
            LOGGER.warning("failed to emit state event for %s: %s", record.mission_id, exc)

    await record_audit_event(
        app,
        mission_id=record.mission_id,
        mission=record,
        agent_id=(
            str(
                record.metadata.get("agent_id")
                or record.metadata.get("selected_agent_id")
                or "SYSTEM"
            )
            if isinstance(record.metadata, dict)
            else "SYSTEM"
        ),
        service_name="orchestrator",
        event_type="MISSION_STATE_UPDATED",
        object_type="mission_state",
        object_id=record.mission_id,
        payload_summary={
            "new_state": payload.new_state.value,
            "expected_state": payload.expected_state.value if payload.expected_state else None,
        },
    )

    return record


@router.post("/missions/{mission_id}/clarify")
async def clarify_mission(
    request: Request,
    mission_id: str,
    payload: MissionClarifyRequest,
    _: AuthContext = MUTATION_AUTH_DEP,
) -> MissionRecord:
    """Supply operator clarification to a mission blocked in CLARIFYING state.

    Stores the clarification text in ``metadata["pm_clarification"]`` and
    re-queues the mission so the PM Agent re-processes the intent with the
    additional context. Only valid when the current state is CLARIFYING;
    returns HTTP 409 otherwise.
    """
    import orchestrator.main as _main  # noqa: PLC0415

    from ..mission_flow import append_chain_event, with_chain_defaults  # noqa: PLC0415

    app = request.app
    redis_ready, _ = await _main._ensure_db_ready(app)
    redis_client = getattr(app.state, "redis", None)

    mission = await _main._fetch_existing_mission(app, mission_id)
    if mission.state != MissionState.clarifying:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Mission {mission_id} is in state {mission.state.value!r}, "
                "not CLARIFYING. Clarification only applies to CLARIFYING missions."
            ),
        )

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    metadata["pm_clarification"] = payload.clarification
    metadata["user_intent"] = "finalize_plan"
    append_chain_event(
        metadata,
        event_type="MISSION_CLARIFICATION_RECEIVED",
        agent_id="AGENT-01-PM",
        details={"clarification_length": len(payload.clarification)},
    )
    await asyncio.to_thread(
        storage.update_mission_metadata,
        app.state.settings,
        mission_id,
        metadata,
    )

    record = await asyncio.to_thread(
        storage.transition_mission_state,
        app.state.settings,
        mission_id,
        MissionState.clarifying,
        MissionState.queued,
        "MISSION_CLARIFICATION_APPLIED",
    )
    if record is None:
        raise HTTPException(status_code=409, detail="state transition rejected")

    if redis_ready and redis_client is not None and app.state.protocol_ready:
        try:
            await _main.emit_state_event(
                app.state.settings,
                app.state.envelope_validator,
                redis_client,
                record,
                "MISSION_CLARIFICATION_APPLIED",
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to emit clarification-applied event for %s: %s", mission_id, exc
            )

    await record_audit_event(
        app,
        mission_id=mission_id,
        mission=record,
        agent_id="AGENT-01-PM",
        service_name="orchestrator",
        event_type="MISSION_CLARIFICATION_RECEIVED",
        object_type="mission",
        object_id=mission_id,
        payload_summary={"clarification_length": len(payload.clarification)},
    )
    _main.start_lifecycle_task(app, mission_id)
    return record


@router.get("/missions/{mission_id}/token-usage", dependencies=[INTERNAL_AUTH_DEP])
async def get_mission_token_usage(mission_id: str, request: Request) -> Any:
    """Return aggregated LLM token usage and estimated cost for a mission."""
    from ..llm_cost_ledger import get_mission_token_usage as _get_usage
    settings = request.app.state.settings
    return await _get_usage(settings=settings, mission_id=mission_id)
