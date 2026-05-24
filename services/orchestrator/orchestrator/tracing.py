from __future__ import annotations

import logging
import os
from typing import Any

LOGGER = logging.getLogger(__name__)
TRUTHY_VALUES = {"1", "true", "yes", "on"}


def _enabled() -> bool:
    return os.getenv("OTEL_TRACING_ENABLED", "true").strip().lower() in TRUTHY_VALUES


def configure_tracing(app: Any, *, service_name: str) -> bool:
    if not _enabled():
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception as exc:
        LOGGER.warning("tracing disabled (dependencies unavailable): %s", exc)
        return False

    endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "http://jaeger:4318/v1/traces",
    ).strip()
    resource = Resource.create({"service.name": service_name})
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)

    try:
        FastAPIInstrumentor.instrument_app(app, excluded_urls="/health,/readyz,/metrics")
    except Exception as exc:
        LOGGER.warning("fastapi tracing instrumentation skipped: %s", exc)

    LOGGER.info("tracing configured for %s via %s", service_name, endpoint)
    return True


def current_trace_id() -> str | None:
    try:
        from opentelemetry import trace
    except Exception:
        return None

    span = trace.get_current_span()
    context = span.get_span_context()
    if context is None or not context.is_valid:
        return None
    return f"{context.trace_id:032x}"


def current_span_id() -> str | None:
    try:
        from opentelemetry import trace
    except Exception:
        return None

    span = trace.get_current_span()
    context = span.get_span_context()
    if context is None or not context.is_valid:
        return None
    return f"{context.span_id:016x}"


def trace_operation(operation_name: str, attributes: dict[str, Any] | None = None):
    """Decorator to trace a function call with OTEL spans."""
    def decorator(func):
        import functools
        if not _enabled():
            return func

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                from opentelemetry import trace
                tracer = trace.get_tracer(__name__)
                with tracer.start_as_current_span(operation_name) as span:
                    if attributes:
                        for key, value in attributes.items():
                            span.set_attribute(key, str(value))
                    return func(*args, **kwargs)
            except Exception:
                return func(*args, **kwargs)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                from opentelemetry import trace
                tracer = trace.get_tracer(__name__)
                with tracer.start_as_current_span(operation_name) as span:
                    if attributes:
                        for key, value in attributes.items():
                            span.set_attribute(key, str(value))
                    return await func(*args, **kwargs)
            except Exception:
                return await func(*args, **kwargs)

            import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    return decorator
