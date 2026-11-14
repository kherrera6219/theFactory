"""Provider-native multi-turn LLM adapters for the AgentHarness.

Verified official provider API specifications (checked 2026-11-13):
- Gemini (`gemini-4-argon` / `v1beta/models/{model}:generateContent`):
  * Auth: `x-goog-api-key` header.
  * Messages: `contents` with `role` in `{"user", "model"}` and `parts`.
  * Client tools: `tools: [{"functionDeclarations": [{"name", "description", "parameters"}]}]`.
  * Hosted tools: `{"google_search": {}}`, `{"url_context": {}}`, `{"code_execution": {}}`.
  * Thinking: `generationConfig.thinkingConfig = {"thinkingLevel": "LOW"|"MEDIUM"|"HIGH"}`.
  * Citations: `candidates[*].groundingMetadata.groundingChunks[*].web.{uri,title}`.
- Anthropic (`claude-opus-5-5` / `POST /v1/messages`):
  * Auth & headers: `x-api-key`, `anthropic-version: 2023-06-01`, optional `anthropic-beta`.
  * Client tools: `tools: [{"name", "description", "input_schema"}]`.
  * Hosted tools: `{"type": "web_search_20250305", "name": "web_search"}`,
    `{"type": "code_execution_20250825", "name": "code_execution"}`.
  * Thinking: `thinking: {"type": "enabled", "budget_tokens": N}`. Assistant `thinking`
    (with `signature`) and `redacted_thinking` blocks MUST be preserved intact on replay.
- OpenAI (`gpt-6.1-terrea` / `POST /v1/responses`, plus Chat Completions compatibility):
  * Auth: `Authorization: Bearer <key>`.
  * Client tools: `tools: [{"type": "function", "name", "description", "parameters"}]`.
  * Hosted tools: `{"type": "web_search"}`,
    `{"type": "code_interpreter", "container": {"type": "auto"}}`.
  * Tool calls: `/responses` `output` items with `type == "function_call"` (`call_id`,
    `name`, `arguments`) paired with `{"type": "function_call_output", "call_id", "output"}`;
    also accepts Chat Completions `choices[0].message.tool_calls` for mock/compat payloads.
- Ollama / vLLM local (`POST /api/chat` or `/v1/chat/completions`):
  * OpenAI-compatible `tools: [{"type": "function", "function": {...}}]` and
    `message.tool_calls` with `{"role": "tool", "tool_call_id", "name", "content"}`.
"""

from __future__ import annotations

import copy
import importlib
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from shared_runtime.pii_guard import redact_pii

from .capabilities import ModelCapabilities, get_model_capabilities
from .config import (
    _GEMINI_THINKING_LEVEL,
    _record_usage_event,
    current_agent_id,
    current_settings,
    current_vault_secrets,
)
from .health import _record_provider_health, is_circuit_open, record_failure, record_success
from .text import _extract_anthropic_text, _extract_gemini_text, _extract_openai_text

LOGGER = logging.getLogger(__name__)


def _pkg() -> Any:
    return importlib.import_module(__package__)


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Normalized JSON-Schema tool specification passed to provider adapters."""

    name: str
    description: str
    parameters: dict[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Normalized client tool invocation requested by an LLM."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    raw_arguments: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": copy.deepcopy(self.arguments),
        }


@dataclass(frozen=True, slots=True)
class ServerToolUse:
    """Normalized provider-hosted tool call observed in a model turn."""

    id: str
    name: str
    tool_type: str
    input: dict[str, Any] = field(default_factory=dict)
    output: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Citation:
    """Grounded source citation returned by a model or hosted search tool."""

    url: str
    title: str = ""
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Normalized token accounting for one provider turn."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class AssistantTurn:
    """Structured response from one multi-turn provider invocation."""

    provider: str
    model: str
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    server_tool_uses: list[ServerToolUse] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    stop_reason: str = "stop"
    usage: TokenUsage = field(default_factory=TokenUsage)
    raw_blocks: list[dict[str, Any]] = field(default_factory=list)
    thinking_blocks: list[dict[str, Any]] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


def _safe_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return {}
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
            return {"value": parsed}
        except json.JSONDecodeError:
            return {"_raw": stripped}
    return {}


def _scrub_outbound_text(text: str, call_context: str) -> tuple[str, bool]:
    """Redact PII and apply llm_safety outbound scan. Returns (clean_text, allowed)."""
    if not text:
        return "", True
    pkg = _pkg()
    cleaned, _ = redact_pii(text)
    from ..llm_safety import check_outbound_prompt, sanitize_outbound_prompt  # noqa: PLC0415

    violations = check_outbound_prompt(cleaned, call_context)
    if violations:
        LOGGER.warning("LLM safety outbound violations [%s]: %s", call_context, violations)
        if bool(getattr(pkg, "LLM_SAFETY_BLOCK_ENABLED", False)):
            return "", False
        cleaned = sanitize_outbound_prompt(cleaned)
    return cleaned, True


def _sanitize_messages_for_outbound(
    messages: list[dict[str, Any]],
    call_context: str,
) -> tuple[list[dict[str, Any]], bool]:
    sanitized: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        cloned = copy.deepcopy(msg)
        content = cloned.get("content")
        if isinstance(content, str):
            clean_text, allowed = _scrub_outbound_text(content, call_context)
            if not allowed:
                return [], False
            cloned["content"] = clean_text
        elif isinstance(content, list):
            new_blocks: list[Any] = []
            for block in content:
                if isinstance(block, dict):
                    b_copy = copy.deepcopy(block)
                    if b_copy.get("type") == "text" and isinstance(b_copy.get("text"), str):
                        clean_b, allowed = _scrub_outbound_text(b_copy["text"], call_context)
                        if not allowed:
                            return [], False
                        b_copy["text"] = clean_b
                    elif b_copy.get("type") == "tool_result" and isinstance(
                        b_copy.get("content"), str
                    ):
                        clean_r, allowed = _scrub_outbound_text(
                            b_copy["content"], call_context
                        )
                        if not allowed:
                            return [], False
                        b_copy["content"] = clean_r
                    new_blocks.append(b_copy)
                else:
                    new_blocks.append(block)
            cloned["content"] = new_blocks
        sanitized.append(cloned)
    return sanitized, True


def _record_turn_telemetry(
    *,
    provider: str,
    model: str,
    elapsed_seconds: float,
    turn: AssistantTurn | None,
    route: str,
) -> None:
    try:
        _record_provider_health(
            provider=provider,
            model=model,
            latency_ms=elapsed_seconds * 1000.0,
            success=turn is not None,
        )
    except Exception:
        LOGGER.warning("failed to record adapter provider health", exc_info=True)
    try:
        from .metrics import record_llm_request  # noqa: PLC0415

        record_llm_request(
            provider=provider,
            model=model,
            agent_id=current_agent_id.get() or "unknown",
            status="success" if turn is not None else "error",
            duration_seconds=elapsed_seconds,
        )
    except Exception:
        LOGGER.warning("failed to record adapter llm metric", exc_info=True)

    usage = turn.usage if turn is not None else TokenUsage()
    _record_usage_event(
        current_settings.get(),
        None,
        None,
        provider,
        model,
        usage.input_tokens,
        usage.output_tokens,
        turn is not None,
        route,
    )


class ProviderAdapter:
    """Base multi-turn provider adapter protocol & shared telemetry wrapper."""

    provider_name: str = "openai"

    def __init__(self, model: str | None = None, *, provider: str | None = None) -> None:
        self.provider = (provider or self.provider_name).strip().lower()
        self.capabilities: ModelCapabilities = get_model_capabilities(self.provider, model)
        self.model = self.capabilities.model

    def _resolve_api_key(self) -> str:
        return ""

    async def _invoke(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[ToolDefinition],
        native_tools: list[str],
        tool_choice: str | dict[str, Any] | None,
        max_output_tokens: int | None,
        thinking: dict[str, Any] | bool | None,
        response_schema: dict[str, Any] | None,
        stream: bool,
        system_prompt: str | None,
        call_context: str,
    ) -> AssistantTurn | None:
        raise NotImplementedError

    async def send(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[ToolDefinition] | None = None,
        native_tools: list[str] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        max_output_tokens: int | None = None,
        thinking: dict[str, Any] | bool | None = None,
        response_schema: dict[str, Any] | None = None,
        stream: bool = False,
        system_prompt: str | None = None,
        call_context: str = "agent_harness",
    ) -> AssistantTurn | None:
        """Send a multi-turn conversation payload and return an ``AssistantTurn``."""
        if is_circuit_open(self.provider):
            LOGGER.warning(
                "%s skipping provider %s — circuit breaker open", call_context, self.provider
            )
            return None

        clean_system = system_prompt
        if clean_system:
            clean_system, sys_ok = _scrub_outbound_text(clean_system, call_context)
            if not sys_ok:
                return None

        clean_messages, msgs_ok = _sanitize_messages_for_outbound(messages, call_context)
        if not msgs_ok:
            return None

        t0 = time.monotonic()
        turn: AssistantTurn | None = None
        try:
            turn = await self._invoke(
                clean_messages,
                tools=list(tools or []),
                native_tools=list(native_tools or []),
                tool_choice=tool_choice,
                max_output_tokens=max_output_tokens,
                thinking=thinking,
                response_schema=response_schema,
                stream=stream,
                system_prompt=clean_system,
                call_context=call_context,
            )
        except Exception as exc:
            LOGGER.warning("%s adapter invoke error (%s): %s", call_context, self.provider, exc)
            turn = None

        elapsed = max(0.0, time.monotonic() - t0)
        if turn is not None:
            record_success(self.provider)
        else:
            record_failure(self.provider)

        _record_turn_telemetry(
            provider=self.provider,
            model=self.model,
            elapsed_seconds=elapsed,
            turn=turn,
            route=f"adapter:{self.provider}",
        )
        return turn

    def build_assistant_message(self, turn: AssistantTurn) -> dict[str, Any]:
        """Convert an ``AssistantTurn`` into a replayable assistant history message."""
        return {
            "role": "assistant",
            "content": turn.text,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in turn.tool_calls
            ],
        }

    def build_tool_results_messages(
        self,
        turn: AssistantTurn,
        tool_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Format executed tool results for the next turn in this provider's protocol."""
        del turn
        return [
            {
                "role": "tool",
                "tool_call_id": str(item.get("tool_call_id") or ""),
                "name": str(item.get("name") or ""),
                "content": str(item.get("output_text") or ""),
            }
            for item in tool_results
        ]


class GeminiAdapter(ProviderAdapter):
    """Google Gemini `generateContent` multi-turn adapter (`v1beta`)."""

    provider_name = "gemini"

    def _resolve_api_key(self) -> str:
        vault = current_vault_secrets.get() or {}
        return (
            vault.get("gemini_api_key")
            or vault.get("google_api_key")
            or getattr(_pkg(), "GEMINI_API_KEY", "")
            or os.getenv("GOOGLE_API_KEY", "").strip()
        )

    @staticmethod
    def _to_gemini_contents(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        contents: list[dict[str, Any]] = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role") or "user").strip().lower()
            if role == "system":
                continue
            gemini_role = "model" if role in {"assistant", "model"} else "user"
            if isinstance(msg.get("parts"), list):
                contents.append({"role": gemini_role, "parts": copy.deepcopy(msg["parts"])})
                continue
            parts: list[dict[str, Any]] = []
            content = msg.get("content")
            if isinstance(content, str) and content:
                parts.append({"text": content})
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if "text" in block:
                            parts.append({"text": str(block["text"])})
                        elif "functionCall" in block or "functionResponse" in block:
                            parts.append(copy.deepcopy(block))
            if parts:
                contents.append({"role": gemini_role, "parts": parts})
        return contents

    def build_assistant_message(self, turn: AssistantTurn) -> dict[str, Any]:
        if turn.raw_blocks:
            return {"role": "assistant", "parts": copy.deepcopy(turn.raw_blocks)}
        parts: list[dict[str, Any]] = []
        if turn.text:
            parts.append({"text": turn.text})
        for tc in turn.tool_calls:
            parts.append({"functionCall": {"name": tc.name, "args": copy.deepcopy(tc.arguments)}})
        return {"role": "assistant", "parts": parts or [{"text": ""}]}

    def build_tool_results_messages(
        self,
        turn: AssistantTurn,
        tool_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        del turn
        parts = [
            {
                "functionResponse": {
                    "name": str(item.get("name") or ""),
                    "response": {
                        "result": item.get("output_data")
                        if item.get("output_data") is not None
                        else str(item.get("output_text") or ""),
                        "is_error": bool(item.get("is_error", False)),
                    },
                }
            }
            for item in tool_results
        ]
        return [{"role": "user", "parts": parts}]

    async def _invoke(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[ToolDefinition],
        native_tools: list[str],
        tool_choice: str | dict[str, Any] | None,
        max_output_tokens: int | None,
        thinking: dict[str, Any] | bool | None,
        response_schema: dict[str, Any] | None,
        stream: bool,
        system_prompt: str | None,
        call_context: str,
    ) -> AssistantTurn | None:
        del stream
        api_key = self._resolve_api_key()
        if not api_key:
            return None
        pkg = _pkg()
        payload: dict[str, Any] = {
            "contents": self._to_gemini_contents(messages),
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        tool_entries: list[dict[str, Any]] = []
        if tools and self.capabilities.supports_tools:
            tool_entries.append(
                {
                    "functionDeclarations": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "parameters": copy.deepcopy(t.parameters),
                        }
                        for t in tools
                    ]
                }
            )
        for native_name in native_tools:
            norm_native = native_name.strip().lower()
            if norm_native == "google_search" and self.capabilities.supports_native_web_search:
                tool_entries.append({"google_search": {}})
            elif norm_native == "url_context" and self.capabilities.supports_url_fetch:
                tool_entries.append({"url_context": {}})
            elif (
                norm_native == "code_execution"
                and self.capabilities.supports_native_code_execution
            ):
                tool_entries.append({"code_execution": {}})
        if tool_entries:
            payload["tools"] = tool_entries

        if tool_choice:
            mode = (
                str(tool_choice).upper()
                if isinstance(tool_choice, str)
                else str(tool_choice.get("mode", "AUTO")).upper()
            )
            if mode in {"AUTO", "ANY", "NONE", "VALIDATED"}:
                payload["toolConfig"] = {"functionCallingConfig": {"mode": mode}}

        gen_cfg: dict[str, Any] = {}
        if max_output_tokens is not None:
            gen_cfg["maxOutputTokens"] = int(max_output_tokens)
        if response_schema and self.capabilities.supports_structured_output:
            gen_cfg["responseMimeType"] = "application/json"
            gen_cfg["responseSchema"] = copy.deepcopy(response_schema)
        if self.capabilities.supports_thinking and thinking is not False:
            level = _GEMINI_THINKING_LEVEL.upper()
            if isinstance(thinking, dict) and thinking.get("level"):
                level = str(thinking["level"]).strip().upper()
            gen_cfg["thinkingConfig"] = {"thinkingLevel": level}
        if gen_cfg:
            payload["generationConfig"] = gen_cfg

        base_url = getattr(pkg, "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
        timeout = float(getattr(pkg, "GEMINI_TIMEOUT_SECONDS", 180.0))
        response = await pkg._post_with_retry(
            f"{base_url.rstrip('/')}/models/{self.model}:generateContent",
            json_payload=payload,
            headers={
                "x-goog-api-key": api_key,
                "content-type": "application/json",
            },
            timeout=timeout,
            call_context=call_context,
        )
        if response is None or response.status_code >= 400:
            if response is not None:
                LOGGER.warning("%s gemini returned status %s", call_context, response.status_code)
            return None

        raw_data = response.json()
        if not isinstance(raw_data, dict):
            return None

        candidates = raw_data.get("candidates")
        first_cand = candidates[0] if isinstance(candidates, list) and candidates else {}
        content = first_cand.get("content") if isinstance(first_cand, dict) else {}
        parts = content.get("parts") if isinstance(content, dict) else []
        raw_blocks: list[dict[str, Any]] = []
        text_chunks: list[str] = []
        thinking_blocks: list[dict[str, Any]] = []
        tool_calls: list[ToolCall] = []
        server_uses: list[ServerToolUse] = []

        if isinstance(parts, list):
            for idx, part in enumerate(parts):
                if not isinstance(part, dict):
                    continue
                raw_blocks.append(copy.deepcopy(part))
                if isinstance(part.get("text"), str):
                    if part.get("thought"):
                        thinking_blocks.append({"type": "thought", "text": part["text"]})
                    else:
                        text_chunks.append(part["text"])
                if isinstance(part.get("functionCall"), dict):
                    fc = part["functionCall"]
                    fc_name = str(fc.get("name") or "")
                    fc_args = _safe_json_dict(fc.get("args"))
                    tool_calls.append(
                        ToolCall(
                            id=f"gem-{idx}-{fc_name}",
                            name=fc_name,
                            arguments=fc_args,
                        )
                    )
                if isinstance(part.get("executableCode"), dict):
                    server_uses.append(
                        ServerToolUse(
                            id=f"gem-exec-{idx}",
                            name="code_execution",
                            tool_type="code_execution",
                            input=dict(part["executableCode"]),
                        )
                    )
                if isinstance(part.get("codeExecutionResult"), dict) and server_uses:
                    last = server_uses[-1]
                    server_uses[-1] = ServerToolUse(
                        id=last.id,
                        name=last.name,
                        tool_type=last.tool_type,
                        input=last.input,
                        output=dict(part["codeExecutionResult"]),
                    )

        citations: list[Citation] = []
        grounding = (
            first_cand.get("groundingMetadata") if isinstance(first_cand, dict) else None
        )
        if isinstance(grounding, dict):
            chunks = grounding.get("groundingChunks") or []
            for chunk in chunks:
                if not isinstance(chunk, dict):
                    continue
                web = chunk.get("web")
                if isinstance(web, dict) and web.get("uri"):
                    citations.append(
                        Citation(
                            url=str(web["uri"]),
                            title=str(web.get("title") or ""),
                        )
                    )

        usage_meta = raw_data.get("usageMetadata")
        usage = TokenUsage(
            input_tokens=int(usage_meta.get("promptTokenCount") or 0)
            if isinstance(usage_meta, dict)
            else 0,
            output_tokens=int(usage_meta.get("candidatesTokenCount") or 0)
            if isinstance(usage_meta, dict)
            else 0,
            cached_input_tokens=int(usage_meta.get("cachedContentTokenCount") or 0)
            if isinstance(usage_meta, dict)
            else 0,
            thinking_tokens=int(usage_meta.get("thoughtsTokenCount") or 0)
            if isinstance(usage_meta, dict)
            else 0,
            total_tokens=int(usage_meta.get("totalTokenCount") or 0)
            if isinstance(usage_meta, dict)
            else 0,
        )
        text = "\n".join(chunk for chunk in text_chunks if chunk).strip()
        if not text:
            text = _extract_gemini_text(raw_data)

        finish_reason = (
            str(first_cand.get("finishReason") or "stop").lower()
            if isinstance(first_cand, dict)
            else "stop"
        )
        stop_reason = "tool_use" if tool_calls else finish_reason

        return AssistantTurn(
            provider=self.provider,
            model=self.model,
            text=text,
            tool_calls=tool_calls,
            server_tool_uses=server_uses,
            citations=citations,
            stop_reason=stop_reason,
            usage=usage,
            raw_blocks=raw_blocks,
            thinking_blocks=thinking_blocks,
            raw_response=raw_data,
        )


class AnthropicAdapter(ProviderAdapter):
    """Anthropic Messages API (`POST /v1/messages`) multi-turn adapter."""

    provider_name = "anthropic"

    def _resolve_api_key(self) -> str:
        vault = current_vault_secrets.get() or {}
        return vault.get("anthropic_api_key") or getattr(_pkg(), "ANTHROPIC_API_KEY", "")

    @staticmethod
    def _to_anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role") or "user").strip().lower()
            if role == "system":
                continue
            mapped_role = "assistant" if role in {"assistant", "model"} else "user"
            content = msg.get("content")
            if isinstance(content, list):
                converted.append({"role": mapped_role, "content": copy.deepcopy(content)})
            else:
                converted.append(
                    {
                        "role": mapped_role,
                        "content": [{"type": "text", "text": str(content or "")}],
                    }
                )
        return converted

    def build_assistant_message(self, turn: AssistantTurn) -> dict[str, Any]:
        # Preserve raw content blocks (including thinking + signature and tool_use) intact.
        if turn.raw_blocks:
            return {"role": "assistant", "content": copy.deepcopy(turn.raw_blocks)}
        blocks: list[dict[str, Any]] = []
        for tb in turn.thinking_blocks:
            blocks.append(copy.deepcopy(tb))
        if turn.text:
            blocks.append({"type": "text", "text": turn.text})
        for tc in turn.tool_calls:
            blocks.append(
                {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": copy.deepcopy(tc.arguments),
                }
            )
        return {"role": "assistant", "content": blocks or [{"type": "text", "text": ""}]}

    def build_tool_results_messages(
        self,
        turn: AssistantTurn,
        tool_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        del turn
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": str(item.get("tool_call_id") or ""),
                        "content": str(item.get("output_text") or ""),
                        "is_error": bool(item.get("is_error", False)),
                    }
                    for item in tool_results
                ],
            }
        ]

    async def _invoke(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[ToolDefinition],
        native_tools: list[str],
        tool_choice: str | dict[str, Any] | None,
        max_output_tokens: int | None,
        thinking: dict[str, Any] | bool | None,
        response_schema: dict[str, Any] | None,
        stream: bool,
        system_prompt: str | None,
        call_context: str,
    ) -> AssistantTurn | None:
        del response_schema, stream
        api_key = self._resolve_api_key()
        if not api_key:
            return None
        pkg = _pkg()
        max_tokens = int(max_output_tokens or 8192)
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": self._to_anthropic_messages(messages),
        }
        if system_prompt:
            if self.capabilities.supports_caching:
                payload["system"] = [
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            else:
                payload["system"] = system_prompt

        tool_entries: list[dict[str, Any]] = []
        if tools and self.capabilities.supports_tools:
            for idx, t in enumerate(tools):
                entry: dict[str, Any] = {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": copy.deepcopy(t.parameters),
                }
                if self.capabilities.supports_caching and idx == len(tools) - 1:
                    entry["cache_control"] = {"type": "ephemeral"}
                tool_entries.append(entry)

        beta_flags: list[str] = ["prompt-caching-2024-07-31"]
        for native_name in native_tools:
            norm = native_name.strip().lower()
            if norm in {"web_search", "google_search"} and (
                self.capabilities.supports_native_web_search
            ):
                tool_entries.append({"type": "web_search_20250305", "name": "web_search"})
            elif norm == "code_execution" and self.capabilities.supports_native_code_execution:
                tool_entries.append(
                    {"type": "code_execution_20250825", "name": "code_execution"}
                )
                beta_flags.append("code-execution-2025-08-25")

        if tool_entries:
            payload["tools"] = tool_entries
        if tool_choice:
            if isinstance(tool_choice, str):
                payload["tool_choice"] = {"type": tool_choice.lower()}
            elif isinstance(tool_choice, dict):
                payload["tool_choice"] = copy.deepcopy(tool_choice)

        if self.capabilities.supports_thinking and thinking:
            budget_tokens = 2048
            if isinstance(thinking, dict) and isinstance(thinking.get("budget_tokens"), int):
                budget_tokens = max(1024, int(thinking["budget_tokens"]))
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
            if max_tokens <= budget_tokens:
                payload["max_tokens"] = budget_tokens + 2048

        base_url = getattr(pkg, "ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
        version = getattr(pkg, "ANTHROPIC_VERSION", "2023-06-01")
        timeout = float(getattr(pkg, "ANTHROPIC_TIMEOUT_SECONDS", 180.0))
        response = await pkg._post_with_retry(
            f"{base_url.rstrip('/')}/messages",
            json_payload=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": version,
                "anthropic-beta": ",".join(dict.fromkeys(beta_flags)),
                "content-type": "application/json",
            },
            timeout=timeout,
            call_context=call_context,
        )
        if response is None or response.status_code >= 400:
            if response is not None:
                LOGGER.warning("%s anthropic returned status %s", call_context, response.status_code)
            return None

        raw_data = response.json()
        if not isinstance(raw_data, dict):
            return None

        content = raw_data.get("content")
        raw_blocks: list[dict[str, Any]] = []
        thinking_blocks: list[dict[str, Any]] = []
        text_chunks: list[str] = []
        tool_calls: list[ToolCall] = []
        server_uses: list[ServerToolUse] = []
        citations: list[Citation] = []

        if isinstance(content, list):
            for idx, block in enumerate(content):
                if not isinstance(block, dict):
                    continue
                raw_blocks.append(copy.deepcopy(block))
                btype = str(block.get("type") or "")
                if btype in {"thinking", "redacted_thinking"}:
                    thinking_blocks.append(copy.deepcopy(block))
                elif btype == "text":
                    if isinstance(block.get("text"), str):
                        text_chunks.append(block["text"])
                    for cite in block.get("citations") or []:
                        if isinstance(cite, dict) and cite.get("url"):
                            citations.append(
                                Citation(
                                    url=str(cite["url"]),
                                    title=str(cite.get("title") or ""),
                                    snippet=str(cite.get("cited_text") or ""),
                                )
                            )
                elif btype == "tool_use":
                    tool_calls.append(
                        ToolCall(
                            id=str(block.get("id") or f"toolu_{idx}"),
                            name=str(block.get("name") or ""),
                            arguments=_safe_json_dict(block.get("input")),
                        )
                    )
                elif btype == "server_tool_use":
                    server_uses.append(
                        ServerToolUse(
                            id=str(block.get("id") or f"srvtoolu_{idx}"),
                            name=str(block.get("name") or ""),
                            tool_type="server_tool_use",
                            input=_safe_json_dict(block.get("input")),
                        )
                    )
                elif btype == "web_search_tool_result":
                    for item in block.get("content") or []:
                        if isinstance(item, dict) and item.get("url"):
                            citations.append(
                                Citation(
                                    url=str(item["url"]),
                                    title=str(item.get("title") or ""),
                                )
                            )

        usage_raw = raw_data.get("usage")
        inp = int(usage_raw.get("input_tokens") or 0) if isinstance(usage_raw, dict) else 0
        out = int(usage_raw.get("output_tokens") or 0) if isinstance(usage_raw, dict) else 0
        cached = (
            int(usage_raw.get("cache_read_input_tokens") or 0)
            if isinstance(usage_raw, dict)
            else 0
        )
        usage = TokenUsage(
            input_tokens=inp,
            output_tokens=out,
            cached_input_tokens=cached,
            total_tokens=inp + out,
        )
        text = "\n".join(c for c in text_chunks if c).strip() or _extract_anthropic_text(raw_data)
        stop_reason = str(raw_data.get("stop_reason") or ("tool_use" if tool_calls else "end_turn"))

        return AssistantTurn(
            provider=self.provider,
            model=self.model,
            text=text,
            tool_calls=tool_calls,
            server_tool_uses=server_uses,
            citations=citations,
            stop_reason=stop_reason,
            usage=usage,
            raw_blocks=raw_blocks,
            thinking_blocks=thinking_blocks,
            raw_response=raw_data,
        )


class OpenAIAdapter(ProviderAdapter):
    """OpenAI Responses API (`POST /v1/responses`) multi-turn adapter."""

    provider_name = "openai"

    def _resolve_api_key(self) -> str:
        vault = current_vault_secrets.get() or {}
        return vault.get("openai_api_key") or getattr(_pkg(), "OPENAI_API_KEY", "")

    @staticmethod
    def _to_responses_input(
        messages: list[dict[str, Any]],
        *,
        system_prompt: str | None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if system_prompt:
            items.append({"role": "system", "content": system_prompt})
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            item_type = msg.get("type")
            if item_type in {"function_call", "function_call_output"}:
                items.append(copy.deepcopy(msg))
                continue
            role = str(msg.get("role") or "user").strip().lower()
            if role == "tool":
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": str(msg.get("tool_call_id") or ""),
                        "output": str(msg.get("content") or ""),
                    }
                )
                continue
            if role == "assistant" and isinstance(msg.get("responses_output"), list):
                items.extend(copy.deepcopy(msg["responses_output"]))
                continue
            items.append({"role": role, "content": msg.get("content") or ""})
        return items

    def build_assistant_message(self, turn: AssistantTurn) -> dict[str, Any]:
        if turn.raw_blocks:
            return {"role": "assistant", "responses_output": copy.deepcopy(turn.raw_blocks)}
        output_items: list[dict[str, Any]] = []
        if turn.text:
            output_items.append(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": turn.text}],
                }
            )
        for tc in turn.tool_calls:
            output_items.append(
                {
                    "type": "function_call",
                    "call_id": tc.id,
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments),
                }
            )
        return {"role": "assistant", "responses_output": output_items}

    def build_tool_results_messages(
        self,
        turn: AssistantTurn,
        tool_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        del turn
        return [
            {
                "type": "function_call_output",
                "call_id": str(item.get("tool_call_id") or ""),
                "output": str(item.get("output_text") or ""),
            }
            for item in tool_results
        ]

    async def _invoke(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[ToolDefinition],
        native_tools: list[str],
        tool_choice: str | dict[str, Any] | None,
        max_output_tokens: int | None,
        thinking: dict[str, Any] | bool | None,
        response_schema: dict[str, Any] | None,
        stream: bool,
        system_prompt: str | None,
        call_context: str,
    ) -> AssistantTurn | None:
        del stream
        api_key = self._resolve_api_key()
        if not api_key:
            return None
        pkg = _pkg()
        payload: dict[str, Any] = {
            "model": self.model,
            "input": self._to_responses_input(messages, system_prompt=system_prompt),
        }
        if max_output_tokens is not None:
            payload["max_output_tokens"] = int(max_output_tokens)
        if self.capabilities.supports_thinking and thinking is not False:
            effort = "medium"
            if isinstance(thinking, dict) and thinking.get("effort"):
                effort = str(thinking["effort"]).strip().lower()
            payload["reasoning"] = {"effort": effort}

        tool_entries: list[dict[str, Any]] = []
        if tools and self.capabilities.supports_tools:
            for t in tools:
                tool_entries.append(
                    {
                        "type": "function",
                        "name": t.name,
                        "description": t.description,
                        "parameters": copy.deepcopy(t.parameters),
                    }
                )
        for native_name in native_tools:
            norm = native_name.strip().lower()
            if norm in {"web_search", "google_search"} and (
                self.capabilities.supports_native_web_search
            ):
                tool_entries.append({"type": "web_search"})
            elif norm in {"code_execution", "code_interpreter"} and (
                self.capabilities.supports_native_code_execution
            ):
                tool_entries.append({"type": "code_interpreter", "container": {"type": "auto"}})
        if tool_entries:
            payload["tools"] = tool_entries
            if tool_choice is not None:
                payload["tool_choice"] = copy.deepcopy(tool_choice)
        if response_schema and self.capabilities.supports_structured_output:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "agent_response",
                    "schema": copy.deepcopy(response_schema),
                    "strict": True,
                }
            }

        base_url = getattr(pkg, "OPENAI_BASE_URL", "https://api.openai.com/v1")
        timeout = float(getattr(pkg, "OPENAI_TIMEOUT_SECONDS", 180.0))
        response = await pkg._post_with_retry(
            f"{base_url.rstrip('/')}/responses",
            json_payload=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "content-type": "application/json",
            },
            timeout=timeout,
            call_context=call_context,
        )
        if response is None or response.status_code >= 400:
            if response is not None:
                LOGGER.warning("%s openai returned status %s", call_context, response.status_code)
            return None

        raw_data = response.json()
        if not isinstance(raw_data, dict):
            return None

        raw_blocks: list[dict[str, Any]] = []
        thinking_blocks: list[dict[str, Any]] = []
        text_chunks: list[str] = []
        tool_calls: list[ToolCall] = []
        server_uses: list[ServerToolUse] = []
        citations: list[Citation] = []

        output = raw_data.get("output")
        if isinstance(output, list):
            for idx, item in enumerate(output):
                if not isinstance(item, dict):
                    continue
                raw_blocks.append(copy.deepcopy(item))
                itype = str(item.get("type") or "")
                if itype == "reasoning":
                    thinking_blocks.append(copy.deepcopy(item))
                elif itype == "function_call":
                    raw_args = item.get("arguments")
                    tool_calls.append(
                        ToolCall(
                            id=str(item.get("call_id") or item.get("id") or f"call_{idx}"),
                            name=str(item.get("name") or ""),
                            arguments=_safe_json_dict(raw_args),
                            raw_arguments=raw_args if isinstance(raw_args, str) else None,
                        )
                    )
                elif itype in {"web_search_call", "code_interpreter_call"}:
                    server_uses.append(
                        ServerToolUse(
                            id=str(item.get("id") or f"srv_{idx}"),
                            name=itype,
                            tool_type=itype,
                            input=_safe_json_dict(item.get("action") or item.get("code")),
                            output=item.get("outputs") or item.get("results"),
                        )
                    )
                elif itype == "message":
                    for part in item.get("content") or []:
                        if not isinstance(part, dict):
                            continue
                        if isinstance(part.get("text"), str):
                            text_chunks.append(part["text"])
                        for ann in part.get("annotations") or []:
                            if isinstance(ann, dict) and ann.get("url"):
                                citations.append(
                                    Citation(
                                        url=str(ann["url"]),
                                        title=str(ann.get("title") or ""),
                                    )
                                )

        # Chat Completions compatibility fallback
        choices = raw_data.get("choices")
        if not output and isinstance(choices, list) and choices:
            msg = choices[0].get("message") if isinstance(choices[0], dict) else {}
            if isinstance(msg, dict):
                if isinstance(msg.get("content"), str):
                    text_chunks.append(msg["content"])
                for idx, tc in enumerate(msg.get("tool_calls") or []):
                    if not isinstance(tc, dict):
                        continue
                    fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                    raw_args = fn.get("arguments")
                    tool_calls.append(
                        ToolCall(
                            id=str(tc.get("id") or f"call_{idx}"),
                            name=str(fn.get("name") or tc.get("name") or ""),
                            arguments=_safe_json_dict(raw_args),
                            raw_arguments=raw_args if isinstance(raw_args, str) else None,
                        )
                    )

        usage_raw = raw_data.get("usage")
        inp = (
            int(usage_raw.get("input_tokens") or usage_raw.get("prompt_tokens") or 0)
            if isinstance(usage_raw, dict)
            else 0
        )
        out = (
            int(usage_raw.get("output_tokens") or usage_raw.get("completion_tokens") or 0)
            if isinstance(usage_raw, dict)
            else 0
        )
        usage = TokenUsage(
            input_tokens=inp,
            output_tokens=out,
            total_tokens=int(usage_raw.get("total_tokens") or (inp + out))
            if isinstance(usage_raw, dict)
            else (inp + out),
        )
        text = "\n".join(c for c in text_chunks if c).strip() or _extract_openai_text(raw_data)
        stop_reason = "tool_use" if tool_calls else str(raw_data.get("status") or "stop")

        return AssistantTurn(
            provider=self.provider,
            model=self.model,
            text=text,
            tool_calls=tool_calls,
            server_tool_uses=server_uses,
            citations=citations,
            stop_reason=stop_reason,
            usage=usage,
            raw_blocks=raw_blocks,
            thinking_blocks=thinking_blocks,
            raw_response=raw_data,
        )


class OllamaAdapter(ProviderAdapter):
    """Local Ollama / vLLM chat-tools adapter."""

    provider_name = "ollama"

    async def _invoke(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[ToolDefinition],
        native_tools: list[str],
        tool_choice: str | dict[str, Any] | None,
        max_output_tokens: int | None,
        thinking: dict[str, Any] | bool | None,
        response_schema: dict[str, Any] | None,
        stream: bool,
        system_prompt: str | None,
        call_context: str,
    ) -> AssistantTurn | None:
        del native_tools, tool_choice, thinking, stream
        pkg = _pkg()
        chat_messages: list[dict[str, Any]] = []
        if system_prompt:
            chat_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            chat_messages.append(copy.deepcopy(msg))

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": chat_messages,
            "stream": False,
        }
        if tools and self.capabilities.supports_tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": copy.deepcopy(t.parameters),
                    },
                }
                for t in tools
            ]
        if response_schema:
            payload["format"] = copy.deepcopy(response_schema)
        if max_output_tokens is not None:
            payload["options"] = {"num_predict": int(max_output_tokens)}

        base_url = getattr(pkg, "OLLAMA_BASE_URL", "http://localhost:11434")
        timeout = float(getattr(pkg, "OLLAMA_TIMEOUT_SECONDS", 60.0))
        response = await pkg._post_with_retry(
            f"{base_url.rstrip('/')}/api/chat",
            json_payload=payload,
            headers={"content-type": "application/json"},
            timeout=timeout,
            call_context=call_context,
        )
        if response is None or response.status_code >= 400:
            if response is not None:
                LOGGER.warning("%s ollama returned status %s", call_context, response.status_code)
            return None

        raw_data = response.json()
        if not isinstance(raw_data, dict):
            return None

        msg = raw_data.get("message")
        if not isinstance(msg, dict):
            choices = raw_data.get("choices")
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                msg = choices[0].get("message") if isinstance(choices[0].get("message"), dict) else {}
            else:
                msg = {}

        text = str(msg.get("content") or raw_data.get("response") or "").strip()
        tool_calls: list[ToolCall] = []
        for idx, tc in enumerate(msg.get("tool_calls") or []):
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") if isinstance(tc.get("function"), dict) else tc
            raw_args = fn.get("arguments")
            tool_calls.append(
                ToolCall(
                    id=str(tc.get("id") or f"ollama_{uuid.uuid4().hex[:6]}_{idx}"),
                    name=str(fn.get("name") or ""),
                    arguments=_safe_json_dict(raw_args),
                    raw_arguments=raw_args if isinstance(raw_args, str) else None,
                )
            )

        inp = int(raw_data.get("prompt_eval_count") or 0)
        out = int(raw_data.get("eval_count") or 0)
        return AssistantTurn(
            provider=self.provider,
            model=self.model,
            text=text,
            tool_calls=tool_calls,
            stop_reason="tool_use" if tool_calls else str(raw_data.get("done_reason") or "stop"),
            usage=TokenUsage(input_tokens=inp, output_tokens=out, total_tokens=inp + out),
            raw_response=raw_data,
        )


def get_provider_adapter(provider: str, model: str | None = None) -> ProviderAdapter:
    """Instantiate the matching ``ProviderAdapter`` for *provider* and *model*."""
    norm = str(provider or "openai").strip().lower() or "openai"
    if norm in {"gemini", "google"}:
        return GeminiAdapter(model=model)
    if norm in {"anthropic", "claude"}:
        return AnthropicAdapter(model=model)
    if norm in {"ollama", "vllm"}:
        return OllamaAdapter(model=model, provider=norm)
    return OpenAIAdapter(model=model)
