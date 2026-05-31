import hashlib
import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

orchestrator_migrations = importlib.import_module("orchestrator.migrations")
orchestrator_settings = importlib.import_module("orchestrator.settings")

migrations = orchestrator_migrations
Settings = orchestrator_settings.Settings


def _settings() -> Settings:
    root = ROOT
    return Settings(
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
        event_schema_path=root / "schemas" / "event.envelope.schema.json",
        topics_path=root / "protocol" / "topics.yaml",
        admin_api_key="admin-key",
        internal_service_api_key="worker-key",
        readonly_api_key="viewer-key",
        extra_api_keys="operator-key=mutate,read",
    )


class FakeCursor:
    def __init__(self, fetchall_results: list[Any] | None = None) -> None:
        self.fetchall_results = list(fetchall_results or [])
        self.executed: list[tuple[str, Any]] = []

    def execute(self, query: str, params: Any = None) -> None:
        self.executed.append((query, params))

    def fetchall(self) -> Any:
        if self.fetchall_results:
            return self.fetchall_results.pop(0)
        return []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeConn:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> FakeCursor:
        return self._cursor

    def __enter__(self) -> "FakeConn":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_parse_version_validation() -> None:
    assert migrations._parse_version(Path("V001_init.sql")) == "001"

    with pytest.raises(RuntimeError):
        migrations._parse_version(Path("001_init.sql"))

    with pytest.raises(RuntimeError):
        migrations._parse_version(Path("Vabc_init.sql"))


def test_load_migrations_orders_by_numeric_version(tmp_path: Path) -> None:
    (tmp_path / "V010_last.sql").write_text("SELECT 10;", encoding="utf-8")
    (tmp_path / "V002_middle.sql").write_text("SELECT 2;", encoding="utf-8")
    (tmp_path / "V001_first.sql").write_text("SELECT 1;", encoding="utf-8")

    scripts = migrations._load_migrations(tmp_path)
    assert [script.version for script in scripts] == ["001", "002", "010"]
    names = [script.name for script in scripts]
    assert names == ["V001_first.sql", "V002_middle.sql", "V010_last.sql"]


def test_apply_migrations_executes_new_scripts(tmp_path: Path) -> None:
    script_path = tmp_path / "V001_init.sql"
    script_sql = "CREATE TABLE IF NOT EXISTS t (id INT);"
    script_path.write_text(script_sql, encoding="utf-8")
    cursor = FakeCursor(fetchall_results=[[]])

    migrations.apply_migrations(
        _settings(),
        connect=lambda _settings_obj: FakeConn(cursor),
        migrations_dir=tmp_path,
    )

    # Order: advisory lock, create table, select, script sql, insert, advisory unlock.
    assert len(cursor.executed) == 6
    assert "pg_advisory_lock" in cursor.executed[0][0]
    assert cursor.executed[0][1] == (migrations.MIGRATION_ADVISORY_LOCK_ID,)
    assert "CREATE TABLE IF NOT EXISTS schema_migrations" in cursor.executed[1][0]
    assert "SELECT version, checksum FROM schema_migrations" in cursor.executed[2][0]
    assert cursor.executed[3][0] == script_sql
    assert cursor.executed[4][1][0] == "001"
    assert cursor.executed[4][1][1] == "V001_init.sql"
    assert "pg_advisory_unlock" in cursor.executed[5][0]
    assert cursor.executed[5][1] == (migrations.MIGRATION_ADVISORY_LOCK_ID,)


def test_apply_migrations_skips_applied_versions(tmp_path: Path) -> None:
    script_path = tmp_path / "V001_init.sql"
    script_sql = "CREATE TABLE IF NOT EXISTS t (id INT);"
    script_path.write_text(script_sql, encoding="utf-8")
    checksum = hashlib.sha256(script_sql.encode("utf-8")).hexdigest()
    cursor = FakeCursor(fetchall_results=[[("001", checksum)]])

    migrations.apply_migrations(
        _settings(),
        connect=lambda _settings_obj: FakeConn(cursor),
        migrations_dir=tmp_path,
    )

    # lock, create table, select, unlock — no script/insert because version is applied.
    assert len(cursor.executed) == 4
    assert "pg_advisory_lock" in cursor.executed[0][0]
    assert "pg_advisory_unlock" in cursor.executed[-1][0]


def test_apply_migrations_raises_on_checksum_mismatch(tmp_path: Path) -> None:
    script_path = tmp_path / "V001_init.sql"
    script_path.write_text("CREATE TABLE IF NOT EXISTS t (id INT);", encoding="utf-8")
    cursor = FakeCursor(fetchall_results=[[("001", "bad-checksum")]])

    with pytest.raises(RuntimeError):
        migrations.apply_migrations(
            _settings(),
            connect=lambda _settings_obj: FakeConn(cursor),
            migrations_dir=tmp_path,
        )

    # The advisory lock must always be released, even when a migration fails.
    assert any("pg_advisory_unlock" in query for query, _ in cursor.executed)


def test_apply_migrations_releases_lock_even_on_script_failure(tmp_path: Path) -> None:
    script_path = tmp_path / "V001_init.sql"
    script_path.write_text("BOOM;", encoding="utf-8")

    class FailingCursor(FakeCursor):
        def execute(self, query: str, params: Any = None) -> None:
            super().execute(query, params)
            if query == "BOOM;":
                raise RuntimeError("script failed")

    cursor = FailingCursor(fetchall_results=[[]])

    with pytest.raises(RuntimeError):
        migrations.apply_migrations(
            _settings(),
            connect=lambda _settings_obj: FakeConn(cursor),
            migrations_dir=tmp_path,
        )

    assert any("pg_advisory_unlock" in query for query, _ in cursor.executed)


def test_apply_migrations_serializes_concurrent_calls() -> None:
    """Concurrent apply_migrations calls must not overlap inside the advisory lock.

    The advisory lock is modeled with a real threading.Lock so that a second
    caller cannot enter the migration body while the first still holds it.
    """
    import threading
    import time

    lock = threading.Lock()
    inside_count = 0
    max_concurrent = 0
    order: list[str] = []
    state_lock = threading.Lock()

    class LockingCursor:
        def __init__(self) -> None:
            self.executed: list[tuple[str, Any]] = []
            self._holds_lock = False

        def execute(self, query: str, params: Any = None) -> None:
            nonlocal inside_count, max_concurrent
            self.executed.append((query, params))
            if "pg_advisory_lock" in query:
                lock.acquire()
                self._holds_lock = True
                with state_lock:
                    inside_count += 1
                    max_concurrent = max(max_concurrent, inside_count)
                    order.append("enter")
                # Hold briefly to give the other thread a chance to race.
                time.sleep(0.02)
            elif "pg_advisory_unlock" in query:
                with state_lock:
                    inside_count -= 1
                    order.append("exit")
                if self._holds_lock:
                    self._holds_lock = False
                    lock.release()

        def fetchall(self) -> Any:
            return []

        def __enter__(self) -> "LockingCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    def run() -> None:
        cursor = LockingCursor()
        migrations.apply_migrations(
            _settings(),
            connect=lambda _settings_obj: FakeConn(cursor),
            migrations_dir=migrations._migration_dir(),
        )

    threads = [threading.Thread(target=run) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # At no point were two callers inside the lock at once.
    assert max_concurrent == 1
    # Each enter is immediately followed by its matching exit.
    assert order == ["enter", "exit"] * 4
