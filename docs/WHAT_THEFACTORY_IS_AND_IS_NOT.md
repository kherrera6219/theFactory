# What theFactory Is and Is Not

Document version: 2026.08.17
Last updated: 2026-08-17
Status: Canonical
Audience: Operators, evaluators, contributors, partners, and internal stakeholders

This document is the canonical positioning statement for theFactory. Use it to align internal teams, brief evaluators, write external-facing copy, and resolve scope disputes about what the product is intended to do.

## Table of Contents

- [Purpose](#purpose)
- [What theFactory Is](#what-thefactory-is)
- [What theFactory Is Not](#what-thefactory-is-not)
- [theFactory vs. Vibe Coding](#thefactory-vs-vibe-coding)
- [theFactory vs. Common Categories](#thefactory-vs-common-categories)
- [Scope Boundaries](#scope-boundaries)
- [Long-Term Vision (Non-Scope)](#long-term-vision-non-scope)

---

## Purpose

Software-AI tooling is a noisy category. The same words mean different things to different people. This document fixes the meaning of theFactory in plain language so that engineering, product, sales, and audit conversations stay grounded.

If a proposed feature, talking point, or roadmap item conflicts with this document, this document wins. Update this document deliberately when product positioning shifts.

## What theFactory Is

theFactory is:

- **A complete software production system.** Missions take a request from natural-language intake through requirements, architecture, code, tests, runtime validation, and audit evidence.
- **A PM-led SOW factory.** Create, import, port, or update through the PM. The operator sees a Statement of Work with an honest factory token-spend range and cap before they approve. PORT through an accepted SOW and fail-QC-blocks-COMPLETE are recorded live.
- **A multi-agent runtime.** A registry of 41 specialist roles activates on demand, communicates over an event bus, and produces verifiable artifacts. The default deployed topology is condensed; 41 isolated processes are not the default.
- **A dependency-reduction engine.** It absorbs unnecessary dependencies by extracting their intent and regenerating first-party code with equivalence tests.
- **A workspace-isolated execution environment.** Every mission operates in an isolated, recoverable workspace; the original source is never modified.
- **A runtime QC platform.** Generated tests run in `sandbox-runner`. A FAIL verdict blocks COMPLETE. A launch-only or syntax-only run is ADVISORY, never PASS.
- **An audit-evidence producer.** Every mission emits a structured chain-of-custody bundle: charter, plan, diff, tests, QC report, approvals.
- **Local-first by design.** It runs on a single Docker host, with optional cloud LLM routing controlled by data classification policy.
- **A governed system.** Human approval gates, signed approvals, and policy enforcement are first-class, not afterthoughts.

## What theFactory Is Not

theFactory is not:

- **Not a chat-to-code tool.** It is not a single-prompt assistant that emits a code block and ends the interaction.
- **Not an autocomplete or IDE extension.** It is not a Copilot-style inline suggester.
- **Not a one-shot generator.** It does not produce throwaway demo code without architecture, tests, or evidence.
- **Not a transpiler.** Transpilers convert syntax. theFactory extracts intent and regenerates behavior.
- **Not a model.** It is a system that orchestrates models. Different missions use different providers.
- **Not a SaaS product.** It is a local-first runtime. Optional managed-service editions are out-of-scope today.
- **Not a build system replacement.** It does not replace Bazel, Gradle, npm, or pip. It uses them.
- **Not a CI/CD platform.** It produces artifacts and evidence that integrate with CI/CD; it does not replace GitHub Actions or equivalents.
- **Not a deployment system.** It builds and validates; deployment to production is a downstream action governed by the operator.
- **Not a vulnerability scanner alone.** It uses scanners as inputs but its scope is broader: hardening, absorbing, and validating.
- **Not a domain-vertical factory.** Today it produces software. Domain factories (data, analytics, simulation) are long-term vision, not current scope.

## theFactory vs. Vibe Coding

"Vibe coding" describes the pattern of prompting an LLM to generate code, previewing the result, patching errors, and iterating until the demo runs. It is fast and useful for prototypes. It is not how theFactory operates.

| Normal Vibe Coding | theFactory |
|---|---|
| Fast prompt-to-code | Full software production lifecycle |
| One model, one chat loop | Task-activated agent workforce |
| Often adds dependencies quickly | Eliminates dependencies unless necessary |
| Preview-first | Requirements, architecture, tests, runtime QC |
| Weak traceability | Mission events, artifacts, audit evidence |
| Demo-focused | Production-readiness focused |
| Runs on your machine | Operates in isolated, disposable workspaces |
| No audit trail | Full chain-of-custody evidence bundle |
| Trust the LLM | Verify with tests and runtime QC |
| Ship the dependency tree | Shrink the dependency tree |

The difference is governance, evidence, and verifiability. Both approaches have their place. theFactory is built for the work that vibe coding cannot ship to production.

## theFactory vs. Common Categories

| Category | How It Differs from theFactory |
|---|---|
| AI code completion (Copilot, Cursor inline) | theFactory orchestrates full missions; completion tools assist a single keystroke |
| Chat-to-code (ChatGPT, Claude conversations) | theFactory persists state, runs agents in parallel, produces evidence; chat is ephemeral |
| Agentic IDE (Cursor agent, Cline, Windsurf) | theFactory is a multi-service backend with its own UI; not a code editor add-on |
| Prompt-engineering libraries (LangChain, DSPy) | theFactory uses such patterns internally but ships as a complete product |
| RAG document Q&A | theFactory uses retrieval but produces software, not answers |
| Test generation tools | theFactory generates tests as part of broader missions, not as the standalone product |
| Static analysis | theFactory uses static analysis as input but its output is changes and evidence |
| Code modernization vendors | theFactory shares the goal but adds dependency absorption, runtime QC, and full audit evidence |
| Build / CI systems | theFactory builds for validation inside missions; production CI/CD is downstream |
| Dependency vulnerability scanners | theFactory consumes their output, but absorbs or replaces the dependency rather than only flagging it |

## Scope Boundaries

**In scope today:**

- Repository import and analysis
- Application Intelligence Map generation
- Dependency analysis, absorption planning, absorption execution
- Code generation, patch planning, patch application
- Test generation and execution
- Ephemeral runtime test environment provisioning
- AI runtime QC for web applications
- Multi-language extraction across 20 routed language keys
- Audit evidence bundle generation
- Local-first deployment with optional cloud LLM routing
- Human approval gates with HMAC-signed approvals

**Adjacent and integratable, but not owned:**

- Production deployment systems (Kubernetes, ECS, etc.)
- External CI/CD pipelines
- Source control hosting
- Long-term artifact storage (S3, Artifactory)
- Identity providers (the factory consumes OIDC, does not provide it)

**Out of scope today:**

- Multi-tenant SaaS hosting
- Real-time collaborative editing
- Domain-specific factories (data factory, simulation factory, analytics factory)
- Mobile-app runtime QC (web first; mobile later)
- Autonomous production deployment without human approval
- Real customer data in test environments

## Long-Term Vision (Non-Scope)

The long-term vision includes domain factories beyond software (data analytics, simulation, scientific computing), federated multi-instance deployments, and managed-service editions. None of these are current-scope items. Treat them as direction, not commitment, and do not build for them today.

The current commitment is straightforward: **build the Software Factory correctly first.** Everything else follows.
