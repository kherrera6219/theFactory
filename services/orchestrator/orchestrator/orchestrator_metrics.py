from __future__ import annotations

from prometheus_client import REGISTRY, Counter, Histogram


def _get_metric(name: str):
    return REGISTRY._names_to_collectors.get(name)

# Using a helper to avoid "Duplicated timeseries" error in tests
REQUEST_COUNTER = _get_metric("orchestrator_http_requests_total") or Counter(
    "orchestrator_http_requests_total",
    "Total HTTP requests served by orchestrator",
    ("method", "path", "status_code"),
)

REQUEST_LATENCY = _get_metric("orchestrator_http_request_duration_seconds") or Histogram(
    "orchestrator_http_request_duration_seconds",
    "HTTP request latency in seconds for orchestrator",
    ("method", "path"),
)

LLM_FALLBACK_TOTAL = _get_metric("llm_fallback_total") or Counter(
    "llm_fallback_total",
    "Count of silent LLM fallbacks",
    ("agent_id", "reason"),
)
