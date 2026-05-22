# Phase 25 — Prompt Versioning and AI Safety Governance

**Status:** ✅ COMPLETE
**Completed:** 2026-05-20
**Last updated:** 2026-05-20
**Depends on:** Phase 19 (system prompts wired), Phase 20 (agent LLM calls active)

---

## Completion Evidence

| Check | Result |
|---|---|
| `prompt_registry.py` exists | ✅ |
| `prompt_assets/` — 5 JSON assets | ✅ pm_feature_contract.v1, ceo_delegation.v1, ceo_mission_contract.v1, specialist_codegen.v1, security_threat_analysis.v1 |
| `llm_safety.py` exists | ✅ |
| `check_outbound_prompt` implemented | ✅ API key, GitHub token, SSN, credit card patterns |
| `check_inbound_response` implemented | ✅ DAN, ignore-instructions, role-override, im_start patterns |
| `sanitize_outbound_prompt` implemented | ✅ Redacts to `[REDACTED]` |
| Safety wired into `_call_with_recommendation` | ✅ Every LLM call scanned |
| `LLM_SAFETY_BLOCK_ENABLED` in settings + .env.example | ✅ Default: false (log-only) |
| `load_prompt_assets()` called at orchestrator startup | ✅ In lifespan hook, `main.py` |
| `GET /internal/prompt-registry` endpoint | ✅ Returns all registered assets |
| `GET /v1/missions/{id}/token-usage` via API gateway | ✅ Proxied through |
| `make eval` target in Makefile | ✅ |
| `tests/eval/test_safety_evals.py` — 10 tests | ✅ 10/10 passing |
| `tests/eval/test_pm_contract_evals.py` — 6 tests | ✅ 6/6 passing |
| `tests/eval/test_prompt_registry_evals.py` — 7 tests | ✅ 7/7 passing |
| Phase 25 eval total | ✅ 23/23 passing in 0.05s |
| `python -m ruff check services tests scripts` | ✅ Clean |
| `npm run lint` | ✅ 0 errors |
| `AI-001` audit check | ✅ PASS (5 prompt assets) |
| `AI-002` audit check | ✅ PASS (10 safety eval tests) |

---

## What Was Done

### Change 1 — Prompt asset registry ✅
`services/orchestrator/orchestrator/prompt_registry.py`:
- `PromptAsset` frozen dataclass: SHA-256 content hash auto-computed on init,
  `render(**kwargs)` validates required variables and raises on missing ones.
- `register()`, `get()`, `list_prompts()`, `load_prompt_assets()` public API.
- `load_prompt_assets()` called in orchestrator lifespan at startup via
  `asyncio.to_thread()`.

`services/orchestrator/orchestrator/prompt_assets/` — 5 versioned JSON files:
- `pm_feature_contract.v1.json` — AGENT-01-PM, 8 variables
- `ceo_delegation.v1.json` — AGENT-02-CEO, 7 variables
- `ceo_mission_contract.v1.json` — AGENT-02-CEO, 7 variables
- `specialist_codegen.v1.json` — AGENT-14-PYTHON (template), 8 variables
- `security_threat_analysis.v1.json` — AGENT-05-SECURITY, 5 variables

### Change 2 — LLM safety envelope ✅
`services/orchestrator/orchestrator/llm_safety.py`:

Outbound patterns (blocks secrets leaving the system):
- `api_key_sk` — `sk-[A-Za-z0-9_-]{20,}`
- `github_token_ghp` — `ghp_[A-Za-z0-9]{20,}`
- `github_pat` — `github_pat_[A-Za-z0-9_]{20,}`
- `ssn_pattern` — `\b\d{3}-\d{2}-\d{4}\b`
- `visa_card` — Visa card number pattern
- `mastercard` — Mastercard number pattern

Inbound patterns (flags injection attempts in model responses):
- `ignore_instructions` — `IGNORE ALL PREVIOUS INSTRUCTIONS`
- `dan_jailbreak` — `You are now DAN`
- `system_override` — `system: you are|ignore`
- `im_start_inject` — `<|im_start|> system`
- `role_override` — `forget your previous instructions`

Wired into `_call_with_recommendation()` in `llm_delegation.py` — runs on
every LLM call before the request is dispatched. Violations logged; blocked
only when `LLM_SAFETY_BLOCK_ENABLED=true`.

### Change 3 — AI eval harness ✅
`tests/eval/` — 4 files:
- `conftest_eval.py`: `live_llm` pytest marker for CI skip
- `test_safety_evals.py`: 10 tests — 6 outbound + 4 inbound
- `test_pm_contract_evals.py`: 6 tests — required fields, title, language,
  approval rules, model provider recorded
- `test_prompt_registry_evals.py`: 7 tests — SHA-256 computation, render
  success, missing variable raises, register/get, disk load, list

`Makefile` — `make eval` target: runs all offline evals, skips `live_llm` tests.

### Change 4 — Settings and endpoints ✅
- `llm_safety_block_enabled` in `Settings` dataclass and factory
- `LLM_SAFETY_BLOCK_ENABLED=false` in `.env.example`
- `GET /internal/prompt-registry` in `routes/internal.py`
- `GET /v1/missions/{id}/token-usage` proxied through `services/api-gateway`
