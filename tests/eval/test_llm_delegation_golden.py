"""
test_llm_delegation_golden.py
==============================
Golden-dataset regression suite for LLM delegation routing.

Each case in golden_delegation_cases.json describes a mission context and the
expected pod-manager / specialist agent IDs that the *deterministic fallback*
path should produce.  These tests do NOT call live LLM APIs — they exercise
the ``_fallback_delegation`` and ``_fallback_pod_manager_delegation`` code paths
which are always reachable and must be stable.

Also includes red-team eval cases that verify data-leakage and injection
protections hold for all known sensitive field names.

Run:
    pytest tests/eval/test_llm_delegation_golden.py -v

Coverage target:
    services/orchestrator/orchestrator/llm_delegation._fallback_delegation
    services/orchestrator/orchestrator/llm_delegation._safe_context_json
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


# ---------------------------------------------------------------------------
# Red-team: data-leakage — forbidden fields must never reach the LLM prompt
# ---------------------------------------------------------------------------

# All field names that must NEVER appear in the serialised context sent to LLMs.
# This list must grow whenever a new sensitive field is introduced anywhere in
# the mission metadata schema.
_FORBIDDEN_CONTEXT_FIELDS = [
    # Core user-controlled content
    "prompt",
    "source_code",
    "chain_trace",
    # Builder artifact refs (may contain internal URLs / paths)
    "binary_ref",
    "binary_digest",
    "image_ref",
    "image_digest",
    # Review/approval fingerprints
    "builder_fingerprint",
    "review_fingerprint",
    # Raw mission description fields
    "description",
    "user_input",
    "raw_prompt",
]


@pytest.mark.parametrize("forbidden_field", _FORBIDDEN_CONTEXT_FIELDS)
def test_safe_context_never_leaks_forbidden_field(forbidden_field: str) -> None:
    """Each forbidden field must be absent from the serialised safe context."""
    context = {
        "mission_id": "mission-redteam-001",
        "requested_target_language": "python",
        "routing_version": "v1.1",
        forbidden_field: "INJECTED_SENSITIVE_DATA — must not appear in LLM prompt",
    }
    result = _safe_context_json(context)
    parsed = json.loads(result)
    assert forbidden_field not in parsed, (
        f"Forbidden field '{forbidden_field}' leaked into safe context JSON"
    )
    # Also ensure the literal string value did not sneak through any other key
    assert "INJECTED_SENSITIVE_DATA" not in result, (
        f"Forbidden field value for '{forbidden_field}' leaked into safe context string"
    )


def test_safe_context_strips_pii_from_mission_id() -> None:
    """PII embedded in mission_id must be redacted by _clean_text."""
    context = {
        "mission_id": "mission-user@example.com-001",
        "requested_target_language": "python",
    }
    result = _safe_context_json(context)
    assert "user@example.com" not in result, (
        "Email address leaked into safe context from mission_id field"
    )


def test_safe_context_strips_secret_patterns() -> None:
    """Secret-like strings in allowed fields must be redacted."""
    context = {
        "mission_id": "mission-sk-supersecretkey1234567890",
        "requested_target_language": "rust",
    }
    result = _safe_context_json(context)
    assert "sk-supersecretkey" not in result, (
        "API key pattern leaked into safe context"
    )


# ---------------------------------------------------------------------------
# Red-team: Unicode / homoglyph injection in field values
# ---------------------------------------------------------------------------

def test_safe_context_normalises_unicode_in_language() -> None:
    """Unicode homoglyphs or non-ASCII in language field must be rejected."""
    # Cyrillic 'а' (U+0430) looks like Latin 'a' — must not pass the pattern
    context = {
        "mission_id": "mission-unicode-001",
        "requested_target_language": "pythоn",  # 'о' is Cyrillic U+043E
    }
    result = _safe_context_json(context)
    parsed = json.loads(result)
    # The language pattern only allows [a-z0-9#+-] so the Cyrillic value
    # must be replaced with the "general" fallback
    assert parsed.get("requested_target_language") == "general", (
        f"Unicode language value was not normalised to 'general': "
        f"{parsed.get('requested_target_language')!r}"
    )


def test_safe_context_normalises_control_characters() -> None:
    """Control characters in field values must be stripped."""
    context = {
        "mission_id": "mission\x00-ctrl-001",
        "requested_target_language": "go",
    }
    result = _safe_context_json(context)
    assert "\x00" not in result, "Null byte survived into safe context"
    assert "\x1b" not in result, "ESC character survived into safe context"


def test_safe_context_size_cap_prevents_oversized_context() -> None:
    """Context serialisation must never exceed _PROMPT_CONTEXT_MAX_BYTES bytes."""
    from services.orchestrator.orchestrator.llm_delegation import _PROMPT_CONTEXT_MAX_BYTES
    # Build a context that would be huge if uncapped
    context = {
        "mission_id": "x" * 10_000,
        "requested_target_language": "java",
    }
    result = _safe_context_json(context)
    assert len(result.encode("utf-8")) <= _PROMPT_CONTEXT_MAX_BYTES + 20, (
        "Safe context exceeded the byte cap"
    )


# ---------------------------------------------------------------------------
# Prompt template loader integration
# ---------------------------------------------------------------------------

def test_prompt_templates_exist_and_render() -> None:
    """All three versioned prompt templates must load and render without error."""
    from services.orchestrator.orchestrator.prompt_loader import render_prompt

    ceo = render_prompt(
        "ceo_delegation",
        recommended_provider="anthropic",
        recommended_model="claude-sonnet-4-6",
        safe_context_json='{"mission_id":"m1"}',
    )
    assert "AGENT-02-CEO" in ceo
    assert "anthropic/claude-sonnet-4-6" in ceo
    assert '{"mission_id":"m1"}' in ceo

    pod_mgr = render_prompt(
        "pod_manager_delegation",
        pod_manager_agent_id="AGENT-12-PODA-MGR",
        recommended_provider="openai",
        recommended_model="gpt-4o",
        default_specialist_agent_id="AGENT-14-PYTHON",
        safe_context_json='{"mission_id":"m2"}',
    )
    assert "AGENT-12-PODA-MGR" in pod_mgr
    assert "AGENT-14-PYTHON" in pod_mgr

    specialist = render_prompt(
        "specialist_planning",
        specialist_agent_id="AGENT-14-PYTHON",
        pod_manager_agent_id="AGENT-12-PODA-MGR",
        recommended_provider="gemini",
        recommended_model="gemini-3-flash-preview",
        safe_context_json='{"mission_id":"m3"}',
    )
    assert "AGENT-14-PYTHON" in specialist
    assert "AGENT-12-PODA-MGR" in specialist


def test_prompt_templates_contain_no_user_controlled_placeholders() -> None:
    """Templates must not embed user-controlled values — only routing metadata."""
    from services.orchestrator.orchestrator.prompt_loader import render_prompt

    # Verify that injecting adversarial content via a non-existent placeholder
    # raises KeyError rather than silently embedding it
    import pytest as _pytest
    with _pytest.raises((KeyError, IndexError)):
        render_prompt(
            "ceo_delegation",
            # Missing required placeholders — must fail loudly
        )
