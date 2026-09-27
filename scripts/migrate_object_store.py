#!/usr/bin/env python3
"""Copy audit artifacts between S3-compatible stores, preserving Object Lock.

Written for the 2026-09-27 MinIO -> SeaweedFS move (docs/OBJECT_STORE_MIGRATION.md),
but deliberately backend-agnostic: it speaks plain S3 to both sides.

What "preserving" means here, because it is the whole point of the tool:

* every object keeps its body, content type and user metadata;
* an object stored under COMPLIANCE/GOVERNANCE retention is written to the
  destination under the *same* mode and retain-until date, never a shorter one;
* an object under legal hold keeps its legal hold;
* the copy is verified by SHA-256 against the source bytes (and against the
  ``payload-sha256`` metadata ``put_audit_report`` records, when present).

Refusals are loud. A source object that is locked cannot be copied into a
destination bucket without Object Lock, so the tool refuses to start rather than
silently downgrading evidence to an unprotected object.

Dry run is the default. Nothing is written without ``--execute``. The source is
only ever read.

Credentials come from the environment, never from the command line (where they
would land in shell history and process listings):

    MIGRATE_SOURCE_ACCESS_KEY / MIGRATE_SOURCE_SECRET_KEY
    MIGRATE_DEST_ACCESS_KEY   / MIGRATE_DEST_SECRET_KEY
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

_LOCKED_MODES = frozenset({"COMPLIANCE", "GOVERNANCE"})


@dataclass
class MigrationReport:
    bucket: str
    execute: bool
    copied: list[str] = field(default_factory=list)
    skipped_identical: list[str] = field(default_factory=list)
    would_copy: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.failed

    def as_dict(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "execute": self.execute,
            "copied": len(self.copied),
            "skipped_identical": len(self.skipped_identical),
            "would_copy": len(self.would_copy),
            "failed": self.failed,
            "ok": self.ok,
        }


def _error_code(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        return str((response.get("Error") or {}).get("Code", ""))
    return ""


def bucket_lock_enabled(client, bucket: str) -> bool:
    try:
        response = client.get_object_lock_configuration(Bucket=bucket)
    except Exception as exc:  # noqa: BLE001 - any S3 error means "no usable lock"
        if _error_code(exc) or "ObjectLock" in str(exc):
            return False
        raise
    configuration = response.get("ObjectLockConfiguration") or {}
    return str(configuration.get("ObjectLockEnabled", "")).lower() == "enabled"


def ensure_destination_bucket(client, bucket: str, *, require_lock: bool, execute: bool) -> None:
    try:
        client.head_bucket(Bucket=bucket)
        exists = True
    except Exception:  # noqa: BLE001
        exists = False
    if not exists:
        if not execute:
            return
        if require_lock:
            client.create_bucket(Bucket=bucket, ObjectLockEnabledForBucket=True)
        else:
            client.create_bucket(Bucket=bucket)
    if require_lock and exists and not bucket_lock_enabled(client, bucket):
        raise RuntimeError(
            f"destination bucket {bucket} exists without Object Lock; locked source "
            "objects cannot be copied into it without losing their protection. "
            "Object Lock can only be enabled at bucket creation."
        )


def list_keys(client, bucket: str, prefix: str) -> list[str]:
    keys: list[str] = []
    token: str | None = None
    while True:
        args: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
        if token:
            args["ContinuationToken"] = token
        response = client.list_objects_v2(**args)
        keys.extend(str(item["Key"]) for item in response.get("Contents", []) or [])
        if not response.get("IsTruncated"):
            return keys
        token = response.get("NextContinuationToken")


def _lock_state(client, bucket: str, key: str, head: dict[str, Any]) -> dict[str, Any]:
    """Read retention + legal hold. HEAD usually carries both; fall back to the APIs."""
    mode = head.get("ObjectLockMode")
    until = head.get("ObjectLockRetainUntilDate")
    hold = head.get("ObjectLockLegalHoldStatus")
    if mode is None:
        try:
            retention = client.get_object_retention(Bucket=bucket, Key=key)["Retention"]
            mode, until = retention.get("Mode"), retention.get("RetainUntilDate")
        except Exception:  # noqa: BLE001 - no retention configured
            pass
    if hold is None:
        try:
            hold = client.get_object_legal_hold(Bucket=bucket, Key=key)["LegalHold"]["Status"]
        except Exception:  # noqa: BLE001 - no legal hold configured
            pass
    return {"mode": mode, "until": until, "legal_hold": hold}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def migrate(
    source,
    dest,
    *,
    source_bucket: str,
    dest_bucket: str,
    prefix: str = "",
    execute: bool = False,
) -> MigrationReport:
    report = MigrationReport(bucket=dest_bucket, execute=execute)
    source_locked = bucket_lock_enabled(source, source_bucket)
    ensure_destination_bucket(dest, dest_bucket, require_lock=source_locked, execute=execute)

    for key in list_keys(source, source_bucket, prefix):
        try:
            obj = source.get_object(Bucket=source_bucket, Key=key)
            body = obj["Body"].read()
            digest = _sha256(body)
            metadata = dict(obj.get("Metadata") or {})
            recorded = metadata.get("payload-sha256")
            if recorded and recorded != digest:
                raise RuntimeError(
                    f"source bytes do not match their recorded payload-sha256 ({recorded})"
                )

            try:
                existing = dest.get_object(Bucket=dest_bucket, Key=key)["Body"].read()
            except Exception:  # noqa: BLE001 - absent at destination
                existing = None
            if existing is not None and _sha256(existing) == digest:
                report.skipped_identical.append(key)
                continue
            if existing is not None:
                raise RuntimeError("destination already holds DIFFERENT bytes under this key")

            if not execute:
                report.would_copy.append(key)
                continue

            lock = _lock_state(source, source_bucket, key, obj)
            put_args: dict[str, Any] = {
                "Bucket": dest_bucket,
                "Key": key,
                "Body": body,
                "ContentType": obj.get("ContentType") or "application/octet-stream",
                "Metadata": metadata,
            }
            if lock["mode"] in _LOCKED_MODES and lock["until"] is not None:
                put_args["ObjectLockMode"] = lock["mode"]
                put_args["ObjectLockRetainUntilDate"] = lock["until"]
            if lock["legal_hold"] == "ON":
                put_args["ObjectLockLegalHoldStatus"] = "ON"
            dest.put_object(**put_args)

            copied = dest.get_object(Bucket=dest_bucket, Key=key)
            if _sha256(copied["Body"].read()) != digest:
                raise RuntimeError("verification failed: destination bytes differ after copy")
            copied_lock = _lock_state(dest, dest_bucket, key, copied)
            if lock["legal_hold"] == "ON" and copied_lock["legal_hold"] != "ON":
                raise RuntimeError("verification failed: legal hold did not survive the copy")
            if lock["mode"] in _LOCKED_MODES and copied_lock["mode"] != lock["mode"]:
                raise RuntimeError("verification failed: retention mode did not survive the copy")
            report.copied.append(key)
        except Exception as exc:  # noqa: BLE001 - recorded per key, never swallowed
            report.failed[key] = f"{type(exc).__name__}: {exc}"
    return report


def _client(endpoint: str, access_env: str, secret_env: str, region: str):
    import boto3
    from botocore.config import Config

    access = os.environ.get(access_env, "")
    secret = os.environ.get(secret_env, "")
    if not access or not secret:
        raise SystemExit(f"set {access_env} and {secret_env} in the environment")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name=region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source-endpoint", required=True)
    parser.add_argument("--dest-endpoint", required=True)
    parser.add_argument("--bucket", required=True, help="source bucket")
    parser.add_argument("--dest-bucket", help="destination bucket (default: same name)")
    parser.add_argument("--prefix", default="")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--execute", action="store_true", help="write (default: dry run)")
    args = parser.parse_args(argv)

    source = _client(
        args.source_endpoint, "MIGRATE_SOURCE_ACCESS_KEY", "MIGRATE_SOURCE_SECRET_KEY", args.region
    )
    dest = _client(
        args.dest_endpoint, "MIGRATE_DEST_ACCESS_KEY", "MIGRATE_DEST_SECRET_KEY", args.region
    )
    report = migrate(
        source,
        dest,
        source_bucket=args.bucket,
        dest_bucket=args.dest_bucket or args.bucket,
        prefix=args.prefix,
        execute=args.execute,
    )
    print(json.dumps(report.as_dict(), indent=2, default=str))
    if not args.execute:
        print("DRY RUN: nothing was written. Re-run with --execute to copy.", file=sys.stderr)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
