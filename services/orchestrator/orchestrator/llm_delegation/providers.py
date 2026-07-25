from __future__ import annotations

import importlib
import logging
import os
import re
import time
from typing import Any

import httpx

from shared_runtime.pii_guard import redact_pii
from shared_runtime.prompt_guard import check_prompt

from .agents import _system_prompt_for_agent
from .config import (
    _GEMINI_THINKING_LEVEL,
    _RETRYABLE_HTTP_ERRORS,
    ANTHROPIC_BASE_URL,
    ANTHROPIC_TIMEOUT_SECONDS,
    ANTHROPIC_VERSION,
    GEMINI_BASE_URL,
    GEMINI_TIMEOUT_SECONDS,
    LLM_SAFETY_BLOCK_ENABLED,
    OPENAI_BASE_URL,
    OPENAI_TIMEOUT_SECONDS,
    PROMPT_GUARD_BLOCK_ENABLED,
    PROMPT_GUARD_BLOCK_LEVEL,
    _record_usage_event,
    current_agent_id,
)
from .health import (
    _record_provider_health,
    is_circuit_open,
    record_failure,
    record_success,
)
from .text import (
    _extract_anthropic_text,
    _extract_decision_payload,
    _extract_gemini_text,
    _extract_openai_text,
)

LOGGER = logging.getLogger(__name__)

# Ordered severity for prompt-injection risk levels (OWASP LLM01).
_PROMPT_RISK_PRIORITY = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def check_user_input(text: str, call_context: str) -> bool:
    """OWASP LLM01 — scan a *user-supplied* fragment for prompt injection.

    Returns True when the fragment is safe to embed in an outbound prompt, and
    False when it should be blocked. Apply this to untrusted free-text
    (mission/operator description, file content, chat messages) BEFORE it is
    interpolated into a prompt — never to system-authored prompt scaffolding,
    which legitimately contains agent IDs and instruction phrasing.

    Blocking is governed by ``PROMPT_GUARD_BLOCK_ENABLED`` and
    ``PROMPT_GUARD_BLOCK_LEVEL``; below the threshold the hit is logged only.
    """
    if not text:
        return True
    result = check_prompt(text)
    if not result.is_suspicious:
        return True
    LOGGER.warning("prompt injection detected [%s]: %s", call_context, result.summary)
    block_threshold = _PROMPT_RISK_PRIORITY.get(PROMPT_GUARD_BLOCK_LEVEL, 3)
    detected = _PROMPT_RISK_PRIORITY.get(result.risk_level, 0)
    return not (PROMPT_GUARD_BLOCK_ENABLED and detected >= block_threshold)


def _pkg() -> Any:
    """Return the public ``llm_delegation`` package module.

    Transport helpers resolve a handful of mutable symbols (API keys, retry
    constants, ``httpx``/``asyncio``, and the provider call functions) through
    this accessor so that tests which ``monkeypatch.setattr`` them on the
    package namespace continue to affect the live call sites after the
    monolith was split into this package (issue #186).
    """
    return importlib.import_module(__package__)

def _retry_delay_for_response(response: httpx.Response, default_delay: float) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after is None:
        return default_delay
    try:
        parsed_delay = float(retry_after)
    except ValueError:
        return default_delay
    return max(default_delay, parsed_delay)


async def _send_rho_traffic_control(
    *,
    rate_limit_action: str,
    agent_target: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit a Protocol Rho traffic-control telemetry message (PBLA-04).

    Fire-and-forget. The transport layer has no ``settings`` in scope, so bus
    config is resolved via ``load_settings()`` — only reached on a real
    rate-limit event, which is rare and already gated behind backoff. Stamps the
    PBLA discriminator (``protocol_bus_emissions``) so a future EDCP Rho consumer
    can filter this shadow telemetry, and lets the producer mint a fresh
    correlation_id so distinct rate-limit events are each recorded, not deduped.
    """
    import asyncio  # noqa: PLC0415

    from ..protocol_bus_emissions import (  # noqa: PLC0415
        EMISSION_KEY,
        PBLA_TRAFFIC_TELEMETRY,
    )
    from ..protocol_bus_producer import send_rho_control  # noqa: PLC0415
    from ..settings import load_settings  # noqa: PLC0415

    try:
        await asyncio.to_thread(
            send_rho_control,
            settings=load_settings(),
            sender="AGENT-03-BROKER",
            recipient="broadcast",
            token_budget=0,
            rate_limit_action=rate_limit_action,
            agent_target=agent_target,
            metadata={
                EMISSION_KEY: PBLA_TRAFFIC_TELEMETRY,
                **(metadata or {}),
            },
        )
    except Exception:
        LOGGER.warning(
            "Rho traffic-control dispatch failed (non-blocking): target=%s",
            agent_target,
        )


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
    pkg = _pkg()
    max_retries = pkg._LLM_MAX_RETRIES
    delay = pkg._LLM_RETRY_BASE_SECONDS
    for attempt in range(1, max_retries + 1):
        try:
            async with pkg.httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=json_payload, headers=headers, params=params)
            # Retry on 429 and 5xx responses only.
            if response.status_code == 429 or response.status_code >= 500:
                if response.status_code == 429:
                    # PBLA-04: a 429 is the canonical traffic-control signal —
                    # emit it on the Rho lane (fire-and-forget telemetry).
                    await _send_rho_traffic_control(
                        rate_limit_action="retry_backoff",
                        agent_target=current_agent_id.get() or "unknown",
                        metadata={
                            "call_context": call_context,
                            "status_code": response.status_code,
                            "attempt": attempt,
                        },
                    )
                if attempt < max_retries:
                    retry_delay = _retry_delay_for_response(response, delay)
                    LOGGER.warning(
                        "%s attempt %d/%d returned %s — retrying in %.1fs",
                        call_context,
                        attempt,
                        max_retries,
                        response.status_code,
                        retry_delay,
                    )
                    await pkg.asyncio.sleep(retry_delay)
                    delay *= 2
                    continue
            return response
        except _RETRYABLE_HTTP_ERRORS as exc:
            if attempt < max_retries:
                LOGGER.warning(
                    "%s attempt %d/%d network error (%s) — retrying in %.1fs",
                    call_context, attempt, max_retries, exc, delay,
                )
                await pkg.asyncio.sleep(delay)
                delay *= 2
            else:
                LOGGER.warning("%s all %d attempts failed: %s", call_context, max_retries, exc)
    return None


async def _call_openai(
    model: str,
    prompt: str,
    *,
    call_context: str,
    system_prompt: str | None = None,
) -> dict[str, Any] | None:
    # Per-mission vault keys set by runtime.py from the Mission Control vault take
    # precedence over the process-level .env keys. This is what lets operators
    # manage provider keys entirely from the Settings page (required for the
    # packaged Windows app, where editing .env is not an option). Read the
    # ContextVar directly from .config so it works regardless of package exports.
    from .config import current_vault_secrets
    vault_map = current_vault_secrets.get() or {}
    openai_api_key = vault_map.get("openai_api_key") or _pkg().OPENAI_API_KEY
    if not openai_api_key:
        return None
    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    # Regex to find: data:<mime>;base64,<data>
    pattern = re.compile(r"data:((?:image|application)/[a-zA-Z0-9.+-]+);base64,([a-zA-Z0-9+/=\s]+)")
    last_idx = 0
    openai_parts = []
    has_media = False

    for match in pattern.finditer(prompt):
        start, end = match.span()
        text_before = prompt[last_idx:start].strip()
        if text_before:
            openai_parts.append({"type": "text", "text": text_before})

        mime_type = match.group(1)
        base64_data = re.sub(r"\s+", "", match.group(2))

        if mime_type.startswith("image/"):
            openai_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_data}"
                }
            })
            has_media = True
        else:
            openai_parts.append({
                "type": "text",
                "text": f"\n[Attached file: {mime_type}]\n"
            })
        last_idx = end

    text_after = prompt[last_idx:].strip()
    if text_after:
        openai_parts.append({"type": "text", "text": text_after})

    if has_media:
        messages.append({"role": "user", "content": openai_parts})
    else:
        messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "input": messages,
        "reasoning": {"effort": "high"},
    }
    headers = {"Authorization": f"Bearer {openai_api_key}"}
    response = await _pkg()._post_with_retry(
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
    # Per-mission vault keys set by runtime.py from the Mission Control vault take
    # precedence over the process-level .env keys. This is what lets operators
    # manage provider keys entirely from the Settings page (required for the
    # packaged Windows app, where editing .env is not an option). Read the
    # ContextVar directly from .config so it works regardless of package exports.
    from .config import current_vault_secrets
    vault_map = current_vault_secrets.get() or {}
    anthropic_api_key = vault_map.get("anthropic_api_key") or _pkg().ANTHROPIC_API_KEY
    if not anthropic_api_key:
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
        "x-api-key": anthropic_api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "anthropic-beta": "prompt-caching-2024-07-31",
        "content-type": "application/json",
    }
    response = await _pkg()._post_with_retry(
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
    # Per-mission vault keys set by runtime.py from the Mission Control vault take
    # precedence over the process-level .env keys. This is what lets operators
    # manage provider keys entirely from the Settings page (required for the
    # packaged Windows app, where editing .env is not an option). Read the
    # ContextVar directly from .config so it works regardless of package exports.
    from .config import current_vault_secrets
    vault_map = current_vault_secrets.get() or {}
    gemini_api_key = vault_map.get("gemini_api_key") or _pkg().GEMINI_API_KEY
    if not gemini_api_key:
        return None
    # Parse prompt for base64 parts
    pattern = re.compile(r"data:((?:image|application)/[a-zA-Z0-9.+-]+);base64,([a-zA-Z0-9+/=\s]+)")
    last_idx = 0
    gemini_parts = []

    for match in pattern.finditer(prompt):
        start, end = match.span()
        text_before = prompt[last_idx:start].strip()
        if text_before:
            gemini_parts.append({"text": text_before})

        mime_type = match.group(1)
        base64_data = re.sub(r"\s+", "", match.group(2))

        gemini_parts.append({
            "inlineData": {
                "mimeType": mime_type,
                "data": base64_data
            }
        })
        last_idx = end

    text_after = prompt[last_idx:].strip()
    if text_after:
        gemini_parts.append({"text": text_after})

    if not gemini_parts:
        gemini_parts.append({"text": prompt})

    payload: dict[str, Any] = {"contents": [{"parts": gemini_parts}]}
    if system_prompt:
        payload["system_instruction"] = {"parts": [{"text": system_prompt}]}
    # Gemini 3.x sets thinking via generationConfig.thinkingConfig.thinkingLevel
    # (camelCase REST fields; valid levels: minimal | low | medium | high). The
    # earlier flat snake_case "thinking_level" was rejected with HTTP 400.
    payload["generationConfig"] = {
        "thinkingConfig": {"thinkingLevel": _GEMINI_THINKING_LEVEL},
    }
    # Pass the API key via the x-goog-api-key header rather than a ?key= query
    # param so it never lands in request-URL logs (httpx logs the full URL).
    response = await _pkg()._post_with_retry(
        f"{GEMINI_BASE_URL}/models/{model}:generateContent",
        json_payload=payload,
        headers={"content-type": "application/json", "x-goog-api-key": gemini_api_key},
        timeout=GEMINI_TIMEOUT_SECONDS,
        call_context=f"{call_context} gemini",
    )
    if response is None:
        return None
    if response.status_code >= 400:
        # Include a truncated response body so misconfigured model/payload
        # errors are diagnosable from the log without a separate live call.
        _body = ""
        try:
            _body = response.text[:300]
        except Exception:  # noqa: BLE001
            _body = "<unreadable body>"
        LOGGER.warning("%s gemini status=%s body=%s", call_context, response.status_code, _body)
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

    pkg = _pkg()
    started = time.perf_counter()
    result: dict[str, Any] | None = None
    try:
        if normalized == "anthropic":
            result = await _call_backend(pkg._call_anthropic)
        elif normalized == "gemini":
            result = await _call_backend(pkg._call_gemini)
        else:
            result = await _call_backend(pkg._call_openai)
        return result
    finally:
        elapsed_seconds = time.perf_counter() - started
        try:
            _record_provider_health(
                provider=normalized or "openai",
                model=model,
                latency_ms=elapsed_seconds * 1000,
                success=isinstance(result, dict),
            )
        except Exception:
            LOGGER.warning("failed to record provider health telemetry", exc_info=True)
        try:
            from .metrics import record_llm_request

            record_llm_request(
                provider=normalized or "openai",
                model=model,
                agent_id=current_agent_id.get() or "unknown",
                status="success" if isinstance(result, dict) else "error",
                duration_seconds=elapsed_seconds,
            )
        except Exception:
            LOGGER.warning("failed to record llm request metric", exc_info=True)


async def _call_with_recommendation(
    *,
    recommendation: dict[str, Any],
    prompt: str,
    call_context: str,
    system_prompt: str | None = None,
) -> tuple[dict[str, Any] | None, str, str, str]:
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.6-flash")).strip()


    # Security Hardening: redact PII from the prompt before sending to any
    # provider. Placed here (not in _call_with_agent_system) so that ALL callers
    # benefit, including the direct _call_with_recommendation paths.
    redacted_prompt, pii_matches = redact_pii(prompt)
    if pii_matches:
        LOGGER.info(
            "PII redaction active for %s: %d matches scrubbed",
            call_context,
            len(pii_matches),
        )
        prompt = redacted_prompt

    # Safety envelope — scan outbound prompt before any LLM call
    from ..llm_safety import (  # noqa: PLC0415
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
        call_provider = _pkg()._call_provider
        try:
            return await call_provider(
                provider=route_provider,
                model=route_model,
                prompt=prompt,
                call_context=route_context,
                system_prompt=system_prompt,
            )
        except TypeError as exc:
            if "system_prompt" not in str(exc):
                raise
            return await call_provider(
                provider=route_provider,
                model=route_model,
                prompt=prompt,
                call_context=route_context,
            )

    # Circuit breaker: skip the primary provider entirely while its circuit is
    # open, routing straight to the fallback instead of issuing a doomed call.
    primary_circuit_open = is_circuit_open(provider)
    if primary_circuit_open:
        LOGGER.warning(
            "%s skipping provider %s — circuit breaker open", call_context, provider
        )
        parsed = None
    else:
        parsed = await _provider_call(
            route_provider=provider,
            route_model=model,
            route_context=call_context,
        )
        if isinstance(parsed, dict):
            record_success(provider)
        else:
            record_failure(provider)

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

    # Do not cascade to a different provider than the one the operator explicitly
    # pinned via LLM_PROVIDER. Otherwise a primary failure routes to a secondary
    # provider that may be misconfigured (e.g. gemini-mode cascading to OpenAI
    # gpt-5.5), producing doomed calls that trip the shared circuit breaker and
    # silently degrade every agent. When a provider is pinned, fail straight to
    # the deterministic fallback instead.
    explicit_provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit_provider and fallback_provider != explicit_provider:
        return None, provider, model, "primary"

    if is_circuit_open(fallback_provider):
        LOGGER.warning(
            "%s skipping fallback provider %s — circuit breaker open",
            call_context,
            fallback_provider,
        )
        return None, provider, model, "primary"

    fallback = await _provider_call(
        route_provider=fallback_provider,
        route_model=fallback_model,
        route_context=f"{call_context} (fallback)",
    )
    if isinstance(fallback, dict):
        record_success(fallback_provider)
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
    record_failure(fallback_provider)
    return None, provider, model, "primary"


async def _call_with_agent_system(
    *,
    recommendation: dict[str, Any],
    prompt: str,
    call_context: str,
    agent_id: str,
) -> tuple[dict[str, Any] | None, str, str, str]:
    """Call the recommendation helper with persona system prompt when supported."""
    # PII redaction and OWASP LLM01 prompt-injection scanning happen at the
    # _call_with_recommendation chokepoint below, so all callers are covered.
    call_with_recommendation = _pkg()._call_with_recommendation
    token = current_agent_id.set(agent_id)
    try:
        try:
            return await call_with_recommendation(
                recommendation=recommendation,
                prompt=prompt,
                call_context=call_context,
                system_prompt=_system_prompt_for_agent(agent_id),
            )
        except TypeError as exc:
            if "system_prompt" not in str(exc):
                raise
            return await call_with_recommendation(
                recommendation=recommendation,
                prompt=prompt,
                call_context=call_context,
            )
    finally:
        current_agent_id.reset(token)

