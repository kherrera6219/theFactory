from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

from .agent_integrations import build_agent_integration_record
from .agent_registry import AGENT_REGISTRY
from .mission_flow import (
    CEO_AGENT_ID,
    resolve_pod_manager_agent_id,
    resolve_specialist_agent_id,
)

LOGGER = logging.getLogger(__name__)

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

JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def _ceo_recommendation() -> dict[str, Any]:
    ceo_agent = next(agent for agent in AGENT_REGISTRY if agent.agent_id == CEO_AGENT_ID)
    return build_agent_integration_record(ceo_agent)["llm_recommendation"]


def _extract_openai_text(payload: dict[str, Any]) -> str | None:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    choices = payload.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
    output = payload.get("output")
    if isinstance(output, list):
        text_chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    text_chunks.append(text.strip())
        if text_chunks:
            return "\n".join(text_chunks)
    return None


def _extract_anthropic_text(payload: dict[str, Any]) -> str | None:
    content = payload.get("content")
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "text":
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    if not parts:
        return None
    return "\n".join(parts)


def _extract_gemini_text(payload: dict[str, Any]) -> str | None:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return None
    lines: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                lines.append(text.strip())
    if not lines:
        return None
    return "\n".join(lines)


def _extract_decision_payload(raw_text: str | None) -> dict[str, Any] | None:
    if not isinstance(raw_text, str) or not raw_text.strip():
        return None
    candidate = raw_text.strip()
    match = JSON_OBJECT_PATTERN.search(candidate)
    if match:
        candidate = match.group(0)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def _call_openai(model: str, prompt: str) -> dict[str, Any] | None:
    if not OPENAI_API_KEY:
        return None
    payload = {
        "model": model,
        "input": prompt,
        "reasoning": {"effort": "medium"},
    }
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    try:
        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{OPENAI_BASE_URL}/responses",
                json=payload,
                headers=headers,
            )
    except Exception as exc:
        LOGGER.warning("ceo delegation openai request failed: %s", exc)
        return None
    if response.status_code >= 400:
        LOGGER.warning("ceo delegation openai status=%s", response.status_code)
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    return _extract_decision_payload(_extract_openai_text(body))


async def _call_anthropic(model: str, prompt: str) -> dict[str, Any] | None:
    if not ANTHROPIC_API_KEY:
        return None
    payload = {
        "model": model,
        "max_tokens": 700,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=ANTHROPIC_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{ANTHROPIC_BASE_URL}/messages",
                json=payload,
                headers=headers,
            )
    except Exception as exc:
        LOGGER.warning("ceo delegation anthropic request failed: %s", exc)
        return None
    if response.status_code >= 400:
        LOGGER.warning("ceo delegation anthropic status=%s", response.status_code)
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    return _extract_decision_payload(_extract_anthropic_text(body))


async def _call_gemini(model: str, prompt: str) -> dict[str, Any] | None:
    if not GEMINI_API_KEY:
        return None
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{GEMINI_BASE_URL}/models/{model}:generateContent",
                params={"key": GEMINI_API_KEY},
                json=payload,
                headers={"content-type": "application/json"},
            )
    except Exception as exc:
        LOGGER.warning("ceo delegation gemini request failed: %s", exc)
        return None
    if response.status_code >= 400:
        LOGGER.warning("ceo delegation gemini status=%s", response.status_code)
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    return _extract_decision_payload(_extract_gemini_text(body))


def _fallback_delegation(
    *,
    requested_target_language: str | None,
    mission_context: dict[str, Any],
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    pod_manager_agent_id = resolve_pod_manager_agent_id(requested_target_language)
    specialist_agent_id = resolve_specialist_agent_id(requested_target_language)
    return {
        "pod_manager_agent_id": pod_manager_agent_id,
        "specialist_agent_id": specialist_agent_id,
        "rationale": "Deterministic fallback delegation based on target language mapping.",
        "source": "fallback",
        "model_provider": recommendation.get("provider"),
        "model": recommendation.get("model"),
        "mission_context": mission_context,
    }


def _build_prompt(
    *,
    mission_context: dict[str, Any],
    recommended_provider: str,
    recommended_model: str,
) -> str:
    return (
        "You are AGENT-02-CEO in a strict chain-of-command runtime.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Return only JSON with keys: pod_manager_agent_id, specialist_agent_id, rationale.\n"
        "Mission context JSON:\n"
        f"{json.dumps(mission_context, sort_keys=True)}\n"
        "Valid pod manager ids: AGENT-12-PODA-MGR, AGENT-18-PODB-MGR, "
        "AGENT-24-PODC-MGR, AGENT-30-PODD-MGR."
    )


async def generate_ceo_delegation(
    *,
    mission_context: dict[str, Any],
    requested_target_language: str | None,
) -> dict[str, Any]:
    recommendation = _ceo_recommendation()
    provider = str(recommendation.get("provider", "openai")).strip().lower()
    model = str(recommendation.get("model", "gpt-5.2-pro")).strip()
    prompt = _build_prompt(
        mission_context=mission_context,
        recommended_provider=provider,
        recommended_model=model,
    )

    parsed: dict[str, Any] | None = None
    if provider == "anthropic":
        parsed = await _call_anthropic(model, prompt)
    elif provider == "gemini":
        parsed = await _call_gemini(model, prompt)
    else:
        parsed = await _call_openai(model, prompt)

    if not isinstance(parsed, dict):
        return _fallback_delegation(
            requested_target_language=requested_target_language,
            mission_context=mission_context,
            recommendation=recommendation,
        )

    pod_manager_agent_id = str(parsed.get("pod_manager_agent_id", "")).strip().upper()
    specialist_agent_id = str(parsed.get("specialist_agent_id", "")).strip().upper()
    if not pod_manager_agent_id:
        pod_manager_agent_id = resolve_pod_manager_agent_id(requested_target_language)
    if not specialist_agent_id:
        specialist_agent_id = resolve_specialist_agent_id(requested_target_language)
    return {
        "pod_manager_agent_id": pod_manager_agent_id,
        "specialist_agent_id": specialist_agent_id,
        "rationale": str(parsed.get("rationale", "Delegation synthesized from mission context.")),
        "source": "llm",
        "model_provider": provider,
        "model": model,
        "mission_context": mission_context,
    }
