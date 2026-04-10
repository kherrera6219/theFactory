import importlib
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api-gateway"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))
sys.path.insert(0, str(ROOT / "services" / "audit-worker"))
sys.path.insert(0, str(ROOT / "services" / "semantic-bus-mcp"))
sys.path.insert(0, str(ROOT / "services" / "dashboard"))

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
    trace_module.set_tracer_provider = lambda provider: provider_state.__setitem__(
        "provider",
        provider,
    )
    trace_module.get_current_span = lambda: SimpleNamespace(
        get_span_context=lambda: SimpleNamespace(is_valid=True, trace_id=0x1234)
    )

    modules = {
        "opentelemetry": ModuleType("opentelemetry"),
        "opentelemetry.trace": trace_module,
        "opentelemetry.exporter": ModuleType("opentelemetry.exporter"),
        "opentelemetry.exporter.otlp": ModuleType("opentelemetry.exporter.otlp"),
        "opentelemetry.exporter.otlp.proto": ModuleType("opentelemetry.exporter.otlp.proto"),
        "opentelemetry.exporter.otlp.proto.http": ModuleType(
            "opentelemetry.exporter.otlp.proto.http"
        ),
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


def test_gateway_configure_tracing_disabled(monkeypatch) -> None:
    monkeypatch.setenv("OTEL_TRACING_ENABLED", "false")
    assert gateway_tracing.configure_tracing(_DummyApp(), service_name="api-gateway") is False


def test_orchestrator_configure_tracing_disabled(monkeypatch) -> None:
    monkeypatch.setenv("OTEL_TRACING_ENABLED", "false")
    assert orchestrator_tracing.configure_tracing(_DummyApp(), service_name="orchestrator") is False


def test_other_services_configure_tracing_disabled(monkeypatch) -> None:
    monkeypatch.setenv("OTEL_TRACING_ENABLED", "false")
    assert pod_worker_tracing.configure_tracing(_DummyApp(), service_name="pod-worker") is False
    assert audit_worker_tracing.configure_tracing(_DummyApp(), service_name="audit-worker") is False
    assert (
        semantic_bus_tracing.configure_tracing(_DummyApp(), service_name="semantic-bus-mcp")
        is False
    )
    assert dashboard_tracing.configure_tracing(_DummyApp(), service_name="dashboard") is False


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
    assert pod_worker_tracing._enabled() is False
    assert audit_worker_tracing._enabled() is False
    assert semantic_bus_tracing._enabled() is False
    assert dashboard_tracing._enabled() is False
    monkeypatch.delenv("OTEL_TRACING_ENABLED", raising=False)
    assert os.getenv("OTEL_TRACING_ENABLED") is None


def test_other_service_tracing_logs_instrumentation_failures(monkeypatch, caplog) -> None:
    monkeypatch.setenv("OTEL_TRACING_ENABLED", "true")
    _install_fake_otel(monkeypatch, fail_fastapi=True, fail_httpx=True)

    with caplog.at_level("WARNING"):
        assert pod_worker_tracing.configure_tracing(_DummyApp(), service_name="pod-worker") is True
        assert (
            audit_worker_tracing.configure_tracing(_DummyApp(), service_name="audit-worker")
            is True
        )
        assert (
            semantic_bus_tracing.configure_tracing(
                _DummyApp(),
                service_name="semantic-bus-mcp",
            )
            is True
        )
        assert dashboard_tracing.configure_tracing(_DummyApp(), service_name="dashboard") is True

    assert "fastapi tracing instrumentation skipped" in caplog.text
    assert "httpx tracing instrumentation skipped" in caplog.text
