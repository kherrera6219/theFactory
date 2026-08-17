# Model Promotion Governance

Document version: 2026.06.13
Last updated: 2026-08-15
Status: Canonical  
Audience: Maintainers, AI operators, and release reviewers

## Purpose

Prevent release promotion when runtime-default LLM routes use preview, experimental, or rolling model versions without an explicit waiver.

## Production Rules

- Release promotion requires a machine-readable agent model inventory.
- `deploy/promotion-policy.json` blocks lifecycle stages `preview`, `experimental`, and `rolling`.
- All 41 agents default to `gemini-3.7-flash` with high thinking for the
  Gemini-first local test path.
- Mission Control exposes operator-selectable model routes:
  `gemini-3.7-flash`, `gpt-5.5`, and `claude-opus-4-8`. These routes are
  allowed for vault-slot testing, but only Gemini 3.7 Flash is assigned as an
  agent default.
- `allowlist_models` in `deploy/promotion-policy.json` is empty; no preview
  waivers are active.
- Preview routes may only be promoted if added to the policy allowlist.

## Gate Inputs

- Model inventory: `scripts/export_agent_model_inventory.py`
- Qualification summary: `scripts/qualification_gate_summary.py`
- Policy evaluator: `scripts/promotion_gate.py`

## Local Commands

- Export inventory: `python scripts/export_agent_model_inventory.py`
- Summarize qualification evidence: `make qualification-summary`
- Evaluate release gate: `make promotion-gate`

## Promotion Checklist

1. Confirm every default primary and fallback model is production-approved or
   explicitly allowlisted with a current provider-doc reference.
2. Confirm weekly qualification evidence is current and passing.
3. Confirm release attestation verification is passing in CI.
4. Confirm the Mission Control model catalog still contains only the approved
   three routes.
5. Only then allow `main` or release-tag promotion.
