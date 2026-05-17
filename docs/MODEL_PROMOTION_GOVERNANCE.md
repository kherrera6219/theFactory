# Model Promotion Governance

Document version: 2026.05.17  
Last updated: 2026-05-17  
Status: Canonical  
Audience: Maintainers, AI operators, and release reviewers

## Purpose

Prevent release promotion when runtime-default LLM routes use preview, experimental, or rolling model versions without an explicit waiver.

## Production Rules

- Release promotion requires a machine-readable agent model inventory.
- `deploy/promotion-policy.json` blocks lifecycle stages `preview`, `experimental`, and `rolling`.
- Current Gemini defaults are `gemini-3.1-pro-preview` and
  `gemini-3.1-flash-lite`.
- Gemini 3.1 Pro is currently a preview-lifecycle route in the official Google
  docs. It is intentionally listed in `allowlist_models` until a stable 3.1 Pro
  ID is published or this project chooses to pin back to stable Gemini 2.5 Pro.
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
4. Only then allow `main` or release-tag promotion.
