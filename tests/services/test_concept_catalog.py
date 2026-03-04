"""Tests for the concept catalog module.

Validates pattern definitions, ID format consistency, and coverage
across all four pod language groups.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

from pod_worker.concept_catalog import (
    LANGUAGE_PATTERNS,
    ConceptPattern,
    all_languages,
    get_patterns,
)


class TestConceptCatalog:
    def test_all_languages_non_empty(self):
        langs = all_languages()
        assert len(langs) >= 15

    def test_pod_a_languages_have_patterns(self):
        for lang in ("python", "javascript", "ruby", "php"):
            patterns = get_patterns(lang)
            assert len(patterns) > 0, f"no patterns for Pod A language: {lang}"

    def test_pod_b_languages_have_patterns(self):
        for lang in ("c", "cpp", "rust"):
            patterns = get_patterns(lang)
            assert len(patterns) > 0, f"no patterns for Pod B language: {lang}"

    def test_pod_c_languages_have_patterns(self):
        for lang in ("java", "csharp", "scala", "kotlin"):
            patterns = get_patterns(lang)
            assert len(patterns) > 0, f"no patterns for Pod C language: {lang}"

    def test_pod_d_languages_have_patterns(self):
        for lang in ("matlab", "r", "julia", "mathematica"):
            patterns = get_patterns(lang)
            assert len(patterns) > 0, f"no patterns for Pod D language: {lang}"

    def test_concept_id_format(self):
        """Every concept_id must match PREFIX-NNN-NNN format."""
        valid_prefixes = {"DYN", "SYS", "ENT", "MATH"}
        id_pattern = re.compile(r"^(DYN|SYS|ENT|MATH)-\d{3}-\d{3}$")

        for lang, patterns in LANGUAGE_PATTERNS.items():
            for pat in patterns:
                assert id_pattern.match(pat.concept_id), (
                    f"bad concept_id '{pat.concept_id}' in language '{lang}'"
                )
                prefix = pat.concept_id.split("-")[0]
                assert prefix in valid_prefixes

    def test_all_patterns_are_valid_regex(self):
        """Every regex in the catalog must compile without error."""
        for lang, patterns in LANGUAGE_PATTERNS.items():
            for pat in patterns:
                try:
                    re.compile(pat.regex, re.IGNORECASE)
                except re.error as exc:
                    pytest.fail(f"invalid regex in {lang}/{pat.concept_id}: {exc}")

    def test_no_empty_fields(self):
        """Every pattern must have all fields populated."""
        for lang, patterns in LANGUAGE_PATTERNS.items():
            for pat in patterns:
                assert pat.concept_id, f"empty concept_id in {lang}"
                assert pat.domain, f"empty domain in {lang}/{pat.concept_id}"
                assert pat.concept, f"empty concept in {lang}/{pat.concept_id}"
                assert pat.intent, f"empty intent in {lang}/{pat.concept_id}"
                assert pat.regex, f"empty regex in {lang}/{pat.concept_id}"

    def test_pod_a_prefix(self):
        """Pod A languages should use DYN- prefix."""
        for lang in ("python", "javascript", "ruby", "php"):
            for pat in get_patterns(lang):
                assert pat.concept_id.startswith("DYN-"), (
                    f"Pod A language '{lang}' has non-DYN concept: {pat.concept_id}"
                )

    def test_pod_b_prefix(self):
        """Pod B languages should use SYS- prefix."""
        for lang in ("c", "cpp", "rust"):
            for pat in get_patterns(lang):
                assert pat.concept_id.startswith("SYS-"), (
                    f"Pod B language '{lang}' has non-SYS concept: {pat.concept_id}"
                )

    def test_pod_c_prefix(self):
        """Pod C languages should use ENT- prefix."""
        for lang in ("java", "csharp", "scala", "kotlin"):
            for pat in get_patterns(lang):
                assert pat.concept_id.startswith("ENT-"), (
                    f"Pod C language '{lang}' has non-ENT concept: {pat.concept_id}"
                )

    def test_pod_d_prefix(self):
        """Pod D languages should use MATH- prefix."""
        for lang in ("matlab", "r", "julia", "mathematica"):
            for pat in get_patterns(lang):
                assert pat.concept_id.startswith("MATH-"), (
                    f"Pod D language '{lang}' has non-MATH concept: {pat.concept_id}"
                )

    def test_typescript_shares_javascript(self):
        """TypeScript should reuse JavaScript patterns."""
        js = get_patterns("javascript")
        ts = get_patterns("typescript")
        assert js == ts

    def test_unknown_language_returns_empty(self):
        assert get_patterns("unknown") == ()
        assert get_patterns("") == ()

    def test_pattern_frozen(self):
        """ConceptPattern should be immutable."""
        pat = ConceptPattern("X-001-001", "test", "test", "test intent", r"\btest\b")
        with pytest.raises(AttributeError):
            pat.concept_id = "Y-001-001"  # type: ignore[misc]
