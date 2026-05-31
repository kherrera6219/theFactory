from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from re import Pattern
from typing import Any

LOGGER = logging.getLogger(__name__)


class ProtocolValidationError(Exception):
    pass


class ReplayDetectedError(ProtocolValidationError):
    """Raised when an event_id has already been processed (replay attack detected)."""


def parse_date_time(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def load_event_schema(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ProtocolValidationError(f"event schema not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_topics(path: Path) -> set[str]:
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
    payload_ref_pattern: Pattern[str],
) -> None:
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    missing = [field for field in required if field not in envelope]
    if missing:
        raise ProtocolValidationError(f"missing fields: {', '.join(missing)}")
    if schema.get("additionalProperties") is False:
        unknown = [field for field in envelope if field not in properties]
        if unknown:
            raise ProtocolValidationError(f"unexpected fields: {', '.join(unknown)}")
    if envelope.get("topic") not in topics:
        raise ProtocolValidationError("unknown topic")
    if not payload_ref_pattern.match(str(envelope.get("payload_ref", ""))):
        raise ProtocolValidationError("invalid payload_ref")
    allowed_priorities = set(properties.get("priority", {}).get("enum", ["NORMAL", "HIGH"]))
    if envelope.get("priority") not in allowed_priorities:
        raise ProtocolValidationError(
            f"priority must be one of: {', '.join(sorted(allowed_priorities))}"
        )
    try:
        parse_date_time(str(envelope["timestamp"]))
    except Exception as exc:
        raise ProtocolValidationError(f"invalid timestamp: {exc}") from exc
    for field, spec in properties.items():
        expected_type = spec.get("type")
        if field in envelope and expected_type == "string" and not isinstance(envelope[field], str):
            raise ProtocolValidationError(f"field '{field}' must be string")


# ---------------------------------------------------------------------------
# In-process replay detection (single-node, no Redis dependency)
# For distributed replay detection, use RedisReplayGuard in your service.
# ---------------------------------------------------------------------------

class _InProcessReplayGuard:
    """Simple TTL-based in-process replay guard.

    Suitable for single-process use. For multi-instance deployments, pair
    this with a Redis SET NX EX guard (RedisReplayGuard pattern).
    """

    def __init__(self, max_entries: int = 100_000) -> None:
        self._seen: dict[str, float] = {}
        self._max_entries = max_entries

    def reset(self) -> None:
        """Clear all recorded event_ids. Intended for test isolation."""
        self._seen.clear()

    def check_and_record(self, event_id: str, *, ttl_seconds: float = 300.0) -> None:
        """Raise ReplayDetectedError if *event_id* was recently seen.

        2026 best practice: 5-minute TTL covers typical distributed clock skew.
        """
        import time
        now = time.monotonic()
        # Evict expired entries (lazy cleanup)
        if len(self._seen) >= self._max_entries:
            expired = [k for k, ts in self._seen.items() if now - ts > ttl_seconds]
            for k in expired:
                del self._seen[k]

        if event_id in self._seen:
            age = now - self._seen[event_id]
            if age < ttl_seconds:
                LOGGER.warning("replay detected for event_id=%s (age=%.1fs)", event_id, age)
                raise ReplayDetectedError(f"duplicate event_id: {event_id}")

        self._seen[event_id] = now


# Module-level singleton for convenience (process-local)
_DEFAULT_REPLAY_GUARD = _InProcessReplayGuard()


def check_replay(event_id: str, *, ttl_seconds: float = 300.0) -> None:
    """Check *event_id* against the module-level replay guard.

    Raises ReplayDetectedError if the event was already seen within TTL.
    """
    _DEFAULT_REPLAY_GUARD.check_and_record(event_id, ttl_seconds=ttl_seconds)


def reset_replay_guard() -> None:
    """Reset the module-level replay guard. Intended for test isolation."""
    _DEFAULT_REPLAY_GUARD.reset()
