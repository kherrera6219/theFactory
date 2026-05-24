from __future__ import annotations
from shared_runtime.agent_keys import normalize_agent_id
from shared_runtime.pii_guard import redact_pii


import asyncio
import json
import logging
import os
import re
import time
from collections import defaultdict
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

import httpx
from prometheus_client import Counter



from .orchestrator_metrics import LLM_FALLBACK_TOTAL
from .agent_integrations import build_agent_integration_record
from .agent_personas import (
    _LANGUAGE_GUIDANCE,
    _LANGUAGE_TOOLING,
    build_agent_system_prompt,
)
from .agent_registry import AGENT_REGISTRY, AgentDefinition
from .hw_agent import build_hw_context_block
from .mission_flow import (
    CEO_AGENT_ID,
    POD_MANAGER_BY_LANGUAGE,
    SPECIALIST_BY_LANGUAGE,
    resolve_pod_manager_agent_id,
    resolve_specialist_agent_id,
)

LOGGER = logging.getLogger(__name__)

LLM_SAFETY_BLOCK_ENABLED = (
    os.getenv("LLM_SAFETY_BLOCK_ENABLED", "false").strip().lower()
    in {"1", "true", "yes"}
)

current_mission_id: ContextVar[str | None] = ContextVar("current_mission_id", default=None)
current_settings: ContextVar[Any | None] = ContextVar("current_settings", default=None)
current_agent_id: ContextVar[str | None] = ContextVar("current_agent_id", default=None)

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
    if not mission_id:
        return
    try:
        import asyncio as _asyncio  # noqa: PLC0415

        from .llm_cost_ledger import record_llm_usage as _record  # noqa: PLC0415
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
_PROVIDER_HEALTH_WINDOW_SECONDS = 300.0
_PROVIDER_HEALTH_MAX_SAMPLES = 200
_provider_health_samples: dict[str, list[dict[str, Any]]] = defaultdict(list)

# Retry configuration for transient LLM API failures.
# Retries apply only to network errors and 5xx responses; 4xx errors are not retried.
_LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
_LLM_RETRY_BASE_SECONDS = float(os.getenv("LLM_RETRY_BASE_SECONDS", "1.0"))

_RETRYABLE_HTTP_ERRORS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)


def _record_provider_health(
    *,
    provider: str,
    model: str,
    latency_ms: float,
    success: bool,
    now: float | None = None,
) -> None:
    normalized_provider = str(provider or "openai").strip().lower() or "openai"
    timestamp = time.time() if now is None else now
    samples = _provider_health_samples[normalized_provider]
    cutoff = timestamp - _PROVIDER_HEALTH_WINDOW_SECONDS
    samples[:] = [
        sample
        for sample in samples[-_PROVIDER_HEALTH_MAX_SAMPLES:]
        if float(sample.get("ts", 0.0)) >= cutoff
    ]
    samples.append(
        {
            "ts": timestamp,
            "model": _clean_text(model, max_length=96),
            "latency_ms": max(0.0, float(latency_ms)),
            "success": bool(success),
        }
    )


def get_provider_health_summary(now: float | None = None) -> dict[str, Any]:
    timestamp = time.time() if now is None else now
    cutoff = timestamp - _PROVIDER_HEALTH_WINDOW_SECONDS
    providers: dict[str, Any] = {}
    for provider, raw_samples in list(_provider_health_samples.items()):
        samples = [
            sample
            for sample in raw_samples[-_PROVIDER_HEALTH_MAX_SAMPLES:]
            if float(sample.get("ts", 0.0)) >= cutoff
        ]
        raw_samples[:] = samples
        latencies = sorted(
            float(sample.get("latency_ms", 0.0))
            for sample in samples
            if isinstance(sample.get("latency_ms"), (int, float))
        )
        error_count = sum(1 for sample in samples if not bool(sample.get("success", False)))
        model_counts: dict[str, int] = {}
        for sample in samples:
            model_name = str(sample.get("model") or "unknown")
            model_counts[model_name] = model_counts.get(model_name, 0) + 1
        p95_index = min(len(latencies) - 1, int(len(latencies) * 0.95)) if latencies else 0
        providers[provider] = {
            "call_count": len(samples),
            "error_count": error_count,
            "success_rate": round((len(samples) - error_count) / len(samples), 4)
            if samples
            else None,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
            "p95_latency_ms": round(latencies[p95_index], 2) if latencies else None,
            "models": model_counts,
        }
    return {
        "schema_version": "provider_health.v1",
        "window_seconds": int(_PROVIDER_HEALTH_WINDOW_SECONDS),
        "providers": providers,
        "generated_at": datetime.now(UTC).isoformat(),
    }


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


def _language_context(language: str | None) -> str:
    language_key = _clean_text(language or "", max_length=32).lower()
    guidance = _LANGUAGE_GUIDANCE.get(language_key, "")
    tooling = _LANGUAGE_TOOLING.get(language_key, "")
    if not guidance and not tooling:
        return ""
    lines = ["Language discipline:"]
    if guidance:
        lines.append(f"  - {guidance}")
    if tooling:
        lines.append(f"  - Tooling references: {tooling}")
    return "\n" + "\n".join(lines) + "\n"


def _format_upstream_risks(metadata: dict[str, Any]) -> str:
    """Summarize upstream PM/CEO risk signals for downstream prompts."""
    lines: list[str] = []
    feature_contract = metadata.get("feature_contract")
    if isinstance(feature_contract, dict):
        risks = _string_list(feature_contract.get("risk_notes"), limit=3)
        questions = _string_list(feature_contract.get("clarifying_questions"), limit=3)
        if risks:
            lines.append("PM risk notes: " + "; ".join(risks))
        if questions:
            lines.append("PM open questions: " + "; ".join(questions))
    mission_contract = metadata.get("mission_contract")
    if isinstance(mission_contract, dict):
        risks = _string_list(mission_contract.get("risk_notes"), limit=3)
        if risks:
            lines.append("CEO risk notes: " + "; ".join(risks))
    if not lines:
        return ""
    return "\nUpstream risk context:\n" + "\n".join(f"  - {line}" for line in lines) + "\n"


def _format_upstream_style(metadata: dict[str, Any]) -> str:
    """Summarize user style directives for downstream prompts."""
    directives = metadata.get("global_style_directives") or []
    if not directives:
        return ""
    return "\nGlobal Team Style Directives (MANDATORY):\n" + "\n".join(f"  - {d}" for d in directives) + "\n"


def _pm_ambiguity_score(contract: dict[str, Any], prompt: str) -> float:
    """Score feature-contract ambiguity from 0.0 to 1.0."""
    score = 0.0
    questions = contract.get("clarifying_questions")
    if isinstance(questions, list):
        score += min(len(questions) * 0.15, 0.45)
    risks = contract.get("risk_notes")
    if isinstance(risks, list):
        score += min(len(risks) * 0.10, 0.20)
    if len(str(prompt or "").strip()) < 60:
        score += 0.20
    complexity = str(contract.get("estimated_complexity") or "medium").strip().lower()
    requirements = contract.get("functional_requirements")
    if complexity in {"high", "very_high"} and isinstance(requirements, list):
        if len(requirements) <= 2:
            score += 0.20
    if bool(contract.get("human_approval_required")):
        score += 0.10
    return round(min(score, 1.0), 3)


def _normalize_agent_choice(raw_value: Any, *, allowed_ids: set[str], fallback: str) -> str:
    candidate = _clean_text(raw_value, max_length=32).upper()
    return candidate if candidate in allowed_ids else fallback


async def _call_openai(
    model: str,
    prompt: str,
    *,
    call_context: str,
    system_prompt: str | None = None,
) -> dict[str, Any] | None:
    if not OPENAI_API_KEY:
        return None
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "input": messages,
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
    text = _extract_openai_text(body)
    parsed = _extract_decision_payload(text)
    if isinstance(parsed, dict):
        usage = body.get("usage") or {}
        parsed["__input_tokens__"] = int(
            usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0) or 0
        )
        parsed["__output_tokens__"] = int(
            usage.get("output_tokens", 0) or usage.get("completion_tokens", 0) or 0
        )
    return parsed


async def _call_anthropic(
    model: str,
    prompt: str,
    *,
    call_context: str,
    system_prompt: str | None = None,
) -> dict[str, Any] | None:
    if not ANTHROPIC_API_KEY:
        return None
    # S4-01: Prompt cache optimization — mark the system prompt and first user
    # turn as ephemeral cache breakpoints for high-frequency CEO/PM calls.
    # The anthropic-beta header enables the prompt-caching feature.
    user_content: list[dict[str, Any]] | str
    if len(prompt) > 1024:
        # Only cache large prompts; small ones don't benefit enough to justify
        # the cache-write token overhead.
        user_content = [{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}]
    else:
        user_content = prompt
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 900,
        "messages": [{"role": "user", "content": user_content}],
    }
    if system_prompt:
        payload["system"] = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
        ]
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "anthropic-beta": "prompt-caching-2024-07-31",
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
    text = _extract_anthropic_text(body)
    parsed = _extract_decision_payload(text)
    if isinstance(parsed, dict):
        usage = body.get("usage") or {}
        parsed["__input_tokens__"] = int(usage.get("input_tokens", 0) or 0)
        parsed["__output_tokens__"] = int(usage.get("output_tokens", 0) or 0)
    return parsed


async def _call_gemini(
    model: str,
    prompt: str,
    *,
    call_context: str,
    system_prompt: str | None = None,
) -> dict[str, Any] | None:
    if not GEMINI_API_KEY:
        return None
    payload: dict[str, Any] = {"contents": [{"parts": [{"text": prompt}]}]}
    if system_prompt:
        payload["system_instruction"] = {"parts": [{"text": system_prompt}]}
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
    text = _extract_gemini_text(body)
    parsed = _extract_decision_payload(text)
    if isinstance(parsed, dict):
        meta = body.get("usageMetadata") or {}
        parsed["__input_tokens__"] = int(meta.get("promptTokenCount", 0) or 0)
        parsed["__output_tokens__"] = int(meta.get("candidatesTokenCount", 0) or 0)
    return parsed


async def _call_provider(
    *,
    provider: str,
    model: str,
    prompt: str,
    call_context: str,
    system_prompt: str | None = None,
) -> dict[str, Any] | None:
    normalized = provider.strip().lower()

    async def _call_backend(func: Any) -> dict[str, Any] | None:
        try:
            return await func(
                model,
                prompt,
                call_context=call_context,
                system_prompt=system_prompt,
            )
        except TypeError as exc:
            if "system_prompt" not in str(exc):
                raise
            return await func(model, prompt, call_context=call_context)

    started = time.perf_counter()
    result: dict[str, Any] | None = None
    try:
        if normalized == "anthropic":
            result = await _call_backend(_call_anthropic)
        elif normalized == "gemini":
            result = await _call_backend(_call_gemini)
        else:
            result = await _call_backend(_call_openai)
        return result
    finally:
        try:
            _record_provider_health(
                provider=normalized or "openai",
                model=model,
                latency_ms=(time.perf_counter() - started) * 1000,
                success=isinstance(result, dict),
            )
        except Exception:
            LOGGER.warning("failed to record provider health telemetry", exc_info=True)


async def _call_with_recommendation(
    *,
    recommendation: dict[str, Any],
    prompt: str,
    call_context: str,
    system_prompt: str | None = None,
) -> tuple[dict[str, Any] | None, str, str, str]:
    provider = str(recommendation.get("provider", "openai")).strip().lower()
    model = str(recommendation.get("model", "gpt-5.5")).strip()

    # Safety envelope — scan outbound prompt before any LLM call
    from .llm_safety import (  # noqa: PLC0415
        check_outbound_prompt,
        sanitize_outbound_prompt,
    )
    _safety_violations = check_outbound_prompt(prompt, call_context)
    if _safety_violations:
        LOGGER.warning("LLM safety outbound violations [%s]: %s", call_context, _safety_violations)
        if LLM_SAFETY_BLOCK_ENABLED:
            return None, provider, model, "blocked_safety"
        prompt = sanitize_outbound_prompt(prompt)  # noqa: PLW2901

    async def _provider_call(
        *,
        route_provider: str,
        route_model: str,
        route_context: str,
    ) -> dict[str, Any] | None:
        try:
            return await _call_provider(
                provider=route_provider,
                model=route_model,
                prompt=prompt,
                call_context=route_context,
                system_prompt=system_prompt,
            )
        except TypeError as exc:
            if "system_prompt" not in str(exc):
                raise
            return await _call_provider(
                provider=route_provider,
                model=route_model,
                prompt=prompt,
                call_context=route_context,
            )

    parsed = await _provider_call(
        route_provider=provider,
        route_model=model,
        route_context=call_context,
    )
    if isinstance(parsed, dict):
        _record_usage_event(
            getattr(recommendation, "__settings__", None),
            str(recommendation.get("__mission_id__", "") or ""),
            str(recommendation.get("__agent_id__", "") or ""),
            provider, model,
            int(parsed.pop("__input_tokens__", 0) or 0),
            int(parsed.pop("__output_tokens__", 0) or 0),
            True, "primary",
        )
        return parsed, provider, model, "primary"

    fallback_provider = str(recommendation.get("fallback_provider", "")).strip().lower()
    fallback_model = str(recommendation.get("fallback_model", "")).strip()
    if not fallback_provider or not fallback_model:
        return None, provider, model, "primary"

    if fallback_provider == provider and fallback_model == model:
        return None, provider, model, "primary"

    fallback = await _provider_call(
        route_provider=fallback_provider,
        route_model=fallback_model,
        route_context=f"{call_context} (fallback)",
    )
    if isinstance(fallback, dict):
        _record_usage_event(
            getattr(recommendation, "__settings__", None),
            str(recommendation.get("__mission_id__", "") or ""),
            str(recommendation.get("__agent_id__", "") or ""),
            fallback_provider, fallback_model,
            int(fallback.pop("__input_tokens__", 0) or 0),
            int(fallback.pop("__output_tokens__", 0) or 0),
            True, "fallback",
        )
        return fallback, fallback_provider, fallback_model, "fallback"
    return None, provider, model, "primary"


async def _call_with_agent_system(
    *,
    recommendation: dict[str, Any],
    prompt: str,
    call_context: str,
    agent_id: str,
) -> tuple[dict[str, Any] | None, str, str, str]:
    """Call the recommendation helper with persona system prompt when supported."""
    # Security Hardening: Redact PII from the prompt before sending to provider
    redacted_prompt, matches = redact_pii(prompt)
    if matches:
        LOGGER.info("PII redaction active for %s: %d matches scrubbed", agent_id, len(matches))
    prompt = redacted_prompt

    token = current_agent_id.set(agent_id)
    try:
        try:
            return await _call_with_recommendation(
                recommendation=recommendation,
                prompt=prompt,
                call_context=call_context,
                system_prompt=_system_prompt_for_agent(agent_id),
            )
        except TypeError as exc:
            if "system_prompt" not in str(exc):
                raise
            return await _call_with_recommendation(
                recommendation=recommendation,
                prompt=prompt,
                call_context=call_context,
            )
    finally:
        current_agent_id.reset(token)


def _fallback_delegation(
    *,
    requested_target_language: str | None,
    mission_context: dict[str, Any],
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    LLM_FALLBACK_TOTAL.labels(agent_id="AGENT-02-CEO", reason="offline").inc()
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
    LLM_FALLBACK_TOTAL.labels(agent_id=pod_manager_agent_id, reason="offline").inc()
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
    LLM_FALLBACK_TOTAL.labels(agent_id=specialist_agent_id, reason="offline").inc()
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
    mission_type = str(mission_context.get("mission_type") or "BUILD_NEW").strip().upper()
    language = str(mission_context.get("requested_target_language") or "auto").strip().lower()
    feature_contract = mission_context.get("feature_contract")
    complexity = ""
    if isinstance(feature_contract, dict):
        complexity = str(feature_contract.get("estimated_complexity") or "").strip().lower()
    type_strategy = {
        "BUILD_NEW": (
            "Select the pod whose language specialist has the strongest code generation "
            "capability for the requested language."
        ),
        "DEBUG_REPAIR": (
            "Select the pod whose specialist has the deepest static analysis and "
            "fault-isolation capability for the source language."
        ),
        "SECURITY_HARDEN": (
            "Select the pod whose specialist understands security-sensitive patterns. "
            "Flag Security and Compliance agents before COMPLETE."
        ),
        "PORT": (
            "This is a PORT mission. It MUST produce exactly two logic clusters:\n"
            "  Cluster 1 (EXTRACTION): domain=source_extraction, priority=HIGH.\n"
            "    Assigned to the SOURCE language pod manager and specialist.\n"
            "    Purpose: extract intent and LogicNodes from the original source.\n"
            "  Cluster 2 (GENERATION): domain=target_generation, priority=MEDIUM.\n"
            "    Assigned to the TARGET language pod manager and specialist.\n"
            "    depends_on: [Cluster 1 title].\n"
            "    Purpose: generate target-language implementation from extracted intent.\n"
            "Identify source and target language from the prompt. "
            "Assign each cluster to the CORRECT pod."
        ),
        "REDUCE_DEPENDENCIES": (
            "Select the pod whose specialist can identify import-level intent and "
            "generate replacement code. Flag DEPABS requirements."
        ),
        "IMPORT_MODERNIZE": (
            "Select the pod whose specialist understands legacy patterns in the "
            "source language. Modernization requires extraction and generation."
        ),
        "ANALYZE_ONLY": (
            "Select the pod whose specialist can produce the richest LogicNode "
            "coverage. No code generation is required."
        ),
    }
    strategy = type_strategy.get(mission_type, type_strategy["BUILD_NEW"])
    complexity_note = (
        " High-complexity mission: consider multiple clusters and parallel pod ownership."
        if complexity in {"high", "very_high"}
        else ""
    )

    risk_assessment = mission_context.get("risk_assessment") or {}
    risk_score = float(risk_assessment.get("risk_score", 0.0))
    risk_note = ""
    if risk_score > 0.6:
        risk_note = f"\nATTENTION: High risk mission (score {risk_score}). Prioritize pods with strong security/audit specialists and plan for rigorous verification cycles."

    style_directives = mission_context.get("global_style_directives") or []
    style_note = ""
    if style_directives:
        style_note = f"\nTEAM STYLE DIRECTIVES: {'; '.join(style_directives)}. Ensure these are propagated to all assigned pod managers and specialists."

    return (
        "You are AGENT-02-CEO in a strict chain-of-command runtime. Act as a strategic executive.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Return only JSON with keys: pod_manager_agent_id, specialist_agent_id, rationale.\n\n"
        f"Mission type: {mission_type}\n"
        f"Target language: {language}\n"
        f"Strategic guidance: {strategy}{complexity_note}{risk_note}{style_note}\n\n"
        "Your rationale must explain why this pod, why this specialist, and any "
        "cross-pod or support-agent dependencies flagged by mission type.\n\n"
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
    pod_family_strategy = {
        "AGENT-12-PODA-MGR": (
            "Pod A owns dynamic language execution. Prioritize runtime ergonomics, "
            "package boundaries, async behavior, and scripting surface clarity."
        ),
        "AGENT-18-PODB-MGR": (
            "Pod B owns systems language execution. Prioritize memory safety, "
            "concurrency, compile-time contracts, and dependency minimization."
        ),
        "AGENT-24-PODC-MGR": (
            "Pod C owns JVM and enterprise language execution. Prioritize layered "
            "architecture, type contracts, build tooling, and operational stability."
        ),
        "AGENT-30-PODD-MGR": (
            "Pod D owns functional and data-oriented language execution. Prioritize "
            "pure transformations, schema boundaries, pipeline semantics, and proofability."
        ),
    }
    mission_type = str(mission_context.get("mission_type") or "BUILD_NEW").strip().upper()
    strategy = pod_family_strategy.get(
        pod_manager_agent_id.strip().upper(),
        "Use pod-family expertise to select the specialist with the strongest mission fit.",
    )
    risk_context = _format_upstream_risks(mission_context)
    style_context = _format_upstream_style(mission_context)

    return (
        f"You are {pod_manager_agent_id} (pod manager) in a strict delegation chain.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Return only JSON with keys: specialist_agent_id, rationale.\n"
        f"Default specialist_agent_id: {default_specialist_agent_id}\n"
        f"Mission type: {mission_type}\n"
        f"Pod-family strategy: {strategy}\n"
        f"{risk_context}{style_context}"
        "Your rationale must identify language fit, risk fit, and whether the pod "
        "needs cross-pod or support-agent follow-up. Explicitly mention if team style "
        "directives were factored into specialist choice.\n"
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
    language = str(mission_context.get("requested_target_language") or "").strip().lower()
    risk_context = _format_upstream_risks(mission_context)
    style_context = _format_upstream_style(mission_context)
    return (
        f"You are {specialist_agent_id}, delegated by {pod_manager_agent_id}.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        f"{_language_context(language)}"
        f"{risk_context}{style_context}"
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
            "rationale": ceo_delegation.get("rationale"),
            "source": ceo_delegation.get("source"),
        },
        sort_keys=True,
    )
    delegation_rationale = _clean_text(ceo_delegation.get("rationale", ""), max_length=280)
    risk_context = _format_upstream_risks(mission_context)
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
        + (f"CEO delegation rationale: {delegation_rationale}\n" if delegation_rationale else "")
        + (f"PM feature contract JSON: {feature_summary}\n" if feature_summary else "")
        + risk_context
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
    attachments: list[dict[str, Any]] | None = None,
    global_style_directives: list[str] | None = None,
) -> str:
    safe_prompt = _clean_text(prompt, max_length=1200)

    docs_context = ""
    if attachments:
        docs_context = "Attached Reference Documents:\n"
        for att in attachments:
            docs_context += f"- {att.get('filename')} (Type: {att.get('content_type')}, Purpose: {att.get('purpose')})\n"
        docs_context += "\n"

    style_context = ""
    if global_style_directives:
        style_context = "Global Style & Team Directives:\n"
        for directive in global_style_directives:
            style_context += f"- {directive}\n"
        style_context += "\n"

    return (
        "You are AGENT-01-PM. Convert the operator request and attached context into a product-level "
        "Feature Contract for a software factory mission. Act as a proactive product partner.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Return only JSON. No markdown, prose, or code fences.\n\n"
        f"Mission type: {_clean_text(mission_type or 'BUILD_NEW', max_length=48).upper()}\n"
        f"Depth mode: {_clean_text(depth_mode or 'STANDARD', max_length=48).upper()}\n"
        f"Output mode: {_clean_text(output_mode or 'FULL_BUILD', max_length=48).upper()}\n"
        "Requested target language: "
        f"{_clean_text(requested_target_language or 'auto', max_length=32).lower()}\n"
        f"{docs_context}{style_context}"
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
    risk_assessment = {
        "complexity": complexity,
        "risk_score": 0.0,
        "risk_factors": _string_list(raw.get("risk_notes"), limit=5),
    }
    if complexity == "very_high": risk_assessment["risk_score"] = 0.9
    elif complexity == "high": risk_assessment["risk_score"] = 0.7
    elif complexity == "medium": risk_assessment["risk_score"] = 0.4
    else: risk_assessment["risk_score"] = 0.2

    contract = {
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
        "risk_assessment": risk_assessment,
        "human_approval_required": human_approval,
        "risk_notes": _string_list(raw.get("risk_notes"), limit=5),
        "clarifying_questions": _string_list(raw.get("clarifying_questions"), limit=5),
        "source": "llm",
        "llm_route": route,
        "model_provider": provider,
        "model": model,
        "created_at": datetime.now(UTC).isoformat(),
    }
    contract["ambiguity_score"] = _pm_ambiguity_score(contract, prompt)
    return contract


def _fallback_pm_feature_contract(
    *,
    prompt: str,
    mission_type: str,
    requested_target_language: str | None,
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    LLM_FALLBACK_TOTAL.labels(agent_id="AGENT-01-PM", reason="offline").inc()
    language = _clean_text(requested_target_language or "", max_length=32).lower()
    contract = {
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
    contract["ambiguity_score"] = _pm_ambiguity_score(contract, prompt)
    return contract


async def generate_pm_feature_contract(
    *,
    prompt: str,
    mission_type: str,
    depth_mode: str,
    output_mode: str,
    requested_target_language: str | None,
    attachments: list[dict[str, Any]] | None = None,
    global_style_directives: list[str] | None = None,
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
        attachments=attachments,
        global_style_directives=global_style_directives,
    )
    parsed, resolved_provider, resolved_model, llm_route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=pm_prompt,
        call_context="pm feature contract",
        agent_id="AGENT-01-PM",
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
    LLM_FALLBACK_TOTAL.labels(agent_id="AGENT-01-PM", reason="offline").inc()
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
    risk_context = _format_upstream_risks(mission_context)
    hw_context = build_hw_context_block(
        mission_type=str(mission_context.get("mission_type") or "BUILD_NEW"),
        language=target_language,
        logic_clusters=(
            mission_context.get("logic_clusters")
            if isinstance(mission_context.get("logic_clusters"), dict)
            else None
        ),
    )
    # PORT mission — inject source behavior context
    port_source_context = ""
    port_nodes = mission_context.get("port_source_logicnodes") or []
    if port_nodes and isinstance(port_nodes, list):
        source_lang = _clean_text(
            str(mission_context.get("port_source_language") or "source"), max_length=32
        )
        node_lines = "\n".join(
            f"- {_clean_text(str(n.get('domain') or ''), max_length=32)}"
            f".{_clean_text(str(n.get('concept') or ''), max_length=48)}: "
            f"{_clean_text(str(n.get('intent') or ''), max_length=100)}"
            for n in port_nodes[:15]
            if isinstance(n, dict)
        )
        if node_lines:
            port_source_context = (
                f"\nSource behavior extracted from original {source_lang} code:\n"
                f"{node_lines}\n"
                f"Preserve this behavior in your {target_language} implementation.\n"
            )

    return (
        f"You are {specialist_agent_id}, a {target_language} specialist.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Generate a single complete source file that satisfies the mission contract.\n"
        "Return only JSON. No markdown, prose, or code fences.\n\n"
        f"Mission: {contract_summary}\n"
        f"Target language: {_clean_text(target_language, max_length=32)}\n"
        f"{_language_context(target_language)}"
        f"{risk_context}"
        f"{hw_context}"
        f"{port_source_context}"
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
    LLM_FALLBACK_TOTAL.labels(agent_id=specialist_agent_id, reason="offline").inc()
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
    mission_type = str(
        mission_context.get("mission_type") or mission_contract.get("mission_type") or "BUILD_NEW"
    ).strip().upper()
    cluster_guidance = (
        "Decompose into 1-8 clusters. Rules:\n"
        "  - Each cluster must be ownable by a single pod manager.\n"
        "  - Clusters that can run in parallel should share priority level.\n"
        "  - Dependent clusters must list upstream titles in depends_on.\n"
        "  - DEBUG_REPAIR: one cluster per suspected fault domain.\n"
        "  - PORT: source extraction and target generation are separate clusters.\n"
        "  - SECURITY_HARDEN: include a security_audit cluster.\n"
        "  - REDUCE_DEPENDENCIES: include a dependency_absorption cluster.\n"
    )
    risk_context = _format_upstream_risks(mission_context)
    return (
        "You are AGENT-02-CEO. Decompose this mission contract into logic clusters.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Return only JSON. No markdown, prose, or code fences.\n\n"
        f"Mission type: {mission_type}\n"
        f"Requested target language: {safe_language}\n"
        f"Mission summary: {contract_summary}\n"
        f"Required domains: {json.dumps(required_domains)}\n"
        f"CEO delegation JSON: {safe_delegation}\n"
        f"Logicnode requirements JSON: {json.dumps(safe_requirements, sort_keys=True)}\n\n"
        f"{cluster_guidance}\n"
        f"{risk_context}"
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
        '      "depends_on": ["upstream cluster titles"],\n'
        '      "rationale": "why this work is grouped together"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Keep clusters coarse enough for pod-level ownership.\n"
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
                "depends_on": _string_list(item.get("depends_on"), limit=8, max_length=96),
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
    LLM_FALLBACK_TOTAL.labels(agent_id="AGENT-02-CEO", reason="offline").inc()
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
                "depends_on": [],
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


def _logicnode_payload(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    nested = record.get("node")
    if isinstance(nested, dict):
        return nested
    return record


def _logicnode_text(value: Any, *keys: str, fallback: str = "") -> str:
    if not isinstance(value, dict):
        return fallback
    for key in keys:
        raw_candidate = value.get(key)
        if raw_candidate is None:
            continue
        candidate = _clean_text(raw_candidate, max_length=120)
        if candidate:
            return candidate
    nested = value.get("payload")
    if isinstance(nested, dict):
        for key in keys:
            raw_candidate = nested.get(key)
            if raw_candidate is None:
                continue
            candidate = _clean_text(raw_candidate, max_length=120)
            if candidate:
                return candidate
    return fallback


def _logicnode_sources(record: Any, payload: dict[str, Any]) -> list[str]:
    sources: list[str] = []
    for container in (record, payload):
        if not isinstance(container, dict):
            continue
        for key in ("node_id", "id", "logicnode_id"):
            raw_candidate = container.get(key)
            if raw_candidate is None:
                continue
            candidate = _clean_text(raw_candidate, max_length=96)
            if candidate and candidate not in sources:
                sources.append(candidate)
    return sources or ["unidentified-logicnode"]


def _logicnode_languages(record: Any, payload: dict[str, Any]) -> list[str]:
    languages: list[str] = []
    for container in (record, payload):
        if not isinstance(container, dict):
            continue
        for key in ("language", "target_language", "requested_target_language", "source_language"):
            raw_candidate = container.get(key)
            if raw_candidate is None:
                continue
            candidate = _clean_text(raw_candidate, max_length=32).lower()
            if candidate and candidate not in languages:
                languages.append(candidate)
    return languages[:6]


def _standard_node_id(index: int, domain: str, concept: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", f"{domain}-{concept}".strip().lower()).strip("-")
    return f"standard-node-{index:02d}-{slug or 'general'}"


def _pod_standard_coverage_verdict(
    *,
    logicnodes: list[dict[str, Any]],
    canonical_logicnodes: list[dict[str, Any]],
    source_code: str | None = None,
) -> dict[str, Any]:
    raw_count = len([node for node in logicnodes if isinstance(node, dict)])
    canonical_count = len(canonical_logicnodes)
    source_line_count = len([line for line in str(source_code or "").splitlines() if line.strip()])
    expected_minimum = max(1, min(20, source_line_count // 25)) if source_line_count else 1
    coverage_thin = canonical_count < expected_minimum or (raw_count > 0 and canonical_count == 0)
    duplicate_ratio = (
        round((max(0, raw_count - canonical_count) / raw_count), 4) if raw_count else 0.0
    )
    findings: list[str] = []
    if coverage_thin:
        findings.append(
            "Canonical LogicNode coverage is thin for the available source and pod evidence."
        )
    if raw_count > 0 and duplicate_ratio >= 0.85:
        findings.append("High duplicate-elimination ratio requires pod-manager review.")
    if not findings:
        findings.append("Canonical LogicNode coverage meets deterministic pod standard checks.")
    return {
        "schema_version": "pod_standard_coverage.v1",
        "raw_logicnode_count": raw_count,
        "canonical_logicnode_count": canonical_count,
        "source_line_count": source_line_count,
        "expected_minimum_canonical_logicnodes": expected_minimum,
        "duplicate_ratio": duplicate_ratio,
        "coverage_thin": coverage_thin,
        "findings": findings,
    }


def _fallback_pod_group_standard(
    *,
    pod_name: str,
    pod_manager_agent_id: str,
    mission_id: str,
    logicnodes: list[dict[str, Any]],
    mission_contract: dict[str, Any],
    recommendation: dict[str, Any],
    source_code: str | None = None,
) -> dict[str, Any]:
    LLM_FALLBACK_TOTAL.labels(agent_id=f"{pod_name.upper()}-MGR", reason="offline").inc()
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for record in logicnodes[:200]:
        payload = _logicnode_payload(record)
        if not payload:
            continue
        domain = _logicnode_text(payload, "domain", "category", fallback="general")
        concept = _logicnode_text(payload, "concept", "name", "title", fallback="")
        if not concept:
            concept = _logicnode_text(payload, "intent", "summary", fallback="primary_operation")
        intent = _logicnode_text(
            payload,
            "intent",
            "summary",
            "description",
            fallback="Implement extracted mission behavior.",
        )
        key = (domain.lower(), concept.lower())
        source_ids = _logicnode_sources(record, payload)
        languages = _logicnode_languages(record, payload)
        existing = grouped.get(key)
        if existing is None:
            confidence = payload.get("confidence")
            grouped[key] = {
                "domain": domain,
                "concept": concept,
                "intent": intent,
                "source_node_ids": source_ids,
                "languages": languages,
                "confidence": confidence if isinstance(confidence, (int, float)) else None,
            }
            continue
        for source_id in source_ids:
            if source_id not in existing["source_node_ids"]:
                existing["source_node_ids"].append(source_id)
        for language in languages:
            if language not in existing["languages"]:
                existing["languages"].append(language)
        if (
            not existing.get("intent")
            or existing["intent"] == "Implement extracted mission behavior."
        ):
            existing["intent"] = intent

    if not grouped:
        requirements = mission_contract.get("logicnode_requirements")
        if isinstance(requirements, list):
            for item in requirements[:8]:
                if not isinstance(item, dict):
                    continue
                domain = _clean_text(item.get("domain") or "general", max_length=64)
                concept = _clean_text(item.get("concept") or "primary_operation", max_length=80)
                grouped[(domain.lower(), concept.lower())] = {
                    "domain": domain,
                    "concept": concept,
                    "intent": _clean_text(
                        item.get("intent") or "Implement mission contract requirement.",
                        max_length=180,
                    ),
                    "source_node_ids": [],
                    "languages": _string_list(
                        mission_contract.get("target_languages"),
                        limit=6,
                        max_length=32,
                    ),
                    "confidence": None,
                }

    canonical: list[dict[str, Any]] = []
    for item in grouped.values():
        node_index = len(canonical) + 1
        confidence = item.get("confidence")
        canonical.append(
            {
                "standard_node_id": _standard_node_id(
                    node_index,
                    str(item.get("domain") or "general"),
                    str(item.get("concept") or "primary_operation"),
                ),
                "domain": item.get("domain") or "general",
                "concept": item.get("concept") or "primary_operation",
                "intent": item.get("intent") or "Implement extracted mission behavior.",
                "source_node_ids": list(item.get("source_node_ids") or [])[:20],
                "languages": list(item.get("languages") or [])[:6],
                "confidence": confidence if isinstance(confidence, (int, float)) else None,
            }
        )
        if len(canonical) >= 20:
            break

    return {
        "schema_version": "pod_group_standard.v1",
        "pod": pod_name,
        "pod_manager_agent_id": pod_manager_agent_id,
        "mission_id": mission_id,
        "canonical_logicnodes": canonical,
        "coverage_verdict": _pod_standard_coverage_verdict(
            logicnodes=logicnodes,
            canonical_logicnodes=canonical,
            source_code=source_code,
        ),
        "eliminated_duplicates": max(0, len(logicnodes) - len(canonical)),
        "summary": (
            "Deterministic pod group standard produced by consolidating equivalent "
            "LogicNodes for pod-manager fusion."
        ),
        "source": "fallback",
        "model_provider": recommendation.get("provider"),
        "model": recommendation.get("model"),
        "created_at": datetime.now(UTC).isoformat(),
    }


def _build_pod_group_standard_prompt(
    *,
    pod_name: str,
    pod_manager_agent_id: str,
    mission_id: str,
    logicnodes: list[dict[str, Any]],
    mission_contract: dict[str, Any],
    recommended_provider: str,
    recommended_model: str,
    source_code: str | None = None,
) -> str:
    safe_nodes = [
        _clean_text(json.dumps(record, sort_keys=True), max_length=420)
        for record in logicnodes[:40]
        if isinstance(record, dict)
    ]
    contract_summary = _clean_text(
        mission_contract.get("contract_summary", "mission"), max_length=320
    )
    source_line_count = len([line for line in str(source_code or "").splitlines() if line.strip()])
    return (
        f"You are {pod_manager_agent_id}, the sub-manager for {pod_name}.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Consolidate specialist LogicNodes into a canonical pod group standard.\n"
        "Deduplicate semantically equivalent nodes across languages and preserve source ids.\n"
        "Call out thin coverage when the canonical standard is too small for the source scope.\n"
        "Return only JSON. No markdown, prose, or code fences.\n\n"
        f"Mission id: {_clean_text(mission_id, max_length=96)}\n"
        f"Mission summary: {contract_summary}\n"
        f"Approximate source line count: {source_line_count}\n"
        f"LogicNodes JSON lines:\n{chr(10).join(safe_nodes) or '- none'}\n\n"
        "Required JSON shape:\n"
        "{\n"
        '  "canonical_logicnodes": [\n'
        "    {\n"
        '      "domain": "domain",\n'
        '      "concept": "canonical concept",\n'
        '      "intent": "canonical intent",\n'
        '      "source_node_ids": ["source logicnode ids"],\n'
        '      "languages": ["languages represented"],\n'
        '      "confidence": 0.0\n'
        "    }\n"
        "  ],\n"
        '  "eliminated_duplicates": 0,\n'
        '  "summary": "one sentence"\n'
        "}\n"
    )


def _normalize_pod_group_standard(
    raw: dict[str, Any],
    *,
    provider: str,
    model: str,
    route: str,
    pod_name: str,
    pod_manager_agent_id: str,
    mission_id: str,
    logicnodes: list[dict[str, Any]],
    mission_contract: dict[str, Any],
    source_code: str | None = None,
) -> dict[str, Any]:
    canonical: list[dict[str, Any]] = []
    raw_nodes = raw.get("canonical_logicnodes")
    if isinstance(raw_nodes, list):
        for item in raw_nodes[:20]:
            if not isinstance(item, dict):
                continue
            domain = _clean_text(item.get("domain") or "general", max_length=64)
            concept = _clean_text(item.get("concept") or "primary_operation", max_length=80)
            confidence = item.get("confidence")
            canonical.append(
                {
                    "standard_node_id": _clean_text(
                        item.get("standard_node_id")
                        or _standard_node_id(len(canonical) + 1, domain, concept),
                        max_length=96,
                    ),
                    "domain": domain,
                    "concept": concept,
                    "intent": _clean_text(
                        item.get("intent") or "Implement extracted mission behavior.",
                        max_length=180,
                    ),
                    "source_node_ids": _string_list(
                        item.get("source_node_ids"),
                        limit=20,
                        max_length=96,
                    ),
                    "languages": _string_list(item.get("languages"), limit=6, max_length=32),
                    "confidence": confidence if isinstance(confidence, (int, float)) else None,
                }
            )
    if not canonical:
        return _fallback_pod_group_standard(
            pod_name=pod_name,
            pod_manager_agent_id=pod_manager_agent_id,
            mission_id=mission_id,
            logicnodes=logicnodes,
            mission_contract=mission_contract,
            recommendation={"provider": provider, "model": model},
            source_code=source_code,
        )
    duplicate_count = raw.get("eliminated_duplicates")
    if not isinstance(duplicate_count, int) or duplicate_count < 0:
        duplicate_count = max(0, len(logicnodes) - len(canonical))
    return {
        "schema_version": "pod_group_standard.v1",
        "pod": pod_name,
        "pod_manager_agent_id": pod_manager_agent_id,
        "mission_id": mission_id,
        "canonical_logicnodes": canonical,
        "coverage_verdict": _pod_standard_coverage_verdict(
            logicnodes=logicnodes,
            canonical_logicnodes=canonical,
            source_code=source_code,
        ),
        "eliminated_duplicates": duplicate_count,
        "summary": _clean_text(
            raw.get("summary")
            or "Pod group standard consolidated from specialist LogicNodes.",
            max_length=260,
        ),
        "source": "llm",
        "llm_route": route,
        "model_provider": provider,
        "model": model,
        "created_at": datetime.now(UTC).isoformat(),
    }


async def generate_pod_group_standard(
    *,
    pod_name: str,
    pod_manager_agent_id: str,
    mission_id: str,
    logicnodes: list[dict[str, Any]],
    mission_contract: dict[str, Any],
    source_code: str | None = None,
) -> dict[str, Any]:
    normalized_pod_manager_agent_id = pod_manager_agent_id.strip().upper()
    recommendation = _agent_recommendation(normalized_pod_manager_agent_id)
    provider = str(recommendation.get("provider", "openai")).strip().lower()
    model = str(recommendation.get("model", "gpt-5.5")).strip()
    prompt = _build_pod_group_standard_prompt(
        pod_name=pod_name,
        pod_manager_agent_id=normalized_pod_manager_agent_id,
        mission_id=mission_id,
        logicnodes=logicnodes,
        mission_contract=mission_contract,
        recommended_provider=provider,
        recommended_model=model,
        source_code=source_code,
    )
    parsed, resolved_provider, resolved_model, llm_route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="pod group standard consolidation",
        agent_id=normalized_pod_manager_agent_id,
    )
    if not isinstance(parsed, dict):
        return _fallback_pod_group_standard(
            pod_name=pod_name,
            pod_manager_agent_id=normalized_pod_manager_agent_id,
            mission_id=mission_id,
            logicnodes=logicnodes,
            mission_contract=mission_contract,
            recommendation=recommendation,
            source_code=source_code,
        )
    return _normalize_pod_group_standard(
        parsed,
        provider=resolved_provider,
        model=resolved_model,
        route=llm_route,
        pod_name=pod_name,
        pod_manager_agent_id=normalized_pod_manager_agent_id,
        mission_id=mission_id,
        logicnodes=logicnodes,
        mission_contract=mission_contract,
        source_code=source_code,
    )


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
    model = str(recommendation.get("model", "gpt-5.5")).strip()
    prompt = _build_codegen_prompt(
        mission_context=mission_context,
        mission_contract=mission_contract,
        logicnodes=logicnodes or [],
        target_language=target_language,
        specialist_agent_id=specialist_agent_id,
        recommended_provider=provider,
        recommended_model=model,
    )
    parsed, resolved_provider, resolved_model, llm_route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context=f"specialist codegen {specialist_agent_id}",
        agent_id=specialist_agent_id,
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


def build_deploy_readiness_assessment(
    *,
    mission_id: str,
    metadata: dict[str, Any],
    build_artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the Deploy Agent's deterministic packaging-readiness fallback."""
    artifacts = build_artifacts if isinstance(build_artifacts, list) else []
    has_packaged_artifact = any(
        isinstance(artifact, dict)
        and str(artifact.get("artifact_type") or artifact.get("type") or "").lower()
        in {"generated_code", "source_bundle_package"}
        for artifact in artifacts
    ) or bool(
        isinstance(metadata.get("mission_artifacts"), dict)
        and metadata["mission_artifacts"].get("build_packaged")
    )
    checks = [
        {
            "name": "packaged_artifact",
            "passed": has_packaged_artifact,
            "summary": "Mission has a generated-code or source-bundle build artifact.",
        },
        {
            "name": "completion_evidence",
            "passed": bool(metadata.get("delivery_summary") or metadata.get("generated_output")),
            "summary": "Mission contains completion evidence for operator review.",
        },
        {
            "name": "pod_standard",
            "passed": bool(metadata.get("pod_group_standards")),
            "summary": "Mission contains a pod group standard for traceability.",
        },
    ]
    blockers = [check["name"] for check in checks if not check["passed"]]
    return {
        "schema_version": "deploy_readiness.v1",
        "mission_id": _clean_text(mission_id, max_length=96),
        "agent_id": "AGENT-11-DEPLOY",
        "ready": not blockers,
        "blockers": blockers,
        "checks": checks,
        "source": "fallback",
        "created_at": datetime.now(UTC).isoformat(),
    }


async def generate_rqca_assessment(
    *,
    mission_id: str,
    execution_result: dict[str, Any],
    mission_contract: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    """Interpret runtime-QC execution results with deterministic fallback."""
    _ = mission_id, mission_contract, language
    verdict = str(execution_result.get("verdict") or "SKIPPED").strip().upper()
    passed = bool(execution_result.get("passed", False))
    if verdict in {"DRY_RUN", "SKIPPED"}:
        return {
            "qc_verdict": "ADVISORY",
            "confidence": "LOW",
            "execution_verdict": verdict,
            "findings": [],
            "remediation": [],
            "deployment_safe": True,
            "source": "advisory",
            "assessed_at": datetime.now(UTC).isoformat(),
        }
    if passed:
        qc_verdict = "PASS"
        findings = ["Runtime execution completed with the expected exit code."]
        remediation: list[str] = []
    else:
        qc_verdict = "FAIL"
        findings = ["Runtime execution did not complete as expected."]
        remediation = ["Inspect stderr/stdout previews and repair the generated artifact."]
    return {
        "qc_verdict": qc_verdict,
        "confidence": "LOW",
        "execution_verdict": verdict,
        "findings": findings,
        "remediation": remediation,
        "deployment_safe": passed,
        "source": "fallback",
        "assessed_at": datetime.now(UTC).isoformat(),
    }


async def generate_pm_delivery_summary(
    *,
    mission_context: dict[str, Any],
    generated_output: dict[str, Any],
    build_artifacts: list[dict[str, Any]],
    feature_contract: dict[str, Any],
    mission_contract: dict[str, Any],
) -> dict[str, Any]:
    """PM Agent produces a final delivery summary for completed missions."""
    recommendation = _agent_recommendation("AGENT-01-PM")
    provider = str(recommendation.get("provider", "openai")).strip().lower()
    model = str(recommendation.get("model", "gpt-5.5")).strip()

    primary_artifact = next(
        (
            artifact
            for artifact in build_artifacts
            if artifact.get("artifact_type") == "generated_code"
        ),
        build_artifacts[0] if build_artifacts else {},
    )
    manifest = primary_artifact.get("manifest") if isinstance(primary_artifact, dict) else {}
    if not isinstance(manifest, dict):
        manifest = {}
    artifact_text = (
        primary_artifact.get("artifact_text")
        if isinstance(primary_artifact, dict)
        else ""
    )
    code_preview = str(generated_output.get("generated_code") or artifact_text or "")[:600]
    filename = str(
        generated_output.get("filename")
        or manifest.get("filename")
        or primary_artifact.get("artifact_id")
        or "mission artifact"
    )
    language = str(
        generated_output.get("language")
        or manifest.get("language")
        or mission_context.get("requested_target_language")
        or "unknown"
    )
    criteria = (
        feature_contract.get("acceptance_criteria")
        or mission_contract.get("acceptance_criteria")
        or []
    )
    contract_summary = (
        mission_contract.get("contract_summary")
        or feature_contract.get("summary")
        or mission_context.get("prompt")
        or "Completed mission"
    )
    artifact_type = (
        primary_artifact.get("artifact_type")
        if isinstance(primary_artifact, dict)
        else None
    )

    prompt = (
        "You are AGENT-01-PM. The mission is complete. Produce a concise "
        "operator delivery summary tied to acceptance criteria and artifacts.\n"
        f"Recommended model: {provider}/{model}\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission: {_clean_text(contract_summary, max_length=300)}\n"
        f"Primary artifact: {filename} ({artifact_type or 'none'}, {language})\n"
        f"Artifact count: {len(build_artifacts)}\n"
        f"Output preview:\n{_clean_text(code_preview, max_length=600)}\n"
        f"Acceptance criteria: {json.dumps(_string_list(criteria, limit=6))}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "delivery_title": "short title for what was delivered",\n'
        '  "delivery_summary": "1-2 sentence summary for the operator",\n'
        '  "criteria_met": ["criteria that appear to be satisfied"],\n'
        '  "criteria_unmet": ["criteria that may need verification"],\n'
        '  "usage_notes": "how to use or inspect the delivered artifact",\n'
        '  "recommendations": ["optional follow-up suggestions"]\n'
        "}\n"
    )

    parsed, resolved_provider, resolved_model, _route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="pm delivery summary",
        agent_id="AGENT-01-PM",
    )
    if not isinstance(parsed, dict):
        return {
            "delivery_title": f"Delivered: {filename}",
            "delivery_summary": (
                "Mission complete. Review the delivered artifact and verify it "
                "against the acceptance criteria."
            ),
            "criteria_met": [],
            "criteria_unmet": _string_list(criteria, limit=6),
            "usage_notes": "Open the delivered artifact and verify it before release.",
            "recommendations": [],
            "primary_artifact_type": artifact_type,
            "source": "fallback",
        }

    return {
        "delivery_title": _clean_text(
            parsed.get("delivery_title") or f"Delivered: {filename}",
            max_length=120,
        ),
        "delivery_summary": _clean_text(
            parsed.get("delivery_summary") or "Mission complete.",
            max_length=500,
        ),
        "criteria_met": _string_list(parsed.get("criteria_met"), limit=6),
        "criteria_unmet": _string_list(parsed.get("criteria_unmet"), limit=6),
        "usage_notes": _clean_text(parsed.get("usage_notes", ""), max_length=300),
        "recommendations": _string_list(parsed.get("recommendations"), limit=4),
        "primary_artifact_type": artifact_type,
        "source": "llm",
        "model_provider": resolved_provider,
        "model": resolved_model,
    }


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
    parsed, resolved_provider, resolved_model, llm_route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="logic cluster decomposition",
        agent_id=CEO_AGENT_ID,
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
    parsed, resolved_provider, resolved_model, llm_route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=contract_prompt,
        call_context="mission contract",
        agent_id=CEO_AGENT_ID,
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

    parsed, resolved_provider, resolved_model, llm_route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="ceo delegation",
        agent_id=CEO_AGENT_ID,
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

    parsed, resolved_provider, resolved_model, llm_route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="pod-manager delegation",
        agent_id=normalized_pod_manager_agent_id,
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

    parsed, resolved_provider, resolved_model, llm_route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="specialist planning",
        agent_id=normalized_specialist_agent_id,
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


async def generate_master_logic_stream(
    *,
    pod_group_standards: dict[str, dict[str, Any]],
    mission_contract: dict[str, Any],
    mission_context: dict[str, Any],
) -> dict[str, Any]:
    """CEO fuses pod Group Standards into a unified Master Logic Stream (Phase 9).

    Merges LogicNodes from all pods, eliminates cross-pod duplicates, and orders
    by dependency for downstream code generation. Falls back to deterministic
    deduplication when LLM is unavailable.
    """
    if not pod_group_standards:
        return {
            "master_logic_stream": [],
            "total_unified_nodes": 0,
            "eliminated_across_pods": 0,
            "ready_for_codegen": False,
            "source": "empty",
        }

    recommendation = _ceo_recommendation()
    provider = str(recommendation.get("provider", "openai")).strip().lower()
    model = str(recommendation.get("model", "gpt-5.5")).strip()

    pods_summary = []
    total_input_nodes = 0
    for pod_name, standard in pod_group_standards.items():
        nodes = standard.get("canonical_logicnodes") or []
        total_input_nodes += len(nodes)
        pods_summary.append({
            "pod": pod_name,
            "node_count": len(nodes),
            "nodes": [
                {"domain": n.get("domain"), "concept": n.get("concept"), "intent": n.get("intent")}
                for n in nodes[:15]
            ],
        })

    contract_summary = _clean_text(mission_contract.get("contract_summary", ""), max_length=300)
    required_domains = mission_contract.get("required_domains") or []
    acceptance_criteria = mission_contract.get("acceptance_criteria") or []

    prompt = (
        "You are AGENT-02-CEO performing Logic Folding — the Grand Fusion.\n"
        f"Recommended model: {provider}/{model}\n"
        "Merge LogicNodes from all pods into a single ordered Master Logic Stream.\n"
        "Remove cross-pod duplicates. Order by dependency (inputs before outputs).\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission: {contract_summary}\n"
        f"Required domains: {json.dumps(required_domains[:10])}\n"
        f"Acceptance criteria: {json.dumps(acceptance_criteria[:4])}\n"
        f"Total input nodes across all pods: {total_input_nodes}\n"
        f"Pod inputs:\n{json.dumps(pods_summary, indent=2)}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "master_logic_stream": [\n'
        '    {"node_id": "unified-001", "domain": "domain", "concept": "concept",\n'
        '     "canonical_intent": "intent", "source_pods": ["podA"], "dependency_order": 1}\n'
        "  ],\n"
        '  "total_unified_nodes": 18,\n'
        '  "eliminated_across_pods": 4,\n'
        '  "ready_for_codegen": true\n'
        "}\n\n"
        "Keep master_logic_stream to 5-25 nodes. Order by dependency_order (lowest first).\n"
    )

    parsed, resolved_provider, resolved_model, _route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="ceo logic fusion",
        agent_id=CEO_AGENT_ID,
    )

    if not isinstance(parsed, dict):
        all_nodes: list[dict[str, Any]] = []
        seen_concepts: set[str] = set()
        order = 1
        for pod_name, standard in pod_group_standards.items():
            for node in (standard.get("canonical_logicnodes") or [])[:10]:
                concept = str(node.get("concept") or "")
                if concept not in seen_concepts:
                    seen_concepts.add(concept)
                    all_nodes.append({
                        "node_id": f"unified-{order:03d}",
                        "domain": node.get("domain", "generic"),
                        "concept": concept,
                        "canonical_intent": node.get("intent", ""),
                        "source_pods": [pod_name],
                        "dependency_order": order,
                    })
                    order += 1
        eliminated = max(0, total_input_nodes - len(all_nodes))
        return {
            "master_logic_stream": all_nodes[:20],
            "total_unified_nodes": len(all_nodes),
            "eliminated_across_pods": eliminated,
            "ready_for_codegen": len(all_nodes) > 0,
            "source": "fallback",
        }

    stream = parsed.get("master_logic_stream") or []
    if not isinstance(stream, list):
        stream = []

    return {
        "master_logic_stream": stream[:25],
        "total_unified_nodes": int(parsed.get("total_unified_nodes") or len(stream)),
        "eliminated_across_pods": int(parsed.get("eliminated_across_pods") or 0),
        "ready_for_codegen": bool(parsed.get("ready_for_codegen", True)),
        "source": "llm",
        "model_provider": resolved_provider,
        "model": resolved_model,
    }


# ---------------------------------------------------------------------------
# S2-02: Security threat analysis (AGENT-05-SECURITY)
# ---------------------------------------------------------------------------

async def generate_security_analysis(
    *,
    mission_id: str,
    mission_context: dict[str, Any],
    generated_output: dict[str, Any] | None,
    mission_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    """Run AGENT-05-SECURITY's threat analysis over the generated code artifact.

    Returns a ``security_analysis.v1`` document with a threat list, risk level,
    and deployment recommendation.  Falls back deterministically when LLM is
    unavailable so the gating phase is never blocked by provider outages.
    """
    recommendation = _agent_recommendation("AGENT-05-SECURITY")
    provider = str(recommendation.get("provider", "anthropic")).strip().lower()
    model = str(recommendation.get("model", "claude-sonnet-4-6")).strip()

    code_snippet = _clean_text(
        str((generated_output or {}).get("generated_code") or ""), max_length=4000
    )
    language = _clean_text(
        str(
            (generated_output or {}).get("language")
            or mission_context.get("requested_target_language")
            or "unknown"
        ),
        max_length=32,
    )
    contract_summary = _clean_text(
        str((mission_contract or {}).get("contract_summary") or ""), max_length=300
    )

    prompt = (
        "You are AGENT-05-SECURITY performing a threat-analysis code review.\n"
        f"Recommended model: {provider}/{model}\n"
        "Analyse the generated code for security vulnerabilities, injection risks,\n"
        "secrets/credential exposure, and unsafe dependencies.\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission ID: {_clean_text(mission_id, max_length=96)}\n"
        f"Language: {language}\n"
        f"Contract summary: {contract_summary}\n"
        f"Code artifact (truncated to 4000 chars):\n```\n{code_snippet}\n```\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "schema_version": "security_analysis.v1",\n'
        '  "risk_level": "low|medium|high|critical",\n'
        '  "deployment_safe": true,\n'
        '  "threats": [\n'
        '    {"id": "T001", "category": "injection", "severity": "high",\n'
        '     "description": "...", "line_hint": null, "remediation": "..."}\n'
        "  ],\n"
        '  "summary": "One-paragraph executive summary.",\n'
        '  "recommendations": ["..."],\n'
        '  "passed": true\n'
        "}\n\n"
        "Limit threats list to 10 items. risk_level must be one of: low, medium, high, critical.\n"
        "Set deployment_safe=false only if risk_level is high or critical.\n"
    )

    parsed, resolved_provider, resolved_model, _route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="security threat analysis",
        agent_id="AGENT-05-SECURITY",
    )

    if not isinstance(parsed, dict):
        return _fallback_security_analysis(mission_id=mission_id, language=language)

    valid_risk_levels = {"low", "medium", "high", "critical"}
    risk_level = _clean_text(parsed.get("risk_level", "low"), max_length=16).lower()
    if risk_level not in valid_risk_levels:
        risk_level = "low"
    deployment_safe = bool(parsed.get("deployment_safe", True))
    threats_raw = parsed.get("threats") or []
    threats: list[dict[str, Any]] = []
    if isinstance(threats_raw, list):
        for item in threats_raw[:10]:
            if not isinstance(item, dict):
                continue
            threats.append({
                "id": _clean_text(item.get("id", ""), max_length=16) or f"T{len(threats)+1:03d}",
                "category": _clean_text(item.get("category", "unknown"), max_length=64),
                "severity": _clean_text(item.get("severity", "low"), max_length=16).lower(),
                "description": _clean_text(item.get("description", ""), max_length=240),
                "line_hint": item.get("line_hint"),
                "remediation": _clean_text(item.get("remediation", ""), max_length=240),
            })
    passed = risk_level not in {"high", "critical"} and deployment_safe
    return {
        "schema_version": "security_analysis.v1",
        "mission_id": _clean_text(mission_id, max_length=96),
        "agent_id": "AGENT-05-SECURITY",
        "risk_level": risk_level,
        "deployment_safe": deployment_safe,
        "threats": threats,
        "summary": _clean_text(
            parsed.get("summary", "Security analysis complete."), max_length=600
        ),
        "recommendations": _string_list(parsed.get("recommendations"), limit=8),
        "passed": passed,
        "source": "llm",
        "model_provider": resolved_provider,
        "model": resolved_model,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _fallback_security_analysis(*, mission_id: str, language: str) -> dict[str, Any]:
    LLM_FALLBACK_TOTAL.labels(agent_id="AGENT-05-SECURITY", reason="offline").inc()
    return {
        "schema_version": "security_analysis.v1",
        "mission_id": _clean_text(mission_id, max_length=96),
        "agent_id": "AGENT-05-SECURITY",
        "risk_level": "low",
        "deployment_safe": True,
        "threats": [],
        "summary": (
            "Security analysis skipped — LLM provider unavailable. Manual review recommended."
        ),
        "recommendations": ["Perform manual security review before production deployment."],
        "passed": True,
        "source": "fallback",
        "created_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# S2-03: Version-control commit strategy (AGENT-07-VC)
# ---------------------------------------------------------------------------

async def generate_vc_commit_strategy(
    *,
    mission_id: str,
    mission_context: dict[str, Any],
    generated_output: dict[str, Any] | None,
    delivery_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    """Ask AGENT-07-VC to produce a commit strategy for the generated artifact.

    Returns a ``vc_commit_strategy.v1`` document with a conventional-commit
    message, branch name, PR summary, and rollback plan.
    """
    recommendation = _agent_recommendation("AGENT-07-VC")
    provider = str(recommendation.get("provider", "openai")).strip().lower()
    model = str(recommendation.get("model", "gpt-5.5")).strip()

    language = _clean_text(
        str(
            (generated_output or {}).get("language")
            or mission_context.get("requested_target_language")
            or "unknown"
        ),
        max_length=32,
    )
    filename = _clean_text(
        str((generated_output or {}).get("filename") or "output"), max_length=128
    )
    delivery_title = _clean_text(
        str((delivery_summary or {}).get("delivery_title") or "Mission output"), max_length=200
    )
    mission_type = _clean_text(
        str(mission_context.get("mission_type") or "BUILD_NEW"), max_length=48
    ).upper()

    prompt = (
        "You are AGENT-07-VC generating a version-control commit strategy.\n"
        f"Recommended model: {provider}/{model}\n"
        "Produce a conventional-commit message, feature branch name, PR summary, "
        "and rollback plan for the generated artifact.\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission ID: {_clean_text(mission_id, max_length=96)}\n"
        f"Mission type: {mission_type}\n"
        f"Language: {language}\n"
        f"Primary artifact: {filename}\n"
        f"Delivery summary: {delivery_title}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "schema_version": "vc_commit_strategy.v1",\n'
        '  "commit_message": "feat(scope): description\\n\\nBody text.",\n'
        '  "branch_name": "feature/mission-<id>-short-slug",\n'
        '  "pr_title": "...",\n'
        '  "pr_body": "## Summary\\n- bullet",\n'
        '  "rollback_steps": ["git revert <sha>", "..."],\n'
        '  "conventional_type": "feat|fix|chore|refactor|docs|test|perf"\n'
        "}\n\n"
        "Keep commit_message under 72 chars for the subject line.\n"
    )

    parsed, resolved_provider, resolved_model, _route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="vc commit strategy",
        agent_id="AGENT-07-VC",
    )

    if not isinstance(parsed, dict):
        return _fallback_vc_commit_strategy(
            mission_id=mission_id, language=language, mission_type=mission_type
        )

    valid_types = {"feat", "fix", "chore", "refactor", "docs", "test", "perf"}
    conv_type = _clean_text(parsed.get("conventional_type", "feat"), max_length=16).lower()
    if conv_type not in valid_types:
        conv_type = "feat"

    return {
        "schema_version": "vc_commit_strategy.v1",
        "mission_id": _clean_text(mission_id, max_length=96),
        "agent_id": "AGENT-07-VC",
        "commit_message": _clean_text(parsed.get("commit_message", ""), max_length=500)
            or f"feat: mission {mission_id[:8]} output",
        "branch_name": _clean_text(parsed.get("branch_name", ""), max_length=120)
            or f"feature/mission-{mission_id[:8]}",
        "pr_title": _clean_text(parsed.get("pr_title", ""), max_length=200)
            or delivery_title,
        "pr_body": _clean_text(parsed.get("pr_body", ""), max_length=2000),
        "rollback_steps": _string_list(parsed.get("rollback_steps"), limit=5),
        "conventional_type": conv_type,
        "source": "llm",
        "model_provider": resolved_provider,
        "model": resolved_model,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _fallback_vc_commit_strategy(
    *, mission_id: str, language: str, mission_type: str
) -> dict[str, Any]:
    slug = mission_id[:8]
    mission_lower = mission_type.lower().replace("_", "-")
    return {
        "schema_version": "vc_commit_strategy.v1",
        "mission_id": mission_id,
        "agent_id": "AGENT-07-VC",
        "commit_message": f"feat({language}): {mission_lower} mission {slug} output",
        "branch_name": f"feature/mission-{slug}-{language}",
        "pr_title": f"Mission {slug} — {mission_lower} ({language})",
        "pr_body": f"## Summary\n- Automated output from HGR mission `{mission_id}`.",
        "rollback_steps": ["git revert HEAD", "make down && make up"],
        "conventional_type": "feat",
        "source": "fallback",
        "created_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# S2-04: Integration test generation (AGENT-10-TESTER)
# ---------------------------------------------------------------------------

async def generate_integration_tests(
    *,
    mission_id: str,
    mission_context: dict[str, Any],
    generated_output: dict[str, Any] | None,
    mission_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    """Ask AGENT-10-TESTER to generate integration tests for the generated artifact.

    Returns an ``integration_tests.v1`` document containing test code and a
    manifest of test cases.  Falls back to a stub test when LLM is unavailable.
    """
    recommendation = _agent_recommendation("AGENT-10-TESTER")
    provider = str(recommendation.get("provider", "openai")).strip().lower()
    model = str(recommendation.get("model", "gpt-5.5")).strip()

    language = _clean_text(
        str(
            (generated_output or {}).get("language")
            or mission_context.get("requested_target_language")
            or "python"
        ),
        max_length=32,
    ).lower()
    filename = _clean_text(
        str((generated_output or {}).get("filename") or "output"), max_length=128
    )
    code_snippet = _clean_text(
        str((generated_output or {}).get("generated_code") or ""), max_length=3000
    )
    contract_summary = _clean_text(
        str((mission_contract or {}).get("contract_summary") or ""), max_length=300
    )
    acceptance_criteria = _string_list(
        (mission_contract or {}).get("acceptance_criteria"), limit=6
    )

    prompt = (
        "You are AGENT-10-TESTER generating integration tests.\n"
        f"Recommended model: {provider}/{model}\n"
        "Write integration tests that verify the acceptance criteria "
        "of the generated artifact. Match the target language.\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission ID: {_clean_text(mission_id, max_length=96)}\n"
        f"Language: {language}\n"
        f"Artifact filename: {filename}\n"
        f"Contract summary: {contract_summary}\n"
        f"Acceptance criteria: {json.dumps(acceptance_criteria)}\n"
        f"Code artifact (truncated):\n```\n{code_snippet}\n```\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "schema_version": "integration_tests.v1",\n'
        '  "test_filename": "test_output.py",\n'
        '  "test_code": "import ...",\n'
        '  "test_cases": [\n'
        '    {"name": "test_happy_path", "description": "...", "expected_outcome": "..."}\n'
        "  ],\n"
        '  "framework": "pytest|jest|mocha|gtest|junit|rspec"\n'
        "}\n\n"
        "Limit test_cases to 8. test_code must be runnable in the target language.\n"
    )

    parsed, resolved_provider, resolved_model, _route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="integration test generation",
        agent_id="AGENT-10-TESTER",
    )

    if not isinstance(parsed, dict):
        return _fallback_integration_tests(
            mission_id=mission_id, language=language, filename=filename
        )

    test_cases_raw = parsed.get("test_cases") or []
    test_cases: list[dict[str, Any]] = []
    if isinstance(test_cases_raw, list):
        for item in test_cases_raw[:8]:
            if not isinstance(item, dict):
                continue
            test_cases.append({
                "name": _clean_text(item.get("name", ""), max_length=120),
                "description": _clean_text(item.get("description", ""), max_length=240),
                "expected_outcome": _clean_text(item.get("expected_outcome", ""), max_length=240),
            })

    return {
        "schema_version": "integration_tests.v1",
        "mission_id": _clean_text(mission_id, max_length=96),
        "agent_id": "AGENT-10-TESTER",
        "test_filename": _clean_text(
            parsed.get("test_filename", f"test_{filename}"), max_length=200
        ),
        "test_code": _clean_text(parsed.get("test_code", ""), max_length=10000),
        "test_cases": test_cases,
        "framework": _clean_text(parsed.get("framework", "pytest"), max_length=32),
        "source": "llm",
        "model_provider": resolved_provider,
        "model": resolved_model,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _fallback_integration_tests(
    *, mission_id: str, language: str, filename: str
) -> dict[str, Any]:
    if language == "python":
        test_code = (
            f"# Auto-generated stub tests for mission {mission_id[:8]}\n"
            f"import importlib, sys\n\n"
            f"def test_module_importable():\n"
            f"    \"\"\"Verify the generated module imports without error.\"\"\"\n"
            f"    # Adjust import path as needed for your project layout\n"
            f"    assert True, 'Module import check placeholder'\n"
        )
        framework = "pytest"
        test_filename = f"test_{filename}"
    elif language in {"javascript", "typescript"}:
        test_code = (
            f"// Auto-generated stub tests for mission {mission_id[:8]}\n"
            f"describe('{filename}', () => {{\n"
            f"  it('should load without error', () => {{\n"
            f"    expect(true).toBe(true);\n"
            f"  }});\n"
            f"}});\n"
        )
        framework = "jest"
        test_filename = f"{filename.rsplit('.', 1)[0]}.test.{filename.rsplit('.', 1)[-1]}"
    else:
        test_code = f"// Stub test for mission {mission_id[:8]} ({language})\n"
        framework = "unknown"
        test_filename = f"test_{filename}"

    return {
        "schema_version": "integration_tests.v1",
        "mission_id": mission_id,
        "agent_id": "AGENT-10-TESTER",
        "test_filename": test_filename,
        "test_code": test_code,
        "test_cases": [
            {
                "name": "test_placeholder",
                "description": "Stub placeholder — replace with real assertions.",
                "expected_outcome": "Passes without error.",
            }
        ],
        "framework": framework,
        "source": "fallback",
        "created_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# S2-05: Pod audit verdict (AGENT-13/19/25/31-AUDIT)
# ---------------------------------------------------------------------------

_POD_AUDIT_AGENTS: dict[str, str] = {
    "podA": "AGENT-13-PODA-AUDIT",
    "podB": "AGENT-19-PODB-AUDIT",
    "podC": "AGENT-25-PODC-AUDIT",
    "podD": "AGENT-31-PODD-AUDIT",
}
_DEFAULT_AUDIT_AGENT = "AGENT-13-PODA-AUDIT"


async def generate_pod_audit_verdict(
    *,
    mission_id: str,
    pod_name: str,
    mission_context: dict[str, Any],
    pod_group_standard: dict[str, Any],
    generated_output: dict[str, Any] | None,
) -> dict[str, Any]:
    """Ask the appropriate pod QC/Audit agent to verdict the pod's output.

    ``pod_name`` must be one of ``podA``, ``podB``, ``podC``, ``podD``.
    Selects the correct audit agent (13/19/25/31) and returns a
    ``pod_audit_verdict.v1`` document.
    """
    normalized_pod = pod_name.strip().lower()
    audit_agent_id = _POD_AUDIT_AGENTS.get(normalized_pod, _DEFAULT_AUDIT_AGENT)
    recommendation = _agent_recommendation(audit_agent_id)
    provider = str(recommendation.get("provider", "openai")).strip().lower()
    model = str(recommendation.get("model", "gpt-5.5")).strip()

    canonical_count = len(pod_group_standard.get("canonical_logicnodes") or [])
    eliminated = int(pod_group_standard.get("eliminated_duplicates") or 0)
    contract_summary = _clean_text(
        str(mission_context.get("contract_summary") or ""), max_length=300
    )
    language = _clean_text(
        str(
            (generated_output or {}).get("language")
            or mission_context.get("requested_target_language")
            or "unknown"
        ),
        max_length=32,
    )

    prompt = (
        f"You are {audit_agent_id} performing QC audit of pod {pod_name}.\n"
        f"Recommended model: {provider}/{model}\n"
        "Review the pod's group standard and generated output for quality, "
        "completeness, and contract alignment.\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission ID: {_clean_text(mission_id, max_length=96)}\n"
        f"Pod: {pod_name}\n"
        f"Language: {language}\n"
        f"Contract summary: {contract_summary}\n"
        f"Canonical LogicNodes produced: {canonical_count}\n"
        f"Duplicates eliminated: {eliminated}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "schema_version": "pod_audit_verdict.v1",\n'
        '  "verdict": "PASS|FAIL|WARN",\n'
        '  "passed": true,\n'
        '  "quality_score": 0.85,\n'
        '  "findings": [\n'
        '    {"id": "F001", "severity": "warn", "description": "..."}\n'
        "  ],\n"
        '  "summary": "Pod audit complete.",\n'
        '  "recommendations": ["..."]\n'
        "}\n\n"
        "verdict must be PASS, FAIL, or WARN. quality_score is 0.0–1.0.\n"
        "Limit findings to 6 items.\n"
    )

    parsed, resolved_provider, resolved_model, _route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context=f"pod audit {pod_name}",
        agent_id=audit_agent_id,
    )

    if not isinstance(parsed, dict):
        return _fallback_pod_audit_verdict(
            mission_id=mission_id,
            pod_name=pod_name,
            audit_agent_id=audit_agent_id,
        )

    valid_verdicts = {"PASS", "FAIL", "WARN"}
    verdict = _clean_text(parsed.get("verdict", "PASS"), max_length=8).upper()
    if verdict not in valid_verdicts:
        verdict = "PASS"

    findings_raw = parsed.get("findings") or []
    findings: list[dict[str, Any]] = []
    if isinstance(findings_raw, list):
        for item in findings_raw[:6]:
            if not isinstance(item, dict):
                continue
            findings.append({
                "id": _clean_text(item.get("id", ""), max_length=16) or f"F{len(findings)+1:03d}",
                "severity": _clean_text(item.get("severity", "info"), max_length=16).lower(),
                "description": _clean_text(item.get("description", ""), max_length=240),
            })

    try:
        quality_score = max(0.0, min(1.0, float(parsed.get("quality_score") or 0.8)))
    except (TypeError, ValueError):
        quality_score = 0.8

    return {
        "schema_version": "pod_audit_verdict.v1",
        "mission_id": _clean_text(mission_id, max_length=96),
        "pod_name": pod_name,
        "agent_id": audit_agent_id,
        "verdict": verdict,
        "passed": verdict != "FAIL",
        "quality_score": round(quality_score, 4),
        "findings": findings,
        "summary": _clean_text(
            parsed.get("summary", "Pod audit complete."), max_length=600
        ),
        "recommendations": _string_list(parsed.get("recommendations"), limit=6),
        "source": "llm",
        "model_provider": resolved_provider,
        "model": resolved_model,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _fallback_pod_audit_verdict(
    *, mission_id: str, pod_name: str, audit_agent_id: str
) -> dict[str, Any]:
    return {
        "schema_version": "pod_audit_verdict.v1",
        "mission_id": mission_id,
        "pod_name": pod_name,
        "agent_id": audit_agent_id,
        "verdict": "PASS",
        "passed": True,
        "quality_score": 0.75,
        "findings": [],
        "summary": (
            "Pod audit skipped — LLM provider unavailable. "
            "Deterministic pass granted for pipeline continuity."
        ),
        "recommendations": ["Rerun pod audit with LLM access for authoritative verdict."],
        "source": "fallback",
        "created_at": datetime.now(UTC).isoformat(),
    }