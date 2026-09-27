"""scripts/migrate_object_store.py must never downgrade locked evidence.

Live-verified MinIO RELEASE.2025-09-07 -> SeaweedFS 4.47 on 2026-09-27; these
tests pin the refusal paths with an in-memory S3 fake so CI covers them.
"""

from __future__ import annotations

import hashlib
import io
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import migrate_object_store as mig  # noqa: E402


class _ClientError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeS3:
    def __init__(self, *, lock: bool | None = None) -> None:
        # lock=None: bucket absent. True/False: bucket exists with/without lock.
        self.buckets: dict[str, bool] = {}
        self.objects: dict[tuple[str, str], dict] = {}
        self.puts: list[dict] = []
        self.corrupt_on_read = False

    def head_bucket(self, Bucket):
        if Bucket not in self.buckets:
            raise _ClientError("404")

    def create_bucket(self, Bucket, ObjectLockEnabledForBucket=False):
        self.buckets[Bucket] = bool(ObjectLockEnabledForBucket)

    def get_object_lock_configuration(self, Bucket):
        if not self.buckets.get(Bucket):
            raise _ClientError("ObjectLockConfigurationNotFoundError")
        return {"ObjectLockConfiguration": {"ObjectLockEnabled": "Enabled"}}

    def list_objects_v2(self, Bucket, Prefix="", ContinuationToken=None):
        keys = sorted(k for b, k in self.objects if b == Bucket and k.startswith(Prefix))
        return {"Contents": [{"Key": k} for k in keys], "IsTruncated": False}

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs

    def get_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise _ClientError("NoSuchKey")
        stored = self.objects[(Bucket, Key)]
        body = stored["Body"] + (b"x" if self.corrupt_on_read else b"")
        return {
            "Body": io.BytesIO(body),
            "ContentType": stored.get("ContentType"),
            "Metadata": dict(stored.get("Metadata") or {}),
            "ObjectLockMode": stored.get("ObjectLockMode"),
            "ObjectLockRetainUntilDate": stored.get("ObjectLockRetainUntilDate"),
            "ObjectLockLegalHoldStatus": stored.get("ObjectLockLegalHoldStatus", "OFF"),
        }


UNTIL = datetime(2026, 11, 3, tzinfo=UTC) + timedelta(days=0)


def _seed(source: FakeS3, *, locked_bucket: bool = True, tamper: bool = False) -> None:
    source.create_bucket("b", ObjectLockEnabledForBucket=locked_bucket)
    body = b'{"status":"FAILED"}'
    source.put_object(
        Bucket="b",
        Key="missions/m/audit-reports/a.json",
        Body=body,
        ContentType="application/json",
        Metadata={
            "status": "FAILED",
            "payload-sha256": "0" * 64 if tamper else hashlib.sha256(body).hexdigest(),
        },
        ObjectLockMode="COMPLIANCE",
        ObjectLockRetainUntilDate=UNTIL,
        ObjectLockLegalHoldStatus="ON",
    )
    source.puts.clear()


def test_dry_run_writes_nothing() -> None:
    source, dest = FakeS3(), FakeS3()
    _seed(source)
    report = mig.migrate(source, dest, source_bucket="b", dest_bucket="b")
    assert report.would_copy == ["missions/m/audit-reports/a.json"]
    assert dest.puts == [] and dest.buckets == {}


def test_execute_preserves_retention_and_legal_hold() -> None:
    source, dest = FakeS3(), FakeS3()
    _seed(source)
    report = mig.migrate(source, dest, source_bucket="b", dest_bucket="b", execute=True)
    assert report.ok and report.copied == ["missions/m/audit-reports/a.json"]
    assert dest.buckets == {"b": True}, "destination must be created WITH Object Lock"
    (put,) = dest.puts
    assert put["ObjectLockMode"] == "COMPLIANCE"
    assert put["ObjectLockRetainUntilDate"] == UNTIL
    assert put["ObjectLockLegalHoldStatus"] == "ON"
    assert put["Metadata"]["status"] == "FAILED"


def test_rerun_is_idempotent() -> None:
    source, dest = FakeS3(), FakeS3()
    _seed(source)
    mig.migrate(source, dest, source_bucket="b", dest_bucket="b", execute=True)
    report = mig.migrate(source, dest, source_bucket="b", dest_bucket="b", execute=True)
    assert report.skipped_identical == ["missions/m/audit-reports/a.json"]
    assert len(dest.puts) == 1


def test_refuses_unlocked_destination_for_locked_source() -> None:
    source, dest = FakeS3(), FakeS3()
    _seed(source)
    dest.create_bucket("b")  # exists, no Object Lock
    with pytest.raises(RuntimeError, match="without Object Lock"):
        mig.migrate(source, dest, source_bucket="b", dest_bucket="b", execute=True)
    assert dest.puts == []


def test_tampered_source_is_reported_not_copied() -> None:
    source, dest = FakeS3(), FakeS3()
    _seed(source, tamper=True)
    report = mig.migrate(source, dest, source_bucket="b", dest_bucket="b", execute=True)
    assert not report.ok
    assert "payload-sha256" in report.failed["missions/m/audit-reports/a.json"]
    assert dest.puts == []


def test_different_bytes_at_destination_are_never_overwritten() -> None:
    source, dest = FakeS3(), FakeS3()
    _seed(source)
    dest.create_bucket("b", ObjectLockEnabledForBucket=True)
    dest.put_object(Bucket="b", Key="missions/m/audit-reports/a.json", Body=b"other")
    dest.puts.clear()
    report = mig.migrate(source, dest, source_bucket="b", dest_bucket="b", execute=True)
    assert "DIFFERENT bytes" in report.failed["missions/m/audit-reports/a.json"]
    assert dest.puts == []


def test_post_copy_verification_catches_corruption() -> None:
    source, dest = FakeS3(), FakeS3()
    _seed(source)
    dest.corrupt_on_read = True
    report = mig.migrate(source, dest, source_bucket="b", dest_bucket="b", execute=True)
    # The pre-copy existence probe sees nothing; the post-copy read-back differs.
    assert "verification failed" in report.failed["missions/m/audit-reports/a.json"]


def test_credentials_are_read_from_environment_only(monkeypatch) -> None:
    monkeypatch.delenv("MIGRATE_SOURCE_ACCESS_KEY", raising=False)
    monkeypatch.delenv("MIGRATE_SOURCE_SECRET_KEY", raising=False)
    with pytest.raises(SystemExit, match="MIGRATE_SOURCE_ACCESS_KEY"):
        mig.main(
            ["--source-endpoint", "http://a", "--dest-endpoint", "http://b", "--bucket", "b"]
        )
