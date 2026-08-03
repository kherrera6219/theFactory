# theFactory — Design vs. Build Audit

Document version: 2026.08.01
Last updated: 2026-08-01
Status: Canonical
Audience: Maintainers, architects, operators, and AI coding agents

**Subject:** `C:\software\Holygrail\theFactory` (the built application) compared to the Holy Grail Refinery design corpus in the *holy grail* project knowledge
**Date:** 1 August 2026
**Method:** Read-only. 143 design documents reviewed (115 `.md`, 27 `.txt`, plus notes); live source read directly under `services/`, `shared_runtime/`, `schemas/`, `protocol/`, `apps/mission-control/`, `deploy/`, `tests/`. **Nothing in the application was changed.**
**Governing rule applied:** code is the source of truth. Every claim below cites a file that was actually opened.

**What to do about it:** `docs/UPGRADE_RECONCILIATION_PLAN_2026-08-01.md` is
the ordered execution plan that closes every finding in this report. Start at
its §0 (Cold start).

---

## 1. Executive Summary

The build is a **stronger production system than the design ever specified, and a weaker semantic engine than the design promised.**

Everything the design treated as supporting infrastructure — the agent registry, the protocol bus, the data plane, security, containerisation, observability, CI/CD, the operator UI — exists, is hardened well past the specification, and in several areas is genuinely enterprise-grade. Several whole capability areas exist that appear nowhere in the design at all (mission taxonomy, dependency absorption, runtime QC, desktop packaging, cryptographic chain-of-custody).

What was *not* built is the thing the design was actually about: the **14 → 4 → 1 comprehension model**. There is no parallel four-pod extraction, no cross-language fusion, no semantic Refined-IR, no equivalence verification at 0.0001% tolerance, and no binary synthesis. A mission today routes to **one pod and one specialist**, selected by the requested target language, and produces **source code**, not a zero-dependency binary.

This is not a criticism of the build so much as an observation that **the product silently changed category** — from "smelt many languages into one verified logic stream" to "governed, evidence-producing, multi-agent code generation and modernisation platform." The application's own `docs/WHAT_THEFACTORY_IS_AND_IS_NOT.md` already describes the second product honestly. The design corpus still describes the first. The single largest risk in the repository right now is not a bug — it is that **two mutually contradictory specifications are both marked canonical**, and neither one has been formally retired.

**Headline verdict by weight:**

| | |
|---|---|
| Design areas fully or better-than met | 9 of 14 |
| Design areas materially diverged | 5 of 14 |
| Capabilities built beyond design | 8 significant |
| Design promises with **zero** implementation | 3 (binary synthesis, formal equivalence, LogicNode registry) |

---

## 2. Scorecard

| # | Design area | Design source | Built state | Verdict |
|---|---|---|---|---|
| 1 | Agent organisation & tiers | Doc 05 §2, Doc 06 | 41 agents, exact tier/pod/naming scheme | **Better** |
| 2 | Language coverage | Doc 05 §1.1 (14 languages) | 19 specialists / 19 routed language keys | **Better** |
| 3 | Six communication protocols | Doc 07 | All six typed and validated on a hardened bus | **Right** |
| 4 | Bus as control plane | Doc 07 §1.2, Mission Flow v2 | Producers on all 6 lanes; **1 consumer**; fire-and-forget | **Worse** |
| 5 | Message envelope | Doc 07 §2 | Two envelope formats, neither matching the design | **Worse** |
| 6 | LogicNode schema | Doc 09 §2 (30 fields) | 7-field envelope | **Worse** |
| 7 | Refined-IR | Doc 09 | Schema real; projection is templated/synthetic | **Worse** |
| 8 | Equivalence verification | Doc 09 §8, Doc 30 §4 | Contract-conformance checks only; off by default | **Worse** |
| 9 | LogicNode Registry | Doc 30 | Per-mission JSONB table only; no registry/clustering | **Missing** |
| 10 | Binary / LLVM output | Doc 01 §1.2, Doc 05 | Not implemented anywhere | **Missing** |
| 11 | Data architecture | Doc 08 | All five stores mapped onto real engines | **Right** |
| 12 | Orchestration engine | Doc 14 (LangGraph) | Custom transition table; LangGraph off by default | **Diverged** |
| 13 | Security & hardening | Doc 26 | Dual-mode auth, HMAC, vault, immutable audit, signing | **Better** |
| 14 | Mission Control UI | Doc 15 | 15 pages, exceeds spec; one visualisation gap | **Better** |

---

## 3. What Is Right — Design Honoured or Exceeded

### 3.1 Agent organisation — exact structural fidelity, extended

`services/orchestrator/orchestrator/agent_registry.py` is a near-literal implementation of Doc 06's tier model, and then some.

| | Design (Doc 05 §2.1) | Built (`agent_registry.py`) |
|---|---|---|
| User Interface | 1 (PM) | 1 — `AGENT-01-PM` |
| Executive | 1 (CEO) | 1 — `AGENT-02-CEO` |
| Support Ring | 9 | **12** (adds DEPABS, TESTDATA, RQCA) |
| Pod core | 24 (4 mgr + 4 audit + 16 spec) | **27** (4 mgr + 4 audit + **19** spec) |
| **Total** | **35** | **41** |

The `AGENT-NN-CODE` naming convention, the tier labels, the pod labels, and the sub-manager/auditor/specialist triad all match the specification exactly. The registry also carries something the design never asked for and that turns out to be essential honesty: a `runtime_class` field distinguishing **27 `shared_worker`** agents (real processes) from **14 `synthesized_heartbeat`** agents (interface, executive, and all support-ring roles — logical agents with no container). That is a mature piece of self-documentation.

### 3.2 Language coverage exceeds the design by five

Design specified 14 languages across four pods. `LANGUAGE_ALIASES` in `agent_registry.py` normalises to **19** distinct keys: python, javascript, ruby, php, c, cpp, rust, zig, go, java, csharp, scala, kotlin, matlab, r, julia, mathematica, haskell, ocaml. Go, Haskell, and OCaml are net-new; TypeScript aliases onto javascript.

### 3.3 The Protocol Bus is the single best-executed component

`services/protocol-bus-mcp/protocol_bus/mcp_server.py` (726 lines) implements all six lanes from Doc 07 as a standalone FastAPI microservice with strict per-protocol Pydantic payloads (`AlphaPayload`, `BetaPayload`, `DeltaPayload`, `SigmaPayload`, …, all `extra="forbid", strict=True`). Beyond the design it adds:

- API-key auth via `hmac.compare_digest`, with a **production fail-fast** if `MCP_API_KEY` is unset
- `X-Agent-Id` header binding, enforced equal to the envelope `sender`, validated against `^AGENT-\d{2}-[A-Z0-9-]+$`
- Opt-in **per-agent HMAC message signing** (`AGENT_HMAC_SIGNING_ENABLED`, per-agent secrets, max-age replay window)
- Correlation-ID **deduplication** with configurable TTL, **replay** rejection, **backpressure** returning 503 above a 10,000-message queue depth, per-stream **DLQ**, message TTL and `XTRIM` pruning
- Prometheus counters for queued / DLQ / deduplicated / replayed messages

Doc 07 §1.2 asked for "Redis Pub/Sub + Streams" with "at-least-once delivery." What was built is materially more rigorous.

### 3.4 Data architecture — all five designed stores exist on real engines

| Doc 08 store | Built |
|---|---|
| Semantic Knowledge Lake | Qdrant + Milvus (`qdrant_store.py`, `milvus_store.py`, `knowledge_lake.py`) |
| Global State Graph | PostgreSQL `missions` / `mission_state_events` + Neo4j mirror (`neo4j_store.py`) |
| LogicNode Registry | PostgreSQL `mission_logicnodes` (JSONB) — *reduced, see §4.5* |
| Traceability Ledger | PostgreSQL migrations V001–V009 + on-disk signed RIR modules |
| Model & Data Store | `llm_usage_events`, `llm_cost_ledger.py`, MinIO object store |

`V009_immutable_audit.sql` goes beyond the design: it revokes `DELETE` on `mission_audit_reports`, `agent_action_events` and `llm_usage_events` from the application role, with retention handled by a `SECURITY DEFINER` prune function. That is a real tamper-evidence control, not a checkbox.

### 3.5 Security exceeds Doc 26 in every dimension that matters

Doc 26 specified JWT + RBAC + TLS + container hardening. Built:

- **Dual-mode auth** (`api_key` / `hybrid` / `oidc`) per `docs/ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md` — a better decision than the design's JWT-only assumption for a local-first product
- `shared_runtime/prompt_guard.py` (OWASP LLM01 injection detection, block level configurable, **default enabled**), `pii_guard.py` (SSN/PAN/email/phone/JWT/API-key redaction)
- `shared_runtime/crypto_signing.py` — ECDSA signing of RIR modules and build artifacts
- Agent-scoped control-plane keys with `shared` / `strict` modes (`docs/AGENT_SERVICE_KEY_ISOLATION.md`)
- Compose hardening applied service-wide: `no-new-privileges`, `cap_drop: ALL`, `read_only` + tmpfs, oom score tuning, TLS for Redis and Postgres
- Production guards that raise `RuntimeError` rather than warn — for `GATEWAY_ADMIN_BYPASS`, CORS wildcards, default MinIO credentials, and unset `SERVICE_API_KEY`

### 3.6 Mission Control UI meets and exceeds Doc 15

Doc 15 specified a dashboard, agent status grid, mission timeline, LogicNode explorer, semantic bus monitor, performance panel, alerts, settings, responsive breakpoints, and WCAG 2.1 AA. Built (`apps/mission-control/app/(shell)/`): **agents, alerts, audit, builder, chat, dashboard, databases, history, logic-nodes, logicnodes, missions (+ detail/history/output), performance, projects, protocol-bus, repo, repo-import, settings** — 15+ routes. Accessibility is wired with `axe-core` and Lighthouse CI (`lighthouserc.json`), and there is an `ACCESSIBILITY_STATEMENT.md`. Playwright E2E specs cover seven mission scenarios plus Electron.

### 3.7 Testing and CI/CD comfortably meet Docs 23 and 41–50

~130 pytest files under `tests/` spanning unit, integration, security (`test_state_mutation_auth.py`, `test_pod_assignment_conflict.py`), golden-fixture extraction locks, prompt-safety evals (`tests/eval/`), a Locust load profile, and script-level tests. Mission Control adds Vitest units and Playwright E2E. CI adds SBOM (SPDX + CycloneDX), Bandit, pip-audit, GPL/AGPL license blocking, and a fail-closed promotion gate — all beyond Doc 24.

---

## 4. What Is Wrong — Material Divergence

These are ordered by architectural consequence, not by effort to fix.

### 4.1 🔴 The 14 → 4 → 1 comprehension model is not implemented

**Design:** Doc 05 §1.1 and `HGR_Mission_Flow_v2.md` are explicit — all four language pods run **in parallel** during extraction; all four QC/Audit agents gate independently; sub-managers perform Tier-3 cross-language verification by receiving four language implementations of the same concept and confirming they produce identical Refined-IR; the CEO then fuses four pod streams into one Master Logic Stream.

**Built:** `mission_flow_v2/phases_build.py:328+` resolves exactly one pod manager and one specialist:

```python
pod_manager_agent_id = _validate_agent_id(..., fallback=resolve_pod_manager_agent_id(mission.requested_target_language))
specialist_agent_id  = _validate_agent_id(..., fallback=resolve_specialist_agent_id(mission.requested_target_language))
```

`_prepare_gating` then produces a group standard for `pod_name = _pod_key_for_manager(pod_manager_agent_id)` — a single pod. There is no fan-out across pods, no cross-language comparison, and consequently no fusion in the designed sense. The four-pod structure survives as **routing metadata**, not as a parallel execution topology.

**Better or worse:** Worse against the design; arguably correct against reality. Running four pods over the same concept to prove semantic identity only pays for itself if you have real semantic IR to compare (see §4.3). Without it, four-pod fan-out would multiply LLM cost for no verification gain. The build made a defensible engineering call — but it made it silently, and the design was never updated to record it.

### 4.2 🔴 The LogicNode shrank from a semantic node to a work envelope

**Design (Doc 09 §2.1):** ~30 fields — `paradigm`, `domain`, `concept`, `intent`, structured `InputSpec[]`/`OutputSpec[]`, `preconditions`/`postconditions` as typed `Constraint[]`, `side_effects: SideEffect[]`, `source_license`, `confidence`, `audit_status`, `audit_agent`, `equivalence_tests_passed`/`_total`, `verification_tolerance`, `complexity`, `purity`, `tags`.

**Built (`schemas/logicnode.schema.json`, 88 lines):** seven required fields — `node_id`, `cmd`, `payload` (unconstrained object), `priority`, `intent`, `types` (`{in: [string], out: [string]}` — plain names, not typed specs), `provenance`.

Everything the design put in first-class, queryable, verifiable positions now lives — if at all — inside the free-form `payload` blob. Validation is deliberately **non-fatal** (`logicnode_schema.py`: "a node that fails the schema is logged and reported back to the caller so extraction is not aborted wholesale").

**Consequence:** The universal type system (Doc 09 §3), constraint system (§4), side-effect system (§5), and composition/dependency-graph model (§7) have no representation in the persisted artifact. They cannot be added later without a schema migration and a re-extraction of every stored node.

### 4.3 🔴 Refined-IR is a templated projection, not a semantic extraction

The RIR **schema** (`schemas/rir.fn.schema.json`, `pod-worker/refined_ir.py`) is faithful to Doc 09 — purity, typed inputs/outputs, pre/postconditions, an op stream, equivalence vectors, sources and chain-of-custody. The **producer** is not. From `build_refined_ir_module()`:

```python
purity        = "IMPURE" if payload.get("intent") else "PURE",
inputs        = [RefinedIRParameter(name="source", type=source_language or "unknown")],
outputs       = [RefinedIRParameter(name="intent", type=target_language or ...)],
preconditions = ["mission payload available"],
ops           = [RefinedIROperation(op_id=f"{node_id}:extract", opcode="EXTRACT_CONCEPT", args=[domain, concept], out="intent")],
tests         = ...equivalence_vectors=[{"in": {"node_id":…, "source_language":…}, "out": {"concept":…, "domain":…}}]
```

Every function gets exactly one op, `EXTRACT_CONCEPT`. Purity is derived from whether a string is truthy. The "equivalence vector" restates the node's own identifiers. This is a **schema-valid artifact carrying no semantic content** — a well-formed empty envelope. The repository's own `docs/LOGICNODE_SCHEMA.md` says so plainly ("the projection itself is currently a templated/synthetic mapping rather than a deep semantic decompilation"), which is to the project's credit, but it does mean the central technical claim of the design is unbacked.

### 4.4 🔴 "Equivalence verification" means something entirely different than designed

**Design:** Doc 09 §8 and Doc 30 §4 specify a sandboxed multi-language **execution** engine running randomised input vectors — 1,000 simulations at 0.0001% tolerance — plus formal verification where tractable. `HGR_Mission_Flow_v2.md` layers three QA tiers on top (specialist self-check at >0.90 confidence, auditor formal verification, sub-manager cross-language equivalence).

**Built (`equivalence_verifier.py`, 693 lines):** a **contract-conformance** checker. Its seven checks are: generated output exists, a build artifact exists, artifact format matches the contract ("single HTML file" → `.html`), declared language matches request, content doesn't look like a Python fallback (regex signature heuristics), acceptance criteria keywords appear, AIM consistency. Its own header is candid: `"verification_scope": "correctness"` — meaning *does the artifact match the contract*, not *does it behave identically to a reference*.

Defaults compound this: `mission_equivalence_enforcement_enabled = False` and `mission_equivalence_python_execution_enabled = False` (`settings.py:87`). Pod audit is an LLM opinion (`generate_pod_audit_verdict`), and specialist confidence is hardcoded — `0.85 if generated_output.get("source") == "llm" else 0.3` (`phases_build.py`).

**Net:** none of the three designed QA tiers exists in the designed form. The 0.0001% tolerance figure, which appears in **every one of the first ten numbered design documents**, is not computed anywhere in the codebase.

### 4.5 🟠 The LogicNode Registry (Doc 30) was never built

Doc 30 (1,635 lines) specifies `logicnodes` + version + cluster tables, a Milvus collection with defined index/search parameters, a semantic clustering engine, an equivalence-test execution engine, and a query/search API. Built: a single `mission_logicnodes (mission_id, node_id, node_json JSONB)` table, **scoped per mission**, with a Neo4j mirror. There is no cross-mission registry, no versioning, no clustering, no dedupe, no semantic search over nodes. Doc 30 is the largest single specification in the corpus with the smallest realised footprint.

### 4.6 🟠 Binary synthesis does not exist

Doc 01 §1.3 promises "zero dependencies (smelted into core logic)"; Doc 05 and Doc 09 §1.3 terminate the pipeline at "Optimized Binary (LLVM IR → machine code)". A repository-wide search for `llvm|binary|compile_to|machine code` across all Python in `services/` returns **three** hits — one comment in `toolchains.py`, one role description in `agent_registry.py` (`AGENT-11-DEPLOY`, "Binary packaging"), one persona string mentioning LLVM in `agent_personas.py`. No compilation stage, no LLVM, no linking.

`toolchains.py` runs **syntax checkers** (`py_compile`, `node --check`, `go vet`, `rustc --parse-only`, `gcc -fsyntax-only`, `javac`, `ghc -fno-code`, `ocamlc -c`) — pre-flight validation, not build. `AGENT-09-HW`, the Hardware-Mapping Injector whose entire design purpose was platform-specific binary optimisation, is a `synthesized_heartbeat` with no compilation role. Outputs are source files and gzipped bundles (`build_artifacts.py`, `deploy_exporter.py`).

### 4.7 🟠 The bus emits but does not command

Since the earlier lane-activation work, **all six lanes now have live producers** — verified:

| Lane | Producer call site |
|---|---|
| Alpha | `mission_flow_v2/phases_build.py:190` |
| Beta | `phases_build.py` (primary) + `phases_runtime.py:513` (fallback) |
| Delta | `phases_build.py:250`, `:816` |
| Sigma | `knowledge_lake.py:broadcast_knowledge_ready` |
| Omega | `phases_delivery.py:67` |
| Rho | `llm_delegation/providers.py:168` |

That is real progress and closes the plan recorded in project memory. But there is exactly **one consumer handler** in the entire application — `main.py:_handle_sigma_knowledge_ready` — and it only re-checks Postgres and logs. Every producer is explicitly fire-and-forget:

> *"Sends remain non-raising by default… callers can treat this as fire-and-forget telemetry."* — `protocol_bus_producer.py` module docstring

`EVENT_DRIVEN_CONTROL_PLANE_ENABLED = False` (`settings.py:127`); the pipeline runs as a synchronous in-process loop through `mission_flow_v2/lifecycle.py`. Doc 07's premise — "agents do not poll, they subscribe and activate when their trigger fires" — is not how the system executes. The bus is a very well-built **observability spine** wearing a control-plane's clothes.

### 4.8 🟠 Three incompatible message envelopes

| Source | Fields | Priority values |
|---|---|---|
| **Doc 07 §2** | `protocol`, `message_id`, `timestamp`, `sender_id`, `recipients`, `correlation_id`, `priority`, `ttl`, `payload`, `metadata{mission_id, retry_count, trace_id}` | `low\|normal\|high\|critical` |
| `schemas/event.envelope.schema.json` | `event_id`, `topic`, `timestamp`, `producer`, `correlation_id`, `payload_ref`, `schema`, `priority` — `additionalProperties: false` | **`NORMAL\|HIGH` only** |
| Bus `/send` body (`protocol_bus_producer.py`) | `schema_version`, `protocol`, `sender`, `recipient`, `correlation_id`, `priority`, `payload` | `low\|normal\|high\|critical` |

Neither implemented envelope matches the design, and **the two implemented envelopes disagree with each other** on both field names and priority vocabulary (uppercase two-value vs lowercase four-value). Design fields with no home anywhere: `ttl`, `metadata.mission_id`, `metadata.retry_count`, `metadata.trace_id`. Correlation across the two transports currently depends on convention, not schema.

### 4.9 🟠 Context isolation was never implemented as designed

Doc 05's **first** architectural principle: *"Each agent operates in a physically isolated context with its own API key and 1M-token window."*

Reality (`llm_delegation/config.py`): one key per **provider** — `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` — resolved globally, with optional vault override via a `ContextVar`. The `AGENT_NN_CODE_SERVICE_API_KEY` family is real and well-designed, but it authenticates **worker→orchestrator control-plane mutations**, not LLM calls; it delivers no context isolation, no per-agent quota, and no blast-radius containment on provider credentials. Agent identity is a persona string plus a prompt (`agent_personas.py`), and 14 of 41 agents have no runtime at all.

The design's stated benefits of isolation — per-agent rate limiting, independent key rotation, cost attribution per agent — are partially recovered by the cost ledger (`llm_cost_ledger.py` attributes usage to `agent_id`), but the isolation property itself does not exist.

### 4.10 🟡 LangGraph: the orchestration design document describes an optional, disabled path

Doc 14 (678 lines) is entirely about LangGraph — per-agent state machines for the executive tier, support ring, and pods; `StateGraph` node/edge definitions; checkpoint-based recovery. Built: `langgraph_enabled: bool = False`, `langgraph_checkpointer: str = "none"`. The live engine is a hand-rolled transition table (`mission_flow_v2/transitions.py`, 109 lines) with **one mission-level** state machine — `V2_TRANSITIONS`, 10 edges, `QUEUED → PM_INTAKE → FETCH → CEO_DELEGATED → POD_ASSIGNED → SPECIALIST_ASSIGNED → RUNNING → GATING → FUSION → VERIFIED → COMPLETE`.

The mission-level machine is clean, tested, has a v1↔v2 compatibility mapping, and recovers in-flight missions on restart. But **per-agent state machines do not exist**, so roughly 80% of Doc 14 describes code that was never written.

### 4.11 🟡 Pod taxonomy drift

Design Pod D is "Mathematical Languages" (MATLAB, R, Julia, Mathematica). Built Pod D also contains **Haskell** and **OCaml** — functional languages, not mathematical ones — apparently because Pod D was the least-full bucket. Go sits in Pod B (systems), while `HolyGrail_Design_Checklist.md` places Go in Pod C. Pods are now uneven (A: 4 specialists, B: 5, C: 4, D: 6) against a design that specified a uniform 6-agent pod.

Minor today because pods are only routing labels — but it becomes a real correctness problem the moment pod-level fusion or cross-language verification is implemented, because "Pod D produces consistent Refined-IR" is a meaningless assertion across MATLAB and OCaml.

### 4.12 🟡 UI: no LogicNode dependency graph

Doc 15 §3.1 specifies an interactive dependency graph for the LogicNode Explorer. A search across `apps/mission-control/app/**/*.tsx` for `d3|cytoscape|reactflow|force` returns no graph library — matches are the word "force" inside unrelated copy and "Graph" in Neo4j status labels. The `logicnodes` page lists nodes; it does not visualise the dependency structure Doc 09 §7 defines. Given §4.2, there is currently no dependency data to draw — the two gaps are the same gap.

---

## 5. What Was Built That Was Never Designed

These are strengths, and they are the reason the divergence in §4 is defensible. They should be **written into the specification**, not left as undocumented surplus.

1. **Mission taxonomy.** `models.py` defines 10 `MissionType` values (BUILD_NEW, IMPORT_MODERNIZE, PORT, DEBUG_REPAIR, SECURITY_HARDEN, REDUCE_DEPENDENCIES, RUN_QC, ARCHITECTURE_DOCS, ANALYZE_ONLY, SELF_ANALYZE), 5 `DepthMode` values, 8 `OutputMode` values, and 4 `DataClassification` tiers. **None of this appears in the numbered design suite.** It is the single largest product surface built without a specification — and it is what makes the product commercially sellable, because it addresses brownfield work rather than only greenfield generation.
2. **Dependency absorption (`AGENT-39-DEPABS`).** Extract a dependency's intent, regenerate it first-party, produce an SBOM delta. A genuinely novel differentiator absent from the design.
3. **Runtime QC (`AGENT-41-RQCA`) and ephemeral test data (`AGENT-40-TESTDATA`).** Sandboxed execution plus AI browser-driven QC. `rqca_enforcement_enabled` defaults to **True** — a failed runtime QC blocks delivery.
4. **Application Intelligence Map and Mission Charter.** `aim_generator.py`, `schemas/mission_charter.v1.json`, wired through `phases_intake.py`. Both were flagged as missing in the May-2026 gap report; both are now live.
5. **Real AST extraction.** The design assumed LLM-based extraction. Built: `ast` (Python), `esprima` with TypeScript pre-stripping (JS/TS), `javalang` (Java), plus Go, Haskell, OCaml, Julia extractors, with regex fallback and golden fixture locks. Deterministic where the design was probabilistic — a clear improvement.
6. **Cryptographic chain-of-custody.** ECDSA-signed RIR modules and artifacts, HMAC-signed human approvals with TTL, immutable audit tables. This is the honest differentiator against every competing tool, and it is stronger than what Doc 08 §4.6 asked for.
7. **Desktop distribution.** Electron packaging, NSIS installer (`theFactory-MissionControl-Setup-0.1.0.exe`), standalone Next.js server bundle, Docker preflight. Not in the design at all.
8. **Feature-flag discipline.** Every unproven capability ships behind `*_ENABLED=false` and cannot block the mission path. This is why the codebase is safe to extend, and it is the practice most worth preserving.

---

## 6. Documentation Integrity Findings

This is where the immediate risk sits.

**6.1 — Two canonical, contradictory specifications.** The project-knowledge suite (Docs 01–64, Feb–Mar 2026) and the repository suite (`docs/`, 2026-06/07) describe different products. `docs/WHAT_THEFACTORY_IS_AND_IS_NOT.md` explicitly says theFactory is "**Not a transpiler**" and produces software with evidence; Doc 01 says it smelts 14 languages into optimised zero-dependency binaries with 99.9999% semantic equivalence. Both are marked authoritative. Nothing in either corpus points at the other.

**6.2 — The project-knowledge gap report is stale and would misdirect planning.** `HGR_Gap_Report.md` (May 2026) is cited as current but has been overtaken:

| Gap report claim | Verified state today |
|---|---|
| "Java AST extractor is a **stub** (`success=False`)" | Real — `javalang`-backed, 207 lines |
| "JS/TS AST extractor is a **stub**" | Real — `esprima` + TS stripping, 278 lines |
| "Mission charter: the producer doesn't exist" | Exists — `phases_intake.py`, `base.py`, `internal.py` |
| "AIM: not implemented" | Exists — `aim_generator.py`, `port_coordinator.py` |
| "38-agent registry" | 41 agents |
| "FUSION → SQUEEZE → DELIVERY not implemented in any form" | All three phases exist and run |

Its §4.1–4.6 assessments (LogicNode thinness, synthetic RIR, no real equivalence) remain **accurate** — which is exactly why the stale parts are dangerous: the document reads as credible.

**6.3 — Two claims in `docs/IMPLEMENTATION_STATUS.md` are not supportable as written.** "**100% feature-complete**" and "Core Software Engine — **100% Complete**… Refined-IR … 100% operational" cannot both be true and consistent with `docs/LOGICNODE_SCHEMA.md`'s own statement that the RIR projection is synthetic. The repository contains a document contradicting its own status page.

**6.4 — There is no design-to-implementation traceability.** `docs/BLUEPRINT_MAP.md` is a file map of the repo, not a mapping from the 64 numbered design documents to implementing modules. Nothing answers "Doc 30 specified a registry — where is it?" except manual reading. For a system whose selling point is auditability, this is the conspicuous absence.

---

## 7. Recommended Actions

Ordered by ratio of risk removed to effort. All are **proposals** — nothing has been changed.

### P0 — Reconcile the specification with reality (days, not weeks)

**A1. Write a single Design Reconciliation ADR.** One document that states, per design area, whether the design is *implemented*, *deliberately superseded*, or *deferred*. Every item in §4 needs one of those three labels and a one-line rationale. Without this, every future contributor and every evaluator re-derives the same confusion. **Highest value action in this report.**

**A2. Archive or annotate the superseded design corpus.** Move Docs 01–64 to an explicitly historical status, or add a header block to each: *"Design phase, Feb 2026. Superseded in part — see Design Reconciliation ADR."* Do the same for `HGR_Gap_Report.md`, adding a "verified stale as of 2026-08-01" note listing the six closed items in §6.2.

**A3. Correct the two unsupportable status claims (§6.3).** Change "100% feature-complete" to a scoped statement — *"feature-complete against the v1.3 mission-pipeline scope; Refined-IR semantic depth and formal equivalence verification are explicitly out of scope."* This costs nothing and removes the only genuine credibility exposure in the repository.

**A4. Retire the 0.0001% / 99.9999% figure everywhere it is not computed.** It appears throughout the design corpus and is not calculated anywhere in the codebase. Semantic equivalence is undecidable for arbitrary programs; the number was never achievable and does not need to be defended. Replace with what the system *does* measure: contract-conformance pass rate and runtime-QC verdicts.

**A5. Build the traceability matrix.** A `docs/DESIGN_TRACEABILITY.md` table: design doc → status → implementing module(s) → evidence file. Roughly 64 rows. Fits naturally alongside `BLUEPRINT_MAP.md` and directly serves the audit story the product sells.

### P1 — Close the divergences worth closing (weeks)

**A6. Unify the message envelope.** Define one envelope covering both transports, or formally document them as two distinct schemas with a stated correlation contract. At minimum, reconcile the priority vocabulary (`NORMAL|HIGH` vs `low|normal|high|critical`) — that mismatch is a latent bug the moment anything routes on priority across both paths.

**A7. Decide the bus's role, in writing.** Two honest options: (a) declare it an observability spine, rename the EDCP plan accordingly, and stop carrying the control-plane framing; or (b) commit to EDCP and put at least one **load-bearing** consumer on a lane — a Delta consumer that can actually fail a mission is the cheapest proof. Option (a) is legitimate and much cheaper. What is not legitimate is leaving it ambiguous.

**A8. Enrich the LogicNode schema — additively.** Promote the fields already sitting inside `payload` (`domain`, `concept`, `confidence`) to first-class optional properties, and add optional `paradigm`, `source_license`, `purity`, `complexity`. Keep them optional so nothing breaks. This is the prerequisite for §4.5, §4.12, and any future semantic work; it gets more expensive every mission that accumulates in `mission_logicnodes`.

**A9. Make the RIR projection's synthetic nature machine-visible.** Add `"projection_method": "templated_v1"` to the RIR module header. Today the honesty lives only in prose in `LOGICNODE_SCHEMA.md`; a downstream consumer reading the JSON cannot distinguish a templated projection from a real one. This is a one-line change with outsized integrity value.

**A10. Rebalance or rename the pods.** Either move Haskell/OCaml into a Pod E ("Functional") or rename Pod D to "Mathematical & Functional." Cheap now; a correctness landmine if cross-language verification is ever implemented.

### P2 — Strategic decisions to take deliberately (decide, then schedule)

**A11. Formally kill or formally schedule binary synthesis.** It is the design's headline promise with zero implementation and no partial scaffolding. Given the product has moved to source-artifact delivery with evidence, killing it is the right call — but it should be an explicit, recorded decision, and `AGENT-09-HW`'s registry role description should be rewritten to match whatever is decided.

**A12. Specify the mission taxonomy retroactively.** The 10 mission types / 5 depth modes / 8 output modes / 4 classification tiers are the product's actual commercial surface and have **no specification document**. This is the largest unwritten spec in the system and the one most likely to cause drift as the matrix grows. Write it before adding the eleventh mission type.

**A13. Reconsider whether the Registry (Doc 30) is wanted.** Doc 30 is the largest unimplemented specification in the corpus. A cross-mission LogicNode registry with semantic clustering is only valuable if RIR carries real semantics; per §4.3 it does not. Recommend explicitly deferring Doc 30 behind the RIR-depth decision rather than leaving it as apparent scope.

**A14. Decide LangGraph's fate.** Either enable it and prove it (Doc 14 becomes real), or mark Doc 14 superseded by `mission_flow_v2/transitions.py` and stop maintaining a disabled second engine. Carrying both indefinitely costs test surface and reader confusion.

---

## 8. Closing Assessment

The build is in better shape than a design-vs-reality comparison usually reveals. The infrastructure is real, the security posture is serious, the test surface is broad, the evidence chain is cryptographic, and the operator experience is well past specification. Several of the most valuable capabilities in the system — dependency absorption, runtime QC, the mission taxonomy, chain-of-custody — were invented during construction and are better than what was designed.

The gap is confined to one axis, but it is the axis the design was named after: **semantic depth**. LogicNodes are envelopes, Refined-IR is a template, equivalence is contract conformance, and nothing compiles. Every one of those is a defensible engineering decision. None of them is written down as a decision.

The work is therefore not primarily engineering. It is **A1 through A5** — deciding, in one document, which product this is, and retiring the specification for the one it isn't. That converts an apparent 60%-implemented design into a fully-implemented and honestly-scoped one, and it is the difference between a system that survives external technical due diligence and one that does not.

---

### Appendix — Primary sources read

**Design corpus** (project knowledge, 143 files): Docs 01, 02, 05, 06, 07, 08, 09, 14, 15, 26, 30; `HGR_Mission_Flow_v2.md`, `HGR_Gap_Report.md`, `HolyGrail_Design_Checklist.md`, `memory.md`.

**Application** (`C:\software\Holygrail\theFactory`):
`services/orchestrator/orchestrator/` — `agent_registry.py`, `agent_personas.py`, `models.py`, `settings.py`, `protocol.py`, `protocol_bus_producer.py`, `logicnode_schema.py`, `equivalence_verifier.py`, `knowledge_lake.py`, `agent_scaling.py`, `build_artifacts.py`, `neo4j_store.py`, `main.py`, `llm_delegation/config.py`, `mission_flow_v2/{transitions,lifecycle,phases_build,phases_runtime,phases_delivery}.py`, `migrations/V001…V009` ·
`services/protocol-bus-mcp/protocol_bus/mcp_server.py` ·
`services/pod-worker/pod_worker/{refined_ir,js_ast_extractor,java_ast_extractor}.py` ·
`schemas/{logicnode,rir.fn,event.envelope}.schema.json` · `protocol/topics.yaml` · `ledger/schema.sql` ·
`deploy/docker-compose.yaml` · `apps/mission-control/app/**` · `tests/**` ·
`docs/` — `IMPLEMENTATION_STATUS.md`, `WHAT_THEFACTORY_IS_AND_IS_NOT.md`, `LOGICNODE_SCHEMA.md`, `BLUEPRINT_MAP.md`, `CURRENT_TODO.md`, `AGENT_SERVICE_KEY_ISOLATION.md`, `ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md`.
