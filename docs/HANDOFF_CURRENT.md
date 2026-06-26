# Current Handoff

Document version: 2026.06.21-a
Last updated: 2026-06-26
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

Use this file, `docs/CURRENT_TODO.md`, and `docs/IMPLEMENTATION_STATUS.md`
before consulting archived plans.

---

## Work Completed in This Session (2026-06-26 - Audit Phase 11 Mission Control E2E)

Phase 11 is complete for this pass after closing the Phase 10 reliability follow-up. Live Mission Control code, package scripts, Playwright specs, and CI workflow wiring were used as the source of truth; archived Phase 11 roadmap text was baseline context only.

Initial Phase 11 review confirmed Mission Control has current `lint`, `test`, `build`, and `test:e2e` scripts; CI installs Chromium and runs `npm run test:e2e`; and `apps/mission-control/e2e/` contains 23 Playwright journeys covering mission lifecycle, operations/persona views, settings/vault, builder/repo intake, error states, data-plane views, cost/runtime-QC panels, and accessibility checks.

First Phase 11 fix removes a Settings page hydration warning. `apps/mission-control/app/(shell)/settings/page.tsx` now renders vault table `<col>` elements from a width array, so `<colgroup>` contains only valid column elements and no whitespace text nodes.

Final Phase 11 fix strengthens production audit check `UI-011`. It now validates the Mission Control package E2E script, CI browser install and E2E step, default Playwright web config, electron-spec exclusion, trace/list reporter settings, six committed web spec files, and `.gitignore` coverage for generated Playwright reports and test results.

Validation completed: `npm --prefix apps/mission-control run lint` passes, `npm --prefix apps/mission-control run test` passes (16 files / 74 tests), `npm --prefix apps/mission-control run test:e2e` passes (23 tests) against the running backend stack, and `npm --prefix apps/mission-control run build` passes. Focused production-audit tests and focused Ruff pass for the `UI-011` hardening. The only remaining E2E console noise is the expected Next.js development-mode `eval()` warning under CSP; production build is unaffected.

Phase 11 active work is complete for this pass. Phase 12 is next; Phase 8 still carries the explicit `mission_flow_v2/` strict coverage carry-forward unless fixed or deferred.

---

## Work Started in This Session (2026-06-26 - Audit Phase 10 reliability qualification)

Phase 10 is now active after completing the tracked Phase 9 security-audit items. Use the live reliability qualification tooling as the source of truth; archived Phase 10 roadmap text is baseline context only.

First Phase 10 fix improves reliability evidence quality. `scripts/reliability_qualification.py` now includes the target `base_url`, configured `readiness_endpoints`, and `readiness_failure_counts_by_endpoint` in every JSON report. This lets operators audit sustained-load evidence and isolate readiness failures by endpoint without reconstructing CLI arguments from logs.

Second Phase 10 fix improves recovery/failure-injection diagnostics. Reliability JSON reports now include capped `mission_error_samples` and `readiness_failure_samples`, and console output prints the target base URL, readiness endpoints, and readiness failure counts by endpoint.

Third Phase 10 fix improves runbook currency. `scripts/reliability_qualification.ps1` now exposes base URL, readiness endpoint, readiness threshold, and recovery threshold parameters from the Python qualification CLI. `docs/TESTING_QUALITY_GATES.md` and `docs/OPERATIONS_RUNBOOK.md` document the current reliability evidence fields operators should verify.

Fourth Phase 10 fix adds offline evidence verification. `scripts/verify_reliability_evidence.py` rejects missing current Phase 10 evidence fields and rejects failed qualification artifacts unless explicitly run with `--allow-failed`.

Fifth Phase 10 fix refreshes baseline evidence. Docker was running, the base stack was rebuilt and started with `docker compose --env-file .env -f deploy/docker-compose.yaml up -d --build`, and gateway/orchestrator readiness both returned 200. `docs/evidence/reliability_qualification_baseline_2026-06-26.json` passed with 600 mission requests, 99.00% success, p95 0.1931s, zero readiness failures across 114 checks, recovery passed after 3 polls, and orchestrator restart injection exited 0.

Sixth Phase 10 fix hardens the transient restart window observed in that evidence. API gateway mission creation now retries `502 orchestrator unavailable` upstream persistence failures with the same mission id. Defaults are `MISSION_CREATE_UPSTREAM_MAX_ATTEMPTS=4` and `MISSION_CREATE_UPSTREAM_RETRY_DELAY_SECONDS=0.5`; other orchestrator write failures still fail immediately.

Validation completed: `tests/scripts/test_reliability_qualification.py` passes (8 tests), `tests/scripts/test_verify_reliability_evidence.py` passes (3 tests), focused Ruff passes for the reliability scripts/tests, PowerShell parser validation passes for `scripts/reliability_qualification.ps1`, the refreshed reliability qualification passed, `scripts/verify_reliability_evidence.py` verified the refreshed JSON, and `tests/services/test_api_gateway_helpers_unit.py` passes (23 tests) for the gateway retry hardening.

Phase 10 active work is complete for this pass. Phase 11 is now active for Mission Control integration and E2E regression review.

---

## Work Completed in This Session (2026-06-24 to 2026-06-26 - Audit Phase 9 security audit)

Phase 9 was started after the operator requested the next phase. The branch was first fast-forwarded to `origin/main` at `266f2a3`, which brought in Dependabot/workflow-only updates. Phase 8 still has the open `mission_flow_v2/` strict coverage finding, so do not treat Phase 8 as fully closed unless that is fixed or explicitly deferred.

Initial Phase 9 review found the repo already has `.gitleaks.toml`, `.pre-commit-config.yaml`, and GitHub Security Checks for gitleaks full-history and staged secret scanning. Existing code/tests also already cover production `AUTH_MODE` fail-fast and protocol-bus `MCP_API_KEY` production fail-closed behavior.

First Phase 9 fix adds storage-boundary sensitive-input scanning to API gateway mission creation. `create_mission()` now runs `shared_runtime.pii_guard` before orchestrator persistence and writes metadata-only scan summaries: schema version, scanner, total match count, PII types, and field/type/count rows. Raw PII/token values are not copied into the scan object. Sensitive inputs set `contains_sensitive_input`, `sensitive_input_pii_types`, and raise `data_classification` to `TIER_2_RESTRICTED` unless already classified as Tier 2/3.

Validation completed: `tests/services/test_api_gateway_helpers_unit.py` passes (19 tests) and focused Ruff passes for the API gateway file and helper tests.

Second Phase 9 fix hardens worker service-boundary auth startup. `shared_runtime.agent_keys.enforce_production_service_auth_config()` now fails production workers closed unless `AGENT_SERVICE_KEY_MODE=strict`, the fallback `SERVICE_API_KEY` is non-placeholder and strong, and configured pod/audit worker identities resolve to strong dedicated keys before Redis consumers start.

Validation completed: `tests/shared_runtime/test_agent_keys.py`, `tests/services/test_pod_worker_unit.py`, and `tests/services/test_audit_worker_unit.py` pass together (68 tests), and focused Ruff passes for the touched auth/worker files.

Third Phase 9 fix closes the first network-boundary hardening slice. `deploy/docker-compose.yaml` now publishes all host-facing ports on `127.0.0.1` by default through explicit `*_HOST_BIND` variables, including data-plane services, observability endpoints, API gateway, orchestrator, protocol-bus MCP, dashboard, and Mission Control. `.env.example` documents the loopback defaults and override path. `deploy/docker-compose.prod.yaml` now states that host-published ports are loopback by default and are not used for internal service-to-service traffic.

Validation completed: `tests/services/test_compose_network_security.py` and `tests/services/test_hardened_api_keys.py` pass together (17 tests) with `python -m pytest -o addopts= ... --basetemp .pytest-tmp` because the current Python environment has pytest but not `pytest-timeout`; focused Ruff passes for the new test; `git diff --check` passes; merged production Compose service rendering passes with `docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.prod.yaml config --services`.

Fourth Phase 9 fix closes a direct orchestrator mission-read gap. `GET /missions/{mission_id}/runtime-qc` now requires `READ_AUTH_DEP`, matching the mission list/detail/events routes and preventing anonymous localhost callers from reading runtime-QC execution previews. The unauthenticated route regression set in `tests/security/test_state_mutation_auth.py` now includes `/missions/mission-1/runtime-qc`.

Validation completed: `tests/security/test_state_mutation_auth.py` and `tests/services/test_api_gateway_auth_mode_unit.py` pass together (28 tests) with `python -m pytest -o addopts= ... --basetemp .pytest-tmp`; focused Ruff passes for the touched route/test files; `git diff --check` passes.

Fifth Phase 9 fix adds API gateway prompt/input validation at mission intake. `create_mission()` now builds a value-redacted `prompt_input_scan` with `shared_runtime.prompt_guard` over the mission prompt, style directives, attachment descriptors, and bounded metadata string fields. In log/default mode this records security metadata; with `PROMPT_GUARD_MODE=block`, high-or-higher risk input is rejected before idempotency reservation, upstream persistence, or intake telemetry.

Validation completed: `tests/services/test_api_gateway_helpers_unit.py` and `tests/services/test_prompt_guard.py` pass together (37 tests) with `python -m pytest -o addopts= ... --basetemp .pytest-tmp`; focused Ruff passes for the touched gateway/test files; `git diff --check` passes.

Sixth Phase 9 fix hardens the production object-storage TLS posture. `deploy/docker-compose.prod.yaml` now sets `OBJECT_STORAGE_REQUIRE_TLS=true` on the orchestrator and documents that production `.env` must provide an HTTPS `OBJECT_STORAGE_ENDPOINT`. `docs/SETTINGS_REFERENCE.md` now marks this as the production requirement. The existing object-store client already fails closed if TLS is required with a non-HTTPS endpoint.

Validation completed: `tests/services/test_compose_network_security.py` and `tests/services/test_object_store_unit.py` pass together (18 tests) with `python -m pytest -o addopts= ... --basetemp .pytest-tmp`; focused Ruff passes for the touched test/gateway files; `git diff --check` passes; merged production Compose service rendering passes with `docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.prod.yaml config --services`.

Seventh Phase 9 fix aligns protocol-bus replay/dedup TTL configuration. The MCP service now accepts canonical `MCP_DEDUP_TTL_SECONDS` and the legacy `MESSAGE_DEDUP_TTL_SECONDS` alias, and production Compose now uses `MCP_DEDUP_TTL_SECONDS=600`. This prevents the production replay/dedup TTL from falling back to the 300-second code default.

Validation completed: `tests/services/test_protocol_bus_mcp.py`, `tests/services/test_protocol_bus_dedup.py`, and `tests/services/test_compose_network_security.py` pass together (59 tests) with `python -m pytest -o addopts= ... --basetemp .pytest-tmp`; focused Ruff passes for the touched protocol-bus/test files; `git diff --check` passes; merged production Compose service rendering passes. The pytest command emitted post-teardown OpenTelemetry exporter logging because local `jaeger:4318` is not resolvable, but exited 0.

Phase 9 tracked security-audit items are complete for this pass. Next active work is to define/start the next audit phase, while keeping the Phase 8 `mission_flow_v2/` strict coverage carry-forward visible unless explicitly deferred.

---
## Work Started in This Session (2026-06-24 - Audit Phase 7 shared runtime)

Phase 4 is closed for this audit pass at `3cced29`. Completed fixes are committed and pushed through API gateway startup validation. Do not mark the broad Phase 4 response-model/runtime-hardening items as done without focused code work and validation.

Phase 5 is now the active audit area. First fix in this phase was pushed as `bc00a7a` and addresses the stuck `CLARIFYING` path: `/missions/{mission_id}/clarify` now re-queues the mission with `MISSION_CLARIFICATION_APPLIED`, restarts lifecycle processing, and PM intake includes `metadata["pm_clarification"]` as `operator_clarification` when rebuilding the feature contract. Focused regression coverage lives in `tests/services/test_mission_clarify_route_unit.py`.

Second Phase 5 fix was pushed as `b338976` and adds audit-facing `pod_assignment` and `language_keys` aliases to `AgentDefinition` with registry coverage in `tests/services/test_agent_personas_registry.py`. Static inventory now confirms 41 agents, no missing personas, no orphan personas, no specialist language-persona gaps, and no missing audit alias fields.

Third Phase 5 fix was pushed as `983d571` and adds permanent ghost/orphan implementation coverage in `tests/services/test_agent_base_unit.py`: registry `runtime_class` values must map to the documented synthesized-heartbeat/shared-worker implementation paths, and every concrete `BaseAgent` subclass must be reachable through `AGENT_REGISTRY`.

Fourth Phase 5 fix was pushed as `40d4cee` and updates `advance_mission_lifecycle_v2` to reset LLM mission/settings context variables in `finally`, with source-level regression coverage in `tests/services/test_mission_flow_v2.py`.

Fifth Phase 5 fix was pushed as `adfc81a` and updates `ProtocolBusConsumer` so decoded envelopes must match the lane protocol before dispatch; misrouted/corrupted messages are dropped before handlers run. Regression coverage lives in `tests/services/test_protocol_bus_consumer.py`.

Phase 6 Mission Control frontend audit is active. First Phase 6 fix was pushed as `db178d2` and converts Settings vault list/save/test/delete calls from raw `fetch` to shared `fetchJson`, preserving standard timeout and structured error handling.

Second Phase 6 fix was pushed as `7681c4d` and removes all explicit production `any` usage from `apps/mission-control/app`: maintenance catches now use `unknown`, mission-detail panels consume canonical shared types, stale panel casts are removed, and the event log uses `MissionPhaseModel`. The zero-`any`/ignore scan, TypeScript, and Vitest all pass (16 files / 74 tests).

Third Phase 6 fix was pushed as `b6d781a` and converts Repo Import and logout from raw `fetch` to shared `fetchJson`. Production client components now have zero raw `fetch` calls; TypeScript and Vitest pass (16 files / 74 tests).

Validation for this batch: bundled Python `py_compile` passes for touched backend/test files, the direct agent implementation invariant check reports 41 registry agents / 24 concrete classes / 24 reachable classes, and the direct protocol lane-guard check drops mismatched envelopes before dispatch. Focused pytest remains blocked because the bundled Python runtime has no `pytest` module; direct MissionFlowV2 runtime import is also blocked in the bundled runtime by missing `httpx`. Phase 6 is closed for this offline audit pass at `b6d781a`; generated OpenAPI client adoption, route-specific loading/error review, Playwright E2E, and live browser validation remain carry-forward items.

Phase 7 Shared Runtime closed at `35dfd50`. Inventory confirms all ten modules have active import consumers and the package root exposes no accidental symbols.

First Phase 7 fix was pushed as `a696152` and hardens `atomic_io.py` for concurrent writers with unique sibling temp files, per-destination backup/replace locking, bounded Windows sharing-violation retry, guaranteed cleanup, and regression coverage. Bundled Python `py_compile` and a direct 64-write concurrency probe pass; focused pytest remains blocked because the bundled runtime has no `pytest`.

Second Phase 7 fix was pushed as `68b86d4` and hardens `crypto_signing.py`: verification now enforces P-256, requires the signed digest with constant-time comparison, rejects malformed base64, and writes signature sidecars atomically. Syntax, direct signing-contract, and artifact-sidecar probes pass; focused pytest remains blocked by the missing `pytest` module.

Third Phase 7 fix was pushed as `ded42a5` and hardens `agent_auth.py`: signing rejects empty identity/secret values, verification validates the hex header and replay window, and future clock skew is limited separately from maximum signature age. Syntax and a direct HMAC freshness probe pass; focused pytest remains blocked by the missing `pytest` module.

Fourth Phase 7 fix was pushed as `ab32fa6` and hardens shared logging: JSON messages, exceptions, nested extras, and credential fields are redacted; plain logs redact the final rendered text; trace/span fields are preserved. Focused unit coverage was added, and bundled Python syntax plus direct behavior probes pass. Focused pytest remains blocked by the missing `pytest` module.

Fifth Phase 7 fix was pushed as `563a4d0` and hardens the shared error model: `FactoryError` sanitizes developer messages at construction, including exception text passed through `wrap_unexpected()`. Focused tests cover direct and wrapped errors; bundled Python syntax and direct probes pass. Focused pytest remains blocked by the missing `pytest` module.

Final Phase 7 work closes A-028 and the remaining checklist: production signing uses an existing read-only mounted PEM and cannot generate `PLAINv1`; signing and agent-service key files are reread for no-restart rotation; nested context redaction is recursive and cycle-safe; lifecycle unit tests no longer contact configured LLM providers; dashboard tests use the typed response contract.

Qualification is green: 128 focused shared-runtime/protocol tests pass, the full Python suite passes with 5 intentional skips, full Ruff and `git diff --check` pass, and the merged production Compose configuration exposes the mounted signing key read-only to orchestrator and audit-worker.

Phase 8 is active. Initial inventory finds 1,538 collected tests, a green full suite with 5 intentional skips, and clean Ruff. Immediate gaps are missing `pytest-randomly`/`pytest-timeout` enforcement, skip reasons without issue references, coverage-floor validation, and a test-directory checklist that does not match the repository's centralized naming convention.

First Phase 8 fix was pushed as `627fa8b` and pins/activates `pytest-randomly` plus `pytest-timeout`, with a 120-second per-test timeout. The full 1,538-test suite passes in randomized order with 5 intentional skips; no test-tree sleeps were found; Ruff and whitespace validation pass.

Current checkpoint: do not advance to Phase 9 yet. Order-dependent API gateway/protocol-bus failures were fixed and pushed at `b77da3c`. The latest Phase 8 progress adds stable coverage for storage-domain persistence and Mission Flow v2 helper/runtime gates. `tests/services/test_storage_unit.py` now covers artifact object-storage offload/fallback, testdata/runtime-QC persistence, and agent action event digest/list behavior. `tests/services/test_mission_flow_v2.py` now covers mission-charter helper edge cases, dependency-absorption skip behavior, and Runtime QC skip/complete enforcement paths. Full coverage passes with 1,545 tests, 5 intentional skips, 82.08% total coverage, and the configured CI threshold script passes. The storage gap is closed (`storage_agents.py` 98.04% XML line coverage, `storage_artifacts.py` 99.14% XML line coverage). Mission Flow v2 improved to 83.51% line / 66.27% branch but remains below the stricter 90% / 85% critical-path target.

Continue Phase 8 with scenario-level Mission Flow v2 lifecycle/build/runtime coverage or an explicit tracked deferral, then finish mock/fixture quality and event-bus integration coverage review. Backend carry-forward remains non-protocol stream dead-event/schema parity and LangGraph fallback isolation.

---

## Work Started in This Session (2026-06-21 - Audit Phase 4 backend service audit)

Phase 3 was committed and pushed to `origin/main` as `9e88bad audit-phase-3-config-wiring`.

Phase 4 is now active. The audit is application-only and covers backend service completeness, API design, error handling, health/readiness/metrics, and service-specific checks for api-gateway, orchestrator, pod-worker, agent-runtime, audit-worker, protocol-bus-mcp, and dashboard. Treat findings as fix-as-we-go items rather than report-only notes.

First Phase 4 fix completed: dashboard observability is now aligned with the rest of the backend services via `/metrics`, `prometheus-client`, and explicit JSON response contracts/status codes.

Second Phase 4 fix completed: protocol-bus producer helpers now cover all six lanes. The bus service already validates alpha/beta/delta/sigma/omega/rho and the consumer supports all six lane names; this batch added typed sigma/rho helper APIs plus helper-schema test coverage. Focused pytest could not be run locally because no repo venv exists and bundled Python has no pytest module.

Documentation hygiene decision: audit-phase helper scripts are not application artifacts. Keep temporary edit/scan scripts outside the repo, and keep committed fixes in stable, domain-named application, test, and documentation files. Current pushed audit baseline is `ff5419f`.

Third Phase 4 fix completed: API gateway startup validation now fails fast for invalid `AUTH_MODE` and rejects `CORS_ALLOW_ORIGINS=*` in production. Added focused unit tests in `tests/services/test_api_gateway_auth_mode_unit.py`; local pytest execution remains blocked because bundled Python has no pytest module.

---

## Work Completed in This Session (2026-06-21 - Audit Phase 3 configuration and dependency wiring)

**Phase 3 fixes completed:**
- Removed duplicate `.env.example` declarations and aligned the Gemini embedding model default to `gemini-embedding-001`.
- Added missing runtime, live-validation, and demo-script environment knobs to `.env.example` with safe documented defaults.
- Pinned `psycopg-pool` in the orchestrator production requirements.
- Removed stale `config/agent_api_keys.yaml`; active key configuration is via environment variables and the Mission Control vault.

**Validation completed:** Phase 3 tracked-file scan shows no duplicate env keys, no missing Python env declarations, no unpinned requirement lines, and no active config files without references. `git diff --check` is clean.

---

## Work Completed in This Session (2026-06-21 - Audit Phase 2 naming and layout)

Phase 2 naming/layout audit was started after the Phase 1 static fixes. Phase 1 still has runtime/start-stop and full pytest/Ruff validation pending because the local Python environment is not usable, but Phase 2 checks that do not require the app are complete.

**Phase 2 verification completed:**
- Service directories are kebab-case and internal Python packages use lowercase/underscore names.
- Tracked source directories have no mixed-case directory names.
- No tracked `utils.py` or `helpers.py` catch-all modules were found.
- No Python star imports were found in tracked source.
- Non-empty package `__init__.py` files now declare explicit `__all__` lists.

**Files changed:** `services/agent-runtime/agent_runtime/__init__.py`, `services/orchestrator/orchestrator/routes/__init__.py`, `services/protocol-bus-mcp/protocol_bus/__init__.py`, and `shared_runtime/__init__.py`.

**Validation completed:** Phase 2 tracked-file scan, bundled Python `py_compile` for touched initializers, and `git diff --check`.

---

## Work Completed in This Session (2026-06-21 - Audit Phase 1 fixes and documentation sync)

The application audit is now being handled as audit-plus-fix: inspect a checklist area, repair concrete app/repo defects, validate what can be validated locally, and update the tracker.

**Phase 1 fixes completed:**
- Added RIR schema regression coverage for generated RefinedIRModule payloads.
- Added example fixture schema coverage for LogicNode and RIR examples.
- Corrected traceability-ledger docs to point at active Postgres migrations instead of the legacy SQLite starter schema.
- Updated AUDIT_PLAN.md with the application-only baseline and fixed findings A-005 through A-007.

**Validation completed:** git diff --check; bundled Python py_compile for edited/new schema tests.

**Validation blocked:** pytest/Ruff cannot run because python resolves to the broken WindowsApps shim; py -3.11 reports no suitable runtime.

**Current next step:** restore a usable project Python environment or run the focused schema tests inside CI, then continue Phase 1 runtime/startup validation.
---

## Work Completed in This Session (2026-06-21 - Application-only cleanup and fallback visibility)

The operator confirmed that only the application should remain in scope. The
marketing website package was removed from the tracked application worktree so it
does not distract from Mission Control/runtime debugging.

**Repository cleanup:**
- Removed the tracked `sites/thefactory-site` tree from git staging.
- Removed the leftover untracked `sites/` directory from disk.
- Verified active docs/code do not reference `thefactory-site`, `sites/thefactory-site`,
  the marketing site, or the Vinext project scaffold outside archived material.

**Mission Control offline fix:**
- PM feature-contract degraded/fallback metadata is now part of the Mission
  Control display model.
- The chat Feature Contract panel now shows a warning when the PM contract came
  from fallback/degraded planning output, including the source/model when known.
- Local builder-preview fallback contracts are explicitly marked degraded with
  reason `pm_feature_contract_unavailable`.

**Validation completed:**
- `npm --prefix apps\mission-control run lint`
- `npm --prefix apps\mission-control run build`
- `python -m pytest tests\services\test_mission_flow_v2.py tests\services\test_runtime_unit.py -q`
- `git diff --check`

**Still required before commit/push:** commit the staged site deletion, UI
change, and documentation updates together.

**Current next step when the app is running:** use `/chat` to confirm degraded PM
output is visibly flagged, then run a fresh mission to verify the PM launch path
does not pause in `CLARIFYING` unless PM actually asks clarifying questions.

## Work Completed in This Session (2026-06-18 - MissionFlow V2 clarification, artifact, and Runtime QC visibility rebuild)

The app was stopped by the operator, then the MissionFlow V2 and Mission Control fixes were implemented and rebuilt.

**Backend lifecycle fixes:**
- Normal ready-path MissionFlow V2 no longer emits the misleading `MISSION_CLARIFYING` transition. The standard path now moves `PM_INTAKE -> FETCH`; `CLARIFYING` remains available only when PM intake actually detects high ambiguity and pauses for operator clarification.
- Runtime QC skipped states are now persisted in mission metadata as `runtime_qc_report` with `skipped: true`, `verdict: SKIPPED`, `execution_type: not_run`, and a concrete reason such as `TESTDATA disabled`, `RQCA disabled`, or `no generated output`.
- A `MISSION_RUNTIME_QC_SKIPPED` chain/mission event is recorded once per mission when runtime QC is skipped, so a completed mission no longer appears to be missing runtime-QC evidence silently.

**Mission Control fixes:**
- Mission Detail now loads generated-code artifact details from `/v1/missions/{mission_id}/build-artifacts/{artifact_id}` when chain trace only includes artifact metadata.
- The Generated Output panel now shows filename, storage backend, status, digest, and byte size, and explicitly states that generated code is persisted as a database-backed build artifact unless separately exported.
- The Runtime QC panel now renders skipped QC as an explicit status with the skip reason instead of hiding the panel or implying QC is pending.

**Validation completed:**
- `python -m pytest tests\services\test_mission_flow_v2.py tests\services\test_runtime_unit.py -q`
- `python -m ruff check services\orchestrator\orchestrator\mission_flow_v2\phases_runtime.py services\orchestrator\orchestrator\mission_flow_v2\transitions.py tests\services\test_mission_flow_v2.py tests\services\test_runtime_unit.py`
- `npm --prefix apps\mission-control run lint`
- `npm --prefix apps\mission-control run build`
- `git diff --check`

**Rebuild completed:** full-dedicated Docker image rebuild completed successfully for `orchestrator`, `api-gateway`, `mission-control`, pod workers, and all dedicated agents.

**Current next step:** restart the app and run a fresh mission. Expected behavior: a ready PM contract should launch without the normal lifecycle showing `CLARIFYING`; if PM asks clarifying questions, launch should remain blocked until scope is clarified; completed missions should show generated code as a build artifact and Runtime QC should show either a real report or an explicit skipped reason.

## Work Completed in This Session (2026-06-18 — Live app audit and PM launch fix batch)

The restarted app was inspected live at `http://localhost:3000/chat` with a
Playwright probe against the real local stack. Runtime baseline was healthy:
`/api/gateway/health` and `/api/gateway/readyz` returned healthy, the mission list
started with only `__knowledge_lake__`, and `/v1/operations/agents` showed 41/41
agents idle with active backlog 0.

**Live reproduction:** the probe submitted a fresh PM chat mission for an offline
Python flashcard trainer. `/api/pm/feature-contract` returned a real Gemini
contract (`source: llm`, `model_provider: gemini`, `model: gemini-3.5-flash`) but
also returned `intake_status: needs_clarification` and clarifying questions. The
UI still allowed **Confirm and Start**, creating
`mission-62f236b6-84d7-497e-8e0a-33a58aff5023`; the mission then moved
`QUEUED -> CLARIFYING` with `last_ambiguity_score=1.0`.

**Root cause confirmed:** mission launch persisted `user_intent: draft` even
after explicit confirmation, and the chat UI treated a PM clarification response
as launchable. This is why a newly-created mission can still get stuck in
`CLARIFYING` after the earlier truncation fixes.

**Fix batch implemented locally:**
- Mission Control chat no longer exposes a launchable Feature Contract when PM
  returns clarifying questions.
- Explicit launch now sends compact mission context and forces
  `user_intent: finalize_plan`.
- Chat history persists/restores the structured Feature Contract instead of only
  message text.
- API client now parses FastAPI 422 validation arrays into actionable messages,
  including metadata-size failures.
- API-client tests cover mission create idempotency and readable 422 validation
  errors.

**Validation completed:**
- `npm --prefix apps\mission-control run lint`
- `npm --prefix apps\mission-control test -- app/lib/api-client.test.ts`
- `npm --prefix apps\mission-control run build`
- `git diff --check`

**Still required:** restart/rebuild the running Mission Control app to pick up
the local source changes, then rerun the chat flow. A successful retest should
show: PM clarification responses do not launch; `proceed with assumptions` or
**Confirm and Start** sends `user_intent: finalize_plan`; fresh mission intake
does not pause only because the operator explicitly confirmed launch.

**Mission Control report reconciliation:** the attached UI report was checked
against current code. The canonical sidebar routes are already correct
(`/missions/history`, `/logicnodes`, `/repo`), but compatibility aliases were
added for stale report paths (`/history`, `/logic-nodes`, `/repo-import`) so
bookmarks/wireframe links land in the right shell routes. The global 404 now
renders inside the Mission Control shell, the header action label is `View
Missions` instead of the ambiguous `Mission Status`, and chat history rows now
show a persisted last-message preview plus timestamp/message count with the
duplicate header-level **New Chat** action removed.

---

## Work Completed in This Session (2026-06-18 — Proceed launch attempt and rebuild)

After the PM contract panel rendered correctly, the operator tried to continue
the Iron Meridian chat by typing `procced`. The UI displayed `Request failed
with status 422`, and a live mission list still showed only the system
`__knowledge_lake__` mission. That confirmed the failure occurred before mission
creation and before mission-flow lifecycle processing.

**Code attempt pushed to `origin/main`:**
- `edb7846` (`fix-pm-chat-proceed-launch`): expands finalize-intent detection to
  include common proceed typos (`procced`, `procede`) and short-circuits
  `sendMessage()` so proceed-style input launches the existing Feature Contract
  instead of sending another PM feature-contract / builder-preview request.

**Validation completed for the code attempt:**
- `npm --prefix apps\mission-control run lint`
- `npm --prefix apps\mission-control run build`
- `git diff --check`
- Local `:3000` route was restarted once and `/chat` returned `200`.

**Retest result:** the operator reported "that did not work" and stopped the
app. Treat `edb7846` as an attempted fix, not proven complete. The next debugging
step should inspect the actual browser network request and server-side API route
response for **Confirm and Start** and typed `proceed/procced`, rather than
guessing another frontend state path.

**Rebuild completed after app stop:**
- Local Mission Control production output rebuilt successfully with
  `npm --prefix apps\mission-control run build`.
- Docker images rebuilt without starting the stack:
  `deploy-orchestrator`, `deploy-api-gateway`, `deploy-mission-control`.
- Final state after rebuild: app stopped, no listener on port `3000`, compose
  stack not running, git clean except the existing untracked `sites/` directory.

**Next session priority:** start the app, reproduce the launch attempt, capture
the failing HTTP request/response, and verify whether the failure is:
- the button/input handler not calling `createMission()`,
- stale browser bundle/cache or old session state,
- `/api/gateway/v1/missions` payload validation,
- or gateway/orchestrator mission creation rejecting injected metadata.

---

## Work Completed in This Session (2026-06-18 — PM chat context + mission launch truncation fix)

The PM route is now API-level healthy and the chat/mission launch handoff has
been hardened for long, multi-turn operator conversations.

**Observed live failure:** the new Iron Meridian mission
`mission-c228332b-4f4e-4941-8e52-eb7494627045` paused in `CLARIFYING`. Inspection
showed the mission prompt passed to intake was truncated mid-brief at `Defeat c`,
so the PM correctly asked for the missing defeat conditions. The failure was not
Gemini, provider routing, or the data plane. It was the frontend launch prompt
builder using compact transcript text with a 1200-character per-message cap, then
mission-flow v2 rerunning intake without the richer chat PM context.

**Fixes pushed to `origin/main`:**
- `525b930` (`improve-pm-chat-context`): PM chat now sends compact
  `conversation_context`, decision memory, working contract, attachment labels,
  and `user_intent`. It detects finalize phrases such as "create the plan",
  "proceed", and "use your best judgment"; the PM prompt treats that intent as
  ready unless there is a hard blocker. This commit also fixed the operations
  polling `422` by sending gateway-accepted minimum limits.
- `37f0779` (`fix-pm-mission-launch-context`): mission launch now builds the
  launch prompt from full user-authored messages with a larger cap and stores
  `conversation_context` plus `user_intent` in mission metadata. Mission-flow v2
  intake now passes those fields into `generate_pm_feature_contract()` so the
  backend PM pass sees the same conversational context as the chat PM.

**Validation completed:**
- `npm --prefix apps\mission-control run build`
- `npm --prefix apps\mission-control run lint`
- Focused backend tests:
  `test_generate_pm_feature_contract_uses_context_and_finalize_intent` and
  `test_list_project_agent_action_events_casts_nullable_filters`
- Focused `ruff` over mission-flow/LLM delegation files
- `git diff --check`
- Docker rebuild/recreate for orchestrator, API gateway, and Mission Control was
  completed once before the operator stopped the app for a clean restart.

**Current runtime status:** the app was intentionally stopped by the operator
after validation. Restart from the updated `main` and run a **new** mission to
verify the launch-context path. The existing Iron Meridian mission is already in
`CLARIFYING` from the old truncated prompt and will not automatically prove the
fix unless it is manually clarified or requeued.

**Carry-forward items:**
- Fresh long-brief mission must reach at least post-PM intake without truncation;
  release confidence still requires one full BUILD_NEW mission to `COMPLETE` with
  non-empty generated code/artifacts.
- Add visible degraded/fallback banners in Mission Control chat and PM contract
  panels.
- Add provider/model preflight from Settings, then wire app-selected provider and
  model into runtime config instead of relying on `.env`.
- Decide whether 41 per-agent vault slots should drive per-agent LLM calls or
  collapse into one provider-level runtime key.
- Rotate the Gemini key that appeared in chat/logs.

---

## Work Completed in This Session (2026-06-17 — PM Happy Path PROVEN: gateway internal-proxy timeout)

**Blocker #1 (the Gemini happy path) is closed at the API level.** The remaining
PM failure after the four delegation fixes was a single misconfigured timeout, not
an LLM defect.

**Symptom:** A real mission in the chat UI failed with *"PM feature contract
failed: The orchestrator service is not reachable. Fallback preview failed:
Request failed with status 422."*

**Root cause:** `services/api-gateway/api_gateway/main.py` `_proxy_post_internal`
used a hardcoded `httpx.AsyncClient(timeout=4.0)`. The orchestrator's
`/internal/pm/feature-contract` invokes Gemini 3.5-flash with high thinking, which
takes ~9–19 s. The gateway gave up at exactly 4.02 s, raised `httpx.RequestError`,
and returned `502 "orchestrator unavailable"` — surfaced to the operator as the
misleading "not reachable". Latency masquerading as connectivity. (The
`/v1/builder/preview` path calls Gemini directly with its own longer timeout, which
is why builder preview worked while PM did not — a useful diagnostic contrast.)

**Fix:** `_proxy_post_internal` now takes a per-call `timeout` (default still `4.0`
for fast DB-write mutations); the PM feature-contract route passes `timeout=90.0`
to match/exceed the UI route's 60 s. Other internal POST proxies
(`_persist_mission_upstream` → `/missions`, maintenance endpoints) are fast and
left at the 4 s default.

**Proof (live, against the rebuilt gateway):**
- `POST /v1/pm/feature-contract` → `HTTP 200` in 9–19 s (was `502` at 4.02 s).
- Response: `source: llm`, `model_provider: gemini`, `model: gemini-3.5-flash`,
  `degraded: None` — a real, rich, prompt-specific feature contract, not the 1 KB
  deterministic stub. Verified across three distinct prompts.
- Gemini was already proven working via `/v1/builder/preview` (`source: gemini`).

**State:** Gateway image rebuilt and recreated; full dedicated stack healthy
(gateway `/health` 200, orchestrator `/readyz` 200, Docker Mission Control `:3100`
serving). The four prior delegation fixes were all correct and necessary — they got
Gemini working; this timeout was the last gate in front of it.

**Still open (secondary, off the critical path):**
- Operations `422`: Mission Control sends
  `/v1/operations/agents?mission_limit=0&assignment_limit=0&event_limit=0`, but the
  gateway enforces `ge=50` on those params → 422 → status bar mislabels the healthy
  runtime as "Runtime Shell". Fix UI to send ≥50 (or omit) or relax the gateway to
  `ge=0`.
- UI fallback preview `422`: the chat page's `createBuilderPreview` fallback 422'd
  even though a direct `POST /v1/builder/preview` returns 200 — body/validation
  mismatch in the `/api/gateway` proxy path. The timeout fix makes this fallback
  rarely fire, but it is still a latent contract bug.

---

## Current Branch State

- Branch: `main`. Latest pushed commit is `edb7846`
  (`fix-pm-chat-proceed-launch`) on `origin/main`; that commit is an attempted
  proceed-launch fix and still needs live proof.
- **CI was fully green** as of `941aca9` (all 12 jobs). Several backend-only
  commits and PM/frontend fixes have landed since (`44f557f`, `4fdab0a`,
  `b6d0848`, `664a5cd`, gateway timeout fix, `525b930`, `37f0779`, `edb7846`);
  CI on these should be re-confirmed.
- **PM/LLM happy path PROVEN on Gemini** (see top session log): routing honors
  `LLM_PROVIDER=gemini`, vault keys reach the providers, the Gemini payload uses
  `thinkingConfig.thinkingLevel`, AND the gateway now waits long enough for the
  call. `POST /v1/pm/feature-contract` returns a real `source: llm` /
  `gemini-3.5-flash` contract (`degraded: None`). Gateway rebuilt + recreated.
- All extended data stores (Milvus, Neo4j, MinIO/object storage) now on by
  default in code, compose, and the dev overlay.
- Live stack verified healthy 2026-06-16: gateway `/health` ok, `/readyz` 200; operations summary reports db/redis/qdrant/milvus/neo4j/object_storage/jaeger all ready; 41/41 agents healthy.
- Current change set: EDCP-01 bus durability foundation, EDCP phase planning,
  PM clarification gating, richer PM planning artifacts, PM chat context
  carry-forward, full mission launch prompt preservation, unlocked-local UX
  cleanup, embedding key UI, live agent validation, and runtime label polish.
- All tests pass (except `test_agent_base_unit.py` which requires the orchestrator
  package on PYTHONPATH — it always fails in isolation; run from
  `services/orchestrator/` or via the services test runner).
- Runtime model policy: all 41 agents default to `gemini/gemini-3.5-flash` with
  high thinking.
- Mission Control model selector: ChatGPT 5.5, Claude Opus 4.8, Gemini Flash 3.5.
- Mission Control local mode starts unlocked. PM/review proxy routes use the
  internal service key from stack configuration; there is no user-facing
  Operator Runtime Key vault row.
- Agent grid runtime labels:
  - `WORKER`: shared pod-worker runtime for specialists, pod managers, and pod audits.
  - `MANAGED`: orchestrator-managed interface/executive/support role heartbeat.
  This is intentional in the condensed local topology; dedicated per-agent
  containers are optional deployment scope, not a current requirement.

---

## Work Completed in This Session (2026-06-17 — PM/LLM Workflow: real Gemini calls + delegation hardening)

The PM agent had been emitting canned 1 KB stubs and asking no clarifying
questions. Root cause was **not** the databases — it was a chain of LLM-delegation
defects, fixed in order (each verified from the orchestrator logs):

1. **Routing** (`4fdab0a`) — with `LLM_PROVIDER=gemini`, agents whose default
   profile is OpenAI-pinned (PM/CEO → `openai_exec`) still routed to OpenAI
   whenever any OpenAI key was present, so every call hit `gpt-5.5` → 400 →
   circuit breaker → fallback. Now non-OpenAI mode always downgrades OpenAI-pinned
   profiles to Gemini.
2. **Vault keys** (`44f557f`) — `providers.py` read `current_vault_secrets` via a
   `getattr` on the package that always returned None, so Settings/vault keys were
   ignored and only `.env` keys were used. Now reads the ContextVar from `.config`.
3. **Gemini payload** (`b6d0848`) — sent `generationConfig.thinking_level`
   (snake/flat); Gemini 3.x requires `generationConfig.thinkingConfig.thinkingLevel`
   (camelCase). Was a hard 400 on every Gemini call.
4. **Delegation hardening** (`664a5cd`) — (a) no cross-provider cascade when
   `LLM_PROVIDER` is pinned (stops the gpt-5.5 breaker storm); (b) deterministic PM
   fallback now carries `degraded=True`/`degraded_reason` + explicit risk note;
   (c) Gemini key sent via `x-goog-api-key` header (out of URL logs) + 4xx body
   logged for diagnosis.

Operational config applied: `.env` `LLM_PROVIDER=gemini` (was `openai`); orchestrator
image rebuilt + container recreated after each backend commit.

### Workflow review findings (the systemic pattern)
The recurring failures share one root cause: the pipeline **silently degrades to
deterministic templates** on any LLM failure with **no operator-visible signal**,
and fragile/forward-dated model config (`gpt-5.5`, the wrong thinking field) plus a
**cross-provider cascade + shared circuit breaker** turned single defects into
total, invisible outages. Full review and remediation plan are in
`docs/CURRENT_TODO.md`.

### Confirmed working / still to verify
- Confirmed in logs: orchestrator now calls `generativelanguage.googleapis.com`
  with the vault/`.env` Gemini key. **Last observed call still 400'd on the
  `thinking_level` payload** — that was fixed in `b6d0848` and the orchestrator
  rebuilt, but a **fresh mission must still be run to confirm a `200` + real
  output** (happy path not yet observed green).
- Gemini key `AQ.Ab8RN6L...` was pasted in chat and appears in older container
  logs — **rotate it.**

### Notes for the next session
- Vault holds 41 per-agent key slots (`AGENT-NN-…-API-KEY`) + `KNOWLEDGE-EMBEDDING-API-KEY`,
  but the mission POST proxy reads a single `GEMINI-API-KEY` slot (absent), so the
  `.env` Gemini key is doing the work. Per-agent-key → per-agent-call wiring is not done.
- `gemini-3.5-flash` is a real model in this environment (confirmed via Google docs).

---

## Work Completed Earlier (2026-06-16 — Data Stores On-by-Default, Vault Auth Fix, Full CI Green)

### Extended data stores enabled by default
- `settings.py`, `docker-compose.yaml`, and `docker-compose.dev.yaml`: `milvus_enabled`,
  `neo4j_enabled`, `object_storage_enabled` flipped `False → True` everywhere; removed
  the dev overlay's hard `NEO4J_ENABLED=false`/`OBJECT_STORAGE_ENABLED=false` overrides.
- Docs reconciled (README, SETTINGS_REFERENCE, DEVELOPER_ONBOARDING, ARCHITECTURE,
  COMPOSE_ENVIRONMENT_PROFILES, IMPLEMENTATION_STATUS, DOCUMENTATION_INDEX).

### Mission Control databases page "not authorized" — root caused and fixed
- The databases page is healthy; the failure was the **standalone UI on :3000**
  sending a **stale `OPERATOR-API-KEY`** from the host vault
  (`~/.thefactory/vault.json`) which the gateway rejected (401 "invalid api key").
  The Docker UI on :3100 worked because its vault volume was wiped by `down -v`.
- Removed the stale vault slot (host-side, backup saved).
- **Self-heal code fix** (`apps/mission-control/app/api/gateway/[...path]/route.ts`):
  the proxy now retries with `INTERNAL_SERVICE_API_KEY` on a 401/403 from a stale
  operator key, so this can't silently break the operations/databases views again.

### Full CI remediation (was red for many commits; now green)
- **Dependabot**: `vite 8.0.10 → 8.0.16`, `tmp 0.2.6 → 0.2.7` (cleared 3 alerts).
- **E2E**: 4 specs updated to click the Phase 2B mission-detail tabs
  (execution/artifacts/contracts/events) before asserting panels in inactive
  (`hidden`) tabs.
- **Python import**: `runtime.py` now imports `current_vault_secrets` from
  `.llm_delegation.config` (matching the rest of the codebase) — fixed 7 ImportErrors.
- **Lint**: import-block ordering (ruff I001).
- **Coverage**: added `_llm_recommendation_for_agent` branch test to restore
  `agent_integrations.py` to 100%.
- **Release Trust**: build-provenance attestation now skipped on private repos
  (feature unavailable) and run normally on public/org repos.

### Known remaining items (not failures)
- 1 Dependabot **medium** alert: `js-yaml ≤4.1.1`, dev-only transitive via
  `@lhci/cli` (Lighthouse, pins js-yaml 3.x) and `@redocly/openapi-core`. Cannot be
  force-upgraded without breaking the Performance Smoke step; resolve when `@lhci/cli`
  adopts js-yaml 4.x. Does not affect the shipped app.
- CodeQL/code scanning is not enabled (requires GHAS on private repos); several
  actions still target the deprecated Node 20 runner (auto-forced to Node 24).
  Both are non-blocking; deferred.

---

## Work Completed Earlier This Session (2026-06-16 — Runtime Connectivity, PM Assumptions, Health Redaction)

### Standalone UI "Runtime offline / databases not connected" — root caused and fixed

**Problem:** The standalone Mission Control UI (the non-container instance on
port 3000 launched by `start_app.bat`) reported "Runtime offline — Orchestrator
unreachable at port 8100", and the Databases page showed every adapter as
Disabled/Degraded. The backend was actually fully healthy: `docker ps` showed
the gateway, orchestrator, Postgres, Redis, Qdrant and all 41 agents up, and
`curl 127.0.0.1:8100/health` returned `ok:true` with `redis_healthy:true`.

**Root cause:** `start_app.bat` assembled `MISSION_API_BASE_URL` as
`http://127.0.0.1:%_GW_PORT%` *inside* a cmd `if (...)` block, where `%_GW_PORT%`
expands at parse time — before the `set "_GW_PORT=8100"` line in the same block
runs. `API_GATEWAY_HOST_PORT` is not in `.env`, so the result was a portless URL
`http://127.0.0.1:` → port 80 → the Next.js proxy's upstream `fetch` threw →
`/api/gateway/*` returned 503. The Databases page renders every adapter flag as
"Disabled" and Redis/Postgres as "Degraded" whenever the operations-summary
fetch fails, so the screenshot statuses were UI fallback artifacts, not real
backend state.

| File | Change |
|------|--------|
| `start_app.bat` | Assemble `MISSION_API_BASE_URL` as a standalone statement after `_GW_PORT` is set, outside the `if`-block, so the port is included |
| `apps/mission-control/app/api/gateway/[...path]/route.ts` | Hardened `DEFAULT_GATEWAY_BASE` from `http://localhost:8100` to `http://127.0.0.1:8100` so an unset env cannot hit the Windows IPv6 (`::1`) path |

**Verification:** Container UI proxy (`:3100`) returns 200; live operations
summary confirms `db_ready`, redis/protocol, `qdrant_ready`, `milvus_ready`,
`neo4j_ready`, `object_storage_ready`, and `jaeger_ready` all `True`. Commit
`04e4fef`. The running :3000 process still has the stale env until
rebuilt/restarted.

### PM feature-contract `assumptions` field now persisted

**Problem:** The PM prompt asks the model for an `assumptions` list, but the
normalizer and deterministic fallback dropped it, so the field never reached the
mission charter.

| File | Change |
|------|--------|
| `services/orchestrator/orchestrator/llm_delegation/normalizers.py` | Persists `assumptions` (string list, limit 6) on the normalized contract |
| `services/orchestrator/orchestrator/llm_delegation/fallbacks.py` | Sets `assumptions: []` on the deterministic fallback contract |

**Verification:** Ruff clean for the four `llm_delegation` files. Commit `f726de4`.

### api-gateway `/health` no longer leaks the Redis password

**Problem:** `GET /health` returned `redis_url` verbatim, including the Redis
password in the URL userinfo.

| File | Change |
|------|--------|
| `services/api-gateway/api_gateway/main.py` | Added `_redact_url_credentials()`; `/health` now returns `rediss://:***@redis:6380/...` with host/port/cert path preserved |

**Verification:** Ruff clean; redaction confirmed on a sample URL. Commit `d743d4e`.

### Pending before next run

- These three commits (`f726de4`, `04e4fef`, `d743d4e`) are **local only** —
  push to origin when approved.
- The standalone :3000 UI must be rebuilt/restarted to pick up `04e4fef`
  (operator is orchestrating stop → rebuild → restart). The `orchestrator`,
  `api-gateway`, and `mission-control` images should be rebuilt so all three
  commits are baked into the running stack.
- The Gemini live BUILD_NEW proof (S1-01) is still the gate before any
  EDCP-02+ load-bearing control-plane work.

---

## Work Completed in This Session (2026-06-14, batch 2 — EDCP Plan + PM Intake Corrections)

### EDCP-01 Bus Durability Foundation

**Problem:** EDCP could not safely make Protocol Bus events load-bearing while
the orchestrator consumer only used non-durable `XREAD` from `$`.

| File | Change |
|------|--------|
| `services/orchestrator/orchestrator/protocol_bus_consumer.py` | Added opt-in consumer-group mode with `XGROUP CREATE`, `XREADGROUP`, and `XACK`; legacy `XREAD` remains default |
| `services/orchestrator/orchestrator/protocol_bus_producer.py` | Added `send_omega_message`, `send_beta_result`, and `send_delta_audit` helpers |
| `services/orchestrator/orchestrator/settings.py` | Added `event_driven_control_plane_enabled` defaulting false |
| `.env.example`, `deploy/docker-compose.yaml` | Added `EVENT_DRIVEN_CONTROL_PLANE_ENABLED=false` |
| `tests/services/test_protocol_bus_consumer.py` | Added grouped consumption, ack/non-ack, and schema-validation tests |

**Validation:** `test_protocol_bus_consumer.py` and
`test_orchestrator_agent_key_mode.py` pass; Ruff passes for touched Python
files. EDCP-02 through EDCP-05 remain pending.

### Event-Driven Control Plane Phase Plan

**Problem:** The current mission lifecycle is a direct in-process function
pipeline; Protocol Bus messages are mostly telemetry rather than the command
backbone.

| File | Change |
|------|--------|
| `docs/EDCP_Phase_Plan.md` | Added phased plan EDCP-01 through EDCP-05: bus durability, missing lane senders, PM to CEO handoff, CEO to pod Alpha promotion, support-ring Delta gates, and final demotion of `missions.state` to projection-only |

**Key rule:** EDCP-01 foundation is complete. Do not start EDCP-02 or later
load-bearing control-plane inversion until a live Gemini BUILD_NEW mission
reaches COMPLETE with non-empty generated code.

### PM Intake Clarification + Planning Package

**Problem:** The PM Agent could turn a detailed but underspecified request into
a generic launchable plan without asking clarifying questions.

| File | Change |
|------|--------|
| `services/orchestrator/orchestrator/llm_delegation/normalizers.py` | Preserves `intake_status` from PM model output |
| `services/orchestrator/orchestrator/llm_delegation/text.py` | Treats `intake_status=needs_clarification` as authoritative for ambiguity scoring |
| `services/orchestrator/orchestrator/mission_flow_v2/base.py` | Adds SOW, product requirements, phased build plan, risk register, and test strategy fields to mission charters |
| `apps/mission-control/app/(shell)/chat/page.tsx` | Shows clarifying questions instead of creating a launchable contract when PM says scope is not ready |
| `apps/mission-control/app/(shell)/settings/page.tsx` | Removes the user-facing Operator Runtime Key vault row |

**Validation:** Focused PM/mission-flow Python suite passed: 125 tests. Ruff
passed for touched orchestrator packages and tests.

---

## Work Completed in This Session (2026-06-14, batch 1 — UI Polish: Mission Output, Navigation & Editing)

### Mission Output Folder Browser + Dedicated Workspace

**Problem:** Completed missions had no clear path to find the generated code or
release the product. The mission detail page showed metadata only, with no
artifact browser or download/release action accessible from the main UI.

| File | Change |
|------|--------|
| `apps/mission-control/app/(shell)/missions/detail/page.tsx` | Added **Artifacts** tab with full folder tree browser: collapsible directories, file icons by extension, copy-to-clipboard and full text preview per file; release flow wired to download endpoint |
| `apps/mission-control/app/api/missions/[id]/artifacts/route.ts` | New `GET` route returning structured artifact manifest (path, size, type) from the orchestrator artifacts store |
| `services/api-gateway/main.py` | Fixed 404 on `/v1/missions/{id}/artifacts` — route was missing; now delegates to orchestrator artifact list endpoint |
| `apps/mission-control/app/(shell)/missions/detail/page.tsx` | Sub-tabs (Overview / Artifacts / Logs / LogicNodes) now fully wired: active tab renders correct panel, stale empty-state replaced |

**Validation:** TypeScript `--noEmit` clean; `npm run build` passed.

---

### Auto-Expanding Sidebar (Chat page)

**Problem:** The Conversations sidebar on the Chat page was hidden/pushed off-screen
when sidebar content overflowed, wasting horizontal space in the main body.

| File | Change |
|------|--------|
| `apps/mission-control/app/globals.css` | `.chat-history-sidebar` changed from fixed `width: 240px` to `flex: 0 0 240px; min-width: 0; overflow: hidden` so it never overflows its grid cell; `.chat-history-item-title` constrained with `max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap` so long titles no longer cause layout blowout |

---

### Feature Contract Edit Modal

**Problem:** Clicking **Edit** on the Feature Contract panel opened a cramped
inline form with a 3-row textarea — insufficient for long mission descriptions.

| File | Change |
|------|--------|
| `apps/mission-control/app/(shell)/chat/page.tsx` | Added `editTitle`, `editLanguages`, `editScope` state; Edit button pre-populates these and sets `editingContract=true`; inline form removed and replaced by full-screen modal rendered inside the page root div |
| `apps/mission-control/app/globals.css` | Added `.contract-edit-backdrop` (fixed full-screen, blurred overlay), `.contract-edit-modal` (760 px max, 90 vh, spring animation), header/body/footer/input/textarea classes with focus rings; responsive sheet-from-bottom on mobile |

**Modal behaviours:** Escape key, backdrop click, and Cancel button all close
without saving. Save applies `sanitizeUserText` to Title/Languages and trims
Scope before writing back to contract state.

**Validation:** TypeScript `--noEmit` clean; `npm run build` passed.

---

### UI Auth and Settings Fixes

**Problem:** The UI Settings page falsely reported "Runtime offline" and the Databases page reported "Not authorized" because the local Next.js proxy was missing the `INTERNAL_SERVICE_API_KEY` for internal orchestrator routes. The "Real embeddings are off" warning was also hardcoded to always display.

| File | Change |
|------|--------|
| `apps/mission-control/app/api/gateway/[...path]/route.ts` | Modified the proxy to inject `INTERNAL_SERVICE_API_KEY` from the server environment for `/internal/*` routes. |
| `apps/mission-control/app/(shell)/settings/page.tsx` | Conditionally displays the embedding warning (now shows a success badge if the vault slot is set), and `orchestratorOffline` is now only triggered on actual network errors (503 or fetch failure). |
| `start_app.bat` | Exports `INTERNAL_SERVICE_API_KEY` and `MISSION_API_BASE_URL` into the spawned Next.js dev/prod server process so server-side API routes have the key available when running outside Docker. |

**Validation:** UI renders correctly and authenticates against the orchestrator.

---

## Work Completed in This Session (2026-06-13, batch 3)

### Mission Control Operator Recovery + Key Setup

**Problem:** PM Agent chat failed with `Operator authentication required` and a
fallback timeout, leaving the operator without a recovery path. Settings
documented embedding environment variables but did not expose an embedding key
slot in the vault table.

| File | Change |
|------|--------|
| `apps/mission-control/app/(shell)/chat/page.tsx` | Converts runtime auth/key failures into a local-stack recovery message |
| `apps/mission-control/app/api/pm/feature-contract/route.ts` | Internal service key fallback routes PM feature-contract calls without a user-facing operator key slot |
| `apps/mission-control/app/(shell)/settings/page.tsx` | Renders operator unlock, adds `KNOWLEDGE-EMBEDDING-API-KEY` vault row, and adds a Knowledge Embeddings configure action |
| `apps/mission-control/app/lib/server/vault.ts` | Preserves embedding model metadata (`gemini-embedding-001`, `text-embedding-3-*`) |
| `apps/mission-control/app/(shell)/agents/page.tsx` | Renames confusing `SYNTHETIC` badge to `MANAGED` and uses neutral styling |

**Validation:** `npm --prefix apps/mission-control run lint`, focused vault
Vitest suite, and `npm --prefix apps/mission-control run build` passed locally.
Live backend validation also passed after starting the full dedicated stack:
`/v1/operations/agents` returned 41/41 agents with `heartbeat_source=live`,
all in `IDLE`; runtime readiness showed Redis, PostgreSQL, Qdrant, Milvus,
Neo4j, object storage, protocol validation, and consumer task ready/running.
The local Google test key was saved to `KNOWLEDGE-EMBEDDING-API-KEY` and a
real Gemini `gemini-embedding-001:embedContent` call returned a 3072-dimension
embedding vector.

---

## Work Completed in This Session (2026-06-13, batch 2)

### Commit `d52d978` — Knowledge Embedding Key + Semantic Search Gate

**Problem:** No way to set a separate API key for embedding calls; semantic search
enabled even when no real key was available (deterministic SHA-256 hash vectors were
being written to Qdrant silently).

| File | Change |
|------|--------|
| `settings.py` | Added `knowledge_embedding_api_key: str = ""` field; `qdrant_vector_size` default raised 64 → 256 |
| `knowledge_embeddings.py` | `_gemini_embedding` and `_openai_embedding` now prefer `KNOWLEDGE_EMBEDDING_API_KEY`; added `task_type` parameter to `_gemini_embedding` and `vector_for_content` |
| `knowledge_lake.py` | New `_embedding_key_available()` helper; `_semantic_search_enabled()` now requires all three: Qdrant enabled + real provider + non-empty key |
| `deploy/docker-compose.yaml` | Wired `KNOWLEDGE_EMBEDDING_API_KEY` env var; `QDRANT_VECTOR_SIZE` default raised to 256 |
| `apps/mission-control/app/(shell)/settings/page.tsx` | New "3. Knowledge Embeddings" UI panel explaining env vars; old sections 3/4 renumbered to 4/5 |

### Commit `bdf73b2` — Query Embedding Task Type + LangGraph PgBouncer Guard + Doc Reconciliation

**Problem 1:** `_vector_search` was passing `content={"language": ..., "concept": ...}`
(no `combined_text` key) to `vector_for_content`, causing `_content_text()` to
JSON-serialize the dict and send it as the query text to Gemini. Also, it used
`RETRIEVAL_DOCUMENT` (indexing task type) instead of `RETRIEVAL_QUERY` for search
queries — semantically wrong embeddings.

**Problem 2:** `langgraph_lifecycle.py` silently fell back to `settings.postgres_url`
(PgBouncer in transaction-pool mode) when `LANGGRAPH_CHECKPOINTER_POSTGRES_URL` was
not set. PgBouncer transaction-pool drops session-level advisory locks between
statements, silently corrupting LangGraph checkpoint state.

**Problem 3:** `docs/KNOWLEDGE_LAKE_AND_EMBEDDINGS.md` described a fictional
`KnowledgeLake` class with `write/query/get_graph/purge` methods that don't exist.
`docs/STORAGE_LAYER.md` listed fictional module names (`storage_events.py`,
`storage_approvals.py`) instead of the actual five domain modules.

| File | Change |
|------|--------|
| `knowledge_lake.py` | Fixed `_vector_search`: `content={"combined_text": concept_key}`, `task_type="RETRIEVAL_QUERY"` |
| `langgraph_lifecycle.py:683` | Replaced silent PgBouncer fallback with explicit guard: logs CRITICAL and returns False when URL is empty |
| `docs/KNOWLEDGE_LAKE_AND_EMBEDDINGS.md` | Complete rewrite — module-level API, Postgres-first design, embedding pipeline, semantic search gate, `task_type` usage |
| `docs/STORAGE_LAYER.md` | Complete rewrite — accurate module list, correct table names (`mission_state_events`, `mission_pod_assignments`, `mission_knowledge`, `agent_runtime_heartbeats`, `agent_action_events`), accurate function tables |
| `README.md` | Data Systems table: Milvus/Neo4j/MinIO changed from `✅ Active` to `⚙️ Integrated / off by default` |

### Commit `c07da61` — Knowledge Lake Unit Tests (previously zero coverage)

| File | Tests added |
|------|-------------|
| `tests/services/test_knowledge_lake_unit.py` | **37 new tests** — `_embedding_key_available`, `_semantic_search_enabled`, `is_stocked`, `index_documentation`, `_mirror_to_qdrant`, `query_documentation` routing, `_vector_search` RETRIEVAL_QUERY regression, `_keyword_search`, `get_language_context` |
| `tests/services/test_knowledge_embeddings_unit.py` | +5 tests: Gemini happy path, `task_type` forwarding captured from HTTP body, `KNOWLEDGE_EMBEDDING_API_KEY` overriding both `GEMINI_API_KEY` and `OPENAI_API_KEY` |
| `tests/services/test_langgraph_lifecycle_unit.py` | +1 test: empty `LANGGRAPH_CHECKPOINTER_POSTGRES_URL` must return False, not fall back to PgBouncer |

### Commit `44cb9c8` — Multiagent System Bug Fixes (silent failures)

A structured audit of all 41 agents, state machine, Redis routing, heartbeat
infrastructure, and protocol bus identified four files with bare `except Exception`
blocks that swallowed failures with no log output:

| File | Fix |
|------|-----|
| `is_agent.py:182,199` | `_knowledge_is_indexed` and `_knowledge_is_current` now log DEBUG on storage errors; was silently returning False, masking Postgres outages |
| `dependency_absorption.py:966` | DEPABS LLM replacement failure now logs WARNING with language/library; added missing `logging` module + `LOGGER`; returns `{"error": str(exc)}` instead of empty dict |
| `knowledge_embeddings.py:68` | Cost-ledger outer except now logs DEBUG (was `pass`) |
| `port_coordinator.py:189,207` | AIM extraction and specialist plan fallbacks now log WARNING with `mission_id` |
| `port_coordinator.py` return | Added `extraction_degraded: bool` to `coordinate_port_extraction()` return value so RQCA/downstream agents know when fidelity is reduced |

---

## Verified Healthy (from audit)

- **State machine** — `models.py:152-193` — 13 states, no dead ends, no orphan states,
  all transitions bidirectional for v1/v2 compatibility
- **Agent registry** — `agent_registry.py` — all 41 agents with correct IDs, categories,
  pod assignments, language mappings
- **Redis stream routing** — `protocol_bus_consumer.py` — XREAD/XADD/XREADGROUP
  correctly wired; 6 protocol lanes (alpha/beta/delta/sigma/omega/rho)
- **Heartbeat infrastructure** — `heartbeat_service.py` — synthetic heartbeats fire on
  schedule; stale consumer reaping implemented
- **Agent dispatch** — `agent-runtime/main.py` (support agents) and
  `pod-worker/main.py` (specialists) correctly import and call `make_agent().execute()`

**Architectural note:** The orchestrator is a pure state-machine router — it does not
call `make_agent()` directly. Agents execute out-of-process in `agent-runtime` and
`pod-worker`. This is intentional (microservice decomposition) but means: if
`agent-runtime` is down, support-agent missions stall with no in-process fallback.

---

## Remaining Open Issues (see `docs/CURRENT_TODO.md`)

Four HIGH items from the multiagent audit are not yet fixed:

1. **No startup agent health check** — AGENT_REGISTRY is never cross-referenced
   against live heartbeats at boot. If `agent-runtime` is down, missions accept and
   route but never complete.
2. **LangGraph thread ID collision on replay** — thread_id is `{prefix}:{mission_id}`,
   so replaying a mission ID merges checkpoint state with the original run.
3. **Heartbeat interval mismatch** — orchestrator pulses every 5 s
   (`AGENT_HEARTBEAT_INTERVAL_SECONDS`); `agent-runtime` defaults to 15 s. The
   stale threshold must exceed the agent-runtime interval.
4. **Sigma lane handler binding — VERIFIED 2026-06-16.** `main.py`
   `protocol_bus_consumer_loop` registers `handlers = {"sigma": _handle_sigma_knowledge_ready}`
   on a `ProtocolBusConsumer` (agent `AGENT-03-BROKER`), guarded by
   `PROTOCOL_BUS_CONSUMER_ENABLED`. Binding path confirmed end-to-end.

---

## Watch Items

- `test_agent_base_unit.py` requires the orchestrator on `sys.path` — it fails under
  the root `pytest` invocation. Run as `cd services/orchestrator && python -m pytest`
  or add `services/orchestrator` to `PYTHONPATH`.
- The OTel/Jaeger exporter logs `Failed to export span batch` during test teardown
  because Jaeger is not running locally. This is harmless — the exporter retries and
  drops on shutdown. It does not affect test results.
- Archived docs under `docs/archive/2026-06-13/` are historical only. Do not
  resurrect them as active work without reconciling into `CURRENT_TODO.md`.
