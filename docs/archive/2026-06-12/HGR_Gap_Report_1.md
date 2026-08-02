# theFactory / Holy Grail Refinery
## Built vs. Should Be Built — Complete Gap Report
**Date:** May 2026 | **Basis:** Full live code review + complete project specification review

---

## Executive Summary

> ### ⚠️ Staleness verification — 2026-08-01
>
> This report **reads as credible and is partly wrong**, which is exactly what makes
> it dangerous for planning. A full design-vs-build audit on 2026-08-01 verified the
> following claims **closed** against live source:
>
> | Claim in this report | Verified state on 2026-08-01 |
> |---|---|
> | "Java AST extractor is a **stub** (`success=False`)" | Real — `javalang`-backed, ~207 lines |
> | "JS/TS AST extractor is a **stub**" | Real — `esprima` + TypeScript stripping, ~278 lines |
> | "Mission charter: the producer doesn't exist" | Exists — `phases_intake.py`, `base.py`, `internal.py` |
> | "AIM: not implemented" | Exists — `aim_generator.py`, `port_coordinator.py` |
> | "38-agent registry" | **41 agents** (`agent_registry.py`) |
> | "FUSION → SQUEEZE → DELIVERY not implemented in any form" | All three phases exist and run |
>
> **Its §4.1–4.6 assessments remain accurate** — LogicNode thinness, synthetic
> Refined-IR, and the absence of real equivalence verification are all still true and
> are addressed by Phases 3–5 of
> `docs/UPGRADE_RECONCILIATION_PLAN_2026-08-01.md`.
>
> Current status of every design area:
> `docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md`. Do not plan from this file.

**Validation update - May 17, 2026 (revised 2026-05-17):** this gap report is a
historical baseline, not the current state of the repo. Phases 1-7 have since
shipped material intelligence-layer work: provider-verified model defaults, PM
feature contracts, mission charters, CEO mission contracts, first generated-output
artifact support, generated-code artifact download, Mission Detail panels for those
artifacts, CEO logic cluster decomposition, pod group standards (Phase 6), and
JavaScript/TypeScript + Java AST extractors (Phase 7). The remaining major gaps
are now FETCH, FUSION, PM delivery verification, AIM, runtime/equivalence QC,
compliance/security execution, DEPABS, and token/cost ledgering.

theFactory has completed 39 development phases and is a production-grade infrastructure system. The pipeline scaffolding, state machine, protocol bus, operator console, security controls, CI/CD, and audit chain are all real and solid. The original missing area was the intelligence layer. That assessment has been partially closed by the May 16-17 implementation pass, but the later Smelt-Cycle phases and trust/production agents remain open.

---

## Section 1 — What Is Fully Built

These components are real, tested, and production-quality. No work needed here beyond maintenance.

### 1.1 Mission Lifecycle Engine
- 11-phase v2 state machine: INTAKE → QUEUED → PM_INTAKE → CEO_DELEGATED → POD_ASSIGNED → SPECIALIST_ASSIGNED → RUNNING → GATING → FUSION → VERIFIED → COMPLETE
- State transitions tested and locked by golden tests
- Lifecycle recovery on orchestrator restart — in-flight missions are re-queued
- Self-heal loop and DLQ (dead-letter queue) for failed intake events
- LangGraph engine available as optional flag (`LANGGRAPH_ENABLED`)
- Mission charter schema (`mission_charter.v1.json`) exists in `/schemas/`

### 1.2 Semantic Bus (Redis Streams)
- All 6 protocols fully implemented in `semantic-bus-mcp`: Alpha (Directive), Beta (Production), Delta (Audit), Sigma (Knowledge), Omega (User), Rho (Traffic)
- Strict Pydantic payload validation for each protocol
- Correlation-ID deduplication with configurable TTL
- Backpressure at 10,000-message queue depth
- Message TTL and stream pruning
- DLQ per stream

### 1.3 Source Extraction Engine
- Regex-based extraction for all 20 language keys across 4 pods
- Python AST extractor (real — uses `ast` module, zero false positives)
- Java AST extractor — **real implementation** (uses `javalang`, implemented 2026-05-17, commit 8b59594)
- JS/TS AST extractor — **real implementation** (uses `esprima`, implemented 2026-05-17, commit 8b59594)
- Concept catalog: ~430 patterns across all language pods
- Golden fixture tests locking extraction output for Python, JS, Java, Rust
- `ExtractedConcept` records include domain, concept, intent, confidence, evidence, extraction_method, source_range

### 1.4 Agent Registry and Class Hierarchy
- 38-agent registry fully defined (`agent_registry.py`)
- Complete `BaseAgent → SpecialistAgent → [16 language agents]` hierarchy
- All 38 agents have `execute()`, `validate()`, `report()` lifecycle methods
- Agent LLM model assignments defined per agent in `agent_integrations.py`
- Agent persona profiles (8-part framework) serialized via `agent_personas.py`
- Heartbeat synthesis for non-pod agents (interface/executive/support) via orchestrator

### 1.5 LLM Delegation
- Real API calls to OpenAI, Anthropic, and Gemini for CEO / pod-manager / specialist routing steps
- Retry with exponential backoff and `Retry-After` header respect
- Deterministic fallback routing by language mapping when LLM is offline
- Prompt injection hardening — `_safe_context_json` strips user-controlled fields before embedding in prompts
- PII and secret redaction in prompt context
- Golden delegation test suite validating fallback routing for all 20 languages

### 1.6 Storage Layer
- PostgreSQL: 5 versioned migrations, tables for missions, state events, pod assignments, logicnodes, knowledge, audit reports, build artifacts, review approvals, agent action events
- Qdrant: active vector store for mission knowledge (replaced pgvector)
- Redis Streams: event backbone
- Storage decomposed into domain modules: `storage_missions.py`, `storage_agents.py`, `storage_artifacts.py`, `storage_logicnodes.py`, `storage_pods.py`
- Optional adapters: Neo4j, Milvus, MinIO (all feature-flagged, off by default)

### 1.7 Security and Auth
- Dual-mode auth: `api_key` / `hybrid` / `oidc` (JWT bearer + JWKS validation)
- Internal service key isolation per agent (`AGENT_XX_YYY_SERVICE_API_KEY`)
- Operator session with HMAC-signed cookies (AES-256-GCM via `vault.ts`)
- Review approvals with HMAC digest chain and TTL expiry
- Vault backend: HashiCorp Vault (if configured), local AES-256-GCM encrypted file, in-memory fallback
- `prompt_guard.py`: OWASP LLM01 injection detection (role-override, delimiter smuggling, jailbreak)
- `pii_guard.py`: SSN, credit card, email, phone, JWT, API key detection and redaction
- Fail-closed auth defaults in production, loud warnings in dev

### 1.8 Mission Control UI
All 9 pages are real and functional:
- **Chat** — PM Agent intake with file upload, language detection from extensions, session-stored history, feature contract generation, mission launch
- **Missions** — full CRUD, SSE live stream + poll fallback, mission type/depth/output/classification selectors
- **Mission Detail** — live phase stepper (7-phase Smelt-Cycle mapped from v2 events), chain trace, LogicNode list, audit reports, build artifacts, active agent panel
- **Repo Import** — real GitHub API integration: tree import, file selection with include/reference/exclude overlay, review with fingerprint, approval gate before mission launch
- **Builder** — workspace-aware file scanning and scoring, diff preview, fingerprint, approval gate before mission launch
- **Agents** — live agent roster with runtime/conceptual toggle, tier/pod/state filters, SSE transport, agent log stream
- **LogicNodes** — list with intent, domain, confidence display
- **Semantic Bus** — live event stream with protocol color coding
- **Settings** — full 35-agent vault slot table, AES-256-GCM key storage, local preference controls

### 1.9 CI/CD and DevOps
- GitHub Actions: lint → schema validation → Python tests (≥80% coverage) → Mission Control lint/unit/Lighthouse/Playwright E2E → Docker build (all 7 services) → SBOM (SPDX + CycloneDX) → release trust/promotion gate
- Weekly qualification workflow: canary rollout, OIDC matrix, LangGraph v2 prototype matrix
- Security workflow: pip-audit, Bandit SAST, license scan (blocks GPL/AGPL)
- Promotion policy JSON: fail-closed, blocks preview/experimental/rolling model lifecycle stages
- Full dedicated-agents Docker Compose profile: all 38 agents as isolated containers

### 1.10 Observability
- Prometheus metrics in all 7 services
- Grafana + Loki + Jaeger in monitoring compose profile
- Optional adapter observability metrics (enabled/ready/latency/mirror-write counters)
- OpenTelemetry tracing wired through gateway and orchestrator
- DORA metrics script

---

## Section 2 — What Is Partially Built (Stubs or Incomplete)

These components exist in the codebase but are not functional end-to-end.

### 2.1 LLM Delegation — Prompts Are Routing-Only
**What exists:** CEO, pod-manager, and specialist agents make real LLM API calls.
**What it actually does:** The CEO prompt is 5 lines asking for `pod_manager_agent_id`, `specialist_agent_id`, `rationale`. The specialist prompt asks for `plan_summary`, `deliverables` (array of short strings), `risk_notes`. No agent receives a meaningful work instruction. No agent generates code, analysis, or transformation output. The LLM calls are routing validators, not work executors.
**What should exist:** Agents that receive mission context and produce substantive work — the PM decomposing requirements into a real Feature Contract, the CEO producing an actual Refined-IR Contract specifying required LogicNodes, specialists generating code from those LogicNodes.

### 2.2 Java and JS/TS AST Extractors
**RESOLVED — 2026-05-17 (commit 8b59594, Phase 7)**
`java_ast_extractor.py` uses `javalang` to extract packages, imports, classes, constructors, methods, parameters, modifiers, and annotations. `js_ast_extractor.py` uses `esprima` to extract imports, classes, class methods, function declarations, and arrow/function-expression assignments, stripping TypeScript syntax before parsing. Both preserve regex concept detection as fallback and return `success=False` only when the library is unavailable or the source has a parse error. Feature flags: `JAVA_AST_EXTRACTOR_ENABLED=true`, `JS_AST_EXTRACTOR_ENABLED=true` — both defaulted on in compose.

### 2.3 Mission Charter Generation
**RESOLVED — 2026-05-16 (Phase 4)**
Mission charters are now generated during PM_INTAKE in Mission Flow v2. The PM path produces a structured `feature_contract` and a schema-validated `mission_charter`, persists both in `metadata`, exposes them in the chain trace API, and displays them in Mission Control Mission Detail. Visual Blueprint generation, multimodal verification, and PM approval workflow remain open (see Section 3.7).

### 2.4 Application Intelligence Map (AIM)
**What exists:** `docs/APPLICATION_INTELLIGENCE_MAP.md` — a detailed canonical spec defining a comprehensive read-only analysis artifact produced before any code changes. The spec says AIM generation is required for IMPORT_MODERNIZE, PORT, DEBUG_REPAIR, SECURITY_HARDEN, REDUCE_DEPENDENCIES, and ANALYZE_ONLY missions.
**What is missing:** Any implementation. No AIM generator, no AIM schema, no AIM storage, no AIM display in Mission Control.

### 2.5 Traceability Ledger (SQLite)
**What exists:** `ledger/schema.sql` — a complete SQLite schema with `artifacts`, `sources`, `custody`, and `audit_runs` tables.
**What is missing:** The ledger is not wired into any running service. The PostgreSQL `agent_action_events` table serves as the actual audit chain (SHA256-chained event digests). The SQLite ledger was the original spec design; the Postgres chain is the current implementation. Decision needed: retire the ledger spec or activate it.

### 2.6 Accountant Agent — Token Cost Ledger
**What exists:** `AGENT-04-ACCOUNTANT` is in the registry with a defined role: token-cost monitoring and budget enforcement. It has a heartbeat and a persona.
**What is missing:** Any actual cost tracking. No per-mission token count is recorded. No budget alerts fire. The Accountant is synthesized heartbeat only — no code executes on its behalf. The spec calls for a Mission Cost Ledger opened at mission start, tracking per-agent token spend in real-time.

### 2.7 Dedicated Agent Profile — Full `full-dedicated-agents` Topology
**What exists:** The Makefile has `make up-full-dedicated` which launches all 38 agents as isolated containers. Each has its own `AGENT_BINDING` environment variable wired in `docker-compose.full-dedicated-agents.yaml`.
**What is missing:** In the dedicated profile, each per-agent container runs the same `agent-runtime` service with a different `WORKER_AGENT_ID`. The `agent_base.py` `execute()` methods all produce audit-oriented stub outputs (delegation plan, pod fusion plan, etc.) — not real language work. The infrastructure for full dedicated topology is real; the cognition inside each container is not.

---

## Section 3 — What Is Not Built At All

These are core spec requirements with zero implementation in the codebase.

### 3.1 FETCH Phase — IS Agent and Knowledge Lake
**Spec:** Phase 2 of the Smelt-Cycle. The IS Agent (AGENT-06) detects required libraries from the mission scope, crawls official documentation and GitHub repos, indexes content into a vector Knowledge Lake via LlamaIndex, and broadcasts `knowledge_ready` events via Protocol Sigma. All 16 specialists pre-load their 700K-token cached documentation windows before extraction begins.
**What's built:** None. There is no IS Agent execution code. There is no document crawler. There is no LlamaIndex integration. There is no Knowledge Lake indexing pipeline. Protocol Sigma's payload schema is defined in `semantic-bus-mcp` but nothing publishes to it. Qdrant is running and ready; it stores mission knowledge summaries but not language documentation.
**Impact:** Specialists extract patterns without documentation context. Extraction quality is purely structural (function names, class names, regex concept matches) with no semantic depth from language documentation.

### 3.2 FUSION Phase — CEO Logic Folding
**Spec:** Phase 4. The CEO receives all 4 Pod Group Standards (consolidated LogicNode sets from each pod), performs Logic Folding — cross-paradigm deduplication, dependency ordering, paradigm conflict resolution — and produces a single Master Logic Stream of 50–200 unified LogicNodes ready for code generation.
**What's built:** None. The `MISSION_FUSION` state checkpoint is emitted (it appears on the phase stepper in the UI) but nothing executes during it. No cross-pod LogicNode consolidation happens. No Master Logic Stream is assembled. The CEO LLM call produces a routing decision (which pod manager, which specialist) — not a fusion of extracted knowledge.
**Impact:** The core semantic compression the system is named after — 14 → 4 → 1 — does not happen. LogicNodes from different pods sit in the database independently with no cross-pod synthesis.

### 3.3 SQUEEZE Phase — Code Generation from Refined-IR
**Spec:** Phase 5/6. Specialists receive the Master Logic Stream and generate actual code — converting each LogicNode back into target-language implementation. The Hardware-Mapping Injector tunes the stream for the target platform. Systems Pod may produce WASM for performance-critical paths. DevOps bundles the output artifact.
**Current validation:** Partially built. Mission Flow v2 can create a first
narrow `generated_output` from the mission contract, persist it in metadata, and
package it as a `generated_code` artifact when present. The source-bundle path
still works for analysis/source missions. This is not yet full SQUEEZE: it does
not consume a Master Logic Stream, perform hardware mapping, generate multi-file
projects, run runtime QC, or prove semantic equivalence.
**Impact:** The system now has an early generated-output loop, but the complete
Refined-IR-to-production-code SQUEEZE phase remains open.

### 3.4 DELIVERY Phase — PM Visual Verification and Deployment
**Spec:** Phase 7. PM Agent uses Gemini multimodal Vision-AI to compare the rendered output against the original Visual Blueprint from intake. Verifies UI matches intent. Routes corrections back if discrepancies exist. Deployment Agent packages and delivers the final artifact.
**What's built:** None. No visual verification. No visual blueprint generation in PM intake. No screenshot capture. No multimodal Gemini call for output comparison. No Deployment Agent execution. The `MISSION_COMPLETE` state fires but no delivery action happens beyond the state transition.

### 3.5 Dependency Absorption Engine (DEPABS)
**Spec:** (`docs/DEPENDENCY_ABSORPTION_DOCTRINE.md`, `AGENT-39-DEPABS`). The absorption engine detects third-party dependencies used in the target application, classifies them (Absorb/Replace/Wrap/Pin/Keep/Block), extracts their used-symbol surface, generates first-party replacement code with equivalence tests, and eliminates the dependency from the output artifact. The doctrine defines a full decision hierarchy, safety block list, and shadow equivalence mode.
**What's built:** The doctrine document and DEPABS agent registration (`AGENT-39-DEPABS` appears in `agent_scaling.py`'s `SCALABLE_AGENT_IDS`). Zero implementation code. No dependency scanner, no symbol extractor, no replacement code generator, no equivalence test harness for dependency verification.
**Impact:** The REDUCE_DEPENDENCIES mission type is selectable in the UI but does nothing beyond running the standard extraction pipeline.

### 3.6 Equivalence Verification (1,000-Simulation Gate)
**Spec:** Each LogicNode must pass 1,000 equivalence tests at 0.0001% tolerance before the QC/Audit gate approves it. Tests compare original source behavior against the LogicNode's specified behavior across normal (80%), edge (15%), and stress (5%) cases.
**What's built:** The `PodAuditAgent.execute()` checks that logicnodes have a `node_id` and `concept` field. That is the full audit gate. No test generation. No simulation runner. No tolerance calculation.
**Impact:** The quality guarantee that differentiates HGR from other tools — the provably correct semantic extraction — does not exist.

### 3.7 PM Agent Cognition — Feature Contract and Visual Blueprint Generation
**Spec:** PM Agent receives user input via Protocol Omega, interprets intent, asks clarifying questions if needed, generates a Visual Blueprint (wireframe/mockup using Gemini multimodal), and produces a structured Feature Contract with functional requirements, acceptance criteria, success metrics, and non-functional requirements.
**Current validation:** Partially built. Mission Flow v2 now persists a
structured `feature_contract` and `mission_charter`, exposes them in chain trace,
and displays them in Mission Detail. The Chat page still uses the local
`createBuilderPreview()` path, and Visual Blueprint generation, multimodal
verification, clarifying-question flow, and PM approval workflow remain open.
**Impact:** The mission path now has a structured PM-to-CEO handoff, but the
operator chat preview and visual/approval parts of PM cognition still need work.

### 3.8 CEO Cognition — Refined-IR Contract and Logic Cluster Decomposition
**Spec:** CEO receives the Feature Contract, decomposes it into Logic Clusters by domain, assigns each cluster to the appropriate pod, and produces a Refined-IR Contract — a precise specification of all required LogicNodes, their domains, expected inputs/outputs, and cross-language requirements.
**Current validation (updated 2026-05-17):** CEO delegation persists a durable
`mission_contract` and decomposes it into `logic_clusters`. Both are exposed in
chain trace and displayed in Mission Detail. Pod workers now consume CEO
logic-cluster domain focus during extraction and boost matching concept confidence
for the assigned pod. FUSION has not yet consolidated pod group standards into a
Master Logic Stream (see Section 3.2).

### 3.9 Sub-Manager Consolidation — Pod Group Standards
**RESOLVED — 2026-05-17 (commit 9e1e8d7, Phase 6)**
Pod group standards are now produced during the GATING phase in Mission Flow v2. `generate_pod_group_standard()` in `llm_delegation.py` consolidates specialist LogicNodes into canonical pod-level nodes, records duplicate elimination counts, emits `MISSION_POD_GROUP_STANDARD_PRODUCED`, and stores results in `metadata["pod_group_standards"]`. Standards are exposed through chain trace and displayed in Mission Control Mission Detail. Full cross-pod FUSION consolidation into a Master Logic Stream (CEO Logic Folding) remains open — see Section 3.2.

### 3.10 Compliance Agent — IP Provenance and License Checking
**Spec:** Compliance Agent (AGENT-08) receives every LogicNode via Protocol Delta, checks the source library license, verifies no GPL contamination, and clears or blocks the node with a compliance verdict.
**What's built:** Compliance Agent exists in the registry as a synthesized heartbeat. No compliance check is executed on any LogicNode.

### 3.11 Security Agent — LogicNode Vulnerability Scanning
**Spec:** Security Agent (AGENT-05) performs pre-fusion security scans on all LogicNodes — vulnerability analysis, penetration test simulation on extracted logic, dependency CVE checking.
**What's built:** Security Agent exists in the registry as a synthesized heartbeat. No security scan executes.

### 3.12 Version Control Agent — Git Commit Per Smelt
**Spec:** Version Control Agent (AGENT-07) commits every completed Smelt to the project repository, tags releases, maintains the traceability chain from LogicNode to final delivered code line.
**What's built:** Version Control Agent exists in the registry as a synthesized heartbeat. No Git operations execute during missions.

### 3.13 Hardware-Mapping Injector — Platform Optimization
**Spec:** Hardware-Mapping Injector (AGENT-09) analyzes the target platform (browser, desktop with RTX 4060 Ti + i7-14700F, mobile), injects hardware-specific tuning directives into the Master Logic Stream — AVX2/FMA instructions, GPU acceleration flags, WASM hints, cache-aware memory patterns.
**What's built:** Hardware-Mapping Injector exists in the registry as a synthesized heartbeat. No hardware analysis executes.

### 3.14 System Integration Tester (E2E) — Runtime QC
**Spec:** System Integration Tester (AGENT-10) runs the complete test suite derived from the original Refined-IR Contract against the generated output, performing end-to-end validation and performance benchmarking. Any failures route back to specialists for correction.
**What's built:** System Integration Tester exists in the registry; it is the `WORKER_AGENT_ID` for the audit-worker service. The audit-worker listens for `MISSION_VERIFIED` events and posts a simple `{"result": "PASS"}` audit report. No tests derived from the Refined-IR Contract are executed.

### 3.15 Multi-LLM Context Window Management and Caching
**Spec:** API Broker manages 35+ dedicated API keys with model routing (Flash for simple tasks, Pro for complex reasoning), activates prompt caching to achieve 90% cost reduction, monitors token budgets in real-time.
**What's built:** `agent_integrations.py` defines per-agent provider/model assignments. The gateway uses a single `ADMIN_API_KEY` for operator routes. No API Broker execution. No per-agent key rotation. No context caching. No Flash vs Pro routing. LLM calls use whichever key is in the environment.

---

## Section 4 — Schema and Model Gaps

### 4.1 LLM Model Governance - Updated
The original model-string finding is closed for OpenAI and Anthropic defaults.
Current defaults are:

- OpenAI executive/ops: `gpt-5.5`
- OpenAI coding specialists and VC: `gpt-5.3-codex`
- Anthropic deep audit: `claude-opus-4-7`
- Anthropic general workhorse: `claude-sonnet-4-6`
- Gemini deep reasoning: `gemini-3.1-pro-preview`
- Gemini fast ops: `gemini-3.1-flash-lite`

Gemini 3.1 Pro remains preview-lifecycle in the official Google docs. It is
intentionally allowlisted in `deploy/promotion-policy.json`; release claims must
keep that waiver visible until Google publishes a stable 3.1 Pro API ID or the
project pins back to a stable Gemini model.

### 4.2 LogicNode Schema Gap Between Spec and Code
The `protocol_beta_production.md` spec defines LogicNodes with `semantic.domain`, `semantic.mathematical_foundation`, `interface.inputs` with full type constraints, `cross_language_equivalents` with semantic similarity scores, `hardware_hints`, `performance.complexity`, `logic.steps`. The code produces `{concept_id, domain, concept, intent, confidence, evidence}`. The code schema is directionally correct but contains ~20% of the spec depth needed for CEO fusion and SQUEEZE code generation to work.

### 4.3 Refined-IR Function Schema vs. What Is Produced
`rir.fn.schema.json` defines functions with `fn_id`, `name`, `purity`, `inputs`, `outputs`, `preconditions`, `postconditions`, `ops` (with real opcodes like `ADD`, `EXTRACT_CONCEPT`), `effects`, `tests` (with equivalence vectors), and `provenance`. The `refined_ir.py` builder populates these fields but with analytical metadata — `opcode: "EXTRACT_CONCEPT"` documents what was found, not what to generate. There is no `opcode: "GENERATE"`, `SYNTHESIZE"`, or `EMIT"` in the current schema. The IR records what was analyzed; it does not instruct code generation.

---

## Section 5 — Infrastructure Gaps (Non-Critical but Open)

### 5.1 Git History TLS Private Keys
Two private TLS keys (`deploy/postgres/certs/server.key` and `deploy/redis/certs/redis.key`) were committed to the repository. The working tree has been cleaned (local-only cert generation via scripts). Git history still contains them. `git filter-repo` is required before any public exposure.

### 5.2 Model Governance — Promotion Gate Will Block
`deploy/promotion-policy.json` blocks `preview`, `experimental`, and `rolling` lifecycle models. The model inventory script (`export_agent_model_inventory.py`) classifies any model containing "preview" or "experimental" in its name as blocked. Until model strings are updated to valid, stable model names, the release promotion gate will fail.

### 5.3 DR Evidence — 4/10 Audit Score Unchanged
Backup and restore scripts exist (`scripts/backup_postgres.ps1`, `scripts/restore_postgres.ps1`, `scripts/dr_drill.ps1`). No timed restore drill has been executed and documented. No RTO/RPO evidence exists in `docs/evidence/`. This was rated 4/10 in the March 2026 audit and has not changed.

### 5.4 E2E Test Coverage Narrow
Playwright E2E suite (~1,100 lines across two spec files) covers: mission create/list/fail states, settings/vault, agent page, accessibility checks. It does not cover: the Builder end-to-end approve-and-launch flow live, the Repo Import full workflow live, the Chat page mission launch, or any live-stack integration scenario. All tests are mocked.

### 5.5 Review Approval Local Disk Receipts
`.runtime/review-approvals/` directory on local disk stores review approval receipts. The March audit flagged this as a horizontal scaling blocker. The current implementation has moved to PostgreSQL-backed approval records via `review_approvals` table (V003 migration), but old code paths and docs may still reference the filesystem backend.

---

## Section 6 — Gap Priority Matrix

| # | Gap | Spec Value | Complexity | Must-Have for "It Works" |
|---|-----|-----------|------------|--------------------------|
| 1 | CEO Refined-IR Contract generation | Highest | High | **Yes** |
| 2 | Specialist code generation from LogicNodes | Highest | Highest | **Yes** |
| 3 | FUSION — cross-pod LogicNode consolidation | Highest | High | **Yes** |
| 4 | Update model strings to valid names | Blocking | Low | **Yes** |
| 5 | PM Feature Contract structured generation | High | Medium | **Yes** |
| 6 | Mission Charter production by PM agent | High | Medium | Yes |
| 7 | IS Agent / Knowledge Lake / FETCH | High | High | For quality |
| 8 | Java AST extractor (activate `javalang`) | Medium | Low | For quality |
| 9 | JS/TS AST extractor (activate `esprima`) | Medium | Low | For quality |
| 10 | Equivalence verification (1,000 sims) | High | High | For trust |
| 11 | Dependency absorption engine | High | Highest | For REDUCE_DEPS |
| 12 | Application Intelligence Map generation | Medium | Medium | For IMPORT missions |
| 13 | Compliance/Security/VC agent execution | Medium | Medium | For full pipeline |
| 14 | Accountant — token cost ledger | Medium | Low | For FinOps |
| 15 | Hardware-Mapping Injector | Medium | High | For optimization |
| 16 | Git history TLS scrub | Security | Low | Before public |
| 17 | DR evidence documentation | Compliance | Low | For enterprise |
| 18 | Promote SQLite ledger or retire it | Architectural | Low | Decision needed |

---

## Section 7 — Summary Statement

theFactory has built the factory floor — the conveyors, the control room, the audit system, the safety interlocks, the worker stations, and the operator console. What it hasn't built yet is the workers themselves: no agent actually thinks about a mission, no agent generates code from extracted patterns, and no mission produces a software artifact that didn't exist before the mission ran.

The shortest path to a working end-to-end demo:
1. Fix model strings to valid names
2. Give CEO a real generative prompt (decompose this mission into what needs to be built)
3. Give specialists a real generative prompt (given these LogicNodes, generate code in {language})
4. Package that generated code as the mission output artifact
5. Display it on the Mission Detail page

That alone — without Knowledge Lake, without equivalence testing, without full fusion — would make theFactory demonstrably produce something. Everything else is quality and scale on top of that first working loop.
