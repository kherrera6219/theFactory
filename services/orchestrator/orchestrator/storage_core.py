"""storage_core.py — Shared DB infrastructure for the orchestrator storage layer.

Provides the psycopg import shim, connection factory, schema migration helper,
and the low-level JSON/datetime helpers used by every domain storage module.

Do not import domain storage modules from here (would create circular imports).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

try:
    import psycopg
except ModuleNotFoundError:
    psycopg = None  # type: ignore[assignment]

from . import migrations
from .settings import Settings


class PodAssignmentConflictError(Exception):
    def __init__(self, existing_assignment: dict[str, Any]) -> None:
        super().__init__("mission already assigned to a different pod")
        self.existing_assignment = existing_assignment


def db_connect(settings: Settings) -> Any:
    if psycopg is None:
        raise RuntimeError("psycopg dependency is not installed")
    return psycopg.connect(settings.postgres_url, autocommit=True)


def ensure_db_schema(settings: Settings) -> None:
    migrations.apply_migrations(settings, connect=db_connect)

    # 1.1.0 QC: Ensure system mission for global knowledge lake bootstrap
    # This prevents foreign key violations when indexing language docs.
    try:
        from .storage_missions import upsert_mission
        from .models import MissionRecord, MissionState
        from datetime import datetime, UTC
        
        system_mission = MissionRecord(
            mission_id="__knowledge_lake__",
            prompt="System knowledge lake bootstrap mission.",
            state=MissionState.complete,
            created_at=datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
            metadata={"source": "system", "name": "Global Knowledge Lake"}
        )
        upsert_mission(settings, system_mission, source_stream_id=None)
    except Exception:
        # Ignore if exists or other transient startup issue; migrations are the priority.
        pass


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
