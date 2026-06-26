from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from re import Pattern
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema import ValidationError as JSONSchemaValidationError

LOGGER = logging.getLogger(__name__)


class ProtocolValidationError(Exception):
    pass


class ReplayDetectedError(ProtocolValidationError):
    """Raised when an event_id has already been processed (replay attack detected)."""


def parse_date_time(value: str) -> datetime:
    """Parse an RFC 3339 timestamp and require timezone information."""
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def load_event_schema(path: Path) -> dict[str, Any]:
    """Load the canonical event-envelope JSON schema from disk."""
    if not path.exists():
        raise ProtocolValidationError(f"event schema not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_topics(path: Path) -> set[str]:
    """Load the protocol topic allow-list from a YAML-style file."""
    if not path.exists():
        raise ProtocolValidationError(f"topics file not found: {path}")
    topics: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("- "):
            topics.add(line[2:].strip())
    if not topics:
        raise ProtocolValidationError("no topics configured")
    return topics


def validate_envelope(
    envelope: dict[str, Any],
    *,
    schema: dict[str, Any],
    topics: set[str],
    payload_ref_pattern: Pattern[str] | None = None,
) -> None:
    """Validate an event envelope against the canonical JSON Schema.

    Structural validation (required fields, additionalProperties, types, the
    ``payload_ref`` ``registry://`` pattern, the ``priority`` enum, and the
    ``date-time`` timestamp format) is delegated to ``jsonschema`` so that
    ``schemas/event.envelope.schema.json`` is the single source of truth. The
    only check kept here is the topic-catalog membership, which lives in an
    external YAML file (``protocol/topics.yaml``) rather than the schema.

    ``payload_ref_pattern`` is accepted for backwards compatibility but is no
    longer used — the pattern is enforced by the schema itself.
    """
    _ = payload_ref_pattern
    # FormatChecker activates the "date-time" and "pattern" assertions in the
    # schema (jsonschema treats "format" as advisory unless a checker is given).
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    try:
        validator.validate(envelope)
    except JSONSchemaValidationError as exc:
        raise ProtocolValidationError(_format_schema_error(exc)) from exc
    # jsonschema's "date-time" format check only enforces a full RFC 3339 string
    # when the optional rfc3339-validator package is installed; enforce the
    # timezone-required invariant explicitly so it holds without that dependency.
    if "timestamp" in envelope:
        try:
            parse_date_time(str(envelope["timestamp"]))
        except Exception as exc:
            raise ProtocolValidationError(f"invalid timestamp: {exc}") from exc
    if envelope.get("topic") not in topics:
        raise ProtocolValidationError("unknown topic")


def _format_schema_error(exc: JSONSchemaValidationError) -> str:
    location = ".".join(str(part) for part in exc.absolute_path)
    if location:
        return f"envelope field '{location}' invalid: {exc.message}"
    return f"envelope invalid: {exc.message}"


# ---------------------------------------------------------------------------
# Distributed replay detection via Redis SET NX EX.
#
# Replay detection MUST be shared across all Protocol Bus instances: a
# per-process guard lets a replayed event slip through whenever the original
# and the replay are routed to different instances. The Redis ``SET key NX EX``
# primitive records the correlation_id atomically across every instance — the
# first writer wins, every subsequent writer (within TTL) is a detected replay.
# ---------------------------------------------------------------------------

REPLAY_KEY_PREFIX = "replay:"


async def check_replay(
    correlation_id: str,
    redis_client: Any,
    *,
    ttl_seconds: int = 300,
) -> None:
    """Record *correlation_id* in Redis and raise on a replay.

    Uses ``SET key NX EX`` so detection is shared across every Protocol Bus
    instance. The first call within the TTL window writes the key and returns
    normally; any subsequent call sees the existing key and raises
    ``ReplayDetectedError``.

    2026 best practice: a 5-minute TTL covers typical distributed clock skew.
    """
    key = f"{REPLAY_KEY_PREFIX}{correlation_id}"
    result = await redis_client.set(key, "1", nx=True, ex=ttl_seconds)
    if result is None:  # key already existed → replay
        LOGGER.warning("replay detected for correlation_id=%s", correlation_id)
        raise ReplayDetectedError(f"duplicate correlation_id: {correlation_id}")


async def reset_replay_guard(redis_client: Any) -> None:
    """Clear all recorded replay keys. Intended for test isolation.

    Removes every key under the ``replay:`` prefix from *redis_client*.
    """
    cursor = 0
    pattern = f"{REPLAY_KEY_PREFIX}*"
    while True:
        cursor, keys = await redis_client.scan(cursor=cursor, match=pattern, count=500)
        if keys:
            await redis_client.delete(*keys)
        if cursor == 0:
            break
