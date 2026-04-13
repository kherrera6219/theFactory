# Model Promotion Governance

Document version: 2026.04.12
Last updated: 2026-04-12
Status: Canonical
Audience: ML engineers, operators, security reviewers, and release managers

## Purpose

This document defines the gates and approval chain required before a new LLM model reference, provider, or prompt template version may be promoted to the production default in theFactory.

Prevent release promotion when runtime-default LLM routes use preview, experimental, or rolling model versions without an explicit waiver.

---

## Model Reference Lifecycle

```
[Development] → [Staging Eval] → [Red-Team Review] → [Security Sign-off] → [Production Default]
```

A model reference consists of three parts that must be governed independently:

| Part | Location | Governance |
|---|---|---|
| Provider + model string | `.env.example`, `OPENAI_MODEL`, `ANTHROPIC_MODEL`, `GEMINI_MODEL` | Change requires env-variable PR review |
| Prompt template version | `PROMPT_VERSION` env var, `prompts/<version>/` | Change requires prompt-review checklist |
| Routing recommendation logic | `llm_delegation.py` `_recommend_model()` | Change requires security review |

---

## Production Rules

- Release promotion requires a machine-readable agent model inventory.
- `deploy/promotion-policy.json` blocks lifecycle stages `preview`, `experimental`, and `rolling`.
- Current Anthropic production default: `claude-sonnet-4-6`
- Current OpenAI production default: `gpt-5.3-codex`
- Current Gemini production default: `gemini-3-flash-preview` (requires waiver until GA)
- Preview routes may only be promoted if added to the policy allowlist with a named waiver approver.

---

## Gates for Promoting a New Model

### Gate 1 — Capability Eval

- [ ] Delegation golden-dataset tests pass: `pytest tests/eval/test_llm_delegation_golden.py`
- [ ] Red-team data-leakage tests pass: all `test_safe_context_*` tests green
- [ ] Latency P95 within 20 % of baseline measured in staging
- [ ] No new Tier 0 fields accessible via the model's tool-call interfaces

### Gate 2 — Prompt Compatibility

If the model requires updated prompts (new template version):

- [ ] New version directory `prompts/<version>/` contains all three templates: `ceo_delegation.txt`, `pod_manager_delegation.txt`, `specialist_planning.txt`
- [ ] `test_prompt_templates_exist_and_render` passes with `PROMPT_VERSION=<new>`
- [ ] `test_prompt_templates_contain_no_user_controlled_placeholders` passes
- [ ] Template diff reviewed by a security reviewer — only Tier 2/3 placeholders permitted (see `DATA_CLASSIFICATION_POLICY.md`)

### Gate 3 — Red-Team Verification

```bash
PROMPT_VERSION=<new> LLM_PROVIDER=<provider> pytest tests/eval/ -v
```

All tests must pass.  Any new data-leakage vector discovered must be:
1. Added to `_FORBIDDEN_CONTEXT_FIELDS` or as a new `test_safe_context_*` function
2. Fixed in `_safe_context_json` or `_clean_text`
3. Confirmed fixed by re-running the suite

### Gate 4 — Security Sign-off

A security lead must approve the promotion PR with:
- Model string before and after
- Prompt version before and after (if changed)
- Red-team test output (copy-paste or CI link)
- Latency delta vs baseline

### Gate 5 — Staged Rollout

1. Deploy model env var change to staging; monitor `llm_call` logs for `status=error` spike (abort if > 1 % over 30 min)
2. Promote to production and redeploy
3. Pin the old version in `.env.example` comment as rollback target for 30 days

---

## Prompt Template Governance

Templates in `services/orchestrator/orchestrator/prompts/<version>/` are **configuration under security review**.

**Templates may contain:** agent registry IDs, `{recommended_provider}/{recommended_model}`, `{safe_context_json}`

**Templates must NOT contain:** `{prompt}`, `{source_code}`, `{user_input}`, or any Tier 0/1 placeholder — see `DATA_CLASSIFICATION_POLICY.md`

---

## Rollback Procedure

1. Set `PROMPT_VERSION` to the previous version and redeploy (no code change required)
2. Set the model env var back to the previous model string and redeploy
3. File a post-mortem; add missing test case before next promotion attempt

---

## Gate Inputs (automated)

- Model inventory: `scripts/export_agent_model_inventory.py`
- Qualification summary: `scripts/qualification_gate_summary.py`
- Policy evaluator: `scripts/promotion_gate.py`

## Local Commands

- Export inventory: `python scripts/export_agent_model_inventory.py`
- Summarize qualification evidence: `make qualification-summary`
- Evaluate promotion gate: `make promotion-gate`

---

## Instrumentation for Auditors

Every LLM call emits a structured log line:

```
llm_call provider=<p> model=<m> route=<primary|fallback> context=<ceo|pod_mgr|specialist>
         latency_ms=<n> prompt_version=<v> status=<success|error|timeout>
```

Operators can verify which model and prompt version handled any mission by filtering on `mission_id` in the log aggregation pipeline.

---

*Last reviewed: 2026-04-12*
