"""storage_pods.py — Pod assignment persistence and project-level aggregation."""
from __future__ import annotations

import json
from typing import Any

from .settings import Settings
from .storage_core import PodAssignmentConflictError, _json_to_dict, _to_iso, db_connect


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
