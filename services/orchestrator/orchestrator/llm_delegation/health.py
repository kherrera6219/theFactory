from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from .text import _clean_text

LOGGER = logging.getLogger(__name__)

_PROVIDER_HEALTH_WINDOW_SECONDS = 300.0
_PROVIDER_HEALTH_MAX_SAMPLES = 200
_provider_health_samples: dict[str, list[dict[str, Any]]] = defaultdict(list)

# ---------------------------------------------------------------------------
# Per-provider circuit breaker.
#
# When a provider returns enough consecutive non-retryable failures, the
# circuit "opens" and callers skip it (routing straight to the fallback
# provider) until a cooldown elapses. After the cooldown the circuit is
# "half-open": the next call is allowed through and a success closes it again,
# while a failure re-opens it. This stops every agent from hammering a dead
# provider once telemetry shows it is down.
# ---------------------------------------------------------------------------
CIRCUIT_OPEN_THRESHOLD = 5  # consecutive failures before opening
CIRCUIT_OPEN_SECONDS = 60.0  # time to stay open before half-open probe

_provider_failures: dict[str, int] = {}
_provider_open_until: dict[str, float] = {}


def _normalize_provider(provider: str) -> str:
    return str(provider or "openai").strip().lower() or "openai"


def is_circuit_open(provider: str, now: float | None = None) -> bool:
    """Return True when *provider*'s circuit is open and calls should be skipped.

    Once the cooldown window elapses the circuit transitions to half-open: the
    failure counter is reset so the next call is allowed through as a probe.
    """
    key = _normalize_provider(provider)
    open_until = _provider_open_until.get(key)
    if open_until is None:
        return False
    timestamp = time.time() if now is None else now
    if timestamp < open_until:
        return True
    # Cooldown elapsed → half-open: clear state and allow a probe call.
    _provider_open_until.pop(key, None)
    _provider_failures[key] = 0
    return False


def record_failure(provider: str, now: float | None = None) -> None:
    """Record a non-retryable failure for *provider*; open the circuit at threshold."""
    key = _normalize_provider(provider)
    _provider_failures[key] = _provider_failures.get(key, 0) + 1
    if _provider_failures[key] >= CIRCUIT_OPEN_THRESHOLD:
        timestamp = time.time() if now is None else now
        _provider_open_until[key] = timestamp + CIRCUIT_OPEN_SECONDS
        LOGGER.warning(
            "Circuit breaker OPEN for provider %s (%d consecutive failures)",
            key,
            _provider_failures[key],
        )


def record_success(provider: str) -> None:
    """Record a successful call for *provider*; close the circuit."""
    key = _normalize_provider(provider)
    _provider_failures[key] = 0
    _provider_open_until.pop(key, None)


def get_circuit_state(provider: str, now: float | None = None) -> str:
    """Return ``"open"``, ``"half_open"``, or ``"closed"`` for *provider*."""
    key = _normalize_provider(provider)
    open_until = _provider_open_until.get(key)
    if open_until is None:
        return "closed"
    timestamp = time.time() if now is None else now
    return "open" if timestamp < open_until else "half_open"


def reset_circuit_breakers() -> None:
    """Clear all circuit-breaker state. Intended for test isolation."""
    _provider_failures.clear()
    _provider_open_until.clear()

def _record_provider_health(
    *,
    provider: str,
    model: str,
    latency_ms: float,
    success: bool,
    now: float | None = None,
) -> None:
    normalized_provider = str(provider or "openai").strip().lower() or "openai"
    timestamp = time.time() if now is None else now
    samples = _provider_health_samples[normalized_provider]
    cutoff = timestamp - _PROVIDER_HEALTH_WINDOW_SECONDS
    samples[:] = [
        sample
        for sample in samples[-_PROVIDER_HEALTH_MAX_SAMPLES:]
        if float(sample.get("ts", 0.0)) >= cutoff
    ]
    samples.append(
        {
            "ts": timestamp,
            "model": _clean_text(model, max_length=96),
            "latency_ms": max(0.0, float(latency_ms)),
            "success": bool(success),
        }
    )


def get_provider_health_summary(now: float | None = None) -> dict[str, Any]:
    timestamp = time.time() if now is None else now
    cutoff = timestamp - _PROVIDER_HEALTH_WINDOW_SECONDS
    providers: dict[str, Any] = {}
    # Surface every provider that has an open/half-open circuit even if it has
    # no recent health samples (e.g. it failed and is now being skipped).
    tracked_providers = set(_provider_health_samples) | set(_provider_open_until)
    for provider in tracked_providers:
        raw_samples = _provider_health_samples.get(provider, [])
        samples = [
            sample
            for sample in raw_samples[-_PROVIDER_HEALTH_MAX_SAMPLES:]
            if float(sample.get("ts", 0.0)) >= cutoff
        ]
        raw_samples[:] = samples
        latencies = sorted(
            float(sample.get("latency_ms", 0.0))
            for sample in samples
            if isinstance(sample.get("latency_ms"), (int, float))
        )
        error_count = sum(1 for sample in samples if not bool(sample.get("success", False)))
        model_counts: dict[str, int] = {}
        for sample in samples:
            model_name = str(sample.get("model") or "unknown")
            model_counts[model_name] = model_counts.get(model_name, 0) + 1
        p95_index = min(len(latencies) - 1, int(len(latencies) * 0.95)) if latencies else 0
        providers[provider] = {
            "call_count": len(samples),
            "error_count": error_count,
            "success_rate": round((len(samples) - error_count) / len(samples), 4)
            if samples
            else None,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
            "p95_latency_ms": round(latencies[p95_index], 2) if latencies else None,
            "models": model_counts,
            "circuit_state": get_circuit_state(provider, now=timestamp),
            "consecutive_failures": _provider_failures.get(_normalize_provider(provider), 0),
        }
    return {
        "schema_version": "provider_health.v2",
        "window_seconds": int(_PROVIDER_HEALTH_WINDOW_SECONDS),
        "providers": providers,
        "generated_at": datetime.now(UTC).isoformat(),
    }

