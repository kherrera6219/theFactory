from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from shared_runtime.protocol import ProtocolValidationError as _SharedProtocolValidationError
from shared_runtime.protocol import parse_date_time as _shared_parse_date_time
from shared_runtime.protocol import to_event_priority as _to_event_priority
from shared_runtime.protocol import validate_envelope as _shared_validate_envelope

from .models import MissionRecord
from .settings import Settings

PAYLOAD_REF_PATTERN = re.compile(r"^registry://")


# Re-exported so existing callers/tests can catch the orchestrator-local name while
# the shared jsonschema validator raises the canonical shared error type.
ProtocolValidationError = _SharedProtocolValidationError

# Re-exported so orchestrator modules normalise priority through one import path.
to_event_priority = _to_event_priority


def _parse_date_time(value: str) -> datetime:
    return _shared_parse_date_time(value)


@dataclass
class EnvelopeValidator:
    settings: Settings
    schema: dict[str, Any]
    topics: set[str]

    @classmethod
    def load(cls, settings: Settings) -> "EnvelopeValidator":
        if not settings.event_schema_path.exists():
            raise ProtocolValidationError(f"event schema not found: {settings.event_schema_path}")
        if not settings.topics_path.exists():
            raise ProtocolValidationError(f"topics file not found: {settings.topics_path}")

        schema = json.loads(settings.event_schema_path.read_text(encoding="utf-8"))

        topics: set[str] = set()
        for raw_line in settings.topics_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("- "):
                topics.add(line[2:].strip())

        if not topics:
            raise ProtocolValidationError("no topics configured")

        return cls(settings=settings, schema=schema, topics=topics)

    def validate(self, envelope: dict[str, Any]) -> None:
        _shared_validate_envelope(
            envelope,
            schema=self.schema,
            topics=self.topics,
            payload_ref_pattern=PAYLOAD_REF_PATTERN,
        )

    def build_state_envelope(self, mission: MissionRecord, event_type: str) -> dict[str, Any]:
        topic = self.settings.topic_for_state(mission.state.value)
        # DEFAULT_EVENT_PRIORITY is operator-settable and was previously written
        # through unvalidated: setting it to a lowercase bus value ("normal")
        # made every state envelope fail schema validation. Normalising here
        # accepts either vocabulary and is a no-op for NORMAL/HIGH (UPG-22).
        priority = (
            "HIGH"
            if mission.state.value == "FAILED"
            else _to_event_priority(self.settings.default_priority)
        )

        envelope = {
            "event_id": f"evt-{uuid.uuid4()}",
            "topic": topic,
            "timestamp": datetime.now(UTC).isoformat(),
            "producer": self.settings.producer_name,
            "correlation_id": mission.mission_id,
            "payload_ref": f"registry://missions/{mission.mission_id}/state/{mission.state.value.lower()}",
            "schema": "missions.state.v1",
            "priority": priority,
        }
        self.validate(envelope)
        return envelope

    def parse_intake_envelope(
        self, raw_fields: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any]:
        envelope_raw = raw_fields.get("envelope")
        if envelope_raw:
            envelope = json.loads(envelope_raw)
        else:
            mission_id = str(payload.get("mission_id", ""))
            if not mission_id:
                raise ProtocolValidationError("payload missing mission_id")
            created_at = str(payload.get("created_at") or datetime.now(UTC).isoformat())
            envelope = {
                "event_id": f"evt-{uuid.uuid4()}",
                "topic": self.settings.intake_topic,
                "timestamp": created_at,
                "producer": raw_fields.get("producer", "api-gateway"),
                "correlation_id": mission_id,
                "payload_ref": raw_fields.get(
                    "payload_ref", f"registry://missions/{mission_id}/intake"
                ),
                "schema": raw_fields.get("schema", "missions.intake.v1"),
                # Normalised for the same reason as build_state_envelope: the
                # raw field arrives from another service and may carry either
                # vocabulary (UPG-22).
                "priority": _to_event_priority(
                    raw_fields.get("priority") or self.settings.default_priority
                ),
            }

        self.validate(envelope)
        return envelope
