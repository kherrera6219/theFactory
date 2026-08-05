"""storage_pods.py — Pod assignment persistence and project-level aggregation."""
from __future__ import annotations

import json
from typing import Any

from .settings import Settings
from .storage_core import PodAssignmentConflictError, _json_to_dict, _to_iso, get_connection

#: ``metadata.assigned_by`` value marking a row the orchestrator wrote when it
#: delegated the mission, before (or instead of) any pod worker claiming it.
PROVISIONAL_ASSIGNED_BY = "orchestrator"

#: A claim may replace a provisional row; a provisional write may only replace
#: another provisional row.  Expressed as ``ON CONFLICT ... DO UPDATE ... WHERE``
#: predicates -- when the predicate is false Postgres updates nothing and
#: ``RETURNING`` yields no row, which is how the caller detects a conflict
#: without a second round trip.
_CLAIM_CONFLICT_PREDICATE = (
    "WHERE mission_pod_assignments.pod_name = EXCLUDED.pod_name"
    " OR mission_pod_assignments.metadata_json->>'assigned_by' = %(provisional)s"
)
_PROVISIONAL_CONFLICT_PREDICATE = (
    "WHERE mission_pod_assignments.metadata_json->>'assigned_by' = %(provisional)s"
)


def upsert_pod_assignment(
    settings: Settings,
    mission_id: str,
    pod_name: str,
    metadata: dict[str, Any],
    assigned_at: str,
    *,
    provisional: bool = False,
) -> dict[str, Any]:
    """Assign a mission to a pod, rejecting conflicting pod changes.

    Two kinds of write share this table, distinguished by ``provisional``:

    ``provisional=False`` (default) -- a *claim*, written by the pod worker that
    has accepted execution.  It may keep its own row up to date and may take
    over a provisional row, but never another worker's claim on a different pod.

    ``provisional=True`` -- the orchestrator recording which pod manager the
    delegation chain routed the mission to, at the moment it emits
    ``MISSION_POD_MANAGER_ASSIGNED``.  It inserts when no row exists and updates
    only its own provisional rows, so it can never overwrite or downgrade a real
    claim (a re-run of the delegation phase is therefore idempotent).

    Raises ``PodAssignmentConflictError`` when the write is refused.
    """
    predicate = _PROVISIONAL_CONFLICT_PREDICATE if provisional else _CLAIM_CONFLICT_PREDICATE
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO mission_pod_assignments (
                    mission_id,
                    pod_name,
                    metadata_json,
                    assigned_at,
                    updated_at
                )
                VALUES (
                    %(mission_id)s,
                    %(pod_name)s,
                    %(metadata)s::jsonb,
                    %(assigned_at)s::timestamptz,
                    NOW()
                )
                ON CONFLICT (mission_id) DO UPDATE SET
                    pod_name = EXCLUDED.pod_name,
                    metadata_json = EXCLUDED.metadata_json,
                    assigned_at = EXCLUDED.assigned_at,
                    updated_at = NOW()
                {predicate}
                RETURNING mission_id, pod_name, metadata_json, assigned_at, updated_at
                """,
                {
                    "mission_id": mission_id,
                    "pod_name": pod_name,
                    "metadata": json.dumps(metadata),
                    "assigned_at": assigned_at,
                    "provisional": PROVISIONAL_ASSIGNED_BY,
                },
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


def is_provisional_assignment(record: Any) -> bool:
    """True when ``record`` is an orchestrator-written row no worker has claimed.

    Accepts either a full assignment record or its ``metadata`` mapping so both
    the orchestrator (which holds records) and the pod worker (which holds the
    decoded JSON body of the internal endpoint) can use one predicate.
    """
    if not isinstance(record, dict):
        return False
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        metadata = record
    return str(metadata.get("assigned_by") or "").strip().lower() == PROVISIONAL_ASSIGNED_BY


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
