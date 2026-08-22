"""storage_projects.py — Project continuity bus: projects, handoff, work ledger."""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from .project_identity import normalize_project_id, resolve_project_id
from .settings import Settings
from .storage_core import _json_to_dict, _json_to_list, _to_iso, get_connection

ALLOWED_WORK_STATUSES = frozenset({"open", "in_progress", "blocked", "done"})


def upsert_project(
    settings: Settings,
    *,
    project_id: str,
    project_name: str | None = None,
    source: str | None = None,
    status: str = "active",
    plan_authority: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert or update a project row. Returns the persisted project dict."""
    pid = normalize_project_id(project_id)
    name = (project_name or pid).strip() or pid
    plan_authority = plan_authority if isinstance(plan_authority, dict) else {}
    metadata = metadata if isinstance(metadata, dict) else {}
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO projects (
                    project_id, project_name, source, status,
                    plan_authority_json, metadata_json, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, NOW(), NOW())
                ON CONFLICT (project_id) DO UPDATE SET
                    project_name = COALESCE(NULLIF(EXCLUDED.project_name, ''), projects.project_name),
                    source = COALESCE(EXCLUDED.source, projects.source),
                    status = EXCLUDED.status,
                    plan_authority_json = CASE
                        WHEN EXCLUDED.plan_authority_json = '{}'::jsonb
                        THEN projects.plan_authority_json
                        ELSE EXCLUDED.plan_authority_json
                    END,
                    metadata_json = projects.metadata_json || EXCLUDED.metadata_json,
                    updated_at = NOW()
                RETURNING
                    project_id, project_name, source, status,
                    plan_authority_json, metadata_json, created_at, updated_at
                """,
                (
                    pid,
                    name,
                    source,
                    status,
                    json.dumps(plan_authority),
                    json.dumps(metadata),
                ),
            )
            row = cur.fetchone()
    return _row_to_project(row)


def fetch_project(settings: Settings, project_id: str) -> dict[str, Any] | None:
    pid = normalize_project_id(project_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT project_id, project_name, source, status,
                       plan_authority_json, metadata_json, created_at, updated_at
                FROM projects
                WHERE project_id = %s
                """,
                (pid,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return _row_to_project(row)


def upsert_project_handoff(
    settings: Settings,
    *,
    project_id: str,
    current_phase: str = "intake",
    next_action: str = "pm_intake",
    blockers: list[Any] | None = None,
    last_mission_id: str | None = None,
    plan_revision: int | None = None,
    plan_summary: str | None = None,
    authority: dict[str, Any] | None = None,
    evidence_refs: list[Any] | None = None,
) -> dict[str, Any]:
    """Upsert the single handoff row for a project."""
    pid = normalize_project_id(project_id)
    blockers = blockers if isinstance(blockers, list) else []
    authority = authority if isinstance(authority, dict) else {}
    evidence_refs = evidence_refs if isinstance(evidence_refs, list) else []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO project_handoff (
                    project_id, current_phase, next_action, blockers_json,
                    last_mission_id, plan_revision, plan_summary,
                    authority_json, evidence_refs_json, updated_at
                )
                VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s::jsonb, NOW())
                ON CONFLICT (project_id) DO UPDATE SET
                    current_phase = EXCLUDED.current_phase,
                    next_action = EXCLUDED.next_action,
                    blockers_json = EXCLUDED.blockers_json,
                    last_mission_id = COALESCE(EXCLUDED.last_mission_id, project_handoff.last_mission_id),
                    plan_revision = COALESCE(EXCLUDED.plan_revision, project_handoff.plan_revision),
                    plan_summary = COALESCE(EXCLUDED.plan_summary, project_handoff.plan_summary),
                    authority_json = CASE
                        WHEN EXCLUDED.authority_json = '{}'::jsonb
                        THEN project_handoff.authority_json
                        ELSE EXCLUDED.authority_json
                    END,
                    evidence_refs_json = EXCLUDED.evidence_refs_json,
                    updated_at = NOW()
                RETURNING
                    project_id, current_phase, next_action, blockers_json,
                    last_mission_id, plan_revision, plan_summary,
                    authority_json, evidence_refs_json, updated_at
                """,
                (
                    pid,
                    current_phase,
                    next_action,
                    json.dumps(blockers),
                    last_mission_id,
                    int(plan_revision) if plan_revision is not None else 0,
                    plan_summary,
                    json.dumps(authority),
                    json.dumps(evidence_refs),
                ),
            )
            row = cur.fetchone()
    return _row_to_handoff(row)


def fetch_project_handoff(settings: Settings, project_id: str) -> dict[str, Any] | None:
    pid = normalize_project_id(project_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT project_id, current_phase, next_action, blockers_json,
                       last_mission_id, plan_revision, plan_summary,
                       authority_json, evidence_refs_json, updated_at
                FROM project_handoff
                WHERE project_id = %s
                """,
                (pid,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return _row_to_handoff(row)


def upsert_work_item(
    settings: Settings,
    *,
    project_id: str,
    title: str,
    work_item_id: str | None = None,
    status: str = "open",
    source: str = "mission",
    mission_id: str | None = None,
    sort_order: int = 0,
    evidence_ref: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert or update one work-ledger row."""
    pid = normalize_project_id(project_id)
    title_clean = str(title or "").strip() or "untitled"
    status_clean = status if status in ALLOWED_WORK_STATUSES else "open"
    wid = work_item_id or f"wi-{uuid.uuid4().hex[:12]}"
    metadata = metadata if isinstance(metadata, dict) else {}
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO project_work_items (
                    work_item_id, project_id, title, status, source,
                    mission_id, sort_order, evidence_ref, metadata_json,
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
                ON CONFLICT (work_item_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    status = EXCLUDED.status,
                    source = EXCLUDED.source,
                    mission_id = COALESCE(EXCLUDED.mission_id, project_work_items.mission_id),
                    sort_order = EXCLUDED.sort_order,
                    evidence_ref = COALESCE(EXCLUDED.evidence_ref, project_work_items.evidence_ref),
                    metadata_json = project_work_items.metadata_json || EXCLUDED.metadata_json,
                    updated_at = NOW()
                RETURNING
                    work_item_id, project_id, title, status, source,
                    mission_id, sort_order, evidence_ref, metadata_json,
                    created_at, updated_at
                """,
                (
                    wid,
                    pid,
                    title_clean,
                    status_clean,
                    source,
                    mission_id,
                    int(sort_order),
                    evidence_ref,
                    json.dumps(metadata),
                ),
            )
            row = cur.fetchone()
    return _row_to_work_item(row)


def list_work_items(
    settings: Settings,
    project_id: str,
    *,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    pid = normalize_project_id(project_id)
    limit = max(1, min(int(limit), 500))
    with get_connection() as conn:
        with conn.cursor() as cur:
            if status and status in ALLOWED_WORK_STATUSES:
                cur.execute(
                    """
                    SELECT work_item_id, project_id, title, status, source,
                           mission_id, sort_order, evidence_ref, metadata_json,
                           created_at, updated_at
                    FROM project_work_items
                    WHERE project_id = %s AND status = %s
                    ORDER BY sort_order ASC, created_at ASC
                    LIMIT %s
                    """,
                    (pid, status, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT work_item_id, project_id, title, status, source,
                           mission_id, sort_order, evidence_ref, metadata_json,
                           created_at, updated_at
                    FROM project_work_items
                    WHERE project_id = %s
                    ORDER BY sort_order ASC, created_at ASC
                    LIMIT %s
                    """,
                    (pid, limit),
                )
            rows = cur.fetchall()
    return [_row_to_work_item(row) for row in rows]


def mark_work_items_done_for_mission(
    settings: Settings,
    *,
    project_id: str,
    mission_id: str,
    evidence_ref: str | None = None,
    only_statuses: tuple[str, ...] = ("open", "in_progress"),
) -> int:
    """Mark work items claimed by this mission as done. Returns row count."""
    pid = normalize_project_id(project_id)
    statuses = [s for s in only_statuses if s in ALLOWED_WORK_STATUSES]
    if not statuses:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE project_work_items
                SET status = 'done',
                    evidence_ref = COALESCE(%s, evidence_ref),
                    updated_at = NOW()
                WHERE project_id = %s
                  AND mission_id = %s
                  AND status = ANY(%s)
                """,
                (evidence_ref, pid, mission_id, list(statuses)),
            )
            return int(cur.rowcount or 0)


def load_project_bus(settings: Settings, project_id: str) -> dict[str, Any]:
    """Load project + handoff + open/in_progress/blocked work items."""
    pid = normalize_project_id(project_id)
    project = fetch_project(settings, pid)
    handoff = fetch_project_handoff(settings, pid)
    items = list_work_items(settings, pid, limit=200)
    openish = [i for i in items if i.get("status") in {"open", "in_progress", "blocked"}]
    return {
        "project_id": pid,
        "project": project,
        "handoff": handoff,
        "work_items": items,
        "open_work_items": openish,
        "loaded_at": datetime.now(UTC).isoformat(),
    }


def resolve_project_id_for_mission(metadata: dict[str, Any] | None, mission_id: str) -> str:
    return resolve_project_id(metadata, mission_id=mission_id)


def _row_to_project(row: Any) -> dict[str, Any]:
    return {
        "project_id": row[0],
        "project_name": row[1],
        "source": row[2],
        "status": row[3],
        "plan_authority": _json_to_dict(row[4]),
        "metadata": _json_to_dict(row[5]),
        "created_at": _to_iso(row[6]),
        "updated_at": _to_iso(row[7]),
    }


def _row_to_handoff(row: Any) -> dict[str, Any]:
    return {
        "project_id": row[0],
        "current_phase": row[1],
        "next_action": row[2],
        "blockers": _json_to_list(row[3]),
        "last_mission_id": row[4],
        "plan_revision": int(row[5] or 0),
        "plan_summary": row[6],
        "authority": _json_to_dict(row[7]),
        "evidence_refs": _json_to_list(row[8]),
        "updated_at": _to_iso(row[9]),
    }


def _row_to_work_item(row: Any) -> dict[str, Any]:
    return {
        "work_item_id": row[0],
        "project_id": row[1],
        "title": row[2],
        "status": row[3],
        "source": row[4],
        "mission_id": row[5],
        "sort_order": int(row[6] or 0),
        "evidence_ref": row[7],
        "metadata": _json_to_dict(row[8]),
        "created_at": _to_iso(row[9]),
        "updated_at": _to_iso(row[10]),
    }
