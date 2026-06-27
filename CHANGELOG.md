# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased]

### Active Docs Reconciliation (2026-06-27)

#### Changed
- Rewrote the active current-state docs (`CURRENT_TODO.md`,
  `HANDOFF_CURRENT.md`, and `IMPLEMENTATION_STATUS.md`) so older phase notes
  no longer appear as active priorities.
- Kept Phase 13 backend/API smoke as the current proof point and moved the
  remaining UI, failure-injection, provider-fallback, `make validate`,
  `INF-008`, and Phase 8 coverage items into explicit current gaps.
- Archived superseded phase, legacy, and duplicate enterprise documents under `docs/archive/2026-06-27/` and removed them from the active docs index.

### Documentation Current-State Cleanup (2026-06-27)

#### Changed
- Added `docs/README.md` as the GitHub docs landing page with current
  application status, proof points, remaining gaps, and navigation.
- Updated the root README and documentation index to reflect the Phase 13
  backend/API smoke proof, the remaining UI/failure/fallback validation gaps,
  and the current `22/23` production-audit baseline.

### Audit Phase 13 End-to-End Smoke (2026-06-27)

#### Fixed
- Added `MISSION_RUNTIME_QC_SKIPPED` and `MISSION_RUNTIME_QC_BLOCKED` to the
  orchestrator `MissionEvent` type so persisted runtime-QC lifecycle events do
  not crash mission event and chain-trace readers.

#### Added
- Added `scripts/phase13_smoke.py` and `make phase13-smoke` for the backend
  Phase 13 smoke path: readiness probes, mission creation, authenticated mission
  polling, event/chain-trace validation, build-artifact retrieval, and Python
  syntax validation with `ast.parse()`.
- Committed the latest Phase 13 smoke evidence at
  `docs/evidence/phase13_smoke_latest.json`.

#### Validation
- `python scripts\phase13_smoke.py --timeout-seconds 240 --poll-seconds 5 --output-file docs\evidence\phase13_smoke_latest.json`
- `python -m pytest -o addopts= tests\scripts\test_phase13_smoke.py tests\services\test_type_annotations.py --basetemp .pytest-tmp`
- `python -m ruff check scripts\phase13_smoke.py tests\scripts\test_phase13_smoke.py services\orchestrator\orchestrator\models.py tests\services\test_type_annotations.py`

### Audit Phase 12 Documentation Drift (2026-06-26)

#### Changed
- `make validate` now runs current-source documentation validation and a
  non-mutating OpenAPI drift check before schema/catalog/test gates.
- `scripts/export_openapi.py` now supports `--check`, which fails when committed
  OpenAPI snapshots differ from the current FastAPI apps and tells maintainers to
  regenerate the specs.
- Refreshed `docs/openapi/orchestrator.v1.json` after the new check identified
  drift from the current orchestrator app.
- Production audit check `DOC-006` now verifies Phase 12 documentation drift
  controls: current top-level docs, Codex standards, OpenAPI snapshots, and
  validation wiring.
- Added public-docstring validation for `shared_runtime/*.py` and
  `services/orchestrator/orchestrator/storage_*.py`, then documented the public
  storage/shared-runtime functions covered by that gate.
- Reconciled architecture diagrams to the live `MISSION_FLOW_V2_ENABLED=true`
  default and the current 41-agent registry, including AGENT-36-GO,
  AGENT-37-HASKELL, AGENT-38-OCAML, and AGENT-39 through AGENT-41 support
  capabilities.
- Added current metadata, validation commands, and active breaking-change
  coverage to `MIGRATION.md`.

#### Validation
- `python scripts/validate_documentation.py`
- `python scripts/export_openapi.py --check`
- `python scripts/production_review_audit.py`
- `python -m pytest -o addopts= tests\scripts\test_production_review_audit.py --basetemp .pytest-tmp`
- `python -m ruff check scripts\export_openapi.py scripts\production_review_audit.py tests\scripts\test_production_review_audit.py`

### Application Scope Cleanup and Fallback Visibility (2026-06-21)

#### Changed
- Removed the tracked `sites/thefactory-site` marketing website package from the
  application worktree so current development stays focused on Mission Control
  and runtime services.
- Mission Control chat now preserves PM feature-contract degraded/fallback
  metadata and displays a warning in the Feature Contract panel when planning
  output is fallback/degraded instead of confirmed live LLM output.

#### Notes
- The removed site was not part of the application runtime.
- A fresh app run is still required to verify PM launch behavior from `/chat`.

#### Validation
- `npm --prefix apps\mission-control run lint`
- `npm --prefix apps\mission-control run build`
- `python -m pytest tests\services\test_mission_flow_v2.py tests\services\test_runtime_unit.py -q`
- `git diff --check`

### MissionFlow V2 Clarification and Artifact Visibility Rebuild (2026-06-18)

#### Fixed
- Normal ready-path MissionFlow V2 no longer emits `MISSION_CLARIFYING`; ready missions now proceed directly from `PM_INTAKE` to `MISSION_FETCH`.
- Runtime QC skipped paths now persist `runtime_qc_report` plus `MISSION_RUNTIME_QC_SKIPPED`, making disabled TESTDATA/RQCA behavior visible in mission detail and event history.
- Mission Detail generated-output panel now fetches build artifact detail records, displays filename/storage/status/size/digest, and clarifies that generated code is database-backed unless explicitly exported.
- Runtime QC panel now displays skipped QC with the configured reason.

#### Validation
- `python -m pytest tests\services\test_mission_flow_v2.py tests\services\test_runtime_unit.py -q`
- `python -m ruff check ...`
- `npm --prefix apps\mission-control run lint`
- `npm --prefix apps\mission-control run build`
- `git diff --check`
- Full-dedicated Docker images rebuilt for orchestrator, API gateway, Mission Control, pod workers, and dedicated agents.

### Public README Development Status Correction (2026-06-18)

#### Changed
- Updated the public README to state that theFactory is still in active
  development and is not production-ready.
- Replaced production-readiness language with the current application status:
  PM/LLM routing is partially proven, but the PM chat to completed mission path
  still needs a fresh end-to-end run to `COMPLETE` with non-empty generated
  artifacts.
- Added the current highest-priority issues directly to the README so public
  readers see the active blockers before interpreting architecture sections as
  release claims.

### PM Launch Gate and Mission Control Report Fixes (2026-06-18)

#### Fixed
- **PM clarification responses could still be launched** — Mission Control now
  withholds the launchable Feature Contract when the PM route returns clarifying
  questions, preventing an operator from confirming a mission that PM already
  marked as not ready.
- **Confirmed launches still looked like drafts to mission intake** — explicit
  Feature Contract launch now compacts the PM conversation context and persists
  `user_intent: finalize_plan`, `launch_confirmed_at`, and
  `launch_source: feature-contract-confirmation` in mission metadata.
- **FastAPI validation failures surfaced as opaque 422s** — the Mission Control
  API client now converts FastAPI validation arrays into actionable messages and
  tests cover mission creation idempotency plus readable 422 errors.
- **Mission Control report findings** — the global 404 now renders inside the
  Mission Control shell; stale `/history`, `/logic-nodes`, and `/repo-import`
  paths redirect to the canonical shell routes; the header action now says `View
  Missions`; PM chat history rows now include persisted preview/timestamp
  metadata.

#### Validation
- `npm --prefix apps\mission-control run lint`
- `npm --prefix apps\mission-control test -- app/api/gateway/[...path]/route.test.ts app/lib/api-client.test.ts`
- `npm --prefix apps\mission-control run build`
- `git diff --check`
- Docker image rebuilt: `deploy-mission-control:latest`

### PM Chat Launch Confirmation Attempt (2026-06-18)

#### Changed
- `edb7846` attempts to treat proceed-style replies, including `procced` and
  `procede`, as mission launch confirmation when a Feature Contract already
  exists, instead of sending another PM/preview request.

#### Notes
- The change passed `npm --prefix apps\mission-control run lint`,
  `npm --prefix apps\mission-control run build`, and `git diff --check`, but the
  operator reported the live retest still did not work. Treat this as an
  attempted fix that needs request/response capture on the next run.
- After the failed retest, the app was stopped and rebuilt: local Mission Control
  production output plus Docker images for `orchestrator`, `api-gateway`, and
  `mission-control` were rebuilt. The stack was left stopped.

### PM Chat Context and Mission Launch Handoff (2026-06-18)

#### Fixed
- **PM chat had useful context, but mission launch lost it** — Mission Control
  now sends compact PM conversation context, decision memory, working contract,
  attachment labels, and finalize intent into PM feature-contract generation
  (`525b930`).
- **Long mission briefs were truncated before mission intake** — mission launch
  now builds the launch prompt from full user-authored messages with a larger cap
  and stores `conversation_context` plus `user_intent` in mission metadata.
  Mission-flow v2 intake forwards those fields to PM contract generation
  (`37f0779`).
- **Operations status false negative** — Mission Control operations callers now
  use gateway-accepted minimum limits instead of `0`, removing the `422` that
  mislabeled a healthy runtime as offline (`525b930`).

#### Notes
- The live Iron Meridian mission
  `mission-c228332b-4f4e-4941-8e52-eb7494627045` paused in `CLARIFYING` because
  the pre-fix prompt was truncated at `Defeat c`. Use a fresh mission after
  restart to verify the new launch path.

### PM/LLM Delegation Workflow Fixes (2026-06-17)

#### Fixed
- **PM agent / missions produced canned 1 KB stubs** — root-caused to a chain of
  LLM-delegation defects, not the data plane:
  - `LLM_PROVIDER=gemini` was overridden for OpenAI-pinned agent profiles whenever
    an OpenAI key was present, forcing `gpt-5.5` → 400 → circuit breaker → fallback
    (`4fdab0a`).
  - `providers.py` ignored Mission Control vault keys (read a non-existent package
    export); now reads `current_vault_secrets` from `.config` (`44f557f`).
  - Gemini payload used `generationConfig.thinking_level`; corrected to
    `generationConfig.thinkingConfig.thinkingLevel` (camelCase), the cause of the
    final Gemini 400 (`b6d0848`).
  - Delegation hardening (`664a5cd`): no cross-provider cascade when `LLM_PROVIDER`
    is pinned (prevents the gpt-5.5 breaker storm); deterministic PM fallback now
    flagged `degraded=True`; Gemini key sent via `x-goog-api-key` header (kept out
    of URL logs) with 4xx bodies logged for diagnosis.
- `.env` `LLM_PROVIDER` switched `openai` → `gemini`.

#### Notes
- PM feature-contract API happy path is now observed green (`source: llm`,
  `model_provider: gemini`, `model: gemini-3.5-flash`). A fresh full mission to
  COMPLETE is still required before EDCP-02+. UI surfacing of degraded mode, a
  provider preflight test, and app-driven provider/model selection remain (see
  CURRENT_TODO).

### Mission Control Vault Auth Self-Heal + Full CI Remediation (2026-06-16)

#### Fixed
- **Standalone Mission Control databases page "not authorized"** — the standalone
  UI (port 3000) sent a stale `OPERATOR-API-KEY` from the host vault, which the
  gateway rejected (401). Removed the stale vault slot and added a self-heal in the
  Next.js gateway proxy (`api/gateway/[...path]/route.ts`): on a 401/403 from a
  vault operator key it now retries with `INTERNAL_SERVICE_API_KEY`.
- **CI green again** after a multi-layer cascade of pre-existing failures:
  - Dependabot: `vite 8.0.10 → 8.0.16`, `tmp 0.2.6 → 0.2.7`.
  - E2E: 4 Playwright specs updated for the Phase 2B tabbed mission-detail layout
    (click the owning tab before asserting `hidden`-tab panels).
  - Python: `runtime.py` imports `current_vault_secrets` from
    `llm_delegation.config` (consistent with `agent_integrations.py` /
    `routes/internal.py`), fixing 7 ImportErrors.
  - Lint: ruff I001 import-block ordering in `runtime.py`.
  - Coverage: new `_llm_recommendation_for_agent` branch test restores
    `agent_integrations.py` to its 100% module threshold.
  - Release Trust: build-provenance attestation skipped on private repos (the
    feature is unavailable there) and run normally on public/org repos.

#### Known
- One remaining Dependabot medium alert (`js-yaml ≤4.1.1`) is dev-only transitive
  via `@lhci/cli` and `@redocly/openapi-core`; deferred pending an `@lhci/cli`
  release on js-yaml 4.x.

### Extended Data Stores Enabled by Default (2026-06-13)

#### Changed
- **Milvus, Neo4j, and MinIO/object storage now on by default** — all three
  containers already started automatically in the base compose stack; the
  application-level integration flags now match:
  - `settings.py`: `milvus_enabled`, `neo4j_enabled`, `object_storage_enabled`
    dataclass defaults and `from_env()` fallbacks changed `False → True`.
  - `docker-compose.yaml`: `MILVUS_ENABLED` default changed `false → true`.
  - `docker-compose.dev.yaml`: removed hard `NEO4J_ENABLED: "false"` and
    `OBJECT_STORAGE_ENABLED: "false"` overrides so the dev stack now runs all
    three stores by default (same as staging/prod).
- **Documentation updated** — `README.md` data systems table, `SETTINGS_REFERENCE.md`,
  `DEVELOPER_ONBOARDING_GUIDE.md`, `ARCHITECTURE.md`, `COMPOSE_ENVIRONMENT_PROFILES.md`,
  and `IMPLEMENTATION_STATUS.md` all updated to reflect new defaults.

### Multiagent Audit — Remaining HIGH Items (2026-06-13)

#### Fixed / Resolved
- **LangGraph thread ID design clarified** (`langgraph_lifecycle.py`) — Added code comment
  explaining the stable `prefix:mission_id` format is intentional for stateful resumption
  (same mission_id must re-use the same thread to continue from the last checkpoint).
  Added DEBUG log of the thread_id for traceability. Safety relies on UUID-v4 mission IDs
  never being reused — enforced by the `missions` table PRIMARY KEY constraint.
- **Heartbeat interval mismatch guard** (`heartbeat_service.py`) — Added module-level
  warning when `AGENT_HEARTBEAT_STALE_SECONDS < 3 × AGENT_HEARTBEAT_INTERVAL_SECONDS`.
  Catches operator misconfiguration before it causes agents to appear spuriously stale
  (pod/specialist agents default to 15 s intervals vs the orchestrator's 5 s default).
- **Agent health coverage in `/health` endpoint** (`main.py`) — The `/health` response now
  includes `agents_total`, `agents_with_heartbeat`, `agents_missing_heartbeat`, and
  `agents_missing_ids`. Also logs a WARNING at health-check time for any registered agent
  with no recent heartbeat, making it visible when `agent-runtime` or `pod-worker` is down.
- **Sigma lane handler verified** (`main.py:505`) — Confirmed `handlers = {"sigma":
  _handle_sigma_knowledge_ready}` is correctly wired at startup. Handler re-checks
  PostgreSQL `is_stocked` on receipt and logs a WARNING on write/broadcast divergence.
  Removed from open issues — no code change needed.

### Multiagent System Bug Fixes (2026-06-13)

#### Fixed
- **Silent exception swallowing** — four locations where `except Exception: pass` or bare
  `except Exception:` gave operators zero visibility into failures:
  - `is_agent.py` — `_knowledge_is_indexed` and `_knowledge_is_current` now log at DEBUG
    when a storage error forces a `False` fallback (was silent, causing repeated re-indexing).
  - `dependency_absorption.py` — DEPABS LLM replacement failure now logs at WARNING with
    language/library context and returns `{"error": str(exc)}` so callers can detect it.
    Also added missing `logging` module + `LOGGER` to this file.
  - `knowledge_embeddings.py` — outer `except Exception` in `_record_embedding_usage` now
    logs at DEBUG (cost-ledger failures are non-fatal but should be observable).
  - `port_coordinator.py` — AIM extraction and specialist plan failures now log at WARNING
    with mission_id instead of silently degrading.
- **Port extraction degradation flag** — `coordinate_port_extraction()` now returns
  `"extraction_degraded": True` when either the AIM extraction or specialist plan fell
  back to an error stub, so RQCA and downstream agents know to expect reduced fidelity.

### Knowledge Lake Unit Tests (2026-06-13)

#### Added
- **`tests/services/test_knowledge_lake_unit.py`** — 37 new tests covering the entire
  `knowledge_lake.py` module (previously zero coverage): `_embedding_key_available`,
  `_semantic_search_enabled`, `is_stocked`, `index_documentation`, `_mirror_to_qdrant`,
  `query_documentation` routing, `_vector_search` (including a regression test confirming
  `content={"combined_text": concept_key}` and `task_type="RETRIEVAL_QUERY"` are passed),
  `_keyword_search`, and `get_language_context`.
- **Embeddings tests** — 5 new tests appended to `test_knowledge_embeddings_unit.py`:
  Gemini happy path, `task_type` forwarding to the Gemini API body, `RETRIEVAL_QUERY`
  correctly propagated, and `KNOWLEDGE_EMBEDDING_API_KEY` overriding both `GEMINI_API_KEY`
  and `OPENAI_API_KEY`.
- **LangGraph PgBouncer guard test** — 1 new test in `test_langgraph_lifecycle_unit.py`
  asserting that an empty `LANGGRAPH_CHECKPOINTER_POSTGRES_URL` returns False (rather than
  silently falling back to the PgBouncer URL and corrupting checkpoint state).

### Knowledge Embedding Key + Semantic Search Gate (2026-06-13)

#### Added
- **Dedicated Embedding API Key**: New `KNOWLEDGE_EMBEDDING_API_KEY` env var (wired through
  `settings.py` and `docker-compose.yaml`) lets operators use a separate API key for embedding
  calls, independent of the global `GEMINI_API_KEY` / `OPENAI_API_KEY` used for LLM generation.
  Both `_gemini_embedding` and `_openai_embedding` prefer this dedicated key when set.
- **Embedding Key Gate in Semantic Search**: `_semantic_search_enabled()` in `knowledge_lake.py`
  now also checks that a real API key is actually available (via the new dedicated key or the
  matching provider env var) before enabling Qdrant indexing. Previously it only checked provider
  name and Qdrant enabled-flag, so deterministic hash vectors were being silently written to Qdrant
  even with no provider key configured.
- **Settings UI — Knowledge Embeddings Panel**: A new "3. Knowledge Embeddings" section in the
  Settings page explains the embedding configuration, the `deterministic` compose default, the
  `KNOWLEDGE_EMBEDDING_API_KEY` env var, and how to enable real semantic search.

#### Changed
- **Qdrant Vector Size Default**: Raised `qdrant_vector_size` default from 64 to 256 in
  `settings.py` and `docker-compose.yaml`. 64 dimensions is too low for meaningful semantic
  separation between code documentation chunks; 256 is the practical floor for cosine similarity.

### PM Chat Intake & Gateway Auth Fixes (2026-06-13)

#### Added
- **Chat Session Auto-Save**: PM Agent Chat now persists the active conversation
  to `localStorage` as messages arrive (capped at `MAX_HISTORY_SESSIONS`), so a
  reload no longer loses in-progress sessions.

#### Changed
- **Resilient Contract Fallback**: When the PM feature-contract call fails and
  the builder-preview fallback also fails, the chat surfaces a combined error
  message instead of masking the original failure with the fallback error.

#### Fixed
- **Dropped Request Fields**: `createBuilderPreview` and `createPmFeatureContract`
  now normalize camelCase request fields (`viewMode`, `requestedTargetLanguage`)
  to the snake_case keys the API gateway expects. Previously the index signature
  on the request types let camelCase keys serialize silently, so the requested
  target language was discarded before reaching the backend.
- **Gateway Operator-Route Auth**: `deploy/docker-compose.yaml` now passes
  `ORCHESTRATOR_ADMIN_API_KEY`, `ORCHESTRATOR_READONLY_API_KEY`, and
  `ORCHESTRATOR_API_KEYS` to the `api-gateway` service so operator-route auth has
  the same key environment as its role map.
- **Lint Gate**: Split the aliased `redis.exceptions` import in
  `services/orchestrator/orchestrator/runtime.py` onto its own line to satisfy
  the `ruff` import-sorting rule (I001) that was failing the Lint and Test gate.

## [1.1.0] - 2026-05-23

### Enterprise Hardening & Native Windows Conversion

#### Added
- **Multi-Modal Context Ingestion**: PM Agent now accepts PDF, Word, Markdown, and PowerPoint documents. IS Agent indexes these into the Qdrant Knowledge Lake for specialist consumption.
- **Certified Specialist Army**: All 41 agents professionally grounded with industry standards (MISRA C, PEP 8/604, OWASP, etc.) and senior-level expert personas.
- **Enterprise Diagnostics**: New system_maintenance.py utility in Orchestrator for generating sanitized diagnostic bundles and full stateful database backups.
- **Native Windows Build Chain**: Configured Electron and NSIS for professional .exe installer generation with location selection, progress bars, and uninstallation support.
- **GitHub Actions Release Pipeline**: .github/workflows/release.yml for automated building, signing, and publishing of Windows releases on version tags.
- **Infrastructure Probes**: Electron app now checks for Docker availability on startup; Orchestrator health now includes Jaeger reachability.

#### Changed
- **Admin Mode Enabled**: Removed redundant Operator Key/Unlock systems. The application is now fully unlocked by default for local-first Windows usage.
- **Refactored API Gateway**: Decomposed massive create_mission route into specialized handlers; unified LLM builder previews behind a single dispatcher.
- **Security Hardening**: Integrated PII redaction middleware into the LLM delegation chain; injected strict enterprise security headers (HSTS, CSP, etc.).
- **Observability Upgrade**: Correlated OTEL trace IDs across API Gateway, Orchestrator, and database stores (Qdrant, Neo4j) for unified agent diagnostics.
- **UI Architecture**: Migrated mission detail pages from dynamic routes (/missions/[id]) to static Electron-compatible routes (/missions/detail?id=...).

#### Fixed
- **LLM Validations (CR-01)**: Updated model profiles to valid 2026 routes (gpt-5.5, gemini-3.5-flash).
- **God Function Factor (CR-02)**: Decomposed dvance_mission_lifecycle_v2 into maintainable state handlers.
- **Docker Build Integrity (H-03/H-06)**: Pinned all base image digests; resolved credsStore pull failures.
- **Database Resilience**: Fixed foreign key violations in Knowledge Lake indexing; added automatic system-mission record creation on startup.
- **Indentation & Syntax**: Resolved several critical Python syntax errors in mission_flow_v2.py and pi_gateway/main.py introduced during refactoring.

---


### Demo Mission Infrastructure (2026-05-22)

#### Added
- `scripts/run_demo_mission.py` (new, 467 lines) — end-to-end demo mission runner:
  - Pre-flight connectivity and LLM provider checks before submission
  - Submits a `BUILD_NEW` mission with a built-in prompt for Python, JavaScript, or TypeScript
  - Polls state to terminal, prints live phase progression, reports chain trace summary
  - Reports: PM Feature Contract, CEO Refined-IR Contract, generated output (with source=llm/fallback), PM Delivery Summary, FETCH result, build artifacts, generated code preview
  - Writes timestamped evidence JSON to `docs/evidence/demo_mission_<ts>.json`
  - Custom prompt via `--prompt`, language via `--language`, connectivity-only via `--dry-run`
- `docs/DEMO_MISSION_SETUP.md` (new) — step-by-step setup guide: TLS cert generation, `.env` creation, secret generation, LLM provider configuration, stack startup, result interpretation

#### Changed
- `Makefile` — added `demo`, `demo-js`, `demo-ts`, `demo-check` targets

---

### Phase 8 — FETCH Phase Completion (2026-05-22)

#### Added
- `services/orchestrator/orchestrator/knowledge_lake.py` (new, 369 lines) — Qdrant-backed semantic query layer for the Knowledge Lake:
  - `is_stocked(language)` — checks whether bootstrap docs for a language are indexed
  - `query_documentation(language, concept, top_k)` — vector similarity search with keyword-overlap fallback
  - `index_documentation(language, library, content)` — upserts a documentation chunk with deterministic embedding
  - `get_language_context(language)` — merged documentation text for prompt injection, capped at 8,000 chars
  - `broadcast_knowledge_ready(languages, mission_id)` — publishes Protocol Sigma `knowledge_ready` event to the protocol bus; fire-and-forget, never blocks mission progression
- `tests/services/test_is_agent_fetch_unit.py` (new, 465 lines) — 30 unit tests covering:
  - `detect_required_languages`: explicit target, TypeScript → js+ts expansion, source-code sniffing, unsupported language fallback
  - `run_fetch_phase`: per-language indexing, skip/error capture, result schema, storage-failure isolation, empty-language handling
  - `is_stocked`, `get_language_context`, `index_documentation`, `broadcast_knowledge_ready`, `query_documentation` — all patched offline, no Qdrant required

#### Changed
- `services/orchestrator/orchestrator/mission_flow_v2.py` — `_prepare_fetch_phase` now imports and calls `broadcast_knowledge_ready` after IS Agent indexing completes; Sigma event fires when `knowledge_ready=True` and indexed languages are non-empty

---

### Production Remediation (2026-04-17)

Executed the full 8-finding remediation plan from `docs/reviews/production-remediation-plan-2026-04-17.md`. One finding (pod-d-worker hardening) was a false positive — the service already inherits `*readonly-service-hardening` via YAML anchor.

#### Security
- **OIDC alg-confusion surface removed:** `OIDC_ALLOWED_ALGORITHMS` default flipped from `RS256,HS256` → `RS256` so a forged HS256 token signed with the JWKS public key can never be accepted (api-gateway/main.py:77).
- **Constant-time API-key compare:** `orchestrator/auth.py` now uses `_match_api_key()` with `hmac.compare_digest`; `protocol-bus-mcp/mcp_server.py:410` flipped from `!=` to `hmac.compare_digest`. Eliminates the timing-side-channel on API-key validation.
- **JWT error no longer leaks token fragments:** `api-gateway/main.py:716` logs the exception *class name* only. PyJWT's message can include decoded header/claims.
- **MCP port no longer exposed on 0.0.0.0:** `deploy/docker-compose.yaml` now uses `${MCP_HOST_BIND:-0.0.0.0}:${MCP_HOST_PORT:-8102}:8090`. Prod `.env` must set `MCP_HOST_BIND=127.0.0.1` (documented in `.env.example`).
- **LangGraph fail-open disabled in prod:** `deploy/docker-compose.prod.yaml` sets `LANGGRAPH_FAIL_OPEN: "false"` so checkpointer outages surface instead of silently masking state loss.

#### Observability
- **Structured JSON logging:** new `shared_runtime/logging_config.py` with stdlib-only `JsonFormatter` and `configure_logging(service_name)`. Gated by `LOG_FORMAT` (plain|json, default plain). Wired into all 7 services: api-gateway, orchestrator, pod-worker, audit-worker, agent-runtime, dashboard, protocol-bus-mcp. Prod overlay now sets `LOG_FORMAT: json` for every service.

#### Build
- **Base images pinned to minor+patch+OS release:** all 7 Python Dockerfiles use `python:3.11-slim-bookworm`; mission-control uses `node:22-alpine3.20`. Digest-pinning deferred (tracked in the plan doc).
- **Healthcheck URLs aligned:** 13 Dockerfile HEALTHCHECK and compose healthcheck entries flipped from `/health` to `/readyz` so liveness no longer races startup (`/readyz` is deterministically gated on upstream readiness).
- **`start_app.bat` prod parity:** default path now runs `npm run build && npm run start`; `--dev` flag falls back to `npm run dev` for local iteration.

#### Verification
- `ruff check shared_runtime services tests` → clean.
- `pytest tests` → 999 passed, 5 skipped.

---

### Settings & Vault — Offline Resilience (2026-04-16)

#### Fixed
- **Settings page: agent API key slots invisible when orchestrator offline (Critical):** `loadVaultAndAgents` previously used `Promise.all` causing both the agent-integrations fetch and the vault fetch to fail atomically when port 8100 is unreachable. Replaced with `Promise.allSettled` so the vault API loads independently. All 35 agent vault slots now appear even when the orchestrator is not running.
- **Settings page: vault table only showed 2 rows offline:** Added `STATIC_AGENT_SLOTS` constant (all 35 agents with provider/model from `config/agent_api_keys.yaml`) used as fallback when `snapshot` is null. Agent rows are now built from the live orchestrator snapshot when available, or the static roster otherwise.
- **Settings page: opaque "Failed to fetch" error:** Error banner now clearly distinguishes orchestrator-offline vs actual vault API failures. An amber warning banner reads: *"Orchestrator offline (port 8100 unreachable) — showing static agent roster. Vault keys can still be saved."*
- **Databases page: "Failed to fetch" with no context (High):** Health Overview panel previously surfaced the raw browser `TypeError` when port 8100 was unreachable. Now detects network errors specifically and shows an actionable amber banner: *"Orchestrator unreachable at port 8100. Start the Docker stack to see live database health."*
- **Vault persistence lost on every server restart (High):** No `.env.local` existed, so `MISSION_CONTROL_ADMIN_KEY` was unset and the vault fell back to ephemeral in-memory mode. Created `apps/mission-control/.env.local` with freshly generated AES-256-GCM keys (`MISSION_CONTROL_ADMIN_KEY`, `APPROVAL_HMAC_SECRET`, `MISSION_CONTROL_SESSION_SECRET`, `VAULT_ADMIN_KEY`). After a server restart the vault persists to `~/.thefactory/vault.json`.

---

### Phase 7 — Extractor Provenance and Tooling (2026-04-14)

#### Added
- `services/pod-worker/pod_worker/js_ast_extractor.py` — JS/TypeScript AST extractor using `ast_grep`/`tree-sitter` fallback; extracts functions, classes, imports with `is_async` and return-type metadata
- `services/pod-worker/pod_worker/java_ast_extractor.py` — Java AST extractor; method/class/import extraction with modifier and annotation capture
- `tests/fixtures/extractors/` — externalized fixture corpus with `python_sample.py`, `js_sample.js`, and `java_sample.java` for cross-extractor golden tests
- `tests/services/test_language_extractor_golden.py` — golden regression tests locking function/class/concept extraction output for Python, JS, and Java fixtures
- `reports/ast_vs_regex_comparison.json` — static comparison report: `PythonExtractor` (regex) vs `extract_python_ast` (AST) on Python fixture; both agree on all 6 functions and 2 classes; documents AST-exclusive (`is_async`, return types) and regex-exclusive (concept catalog, parse-resilience) capabilities
- `TestEventSchemaEquivalence` in `tests/services/test_lifecycle_interface_unit.py` — 5 new AST-inspection tests asserting identical event-emission schema across all three lifecycle engine adapters: direct `emit_state_event` call (LegacyV1), `emit_state_event_fn=` kwarg delegation (V2 + LangGraph), locked-down function signature, and canonical `EventType` membership for all inline event-type literals

#### Changed
- `ExtractedConcept` dataclass — added `extraction_method: Literal["ast", "regex"]` and `source_range: dict[str, int] | None` provenance fields
- `pod_worker/main.py` `_handle_running_mission` — LogicNode payloads now include `extraction_method` and `source_range` from `ExtractedConcept`

---

### Phase 6 — Mission Control UI Enhancements (2026-04-14)

#### Added
- **Active Runtime vs Conceptual Architecture toggle** (`agents/page.tsx`): `viewMode` state with toggle buttons in the Filters panel; Runtime mode filters agents to `heartbeat_source === "live"` (falls back to `runtime_class === "shared_worker"`); Conceptual mode shows the full 38-agent registry
- **Lifecycle engine badge** (`missions/[id]/page.tsx`): `lifecycleEngine` derived value maps `phaseDescriptor.model === "v2"` → MissionFlow V2, `routing_version.includes("langgraph")` → LangGraph, else → Legacy V1; rendered as a color-coded `.connection-chip` in Mission Signals panel
- **Audit Evidence panel** (`missions/[id]/page.tsx`): fetches `/internal/missions/{id}/audit-reports` via new `listMissionAuditReports` API client function; renders status chip, score, summary, and findings list; `.catch(() => [])` ensures page loads even on auth failure
- **Feature flag warning banners** (`agents/page.tsx`): `role="alert"` warning block in Runtime Dependencies panel; warns when `consumer_running`, `protocol_ready`, `redis_ready`, or `db_ready` are falsy; error-level banner when `db_ready` is false; info banner when `langgraph_enabled === false`

#### Changed
- `apps/mission-control/app/lib/types.ts` — added `AgentHeartbeatSource` type; added `heartbeat_age_seconds` and `heartbeat_source` to `OperationsAgentRecord`; extended `OperationsAgentsSnapshot.runtime` with `langgraph_enabled`, `langgraph_fail_open`, `langgraph_checkpointer`; added `OperationsAuditReportRecord` type
- `apps/mission-control/app/lib/api-client.ts` — added `listMissionAuditReports(missionId, limit)` function

---

### Phase 5 — Orchestrator Decomposition (2026-04-14)

#### Added
- `services/orchestrator/orchestrator/lifecycle_interface.py` — `LifecycleEngine` Protocol; `MissionFlowV2Engine`, `LangGraphEngine`, `LegacyV1Engine` adapters; `get_lifecycle_engine(settings)` factory replacing inline `if/elif/else` branch in `runtime.py`
- `services/orchestrator/orchestrator/heartbeat_service.py` — extracted `_build_non_pod_heartbeat_payloads`, `_emit_agent_telemetry_event`, `agent_heartbeat_loop`, `AGENT_HEARTBEAT_STALE_SECONDS`
- `services/orchestrator/orchestrator/review_policy.py` — extracted all review approval validation, HMAC-verification, and TTL-check logic
- `services/orchestrator/orchestrator/lifecycle_recovery.py` — extracted `_recover_inflight_lifecycle_tasks`
- `services/orchestrator/orchestrator/storage/` — 6-module façade package: `missions.py`, `agents.py`, `artifacts.py`, `knowledge.py`, `audit.py`, `scaling.py`; `storage.py` becomes a thin re-export shim for backward compatibility
- `tests/services/test_lifecycle_interface_unit.py` — 14 unit tests for `LifecycleEngine` protocol satisfaction, `get_lifecycle_engine` factory flag logic, `MissionFlowV2Engine` delegation, `LangGraphEngine` fall-through, `LegacyV1Engine` event-type regression guard

#### Changed
- `services/orchestrator/orchestrator/main.py` — reduced from **1250 to 423 lines**; retains lifespan, middleware, router wiring, and health/readyz/metrics only
- `services/orchestrator/orchestrator/models.py` — now the single source of truth for `VALID_TRANSITIONS`; duplicate copy removed from `mission_flow_v2.py`
- `tests/services/test_orchestrator_lifecycle_recovery_unit.py` — updated to import from `orchestrator.lifecycle_recovery` (moved from `main.py`)
- `tests/services/test_orchestrator_main_helpers_unit.py` — updated to import from `orchestrator.heartbeat_service`, `orchestrator.routes.internal`, and `orchestrator.routes.operations` (functions moved from `main.py`)
- `tests/services/test_orchestrator_endpoints_extra.py` — updated to import `_build_mission_chain_trace` from `orchestrator.routes.internal`

---

### Mission Control UI — Enterprise Hardening (2026-04-14)

#### Fixed
- **Scroll layout (Critical):** Shell grid container now sets `height: 100vh; overflow: hidden` and the main column sets `overflow-y: auto; height: 100vh` — eliminating the dead-space-on-scroll bug where the sticky sidebar created a phantom document scroll offset
- **Horizontal overflow (High):** Added `flex-wrap: wrap` to `.shell-header-actions`; `flex-shrink: 0; white-space: nowrap` to `.summary-list li` value spans and `.pill` badges; `overflow-x: hidden` to `.shell-main`; prevents button/badge/status text clipping at viewport edge
- **404 not-found renders in shell (High):** Moved `app/not-found.tsx` → `app/(shell)/not-found.tsx` so Next.js wraps 404 pages inside the sidebar/header shell chrome. Changed `<main>` → `<div>` to avoid duplicate landmark; demoted `<h1>` → `<h2>`
- **KPI cards blank on error (High):** Removed `{!error && ...}` guard around `.kpi-grid`; metric cards now render with `0` values when the API errors rather than disappearing entirely
- **Duplicate nav actions (Medium):** Removed redundant "New Mission / Mission Center" buttons from `dashboard/page.tsx` `PageHeader` — they already exist in the persistent shell header on every page
- **File input unstyled (Medium):** Chat page `<input type="file">` now wrapped in a styled `<label className="file-input-label">` with full dark-theme styling, hover state, and proper `:focus-within` ring; native input visually hidden but accessible
- **Root error.tsx `<main>` duplicate (Low):** Changed `app/error.tsx` wrapper from `<main>` to `<div>` for consistency with `(shell)/error.tsx`
- **Temp file removed:** Deleted `apps/mission-control/temp_extract.py` and added `temp_*.py / *.pyc / __pycache__/` to `.gitignore`

#### Added
- **Color-coded status badges (High):** Runtime Health rows in `dashboard/page.tsx` and Runtime Dependencies in `agents/page.tsx` now use existing `.connection-chip.live/.stale/.retrying` classes with `role="status"` and `aria-label` attributes instead of plain text
- **Compact PageHeader variant (Medium):** `PageHeader` component now accepts a `compact` boolean prop; renders a slim border-bottom bar (1.3rem h1, no panel chrome) on all operational pages (Agents, Chat, Missions, LogicNodes, Protocol Bus, Databases, Repo, Settings, Alerts, Builder, Performance, Projects). Home/Launch Pad keeps the full hero panel
- **Dynamic shell header title (Medium):** New `ShellHeaderMeta` client component uses `usePathname()` + `NAV_ITEMS` lookup to display the active page name in the header (e.g., "Local Runtime — Agents") instead of the hardcoded static subtitle
- **HTTPS warning in Settings (Low-Medium):** API base URL input now shows a `.warning-box` when the configured value is non-HTTPS and non-localhost
- **Actionable empty states (Medium):** "Top Mission States" (dashboard) shows "Launch your first mission →" link; Agents Grid distinguishes "no agents found" (backend link to Settings) vs "no agents match filters" (filter hint); Alerts "Active and Recent Alerts" shows "All systems operating normally" when empty

#### Changed
- **Performance page KPI grid semantic HTML:** Changed from `<div role="list"><article role="listitem">` to `<ul><li>` (correct semantic list markup); `.kpi-grid` CSS updated with `list-style: none; margin: 0; padding: 0`
- **Alerts and other pages:** Added `compact` to all PageHeader uses that were missing it (alerts, builder, performance, projects)

---

### Phase 3 (continued) — Orchestrator Decomposition (2026-03-31)

#### Added
- `services/orchestrator/orchestrator/routes/` — new routes package splitting the 2065-line `main.py` into focused modules:
  - `routes/missions.py` (147 lines) — mission CRUD and state transition routes
  - `routes/internal.py` (605 lines) — all `/internal/*` routes: pod assignment, chain trace, logicnodes, knowledge, audit reports, review approvals, build artifacts, partition results, agent heartbeat
  - `routes/operations.py` (263 lines) — all `/internal/operations/*` routes: summary, agents snapshot, events, alerts, projects
  - `routes/_deps.py` (16 lines) — shared `INTERNAL_AUTH_DEP` / `MUTATION_AUTH_DEP` Depends wrappers

#### Changed
- `services/orchestrator/orchestrator/main.py` — reduced from 2065 to 1250 lines via extraction; retains all helpers, lifespan, background tasks, middleware, health/readyz/metrics, and `app.include_router()` wiring. No functional changes.

### Phase 4 — Production Hardening (2026-03-31)

#### Changed
- `deploy/docker-compose.prod.yaml` — comprehensive production overlay: activates `PII_GUARD_MODE=redact` and `PROMPT_GUARD_MODE=block` for api-gateway and orchestrator; tightens circuit breaker to 3 failures / 60s recovery for all dedicated agent workers; reduces protocol bus backpressure limit to 5 000 and extends dedup TTL to 600s; sets `LOG_LEVEL=WARNING` across all services; adds `AUDIT_LOG_ENABLED=true`
- `.github/workflows/ci.yml` — added CycloneDX JSON SBOM generation alongside existing SPDX JSON (both formats uploaded as CI artifacts); SLSA provenance already generated via `actions/attest-build-provenance@v2`

### Phase 3 — Intelligence Layer Upgrade (2026-03-31)

#### Added
- `services/pod-worker/pod_worker/ast_extractor.py` — AST-based Python extraction using the built-in `ast` module; provides `AstFunctionInfo`, `AstClassInfo`, `AstImportInfo`, and `AstExtractionResult` with accurate function/class/import detection, type annotation extraction, decorator capture, and docstring harvesting; graceful fallback on SyntaxError
- `tests/services/test_ast_extractor.py` — 36 unit tests covering function/class/import extraction, async detection, decorator capture, edge cases, and frozen-dataclass immutability
- `tests/services/test_circuit_breaker.py` — 18 unit tests for the CLOSED→OPEN→HALF-OPEN circuit breaker state machine in agent-runtime
- `tests/services/test_protocol_bus_dedup.py` — 8 integration tests for message deduplication (Redis SET NX EX on `correlation_id`) and backpressure (503 + `Retry-After: 5` when queue > limit), including graceful-degradation coverage

#### Changed
- `services/agent-runtime/agent_runtime/main.py` — added `_CircuitBreaker` class (CLOSED/OPEN/HALF states, configurable `CIRCUIT_FAILURE_THRESHOLD` and `CIRCUIT_RECOVERY_SECONDS`); integrated into `_request()` to fail-fast when orchestrator is unreachable; added `AGENT_CIRCUIT_OPEN` Prometheus counter
- `services/protocol-bus-mcp/protocol_bus/mcp_server.py` — added message deduplication via Redis SET NX EX keyed on `correlation_id` (idempotent 200 response with `"deduplicated": true`); added backpressure check via `xlen` against `BACKPRESSURE_QUEUE_LIMIT` (default 10 000) with `Retry-After: 5` header; added `MESSAGES_DEDUPLICATED` Prometheus counter

### Phase 2 — Security Hardening (2026-03-31)

#### Added
- `shared_runtime/pii_guard.py` — PII detection and redaction module; patterns for SSN, credit card, email, phone (US + intl), JWT tokens, hex/base64 API keys, password KV pairs, IP addresses; overlap-aware deduplication; `detect_pii`, `redact_pii`, `has_pii`, `scan_dict_for_pii`, `safe_context_json_redact`
- `shared_runtime/prompt_guard.py` — prompt injection detection and sanitization; patterns for system-tag delimiter smuggling, INST-tag injection, human-turn injection, role override, jailbreak keywords, agent-ID injection, prompt extraction, and base64 content; `check_prompt` returns `InjectionResult` with risk level; `sanitize_prompt` strips known attack vectors
- `tests/services/test_pii_guard.py` — 22 unit tests for all PII detection, redaction, and dict-scanning paths
- `tests/services/test_prompt_guard.py` — 17 unit tests covering all injection patterns, sanitization, and risk-level escalation
- `apps/mission-control/e2e/mission-control-extended.spec.ts` — 13 Playwright E2E tests covering mission failure path, full v2 lifecycle, vault/settings, agents grid, protocol bus monitor, accessibility, and databases page
- `tests/eval/golden_delegation_cases.json` — expanded from 6 to 30 golden delegation cases including all language specialists, 6 adversarial injection cases, and 3 regression/isolation cases
- `docs/runbooks/dr_validation_runbook.md` — DR drill runbook for PostgreSQL backup/restore, full cold-start, orchestrator failure + LangGraph checkpoint recovery, and Redis stream recovery

#### Changed
- `shared_runtime/protocol.py` — added `ReplayDetectedError`, in-process `_InProcessReplayGuard` with lazy-eviction TTL, and `check_replay()` public function for event replay detection
- `services/api-gateway/api_gateway/main.py` — added structured audit log middleware emitting `{audit, method, path, status, duration_ms, trace_id, client_ip_hash}` as structured JSON on every request
- `apps/mission-control/app/api/review/approve/route.ts` — HMAC-SHA256 signature on approval records; `issued_at` / `expires_at` / `hmac_digest` fields sent to orchestrator; configurable `APPROVAL_HMAC_SECRET` and `APPROVAL_TTL_SECONDS`
- `.env.example` — added `APPROVAL_HMAC_SECRET`, `APPROVAL_TTL_SECONDS`, `PII_GUARD_MODE`, `PROMPT_GUARD_MODE`

### Phase 0 — Secret Hygiene & Supply Chain Baseline (2026-03-31)

#### Added
- `.gitleaks.toml` — custom gitleaks config with theFactory-specific API key patterns and CHANGE_ME allowlist
- `.pre-commit-config.yaml` — pre-commit hooks: gitleaks (staged secret scan), ruff lint+format, YAML/JSON validation, large-file guard, private-key detection, no-commit-to-main
- `scripts/rotate_secrets.sh` — secret rotation helper: generates 32-char hex keys for all rotatable env vars, validates .env.example is clean, checks git history via gitleaks
- `shared_runtime/agent_keys.py` — Shannon entropy validation (`validate_key_strength`) and structured key-access logging; keys below 16 chars or 3.0 bits/char emit warnings

#### Changed
- `.github/workflows/security.yml` — added Python + Node license scanning (blocks GPL/AGPL in transitive deps), hardened gitleaks to full history scan with custom `.gitleaks.toml`, added `.env.example` real-secret verification step

### Added
- Documentation governance and archive package:
  - canonical documentation standard in `docs/DOCUMENTATION_STANDARDS.md`
  - canonical data-flow coverage in `docs/ARCHITECTURE_DATA_FLOWS.md`
  - developer and operator guides in `docs/DEVELOPER_GUIDE.md` and `docs/user/OPERATOR_GUIDE.md`
  - archive index in `docs/archive/README.md`
  - repository-tree generator in `scripts/generate_build_map.py` with generated output in `docs/REPOSITORY_BUILD_MAP_2026-03-29.md`
  - documentation maintenance tooling:
    - `scripts/normalize_document_headers.py`
    - `scripts/validate_documentation.py`
- Strategic and mission-flow governance ADR package:
  - `docs/ADR_STRATEGIC_DEFERRED_SCOPE_DECISIONS_2026-03-08.md`
  - `docs/ADR_V2_MISSION_FLOW_ADOPTION_DESIGN_2026-03-08.md`
- Dedicated-agent canary rollout qualification tooling:
  - `scripts/dedicated_agent_canary_rollout.py`
  - `scripts/dedicated_agent_canary_rollout.ps1`
  - `tests/scripts/test_dedicated_agent_canary_rollout.py`
  - `docs/runbooks/dedicated_agent_canary_runbook.md`
  - `docs/evidence/phase37_strategy_auth_canary_2026-03-08.md`
- Qualification matrix automation tooling:
  - `scripts/operator_route_auth_matrix_qualification.py`
  - `scripts/operator_route_auth_matrix_qualification.ps1`
  - `scripts/dedicated_agent_canary_trend.py`
  - `scripts/dedicated_agent_canary_trend.ps1`
  - `scripts/langgraph_v2_prototype_matrix.py`
  - `scripts/langgraph_v2_prototype_matrix.ps1`
  - script unit coverage:
    - `tests/scripts/test_operator_route_auth_matrix_qualification.py`
    - `tests/scripts/test_dedicated_agent_canary_trend.py`
    - `tests/scripts/test_langgraph_v2_prototype_matrix.py`
  - runbook/evidence:
    - `docs/runbooks/qualification_matrix_runbook.md`
    - `docs/evidence/phase38_qualification_matrix_automation_2026-03-08.md`
    - `docs/evidence/operator_route_oidc_matrix_2026-03-08.json`
    - `docs/evidence/dedicated_agent_canary_trend_2026-03-08.json`
    - `docs/evidence/langgraph_v2_prototype_matrix_2026-03-08.json`
- LangGraph LLM node-depth wiring package:
  - pod-manager and specialist provider-backed delegation/planning calls in
    `services/orchestrator/orchestrator/llm_delegation.py`
  - specialist planning LangGraph node and chain event wiring in
    `services/orchestrator/orchestrator/langgraph_lifecycle.py`
  - unit coverage updates:
    - `tests/services/test_llm_delegation_unit.py`
    - `tests/services/test_langgraph_lifecycle_unit.py`
  - validation evidence:
    - `docs/evidence/phase39_llm_node_wiring_hardening_2026-03-08.md`
- Tracing entrypoint wiring regression test:
  - `tests/services/test_tracing_wiring_unit.py`
- Mission-flow runtime enforcement package:
  - canonical PM intake normalization and routing metadata at gateway intake
  - orchestrator chain trace persistence and endpoints for per-mission PM -> CEO -> pod/specialist visibility
  - LangGraph CEO delegation engine with provider-aware LLM calls plus deterministic fallback routing
  - completion-integrity guardrails preventing `COMPLETE` without required execution artifacts
- Mission artifact qualification tooling:
  - `scripts/mission_artifact_qualification.py`
  - `scripts/mission_artifact_qualification.ps1`
  - `tests/scripts/test_mission_artifact_qualification.py`
  - evidence artifacts for both shared and dedicated profiles:
    - `docs/evidence/mission_artifact_qualification_shared_2026-03-08.json`
    - `docs/evidence/mission_artifact_qualification_dedicated_2026-03-08.json`
- Mission-flow status ADR and phase evidence/docs:
  - `docs/ADR_MISSION_FLOW_V2_STATUS_2026-03-08.md`
  - `docs/evidence/phase35_mission_artifact_runtime_integrity_validation_2026-03-08.md`
- Additional distributed tracing wiring modules:
  - `services/pod-worker/pod_worker/tracing.py`
  - `services/audit-worker/audit_worker/tracing.py`
  - `services/protocol-bus-mcp/protocol_bus/tracing.py`
  - `services/dashboard/dashboard/tracing.py`
- Mission Control token sync helper for container-safe styling:
  - `apps/mission-control/scripts/sync-design-tokens.mjs`
  - generated `apps/mission-control/app/generated-tokens.css`

- Frontend Style Guide compliance pass:
  - Typography: `layout.tsx` updated to use Style Guide-specified `Inter` (display) and `JetBrains_Mono` (code) fonts.
  - Dark mode: `globals.css` rewritten with 31-token CSS variable system — SLATE `#0F172A` background, Refinery Violet `#8B5CF6` accent, SLATE-400 muted text, SLATE-700 borders throughout.
  - Reconnect banner: new `components/reconnect-banner.tsx` — accessible `role="alert"` component with retrying/stale states, pre-wired into shell layout ready for SSE connection state.
  - Responsive breakpoints: `globals.css` now includes 1440px (wide desktop) and 1024px (standard desktop) breakpoints per Frontend Design §12.
  - Safari: `-webkit-backdrop-filter` added alongside `backdrop-filter` on shell header.
  - Evidence: `docs/evidence/frontend_style_guide_compliance_2026-03-03.md`

- Pod A/B/C/D language extraction engine:
  - `concept_catalog.py`: 232 regex patterns across 16 routable languages (DYN/SYS/ENT/MATH concept IDs)
  - `language_extractor.py`: base class + 16 per-language extractors (Python, JS/TS, Ruby, PHP, C, C++, Rust, Zig, Java, C#, Scala, Kotlin, MATLAB, R, Julia, Mathematica)
  - Pod-worker `main.py`: wired extraction into `_handle_running_mission` — creates per-concept LogicNodes with confidence scores and source evidence
  - Prometheus metrics: `pod_worker_concepts_extracted_total`, `pod_worker_extraction_latency_seconds`
  - Tests: 38 new tests (extractor accuracy + catalog validation), 32 existing tests pass with no regressions
  - Evidence: `docs/evidence/pod_language_extraction_2026-03-03.md`

- Versioned orchestrator migration framework:
  - `services/orchestrator/orchestrator/migrations.py`
  - `services/orchestrator/orchestrator/migrations/V001_initial_runtime_schema.sql`
  - checksum-tracked `schema_migrations` table enforcement
- Mission Control frontend unit test baseline:
  - Vitest + jsdom test tooling in `apps/mission-control`
  - initial API client tests in `apps/mission-control/app/lib/api-client.test.ts`
- Release trust and promotion controls:
  - promotion policy in `deploy/promotion-policy.json`
  - policy evaluator in `scripts/promotion_gate.py`
  - CI release-trust job with provenance attestation and verification
  - release trust documentation in `docs/RELEASE_TRUST_PROMOTION_GATE.md`
- Long-duration reliability qualification tooling:
  - `scripts/reliability_qualification.py`
  - `scripts/reliability_qualification.ps1`
  - baseline evidence in `docs/evidence/reliability_qualification_baseline_2026-03-03.json`
  - reliability runbook in `docs/LONG_DURATION_RELIABILITY_QUALIFICATION.md`
- Mission Control e2e regression tooling:
  - Playwright config in `apps/mission-control/playwright.config.ts`
  - critical-path e2e suite in `apps/mission-control/e2e/mission-control.spec.ts`
- Protocol Bus MCP service (`services/protocol-bus-mcp`) with:
  - six-protocol payload validation (alpha/beta/delta/sigma/omega/rho)
  - `/send`, `/health`, `/readyz`, `/metrics`, and `/dlq` endpoints
  - payload size enforcement and sender identity checks
- Infrastructure hardening updates in `deploy/docker-compose.yaml`:
  - restart policies, log rotation, healthchecks, resource controls
  - dedicated `hgr-network`
  - optional extended data plane services (MinIO/Milvus profile)
  - Jaeger and protocol-bus-mcp service definitions
- Redis runtime config at `deploy/redis/redis.conf`.
- Worker metrics endpoints in pod-worker and audit-worker.
- Worker readiness endpoints:
  - `services/pod-worker`: `/readyz`
  - `services/audit-worker`: `/readyz`
- Monitoring scrape and alert expansions for MCP and workers.
- New governance and onboarding docs:
  - `docs/DATA_CLASSIFICATION_POLICY.md`
  - `docs/DEVELOPER_ONBOARDING_GUIDE.md`
  - `docs/API_INTEGRATION_GUIDE.md`
  - `docs/runbooks/protocol_bus_incident_runbook.md`
- Core coverage validation utility:
  - `scripts/check_coverage_thresholds.py`
- Core agent/runtime test suite expansion:
  - `tests/services/test_agent_core_unit.py`
  - targeted branch tests for protocol/runtime, protocol-bus, pod-worker, and audit-worker paths
- Testing policy documentation:
  - `docs/TESTING_QUALITY_GATES.md`
- Qdrant knowledge integration baseline:
  - `services/orchestrator/orchestrator/qdrant_store.py`
  - `tests/services/test_qdrant_store_unit.py`
  - phase evidence in `docs/evidence/phase16_data_system_activation_validation_2026-03-03.md`
- Neo4j optional graph integration baseline:
  - `services/orchestrator/orchestrator/neo4j_store.py`
  - `tests/services/test_neo4j_store_unit.py`
  - phase evidence in `docs/evidence/phase17_neo4j_feature_flag_validation_2026-03-03.md`
- Object-storage retention/legal-hold baseline:
  - `services/orchestrator/orchestrator/object_store.py`
  - `tests/services/test_object_store_unit.py`
  - phase evidence in `docs/evidence/phase18_object_storage_validation_2026-03-03.md`
- Post-Phase-18 planning refresh:
  - `docs/UPDATED_PHASE_PLAN_2026-03-03.md`
- Mission Control live transport baseline:
  - API Gateway SSE endpoint `GET /v1/stream/state` with mission filtering, keepalive, and `Last-Event-ID` resume support
  - frontend EventSource transport integration for mission detail, Protocol Bus, and agent operations views
  - `tests/services/test_api_gateway_live_stream_unit.py`
  - phase evidence in `docs/evidence/phase27_mission_control_live_transport_validation_2026-03-04.md`
- Smelt-cycle runtime reconciliation baseline:
  - deterministic lifecycle checkpoint events `MISSION_GATING` and `MISSION_FUSION`
  - canonical phase mapping policy in `docs/SMELT_CYCLE_RUNTIME_MAPPING_2026-03-04.md`
  - frontend mapping helper/tests in `apps/mission-control/app/lib/smelt-cycle.ts` and `smelt-cycle.test.ts`
  - phase evidence in `docs/evidence/phase28_smelt_cycle_runtime_reconciliation_validation_2026-03-04.md`
- Phase 29 decision package:
  - topology ADR in `docs/ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md`
  - security-model ADR in `docs/ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md`
  - decision validation evidence in `docs/evidence/phase29_topology_and_security_adr_validation_2026-03-04.md`
- Phase 30 ADR execution baseline:
  - gateway auth mode controls (`AUTH_MODE=api_key|hybrid|oidc`) with OIDC bearer validation path for mutation endpoint authorization
  - dedicated topology compose scaffolding profile (`--profile dedicated-agents`)
  - auth-mode regression suite `tests/services/test_api_gateway_auth_mode_unit.py`
  - validation evidence in `docs/evidence/phase30_auth_mode_and_dedicated_profile_validation_2026-03-04.md`
- Phase 31 dedicated-agent binding scheduler enforcement:
  - pod-worker runtime now enforces `AGENT_BINDING` policy for dedicated workers
  - mission agent resolution supports payload fields, payload metadata, and orchestrator mission metadata fallback
  - new metric `pod_worker_binding_skips_total{pod_name,reason}` and `/health` visibility for active bindings
  - regression coverage updates in `tests/services/test_pod_worker_unit.py` and `tests/services/test_runtime_unit.py`
  - validation evidence in `docs/evidence/phase31_dedicated_agent_binding_scheduler_validation_2026-03-04.md`
- Phase 32 optional data-plane observability and SLO controls:
  - added optional adapter metrics for Neo4j/object-storage readiness, operations, and mirror writes
  - added mirror-write telemetry in orchestrator routes for Neo4j/object-storage paths
  - added Prometheus alert rules and Grafana panels for optional data-plane readiness, error-rate, and p95 latency
  - added incident runbook `docs/runbooks/optional_data_plane_incident_runbook.md`
  - validation evidence in `docs/evidence/phase32_optional_data_plane_observability_validation_2026-03-04.md`
- Phase 33 extended data-plane live qualification:
  - added live integration suite `tests/services/test_live_extended_data_plane_integration.py`
  - added skip-safe disruption/recovery qualification flow for temporary Neo4j/MinIO outages
  - added `make test-live-extended` for local execution
  - validation evidence in `docs/evidence/phase33_extended_data_plane_live_qualification_validation_2026-03-04.md`

### Changed
- API Gateway OIDC policy now extends to operator telemetry routes and live stream route:
  - `/v1/operations/*`
  - `/v1/stream/state`
  - new auth controls: `OIDC_OPERATOR_ROLE`, `OIDC_ENFORCE_OPERATOR_ROUTES`
- Production audit coverage expanded to `14/14` checks with compliance evidence mapping control (`GRC-012`).
- Mission Control now imports generated local token CSS and syncs tokens during `dev`/`build`.
- Docker runtime stack rebuilt and validated with Redis TLS port wiring and updated mission-flow enforcement paths.
- Word-doc audit backlog and phase plan documentation updated to mark phase-35 artifact integrity validation complete.
- Makefile now exposes recurring qualification targets:
  - `make oidc-matrix`
  - `make dedicated-canary-trend`
  - `make langgraph-v2-prototype`
- Compose shared service baseline now enforces `security_opt: [no-new-privileges:true]`.

- `.env.example` expanded with Redis password, MCP, MinIO, Milvus, Jaeger, and per-worker service key variables.
- `deploy/docker-compose.yaml` healthchecks migrated from `wget` to runtime-native probes (`python`/`node`) for slim images.
- `scripts/debug_sweep.ps1` expanded to validate MCP (`/health`, `/readyz`, `/metrics`) in addition to core services.
- Worker and MCP shutdown paths hardened for both async and sync Redis client close semantics.
- `docs/DOCUMENTATION_INDEX.md` updated with new operations/compliance docs.
- `Makefile` and `.github/workflows/ci.yml` now enforce 100% coverage for core multi-agent communication/runtime modules while preserving global `>= 80%` coverage.
- `services/orchestrator/orchestrator/storage.py` now applies versioned SQL migrations instead of inline table DDL.
- Added migration unit coverage in `tests/services/test_migrations_unit.py` and updated schema bootstrap tests.
- `.github/workflows/ci.yml` now runs Mission Control `npm run lint` and `npm run test` as part of CI validation.
- `Makefile` now exposes `make test-ui` for Mission Control lint/test execution.
- `README.md` now explicitly distinguishes Mission Control Docker host port (`3100`) from direct Next.js dev port (`3000`).
- Added operational script unit tests in `tests/scripts/test_production_review_audit.py`.
- Added performance-smoke script unit tests in `tests/scripts/test_perf_smoke.py`.
- Added promotion gate unit tests in `tests/scripts/test_promotion_gate.py`.
- `scripts/production_review_audit.py` now includes critical check `REL-001` for release trust controls.
- `scripts/production_review_audit.py` now includes reliability evidence check `PERF-010`.
- `scripts/production_review_audit.py` now includes Mission Control e2e gate check `UI-011`.
- `Makefile` now exposes `make promotion-gate` for local policy evaluation.
- `Makefile` now exposes `make reliability` for sustained-load qualification.
- `Makefile` now exposes `make test-ui-e2e` for Mission Control Playwright execution.
- `.github/workflows/ci.yml` now runs Mission Control Playwright e2e tests with Chromium install.
- Orchestrator internal knowledge endpoints now mirror to and retrieve from Qdrant (with PostgreSQL fallback), and runtime readiness payloads now include Qdrant dependency state.
- `.env.example` and `deploy/docker-compose.yaml` now expose Qdrant runtime controls (`QDRANT_ENABLED`, `QDRANT_COLLECTION`, `QDRANT_VECTOR_SIZE`, `QDRANT_TIMEOUT_SECONDS`, `QDRANT_API_KEY`).
- Orchestrator now supports feature-flagged Neo4j graph mirroring/query paths with readiness reporting, plus gateway route `GET /v1/missions/{mission_id}/knowledge-graph`.
- `.env.example` and `deploy/docker-compose.yaml` now expose `NEO4J_*` runtime controls and optional profiled Neo4j service wiring.
- Orchestrator now supports feature-flagged object-storage audit-artifact mirroring/listing with retention/legal-hold policy metadata and gateway route `GET /v1/missions/{mission_id}/audit-artifacts`.
- `.env.example` and `deploy/docker-compose.yaml` now expose `OBJECT_STORAGE_*` runtime controls; orchestrator requirements now include `boto3` for S3-compatible adapters.
- Canonical planning docs refreshed to align with current baseline and identify next execution phases after optional data-plane activation.
- `deploy/docker-compose.yaml` extended data-plane MinIO image tag updated to a valid release (`RELEASE.2025-09-07T16-13-09Z`) and MinIO healthcheck now uses `curl` (runtime-available) instead of `wget`.
- `Makefile` now exposes `make test-live-extended` for optional Neo4j/MinIO live qualification.
