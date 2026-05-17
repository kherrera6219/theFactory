from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from .agent_integrations import build_agent_integration_record
from .agent_registry import AGENT_REGISTRY, AgentDefinition
from .mission_flow import (
    CEO_AGENT_ID,
    POD_MANAGER_BY_LANGUAGE,
    SPECIALIST_BY_LANGUAGE,
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
_CONTROL_CHAR_PATTERN = re.compile(r"[\u0000-\u001F\u007F]")
_LANGUAGE_PATTERN = re.compile(r"^[a-z0-9#+-]{1,32}$")
_ROUTING_VERSION_PATTERN = re.compile(r"^[a-z0-9._-]{1,32}$")
_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_SECRET_LIKE_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"
)
_VALID_AGENT_IDS = {agent.agent_id for agent in AGENT_REGISTRY}
_VALID_POD_MANAGER_IDS = set(POD_MANAGER_BY_LANGUAGE.values())
_VALID_SPECIALIST_IDS = set(SPECIALIST_BY_LANGUAGE.values())

# Retry configuration for transient LLM API failures.
# Retries apply only to network errors and 5xx responses; 4xx errors are not retried.
_LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
_LLM_RETRY_BASE_SECONDS = float(os.getenv("LLM_RETRY_BASE_SECONDS", "1.0"))

_RETRYABLE_HTTP_ERRORS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)


def _retry_delay_for_response(response: httpx.Response, default_delay: float) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after is None:
        return default_delay
    try:
        parsed_delay = float(retry_after)
    except ValueError:
        return default_delay
    return max(default_delay, parsed_delay)


async def _post_with_retry(
    url: str,
    *,
    json_payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
    call_context: str,
    params: dict[str, str] | None = None,
) -> httpx.Response | None:
    """POST *url* with exponential-backoff retry on transient failures.

    Returns the response on success (any status code), or ``None`` after all
    retry attempts are exhausted.  The caller is responsible for checking the
    status code and treating non-2xx as an error.
    """
    delay = _LLM_RETRY_BASE_SECONDS
    for attempt in range(1, _LLM_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=json_payload, headers=headers, params=params)
            # Retry on 429 and 5xx responses only.
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < _LLM_MAX_RETRIES:
                    retry_delay = _retry_delay_for_response(response, delay)
                    LOGGER.warning(
                        "%s attempt %d/%d returned %s — retrying in %.1fs",
                        call_context,
                        attempt,
                        _LLM_MAX_RETRIES,
                        response.status_code,
                        retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                    delay *= 2
                    continue
            return response
        except _RETRYABLE_HTTP_ERRORS as exc:
            if attempt < _LLM_MAX_RETRIES:
                LOGGER.warning(
                    "%s attempt %d/%d network error (%s) — retrying in %.1fs",
                    call_context, attempt, _LLM_MAX_RETRIES, exc, delay,
                )
                await asyncio.sleep(delay)
                delay *= 2
            else:
                LOGGER.warning("%s all %d attempts failed: %s", call_context, _LLM_MAX_RETRIES, exc)
    return None


# Maximum bytes allowed for serialized mission context embedded in prompts.
# Prevents oversized or adversarially crafted context from consuming the model
# context window or injecting rogue instructions.
_PROMPT_CONTEXT_MAX_BYTES = 4096


def _clean_text(value: Any, *, max_length: int = 160) -> str:
    text = _CONTROL_CHAR_PATTERN.sub(" ", str(value)).strip()
    text = _EMAIL_PATTERN.sub("[redacted-email]", text)
    text = _SECRET_LIKE_PATTERN.sub("[redacted-secret]", text)
    return text[:max_length]


def _sanitize_context_value(key: str, value: Any) -> Any:
    if key == "routing_enforced":
        return bool(value)
    if key == "requested_target_language":
        language = _clean_text(value, max_length=32).lower()
        return language if _LANGUAGE_PATTERN.fullmatch(language) else "general"
    if key == "routing_version":
        version = _clean_text(value, max_length=32).lower()
        return version if _ROUTING_VERSION_PATTERN.fullmatch(version) else "unknown"
    if key in {
        "intake_agent_id",
        "executive_agent_id",
        "expected_pod_manager_agent_id",
        "expected_specialist_agent_id",
        "selected_agent_id",
        "agent_id",
    }:
        candidate = _clean_text(value, max_length=32).upper()
        return candidate if candidate in _VALID_AGENT_IDS else None
    return _clean_text(value, max_length=96)


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
    filtered: dict[str, Any] = {}
    for key in safe_fields:
        if key not in mission_context:
            continue
        sanitized = _sanitize_context_value(key, mission_context.get(key))
        if sanitized is not None:
            filtered[key] = sanitized
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


def _pm_recommendation() -> dict[str, Any]:
    return _agent_recommendation("AGENT-01-PM")


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
        items = [_clean_text(value)]
    elif isinstance(value, list):
        items = [_clean_text(item) for item in value if _clean_text(item)]
    return items[:limit]


def _normalize_agent_choice(raw_value: Any, *, allowed_ids: set[str], fallback: str) -> str:
    candidate = _clean_text(raw_value, max_length=32).upper()
    return candidate if candidate in allowed_ids else fallback


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
    response = await _post_with_retry(
        f"{OPENAI_BASE_URL}/responses",
        json_payload=payload,
        headers=headers,
        timeout=OPENAI_TIMEOUT_SECONDS,
        call_context=f"{call_context} openai",
    )
    if response is None:
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
    response = await _post_with_retry(
        f"{ANTHROPIC_BASE_URL}/messages",
        json_payload=payload,
        headers=headers,
        timeout=ANTHROPIC_TIMEOUT_SECONDS,
        call_context=f"{call_context} anthropic",
    )
    if response is None:
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
    response = await _post_with_retry(
        f"{GEMINI_BASE_URL}/models/{model}:generateContent",
        json_payload=payload,
        headers={"content-type": "application/json"},
        timeout=GEMINI_TIMEOUT_SECONDS,
        call_context=f"{call_context} gemini",
        params={"key": GEMINI_API_KEY},
    )
    if response is None:
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
    model = str(recommendation.get("model", "gpt-5.5")).strip()

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


def _build_mission_contract_prompt(
    *,
    mission_context: dict[str, Any],
    prompt: str,
    mission_type: str,
    output_mode: str,
    requested_target_language: str | None,
    ceo_delegation: dict[str, Any],
    recommended_provider: str,
    recommended_model: str,
) -> str:
    safe_prompt = _clean_text(prompt, max_length=1200)
    safe_mission_type = _clean_text(mission_type or "BUILD_NEW", max_length=48).upper()
    safe_output_mode = _clean_text(output_mode or "FULL_BUILD", max_length=48).upper()
    safe_language = _clean_text(requested_target_language or "auto", max_length=32).lower()
    safe_delegation = json.dumps(
        {
            "pod_manager_agent_id": ceo_delegation.get("pod_manager_agent_id"),
            "specialist_agent_id": ceo_delegation.get("specialist_agent_id"),
            "source": ceo_delegation.get("source"),
        },
        sort_keys=True,
    )
    feature_contract = mission_context.get("feature_contract")
    feature_summary = ""
    if isinstance(feature_contract, dict):
        feature_summary = json.dumps(
            {
                "title": feature_contract.get("title"),
                "summary": feature_contract.get("summary"),
                "functional_requirements": feature_contract.get("functional_requirements"),
                "acceptance_criteria": feature_contract.get("acceptance_criteria"),
            },
            sort_keys=True,
        )
    return (
        "You are AGENT-02-CEO. Produce the durable Mission Contract for this mission.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Return only JSON. No markdown, prose, or code fences.\n\n"
        f"Mission type: {safe_mission_type}\n"
        f"Output mode: {safe_output_mode}\n"
        f"Requested target language: {safe_language}\n"
        f"CEO delegation JSON: {safe_delegation}\n"
        + (f"PM feature contract JSON: {feature_summary}\n" if feature_summary else "")
        + f"User prompt: {safe_prompt}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "contract_summary": "one sentence describing the requested deliverable",\n'
        '  "mission_type": "BUILD_NEW | IMPORT_MODERNIZE | PORT | DEBUG_REPAIR | ANALYZE_ONLY",\n'
        '  "target_languages": ["language names"],\n'
        '  "output_mode": "FULL_BUILD | ANALYZE_ONLY | PLAN_ONLY | PATCH_PROPOSAL | APPLY_PATCH",\n'
        '  "output_format": "standalone_script | library | service | analysis_report | patch",\n'
        '  "required_domains": ["short domain names"],\n'
        '  "logicnode_requirements": [\n'
        '    {"domain": "domain", "concept": "concept", '
        '"intent": "testable intent", "priority": "HIGH | MEDIUM | LOW"}\n'
        "  ],\n"
        '  "acceptance_criteria": ["testable pass/fail criteria"],\n'
        '  "risk_notes": ["material risks or constraints"]\n'
        "}\n\n"
        "Keep arrays concise. Use 1-12 logicnode requirements and 1-6 acceptance criteria.\n"
        f"Safe mission context: {_safe_context_json(mission_context)}"
    )


def _build_pm_feature_contract_prompt(
    *,
    prompt: str,
    mission_type: str,
    depth_mode: str,
    output_mode: str,
    requested_target_language: str | None,
    recommended_provider: str,
    recommended_model: str,
) -> str:
    safe_prompt = _clean_text(prompt, max_length=1200)
    return (
        "You are AGENT-01-PM. Convert the operator request into a product-level "
        "Feature Contract for a software factory mission.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Return only JSON. No markdown, prose, or code fences.\n\n"
        f"Mission type: {_clean_text(mission_type or 'BUILD_NEW', max_length=48).upper()}\n"
        f"Depth mode: {_clean_text(depth_mode or 'STANDARD', max_length=48).upper()}\n"
        f"Output mode: {_clean_text(output_mode or 'FULL_BUILD', max_length=48).upper()}\n"
        "Requested target language: "
        f"{_clean_text(requested_target_language or 'auto', max_length=32).lower()}\n"
        f"Operator request: {safe_prompt}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "title": "short title",\n'
        '  "summary": "one paragraph",\n'
        '  "functional_requirements": ["specific requirements"],\n'
        '  "non_functional_requirements": ["constraints"],\n'
        '  "acceptance_criteria": ["testable criteria"],\n'
        '  "target_languages": ["language names"],\n'
        '  "estimated_complexity": "low | medium | high | very_high",\n'
        '  "human_approval_required": true,\n'
        '  "risk_notes": ["risks"],\n'
        '  "clarifying_questions": ["questions if needed"]\n'
        "}\n"
    )


def _normalize_pm_feature_contract(
    raw: dict[str, Any],
    *,
    provider: str,
    model: str,
    route: str,
    prompt: str,
    requested_target_language: str | None,
) -> dict[str, Any]:
    complexity = _clean_text(raw.get("estimated_complexity", "medium"), max_length=24).lower()
    if complexity not in {"low", "medium", "high", "very_high"}:
        complexity = "medium"
    human_approval = raw.get("human_approval_required", False)
    if not isinstance(human_approval, bool):
        human_approval = str(human_approval).strip().lower() in {"1", "true", "yes", "on"}
    target_languages = _string_list(raw.get("target_languages"), limit=4, max_length=32)
    if not target_languages and requested_target_language:
        target_languages = [_clean_text(requested_target_language, max_length=32).lower()]
    functional_requirements = _string_list(raw.get("functional_requirements"), limit=8)
    if not functional_requirements:
        functional_requirements = [_clean_text(prompt, max_length=160) or "Complete mission"]
    acceptance_criteria = _string_list(raw.get("acceptance_criteria"), limit=6)
    if not acceptance_criteria:
        acceptance_criteria = ["Mission completes without error."]
    return {
        "schema_version": "feature_contract.v1",
        "title": _clean_text(raw.get("title", "Mission"), max_length=80) or "Mission",
        "summary": _clean_text(raw.get("summary", prompt), max_length=500),
        "functional_requirements": functional_requirements,
        "non_functional_requirements": _string_list(
            raw.get("non_functional_requirements"), limit=4
        ),
        "acceptance_criteria": acceptance_criteria,
        "target_languages": target_languages,
        "estimated_complexity": complexity,
        "human_approval_required": human_approval,
        "risk_notes": _string_list(raw.get("risk_notes"), limit=5),
        "clarifying_questions": _string_list(raw.get("clarifying_questions"), limit=5),
        "source": "llm",
        "llm_route": route,
        "model_provider": provider,
        "model": model,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _fallback_pm_feature_contract(
    *,
    prompt: str,
    mission_type: str,
    requested_target_language: str | None,
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    language = _clean_text(requested_target_language or "", max_length=32).lower()
    return {
        "schema_version": "feature_contract.v1",
        "title": _clean_text(prompt, max_length=80) or "Mission",
        "summary": _clean_text(prompt, max_length=500),
        "functional_requirements": [_clean_text(prompt, max_length=160) or "Complete mission"],
        "non_functional_requirements": [],
        "acceptance_criteria": ["Mission completes without error."],
        "target_languages": [language] if language else [],
        "estimated_complexity": "medium",
        "human_approval_required": str(mission_type).strip().upper()
        in {"IMPORT_MODERNIZE", "PORT", "DEBUG_REPAIR", "SECURITY_HARDEN"},
        "risk_notes": ["Feature contract generated via deterministic fallback."],
        "clarifying_questions": [],
        "source": "fallback",
        "model_provider": recommendation.get("provider"),
        "model": recommendation.get("model"),
        "created_at": datetime.now(UTC).isoformat(),
    }


async def generate_pm_feature_contract(
    *,
    prompt: str,
    mission_type: str,
    depth_mode: str,
    output_mode: str,
    requested_target_language: str | None,
) -> dict[str, Any]:
    recommendation = _pm_recommendation()
    provider = str(recommendation.get("provider", "anthropic")).strip().lower()
    model = str(recommendation.get("model", "claude-sonnet-4-6")).strip()
    pm_prompt = _build_pm_feature_contract_prompt(
        prompt=prompt,
        mission_type=mission_type,
        depth_mode=depth_mode,
        output_mode=output_mode,
        requested_target_language=requested_target_language,
        recommended_provider=provider,
        recommended_model=model,
    )
    parsed, resolved_provider, resolved_model, llm_route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=pm_prompt,
        call_context="pm feature contract",
    )
    if not isinstance(parsed, dict):
        return _fallback_pm_feature_contract(
            prompt=prompt,
            mission_type=mission_type,
            requested_target_language=requested_target_language,
            recommendation=recommendation,
        )
    return _normalize_pm_feature_contract(
        parsed,
        provider=resolved_provider,
        model=resolved_model,
        route=llm_route,
        prompt=prompt,
        requested_target_language=requested_target_language,
    )


def _string_list(value: Any, *, limit: int, max_length: int = 120) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        cleaned
        for item in value[:limit]
        if (cleaned := _clean_text(item, max_length=max_length))
    ]


def _normalize_mission_contract(
    raw: dict[str, Any],
    *,
    provider: str,
    model: str,
    route: str,
    mission_type: str,
    output_mode: str,
    requested_target_language: str | None,
) -> dict[str, Any]:
    valid_priorities = {"HIGH", "MEDIUM", "LOW"}
    valid_output_formats = {"standalone_script", "library", "service", "analysis_report", "patch"}
    normalized_output_format = _clean_text(
        raw.get("output_format", "standalone_script"), max_length=48
    ).lower()
    if normalized_output_format not in valid_output_formats:
        normalized_output_format = "standalone_script"

    requirements: list[dict[str, Any]] = []
    raw_requirements = raw.get("logicnode_requirements")
    if isinstance(raw_requirements, list):
        for item in raw_requirements[:12]:
            if not isinstance(item, dict):
                continue
            priority = _clean_text(item.get("priority", "MEDIUM"), max_length=16).upper()
            if priority not in valid_priorities:
                priority = "MEDIUM"
            requirements.append(
                {
                    "domain": _clean_text(item.get("domain", "generic"), max_length=64)
                    or "generic",
                    "concept": _clean_text(
                        item.get("concept", "primary_operation"), max_length=64
                    )
                    or "primary_operation",
                    "intent": _clean_text(item.get("intent", "Implement requested behavior")),
                    "priority": priority,
                }
            )
    if not requirements:
        requirements = [
            {
                "domain": "generic",
                "concept": "primary_operation",
                "intent": "Implement the requested mission behavior",
                "priority": "HIGH",
            }
        ]

    target_languages = _string_list(raw.get("target_languages"), limit=4, max_length=32)
    if not target_languages and requested_target_language:
        target_languages = [_clean_text(requested_target_language, max_length=32).lower()]

    acceptance_criteria = _string_list(raw.get("acceptance_criteria"), limit=6)
    if not acceptance_criteria:
        acceptance_criteria = ["Mission output satisfies the requested behavior."]

    return {
        "schema_version": "mission_contract.v1",
        "contract_summary": _clean_text(
            raw.get("contract_summary", "Mission contract generated."), max_length=240
        ),
        "mission_type": _clean_text(raw.get("mission_type", mission_type), max_length=48).upper(),
        "target_languages": target_languages,
        "output_mode": _clean_text(raw.get("output_mode", output_mode), max_length=48).upper(),
        "output_format": normalized_output_format,
        "required_domains": _string_list(raw.get("required_domains"), limit=10, max_length=64),
        "logicnode_requirements": requirements,
        "acceptance_criteria": acceptance_criteria,
        "risk_notes": _string_list(raw.get("risk_notes"), limit=5),
        "source": "llm",
        "llm_route": route,
        "model_provider": provider,
        "model": model,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _fallback_mission_contract(
    *,
    prompt: str,
    mission_type: str,
    output_mode: str,
    requested_target_language: str | None,
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    language = _clean_text(requested_target_language or "general", max_length=32).lower()
    return {
        "schema_version": "mission_contract.v1",
        "contract_summary": _clean_text(
            prompt or "Complete the requested mission.",
            max_length=240,
        ),
        "mission_type": _clean_text(mission_type or "BUILD_NEW", max_length=48).upper(),
        "target_languages": [language] if language != "general" else [],
        "output_mode": _clean_text(output_mode or "FULL_BUILD", max_length=48).upper(),
        "output_format": "standalone_script",
        "required_domains": ["generic"],
        "logicnode_requirements": [
            {
                "domain": "generic",
                "concept": "primary_operation",
                "intent": "Implement the requested mission behavior",
                "priority": "HIGH",
            }
        ],
        "acceptance_criteria": ["Mission output satisfies the requested behavior."],
        "risk_notes": ["Mission contract generated via deterministic fallback."],
        "source": "fallback",
        "model_provider": recommendation.get("provider"),
        "model": recommendation.get("model"),
        "created_at": datetime.now(UTC).isoformat(),
    }


def _build_codegen_prompt(
    *,
    mission_context: dict[str, Any],
    mission_contract: dict[str, Any],
    logicnodes: list[dict[str, Any]],
    target_language: str,
    specialist_agent_id: str,
    recommended_provider: str,
    recommended_model: str,
) -> str:
    contract_summary = _clean_text(
        mission_contract.get("contract_summary", "Implement the mission"), max_length=280
    )
    acceptance = "\n".join(
        f"- {_clean_text(item, max_length=140)}"
        for item in (mission_contract.get("acceptance_criteria") or [])[:6]
    ) or "- Satisfy the mission contract."
    requirements = []
    raw_requirements = mission_contract.get("logicnode_requirements")
    if isinstance(raw_requirements, list):
        for item in raw_requirements[:12]:
            if isinstance(item, dict):
                requirements.append(
                    "- "
                    f"{_clean_text(item.get('domain'), max_length=48)}."
                    f"{_clean_text(item.get('concept'), max_length=48)}: "
                    f"{_clean_text(item.get('intent'), max_length=140)}"
                )
    logicnode_lines = []
    for node in logicnodes[:12]:
        if isinstance(node, dict):
            logicnode_lines.append(_clean_text(json.dumps(node, sort_keys=True), max_length=220))
    return (
        f"You are {specialist_agent_id}, a {target_language} specialist.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Generate a single complete source file that satisfies the mission contract.\n"
        "Return only JSON. No markdown, prose, or code fences.\n\n"
        f"Mission: {contract_summary}\n"
        f"Target language: {_clean_text(target_language, max_length=32)}\n"
        f"Acceptance criteria:\n{acceptance}\n\n"
        f"Contract requirements:\n{chr(10).join(requirements) or '- primary_operation'}\n\n"
        f"Extracted logicnode context:\n{chr(10).join(logicnode_lines) or '- none'}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "generated_code": "complete source code string",\n'
        '  "filename": "safe filename",\n'
        '  "language": "target language",\n'
        '  "description": "one sentence",\n'
        '  "dependencies": ["package names"],\n'
        '  "usage_example": "one short usage example"\n'
        "}\n"
        f"Safe mission context: {_safe_context_json(mission_context)}"
    )


def _strip_code_fences(value: str) -> str:
    text = value.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _safe_filename(value: Any, fallback: str) -> str:
    filename = _clean_text(value or fallback, max_length=96)
    filename = filename.replace("\\", "_").replace("/", "_").replace("..", "_").strip()
    return filename or fallback


def _normalize_codegen_result(
    raw: dict[str, Any],
    *,
    specialist_agent_id: str,
    target_language: str,
    provider: str,
    model: str,
    route: str,
) -> dict[str, Any] | None:
    generated_code = _strip_code_fences(str(raw.get("generated_code", "")))
    if len(generated_code.strip()) < 10:
        return None
    language = _clean_text(raw.get("language", target_language), max_length=32).lower()
    filename = _safe_filename(raw.get("filename"), f"generated.{language or 'txt'}")
    return {
        "schema_version": "generated_output.v1",
        "generated_code": generated_code,
        "filename": filename,
        "language": language or target_language,
        "description": _clean_text(raw.get("description", "Generated output."), max_length=240),
        "dependencies": _string_list(raw.get("dependencies"), limit=20, max_length=80),
        "usage_example": _clean_text(raw.get("usage_example", ""), max_length=240),
        "source": "llm",
        "specialist_agent_id": specialist_agent_id,
        "llm_route": route,
        "model_provider": provider,
        "model": model,
        "generated_at": datetime.now(UTC).isoformat(),
        "code_length_chars": len(generated_code),
    }


def _fallback_codegen(
    *,
    specialist_agent_id: str,
    target_language: str,
    contract_summary: str,
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    language = _clean_text(target_language or "text", max_length=32).lower()
    return {
        "schema_version": "generated_output.v1",
        "generated_code": "",
        "filename": f"generated.{language or 'txt'}",
        "language": language,
        "description": "Code generation unavailable; provider output was not available.",
        "dependencies": [],
        "usage_example": "",
        "source": "fallback",
        "specialist_agent_id": specialist_agent_id,
        "model_provider": recommendation.get("provider"),
        "model": recommendation.get("model"),
        "generated_at": datetime.now(UTC).isoformat(),
        "code_length_chars": 0,
        "risk_notes": [
            _clean_text(contract_summary, max_length=160),
            "Fallback output is not a generated software deliverable.",
        ],
    }


def _priority(value: Any) -> str:
    priority = _clean_text(value or "MEDIUM", max_length=16).upper()
    if priority not in {"HIGH", "MEDIUM", "LOW"}:
        return "MEDIUM"
    return priority


def _cluster_id(index: int, domain: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", domain.strip().lower()).strip("-")
    return f"cluster-{index:02d}-{slug or 'general'}"


def _build_logic_clusters_prompt(
    *,
    mission_context: dict[str, Any],
    mission_contract: dict[str, Any],
    ceo_delegation: dict[str, Any],
    requested_target_language: str | None,
    recommended_provider: str,
    recommended_model: str,
) -> str:
    safe_language = _clean_text(requested_target_language or "auto", max_length=32).lower()
    contract_summary = _clean_text(
        mission_contract.get("contract_summary", "mission"), max_length=500
    )
    required_domains = _string_list(mission_contract.get("required_domains"), limit=10)
    requirements = mission_contract.get("logicnode_requirements")
    safe_requirements = requirements if isinstance(requirements, list) else []
    safe_delegation = json.dumps(
        {
            "pod_manager_agent_id": ceo_delegation.get("pod_manager_agent_id"),
            "specialist_agent_id": ceo_delegation.get("specialist_agent_id"),
        },
        sort_keys=True,
    )
    return (
        "You are AGENT-02-CEO. Decompose this mission contract into logic clusters.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Return only JSON. No markdown, prose, or code fences.\n\n"
        f"Requested target language: {safe_language}\n"
        f"Mission summary: {contract_summary}\n"
        f"Required domains: {json.dumps(required_domains)}\n"
        f"CEO delegation JSON: {safe_delegation}\n"
        f"Logicnode requirements JSON: {json.dumps(safe_requirements, sort_keys=True)}\n\n"
        "Required JSON shape:\n"
        "{\n"
        '  "clusters": [\n'
        "    {\n"
        '      "title": "short cluster title",\n'
        '      "domain": "domain",\n'
        '      "priority": "HIGH | MEDIUM | LOW",\n'
        '      "pod_manager_agent_id": "assigned pod manager id",\n'
        '      "specialist_agent_id": "assigned specialist id",\n'
        '      "requirement_refs": ["requirement concept names"],\n'
        '      "rationale": "why this work is grouped together"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Return 1-8 clusters. Keep clusters coarse enough for pod-level ownership.\n"
        f"Safe mission context: {_safe_context_json(mission_context)}"
    )


def _normalize_logic_clusters(
    raw: dict[str, Any],
    *,
    provider: str,
    model: str,
    route: str,
    mission_contract: dict[str, Any],
    requested_target_language: str | None,
    ceo_delegation: dict[str, Any],
) -> dict[str, Any]:
    default_pod_manager = _normalize_agent_choice(
        ceo_delegation.get("pod_manager_agent_id"),
        allowed_ids=_VALID_POD_MANAGER_IDS,
        fallback=resolve_pod_manager_agent_id(requested_target_language),
    )
    default_specialist = _normalize_agent_choice(
        ceo_delegation.get("specialist_agent_id"),
        allowed_ids=_VALID_SPECIALIST_IDS,
        fallback=resolve_specialist_agent_id(requested_target_language),
    )
    raw_clusters = raw.get("clusters")
    if not isinstance(raw_clusters, list):
        raw_clusters = []
    clusters: list[dict[str, Any]] = []
    for item in raw_clusters[:8]:
        if not isinstance(item, dict):
            continue
        domain = _clean_text(item.get("domain") or item.get("title") or "general", max_length=64)
        cluster_index = len(clusters) + 1
        clusters.append(
            {
                "cluster_id": _clean_text(
                    item.get("cluster_id") or _cluster_id(cluster_index, domain),
                    max_length=80,
                ),
                "title": _clean_text(item.get("title") or domain, max_length=96),
                "domain": domain,
                "priority": _priority(item.get("priority")),
                "pod_manager_agent_id": _normalize_agent_choice(
                    item.get("pod_manager_agent_id"),
                    allowed_ids=_VALID_POD_MANAGER_IDS,
                    fallback=default_pod_manager,
                ),
                "specialist_agent_id": _normalize_agent_choice(
                    item.get("specialist_agent_id"),
                    allowed_ids=_VALID_SPECIALIST_IDS,
                    fallback=default_specialist,
                ),
                "requirement_refs": _string_list(item.get("requirement_refs"), limit=8),
                "rationale": _clean_text(
                    item.get("rationale") or "Grouped by related domain scope.",
                    max_length=240,
                ),
            }
        )
    if not clusters:
        return _fallback_logic_clusters(
            mission_contract=mission_contract,
            requested_target_language=requested_target_language,
            ceo_delegation=ceo_delegation,
            recommendation={"provider": provider, "model": model},
        )
    return {
        "schema_version": "logic_clusters.v1",
        "clusters": clusters,
        "source": "llm",
        "llm_route": route,
        "model_provider": provider,
        "model": model,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _fallback_logic_clusters(
    *,
    mission_contract: dict[str, Any],
    requested_target_language: str | None,
    ceo_delegation: dict[str, Any],
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    pod_manager_agent_id = _normalize_agent_choice(
        ceo_delegation.get("pod_manager_agent_id"),
        allowed_ids=_VALID_POD_MANAGER_IDS,
        fallback=resolve_pod_manager_agent_id(requested_target_language),
    )
    specialist_agent_id = _normalize_agent_choice(
        ceo_delegation.get("specialist_agent_id"),
        allowed_ids=_VALID_SPECIALIST_IDS,
        fallback=resolve_specialist_agent_id(requested_target_language),
    )
    requirements = mission_contract.get("logicnode_requirements")
    requirement_items = (
        [item for item in requirements if isinstance(item, dict)]
        if isinstance(requirements, list)
        else []
    )
    domains = _string_list(mission_contract.get("required_domains"), limit=8)
    if not domains:
        domains = [
            _clean_text(item.get("domain") or "general", max_length=64)
            for item in requirement_items[:8]
        ]
    if not domains:
        domains = ["general"]
    seen: set[str] = set()
    clusters: list[dict[str, Any]] = []
    for domain in domains:
        normalized_domain = domain or "general"
        key = normalized_domain.lower()
        if key in seen:
            continue
        seen.add(key)
        matching_requirements = [
            _clean_text(
                item.get("concept") or item.get("intent") or normalized_domain,
                max_length=80,
            )
            for item in requirement_items
            if _clean_text(item.get("domain") or "", max_length=64).lower() == key
        ]
        priority = "MEDIUM"
        for item in requirement_items:
            if _clean_text(item.get("domain") or "", max_length=64).lower() == key:
                priority = _priority(item.get("priority"))
                break
        cluster_index = len(clusters) + 1
        clusters.append(
            {
                "cluster_id": _cluster_id(cluster_index, normalized_domain),
                "title": f"{normalized_domain.title()} Cluster",
                "domain": normalized_domain,
                "priority": priority,
                "pod_manager_agent_id": pod_manager_agent_id,
                "specialist_agent_id": specialist_agent_id,
                "requirement_refs": matching_requirements[:8],
                "rationale": "Deterministic cluster from mission contract domain scope.",
            }
        )
    return {
        "schema_version": "logic_clusters.v1",
        "clusters": clusters[:8],
        "source": "fallback",
        "model_provider": recommendation.get("provider"),
        "model": recommendation.get("model"),
        "created_at": datetime.now(UTC).isoformat(),
    }


async def generate_code_from_contract(
    *,
    mission_context: dict[str, Any],
    specialist_agent_id: str,
    mission_contract: dict[str, Any],
    logicnodes: list[dict[str, Any]] | None,
    target_language: str,
) -> dict[str, Any]:
    recommendation = _agent_recommendation(specialist_agent_id)
    provider = str(recommendation.get("provider", "openai")).strip().lower()
    model = str(recommendation.get("model", "gpt-5.3-codex")).strip()
    prompt = _build_codegen_prompt(
        mission_context=mission_context,
        mission_contract=mission_contract,
        logicnodes=logicnodes or [],
        target_language=target_language,
        specialist_agent_id=specialist_agent_id,
        recommended_provider=provider,
        recommended_model=model,
    )
    parsed, resolved_provider, resolved_model, llm_route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context=f"specialist codegen {specialist_agent_id}",
    )
    contract_summary = str(mission_contract.get("contract_summary", "mission"))
    if not isinstance(parsed, dict):
        return _fallback_codegen(
            specialist_agent_id=specialist_agent_id,
            target_language=target_language,
            contract_summary=contract_summary,
            recommendation=recommendation,
        )
    normalized = _normalize_codegen_result(
        parsed,
        specialist_agent_id=specialist_agent_id,
        target_language=target_language,
        provider=resolved_provider,
        model=resolved_model,
        route=llm_route,
    )
    if normalized is None:
        return _fallback_codegen(
            specialist_agent_id=specialist_agent_id,
            target_language=target_language,
            contract_summary=contract_summary,
            recommendation=recommendation,
        )
    return normalized


async def generate_logic_clusters(
    *,
    mission_context: dict[str, Any],
    mission_contract: dict[str, Any],
    requested_target_language: str | None,
    ceo_delegation: dict[str, Any],
) -> dict[str, Any]:
    recommendation = _ceo_recommendation()
    provider = str(recommendation.get("provider", "openai")).strip().lower()
    model = str(recommendation.get("model", "gpt-5.5")).strip()
    prompt = _build_logic_clusters_prompt(
        mission_context=mission_context,
        mission_contract=mission_contract,
        ceo_delegation=ceo_delegation,
        requested_target_language=requested_target_language,
        recommended_provider=provider,
        recommended_model=model,
    )
    parsed, resolved_provider, resolved_model, llm_route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context="logic cluster decomposition",
    )
    if not isinstance(parsed, dict):
        return _fallback_logic_clusters(
            mission_contract=mission_contract,
            requested_target_language=requested_target_language,
            ceo_delegation=ceo_delegation,
            recommendation=recommendation,
        )
    return _normalize_logic_clusters(
        parsed,
        provider=resolved_provider,
        model=resolved_model,
        route=llm_route,
        mission_contract=mission_contract,
        requested_target_language=requested_target_language,
        ceo_delegation=ceo_delegation,
    )


async def generate_mission_contract(
    *,
    mission_context: dict[str, Any],
    prompt: str,
    mission_type: str,
    output_mode: str,
    requested_target_language: str | None,
    ceo_delegation: dict[str, Any],
) -> dict[str, Any]:
    recommendation = _ceo_recommendation()
    provider = str(recommendation.get("provider", "openai")).strip().lower()
    model = str(recommendation.get("model", "gpt-5.5")).strip()
    contract_prompt = _build_mission_contract_prompt(
        mission_context=mission_context,
        prompt=prompt,
        mission_type=mission_type,
        output_mode=output_mode,
        requested_target_language=requested_target_language,
        ceo_delegation=ceo_delegation,
        recommended_provider=provider,
        recommended_model=model,
    )
    parsed, resolved_provider, resolved_model, llm_route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=contract_prompt,
        call_context="mission contract",
    )
    if not isinstance(parsed, dict):
        return _fallback_mission_contract(
            prompt=prompt,
            mission_type=mission_type,
            output_mode=output_mode,
            requested_target_language=requested_target_language,
            recommendation=recommendation,
        )
    return _normalize_mission_contract(
        parsed,
        provider=resolved_provider,
        model=resolved_model,
        route=llm_route,
        mission_type=mission_type,
        output_mode=output_mode,
        requested_target_language=requested_target_language,
    )


async def generate_ceo_delegation(
    *,
    mission_context: dict[str, Any],
    requested_target_language: str | None,
) -> dict[str, Any]:
    recommendation = _ceo_recommendation()
    provider = str(recommendation.get("provider", "openai")).strip().lower()
    model = str(recommendation.get("model", "gpt-5.5")).strip()
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

    pod_manager_fallback = resolve_pod_manager_agent_id(requested_target_language)
    specialist_fallback = resolve_specialist_agent_id(requested_target_language)
    pod_manager_agent_id = _normalize_agent_choice(
        parsed.get("pod_manager_agent_id"),
        allowed_ids=_VALID_POD_MANAGER_IDS,
        fallback=pod_manager_fallback,
    )
    specialist_agent_id = _normalize_agent_choice(
        parsed.get("specialist_agent_id"),
        allowed_ids=_VALID_SPECIALIST_IDS,
        fallback=specialist_fallback,
    )
    return {
        "pod_manager_agent_id": pod_manager_agent_id,
        "specialist_agent_id": specialist_agent_id,
        "rationale": _clean_text(
            parsed.get("rationale", "Delegation synthesized from mission context."),
            max_length=240,
        ),
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
    model = str(recommendation.get("model", "gpt-5.5")).strip()
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

    specialist_agent_id = _normalize_agent_choice(
        parsed.get("specialist_agent_id"),
        allowed_ids=_VALID_SPECIALIST_IDS,
        fallback=fallback_specialist,
    )

    return {
        "pod_manager_agent_id": normalized_pod_manager_agent_id,
        "specialist_agent_id": specialist_agent_id,
        "rationale": _clean_text(
            parsed.get(
                "rationale",
                "Pod manager confirmed specialist routing from mission context.",
            ),
            max_length=240,
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
    model = str(recommendation.get("model", "gpt-5.5")).strip()
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

    plan_summary = _clean_text(parsed.get("plan_summary", ""), max_length=280)
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
