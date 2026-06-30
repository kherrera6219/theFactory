"""storage_artifacts.py — Audit reports, review approvals, and build artifact persistence."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from .models import MissionBuildArtifactRecord
from .settings import Settings
from .storage_core import _json_to_dict, _to_iso, get_connection

LOGGER = logging.getLogger(__name__)


def _artifact_text_trace(value: str) -> dict[str, Any]:
    return {
        "digest_sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
        "length_chars": len(value),
        "size_bytes": len(value.encode("utf-8")),
        "non_ascii_count": sum(1 for char in value if ord(char) > 127),
    }


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
    """Insert or update an audit report for a mission."""
    with get_connection() as conn:
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
    """List recent audit reports for one mission."""
    with get_connection() as conn:
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
    """List recent audit reports across missions."""
    with get_connection() as conn:
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
    """Insert or update a durable human-review approval receipt."""
    with get_connection() as conn:
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
    """Fetch one human-review approval receipt by id."""
    with get_connection() as conn:
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
    """Insert or update a generated build artifact record."""
    # ── S4-05: offload large artifact_text to object storage ──────────────────
    threshold = int(getattr(settings, "object_storage_size_threshold_bytes", 524288))
    if (
        settings.object_storage_enabled
        and artifact_text
        and len(artifact_text.encode("utf-8")) > threshold
    ):
        try:
            from . import object_store
            prefix = settings.object_storage_prefix.strip("/")
            key = f"{prefix}/{mission_id}/artifacts/{artifact_id}.txt"
            meta = {
                "mission-id": mission_id,
                "artifact-id": artifact_id,
                "artifact-type": artifact_type,
                "created-at": created_at,
            }
            object_store.put_object(
                settings,
                key=key,
                body=artifact_text.encode("utf-8"),
                content_type="text/plain; charset=utf-8",
                metadata=meta,
            )
            # Route artifact through S3 — clear inline text to avoid Postgres bloat
            storage_backend = "s3"
            storage_ref = key
            artifact_text = None
            LOGGER.info(
                "artifact %s/%s offloaded to object storage key=%s", mission_id, artifact_id, key
            )
        except Exception as exc:
            # Fall back to Postgres inline storage — log but do not fail the mission
            LOGGER.warning(
                "object storage offload failed for %s/%s: %s — storing inline",
                mission_id, artifact_id, exc,
            )

    with get_connection() as conn:
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

    record = _row_to_build_artifact(row).model_dump(mode="json")
    persisted_text = record.get("artifact_text")
    if isinstance(persisted_text, str):
        manifest = record.get("manifest") if isinstance(record.get("manifest"), dict) else {}
        encoding_trace = (
            manifest.get("encoding_trace") if isinstance(manifest.get("encoding_trace"), dict) else {}
        )
        manifest["encoding_trace"] = {
            **encoding_trace,
            "storage_readback": _artifact_text_trace(persisted_text),
        }
        record["manifest"] = manifest
    return record


def list_build_artifacts(settings: Settings, mission_id: str, limit: int) -> list[dict[str, Any]]:
    """List build artifacts for a mission without inline artifact text."""
    with get_connection() as conn:
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
    """Fetch one build artifact, including inline text when stored."""
    with get_connection() as conn:
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


def insert_testdata_manifest(
    settings: Settings,
    mission_id: str,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Persist a TESTDATA manifest for a mission."""
    language = str(manifest.get("language") or "").strip() or None
    base_image = str(manifest.get("base_image") or "").strip() or None
    test_framework = str(manifest.get("test_framework") or "").strip() or None
    source = str(manifest.get("source") or "").strip() or None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mission_testdata_manifests (
                    mission_id,
                    manifest_json,
                    language,
                    base_image,
                    test_framework,
                    source
                )
                VALUES (%s, %s::jsonb, %s, %s, %s, %s)
                RETURNING
                    mission_id,
                    manifest_json,
                    language,
                    base_image,
                    test_framework,
                    source,
                    created_at
                """,
                (
                    mission_id,
                    json.dumps(manifest),
                    language,
                    base_image,
                    test_framework,
                    source,
                ),
            )
            row = cur.fetchone()
    return {
        "mission_id": row[0],
        "manifest": _json_to_dict(row[1]),
        "language": row[2],
        "base_image": row[3],
        "test_framework": row[4],
        "source": row[5],
        "created_at": _to_iso(row[6]),
    }


def get_testdata_manifest(settings: Settings, mission_id: str) -> dict[str, Any] | None:
    """Fetch the latest TESTDATA manifest for a mission."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    mission_id,
                    manifest_json,
                    language,
                    base_image,
                    test_framework,
                    source,
                    created_at
                FROM mission_testdata_manifests
                WHERE mission_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (mission_id,),
            )
            row = cur.fetchone()
    if row is None:
        return None
    return {
        "mission_id": row[0],
        "manifest": _json_to_dict(row[1]),
        "language": row[2],
        "base_image": row[3],
        "test_framework": row[4],
        "source": row[5],
        "created_at": _to_iso(row[6]),
    }


def insert_runtime_qc_report(
    settings: Settings,
    mission_id: str,
    execution_result: dict[str, Any],
    qc_assessment: dict[str, Any],
) -> dict[str, Any]:
    """Persist runtime execution and QC assessment details for a mission."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mission_runtime_qc (
                    mission_id,
                    execution_type,
                    verdict,
                    qc_verdict,
                    exit_code,
                    language,
                    filename,
                    base_image,
                    stdout_preview,
                    stderr_preview,
                    execution_result_json,
                    qc_assessment_json,
                    started_at,
                    completed_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s::timestamptz, %s::timestamptz
                )
                RETURNING
                    mission_id,
                    execution_type,
                    verdict,
                    qc_verdict,
                    exit_code,
                    language,
                    filename,
                    base_image,
                    stdout_preview,
                    stderr_preview,
                    execution_result_json,
                    qc_assessment_json,
                    started_at,
                    completed_at,
                    created_at
                """,
                (
                    mission_id,
                    str(execution_result.get("execution_type") or "skipped"),
                    str(execution_result.get("verdict") or "SKIPPED"),
                    qc_assessment.get("qc_verdict"),
                    execution_result.get("exit_code"),
                    execution_result.get("language"),
                    execution_result.get("filename"),
                    execution_result.get("base_image"),
                    execution_result.get("stdout_preview"),
                    execution_result.get("stderr_preview"),
                    json.dumps(execution_result),
                    json.dumps(qc_assessment),
                    execution_result.get("started_at"),
                    execution_result.get("completed_at"),
                ),
            )
            row = cur.fetchone()
    return _runtime_qc_row_to_dict(row)


def get_runtime_qc_report(settings: Settings, mission_id: str) -> dict[str, Any] | None:
    """Fetch the latest runtime QC report for a mission."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    mission_id,
                    execution_type,
                    verdict,
                    qc_verdict,
                    exit_code,
                    language,
                    filename,
                    base_image,
                    stdout_preview,
                    stderr_preview,
                    execution_result_json,
                    qc_assessment_json,
                    started_at,
                    completed_at,
                    created_at
                FROM mission_runtime_qc
                WHERE mission_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (mission_id,),
            )
            row = cur.fetchone()
    if row is None:
        return None
    return _runtime_qc_row_to_dict(row)


def _runtime_qc_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "mission_id": row[0],
        "execution_type": row[1],
        "verdict": row[2],
        "qc_verdict": row[3],
        "exit_code": row[4],
        "language": row[5],
        "filename": row[6],
        "base_image": row[7],
        "stdout_preview": row[8],
        "stderr_preview": row[9],
        "execution_result": _json_to_dict(row[10]),
        "qc_assessment": _json_to_dict(row[11]),
        "started_at": _to_iso(row[12]) if row[12] is not None else None,
        "completed_at": _to_iso(row[13]) if row[13] is not None else None,
        "created_at": _to_iso(row[14]),
    }
