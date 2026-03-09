from __future__ import annotations

import os
import re
from typing import Any, Mapping

AGENT_SERVICE_KEY_ENV_PATTERN = re.compile(r"^AGENT_(\d{2})_([A-Z0-9_]+)_SERVICE_API_KEY$")


def normalize_agent_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    return normalized or None


def agent_service_key_env_name(agent_id: str) -> str | None:
    normalized = normalize_agent_id(agent_id)
    if normalized is None:
        return None
    return f"{normalized.replace('-', '_')}_SERVICE_API_KEY"


def parse_agent_service_key_map(
    raw: str,
    *,
    allowed_agent_ids: set[str] | None = None,
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for entry in (part.strip() for part in raw.split(";") if part.strip()):
        if "=" not in entry:
            continue
        agent_id, key = entry.split("=", 1)
        normalized_agent_id = normalize_agent_id(agent_id)
        normalized_key = key.strip()
        if not normalized_agent_id or not normalized_key:
            continue
        if allowed_agent_ids is not None and normalized_agent_id not in allowed_agent_ids:
            continue
        mapping[normalized_agent_id] = normalized_key
    return mapping


def configured_agent_service_key_map(
    raw_mapping: str,
    *,
    env: Mapping[str, str] | None = None,
    allowed_agent_ids: set[str] | None = None,
) -> dict[str, str]:
    env_mapping = env if env is not None else os.environ
    mapping = parse_agent_service_key_map(raw_mapping, allowed_agent_ids=allowed_agent_ids)
    for env_name, raw_value in env_mapping.items():
        match = AGENT_SERVICE_KEY_ENV_PATTERN.match(env_name)
        if not match:
            continue
        normalized_key = raw_value.strip()
        if not normalized_key:
            continue
        agent_id = f"AGENT-{match.group(1)}-{match.group(2).replace('_', '-')}"
        if allowed_agent_ids is not None and agent_id not in allowed_agent_ids:
            continue
        mapping[agent_id] = normalized_key
    return mapping


def service_api_key_for_agent(
    agent_id: str | None,
    *,
    fallback_key: str,
    raw_mapping: str = "",
    key_mode: str = "shared",
    env: Mapping[str, str] | None = None,
    allowed_agent_ids: set[str] | None = None,
) -> str:
    normalized_agent_id = normalize_agent_id(agent_id)
    env_mapping = env if env is not None else os.environ
    if normalized_agent_id:
        env_name = agent_service_key_env_name(normalized_agent_id)
        if env_name:
            direct_env_key = env_mapping.get(env_name, "").strip()
            if direct_env_key:
                return direct_env_key
        mapped_key = configured_agent_service_key_map(
            raw_mapping,
            env=env_mapping,
            allowed_agent_ids=allowed_agent_ids,
        ).get(normalized_agent_id)
        if mapped_key:
            return mapped_key
        if (key_mode.strip().lower() or "shared") == "strict":
            raise RuntimeError(f"missing dedicated service key for {normalized_agent_id}")
    return fallback_key
