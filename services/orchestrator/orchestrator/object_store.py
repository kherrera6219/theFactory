from __future__ import annotations

import hashlib
import importlib
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

from .data_plane_metrics import (
    observe_optional_adapter_operation,
    set_optional_adapter_enabled,
    set_optional_adapter_ready,
)
from .settings import Settings

_BUCKET_CACHE: set[str] = set()
_ADAPTER = "object_storage"


def _cache_key(settings: Settings) -> str:
    return (
        f"{settings.object_storage_endpoint.rstrip('/')}:"
        f"{settings.object_storage_bucket}:"
        f"{settings.object_storage_region}:"
        f"{settings.object_storage_access_key}"
    )


def _object_url(settings: Settings, key: str) -> str:
    endpoint = settings.object_storage_endpoint.rstrip("/")
    return (
        f"{endpoint}/{quote(settings.object_storage_bucket, safe='')}/"
        f"{quote(key.lstrip('/'), safe='/')}"
    )


def _s3_client(settings: Settings):
    if not settings.object_storage_enabled:
        raise RuntimeError("object storage is disabled")
    if not settings.object_storage_access_key or not settings.object_storage_secret_key:
        raise RuntimeError(
            "object storage credentials are required when OBJECT_STORAGE_ENABLED=true"
        )
    if (
        settings.object_storage_require_tls
        and not settings.object_storage_endpoint.startswith("https://")
    ):
        raise RuntimeError(
            "OBJECT_STORAGE_REQUIRE_TLS=true requires an https OBJECT_STORAGE_ENDPOINT"
        )

    try:
        boto3 = importlib.import_module("boto3")
        botocore_config = importlib.import_module("botocore.config")
    except Exception as exc:
        raise RuntimeError("boto3/botocore is required for object-storage support") from exc

    config = botocore_config.Config(
        connect_timeout=settings.object_storage_timeout_seconds,
        read_timeout=settings.object_storage_timeout_seconds,
        retries={"max_attempts": 2, "mode": "standard"},
        signature_version="s3v4",
        s3={"addressing_style": "path" if settings.object_storage_force_path_style else "virtual"},
    )
    return boto3.client(
        "s3",
        endpoint_url=settings.object_storage_endpoint,
        aws_access_key_id=settings.object_storage_access_key,
        aws_secret_access_key=settings.object_storage_secret_key,
        region_name=settings.object_storage_region,
        use_ssl=settings.object_storage_endpoint.lower().startswith("https://"),
        config=config,
    )


def ensure_bucket(settings: Settings) -> None:
    set_optional_adapter_enabled(_ADAPTER, enabled=settings.object_storage_enabled)
    if not settings.object_storage_enabled:
        return

    cache_key = _cache_key(settings)
    if cache_key in _BUCKET_CACHE:
        return

    started = time.perf_counter()
    success = False
    try:
        client = _s3_client(settings)
        bucket = settings.object_storage_bucket
        try:
            client.head_bucket(Bucket=bucket)
        except Exception:
            if settings.object_storage_region == "us-east-1":
                client.create_bucket(Bucket=bucket)
            else:
                client.create_bucket(
                    Bucket=bucket,
                    CreateBucketConfiguration={
                        "LocationConstraint": settings.object_storage_region
                    },
                )

        _BUCKET_CACHE.add(cache_key)
        success = True
    finally:
        observe_optional_adapter_operation(
            adapter=_ADAPTER,
            operation="ensure_bucket",
            duration_seconds=time.perf_counter() - started,
            success=success,
        )


def object_storage_ready(settings: Settings) -> bool:
    set_optional_adapter_enabled(_ADAPTER, enabled=settings.object_storage_enabled)
    if not settings.object_storage_enabled:
        set_optional_adapter_ready(_ADAPTER, ready=False)
        return False
    started = time.perf_counter()
    ready = False
    try:
        ensure_bucket(settings)
        ready = True
    except Exception:
        set_optional_adapter_ready(_ADAPTER, ready=False)
        observe_optional_adapter_operation(
            adapter=_ADAPTER,
            operation="ready_check",
            duration_seconds=time.perf_counter() - started,
            success=False,
        )
        return False
    set_optional_adapter_ready(_ADAPTER, ready=True)
    observe_optional_adapter_operation(
        adapter=_ADAPTER,
        operation="ready_check",
        duration_seconds=time.perf_counter() - started,
        success=ready,
    )
    return ready


def _artifact_key(settings: Settings, mission_id: str, audit_id: str) -> str:
    prefix = settings.object_storage_prefix.strip("/")
    if prefix:
        return f"{prefix}/{mission_id}/audit-reports/{audit_id}.json"
    return f"{mission_id}/audit-reports/{audit_id}.json"


def _retention_deadline(created_at: str, retention_days: int) -> datetime:
    raw = created_at.strip()
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed + timedelta(days=retention_days)


def _requires_legal_hold(settings: Settings, status: str) -> bool:
    return settings.object_storage_legal_hold_on_fail and status.strip().upper() in {
        "FAIL",
        "FAILED",
        "REJECT",
        "REJECTED",
        "ERROR",
    }


def put_audit_report(
    settings: Settings,
    mission_id: str,
    audit_id: str,
    status: str,
    report: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    success = False
    try:
        ensure_bucket(settings)

        key = _artifact_key(settings, mission_id, audit_id)
        payload_bytes = json.dumps(report, separators=(",", ":"), sort_keys=True).encode("utf-8")
        payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()

        retention_until = _retention_deadline(created_at, settings.object_storage_retention_days)
        legal_hold = _requires_legal_hold(settings, status)

        metadata = {
            "mission-id": mission_id,
            "audit-id": audit_id,
            "status": status,
            "created-at": created_at,
            "retention-until": retention_until.isoformat(),
            "legal-hold": "on" if legal_hold else "off",
            "payload-sha256": payload_sha256,
        }

        client = _s3_client(settings)
        base_args = {
            "Bucket": settings.object_storage_bucket,
            "Key": key,
            "Body": payload_bytes,
            "ContentType": "application/json",
            "Metadata": metadata,
        }

        response: dict[str, Any]
        try:
            lock_args = {
                **base_args,
                "ObjectLockMode": "COMPLIANCE",
                "ObjectLockRetainUntilDate": retention_until,
            }
            if legal_hold:
                lock_args["ObjectLockLegalHoldStatus"] = "ON"
            response = client.put_object(**lock_args)
        except Exception:
            # Fallback for buckets without object-lock support.
            response = client.put_object(**base_args)

        etag = str(response.get("ETag", "")).strip('"') if isinstance(response, dict) else ""
        success = True
        return {
            "bucket": settings.object_storage_bucket,
            "key": key,
            "etag": etag,
            "content_sha256": payload_sha256,
            "retention_until": retention_until.isoformat(),
            "legal_hold": legal_hold,
            "url": _object_url(settings, key),
        }
    finally:
        observe_optional_adapter_operation(
            adapter=_ADAPTER,
            operation="put_audit_report",
            duration_seconds=time.perf_counter() - started,
            success=success,
        )


def put_object(
    settings: Settings,
    key: str,
    body: bytes,
    content_type: str = "application/octet-stream",
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Upload raw bytes to object storage under ``key``.

    Returns ``{"bucket": ..., "key": ..., "etag": ..., "url": ...}``.
    Raises RuntimeError when object storage is disabled or credentials are missing.
    """
    started = time.perf_counter()
    success = False
    try:
        ensure_bucket(settings)
        client = _s3_client(settings)
        args: dict[str, Any] = {
            "Bucket": settings.object_storage_bucket,
            "Key": key,
            "Body": body,
            "ContentType": content_type,
        }
        if metadata:
            args["Metadata"] = {str(k): str(v) for k, v in metadata.items()}
        response = client.put_object(**args)
        etag = str(response.get("ETag", "")).strip('"') if isinstance(response, dict) else ""
        success = True
        return {
            "bucket": settings.object_storage_bucket,
            "key": key,
            "etag": etag,
            "url": _object_url(settings, key),
        }
    finally:
        observe_optional_adapter_operation(
            adapter=_ADAPTER,
            operation="put_object",
            duration_seconds=time.perf_counter() - started,
            success=success,
        )


def get_presigned_url(
    settings: Settings,
    key: str,
    expires_in_seconds: int = 3600,
) -> str:
    """Generate a presigned GET URL for the object at ``key``.

    The URL is valid for ``expires_in_seconds`` seconds (default 1 hour).
    Raises RuntimeError when object storage is disabled or unavailable.
    """
    started = time.perf_counter()
    success = False
    try:
        client = _s3_client(settings)
        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.object_storage_bucket,
                "Key": key,
            },
            ExpiresIn=max(60, min(expires_in_seconds, 604800)),  # 1 min – 7 days
        )
        success = True
        return str(url)
    finally:
        observe_optional_adapter_operation(
            adapter=_ADAPTER,
            operation="get_presigned_url",
            duration_seconds=time.perf_counter() - started,
            success=success,
        )


def list_audit_artifacts(settings: Settings, mission_id: str, limit: int) -> list[dict[str, Any]]:
    started = time.perf_counter()
    success = False
    try:
        ensure_bucket(settings)

        query_limit = max(1, min(limit, 500))
        prefix = _artifact_key(settings, mission_id, "")[:-5]
        client = _s3_client(settings)
        response = client.list_objects_v2(
            Bucket=settings.object_storage_bucket,
            Prefix=prefix,
            MaxKeys=query_limit,
        )

        contents = response.get("Contents", []) if isinstance(response, dict) else []
        records: list[dict[str, Any]] = []
        for item in contents:
            if not isinstance(item, dict):
                continue
            key = str(item.get("Key", ""))
            if not key.endswith(".json"):
                continue
            last_modified = item.get("LastModified")
            last_modified_iso = (
                last_modified.astimezone(UTC).isoformat()
                if isinstance(last_modified, datetime)
                else str(last_modified or "")
            )
            etag = str(item.get("ETag", "")).strip('"')
            records.append(
                {
                    "bucket": settings.object_storage_bucket,
                    "key": key,
                    "size_bytes": int(item.get("Size", 0)),
                    "etag": etag,
                    "last_modified": last_modified_iso,
                    "url": _object_url(settings, key),
                }
            )

        records.sort(key=lambda record: record.get("last_modified", ""), reverse=True)
        success = True
        return records[:query_limit]
    finally:
        observe_optional_adapter_operation(
            adapter=_ADAPTER,
            operation="list_audit_artifacts",
            duration_seconds=time.perf_counter() - started,
            success=success,
        )
