from __future__ import annotations

import logging
import os
from contextvars import ContextVar
from typing import Any

import httpx

from ..agent_registry import AGENT_REGISTRY
from ..mission_flow import POD_MANAGER_BY_LANGUAGE, SPECIALIST_BY_LANGUAGE

LOGGER = logging.getLogger(__name__)

LLM_SAFETY_BLOCK_ENABLED = (
    os.getenv("LLM_SAFETY_BLOCK_ENABLED", "false").strip().lower()
    in {"1", "true", "yes"}
)

# OWASP LLM01 (Prompt Injection) defense. When enabled, prompts whose injection
# risk meets PROMPT_GUARD_BLOCK_LEVEL are blocked before reaching any provider;
# otherwise the detection is logged and the call proceeds. Default: enabled.
PROMPT_GUARD_BLOCK_ENABLED = (
    os.getenv("PROMPT_GUARD_BLOCK_ENABLED", "true").strip().lower()
    in {"1", "true", "yes"}
)
# Minimum risk level (low < medium < high < critical) that triggers a block.
PROMPT_GUARD_BLOCK_LEVEL = os.getenv("PROMPT_GUARD_BLOCK_LEVEL", "high").strip().lower()

current_mission_id: ContextVar[str | None] = ContextVar("current_mission_id", default=None)
current_settings: ContextVar[Any | None] = ContextVar("current_settings", default=None)
current_agent_id: ContextVar[str | None] = ContextVar("current_agent_id", default=None)
current_vault_secrets: ContextVar[dict[str, str] | None] = ContextVar(
    "current_vault_secrets",
    default=None,
)

# Lazy import to avoid circular — resolved at call time.
def _record_usage_event(  # noqa: PLR0913
    settings, mission_id, agent_id, provider, model, inp, out, succeeded, route
):
    """Fire-and-forget token usage recording. Never raises."""
    if not settings:
        settings = current_settings.get()
    if not mission_id:
        mission_id = current_mission_id.get() or ""
    if not agent_id:
        agent_id = current_agent_id.get() or ""

    # Prometheus token/cost metrics are independent of the per-mission DB
    # ledger and must be recorded even when mission_id is unknown.
    try:
        from .metrics import record_llm_usage as _record_metric_usage  # noqa: PLC0415

        _record_metric_usage(
            provider=provider, model=model,
            input_tokens=int(inp or 0), output_tokens=int(out or 0),
        )
    except Exception:
        pass

    if not mission_id:
        return
    try:
        import asyncio as _asyncio  # noqa: PLC0415

        from ..llm_cost_ledger import record_llm_usage as _record  # noqa: PLC0415
        coro = _record(
            settings=settings, mission_id=mission_id, agent_id=agent_id,
            provider=provider, model=model,
            input_tokens=inp, output_tokens=out,
            call_succeeded=succeeded, routing_source=route,
        )
        try:
            loop = _asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            pass
    except Exception:
        pass


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20"))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1").rstrip("/")
ANTHROPIC_TIMEOUT_SECONDS = float(os.getenv("ANTHROPIC_TIMEOUT_SECONDS", "20"))
ANTHROPIC_VERSION = os.getenv("ANTHROPIC_VERSION", "2023-06-01").strip()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
).rstrip("/")
GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "20"))
# Gemini 3.5+ thinking level: minimal | low | medium | high (default: high).
# Replaces the old integer thinking_budget used in Gemini 2.x/3.0.
_GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "high").strip().lower()
_GEMINI_VALID_THINKING_LEVELS = {"minimal", "low", "medium", "high"}
if _GEMINI_THINKING_LEVEL not in _GEMINI_VALID_THINKING_LEVELS:
    _GEMINI_THINKING_LEVEL = "high"


_VALID_AGENT_IDS = {agent.agent_id for agent in AGENT_REGISTRY}
_VALID_POD_MANAGER_IDS = set(POD_MANAGER_BY_LANGUAGE.values())
_VALID_SPECIALIST_IDS = set(SPECIALIST_BY_LANGUAGE.values())
_PROVIDER_HEALTH_WINDOW_SECONDS = 300.0
_PROVIDER_HEALTH_MAX_SAMPLES = 200

_LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
_LLM_RETRY_BASE_SECONDS = float(os.getenv("LLM_RETRY_BASE_SECONDS", "1.0"))

_RETRYABLE_HTTP_ERRORS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)


# Maximum bytes allowed for serialized mission context embedded in prompts.
# Prevents oversized or adversarially crafted context from consuming the model
# context window or injecting rogue instructions.
_PROMPT_CONTEXT_MAX_BYTES = 4096

