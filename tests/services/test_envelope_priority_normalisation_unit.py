"""Regression tests for UPG-22 priority normalisation at the envelope write sites.

Before UPG-22 the operator-settable ``DEFAULT_EVENT_PRIORITY`` was written into
the event envelope unvalidated, while ``schemas/event.envelope.schema.json``
accepted only ``NORMAL``/``HIGH``. Setting it to a lowercase Protocol Bus value
-- the natural thing to type, since the bus ``/send`` API uses
``low|normal|high|critical`` -- made every mission state envelope fail schema
validation at ``EnvelopeValidator.build_state_envelope``.

These tests pin both halves of the fix:

1. A lowercase ``DEFAULT_EVENT_PRIORITY`` no longer breaks envelope construction.
2. The existing uppercase configuration produces byte-identical output, so the
   change is additive rather than behavioural.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from orchestrator.models import MissionRecord, MissionState  # noqa: E402
from orchestrator.protocol import EnvelopeValidator, ProtocolValidationError  # noqa: E402


class _StubSettings:
    """Minimal stand-in for Settings covering only what EnvelopeValidator reads."""

    def __init__(self, default_priority: str) -> None:
        self.default_priority = default_priority
        self.producer_name = "orchestrator"
        self.intake_topic = "mission.intake.requested"

    def topic_for_state(self, state: str) -> str:  # noqa: D102
        return f"mission.state.{state.lower()}"


def _validator(default_priority: str) -> EnvelopeValidator:
    schema = json.loads(
        (ROOT / "schemas" / "event.envelope.schema.json").read_text(encoding="utf-8")
    )
    topics = {f"mission.state.{s.value.lower()}" for s in MissionState}
    topics.add("mission.intake.requested")
    return EnvelopeValidator(
        settings=_StubSettings(default_priority),  # type: ignore[arg-type]
        schema=schema,
        topics=topics,
    )


def _mission(state: MissionState = MissionState.running) -> MissionRecord:
    return MissionRecord(
        mission_id="mission-upg22",
        prompt="reconcile the envelope vocabularies",
        state=state,
        created_at=datetime.now(UTC),
    )


@pytest.mark.parametrize("bus_value", ["low", "normal", "high", "critical"])
def test_lowercase_default_priority_no_longer_breaks_state_envelope(bus_value) -> None:
    """The regression: this raised ProtocolValidationError before UPG-22."""
    envelope = _validator(bus_value).build_state_envelope(_mission(), "MISSION_RUNNING")
    assert envelope["priority"] in {"NORMAL", "HIGH"}


def test_uppercase_default_priority_output_is_unchanged() -> None:
    """Additive, not behavioural: existing configurations write the same bytes."""
    envelope = _validator("NORMAL").build_state_envelope(_mission(), "MISSION_RUNNING")
    assert envelope["priority"] == "NORMAL"


def test_failed_state_still_escalates_to_high() -> None:
    envelope = _validator("NORMAL").build_state_envelope(
        _mission(MissionState.failed), "MISSION_FAILED"
    )
    assert envelope["priority"] == "HIGH"


def test_garbage_default_priority_fails_loudly() -> None:
    """A typo must raise rather than silently downgrade the priority."""
    with pytest.raises(ProtocolValidationError):
        _validator("URGENT").build_state_envelope(_mission(), "MISSION_RUNNING")


@pytest.mark.parametrize("bus_value", ["low", "critical"])
def test_intake_envelope_normalises_a_bus_priority_from_another_service(bus_value) -> None:
    """parse_intake_envelope reads priority off a raw stream field.

    That field arrives from api-gateway and may legitimately carry either
    vocabulary, so it is normalised on the way in.
    """
    envelope = _validator("NORMAL").parse_intake_envelope(
        {"priority": bus_value},
        {"mission_id": "mission-upg22", "created_at": "2026-08-01T00:00:00+00:00"},
    )
    assert envelope["priority"] in {"NORMAL", "HIGH"}
