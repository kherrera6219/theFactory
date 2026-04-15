"""storage_agents.py — Agent heartbeat upserts and runtime event log."""
from __future__ import annotations

import json
from typing import Any

from .settings import Settings
from .storage_core import _json_to_dict, _json_to_list, _to_iso, db_connect


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
