from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

OPTIONAL_ADAPTER_ENABLED = Gauge(
    "orchestrator_optional_adapter_enabled",
    "Whether an optional adapter is enabled in orchestrator settings (1=true, 0=false)",
    ("adapter",),
)
OPTIONAL_ADAPTER_READY = Gauge(
    "orchestrator_optional_adapter_ready",
    "Whether an optional adapter is currently ready (1=true, 0=false)",
    ("adapter",),
)
OPTIONAL_ADAPTER_OPERATIONS_TOTAL = Counter(
    "orchestrator_optional_adapter_operations_total",
    "Total optional adapter operations by operation and result",
    ("adapter", "operation", "status"),
)
OPTIONAL_ADAPTER_OPERATION_LATENCY_SECONDS = Histogram(
    "orchestrator_optional_adapter_operation_latency_seconds",
    "Latency of optional adapter operations",
    ("adapter", "operation"),
)
OPTIONAL_ADAPTER_MIRROR_WRITES_TOTAL = Counter(
    "orchestrator_optional_adapter_mirror_writes_total",
    "Total mirror writes to optional adapters by artifact and result",
    ("adapter", "artifact", "status"),
)
OPTIONAL_ADAPTER_MIRROR_WRITE_LATENCY_SECONDS = Histogram(
    "orchestrator_optional_adapter_mirror_write_latency_seconds",
    "Latency of mirror writes to optional adapters",
    ("adapter", "artifact"),
)
OBJECT_STORAGE_LEGAL_HOLD_FALLBACK_TOTAL = Counter(
    "object_storage_legal_hold_fallback_total",
    "Times a legal-hold write could not apply Object Lock because the bucket "
    "does not support it (the write is refused rather than written unprotected)",
)
OPTIONAL_ADAPTER_OBJECT_LOCK_ENABLED = Gauge(
    "orchestrator_optional_adapter_object_lock_enabled",
    "Whether the adapter's bucket was created with Object Lock enabled (1=true, 0=false). "
    "0 while legal holds are required means every failed-audit artifact is being refused",
    ("adapter",),
)


def set_optional_adapter_enabled(adapter: str, *, enabled: bool) -> None:
    OPTIONAL_ADAPTER_ENABLED.labels(adapter=adapter).set(1.0 if enabled else 0.0)


def set_object_lock_enabled(adapter: str, *, enabled: bool) -> None:
    OPTIONAL_ADAPTER_OBJECT_LOCK_ENABLED.labels(adapter=adapter).set(1.0 if enabled else 0.0)


def set_optional_adapter_ready(adapter: str, *, ready: bool) -> None:
    OPTIONAL_ADAPTER_READY.labels(adapter=adapter).set(1.0 if ready else 0.0)


def observe_optional_adapter_operation(
    *,
    adapter: str,
    operation: str,
    duration_seconds: float,
    success: bool,
) -> None:
    status = "success" if success else "error"
    OPTIONAL_ADAPTER_OPERATIONS_TOTAL.labels(
        adapter=adapter,
        operation=operation,
        status=status,
    ).inc()
    OPTIONAL_ADAPTER_OPERATION_LATENCY_SECONDS.labels(
        adapter=adapter,
        operation=operation,
    ).observe(max(0.0, duration_seconds))


def observe_optional_adapter_mirror_write(
    *,
    adapter: str,
    artifact: str,
    duration_seconds: float,
    success: bool,
) -> None:
    status = "success" if success else "error"
    OPTIONAL_ADAPTER_MIRROR_WRITES_TOTAL.labels(
        adapter=adapter,
        artifact=artifact,
        status=status,
    ).inc()
    OPTIONAL_ADAPTER_MIRROR_WRITE_LATENCY_SECONDS.labels(
        adapter=adapter,
        artifact=artifact,
    ).observe(max(0.0, duration_seconds))
