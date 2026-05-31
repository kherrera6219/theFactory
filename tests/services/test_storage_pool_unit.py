"""Unit tests for the storage connection pool and batch insert helpers.

Covers:
- init_connection_pool / get_connection / close_connection_pool lifecycle
  (Fix 1: psycopg ConnectionPool)
- upsert_logicnodes_batch / upsert_knowledge_batch (Fix 6: batch inserts)
"""
import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

storage = importlib.import_module("orchestrator.storage")
storage_core = importlib.import_module("orchestrator.storage_core")
storage_logicnodes = importlib.import_module("orchestrator.storage_logicnodes")
orchestrator_settings = importlib.import_module("orchestrator.settings")

Settings = orchestrator_settings.Settings


def _settings(**overrides) -> Settings:
    base = {
        "redis_url": "redis://redis:6379/0",
        "postgres_url": "postgresql://postgres:postgres@postgres:5432/ulr",
        "intake_stream": "missions.intake",
        "state_stream": "missions.state",
        "max_stream_len": 1000,
        "consumer_group": "orchestrator",
        "consumer_name": "orchestrator-test",
        "auto_transition_enabled": True,
        "transition_step_seconds": 1.0,
        "intake_topic": "intake.feature_contract.created",
        "default_priority": "NORMAL",
        "producer_name": "orchestrator",
        "event_schema_path": Path("."),
        "topics_path": Path("."),
        "admin_api_key": "",
        "internal_service_api_key": "",
        "readonly_api_key": "",
        "extra_api_keys": "",
    }
    base.update(overrides)
    return Settings(**base)


class FakeCursor:
    def __init__(self, *, rowcount: int = 0) -> None:
        self.rowcount = rowcount
        self.executemany_calls: list[tuple[str, list[Any]]] = []

    def execute(self, query: str, params: Any = None) -> None:  # pragma: no cover
        pass

    def executemany(self, query: str, seq: list[Any]) -> None:
        self.executemany_calls.append((query, seq))
        self.rowcount = len(seq)

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeConn:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.returned_to_pool = False

    def cursor(self) -> FakeCursor:
        return self._cursor

    def __enter__(self) -> "FakeConn":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        # Simulate the pool reclaiming the connection on block exit.
        self.returned_to_pool = True
        return False


class FakePool:
    """Mimics the subset of psycopg_pool.ConnectionPool that storage_core uses."""

    def __init__(self, conn: FakeConn, **kwargs: Any) -> None:
        self.conn = conn
        self.kwargs = kwargs
        self.closed = False
        self.borrow_count = 0

    def connection(self) -> FakeConn:
        self.borrow_count += 1
        return self.conn

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_pool():
    storage_core.close_connection_pool()
    yield
    storage_core.close_connection_pool()


def test_get_connection_raises_when_pool_uninitialized():
    storage_core.close_connection_pool()
    with pytest.raises(RuntimeError, match="connection pool is not initialized"):
        with storage_core.get_connection():
            pass


def test_init_connection_pool_passes_configured_sizes(monkeypatch):
    captured: dict[str, Any] = {}

    def _factory(**kwargs):
        captured.update(kwargs)
        return FakePool(FakeConn(FakeCursor()), **kwargs)

    monkeypatch.setattr(storage_core, "ConnectionPool", _factory)
    pool = storage_core.init_connection_pool(
        _settings(db_pool_min_size=3, db_pool_max_size=7)
    )

    assert pool is not None
    assert captured["min_size"] == 3
    assert captured["max_size"] == 7
    assert captured["max_waiting"] == 20
    assert captured["timeout"] == 30


def test_init_connection_pool_is_idempotent(monkeypatch):
    monkeypatch.setattr(
        storage_core, "ConnectionPool",
        lambda **kw: FakePool(FakeConn(FakeCursor()), **kw),
    )
    first = storage_core.init_connection_pool(_settings())
    second = storage_core.init_connection_pool(_settings())
    assert first is second


def test_get_connection_borrows_and_returns(monkeypatch):
    conn = FakeConn(FakeCursor())
    pool = FakePool(conn)
    monkeypatch.setattr(storage_core, "ConnectionPool", lambda **kw: pool)
    storage_core.init_connection_pool(_settings())

    with storage_core.get_connection() as borrowed:
        assert borrowed is conn
        assert pool.borrow_count == 1
        assert not conn.returned_to_pool

    # On block exit the connection is handed back to the pool.
    assert conn.returned_to_pool


def test_close_connection_pool_closes_and_clears(monkeypatch):
    pool = FakePool(FakeConn(FakeCursor()))
    monkeypatch.setattr(storage_core, "ConnectionPool", lambda **kw: pool)
    storage_core.init_connection_pool(_settings())

    storage_core.close_connection_pool()
    assert pool.closed
    with pytest.raises(RuntimeError):
        with storage_core.get_connection():
            pass


def test_init_connection_pool_raises_without_dependency(monkeypatch):
    monkeypatch.setattr(storage_core, "ConnectionPool", None)
    with pytest.raises(RuntimeError, match="psycopg-pool"):
        storage_core.init_connection_pool(_settings())


# --- Fix 6: batch inserts -------------------------------------------------


def test_upsert_logicnodes_batch_executes_many():
    cursor = FakeCursor()
    conn = FakeConn(cursor)
    nodes = [
        {"node_id": "n1", "node": {"k": 1}, "created_at": "2026-03-01T00:00:00+00:00"},
        {"node_id": "n2", "node": {"k": 2}, "created_at": "2026-03-01T00:00:01+00:00"},
    ]
    affected = storage_logicnodes.upsert_logicnodes_batch(conn, "m1", nodes)

    assert affected == 2
    assert len(cursor.executemany_calls) == 1
    query, params = cursor.executemany_calls[0]
    assert "mission_logicnodes" in query
    assert "ON CONFLICT (mission_id, node_id)" in query
    assert params[0] == ("m1", "n1", '{"k": 1}', "2026-03-01T00:00:00+00:00")


def test_upsert_logicnodes_batch_empty_is_noop():
    cursor = FakeCursor()
    conn = FakeConn(cursor)
    assert storage_logicnodes.upsert_logicnodes_batch(conn, "m1", []) == 0
    assert cursor.executemany_calls == []


def test_upsert_knowledge_batch_executes_many():
    cursor = FakeCursor()
    conn = FakeConn(cursor)
    items = [
        {"knowledge_id": "k1", "content": {"a": 1}, "created_at": "2026-03-01T00:00:00+00:00"},
        {"knowledge_id": "k2", "content": {"a": 2}, "created_at": "2026-03-01T00:00:01+00:00"},
    ]
    affected = storage_logicnodes.upsert_knowledge_batch(conn, "m1", items)

    assert affected == 2
    assert len(cursor.executemany_calls) == 1
    query, params = cursor.executemany_calls[0]
    assert "mission_knowledge" in query
    assert "ON CONFLICT (mission_id, knowledge_id)" in query
    assert params[1] == ("m1", "k2", '{"a": 2}', "2026-03-01T00:00:01+00:00")


def test_upsert_knowledge_batch_empty_is_noop():
    cursor = FakeCursor()
    conn = FakeConn(cursor)
    assert storage_logicnodes.upsert_knowledge_batch(conn, "m1", []) == 0
    assert cursor.executemany_calls == []


def test_batch_helpers_reexported_from_storage_facade():
    assert storage.upsert_logicnodes_batch is storage_logicnodes.upsert_logicnodes_batch
    assert storage.upsert_knowledge_batch is storage_logicnodes.upsert_knowledge_batch
    assert hasattr(storage, "init_connection_pool")
    assert hasattr(storage, "close_connection_pool")
    assert hasattr(storage, "get_connection")
