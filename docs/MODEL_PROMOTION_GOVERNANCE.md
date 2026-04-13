# Model Promotion Governance

Document version: 2026.03.29  
Last updated: 2026-03-29  
Status: Canonical  
Audience: Maintainers, AI operators, and release reviewers

## Purpose

Prevent release promotion when runtime-default LLM routes use preview, experimental, or rolling model versions without an explicit waiver.

## Production Rules

- Release promotion requires a machine-readable agent model inventory.
- `deploy/promotion-policy.json` blocks lifecycle stages `preview`, `experimental`, and `rolling`.
- Current Gemini production defaults are `gemini-2.5-pro` and `gemini-2.5-flash`.
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

1. Confirm every default primary and fallback model is production-approved.
2. Confirm weekly qualification evidence is current and passing.
3. Confirm release attestation verification is passing in CI.
4. Only then allow `main` or release-tag promotion.
