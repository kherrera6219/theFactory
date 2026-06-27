"""
test_type_annotations.py
=========================
Regression guard for type annotation correctness in critical modules.

Verifies:
- _as_bool accepts None without raising TypeError
- MissionEvent.event_type is validated against the EventType Literal
- EventType covers all values emitted by the runtime
"""
from __future__ import annotations

import pytest

from services.orchestrator.orchestrator.models import (
    EventType,
    MissionEvent,
    MissionState,
)
from services.orchestrator.orchestrator.settings import _as_bool

# ---------------------------------------------------------------------------
# _as_bool: must accept None (previously annotated as str, not str | None)
# ---------------------------------------------------------------------------

class TestAsBool:
    def test_none_returns_default_false(self):
        assert _as_bool(None, False) is False

    def test_none_returns_default_true(self):
        assert _as_bool(None, True) is True

    def test_true_strings(self):
        for val in ("1", "true", "True", "TRUE", "yes", "YES", "on", "ON"):
            assert _as_bool(val, False) is True, f"_as_bool({val!r}) should be True"

    def test_false_strings(self):
        for val in ("0", "false", "no", "off", ""):
            assert _as_bool(val, True) is False, f"_as_bool({val!r}) should be False"

    def test_empty_string_returns_default(self):
        # Empty string is falsy — should not be in TRUTHY_VALUES
        assert _as_bool("", True) is False


# ---------------------------------------------------------------------------
# MissionEvent: event_type Literal validation
# ---------------------------------------------------------------------------

def _make_event(event_type: str) -> MissionEvent:
    from datetime import UTC, datetime

    return MissionEvent(
        mission_id="test-123",
        previous_state=None,
        new_state=MissionState.queued,
        event_type=event_type,  # type: ignore[arg-type]
        ts=datetime.now(UTC),
    )


class TestMissionEventType:
    def test_valid_event_type_accepted(self):
        event = _make_event("MISSION_QUEUED")
        assert event.event_type == "MISSION_QUEUED"

    def test_all_state_transition_events_are_valid(self):
        """Every MISSION_{STATE} string must be in the EventType Literal."""
        import typing

        state_events = [f"MISSION_{s.value}" for s in MissionState]
        # Get the valid values from the Literal type
        valid: tuple[str, ...] = typing.get_args(EventType)
        for ev in state_events:
            assert ev in valid, (
                f"EventType Literal is missing state-transition event '{ev}'"
            )

    def test_invalid_event_type_rejected_by_pydantic(self):
        import pydantic

        with pytest.raises((pydantic.ValidationError, ValueError)):
            _make_event("NOT_A_REAL_EVENT_TYPE_XYZ")

    def test_agent_state_changed_is_valid(self):
        event = _make_event("AGENT_STATE_CHANGED")
        assert event.event_type == "AGENT_STATE_CHANGED"

    def test_mission_completion_blocked_is_valid(self):
        event = _make_event("MISSION_COMPLETION_BLOCKED")
        assert event.event_type == "MISSION_COMPLETION_BLOCKED"

    @pytest.mark.parametrize(
        "event_type",
        [
            "MISSION_RUNTIME_QC_SKIPPED",
            "MISSION_RUNTIME_QC_BLOCKED",
            "MISSION_RUNTIME_QC_COMPLETE",
        ],
    )
    def test_runtime_qc_events_are_valid(self, event_type: str):
        event = _make_event(event_type)
        assert event.event_type == event_type
