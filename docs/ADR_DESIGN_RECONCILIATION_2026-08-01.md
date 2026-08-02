# ADR: Design Reconciliation — Holy Grail Refinery Design Corpus vs. theFactory (2026-08-01)

Status: Accepted
Owner: platform architecture
Supersedes in part: the Feb–Mar 2026 numbered design corpus (Docs 01–64)
Evidence base: [DESIGN_VS_BUILD_AUDIT_2026-08-01.md](DESIGN_VS_BUILD_AUDIT_2026-08-01.md)
Execution plan: [UPGRADE_RECONCILIATION_PLAN_2026-08-01.md](UPGRADE_RECONCILIATION_PLAN_2026-08-01.md)

## Context

Two document sets in this project are both marked authoritative and they describe
**different products**.

The Feb–Mar 2026 design corpus (Docs 01–64, archived under
`docs/archive/2026-03-29/legacy-workspace/root-legacy-documentation/`) specifies the
*Holy Grail Refinery*: a system that ingests 14 languages, extracts semantic
LogicNodes in parallel across four language pods, fuses them into one verified
Master Logic Stream via cross-language equivalence checking at 0.0001% tolerance,
and emits an optimised zero-dependency binary via LLVM IR.

The repository's own `docs/` suite (2026-06 onward) describes theFactory: a
governed, evidence-producing, multi-agent code generation and modernisation
platform that delivers **source artifacts plus a cryptographic evidence chain**.
[WHAT_THEFACTORY_IS_AND_IS_NOT.md](WHAT_THEFACTORY_IS_AND_IS_NOT.md) already states
this honestly.

The second product is what exists. The first was never formally retired. Until now
nothing in either corpus pointed at the other, so every new contributor and every
external evaluator re-derived the same confusion — and the repository contained a
status page contradicting its own schema documentation.

This ADR assigns exactly one verdict — **Implemented**, **Superseded**, or
**Deferred** — to every design area, with the deciding evidence. It is the single
reference for "was this built, and if not, was that a decision or an omission?"

**Governing rule used throughout: code is the source of truth.** Every row below
cites a file that was read directly. Where the audit and the code disagreed, the
code won and the discrepancy is noted in [§ Corrections](#corrections-to-the-audit-and-plan).

## Decisions

Verdict definitions:

- **Implemented** — the design intent exists in shipped code. May exceed the design.
- **Superseded** — deliberately replaced by a different approach. Not a gap. The
  design document is historical from this date.
- **Deferred** — still wanted, not built, with a named revisit trigger.

| # | Design area | Design source | Verdict | Rationale | Deciding evidence |
|---|---|---|---|---|---|
| 1 | Agent organisation & tiers | Doc 05 §2, Doc 06 | **Implemented** (exceeds) | 41 agents against a designed 35; tier/pod/`AGENT-NN-CODE` naming matches exactly. Adds a `runtime_class` field the design never asked for, distinguishing real worker processes from logical agents | `agent_registry.py` — 41 `AgentDefinition` blocks; `runtime_class` defaults to `synthesized_heartbeat`, derived to `shared_worker` by category (L18, L37–40) |
| 2 | Language coverage | Doc 05 §1.1 (14 languages) | **Implemented** (exceeds) | 19 routed language keys against a designed 14. Go, Haskell, OCaml are net-new; TypeScript aliases onto javascript | `agent_registry.py` `LANGUAGE_ALIASES` → 19 distinct targets: c, cpp, csharp, go, haskell, java, javascript, julia, kotlin, mathematica, matlab, ocaml, php, python, r, ruby, rust, scala, zig |
| 3 | Six communication protocols | Doc 07 | **Implemented** (exceeds) | All six lanes typed and validated on a hardened bus. Adds per-agent HMAC signing, dedup, replay rejection, backpressure, DLQ, and production fail-fast — materially beyond the designed "at-least-once delivery" | `services/protocol-bus-mcp/protocol_bus/mcp_server.py`; strict `extra="forbid"` per-protocol payloads |
| 4 | Bus as control plane | Doc 07 §1.2 | **Deferred** | All six lanes have live producers, but exactly **one** consumer handler exists and every send is fire-and-forget. Doc 07's "agents subscribe and activate when their trigger fires" is not how the system executes. Committed to via decision D3, executed as Phase 6 (EDCP) | `main.py:505` — `handlers = {"sigma": _handle_sigma_knowledge_ready}`; `settings.py:127` — `event_driven_control_plane_enabled: bool = False` |
| 5 | Message envelope | Doc 07 §2 | **Superseded** | Two envelopes are in production, neither matching Doc 07, and they disagree with each other on priority vocabulary. The design envelope is retired; the two live envelopes are documented and reconciled additively in Phase 2 (UPG-22) | `schemas/event.envelope.schema.json` — priority enum is `["NORMAL","HIGH"]`; bus `/send` body accepts `low\|normal\|high\|critical` |
| 6 | LogicNode schema (30 fields) | Doc 09 §2.1 | **Superseded, partially reinstated** | The shipped node is a 7-field work envelope with everything descriptive inside a free-form `payload`. The 30-field semantic node is not being built as designed, but the descriptive fields are promoted to first-class *optional* properties in Phase 3 (UPG-30/31) | `schemas/logicnode.schema.json` — `required` = `node_id, cmd, payload, priority, intent, types, provenance`; `additionalProperties: false`; `types.in`/`types.out` emitted empty |
| 7 | Refined-IR (semantic) | Doc 09 | **Superseded, partially reinstated** | The RIR *schema* is faithful; the *producer* is templated. One `EXTRACT_CONCEPT` op per function, purity derived from whether a string is truthy, equivalence vectors that restate the node's own identifiers. Real derivation ships for AST-backed languages only in Phase 4; regex-only languages stay templated and are labelled as such | `pod-worker/refined_ir.py` `build_refined_ir_module()`; corroborated by [LOGICNODE_SCHEMA.md](LOGICNODE_SCHEMA.md) |
| 8 | Equivalence verification | Doc 09 §8, Doc 30 §4 | **Superseded, partially reinstated** | Shipped verification is **contract conformance**, not behaviour: does the artifact match its contract. The designed 1,000-simulation execution engine at 0.0001% tolerance does not exist. Execution-based behavioural equivalence for a language subset ships in Phase 5, reusing RQCA's existing sandbox | `equivalence_verifier.py` — `"verification_scope": "correctness"`; `settings.py:87–88` — both `mission_equivalence_enforcement_enabled` and `mission_equivalence_python_execution_enabled` default `False` |
| 9 | Equivalence tolerance 0.0001% / 99.9999% | Docs 01–09 | **Superseded** | The figure appears in every one of the first ten design documents and is **computed nowhere**. Semantic equivalence is undecidable for arbitrary programs; the number was never achievable. Replaced by metrics the system actually produces — contract-conformance pass rate, runtime-QC verdict, and (post-Phase 5) behavioural equivalence-vector pass ratio | Repository-wide search: no occurrence of the figure in any `services/` source file |
| 10 | LogicNode Registry | Doc 30 (1,635 lines) | **Deferred** | The largest unimplemented specification in the corpus. Built instead: a per-mission `mission_logicnodes` JSONB table with a Neo4j mirror — no cross-mission registry, versioning, clustering, or semantic search. Only valuable once RIR carries real cross-mission semantics. **Revisit trigger: Phase 4 `ast_v1` projections cover a majority of missions** | `mission_logicnodes (mission_id, node_id, node_json JSONB)`; `neo4j_store.py` |
| 11 | Binary / LLVM synthesis | Doc 01 §1.3, Doc 05, Doc 09 §1.3 | **Superseded** (decision D2) | The design's headline promise, with zero implementation and no partial scaffolding. The product delivers source artifacts plus an evidence chain. Formally killed — see [§ D2](#d2--binary-synthesis-is-retired) | No compilation, linking, or LLVM stage anywhere in `services/`. Outputs are source files and gzipped bundles (`build_artifacts.py`, `deploy_exporter.py`) |
| 12 | Data architecture | Doc 08 | **Implemented** (exceeds) | All five designed stores map onto real engines. `V009_immutable_audit.sql` revokes `DELETE` on audit tables from the application role with retention via a `SECURITY DEFINER` prune function — a real tamper-evidence control beyond the design | Qdrant + Milvus, PostgreSQL + Neo4j, migrations V001–V009, MinIO, `llm_cost_ledger.py` |
| 13 | Orchestration engine (LangGraph) | Doc 14 (678 lines) | **Superseded** | Doc 14 is entirely per-agent LangGraph state machines; those were never written. The live engine is a hand-rolled mission-level transition table that is clean, tested, has v1↔v2 compatibility mapping, and recovers in-flight missions on restart. Formal disposition of the disabled second engine is UPG-71 | `settings.py:79,81` — `langgraph_enabled = False`, `langgraph_checkpointer = "none"`; `mission_flow_v2/transitions.py` — `V2_TRANSITIONS` |
| 14 | 14 → 4 → 1 comprehension model | Doc 05 §1.1, `HGR_Mission_Flow_v2` | **Superseded** (decision D1) | No parallel four-pod extraction, no cross-language fusion, no Tier-3 cross-language verification. A mission routes to **one pod and one specialist** from `requested_target_language`. Four-pod fan-out multiplies LLM cost per mission and only pays for itself once RIR carries deep semantics across every language — which it will not after the current plan. The four-pod structure survives as routing metadata | `mission_flow_v2/phases_build.py:328+` — single `resolve_pod_manager_agent_id` / `resolve_specialist_agent_id` |
| 15 | Security & hardening | Doc 26 | **Implemented** (exceeds) | Doc 26 asked for JWT + RBAC + TLS + container hardening. Built: dual-mode auth, prompt/PII guards, ECDSA artifact signing, agent-scoped control-plane keys, service-wide compose hardening, and production guards that raise rather than warn | `shared_runtime/{prompt_guard,pii_guard,crypto_signing}.py`; [ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md](ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md) |
| 16 | Per-agent context isolation | Doc 05 (first principle) | **Superseded** | Doc 05's first architectural principle was per-agent API keys and 1M-token windows. Reality is one key per *provider*, resolved globally. The `AGENT_NN_*_SERVICE_API_KEY` family is real but authenticates worker→orchestrator control-plane mutations, not LLM calls. Per-agent *provider* credentials are not worth the operational cost at single-operator scale; cost attribution is already recovered per `agent_id` | `llm_delegation/config.py`; `llm_cost_ledger.py`; [AGENT_SERVICE_KEY_ISOLATION.md](AGENT_SERVICE_KEY_ISOLATION.md) |
| 17 | Mission Control UI | Doc 15 | **Implemented** (exceeds), one gap **Deferred** | 15+ routes against a designed 9 panels, with `axe-core`, Lighthouse CI, and Playwright E2E. The one genuine gap is Doc 15 §3.1's LogicNode dependency graph — deferred to UPG-70 because until Phase 3 lands there is no dependency data to draw | `apps/mission-control/app/(shell)/`; no graph library present |
| 18 | Pod taxonomy | Docs 10–13 | **Superseded** (drift to be corrected) | Pod D is labelled "Mathematical Languages" but contains Haskell and OCaml. Pods are uneven against a design specifying uniform 6-agent pods. Renamed rather than restructured in UPG-23 | Verified per-pod specialist counts: **A:4, B:5, C:4, D:6** (Pod D specialists = MATLAB, R, Julia, Mathematica, Haskell, OCaml; Go is Pod B) |
| 19 | Mission taxonomy | *no design source* | **Implemented** (undesigned) | 10 `MissionType`, 5 `DepthMode`, 8 `OutputMode`, 4 `DataClassification` values exist with **no specification document**. This is the product's actual commercial surface and the largest unwritten spec in the system. To be specified retroactively in UPG-72 | `models.py` |

## D2 — Binary synthesis is retired

Recorded here rather than in a separate ADR, because the decision is one row of a
larger reconciliation and splitting it would create two documents to keep in sync.

**Decision:** theFactory does not, and will not, compile to binaries. It delivers
source artifacts with a cryptographic evidence chain. Doc 01 §1.3's "zero
dependencies (smelted into core logic)" and Doc 09 §1.3's "Optimized Binary (LLVM
IR → machine code)" are retired.

**Rationale:** zero implementation, no partial scaffolding, and no customer-facing
commitment depends on it. The product's differentiation moved to governance,
provenance, and brownfield modernisation — none of which needs a compiler.

**What this decision does *not* touch — read this before deleting anything:**

- `pod-worker/toolchains.py` **stays exactly as-is.** It runs *syntax checkers*
  (`py_compile`, `node --check`, `go vet`, `rustc --parse-only`, `gcc -fsyntax-only`,
  `javac`, `ghc -fno-code`, `ocamlc -c`). That is pre-flight validation and it is
  correct and useful. Retiring binary *synthesis* is not removing toolchain
  *validation*.
- The `agent_personas.py` Julia persona's "LLVM-backend awareness" phrase **stays.**
  Julia genuinely is an LLVM-based JIT language; the phrase describes the target
  language's real compiler and is guidance a Julia specialist should have. It is not
  a claim that theFactory emits LLVM IR. See [§ Corrections](#corrections-to-the-audit-and-plan).

**Agent role strings rewritten under this decision:**

| Agent | Before | After |
|---|---|---|
| `AGENT-11-DEPLOY` | "Binary packaging, delivery, and environment setup" | "Artifact packaging, delivery, and environment setup" |
| `AGENT-09-HW` | "CPU/GPU optimization and hardware-specific mapping" | "Reserved: target-profile hints for generation (no compilation role)" |

## Corrections to the audit and plan

Phase 1 was executed with instructions to validate the plan against live code. Three
of the plan's premises did not survive that check. They are recorded here so the next
reader does not re-derive them.

1. **`agent_personas.py`'s LLVM reference should not be removed.** UPG-11 instructs
   "remove or requalify the LLVM reference (~L136)". The line reads *"Certified Julia
   Developer: Multiple dispatch optimization, LLVM-backend awareness, and
   high-performance scientific kernels."* This is an accurate statement about Julia's
   own compiler and useful persona guidance. Removing it would make the persona less
   correct, not more honest. **Kept, with the rationale recorded above.**

2. **UPG-11's "strip binary/LLVM claims from `docs/`" was already satisfied.** No
   document under `docs/` outside `archive/` asserts binary or LLVM output as a
   product capability. Remaining matches are legitimate unrelated uses ("binary file
   detection" in the ZIP import plan, `docker_bin`, `psycopg[binary]`, "a single
   binary gate" meaning two-valued) or meta-discussion of this retirement. The
   2026-07-03 documentation audit appears to have removed the claims already.

3. **UPG-13's "remove the 0.0001% figure from `docs/`" was likewise already
   satisfied.** The figure survives in `docs/` only in the audit, the plan,
   `CURRENT_TODO.md`, `HANDOFF_CURRENT.md`, and `AGENTS.md` — all of which reference
   it in order to retire it — plus
   `docs/evidence/word_doc_extraction_2026-03-08.json`, which is an **evidence
   artifact recording what the design documents said**. Evidence files are immutable
   records and were deliberately not rewritten; `evidence/` is also excluded from
   `scripts/validate_documentation.py`. The substantive work of UPG-13 is therefore
   the replacement-metric statement in row 9 above, not deletion.

4. **UPG-15's target corpus is already archived.** Docs 01–64 are not loose in the
   repository — they are at
   `docs/archive/2026-03-29/legacy-workspace/root-legacy-documentation/`, a path that
   `validate_documentation.py` skips entirely and that this project's own conventions
   already treat as historical. Annotating 65 files individually was judged
   disproportionate; a single directory-level `README.md` carrying the supersession
   notice was written instead, which is what a reader entering that directory actually
   encounters.

## Canonical policy

1. **This ADR outranks the numbered design corpus** wherever they disagree. Docs 01–64
   are historical from 2026-08-01.
2. A **Superseded** verdict is a closed decision, not a backlog item. Reopening one
   requires an amendment to this ADR, not a plan edit.
3. A **Deferred** verdict must carry a named revisit trigger. Deferred items are not
   roadmap commitments.
4. No document in this repository may claim binary/LLVM output or a 0.0001% /
   99.9999% equivalence tolerance.
5. Where a shipped artifact is synthetic or templated, it must say so in a field a
   consumer can read — not only in prose. (Implemented as `projection_method` in
   UPG-40.)

## Consequences

- The repository stops carrying two contradictory canonical specifications. The
  credibility exposure identified as the single largest risk in the audit closes.
- `docs/IMPLEMENTATION_STATUS.md` is rescoped to claims that survive scrutiny
  (UPG-12), removing its contradiction with `docs/LOGICNODE_SCHEMA.md`.
- Design areas 4, 6, 7, 8, 10, 17 have named execution phases; areas 5, 11, 13, 14,
  16, 18 are closed decisions requiring no further work beyond the string edits above.
- External technical due diligence can be answered from one table rather than by
  reading 64 design documents against a live codebase.
- What was an apparently 60%-implemented design becomes a fully-implemented and
  honestly-scoped one.

## Related

- [DESIGN_VS_BUILD_AUDIT_2026-08-01.md](DESIGN_VS_BUILD_AUDIT_2026-08-01.md) — the evidence base
- [UPGRADE_RECONCILIATION_PLAN_2026-08-01.md](UPGRADE_RECONCILIATION_PLAN_2026-08-01.md) — the execution plan
- [DESIGN_TRACEABILITY.md](DESIGN_TRACEABILITY.md) — per-design-document traceability matrix
- [WHAT_THEFACTORY_IS_AND_IS_NOT.md](WHAT_THEFACTORY_IS_AND_IS_NOT.md) — the product statement this ADR ratifies
- [LOGICNODE_SCHEMA.md](LOGICNODE_SCHEMA.md) — source-grounded LogicNode/RIR reference
- [ADR_STRATEGIC_DEFERRED_SCOPE_DECISIONS_2026-03-08.md](ADR_STRATEGIC_DEFERRED_SCOPE_DECISIONS_2026-03-08.md) — prior deferral governance
