from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

from . import storage
from .models import AgentActionEventUpsert, MissionRecord
from .project_identity import resolve_project_id
from .tracing import current_span_id, current_trace_id

LOGGER = logging.getLogger(__name__)
_SUMMARY_LIST_LIMIT = 8
_SUMMARY_STRING_LIMIT = 240


def summarize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        compact = " ".join(value.split())
        if len(compact) <= _SUMMARY_STRING_LIMIT:
            return compact
        return f"{compact[:_SUMMARY_STRING_LIMIT]}..."
    if isinstance(value, dict):
        items = list(value.items())[:_SUMMARY_LIST_LIMIT]
        summarized = {str(key): summarize_value(item) for key, item in items}
        if len(value) > _SUMMARY_LIST_LIMIT:
            summarized["_truncated_keys"] = len(value) - _SUMMARY_LIST_LIMIT
        return summarized
    if isinstance(value, list):
        summarized = [summarize_value(item) for item in value[:_SUMMARY_LIST_LIMIT]]
        if len(value) > _SUMMARY_LIST_LIMIT:
            summarized.append({"_truncated_items": len(value) - _SUMMARY_LIST_LIMIT})
        return summarized
    return str(value)


def summarize_mapping(value: Any) -> dict[str, Any]:
    return summarize_value(value) if isinstance(value, dict) else {}


def content_sha256(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        payload = value
    else:
        payload = str(summarize_value(value))
    if not payload:
        return None
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def record_audit_event(
    app: Any,
    *,
    mission_id: str,
    agent_id: str,
    service_name: str,
    event_type: str,
    status: str = "SUCCESS",
    object_type: str | None = None,
    object_id: str | None = None,
    tool_name: str | None = None,
    correlation_id: str | None = None,
    parent_event_id: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    payload_summary: dict[str, Any] | None = None,
    content_hash_source: Any = None,
    content_sha256_value: str | None = None,
    blob_ref: str | None = None,
    mission: MissionRecord | None = None,
) -> dict[str, Any] | None:
    settings = app.state.settings
    mission_record = mission or await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
    if mission_record is None:
        return None

    normalized_started_at = started_at or datetime.now(UTC).isoformat()
    normalized_ended_at = ended_at or normalized_started_at
    summary = summarize_mapping(payload_summary)
    project_id = str(
        mission_record.project_id
        or resolve_project_id(mission_record.metadata, mission_id=mission_record.mission_id)
    )
    payload = AgentActionEventUpsert(
        mission_id=mission_record.mission_id,
        project_id=project_id,
        agent_id=str(agent_id),
        service_name=str(service_name),
        event_type=str(event_type),
        status=str(status),
        object_type=object_type,
        object_id=object_id,
        tool_name=tool_name,
        trace_id=current_trace_id(),
        span_id=current_span_id(),
        correlation_id=correlation_id or mission_record.mission_id,
        parent_event_id=parent_event_id,
        started_at=normalized_started_at,
        ended_at=normalized_ended_at,
        payload_summary=summary,
        content_sha256=content_sha256_value
        or content_sha256(content_hash_source if content_hash_source is not None else summary),
        blob_ref=blob_ref,
    )
    try:
        return await asyncio.to_thread(
            storage.create_agent_action_event,
            settings,
            project_id=payload.project_id or project_id,
            mission_id=payload.mission_id,
            agent_id=payload.agent_id,
            service_name=payload.service_name,
            event_type=payload.event_type,
            status=payload.status,
            event_id=payload.event_id,
            object_type=payload.object_type,
            object_id=payload.object_id,
            tool_name=payload.tool_name,
            trace_id=payload.trace_id,
            span_id=payload.span_id,
            correlation_id=payload.correlation_id,
            parent_event_id=payload.parent_event_id,
            started_at=payload.started_at or normalized_started_at,
            ended_at=payload.ended_at or normalized_ended_at,
            payload_summary=payload.payload_summary,
            content_sha256=payload.content_sha256,
            blob_ref=payload.blob_ref,
        )
    except Exception as exc:
        LOGGER.warning(
            "failed to record audit event %s for mission %s: %s",
            event_type,
            mission_record.mission_id,
            exc,
        )
        return None
