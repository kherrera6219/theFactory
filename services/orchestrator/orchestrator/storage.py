from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

try:
    import psycopg
except ModuleNotFoundError:
    psycopg = None

from .models import MissionEvent, MissionRecord, MissionState
from .settings import Settings


class PodAssignmentConflictError(Exception):
    def __init__(self, existing_assignment: dict[str, Any]) -> None:
        super().__init__("mission already assigned to a different pod")
        self.existing_assignment = existing_assignment


def db_connect(settings: Settings) -> Any:
    if psycopg is None:
        raise RuntimeError("psycopg dependency is not installed")
    return psycopg.connect(settings.postgres_url, autocommit=True)


def ensure_db_schema(settings: Settings) -> None:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS missions (
                    mission_id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    requested_target_language TEXT,
                    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    state TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    source_stream_id TEXT
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_missions_state_created_at
                ON missions (state, created_at DESC);
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS mission_state_events (
                    event_id BIGSERIAL PRIMARY KEY,
                    mission_id TEXT NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
                    previous_state TEXT,
                    new_state TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_mission_state_events_mission_ts
                ON mission_state_events (mission_id, ts DESC);
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS mission_pod_assignments (
                    mission_id TEXT PRIMARY KEY REFERENCES missions(mission_id) ON DELETE CASCADE,
                    pod_name TEXT NOT NULL,
                    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    assigned_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS mission_logicnodes (
                    id BIGSERIAL PRIMARY KEY,
                    mission_id TEXT NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
                    node_id TEXT NOT NULL,
                    node_json JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    UNIQUE (mission_id, node_id)
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_mission_logicnodes_mission_created
                ON mission_logicnodes (mission_id, created_at DESC);
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS mission_knowledge (
                    id BIGSERIAL PRIMARY KEY,
                    mission_id TEXT NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
                    knowledge_id TEXT NOT NULL,
                    content_json JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    UNIQUE (mission_id, knowledge_id)
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_mission_knowledge_mission_created
                ON mission_knowledge (mission_id, created_at DESC);
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS mission_audit_reports (
                    id BIGSERIAL PRIMARY KEY,
                    mission_id TEXT NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
                    audit_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    report_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL,
                    UNIQUE (mission_id, audit_id)
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_mission_audit_reports_mission_created
                ON mission_audit_reports (mission_id, created_at DESC);
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_runtime_heartbeats (
                    agent_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    queue_depth INTEGER NOT NULL DEFAULT 0,
                    workload_pct INTEGER NOT NULL DEFAULT 0,
                    active_mission_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    last_heartbeat TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_runtime_heartbeats_last
                ON agent_runtime_heartbeats (last_heartbeat DESC);
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_runtime_events (
                    id BIGSERIAL PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    previous_state TEXT,
                    new_state TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_runtime_events_agent_created
                ON agent_runtime_events (agent_id, created_at DESC);
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_runtime_events_created
                ON agent_runtime_events (created_at DESC);
                """
            )


def _to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return str(value)


def _json_to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return json.loads(value or "{}")
    if isinstance(value, dict):
        return value
    return {}


def _json_to_list(value: Any) -> list[Any]:
    if isinstance(value, str):
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    if isinstance(value, list):
        return value
    return []


def row_to_mission(row: Any) -> MissionRecord:
    return MissionRecord(
        mission_id=row[0],
        prompt=row[1],
        requested_target_language=row[2],
        metadata=_json_to_dict(row[3]),
        state=MissionState(row[4]),
        created_at=_to_iso(row[5]),
    )


def upsert_mission(settings: Settings, record: MissionRecord, source_stream_id: str | None) -> None:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO missions (
                    mission_id,
                    prompt,
                    requested_target_language,
                    metadata_json,
                    state,
                    created_at,
                    updated_at,
                    source_stream_id
                )
                VALUES (%s, %s, %s, %s::jsonb, %s, %s::timestamptz, NOW(), %s)
                ON CONFLICT (mission_id) DO UPDATE SET
                    prompt = EXCLUDED.prompt,
                    requested_target_language = EXCLUDED.requested_target_language,
                    metadata_json = EXCLUDED.metadata_json,
                    state = EXCLUDED.state,
                    updated_at = NOW(),
                    source_stream_id = EXCLUDED.source_stream_id;
                """,
                (
                    record.mission_id,
                    record.prompt,
                    record.requested_target_language,
                    json.dumps(record.metadata),
                    record.state.value,
                    record.created_at,
                    source_stream_id,
                ),
            )


def fetch_mission(settings: Settings, mission_id: str) -> MissionRecord | None:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    mission_id,
                    prompt,
                    requested_target_language,
                    metadata_json,
                    state,
                    created_at
                FROM missions
                WHERE mission_id = %s
                """,
                (mission_id,),
            )
            row = cur.fetchone()

    if not row:
        return None
    return row_to_mission(row)


def list_missions(settings: Settings, limit: int) -> list[MissionRecord]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    mission_id,
                    prompt,
                    requested_target_language,
                    metadata_json,
                    state,
                    created_at
                FROM missions
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [row_to_mission(row) for row in rows]


def insert_mission_event(
    settings: Settings,
    mission_id: str,
    previous_state: MissionState | None,
    new_state: MissionState,
    event_type: str,
) -> None:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mission_state_events (mission_id, previous_state, new_state, event_type)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    mission_id,
                    previous_state.value if previous_state else None,
                    new_state.value,
                    event_type,
                ),
            )


def list_mission_events(settings: Settings, mission_id: str, limit: int) -> list[MissionEvent]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mission_id, previous_state, new_state, event_type, ts
                FROM mission_state_events
                WHERE mission_id = %s
                ORDER BY ts DESC
                LIMIT %s
                """,
                (mission_id, limit),
            )
            rows = cur.fetchall()

    events: list[MissionEvent] = []
    for row in rows:
        previous_state = MissionState(row[1]) if row[1] else None
        events.append(
            MissionEvent(
                mission_id=row[0],
                previous_state=previous_state,
                new_state=MissionState(row[2]),
                event_type=row[3],
                ts=_to_iso(row[4]),
            )
        )
    return events


def list_recent_mission_events(settings: Settings, limit: int) -> list[MissionEvent]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mission_id, previous_state, new_state, event_type, ts
                FROM mission_state_events
                ORDER BY ts DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    events: list[MissionEvent] = []
    for row in rows:
        previous_state = MissionState(row[1]) if row[1] else None
        events.append(
            MissionEvent(
                mission_id=row[0],
                previous_state=previous_state,
                new_state=MissionState(row[2]),
                event_type=row[3],
                ts=_to_iso(row[4]),
            )
        )
    return events


def transition_mission_state(
    settings: Settings,
    mission_id: str,
    expected_state: MissionState | None,
    new_state: MissionState,
    event_type: str,
) -> MissionRecord | None:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            if expected_state is None:
                cur.execute(
                    """
                    UPDATE missions
                    SET state = %s, updated_at = NOW()
                    WHERE mission_id = %s
                    RETURNING
                        mission_id,
                        prompt,
                        requested_target_language,
                        metadata_json,
                        state,
                        created_at
                    """,
                    (new_state.value, mission_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE missions
                    SET state = %s, updated_at = NOW()
                    WHERE mission_id = %s AND state = %s
                    RETURNING
                        mission_id,
                        prompt,
                        requested_target_language,
                        metadata_json,
                        state,
                        created_at
                    """,
                    (new_state.value, mission_id, expected_state.value),
                )
            row = cur.fetchone()

    if not row:
        return None

    record = row_to_mission(row)
    insert_mission_event(settings, mission_id, expected_state, new_state, event_type)
    return record


def count_missions(settings: Settings) -> int:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM missions")
            row = cur.fetchone()
    return int(row[0] if row else 0)


def mission_state_counts(settings: Settings) -> dict[str, int]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT state, COUNT(*)
                FROM missions
                GROUP BY state
                """
            )
            rows = cur.fetchall()

    return {str(row[0]): int(row[1]) for row in rows}


def upsert_pod_assignment(
    settings: Settings,
    mission_id: str,
    pod_name: str,
    metadata: dict[str, Any],
    assigned_at: str,
) -> dict[str, Any]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mission_pod_assignments (
                    mission_id,
                    pod_name,
                    metadata_json,
                    assigned_at,
                    updated_at
                )
                VALUES (%s, %s, %s::jsonb, %s::timestamptz, NOW())
                ON CONFLICT (mission_id) DO UPDATE SET
                    pod_name = EXCLUDED.pod_name,
                    metadata_json = EXCLUDED.metadata_json,
                    assigned_at = EXCLUDED.assigned_at,
                    updated_at = NOW()
                WHERE mission_pod_assignments.pod_name = EXCLUDED.pod_name
                RETURNING mission_id, pod_name, metadata_json, assigned_at, updated_at
                """,
                (mission_id, pod_name, json.dumps(metadata), assigned_at),
            )
            row = cur.fetchone()

    if row is None:
        existing = get_pod_assignment(settings, mission_id)
        if existing is None:
            raise RuntimeError("pod assignment conflict with no existing record")
        raise PodAssignmentConflictError(existing)

    return {
        "mission_id": row[0],
        "pod_name": row[1],
        "metadata": _json_to_dict(row[2]),
        "assigned_at": _to_iso(row[3]),
        "updated_at": _to_iso(row[4]),
    }


def get_pod_assignment(settings: Settings, mission_id: str) -> dict[str, Any] | None:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mission_id, pod_name, metadata_json, assigned_at, updated_at
                FROM mission_pod_assignments
                WHERE mission_id = %s
                """,
                (mission_id,),
            )
            row = cur.fetchone()

    if not row:
        return None

    return {
        "mission_id": row[0],
        "pod_name": row[1],
        "metadata": _json_to_dict(row[2]),
        "assigned_at": _to_iso(row[3]),
        "updated_at": _to_iso(row[4]),
    }


def list_pod_assignments(settings: Settings, limit: int) -> list[dict[str, Any]]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mission_id, pod_name, metadata_json, assigned_at, updated_at
                FROM mission_pod_assignments
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "mission_id": row[0],
            "pod_name": row[1],
            "metadata": _json_to_dict(row[2]),
            "assigned_at": _to_iso(row[3]),
            "updated_at": _to_iso(row[4]),
        }
        for row in rows
    ]


def upsert_logicnode(
    settings: Settings,
    mission_id: str,
    node_id: str,
    node: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mission_logicnodes (mission_id, node_id, node_json, created_at)
                VALUES (%s, %s, %s::jsonb, %s::timestamptz)
                ON CONFLICT (mission_id, node_id) DO UPDATE SET
                    node_json = EXCLUDED.node_json,
                    created_at = EXCLUDED.created_at
                RETURNING mission_id, node_id, node_json, created_at
                """,
                (mission_id, node_id, json.dumps(node), created_at),
            )
            row = cur.fetchone()

    return {
        "mission_id": row[0],
        "node_id": row[1],
        "node": _json_to_dict(row[2]),
        "created_at": _to_iso(row[3]),
    }


def list_logicnodes(settings: Settings, mission_id: str, limit: int) -> list[dict[str, Any]]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mission_id, node_id, node_json, created_at
                FROM mission_logicnodes
                WHERE mission_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (mission_id, limit),
            )
            rows = cur.fetchall()

    return [
        {
            "mission_id": row[0],
            "node_id": row[1],
            "node": _json_to_dict(row[2]),
            "created_at": _to_iso(row[3]),
        }
        for row in rows
    ]


def list_recent_logicnodes(settings: Settings, limit: int) -> list[dict[str, Any]]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mission_id, node_id, node_json, created_at
                FROM mission_logicnodes
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "mission_id": row[0],
            "node_id": row[1],
            "node": _json_to_dict(row[2]),
            "created_at": _to_iso(row[3]),
        }
        for row in rows
    ]


def upsert_knowledge(
    settings: Settings,
    mission_id: str,
    knowledge_id: str,
    content: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mission_knowledge (mission_id, knowledge_id, content_json, created_at)
                VALUES (%s, %s, %s::jsonb, %s::timestamptz)
                ON CONFLICT (mission_id, knowledge_id) DO UPDATE SET
                    content_json = EXCLUDED.content_json,
                    created_at = EXCLUDED.created_at
                RETURNING mission_id, knowledge_id, content_json, created_at
                """,
                (mission_id, knowledge_id, json.dumps(content), created_at),
            )
            row = cur.fetchone()

    return {
        "mission_id": row[0],
        "knowledge_id": row[1],
        "content": _json_to_dict(row[2]),
        "created_at": _to_iso(row[3]),
    }


def list_knowledge(settings: Settings, mission_id: str, limit: int) -> list[dict[str, Any]]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mission_id, knowledge_id, content_json, created_at
                FROM mission_knowledge
                WHERE mission_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (mission_id, limit),
            )
            rows = cur.fetchall()

    return [
        {
            "mission_id": row[0],
            "knowledge_id": row[1],
            "content": _json_to_dict(row[2]),
            "created_at": _to_iso(row[3]),
        }
        for row in rows
    ]


def upsert_audit_report(
    settings: Settings,
    mission_id: str,
    audit_id: str,
    status: str,
    report: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mission_audit_reports (
                    mission_id,
                    audit_id,
                    status,
                    report_json,
                    created_at
                )
                VALUES (%s, %s, %s, %s::jsonb, %s::timestamptz)
                ON CONFLICT (mission_id, audit_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    report_json = EXCLUDED.report_json,
                    created_at = EXCLUDED.created_at
                RETURNING mission_id, audit_id, status, report_json, created_at
                """,
                (mission_id, audit_id, status, json.dumps(report), created_at),
            )
            row = cur.fetchone()

    return {
        "mission_id": row[0],
        "audit_id": row[1],
        "status": row[2],
        "report": _json_to_dict(row[3]),
        "created_at": _to_iso(row[4]),
    }


def list_audit_reports(settings: Settings, mission_id: str, limit: int) -> list[dict[str, Any]]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mission_id, audit_id, status, report_json, created_at
                FROM mission_audit_reports
                WHERE mission_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (mission_id, limit),
            )
            rows = cur.fetchall()

    return [
        {
            "mission_id": row[0],
            "audit_id": row[1],
            "status": row[2],
            "report": _json_to_dict(row[3]),
            "created_at": _to_iso(row[4]),
        }
        for row in rows
    ]


def list_recent_audit_reports(settings: Settings, limit: int) -> list[dict[str, Any]]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mission_id, audit_id, status, report_json, created_at
                FROM mission_audit_reports
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "mission_id": row[0],
            "audit_id": row[1],
            "status": row[2],
            "report": _json_to_dict(row[3]),
            "created_at": _to_iso(row[4]),
        }
        for row in rows
    ]


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
    normalized_mission_ids = [
        str(mission_id).strip()
        for mission_id in active_mission_ids
        if isinstance(mission_id, str) and str(mission_id).strip()
    ][:100]
    normalized_state = str(state).strip().upper() or "IDLE"
    normalized_queue_depth = max(0, int(queue_depth))
    normalized_workload = min(100, max(0, int(workload_pct)))

    with db_connect(settings) as conn:
        with conn.cursor() as cur:
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
    with db_connect(settings) as conn:
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
    with db_connect(settings) as conn:
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
    with db_connect(settings) as conn:
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


def summarize_projects(settings: Settings, limit: int) -> list[dict[str, Any]]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(NULLIF(metadata_json->>'source', ''), 'unknown') AS project_source,
                    COUNT(*) AS mission_count,
                    MAX(updated_at) AS last_updated_at,
                    SUM(CASE WHEN state = 'FAILED' THEN 1 ELSE 0 END) AS failed_count,
                    SUM(CASE WHEN state = 'COMPLETE' THEN 1 ELSE 0 END) AS complete_count
                FROM missions
                GROUP BY project_source
                ORDER BY last_updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    summarized: list[dict[str, Any]] = []
    for row in rows:
        source = str(row[0])
        mission_count = int(row[1])
        failed_count = int(row[3] or 0)
        complete_count = int(row[4] or 0)
        if failed_count > 0:
            status = "paused"
        elif mission_count > 0 and mission_count == complete_count:
            status = "completed"
        else:
            status = "active"
        summarized.append(
            {
                "project_id": f"project-{source}",
                "source": source,
                "mission_count": mission_count,
                "failed_count": failed_count,
                "complete_count": complete_count,
                "status": status,
                "last_updated_at": _to_iso(row[2]),
            }
        )
    return summarized
