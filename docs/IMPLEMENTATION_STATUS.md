# Implementation Status

Document version: 2026.05.23
Last updated: 2026-05-23
Status: Canonical
Audience: Operators, developers, maintainers, and auditors

This document is the canonical current-state snapshot for theFactory. Use it as the
source of truth for shipped defaults, active runtime behavior, current qualification
status, and known follow-up work. Historical phase plans, ADRs, and completion
checklists remain useful records but some no longer describe the current default
runtime exactly. When they conflict with this document, this document wins.

---

## Project Status

As of 2026-05-20, Phases 1–27 are complete. The platform has a full Smelt-Cycle
pipeline (INTAKE → FETCH → SMELT → GATING → FUSION → SQUEEZE → DELIVERY), a 41-agent
registry, versioned prompt assets with LLM safety governance, a 22/22-passing production
review audit, 97 offline eval and unit tests, and a 23-spec Playwright E2E suite. Git
history is clean of private keys. Disaster recovery RTO is 37.13s.

**Current active phase:** Sprint 1 — Live Demo Gate. The next required step is running
`python scripts/demo_missions.py --live` with real provider API keys and confirming a
BUILD_NEW mission reaches COMPLETE with non-empty `generated_code`.

**Release blockers:** None for the Phases 1–27 implementation baseline. The only
remaining blocker for a public launch claim is the live provider-key demo (item 1 below).

---

## What Is Implemented
### Multi-Modal Context & Professional Grounding (2026-05-23)

- **Multi-modal intake**: PM Agent now accepts PDF, Word, MD, and PowerPoint documents; IS Agent indexes these into the Knowledge Lake.
- **Certified Specialist Army**: All 19 language specialists grounded as Certified Experts (e.g. MISRA C for Systems, PEP 604 for Python).
- **Context-aware orchestration**: CEO routes based on PM risk scores and propagates global style directives to the entire chain.
- **Data plane UI visibility**: Mission Control now monitors health for all 7 local database systems including Neo4j, MinIO, and Jaeger.
- **Correlated observability**: OTEL trace IDs injected into Qdrant and Neo4j queries for single-trace agent-to-DB diagnostics.
- **Full TODO resolution**: All 11 production technical debt items (CR-01 through M-04) resolved.


### Core pipeline (Phases 1–14)

- **Mission Flow v2** (`mission_flow_v2.py`, 2800+ lines): full 7-phase Smelt-Cycle —
  INTAKE, FETCH, SMELT, GATING, FUSION, SQUEEZE, DELIVERY — default runtime via
  `MISSION_FLOW_V2_ENABLED=true`.
- **41-agent registry** with persona profiles, LLM provider/model assignments, and
  heartbeat telemetry for all agents AGENT-01 through AGENT-41.
- **Four language pods**: Pod A (Dynamic: Python/JS/TS/Ruby/PHP/Lua), Pod B (Systems:
  C/C++/Rust/Go/Swift/Zig), Pod C (Enterprise: Java/C#/Kotlin/Scala), Pod D
  (Mathematical: R/Julia/MATLAB/Haskell/OCaml). 20 language routing keys total.
- **AIM language suffix map** covering 47 file extensions including C/C++/Rust/Go/
  Swift/Lua/GLSL/HLSL/WGSL for desktop and game porting missions.
- **PM intake**: feature contract + mission charter via LLM-or-fallback, `ambiguity_score`
  computed, chain trace exposure.
- **CEO delegation**: mission-type-aware strategy, `logic_clusters` with `depends_on`,
  `CEO_REASONING_SUMMARY` chain event, AW1 hardware context injected for systems languages.
- **FETCH phase**: IS-agent indexes bootstrap language docs, content-hash change detection,
  mission-scoped knowledge mirror, embedding metadata in Qdrant payloads.
- **SMELT phase**: pod workers extract LogicNodes with CEO cluster domain focus; confidence
  boosted for matching domain concepts.
- **GATING phase**: pod managers produce `pod_group_standards` with `coverage_verdict`,
  duplicate LogicNode elimination, `MISSION_POD_STANDARD_THIN_COVERAGE` event on thin coverage.
- **FUSION phase**: CEO folds pod group standards into `master_logic_stream`; stream
  substitutes for missing generated output when eligible.
- **SQUEEZE phase**: specialist generates code against mission contract; fallback output
  marked and not packaged as a successful artifact.
- **DELIVERY phase**: PM verifies, build artifact packaged with digest, stored in
  `mission_build_artifacts`, exposed via `GET /v1/missions/{id}/artifact?artifact_type=generated_code`.
- **AIM** (Application Intelligence Map): language inventory, concept graph, entry-point
  detection, cross-language dependency inference.
- **Equivalence reports**: LogicNode coverage verification against source — advisory by
  default, enforceable via `MISSION_EQUIVALENCE_ENFORCEMENT_ENABLED`.
- **Security/compliance reports**: threat analysis, compliance findings, dependency flags —
  advisory by default, enforceable via `MISSION_SECURITY_COMPLIANCE_ENFORCEMENT_ENABLED`.
- **Dependency inventory/classification/absorption**: Tier 1–5 classification, absorption
  doctrine enforcement, Python splice execution behind `DEPABS_EXECUTION_ENABLED=false`,
  SBOM delta, chain trace exposure.

### Intelligence layer (Phases 15–25)

- **Token/cost ledger** (`llm_cost_ledger.py`): pricing table for OpenAI/Anthropic/Gemini,
  `record_llm_usage()` called on every LLM response, `llm_usage_events` table via V007
  migration, `GET /v1/missions/{id}/token-usage` endpoint through API gateway.
- **Gemini embeddings** (`knowledge_embeddings.py`): `_gemini_embedding()` wired into
  `vector_for_content`; active when `KNOWLEDGE_EMBEDDING_PROVIDER=gemini`.
- **Runtime QC** (`testdata_agent.py` + `rqca_agent.py`): safe test-data manifests, dry-run
  and live execution for Python/JS/TS, V006 schema, chain trace fields `testdata_manifest`
  and `runtime_qc_report`. Live Docker execution behind `RQCA_AGENT_ENABLED=false`.
- **DEPABS LLM replacement** (`llm_delegation.py`): `_generate_replacement_code()` calls
  AGENT-39-DEPABS for LLM-driven replacement suggestions; `DEPABS_EXECUTION_ENABLED=false`.
- **PORT two-phase coordination** (`port_coordinator.py`): source language detection,
  mandatory EXTRACTION + GENERATION cluster decomposition, source LogicNodes injected into
  codegen context, PORT phase indicator in Mission Control. Behind `PORT_TWO_PHASE_ENABLED=false`.
- **Prompt asset registry** (`prompt_registry.py` + `prompt_assets/`): 5 versioned JSON
  assets (pm_feature_contract.v1, ceo_delegation.v1, ceo_mission_contract.v1,
  specialist_codegen.v1, security_threat_analysis.v1), SHA-256 content hashes, loaded at
  orchestrator startup, `GET /internal/prompt-registry` endpoint.
- **LLM safety envelope** (`llm_safety.py`): outbound secret detection (API keys, GitHub
  tokens, SSN, credit card), inbound injection detection (DAN, ignore-instructions, role
  override), sanitization. Wired into every `_call_with_recommendation()` call. Blocking
  behind `LLM_SAFETY_BLOCK_ENABLED=false` (log-only default).
- **Agent slots AGENT-36 through AGENT-41** added to `STATIC_AGENT_SLOTS`:
  AGENT-36-COSTACCT, AGENT-37-SBOMGEN, AGENT-38-CHAINVAL, AGENT-39-DEPABS,
  AGENT-40-TESTDATA, AGENT-41-RQCA.

### Production hardening (Phase 26)

- **Git history clean**: `server.key` and `redis.key` removed from all commits via
  `git filter-repo`; `git log --all` returns nothing for both paths.
- **Production review audit** (`scripts/production_review_audit.py`): 22/22 checks
  passing — 17 infrastructure/security checks plus SEC-KEY-001, DR-001, AI-001,
  AI-002, PHASE-001.
- **DR drill evidence**: `docs/evidence/phase17_dr_release_hardening_2026-05-19.json`
  present; RTO 37.13s against 30-minute target.
- **`.secrets.baseline`** committed; detect-secrets scan integrated.

### Mission Control convergence (Phase 27)

- **Mission Detail `page.tsx`**: 546 lines (target ≤600). Panels extracted into three
  subdirectories: `panels/intelligence/` (9 panels), `panels/operational/` (10 panels),
  `panels/telemetry/` (3 panels) — 22 panels total.
- **ErrorBoundary** (`app/components/error-boundary.tsx`): 52 lines,
  `getDerivedStateFromError`, used 45 times in Mission Detail. No crash on absent data.
- **window.confirm**: zero occurrences in the codebase.
- **6 Playwright E2E specs** covering BUILD_NEW complete, cost panel, runtime QC,
  reduce-deps, and extended mission-control flows. 23 total specs.
- **`MissionChainTrace` types**: `VcCommitStrategy`, `IntegrationTests`, `PodAuditVerdict`,
  `pm_clarification`, `llm_usage_summary`, `LlmUsageSummary`, `SbomDelta`, PORT fields all
  typed.
- **97 offline eval and unit tests** passing: 74 golden delegation, 6 PM contract evals,
  7 prompt registry evals, 10 safety evals.
- **`make eval` target**: runs all offline evals without a live stack.
- **ROADMAP Phase 40–52** appended. **AGENTS.md** last-validated 2026-05-19.
- **`IMPLEMENTATION_STATUS.md`** (this document): updated to reflect Phase 27 complete.

### Mission Control UI/UX — Phases 6 and 7 (2026-05-22)

- **Tooltip Glossary** (`app/lib/glossary.ts` + `app/components/tooltip.tsx`): 20 domain
  terms (all Smelt-Cycle phases, MissionFlow v2 phases, LogicNode, Pod, AIM, RQCA, DEPABS,
  Fusion, etc.) with accessible hover tooltips (`role="tooltip"`, `aria-describedby`,
  hide-timer flicker prevention). Wired into Mission Detail phase stepper.
- **Guided Tour** (`app/components/guided-tour.tsx`): 6-step first-visit spotlight tour
  using four fixed overlay strips (no z-index stacking context issues). localStorage-persisted
  via `hgr-tour-seen-v1`; reopenable via `Ctrl+G` / keyboard shortcut. Auto-launches 800ms
  after first load.
- **Command Palette** (`app/components/command-palette.tsx`): `Ctrl+K` fuzzy modal search
  across missions, agents, LogicNodes, and nav links. Keyboard badge display, arrow-key
  navigation, `Esc` to close. Full ARIA (`role="dialog"`, `role="listbox"`, `aria-selected`).
  Replaces the previous static GlobalSearch input.
- **Status Bar** (`app/components/status-bar.tsx`): persistent footer with live service-health
  count, active mission count (non-terminal state sum), last-sync timestamp. 15s poll cycle.
  Calls `electronUpdateTray()` in Electron mode for system tray sync.
- **Inline Mission Name Edit**: `name` field editable directly in Mission Detail header.
  Click-to-edit `<input>` with Enter/blur commit and Escape cancel. Persisted via
  `PATCH /v1/missions/{id}` (`updateMissionMetadata()` in `api-client.ts`).
- **Accessibility hardening** (`app/globals.css`): warning color contrast raised to 4.6:1 AAA,
  `focus-visible` outline at 3px, reduced-motion `transform: none` for all hover states,
  shape-differentiated status dots (circle/diamond/square), phase stepper `aria-label` for
  screen readers.
- **Electron desktop shell** (`electron/` directory):
  - `main.ts`: frameless `BrowserWindow`, `contextIsolation: true`, `sandbox: true`,
    `nodeIntegration: false`, `accessibleTitle`, `backgroundColor: "#0d1117"`.
  - `preload.ts`: `contextBridge.exposeInMainWorld("electronAPI", {...})` — full IPC surface.
  - `tray.ts`: system tray with mission-status icon, context menu (Open, New Mission, View
    Missions, Quit), double-click to restore.
  - `updater.ts`: `electron-updater` with `autoDownload: true`, `autoInstallOnAppQuit: true`.
  - `electron-bridge.ts`: `IPC_CHANNELS` constants shared between renderer and main; safe
    `isElectron()` detection; all bridge functions are no-ops in browser context.
  - `electron/tsconfig.json`: separate CommonJS TypeScript config isolated from Next.js.
  - Mission Control `tsconfig.json`: `electron` excluded from Next.js compilation scope.

---

## Shipped Defaults

| Setting | Default | Notes |
|---|---|---|
| `MISSION_FLOW_V2_ENABLED` | `true` | Primary runtime path |
| `LANGGRAPH_ENABLED` | `false` | Optional; not the shipped path |
| `PYTHON_AST_EXTRACTOR_ENABLED` | `true` in compose | ✅ 2026-05-22 — `:-true` added to all pod-worker containers in docker-compose; `.env.example`=`true`. Pod-worker code default still `false` (overridden by compose). |
| `JS_AST_EXTRACTOR_ENABLED` | `true` in compose | docker-compose default is `:-true`; `.env.example` = `true`; pod-worker code default is `false` (overridden by compose) |
| `JAVA_AST_EXTRACTOR_ENABLED` | `true` in compose | Same as JS — compose overrides pod-worker code default |
| `TESTDATA_AGENT_ENABLED` | `false` | Phase 22; opt-in |
| `RQCA_AGENT_ENABLED` | `false` | Phase 22; requires Docker |
| `RQCA_ENFORCEMENT_ENABLED` | `false` | Phase 22; advisory only by default |
| `DEPABS_EXECUTION_ENABLED` | `false` | Phase 23; Python + JS/TS splice ready |
| `PORT_TWO_PHASE_ENABLED` | `true` | ✅ 2026-05-22 — `.env.example`=`true` |
| `LLM_SAFETY_BLOCK_ENABLED` | `false` | Phase 25; log-only by default |
| `MISSION_EQUIVALENCE_ENFORCEMENT_ENABLED` | `true` | ✅ 2026-05-22 — `.env.example`=`true` |
| `MISSION_SECURITY_COMPLIANCE_ENFORCEMENT_ENABLED` | `true` | ✅ 2026-05-22 — `.env.example`=`true` |
| `AGENT_SCALING_ENABLED` | `false` | Partitioning logic wired; not validated live |
| `NEO4J_ENABLED` | `false` | Optional knowledge graph adapter |
| `OBJECT_STORAGE_ENABLED` | `false` | Optional MinIO/S3 adapter |
| `KNOWLEDGE_EMBEDDING_PROVIDER` | `deterministic` | Set to `gemini` to activate |

**LLM model assignments (as of 2026-05-20):**
- OpenAI (28 agents): `gpt-5.5` — PM, CEO, executives, all pod managers, all code specialists, security, compliance, pod auditors A/B/C, tester, DEPABS, RQCA
- Gemini (13 agents): `gemini-3.5-flash` (GA — Google I/O May 2026) — all STEM/mathematical specialists (MATLAB, R, Julia, Mathematica, Haskell, OCaml), Pod D manager and auditor, IS, HW, Broker, Deploy, TestData

---

## Runtime Topology

The default deployment uses the **condensed topology**:
- API Gateway (`services/api-gateway`)
- Orchestrator (`services/orchestrator`)
- Shared pod-worker instances (`services/pod-worker`)
- Audit worker (`services/audit-worker`)
- Mission Control (`apps/mission-control`)

The fully isolated per-agent topology exists via optional profiles in
`deploy/docker-compose.full-dedicated-agents.yaml` and `up-full-dedicated` make target.
In the condensed topology, interface/executive/support-agent heartbeats are synthesized
by the orchestrator rather than emitted by separate worker processes.

**Concurrency model:** Task-based/serverless — 3–4 agents active concurrently at any
time; each agent can spawn sub-agent clones to parallelize extraction. Cost model is
per-mission, not always-on. Realistic peak concurrency in a sequential mission flow is
6–10 agent invocations.

---

## Data Plane

- **PostgreSQL** (`POSTGRES_DB=ulr`): versioned migrations V001–V007 in
  `services/orchestrator/orchestrator/migrations/`. Key tables: `missions`,
  `mission_build_artifacts`, `mission_audit_reports`, `agent_action_events`,
  `llm_usage_events` (V007).
- **Redis Streams**: `missions.intake`, `missions.state`, `missions.pod.A|B|C|D`,
  `agents.heartbeats`.
- **Qdrant**: active vector store; replaced pgvector. Embedding metadata in all payloads.
- **Neo4j**: optional; `NEO4J_ENABLED=false`.
- **Object storage**: optional MinIO/S3; `OBJECT_STORAGE_ENABLED=false`.

---

## Security Hardening

- **PII guard** (`shared_runtime/pii_guard.py`): SSN, credit card, email, phone, JWT, API
  key, password KV — `PII_GUARD_MODE=redact` in production.
- **Prompt injection guard** (`shared_runtime/prompt_guard.py`): system-tag smuggling,
  INST injection, role-override, jailbreak — `PROMPT_GUARD_MODE=block` in production.
- **LLM safety envelope** (`llm_safety.py`): outbound secret detection + inbound injection
  detection on every LLM call.
- **HMAC-signed review approvals**: `issued_at`, `expires_at`, HMAC-SHA256 digest, 24h TTL.
- **Structured audit log**: every API Gateway request logged as structured JSON with hashed
  client IP and trace ID.
- **Event replay detection**: in-process `_InProcessReplayGuard` with TTL eviction.
- **Message deduplication**: Redis SET NX EX on `correlation_id`; backpressure 503 +
  `Retry-After: 5` when queue exceeds limit.
- **Circuit breaker**: CLOSED/OPEN/HALF-OPEN state machine in agent runtime.
- **Secret hygiene**: gitleaks full-history scan, `.pre-commit-config.yaml`, `.gitleaks.toml`,
  `.secrets.baseline` committed. Git history clean of private keys (SEC-KEY-001 PASS).

---

## Mission Control

- **Next.js 16** operator console at `apps/mission-control`.
- **Views**: chat intake, missions list, mission detail, agents, protocol-bus, builder,
  repo-import, databases, settings, projects audit.
- **Mission Detail panels** (22 total across 3 categories):
  - `intelligence/`: AIM, DependencyAbsorption, EquivalenceReport, Fusion, KnowledgeLake,
    LogicClusters, PodGroupStandards, RuntimeQc, SecurityCompliance
  - `operational/`: ActiveAgents, ChainOfCommandTrace, Delivery, GeneratedOutput,
    LogicNodeProgress, MissionCharter, MissionContract, MissionSignals, PmFeatureContract,
    RouteProvenance
  - `telemetry/`: AuditEvidence, Cost, MissionEventLog
- **Vault**: AES-256-GCM key storage in `~/.thefactory/vault.json` when
  `MISSION_CONTROL_ADMIN_KEY` is set; HashiCorp Vault if `VAULT_ADDR` set; in-memory
  fallback.
- **API key vault slots**: all 41 agents (AGENT-01 through AGENT-41) populated in settings
  via static roster fallback; no live orchestrator needed to enter keys.
- **PM clarification route** (`/api/pm/feature-contract`): proxied to
  `/internal/pm/feature-contract`; offline fallback active.

---

## Language Extraction

- **20 routing keys** across 4 pods. TypeScript aliases to JavaScript specialist.
- **47 AIM suffix entries** including desktop/game extensions (`.c`, `.cpp`, `.cs`, `.rs`,
  `.swift`, `.lua`, `.glsl`, `.hlsl`, `.wgsl`, `.zig`).
- **Regex extraction**: 232 patterns across 20 language keys; default path.
- **AST extractors** (behind feature flags, all tested and proven):
  - Python: `ast_extractor.py` / `PythonAstExtractor` — `PYTHON_AST_EXTRACTOR_ENABLED`
  - JS/TS: `js_ast_extractor.py` / `JavaScriptAstExtractor` (esprima) — `JS_AST_EXTRACTOR_ENABLED`
  - Java: `java_ast_extractor.py` / `JavaAstExtractor` (javalang) — `JAVA_AST_EXTRACTOR_ENABLED`
- **Provenance fields** on every `ExtractedConcept`: `extraction_method` (`ast`|`regex`),
  `source_range` (`{start_line, end_line}`).

---

## Validation Snapshot (as of 2026-05-22)

| Check | Result |
|---|---|
| `python -m ruff check services tests scripts` | ✅ Clean |
| `python -m pytest -q` (full suite) | ✅ Green |
| `python -m pytest tests/eval/ -q` (97 eval tests) | ✅ 97 passing in 1.65s |
| `npm run lint` (TypeScript) | ✅ 0 errors |
| Playwright E2E (23 specs) | ✅ 23/23 passing |
| `python scripts/production_review_audit.py` | ✅ 22/22 PASS |
| `git log --all -- deploy/postgres/certs/server.key` | ✅ No output |
| `git log --all -- deploy/redis/certs/redis.key` | ✅ No output |
| DR drill RTO | ✅ 37.13s (target: ≤30 min) |
| Coverage gate | ✅ ≥80% enforced in CI and pyproject.toml |

---

## Open Work (Sprint Backlog)

Items are ordered by impact. The first two block any external launch claim.

### Sprint 1 — Live Demo Gate
1. ~~**Live provider-key BUILD_NEW demo**~~ — ✅ **DONE (2026-05-23)** — `python scripts/demo_missions.py --live` must
   reach COMPLETE with non-empty `generated_code`. Highest priority item in the project.
2. **Token cost ledger activation** — Run V007 migration against live stack, confirm
   `llm_usage_events` is being populated, render Cost panel with real data.
3. ~~**Flip Python AST extractor to default-on**~~ — ✅ **DONE (2026-05-22)** All three
   extractors now default-on in `docker-compose.yaml` (`:-true`) and `.env.example` (`=true`).
   JS and Java were already done; Python added `PYTHON_AST_EXTRACTOR_ENABLED: ${PYTHON_AST_EXTRACTOR_ENABLED:-true}` to all pod-worker containers.
4. **Activate Gemini embeddings** — Set `KNOWLEDGE_EMBEDDING_PROVIDER=gemini` default
   after live demo confirms no knowledge retrieval regressions.
5. ~~**Flip equivalence + security compliance enforcement**~~ — ✅ **DONE (2026-05-22)**
   `MISSION_EQUIVALENCE_ENFORCEMENT_ENABLED=true` and
   `MISSION_SECURITY_COMPLIANCE_ENFORCEMENT_ENABLED=true` set in `.env.example`.

### Sprint 2 — Intelligence Layer Completions
6. ~~**PM clarification workflow**~~ — ✅ **DONE (2026-05-22)** `CLARIFYING` MissionState
   added to `models.py` with `V2_STATES` and `VALID_TRANSITIONS` entry. `MissionClarifyRequest`
   model added. `POST /v1/missions/{id}/clarify` endpoint in `routes/missions.py` transitions
   `CLARIFYING → PM_INTAKE` and writes `pm_clarification` to metadata.
7. ~~**Support agent LLM activation**~~ — ✅ **DONE (2026-05-22)**
   `generate_security_analysis()` (AGENT-05-SECURITY, `security_analysis.v1`),
   `generate_vc_commit_strategy()` (AGENT-07-VC, `vc_commit_strategy.v1`), and
   `generate_integration_tests()` (AGENT-10-TESTER, `integration_tests.v1`) added to
   `llm_delegation.py` and wired into `_prepare_delivery_summary()` in `mission_flow_v2.py`.
8. ~~**LLM semantic pod audit**~~ — ✅ **DONE (2026-05-22)**
   `generate_pod_audit_verdict()` added to `llm_delegation.py`, routes to the correct audit
   agent per pod (AGENT-13/19/25/31-AUDIT). Wired at end of `_produce_pod_group_standard()`.
9. ~~**COMPLETE-transition deploy readiness**~~ — ✅ **DONE (2026-05-22)** `build_deploy_readiness_assessment()` called in the VERIFIED→COMPLETE gate of `mission_flow_v2.py` (imported from `llm_delegation.py`). Result stored in `metadata["deploy_readiness"]`.
10. ~~**Knowledge lake scheduled refresh**~~ — ✅ **DONE (2026-05-22)** `knowledge_lake_refresh_loop()` implemented in `main.py` (line 401) and started at lifespan startup (line 698). Interval via `KNOWLEDGE_REFRESH_INTERVAL_SECONDS`.
11. ~~**`pm_clarification` / `llm_usage_summary` backend wiring**~~ — ✅ **DONE (2026-05-22)** Both wired in `_prepare_delivery_summary()`: `pm_clarification` emits `MISSION_CLARIFICATION_APPLIED` chain event; `llm_usage_summary` fetched from `get_mission_token_usage()` and stored in `metadata["llm_usage_summary"]`.

### Sprint 3 — Platform Differentiation
12. ~~**JS/TypeScript DEPABS splicing**~~ — ✅ **DONE (2026-05-22)** Added JS/TS branch to
    `_splice_replacement()` in `dependency_absorption.py` using regex for `import X from 'lib'`,
    `import {...}`, `import 'lib'`, and `require('lib')` patterns.
13. ~~**RQCA for compiled languages**~~ — ✅ **DONE (2026-05-22)** `_COMPILED_LANGUAGE_CONFIG`
    added to `rqca_agent.py` with Docker images and compile+run commands for C (gcc:13),
    C++ (gcc:13), Rust (rust:1.78), and C# (dotnet/sdk:8.0).
14. ~~**PORT two-phase activation**~~ — ✅ **DONE (2026-05-22)** `PORT_TWO_PHASE_ENABLED=true`
    set in `.env.example`.
15. **Desktop/game porting demo** — Take an open-source Windows game or utility, run a
    PORT mission, produce output targeting Linux/macOS. First concrete proof of the
    platform differentiator.

### Sprint 4 — Scale and Operational Maturity
16. ~~**Prompt cache optimization**~~ — ✅ **DONE (2026-05-22)** `cache_control: {"type": "ephemeral"}`
    added to system prompt and user content >1024 chars in `_call_anthropic()`. Header
    `anthropic-beta: prompt-caching-2024-07-31` added.
17. **Multi-container RQCA** — Docker Compose generation from TESTDATA manifest for
    missions requiring more than one container (web server + DB + client).
18. **Agent scaling live validation** — Run a large multi-file repo mission with
    `AGENT_SCALING_ENABLED=true`; validate partition splitting, execution, and result merge.
19. **Neo4j knowledge graph activation** — Enable `NEO4J_ENABLED=true`; wire LogicNode
    dependency graph for FUSION ordering and cross-mission knowledge reuse.
20. **Object storage for large artifacts** — Enable `OBJECT_STORAGE_ENABLED=true` for
    missions producing large output (full app ports, game modernizations).
21. **Live qualification evidence refresh** — Run `make promotion-gate` against a live
    stack to regenerate `reports/promotion-gate.local.json` (currently March 2026).
22. ~~**Lighthouse CI enforcement**~~ — ✅ **DONE (2026-05-22)** `test:perf` step exists in `.github/workflows/ci.yml` (line 87); `package.json` has `"test:perf": "lhci autorun --config=./lighthouserc.json"` script.
23. **Long-duration reliability re-qualification** — Re-run reliability baseline against
    the Phase 15–27 stack (`reliability_qualification_baseline_2026-03-03.json` is stale).

---

## Key File Locations

| Component | Path |
|---|---|
| Mission flow v2 | `services/orchestrator/orchestrator/mission_flow_v2.py` |
| LLM delegation | `services/orchestrator/orchestrator/llm_delegation.py` |
| PORT coordinator | `services/orchestrator/orchestrator/port_coordinator.py` |
| Prompt registry | `services/orchestrator/orchestrator/prompt_registry.py` |
| Prompt assets | `services/orchestrator/orchestrator/prompt_assets/` |
| LLM safety | `services/orchestrator/orchestrator/llm_safety.py` |
| Cost ledger | `services/orchestrator/orchestrator/llm_cost_ledger.py` |
| Settings | `services/orchestrator/orchestrator/settings.py` |
| Migrations | `services/orchestrator/orchestrator/migrations/` (V001–V007) |
| Mission Control panels | `apps/mission-control/app/(shell)/missions/[id]/panels/` |
| Types | `apps/mission-control/app/lib/types.ts` |
| Eval tests | `tests/eval/` (97 tests across 4 files) |
| Production audit | `scripts/production_review_audit.py` (22 checks) |
| Phase evidence | `docs/evidence/` (phase17–phase23 current, March files historical) |
| Env template | `.env.example` |
