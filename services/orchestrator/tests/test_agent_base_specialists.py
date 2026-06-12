"""
test_agent_base_specialists.py

Regression tests for issue #187 — Go, Haskell, OCaml specialists
silently falling back to BaseAgent / SpecialistAgent.

These tests assert that every specialist registered in AGENT_REGISTRY
resolves to a concrete language-specific SpecialistAgent subclass, not
the base SpecialistAgent or BaseAgent directly.
"""
from __future__ import annotations

import pytest
from orchestrator.agent_base import (
    _SPECIALIST_BY_LANGUAGE,
    BaseAgent,
    GoAgent,
    HaskellAgent,
    OcamlAgent,
    SpecialistAgent,
    make_agent,
    make_specialist_for_language,
)
from orchestrator.agent_registry import AGENT_REGISTRY

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_SPECIALIST_DEFS = [
    defn for defn in AGENT_REGISTRY if defn.category == "specialist"
]

_SPECIALIST_PARAMS = [
    pytest.param(defn.agent_id, id=defn.agent_id) for defn in _ALL_SPECIALIST_DEFS
]


# ---------------------------------------------------------------------------
# Core regression: no specialist resolves to bare BaseAgent or SpecialistAgent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("agent_id", _SPECIALIST_PARAMS)
def test_all_specialists_resolve_to_non_base_class(agent_id: str) -> None:
    """
    Every 'specialist' entry in AGENT_REGISTRY must resolve to a *concrete*
    SpecialistAgent subclass — never the bare SpecialistAgent or BaseAgent.

    This is the primary regression guard for issue #187.
    """
    agent = make_agent(agent_id)
    assert isinstance(agent, SpecialistAgent), (
        f"{agent_id} did not resolve to a SpecialistAgent subclass; "
        f"got {type(agent).__name__}"
    )
    assert type(agent) is not SpecialistAgent, (
        f"{agent_id} resolved to the bare SpecialistAgent base class, "
        f"not a concrete language subclass. "
        f"Add it to _SPECIALIST_BY_LANGUAGE in agent_base.py."
    )
    assert type(agent) is not BaseAgent, (
        f"{agent_id} fell back to BaseAgent. "
        f"Check make_agent() dispatch logic."
    )


# ---------------------------------------------------------------------------
# Language key integrity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("agent_id", _SPECIALIST_PARAMS)
def test_specialist_language_key_matches_registry(agent_id: str) -> None:
    """
    The concrete agent's language_key must match the first specialty
    registered in AGENT_REGISTRY for that agent.
    """
    defn = next(d for d in AGENT_REGISTRY if d.agent_id == agent_id)
    expected_language = defn.specialties[0] if defn.specialties else ""
    agent = make_agent(agent_id)
    assert agent.language_key == expected_language, (
        f"{agent_id}: expected language_key={expected_language!r}, "
        f"got {agent.language_key!r}"
    )


# ---------------------------------------------------------------------------
# Extraction guidance must be set
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("agent_id", _SPECIALIST_PARAMS)
def test_specialist_extraction_guidance_is_not_empty(agent_id: str) -> None:
    """
    Every concrete specialist must carry a non-empty extraction_guidance
    string so that audit reports are informative.
    """
    agent = make_agent(agent_id)
    assert agent.extraction_guidance, (
        f"{agent_id} has an empty extraction_guidance string. "
        f"Set it on the concrete class in agent_base.py."
    )
    assert agent.extraction_guidance != "Language-specific intent extraction.", (
        f"{agent_id} is using the SpecialistAgent base-class default for "
        f"extraction_guidance. Override it on the concrete subclass."
    )


# ---------------------------------------------------------------------------
# Explicit named assertions for the three agents called out in issue #187
# ---------------------------------------------------------------------------


def test_go_agent_resolves_correctly() -> None:
    """Agent #36 (GO) must resolve to GoAgent, not BaseAgent or SpecialistAgent."""
    agent = make_agent("AGENT-36-GO")
    assert type(agent) is GoAgent, (
        f"Expected GoAgent, got {type(agent).__name__}"
    )
    assert agent.language_key == "go"
    assert "go" in agent.extraction_guidance.lower() or "goroutine" in agent.extraction_guidance.lower(), (
        "GoAgent extraction_guidance should reference Go-specific concepts."
    )


def test_haskell_agent_resolves_correctly() -> None:
    """Agent #37 (HASKELL) must resolve to HaskellAgent, not BaseAgent or SpecialistAgent."""
    agent = make_agent("AGENT-37-HASKELL")
    assert type(agent) is HaskellAgent, (
        f"Expected HaskellAgent, got {type(agent).__name__}"
    )
    assert agent.language_key == "haskell"
    assert "haskell" in agent.extraction_guidance.lower() or "functional" in agent.extraction_guidance.lower(), (
        "HaskellAgent extraction_guidance should reference Haskell-specific concepts."
    )


def test_ocaml_agent_resolves_correctly() -> None:
    """Agent #38 (OCAML) must resolve to OcamlAgent, not BaseAgent or SpecialistAgent."""
    agent = make_agent("AGENT-38-OCAML")
    assert type(agent) is OcamlAgent, (
        f"Expected OcamlAgent, got {type(agent).__name__}"
    )
    assert agent.language_key == "ocaml"
    assert "ocaml" in agent.extraction_guidance.lower() or "module" in agent.extraction_guidance.lower(), (
        "OcamlAgent extraction_guidance should reference OCaml-specific concepts."
    )


# ---------------------------------------------------------------------------
# make_specialist_for_language() factory path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "language,expected_type",
    [
        ("go", GoAgent),
        ("haskell", HaskellAgent),
        ("ocaml", OcamlAgent),
    ],
)
def test_make_specialist_for_language_go_haskell_ocaml(
    language: str, expected_type: type
) -> None:
    """
    make_specialist_for_language() must return the correct concrete class
    for go, haskell, and ocaml — the three languages called out in #187.
    """
    agent = make_specialist_for_language(language)
    assert agent is not None, (
        f"make_specialist_for_language({language!r}) returned None. "
        f"Ensure a specialist definition with this language exists in AGENT_REGISTRY."
    )
    assert type(agent) is expected_type, (
        f"make_specialist_for_language({language!r}): "
        f"expected {expected_type.__name__}, got {type(agent).__name__}"
    )


# ---------------------------------------------------------------------------
# Dispatch map completeness guard
# ---------------------------------------------------------------------------


def test_all_specialist_language_keys_in_dispatch_map() -> None:
    """
    _SPECIALIST_BY_LANGUAGE must have an entry for every language key
    present in the AGENT_REGISTRY specialist definitions.

    Any missing entry would cause make_agent() to silently fall back to
    the bare SpecialistAgent (the root cause of issue #187).
    """
    missing: list[str] = []
    for defn in _ALL_SPECIALIST_DEFS:
        for language in defn.specialties:
            if language not in _SPECIALIST_BY_LANGUAGE:
                missing.append(f"{defn.agent_id} → language={language!r}")

    assert not missing, (
        "The following specialist languages are missing from "
        "_SPECIALIST_BY_LANGUAGE in agent_base.py:\n"
        + "\n".join(f"  - {entry}" for entry in missing)
        + "\nAdd the missing class(es) and register them in the dispatch map."
    )
