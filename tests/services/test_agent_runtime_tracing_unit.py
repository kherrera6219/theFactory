"""Coverage-focused tests for dedicated agent-runtime tracing wiring."""

import importlib
import logging
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "agent-runtime"))
sys.path.insert(0, str(ROOT / "services" / "api-gateway"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))
sys.path.insert(0, str(ROOT / "services" / "audit-worker"))
sys.path.insert(0, str(ROOT / "services" / "semantic-bus-mcp"))
sys.path.insert(0, str(ROOT / "services" / "dashboard"))

agent_runtime_tracing = importlib.import_module("agent_runtime.tracing")
gateway_tracing = importlib.import_module("api_gateway.tracing")
orchestrator_tracing = importlib.import_module("orchestrator.tracing")
pod_worker_tracing = importlib.import_module("pod_worker.tracing")
audit_worker_tracing = importlib.import_module("audit_worker.tracing")
semantic_bus_tracing = importlib.import_module("semantic_bus.tracing")
dashboard_tracing = importlib.import_module("dashboard.tracing")


class _DummyApp:
    pass


def _install_fake_otel(monkeypatch, *, fail_fastapi: bool = False, fail_httpx: bool = False):
    provider_state = {"provider": object(), "fastapi_calls": [], "httpx_calls": 0}

    class FakeTracerProvider:
        def __init__(self, *, resource):
            self.resource = resource
            self.processors = []

        def add_span_processor(self, processor):
            self.processors.append(processor)

    class FakeBatchSpanProcessor:
        def __init__(self, exporter):
            self.exporter = exporter

    class FakeOTLPSpanExporter:
        def __init__(self, *, endpoint):
            self.endpoint = endpoint

    class FakeResource:
        @staticmethod
        def create(payload):
            return payload

    class FakeFastAPIInstrumentor:
        @staticmethod
        def instrument_app(app, *, excluded_urls):
            if fail_fastapi:
                raise RuntimeError("fastapi failed")
            provider_state["fastapi_calls"].append((app, excluded_urls))

    class FakeHTTPXClientInstrumentor:
        def instrument(self):
            if fail_httpx:
                raise RuntimeError("httpx failed")
            provider_state["httpx_calls"] += 1

    trace_module = ModuleType("opentelemetry.trace")
    trace_module.get_tracer_provider = lambda: provider_state["provider"]
    trace_module.set_tracer_provider = lambda provider: provider_state.__setitem__("provider", provider)
    trace_module.get_current_span = lambda: SimpleNamespace(
        get_span_context=lambda: SimpleNamespace(is_valid=True, trace_id=0x1234)
    )

    modules = {
        "opentelemetry": ModuleType("opentelemetry"),
        "opentelemetry.trace": trace_module,
        "opentelemetry.exporter": ModuleType("opentelemetry.exporter"),
        "opentelemetry.exporter.otlp": ModuleType("opentelemetry.exporter.otlp"),
        "opentelemetry.exporter.otlp.proto": ModuleType("opentelemetry.exporter.otlp.proto"),
        "opentelemetry.exporter.otlp.proto.http": ModuleType("opentelemetry.exporter.otlp.proto.http"),
        "opentelemetry.exporter.otlp.proto.http.trace_exporter": ModuleType(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter"
        ),
        "opentelemetry.instrumentation": ModuleType("opentelemetry.instrumentation"),
        "opentelemetry.instrumentation.fastapi": ModuleType(
            "opentelemetry.instrumentation.fastapi"
        ),
        "opentelemetry.instrumentation.httpx": ModuleType("opentelemetry.instrumentation.httpx"),
        "opentelemetry.sdk": ModuleType("opentelemetry.sdk"),
        "opentelemetry.sdk.resources": ModuleType("opentelemetry.sdk.resources"),
        "opentelemetry.sdk.trace": ModuleType("opentelemetry.sdk.trace"),
        "opentelemetry.sdk.trace.export": ModuleType("opentelemetry.sdk.trace.export"),
    }
    modules["opentelemetry"].trace = trace_module
    modules["opentelemetry.exporter.otlp.proto.http.trace_exporter"].OTLPSpanExporter = (
        FakeOTLPSpanExporter
    )
    modules["opentelemetry.instrumentation.fastapi"].FastAPIInstrumentor = FakeFastAPIInstrumentor
    modules["opentelemetry.instrumentation.httpx"].HTTPXClientInstrumentor = (
        FakeHTTPXClientInstrumentor
    )
    modules["opentelemetry.sdk.resources"].Resource = FakeResource
    modules["opentelemetry.sdk.trace"].TracerProvider = FakeTracerProvider
    modules["opentelemetry.sdk.trace.export"].BatchSpanProcessor = FakeBatchSpanProcessor
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    return provider_state


def test_configure_tracing_success_path(monkeypatch) -> None:
    monkeypatch.setenv("OTEL_TRACING_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector.local/v1/traces")
    state = _install_fake_otel(monkeypatch)

    modules = [
        agent_runtime_tracing,
        gateway_tracing,
        orchestrator_tracing,
        pod_worker_tracing,
        audit_worker_tracing,
        semantic_bus_tracing,
        dashboard_tracing,
    ]
    for module in modules:
        assert module.configure_tracing(_DummyApp(), service_name="svc") is True

    assert state["httpx_calls"] >= 3
    assert len(state["fastapi_calls"]) == len(modules)
    assert isinstance(state["provider"], sys.modules["opentelemetry.sdk.trace"].TracerProvider)


def test_configure_tracing_logs_instrumentation_failures(monkeypatch, caplog) -> None:
    monkeypatch.setenv("OTEL_TRACING_ENABLED", "true")
    _install_fake_otel(monkeypatch, fail_fastapi=True, fail_httpx=True)

    with caplog.at_level(logging.WARNING):
        assert gateway_tracing.configure_tracing(_DummyApp(), service_name="api-gateway") is True
        assert agent_runtime_tracing.configure_tracing(_DummyApp(), service_name="agent-runtime") is True
        assert orchestrator_tracing.configure_tracing(_DummyApp(), service_name="orchestrator") is True

    assert "fastapi tracing instrumentation skipped" in caplog.text
    assert "httpx tracing instrumentation skipped" in caplog.text


def test_current_trace_id_uses_valid_context(monkeypatch) -> None:
    _install_fake_otel(monkeypatch)
    assert gateway_tracing.current_trace_id() == f"{0x1234:032x}"
    assert orchestrator_tracing.current_trace_id() == f"{0x1234:032x}"

    invalid_trace = ModuleType("opentelemetry.trace")
    invalid_trace.get_current_span = lambda: SimpleNamespace(
        get_span_context=lambda: SimpleNamespace(is_valid=False, trace_id=0)
    )
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", invalid_trace)
    monkeypatch.setitem(sys.modules, "opentelemetry", SimpleNamespace(trace=invalid_trace))
    assert gateway_tracing.current_trace_id() is None
    assert orchestrator_tracing.current_trace_id() is None
