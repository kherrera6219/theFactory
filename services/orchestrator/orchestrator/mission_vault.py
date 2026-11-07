"""Per-mission provider credentials, kept out of Postgres.

The Mission Control gateway forwards the operator's provider API keys with each
mission so the orchestrator can call the operator's chosen LLM. They used to be
stored in ``missions.metadata_json["vault"]`` -- plaintext in the database, returned
by mission reads, and retained forever. They now live in Redis under
``mission-vault:<mission_id>`` with a TTL that is refreshed on every lifecycle
advance, so a finished or abandoned mission's keys expire on their own.

Nothing here logs or returns secret values.
"""

from __future__ import annotations

from shared_runtime.mission_vault import (
    VAULT_METADATA_KEY,
    VAULT_TTL_SECONDS,
    load_vault,
    scrub_intake_payload_raw,
    split_vault,
    store_vault,
    strip_vault,
    vault_key,
)

__all__ = [
    "VAULT_METADATA_KEY",
    "VAULT_TTL_SECONDS",
    "load_vault",
    "scrub_intake_payload_raw",
    "split_vault",
    "store_vault",
    "strip_vault",
    "vault_key",
]
