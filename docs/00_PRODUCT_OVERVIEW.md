# Product Overview

Document version: 2026.08.17
Last updated: 2026-08-17
Status: Canonical
Audience: Operators, developers, partners, evaluators, and new contributors

This is the five-minute orientation document for theFactory. Read this first if you are new to the project, evaluating it as a buyer, considering contribution, or trying to position it internally to a team.

## Table of Contents

- [What theFactory Is](#what-thefactory-is)
- [What Problem It Solves](#what-problem-it-solves)
- [Core Value Propositions](#core-value-propositions)
- [How It Works at a Glance](#how-it-works-at-a-glance)
- [Mission Modes](#mission-modes)
- [Mission Depth Modes](#mission-depth-modes)
- [Output Modes](#output-modes)
- [Who It Is For](#who-it-is-for)
- [Doctrines](#doctrines)
- [Where to Go Next](#where-to-go-next)

---

## What theFactory Is

theFactory is a local-first, event-driven AI software factory. It accepts natural-language missions and delivers working software through a fully governed orchestration pipeline staffed by task-activated specialist agents.

It is not a code-completion tool, a chat-to-code assistant, or a single-prompt generator. It is a complete software production system that produces requirements, architecture, code, tests, runtime environments, runtime validation, and audit-ready evidence as part of every mission it runs.

### Current factory face (2026-08-17)

The operator talks to the PM. They can **create** software or **import**
existing software for rework / port / update. They receive a Statement of
Work — scope, out of scope, deliverables, acceptance, and an honest
factory token-spend range plus cap — **before** they approve. Work is
tested in `sandbox-runner`. A failing generated test does not become
`COMPLETE`. Live evidence:
[end_state_live_proof_20260817.json](evidence/end_state_live_proof_20260817.json).

## What Problem It Solves

Modern AI coding tools generate code quickly but produce systems that are difficult to verify, maintain, and govern:

- Generated code carries unnecessary dependency trees
- Demos pass but production fails because runtime conditions were never tested
- There is no audit trail for what was changed, why, or by which agent
- Sensitive code is shipped to external providers without policy
- Reviewing AI-authored output is harder than writing the code by hand
- Modernization, porting, and security hardening are unattainable with one-shot prompts

theFactory addresses these directly with task-activated specialist agents, dependency absorption, isolated workspaces, ephemeral test environments, AI runtime QC, and a complete chain-of-custody evidence bundle for every mission.

## Core Value Propositions

| Capability | What It Means |
|---|---|
| Task-activated agent workforce | 41+ specialist roles activate only when needed; no idle workforce, no missing skills |
| Multi-provider model routing | Anthropic, OpenAI, Google, and local models routed per agent and per data classification |
| Dependency absorption | The factory eliminates unnecessary dependencies by extracting their intent and regenerating first-party code |
| Isolated workspaces | Every mission runs in a disposable workspace; the original source is never modified |
| Ephemeral runtime environments | PostgreSQL, Redis, and other services provisioned per mission, torn down on completion |
| AI runtime QC | The factory launches the built application and validates it through a sandboxed browser session |
| Audit evidence bundle | Every mission produces a verifiable proof package: charter, plan, diff, tests, QC, approvals |
| Multiple deployment topologies | Default condensed runtime; dedicated agent containers; full 41-agent isolation overlay |

## How It Works at a Glance

```
PM intake
  → requirements
  → architecture
  → mission plan
  → agent activation
  → code, docs, tests, build
  → dependency absorption
  → isolated workspace
  → disposable test environment
  → runtime QC
  → audit evidence
  → release handoff
```

A mission begins when an operator submits a natural-language request through Mission Control or the API gateway. The PM agent (AGENT-01) formalizes it into a Mission Charter, the CEO agent (AGENT-02) plans delegation, and specialist agents activate to execute the plan. The protocol bus routes events between agents on Redis Streams. The orchestrator persists state in PostgreSQL and emits live updates over Server-Sent Events. The audit worker verifies completion and produces the evidence bundle.

For full architecture detail, see [`ARCHITECTURE.md`](ARCHITECTURE.md), [`ARCHITECTURE_DIAGRAMS.md`](ARCHITECTURE_DIAGRAMS.md), and [`ARCHITECTURE_DATA_FLOWS.md`](ARCHITECTURE_DATA_FLOWS.md).

## Mission Modes

The operator selects what they want the factory to do at intake:

1. Build a new application from scratch
2. Import and modernize an existing repo
3. Port an application to another OS, platform, or language
4. Debug or repair a repo
5. Security harden a repo
6. Reduce dependencies and code bloat
7. Run and QC a built or patched app
8. Generate architecture and documentation only
9. Analyze only — no code changes
10. Self-analyze theFactory itself

## Mission Depth Modes

| Mode | Use |
|---|---|
| Sprint | Fast prototype or first pass |
| Standard | Normal engineering workflow |
| Production | Full docs, tests, security, runtime QC |
| Regulated | Compliance gates, stronger evidence, full approval chain |
| Autonomous Long Run | Multi-hour or multi-day work with checkpoints and resume |

## Output Modes

| Mode | Behavior |
|---|---|
| Analyze only | Reports only, no changes |
| Plan only | Plans and charters only |
| Patch proposal | Generates diffs but does not apply |
| Apply patch | Applies approved changes to an isolated workspace |
| Full build | Applies, tests, documents, and packages |
| Dependency reduction only | Removes or absorbs safe dependencies |
| Run and QC only | Launches and validates an existing app |
| Full transformation | Multi-phase port or modernization |

## Who It Is For

| Role | Primary Use |
|---|---|
| Engineering team | Repository hardening, dependency reduction, modernization |
| Security team | Repo security review, dependency vulnerability remediation |
| Platform team | Application onboarding, runtime validation, supply-chain governance |
| Buyer or evaluator | Verifiable production work with full evidence bundles |
| Compliance and audit | Audit-ready chain-of-custody evidence per mission |
| Solo developer or contractor | End-to-end software production with reduced dependency surface |

## Doctrines

These are the non-negotiable principles that guide every implementation decision in the project:

1. **theFactory is not vibe coding.** It produces complete, governed software production cycles, not single-prompt code drops.
2. **Agents are task-activated.** A registry of available roles is not a permanent workforce. Agents activate when needed and return to idle.
3. **Dependencies are liabilities until proven necessary.** The default action is to absorb a dependency by extracting its intent and regenerating first-party code. Dependencies that survive must be justified.
4. **Smart coding.** Generate only what the application actually needs. No unused logic, no bloated package chains, no external code unless truly required.
5. **Workspaces are isolated by default.** The factory never modifies the source directly. Changes are diffs, reviewed and applied only after approval.
6. **Nothing ships without evidence.** Every mission that modifies code produces a verifiable audit trail.
7. **Sensitive code stays local.** Code containing credentials, PII, trade secrets, or regulated data is never sent to external LLM providers without operator consent.

These are documented in detail in [`WHAT_THEFACTORY_IS_AND_IS_NOT.md`](WHAT_THEFACTORY_IS_AND_IS_NOT.md) and [`DEPENDENCY_ABSORPTION_DOCTRINE.md`](DEPENDENCY_ABSORPTION_DOCTRINE.md).

## Where to Go Next

| If you want to | Read |
|---|---|
| Run the system locally | [`user/GETTING_STARTED.md`](user/GETTING_STARTED.md) |
| Understand the architecture | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Position the product internally | [`WHAT_THEFACTORY_IS_AND_IS_NOT.md`](WHAT_THEFACTORY_IS_AND_IS_NOT.md) |
| Understand the dependency absorption capability | [`DEPENDENCY_ABSORPTION_DOCTRINE.md`](DEPENDENCY_ABSORPTION_DOCTRINE.md) |
| Understand application intelligence | [`APPLICATION_INTELLIGENCE_MAP.md`](APPLICATION_INTELLIGENCE_MAP.md) |
| Understand runtime QC | [`RUNTIME_QC_AND_TEST_ENVIRONMENTS.md`](RUNTIME_QC_AND_TEST_ENVIRONMENTS.md) |
| Review the data and code handling policy | [`SENSITIVE_CODE_HANDLING_POLICY.md`](SENSITIVE_CODE_HANDLING_POLICY.md) |
| Understand schema governance | [`SCHEMA_REGISTRY_AND_VERSIONING.md`](SCHEMA_REGISTRY_AND_VERSIONING.md) |
| Understand the license model | [`LICENSE_STRATEGY.md`](LICENSE_STRATEGY.md) |
| Check what is shipped today | [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) |
| See current status | [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) |
