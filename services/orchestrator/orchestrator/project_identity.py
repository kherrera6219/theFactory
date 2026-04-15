from __future__ import annotations

import re
from typing import Any

_PROJECT_SLUG_PATTERN = re.compile(r"[^a-z0-9._-]+")


def normalize_project_id(value: Any, *, fallback: str = "project-unknown") -> str:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return fallback
    candidate = _PROJECT_SLUG_PATTERN.sub("-", candidate).strip("-.")
    if not candidate:
        return fallback
    if candidate.startswith("project-"):
        return candidate
    return f"project-{candidate}"


def resolve_project_id(
    metadata: dict[str, Any] | None,
    *,
    mission_id: str | None = None,
) -> str:
    details = metadata if isinstance(metadata, dict) else {}
    explicit = details.get("project_id")
    if isinstance(explicit, str) and explicit.strip():
        return normalize_project_id(explicit)

    source = details.get("source")
    if isinstance(source, str) and source.strip():
        return normalize_project_id(source)

    if isinstance(mission_id, str) and mission_id.strip():
        return normalize_project_id(mission_id)

    return "project-unknown"


def with_project_identity(
    metadata: dict[str, Any] | None,
    *,
    mission_id: str | None = None,
) -> dict[str, Any]:
    normalized = dict(metadata) if isinstance(metadata, dict) else {}
    project_id = resolve_project_id(normalized, mission_id=mission_id)
    normalized["project_id"] = project_id
    if "project_name" not in normalized:
        source = normalized.get("source")
        if isinstance(source, str) and source.strip():
            normalized["project_name"] = source.strip()
    return normalized
