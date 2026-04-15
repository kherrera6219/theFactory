# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased]

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
- **Compact PageHeader variant (Medium):** `PageHeader` component now accepts a `compact` boolean prop; renders a slim border-bottom bar (1.3rem h1, no panel chrome) on all operational pages (Agents, Chat, Missions, LogicNodes, Semantic Bus, Databases, Repo, Settings, Alerts, Builder, Performance, Projects). Home/Launch Pad keeps the full hero panel
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
- `deploy/docker-compose.prod.yaml` — comprehensive production overlay: activates `PII_GUARD_MODE=redact` and `PROMPT_GUARD_MODE=block` for api-gateway and orchestrator; tightens circuit breaker to 3 failures / 60s recovery for all dedicated agent workers; reduces semantic bus backpressure limit to 5 000 and extends dedup TTL to 600s; sets `LOG_LEVEL=WARNING` across all services; adds `AUDIT_LOG_ENABLED=true`
- `.github/workflows/ci.yml` — added CycloneDX JSON SBOM generation alongside existing SPDX JSON (both formats uploaded as CI artifacts); SLSA provenance already generated via `actions/attest-build-provenance@v2`

### Phase 3 — Intelligence Layer Upgrade (2026-03-31)

#### Added
- `services/pod-worker/pod_worker/ast_extractor.py` — AST-based Python extraction using the built-in `ast` module; provides `AstFunctionInfo`, `AstClassInfo`, `AstImportInfo`, and `AstExtractionResult` with accurate function/class/import detection, type annotation extraction, decorator capture, and docstring harvesting; graceful fallback on SyntaxError
- `tests/services/test_ast_extractor.py` — 36 unit tests covering function/class/import extraction, async detection, decorator capture, edge cases, and frozen-dataclass immutability
- `tests/services/test_circuit_breaker.py` — 18 unit tests for the CLOSED→OPEN→HALF-OPEN circuit breaker state machine in agent-runtime
- `tests/services/test_semantic_bus_dedup.py` — 8 integration tests for message deduplication (Redis SET NX EX on `correlation_id`) and backpressure (503 + `Retry-After: 5` when queue > limit), including graceful-degradation coverage

#### Changed
- `services/agent-runtime/agent_runtime/main.py` — added `_CircuitBreaker` class (CLOSED/OPEN/HALF states, configurable `CIRCUIT_FAILURE_THRESHOLD` and `CIRCUIT_RECOVERY_SECONDS`); integrated into `_request()` to fail-fast when orchestrator is unreachable; added `AGENT_CIRCUIT_OPEN` Prometheus counter
- `services/semantic-bus-mcp/semantic_bus/mcp_server.py` — added message deduplication via Redis SET NX EX keyed on `correlation_id` (idempotent 200 response with `"deduplicated": true`); added backpressure check via `xlen` against `BACKPRESSURE_QUEUE_LIMIT` (default 10 000) with `Retry-After: 5` header; added `MESSAGES_DEDUPLICATED` Prometheus counter

### Phase 2 — Security Hardening (2026-03-31)

#### Added
- `shared_runtime/pii_guard.py` — PII detection and redaction module; patterns for SSN, credit card, email, phone (US + intl), JWT tokens, hex/base64 API keys, password KV pairs, IP addresses; overlap-aware deduplication; `detect_pii`, `redact_pii`, `has_pii`, `scan_dict_for_pii`, `safe_context_json_redact`
- `shared_runtime/prompt_guard.py` — prompt injection detection and sanitization; patterns for system-tag delimiter smuggling, INST-tag injection, human-turn injection, role override, jailbreak keywords, agent-ID injection, prompt extraction, and base64 content; `check_prompt` returns `InjectionResult` with risk level; `sanitize_prompt` strips known attack vectors
- `tests/services/test_pii_guard.py` — 22 unit tests for all PII detection, redaction, and dict-scanning paths
- `tests/services/test_prompt_guard.py` — 17 unit tests covering all injection patterns, sanitization, and risk-level escalation
- `apps/mission-control/e2e/mission-control-extended.spec.ts` — 13 Playwright E2E tests covering mission failure path, full v2 lifecycle, vault/settings, agents grid, semantic bus monitor, accessibility, and databases page
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
  - `services/semantic-bus-mcp/semantic_bus/tracing.py`
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
- Semantic Bus MCP service (`services/semantic-bus-mcp`) with:
  - six-protocol payload validation (alpha/beta/delta/sigma/omega/rho)
  - `/send`, `/health`, `/readyz`, `/metrics`, and `/dlq` endpoints
  - payload size enforcement and sender identity checks
- Infrastructure hardening updates in `deploy/docker-compose.yaml`:
  - restart policies, log rotation, healthchecks, resource controls
  - dedicated `hgr-network`
  - optional extended data plane services (MinIO/Milvus profile)
  - Jaeger and semantic-bus-mcp service definitions
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
  - `docs/runbooks/semantic_bus_incident_runbook.md`
- Core coverage validation utility:
  - `scripts/check_coverage_thresholds.py`
- Core agent/runtime test suite expansion:
  - `tests/services/test_agent_core_unit.py`
  - targeted branch tests for protocol/runtime, semantic-bus, pod-worker, and audit-worker paths
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
  - frontend EventSource transport integration for mission detail, Semantic Bus, and agent operations views
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
