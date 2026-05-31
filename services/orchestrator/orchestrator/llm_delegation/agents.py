from __future__ import annotations

import logging
from typing import Any

from ..agent_integrations import build_agent_integration_record
from ..agent_personas import build_agent_system_prompt
from ..agent_registry import AGENT_REGISTRY, AgentDefinition
from ..mission_flow import CEO_AGENT_ID
from .text import _clean_text

LOGGER = logging.getLogger(__name__)

def _system_prompt_for_agent(agent_id: str) -> str | None:
    """Return a persona-grounded system prompt for an agent."""
    normalized_agent_id = _clean_text(agent_id, max_length=32).upper()
    try:
        agent = next(
            (
                candidate
                for candidate in AGENT_REGISTRY
                if candidate.agent_id == normalized_agent_id
            ),
            None,
        )
        if agent is None:
            return None
        return build_agent_system_prompt(agent)
    except Exception:
        LOGGER.warning("failed to build system prompt for %s", normalized_agent_id, exc_info=True)
        return None


def _resolve_agent(agent_id: str | None) -> AgentDefinition:
    normalized = str(agent_id or "").strip().upper()
    if normalized:
        for agent in AGENT_REGISTRY:
            if agent.agent_id == normalized:
                return agent
    return next(agent for agent in AGENT_REGISTRY if agent.agent_id == CEO_AGENT_ID)


def _agent_recommendation(agent_id: str | None) -> dict[str, Any]:
    agent = _resolve_agent(agent_id)
    recommendation = dict(build_agent_integration_record(agent)["llm_recommendation"])
    recommendation["agent_id"] = agent.agent_id
    return recommendation


def _ceo_recommendation() -> dict[str, Any]:
    return _agent_recommendation(CEO_AGENT_ID)


def _pm_recommendation() -> dict[str, Any]:
    return _agent_recommendation("AGENT-01-PM")

