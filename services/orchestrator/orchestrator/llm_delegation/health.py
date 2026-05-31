from __future__ import annotations

import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from .text import _clean_text

_PROVIDER_HEALTH_WINDOW_SECONDS = 300.0
_PROVIDER_HEALTH_MAX_SAMPLES = 200
_provider_health_samples: dict[str, list[dict[str, Any]]] = defaultdict(list)

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
    for provider, raw_samples in list(_provider_health_samples.items()):
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
        }
    return {
        "schema_version": "provider_health.v1",
        "window_seconds": int(_PROVIDER_HEALTH_WINDOW_SECONDS),
        "providers": providers,
        "generated_at": datetime.now(UTC).isoformat(),
    }

