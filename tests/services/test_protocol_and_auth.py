import asyncio
import importlib
import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api-gateway"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

api_gateway_main = importlib.import_module("api_gateway.main")
orchestrator_auth = importlib.import_module("orchestrator.auth")
orchestrator_models = importlib.import_module("orchestrator.models")
orchestrator_protocol = importlib.import_module("orchestrator.protocol")
orchestrator_settings = importlib.import_module("orchestrator.settings")

GatewayProtocolValidationError = api_gateway_main.ProtocolValidationError
validate_gateway_envelope = api_gateway_main._validate_envelope
require_roles = orchestrator_auth.require_roles
MissionRecord = orchestrator_models.MissionRecord
MissionState = orchestrator_models.MissionState
EnvelopeValidator = orchestrator_protocol.EnvelopeValidator
OrchestratorProtocolError = orchestrator_protocol.ProtocolValidationError
Settings = orchestrator_settings.Settings


def _repo_root() -> Path:
    return ROOT


def _make_settings() -> Settings:
    root = _repo_root()
    return Settings(
        redis_url="redis://redis:6379/0",
        postgres_url="postgresql://postgres:postgres@postgres:5432/ulr",
        intake_stream="missions.intake",
        state_stream="missions.state",
        max_stream_len=1000,
        consumer_group="orchestrator",
        consumer_name="orchestrator-test",
        auto_transition_enabled=True,
        transition_step_seconds=1.0,
        intake_topic="intake.feature_contract.created",
        default_priority="NORMAL",
        producer_name="orchestrator",
        event_schema_path=root / "schemas" / "event.envelope.schema.json",
        topics_path=root / "protocol" / "topics.yaml",
        admin_api_key="admin-key",
        internal_service_api_key="worker-key",
        readonly_api_key="viewer-key",
        extra_api_keys="operator-key=mutate,read",
    )


def _with_settings_overrides(**overrides) -> Settings:
    base = _make_settings()
    return Settings(**{**base.__dict__, **overrides})


def test_gateway_envelope_validation_accepts_valid_contract() -> None:
    envelope = {
        "event_id": "evt-123",
        "topic": "intake.feature_contract.created",
        "timestamp": "2026-02-28T00:00:00+00:00",
        "producer": "api-gateway",
        "correlation_id": "mission-123",
        "payload_ref": "registry://missions/mission-123/intake",
        "schema": "missions.intake.v1",
        "priority": "NORMAL",
    }
    validate_gateway_envelope(envelope)


def test_gateway_envelope_validation_rejects_invalid_priority() -> None:
    envelope = {
        "event_id": "evt-123",
        "topic": "intake.feature_contract.created",
        "timestamp": "2026-02-28T00:00:00+00:00",
        "producer": "api-gateway",
        "correlation_id": "mission-123",
        "payload_ref": "registry://missions/mission-123/intake",
        "schema": "missions.intake.v1",
        "priority": "LOW",
    }
    with pytest.raises(GatewayProtocolValidationError):
        validate_gateway_envelope(envelope)


def test_orchestrator_envelope_builder_uses_allowed_topic() -> None:
    validator = EnvelopeValidator.load(_make_settings())
    mission = MissionRecord(
        mission_id="mission-1",
        prompt="Generate API",
        requested_target_language="python",
        metadata={},
        state=MissionState.running,
        created_at="2026-02-28T00:00:00+00:00",
    )
    envelope = validator.build_state_envelope(mission, "MISSION_RUNNING")
    assert envelope["topic"] == "fusion.requested"


def test_orchestrator_envelope_validator_rejects_unknown_topic() -> None:
    validator = EnvelopeValidator.load(_make_settings())
    envelope = {
        "event_id": "evt-1",
        "topic": "not.in.catalog",
        "timestamp": "2026-02-28T00:00:00+00:00",
        "producer": "test",
        "correlation_id": "mission-1",
        "payload_ref": "registry://missions/mission-1",
        "schema": "test.v1",
        "priority": "NORMAL",
    }
    with pytest.raises(OrchestratorProtocolError):
        validator.validate(envelope)


def test_auth_dependency_allows_mutate_role() -> None:
    settings = _make_settings()
    dependency = require_roles(settings, {"mutate"})
    context = asyncio.run(dependency(x_api_key="operator-key"))
    assert "mutate" in context.roles


def test_settings_api_key_roles_include_agent_service_keys(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_14_PYTHON_SERVICE_API_KEY", "python-agent-key")
    settings = _make_settings()
    assert settings.api_key_roles["python-agent-key"] == {"worker", "mutate", "internal", "read"}


def test_auth_dependency_blocks_readonly_for_mutate() -> None:
    settings = _make_settings()
    dependency = require_roles(settings, {"mutate"})
    with pytest.raises(HTTPException):
        asyncio.run(dependency(x_api_key="viewer-key"))


def test_parse_datetime_handles_z_and_requires_timezone() -> None:
    parsed = orchestrator_protocol._parse_date_time("2026-03-01T00:00:00Z")
    assert parsed.tzinfo is not None

    with pytest.raises(ValueError):
        orchestrator_protocol._parse_date_time("2026-03-01T00:00:00")


def test_orchestrator_envelope_load_missing_files(tmp_path: Path) -> None:
    missing_schema = _with_settings_overrides(event_schema_path=tmp_path / "missing-schema.json")
    with pytest.raises(OrchestratorProtocolError):
        EnvelopeValidator.load(missing_schema)

    missing_topics = _with_settings_overrides(topics_path=tmp_path / "missing-topics.yaml")
    with pytest.raises(OrchestratorProtocolError):
        EnvelopeValidator.load(missing_topics)


def test_orchestrator_envelope_load_rejects_empty_topics(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    topics_path = tmp_path / "topics.yaml"
    schema_path.write_text(
        json.dumps(
            {
                "required": ["event_id", "topic", "timestamp", "producer", "correlation_id"],
                "properties": {
                    "event_id": {"type": "string"},
                    "topic": {"type": "string"},
                    "timestamp": {"type": "string"},
                    "producer": {"type": "string"},
                    "correlation_id": {"type": "string"},
                    "payload_ref": {"type": "string"},
                    "schema": {"type": "string"},
                    "priority": {"type": "string", "enum": ["NORMAL", "HIGH"]},
                },
                "additionalProperties": False,
            }
        ),
        encoding="utf-8",
    )
    topics_path.write_text("topics:\n  none: true\n", encoding="utf-8")

    with pytest.raises(OrchestratorProtocolError):
        EnvelopeValidator.load(
            _with_settings_overrides(event_schema_path=schema_path, topics_path=topics_path)
        )


def test_parse_intake_envelope_paths() -> None:
    validator = EnvelopeValidator.load(_make_settings())

    built = validator.parse_intake_envelope({}, {"mission_id": "mission-1"})
    assert built["correlation_id"] == "mission-1"
    assert built["topic"] == validator.settings.intake_topic
    assert built["payload_ref"] == "registry://missions/mission-1/intake"

    embedded = {
        "event_id": "evt-embedded",
        "topic": validator.settings.intake_topic,
        "timestamp": "2026-03-01T00:00:00+00:00",
        "producer": "api-gateway",
        "correlation_id": "mission-2",
        "payload_ref": "registry://missions/mission-2/intake",
        "schema": "missions.intake.v1",
        "priority": "NORMAL",
    }
    parsed = validator.parse_intake_envelope({"envelope": json.dumps(embedded)}, {})
    assert parsed == embedded

    with pytest.raises(OrchestratorProtocolError):
        validator.parse_intake_envelope({}, {})


def test_orchestrator_envelope_validator_failure_branches() -> None:
    validator = EnvelopeValidator.load(_make_settings())
    envelope = {
        "event_id": "evt-1",
        "topic": "intake.feature_contract.created",
        "timestamp": "2026-03-01T00:00:00+00:00",
        "producer": "api-gateway",
        "correlation_id": "mission-1",
        "payload_ref": "registry://missions/mission-1/intake",
        "schema": "missions.intake.v1",
        "priority": "NORMAL",
    }

    missing_required = dict(envelope)
    del missing_required["producer"]
    with pytest.raises(OrchestratorProtocolError):
        validator.validate(missing_required)

    unexpected = dict(envelope)
    unexpected["extra_field"] = "boom"
    with pytest.raises(OrchestratorProtocolError):
        validator.validate(unexpected)

    bad_payload_ref = dict(envelope)
    bad_payload_ref["payload_ref"] = "http://bad"
    with pytest.raises(OrchestratorProtocolError):
        validator.validate(bad_payload_ref)

    bad_priority = dict(envelope)
    bad_priority["priority"] = "LOW"
    with pytest.raises(OrchestratorProtocolError):
        validator.validate(bad_priority)

    bad_timestamp = dict(envelope)
    bad_timestamp["timestamp"] = "2026-03-01T00:00:00"
    with pytest.raises(OrchestratorProtocolError):
        validator.validate(bad_timestamp)


def test_orchestrator_envelope_validator_allows_unknown_when_schema_allows(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    topics_path = tmp_path / "topics.yaml"
    schema_path.write_text(
        json.dumps(
            {
                "required": [
                    "event_id",
                    "topic",
                    "timestamp",
                    "producer",
                    "correlation_id",
                    "payload_ref",
                    "schema",
                    "priority",
                ],
                "properties": {
                    "event_id": {"type": "string"},
                    "topic": {"type": "string"},
                    "timestamp": {"type": "string"},
                    "producer": {"type": "string"},
                    "correlation_id": {"type": "string"},
                    "payload_ref": {"type": "string"},
                    "schema": {"type": "string"},
                    "priority": {"type": "string", "enum": ["NORMAL", "HIGH"]},
                },
                "additionalProperties": True,
            }
        ),
        encoding="utf-8",
    )
    topics_path.write_text("- intake.feature_contract.created\n", encoding="utf-8")
    validator = EnvelopeValidator.load(
        _with_settings_overrides(event_schema_path=schema_path, topics_path=topics_path)
    )
    envelope = {
        "event_id": "evt-1",
        "topic": "intake.feature_contract.created",
        "timestamp": "2026-03-01T00:00:00+00:00",
        "producer": "api-gateway",
        "correlation_id": "mission-1",
        "payload_ref": "registry://missions/mission-1/intake",
        "schema": "missions.intake.v1",
        "priority": "NORMAL",
        "extra_field": "allowed",
    }
    validator.validate(envelope)


def test_orchestrator_envelope_validator_rejects_non_string_field() -> None:
    validator = EnvelopeValidator.load(_make_settings())
    envelope = {
        "event_id": 123,
        "topic": "intake.feature_contract.created",
        "timestamp": "2026-03-01T00:00:00+00:00",
        "producer": "api-gateway",
        "correlation_id": "mission-1",
        "payload_ref": "registry://missions/mission-1/intake",
        "schema": "missions.intake.v1",
        "priority": "NORMAL",
    }
    with pytest.raises(OrchestratorProtocolError):
        validator.validate(envelope)


def test_settings_roles_and_state_topics(monkeypatch) -> None:
    settings = _with_settings_overrides(
        admin_api_key="",
        internal_service_api_key="",
        readonly_api_key="",
        extra_api_keys="invalid;operator-key=mutate,read;blank-key=;",
    )
    assert settings.api_key_roles == {"operator-key": {"mutate", "read"}}

    monkeypatch.setenv("STATE_TOPIC_RUNNING", "topic.running")
    monkeypatch.setenv("STATE_TOPIC_VERIFIED", "topic.verified")
    monkeypatch.setenv("STATE_TOPIC_COMPLETE", "topic.complete")
    monkeypatch.setenv("STATE_TOPIC_FAILED", "topic.failed")
    monkeypatch.setenv("STATE_TOPIC_QUEUED", "topic.queued")

    assert settings.topic_for_state("RUNNING") == "topic.running"
    assert settings.topic_for_state("VERIFIED") == "topic.verified"
    assert settings.topic_for_state("COMPLETE") == "topic.complete"
    assert settings.topic_for_state("FAILED") == "topic.failed"
    assert settings.topic_for_state("UNKNOWN") == "topic.queued"


def test_settings_as_bool_none_defaults() -> None:
    assert orchestrator_settings._as_bool(None, True) is True
    assert orchestrator_settings._as_bool(None, False) is False
