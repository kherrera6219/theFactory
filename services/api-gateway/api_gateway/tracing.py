from __future__ import annotations

import logging
import os
from typing import Any

LOGGER = logging.getLogger(__name__)
TRUTHY_VALUES = {"1", "true", "yes", "on"}


def _enabled() -> bool:
    return os.getenv("OTEL_TRACING_ENABLED", "true").strip().lower() in TRUTHY_VALUES


def _sampling_ratio() -> float:
    """Head-based trace sampling ratio (0.0–1.0).

    Defaults to 0.1 (10%) to bound production trace volume and storage; set
    OTEL_SAMPLING_RATIO=1.0 in dev to capture every trace. A ParentBased
    sampler wraps this so child spans honor the parent's sampling decision.
    """
    try:
        ratio = float(os.getenv("OTEL_SAMPLING_RATIO", "0.1"))
    except ValueError:
        LOGGER.warning("invalid OTEL_SAMPLING_RATIO; falling back to 0.1")
        return 0.1
    return min(1.0, max(0.0, ratio))


def configure_tracing(app: Any, *, service_name: str) -> bool:
    if not _enabled():
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    except Exception as exc:
        LOGGER.warning("tracing disabled (dependencies unavailable): %s", exc)
        return False

    endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "http://jaeger:4318/v1/traces",
    ).strip()
    sampler = ParentBased(root=TraceIdRatioBased(_sampling_ratio()))
    resource = Resource.create({"service.name": service_name})
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider(resource=resource, sampler=sampler)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)

    try:
        FastAPIInstrumentor.instrument_app(app, excluded_urls="/health,/readyz,/metrics")
    except Exception as exc:
        LOGGER.warning("fastapi tracing instrumentation skipped: %s", exc)

    try:
        HTTPXClientInstrumentor().instrument()
    except Exception as exc:
        LOGGER.warning("httpx tracing instrumentation skipped: %s", exc)

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
