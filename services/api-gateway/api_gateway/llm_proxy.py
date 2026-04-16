"""llm_proxy.py — Builder preview LLM proxy calls (OpenAI, Anthropic, Gemini)."""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from .config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_BASE_URL,
    ANTHROPIC_THINKING_BUDGET_TOKENS,
    ANTHROPIC_THINKING_MODE,
    ANTHROPIC_TIMEOUT_SECONDS,
    ANTHROPIC_VERSION,
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    GEMINI_THINKING_BUDGET,
    GEMINI_THINKING_LEVEL,
    GEMINI_TIMEOUT_SECONDS,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_REASONING_EFFORT,
    OPENAI_TIMEOUT_SECONDS,
)

LOGGER = logging.getLogger(__name__)


class BuilderPreviewPayload:
    """Minimal duck-type used by LLM helpers — avoids importing the Pydantic model here."""

    def __init__(
        self,
        *,
        request: str,
        constraints: list[str],
        view_mode: str | None,
        provider: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        thinking_budget: int | None = None,
    ) -> None:
        self.request = request
        self.constraints = constraints
        self.view_mode = view_mode
        self.provider = provider
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.thinking_budget = thinking_budget


def _normalize_builder_text(value: str) -> str:
    return " ".join(value.split())


def _collect_distinct_lines(value: str, limit: int) -> list[str]:
    lines: list[str] = []
    for raw_line in value.splitlines():
        candidate = raw_line.strip().lstrip("-*").strip()
        if not candidate or candidate in lines:
            continue
        lines.append(candidate)
        if len(lines) >= limit:
            break
    return lines


def _build_offline_builder_preview(
    payload: Any,
    *,
    source: str = "offline",
    notice: str | None = None,
) -> dict[str, Any]:
    normalized_request = _normalize_builder_text(payload.request)
    constraints = [
        _normalize_builder_text(item)
        for item in payload.constraints
        if isinstance(item, str) and _normalize_builder_text(item)
    ][:5]
    key_constraint = constraints[0] if constraints else "Preserve existing architecture boundaries."

    response: dict[str, Any] = {
        "request_id": f"builder-{uuid.uuid4()}",
        "source": source,
        "generated_at": datetime.now(UTC).isoformat(),
        "plan": [
            {
                "title": "Scope and acceptance criteria",
                "description": f"Clarify boundaries for: {normalized_request[:180]}",
            },
            {
                "title": "Implementation slices",
                "description": (
                    "Deliver in thin vertical slices across API, UI, and persistence "
                    "with rollback safety."
                ),
            },
            {
                "title": "Validation and hardening",
                "description": "Add tests, lint, and production checks before merge.",
            },
        ],
        "diff_summary": [
            f"Proposed change request: {normalized_request[:220]}",
            f"Primary constraint: {key_constraint[:180]}",
            f"Viewport target: {payload.view_mode or 'desktop'}",
        ],
        "risk_notes": [
            "Verify backward compatibility for existing mission routes and payload contracts.",
            "Guard UI changes with loading/error states to avoid stale operator actions.",
            "Validate input sanitization and idempotency for mutation endpoints.",
        ],
        "test_plan": [
            "Add unit tests for parsing and route behavior.",
            "Run service tests, lint checks, and frontend build verification.",
            "Run smoke tests against local docker stack before release.",
        ],
    }
    if notice:
        response["notice"] = notice
    return response


def _build_builder_prompt(payload: Any) -> str:
    constraints_text = "\n".join(
        f"- {_normalize_builder_text(item)}"
        for item in payload.constraints
        if isinstance(item, str) and _normalize_builder_text(item)
    )
    user_prompt = payload.request
    if constraints_text:
        user_prompt = f"{payload.request}\n\nConstraints:\n{constraints_text}"
    if payload.view_mode:
        user_prompt = f"{user_prompt}\n\nViewport: {payload.view_mode}"
    return user_prompt


def _extract_openai_text(payload: dict[str, Any]) -> str | None:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    if isinstance(output_text, list):
        collected = [item.strip() for item in output_text if isinstance(item, str) and item.strip()]
        if collected:
            return "\n".join(collected)

    output_items = payload.get("output")
    if isinstance(output_items, list):
        collected_parts: list[str] = []
        for item in output_items:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                text_value = block.get("text")
                if isinstance(text_value, str) and text_value.strip():
                    collected_parts.append(text_value.strip())
        if collected_parts:
            return "\n".join(collected_parts)

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
    return None


def _extract_anthropic_text(payload: dict[str, Any]) -> str | None:
    content = payload.get("content")
    if not isinstance(content, list):
        return None

    collected: list[str] = []
    for item in content:
        if not isinstance(item, dict) or item.get("type") != "text":
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            collected.append(text.strip())

    return "\n".join(collected) if collected else None


def _extract_gemini_text(payload: dict[str, Any]) -> str | None:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return None

    collected: list[str] = []
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
                collected.append(text.strip())

    return "\n".join(collected) if collected else None


def _is_gemini_3_model(model: str) -> bool:
    normalized = model.strip().lower()
    return normalized.startswith("gemini-3-") or normalized.startswith("gemini-3.1-")


def _to_gemini_thinking_level(reasoning_effort: str | None) -> str:
    effort = (reasoning_effort or "").strip().lower()
    if effort in {"none", "minimal", "low"}:
        return "low"
    if effort in {"high", "xhigh"}:
        return "high"
    return "medium"


def _apply_llm_lines_to_preview(
    preview: dict[str, Any], summary_lines: list[str]
) -> dict[str, Any]:
    if summary_lines:
        preview["plan"][0]["description"] = summary_lines[0]
        preview["diff_summary"] = summary_lines[:4]
        if len(summary_lines) > 4:
            preview["risk_notes"] = summary_lines[4:7]
    preview["notice"] = "Generated from live LLM output."
    return preview


async def _openai_builder_preview(
    payload: Any,
    *,
    model: str,
    reasoning_effort: str | None,
) -> dict[str, Any] | None:
    user_prompt = _build_builder_prompt(payload)
    request_payload: dict[str, Any] = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You are a software architect. Provide concise implementation guidance "
                    "for a local enterprise application."
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
    }
    if reasoning_effort:
        request_payload["reasoning"] = {"effort": reasoning_effort}

    try:
        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{OPENAI_BASE_URL}/responses",
                json=request_payload,
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
    except Exception as exc:
        LOGGER.warning("openai preview request failed: %s", exc)
        return None

    if response.status_code >= 400:
        LOGGER.warning("openai preview returned non-success status: %s", response.status_code)
        return None

    try:
        payload_json = response.json()
    except ValueError:
        LOGGER.warning("openai preview returned non-json payload")
        return None

    llm_text = _extract_openai_text(payload_json)
    if llm_text is None:
        LOGGER.warning("openai preview response did not contain readable text")
        return None

    return _apply_llm_lines_to_preview(
        _build_offline_builder_preview(payload, source="openai"),
        _collect_distinct_lines(llm_text, 8),
    )


async def _anthropic_builder_preview(
    payload: Any,
    *,
    model: str,
    thinking_mode: str,
    thinking_budget: int,
) -> dict[str, Any] | None:
    user_prompt = _build_builder_prompt(payload)
    request_payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 1200,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if thinking_mode == "enabled":
        request_payload["thinking"] = {
            "type": "enabled",
            "budget_tokens": max(1024, thinking_budget),
        }
    elif thinking_mode == "adaptive":
        request_payload["thinking"] = {"type": "adaptive"}

    try:
        async with httpx.AsyncClient(timeout=ANTHROPIC_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{ANTHROPIC_BASE_URL}/messages",
                json=request_payload,
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "Content-Type": "application/json",
                },
            )
    except Exception as exc:
        LOGGER.warning("anthropic preview request failed: %s", exc)
        return None

    if response.status_code >= 400:
        LOGGER.warning("anthropic preview returned non-success status: %s", response.status_code)
        return None

    try:
        payload_json = response.json()
    except ValueError:
        LOGGER.warning("anthropic preview returned non-json payload")
        return None

    llm_text = _extract_anthropic_text(payload_json)
    if llm_text is None:
        LOGGER.warning("anthropic preview response did not contain readable text")
        return None

    return _apply_llm_lines_to_preview(
        _build_offline_builder_preview(payload, source="anthropic"),
        _collect_distinct_lines(llm_text, 8),
    )


async def _gemini_builder_preview(
    payload: Any,
    *,
    model: str,
    thinking_budget: int,
    thinking_level: str | None,
) -> dict[str, Any] | None:
    user_prompt = _build_builder_prompt(payload)
    generation_config: dict[str, Any] = {"temperature": 0.2, "maxOutputTokens": 1200}
    if _is_gemini_3_model(model):
        generation_config["thinkingConfig"] = {
            "thinkingLevel": _to_gemini_thinking_level(thinking_level),
        }
    elif thinking_budget >= 0:
        generation_config["thinkingConfig"] = {"thinkingBudget": thinking_budget}

    try:
        async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{GEMINI_BASE_URL}/models/{model}:generateContent",
                params={"key": GEMINI_API_KEY},
                json={
                    "contents": [{"parts": [{"text": user_prompt}]}],
                    "generationConfig": generation_config,
                },
                headers={"Content-Type": "application/json"},
            )
    except Exception as exc:
        LOGGER.warning("gemini preview request failed: %s", exc)
        return None

    if response.status_code >= 400:
        LOGGER.warning("gemini preview returned non-success status: %s", response.status_code)
        return None

    try:
        payload_json = response.json()
    except ValueError:
        LOGGER.warning("gemini preview returned non-json payload")
        return None

    llm_text = _extract_gemini_text(payload_json)
    if llm_text is None:
        LOGGER.warning("gemini preview response did not contain readable text")
        return None

    return _apply_llm_lines_to_preview(
        _build_offline_builder_preview(payload, source="gemini"),
        _collect_distinct_lines(llm_text, 8),
    )


__all__ = [
    "ANTHROPIC_THINKING_BUDGET_TOKENS",
    "ANTHROPIC_THINKING_MODE",
    "GEMINI_THINKING_BUDGET",
    "GEMINI_THINKING_LEVEL",
    "OPENAI_REASONING_EFFORT",
    "_anthropic_builder_preview",
    "_build_offline_builder_preview",
    "_collect_distinct_lines",
    "_extract_anthropic_text",
    "_extract_gemini_text",
    "_extract_openai_text",
    "_gemini_builder_preview",
    "_is_gemini_3_model",
    "_normalize_builder_text",
    "_openai_builder_preview",
    "_to_gemini_thinking_level",
]
