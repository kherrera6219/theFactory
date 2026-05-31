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
sys.path.insert(0, str(ROOT / "services" / "protocol-bus-mcp"))
sys.path.insert(0, str(ROOT / "services" / "dashboard"))

gateway_tracing = importlib.import_module("api_gateway.tracing")
orchestrator_tracing = importlib.import_module("orchestrator.tracing")
pod_worker_tracing = importlib.import_module("pod_worker.tracing")
audit_worker_tracing = importlib.import_module("audit_worker.tracing")
protocol_bus_tracing = importlib.import_module("protocol_bus.tracing")
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
        protocol_bus_tracing.configure_tracing(_DummyApp(), service_name="protocol-bus-mcp")
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
    assert protocol_bus_tracing._enabled() is False
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
            protocol_bus_tracing.configure_tracing(
                _DummyApp(),
                service_name="protocol-bus-mcp",
            )
            is True
        )
        assert dashboard_tracing.configure_tracing(_DummyApp(), service_name="dashboard") is True

    assert "fastapi tracing instrumentation skipped" in caplog.text
    assert "httpx tracing instrumentation skipped" in caplog.text


# ---------------------------------------------------------------------------
# orchestrator.tracing.current_span_id
# ---------------------------------------------------------------------------
def test_current_span_id_without_span() -> None:
    span_id = orchestrator_tracing.current_span_id()
    assert span_id is None or len(span_id) == 16


def _install_valid_span(monkeypatch, *, trace_id: int, span_id: int) -> None:
    """Inject an opentelemetry.trace whose current span has a valid context,
    covering the hex-formatting branch of current_trace_id/current_span_id."""
    trace_module = ModuleType("opentelemetry.trace")
    trace_module.get_current_span = lambda: SimpleNamespace(
        get_span_context=lambda: SimpleNamespace(
            is_valid=True, trace_id=trace_id, span_id=span_id
        )
    )
    otel = ModuleType("opentelemetry")
    otel.trace = trace_module
    monkeypatch.setitem(sys.modules, "opentelemetry", otel)
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", trace_module)


def test_current_trace_id_valid_span_returns_hex(monkeypatch) -> None:
    _install_valid_span(monkeypatch, trace_id=0x1234, span_id=0xABCD)
    trace_id = orchestrator_tracing.current_trace_id()
    assert trace_id == f"{0x1234:032x}"
    assert len(trace_id) == 32


def test_current_span_id_valid_span_returns_hex(monkeypatch) -> None:
    _install_valid_span(monkeypatch, trace_id=0x1234, span_id=0xABCD)
    span_id = orchestrator_tracing.current_span_id()
    assert span_id == f"{0xABCD:016x}"
    assert len(span_id) == 16


# ---------------------------------------------------------------------------
# orchestrator.tracing.trace_operation (orchestrator-only decorator)
# ---------------------------------------------------------------------------
def test_trace_operation_sync_returns_result(monkeypatch) -> None:
    monkeypatch.setenv("OTEL_TRACING_ENABLED", "true")

    @orchestrator_tracing.trace_operation("test.sync", attributes={"phase": "unit"})
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, 3) == 5


def test_trace_operation_async_returns_result(monkeypatch) -> None:
    import asyncio

    monkeypatch.setenv("OTEL_TRACING_ENABLED", "true")

    @orchestrator_tracing.trace_operation("test.async", attributes={"phase": "unit"})
    async def add(a: int, b: int) -> int:
        return a + b

    assert asyncio.run(add(4, 5)) == 9
    assert asyncio.iscoroutinefunction(add)


def test_trace_operation_disabled_returns_original(monkeypatch) -> None:
    monkeypatch.setenv("OTEL_TRACING_ENABLED", "false")

    def original(x: int) -> int:
        return x * 2

    decorated = orchestrator_tracing.trace_operation("test.disabled")(original)
    # When disabled the decorator returns the function unchanged.
    assert decorated is original
    assert decorated(21) == 42


def test_trace_operation_no_attributes(monkeypatch) -> None:
    monkeypatch.setenv("OTEL_TRACING_ENABLED", "true")

    @orchestrator_tracing.trace_operation("test.no-attrs")
    def noop() -> str:
        return "done"

    assert noop() == "done"


def _install_raising_tracer(monkeypatch) -> None:
    """Inject an opentelemetry.trace whose get_tracer raises, so the
    trace_operation wrappers must fall back to calling func directly."""
    trace_module = ModuleType("opentelemetry.trace")

    def _boom(*args, **kwargs):
        raise RuntimeError("tracer unavailable")

    trace_module.get_tracer = _boom
    otel = ModuleType("opentelemetry")
    otel.trace = trace_module
    monkeypatch.setitem(sys.modules, "opentelemetry", otel)
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", trace_module)


def test_trace_operation_sync_fallback_on_tracer_error(monkeypatch) -> None:
    monkeypatch.setenv("OTEL_TRACING_ENABLED", "true")
    _install_raising_tracer(monkeypatch)

    @orchestrator_tracing.trace_operation("test.sync.fallback")
    def add(a: int, b: int) -> int:
        return a + b

    # Tracer raises internally; wrapper must still return the real result.
    assert add(7, 8) == 15


def test_trace_operation_async_fallback_on_tracer_error(monkeypatch) -> None:
    import asyncio

    monkeypatch.setenv("OTEL_TRACING_ENABLED", "true")
    _install_raising_tracer(monkeypatch)

    @orchestrator_tracing.trace_operation("test.async.fallback")
    async def add(a: int, b: int) -> int:
        return a + b

    assert asyncio.run(add(7, 8)) == 15
