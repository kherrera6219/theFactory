# Sensitive Code Handling Policy

Document version: 2026.04.25
Last updated: 2026-04-25
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

| Data Tier | Allowed Providers |
|---|---|
| Tier 0 — Public | Any (Anthropic, OpenAI, Google, local) |
| Tier 1 — Internal | Operator-configured (may include cloud) |
| Tier 2 — Sensitive | Local only (no cloud providers without explicit override) |
| Tier 3 — Regulated | Local only, isolated network, air-gapped option |

The LLM delegation layer enforces routing at request time. A request from a Tier 2 mission to a cloud provider is refused unless an active operator override is recorded. The override carries an expiration time and is included in the audit bundle.

Each agent retains its preferred cloud model in its profile but falls back to a local model when the data classification or operator configuration requires it. The model routing dashboard shows the actual routing decisions per agent, including which tier triggered any local fallback.

## Storage and Retention

| Tier | Default Retention | Encryption at Rest | Key Management |
|---|---|---|---|
| Tier 0 | 90 days | Optional | Standard |
| Tier 1 | 90 days | Required | Standard |
| Tier 2 | 30 days | Required | Operator-managed |
| Tier 3 | 7 days (default) | Required | Compliance-managed |

Audit evidence bundles are retained according to the mission's tier unless the operator configures longer retention. Tier 3 evidence retention is governed by the applicable regulatory framework.

## Logging Restrictions

| Tier | Snippet Logging | Variable Names | Trace Correlation |
|---|---|---|---|
| Tier 0 | Permitted | Permitted | Permitted |
| Tier 1 | Debug only, redacted | Permitted | Permitted |
| Tier 2 | Forbidden | Hash-only | Permitted |
| Tier 3 | Forbidden | Forbidden | Permitted |

The `pii_guard.py` module is extended for Tier 2 and Tier 3 to detect code-level secrets (API key patterns, connection strings, private key headers, JWT tokens, OAuth tokens) and redact them in any log output, not only in user input.

## Operator Overrides

An operator may temporarily route a Tier 2 mission to a cloud provider when:

- A specific phase requires capability available only in a cloud model
- The risk has been reviewed and accepted
- The override is recorded in an approval record
- The override has an explicit expiration time

Tier 3 missions cannot be overridden to cloud routing. Tier 3 routing is enforced at the deployment level (local-only LLM endpoints configured) rather than at runtime.

Every override is included in the mission evidence bundle and counts toward compliance reporting metrics.

## Audit Requirements

Every classification decision, override, and routing decision is recorded:

- Mission Charter records the declared and final classification
- Each LLM call records the provider, model, and routing rationale
- Approval records capture every override with operator identity, timestamp, and justification
- Evidence bundles include the full classification chain for compliance review

Compliance officers may export classification and routing reports per project, per tier, or per time window via the audit-evidence export tooling.

## Relationship to DATA_CLASSIFICATION_POLICY

[`DATA_CLASSIFICATION_POLICY.md`](DATA_CLASSIFICATION_POLICY.md) governs theFactory's own runtime data: mission state, internal events, agent telemetry, audit logs, and operator credentials. It uses three levels (PUBLIC, INTERNAL, RESTRICTED — see that document for the definitive list).

This document, `SENSITIVE_CODE_HANDLING_POLICY.md`, governs target application source code submitted as part of a mission. Its tier system (0–3) is distinct because the threat model is different: target code is operator-supplied, may be subject to external regulatory frameworks, and is subject to provider-routing decisions that the factory's own runtime data is not.

Both policies operate together:

- A Tier 3 mission's source content is governed here
- The mission's RESTRICTED runtime metadata (state events, agent telemetry) is governed by `DATA_CLASSIFICATION_POLICY.md`
- Conflicts resolve to the stricter requirement
