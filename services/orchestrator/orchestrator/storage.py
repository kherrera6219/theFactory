from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

try:
    import psycopg
except ModuleNotFoundError:
    psycopg = None

from . import migrations
from .agent_scaling import (
    PartitionResult as ScalingPartitionResult,
)
from .agent_scaling import (
    all_partitions_complete,
    merge_partition_results,
)
from .agent_scaling import (
    record_partition_result as embed_partition_result,
)
from .models import MissionBuildArtifactRecord, MissionEvent, MissionRecord, MissionState
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
    migrations.apply_migrations(settings, connect=db_connect)


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


def _row_to_build_artifact(row: Any) -> MissionBuildArtifactRecord:
    return MissionBuildArtifactRecord(
        mission_id=row[0],
        artifact_id=row[1],
        artifact_type=row[2],
        stage=row[3],
        status=row[4],
        storage_backend=row[5],
        storage_ref=row[6],
        digest_sha256=row[7],
        size_bytes=int(row[8] or 0),
        manifest=_json_to_dict(row[9]),
        verification=_json_to_dict(row[10]),
        build_log=str(row[11] or ""),
        artifact_text=row[12],
        created_at=_to_iso(row[13]),
        updated_at=_to_iso(row[14]),
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


def update_mission_metadata(
    settings: Settings,
    mission_id: str,
    metadata: dict[str, Any],
) -> MissionRecord | None:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE missions
                SET metadata_json = %s::jsonb, updated_at = NOW()
                WHERE mission_id = %s
                RETURNING
                    mission_id,
                    prompt,
                    requested_target_language,
                    metadata_json,
                    state,
                    created_at
                """,
                (json.dumps(metadata), mission_id),
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


def list_missions_in_states(
    settings: Settings,
    states: list[MissionState] | tuple[MissionState, ...],
    limit: int,
) -> list[MissionRecord]:
    normalized_states = [state.value for state in states if isinstance(state, MissionState)]
    if not normalized_states:
        return []

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
                WHERE state = ANY(%s)
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (normalized_states, max(1, int(limit))),
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


def upsert_review_approval(
    settings: Settings,
    approval_id: str,
    scope: str,
    fingerprint: str,
    summary: str,
    metadata: dict[str, Any],
    receipt_digest: str,
    storage_backend: str,
    approved_at: str,
) -> dict[str, Any]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO review_approvals (
                    approval_id,
                    scope,
                    fingerprint,
                    summary,
                    metadata_json,
                    receipt_digest,
                    storage_backend,
                    approved_at,
                    updated_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s::jsonb,
                    %s,
                    %s,
                    %s::timestamptz,
                    NOW()
                )
                ON CONFLICT (approval_id) DO UPDATE SET
                    scope = EXCLUDED.scope,
                    fingerprint = EXCLUDED.fingerprint,
                    summary = EXCLUDED.summary,
                    metadata_json = EXCLUDED.metadata_json,
                    receipt_digest = EXCLUDED.receipt_digest,
                    storage_backend = EXCLUDED.storage_backend,
                    approved_at = EXCLUDED.approved_at,
                    updated_at = NOW()
                RETURNING
                    approval_id,
                    scope,
                    fingerprint,
                    summary,
                    metadata_json,
                    receipt_digest,
                    storage_backend,
                    approved_at,
                    updated_at
                """,
                (
                    approval_id,
                    scope,
                    fingerprint,
                    summary,
                    json.dumps(metadata),
                    receipt_digest,
                    storage_backend,
                    approved_at,
                ),
            )
            row = cur.fetchone()

    return {
        "approval_id": row[0],
        "scope": row[1],
        "fingerprint": row[2],
        "summary": row[3],
        "metadata": _json_to_dict(row[4]),
        "receipt_digest": row[5],
        "storage_backend": row[6],
        "approved_at": _to_iso(row[7]),
        "updated_at": _to_iso(row[8]),
    }


def get_review_approval(settings: Settings, approval_id: str) -> dict[str, Any] | None:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    approval_id,
                    scope,
                    fingerprint,
                    summary,
                    metadata_json,
                    receipt_digest,
                    storage_backend,
                    approved_at,
                    updated_at
                FROM review_approvals
                WHERE approval_id = %s
                """,
                (approval_id,),
            )
            row = cur.fetchone()

    if row is None:
        return None

    return {
        "approval_id": row[0],
        "scope": row[1],
        "fingerprint": row[2],
        "summary": row[3],
        "metadata": _json_to_dict(row[4]),
        "receipt_digest": row[5],
        "storage_backend": row[6],
        "approved_at": _to_iso(row[7]),
        "updated_at": _to_iso(row[8]),
    }


def upsert_build_artifact(
    settings: Settings,
    mission_id: str,
    artifact_id: str,
    artifact_type: str,
    stage: str,
    status: str,
    storage_backend: str,
    storage_ref: str | None,
    digest_sha256: str | None,
    size_bytes: int,
    manifest: dict[str, Any],
    verification: dict[str, Any],
    build_log: str,
    artifact_text: str | None,
    created_at: str,
) -> dict[str, Any]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mission_build_artifacts (
                    mission_id,
                    artifact_id,
                    artifact_type,
                    stage,
                    status,
                    storage_backend,
                    storage_ref,
                    digest_sha256,
                    size_bytes,
                    manifest_json,
                    verification_json,
                    build_log,
                    artifact_text,
                    created_at,
                    updated_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s::jsonb,
                    %s::jsonb,
                    %s,
                    %s,
                    %s::timestamptz,
                    NOW()
                )
                ON CONFLICT (mission_id, artifact_id) DO UPDATE SET
                    artifact_type = EXCLUDED.artifact_type,
                    stage = EXCLUDED.stage,
                    status = EXCLUDED.status,
                    storage_backend = EXCLUDED.storage_backend,
                    storage_ref = EXCLUDED.storage_ref,
                    digest_sha256 = EXCLUDED.digest_sha256,
                    size_bytes = EXCLUDED.size_bytes,
                    manifest_json = EXCLUDED.manifest_json,
                    verification_json = EXCLUDED.verification_json,
                    build_log = EXCLUDED.build_log,
                    artifact_text = EXCLUDED.artifact_text,
                    created_at = EXCLUDED.created_at,
                    updated_at = NOW()
                RETURNING
                    mission_id,
                    artifact_id,
                    artifact_type,
                    stage,
                    status,
                    storage_backend,
                    storage_ref,
                    digest_sha256,
                    size_bytes,
                    manifest_json,
                    verification_json,
                    build_log,
                    artifact_text,
                    created_at,
                    updated_at
                """,
                (
                    mission_id,
                    artifact_id,
                    artifact_type,
                    stage,
                    status,
                    storage_backend,
                    storage_ref,
                    digest_sha256,
                    max(0, int(size_bytes)),
                    json.dumps(manifest),
                    json.dumps(verification),
                    build_log,
                    artifact_text,
                    created_at,
                ),
            )
            row = cur.fetchone()

    record = _row_to_build_artifact(row)
    return record.model_dump(mode="json")


def list_build_artifacts(settings: Settings, mission_id: str, limit: int) -> list[dict[str, Any]]:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    mission_id,
                    artifact_id,
                    artifact_type,
                    stage,
                    status,
                    storage_backend,
                    storage_ref,
                    digest_sha256,
                    size_bytes,
                    manifest_json,
                    verification_json,
                    build_log,
                    artifact_text,
                    created_at,
                    updated_at
                FROM mission_build_artifacts
                WHERE mission_id = %s
                ORDER BY updated_at DESC, created_at DESC
                LIMIT %s
                """,
                (mission_id, limit),
            )
            rows = cur.fetchall()

    records: list[dict[str, Any]] = []
    for row in rows:
        record = _row_to_build_artifact(row).model_dump(mode="json")
        record["artifact_text"] = None
        records.append(record)
    return records


def get_build_artifact(
    settings: Settings,
    mission_id: str,
    artifact_id: str,
) -> dict[str, Any] | None:
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    mission_id,
                    artifact_id,
                    artifact_type,
                    stage,
                    status,
                    storage_backend,
                    storage_ref,
                    digest_sha256,
                    size_bytes,
                    manifest_json,
                    verification_json,
                    build_log,
                    artifact_text,
                    created_at,
                    updated_at
                FROM mission_build_artifacts
                WHERE mission_id = %s AND artifact_id = %s
                """,
                (mission_id, artifact_id),
            )
            row = cur.fetchone()

    if row is None:
        return None
    return _row_to_build_artifact(row).model_dump(mode="json")


def _locked_mission_metadata_update(
    settings: Settings,
    mission_id: str,
    updater: Any,
) -> MissionRecord | None:
    if psycopg is None:
        raise RuntimeError("psycopg dependency is not installed")

    conn = psycopg.connect(settings.postgres_url, autocommit=False)
    try:
        with conn:
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
                    FOR UPDATE
                    """,
                    (mission_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None

                mission = row_to_mission(row)
                metadata = dict(mission.metadata) if isinstance(mission.metadata, dict) else {}
                updated_metadata = updater(metadata, mission)
                if not isinstance(updated_metadata, dict):
                    updated_metadata = metadata

                cur.execute(
                    """
                    UPDATE missions
                    SET metadata_json = %s::jsonb, updated_at = NOW()
                    WHERE mission_id = %s
                    RETURNING
                        mission_id,
                        prompt,
                        requested_target_language,
                        metadata_json,
                        state,
                        created_at
                    """,
                    (json.dumps(updated_metadata), mission_id),
                )
                updated_row = cur.fetchone()
                if updated_row is None:
                    return None
        return row_to_mission(updated_row)
    finally:
        conn.close()


def record_partition_result(
    settings: Settings,
    mission_id: str,
    result: dict[str, Any],
) -> MissionRecord | None:
    partition_result = ScalingPartitionResult(
        partition_id=str(result.get("partition_id", "")),
        instance_index=int(result.get("instance_index", 0)),
        agent_id=str(result.get("agent_id", "")),
        logicnodes=[node for node in result.get("logicnodes", []) if isinstance(node, dict)],
        artifacts=[
            artifact for artifact in result.get("artifacts", []) if isinstance(artifact, dict)
        ],
        report=result.get("report") if isinstance(result.get("report"), dict) else {},
        completed_at=str(result.get("completed_at", "")),
    )

    def _update(metadata: dict[str, Any], _mission: MissionRecord) -> dict[str, Any]:
        embed_partition_result(metadata, partition_result)
        metadata["last_partition_result_at"] = partition_result.completed_at
        partition_results = metadata.get("partition_results")
        if isinstance(partition_results, dict):
            metadata["partition_result_count"] = len(partition_results)

        if all_partitions_complete(metadata):
            results: list[ScalingPartitionResult] = []
            for raw in (metadata.get("partition_results") or {}).values():
                if not isinstance(raw, dict):
                    continue
                results.append(
                    ScalingPartitionResult(
                        partition_id=str(raw.get("partition_id", "")),
                        instance_index=int(raw.get("instance_index", 0)),
                        agent_id=str(raw.get("agent_id", "")),
                        logicnodes=[
                            node for node in raw.get("logicnodes", []) if isinstance(node, dict)
                        ],
                        artifacts=[
                            artifact
                            for artifact in raw.get("artifacts", [])
                            if isinstance(artifact, dict)
                        ],
                        report=raw.get("report") if isinstance(raw.get("report"), dict) else {},
                        completed_at=str(raw.get("completed_at", "")),
                    )
                )
            merged = merge_partition_results(results)
            metadata["merged_partition_result"] = merged.to_dict()
            metadata["scaling_merge_complete"] = True
            metadata["scaling_completed_at"] = merged.merged_at
        else:
            metadata["scaling_merge_complete"] = False

        return metadata

    return _locked_mission_metadata_update(settings, mission_id, _update)


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
