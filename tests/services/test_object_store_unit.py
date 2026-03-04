import importlib
import sys
from datetime import UTC, datetime
from pathlib import Path

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
    def __init__(self) -> None:
        self.head_bucket_called = 0
        self.created_bucket = False
        self.put_calls: list[dict[str, object]] = []
        self.contents: list[dict[str, object]] = []

    def head_bucket(self, *, Bucket: str) -> None:
        _ = Bucket
        self.head_bucket_called += 1
        if not self.created_bucket:
            raise RuntimeError("missing")

    def create_bucket(self, **kwargs) -> None:
        _ = kwargs
        self.created_bucket = True

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)
        return {"ETag": '"etag-1"'}

    def list_objects_v2(self, **kwargs):
        _ = kwargs
        return {
            "Contents": self.contents,
        }


def test_ensure_bucket_creates_when_missing(monkeypatch) -> None:
    object_store._BUCKET_CACHE.clear()
    fake = _FakeS3Client()
    monkeypatch.setattr(object_store, "_s3_client", lambda _settings: fake)

    object_store.ensure_bucket(_settings())

    assert fake.head_bucket_called == 1
    assert fake.created_bucket is True


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
