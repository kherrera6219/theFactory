"""storage_core.py — Shared DB infrastructure for the orchestrator storage layer.

Provides the psycopg import shim, connection factory, schema migration helper,
and the low-level JSON/datetime helpers used by every domain storage module.

Do not import domain storage modules from here (would create circular imports).
"""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Iterator

try:
    import psycopg
except ModuleNotFoundError:
    psycopg = None  # type: ignore[assignment]

try:
    from psycopg_pool import ConnectionPool
except ModuleNotFoundError:
    ConnectionPool = None  # type: ignore[assignment,misc]

from . import migrations
from .settings import Settings

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


class PodAssignmentConflictError(Exception):
    def __init__(self, existing_assignment: dict[str, Any]) -> None:
        super().__init__("mission already assigned to a different pod")
        self.existing_assignment = existing_assignment


def db_connect(settings: Settings) -> Any:
    """Open a single, direct connection (no pool).

    Used for schema migrations, which take a session-level advisory lock and so
    require a stable session. Connects via ``migration_postgres_url`` (Postgres
    directly) rather than ``postgres_url`` (PgBouncer): in transaction-pool mode
    the bouncer reassigns the backend and runs DISCARD ALL between statements,
    silently releasing the advisory lock mid-migration. Storage operations use
    the pool via ``get_connection``.
    """
    if psycopg is None:
        raise RuntimeError("psycopg dependency is not installed")
    # prepare_threshold=None disables psycopg's automatic server-side prepared
    # statements, kept for parity with the pooled path.
    return psycopg.connect(
        settings.migration_postgres_url, autocommit=True, prepare_threshold=None
    )


def init_connection_pool(settings: Settings) -> ConnectionPool:
    """Initialize the module-level connection pool (idempotent).

    Connections are configured with ``autocommit=True`` to preserve the
    transaction semantics of the previous per-call ``db_connect`` behavior.
    """
    global _pool
    if _pool is not None:
        return _pool
    if ConnectionPool is None:
        raise RuntimeError("psycopg-pool dependency is not installed")

    def _configure(conn: Any) -> None:
        conn.autocommit = True
        # Disable server-side prepared statements so the pool is safe behind
        # PgBouncer transaction pooling (connections are reassigned between
        # transactions and named prepared statements would not persist).
        conn.prepare_threshold = None

    _pool = ConnectionPool(
        conninfo=settings.postgres_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        max_waiting=20,
        timeout=30,
        configure=_configure,
        open=True,
    )
    return _pool


def close_connection_pool() -> None:
    """Close the module-level connection pool, if open."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def get_connection() -> Iterator[Any]:
    """Borrow a connection from the pool for the duration of the block.

    The connection is returned to the pool on block exit. Raises if the pool
    has not been initialized via ``init_connection_pool``.
    """
    if _pool is None:
        raise RuntimeError(
            "connection pool is not initialized; call init_connection_pool() first"
        )
    with _pool.connection() as conn:
        yield conn


def ensure_db_schema(settings: Settings) -> None:
    """Apply schema migrations and ensure required system bootstrap rows exist."""
    migrations.apply_migrations(settings, connect=db_connect)

    # 1.1.0 QC: Ensure system mission for global knowledge lake bootstrap
    # This prevents foreign key violations when indexing language docs.
    try:
        from datetime import UTC, datetime

        from .models import MissionRecord, MissionState
        from .storage_missions import upsert_mission

        system_mission = MissionRecord(
            mission_id="__knowledge_lake__",
            prompt="System knowledge lake bootstrap mission.",
            state=MissionState.complete,
            created_at=datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
            metadata={"source": "system", "name": "Global Knowledge Lake"}
        )
        upsert_mission(settings, system_mission, source_stream_id=None)
    except Exception as e:
        logger.warning("Knowledge lake bootstrap skipped (may already exist): %s", e)


def _to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return str(value)


def _json_to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return json.loads(value or "{}")
    if isinstance(value, dict):
        return value
    return {}


def _json_to_list(value: Any) -> list[Any]:
    if isinstance(value, str):
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    if isinstance(value, list):
        return value
    return []


class FactoryJsonEncoder(json.JSONEncoder):
    """JSON encoder that supports datetime and other pydantic-adjacent types."""

    def default(self, obj: Any) -> Any:
        """Return a JSON-serializable representation for supported objects."""
        if isinstance(obj, datetime):
            return obj.astimezone(UTC).isoformat()
        if hasattr(obj, "model_dump") and callable(obj.model_dump):
            return obj.model_dump()
        return super().default(obj)


def factory_json_dumps(payload: Any) -> str:
    """Consistently dump JSON using the factory encoder."""
    return json.dumps(
        payload,
        cls=FactoryJsonEncoder,
        separators=(",", ":"),
        sort_keys=True
    )



_DIAGNOSTIC_TABLES: tuple[str, ...] = (
    "missions",
    "mission_logicnodes",
    "mission_knowledge",
    "mission_build_artifacts",
    "mission_audit_reports",
    "review_approvals",
    "mission_runtime_qc",
    "mission_state_events",
    "agent_action_events",
    "llm_usage_events",
    "projects",
    "project_work_items",
)


def get_database_diagnostics(settings: Settings) -> dict[str, Any]:
    """Return non-sensitive PostgreSQL schema, pool, and table row-count diagnostics."""
    pool_info: dict[str, Any] = {
        "initialized": _pool is not None,
        "min_size": int(getattr(settings, "db_pool_min_size", 2)),
        "max_size": int(getattr(settings, "db_pool_max_size", 10)),
    }
    if _pool is not None and hasattr(_pool, "get_stats") and callable(_pool.get_stats):
        try:
            stats = _pool.get_stats()
            if isinstance(stats, dict):
                pool_info["pool_size"] = int(stats.get("pool_size", 0))
                pool_info["pool_available"] = int(stats.get("pool_available", 0))
                pool_info["requests_waiting"] = int(stats.get("requests_waiting", 0))
        except Exception:
            pass

    table_counts: dict[str, int] = {name: 0 for name in _DIAGNOSTIC_TABLES}
    latest_migration_version = "011"
    migration_count = 11
    try:
        scripts = migrations._load_migrations(migrations._migration_dir())
        if scripts:
            latest_migration_version = scripts[-1].version
            migration_count = len(scripts)
    except Exception:
        pass

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT version, COUNT(*) OVER () AS total_count
                    FROM schema_migrations
                    ORDER BY version DESC
                    LIMIT 1
                    """
                )
                mig_row = cur.fetchone()
                if mig_row:
                    latest_migration_version = str(mig_row[0])
                    migration_count = int(mig_row[1])

                cur.execute(
                    """
                    SELECT relname, GREATEST(reltuples::bigint, 0)
                    FROM pg_class
                    WHERE relname = ANY(%s)
                    """,
                    (list(_DIAGNOSTIC_TABLES),),
                )
                for row in cur.fetchall() or []:
                    if row and len(row) >= 2:
                        table_counts[str(row[0])] = max(0, int(row[1]))
    except Exception:
        pass

    return {
        "pool": pool_info,
        "latest_migration_version": latest_migration_version,
        "migration_count": migration_count,
        "table_counts": table_counts,
        "retention_days_default": 90,
    }
