from __future__ import annotations

import json
import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Mapping

AGENT_SERVICE_KEY_ENV_PATTERN = re.compile(r"^AGENT_(\d{2})_([A-Z0-9_]+)_SERVICE_API_KEY$")

LOGGER = logging.getLogger(__name__)

# 2026 best practice: minimum key entropy and length to guard against weak keys
_MIN_KEY_LENGTH = 16
_MIN_KEY_ENTROPY = 3.0
PRODUCTION_ENVIRONMENTS = {"prod", "production"}
PLACEHOLDER_SERVICE_API_KEYS = {
    "",
    "change-me",
    "changeme",
    "dev-key",
    "test-key",
    "test-worker-key",
    "worker-key",
}


def _shannon_entropy(value: str) -> float:
    """Compute Shannon entropy of *value* in bits per character."""
    if not value:
        return 0.0
    freq: dict[str, int] = {}
    for ch in value:
        freq[ch] = freq.get(ch, 0) + 1
    total = len(value)
    return -sum((count / total) * math.log2(count / total) for count in freq.values())


def validate_key_strength(key: str, agent_id: str | None = None) -> bool:
    """Return True if *key* meets minimum strength requirements; log warnings otherwise.

    Does NOT raise — callers decide whether to fail-closed or warn-only.
    """
    label = agent_id or "<unknown>"
    if len(key) < _MIN_KEY_LENGTH:
        LOGGER.warning(
            "agent key for %s is too short (%d chars; minimum %d)",
            label, len(key), _MIN_KEY_LENGTH,
        )
        return False
    entropy = _shannon_entropy(key)
    if entropy < _MIN_KEY_ENTROPY:
        LOGGER.warning(
            "agent key for %s has low entropy (%.2f bits; minimum %.1f)",
            label, entropy, _MIN_KEY_ENTROPY,
        )
        return False
    return True


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
    key_file = env_mapping.get("AGENT_SERVICE_KEY_FILE", "").strip()
    if key_file:
        mapping.update(
            load_agent_service_key_file(
                key_file,
                allowed_agent_ids=allowed_agent_ids,
            )
        )
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


def load_agent_service_key_file(
    path: str | os.PathLike[str],
    *,
    allowed_agent_ids: set[str] | None = None,
) -> dict[str, str]:
    """Load a JSON ``agent_id -> key`` map for live key rotation.

    The file is read on every key resolution, so an atomic file replacement rotates
    credentials without restarting workers. Invalid configured files fail closed.
    """
    key_path = Path(path)
    try:
        payload = json.loads(key_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"failed to load agent service key file: {key_path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("agent service key file must contain a JSON object")

    mapping: dict[str, str] = {}
    for raw_agent_id, raw_key in payload.items():
        normalized_agent_id = normalize_agent_id(raw_agent_id)
        if not normalized_agent_id or not isinstance(raw_key, str):
            raise RuntimeError("agent service key file contains an invalid entry")
        normalized_key = raw_key.strip()
        if not normalized_key:
            raise RuntimeError(
                f"agent service key file contains an empty key for {normalized_agent_id}"
            )
        if allowed_agent_ids is not None and normalized_agent_id not in allowed_agent_ids:
            continue
        mapping[normalized_agent_id] = normalized_key
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
                validate_key_strength(direct_env_key, normalized_agent_id)
                LOGGER.debug("key resolved via env var for agent %s", normalized_agent_id)
                return direct_env_key
        mapped_key = configured_agent_service_key_map(
            raw_mapping,
            env=env_mapping,
            allowed_agent_ids=allowed_agent_ids,
        ).get(normalized_agent_id)
        if mapped_key:
            validate_key_strength(mapped_key, normalized_agent_id)
            LOGGER.debug("key resolved via mapping for agent %s", normalized_agent_id)
            return mapped_key
        if (key_mode.strip().lower() or "shared") == "strict":
            raise RuntimeError(f"missing dedicated service key for {normalized_agent_id}")
    validate_key_strength(fallback_key, "fallback")
    LOGGER.debug("using fallback key for agent %s", normalized_agent_id or "<none>")
    return fallback_key

def enforce_production_service_auth_config(
    *,
    environment: str,
    service_api_key: str,
    key_mode: str,
    required_agent_ids: list[str | None] | tuple[str | None, ...] = (),
    raw_mapping: str = "",
    env: Mapping[str, str] | None = None,
    service_name: str = "service",
) -> None:
    """Fail closed on production worker auth misconfiguration.

    Local development can use the shared fallback key, but production service
    callers must use strict per-agent keys and a non-placeholder fallback for
    any legacy or unassigned internal calls.
    """
    normalized_environment = environment.strip().lower()
    if normalized_environment not in PRODUCTION_ENVIRONMENTS:
        return

    normalized_mode = key_mode.strip().lower() or "shared"
    if normalized_mode != "strict":
        raise RuntimeError(
            f"{service_name} requires AGENT_SERVICE_KEY_MODE=strict in production"
        )

    normalized_fallback = service_api_key.strip()
    if normalized_fallback.lower() in PLACEHOLDER_SERVICE_API_KEYS:
        raise RuntimeError(
            f"{service_name} requires a non-placeholder SERVICE_API_KEY in production"
        )
    if not validate_key_strength(normalized_fallback, "fallback"):
        raise RuntimeError(
            f"{service_name} requires a strong SERVICE_API_KEY in production"
        )

    for required_agent_id in required_agent_ids:
        normalized_agent_id = normalize_agent_id(required_agent_id)
        if not normalized_agent_id:
            continue
        resolved_key = service_api_key_for_agent(
            normalized_agent_id,
            fallback_key=normalized_fallback,
            raw_mapping=raw_mapping,
            key_mode=normalized_mode,
            env=env,
        )
        if not validate_key_strength(resolved_key, normalized_agent_id):
            raise RuntimeError(
                f"{service_name} requires a strong dedicated key for {normalized_agent_id}"
            )
