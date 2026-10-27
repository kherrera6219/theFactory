"""Canonical taxonomy and routing definitions for theFactory (Holy Grail Refinery).

This module is the single source of truth for:
1. Supported programming languages and their canonical string keys.
2. Paradigm pods (Dynamic, Systems, Enterprise, Mathematical & Functional).
3. Pod managers and specialist agent IDs.
4. Language-to-pod mappings and validation utilities.
"""

from __future__ import annotations

from enum import Enum
from typing import Final


class ParadigmPod(str, Enum):
    """The four paradigm pods governing the 20 routed languages."""

    POD_A = "pod_a"  # Dynamic / Web
    POD_B = "pod_b"  # Systems
    POD_C = "pod_c"  # Enterprise / Managed
    POD_D = "pod_d"  # Mathematical & Functional


class SupportedLanguage(str, Enum):
    """The 20 canonically supported target languages."""

    # Pod A (Dynamic)
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUBY = "ruby"
    PHP = "php"

    # Pod B (Systems)
    C = "c"
    CPP = "cpp"
    RUST = "rust"
    GO = "go"
    ZIG = "zig"

    # Pod C (Enterprise)
    JAVA = "java"
    CSHARP = "csharp"
    SCALA = "scala"
    KOTLIN = "kotlin"

    # Pod D (Mathematical & Functional)
    R = "r"
    MATLAB = "matlab"
    JULIA = "julia"
    MATHEMATICA = "mathematica"
    HASKELL = "haskell"
    OCAML = "ocaml"


POD_MANAGER_MAP: Final[dict[str, str]] = {
    "pod_a": "AGENT-03-POD-A-DYNAMIC-MGR",
    "pod_b": "AGENT-04-POD-B-SYSTEMS-MGR",
    "pod_c": "AGENT-05-POD-C-ENTERPRISE-MGR",
    "pod_d": "AGENT-06-POD-D-MATH-MGR",
}

LANGUAGE_TO_POD_MAP: Final[dict[SupportedLanguage, ParadigmPod]] = {
    # Pod A
    SupportedLanguage.PYTHON: ParadigmPod.POD_A,
    SupportedLanguage.JAVASCRIPT: ParadigmPod.POD_A,
    SupportedLanguage.TYPESCRIPT: ParadigmPod.POD_A,
    SupportedLanguage.RUBY: ParadigmPod.POD_A,
    SupportedLanguage.PHP: ParadigmPod.POD_A,
    # Pod B
    SupportedLanguage.C: ParadigmPod.POD_B,
    SupportedLanguage.CPP: ParadigmPod.POD_B,
    SupportedLanguage.RUST: ParadigmPod.POD_B,
    SupportedLanguage.GO: ParadigmPod.POD_B,
    SupportedLanguage.ZIG: ParadigmPod.POD_B,
    # Pod C
    SupportedLanguage.JAVA: ParadigmPod.POD_C,
    SupportedLanguage.CSHARP: ParadigmPod.POD_C,
    SupportedLanguage.SCALA: ParadigmPod.POD_C,
    SupportedLanguage.KOTLIN: ParadigmPod.POD_C,
    # Pod D
    SupportedLanguage.R: ParadigmPod.POD_D,
    SupportedLanguage.MATLAB: ParadigmPod.POD_D,
    SupportedLanguage.JULIA: ParadigmPod.POD_D,
    SupportedLanguage.MATHEMATICA: ParadigmPod.POD_D,
    SupportedLanguage.HASKELL: ParadigmPod.POD_D,
    SupportedLanguage.OCAML: ParadigmPod.POD_D,
}

ALL_SUPPORTED_LANGUAGES: Final[frozenset[str]] = frozenset(
    lang.value for lang in SupportedLanguage
)


def get_pod_for_language(language: str | SupportedLanguage | None) -> str | None:
    """Return the canonical pod identifier (e.g. 'pod_a') for a given language."""
    if not language:
        return None
    normalized = str(language).strip().lower()
    try:
        lang_enum = SupportedLanguage(normalized)
        return LANGUAGE_TO_POD_MAP[lang_enum].value
    except (ValueError, KeyError):
        return None


def get_pod_manager_for_language(language: str | SupportedLanguage | None) -> str | None:
    """Return the pod manager agent ID for a given language, or None if unknown."""
    pod = get_pod_for_language(language)
    if not pod:
        return None
    return POD_MANAGER_MAP.get(pod)


def is_language_supported(language: str | None) -> bool:
    """Return True if the language is in the canonical 20-language set."""
    if not language:
        return False
    return str(language).strip().lower() in ALL_SUPPORTED_LANGUAGES
