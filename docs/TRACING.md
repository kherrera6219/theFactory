# OpenTelemetry Tracing

Document version: 2026.06.13
Last updated: 2026-06-27
Status: Canonical

**Code file:** `services/orchestrator/orchestrator/tracing.py`  
**Audience:** Developers, Operators  
**Last reviewed:** 2026-06-11

This document covers the OpenTelemetry (OTEL) distributed tracing integration for the orchestrator service — how it is configured, how spans are created, and how to instrument new code.

---

## Overview

`tracing.py` is the single entry point for all OTEL instrumentation in the orchestrator. It provides:

- `configure_tracing(app, service_name)` — bootstraps the OTEL tracer provider and instruments FastAPI
- `current_trace_id()` / `current_span_id()` — safe accessors for the active span context (used in log correlation)
- `@trace_operation(name, attributes)` — a decorator that wraps any sync or async function in a named OTEL span

All functions are **fail-safe**: if the `opentelemetry` SDK packages are not installed, or if OTEL is disabled via env var, every function silently no-ops rather than raising an exception. This ensures tracing is always an optional overlay — it never affects correctness.

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OTEL_TRACING_ENABLED` | `true` | Set to `false` (or `0`, `no`, `off`) to disable all tracing globally |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | `http://jaeger:4318/v1/traces` | OTLP HTTP endpoint for span export. Point to any OTLP-compatible collector (Jaeger, Tempo, Honeycomb, Datadog OTLP ingest, etc.) |
| `OTEL_SAMPLING_RATIO` | `0.1` | Head-based trace sampling ratio (0.0–1.0). `0.1` = 10% of traces are sampled. Set to `1.0` in development to capture all traces. |

### Sampling Strategy

The sampler is `ParentBased(root=TraceIdRatioBased(ratio))`. This means:
- **Root spans** (no incoming trace context) are sampled at the configured ratio
- **Child spans** (with an incoming `traceparent` header) inherit the parent's sampling decision regardless of the local ratio

The default of 10% is intentional for production — full trace capture at high mission throughput would produce significant storage volume. Set `OTEL_SAMPLING_RATIO=1.0` in local development or staging.

### FastAPI Auto-Instrumentation

`configure_tracing()` calls `FastAPIInstrumentor.instrument_app()`, which automatically creates spans for every HTTP request handled by FastAPI. The following paths are excluded from instrumentation to avoid span noise:

- `/health`
- `/readyz`
- `/metrics`

---

## Public API

### `configure_tracing(app, *, service_name) -> bool`

Called once during FastAPI lifespan startup (see `ORCHESTRATOR_MAIN.md`). Returns `True` if tracing was successfully configured, `False` if disabled or if SDK packages are unavailable.

```python
from .tracing import configure_tracing

configured = configure_tracing(app, service_name="orchestrator")
```

**Behaviour:**
- Checks `OTEL_TRACING_ENABLED`. If false, returns `False` immediately.
- Attempts to import the OTEL SDK. If unavailable, logs a warning and returns `False`.
- Creates a `TracerProvider` with a `BatchSpanProcessor` pointing at the OTLP endpoint.
- Sets the provider as the global tracer provider (idempotent — skips if a `TracerProvider` is already set).
- Instruments the FastAPI `app` instance.

---

### `current_trace_id() -> str | None`

Returns the current trace ID as a 32-character lowercase hex string, or `None` if there is no active span or OTEL is unavailable.

Used to correlate structured log lines with Jaeger/Tempo traces:

```python
from .tracing import current_trace_id

logger.info("mission dispatched", extra={"trace_id": current_trace_id()})
```

---

### `current_span_id() -> str | None`

Returns the current span ID as a 16-character lowercase hex string, or `None` if there is no active span.

---

### `@trace_operation(operation_name, attributes=None)`

Decorator that wraps a sync or async function in a named OTEL span. Automatically detects coroutines and applies the correct wrapper.

```python
from .tracing import trace_operation

@trace_operation("mission.dispatch", attributes={"component": "runtime"})
async def dispatch_mission(mission_id: str) -> None:
    ...

@trace_operation("logicnode.extract")
def extract_logicnodes(source: str) -> list:
    ...
```

**Behaviour:**
- If `OTEL_TRACING_ENABLED=false`, the decorator returns the original function unwrapped (zero overhead).
- If OTEL is enabled but an exception occurs inside the span management, the function is called without tracing (fail-safe — the business function is never suppressed).
- Attributes are set as span attributes via `span.set_attribute(key, str(value))`.

---

## Jaeger UI

In the default `docker compose up` environment, Jaeger runs at:

- **Trace collector (OTLP HTTP):** `http://jaeger:4318` (in-network) / `http://localhost:4318` (host)
- **Jaeger UI:** `http://localhost:16686`

Set `OTEL_SAMPLING_RATIO=1.0` locally to ensure all traces appear in the UI during development.

---

## Log Correlation

To correlate Prometheus/structured log lines with Jaeger traces, inject `current_trace_id()` into your log `extra` dict:

```python
logger.info(
    "phase transition complete",
    extra={
        "mission_id": mission_id,
        "phase": phase_name,
        "trace_id": current_trace_id(),
        "span_id": current_span_id(),
    }
)
```

Grafana Loki and similar log aggregators can then link log lines directly to the Tempo/Jaeger trace using the `trace_id` field.

---

## Instrumenting New Code

Three patterns cover all use cases:

**1. Instrument an entire function (preferred)**
```python
@trace_operation("pod.worker.run", attributes={"pod": "A", "language": "python"})
async def run_pod_worker(mission_id: str) -> dict:
    ...
```

**2. Manual span for a code block**
```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("logicnode.batch_insert") as span:
    span.set_attribute("count", len(nodes))
    await store.insert_many(nodes)
```

**3. Log correlation only (no new span)**
```python
from .tracing import current_trace_id

logger.warning("retry attempt", extra={"trace_id": current_trace_id(), "attempt": n})
```

---

## SDK Availability

The OTEL SDK packages are **optional dependencies** — the orchestrator boots and operates normally without them. If tracing packages are absent from the container image, `configure_tracing()` logs a single `WARNING` at startup and returns `False`. All `@trace_operation` decorators become transparent pass-throughs.

Required packages (when tracing is enabled):
```
opentelemetry-sdk
opentelemetry-exporter-otlp-proto-http
opentelemetry-instrumentation-fastapi
```

These are included in `services/orchestrator/requirements.txt` and the production Docker image. They may be absent in minimal local environments if `pip install -r requirements.txt` was not run.

---

## Related Documentation

- [OBSERVABILITY_STACK.md](OBSERVABILITY_STACK.md) — full observability stack including Prometheus, Grafana, and Jaeger
- [ORCHESTRATOR_MAIN.md](ORCHESTRATOR_MAIN.md) — where `configure_tracing()` is called during lifespan startup
- [SETTINGS_REFERENCE.md](SETTINGS_REFERENCE.md) — companion env var reference
- [METRICS_SOURCE_MODULES.md](METRICS_SOURCE_MODULES.md) — Prometheus metrics (separate from OTEL traces)
