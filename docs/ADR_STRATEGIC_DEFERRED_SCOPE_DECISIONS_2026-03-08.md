# ADR: Strategic Deferred-Scope Decisions (2026-03-08)

Status: Accepted  
Owner: platform architecture

## Context

Legacy planning artifacts included advanced strategic tracks that were intentionally deferred while theFactory stabilized mission-flow correctness, security, observability, and production hardening.

This ADR converts those deferred items into explicit governance decisions with trigger criteria and prerequisites.

## Decisions

| Scope Item | Decision | Trigger Criteria | Prerequisites |
| --- | --- | --- | --- |
| Self-update/autonomous upgrade engine | Defer | Signed release promotion runs clean for 90 days and rollback MTTR < 15 minutes | Trusted updater design, staged rollout controls, cryptographic key rotation playbook |
| Hosted cloud multi-tenant operations | Defer | Customer requirement for tenant isolation and managed control-plane operation | Tenant isolation architecture, per-tenant key management, audited billing/compliance boundaries |
| Third-party agent marketplace | Defer | Partner demand and governance capacity for curated external extensions | Package signing, malware scanning, trust policy enforcement, legal/compliance review workflow |
| Distributed execution (GPU/TPU/FPGA and mission sharding) | Defer (R&D) | Measured workload saturation on current single-node topology | Scheduler redesign, resource quota policy, deterministic mission partition/retry model |
| Language-surface expansion beyond current specialist set | Defer | Sustained backlog where unsupported language requests exceed 20% of intake over 30 days | Specialist persona package, extractor coverage, test fixtures, quality-gate expansion |

## Canonical Policy

1. Deferred items are not active production commitments.
2. Adoption requires a dedicated ADR and implementation phase plan before enablement.
3. Any pilot must include rollback guardrails, evidence artifacts, and explicit success/failure gates.

## Consequences

- Roadmap claims remain aligned with shipped behavior.
- Strategic items stay visible but governed by measurable entry criteria.
- Delivery focus remains on deterministic mission runtime reliability and enterprise controls.
