"""W3C distributed tracing context propagation across Redis protocol streams."""

from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


def inject_w3c_trace_context(carrier: dict[str, Any] | None = None) -> dict[str, str]:
    """Inject active OpenTelemetry span context into a carrier dict (W3C format).

    Returns a dict with 'traceparent' and optionally 'tracestate'.
    Safe to call when OpenTelemetry is unavailable or no span is active.
    """
    target: dict[str, str] = {} if carrier is None else carrier
    try:
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

        TraceContextTextMapPropagator().inject(target)
    except Exception as exc:
        LOGGER.debug("inject_w3c_trace_context skipped: %s", exc)
    return target


def extract_w3c_trace_context(carrier: dict[str, Any]) -> Any:
    """Extract OpenTelemetry context from carrier dict containing 'traceparent'.

    Returns an OpenTelemetry Context object (or None if unavailable/empty).
    """
    if not carrier or not isinstance(carrier, dict):
        return None
    try:
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

        return TraceContextTextMapPropagator().extract(carrier)
    except Exception as exc:
        LOGGER.debug("extract_w3c_trace_context skipped: %s", exc)
        return None


def inject_envelope_trace_context(envelope: dict[str, Any]) -> dict[str, Any]:
    """Inject W3C traceparent and tracestate into an event envelope if an active span exists."""
    carrier: dict[str, str] = {}
    inject_w3c_trace_context(carrier)
    if carrier.get("traceparent"):
        envelope["traceparent"] = carrier["traceparent"]
    if carrier.get("tracestate"):
        envelope["tracestate"] = carrier["tracestate"]
    return envelope


def extract_envelope_trace_context(envelope: dict[str, Any]) -> Any:
    """Extract OpenTelemetry context from an event or message envelope."""
    if not envelope or not isinstance(envelope, dict):
        return None
    if not envelope.get("traceparent"):
        return None
    carrier: dict[str, str] = {"traceparent": str(envelope["traceparent"])}
    if envelope.get("tracestate"):
        carrier["tracestate"] = str(envelope["tracestate"])
    return extract_w3c_trace_context(carrier)
