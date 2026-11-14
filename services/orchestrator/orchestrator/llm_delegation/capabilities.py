"""Model capability registry for the multi-turn AgentHarness.

Every supported LLM provider/model declares its native tool, thinking,
context-window, and caching capabilities here so the harness never assumes a
local/older model can run parallel server-side tools or extended thinking.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    """Declared and preflight-confirmed capabilities for a provider model."""

    provider: str
    model: str
    context_window: int
    max_output_tokens: int
    supports_tools: bool = True
    supports_parallel_tools: bool = True
    supports_native_web_search: bool = False
    supports_url_fetch: bool = False
    supports_native_code_execution: bool = False
    supports_vision: bool = True
    supports_structured_output: bool = True
    supports_thinking: bool = False
    supports_caching: bool = False
    confirmed_by_preflight: bool = False

    def with_preflight(self, confirmed: bool, *, model: str | None = None) -> ModelCapabilities:
        """Return a copy annotated with preflight confirmation status."""
        return replace(
            self,
            model=model or self.model,
            confirmed_by_preflight=bool(confirmed),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize capability fields into a JSON-safe mapping."""
        return asdict(self)


_CAPABILITY_CATALOG: dict[tuple[str, str], ModelCapabilities] = {
    (
        "gemini",
        "gemini-4-argon",
    ): ModelCapabilities(
        provider="gemini",
        model="gemini-4-argon",
        context_window=1_048_576,
        max_output_tokens=65_536,
        supports_tools=True,
        supports_parallel_tools=True,
        supports_native_web_search=True,
        supports_url_fetch=True,
        supports_native_code_execution=True,
        supports_vision=True,
        supports_structured_output=True,
        supports_thinking=True,
        supports_caching=True,
    ),
    (
        "gemini",
        "gemini-3.8-flash",
    ): ModelCapabilities(
        provider="gemini",
        model="gemini-3.8-flash",
        context_window=1_048_576,
        max_output_tokens=65_536,
        supports_tools=True,
        supports_parallel_tools=True,
        supports_native_web_search=True,
        supports_url_fetch=True,
        supports_native_code_execution=True,
        supports_vision=True,
        supports_structured_output=True,
        supports_thinking=True,
        supports_caching=True,
    ),
    (
        "openai",
        "gpt-6.1-terrea",
    ): ModelCapabilities(
        provider="openai",
        model="gpt-6.1-terrea",
        context_window=400_000,
        max_output_tokens=32_768,
        supports_tools=True,
        supports_parallel_tools=True,
        supports_native_web_search=True,
        supports_url_fetch=False,
        supports_native_code_execution=True,
        supports_vision=True,
        supports_structured_output=True,
        supports_thinking=True,
        supports_caching=True,
    ),
    (
        "openai",
        "gpt-5.6",
    ): ModelCapabilities(
        provider="openai",
        model="gpt-5.6",
        context_window=400_000,
        max_output_tokens=32_768,
        supports_tools=True,
        supports_parallel_tools=True,
        supports_native_web_search=True,
        supports_url_fetch=False,
        supports_native_code_execution=True,
        supports_vision=True,
        supports_structured_output=True,
        supports_thinking=True,
        supports_caching=True,
    ),
    (
        "openai",
        "gpt-4o",
    ): ModelCapabilities(
        provider="openai",
        model="gpt-4o",
        context_window=128_000,
        max_output_tokens=16_384,
        supports_tools=True,
        supports_parallel_tools=True,
        supports_native_web_search=False,
        supports_url_fetch=False,
        supports_native_code_execution=False,
        supports_vision=True,
        supports_structured_output=True,
        supports_thinking=False,
        supports_caching=True,
    ),
    (
        "anthropic",
        "claude-opus-5-5",
    ): ModelCapabilities(
        provider="anthropic",
        model="claude-opus-5-5",
        context_window=200_000,
        max_output_tokens=32_768,
        supports_tools=True,
        supports_parallel_tools=True,
        supports_native_web_search=True,
        supports_url_fetch=False,
        supports_native_code_execution=True,
        supports_vision=True,
        supports_structured_output=True,
        supports_thinking=True,
        supports_caching=True,
    ),
    (
        "anthropic",
        "claude-sonnet-4-6",
    ): ModelCapabilities(
        provider="anthropic",
        model="claude-sonnet-4-6",
        context_window=200_000,
        max_output_tokens=16_384,
        supports_tools=True,
        supports_parallel_tools=True,
        supports_native_web_search=True,
        supports_url_fetch=False,
        supports_native_code_execution=True,
        supports_vision=True,
        supports_structured_output=True,
        supports_thinking=True,
        supports_caching=True,
    ),
    (
        "ollama",
        "qwen2.5-coder:7b",
    ): ModelCapabilities(
        provider="ollama",
        model="qwen2.5-coder:7b",
        context_window=32_768,
        max_output_tokens=8_192,
        supports_tools=True,
        supports_parallel_tools=True,
        supports_native_web_search=False,
        supports_url_fetch=False,
        supports_native_code_execution=False,
        supports_vision=False,
        supports_structured_output=True,
        supports_thinking=False,
        supports_caching=False,
    ),
}

_PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "gemini": "gemini-4-argon",
    "google": "gemini-4-argon",
    "openai": "gpt-6.1-terrea",
    "anthropic": "claude-opus-5-5",
    "claude": "claude-opus-5-5",
    "ollama": "qwen2.5-coder:7b",
    "vllm": "qwen2.5-coder:7b",
}

_MODEL_ALIASES: dict[tuple[str, str], str] = {
    ("anthropic", "claude-ops-5.5"): "claude-opus-5-5",
    ("anthropic", "claude-opus-5.5"): "claude-opus-5-5",
    ("anthropic", "claude-opus.5.5"): "claude-opus-5-5",
    ("openai", "gpt-5.5"): "gpt-5.6",
}

_CONFIRMED_PROVIDERS: dict[str, bool] = {}


def _normalize_provider_name(provider: str | None) -> str:
    norm = str(provider or "openai").strip().lower() or "openai"
    if norm == "google":
        return "gemini"
    if norm == "claude":
        return "anthropic"
    return norm


def _canonical_model_name(provider: str, model: str | None) -> str:
    raw = str(model or "").strip()
    if not raw:
        return _PROVIDER_DEFAULT_MODELS.get(provider, "gpt-6.1-terrea")
    alias = _MODEL_ALIASES.get((provider, raw.lower()))
    return alias or raw


def get_model_capabilities(
    provider: str,
    model: str | None = None,
    *,
    confirmed_override: bool | None = None,
) -> ModelCapabilities:
    """Return declared (and preflight-confirmed if applicable) capabilities for a model."""
    norm_provider = _normalize_provider_name(provider)
    requested_model = str(model or "").strip() or _PROVIDER_DEFAULT_MODELS.get(
        norm_provider,
        "gpt-6.1-terrea",
    )
    canonical = _canonical_model_name(norm_provider, requested_model)
    lookup_provider = "ollama" if norm_provider == "vllm" else norm_provider

    entry = _CAPABILITY_CATALOG.get((lookup_provider, canonical))
    if entry is None:
        # Prefix match on versioned model identifiers.
        lower_canon = canonical.lower()
        for (cat_provider, cat_model), candidate in _CAPABILITY_CATALOG.items():
            if cat_provider == lookup_provider and (
                lower_canon.startswith(cat_model.lower())
                or cat_model.lower().startswith(lower_canon)
            ):
                entry = candidate
                break

    if entry is None:
        default_model = _PROVIDER_DEFAULT_MODELS.get(lookup_provider, "gpt-6.1-terrea")
        entry = _CAPABILITY_CATALOG.get(
            (lookup_provider, default_model),
            ModelCapabilities(
                provider=norm_provider,
                model=requested_model,
                context_window=32_768,
                max_output_tokens=4_096,
                supports_tools=True,
                supports_parallel_tools=False,
                supports_vision=False,
            ),
        )

    confirmed = (
        confirmed_override
        if confirmed_override is not None
        else bool(_CONFIRMED_PROVIDERS.get(norm_provider, False))
    )
    return replace(
        entry,
        provider=norm_provider,
        model=requested_model,
        confirmed_by_preflight=confirmed,
    )


def list_model_capabilities() -> list[dict[str, Any]]:
    """Return serialized capability declarations for all cataloged models."""
    results: list[dict[str, Any]] = []
    for (_, _), cap in sorted(_CAPABILITY_CATALOG.items()):
        confirmed = bool(_CONFIRMED_PROVIDERS.get(cap.provider, False))
        results.append(cap.with_preflight(confirmed).to_dict())
    return results


def confirm_capabilities_from_preflight(
    preflight_report: dict[str, Any],
) -> dict[str, ModelCapabilities]:
    """Update runtime preflight confirmation flags from a preflight probe result."""
    providers_map = (
        preflight_report.get("providers")
        if isinstance(preflight_report, dict)
        else None
    )
    confirmed: dict[str, ModelCapabilities] = {}
    if not isinstance(providers_map, dict):
        return confirmed

    for raw_provider, entry in providers_map.items():
        if not isinstance(entry, dict):
            continue
        provider = _normalize_provider_name(str(raw_provider))
        is_ready = bool(entry.get("ready", False))
        _CONFIRMED_PROVIDERS[provider] = is_ready
        default_model = _PROVIDER_DEFAULT_MODELS.get(provider, "")
        confirmed[provider] = get_model_capabilities(
            provider,
            default_model,
            confirmed_override=is_ready,
        )
    return confirmed


def reset_preflight_confirmations() -> None:
    """Clear runtime preflight confirmation state (for isolated unit tests)."""
    _CONFIRMED_PROVIDERS.clear()
