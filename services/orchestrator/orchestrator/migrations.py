from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .settings import Settings

try:
    import psycopg
except ModuleNotFoundError:
    psycopg = None


# Fixed advisory-lock id so concurrent orchestrator boots serialize on apply_migrations()
# instead of racing on the schema_migrations primary key.
MIGRATION_ADVISORY_LOCK_ID = 12345678


@dataclass(frozen=True)
class MigrationScript:
    version: str
    name: str
    checksum: str
    sql: str


def _default_connect(settings: Settings) -> Any:
    if psycopg is None:
        raise RuntimeError("psycopg dependency is not installed")
    # Migrations connect via migration_postgres_url (Postgres directly), not
    # through PgBouncer: the session-level advisory lock taken in apply_migrations
    # would not survive transaction-pool backend reassignment. prepare_threshold=None
    # keeps parity with the pooled connection settings.
    return psycopg.connect(
        settings.migration_postgres_url, autocommit=True, prepare_threshold=None
    )


def _migration_dir() -> Path:
    return Path(__file__).resolve().parent / "migrations"


def _parse_version(path: Path) -> str:
    stem = path.stem
    if not stem.startswith("V"):
        raise RuntimeError(f"invalid migration filename (missing V prefix): {path.name}")
    token = stem[1:].split("_", 1)[0]
    if not token.isdigit():
        raise RuntimeError(f"invalid migration filename version: {path.name}")
    return token


def _load_migrations(migrations_dir: Path) -> list[MigrationScript]:
    scripts: list[MigrationScript] = []
    sorted_paths = sorted(
        migrations_dir.glob("V*.sql"),
        key=lambda p: (int(_parse_version(p)), p.name),
    )
    for path in sorted_paths:
        sql = path.read_text(encoding="utf-8")
        scripts.append(
            MigrationScript(
                version=_parse_version(path),
                name=path.name,
                checksum=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
                sql=sql,
            )
        )
    return scripts


def apply_migrations(
    settings: Settings,
    *,
    connect: Callable[[Settings], Any] | None = None,
    migrations_dir: Path | None = None,
) -> None:
    connector = connect or _default_connect
    directory = migrations_dir or _migration_dir()
    scripts = _load_migrations(directory)

    with connector(settings) as conn:
        with conn.cursor() as cur:
            # Serialize concurrent migration runs. The lock is held for the duration of
            # the migration work and released in the finally block (also released on
            # connection close, but we release explicitly to free it promptly).
            cur.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_ADVISORY_LOCK_ID,))
            try:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        checksum TEXT NOT NULL,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                cur.execute("SELECT version, checksum FROM schema_migrations")
                applied_rows = cur.fetchall() or []
                applied_checksums = {row[0]: row[1] for row in applied_rows}

                for script in scripts:
                    existing_checksum = applied_checksums.get(script.version)
                    if existing_checksum is not None:
                        if existing_checksum != script.checksum:
                            raise RuntimeError(
                                "migration checksum mismatch for "
                                f"version {script.version} ({script.name})"
                            )
                        continue

                    cur.execute(script.sql)
                    cur.execute(
                        """
                        INSERT INTO schema_migrations (version, name, checksum)
                        VALUES (%s, %s, %s)
                        """,
                        (script.version, script.name, script.checksum),
                    )
            finally:
                cur.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_ADVISORY_LOCK_ID,))
