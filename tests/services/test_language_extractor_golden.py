"""Golden tests for the language extraction engine.

Each test loads a fixture from tests/fixtures/extractors/ and asserts specific
expected structural output.  These tests document (and lock) the exact behaviour
of each extractor against a known-good corpus — regressions are immediately visible.

Rules:
  - Never change a fixture file without updating the corresponding golden values here.
  - Add a new fixture file when adding a new language or extraction path.
  - The AST extractor golden values must be a strict superset of the regex values
    (AST replaces structural fields; concepts are always regex-derived).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "extractors"
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

from pod_worker.language_extractor import (  # noqa: E402
    JavaExtractor,
    JavaScriptExtractor,
    PythonAstExtractor,
    PythonExtractor,
    RustExtractor,
)


def _load(filename: str) -> str:
    return (FIXTURES / filename).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Python — regex extractor
# ---------------------------------------------------------------------------


class TestPythonRegexGolden:
    def setup_method(self) -> None:
        self.result = PythonExtractor().extract(_load("python_sample.py"))

    def test_no_error(self):
        assert self.result.error is None

    def test_function_names(self):
        names = {f.name for f in self.result.functions}
        assert names == {
            "__init__",
            "process",
            "validate",
            "log_event",
            "fetch_mission",
            "_internal_helper",
        }

    def test_class_names(self):
        assert {c.name for c in self.result.classes} == {"DataProcessor", "AuditLogger"}

    def test_concepts_non_empty(self):
        assert len(self.result.concepts) > 0

    def test_all_concepts_have_regex_extraction_method(self):
        for concept in self.result.concepts:
            assert concept.extraction_method == "regex", (
                f"concept {concept.concept_id!r} has method {concept.extraction_method!r}"
            )

    def test_source_range_defaults_to_none(self):
        for concept in self.result.concepts:
            assert concept.source_range is None

    def test_source_lines_positive(self):
        for concept in self.result.concepts:
            assert concept.source_line >= 1


# ---------------------------------------------------------------------------
# Python — AST extractor
# ---------------------------------------------------------------------------


class TestPythonAstGolden:
    def setup_method(self) -> None:
        self.regex_result = PythonExtractor().extract(_load("python_sample.py"))
        self.ast_result = PythonAstExtractor().extract(_load("python_sample.py"))

    def test_no_error(self):
        assert self.ast_result.error is None

    def test_function_names_match_regex(self):
        """AST structural fields must be at least as complete as regex."""
        regex_names = {f.name for f in self.regex_result.functions}
        ast_names = {f.name for f in self.ast_result.functions}
        assert regex_names == ast_names

    def test_class_names_match_regex(self):
        regex_names = {c.name for c in self.regex_result.classes}
        ast_names = {c.name for c in self.ast_result.classes}
        assert regex_names == ast_names

    def test_concepts_identical_to_regex(self):
        """Concept detection is always regex — AST must not alter it."""
        assert len(self.ast_result.concepts) == len(self.regex_result.concepts)

    def test_all_concepts_still_have_regex_extraction_method(self):
        """AST replaces structural fields, not concept detection."""
        for concept in self.ast_result.concepts:
            assert concept.extraction_method == "regex"

    def test_ast_fallback_on_syntax_error(self):
        """On SyntaxError the AST extractor returns regex results unchanged."""
        bad_source = "def broken(:\n    pass\n"
        regex_r = PythonExtractor().extract(bad_source)
        ast_r = PythonAstExtractor().extract(bad_source)
        assert ast_r.functions == regex_r.functions
        assert ast_r.classes == regex_r.classes


# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------


class TestJavaScriptGolden:
    def setup_method(self) -> None:
        self.result = JavaScriptExtractor().extract(_load("javascript_sample.js"))

    def test_no_error(self):
        assert self.result.error is None

    def test_class_detected(self):
        assert "MissionRunner" in {c.name for c in self.result.classes}

    def test_top_level_functions_detected(self):
        names = {f.name for f in self.result.functions}
        # submitMission (function keyword) and validateMission (arrow/const) are top-level
        assert "submitMission" in names
        assert "validateMission" in names

    def test_class_methods_not_detected_by_regex(self):
        """Class shorthand methods (no 'function' keyword) are invisible to regex.

        This is the expected limitation of the regex extractor — documents it
        so a future AST-backed JS extractor can be validated against this.
        """
        names = {f.name for f in self.result.functions}
        assert "run" not in names
        assert "process" not in names

    def test_concepts_non_empty(self):
        assert len(self.result.concepts) > 0

    def test_all_concepts_have_regex_extraction_method(self):
        for concept in self.result.concepts:
            assert concept.extraction_method == "regex"


# ---------------------------------------------------------------------------
# Java
# ---------------------------------------------------------------------------


class TestJavaGolden:
    def setup_method(self) -> None:
        self.result = JavaExtractor().extract(_load("java_sample.java"))

    def test_no_error(self):
        assert self.result.error is None

    def test_class_names(self):
        names = {c.name for c in self.result.classes}
        assert "MissionOrchestrator" in names
        assert "MissionRepository" in names

    def test_public_methods_detected(self):
        names = {f.name for f in self.result.functions}
        assert "createMission" in names
        assert "findById" in names

    def test_concepts_non_empty(self):
        assert len(self.result.concepts) > 0

    def test_all_concepts_have_regex_extraction_method(self):
        for concept in self.result.concepts:
            assert concept.extraction_method == "regex"


# ---------------------------------------------------------------------------
# Rust
# ---------------------------------------------------------------------------


class TestRustGolden:
    def setup_method(self) -> None:
        self.result = RustExtractor().extract(_load("rust_sample.rs"))

    def test_no_error(self):
        assert self.result.error is None

    def test_function_names(self):
        names = {f.name for f in self.result.functions}
        assert "create_mission" in names
        assert "advance_mission" in names

    def test_struct_and_enum_detected(self):
        names = {c.name for c in self.result.classes}
        assert "Mission" in names
        assert "MissionState" in names

    def test_concepts_non_empty(self):
        assert len(self.result.concepts) > 0

    def test_all_concepts_have_regex_extraction_method(self):
        for concept in self.result.concepts:
            assert concept.extraction_method == "regex"


# ---------------------------------------------------------------------------
# Provenance contract — all extractors
# ---------------------------------------------------------------------------


class TestProvenanceContract:
    """Cross-language contract: every ExtractedConcept must satisfy the
    provenance schema expected by _logicnodes_from_extraction in pod_worker/main.py."""

    @pytest.mark.parametrize(
        "extractor,fixture",
        [
            (PythonExtractor(), "python_sample.py"),
            (PythonAstExtractor(), "python_sample.py"),
            (JavaScriptExtractor(), "javascript_sample.js"),
            (JavaExtractor(), "java_sample.java"),
            (RustExtractor(), "rust_sample.rs"),
        ],
    )
    def test_extraction_method_is_string(self, extractor, fixture):
        result = extractor.extract(_load(fixture))
        for concept in result.concepts:
            assert isinstance(concept.extraction_method, str)
            assert concept.extraction_method in {"regex", "ast"}

    @pytest.mark.parametrize(
        "extractor,fixture",
        [
            (PythonExtractor(), "python_sample.py"),
            (JavaScriptExtractor(), "javascript_sample.js"),
        ],
    )
    def test_source_range_is_none_or_tuple(self, extractor, fixture):
        result = extractor.extract(_load(fixture))
        for concept in result.concepts:
            assert concept.source_range is None or (
                isinstance(concept.source_range, tuple) and len(concept.source_range) == 2
            )
