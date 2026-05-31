"""Contract tests keeping the Pydantic envelope models and the canonical
``schemas/event.envelope.schema.json`` in sync.

The JSON Schema is the single source of truth (issue #189). These tests assert:

1. The ``EventEnvelope`` Pydantic model declares exactly the fields the schema
   requires — if a field is added to the schema or the model without updating
   the other, the field-set comparison fails.
2. A valid ``EventEnvelope`` built for every one of the six protocol types
   serializes to a dict that passes ``jsonschema.validate`` against the schema.
3. The shared ``validate_envelope`` helper (used by the orchestrator and
   api-gateway) rejects a payload that is missing a required field, proving the
   hand-rolled checks were genuinely replaced by the schema validator.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as JSONSchemaValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "semantic-bus-mcp"))

from semantic_bus.mcp_server import EventEnvelope, _validate_protocol_payload  # noqa: E402

from shared_runtime.protocol import ProtocolValidationError, validate_envelope  # noqa: E402

SCHEMA_PATH = ROOT / "schemas" / "event.envelope.schema.json"
PAYLOAD_REF_PATTERN = re.compile(r"^registry://")

PROTOCOL_PAYLOADS: dict[str, dict[str, object]] = {
    "alpha": {
        "schema_version": "v1",
        "priority": "high",
        "target_pod": "podA",
        "directive_type": "mission_assignment",
        "directive": {"mission_id": "mission-1"},
    },
    "beta": {
        "schema_version": "v1",
        "logicnode_id": "node-1",
        "confidence_score": 0.9,
        "source_language": "python",
        "payload": {},
    },
    "delta": {
        "schema_version": "v1",
        "audit_result": "pass",
        "verification_method": "static-analysis",
        "tolerance_score": 0.95,
        "findings": {},
    },
    "sigma": {
        "schema_version": "v1",
        "knowledge_type": "pattern",
        "embedding_ref": "registry://embeddings/e-1",
        "relevance_scope": "global",
        "content": {},
    },
    "omega": {
        "schema_version": "v1",
        "feature_contract": {},
        "visual_blueprint": {},
        "user_intent": "build a dashboard",
        "attachments": [],
    },
    "rho": {
        "schema_version": "v1",
        "token_budget": 1000,
        "rate_limit_action": "throttle",
        "agent_target": "AGENT-14-PYTHON",
        "metadata": {},
    },
}


@pytest.fixture(scope="module")
def schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def topics() -> set[str]:
    # The schema's "topic" field is a free string; the topic catalog is enforced
    # separately. Use the protocol-derived topic so validate_envelope passes.
    return {f"protocol.{name}.event" for name in PROTOCOL_PAYLOADS}


def _envelope_for(protocol: str) -> EventEnvelope:
    return EventEnvelope.model_validate(
        {
            "event_id": f"evt-{protocol}",
            "topic": f"protocol.{protocol}.event",
            "timestamp": "2026-03-01T00:00:00+00:00",
            "producer": "semantic-bus-mcp",
            "correlation_id": f"corr-{protocol}",
            "payload_ref": f"registry://protocol/{protocol}/payload",
            "schema": f"protocol.{protocol}.v1",
            "priority": "NORMAL",
        }
    )


def test_event_envelope_model_matches_schema_required_fields(schema) -> None:
    schema_required = set(schema["required"])
    # model_fields keys use the alias ("schema") via the populate_by alias config.
    model_fields = {
        info.alias or name for name, info in EventEnvelope.model_fields.items()
    }
    assert schema_required <= model_fields, (
        "EventEnvelope is missing required schema fields: "
        f"{schema_required - model_fields}"
    )
    schema_properties = set(schema["properties"])
    assert model_fields == schema_properties, (
        "EventEnvelope fields and schema properties have drifted: "
        f"model-only={model_fields - schema_properties}, "
        f"schema-only={schema_properties - model_fields}"
    )


@pytest.mark.parametrize("protocol", sorted(PROTOCOL_PAYLOADS))
def test_pydantic_envelope_validates_against_json_schema(protocol, schema) -> None:
    # The per-protocol payload model must accept the fixture payload.
    _validate_protocol_payload(protocol, PROTOCOL_PAYLOADS[protocol])

    envelope = _envelope_for(protocol)
    as_dict = envelope.model_dump(mode="json", by_alias=True)

    # Authoritative check: serialized Pydantic output passes the JSON Schema.
    Draft202012Validator(
        schema, format_checker=Draft202012Validator.FORMAT_CHECKER
    ).validate(as_dict)


@pytest.mark.parametrize("protocol", sorted(PROTOCOL_PAYLOADS))
def test_shared_validate_envelope_accepts_model_output(protocol, schema, topics) -> None:
    envelope = _envelope_for(protocol).model_dump(mode="json", by_alias=True)
    validate_envelope(
        envelope,
        schema=schema,
        topics=topics,
        payload_ref_pattern=PAYLOAD_REF_PATTERN,
    )


def test_shared_validate_envelope_rejects_missing_required_field(schema, topics) -> None:
    envelope = _envelope_for("alpha").model_dump(mode="json", by_alias=True)
    del envelope["correlation_id"]
    with pytest.raises(ProtocolValidationError):
        validate_envelope(
            envelope,
            schema=schema,
            topics=topics,
            payload_ref_pattern=PAYLOAD_REF_PATTERN,
        )


def test_json_schema_rejects_bad_payload_ref(schema) -> None:
    envelope = _envelope_for("beta").model_dump(mode="json", by_alias=True)
    envelope["payload_ref"] = "http://not-a-registry-ref"
    with pytest.raises(JSONSchemaValidationError):
        Draft202012Validator(schema).validate(envelope)
