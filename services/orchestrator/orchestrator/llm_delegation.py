from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

from .agent_integrations import build_agent_integration_record
from .agent_registry import AGENT_REGISTRY, AgentDefinition
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

# Maximum bytes allowed for serialized mission context embedded in prompts.
# Prevents oversized or adversarially crafted context from consuming the model
# context window or injecting rogue instructions.
_PROMPT_CONTEXT_MAX_BYTES = 4096


def _safe_context_json(mission_context: dict[str, Any]) -> str:
    """Serialize mission_context for prompt embedding with a hard size cap.

    Only the fields needed for routing are kept; all others are dropped before
    serialisation so that user-controlled content (e.g. ``prompt``,
    ``source_code``) cannot inject instructions into the LLM prompt.
    """
    safe_fields = {
        "mission_id",
        "requested_target_language",
        "routing_version",
        "routing_enforced",
        "intake_agent_id",
        "executive_agent_id",
        "expected_pod_manager_agent_id",
        "expected_specialist_agent_id",
        "selected_agent_id",
        "agent_id",
    }
    filtered: dict[str, Any] = {
        k: v for k, v in mission_context.items() if k in safe_fields
    }
    serialized = json.dumps(filtered, sort_keys=True)
    if len(serialized.encode("utf-8")) > _PROMPT_CONTEXT_MAX_BYTES:
        # Truncate to safe length rather than embedding unbounded data.
        serialized = serialized.encode("utf-8")[:_PROMPT_CONTEXT_MAX_BYTES].decode(
            "utf-8", errors="replace"
        ) + "...[truncated]"
    return serialized


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


def _normalize_text_list(value: Any, *, limit: int = 5) -> list[str]:
    items: list[str] = []
    if isinstance(value, str) and value.strip():
        items = [value.strip()]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    return items[:limit]


async def _call_openai(
    model: str,
    prompt: str,
    *,
    call_context: str,
) -> dict[str, Any] | None:
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
        LOGGER.warning("%s openai request failed: %s", call_context, exc)
        return None
    if response.status_code >= 400:
        LOGGER.warning("%s openai status=%s", call_context, response.status_code)
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    return _extract_decision_payload(_extract_openai_text(body))


async def _call_anthropic(
    model: str,
    prompt: str,
    *,
    call_context: str,
) -> dict[str, Any] | None:
    if not ANTHROPIC_API_KEY:
        return None
    payload = {
        "model": model,
        "max_tokens": 900,
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
        LOGGER.warning("%s anthropic request failed: %s", call_context, exc)
        return None
    if response.status_code >= 400:
        LOGGER.warning("%s anthropic status=%s", call_context, response.status_code)
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    return _extract_decision_payload(_extract_anthropic_text(body))


async def _call_gemini(
    model: str,
    prompt: str,
    *,
    call_context: str,
) -> dict[str, Any] | None:
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
        LOGGER.warning("%s gemini request failed: %s", call_context, exc)
        return None
    if response.status_code >= 400:
        LOGGER.warning("%s gemini status=%s", call_context, response.status_code)
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    return _extract_decision_payload(_extract_gemini_text(body))


async def _call_provider(
    *,
    provider: str,
    model: str,
    prompt: str,
    call_context: str,
) -> dict[str, Any] | None:
    normalized = provider.strip().lower()
    if normalized == "anthropic":
        return await _call_anthropic(model, prompt, call_context=call_context)
    if normalized == "gemini":
        return await _call_gemini(model, prompt, call_context=call_context)
    return await _call_openai(model, prompt, call_context=call_context)


async def _call_with_recommendation(
    *,
    recommendation: dict[str, Any],
    prompt: str,
    call_context: str,
) -> tuple[dict[str, Any] | None, str, str, str]:
    provider = str(recommendation.get("provider", "openai")).strip().lower()
    model = str(recommendation.get("model", "gpt-5.2-pro")).strip()

    parsed = await _call_provider(
        provider=provider,
        model=model,
        prompt=prompt,
        call_context=call_context,
    )
    if isinstance(parsed, dict):
        return parsed, provider, model, "primary"

    fallback_provider = str(recommendation.get("fallback_provider", "")).strip().lower()
    fallback_model = str(recommendation.get("fallback_model", "")).strip()
    if not fallback_provider or not fallback_model:
        return None, provider, model, "primary"

    if fallback_provider == provider and fallback_model == model:
        return None, provider, model, "primary"

    fallback = await _call_provider(
        provider=fallback_provider,
        model=fallback_model,
        prompt=prompt,
        call_context=f"{call_context} (fallback)",
    )
    if isinstance(fallback, dict):
        return fallback, fallback_provider, fallback_model, "fallback"
    return None, provider, model, "primary"


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


def _fallback_pod_manager_delegation(
    *,
    pod_manager_agent_id: str,
    specialist_agent_id: str,
    mission_context: dict[str, Any],
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "pod_manager_agent_id": pod_manager_agent_id,
        "specialist_agent_id": specialist_agent_id,
        "rationale": "Deterministic pod-manager fallback delegation based on language mapping.",
        "source": "fallback",
        "model_provider": recommendation.get("provider"),
        "model": recommendation.get("model"),
        "mission_context": mission_context,
    }


def _fallback_specialist_plan(
    *,
    specialist_agent_id: str,
    pod_manager_agent_id: str,
    mission_context: dict[str, Any],
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    language = str(mission_context.get("requested_target_language") or "general").strip().lower()
    return {
        "specialist_agent_id": specialist_agent_id,
        "pod_manager_agent_id": pod_manager_agent_id,
        "plan_summary": (
            "Fallback specialist plan generated deterministically from mission metadata "
            "and language routing."
        ),
        "deliverables": [
            f"Produce validated implementation for {language} target.",
            "Publish logicnode evidence and audit artifacts before mission verification.",
        ],
        "risk_notes": [
            "Provider output unavailable; deterministic fallback plan used.",
        ],
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
        f"{_safe_context_json(mission_context)}\n"
        "Valid pod manager ids: AGENT-12-PODA-MGR, AGENT-18-PODB-MGR, "
        "AGENT-24-PODC-MGR, AGENT-30-PODD-MGR."
    )


def _build_pod_manager_prompt(
    *,
    mission_context: dict[str, Any],
    pod_manager_agent_id: str,
    default_specialist_agent_id: str,
    recommended_provider: str,
    recommended_model: str,
) -> str:
    return (
        f"You are {pod_manager_agent_id} (pod manager) in a strict delegation chain.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Return only JSON with keys: specialist_agent_id, rationale.\n"
        f"Default specialist_agent_id: {default_specialist_agent_id}\n"
        "Mission context JSON:\n"
        f"{_safe_context_json(mission_context)}"
    )


def _build_specialist_prompt(
    *,
    mission_context: dict[str, Any],
    specialist_agent_id: str,
    pod_manager_agent_id: str,
    recommended_provider: str,
    recommended_model: str,
) -> str:
    return (
        f"You are {specialist_agent_id}, delegated by {pod_manager_agent_id}.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Return only JSON with keys: plan_summary, deliverables, risk_notes.\n"
        "deliverables and risk_notes must be arrays of short strings.\n"
        "Mission context JSON:\n"
        f"{_safe_context_json(mission_context)}"
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

    parsed, resolved_provider, resolved_model, llm_route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context="ceo delegation",
    )

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
        "llm_route": llm_route,
        "model_provider": resolved_provider,
        "model": resolved_model,
        "mission_context": mission_context,
    }


async def generate_pod_manager_delegation(
    *,
    mission_context: dict[str, Any],
    requested_target_language: str | None,
    pod_manager_agent_id: str,
    default_specialist_agent_id: str | None = None,
) -> dict[str, Any]:
    normalized_pod_manager_agent_id = pod_manager_agent_id.strip().upper()
    fallback_specialist = (
        default_specialist_agent_id.strip().upper()
        if isinstance(default_specialist_agent_id, str) and default_specialist_agent_id.strip()
        else resolve_specialist_agent_id(requested_target_language)
    )

    recommendation = _agent_recommendation(normalized_pod_manager_agent_id)
    provider = str(recommendation.get("provider", "openai")).strip().lower()
    model = str(recommendation.get("model", "gpt-5.2-pro")).strip()
    prompt = _build_pod_manager_prompt(
        mission_context=mission_context,
        pod_manager_agent_id=normalized_pod_manager_agent_id,
        default_specialist_agent_id=fallback_specialist,
        recommended_provider=provider,
        recommended_model=model,
    )

    parsed, resolved_provider, resolved_model, llm_route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context="pod-manager delegation",
    )
    if not isinstance(parsed, dict):
        return _fallback_pod_manager_delegation(
            pod_manager_agent_id=normalized_pod_manager_agent_id,
            specialist_agent_id=fallback_specialist,
            mission_context=mission_context,
            recommendation=recommendation,
        )

    specialist_agent_id = str(parsed.get("specialist_agent_id", "")).strip().upper()
    if not specialist_agent_id:
        specialist_agent_id = fallback_specialist

    return {
        "pod_manager_agent_id": normalized_pod_manager_agent_id,
        "specialist_agent_id": specialist_agent_id,
        "rationale": str(
            parsed.get(
                "rationale",
                "Pod manager confirmed specialist routing from mission context.",
            )
        ),
        "source": "llm",
        "llm_route": llm_route,
        "model_provider": resolved_provider,
        "model": resolved_model,
        "mission_context": mission_context,
    }


async def generate_specialist_plan(
    *,
    mission_context: dict[str, Any],
    requested_target_language: str | None,
    specialist_agent_id: str,
    pod_manager_agent_id: str,
) -> dict[str, Any]:
    normalized_specialist_agent_id = specialist_agent_id.strip().upper()
    if not normalized_specialist_agent_id:
        normalized_specialist_agent_id = resolve_specialist_agent_id(requested_target_language)

    normalized_pod_manager_agent_id = pod_manager_agent_id.strip().upper()
    if not normalized_pod_manager_agent_id:
        normalized_pod_manager_agent_id = resolve_pod_manager_agent_id(requested_target_language)

    recommendation = _agent_recommendation(normalized_specialist_agent_id)
    provider = str(recommendation.get("provider", "openai")).strip().lower()
    model = str(recommendation.get("model", "gpt-5.2-pro")).strip()
    prompt = _build_specialist_prompt(
        mission_context=mission_context,
        specialist_agent_id=normalized_specialist_agent_id,
        pod_manager_agent_id=normalized_pod_manager_agent_id,
        recommended_provider=provider,
        recommended_model=model,
    )

    parsed, resolved_provider, resolved_model, llm_route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context="specialist planning",
    )
    if not isinstance(parsed, dict):
        return _fallback_specialist_plan(
            specialist_agent_id=normalized_specialist_agent_id,
            pod_manager_agent_id=normalized_pod_manager_agent_id,
            mission_context=mission_context,
            recommendation=recommendation,
        )

    plan_summary = str(parsed.get("plan_summary", "")).strip()
    if not plan_summary:
        plan_summary = "Specialist execution plan generated from mission context."

    deliverables = _normalize_text_list(parsed.get("deliverables"), limit=6)
    if not deliverables:
        deliverables = [
            "Produce implementation changes for the assigned mission scope.",
            "Persist logicnode evidence and audit artifacts before completion.",
        ]

    risk_notes = _normalize_text_list(parsed.get("risk_notes"), limit=6)
    if not risk_notes:
        risk_notes = ["No explicit risks returned by model output."]

    return {
        "specialist_agent_id": normalized_specialist_agent_id,
        "pod_manager_agent_id": normalized_pod_manager_agent_id,
        "plan_summary": plan_summary,
        "deliverables": deliverables,
        "risk_notes": risk_notes,
        "source": "llm",
        "llm_route": llm_route,
        "model_provider": resolved_provider,
        "model": resolved_model,
        "mission_context": mission_context,
    }
