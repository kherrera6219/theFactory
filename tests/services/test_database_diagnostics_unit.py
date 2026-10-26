"""Phase 4 (COMPLETION_PLAN_2026-10-26): database diagnostics + delta gate preservation."""
from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

storage_core = importlib.import_module("orchestrator.storage_core")
storage_missions = importlib.import_module("orchestrator.storage_missions")
storage = importlib.import_module("orchestrator.storage")


class _Cursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, Any]] = []
        self._last = ""

    def execute(self, query: str, params: Any = None) -> None:
        self.executed.append((query, params))
        self._last = query

    def fetchone(self) -> Any:
        return ("011", 11)

    def fetchall(self) -> Any:
        return [("missions", 42), ("mission_logicnodes", -1)]

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, *a: Any) -> bool:
        return False


class _Conn:
    def __init__(self, cur: _Cursor) -> None:
        self._cur = cur

    def cursor(self) -> _Cursor:
        return self._cur


def test_update_mission_metadata_sql_preserves_delta_audit_gate() -> None:
    sql = storage_missions.UPDATE_MISSION_METADATA_SQL
    assert "delta_audit_gate" in sql
    assert sql.count("%s") == 3
    assert "jsonb_build_object('delta_audit_gate'" in sql


def test_get_database_diagnostics_reports_counts(monkeypatch: Any) -> None:
    cur = _Cursor()

    @contextmanager
    def fake_conn():
        yield _Conn(cur)

    monkeypatch.setattr(storage_core, "get_connection", fake_conn)
    monkeypatch.setattr(storage_core, "_pool", None)
    settings = SimpleNamespace(db_pool_min_size=2, db_pool_max_size=10)
    result = storage.get_database_diagnostics(settings)
    assert result["latest_migration_version"] == "011"
    assert result["migration_count"] == 11
    assert result["table_counts"]["missions"] == 42
    assert result["table_counts"]["mission_logicnodes"] == 0
    assert result["pool"]["initialized"] is False


def test_get_database_diagnostics_survives_db_failure(monkeypatch: Any) -> None:
    @contextmanager
    def boom():
        raise RuntimeError("db down")
        yield  # pragma: no cover

    monkeypatch.setattr(storage_core, "get_connection", boom)
    result = storage.get_database_diagnostics(SimpleNamespace())
    assert result["table_counts"]["missions"] == 0
    assert result["latest_migration_version"]


def test_v011_migration_present() -> None:
    path = (
        ROOT / "services" / "orchestrator" / "orchestrator" / "migrations"
        / "V011_database_performance_indexes.sql"
    )
    text = path.read_text(encoding="utf-8")
    for idx in (
        "idx_mission_knowledge_language",
        "idx_mission_logicnodes_domain",
        "idx_missions_project_state",
    ):
        assert idx in text
