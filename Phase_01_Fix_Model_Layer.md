# Phase 1 - Model Governance and Live LLM Validation
## Tier 1 | Estimated Duration: 1-2 days

---

## Context

The previous Phase 1 plan assumed that every current OpenAI model string was
invalid and prescribed immediate replacements with `o3`, `o4-mini`,
`gpt-4o`, and `gpt-4o-mini`.

That is too strong. The current codebase does contain hard-coded model IDs such
as `gpt-5.5` and `gpt-5.3-codex`, but model availability is
time-sensitive. The correct first step is to verify the active model matrix
against the live provider/API and promotion policy, then update only the entries
that are actually invalid, blocked, deprecated, or mismatched with the runtime
API payload.

The goal of this phase is not "replace strings." The goal is to prove that the
LLM layer is alive, governed, and observable.

---

## Current Risk

LLM delegation is central to CEO routing, pod-manager routing, specialist
planning, and future contract/code generation. If a configured model is invalid,
blocked, or incompatible with the request payload, the runtime can silently fall
back to deterministic behavior.

That fallback is useful, but it can make the UI appear healthy while the
intelligence layer is offline. Phase 1 makes this explicit and testable.

**Current validation - May 17, 2026:** Phase 1 is implemented for the repo's
configured defaults. The active model matrix has been updated to `gpt-5.5`,
`gpt-5.3-codex`, `claude-opus-4-7`, `claude-sonnet-4-6`,
`gemini-3.1-pro-preview`, and `gemini-3.1-flash-lite`; model inventory export,
focused tests, full Python tests, Mission Control lint/test, and deterministic
CEO-delegation smoke have passed. Remaining work is a credentialed live-provider
smoke proving non-fallback LLM routing in this environment.

---

## Exact Work

### 1. Inventory model assignments

Search and record model IDs from:

- `services/orchestrator/orchestrator/agent_integrations.py`
- `services/orchestrator/orchestrator/llm_delegation.py`
- `services/api-gateway/api_gateway/main.py`
- `apps/mission-control/app/(shell)/settings/page.tsx`
- `.env.example`
- `deploy/docker-compose.yaml`
- `docs/AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md`
- `docs/MODEL_PROMOTION_GOVERNANCE.md`

Expected current strings include:

- `gpt-5.5`
- `gpt-5.3-codex`
- provider fallback models for Anthropic and Gemini

Do not treat these as invalid until verified.

### 2. Verify provider availability

Use the live provider/API or current official provider model catalog to classify
each configured model as:

- `active`
- `deprecated`
- `preview`
- `rolling`
- `unknown`
- `blocked_by_policy`
- `payload_incompatible`

Record the result in a checked-in report under `reports/` or an implementation
status appendix.

### 3. Update model config only where needed

If a model is invalid or blocked, update:

- backend model profile;
- fallback profile;
- Mission Control static display;
- `.env.example`;
- Docker Compose default;
- model governance docs.

Do not hard-code `o3`, `o4-mini`, or any other replacement unless it has been
verified as available, production-approved, and compatible with the code path
using it.

### 4. Add a model-governance smoke test

Add a test that builds the agent integration snapshot and fails if a production
agent uses:

- an empty model;
- an unknown model classification;
- a preview/rolling model blocked by policy;
- a backend/display mismatch between orchestrator and Mission Control.

The test should not rely on stale assumptions like "all `gpt-5` names are
invalid." It should rely on the repo's explicit model registry or a generated
model-governance fixture.

### 5. Add a live/fallback LLM smoke path

Create a small checked-in smoke script, for example:

```bash
python scripts/smoke_ceo_delegation.py
```

Behavior:

- if API keys are present, make one CEO delegation call and assert the result is
  an LLM-sourced route;
- if API keys are absent, assert deterministic fallback works and print a clear
  "no credentials" status;
- never print secret values.

### 6. Update docs

Update:

- `docs/IMPLEMENTATION_STATUS.md`
- `docs/AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md`
- `docs/MODEL_PROMOTION_GOVERNANCE.md`
- this phase doc if exact model choices change during implementation

The docs should distinguish:

- configured model;
- verified provider availability date;
- promotion lifecycle;
- fallback model;
- whether live delegation was actually tested.

---

## Files Likely Changed

- `services/orchestrator/orchestrator/agent_integrations.py`
- `services/orchestrator/orchestrator/llm_delegation.py`
- `services/api-gateway/api_gateway/main.py`
- `apps/mission-control/app/(shell)/settings/page.tsx`
- `.env.example`
- `deploy/docker-compose.yaml`
- `scripts/smoke_ceo_delegation.py`
- `tests/services/test_llm_delegation_unit.py`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md`
- `docs/MODEL_PROMOTION_GOVERNANCE.md`

---

## Validation Steps

Run the model inventory:

```bash
python scripts/export_agent_model_inventory.py --output-file reports/agent-model-inventory.local.json
```

Run the promotion gate summary:

```bash
python scripts/qualification_gate_summary.py --policy-file deploy/promotion-policy.json --output-file reports/qualification-gate-summary.local.json
```

Run unit tests:

```bash
pytest tests/services/test_llm_delegation_unit.py -v
```

Run the full suite:

```bash
make test
```

Run the CEO delegation smoke:

```bash
python scripts/smoke_ceo_delegation.py
```

If Python is unavailable in the local shell, stop and fix the environment before
claiming Phase 1 complete.

---

## Definition of Done

- [x] Current model IDs are inventoried from backend, frontend, env, deploy, and docs.
- [x] Each production model assignment has a verified availability/lifecycle status.
- [x] Invalid or blocked assignments are replaced with verified alternatives.
- [x] Backend config, frontend display, env defaults, and docs agree.
- [x] Promotion model governance reports zero blocked production agents.
- [ ] CEO delegation smoke proves live LLM routing when credentials are present.
- [x] Deterministic fallback is explicitly verified when credentials are absent.
- [x] Focused unit tests, full Python tests, Mission Control lint, and Mission Control tests pass.
- [x] `docs/IMPLEMENTATION_STATUS.md` records the verification result.

---

## Risk Notes

### Model names drift

Provider model catalogs change. Do not encode permanent truth in the plan. Encode
the verification process and record the verification date.

### Payload compatibility matters

A model can exist and still fail if the request payload is incompatible. The
OpenAI path currently uses the Responses API style. Any replacement must be
tested against that path, not only checked for existence in a model list.

### Fallback can hide failure

Fallback behavior is useful for local operation, but a production system needs
to show when fallback was used. Phase 1 should ensure source, provider, model,
and fallback status are visible in audit events or mission metadata.

### Do not print secrets

Smoke scripts may inspect whether credentials exist, but they must never print
secret values.
