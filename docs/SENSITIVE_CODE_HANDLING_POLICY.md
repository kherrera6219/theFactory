# Sensitive Code Handling Policy

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Canonical (Policy)
Audience: Operators, security reviewers, agent developers, integrators, compliance officers

This policy governs how theFactory classifies, routes, stores, and protects target application source code submitted as part of a mission. It complements [`DATA_CLASSIFICATION_POLICY.md`](DATA_CLASSIFICATION_POLICY.md), which governs theFactory's own runtime data; this document specifically governs target application code processed by missions.

## Table of Contents

- [Scope](#scope)
- [Doctrine](#doctrine)
- [Source Code Classification Tiers](#source-code-classification-tiers)
- [Classification Procedure](#classification-procedure)
- [Provider Routing by Tier](#provider-routing-by-tier)
- [Storage and Retention](#storage-and-retention)
- [Logging Restrictions](#logging-restrictions)
- [Operator Overrides](#operator-overrides)
- [Audit Requirements](#audit-requirements)
- [Relationship to DATA_CLASSIFICATION_POLICY](#relationship-to-data_classification_policy)

---

## Scope

This policy applies to:

- Target application source code submitted via repo import or builder workflows
- Generated artifacts derived from that source (Refined IR nodes, LogicNodes, AIM)
- LLM prompts and completions that include or reference target source
- Logs, traces, and metrics that may capture target source content
- Audit evidence bundles that include target source artifacts

It does **not** apply to:

- theFactory's own runtime code (governed by normal repository practices)
- theFactory's own configuration data (governed by [`DATA_CLASSIFICATION_POLICY.md`](DATA_CLASSIFICATION_POLICY.md))
- Public open-source repositories used as demo or test inputs (treated as Tier 0)

## Doctrine

**Sensitive code stays local.**

Code submitted to theFactory belongs to the operator's organization, not to the model provider. Default routing decisions favor local processing, redaction over exposure, and explicit operator consent over implicit data transfer.

When in doubt, classify higher. The cost of over-protecting is operational friction. The cost of under-protecting is a disclosure incident.

## Source Code Classification Tiers

theFactory defines four tiers for source code classification. Each mission's `data_classification` field in the Mission Charter records the tier.

### Tier 0 — Public

**Definition:** Open-source repositories, demo repositories, or community projects under permissive licenses.

**Examples:**

- A public GitHub repository the operator imports for analysis
- The factory's own demo repos
- Curated community sample applications

**Routing:** Any provider permitted (Anthropic, OpenAI, Google, local).

**Storage:** Standard mission artifact retention (default 90 days).

**Logging:** Snippet logging permitted at debug level.

### Tier 1 — Internal

**Definition:** Proprietary code with no regulated data, no customer PII embedded, and no trade-secret algorithms. The default tier for typical enterprise code.

**Examples:**

- A typical internal SaaS application
- A company's internal CLI tools
- Build scripts and infrastructure-as-code

**Routing:** Operator-configured. May include cloud providers if the operator's organization has approved them.

**Storage:** Standard mission artifact retention; redacted in long-term archives.

**Logging:** No raw source content above debug level. Snippet redaction enabled.

### Tier 2 — Sensitive

**Definition:** Code containing credentials patterns, customer PII embedded as data, trade secrets, proprietary algorithms, or competitive intellectual property.

**Examples:**

- Code that processes payment information
- Trading or pricing algorithms
- Authentication and authorization logic with embedded secrets
- Code with hardcoded customer data (typically a finding to flag, not accept)

**Routing:** Local models only by default. Cloud providers permitted only with explicit operator override and audit record.

**Storage:** Encrypted at rest. Mission artifact retention reduced to 30 days unless extended by approval.

**Logging:** No source content in logs. Trace IDs only. PII guard enforced on all log paths.

### Tier 3 — Regulated

**Definition:** Code subject to regulatory frameworks: HIPAA, PCI-DSS, CUI, ITAR, EAR, FedRAMP, or equivalent.

**Examples:**

- Code processing protected health information
- Payment-card-handling code in PCI-scoped systems
- Defense-related code under ITAR controls
- Code in CUI-scoped environments

**Routing:** Local models only, no exceptions. Air-gapped deployment required for ITAR / CUI.

**Storage:** Encrypted at rest with strong key management. Retention defined by regulatory requirements; default 7-day artifact retention with operator-managed archive.

**Logging:** Production-level redaction. No source content in any log channel. Compliance officer review required for any retained evidence.

## Classification Procedure

Classification is performed at mission intake:

1. The operator declares a tier in the Mission Charter (default: Tier 1)
2. The factory runs initial heuristics during AIM generation:
   - PII pattern detection
   - Credentials and secrets pattern detection
   - Auth and crypto path detection
   - Regulated-data signal detection (HIPAA, PCI vocabulary)
3. If the heuristics suggest a higher tier than declared, the factory raises a classification warning
4. The operator confirms or revises the classification before subsequent phases proceed
5. The final classification is recorded in the Mission Charter and propagates to all downstream artifacts

Classification can only be downgraded by an explicit operator action recorded in an approval record.

## Provider Routing by Tier

**Correction (2026-07-03): this section describes an aspirational policy, not implemented enforcement.** There is no `local_only` field on `AgentPersona`/`agent_personas.py`, no tier-conditional routing refusal, and no override/expiration/approval-record mechanism anywhere in `llm_delegation/` (verified by grepping the package for `local_only`/`override`/`LocalOnlyViolation` — none exist). Every mission currently routes to whichever provider/model is configured for its agent (see `AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md`) regardless of `data_classification`. If tier-based provider restriction is required for your deployment, it must be enforced procedurally (e.g. by only configuring on-prem/local model endpoints for that deployment) rather than relying on the runtime to do it automatically.

The table below is retained as a statement of intended policy, not current behavior:

| Data Tier | Allowed Providers (intended policy, not enforced) |
|---|---|
| Tier 0 — Public | Any (Anthropic, OpenAI, Google, local) |
| Tier 1 — Internal | Operator-configured (may include cloud) |
| Tier 2 — Sensitive | Local only (no cloud providers without explicit override) |
| Tier 3 — Regulated | Local only, isolated network, air-gapped option |

## Storage and Retention

**Not implemented.** No tier-conditional retention job, encryption-at-rest toggle, or key-management tier exists in code today — missions and their artifacts persist in PostgreSQL/object storage indefinitely until manually pruned, regardless of `data_classification`. The table below is retained as a statement of intended policy for a future retention system, not current behavior:

| Tier | Default Retention (intended policy, not enforced) | Encryption at Rest | Key Management |
|---|---|---|---|
| Tier 0 | 90 days | Optional | Standard |
| Tier 1 | 90 days | Required | Standard |
| Tier 2 | 30 days | Required | Operator-managed |
| Tier 3 | 7 days (default) | Required | Compliance-managed |

## Logging Restrictions

| Tier | Snippet Logging | Variable Names | Trace Correlation |
|---|---|---|---|
| Tier 0 | Permitted | Permitted | Permitted |
| Tier 1 | Debug only, redacted | Permitted | Permitted |
| Tier 2 | Forbidden | Hash-only | Permitted |
| Tier 3 | Forbidden | Forbidden | Permitted |

**Correction (2026-07-03):** `shared_runtime/pii_guard.py` is a flat, non-tiered regex scanner (`detect_pii`/`redact_pii`) — it has no `DataClassification`-conditional branching and applies the same secret/PII patterns (API key patterns, JWT tokens, generic password/token key-value pairs, etc.) regardless of a mission's tier. The tier-differentiated logging table above describes an intended policy, not code that currently enforces it per-tier.

## Operator Overrides

**Not implemented.** This section previously described a temporary cloud-routing override mechanism (approval record, expiration time, evidence-bundle inclusion) that does not exist in the codebase — see the correction above. There is no override to request or grant today.

## Audit Requirements

Every classification decision, override, and routing decision is recorded:

- Mission Charter records the declared and final classification
- Each LLM call records the provider, model, and routing rationale
- Approval records capture every override with operator identity, timestamp, and justification
- Evidence bundles include the full classification chain for compliance review

Compliance officers may export classification and routing reports per project, per tier, or per time window via the audit-evidence export tooling.

## Relationship to DATA_CLASSIFICATION_POLICY

[`DATA_CLASSIFICATION_POLICY.md`](DATA_CLASSIFICATION_POLICY.md) documents the real `DataClassification` enum used for mission-level classification (`TIER_0_PUBLIC`/`TIER_1_INTERNAL`/`TIER_2_SENSITIVE`/`TIER_3_REGULATED`) and how thin its actual runtime enforcement currently is — see that document for the definitive, code-verified description.

This document, `SENSITIVE_CODE_HANDLING_POLICY.md`, governs target application source code submitted as part of a mission. Its tier system (0–3) is distinct because the threat model is different: target code is operator-supplied, may be subject to external regulatory frameworks, and is subject to provider-routing decisions that the factory's own runtime data is not.

Both policies operate together:

- A Tier 3 mission's source content is governed here
- The mission's RESTRICTED runtime metadata (state events, agent telemetry) is governed by `DATA_CLASSIFICATION_POLICY.md`
- Conflicts resolve to the stricter requirement
