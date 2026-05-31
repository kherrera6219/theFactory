"""llm_delegation/metrics.py — Prometheus instrumentation for LLM API calls.

Previously the delegation layer had no latency / token / cost / error metrics,
leaving model performance and spend completely unobservable. These counters and
histograms are wired into the provider transport (``providers._call_provider``)
and the token-usage recorder (``config._record_usage_event``).

All recording helpers are non-fatal: observability must never break a mission.
"""
from __future__ import annotations

import logging

from prometheus_client import REGISTRY, Counter, Histogram

LOGGER = logging.getLogger(__name__)


def _get_metric(name: str):
    return REGISTRY._names_to_collectors.get(name)


LLM_REQUESTS_TOTAL = _get_metric("factory_llm_requests_total") or Counter(
    "factory_llm_requests_total",
    "Total LLM API requests",
    ("provider", "model", "agent_id", "status"),  # success | error | timeout | rate_limited
)

LLM_REQUEST_DURATION_SECONDS = (
    _get_metric("factory_llm_request_duration_seconds")
    or Histogram(
        "factory_llm_request_duration_seconds",
        "LLM API request duration",
        ("provider", "model"),
        buckets=(0.5, 1, 2, 5, 10, 30, 60, 120),
    )
)

LLM_TOKENS_TOTAL = _get_metric("factory_llm_tokens_total") or Counter(
    "factory_llm_tokens_total",
    "Total LLM tokens used",
    ("provider", "model", "token_type"),  # prompt | completion
)

LLM_ESTIMATED_COST_USD_TOTAL = (
    _get_metric("factory_llm_estimated_cost_usd_total")
    or Counter(
        "factory_llm_estimated_cost_usd_total",
        "Estimated total LLM cost in USD",
        ("provider", "model"),
    )
)


def record_llm_request(
    *,
    provider: str,
    model: str,
    agent_id: str,
    status: str,
    duration_seconds: float | None = None,
) -> None:
    """Record one LLM request outcome and (optionally) its latency. Never raises."""
    try:
        LLM_REQUESTS_TOTAL.labels(
            provider=provider or "unknown",
            model=model or "unknown",
            agent_id=agent_id or "unknown",
            status=status,
        ).inc()
        if duration_seconds is not None:
            LLM_REQUEST_DURATION_SECONDS.labels(
                provider=provider or "unknown", model=model or "unknown"
            ).observe(max(0.0, duration_seconds))
    except Exception:  # noqa: BLE001
        LOGGER.warning("failed to record llm request metric", exc_info=True)


def record_llm_usage(
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Record token counts and estimated cost for one LLM call. Never raises."""
    try:
        prov = provider or "unknown"
        mod = model or "unknown"
        if input_tokens:
            LLM_TOKENS_TOTAL.labels(
                provider=prov, model=mod, token_type="prompt"
            ).inc(input_tokens)
        if output_tokens:
            LLM_TOKENS_TOTAL.labels(
                provider=prov, model=mod, token_type="completion"
            ).inc(output_tokens)

        from ..llm_cost_ledger import _estimate_cost

        cost, pricing_known = _estimate_cost(provider, model, input_tokens, output_tokens)
        if pricing_known and cost:
            LLM_ESTIMATED_COST_USD_TOTAL.labels(provider=prov, model=mod).inc(cost)
    except Exception:  # noqa: BLE001
        LOGGER.warning("failed to record llm usage metric", exc_info=True)
