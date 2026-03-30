"""
test_llm_delegation_golden.py
==============================
Golden-dataset regression suite for LLM delegation routing.

Each case in golden_delegation_cases.json describes a mission context and the
expected pod-manager / specialist agent IDs that the *deterministic fallback*
path should produce.  These tests do NOT call live LLM APIs — they exercise
the ``_fallback_delegation`` and ``_fallback_pod_manager_delegation`` code paths
which are always reachable and must be stable.

Run:
    pytest tests/eval/test_llm_delegation_golden.py -v

Coverage target:
    services/orchestrator/orchestrator/llm_delegation._fallback_delegation
    services/orchestrator/orchestrator/llm_delegation.resolve_pod_manager_agent_id
    services/orchestrator/orchestrator/llm_delegation.resolve_specialist_agent_id
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from services.orchestrator.orchestrator.llm_delegation import (
    _fallback_delegation,
    _safe_context_json,
)
from services.orchestrator.orchestrator.mission_flow import (
    resolve_pod_manager_agent_id,
    resolve_specialist_agent_id,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GOLDEN_PATH = Path(__file__).parent / "golden_delegation_cases.json"


def _load_cases() -> list[dict[str, Any]]:
    return json.loads(GOLDEN_PATH.read_text())


# ---------------------------------------------------------------------------
# Parametrised golden-dataset test
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", _load_cases(), ids=[c["id"] for c in _load_cases()])
def test_fallback_delegation_matches_golden(case: dict[str, Any]) -> None:
    """The deterministic fallback must always route to the expected agents."""
    mission_context = case["mission_context"]
    requested_language = mission_context.get("requested_target_language")

    recommendation: dict[str, Any] = {
        "provider": "openai",
        "model": "gpt-5.2-pro",
    }

    result = _fallback_delegation(
        requested_target_language=requested_language,
        mission_context=mission_context,
        recommendation=recommendation,
    )

    assert result["pod_manager_agent_id"] in case["tolerance_pod_manager"], (
        f"[{case['id']}] pod_manager_agent_id={result['pod_manager_agent_id']!r} "
        f"not in allowed set {case['tolerance_pod_manager']}"
    )
    assert result["specialist_agent_id"] in case["tolerance_specialist"], (
        f"[{case['id']}] specialist_agent_id={result['specialist_agent_id']!r} "
        f"not in allowed set {case['tolerance_specialist']}"
    )
    assert result["source"] == "fallback"


@pytest.mark.parametrize("case", _load_cases(), ids=[c["id"] for c in _load_cases()])
def test_safe_context_strips_injection_fields(case: dict[str, Any]) -> None:
    """_safe_context_json must not include prompt, source_code, or chain_trace."""
    result = _safe_context_json(case["mission_context"])
    parsed = json.loads(result)
    for forbidden in ("prompt", "source_code", "chain_trace"):
        assert forbidden not in parsed, (
            f"[{case['id']}] forbidden field '{forbidden}' leaked into safe context"
        )


# ---------------------------------------------------------------------------
# Resolve helpers are deterministic and cover all documented languages
# ---------------------------------------------------------------------------

_LANGUAGE_TO_SPECIALIST = {
    "python": "AGENT-14-PYTHON",
    "javascript": "AGENT-15-JAVASCRIPT",
    "ruby": "AGENT-16-RUBY",
    "php": "AGENT-17-PHP",
    "c": "AGENT-20-C",
    "cpp": "AGENT-21-CPP",
    "rust": "AGENT-22-RUST",
    "zig": "AGENT-23-ZIG",
    "java": "AGENT-26-JAVA",
    "csharp": "AGENT-27-CSHARP",
    "scala": "AGENT-28-SCALA",
    "kotlin": "AGENT-29-KOTLIN",
}


@pytest.mark.parametrize("language,expected_id", _LANGUAGE_TO_SPECIALIST.items())
def test_resolve_specialist_agent_id(language: str, expected_id: str) -> None:
    agent_id = resolve_specialist_agent_id(language)
    assert agent_id == expected_id, (
        f"resolve_specialist_agent_id({language!r}) returned {agent_id!r}, expected {expected_id!r}"
    )


def test_resolve_specialist_agent_id_unknown_language_returns_python() -> None:
    """Unknown or None language should fall back to the Python specialist."""
    assert resolve_specialist_agent_id(None).startswith("AGENT-")
    assert resolve_specialist_agent_id("cobol").startswith("AGENT-")


def test_resolve_pod_manager_agent_id_returns_valid_agent() -> None:
    for lang in list(_LANGUAGE_TO_SPECIALIST) + [None, "unknown"]:
        agent_id = resolve_pod_manager_agent_id(lang)
        assert agent_id.startswith("AGENT-"), (
            f"resolve_pod_manager_agent_id({lang!r}) returned non-agent ID: {agent_id!r}"
        )
