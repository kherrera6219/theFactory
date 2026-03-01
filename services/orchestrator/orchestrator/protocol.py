from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .models import MissionRecord
from .settings import Settings

PAYLOAD_REF_PATTERN = re.compile(r"^registry://")


class ProtocolValidationError(Exception):
    pass


def _parse_date_time(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


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
        required = self.schema.get("required", [])
        properties = self.schema.get("properties", {})

        missing = [field for field in required if field not in envelope]
        if missing:
            raise ProtocolValidationError(f"envelope missing required fields: {', '.join(missing)}")

        if self.schema.get("additionalProperties") is False:
            unknown = [field for field in envelope if field not in properties]
            if unknown:
                raise ProtocolValidationError(f"unexpected envelope fields: {', '.join(unknown)}")

        topic = str(envelope.get("topic", ""))
        if topic not in self.topics:
            raise ProtocolValidationError(f"topic '{topic}' is not in protocol catalog")

        payload_ref = str(envelope.get("payload_ref", ""))
        if not PAYLOAD_REF_PATTERN.match(payload_ref):
            raise ProtocolValidationError("payload_ref must start with registry://")

        priority = envelope.get("priority")
        allowed = set(properties.get("priority", {}).get("enum", ["NORMAL", "HIGH"]))
        if priority not in allowed:
            raise ProtocolValidationError(f"priority must be one of: {', '.join(sorted(allowed))}")

        try:
            _parse_date_time(str(envelope["timestamp"]))
        except Exception as exc:
            raise ProtocolValidationError(f"invalid timestamp: {exc}") from exc

        for field, spec in properties.items():
            expected_type = spec.get("type")
            if (
                field in envelope
                and expected_type == "string"
                and not isinstance(envelope[field], str)
            ):
                raise ProtocolValidationError(f"field '{field}' must be string")

    def build_state_envelope(self, mission: MissionRecord, event_type: str) -> dict[str, Any]:
        topic = self.settings.topic_for_state(mission.state.value)
        priority = "HIGH" if mission.state.value == "FAILED" else self.settings.default_priority

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
                "priority": raw_fields.get("priority", self.settings.default_priority),
            }

        self.validate(envelope)
        return envelope
