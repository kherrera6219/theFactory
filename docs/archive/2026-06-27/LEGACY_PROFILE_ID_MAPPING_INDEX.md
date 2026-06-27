# Legacy Profile ID Mapping Index

Document version: 2026.03.29  
Last updated: 2026-03-29  
Status: Reference  
Audience: Operators, developers, maintainers, and auditors

> Historical note (2026-03-29): This document predates the current 41-agent runtime. Treat any `35-agent` references below as historical planning terminology unless explicitly updated in a newer canonical document.

## Canonical Rule

- Runtime authority is the 41-agent registry in `services/orchestrator/orchestrator/agent_registry.py`.
- Legacy `*-001` profile IDs are documentation aliases only and must not be emitted in mission metadata or scheduler bindings.

## Direct Alias Mappings

| Legacy alias | Canonical target | Notes |
|---|---|---|
| `ARCH-001`, `PM-001`, `EXEC-PM-001`, `PM-AGENT-001` | `AGENT-01-PM` | User-facing intake lead |
| `CEO-001`, `EXEC-CEO-001`, `CEO-AGENT-001` | `AGENT-02-CEO` | Executive delegation lead |
| `BROKER-001` | `AGENT-03-BROKER` | API broker support role |
| `MANAGER-POD-A-001`, `POD-A-MGR-001`, `MGR-POD-A` | `AGENT-12-PODA-MGR` | Pod A manager |
| `MANAGER-POD-B-001`, `POD-B-MGR-001`, `MGR-POD-B` | `AGENT-18-PODB-MGR` | Pod B manager |
| `MANAGER-POD-C-001`, `POD-C-MGR-001`, `MGR-POD-C` | `AGENT-24-PODC-MGR` | Pod C manager |
| `MANAGER-POD-D-001`, `POD-D-MGR-001`, `MGR-POD-D` | `AGENT-30-PODD-MGR` | Pod D manager |
| `AGENT-PY-001`, `PY-001` | `AGENT-14-PYTHON` | Pod A specialist |
| `JS-001` | `AGENT-15-JAVASCRIPT` | Legacy shorthand without `AGENT-` prefix |
| `AGENT-RUBY-001` | `AGENT-16-RUBY` | Pod A specialist |
| `AGENT-PHP-001` | `AGENT-17-PHP` | Pod A specialist |
| `AGENT-C-001` | `AGENT-20-C` | Pod B specialist |
| `AGENT-CPP-001` | `AGENT-21-CPP` | Pod B specialist |
| `AGENT-RUST-001` | `AGENT-22-RUST` | Pod B specialist |
| `AGENT-ZIG-001` | `AGENT-23-ZIG` | Pod B specialist |
| `AGENT-JAVA-001` | `AGENT-26-JAVA` | Pod C specialist |
| `AGENT-CS-001` | `AGENT-27-CSHARP` | Legacy `CS` alias maps to canonical `CSHARP` |
| `AGENT-SCALA-001` | `AGENT-28-SCALA` | Pod C specialist |
| `AGENT-KOTLIN-001` | `AGENT-29-KOTLIN` | Pod C specialist |
| `AGENT-MATLAB-001` | `AGENT-32-MATLAB` | Pod D specialist |
| `AGENT-R-001` | `AGENT-33-R` | Pod D specialist |
| `AGENT-JULIA-001` | `AGENT-34-JULIA` | Pod D specialist |
| `AGENT-MATH-001` | `AGENT-35-MATHEMATICA` | Legacy math alias |

## Capability Mappings

| Legacy alias | Canonical disposition | Notes |
|---|---|---|
| `AUDIT-LEAD-001`, `AUDIT-CORRECTNESS-001`, `AUDIT-PERF-001`, `AUDIT-SEC-001`, `AUDIT-COMPLIANCE-001`, `AUDIT-INTEGRATION-001` | Pod audit roles plus `AGENT-05-SECURITY`, `AGENT-08-COMPLIANCE`, `AGENT-10-TESTER` | Quality dimensions, not extra registry IDs |
| `SUPPORT-SEC-001` | `AGENT-05-SECURITY` | Canonical support agent |
| `SUPPORT-DEPLOY-001`, `SUPPORT-DEVOPS-001` | `AGENT-11-DEPLOY` | Deployment/DevOps capability rolls into deployment agent behavior |
| `SUPPORT-COMPLIANCE-001` | `AGENT-08-COMPLIANCE` | Canonical support agent |
| `SUPPORT-INFRA-001` | Platform service behavior | No dedicated canonical agent ID |
| `SUPPORT-DIR-001` | Governance escalation alias | Route through PM/CEO and support ring; do not use as runtime agent ID |

## Deprecated or Non-Canonical Aliases

| Legacy alias | Disposition | Notes |
|---|---|---|
| `AGENT-GO-001` | `AGENT-36-GO` | Canonical Go specialist in the 41-agent runtime |
| `SPECIALIST-AI-001` | Deprecated design placeholder | Not part of the canonical 41-agent runtime |
| `EXEC-001`, `EXEC-002`, `SUPPORT-001`..`SUPPORT-009` | Ambiguous numeric aliases | Replace with the named canonical `AGENT-xx-*` IDs only |
| `LN-*`, `TASK-*`, `M-*`, `SYS-*`, `ENT-*`, `MATH-*` | Non-agent identifiers | Artifact, example, or domain IDs; not runtime profile IDs |


