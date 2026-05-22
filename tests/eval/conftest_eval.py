"""conftest_eval.py — Shared fixtures and markers for the eval suite.

Eval tests are offline by default. Tests requiring a live LLM API key
should be marked @pytest.mark.live_llm and are skipped in CI.
"""
import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live_llm: mark test as requiring a live LLM API key (skipped in CI)",
    )
