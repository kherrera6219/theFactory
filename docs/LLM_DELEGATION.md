# LLM Delegation Layer

Document version: 2026.06.11  
Last updated: 2026-06-11  
Status: Canonical  
Audience: Developers, LLM integration engineers, and infrastructure operators

---

## Purpose

The LLM delegation layer is the orchestrator's **provider-aware routing engine** — the component responsible for selecting the correct LLM provider and model for each agent call, constructing the API request, managing retries and fallback, and normalizing the response back into a format the orchestrator can process. It is the single point of contact between orchestrator business logic and external (or local) LLM APIs.

No agent, mission flow, or protocol bus consumer calls an LLM API directly. All LLM traffic flows through this layer.

---

## Code Location

| File / Directory | Description |
|---|---|
| `services/orchestrator/orchestrator/llm_delegation/` | Package root for the delegation layer |
| `services/orchestrator/orchestrator/llm_delegation/__init__.py` | Public interface: `LLMDelegator`, `DelegationRequest`, `DelegationResponse` |
| `services/orchestrator/orchestrator/llm_delegation/providers/` | One submodule per supported provider (OpenAI, Anthropic, Gemini, Ollama) |
| `services/orchestrator/orchestrator/llm_delegation/router.py` | Routing logic: maps agent key + persona recommendation → provider selection |
| `services/orchestrator/orchestrator/llm_delegation/retry.py` | Retry and fallback policy: exponential backoff, provider fallback chain |
| `services/orchestrator/orchestrator/llm_delegation/cost_guard.py` | Per-mission cost ceiling enforcement using `llm_cost_ledger.py` |

---

## Architecture Overview

```
Agent (agent_base.py)
        │
        │  DelegationRequest(agent_key, messages, config)
        ▼
  LLMDelegator
        │
        ├── router.py          → selects provider + model
        ├── cost_guard.py      → checks mission cost ceiling
        ├── providers/
        │     ├── openai.py    → OpenAI Chat Completions API
        │     ├── anthropic.py → Anthropic Messages API
        │     ├── gemini.py    → Google Gemini API
        │     └── ollama.py    → Local Ollama inference (offline mode)
        ├── retry.py           → exponential backoff + provider fallback
        │
        ▼
  DelegationResponse(content, provider, model, tokens, cost_usd)
```

---

## Supported Providers

| Provider | Env Variable | Offline Capable | Notes |
|---|---|---|---|
| OpenAI | `OPENAI_API_KEY` | No | Default provider for most agents |
| Anthropic | `ANTHROPIC_API_KEY` | No | Preferred for long-context and analysis agents |
| Google Gemini | `GEMINI_API_KEY` | No | Used for specific mathematical pod agents |
| Ollama | `OLLAMA_BASE_URL` | **Yes** | Local inference; activated when `LLM_OFFLINE_MODE=true` |

Provider availability is checked at orchestrator startup. If a required provider key is absent and offline mode is not enabled, the orchestrator logs a `WARN` and marks affected agents as `DEGRADED` rather than failing the entire startup.

---

## Routing Logic

The router uses a **three-tier decision hierarchy** to select a provider and model for each delegation request:

1. **Mission-level override:** If the operator has set `mission.llm_override` in the mission payload, that provider/model is used unconditionally.
2. **Persona recommendation:** The agent's persona definition (`agent_personas.py`) specifies a `preferred_provider` and `preferred_model`. The router honors this recommendation if the provider is available.
3. **System default:** If the persona recommendation is unavailable (provider key missing, rate-limited), the router falls through to the system default provider defined in `settings.py` (`LLM_DEFAULT_PROVIDER`).

This hierarchy ensures that sensitive code handling policies (see [SENSITIVE_CODE_HANDLING_POLICY.md](SENSITIVE_CODE_HANDLING_POLICY.md)) are respected — agents designated for local-only processing are always routed to Ollama regardless of tier-1 and tier-2 recommendations.

---

## Retry and Fallback Policy

Managed by `retry.py`:

- **Transient errors** (rate limit 429, timeout, 5xx): exponential backoff with jitter, up to 3 attempts on the same provider.
- **Provider failure** (all retries exhausted): falls back to the next available provider in the fallback chain defined per agent class in `agent_personas.py`.
- **All providers exhausted:** raises `LLMDelegationError`, which the mission flow interprets as a `PHASE_FAILED` event and triggers lifecycle recovery.
- **Maximum retry wall time:** 90 seconds per delegation request. Configurable via `LLM_MAX_RETRY_SECONDS` environment variable.

---

## Cost Guard

`cost_guard.py` integrates with `llm_cost_ledger.py` to enforce per-mission and per-day cost ceilings:

- Before each delegation, the guard checks the ledger's running total for the current mission against `MISSION_COST_CEILING_USD` (default: `$2.00`).
- If the ceiling would be exceeded, the delegation raises `CostCeilingExceeded`, triggering a graceful mission pause and operator notification via the SSE stream.
- All token usage and cost estimates are written to the ledger and included in the mission's audit evidence bundle.

---

## DelegationRequest and DelegationResponse

### `DelegationRequest`

```python
@dataclass
class DelegationRequest:
    agent_key: str                    # e.g., "AGENT-05-ARCH"
    messages: list[dict]              # OpenAI-format message list
    temperature: float = 0.2
    max_tokens: int = 4096
    provider_override: str | None = None
    model_override: str | None = None
    mission_id: str | None = None     # for cost ledger attribution
```

### `DelegationResponse`

```python
@dataclass
class DelegationResponse:
    content: str                      # raw LLM output text
    provider: str                     # actual provider used
    model: str                        # actual model used
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float                   # estimated cost
    latency_ms: int
    fallback_used: bool               # True if primary provider failed
```

---

## Offline Mode

When `LLM_OFFLINE_MODE=true` is set in the environment:

- All delegation requests are unconditionally routed to the Ollama provider.
- The router skips persona recommendations and mission overrides.
- Cost guard is disabled (Ollama incurs no API cost).
- `DelegationResponse.provider` is always `"ollama"` regardless of the agent's persona preference.

This mode is intended for local development, air-gapped deployments, and CI environments where external API calls must be avoided. See [DEPLOYMENT_DR_PLAYBOOK.md](DEPLOYMENT_DR_PLAYBOOK.md) for offline mode activation in operational contexts.

---

## Adding a New Provider

1. Create `services/orchestrator/orchestrator/llm_delegation/providers/{provider_name}.py` implementing the `BaseProvider` interface (defined in `providers/__init__.py`).
2. Register the provider in `router.py`'s `PROVIDER_REGISTRY` dict.
3. Add the provider's API key environment variable to `docker-compose.yml`, `.env.example`, and `COMPOSE_ENVIRONMENT_PROFILES.md`.
4. Add the new model options to `AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md`.
5. Write unit tests in `services/orchestrator/tests/test_llm_delegation.py` covering normal response, rate-limit retry, and fallback behavior.

---

## Relationship to Sensitive Code Handling

The delegation layer enforces the local-routing requirements defined in [SENSITIVE_CODE_HANDLING_POLICY.md](SENSITIVE_CODE_HANDLING_POLICY.md). Agents tagged with `sensitivity: local_only` in their persona definition will always be routed to Ollama by the router, regardless of tier-1 or tier-2 routing decisions. This is implemented as a pre-route check in `router.py` and cannot be overridden by a mission-level `llm_override`.

---

## See Also

- [PROMPT_REGISTRY_AND_ASSETS.md](PROMPT_REGISTRY_AND_ASSETS.md) — prompt construction that feeds into delegation requests
- [AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md](AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md) — full provider/model matrix per agent
- [SENSITIVE_CODE_HANDLING_POLICY.md](SENSITIVE_CODE_HANDLING_POLICY.md) — local-routing policy the delegation layer enforces
- [OBSERVABILITY_STACK.md](OBSERVABILITY_STACK.md) — LLM latency and cost metrics exported by this layer
- [DATA_CLASSIFICATION_POLICY.md](DATA_CLASSIFICATION_POLICY.md) — data handling rules that govern which providers may receive which data
