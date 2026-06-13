# Implementation Status

Document version: 2026.06.13
Last updated: 2026-06-13
Status: Canonical
Audience: Operators, developers, maintainers, and auditors

This document is the canonical current-state snapshot for theFactory. Use it as the
source of truth for shipped defaults, active runtime behavior, current qualification
status, and known follow-up work. Historical phase plans, ADRs, and completion
checklists remain useful records but some no longer describe the current default
runtime exactly. When they conflict with this document, this document wins.

---

## Project Status

**Version: v1.2.0** (current baseline with Gemini-first model routing update,
2026-06-13).

As of 2026-06-13, Phases 1–27 are complete. The platform has a full Smelt-Cycle
pipeline (INTAKE → FETCH → SMELT → GATING → FUSION → SQUEEZE → DELIVERY), a 41-agent
registry, versioned prompt assets with LLM safety governance, a 22/22-passing production
review audit, 97 offline eval and unit tests, and a 23-spec Playwright E2E suite. Git
history is clean of private keys. Disaster recovery RTO is 37.13s.

**Current active phase:** Gemini-first operator validation. The next required
step is running the local stack with a real Gemini key and confirming a
BUILD_NEW mission reaches COMPLETE with non-empty `generated_code`.

**Release blockers:** None for the Phases 1–27 implementation baseline. The only
remaining blocker for a public launch claim after the model-routing update is a
fresh live Gemini provider-key demo.

---

## What Is Implemented

### Gemini-first model routing update (2026-06-13)

- All 41 agents default to `gemini/gemini-3.5-flash` with high thinking.
- Mission Control Settings exposes a 3-model selector for vault-slot testing:
  ChatGPT 5.5, Claude Opus 4.8, and Gemini Flash 3.5.
- Vault slot metadata persists provider and model selection alongside secret
  status; key values remain redacted.
- Gateway preview/model validation allows only the approved 3-model catalog.
- Local validation passed focused Ruff checks, targeted backend tests for agent
  integrations and settings, Mission Control lint/test/build, and Docker image
  builds for API Gateway, Orchestrator, and Mission Control.

### v1.2.0 Improvement Batch (2026-05-30)

Ten correctness, consistency, and quality improvements landed across PRs #185–#194:

- **#185 — Agent count reconciliation**: Reconciled the agent count to **41** throughout
  all docs and code; removed conflicting tallies.
- **#186 — Module decomposition**: Split `llm_delegation.py` (3,493 lines) and
  `mission_flow_v2.py` (3,161 lines) into cohesive per-provider / per-phase module packages.
- **#187 — Go/Haskell/OCaml specialists**: Implemented concrete `SpecialistAgent`
  subclasses for Go, Haskell, and OCaml — these were previously falling back silently to
  `BaseAgent`.
- **#188 — MCP dedup/backpressure hardening**: Wired MCP replay detection (409 on duplicate
  correlation-id); replaced `except/pass` with fail-closed **503** on Redis errors for dedup
  and backpressure; backpressure now checks all channels.
- **#189 — Unified envelope contract**: Unified the MCP envelope and
  `event.envelope.schema.json` into a single shared contract; replaced hand-rolled validation
  with `jsonschema.validate()` in the orchestrator.
- **#190 — Protocol bus rename**: Renamed `semantic-bus-mcp` → `protocol-bus-mcp` throughout
  (service, routes, UI, docs, env vars) — routing is lexical, not semantic.
- **#191 — Removed committed artifacts**: Removed committed generated artifacts
  (`coverage.xml`, `ruff_errors.txt`, `.secrets.baseline`, `reports/`) from VCS; added to
  `.gitignore`; CI already archives them as build artifacts.
- **#192 — runtime.py coverage**: Raised the `runtime.py` test coverage floor from 60% → 80%;
  `runtime.py` is now at **100% line / 99% branch** coverage.
- **#193 — Typed API client + real status codes**: Replaced all `any` types in
  `api-client.ts` with OpenAPI-generated types; gateway proxy now forwards real HTTP status
  codes (404/500/503) instead of `200` + `__gateway_error`.
- **#194 — Unified agent personas**: Consolidated `agent_personas.py` from ~10 parallel dicts
  into a unified `AgentPersona` dataclass per agent; added a drift-prevention test.

#### Known gaps resolved in this batch

The following previously-tracked known gaps are now closed:

- ~~GO/HASKELL/OCAML specialists silently falling back to `BaseAgent`~~ — ✅ Fixed in #187
- ~~MCP replay detection not wired / `except/pass` on Redis~~ — ✅ Fixed in #188
- ~~Divergent envelope schemas~~ — ✅ Fixed in #189
- ~~Committed generated artifacts~~ — ✅ Fixed in #191
- ~~`runtime.py` 60% coverage floor~~ — ✅ Fixed in #192
- ~~`any` types in `api-client.ts` / gateway `200`-on-error~~ — ✅ Fixed in #193

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
- Historical phase log updated through Phase 52. **AGENTS.md** last-validated 2026-05-19.
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
| `KNOWLEDGE_EMBEDDING_PROVIDER` | `gemini` in local env template | Gemini embeddings active when `GEMINI_API_KEY` is set |
| `LLM_PROVIDER` | `gemini` | Default LLM provider for all agent routes |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Default model for all 41 agents |
| `GEMINI_THINKING_LEVEL` | `high` | Default effort for Gemini route |
| `OPENAI_MODEL` | `gpt-5.5` | Available in Mission Control model selector only |
| `OPENAI_REASONING_EFFORT` | `high` | Default effort for OpenAI route |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | Available in Mission Control model selector only |
| `ANTHROPIC_THINKING_BUDGET_TOKENS` | `8192` | High-effort Anthropic thinking budget |

**LLM model assignments (as of 2026-06-13):**
- Gemini (41 agents): `gemini-3.5-flash` with high thinking.
- Mission Control selectable non-default routes: `gpt-5.5` and
  `claude-opus-4-8`.

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
- **Settings vault model selector**: each API key slot can store one of the
  approved provider/model routes: ChatGPT 5.5, Claude Opus 4.8, or Gemini Flash
  3.5. Gemini Flash 3.5 is the runtime default for all agents.
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

## Validation Snapshot (as of 2026-06-13)

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
| `runtime.py` per-module coverage floor | ✅ Raised 60% → 80% (#192); actual 100% line / 99% branch |
| Gemini-first focused checks | ✅ Ruff, targeted pytest, Mission Control lint/test/build, and Docker image builds passed |

---

## Current Backlog

The archived sprint backlog is no longer the source of truth. Use this section
and `docs/CURRENT_TODO.md` for active work.

### Completed today (2026-06-13)

- Routed all 41 agents to Gemini Flash 3.5 with high thinking and added the
  Mission Control 3-model selector for ChatGPT 5.5, Claude Opus 4.8, and Gemini
  Flash 3.5.
- Updated active docs to match the Gemini-first runtime and archived superseded
  roadmap, backlog, phased-update, release-completion, reliability, and dated
  runtime-mapping documents under `docs/archive/2026-06-13/`.
- Regenerated the current repository build map as
  `docs/REPOSITORY_BUILD_MAP_2026-06-13.md`.
- Fixed stale model-inventory test expectations so CI no longer expects OpenAI
  defaults after the Gemini-first routing update.
- Hardened CI production signaling so Docker build validation, SBOM generation,
  Electron E2E smoke, and Release Trust are no longer silently skipped on
  production refs.

### Production blockers

1. **Fresh Gemini live mission proof**: run the local stack with a real
   `GEMINI_API_KEY`, submit a BUILD_NEW mission, and capture evidence that the
   mission reaches COMPLETE with non-empty LLM-generated output.
2. **CI green after production-gate hardening**: confirm the post-`867d3ec`
   GitHub Actions run completes with all production-critical gates running and
   passing.
3. **Repository-host protections**: enforce branch protection, required status
   checks, secret scanning, and release attestation verification in GitHub
   settings.
4. **Production-environment evidence**: produce target-environment DR,
   retention, backup/restore, and operational evidence outside the local repo.
5. **Legal/policy approval**: review and approve privacy, terms, and external
   publication policy documents before partner-facing release.

### Non-blocking validation backlog

- Run a PORT mission against a real open-source Windows game or utility and
  capture cross-platform output evidence.
- Run agent-scaling live validation with `AGENT_SCALING_ENABLED=true` on a
  multi-file repository mission.
- Re-run long-duration reliability qualification against the current
  Gemini-first, production-gate-hardened baseline.

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
