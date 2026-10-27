"""Tests verifying alignment of the centralized taxonomy across the system."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared_runtime"))

from thefactory_common.taxonomy import (
    ALL_SUPPORTED_LANGUAGES,
    LANGUAGE_TO_POD_MAP,
    POD_MANAGER_MAP,
    ParadigmPod,
    SupportedLanguage,
    get_pod_for_language,
    get_pod_manager_for_language,
    is_language_supported,
)


def test_taxonomy_contains_exact_20_languages() -> None:
    assert len(SupportedLanguage) == 20
    assert len(ALL_SUPPORTED_LANGUAGES) == 20
    assert len(LANGUAGE_TO_POD_MAP) == 20


def test_all_four_pods_are_represented() -> None:
    pods = {pod for pod in ParadigmPod}
    mapped_pods = set(LANGUAGE_TO_POD_MAP.values())
    assert pods == mapped_pods
    assert len(POD_MANAGER_MAP) == 4


def test_pod_lookup_helpers() -> None:
    assert get_pod_for_language("python") == "pod_a"
    assert get_pod_for_language("RUST") == "pod_b"
    assert get_pod_for_language("csharp") == "pod_c"
    assert get_pod_for_language("haskell") == "pod_d"
    assert get_pod_for_language("unknown_lang") is None
    assert get_pod_for_language(None) is None


def test_pod_manager_lookup_helpers() -> None:
    assert get_pod_manager_for_language("python") == "AGENT-03-POD-A-DYNAMIC-MGR"
    assert get_pod_manager_for_language("c") == "AGENT-04-POD-B-SYSTEMS-MGR"
    assert get_pod_manager_for_language("java") == "AGENT-05-POD-C-ENTERPRISE-MGR"
    assert get_pod_manager_for_language("ocaml") == "AGENT-06-POD-D-MATH-MGR"
    assert get_pod_manager_for_language("invalid") is None


def test_is_language_supported() -> None:
    assert is_language_supported("python") is True
    assert is_language_supported("Go") is True
    assert is_language_supported("COBOL") is False
    assert is_language_supported("") is False
    assert is_language_supported(None) is False
