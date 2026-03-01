import asyncio
import importlib
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


def test_auth_dependency_blocks_readonly_for_mutate() -> None:
    settings = _make_settings()
    dependency = require_roles(settings, {"mutate"})
    with pytest.raises(HTTPException):
        asyncio.run(dependency(x_api_key="viewer-key"))
