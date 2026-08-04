"""Every MissionType must have its own CEO routing strategy.

`llm_delegation/prompts.py` builds the CEO delegation prompt from a
`type_strategy` map keyed on mission type, with
`type_strategy.get(mission_type, type_strategy["BUILD_NEW"])` as the fallback.

Until 2026-08-03 that map covered 7 of 10 mission types, so `RUN_QC`,
`ARCHITECTURE_DOCS`, and `SELF_ANALYZE` silently received **BUILD_NEW's**
instruction — "select the pod whose language specialist has the strongest code
generation capability" — for missions that generate no code at all.

Nothing raised, no output looked wrong, and the mission completed. That is
exactly why it survived: the failure mode is quietly suboptimal routing, not an
error anyone sees. Writing this test is the only way the gap stays closed when
an eleventh mission type is added.

Discovered while writing docs/MISSION_TAXONOMY.md (UPG-72).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from orchestrator.llm_delegation.prompts import _build_prompt  # noqa: E402
from orchestrator.models import MissionType  # noqa: E402

# The distinctive phrase from BUILD_NEW's strategy. If a non-BUILD_NEW mission
# type produces it, that type fell through the fallback.
_BUILD_NEW_MARKER = "strongest code generation capability"

# Mission types that legitimately are code generation, so the marker is correct.
_CODEGEN_TYPES = {"BUILD_NEW"}


def _prompt_for(mission_type: str) -> str:
    return _build_prompt(
        mission_context={
            "mission_id": "mission-routing",
            "prompt": "do the thing",
            "mission_type": mission_type,
            "requested_target_language": "python",
        },
        recommended_provider="gemini",
        recommended_model="gemini-3.5-flash",
    )


@pytest.mark.parametrize("mission_type", sorted(m.value for m in MissionType))
def test_every_mission_type_gets_its_own_routing_strategy(mission_type: str) -> None:
    prompt = _prompt_for(mission_type)
    if mission_type in _CODEGEN_TYPES:
        return
    assert _BUILD_NEW_MARKER not in prompt, (
        f"{mission_type} fell through to BUILD_NEW's codegen routing instruction. "
        "Add an entry to type_strategy in llm_delegation/prompts.py — see "
        "docs/MISSION_TAXONOMY.md section 7."
    )


@pytest.mark.parametrize(
    ("mission_type", "expected_phrase"),
    [
        ("RUN_QC", "generates none"),
        ("ARCHITECTURE_DOCS", "not code"),
        ("SELF_ANALYZE", "own codebase"),
    ],
)
def test_the_three_previously_missing_types_route_correctly(
    mission_type: str, expected_phrase: str
) -> None:
    assert expected_phrase in _prompt_for(mission_type)


def test_build_new_still_asks_for_generation_capability() -> None:
    """The fallback's content is right for the type it belongs to."""
    assert _BUILD_NEW_MARKER in _prompt_for("BUILD_NEW")


def test_unrecognised_mission_type_still_produces_a_usable_prompt() -> None:
    """The fallback remains, for forward compatibility with an unknown value —
    it just must not be how a *known* type gets routed."""
    prompt = _prompt_for("SOME_FUTURE_TYPE")
    assert prompt.strip()
