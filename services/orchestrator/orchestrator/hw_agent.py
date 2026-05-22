"""Hardware context injection for performance-sensitive specialist prompts."""

from __future__ import annotations

from typing import Any

_AW1_PROFILE = {
    "cpu": "Intel i7-14700F (20 cores, 28 threads, 5.4GHz boost)",
    "gpu": "NVIDIA RTX 4060 Ti (8GB VRAM, CUDA 12.x)",
    "ram": "64GB DDR5",
    "storage": "1TB NVMe SSD",
    "os": "Windows 11 / WSL2",
    "llm_inference": "off-device via API (no local GPU inference)",
}

_PERFORMANCE_SENSITIVE_TYPES = {
    "BUILD_NEW",
    "PORT",
    "IMPORT_MODERNIZE",
    "REDUCE_DEPENDENCIES",
}
_PERFORMANCE_SENSITIVE_DOMAINS = {
    "numerical_computation",
    "matrix_operations",
    "parallel_processing",
    "gpu_acceleration",
    "memory_management",
    "io_operations",
    "system_calls",
    "crypto",
}
_SYSTEMS_LANGUAGES = {"c", "cpp", "rust", "go", "zig", "julia", "matlab"}


def build_hw_context_block(
    *,
    mission_type: str,
    language: str,
    logic_clusters: dict[str, Any] | None,
) -> str:
    """Return hardware guidance when the mission likely benefits from it."""
    if str(mission_type or "").strip().upper() not in _PERFORMANCE_SENSITIVE_TYPES:
        return ""

    clusters = (logic_clusters or {}).get("clusters") if isinstance(logic_clusters, dict) else []
    cluster_domains = {
        str(cluster.get("domain") or "").strip().lower()
        for cluster in clusters
        if isinstance(cluster, dict)
    }
    has_perf_domain = bool(cluster_domains & _PERFORMANCE_SENSITIVE_DOMAINS)
    is_systems_language = str(language or "").strip().lower() in _SYSTEMS_LANGUAGES
    if not (has_perf_domain or is_systems_language):
        return ""

    return (
        "\nRuntime hardware context (AW1):\n"
        f"  CPU: {_AW1_PROFILE['cpu']}\n"
        f"  GPU: {_AW1_PROFILE['gpu']} - available for CUDA/compute workloads\n"
        f"  RAM: {_AW1_PROFILE['ram']} - large working set is available\n"
        f"  LLM inference: {_AW1_PROFILE['llm_inference']}\n"
        "  Optimize generated code for this hardware profile when relevant.\n"
        "  Avoid assuming constrained memory or single-core execution.\n"
    )
