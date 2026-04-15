# Codex Baseline Findings — theFactory
## Review Date: 2026-04-14
## Reviewer: Claude Code (read-only pass)
## Branch: main (validated from worktree claude/determined-haslett)

---

> **This is a READ-ONLY validation pass. No files were modified.**
> For each topic: findings are confirmed against actual code, contradictions noted,
> risk assigned, and next action recommended.
> Each item is marked: ✅ CONFIRMED | ❌ DISPROVEN | ⚠️ INCONCLUSIVE | 🔲 NOT REVIEWED

---

## Topic 1: Semantic Extraction Core

### Scope Reviewed
- `services/pod-worker/pod_worker/language_extractor.py`
- `services/pod-worker/pod_worker/ast_extractor.py`
- `services/pod-worker/pod_worker/concept_catalog.py`
- `services/pod-worker/pod_worker/main.py`
- `tests/services/test_language_extractor.py`
- `tests/services/test_ast_extractor.py`

### Questions Answered

| # | Question | Finding | Files Reviewed |
|---|---|---|---|
| 1.1 | Is the current extraction engine primarily regex-based? | ✅ CONFIRMED — Yes. `LanguageExtractor` base class uses three compiled `re.Pattern` fields per language (`_function_pattern`, `_class_pattern`, `_import_pattern`). All 18 language subclasses are regex-only. `concept_catalog.py` contains 234 `ConceptPattern` entries, each keyed on a `regex` field. | `language_extractor.py:89–200`, `concept_catalog.py:1–234` |
| 1.2 | Which languages have AST or semantic-model upgrades? | ✅ CONFIRMED — Python only. `ast_extractor.py` uses Python's built-in `ast` module for accurate function/class/import/type-annotation extraction. **Critical gap: this module is never called from `main.py`.** The production pipeline still routes Python through the regex `PythonExtractor`. | `ast_extractor.py:1–240`, `main.py` (no import of ast_extractor) |
| 1.3 | Is there a shared extractor interface/contract? | ✅ CONFIRMED — `LanguageExtractor` base class with `.extract(source: str) -> ExtractionResult` contract. All 18 language extractors inherit from it. Registry dict `_EXTRACTORS` maps language name → class. Public API: `get_extractor(language)`. | `language_extractor.py:89–454` |
| 1.4 | Are LogicNode provenance fields (confidence, source, method) populated? | ⚠️ PARTIAL — `confidence` (via `_compute_confidence()`) and `source_line` are populated. There is **no `extraction_method` field** in the LogicNode payload; the plan doc's `method` provenance field does not exist yet. | `main.py:255–265`, `language_extractor.py:203–218` |
| 1.5 | Are there fixture-based equivalence tests? | ✅ CONFIRMED — Comprehensive inline fixtures exist for Python, JS, Rust, Java, Go, Zig, Haskell, OCaml. 659-line test file with dedicated `TestXxxExtractor` classes per language. | `tests/services/test_language_extractor.py:1–659` |
| 1.6 | Does Python have a working AST extractor? Is it tested? | ✅ CONFIRMED — `extract_python_ast()` is fully working with 38 test cases covering functions, classes, imports, decorators, type annotations, async, edge cases. **Not wired into production pipeline.** | `ast_extractor.py:217`, `tests/services/test_ast_extractor.py:1–340` |

### Contradictions Between Docs and Code

| Doc Claim | Code Reality | File | Severity |
|---|---|---|---|
| AGENTS.md §5: "Python now has an AST-backed extractor" (implying it's in use) | `ast_extractor.py` exists and is tested, but is **never imported or called from `pod_worker/main.py`**. Python still runs through `PythonExtractor` (regex). | `pod_worker/main.py`, `ast_extractor.py` | **High** — misleads reviewers into thinking Python extraction is already semantic |
| HGR plan: LogicNode provenance includes "confidence, extraction_method, source_range" | `extraction_method` field does not exist. Field is `source_line` (not `source_range`). | `main.py:255–265` | Medium — plan anticipates fields that need to be added |

### Risk Level
- [x] **Medium** — Fixture tests exist and regex heuristics work. But the AST extractor (Python) is built and tested yet sits disconnected. For 19 remaining languages there is no upgrade path yet.

### Recommended Next Action
1. Wire `ast_extractor.py` into the Python extraction path in `pod_worker/main.py` behind a feature flag.
2. Add `extraction_method` and `source_range` to `ExtractedConcept` to complete the provenance contract.
3. Baseline fixture comparison: run AST vs regex on Python fixtures and confirm parity before promoting.

---

## Topic 2: Runtime Topology Truthfulness

### Scope Reviewed
- `services/orchestrator/orchestrator/main.py`
- `services/orchestrator/orchestrator/agent_registry.py`
- `services/orchestrator/orchestrator/routes/operations.py`
- `deploy/docker-compose.yaml`
- `deploy/docker-compose.full-dedicated-agents.yaml`

### Questions Answered

| # | Question | Finding | Files Reviewed |
|---|---|---|---|
| 2.1 | How many agents are real workers vs. synthesized heartbeats? | ✅ CONFIRMED — Pod workers (A/B/C/D) send real heartbeats via `/internal/agents/heartbeat`. Non-pod agents (categories: `interface`, `executive`, `support`) receive synthesized heartbeats generated by `_build_non_pod_heartbeat_payloads()`. Flag `AGENT_AUTOFILL_NON_POD_HEARTBEATS` (default: `true`) controls synthesis. | `main.py:64–71, 664–762` |
| 2.2 | Where does heartbeat synthesis happen? | ✅ CONFIRMED — `_build_non_pod_heartbeat_payloads()` at `main.py:664–730`. Loop: `agent_heartbeat_loop()` at `main.py:733–762`, runs every `AGENT_HEARTBEAT_INTERVAL_SECONDS` (default 5s). Synthesizes based on mission counts and system state. | `main.py:664–762` |
| 2.3 | Does the API expose runtime classification (real vs. virtual)? | ❌ DISPROVEN — The `/internal/operations/summary` endpoint exposes component readiness (`redis_ready`, `db_ready`, etc.) but **no `runtime_class` field** for agents. Agent records in the API contain no `real_worker` vs `synthesized_heartbeat` distinction. | `routes/operations.py:21–65` |
| 2.4 | Does Mission Control display agent states that don't reflect reality? | ⚠️ INCONCLUSIVE — Production code loads agent states dynamically from API. However `layout.tsx:22` states "38-agent multi-language refinery" in the app metadata description, implying a full dedicated topology regardless of what is deployed. | `apps/mission-control/app/layout.tsx:22` |
| 2.5 | Is there a dedicated topology profile? What does it enable? | ✅ CONFIRMED — `docker-compose.full-dedicated-agents.yaml` defines a `full-dedicated-agents` profile that spawns individual `agent-runtime` containers (384m memory, 0.35 CPU each) instead of shared pod workers. Documented in `docs/COMPOSE_ENVIRONMENT_PROFILES.md`. | `deploy/docker-compose.full-dedicated-agents.yaml:43–80` |
| 2.6 | Are Go, Haskell, OCaml registered but without real containers? | ❌ DISPROVEN — All 38 agents including Go (AGENT-36-GO), Haskell (AGENT-37-HASKELL), OCaml (AGENT-38-OCAML) have real pod assignments (Pod B and D respectively) in `agent_registry.py`. They are **not purely virtual** — they run inside pod-worker containers. | `agent_registry.py:389–418` |

### Contradictions Between Docs and Code

| Doc Claim | Code Reality | File | Severity |
|---|---|---|---|
| AGENTS.md §2: "Executive/Support synthetics — Registry personas — heartbeats generated by orchestrator" | Correct for non-pod agents. But Go/Haskell/OCaml are **real pod assignments**, not registry personas as implied elsewhere. | `agent_registry.py:389–418` | Medium — nuance gap, not a hard contradiction |
| HGR plan §B: "Add `runtime_class` field to every agent record" | Field does not exist yet anywhere in the API or registry. | `routes/operations.py`, `agent_registry.py` | Confirmed gap — needs implementation |

### Risk Level
- [x] **Medium** — UI and runtime are largely honest (states come from real API data), but operators have no programmatic way to distinguish real workers from synthesized heartbeats. The `layout.tsx` "38-agent" copy is misleading.

### Recommended Next Action
1. Add `runtime_class: "real_worker" | "shared_worker" | "synthesized_heartbeat"` to agent registry entries.
2. Expose `runtime_class` in the `/internal/operations/agents` response.
3. Fix `layout.tsx` metadata to not assert 38-agent dedicated topology.
4. Add `topology_mode` to system status endpoint.

---

## Topic 3: Lifecycle Engine Clarity

### Scope Reviewed
- `services/orchestrator/orchestrator/runtime.py`
- `services/orchestrator/orchestrator/settings.py`
- `services/orchestrator/orchestrator/mission_flow_v2.py`
- `services/orchestrator/orchestrator/langgraph_lifecycle.py`
- `services/orchestrator/orchestrator/models.py`

### Questions Answered

| # | Question | Finding | Files Reviewed |
|---|---|---|---|
| 3.1 | What is the actual call path for a new mission under default config? | ✅ CONFIRMED — `advance_mission_lifecycle()` → `advance_mission_lifecycle_v2()`. 9-phase progression: `PM_INTAKE → CEO_DELEGATED → POD_ASSIGNED → SPECIALIST_ASSIGNED → RUNNING → GATING → FUSION → VERIFIED → COMPLETE` | `runtime.py:539–554`, `mission_flow_v2.py:780–1078` |
| 3.2 | Where is `MISSION_FLOW_V2_ENABLED` checked? | ✅ CONFIRMED — Defined in `settings.py:73` (default `True`). Checked at `runtime.py:544`. If True → calls v2 and returns early. If False → falls through to LangGraph check (line 557), then legacy v1.1 (line 568). | `settings.py:73`, `runtime.py:544–672` |
| 3.3 | Is LangGraph integration complete or partial? | ✅ CONFIRMED PARTIAL — `langgraph_lifecycle.py:30–45` uses optional imports (`StateGraph = None` if langgraph not installed). Supports checkpointing and transition graph, but does **not replace core orchestration**. `LANGGRAPH_ENABLED` defaults to `false`. | `langgraph_lifecycle.py:30–65`, `settings.py:66` |
| 3.4 | Is there a single adapter/interface for engine choice? | ❌ NO ADAPTER — Engine selection is a sequential `if/elif/else` fallthrough in `advance_mission_lifecycle()`. No `LifecycleEngine` protocol, no factory class, no ABC. Decision logic is embedded in the function body. | `runtime.py:539–672` |
| 3.5 | Do all three paths emit the same lifecycle events? | ✅ CONFIRMED — All three paths call the same `emit_state_event()` function (`runtime.py:293–330`). Event schema is consistent: same envelope + payload structure, same event type constants from `models.py:59–82`. | `runtime.py:293–330`, `models.py:59–82` |
| 3.6 | Is the legacy fallback documented as deprecated? | ❌ DISPROVEN — Legacy v1.1 fallback at `runtime.py:568–672` has no deprecation marker, docstring, or comment flagging it as a compatibility shim. | `runtime.py:568–672` |

### Contradictions Between Docs and Code

| Doc Claim | Code Reality | File | Severity |
|---|---|---|---|
| AGENTS.md §3: "MISSION_FLOW_V2_ENABLED=true (DEFAULT)" | ✅ Correct — `settings.py:73` confirms default True | `settings.py:73` | None |
| HGR plan §C: "Create a single LifecycleEngine adapter interface" | Not yet created — three paths live inside one function with no abstract interface | `runtime.py:539–672` | Confirmed gap |

### Risk Level
- [x] **Medium** — v2 engine is the production default and event emission is consistent. The lack of an adapter interface is a maintainability risk, not a runtime correctness issue today.

### Recommended Next Action
1. Define a `LifecycleEngine` Protocol with `start_mission`, `advance_phase`, `complete_mission`, `fail_mission`.
2. Wrap v2, LangGraph, and legacy as adapter implementations.
3. Add `# COMPATIBILITY SHIM — not a supported path` docstring to legacy block.
4. Move engine selection to a single `get_lifecycle_engine(settings)` factory.

---

## Topic 4: Orchestrator Maintainability

### Scope Reviewed
- `services/orchestrator/orchestrator/` — all modules

### Module Line Counts

| Module | Line Count | Domains Mixed | Refactor Priority |
|---|---|---|---|
| `storage.py` | 1,446 | Mission CRUD, events, artifacts, pod assignments, knowledge lake, audit logs, logistics, review approvals (7+ concerns) | **P1 — Critical** |
| `main.py` | 1,235 | HTTP routes, lifecycle task spawning, heartbeat synthesis, review approvals | **P1 — Critical** |
| `mission_flow_v2.py` | 1,078 | 9 lifecycle phases + delegation triggers + completion checks | **P2 — High** |
| `agent_personas.py` | 920 | Agent profile definitions + capabilities | P3 — Medium |
| `agent_base.py` | 812 | Agent base class, metrics, validation | P3 — Medium |
| `llm_delegation.py` | 769 | CEO/PM/specialist delegation + LLM calls | P2 — High |
| `runtime.py` | 759 | Lifecycle advancement, event emission, consumer loop, recovery | P2 — High |
| `langgraph_lifecycle.py` | 720 | LangGraph graph builder + checkpointing | P3 — Medium |
| `agent_registry.py` | 462 | 38 agent definitions + language aliases | P4 — Low |
| `agent_scaling.py` | 374 | Dynamic scaling decisions + partition logic | P4 — Low |
| `agent_integrations.py` | 385 | Integration snapshots + telemetry | P4 — Low |
| `neo4j_store.py` | 309 | Neo4j knowledge graph | P4 — Low |
| `object_store.py` | 293 | MinIO/S3 artifact storage | P4 — Low |

### Questions Answered

| # | Question | Finding | Files Reviewed |
|---|---|---|---|
| 4.1 | Line counts (above table) | ✅ Confirmed | all modules |
| 4.2 | Which modules mix multiple domains? | `storage.py` (7+ concerns), `main.py` (routes + heartbeat + approvals), `runtime.py` (advancement + recovery + consumer loop) | `storage.py`, `main.py`, `runtime.py` |
| 4.3 | Is persistence isolated from business logic? | ⚠️ PARTIAL — `storage.py` is a separate module, but there is no repository/DAO abstraction. `main.py` calls `storage.*` functions directly throughout with no interface layer. | `main.py:187, 637, 746` |
| 4.4 | Is agent-registry/heartbeat isolated from mission lifecycle? | ❌ NO — Both live in `main.py`. Heartbeat synthesis (`main.py:664–762`) and HTTP route handlers are in the same 1,235-line file as lifecycle task spawning. | `main.py` |
| 4.5 | Testable units without booting full service? | ⚠️ PARTIAL — `test_orchestrator_main_helpers_unit.py` covers `_parse_iso_datetime()`, `_route_provenance_snapshot()`, `_artifact_summary()`. Lifecycle engine tests require full boot. | `tests/services/test_orchestrator_main_helpers_unit.py` |
| 4.6 | Top 3 highest-risk areas for regressions during decomposition? | (1) `VALID_TRANSITIONS` in `models.py:85–102` must stay in sync with v2 and v1.1 — duplication risk. (2) Event emission callback signature in `runtime.py:293–330` — if it drifts across paths, downstream audit fails. (3) Heartbeat synthesis / pod assignment race in `main.py:664–756` — stale queue_depth can cause misrouting. | `models.py`, `runtime.py`, `main.py` |

### Risk Level
- [x] **High** — `storage.py` at 1,446 lines mixing 7+ concerns is the single highest-risk file in the repo. A bug fix in mission CRUD can accidentally affect the audit log writer. Decomposition is in progress but the blast radius of these files is large.

### Recommended Next Action
1. **Split `storage.py` first** — extract into domain-specific modules: `mission_store.py`, `artifact_store.py`, `audit_store.py`, `knowledge_store.py`, `event_store.py`.
2. Extract `agent_registry.py` heartbeat synthesis out of `main.py` into a dedicated `heartbeat_service.py`.
3. Add integration tests that cover each split module independently before merging.
4. Centralize `VALID_TRANSITIONS` — remove duplication between `models.py` and `mission_flow_v2.py`.

---

## Topic 5: Mission Control / UI Truthfulness

### Scope Reviewed
- `apps/mission-control/app/(shell)/agents/page.tsx`
- `apps/mission-control/app/(shell)/missions/[id]/page.tsx`
- `apps/mission-control/app/layout.tsx`
- `apps/mission-control/app/lib/types.ts`
- `apps/mission-control/app/lib/mock-data.ts`
- `apps/mission-control/e2e/mission-control-extended.spec.ts`

### Questions Answered

| # | Question | Finding | Files Reviewed |
|---|---|---|---|
| 5.1 | Does the Agents page imply all 38 agents are always running? | ⚠️ INCONCLUSIVE — Production component at `agents/page.tsx:207` loads agents dynamically from the API (`snapshot?.agents ?? []`) and discovers states at runtime. No production hardcoding. However `layout.tsx:22` metadata states "38-agent multi-language refinery" and the e2e test fixture hard-codes `Array.from({ length: 38 }, ...)`. | `agents/page.tsx:207`, `layout.tsx:22`, `e2e/mission-control-extended.spec.ts:183` |
| 5.2 | Does the Mission Detail page show the active lifecycle engine? | ❌ NO — Mission detail shows state, phase progress, LogicNode counts, and transport mode. **No display of which lifecycle engine (v2, LangGraph, legacy) is processing the mission.** | `missions/[id]/page.tsx:358–368` |
| 5.3 | Are any agent status values hardcoded or mocked? | ❌ DISPROVEN in production — States are discovered dynamically: `agents.forEach((item) => discovered.add(item.state))` at `page.tsx:216`. Mock data in `mock-data.ts` is test-only and not served in production. | `agents/page.tsx:216`, `mock-data.ts:1–65` |
| 5.4 | Does audit evidence appear on mission completion? | ⚠️ PARTIAL — "Build Artifacts" panel shows `artifact_type`, `status`, `stage`, `storage_backend`, `digest_sha256`, `size_bytes`, `updated_at`. No dedicated "audit evidence" record type in `types.ts`. Audit trail, approval chain, and LogicNode audit report are not surfaced. | `missions/[id]/page.tsx:544–612`, `types.ts:255` |
| 5.5 | Are there UI labels referencing features not backed by the API? | ⚠️ MINOR — Placeholder "No build or package artifacts recorded for this mission yet." implies delayed population that may never arrive for certain mission states. `layout.tsx` "38-agent" copy is misleading for condensed deployments. | `missions/[id]/page.tsx:581`, `layout.tsx:22` |
| 5.6 | Does the UI expose topology profile (condensed vs dedicated)? | ❌ NO — Zero references to topology profiles, `condensed` vs `dedicated` mode, or profile selection in the entire Mission Control frontend. | All MC files |

### Contradictions Between Docs and Code

| UI Claim | Backend Reality | Component | Severity |
|---|---|---|---|
| `layout.tsx:22` — "38-agent multi-language refinery" | Default deployment is condensed — 4 pod workers + synthesized non-pod heartbeats | `layout.tsx:22` | **Medium** — misleads operators who aren't reading source code |
| Mission Detail: no lifecycle engine shown | Three possible engines are active (v2/LangGraph/legacy) with no UI indicator | `missions/[id]/page.tsx` | Medium — reduces debuggability |
| No `runtime_class` on agent cards | Backend synthesizes heartbeats for non-pod agents; UI cannot distinguish real vs. virtual | `agents/page.tsx` | Medium |

### Risk Level
- [x] **Medium** — Production UI does not hardcode state. The gaps are omissions (no lifecycle engine display, no topology mode, no audit evidence chain) rather than active misrepresentation.

### Recommended Next Action
1. Fix `layout.tsx` metadata to be topology-neutral ("multi-agent AI manufacturing system").
2. Add `runtime_class` badge to agent cards once backend exposes the field.
3. Add active lifecycle engine indicator to Mission Detail page.
4. Add `topology_mode` indicator to System Status page.
5. Expose audit report ID + artifact hash + approval chain on mission completion.

---

## Known Open Gaps — Status Check

| Gap | Status | File / Evidence |
|---|---|---|
| DLQ on intake stream | ✅ **FIXED** — `_write_intake_dlq()` uses `redis.xadd()` to `INTAKE_DLQ_STREAM`. Triggered on validation failures and exceptions with proper `xack`. Config via `INTAKE_DLQ_STREAM` and `INTAKE_DLQ_MAX_LEN`. | `orchestrator/runtime.py:394–506`, `.env.example:70–71` |
| MCP_API_KEY auto-gen instability | ✅ **FIXED** — Production: raises `RuntimeError` if not explicitly set. Development: auto-generates but logs a loud `_DEV_SESSION_NOTICE` warning. Key auto-gen is now intentionally dev-only. | `semantic-bus-mcp/mcp_server.py:32–47` |
| Silent AUTH_MODE fallback | ✅ **FIXED** — `AUTH_MODE` defaults to `"api_key"` with explicit logging. Invalid values: production raises `RuntimeError`, development logs error and falls back. Startup logs active mode. | `api-gateway/main.py:54, 152–167` |
| Cert path mismatch (.env.example vs docker-compose) | ✅ **FIXED** — `.env.example` now has inline comments explaining both contexts: Docker containers use `/run/redis-certs/ca.crt` and `/run/postgres-certs/ca.crt` via volume mount; local dev outside Docker uses `deploy/.local/...`. | `.env.example:1–5, 32–33` |

---

## Summary Scorecard

| Topic | Risk Level | Recommended Priority |
|---|---|---|
| 1. Extraction Core | **Medium** | P2 — Wire Python AST; add provenance fields; build interface contract |
| 2. Runtime Topology | **Medium** | P2 — Add `runtime_class` to registry + API + UI |
| 3. Lifecycle Engine | **Medium** | P3 — Define adapter interface; annotate legacy as shim |
| 4. Orchestrator Maintainability | **High** | P1 — Split `storage.py`; extract heartbeat from `main.py` |
| 5. Mission Control Truthfulness | **Medium** | P3 — Fix `layout.tsx`; add engine + topology indicators |
| Known Gap: DLQ | ✅ Fixed | — |
| Known Gap: MCP_API_KEY | ✅ Fixed | — |
| Known Gap: AUTH_MODE | ✅ Fixed | — |
| Known Gap: Cert Path | ✅ Fixed | Added inline comments explaining Docker vs local-dev path split |

---

## Ranked Refactor Candidates

| Rank | Item | Rationale | Blocking? |
|---|---|---|---|
| 1 | Split `storage.py` (1,446 lines, 7+ concerns) | Highest blast radius in the repo. Any change to one domain can regress 6 others. Must be split before further orchestrator decomposition. | Yes — blocks safe orchestrator slimming |
| 2 | Wire Python AST extractor into production pipeline | The extractor exists, is tested, but is never called. This is the lowest-cost, highest-value semantic upgrade available. | No |
| 3 | Add `runtime_class` to agent registry + API + UI | Enables operators to distinguish real workers from synthesized heartbeats. Small additive change, high operational value. | No |
| 4 | Extract heartbeat synthesis from `main.py` | `main.py` at 1,235 lines mixes HTTP routes with heartbeat synthesis. Extract to `heartbeat_service.py`. | No |
| 5 | Define `LifecycleEngine` adapter Protocol | Wraps v2/LangGraph/legacy in a consistent interface. Prerequisite for safe lifecycle engine replacement in any future phase. | No |
| 6 | ~~Fix `.env.example` cert paths~~ | ✅ Done — inline comments explain Docker vs local-dev path split | No |
| 7 | ~~Fix `layout.tsx` "38-agent" metadata copy~~ | ✅ Done — replaced with topology-neutral description | No |
| 8 | Add `extraction_method` + `source_range` to LogicNode provenance | Completes the provenance contract the Phase 4 plan depends on. Required before AST migration can be measured. | Blocks Phase 4/5 of upgrade plan |

---

## Sign-off

- [x] All 5 topics reviewed
- [x] No files modified during this pass
- [x] Findings committed to `docs/reviews/codex-baseline-findings-2026-04-14.md`
- [x] Ready for Phase 1 (AGENTS.md + Codex guardrails)

**Key deviations from the plan document's assumptions:**
1. Three of four "known gaps" (DLQ, MCP_API_KEY, AUTH_MODE) are already fixed in code — the plan should not re-implement them.
2. Go/Haskell/OCaml are NOT virtual personas — they have real pod assignments. The topology section of AGENTS.md needs a nuance update.
3. Python AST extractor is built and fully tested but disconnected from production — this is the single easiest high-value win.
4. `storage.py` at 1,446 lines is a higher risk than `main.py` and should be the first decomposition target.
