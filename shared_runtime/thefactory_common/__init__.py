"""theFactory common runtime definitions and canonical taxonomy."""

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

__all__ = [
    "ALL_SUPPORTED_LANGUAGES",
    "LANGUAGE_TO_POD_MAP",
    "POD_MANAGER_MAP",
    "ParadigmPod",
    "SupportedLanguage",
    "get_pod_for_language",
    "get_pod_manager_for_language",
    "is_language_supported",
]
