from __future__ import annotations

import hashlib
import importlib
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

from .data_plane_metrics import (
    OBJECT_STORAGE_LEGAL_HOLD_FALLBACK_TOTAL,
    observe_optional_adapter_operation,
    set_object_lock_enabled,
    set_optional_adapter_enabled,
    set_optional_adapter_ready,
)
from .settings import Settings

LOGGER = logging.getLogger(__name__)

_BUCKET_CACHE: set[str] = set()
# Object Lock status per bucket, populated by ensure_bucket(). Cached because it
# is a property of the bucket that cannot change after creation, so re-checking
# it on every write would be a pointless round-trip.
_OBJECT_LOCK_STATE: dict[str, bool] = {}
_ADAPTER = "object_storage"


class LegalHoldUnavailableError(RuntimeError):
    """A legal-hold write was refused because the bucket has no Object Lock.

    Distinct from a transient object-storage outage: this is a permanent
    misconfiguration that drops every failed-audit artifact until the bucket is
    recreated, so callers should be able to tell the two apart. Subclasses
    ``RuntimeError`` so existing ``except RuntimeError`` handling is unaffected.
    """


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


# Error codes that positively mean "this bucket cannot hold a legal hold",
# as opposed to "we could not find out". Anything else (auth failure, network
# error, throttling) is genuinely unknown and must not be reported as a
# missing lock -- that would raise a loud compliance alarm for a credentials
# typo, and train operators to ignore it.
_NO_OBJECT_LOCK_ERROR_CODES = frozenset(
    {
        "ObjectLockConfigurationNotFoundError",
        "ObjectLockConfigurationNotFound",
        "NoSuchObjectLockConfiguration",
        "InvalidRequest",
        "NotImplemented",
        "MethodNotAllowed",
    }
)


def _bucket_has_object_lock(client, bucket: str) -> bool | None:
    """Report whether ``bucket`` was created with Object Lock enabled.

    Returns ``True``/``False`` when the answer is known, and ``None`` when it
    could not be determined. A backend that does not implement the API at all
    counts as ``False`` -- it can never hold a legal hold either.
    """
    try:
        response = client.get_object_lock_configuration(Bucket=bucket)
    except Exception as exc:
        code = ""
        response_payload = getattr(exc, "response", None)
        if isinstance(response_payload, dict):
            code = str((response_payload.get("Error") or {}).get("Code", ""))
        if code:
            return False if code in _NO_OBJECT_LOCK_ERROR_CODES else None
        # Backends and fakes that raise a plain exception carry no error code.
        # Treat the well-known "not found" wording as definitive and anything
        # else as unknown.
        message = str(exc)
        if any(token in message for token in ("ObjectLock", "NoSuchObjectLock", "NotImplemented")):
            return False
        return None
    configuration = response.get("ObjectLockConfiguration") or {}
    return str(configuration.get("ObjectLockEnabled", "")).strip().lower() == "enabled"


def _create_bucket(client, settings: Settings) -> None:
    """Create the artifact bucket, with Object Lock when legal holds are required.

    Object Lock can only be turned on *at creation time* in both S3 and MinIO;
    there is no API that retrofits it onto an existing bucket. A bucket created
    without it can therefore never accept the legal-hold writes that
    :func:`put_audit_report` performs for failed audits, so getting this right
    here is the only chance we have.
    """
    create_args: dict[str, Any] = {"Bucket": settings.object_storage_bucket}
    if settings.object_storage_region != "us-east-1":
        create_args["CreateBucketConfiguration"] = {
            "LocationConstraint": settings.object_storage_region
        }

    if not settings.object_storage_legal_hold_on_fail:
        # No legal holds will ever be requested, so don't impose Object Lock
        # (it forces versioning on permanently and cannot be turned back off).
        client.create_bucket(**create_args)
        return

    try:
        client.create_bucket(**create_args, ObjectLockEnabledForBucket=True)
    except Exception as exc:
        # Some S3-compatible backends reject the parameter outright. Falling
        # back to an unlocked bucket keeps retention-only writes working rather
        # than failing storage entirely; _record_object_lock_state then reports
        # the degradation loudly, so this fallback hides nothing.
        LOGGER.warning(
            "Could not create bucket %s with Object Lock enabled (%s); creating it "
            "without Object Lock. Legal-hold audit reports will be refused.",
            settings.object_storage_bucket,
            exc,
        )
        client.create_bucket(**create_args)


def _record_object_lock_state(client, settings: Settings) -> bool | None:
    """Cache the bucket's Object Lock status and complain loudly if it is missing."""
    enabled = _bucket_has_object_lock(client, settings.object_storage_bucket)
    cache_key = _cache_key(settings)
    if enabled is None:
        # Unknown: leave any previously established answer in place rather than
        # overwriting it with a guess.
        _OBJECT_LOCK_STATE.pop(cache_key, None)
        LOGGER.warning(
            "Could not determine the Object Lock status of bucket %s; legal-hold audit "
            "reports may be refused.",
            settings.object_storage_bucket,
        )
        return None

    _OBJECT_LOCK_STATE[cache_key] = enabled
    set_object_lock_enabled(_ADAPTER, enabled=enabled)

    if settings.object_storage_legal_hold_on_fail and not enabled:
        LOGGER.error(
            "Bucket %s has no Object Lock configuration, so legal-hold audit reports "
            "(status FAIL/FAILED/REJECT/REJECTED/ERROR) will be REFUSED and not stored. "
            "Object Lock can only be enabled when a bucket is created: recreate %s with "
            "ObjectLockEnabledForBucket=true and migrate existing objects into it, or set "
            "OBJECT_STORAGE_LEGAL_HOLD_ON_FAIL=false to accept unprotected retention-only "
            "writes.",
            settings.object_storage_bucket,
            settings.object_storage_bucket,
        )
    return enabled


def object_lock_ready(settings: Settings) -> bool | None:
    """Object Lock status for the configured bucket.

    ``None`` means "not established yet" -- object storage is disabled, or
    :func:`ensure_bucket` has not successfully inspected the bucket. Callers
    should treat that as unknown rather than as a failure.
    """
    if not settings.object_storage_enabled:
        return None
    return _OBJECT_LOCK_STATE.get(_cache_key(settings))


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
            _create_bucket(client, settings)

        # Checked on every fresh bucket -- an existing bucket created before
        # Object Lock was requested is exactly the case that silently dropped
        # failed-audit artifacts, and it is invisible without this probe.
        _record_object_lock_state(client, settings)

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
    """Persist an audit report to object storage with retention / legal hold.

    The write first attempts an Object-Lock-protected ``put_object`` (COMPLIANCE
    retention, plus a legal hold when the audit failed). If the bucket does not
    support Object Lock, behaviour depends on whether a legal hold was required:

    * **legal_hold=True** — the failure is loud: an error is logged, the
      ``object_storage_legal_hold_fallback_total`` counter is incremented, and the
      original exception is re-raised. A legal-hold write must never silently
      succeed as an unprotected object.
    * **legal_hold=False** (retention only) — a warning is logged and the report
      is written without a lock. Retention will not be enforced, which is
      acceptable for non-legal-hold artifacts.
    """
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
        except Exception as exc:
            if legal_hold:
                # A legal hold must never silently degrade to an unprotected
                # write. Make the failure loud and refuse the write.
                OBJECT_STORAGE_LEGAL_HOLD_FALLBACK_TOTAL.inc()
                LOGGER.error(
                    "Object Lock not supported on bucket %s; refusing to write "
                    "legal-hold audit report %s for mission %s without a lock.",
                    settings.object_storage_bucket,
                    audit_id,
                    mission_id,
                )
                # Re-raised as a distinct type so callers can tell a permanent
                # Object Lock misconfiguration from a transient outage. The
                # original message is preserved in the text and as __cause__.
                raise LegalHoldUnavailableError(
                    f"Object Lock is not configured on bucket "
                    f"{settings.object_storage_bucket}; refused to store legal-hold "
                    f"audit report {audit_id} for mission {mission_id}: {exc}"
                ) from exc
            # Retention-only writes may proceed without a lock; retention will
            # not be enforced for this object.
            LOGGER.warning(
                "Object Lock not supported on bucket; retention will not be "
                "enforced. Object written without lock."
            )
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


def get_object(settings: Settings, key: str) -> bytes | None:
    """Download raw bytes from object storage at ``key``.

    Returns the object body, or ``None`` when object storage is disabled or the
    object does not exist. Other errors (auth, network) propagate so callers can
    distinguish "not stored" from "storage unavailable".
    """
    if not settings.object_storage_enabled:
        return None
    started = time.perf_counter()
    success = False
    try:
        client = _s3_client(settings)
        try:
            response = client.get_object(
                Bucket=settings.object_storage_bucket,
                Key=key,
            )
        except Exception as exc:
            if type(exc).__name__ in ("NoSuchKey", "ClientError") and _is_not_found(exc):
                success = True  # a clean "not found" is not an adapter failure
                return None
            raise
        body = response.get("Body") if isinstance(response, dict) else None
        data = body.read() if body is not None else b""
        success = True
        return data
    finally:
        observe_optional_adapter_operation(
            adapter=_ADAPTER,
            operation="get_object",
            duration_seconds=time.perf_counter() - started,
            success=success,
        )


def _is_not_found(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = str(response.get("Error", {}).get("Code", ""))
        return code in ("NoSuchKey", "404", "NotFound")
    return False


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
