"""Tests for W3C distributed tracing context propagation across envelopes and spans."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Prevent module-level configure_tracing in mcp_server from connecting to remote Jaeger in tests
os.environ["OTEL_TRACING_ENABLED"] = "false"

import pytest
from jsonschema import Draft202012Validator
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared_runtime"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "protocol-bus-mcp"))

from protocol_bus.mcp_server import (  # noqa: E402
    EventEnvelope,
    MessageEnvelope,
    SendMessageRequest,
)
from thefactory_common.tracing import (  # noqa: E402
    extract_envelope_trace_context,
    extract_w3c_trace_context,
    inject_envelope_trace_context,
    inject_w3c_trace_context,
)

# Re-enable for unit tests of orchestrator.tracing
os.environ["OTEL_TRACING_ENABLED"] = "true"

from orchestrator.tracing import (  # noqa: E402
    current_span_id,
    current_trace_id,
    trace_from_carrier,
    trace_operation,
)

SCHEMA_PATH = ROOT / "schemas" / "event.envelope.schema.json"


@pytest.fixture(autouse=True)
def setup_clean_tracer():
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(InMemorySpanExporter()))
    trace.set_tracer_provider(provider)
    yield trace.get_tracer("test-distributed-tracer")
    provider.shutdown()


def test_w3c_trace_context_injection_and_extraction(setup_clean_tracer) -> None:
    tracer = setup_clean_tracer

    # Outside an active span: carrier remains clean
    carrier: dict[str, str] = {}
    inject_w3c_trace_context(carrier)
    assert carrier == {}

    # Inside an active span: traceparent is generated and matches active span
    with tracer.start_as_current_span("root_span") as span:
        ctx = span.get_span_context()
        expected_trace_id = f"{ctx.trace_id:032x}"
        expected_span_id = f"{ctx.span_id:016x}"

        inject_w3c_trace_context(carrier)
        assert "traceparent" in carrier
        parts = carrier["traceparent"].split("-")
        assert len(parts) == 4
        assert parts[0] == "00"  # W3C version
        assert parts[1] == expected_trace_id
        assert parts[2] == expected_span_id

        # Verify orchestrator current_trace_id / current_span_id helpers
        assert current_trace_id() == expected_trace_id
        assert current_span_id() == expected_span_id

        # Extract and verify remote span context
        extracted = extract_w3c_trace_context(carrier)
        assert extracted is not None


def test_envelope_trace_context_injection_and_schema_validation(setup_clean_tracer) -> None:
    tracer = setup_clean_tracer
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)

    base_envelope = {
        "event_id": "evt-test-1",
        "topic": "missions.intake",
        "timestamp": "2026-10-29T12:00:00Z",
        "producer": "api-gateway",
        "correlation_id": "mission-123",
        "payload_ref": "registry://missions/mission-123/intake",
        "schema": "missions.intake.v1",
        "priority": "NORMAL",
    }

    # 1. Base envelope without tracing passes schema
    validator.validate(base_envelope)

    # 2. Inject active trace context into envelope
    with tracer.start_as_current_span("gateway_ingress"):
        envelope = dict(base_envelope)
        inject_envelope_trace_context(envelope)
        assert "traceparent" in envelope
        assert envelope["traceparent"].startswith("00-")

        # Envelope with traceparent passes strict schema validation
        validator.validate(envelope)

        # 3. Extract from envelope
        extracted = extract_envelope_trace_context(envelope)
        assert extracted is not None


def test_distributed_trace_continuation_via_carrier(setup_clean_tracer) -> None:
    tracer = setup_clean_tracer

    with tracer.start_as_current_span("client_request") as root_span:
        carrier: dict[str, str] = {}
        inject_w3c_trace_context(carrier)
        root_ctx = root_span.get_span_context()

    # Simulate downstream service receiving message over Redis Stream
    with trace_from_carrier("worker_process", carrier, attributes={"worker.id": "pod-a"}) as child_span:
        assert child_span is not None
        child_ctx = child_span.get_span_context()

        # Child span continues the exact same trace ID
        assert f"{child_ctx.trace_id:032x}" == f"{root_ctx.trace_id:032x}"
        # Child span's parent is the root span
        if hasattr(child_span, "parent") and child_span.parent is not None:
            assert f"{child_span.parent.span_id:016x}" == f"{root_ctx.span_id:016x}"


def test_pydantic_envelopes_support_w3c_trace_fields() -> None:
    # 1. EventEnvelope
    event_env = EventEnvelope(
        event_id="evt-100",
        topic="protocol.alpha.event",
        timestamp="2026-10-29T12:00:00Z",
        producer="orchestrator",
        correlation_id="corr-100",
        payload_ref="registry://missions/m-100/state",
        schema="missions.state.v1",
        priority="NORMAL",
        traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        tracestate="congo=t61rcWkgMzE",
    )
    dumped = event_env.model_dump(mode="json", by_alias=True)
    assert dumped["traceparent"] == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    assert dumped["tracestate"] == "congo=t61rcWkgMzE"

    # Schema accepts dumped dict
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(dumped)

    # 2. MessageEnvelope
    msg_env = MessageEnvelope(
        message_id="msg-100",
        schema_version="v1",
        protocol="beta",
        sender="AGENT-14-PYTHON",
        recipient="AGENT-03-POD-MGR",
        correlation_id="corr-100",
        priority="normal",
        timestamp="2026-10-29T12:00:00Z",
        payload={"schema_version": "v1", "logicnode_id": "node-1", "source_language": "python", "payload": {}},
        traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    )
    msg_dump = msg_env.model_dump(mode="json")
    assert msg_dump["traceparent"] == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    # 3. SendMessageRequest
    req = SendMessageRequest(
        schema_version="v1",
        protocol="alpha",
        sender="AGENT-01-PM",
        recipient="AGENT-03-POD-MGR",
        correlation_id="corr-100",
        traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    )
    assert req.traceparent == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


def test_trace_operation_decorator() -> None:
    @trace_operation("sync_test_op", {"custom.tag": "value1"})
    def my_sync_fn(x: int) -> int:
        return x * 2

    assert my_sync_fn(5) == 10

    @trace_operation("async_test_op", {"custom.tag": "value2"})
    async def my_async_fn(x: int) -> int:
        return x + 5

    import asyncio
    assert asyncio.run(my_async_fn(5)) == 10

def test_tracing_sampling_ratio(monkeypatch) -> None:
    from orchestrator.tracing import _sampling_ratio

    monkeypatch.setenv("OTEL_SAMPLING_RATIO", "0.5")
    assert _sampling_ratio() == 0.5

    monkeypatch.setenv("OTEL_SAMPLING_RATIO", "invalid")
    assert _sampling_ratio() == 0.1

    monkeypatch.setenv("OTEL_SAMPLING_RATIO", "1.5")
    assert _sampling_ratio() == 1.0

    monkeypatch.setenv("OTEL_SAMPLING_RATIO", "-0.2")
    assert _sampling_ratio() == 0.0


def test_tracing_configure_disabled(monkeypatch) -> None:
    from orchestrator.tracing import configure_tracing

    monkeypatch.setattr("orchestrator.tracing._enabled", lambda: False)
    assert configure_tracing(None, service_name="test") is False


def test_tracing_configure_existing_provider(monkeypatch) -> None:
    from unittest.mock import MagicMock

    from orchestrator.tracing import configure_tracing

    monkeypatch.setattr("orchestrator.tracing._enabled", lambda: True)
    mock_app = MagicMock()
    # provider is already a TracerProvider from setup_clean_tracer
    result = configure_tracing(mock_app, service_name="test-service")
    assert result is True


def test_current_ids_when_no_active_span(setup_clean_tracer) -> None:
    assert current_trace_id() is None
    assert current_span_id() is None


def test_trace_operation_disabled(monkeypatch) -> None:
    monkeypatch.setattr("orchestrator.tracing._enabled", lambda: False)

    @trace_operation("disabled_op")
    def sync_fn():
        return 42

    assert sync_fn() == 42


def test_trace_from_carrier_empty() -> None:
    with trace_from_carrier("empty_op", None) as span:
        assert span is None

    with trace_from_carrier("empty_dict_op", {}) as span:
        assert span is None


def test_common_tracing_edge_cases() -> None:
    # Non-dict inputs
    assert extract_w3c_trace_context(None) is None
    assert extract_w3c_trace_context("invalid") is None
    assert extract_envelope_trace_context(None) is None
    assert extract_envelope_trace_context({}) is None

    # Envelope with both traceparent and tracestate
    env = {
        "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        "tracestate": "congo=t61rcWkgMzE",
    }
    ctx = extract_envelope_trace_context(env)
    assert ctx is not None

    # Envelope with only tracestate (no traceparent) returns None
    assert extract_envelope_trace_context({"tracestate": "foo=bar"}) is None
