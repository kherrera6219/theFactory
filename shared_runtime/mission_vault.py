"""Per-mission provider credentials, kept out of Postgres, streams, and idempotency keys.

The Mission Control gateway forwards the operator's provider API keys with each
mission so the orchestrator can call the operator's chosen LLM. They used to be
stored in ``missions.metadata_json["vault"]`` -- plaintext in the database, returned
by mission reads, and retained forever. They now live in Redis under
``mission-vault:<mission_id>`` with a TTL that is refreshed on every lifecycle
advance, so a finished or abandoned mission's keys expire on their own.

Nothing here logs or returns secret values.
"""

from __future__ import annotations

import json
import logging
from typing import Any

LOGGER = logging.getLogger(__name__)

VAULT_METADATA_KEY = "vault"
VAULT_TTL_SECONDS = 72 * 3600


def vault_key(mission_id: str) -> str:
    """Return the Redis key used to store the per-mission credential vault."""
    return f"mission-vault:{mission_id}"


def split_vault(metadata: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, str]]:
    """Return ``(metadata without vault, vault secrets)``. Never mutates the input."""
    clean = dict(metadata or {})
    raw = clean.pop(VAULT_METADATA_KEY, None)
    vault = {str(k): str(v) for k, v in raw.items() if v} if isinstance(raw, dict) else {}
    return clean, vault


def strip_vault(metadata: dict[str, Any]) -> dict[str, Any]:
    """Defensive scrub used by every metadata write path."""
    if VAULT_METADATA_KEY not in metadata:
        return metadata
    return {k: v for k, v in metadata.items() if k != VAULT_METADATA_KEY}


def scrub_intake_payload_raw(payload_raw: str) -> str:
    """Strip ``metadata.vault`` from a serialized intake payload before DLQ persistence."""
    if not payload_raw or VAULT_METADATA_KEY not in payload_raw:
        return payload_raw
    try:
        parsed = json.loads(payload_raw)
    except Exception:  # noqa: BLE001
        return payload_raw
    if not isinstance(parsed, dict):
        return payload_raw
    changed = False
    if VAULT_METADATA_KEY in parsed:
        parsed = strip_vault(parsed)
        changed = True
    metadata = parsed.get("metadata")
    if isinstance(metadata, dict) and VAULT_METADATA_KEY in metadata:
        parsed = dict(parsed)
        parsed["metadata"] = strip_vault(metadata)
        changed = True
    return json.dumps(parsed) if changed else payload_raw


async def store_vault(redis_client: Any, mission_id: str, vault: dict[str, str]) -> bool:
    """Persist ``vault`` for ``mission_id`` with a TTL. Returns False if nothing stored."""
    if not vault or redis_client is None:
        return False
    try:
        await redis_client.set(vault_key(mission_id), json.dumps(vault), ex=VAULT_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001 - never leak values; log the type only
        LOGGER.warning("mission vault store failed for %s: %s", mission_id, type(exc).__name__)
        return False
    return True


async def load_vault(redis_client: Any, mission_id: str) -> dict[str, str]:
    """Load and TTL-refresh the vault for ``mission_id``; empty dict when absent."""
    if redis_client is None:
        return {}
    try:
        raw = await redis_client.get(vault_key(mission_id))
        if not raw:
            return {}
        await redis_client.expire(vault_key(mission_id), VAULT_TTL_SECONDS)
        parsed = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("mission vault load failed for %s: %s", mission_id, type(exc).__name__)
        return {}
    return parsed if isinstance(parsed, dict) else {}
