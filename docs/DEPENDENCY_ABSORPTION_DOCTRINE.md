# Dependency Absorption Doctrine

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Canonical (Doctrine)
Audience: Operators, security reviewers, agent developers, mission designers

This document defines the doctrine that governs how theFactory treats third-party dependencies in target applications. It is the single source of truth for absorption, replacement, retention, and governance decisions.

## Current Implementation Status (added 2026-07-03)

This document is a **policy target**, not a description of the shipped implementation — most of it is aspirational governance layered over a much simpler real classifier. Verified against `services/orchestrator/orchestrator/dependency_absorption.py`:

- **Implemented:** the block-list families (Security-critical, Platform/runtime drivers, Validation/serialization, HTTP clients, Framework core, Complex parsers, Safety-critical math, Observability — see `_classify_dependency()`'s family checks) and 3 of 6 named artifact schemas (`dependency_inventory.v1`, `dependency_absorption_report.v1` via `build_dependency_absorption_reports()`, and a real SBOM delta via `build_sbom_delta()`).
- **Not implemented:** the 7-step "Decision Hierarchy" (Absorb→Reimplement→Replace→Vendor→Wrap→Pin→Keep) does not exist — the real classifier is one function (`_classify_dependency()`) that checks a dependency's name against each block-list family in a fixed if/elif order and returns immediately on the first match, with exactly **6** outcomes (`keep`/`block`/`wrap`/`pin`/`replace`/`absorb` → categories `Keep`/`Block`/`Wrap`/`Pin`/`Replace`/`Absorbable`) — there is no separate "Possibly Absorbable" category. Most of the "Required Review Gates" below are not implemented: there is no distinct Intent gate, no `dependency_intent_node.v1` artifact, and no SecurityAgent-integration call site in this module. "Shadow Equivalence Mode" (running original and replacement in parallel before removal) does not exist anywhere in the codebase. The SBOM format is a custom `sbom_delta.v1` schema (`original_dependency_count`/`removed`/`remaining`/`kept_with_justification`/`reduction_percent`), **not CycloneDX 1.5** as stated below.

Treat everything below this point as the intended future-state doctrine, not a guarantee of current behavior. If you need to know what the code actually does today, read `dependency_absorption.py` directly — it is much simpler than this document describes.

## Table of Contents

- [Doctrine Statement](#doctrine-statement)
- [Why Absorb](#why-absorb)
- [Absorbability Categories](#absorbability-categories)
- [Decision Hierarchy](#decision-hierarchy)
- [Keep Criteria](#keep-criteria)
- [Initial Safety Block List](#initial-safety-block-list)
- [Required Review Gates](#required-review-gates)
- [Shadow Equivalence Mode](#shadow-equivalence-mode)
- [Absorption Workflow](#absorption-workflow)
- [Artifacts Produced](#artifacts-produced)
- [License and Legal Considerations](#license-and-legal-considerations)
- [Failure Modes and Anti-Patterns](#failure-modes-and-anti-patterns)

---

## Doctrine Statement

**Dependencies are liabilities until proven necessary.**

If theFactory can extract a dependency's logical intent, regenerate the needed behavior in first-party target code, prove equivalence with tests, reduce risk, size, or complexity, and run the application successfully, the dependency is eliminated.

Dependencies remain only when they cannot be safely, legally, efficiently, or economically replicated.

The default action is **ABSORB**. The default action is not KEEP.

## Why Absorb

Every third-party dependency carries cost beyond its useful function:

- **Security risk.** CVEs, malicious updates, abandoned maintenance, supply-chain attacks
- **Bloat.** Transitive dependency trees that ship hundreds of unused packages
- **License risk.** Copyleft contamination, viral re-licensing requirements
- **Maintenance burden.** Version pinning, breaking changes, compatibility windows
- **Audit complexity.** SBOM noise, attribution overhead, regulatory documentation
- **Performance cost.** Larger bundles, slower install, higher memory, longer cold starts
- **Behavioral lock-in.** Application bends to library design rather than the other way around

Most dependencies are used for a small, deterministic subset of their surface area. When theFactory can identify exactly which symbols are used, what they do, and how to reproduce them, absorption converts a liability into first-party code that is owned, understood, and tested.

## Absorbability Categories

theFactory classifies every detected dependency into one of these categories:

| Category | Meaning |
|---|---|
| Absorbable | Likely safe to internalize. Used surface is small, deterministic, and replicable. |
| Possibly Absorbable | Needs deeper review before a decision. Confidence is moderate. |
| Replace | Use a smaller or approved alternative rather than absorbing. |
| Wrap | Keep but isolate behind an internal adapter for future replaceability. |
| Pin | Keep, but lock the version with hash verification and CVE monitoring. |
| Keep | Must justify survival. Recorded in the survival justification artifact. |
| Block | Remove due to unacceptable security, license, or supply-chain risk. |

## Decision Hierarchy

When the absorption agent processes a dependency, it works through this hierarchy in order. The first applicable action wins.

| Priority | Action | Meaning |
|---|---|---|
| 1 | Absorb | Extract logic and rewrite as first-party target code |
| 2 | Reimplement | Build a cleaner internal version from extracted intent |
| 3 | Replace | Use a smaller, internal, or approved alternative |
| 4 | Vendor | Freeze a controlled internal copy with license tracking |
| 5 | Wrap | Isolate behind an adapter layer |
| 6 | Pin | Keep but lock version and add CVE monitoring |
| 7 | Keep | Only when safer options have been ruled out |

## Keep Criteria

A dependency survives only if one or more of the following are true. Each true criterion is recorded in the survival justification artifact:

1. Intent extraction failed or confidence is below the configured threshold
2. Behavior is too complex to reproduce safely
3. Replacement creates greater risk than keeping the dependency
4. The dependency is security-critical (cryptography, TLS, password hashing, JWT signing, signature verification)
5. The dependency is a platform or runtime driver (database driver, OS SDK, hardware driver)
6. The dependency is certified, regulated, proprietary, or contractually required
7. Equivalence tests cannot prove replacement behavior at the required confidence
8. Performance or compatibility cannot be matched within acceptable bounds
9. License does not allow inspection, copying, or derivative implementation
10. Human approval has explicitly marked the dependency as required

## Initial Safety Block List

The initial release of the absorption engine **must not attempt absorption** on the following families. They are reserved for advanced equivalence testing and SecurityAgent review only.

**Security-critical:**

- `cryptography` (Python `pyca/cryptography`)
- TLS and SSL libraries (`ssl`, `certifi`, `pyOpenSSL`)
- Password hashing (`bcrypt`, `argon2-cffi`, `passlib`)
- JWT signing and verification (`PyJWT`, `python-jose`, `jose`)
- HMAC and signature libraries
- Random number generation libraries used for crypto

**Platform and runtime drivers:**

- Database drivers (`asyncpg`, `psycopg2`, `motor`, `pymongo`, `redis-py`, `aiomysql`)
- Cloud SDK auth and signing modules (`boto3` signing, `google-auth`, `azure-identity`)
- Hardware and OS SDKs

**Validation and serialization (high edge-case risk):**

- `pydantic` — coercion behavior is complex and version-sensitive
- `marshmallow`
- `attrs`
- `zod` (TypeScript)

**HTTP clients:**

- `requests`, `httpx`, `aiohttp` — connection pooling, retry, TLS handling are non-trivial
- `axios`, fetch polyfills

**Framework core:**

- `fastapi`, `starlette`, `django`, `flask`
- `express`, `nextjs`, `react`, `vue`

**Complex parsers and compilers:**

- Compiler toolchains, parser combinators, regex engines, AST libraries

**Safety-critical math and science:**

- `numpy`, `scipy`, `sympy` — precision and correctness are proven; do not reimplement

**Logging frameworks (observability-impacting):**

- `structlog`, `loguru` — when deeply wired into the observability contract

This list is initial. It may shrink as advanced equivalence testing matures. It does not shrink unilaterally — changes require an ADR and SecurityAgent sign-off.

## Required Review Gates

Every absorption decision must pass these gates before any code is changed:

1. **Detection gate.** Dependency must appear in `dependency_inventory.v1` with usage information.
2. **Intent gate.** A `dependency_intent_node.v1` artifact must be produced with confidence above threshold.
3. **SecurityAgent gate.** AGENT-05-SECURITY reviews every absorption candidate, regardless of category. Approval is recorded in the absorption plan.
4. **Operator approval gate.** For Production and Regulated depth modes, the operator approves the absorption plan as a whole.
5. **Equivalence gate.** Generated equivalence tests must pass before the original dependency is removed.
6. **Shadow gate.** Shadow equivalence must pass during the configured shadow period.
7. **Build gate.** The application must build successfully without the absorbed dependency.
8. **Runtime QC gate.** Runtime QC must pass before the mission is marked complete.

A failure at any gate halts the absorption and produces a `dependency_survival_justification.v1` instead of an absorption report.

## Shadow Equivalence Mode

Before removing an absorbed dependency, the factory runs both the original and the replacement in parallel.

**Procedure:**

1. The replacement module is wired in alongside the original
2. Both receive identical inputs from the running application
3. Outputs are compared using the generated equivalence test suite plus runtime divergence detection
4. Divergence above the configured threshold halts the absorption
5. The shadow period runs for a configurable duration (minutes for utilities, hours for core libraries)
6. Only after the shadow period passes with zero unexplained divergence does the original dependency get removed

Shadow equivalence is mandatory for any dependency the SecurityAgent classifies as medium or high risk. It is configurable for low-risk utility absorption.

## Absorption Workflow

```
Dependency graph scan
  → usage mapping (which files, which symbols, which call patterns)
  → used-symbol extraction
  → dependency intent extraction → dependency_intent_node.v1
  → Refined IR / LogicNode generation
  → absorbability classification
  → SecurityAgent review of all candidates
  → operator approval of absorption plan (Production/Regulated)
  → target-code regeneration
  → equivalence test generation
  → shadow equivalence run
  → import and call-site rewrite
  → package removal
  → SBOM delta (CycloneDX 1.5)
  → build / test / runtime QC
  → absorption report or survival justification
```

## Artifacts Produced

Every dependency processed in an absorption mission produces at least one of the following:

| Artifact | When Produced |
|---|---|
| `dependency_inventory.v1` | Once per mission, lists all detected dependencies and classifications |
| `dependency_intent_node.v1` | Per dependency that proceeds past detection |
| `dependency_absorption_plan.v1` | Per mission, lists all proposed absorption actions |
| `dependency_absorption_report.v1` | Per dependency successfully absorbed |
| `dependency_survival_justification.v1` | Per dependency that survives any review gate |
| `code_bloat_reduction_report.v1` | Per dependency absorbed, with size and performance impact |
| SBOM before / SBOM after / SBOM delta | Per mission, in CycloneDX 1.5 format |

## License and Legal Considerations

Absorption is not legal license laundering. The license of an absorbed dependency must permit the target code's intended distribution.

**Permitted (under typical conditions):**

- MIT, Apache 2.0, BSD-2-Clause, BSD-3-Clause, ISC, MPL-2.0 (file-level)

**Conditional or blocked (depends on target distribution):**

- LGPL — only with proper attribution and dynamic linking treatment
- GPL, AGPL — incompatible with closed-source distribution; absorption is blocked unless target is also GPL/AGPL
- Proprietary or unknown — absorption blocked

The absorption agent records the source license in the absorption report and refuses absorption when the license is incompatible with the target's intended distribution.

License classification is performed during the dependency inventory phase and is reviewed by the operator alongside the absorption plan.

## Failure Modes and Anti-Patterns

The following are explicitly prohibited:

- **Absorbing a dependency without SecurityAgent review.** Every candidate gets reviewed.
- **Absorbing without equivalence tests.** Behavior must be provable.
- **Absorbing without shadow equivalence for medium and high risk.** Edge cases hide outside unit test coverage.
- **Absorbing without recording the original license.** License compatibility is non-negotiable.
- **Absorbing without SBOM delta.** Supply chain accountability requires before-and-after evidence.
- **Skipping the operator approval gate.** Production and Regulated missions require human sign-off.
- **Absorbing items on the safety block list.** No exceptions without ADR and SecurityAgent sign-off.
- **Reimplementing cryptographic primitives.** Use vetted libraries; pin and monitor instead.
- **Removing a dependency before the absorption is verified.** Snapshots are mandatory; rollback must be available.
