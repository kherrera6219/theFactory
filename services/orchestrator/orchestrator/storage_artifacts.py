"""storage_artifacts.py — Audit reports, review approvals, and build artifact persistence."""
from __future__ import annotations

import json
from typing import Any

from .models import MissionBuildArtifactRecord
from .settings import Settings
from .storage_core import _json_to_dict, _to_iso, db_connect


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
    expires_at: str | None,
    hmac_digest: str | None,
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
                    expires_at,
                    hmac_digest,
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
                    %s::timestamptz,
                    %s,
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
                    expires_at = EXCLUDED.expires_at,
                    hmac_digest = EXCLUDED.hmac_digest,
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
                    expires_at,
                    hmac_digest,
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
                    expires_at,
                    hmac_digest,
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
        "expires_at": _to_iso(row[8]) if row[8] is not None else None,
        "hmac_digest": row[9],
        "updated_at": _to_iso(row[10]),
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
                    expires_at,
                    hmac_digest,
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
        "expires_at": _to_iso(row[8]) if row[8] is not None else None,
        "hmac_digest": row[9],
        "updated_at": _to_iso(row[10]),
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
