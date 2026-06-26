"""storage_pods.py — Pod assignment persistence and project-level aggregation."""
from __future__ import annotations

import json
from typing import Any

from .settings import Settings
from .storage_core import PodAssignmentConflictError, _json_to_dict, _to_iso, get_connection


def upsert_pod_assignment(
    settings: Settings,
    mission_id: str,
    pod_name: str,
    metadata: dict[str, Any],
    assigned_at: str,
) -> dict[str, Any]:
    """Assign a mission to a pod, rejecting conflicting pod changes."""
    with get_connection() as conn:
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
    """Fetch the pod assignment for one mission."""
    with get_connection() as conn:
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
    """List recent pod assignments ordered by update time."""
    with get_connection() as conn:
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
    """Summarize project mission counts and derived project status."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    project_id,
                    COALESCE(
                        NULLIF(metadata_json->>'project_name', ''),
                        NULLIF(metadata_json->>'source', ''),
                        project_id
                    ) AS project_name,
                    COALESCE(NULLIF(metadata_json->>'source', ''), project_id) AS project_source,
                    COUNT(*) AS mission_count,
                    MAX(updated_at) AS last_updated_at,
                    SUM(CASE WHEN state = 'FAILED' THEN 1 ELSE 0 END) AS failed_count,
                    SUM(CASE WHEN state = 'COMPLETE' THEN 1 ELSE 0 END) AS complete_count
                FROM missions
                GROUP BY
                    project_id,
                    COALESCE(
                        NULLIF(metadata_json->>'project_name', ''),
                        NULLIF(metadata_json->>'source', ''),
                        project_id
                    ),
                    COALESCE(NULLIF(metadata_json->>'source', ''), project_id)
                ORDER BY last_updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    summarized: list[dict[str, Any]] = []
    for row in rows:
        if len(row) >= 7:
            project_id = str(row[0] or "project-unknown")
            project_name = str(row[1] or project_id)
            source = str(row[2] or project_name)
            mission_count = int(row[3])
            last_updated_at = row[4]
            failed_count = int(row[5] or 0)
            complete_count = int(row[6] or 0)
        else:
            source = str(row[0] or "unknown")
            project_id = f"project-{source}"
            project_name = source
            mission_count = int(row[1])
            last_updated_at = row[2]
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
                "project_id": project_id,
                "project_name": project_name,
                "source": source,
                "mission_count": mission_count,
                "failed_count": failed_count,
                "complete_count": complete_count,
                "status": status,
                "last_updated_at": _to_iso(last_updated_at),
            }
        )
    return summarized
