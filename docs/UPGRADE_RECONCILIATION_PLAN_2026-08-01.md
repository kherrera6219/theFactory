# theFactory — Upgrade & Reconciliation Plan (2026-08-01)

Document version: 2026.08.01
Last updated: 2026-08-01
Status: Canonical — active plan. **Phase 1 COMPLETE (2026-08-01). Phase 2 is next.**
Audience: Maintainers and AI coding agents executing the work

**No application code has been changed.** The only edits made when this plan was
filed were documentation: this file, the companion audit,
`docs/CURRENT_TODO.md`, `docs/HANDOFF_CURRENT.md`, `AGENTS.md`,
`docs/IMPLEMENTATION_STATUS.md` (a contested-claims banner),
`docs/EDCP_PHASE_PLAN.md`, `docs/PROTOCOL_BUS_PROGRAM_ROADMAP.md`,
`docs/README.md`, and `docs/DOCUMENTATION_INDEX.md` — plus deletion of a stale
duplicate of `FULL_APP_REMEDIATION_PLAN_2026-07-05.md` at the repo root.

**Companion document:** `docs/DESIGN_VS_BUILD_AUDIT_2026-08-01.md` is
the source of every finding referenced here (file/line evidence, per-area
verdicts). Read it first if you need the raw evidence behind any item below —
this plan restates findings only briefly enough to sequence and justify the work.

**Relationship to existing plans.** This plan does **not** replace
`docs/EDCP_PHASE_PLAN.md` or `docs/PROTOCOL_BUS_PROGRAM_ROADMAP.md`. Those are
already well-specified and are executed as-written in Phase 6, with one inserted
sub-phase. `docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` Phase 4 (Electron /
Windows installer) is orthogonal and continues independently.

---

## 0. Cold start — read this first

If you are a fresh coding session picking this up with no prior context, read in
this order and stop when you can answer the question in brackets:

1. `docs/DESIGN_VS_BUILD_AUDIT_2026-08-01.md` §1–§2 — *[what is the gap?]*
2. This document §1 (Decisions taken) and §11 (Explicit non-goals) — *[what did
   we decide, and what must I refuse to build?]*
3. This document §4 (Phase 1) — *[what is the first task?]*
4. `docs/CURRENT_TODO.md` "Active Work Queue" — *[what is actually next right now?]*

Then, only when the phase you are working on needs it:

- Phase 3/4 work → `docs/LOGICNODE_SCHEMA.md` (the source-grounded reference for
  the real LogicNode/RIR pipeline), `schemas/logicnode.schema.json`,
  `services/pod-worker/pod_worker/main.py:_build_schema_node`
- Phase 5 work → `services/orchestrator/orchestrator/rqca_agent.py`,
  `equivalence_verifier.py`
- Phase 6 work → `docs/EDCP_PHASE_PLAN.md`, `docs/PROTOCOL_BUS_PROGRAM_ROADMAP.md`

**Do not read the numbered design documents (01–64) as current specification.**
They are the Feb–Mar 2026 design phase and are superseded in part — that is what
Phase 1 exists to record. `docs/HGR_Gap_Report.md`-style material in project
knowledge is stale in its "what's missing" sections (see UPG-15).

**Three standing rules for every phase:**

- Code is the source of truth. Verify against live files before asserting.
- Every behavioural change ships behind an `*_ENABLED` flag defaulting to
  `false`. Flag off ⇒ byte-identical behaviour.
- Nothing in §14 ("What stays exactly as it is") gets removed or weakened.

---

## 1. Decisions taken

Three forks were open. All three are now closed and are treated as settled
inputs to this plan, not open questions:

| # | Decision | Chosen | Consequence |
|---|---|---|---|
| D1 | Semantic engine | **Pragmatic middle** | Enrich LogicNodes additively, make RIR extraction real where AST support already exists, build genuine execution-based equivalence for a language subset. **Keep single-specialist routing.** No 4-pod fan-out. |
| D2 | Binary synthesis | **Formally killed** | Recorded in an ADR, stripped from all docs, `AGENT-09-HW` and `AGENT-11-DEPLOY` role text rewritten. The product delivers source artifacts + evidence. |
| D3 | Protocol Bus | **Commit to EDCP** | The bus becomes load-bearing. Existing EDCP plan executes, starting with a Delta consumer that can actually gate a mission. |

**What D1 explicitly does not mean.** It does not mean the 14 → 4 → 1
comprehension model gets built. Parallel four-pod extraction and cross-language
Tier-3 verification remain **out of scope** — they multiply LLM cost per mission
and only pay for themselves once RIR carries deep semantics across every
language, which it will not after this plan. What D1 buys is that Refined-IR
stops being a well-formed empty envelope and starts carrying verifiable content
for the languages where the AST work is already done.

---

## 2. Guiding principles

1. **Keep the good, and keep it working.** Everything in §3 of the audit —
   the bus hardening, the immutable audit chain, dual-mode auth, ECDSA signing,
   feature-flag discipline, the 41-agent registry, the operator UI — is
   untouched by this plan except where a phase explicitly extends it. No phase
   removes a working capability.
2. **Additive schema evolution only.** Every LogicNode and RIR change adds
   optional fields. `additionalProperties: false` stays. Validation stays
   non-fatal. Nothing already persisted in `mission_logicnodes` becomes invalid.
3. **Flag discipline, unchanged.** Every behavioural change ships behind an
   `*_ENABLED` flag defaulting to `false`, per the existing convention
   (`AGENT_SCALING_ENABLED`, `MISSION_*_ENFORCEMENT_ENABLED`,
   `EVENT_DRIVEN_CONTROL_PLANE_ENABLED`). Flag off ⇒ byte-identical behaviour.
4. **Reuse the sandbox you already built.** Execution-based equivalence
   (Phase 5) runs inside RQCA's existing Docker harness (`rqca_agent.py`,
   `_COMPILED_LANGUAGE_CONFIG`, `_EXECUTABLE_LANGUAGES`, `_MAX_TIMEOUT_SECONDS
   = 60`, `_MAX_MEMORY_MB = 512`). That harness already runs containers with
   `--network=none --read-only --cap-drop=ALL --memory-swap=0 --cpus=1
   --security-opt=no-new-privileges:true`, a 64 MB tmpfs, and a read-only
   `/workspace` bind mount (`rqca_agent.py:649-661`). Do not build a second
   execution environment, and do not relax any of those flags.
5. **Honesty is machine-readable, not just prose.** Where an artifact is
   synthetic, the artifact says so in a field a consumer can read — not only in
   a paragraph in `docs/LOGICNODE_SCHEMA.md`.
6. **Documentation truth precedes code.** Phase 1 is documentation-only and
   lands first, because every later phase is judged against a specification
   that must first be correct.

---

## 3. Sequencing rationale

Phases are ordered by **what unblocks what**, not by area:

- **Phase 1 (docs)** first because it costs days, not weeks, removes the only
  real credibility exposure in the repository, and defines the target every
  later phase is measured against. It has no code dependency and could run in
  parallel with anything — it is first because it is cheap and clarifying.
- **Phase 2 (foundation)** next: closes the S1-01 gate with real evidence,
  removes a dead setting, and fixes the envelope vocabulary mismatch. Phase 6
  (EDCP) has S1-01 as a hard prerequisite, so this must precede it.
- **Phase 3 (LogicNode v2)** before Phase 4, because RIR is projected *from*
  LogicNodes — a richer node is the input a real projection needs. It also gets
  more expensive with every mission that accumulates rows in
  `mission_logicnodes`, so it should not wait.
- **Phase 4 (real RIR)** before Phase 5, because execution-based equivalence
  needs real equivalence vectors, and those come from real signatures.
- **Phase 5 (behavioural equivalence)** is the payoff phase — the first point at
  which the product can honestly claim it verifies behaviour rather than shape.
- **Phase 6 (EDCP)** is independent of Phases 3–5 and could run concurrently if there
  is capacity. It is sequenced after because it is the largest surface and
  because debugging an event-driven pipeline while also changing the artifact
  schema doubles the diagnostic difficulty.
- **Phase 7 (consolidation)** last: the UI dependency graph needs Phase 3's
  data to have anything to draw, and the remaining decisions are cheap once
  everything else has landed.

```
Phase 1 ──▶ Phase 2 ──┬──▶ Phase 3 ──▶ Phase 4 ──▶ Phase 5 ──┐
   docs      foundation │      nodes       RIR      behaviour  ├──▶ Phase 7
                        └──▶ Phase 6 (EDCP, per existing plan)─┘   consolidation
```

---

## 4. Phase 1 — Truth reconciliation (documentation only, no runtime change)

> **✅ COMPLETE — 2026-08-01.** All five exit criteria met. Deliverables:
> `docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md` (UPG-10, 19 verdict rows),
> two `agent_registry.py` role strings rewritten (UPG-11),
> `docs/IMPLEMENTATION_STATUS.md` rescoped (UPG-12),
> `docs/DESIGN_TRACEABILITY.md` created (UPG-14),
> corpus README + gap-report staleness block (UPG-15).
>
> **Three plan premises did not survive validation against live code and were
> deliberately not executed as written.** They are recorded in the ADR's
> "Corrections to the audit and plan" section — read that before assuming an item
> below was skipped:
> 1. `agent_personas.py`'s LLVM reference **kept** — it accurately describes Julia's
>    own compiler, not a claim that theFactory emits LLVM IR.
> 2. UPG-11's "strip binary claims from `docs/`" was **already satisfied** by the
>    2026-07-03 documentation audit.
> 3. UPG-13's "remove the 0.0001% figure from `docs/`" was **already satisfied**;
>    the surviving occurrences are meta-references retiring it, plus an immutable
>    evidence artifact.
>
> **One defect was found outside the plan's scope and fixed:**
> `IMPLEMENTATION_STATUS.md` documented `RQCA_ENFORCEMENT_ENABLED` as `false` /
> "Advisory by default", but `settings.py:98` and `:228` both default it to `true`
> (flipped by remediation Phase 0 and never reflected in the doc). A stale shipped
> *default* misleads operators about whether a gate blocks — corrected, along with
> two missing enforcement-flag rows.

**Closes audit items A1–A5, A11 (doc half), §6.1–§6.4.** No code executes
differently after this phase. Two small string edits to agent role text are
included because leaving them contradicts the ADR written in the same phase.

### UPG-10 — Design Reconciliation ADR

Create `docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md`. One row per design area,
each labelled exactly one of **Implemented / Superseded / Deferred**, with a
one-line rationale and the deciding evidence.

Minimum rows (from the audit's §2 scorecard): agent organisation, language
coverage, six protocols, bus-as-control-plane, message envelope, LogicNode
schema, Refined-IR, equivalence verification, LogicNode Registry, binary
synthesis, data architecture, orchestration engine, security, UI, context
isolation, pod taxonomy, LangGraph.

This is the highest-value single artifact in the plan. Everything else in
Phase 1 is downstream of it.

### UPG-11 — Formally retire binary synthesis (D2)

- Record the decision in the UPG-10 ADR (or a dedicated
  `ADR_BINARY_SYNTHESIS_RETIRED_2026-08-01.md`).
- `services/orchestrator/orchestrator/agent_registry.py` — rewrite
  `AGENT-11-DEPLOY`'s role string (currently *"Binary packaging, delivery, and
  environment setup"*, ~L151) to describe artifact packaging and export;
  rewrite `AGENT-09-HW`'s role (*"CPU/GPU optimization and hardware-specific
  mapping"*) to describe target-profile hints for generation, or mark it
  explicitly reserved.
- `services/orchestrator/orchestrator/agent_personas.py` — remove or requalify
  the LLVM reference (~L136).
- Strip "zero-dependency binary", "LLVM IR", and "machine code" claims from
  `docs/`.

**Note:** `pod-worker/toolchains.py` stays exactly as-is. It runs syntax
checkers (`py_compile`, `node --check`, `go vet`, `rustc --parse-only`,
`gcc -fsyntax-only`, `javac`, `ghc -fno-code`, `ocamlc -c`), which are
pre-flight validation and remain correct and useful. Do not confuse retiring
binary *synthesis* with removing toolchain *validation*.

### UPG-12 — Correct the unsupportable status claims

`docs/IMPLEMENTATION_STATUS.md` currently asserts "**100% feature-complete**"
and "Core Software Engine — **100% Complete** … Refined-IR … 100% operational",
while `docs/LOGICNODE_SCHEMA.md` in the same repository states the RIR
projection is "a templated/synthetic mapping rather than a deep semantic
decompilation." Replace with a scoped claim, e.g.:

> Feature-complete against the v1.3 mission-pipeline scope. Refined-IR semantic
> depth is templated for regex-extracted languages (see
> `docs/LOGICNODE_SCHEMA.md`); behavioural equivalence verification is scoped in
> `docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md`.

### UPG-13 — Retire the 0.0001% / 99.9999% claim

The figure appears throughout the design corpus (all ten of design docs 00–09)
and is **computed nowhere in the codebase**. Semantic equivalence is undecidable
for arbitrary programs; the number was never achievable. Remove it from `docs/`
and replace with what the system actually measures: contract-conformance pass
rate, runtime-QC verdict, and — after Phase 5 — behavioural equivalence-vector
pass ratio.

### UPG-14 — Design traceability matrix

Create `docs/DESIGN_TRACEABILITY.md`: one row per numbered design document
(01–64) → status (Implemented / Superseded / Deferred, matching UPG-10) →
implementing module(s) → evidence file. Sits alongside `docs/BLUEPRINT_MAP.md`,
which is a repo file map and does not serve this purpose.

### UPG-15 — Annotate the project-knowledge corpus

- Add a header block to the numbered design documents: *"Design phase, Feb–Mar
  2026. Superseded in part — see `ADR_DESIGN_RECONCILIATION_2026-08-01.md`."*
- Add a staleness note to `HGR_Gap_Report.md` listing the six items verified
  closed on 2026-08-01: Java AST extractor (real, `javalang`), JS/TS AST
  extractor (real, `esprima`), mission charter producer (exists), AIM (exists),
  agent count (41, not 38), FUSION→SQUEEZE→DELIVERY (all three run). Note that
  its §4.1–4.6 assessments remain accurate.

### Phase 1 exit criteria

| # | Criterion | Result (2026-08-01) |
|---|---|---|
| 1 | `scripts/validate_documentation.py` passes | ✅ passed — 79 metadata files, 123 link files, 17 docstring files, migration guide, 3 diagram sets |
| 2 | No document under `docs/` claims binary/LLVM output or a 0.0001% tolerance | ✅ met — surviving occurrences are confined to the six reconciliation documents, each naming the claim in order to retire it, plus `docs/evidence/word_doc_extraction_2026-03-08.json` (an immutable evidence record, excluded from the validator). No document asserts either as a capability |
| 3 | `IMPLEMENTATION_STATUS.md` and `LOGICNODE_SCHEMA.md` no longer contradict each other | ✅ met — completeness rescoped to v1.3 mission-pipeline scope; a new "Semantic depth — scoped out" row states the templated projection explicitly |
| 4 | Every audit §2 scorecard row has an ADR verdict | ✅ met — all 14 scorecard rows mapped, plus 5 additional areas from audit §4/§5 (tolerance, 14→4→1, context isolation, pod taxonomy, mission taxonomy) = 19 ADR rows |
| 5 | `ruff check` clean on the two touched `.py` files (string-only edits) | ✅ met — **one** file touched, not two (`agent_registry.py`); `agent_personas.py` was validated as should-not-change. Ruff clean; 39 registry/persona tests pass; registry loads with 41 agents intact |

---

## 5. Phase 2 — Foundation truth and cheap corrections

> **◐ PARTIAL — 2026-08-01. UPG-21, UPG-22, UPG-23 are DONE. UPG-20 is NOT
> STARTED** and requires a running stack (see below).
>
> Exit criteria 2, 3, 4, 5 met. **Criterion 1 (S1-01 evidence) is outstanding
> and remains the hard blocker for Phase 6.**
>
> **UPG-22 turned out to be a live bug, not cosmetic drift.**
> `DEFAULT_EVENT_PRIORITY` is operator-settable and was written into the event
> envelope unvalidated while the schema accepted only `NORMAL|HIGH` — so setting
> it to a lowercase bus value made *every* mission state envelope fail
> validation. Three write sites were affected; one of them
> (`phases_intake.py`) degraded silently to a warning, dropping the partition
> envelope. Fixed additively, with six regression tests proven to fail against
> pre-fix source.
>
> **One plan premise was wrong and is corrected in `docs/PROTOCOL_ENVELOPES.md`:**
> UPG-22 states the correlation contract is *"`correlation_id` carries
> `mission_id` on both paths"*. It does not, and **cannot** — the bus reuses
> `correlation_id` as both the replay-rejection key (`mcp_server.py:624`) and
> the dedup key (`:650`), so producers must send a composite
> (`delta-{mission_id}-{pod_name}`). A bare `mission_id` would make the second
> emission for a mission look like a replay and be dropped. **The transports
> join by prefix parse, never by equality** — a Phase 6 Delta consumer that
> queries by equality finds nothing and fails silently.
>
> **UPG-21's two exit criteria contradicted each other** (criterion 2 wants a
> test that fails while the flag has no consumer; criterion 5 wants a green
> suite). Resolved with `xfail(strict=True)` — green today, turns red on purpose
> the moment Phase 5 wires the flag.
>
> **UPG-23 scope note:** `pod="Pod D"` is a **routing key**
> (`mission_flow_v2/base.py:151` maps it to `podD`), not a label. Only
> descriptive strings were changed; the key is deliberately untouched.

**Closes A6 (partial), and the S1-01 gate that blocks Phase 6.**

### UPG-20 — Close S1-01 with durable evidence

S1-01 ("a live BUILD_NEW mission reaches `COMPLETE` with non-empty
`generated_code`") is still listed as an open gate in `docs/CURRENT_TODO.md`,
but it has in practice been met: `output/mission-ac933664-…/reverser.py` is 22
lines of real LLM-generated Python with three passing test functions, produced
by the Phase 13 smoke run on 2026-06-30 (`output/phase13_rebuild_smoke_latest.json`,
`"passed": true`).

Work:
- Re-run `scripts/demo_missions.py --live` on a **non-trivial** mission — a
  string reverser does not exercise the pipeline meaningfully. Use a mission
  with multiple acceptance criteria and a required artifact format.
- Commit the result as `docs/evidence/s1_01_live_generation_2026-08-XX.json`.
- Close the gate in `CURRENT_TODO.md` and reference the evidence from
  `EDCP_PHASE_PLAN.md`'s hard-prerequisites section.

**This is a hard blocker for Phase 6.** EDCP's own plan says so: *"Do not invert
control flow on a pipeline that has not yet been proven to produce real output
end to end."*

### UPG-21 — Resolve the dead equivalence flag

`mission_equivalence_python_execution_enabled` is declared at `settings.py:88`
and loaded from `MISSION_EQUIVALENCE_PYTHON_EXECUTION_ENABLED` at
`settings.py:384` — and **read nowhere else in the repository**. It is a
declared capability with no implementation behind it.

Decision: **keep it and wire it in Phase 5** (it is exactly the right gate for
execution-based equivalence). In this phase, add a regression test asserting the
setting is consumed by at least one call site, so it cannot silently rot again.
If Phase 5 slips, delete the flag rather than leave it dangling.

### UPG-22 — Unify the envelope vocabulary and document the contract

Two envelopes are in production and they disagree:

| Transport | Priority values |
|---|---|
| `schemas/event.envelope.schema.json` (Redis state events) | `NORMAL` \| `HIGH` |
| Bus `/send` body (`protocol_bus_producer.py` → `mcp_server.py`) | `low` \| `normal` \| `high` \| `critical` |

Work:
- Add `docs/PROTOCOL_ENVELOPES.md`: both schemas side by side, when each is
  used, and the explicit correlation contract (`correlation_id` carries
  `mission_id` on both paths — currently convention, not schema).
- Reconcile the priority vocabulary. Recommended: extend the event envelope
  enum to accept the four lowercase values **additively** (keep `NORMAL`/`HIGH`
  valid for backward compatibility) and normalise on write. Do not do this as a
  breaking change — `additionalProperties: false` plus a narrowed enum would
  reject in-flight events.
- Add a contract test asserting a priority value valid on one transport is
  representable on the other. `tests/services/test_envelope_schema_contract.py`
  is the natural home.

### UPG-23 — Fix the pod taxonomy drift

Pod D is labelled "Mathematical Languages" but contains MATLAB, R, Julia,
Mathematica, **Haskell, and OCaml**. Pods are uneven (A:4, B:5, C:4, D:6)
against a design that specified uniform 6-agent pods.

Recommended: **rename Pod D to "Mathematical & Functional"** rather than
creating a Pod E. Renaming touches label strings only; adding a pod touches the
registry indices, `POD_MANAGER_BY_LANGUAGE`, `SPECIALIST_BY_LANGUAGE`, compose
overlays, and the full-dedicated agent-key blocks.

Touch points: `agent_registry.py` pod strings, `agent_personas.py`,
`mission_flow.py` pod maps, Mission Control pod labels,
`deploy/docker-compose.full-dedicated-agents.yaml` group comments.

Cheap now; a correctness landmine if cross-language verification is ever added,
because "Pod D produces consistent Refined-IR" is meaningless across MATLAB and
OCaml.

### Phase 2 exit criteria

| # | Criterion | Result (2026-08-01) |
|---|---|---|
| 1 | S1-01 evidence committed under `docs/evidence/` for a multi-criterion mission | ❌ **OUTSTANDING** — requires a running stack. Still the hard blocker for Phase 6 |
| 2 | A test fails if `mission_equivalence_python_execution_enabled` has no consumer | ✅ met via `xfail(strict=True)` in `tests/services/test_equivalence_execution_flag_wiring_unit.py` — the only formulation compatible with criterion 5. Verified the detector fires when a consumer appears |
| 3 | Priority vocabularies reconciled additively; no previously-valid envelope now rejected | ✅ met — schema accepts all six values; a dedicated test asserts both legacy values still validate; writers normalise so output is byte-identical for existing configs |
| 4 | `docs/PROTOCOL_ENVELOPES.md` exists and states the correlation contract | ✅ met — and **corrects** this plan's premise about it (see the Phase 2 status block above) |
| 5 | Full backend suite green; `ruff check .` clean | ✅ met — **1768 passed, 5 skipped, 1 xfailed (by design), 0 failed**; ruff clean across `services/`, `shared_runtime/`, `tests/`; docs validation passes |

---

## 6. Phase 3 — LogicNode schema v2 (additive enrichment)

> **✅ COMPLETE — 2026-08-01.** All five exit criteria met. Full backend suite
> **1796 passed, 0 failed, 0 errors** (up from 1768 — 28 new tests).
>
> **UPG-31 was not the pure wiring the plan describes.** The plan says the data
> "already exists… This is **wiring, not new analysis**", scoped to Python,
> JS/TS, Java, Go, Haskell, OCaml, and Julia. In fact every AST extractor's
> structured output was **flattened to `FunctionInfo(name, line, signature)`**
> on entry to `ExtractionResult` — `language_extractor.py:348` discarded
> Python's `arg_types`/`return_annotation` outright, and the Java converter did
> the same to `parameters`/`return_type`. Of the seven languages named, only
> **Python** and **Java** carry structured types at all; **Haskell** has a
> parseable declared signature. Go carries `receiver`, OCaml carries
> `is_recursive`, and Julia and JS/TS carry nothing but a raw signature string —
> extracting types from those means regex-parsing signatures, which *is* new
> analysis. The three real cases were implemented; the rest stay honestly empty.
>
> Doing it required two changes the plan did not anticipate:
> 1. **`FunctionInfo` was widened additively** (`arg_types`, `return_type`, both
>    defaulted) and the converters stopped discarding AST type data.
> 2. **A concept→function correlation step**, because nodes are built per
>    *concept* while signatures are per *function*, and the two arrive as
>    sibling lists with no link. `_enclosing_function_for_line` correlates by
>    position and refuses to guess — a concept above the first function gets no
>    types, and a match is only used when the function actually carries type
>    data, so a mis-correlation cannot invent types that were never declared.
>
> **Reserved-but-unpopulated fields are deliberate.** `paradigm`, `purity`,
> `complexity`, `source_license`, and `tags` exist in the schema and are left
> absent — an absent field means "not determined", and emitting a default would
> be a false claim. `purity` in particular is Phase 4's job (UPG-41).

**Closes A8. Prerequisite for Phases 4, 5, and 7.**

### The insertion point is a single function

`services/pod-worker/pod_worker/main.py` → `_build_schema_node()` (~L265) is the
**only** place a schema node is constructed. Both other paths route through it:
`_coerce_schema_node()` (~L317, agent-pipeline nodes) and
`_logicnodes_from_extraction()` (~L394, extractor concepts). Enriching one
function enriches every node in the system.

### UPG-30 — Promote descriptive fields to first-class optional properties

Today everything descriptive lives inside the free-form `payload` blob:
`concept_id`, `concept`, `domain`, `node_name`, `source_language`,
`target_language`, and (from extraction) `confidence`, `source_line`,
`evidence`, `extraction_method`, `source_range`.

Add to `schemas/logicnode.schema.json` as **optional** top-level properties:
`domain`, `concept`, `confidence`, `source_language`, `extraction_method`,
plus new `paradigm`, `purity`, `complexity`, `source_license`, `tags`.

Rules: all optional; `additionalProperties: false` stays; `payload` keeps
carrying the same values so nothing that reads `payload.domain` today breaks;
validation stays non-fatal per `logicnode_schema.py`'s documented contract.

### UPG-31 — Populate `types.in` / `types.out` from AST signatures

`_build_schema_node` currently emits `"types": {"in": [], "out": []}` with the
comment *"Extractors do not infer I/O types yet; emit empty arrays for the
schema."*

The data already exists. `JsFunctionInfo` carries `signature`;
`JavaMethodInfo` carries `parameters`, `return_type`, `modifiers`,
`annotations`; the Python `ast` extractor has full `arg`/`annotation` access.
This is **wiring, not new analysis**.

Scope to AST-backed languages only (Python, JS/TS, Java, Go, Haskell, OCaml,
Julia). Regex-only languages keep empty arrays — and now that emptiness is
meaningful rather than universal.

### UPG-32 — Backfill and fixtures

- Update golden extraction fixtures under `tests/fixtures/extractors/`.
- Extend `tests/services/test_logicnode_schema.py` for the new optional fields
  and for a node that omits every one of them (must still validate).
- Optional migration script to backfill promoted fields on existing
  `mission_logicnodes` rows from their `payload`. Additive, idempotent, safe to
  skip.

### Phase 3 exit criteria

| # | Criterion | Result (2026-08-01) |
|---|---|---|
| 1 | A node with none of the new fields still validates (backward compatible) | ✅ met — `test_node_omitting_every_new_optional_field_still_validates` asserts the pre-UPG-30 shape explicitly. Nothing persisted in `mission_logicnodes` becomes invalid |
| 2 | Nodes from AST-backed languages carry non-empty `types.in`/`types.out` | ✅ met for **Python, Java, Haskell** — verified end to end (`add(int,int)->int`, `label(double,boolean)->String`, `applyTwice((a -> a), a) -> a`). **Not** met for Go/OCaml/Julia/JS-TS, which the plan named but whose extractors carry no type data; they stay empty by design |
| 3 | `payload` still carries every value it carries today (no reader breaks) | ✅ met — `test_build_schema_node_promotes_fields_without_emptying_payload` asserts both positions for all five promoted fields |
| 4 | Golden fixtures updated; extraction tests green | ✅ met — golden fixtures needed no change (the widening is additive and defaulted); 145 extractor/LogicNode/pod-worker tests green |
| 5 | `scripts/validate_schemas.py` passes | ✅ met — all five schemas valid |

---

## 7. Phase 4 — Real Refined-IR projection

> **✅ COMPLETE — 2026-08-01.** All six exit criteria met. Full backend suite
> **1816 passed, 0 failed, 0 errors** (up from 1796 — 20 new tests).
>
> Refined-IR is no longer "a schema-valid artifact carrying no semantic
> content". For AST-backed input it now carries real typed signatures, a real
> statement-level op stream, a purity verdict from genuine side-effect analysis,
> and executable equivalence vectors. The templated path **remains** for
> languages with no recoverable signature, tagged `templated_v1`.
>
> **Two things the plan did not account for:**
>
> 1. **`purity` needed a third value.** The plan's table implies deriving
>    `PURE`/`IMPURE` from side-effect analysis, but analysis cannot always
>    decide: a function calling something unresolvable could do anything.
>    Reporting it `PURE` would be a false claim and `IMPURE` a slander, so
>    `UNKNOWN` was added to both `rir.fn.schema.json` and the LogicNode schema.
>    **Absence of detected effects is not evidence of purity** — that rule is
>    what makes the other two values trustworthy.
> 2. **`mixed_v1` was added to `projection_method`.** The plan specifies two
>    values, but one source file legitimately mixes AST-backed and regex-only
>    extraction, and collapsing that to either extreme misreports the module.
>    Per-function `projection_method` is `templated_v1`/`ast_v1` as specified;
>    only the module-level summary can be `mixed_v1`.
>
> **UPG-42 deliberately stops short of inventing expected outputs.** Vectors
> carry concrete typed argument values but `expected: null`, because the
> expected output is not knowable until something executes the artifact.
> Fabricating one would recreate the "vector that can never fail" problem in a
> new form. Phase 5 (UPG-50) fills it by execution. Vectors are tagged
> `executable: true|false` so Phase 5 can skip what it cannot run.

**Closes A9 fully and the audit's §4.3.**

### UPG-40 — Ship the honesty field first

Add `projection_method` to `RefinedIRModule` (`pod-worker/refined_ir.py`),
values `"templated_v1"` or `"ast_v1"`. One line, outsized value: today a
downstream consumer reading a `.rir.module.json` cannot distinguish a templated
projection from a real one — the honesty exists only as prose in
`docs/LOGICNODE_SCHEMA.md`.

**Ship this even if the rest of Phase 4 slips.**

### UPG-41 — Derive real content for AST-backed languages

Replace the templated derivations in `build_refined_ir_module()`:

| Field | Today | After |
|---|---|---|
| `purity` | `"IMPURE" if payload.get("intent") else "PURE"` | Side-effect analysis: global/nonlocal assignment, I/O calls, mutation of arguments |
| `inputs` | always `[{name: "source", type: <source_language>}]` | Real parameter names and types from Phase 2's `types.in` |
| `outputs` | always `[{name: "intent", type: <target_language>}]` | Real return type from `types.out` |
| `ops` | always one `EXTRACT_CONCEPT` | Statement/expression sequence from the AST |
| `effects` | `["logicnode_recorded"] if confidence < 1` | Detected I/O, network, filesystem, and global-state effects |
| `preconditions` | `["mission payload available"]` | Argument constraints where inferable (non-null, type guards) |

The templated path **remains** as the fallback for regex-only languages, tagged
`templated_v1`. This is the pragmatic-middle boundary: real semantics where the
AST work is already done, honest templating everywhere else.

### UPG-42 — Generate real equivalence vectors

Today `tests.equivalence_vectors` restates the node's own identifiers
(`{"in": {"node_id":…, "source_language":…}, "out": {"concept":…, "domain":…}}`)
— it can never fail. Replace with vectors derived from the real signature:
argument values matching inferred types, plus an LLM-proposed set of edge cases
(empty, boundary, negative) validated against the schema before being written.

These vectors are the input Phase 5 executes. Without this step Phase 5 has
nothing meaningful to run.

### UPG-43 — Populate the RIR catalog

`artifacts/refined-ir/index.json` is currently `{"artifacts": []}` while signed
RIR modules are being written to disk per mission.
`scripts/build_refined_ir_catalog.py` exists. Wire it into the mission path or a
scheduled task so the catalog reflects reality.

### Phase 4 exit criteria

| # | Criterion | Result (2026-08-01) |
|---|---|---|
| 1 | Every `.rir.module.json` carries `projection_method` | ✅ met — at module level (`templated_v1`/`ast_v1`/`mixed_v1`) and per function. Optional in the schema, so modules written before UPG-40 stay valid |
| 2 | For a Python input, `fns[].ops` has more than one op and `inputs` matches the real signature | ✅ met — a 2-branch function yields `ASSIGN, BRANCH, ASSIGN, ASSIGN, LOOP, ASSIGN, RETURN` (7 ops) against the previous single synthetic `EXTRACT_CONCEPT`; `inputs` are the real `(float, float) -> str` |
| 3 | `purity` differs across a pure and an impure function in the same module | ✅ met — `classify` → `PURE` with `effects: []`, `persist` → `IMPURE` with `effects: ["io.filesystem"]`. Previously purity was `"IMPURE" if payload.get("intent") else "PURE"` |
| 4 | Equivalence vectors contain real argument values, not identifier restatements | ✅ met — three cases (nominal/boundary_low/boundary_high) of concrete typed args. `expected` is `null` by design; see the status block above |
| 5 | Golden fixture locks an `ast_v1` module; `test_refined_ir_unit.py` and `test_fusion_rir_verify.py` green | ✅ met — `test_golden_ast_v1_projection_shape_is_locked` locks the projection's shape and derivation; both named suites pass **unchanged** |
| 6 | `artifacts/refined-ir/index.json` non-empty after a mission | ✅ met — the catalog is now upserted atomically on every module write, keyed by path so a re-run replaces rather than duplicates. The record shape is shared with `scripts/build_refined_ir_catalog.py` so a rebuild and an incremental update cannot drift |

---

## 8. Phase 5 — Behavioural equivalence verification

**Closes A4's engineering half. This is the phase that earns the word
"verification."**

### UPG-50 — Execution harness, built on RQCA

Create `services/orchestrator/orchestrator/equivalence_execution.py`.

**Reuse, do not rebuild.** `rqca_agent.py` already has a hardened Docker
sandbox: `_EXECUTABLE_LANGUAGES` (python, javascript, typescript),
`_COMPILED_LANGUAGE_CONFIG` (gcc, g++, rustc, dotnet-script images with
compile-and-run templates), `_MAX_TIMEOUT_SECONDS = 60`, `_MAX_MEMORY_MB = 512`,
and `_check_docker_available()`. The invocation at `rqca_agent.py:649-661`
already passes `--network=none --read-only --cap-drop=ALL --memory-swap=0
--cpus=1 --security-opt=no-new-privileges:true --tmpfs=/tmp:size=64m` with a
read-only `/workspace` mount. Extract that invocation core into a shared helper
rather than duplicating it — a second, less-hardened execution path is the most
likely way this plan introduces a real vulnerability.

Behaviour: for each `tests.equivalence_vectors` entry in the mission's RIR,
invoke the generated artifact with the vector's `in` values in the sandbox and
compare the result to `out`. Record passed/total.

### UPG-51 — Wire the dead flag

Gate the new path on `mission_equivalence_python_execution_enabled`
(`settings.py:88`) — the flag identified as dead in UPG-21. Start Python-only,
then extend across `_EXECUTABLE_LANGUAGES`. Default stays `false`.

### UPG-52 — Extend the equivalence report

`equivalence_verifier.py` currently emits `"verification_scope": "correctness"`
with seven contract-conformance checks. Keep all of them. Add:

- a second report section with `"verification_scope": "behavioural"`
- `equivalence_vectors_passed` / `equivalence_vectors_total`
- per-vector failure detail in `findings`

Surface both scopes in Mission Control's `EquivalenceReportPanel.tsx`.

### UPG-53 — Measure before enforcing

`mission_equivalence_enforcement_enabled` stays `false` until behavioural pass
rates have been observed across at least 20 real missions. Enforcing an
unmeasured gate is how you teach operators to disable gates.

### Phase 5 exit criteria

| # | Criterion |
|---|---|
| 1 | Flag off ⇒ equivalence report byte-identical to today |
| 2 | Flag on ⇒ a Python BUILD_NEW mission reports a real behavioural pass ratio |
| 3 | A deliberately wrong artifact fails at least one vector (the gate can actually fail) |
| 4 | Sandbox timeout/OOM is a vector failure, never a mission crash |
| 5 | No second Docker execution path exists — RQCA's harness is shared |
| 6 | Both scopes visible in Mission Control |

---

## 9. Phase 6 — Make the Protocol Bus load-bearing (EDCP)

**Closes A7 and D3.** Execute `docs/EDCP_PHASE_PLAN.md` as written. Hard
prerequisite: **UPG-20 (S1-01)**.

### One inserted sub-phase: EDCP-02a — Delta consumer as the pod-audit gate

The existing plan starts inversion at the PM→CEO Omega seam (EDCP-02). Insert a
cheaper proof before it.

**Why Delta first.** It already has two live producer call sites
(`phases_build.py:250` and `:816`, both inside the `MISSION_POD_AUDIT_COMPLETE`
idempotency guard), it carries a natural pass/fail semantic
(`audit_result: pass|fail|warning`, `tolerance_score`), and its natural gate
already exists in `lifecycle.py:_advance_verified_to_complete` alongside the
security-compliance, dependency-absorption, and runtime-QC gates. Adding a Delta
handler to `main.py`'s `handlers` dict — today `{"sigma": _handle_sigma_knowledge_ready}`
— and letting a consumed `fail` verdict block completion is the smallest
possible change that makes a lane genuinely load-bearing.

It also directly proves EDCP exit criterion 3 (*"with the consumer down, the
mission does not silently complete"*) on a seam where failure is recoverable,
before betting the PM→CEO handoff on it.

**Then proceed as written:** EDCP-02 (PM→CEO Omega), EDCP-03a/b (CEO→pod
manager, crosses into pod-worker), EDCP-04 (support ring on Alpha/Delta),
EDCP-05.

**Out of scope for this plan:** Stage 3 (Agent Runtime Split) and Stage 4
(Semantic Bus) from `PROTOCOL_BUS_PROGRAM_ROADMAP.md`. Both remain stubs and
correctly depend on EDCP completing first.

### Phase 6 exit criteria

Per `EDCP_PHASE_PLAN.md`'s own per-phase tables, plus:

| # | Criterion |
|---|---|
| 1 | At least one lane where suppressing the consumer measurably blocks a mission |
| 2 | `protocol_bus_producer.py`'s "fire-and-forget telemetry" docstring updated for lanes that are no longer fire-and-forget |
| 3 | `PROTOCOL_BUS_PROGRAM_ROADMAP.md` Stage 2 status advanced from "EDCP-01 complete" |

---

## 10. Phase 7 — Consolidation

### UPG-70 — LogicNode dependency graph (Doc 15 §3.1)

No graph library exists in Mission Control today. Now that Phase 3 gives nodes
real typed relationships, the visualisation has data to render. Choose a library
compatible with the CSP work deferred from
`FULL_APP_REMEDIATION_PLAN_2026-07-05.md` Phase 5 — avoid anything requiring
`unsafe-inline` or `unsafe-eval`.

### UPG-71 — Decide LangGraph's fate

`langgraph_enabled = False`, `langgraph_checkpointer = "none"`. Design Doc 14
(678 lines) is entirely about LangGraph per-agent state machines that were never
written. Either enable and prove it, or mark Doc 14 superseded by
`mission_flow_v2/transitions.py` and remove the disabled second engine. Carrying
both indefinitely costs test surface and reader confusion. Recommended: mark
superseded — the hand-rolled machine is clean, tested, and recovers correctly.

### UPG-72 — Specify the mission taxonomy retroactively

`models.py` defines 10 `MissionType`, 5 `DepthMode`, 8 `OutputMode`, and 4
`DataClassification` values. **None appears in any design document.** This is the
product's actual commercial surface and the largest unwritten specification in
the system. Write `docs/MISSION_TAXONOMY.md` — semantics of each value, valid
combinations, which phases each triggers — before adding an eleventh mission type.

### UPG-73 — Formally defer the LogicNode Registry (Doc 30)

Doc 30 (1,635 lines: registry tables, versioning, Milvus collection, semantic
clustering, query API) is the largest unimplemented specification in the corpus.
It is only valuable once RIR carries real cross-mission semantics. Record it as
**Deferred** in the UPG-10 ADR, with an explicit revisit trigger: *"reconsider
once Phase 4 `ast_v1` projections cover a majority of missions."* Do not leave
it as apparent scope.

---

## 11. Explicit non-goals

Stating these prevents the plan from silently re-growing:

- **Parallel four-pod fan-out and cross-language Tier-3 verification.** Per D1.
- **Zero-dependency binary synthesis, LLVM, compilation to machine code.** Per D2.
- **The 0.0001% / 99.9999% equivalence tolerance.** Retired in UPG-13.
- **The LogicNode Registry (Doc 30).** Deferred in UPG-73.
- **Per-agent LLM API key isolation** (audit §4.9). The `AGENT_NN_*_SERVICE_API_KEY`
  control-plane keys stay as they are; per-agent *provider* credentials are not
  worth the operational cost at single-operator scale. Cost attribution is
  already recovered by `llm_cost_ledger.py`. Record as Superseded in UPG-10.
- **Agent Runtime Split and Semantic Bus** (bus roadmap Stages 3–4).
- **Deep RIR for regex-only languages.** They stay `templated_v1`, honestly labelled.

---

## 12. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Phase 3 schema change breaks a `payload.*` reader | Medium | `payload` keeps carrying every value it carries today; new fields are duplicates, not moves. Contract test asserts both paths. |
| Phase 4 AST derivation is slower than templating | Medium | Extraction is already the fast half of a mission dominated by LLM latency. Measure with `pod_worker_task_latency_seconds` before and after. |
| Phase 5 sandbox execution runs untrusted generated code | **High impact** | Reuse RQCA's verified constraints — `--network=none`, `--read-only`, `--cap-drop=ALL`, `--memory-swap=0`, `--cpus=1`, no-new-privileges, 64 MB tmpfs, read-only `/workspace`, 60 s timeout, 512 MB. Do not relax them. Treat every equivalence vector as hostile input. |
| Phase 6 EDCP debugging difficulty | Medium | Strangler pattern and single flag are already the plan's design. Do not run Phase 6 concurrently with Phases 3–5 unless there is capacity to isolate failures. |
| Phase 1 doc edits break `validate_documentation.py` | Low | Run it as the phase gate, not after. |
| Plan re-grows to include the retired design | Medium | §11 exists for exactly this. Any addition needs an ADR amendment. |

---

## 13. Effort shape

Not calendar estimates — relative weight, for sequencing only.

| Phase | Weight | Can run in parallel with |
|---|---|---|
| **1 — Docs / truth reconciliation** | **S** | Anything |
| **2 — Foundation** | **S** | Phase 1 |
| **3 — LogicNode v2** | **M** | Phase 6 |
| **4 — Real RIR** | **L** | Phase 6 |
| **5 — Behavioural equivalence** | **L** | Phase 6 |
| **6 — EDCP** | **L** | Phases 3–5 (capacity permitting) |
| **7 — Consolidation** | **M** | — |

The two smallest phases (1 and 2) remove the majority of the reputational and
correctness risk identified in the audit. If only one thing gets done, do
**Phase 1**.

---

## 14. What stays exactly as it is

Recorded so no phase quietly erodes it:

the 41-agent registry and its `runtime_class` honesty · the Protocol Bus
hardening (dedup, replay rejection, backpressure, DLQ, per-agent HMAC, prod
fail-fast) · the immutable audit migrations (V008/V009) · dual-mode auth and the
ADR behind it · `prompt_guard.py` and `pii_guard.py` · ECDSA artifact signing ·
HMAC-signed approval gates · the AST extractors and their golden fixtures ·
`toolchains.py` syntax checking · dependency absorption, TESTDATA, and RQCA ·
the mission taxonomy itself · Mission Control's 15 routes, accessibility wiring,
and Playwright suite · compose hardening · SBOM, Bandit, pip-audit, and the
promotion gate · Electron packaging · and the feature-flag discipline that makes
all of the above safe to extend.
