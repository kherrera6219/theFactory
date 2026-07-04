# LLM Delegation Layer

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Canonical
Audience: Developers, Architects

This document was rewritten on 2026-07-03 — the previous version described `LLMDelegator`/`DelegationRequest`/`DelegationResponse`/`BaseProvider`/`PROVIDER_REGISTRY` classes, a `router.py`/`retry.py`/`cost_guard.py`/`providers/` submodule layout, and an Ollama/offline mode — none of which exist. The real package (`services/orchestrator/orchestrator/llm_delegation/`) is function-based across 12 flat modules.

## Package Layout

| File | Responsibility |
|---|---|
| `providers.py` | Raw provider HTTP calls (`_call_openai`/`_call_anthropic`/`_call_gemini`), retry-with-backoff (`_post_with_retry`), and the top-level dispatch functions (`_call_provider`, `_call_with_recommendation`, `_call_with_agent_system`) |
| `health.py` | Per-provider circuit breaker (`is_circuit_open`/`record_failure`/`record_success`) and health summary aggregation |
| `config.py` | Module-level flags (`LLM_SAFETY_BLOCK_ENABLED`, `PROMPT_GUARD_BLOCK_ENABLED`/`_BLOCK_LEVEL`), `ContextVar`s for the current mission/settings/agent/vault-secrets, and usage-event recording |
| `agents.py` | Per-agent system-prompt resolution and recommendation building (`_agent_recommendation`, `_ceo_recommendation`, `_pm_recommendation`) |
| `prompts.py` | Prompt template construction for each generator (`_build_prompt`, `_build_pod_manager_prompt`, `_build_codegen_prompt`, etc.) |
| `generators.py` | Public async entry points for core mission-flow LLM calls: `generate_ceo_delegation`, `generate_pod_manager_delegation`, `generate_specialist_plan`, `generate_mission_contract`, `generate_code_from_contract`, `generate_logic_clusters`, `generate_pm_feature_contract`, `generate_pod_group_standard` |
| `generators_artifacts.py` | Public async entry points for delivery-phase LLM calls: `generate_rqca_assessment`, `generate_security_analysis`, `generate_compliance_assessment`, `generate_vc_commit_strategy`, `generate_pm_delivery_summary`, `generate_master_logic_stream`, `generate_pod_audit_verdict`, plus `build_deploy_readiness_assessment` |
| `normalizers.py` | Post-call response normalization/repair for each generator's expected shape |
| `fallbacks.py` | Deterministic non-LLM fallback builders (`_fallback_codegen`, `_fallback_mission_contract`, etc.) used when a provider call fails or is unavailable |
| `text.py` | Text/JSON extraction helpers (`_extract_openai_text`, `_extract_anthropic_text`, `_extract_gemini_text`, `_find_balanced_json_objects`), sanitization, and PM clarification-question heuristics |
| `metrics.py` | Prometheus recording for LLM request/usage counters |

## Provider Dispatch

`_call_provider()` (in `providers.py`) is the low-level dispatcher for a single provider call; `_call_with_recommendation()` wraps it with the agent's resolved provider/model recommendation and retry/fallback handling; `_call_with_agent_system()` is the higher-level entry that resolves an agent ID to its persona, builds the prompt, and calls through. The three real providers called directly via `httpx` are OpenAI, Anthropic, and Gemini (`_call_openai`/`_call_anthropic`/`_call_gemini`) — **there is no Ollama provider and no offline/local-inference mode** in this package (a separate `hw_agent.py` detects local hardware capability for other purposes, unrelated to LLM routing).

## Circuit Breaker

`health.py` implements a real per-provider circuit breaker:
- `CIRCUIT_OPEN_THRESHOLD = 5` consecutive non-retryable failures opens the circuit.
- `CIRCUIT_OPEN_SECONDS = 60.0` — once open, calls are skipped (routing straight to the fallback path) for this cooldown window.
- After cooldown, the circuit becomes half-open: the next call is allowed through as a probe; success closes it, failure re-opens it.
- `record_success`/`record_failure`/`is_circuit_open`/`get_circuit_state`/`reset_circuit_breakers` are the public functions; `get_provider_health_summary()` aggregates a rolling 300-second window (`_PROVIDER_HEALTH_WINDOW_SECONDS`, capped at 200 samples) for the `/v1/operations/*` health endpoints.

## Prompt-Injection Guard

`config.py`'s `PROMPT_GUARD_BLOCK_ENABLED` (default `true`) and `PROMPT_GUARD_BLOCK_LEVEL` (default `high`) gate `providers.py`'s `check_user_input()`, which is called before every outbound call to detect and optionally block OWASP LLM01-style prompt injection in user-supplied text (mission prompts, PM feature-contract input, etc.) using `shared_runtime/prompt_guard.py`'s detection — see `LLM_SAFETY_AND_DOCUMENT_PARSER.md` for that module.

## Fallback Behavior

Every `generators.py`/`generators_artifacts.py` entry point degrades to a deterministic fallback builder in `fallbacks.py` when the LLM call fails, the circuit is open, or the response fails normalization — these fallbacks are hand-written heuristics (e.g. `_fallback_codegen` produces a minimal boilerplate file, `_fallback_mission_contract` produces a generic contract skeleton), not another LLM call. Fallback usage is tagged `"source": "fallback"` in the returned dict so downstream consumers (e.g. `port_coordinator.py`'s `extraction_degraded` flag) can detect degraded results.

## Adding a New Provider

There is no plugin registry to implement against. Adding a provider means:
1. Writing a new `_call_<provider>()` function in `providers.py` following the existing `_call_openai`/`_call_anthropic`/`_call_gemini` shape (accepts prompt/model/settings, returns extracted text or `None`).
2. Adding a text-extraction helper in `text.py` if the response shape is novel.
3. Wiring the new provider into `_call_provider()`'s dispatch and `health.py`'s circuit-breaker key space (it's keyed by provider name string, no registration step needed).
4. Adding the provider's API key/model settings to `services/orchestrator/orchestrator/settings.py`.
