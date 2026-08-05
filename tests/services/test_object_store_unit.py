import importlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

object_store = importlib.import_module("orchestrator.object_store")
data_plane_metrics = importlib.import_module("orchestrator.data_plane_metrics")
Settings = importlib.import_module("orchestrator.settings").Settings


def _settings(**overrides: object) -> Settings:
    base = Settings(
        redis_url="redis://redis:6379/0",
        postgres_url="postgresql://postgres:postgres@postgres:5432/ulr",
        intake_stream="missions.intake",
        state_stream="missions.state",
        max_stream_len=1000,
        consumer_group="orchestrator",
        consumer_name="orchestrator-test",
        auto_transition_enabled=True,
        transition_step_seconds=1.0,
        intake_topic="intake.feature_contract.created",
        default_priority="NORMAL",
        producer_name="orchestrator",
        event_schema_path=ROOT / "schemas" / "event.envelope.schema.json",
        topics_path=ROOT / "protocol" / "topics.yaml",
        admin_api_key="admin-key",
        internal_service_api_key="worker-key",
        readonly_api_key="viewer-key",
        extra_api_keys="",
        qdrant_url="http://qdrant:6333",
        qdrant_api_key="",
        qdrant_enabled=True,
        qdrant_collection="mission_knowledge",
        qdrant_vector_size=8,
        qdrant_timeout_seconds=1.0,
        neo4j_url="http://neo4j:7474",
        neo4j_enabled=False,
        neo4j_username="neo4j",
        neo4j_password="pass",
        neo4j_database="neo4j",
        neo4j_timeout_seconds=1.0,
        object_storage_enabled=True,
        object_storage_endpoint="http://minio:9000",
        object_storage_access_key="minioadmin",
        object_storage_secret_key="minioadmin123",
        object_storage_bucket="mission-audit-artifacts",
        object_storage_prefix="missions",
        object_storage_region="us-east-1",
        object_storage_timeout_seconds=5.0,
        object_storage_retention_days=90,
        object_storage_legal_hold_on_fail=True,
        object_storage_force_path_style=True,
        object_storage_require_tls=False,
    )
    return Settings(**{**base.__dict__, **overrides})


class _FakeS3Client:
    def __init__(self, *, object_lock: bool = True) -> None:
        self.head_bucket_called = 0
        self.created_bucket = False
        self.put_calls: list[dict[str, object]] = []
        self.contents: list[dict[str, object]] = []
        # Mirrors the real constraint: Object Lock is a property fixed at
        # creation, so this flips only via create_bucket.
        self.object_lock = object_lock

    def head_bucket(self, *, Bucket: str) -> None:
        _ = Bucket
        self.head_bucket_called += 1
        if not self.created_bucket:
            raise RuntimeError("missing")

    def create_bucket(self, **kwargs) -> None:
        self.created_bucket = True
        self.object_lock = bool(kwargs.get("ObjectLockEnabledForBucket", False))

    def get_object_lock_configuration(self, *, Bucket: str):
        _ = Bucket
        if not self.object_lock:
            raise RuntimeError("ObjectLockConfigurationNotFoundError")
        return {"ObjectLockConfiguration": {"ObjectLockEnabled": "Enabled"}}

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)
        return {"ETag": '"etag-1"'}

    def list_objects_v2(self, **kwargs):
        _ = kwargs
        return {
            "Contents": self.contents,
        }


def _reset_bucket_state() -> None:
    object_store._BUCKET_CACHE.clear()
    object_store._OBJECT_LOCK_STATE.clear()


def test_ensure_bucket_creates_when_missing(monkeypatch) -> None:
    _reset_bucket_state()
    fake = _FakeS3Client()
    monkeypatch.setattr(object_store, "_s3_client", lambda _settings: fake)

    object_store.ensure_bucket(_settings())

    assert fake.head_bucket_called == 1
    assert fake.created_bucket is True


def test_helper_functions_cover_key_and_retention_paths() -> None:
    settings = _settings(object_storage_prefix="missions")
    assert (
        object_store._artifact_key(settings, "mission-1", "audit-1")
        == "missions/mission-1/audit-reports/audit-1.json"
    )
    assert object_store._object_url(settings, "/mission-1/audit report.json").endswith(
        "mission-audit-artifacts/mission-1/audit%20report.json"
    )
    assert object_store._retention_deadline("2026-03-03T00:00:00", 30).tzinfo is UTC
    assert object_store._requires_legal_hold(settings, "failed") is True
    assert object_store._requires_legal_hold(settings, "pass") is False


def test_s3_client_validates_configuration() -> None:
    with pytest.raises(RuntimeError, match="disabled"):
        object_store._s3_client(_settings(object_storage_enabled=False))

    with pytest.raises(RuntimeError, match="credentials are required"):
        object_store._s3_client(
            _settings(
                object_storage_access_key="",
                object_storage_secret_key="",
            )
        )

    with pytest.raises(RuntimeError, match="requires an https"):
        object_store._s3_client(
            _settings(
                object_storage_endpoint="http://minio:9000",
                object_storage_require_tls=True,
            )
        )


def test_s3_client_builds_boto_configuration(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeConfig:
        def __init__(self, **kwargs) -> None:
            captured["config_kwargs"] = kwargs

    boto3_module = ModuleType("boto3")

    def _client(service_name: str, **kwargs):
        captured["service_name"] = service_name
        captured["client_kwargs"] = kwargs
        return "fake-client"

    boto3_module.client = _client
    botocore_config_module = ModuleType("botocore.config")
    botocore_config_module.Config = _FakeConfig

    monkeypatch.setattr(object_store.importlib, "import_module", lambda name: {
        "boto3": boto3_module,
        "botocore.config": botocore_config_module,
    }[name])

    client = object_store._s3_client(
        _settings(
            object_storage_endpoint="https://minio.example",
            object_storage_force_path_style=False,
        )
    )

    assert client == "fake-client"
    assert captured["service_name"] == "s3"
    assert captured["config_kwargs"]["signature_version"] == "s3v4"
    assert captured["config_kwargs"]["s3"] == {"addressing_style": "virtual"}
    assert captured["client_kwargs"]["use_ssl"] is True


def test_s3_client_raises_when_boto_missing(monkeypatch) -> None:
    def _import_module(_name: str):
        raise ImportError("missing")

    monkeypatch.setattr(object_store.importlib, "import_module", _import_module)

    with pytest.raises(RuntimeError, match="boto3/botocore"):
        object_store._s3_client(_settings())


def test_ensure_bucket_creates_with_location_constraint(monkeypatch) -> None:
    _reset_bucket_state()
    fake = _FakeS3Client()
    calls: list[dict[str, object]] = []

    def _create_bucket(**kwargs) -> None:
        calls.append(kwargs)
        fake.created_bucket = True

    fake.create_bucket = _create_bucket
    monkeypatch.setattr(object_store, "_s3_client", lambda _settings: fake)

    object_store.ensure_bucket(_settings(object_storage_region="us-west-2"))

    assert calls == [
        {
            "Bucket": "mission-audit-artifacts",
            "CreateBucketConfiguration": {"LocationConstraint": "us-west-2"},
            # Object Lock can only be enabled at creation, and legal holds are
            # required by default, so it must be requested here or failed-audit
            # artifacts can never be stored.
            "ObjectLockEnabledForBucket": True,
        }
    ]


def test_ensure_bucket_omits_object_lock_when_legal_holds_disabled(monkeypatch) -> None:
    _reset_bucket_state()
    fake = _FakeS3Client()
    calls: list[dict[str, object]] = []

    def _create_bucket(**kwargs) -> None:
        calls.append(kwargs)
        fake.created_bucket = True
        fake.object_lock = bool(kwargs.get("ObjectLockEnabledForBucket", False))

    fake.create_bucket = _create_bucket
    monkeypatch.setattr(object_store, "_s3_client", lambda _settings: fake)

    object_store.ensure_bucket(_settings(object_storage_legal_hold_on_fail=False))

    # Object Lock forces versioning on permanently and cannot be undone, so it
    # is not imposed when no legal hold will ever be requested.
    assert calls == [{"Bucket": "mission-audit-artifacts"}]


def test_ensure_bucket_falls_back_when_backend_rejects_object_lock(monkeypatch) -> None:
    _reset_bucket_state()
    fake = _FakeS3Client(object_lock=False)
    calls: list[dict[str, object]] = []

    def _create_bucket(**kwargs) -> None:
        calls.append(kwargs)
        if kwargs.get("ObjectLockEnabledForBucket"):
            raise RuntimeError("object lock not supported by this backend")
        fake.created_bucket = True

    fake.create_bucket = _create_bucket
    monkeypatch.setattr(object_store, "_s3_client", lambda _settings: fake)

    settings = _settings()
    object_store.ensure_bucket(settings)

    # A backend without Object Lock support still gets a usable bucket for
    # retention-only writes, and the degradation is reported rather than hidden.
    assert len(calls) == 2
    assert calls[0]["ObjectLockEnabledForBucket"] is True
    assert "ObjectLockEnabledForBucket" not in calls[1]
    assert object_store.object_lock_ready(settings) is False


def test_ensure_bucket_reports_missing_object_lock_on_existing_bucket(
    monkeypatch, caplog
) -> None:
    _reset_bucket_state()
    # The regression this guards: a bucket created before Object Lock was
    # requested already exists, so head_bucket succeeds and create_bucket is
    # never reached -- the only way to notice is to inspect the configuration.
    fake = _FakeS3Client(object_lock=False)
    fake.created_bucket = True
    monkeypatch.setattr(object_store, "_s3_client", lambda _settings: fake)

    settings = _settings()
    with caplog.at_level("ERROR", logger="orchestrator.object_store"):
        object_store.ensure_bucket(settings)

    assert object_store.object_lock_ready(settings) is False
    assert any("no Object Lock configuration" in message for message in caplog.messages)


def test_ensure_bucket_reports_object_lock_on_compliant_bucket(monkeypatch) -> None:
    _reset_bucket_state()
    fake = _FakeS3Client(object_lock=True)
    fake.created_bucket = True
    monkeypatch.setattr(object_store, "_s3_client", lambda _settings: fake)

    settings = _settings()
    object_store.ensure_bucket(settings)

    assert object_store.object_lock_ready(settings) is True


def test_object_lock_state_is_unknown_when_probe_fails(monkeypatch, caplog) -> None:
    _reset_bucket_state()
    fake = _FakeS3Client()
    fake.created_bucket = True

    def _raise_access_denied(*, Bucket: str):
        _ = Bucket
        error = Exception("nope")
        error.response = {"Error": {"Code": "InvalidAccessKeyId"}}
        raise error

    fake.get_object_lock_configuration = _raise_access_denied
    monkeypatch.setattr(object_store, "_s3_client", lambda _settings: fake)

    settings = _settings()
    with caplog.at_level("WARNING", logger="orchestrator.object_store"):
        object_store.ensure_bucket(settings)

    # A credentials failure must not masquerade as a compliance alarm.
    assert object_store.object_lock_ready(settings) is None
    assert not any("no Object Lock configuration" in message for message in caplog.messages)
    assert any("Could not determine the Object Lock status" in m for m in caplog.messages)


def test_bucket_has_object_lock_classifies_error_codes() -> None:
    class _Client:
        def __init__(self, code: str) -> None:
            self.code = code

        def get_object_lock_configuration(self, *, Bucket: str):
            _ = Bucket
            error = Exception("boom")
            error.response = {"Error": {"Code": self.code}}
            raise error

    assert object_store._bucket_has_object_lock(_Client("ObjectLockConfigurationNotFoundError"), "b") is False
    assert object_store._bucket_has_object_lock(_Client("NotImplemented"), "b") is False
    assert object_store._bucket_has_object_lock(_Client("AccessDenied"), "b") is None
    assert object_store._bucket_has_object_lock(_Client("InvalidAccessKeyId"), "b") is None


def test_object_lock_ready_is_unknown_until_inspected() -> None:
    _reset_bucket_state()
    assert object_store.object_lock_ready(_settings()) is None
    assert object_store.object_lock_ready(_settings(object_storage_enabled=False)) is None


def test_put_audit_report_applies_legal_hold_for_failure(monkeypatch) -> None:
    fake = _FakeS3Client()
    monkeypatch.setattr(object_store, "ensure_bucket", lambda _settings: None)
    monkeypatch.setattr(object_store, "_s3_client", lambda _settings: fake)
    before = data_plane_metrics.OPTIONAL_ADAPTER_OPERATIONS_TOTAL.labels(
        adapter="object_storage",
        operation="put_audit_report",
        status="success",
    )._value.get()

    record = object_store.put_audit_report(
        _settings(object_storage_retention_days=30),
        "mission-1",
        "audit-1",
        "FAILED",
        {"score": 1},
        "2026-03-03T00:00:00+00:00",
    )

    assert fake.put_calls
    put_args = fake.put_calls[0]
    assert put_args["ObjectLockMode"] == "COMPLIANCE"
    assert put_args["ObjectLockLegalHoldStatus"] == "ON"
    assert record["key"].endswith("audit-1.json")
    assert record["legal_hold"] is True
    after = data_plane_metrics.OPTIONAL_ADAPTER_OPERATIONS_TOTAL.labels(
        adapter="object_storage",
        operation="put_audit_report",
        status="success",
    )._value.get()
    assert after >= before + 1


def test_put_audit_report_falls_back_when_object_lock_unsupported(monkeypatch) -> None:
    fake = _FakeS3Client()

    def _put_object(**kwargs):
        fake.put_calls.append(kwargs)
        if "ObjectLockMode" in kwargs:
            raise RuntimeError("lock unsupported")
        return {"ETag": '"etag-2"'}

    fake.put_object = _put_object
    monkeypatch.setattr(object_store, "ensure_bucket", lambda _settings: None)
    monkeypatch.setattr(object_store, "_s3_client", lambda _settings: fake)

    record = object_store.put_audit_report(
        _settings(object_storage_legal_hold_on_fail=False),
        "mission-1",
        "audit-2",
        "PASS",
        {"score": 2},
        "2026-03-03T00:00:00+00:00",
    )

    assert len(fake.put_calls) == 2
    assert "ObjectLockMode" in fake.put_calls[0]
    assert "ObjectLockMode" not in fake.put_calls[1]
    assert record["etag"] == "etag-2"


def test_put_audit_report_raises_when_legal_hold_lock_unsupported(monkeypatch) -> None:
    fake = _FakeS3Client()

    def _put_object(**kwargs):
        fake.put_calls.append(kwargs)
        if "ObjectLockMode" in kwargs:
            raise RuntimeError("lock unsupported")
        return {"ETag": '"etag-plain"'}

    fake.put_object = _put_object
    monkeypatch.setattr(object_store, "ensure_bucket", lambda _settings: None)
    monkeypatch.setattr(object_store, "_s3_client", lambda _settings: fake)
    before = data_plane_metrics.OBJECT_STORAGE_LEGAL_HOLD_FALLBACK_TOTAL._value.get()

    # Raised as a distinct type so callers can separate a permanent Object Lock
    # misconfiguration from a transient outage, while remaining a RuntimeError.
    with pytest.raises(object_store.LegalHoldUnavailableError, match="lock unsupported") as excinfo:
        object_store.put_audit_report(
            _settings(object_storage_legal_hold_on_fail=True),
            "mission-1",
            "audit-legal",
            "FAILED",
            {"score": 3},
            "2026-03-03T00:00:00+00:00",
        )

    assert isinstance(excinfo.value, RuntimeError)
    assert isinstance(excinfo.value.__cause__, RuntimeError)
    # The locked write was attempted, but no unprotected fallback write happened.
    assert len(fake.put_calls) == 1
    assert "ObjectLockMode" in fake.put_calls[0]
    after = data_plane_metrics.OBJECT_STORAGE_LEGAL_HOLD_FALLBACK_TOTAL._value.get()
    assert after == before + 1


def test_put_audit_report_warns_and_writes_for_retention_only(monkeypatch, caplog) -> None:
    fake = _FakeS3Client()

    def _put_object(**kwargs):
        fake.put_calls.append(kwargs)
        if "ObjectLockMode" in kwargs:
            raise RuntimeError("lock unsupported")
        return {"ETag": '"etag-retention"'}

    fake.put_object = _put_object
    monkeypatch.setattr(object_store, "ensure_bucket", lambda _settings: None)
    monkeypatch.setattr(object_store, "_s3_client", lambda _settings: fake)

    with caplog.at_level("WARNING", logger="orchestrator.object_store"):
        record = object_store.put_audit_report(
            _settings(object_storage_legal_hold_on_fail=False),
            "mission-1",
            "audit-retention",
            "PASS",
            {"score": 4},
            "2026-03-03T00:00:00+00:00",
        )

    # Locked attempt then unprotected fallback write.
    assert len(fake.put_calls) == 2
    assert "ObjectLockMode" in fake.put_calls[0]
    assert "ObjectLockMode" not in fake.put_calls[1]
    assert record["etag"] == "etag-retention"
    assert record["legal_hold"] is False
    assert any("retention will not be enforced" in message for message in caplog.messages)


def test_list_audit_artifacts_sorts_last_modified(monkeypatch) -> None:
    fake = _FakeS3Client()
    fake.contents = [
        {
            "Key": "missions/mission-1/audit-reports/a-old.json",
            "Size": 10,
            "ETag": '"old"',
            "LastModified": datetime(2026, 3, 3, 0, 0, 0, tzinfo=UTC),
        },
        {
            "Key": "missions/mission-1/audit-reports/a-new.json",
            "Size": 11,
            "ETag": '"new"',
            "LastModified": datetime(2026, 3, 4, 0, 0, 0, tzinfo=UTC),
        },
    ]
    monkeypatch.setattr(object_store, "ensure_bucket", lambda _settings: None)
    monkeypatch.setattr(object_store, "_s3_client", lambda _settings: fake)

    records = object_store.list_audit_artifacts(_settings(), "mission-1", 10)

    assert [record["etag"] for record in records] == ["new", "old"]
    assert records[0]["size_bytes"] == 11


def test_list_audit_artifacts_filters_invalid_entries(monkeypatch) -> None:
    fake = _FakeS3Client()
    fake.contents = [
        {
            "Key": "missions/mission-1/audit-reports/audit-1.txt",
            "Size": 1,
            "ETag": '"skip"',
            "LastModified": "bad-date",
        },
        {
            "Key": "missions/mission-1/audit-reports/audit-2.json",
            "Size": 2,
            "ETag": '"ok"',
            "LastModified": "unknown",
        },
        "not-a-dict",
    ]
    monkeypatch.setattr(object_store, "ensure_bucket", lambda _settings: None)
    monkeypatch.setattr(object_store, "_s3_client", lambda _settings: fake)

    records = object_store.list_audit_artifacts(_settings(), "mission-1", 999)

    assert records == [
        {
            "bucket": "mission-audit-artifacts",
            "key": "missions/mission-1/audit-reports/audit-2.json",
            "size_bytes": 2,
            "etag": "ok",
            "last_modified": "unknown",
            "url": "http://minio:9000/mission-audit-artifacts/missions/mission-1/audit-reports/audit-2.json",
        }
    ]


def test_object_storage_ready_returns_false_when_disabled() -> None:
    assert object_store.object_storage_ready(_settings(object_storage_enabled=False)) is False
    assert (
        data_plane_metrics.OPTIONAL_ADAPTER_ENABLED.labels(adapter="object_storage")._value.get()
        == 0
    )
    assert (
        data_plane_metrics.OPTIONAL_ADAPTER_READY.labels(adapter="object_storage")._value.get()
        == 0
    )


def test_object_storage_ready_returns_false_on_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        object_store,
        "ensure_bucket",
        lambda _settings: (_ for _ in ()).throw(RuntimeError("down")),
    )

    assert object_store.object_storage_ready(_settings()) is False
    assert (
        data_plane_metrics.OPTIONAL_ADAPTER_READY.labels(adapter="object_storage")._value.get()
        == 0
    )


def test_object_storage_ready_sets_ready_on_success(monkeypatch) -> None:
    monkeypatch.setattr(object_store, "ensure_bucket", lambda _settings: None)
    assert object_store.object_storage_ready(_settings()) is True
    assert (
        data_plane_metrics.OPTIONAL_ADAPTER_ENABLED.labels(adapter="object_storage")._value.get()
        == 1
    )
    assert (
        data_plane_metrics.OPTIONAL_ADAPTER_READY.labels(adapter="object_storage")._value.get()
        == 1
    )
