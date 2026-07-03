"""storage_agents.py — Agent heartbeat upserts and runtime event log."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from .models import AgentActionEventRecord
from .settings import Settings
from .storage_core import _json_to_dict, _json_to_list, _to_iso, get_connection


def upsert_agent_heartbeat(
    settings: Settings,
    agent_id: str,
    state: str,
    queue_depth: int,
    workload_pct: int,
    active_mission_ids: list[str],
    metadata: dict[str, Any],
    last_heartbeat: str,
) -> dict[str, Any]:
    """Insert or update one agent heartbeat and log state changes atomically."""
    normalized_mission_ids = [
        str(mission_id).strip()
        for mission_id in active_mission_ids
        if isinstance(mission_id, str) and str(mission_id).strip()
    ][:100]
    normalized_state = str(state).strip().upper() or "IDLE"
    normalized_queue_depth = max(0, int(queue_depth))
    normalized_workload = min(100, max(0, int(workload_pct)))

    with get_connection() as conn:
        # Pool connections use autocommit=True, so the heartbeat upsert and the
        # AGENT_STATE_CHANGED event would otherwise commit independently. The
        # combined transaction() + cursor() wraps both writes so a failure
        # between them rolls back cleanly (no heartbeat without its event).
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(
                """
                SELECT state
                FROM agent_runtime_heartbeats
                WHERE agent_id = %s
                """,
                (agent_id,),
            )
            previous = cur.fetchone()
            previous_state = str(previous[0]) if previous else None

            cur.execute(
                """
                INSERT INTO agent_runtime_heartbeats (
                    agent_id,
                    state,
                    queue_depth,
                    workload_pct,
                    active_mission_ids_json,
                    metadata_json,
                    last_heartbeat,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::timestamptz, NOW())
                ON CONFLICT (agent_id) DO UPDATE SET
                    state = EXCLUDED.state,
                    queue_depth = EXCLUDED.queue_depth,
                    workload_pct = EXCLUDED.workload_pct,
                    active_mission_ids_json = EXCLUDED.active_mission_ids_json,
                    metadata_json = EXCLUDED.metadata_json,
                    last_heartbeat = EXCLUDED.last_heartbeat,
                    updated_at = NOW()
                RETURNING
                    agent_id,
                    state,
                    queue_depth,
                    workload_pct,
                    active_mission_ids_json,
                    metadata_json,
                    last_heartbeat,
                    updated_at
                """,
                (
                    agent_id,
                    normalized_state,
                    normalized_queue_depth,
                    normalized_workload,
                    json.dumps(normalized_mission_ids),
                    json.dumps(metadata),
                    last_heartbeat,
                ),
            )
            row = cur.fetchone()

            state_changed = previous_state is None or previous_state != normalized_state
            if state_changed:
                cur.execute(
                    """
                    INSERT INTO agent_runtime_events (
                        agent_id,
                        previous_state,
                        new_state,
                        event_type,
                        payload_json,
                        created_at
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        'AGENT_STATE_CHANGED',
                        %s::jsonb,
                        %s::timestamptz
                    )
                    """,
                    (
                        agent_id,
                        previous_state,
                        normalized_state,
                        json.dumps(
                            {
                                "queue_depth": normalized_queue_depth,
                                "workload_pct": normalized_workload,
                                "active_mission_ids": normalized_mission_ids,
                                "metadata": metadata,
                            }
                        ),
                        last_heartbeat,
                    ),
                )

    return {
        "agent_id": row[0],
        "state": row[1],
        "queue_depth": int(row[2]),
        "workload_pct": int(row[3]),
        "active_mission_ids": [
            str(value) for value in _json_to_list(row[4]) if isinstance(value, str)
        ],
        "metadata": _json_to_dict(row[5]),
        "last_heartbeat": _to_iso(row[6]),
        "updated_at": _to_iso(row[7]),
        "previous_state": previous_state,
        "state_changed": state_changed,
    }


def get_agent_heartbeat(settings: Settings, agent_id: str) -> dict[str, Any] | None:
    """Return the latest stored heartbeat for one agent, if present."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    agent_id,
                    state,
                    queue_depth,
                    workload_pct,
                    active_mission_ids_json,
                    metadata_json,
                    last_heartbeat,
                    updated_at
                FROM agent_runtime_heartbeats
                WHERE agent_id = %s
                """,
                (agent_id,),
            )
            row = cur.fetchone()

    if row is None:
        return None
    return {
        "agent_id": row[0],
        "state": str(row[1]),
        "queue_depth": int(row[2]),
        "workload_pct": int(row[3]),
        "active_mission_ids": [
            str(value) for value in _json_to_list(row[4]) if isinstance(value, str)
        ],
        "metadata": _json_to_dict(row[5]),
        "last_heartbeat": _to_iso(row[6]),
        "updated_at": _to_iso(row[7]),
    }


def list_agent_heartbeats(settings: Settings, limit: int) -> list[dict[str, Any]]:
    """Return recent agent heartbeats ordered by heartbeat timestamp."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    agent_id,
                    state,
                    queue_depth,
                    workload_pct,
                    active_mission_ids_json,
                    metadata_json,
                    last_heartbeat,
                    updated_at
                FROM agent_runtime_heartbeats
                ORDER BY last_heartbeat DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "agent_id": row[0],
            "state": str(row[1]),
            "queue_depth": int(row[2]),
            "workload_pct": int(row[3]),
            "active_mission_ids": [
                str(value) for value in _json_to_list(row[4]) if isinstance(value, str)
            ],
            "metadata": _json_to_dict(row[5]),
            "last_heartbeat": _to_iso(row[6]),
            "updated_at": _to_iso(row[7]),
        }
        for row in rows
    ]


def list_recent_agent_events(settings: Settings, limit: int) -> list[dict[str, Any]]:
    """Return recent agent runtime state-change events."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    agent_id,
                    previous_state,
                    new_state,
                    event_type,
                    payload_json,
                    created_at
                FROM agent_runtime_events
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "event_id": int(row[0]),
            "agent_id": row[1],
            "previous_state": row[2],
            "new_state": row[3],
            "event_type": row[4],
            "payload": _json_to_dict(row[5]),
            "created_at": _to_iso(row[6]),
        }
        for row in rows
    ]


def _normalize_payload_summary(payload_summary: Any) -> dict[str, Any]:
    return dict(payload_summary) if isinstance(payload_summary, dict) else {}


def _event_duration_ms(started_at: Any, ended_at: Any) -> int | None:
    if not isinstance(started_at, datetime) or not isinstance(ended_at, datetime):
        return None
    delta_ms = int((ended_at - started_at).total_seconds() * 1000)
    return max(0, delta_ms)


def _event_digest_payload(
    *,
    prev_digest: str | None,
    record: AgentActionEventRecord,
    content_sha256: str | None,
) -> str:
    payload = {
        "prev_event_digest_sha256": prev_digest,
        "event_id": record.event_id,
        "project_id": record.project_id,
        "mission_id": record.mission_id,
        "agent_id": record.agent_id,
        "service_name": record.service_name,
        "event_type": record.event_type,
        "status": record.status,
        "object_type": record.object_type,
        "object_id": record.object_id,
        "tool_name": record.tool_name,
        "trace_id": record.trace_id,
        "span_id": record.span_id,
        "correlation_id": record.correlation_id,
        "parent_event_id": record.parent_event_id,
        "started_at": _to_iso(record.started_at),
        "ended_at": _to_iso(record.ended_at) if record.ended_at else None,
        "duration_ms": record.duration_ms,
        "payload_summary": _normalize_payload_summary(record.payload_summary),
        "content_sha256": content_sha256,
        "blob_ref": record.blob_ref,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _content_digest(record: AgentActionEventRecord) -> str | None:
    if record.content_sha256:
        return str(record.content_sha256)
    payload_summary = _normalize_payload_summary(record.payload_summary)
    if payload_summary:
        return hashlib.sha256(
            json.dumps(payload_summary, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    if record.blob_ref:
        return hashlib.sha256(str(record.blob_ref).encode("utf-8")).hexdigest()
    return None


def _row_to_agent_action_event(row: Any) -> dict[str, Any]:
    return {
        "event_id": str(row[0]),
        "project_id": str(row[1]),
        "mission_id": str(row[2]),
        "agent_id": str(row[3]),
        "service_name": str(row[4]),
        "event_type": str(row[5]),
        "status": str(row[6]),
        "object_type": row[7],
        "object_id": row[8],
        "tool_name": row[9],
        "trace_id": row[10],
        "span_id": row[11],
        "correlation_id": row[12],
        "parent_event_id": row[13],
        "started_at": _to_iso(row[14]),
        "ended_at": _to_iso(row[15]) if row[15] else None,
        "duration_ms": int(row[16]) if row[16] is not None else None,
        "payload_summary": _json_to_dict(row[17]),
        "content_sha256": row[18],
        "blob_ref": row[19],
        "prev_event_digest_sha256": row[20],
        "event_digest_sha256": str(row[21]),
        "created_at": _to_iso(row[22]),
    }


def insert_agent_action_event(settings: Settings, record: AgentActionEventRecord) -> dict[str, Any]:
    """Persist an immutable agent action event with digest chaining."""
    normalized = AgentActionEventRecord(
        **{
            **record.model_dump(mode="python"),
            "payload_summary": _normalize_payload_summary(record.payload_summary),
            "duration_ms": (
                record.duration_ms
                if record.duration_ms is not None
                else _event_duration_ms(record.started_at, record.ended_at)
            ),
            "created_at": record.created_at,
        }
    )
    content_sha256 = _content_digest(normalized)
    with get_connection() as conn:
        # Pool connections use autocommit=True, so the read-latest-digest and
        # the chained INSERT would otherwise run as two independent
        # statements with no isolation between them. Two concurrent events
        # for the same project_id could both read the same prev_digest and
        # both chain to it, forking the tamper-evident hash chain with no
        # error. The transaction() plus a per-project advisory lock
        # serializes concurrent writers so only one can be inside this
        # read-then-chain critical section for a given project_id at a time.
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (normalized.project_id,),
            )
            cur.execute(
                """
                SELECT event_digest_sha256
                FROM agent_action_events
                WHERE project_id = %s
                ORDER BY created_at DESC, event_id DESC
                LIMIT 1
                """,
                (normalized.project_id,),
            )
            prev_row = cur.fetchone()
            prev_digest = str(prev_row[0]) if prev_row and prev_row[0] else None
            event_digest = hashlib.sha256(
                _event_digest_payload(
                    prev_digest=prev_digest,
                    record=normalized,
                    content_sha256=content_sha256,
                ).encode("utf-8")
            ).hexdigest()
            cur.execute(
                """
                INSERT INTO agent_action_events (
                    event_id,
                    project_id,
                    mission_id,
                    agent_id,
                    service_name,
                    event_type,
                    status,
                    object_type,
                    object_id,
                    tool_name,
                    trace_id,
                    span_id,
                    correlation_id,
                    parent_event_id,
                    started_at,
                    ended_at,
                    duration_ms,
                    payload_summary_json,
                    content_sha256,
                    blob_ref,
                    prev_event_digest_sha256,
                    event_digest_sha256,
                    created_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::timestamptz, %s::timestamptz, %s, %s::jsonb, %s, %s, %s, %s,
                    %s::timestamptz
                )
                RETURNING
                    event_id,
                    project_id,
                    mission_id,
                    agent_id,
                    service_name,
                    event_type,
                    status,
                    object_type,
                    object_id,
                    tool_name,
                    trace_id,
                    span_id,
                    correlation_id,
                    parent_event_id,
                    started_at,
                    ended_at,
                    duration_ms,
                    payload_summary_json,
                    content_sha256,
                    blob_ref,
                    prev_event_digest_sha256,
                    event_digest_sha256,
                    created_at
                """,
                (
                    normalized.event_id,
                    normalized.project_id,
                    normalized.mission_id,
                    normalized.agent_id,
                    normalized.service_name,
                    normalized.event_type,
                    normalized.status,
                    normalized.object_type,
                    normalized.object_id,
                    normalized.tool_name,
                    normalized.trace_id,
                    normalized.span_id,
                    normalized.correlation_id,
                    normalized.parent_event_id,
                    normalized.started_at,
                    normalized.ended_at,
                    normalized.duration_ms,
                    json.dumps(_normalize_payload_summary(normalized.payload_summary)),
                    content_sha256,
                    normalized.blob_ref,
                    prev_digest,
                    event_digest,
                    normalized.created_at,
                ),
            )
            row = cur.fetchone()
    return _row_to_agent_action_event(row)


def create_agent_action_event(
    settings: Settings,
    *,
    project_id: str,
    mission_id: str,
    agent_id: str,
    service_name: str,
    event_type: str,
    status: str = "SUCCESS",
    event_id: str | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    tool_name: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
    correlation_id: str | None = None,
    parent_event_id: str | None = None,
    started_at: str | datetime,
    ended_at: str | datetime | None = None,
    payload_summary: dict[str, Any] | None = None,
    content_sha256: str | None = None,
    blob_ref: str | None = None,
) -> dict[str, Any]:
    """Build and persist an agent action event from primitive fields."""
    record = AgentActionEventRecord(
        event_id=event_id or f"aevt-{uuid.uuid4()}",
        project_id=project_id,
        mission_id=mission_id,
        agent_id=agent_id,
        service_name=service_name,
        event_type=event_type,
        status=status,
        object_type=object_type,
        object_id=object_id,
        tool_name=tool_name,
        trace_id=trace_id,
        span_id=span_id,
        correlation_id=correlation_id,
        parent_event_id=parent_event_id,
        started_at=started_at,
        ended_at=ended_at,
        duration_ms=_event_duration_ms(started_at, ended_at),
        payload_summary=_normalize_payload_summary(payload_summary),
        content_sha256=content_sha256,
        blob_ref=blob_ref,
        prev_event_digest_sha256=None,
        event_digest_sha256="pending",
        created_at=ended_at or started_at,
    )
    return insert_agent_action_event(settings, record)


def list_mission_agent_action_events(
    settings: Settings,
    mission_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    """List recent action events for a single mission."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    event_id,
                    project_id,
                    mission_id,
                    agent_id,
                    service_name,
                    event_type,
                    status,
                    object_type,
                    object_id,
                    tool_name,
                    trace_id,
                    span_id,
                    correlation_id,
                    parent_event_id,
                    started_at,
                    ended_at,
                    duration_ms,
                    payload_summary_json,
                    content_sha256,
                    blob_ref,
                    prev_event_digest_sha256,
                    event_digest_sha256,
                    created_at
                FROM agent_action_events
                WHERE mission_id = %s
                ORDER BY created_at DESC, event_id DESC
                LIMIT %s
                """,
                (mission_id, limit),
            )
            rows = cur.fetchall()
    return [_row_to_agent_action_event(row) for row in rows]


def list_project_agent_action_events(
    settings: Settings,
    project_id: str,
    limit: int,
    *,
    mission_id: str | None = None,
    agent_id: str | None = None,
    tool_name: str | None = None,
) -> list[dict[str, Any]]:
    """List recent action events for a project with optional filters."""
    query = """
        SELECT
            event_id,
            project_id,
            mission_id,
            agent_id,
            service_name,
            event_type,
            status,
            object_type,
            object_id,
            tool_name,
            trace_id,
            span_id,
            correlation_id,
            parent_event_id,
            started_at,
            ended_at,
            duration_ms,
            payload_summary_json,
            content_sha256,
            blob_ref,
            prev_event_digest_sha256,
            event_digest_sha256,
            created_at
        FROM agent_action_events
        WHERE project_id = %s
          AND (%s::text IS NULL OR mission_id = %s)
          AND (%s::text IS NULL OR agent_id = %s)
          AND (%s::text IS NULL OR tool_name = %s)
        ORDER BY created_at DESC, event_id DESC
        LIMIT %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    project_id,
                    mission_id,
                    mission_id,
                    agent_id,
                    agent_id,
                    tool_name,
                    tool_name,
                    limit,
                ),
            )
            rows = cur.fetchall()
    return [_row_to_agent_action_event(row) for row in rows]


def prune_audit_tables(settings: Settings, retention_days: int | None = None) -> list[dict[str, Any]]:
    """Delete audit rows older than the retention window via prune_audit_tables().

    Calls the SECURITY DEFINER SQL function (migration V008) so retention keeps
    working even after V009 revokes DELETE on the audit tables from the app role.
    Returns one ``{"table_name", "rows_deleted"}`` entry per audit table.
    """
    days = retention_days if retention_days is not None else settings.audit_retention_days
    days = max(1, int(days))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT table_name, rows_deleted FROM prune_audit_tables(%s)", (days,))
            rows = cur.fetchall()
    return [{"table_name": str(row[0]), "rows_deleted": int(row[1])} for row in rows]
