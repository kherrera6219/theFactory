import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api-gateway"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

gateway_tracing = importlib.import_module("api_gateway.tracing")
orchestrator_tracing = importlib.import_module("orchestrator.tracing")


class _DummyApp:
    pass


def test_gateway_configure_tracing_disabled(monkeypatch) -> None:
    monkeypatch.setenv("OTEL_TRACING_ENABLED", "false")
    assert gateway_tracing.configure_tracing(_DummyApp(), service_name="api-gateway") is False


def test_orchestrator_configure_tracing_disabled(monkeypatch) -> None:
    monkeypatch.setenv("OTEL_TRACING_ENABLED", "false")
    assert orchestrator_tracing.configure_tracing(_DummyApp(), service_name="orchestrator") is False


def test_current_trace_id_without_span_is_none() -> None:
    trace_id_gateway = gateway_tracing.current_trace_id()
    trace_id_orchestrator = orchestrator_tracing.current_trace_id()
    assert trace_id_gateway is None or len(trace_id_gateway) == 32
    assert trace_id_orchestrator is None or len(trace_id_orchestrator) == 32


def test_trace_enabled_parser(monkeypatch) -> None:
    monkeypatch.setenv("OTEL_TRACING_ENABLED", "true")
    assert gateway_tracing._enabled() is True
    monkeypatch.setenv("OTEL_TRACING_ENABLED", "0")
    assert orchestrator_tracing._enabled() is False
    monkeypatch.delenv("OTEL_TRACING_ENABLED", raising=False)
    assert os.getenv("OTEL_TRACING_ENABLED") is None
