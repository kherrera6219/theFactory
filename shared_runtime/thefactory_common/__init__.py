"""theFactory common runtime definitions, canonical taxonomy, and distributed tracing."""

from __future__ import annotations

from .taxonomy import (
    ALL_SUPPORTED_LANGUAGES,
    LANGUAGE_TO_POD_MAP,
    POD_MANAGER_MAP,
    ParadigmPod,
    SupportedLanguage,
    get_pod_for_language,
    get_pod_manager_for_language,
    is_language_supported,
)
from .tracing import (
    extract_envelope_trace_context,
    extract_w3c_trace_context,
    inject_envelope_trace_context,
    inject_w3c_trace_context,
)

__all__ = [
    "ALL_SUPPORTED_LANGUAGES",
    "LANGUAGE_TO_POD_MAP",
    "POD_MANAGER_MAP",
    "ParadigmPod",
    "SupportedLanguage",
    "extract_envelope_trace_context",
    "extract_w3c_trace_context",
    "get_pod_for_language",
    "get_pod_manager_for_language",
    "inject_envelope_trace_context",
    "inject_w3c_trace_context",
    "is_language_supported",
]
