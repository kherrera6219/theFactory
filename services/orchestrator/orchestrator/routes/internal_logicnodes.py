"""Internal LogicNode write and query routes for orchestrator."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query, Request

from .. import storage
from ..audit_events import record_audit_event, summarize_mapping
from ..auth import AuthContext
from ..logicnode_schema import validate_logicnode
from ..models import LogicNodeUpsert
from ._deps import INTERNAL_AUTH_DEP
from .internal_helpers import _agent_id_from_metadata, _agent_id_from_node

LOGGER = logging.getLogger(__name__)

router = APIRouter()


@router.post("/internal/logicnodes")
async def upsert_logicnode(
    request: Request,
    payload: LogicNodeUpsert,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    mission = await _main._fetch_existing_mission(app, payload.mission_id)

    created_at = (
        payload.created_at.isoformat()
        if isinstance(payload.created_at, datetime)
        else (payload.created_at or datetime.now(UTC).isoformat())
    )

    # Enforce schemas/logicnode.schema.json at the write boundary. Validation is
    # non-fatal: an invalid node is logged and persisted with the errors recorded
    # so a single malformed extraction does not abort the whole mission.
    validation_errors: list[str] = []
    try:
        validation_errors = validate_logicnode(
            payload.node, schema_path=app.state.settings.logicnode_schema_path
        )
    except Exception as exc:  # pragma: no cover - schema file misconfiguration
        LOGGER.error("logicnode schema unavailable; skipping validation: %s", exc)
    if validation_errors:
        LOGGER.warning(
            "logicnode %s for mission %s failed schema validation: %s",
            payload.node_id,
            payload.mission_id,
            "; ".join(validation_errors),
        )

    record = await asyncio.to_thread(
        storage.upsert_logicnode,
        app.state.settings,
        payload.mission_id,
        payload.node_id,
        payload.node,
        created_at,
    )
    if validation_errors:
        record["validation_errors"] = validation_errors
    await record_audit_event(
        app,
        mission_id=payload.mission_id,
        mission=mission,
        agent_id=(
            _agent_id_from_node(payload.node)
            or _agent_id_from_metadata(mission.metadata)
            or "SYSTEM"
        ),
        service_name="orchestrator",
        event_type="MISSION_LOGICNODE_WRITTEN",
        object_type="logicnode",
        object_id=payload.node_id,
        status="ERROR" if validation_errors else "SUCCESS",
        payload_summary={
            "node_id": payload.node_id,
            "node": summarize_mapping(payload.node),
            "validation_errors": validation_errors,
        },
    )
    return record


@router.get("/internal/missions/{mission_id}/logicnodes")
@router.get("/missions/{mission_id}/logicnodes", include_in_schema=False)
async def get_logicnodes(
    request: Request,
    mission_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    await _main._fetch_existing_mission(app, mission_id)
    return await asyncio.to_thread(storage.list_logicnodes, app.state.settings, mission_id, limit)
