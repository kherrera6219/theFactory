"""
test_generated_code_sanitizer.py
================================
Regression guard for `_clean_code`, the sanitizer used on generated *source
code* fields.

Generated unit tests were stored through `_clean_text`, which replaces every
control character with a space. The newline is a control character, so every
generated test file arrived as one line -- `import inspect import pytest from
sum_integers import sum_integers ...` -- and Python could not import any of
them. Missions still reported COMPLETE, because a test that cannot load looks
much like a test that failed on its own merits.

Coverage target: llm_delegation.text._clean_code
"""

from __future__ import annotations

import ast

from services.orchestrator.orchestrator.llm_delegation.text import _clean_code, _clean_text

# The exact shape the LLM returns for a Python test module.
SAMPLE_TEST = (
    "import pytest\n"
    "from sum_integers import sum_integers\n"
    "\n"
    "def test_empty_list():\n"
    "    assert sum_integers([]) == 0\n"
    "\n"
    "def test_positive_integers():\n"
    "    assert sum_integers([1, 2, 3, 4]) == 10\n"
)


def test_clean_code_preserves_newlines() -> None:
    assert _clean_code(SAMPLE_TEST).count("\n") >= 6


def test_clean_code_output_is_parseable_python() -> None:
    """The regression in one assertion: the result must actually import."""
    ast.parse(_clean_code(SAMPLE_TEST))


def test_clean_text_would_have_destroyed_it() -> None:
    """Pin the old behaviour so the distinction cannot be quietly undone."""
    flattened = _clean_text(SAMPLE_TEST, max_length=10000)
    assert "\n" not in flattened
    assert "import pytest from sum_integers" in flattened


def test_clean_code_preserves_indentation() -> None:
    out = _clean_code(SAMPLE_TEST)
    assert "    assert sum_integers([]) == 0" in out


def test_clean_code_preserves_tabs() -> None:
    assert _clean_code("a\tb") == "a\tb"


def test_clean_code_still_strips_dangerous_control_characters() -> None:
    for bad in ("\x00", "\x07", "\x1b", "\x7f"):
        out = _clean_code(f"a{bad}b")
        assert bad not in out
        assert out == "a b"


def test_clean_code_still_redacts_secrets_and_emails() -> None:
    assert "[redacted-secret]" in _clean_code('token = "sk-abcdefgh12345678"')
    assert "[redacted-email]" in _clean_code("# owner: dev@example.com")


def test_clean_code_normalizes_crlf() -> None:
    assert _clean_code("a\r\nb") == "a\nb"


def test_clean_code_trims_trailing_whitespace_per_line() -> None:
    assert _clean_code("a   \nb\t\n") == "a\nb"


def test_clean_code_respects_max_length() -> None:
    assert len(_clean_code("x\n" * 500, max_length=40)) <= 40


def test_clean_code_handles_non_string_input() -> None:
    assert _clean_code(None) == "None"
    assert _clean_code(123) == "123"
