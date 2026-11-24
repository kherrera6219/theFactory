"""Shared rules for which missions are internal and which need operator attention.

Mission Control used to count missions page by page, and they disagreed:

- the two Knowledge Lake bootstrap rows (``storage_core`` creates them so
  knowledge documents have a parent mission) were counted as real missions;
- a mission whose completion gate refused it stays in ``VERIFIED`` with
  ``last_chain_event_type == MISSION_COMPLETION_BLOCKED``. Every count treated
  it as healthy or "active", synthesized agents showed work for it, and the
  only signal was an alert that did not say which mission.

These helpers are the single definition the operations routes and the
heartbeat synthesizer use. The UI mirrors them in ``app/lib/mission-status.ts``.
"""

from __future__ import annotations

from typing import Any

SYSTEM_MISSION_IDS: frozenset[str] = frozenset({"__knowledge_lake__", "system-knowledge-lake"})
COMPLETION_BLOCKED_EVENT = "MISSION_COMPLETION_BLOCKED"
_TERMINAL_STATES = frozenset({"COMPLETE", "FAILED"})


def is_system_mission(mission_id: str | None) -> bool:
    """True for the internal Knowledge Lake bootstrap missions."""
    return str(mission_id or "") in SYSTEM_MISSION_IDS


def _state_value(state: Any) -> str:
    return str(getattr(state, "value", state) or "").upper()


def is_completion_blocked(state: Any, metadata: Any) -> bool:
    """True when a non-terminal mission's last chain event is a completion block."""
    if _state_value(state) in _TERMINAL_STATES:
        return False
    if not isinstance(metadata, dict):
        return False
    return str(metadata.get("last_chain_event_type") or "") == COMPLETION_BLOCKED_EVENT


def mission_is_blocked(mission: Any) -> bool:
    """``is_completion_blocked`` for a ``MissionRecord``-like object."""
    return is_completion_blocked(getattr(mission, "state", None), getattr(mission, "metadata", None))
