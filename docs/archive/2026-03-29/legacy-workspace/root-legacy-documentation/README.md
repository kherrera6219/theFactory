# ⚠️ Historical design corpus — superseded in part (Feb–Mar 2026)

Document version: 2026.08.01
Last updated: 2026-08-01
Status: Historical — superseded in part, not current specification
Audience: Anyone who arrived at the numbered design documents in this directory

**Do not read the numbered documents (01–64) in this directory as current
specification.** They are the Feb–Mar 2026 design phase of the *Holy Grail Refinery*.
The product that was actually built diverged from them deliberately, and that
divergence was formally recorded on 2026-08-01.

## Read these instead

| For | Read |
|---|---|
| Which design areas were built, superseded, or deferred — and why | [`docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md`](../../../../ADR_DESIGN_RECONCILIATION_2026-08-01.md) |
| Per-document status for every file in this directory | [`docs/DESIGN_TRACEABILITY.md`](../../../../DESIGN_TRACEABILITY.md) |
| The file-by-file evidence behind those verdicts | [`docs/DESIGN_VS_BUILD_AUDIT_2026-08-01.md`](../../../../DESIGN_VS_BUILD_AUDIT_2026-08-01.md) |
| What the product actually is today | [`docs/WHAT_THEFACTORY_IS_AND_IS_NOT.md`](../../../../WHAT_THEFACTORY_IS_AND_IS_NOT.md) |

## What specifically is retired

These appear throughout the numbered documents and are **closed decisions**, not
backlog items. Do not reintroduce them into planning:

- **Binary / LLVM synthesis.** Docs 01 §1.3 and 09 §1.3 terminate the pipeline at
  "Optimized Binary (LLVM IR → machine code)". Never implemented; formally killed
  (ADR decision D2). theFactory delivers **source artifacts plus a cryptographic
  evidence chain**. *Note: this does not retire `pod-worker/toolchains.py` syntax
  validation, which stays.*
- **The 0.0001% / 99.9999% equivalence tolerance.** Present in all ten of Docs
  00–09 and **computed nowhere** in the codebase. Semantic equivalence is
  undecidable for arbitrary programs; the figure was never achievable. Replaced by
  contract-conformance pass rate and runtime-QC verdict.
- **The 14 → 4 → 1 comprehension model.** No parallel four-pod extraction, no
  cross-language fusion, no Tier-3 cross-language verification. A mission routes to
  **one pod and one specialist** from the requested target language. The four-pod
  structure survives as routing metadata (ADR decision D1).
- **The LogicNode Registry (Doc 30).** Deferred, with a named revisit trigger.
- **Per-agent LLM context isolation** (Doc 05's first architectural principle).
  Superseded — one credential per provider, with cost attribution per `agent_id`.

## What is still accurate

Most of this corpus describes what was built, often understating it. Docs 06
(agent architecture), 08 (data architecture), 21 (schemas), 23–28 (quality,
CI/CD, observability, security, operations), and 41–50 (test strategy) map onto
shipped code that in several cases exceeds the specification. `DESIGN_TRACEABILITY.md`
gives the per-document verdict.

## Why these files are kept

They are the design record. They explain why the system is shaped the way it is,
and several of the retired ideas are worth understanding before anyone proposes
them again.
