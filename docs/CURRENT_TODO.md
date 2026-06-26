# Current TODO

Document version: 2026.06.21-a
Last updated: 2026-06-26
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

This is the active TODO list for theFactory. Superseded sprint plans and
historical backlogs live under `docs/archive/` and should not be treated as
current work.

---

## Latest Status - Audit Phase 10 Reliability Qualification Started (2026-06-26)

Phase 10 starts from the live long-duration reliability tooling instead of archived baseline status. Initial scope is reliability evidence quality, readiness/recovery diagnostics, and the qualification script/runbook path.

First Phase 10 fix: `scripts/reliability_qualification.py` now writes the target `base_url`, configured `readiness_endpoints`, and `readiness_failure_counts_by_endpoint` into the JSON report. This makes sustained-load evidence self-contained and lets operators distinguish a gateway readiness issue from an orchestrator readiness issue without reconstructing CLI arguments from logs.

Second Phase 10 fix: reliability reports now include capped `mission_error_samples` and `readiness_failure_samples`, and console output prints the target base URL, readiness endpoints, and readiness failure counts by endpoint. This gives operators immediate recovery/failure-injection diagnostics without needing to rerun the qualification job.

Third Phase 10 fix: `scripts/reliability_qualification.ps1` now exposes the Python qualification controls for base URL, readiness endpoints, readiness polling/failure thresholds, and recovery polling/timeout thresholds. `docs/TESTING_QUALITY_GATES.md` and `docs/OPERATIONS_RUNBOOK.md` now document the current evidence fields operators must verify in reliability reports.

Fourth Phase 10 fix: `scripts/verify_reliability_evidence.py` validates refreshed reliability JSON before it is accepted as current Phase 10 evidence. It requires the target, readiness endpoint, endpoint failure-count, capped failure-sample, recovery, failure-injection, threshold, pass/fail, and failure-reason fields added by the live qualification script.

Fifth Phase 10 fix: baseline reliability evidence was refreshed against the running local Docker stack at `docs/evidence/reliability_qualification_baseline_2026-06-26.json`. The run used the default 300 second sustained load, 2 requests/second, 12 concurrency, and orchestrator restart injection. Result: pass, 600 mission requests, 99.00% success, p95 0.1931s, max latency 1.0678s, 114 readiness checks, zero readiness failures, recovery probe passed after 3 polls, and failure injection exited 0.

Sixth Phase 10 fix: API gateway mission creation now retries transient `502 orchestrator unavailable` upstream persistence failures using the same gateway-generated mission id. Defaults are `MISSION_CREATE_UPSTREAM_MAX_ATTEMPTS=4` and `MISSION_CREATE_UPSTREAM_RETRY_DELAY_SECONDS=0.5`. This targets the six transient 502 mission-create samples observed during the successful orchestrator restart qualification without masking non-retryable orchestrator write failures.

Validation: `tests/scripts/test_reliability_qualification.py` passes (8 tests), `tests/scripts/test_verify_reliability_evidence.py` passes (3 tests), focused Ruff passes for the reliability scripts/tests, PowerShell parser validation passes for `scripts/reliability_qualification.ps1`, live Docker readiness probes returned 200 for gateway and orchestrator, the refreshed reliability qualification passed, `scripts/verify_reliability_evidence.py` verified the refreshed JSON, and `tests/services/test_api_gateway_helpers_unit.py` passes (23 tests) for the gateway retry hardening.

Next active work: begin Phase 11 Mission Control integration and E2E regression review from live code and current CI/test scripts, not the archived baseline alone.

---

## Latest Status - Audit Phase 9 Security Audit Completed (2026-06-26)

Phase 9 started after fast-forwarding through Dependabot/workflow updates to `266f2a3` and is now complete for the tracked security-audit checklist. Phase 8 still carries the open `mission_flow_v2/` strict coverage finding unless explicitly deferred.

Initial Phase 9 review confirms `.gitleaks.toml`, `.pre-commit-config.yaml`, and `.github/workflows/security.yml` already provide the expected gitleaks coverage for full-history CI scans and staged-file pre-commit scans. Existing Phase 4/7 work also already covers production `AUTH_MODE` fail-fast, protocol-bus `MCP_API_KEY` production fail-closed behavior, and rotatable agent/service signing keys.

First Phase 9 fix: API gateway mission creation now runs deterministic `shared_runtime.pii_guard` scanning over prompt, source code, style directives, attachment descriptors, and submitted metadata before orchestrator persistence. The stored scan metadata contains only field names, PII types, and counts; it never duplicates matched values. Sensitive missions are tagged with `contains_sensitive_input`, `sensitive_input_pii_types`, and `data_classification=TIER_2_RESTRICTED` unless already classified higher.

Validation: `tests/services/test_api_gateway_helpers_unit.py` passes (19 tests) and focused Ruff passes for `services/api-gateway/api_gateway/main.py` plus the helper tests.

Second Phase 9 fix: pod-worker and audit-worker now enforce production service-auth posture at startup through `shared_runtime.agent_keys.enforce_production_service_auth_config()`. Production requires `AGENT_SERVICE_KEY_MODE=strict`, rejects placeholder fallback `SERVICE_API_KEY` values such as `worker-key`, and verifies strong dedicated keys for the configured worker identity before Redis consumers start.

Validation: `tests/shared_runtime/test_agent_keys.py`, `tests/services/test_pod_worker_unit.py`, and `tests/services/test_audit_worker_unit.py` pass together (68 tests), and focused Ruff passes for the touched auth/worker files.

Third Phase 9 fix: base Compose host-published ports now default to loopback through explicit `*_HOST_BIND=127.0.0.1` controls for data-plane services, observability ports, API gateway, orchestrator, protocol-bus MCP, dashboard, and Mission Control. Operators can still intentionally publish beyond the workstation by overriding the matching bind variable. `.env.example` documents the controls, and production compose comments now reflect that host-published ports are not required for service-to-service traffic.

Validation: `tests/services/test_compose_network_security.py` and `tests/services/test_hardened_api_keys.py` pass together (17 tests) with local pytest addopts overridden because this Python environment lacks `pytest-timeout`; focused Ruff passes for the new compose security test; `git diff --check` passes; `docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.prod.yaml config --services` renders successfully.

Fourth Phase 9 fix: direct orchestrator `GET /missions/{mission_id}/runtime-qc` now requires `READ_AUTH_DEP`, matching the other mission read routes and preventing anonymous localhost callers from reading runtime execution/QC previews from mission metadata. `tests/security/test_state_mutation_auth.py` now covers this route in the unauthenticated mission-read regression set.

Validation: `tests/security/test_state_mutation_auth.py` and `tests/services/test_api_gateway_auth_mode_unit.py` pass together (28 tests) with local pytest addopts overridden because this Python environment lacks `pytest-timeout`; focused Ruff passes for the touched route/test files; `git diff --check` passes.

Fifth Phase 9 fix: API gateway mission creation now runs deterministic `shared_runtime.prompt_guard` scanning over submitted prompt text, style directives, attachment descriptors, and bounded metadata string fields before orchestrator persistence. The stored `prompt_input_scan` contains only field names, attack types, risk levels, and counts; it never stores matched prompt text. When `PROMPT_GUARD_MODE=block` and the risk meets `PROMPT_GUARD_BLOCK_LEVEL` (default `high`), mission creation rejects the request before idempotency reservation, orchestrator persistence, or intake telemetry.

Validation: `tests/services/test_api_gateway_helpers_unit.py` and `tests/services/test_prompt_guard.py` pass together (37 tests) with local pytest addopts overridden because this Python environment lacks `pytest-timeout`; focused Ruff passes for the touched gateway/test files; `git diff --check` passes.

Sixth Phase 9 fix: production Compose now sets `OBJECT_STORAGE_REQUIRE_TLS=true` for the orchestrator and documents that production operators must override `OBJECT_STORAGE_ENDPOINT` to an HTTPS S3-compatible endpoint. This uses the existing object-store fail-closed behavior that rejects non-HTTPS endpoints when TLS is required. `docs/SETTINGS_REFERENCE.md` now reflects the production requirement.

Validation: `tests/services/test_compose_network_security.py` and `tests/services/test_object_store_unit.py` pass together (18 tests) with local pytest addopts overridden because this Python environment lacks `pytest-timeout`; focused Ruff passes for the touched test/gateway files; `git diff --check` passes; `docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.prod.yaml config --services` renders successfully.

Seventh Phase 9 fix: protocol-bus replay/dedup TTL configuration is now aligned. `protocol_bus.mcp_server` accepts both canonical `MCP_DEDUP_TTL_SECONDS` and legacy `MESSAGE_DEDUP_TTL_SECONDS`, while production Compose now uses the canonical `MCP_DEDUP_TTL_SECONDS=600`. This prevents the production 10-minute replay/dedup window from being silently ignored. The existing replay/dedup suites verify duplicate rejection, idempotent dedup returns, cross-client Redis-backed detection, fail-closed Redis errors, and the production Compose variable.

Validation: `tests/services/test_protocol_bus_mcp.py`, `tests/services/test_protocol_bus_dedup.py`, and `tests/services/test_compose_network_security.py` pass together (59 tests) with local pytest addopts overridden because this Python environment lacks `pytest-timeout`; focused Ruff passes for the touched protocol-bus/test files; `git diff --check` passes; `docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.prod.yaml config --services` renders successfully. The focused pytest run emitted post-teardown OpenTelemetry exporter logging because local `jaeger:4318` is not resolvable, but the test process exited 0.

Phase 9 tracked security-audit items are complete for this pass. Next active work: define or start the next audit phase, while keeping the Phase 8 `mission_flow_v2/` strict coverage carry-forward visible unless explicitly deferred.

---
## Latest Status - Audit Phase 8 Test Coverage Audit Started (2026-06-24)

Phase 4 is closed for this audit pass at `3cced29`. Completed Phase 4 app fixes: dashboard metrics/response contracts, six-lane protocol producer helpers, and API gateway auth/CORS startup validation.

Phase 4 carry-forward hardening remains open for later targeted work: broad FastAPI response-model coverage, full pytest/Ruff after Python tooling is restored, and deeper live mission lifecycle recovery validation.

First Phase 5 fix completed and pushed as `bc00a7a`: clarified missions now re-queue, emit `MISSION_CLARIFICATION_APPLIED`, restart lifecycle processing, and pass the operator clarification back into PM intake context. Added focused regression coverage in `tests/services/test_mission_clarify_route_unit.py`.

Second Phase 5 fix completed and pushed as `b338976`: the 41-agent registry now exposes audit-facing `pod_assignment` and `language_keys` aliases. Static inventory confirms 41 agents, 14 synthesized-heartbeat agents, 27 shared-worker agents, no missing personas, no orphan personas, no specialist language-persona gaps, and no missing audit alias fields.

Third Phase 5 fix completed and pushed as `983d571`: `tests/services/test_agent_base_unit.py` now permanently verifies synthesized-heartbeat versus shared-worker runtime mapping and confirms every concrete `BaseAgent` subclass is reachable from `AGENT_REGISTRY`, closing the ghost/orphan implementation checklist items.

Fourth Phase 5 fix completed and pushed as `40d4cee`: MissionFlowV2 now resets LLM mission/settings context variables in `finally`, preventing early-return/exception context leakage between missions on a reused worker task. Added source-level regression coverage in `tests/services/test_mission_flow_v2.py`.

Fifth Phase 5 fix completed and pushed as `adfc81a`: `ProtocolBusConsumer` now drops entries whose envelope protocol does not match the Redis lane being consumed, preventing misrouted/corrupted events from reaching the wrong handler. Added regression coverage in `tests/services/test_protocol_bus_consumer.py`.

Phase 6 Mission Control frontend audit is active. First Phase 6 fix was pushed as `db178d2` and converts Settings vault list/save/test/delete calls from raw `fetch` to shared `fetchJson`, preserving standard timeout and structured error handling.

Second Phase 6 fix was pushed as `7681c4d` and removes all explicit production `any` usage from `apps/mission-control/app`: maintenance catches now use `unknown`, mission-detail panels consume canonical shared types, stale panel casts are removed, and the event log uses `MissionPhaseModel`. The zero-`any`/ignore scan, TypeScript, and Vitest all pass (16 files / 74 tests).

Third Phase 6 fix was pushed as `b6d781a` and converts Repo Import and logout from raw `fetch` to shared `fetchJson`. Production client components now have zero raw `fetch` calls; TypeScript and Vitest pass (16 files / 74 tests).

Validation: bundled Python `py_compile` passes for touched backend/test files, the direct agent implementation invariant check reports 41 registry agents / 24 concrete classes / 24 reachable classes, and the direct protocol lane-guard check drops mismatched envelopes before dispatch. Focused pytest is still blocked locally because the bundled Python runtime has no `pytest` module; direct MissionFlowV2 runtime import is also blocked in the bundled runtime by missing `httpx`.

Phase 6 is closed for this offline audit pass at `b6d781a`. Carry forward generated OpenAPI client adoption, route-specific loading/error review, Playwright E2E, and live browser validation.

Phase 7 inventory confirms all ten `shared_runtime` modules have active import consumers and `shared_runtime/__init__.py` exposes no accidental public symbols.

First Phase 7 fix was pushed as `a696152` and hardens `atomic_io.py`: concurrent writers now use unique sibling temp files, serialize backup/replace per destination, retry transient Windows sharing violations, and always clean up temp files. Added a concurrency regression test. Bundled Python `py_compile` and a direct 64-write concurrency probe pass; focused pytest remains blocked because the bundled runtime has no `pytest`.

Second Phase 7 fix was pushed as `68b86d4` and hardens `crypto_signing.py`: verification now enforces P-256, requires the signed digest with constant-time comparison, rejects malformed base64, and writes signature sidecars atomically. Syntax, direct signing-contract, and artifact-sidecar probes pass; focused pytest remains blocked by the missing `pytest` module.

Third Phase 7 fix was pushed as `ded42a5` and hardens `agent_auth.py`: signing rejects empty identity/secret values, verification validates the hex header and replay window, and future clock skew is limited separately from maximum signature age. Syntax and a direct HMAC freshness probe pass; focused pytest remains blocked by the missing `pytest` module.

Fourth Phase 7 fix was pushed as `ab32fa6` and hardens `logging_config.py`: JSON messages, exception text, nested extras, and named credential fields are redacted, plain logs redact their fully rendered output, and trace/span correlation values remain intact. Added focused unit coverage; bundled Python `py_compile` and a direct logging-redaction probe pass. Focused pytest remains blocked by the missing `pytest` module.

Fifth Phase 7 fix was pushed as `563a4d0` and hardens `errors.py`: `FactoryError` now redacts recognized PII and credentials from developer messages during construction, so direct callers and `wrap_unexpected()` cannot serialize raw exception secrets. Added focused regression coverage; bundled Python syntax and direct sanitation probes pass. Focused pytest remains blocked by the missing `pytest` module.

Final Phase 7 fix batch closes A-028 and the remaining shared-runtime checklist: production now requires an existing read-only mounted P-256 PEM and refuses `PLAINv1` generation; the signing key is reread for no-restart rotation; agent service keys can rotate through a fail-closed JSON key file; nested LLM context is recursively redacted with cycle/depth protection; dashboard/lifecycle tests are deterministic and offline. Protocol/schema parity and prompt-guard adversarial behavior are verified.

Phase 7 qualification is green: the focused shared-runtime/protocol suite passes 128 tests, the full repository Python suite passes with 5 intentional skips, full Ruff passes, merged production Compose validation passes, and `git diff --check` passes.

Phase 7 closed and was pushed as `35dfd50`. Phase 8 test coverage and quality-gate audit is active.

Initial Phase 8 inventory: 1,538 tests are collected; the full suite passes with 5 intentional skips and full Ruff passes. Coverage thresholds are configured in CI, but `pytest-randomly` and `pytest-timeout` are not installed despite the audit policy. Several skip paths do not cite tracked issues, and the centralized `tests/services/` layout does not match the audit plan's proposed per-service directories.

First Phase 8 fix was pushed as `627fa8b`: it pins `pytest-randomly==4.1.0` and `pytest-timeout==2.4.0` and enforces a 120-second thread-based per-test timeout. The complete 1,538-test suite passes under randomized ordering with 5 intentional skips; no `time.sleep()` calls exist in tests; Ruff and `git diff --check` pass.

Current checkpoint: Phase 8 is not complete and we should not advance to Phase 9 yet. Order-dependent API gateway/protocol-bus failures were fixed and pushed at `b77da3c`. The latest Phase 8 progress adds storage-domain and Mission Flow v2 regression coverage: `tests/services/test_storage_unit.py` now covers artifact object-storage offload/fallback, testdata/runtime-QC persistence, and agent action event digest/list behavior; `tests/services/test_mission_flow_v2.py` now covers mission-charter helper edge cases, dependency-absorption skip behavior, and Runtime QC skip/complete enforcement paths. Full coverage passes with 1,545 tests, 5 intentional skips, 82.08% total coverage, and the configured CI coverage threshold script passes. The storage coverage gap is closed (`storage_agents.py` 98.04% XML line coverage, `storage_artifacts.py` 99.14% XML line coverage). Outstanding Phase 8 work is now focused on the stricter critical-path `mission_flow_v2/` target, which improved to 83.51% line / 66.27% branch but remains below 90% / 85%, plus mock/fixture quality review and event-bus integration coverage review.

Next active work: continue Phase 8 with scenario-level Mission Flow v2 lifecycle/build/runtime coverage or an explicit tracked deferral. Phase 5 non-protocol stream/schema parity and LangGraph isolation remain backend follow-ups.

---

## Latest Status - Audit Phase 4 Backend Service Audit Started (2026-06-21)

Phase 3 configuration/dependency wiring was committed and pushed as `9e88bad audit-phase-3-config-wiring`.

Current active work is Phase 4 backend service audit. Initial scope is the seven application services: api-gateway, orchestrator, pod-worker, agent-runtime, audit-worker, protocol-bus-mcp, and dashboard. The first checks are route/health/metrics coverage, production stubs/TODOs, response-model gaps, protocol bus stream usage, and mission lifecycle/runtime failure paths.

Completed in the first Phase 4 fix batch: dashboard now exposes Prometheus `/metrics`, includes `prometheus-client`, and uses explicit response models/status codes for its JSON health/readiness/snapshot routes.

Completed in the second Phase 4 fix batch: protocol-bus producer helpers now cover sigma and rho in addition to alpha, beta, delta, and omega. Focused pytest remains blocked locally because the checkout has no `.venv` and bundled Python does not have pytest installed; syntax validation passed with bundled Python.

Documentation hygiene rule added: audit-phase helper scripts are temporary tooling only and must stay outside the repo; permanent fixes belong in normal app, test, and documentation files. Current pushed audit baseline is `ff5419f`.

Completed in the third Phase 4 fix batch: API gateway startup validation now rejects invalid `AUTH_MODE` and rejects wildcard CORS origins in production. Syntax validation passed; focused pytest remains blocked by missing local pytest tooling.

---

## Latest Status - Audit Phase 3 Config/Dependency Fix Batch (2026-06-21)

Completed in the latest audit-plus-fix batch:
- `.env.example` deduped and expanded to cover runtime Python env lookups plus live/demo script controls.
- Gemini embedding default corrected to `gemini-embedding-001`.
- Orchestrator production requirements now have no unpinned dependency lines.
- Removed stale YAML agent-key sample from active `config/`; runtime keys remain env/vault based.

Next active work: Phase 4 backend service audit, unless we first restore the local Python environment to run full pytest/Ruff and clean-start validation.

---

## Latest Status - Audit Phase 2 Naming/Layout Fix Batch (2026-06-21)

Completed in the latest audit-plus-fix batch:
- Verified tracked service names and internal package names follow repo conventions.
- Verified tracked source directories have no mixed-case names.
- Verified no tracked `utils.py` or `helpers.py` catch-all modules exist.
- Verified no tracked Python star imports exist.
- Added explicit empty `__all__` declarations to package initializers that only carry docstrings/comments.

Blocked carry-forward from Phase 1 remains unchanged: full pytest/Ruff and clean start/stop validation still require a usable project Python/runtime environment.

Next active work: continue to Phase 3 configuration/dependency wiring after this Phase 2 slice is validated and committed, or restore the Python test environment first if we want full local validation before moving deeper.

---

## Latest Status - Audit Phase 1 Fix Batch (2026-06-21)

Completed in the latest audit-plus-fix batch:
- RIR producer output now has schema-alignment regression coverage.
- Static examples now have schema-alignment coverage.
- Traceability-ledger docs now identify active Postgres migrations and label ledger/schema.sql legacy.
- AUDIT_PLAN.md now tracks the application-only audit baseline and fixed findings A-005 through A-007.

Validation passed: git diff --check and bundled Python py_compile for the schema test files.

Blocked: pytest/Ruff cannot run until a usable project Python runtime is available; the current shell only finds the broken WindowsApps shim.

Next active work: restore the Python test environment, run focused schema tests/Ruff, then continue Phase 1 checks for shared_runtime, conftest.py, and start/stop clean-environment behavior.
---

## Latest Status - Application-Only Cleanup and Offline Fix Batch (2026-06-21)

The marketing website package has been removed from the application worktree so
current review, build, and TODO tracking stay focused on Mission Control and the
runtime services. The removed site was not part of the application runtime.

Completed in the latest offline batch:
- Removed the tracked `sites/thefactory-site` tree and verified no active
  non-archive references remain.
- Preserved PM feature-contract degraded/fallback metadata in Mission Control
  chat instead of dropping it at the display layer.
- Added a visible warning in the Feature Contract panel when PM planning output
  came from a deterministic/local fallback or otherwise marked itself degraded.

Validation passed:
- `npm --prefix apps\mission-control run lint`
- `npm --prefix apps\mission-control run build`
- `python -m pytest tests\services\test_mission_flow_v2.py tests\services\test_runtime_unit.py -q`
- `git diff --check`

Next active verification when the app can run:
1. Restart the app.
2. Run a fresh PM chat mission from `/chat`.
3. Confirm fallback/degraded PM output shows the warning instead of looking like a
   normal live LLM contract.
4. Confirm a ready contract does not show the normal lifecycle as `CLARIFYING`.
5. Confirm generated code is visible/downloadable from Mission Detail artifacts.
6. Confirm Runtime QC shows either a real report or an explicit skipped reason.

## Latest Status - Rebuilt MissionFlow V2 Fix Batch (2026-06-18)

The app has been stopped, patched, validated, and rebuilt. Do not treat the previous rebuild item as pending.

Completed in the latest batch:
- Normal MissionFlow V2 ready path no longer emits `MISSION_CLARIFYING`; ready missions now proceed `PM_INTAKE -> FETCH`. Clarification remains a real paused state only for high-ambiguity PM intake.
- Runtime QC skips are persisted as `runtime_qc_report` and `MISSION_RUNTIME_QC_SKIPPED`, with the reason visible in Mission Detail.
- Mission Detail generated output now fetches artifact detail text and clearly labels generated code as a database-backed build artifact, not a repo checkout file.
- Full-dedicated Docker images were rebuilt successfully after the final backend change.

Validation passed:
- `python -m pytest tests\services\test_mission_flow_v2.py tests\services\test_runtime_unit.py -q`
- `python -m ruff check ...`
- `npm --prefix apps\mission-control run lint`
- `npm --prefix apps\mission-control run build`
- `git diff --check`

Next active verification:
1. Restart the app.
2. Run a fresh PM chat mission from `/chat`.
3. Confirm a ready contract does not show the normal lifecycle as `CLARIFYING`.
4. Confirm generated code is visible/downloadable from Mission Detail artifacts.
5. Confirm Runtime QC shows either a real report or an explicit skipped reason.
6. After this proof, decide whether to enable TESTDATA/RQCA by default for standard BUILD_NEW missions or keep them visible-but-skipped until the runtime-QC environment work is complete.

## Highest Priority — PM/LLM Workflow (2026-06-18)

The PM agent + mission pipeline was producing canned 1 KB stubs. Routing, vault
keys, the Gemini payload, and the cross-provider cascade were fixed
(`4fdab0a`, `44f557f`, `b6d0848`, `664a5cd`); the **final gate was a gateway
internal-proxy `timeout=4.0` that killed the ~9–19 s Gemini PM call** and returned
`502 "orchestrator unavailable"`. Fixed by making `_proxy_post_internal` accept a
per-call timeout and passing `90.0` for the PM route.

The next failure was in the Mission Control chat/launch handoff, not the LLM:
the chat preview could build a useful PM contract, but mission launch rebuilt the
intake prompt from compact transcript text capped at 1200 characters per message.
A live Iron Meridian test mission (`mission-c228332b-4f4e-4941-8e52-eb7494627045`)
entered `CLARIFYING` because the prompt reached mission intake truncated at
`Defeat c`. Recent fixes:

- `525b930` (`improve-pm-chat-context`) sends compact conversation context,
  decision memory, working contract, attachment labels, and finalize intent into
  the PM feature-contract route; it also fixes operations callers to satisfy the
  gateway's `ge=50` limits.
- `37f0779` (`fix-pm-mission-launch-context`) makes mission launch send full
  user-authored brief/history text with a larger cap and passes
  `conversation_context` plus `user_intent` through mission metadata into
  mission-flow v2 intake.
- `edb7846` (`fix-pm-chat-proceed-launch`) attempts to treat typed proceed-style
  replies, including `procced` and `procede`, as launch confirmation when a
  Feature Contract already exists instead of sending another PM/preview request.
  This was validated by TypeScript/build checks, but the operator reported the
  live retest still did not work, so the browser-side launch action remains the
  next active investigation item.

Current state: code is committed and pushed to `origin/main`; Docker images and
the Next.js production build were rebuilt successfully during validation. After
the `edb7846` retest failed, the operator stopped the app and the local Next.js
production output plus Docker images (`orchestrator`, `api-gateway`,
`mission-control`) were rebuilt again without starting the stack. The old Iron
Meridian mission remains paused in `CLARIFYING` from the pre-fix truncated prompt
and is not expected to auto-prove the fix.

Remaining:

1. ~~**Confirm the happy path.**~~ ✅ **DONE (2026-06-17).** `POST
   /v1/pm/feature-contract` returns `HTTP 200` in 9–19 s with `source: llm`,
   `model_provider: gemini`, `model: gemini-3.5-flash`, `degraded: None` — a real,
   prompt-specific feature contract, verified across three prompts against the
   rebuilt gateway.
1a. **Fix and verify chat launch from an existing Feature Contract.** A live
   Playwright probe on 2026-06-18 proved the rebuilt app can create a mission
   record, but also exposed the real remaining launch bug: the PM preview can
   return `intake_status: needs_clarification` while the UI still exposes a
   launchable Feature Contract, and **Confirm and Start** persisted
   `user_intent: draft`. Mission-flow v2 then correctly paused the fresh mission
   in `CLARIFYING` with `last_ambiguity_score=1.0`. The active fix now gates
   launch when PM asks clarifying questions, persists/restores structured chat
   contracts, compacts mission-launch context, forces `user_intent:
   finalize_plan` on explicit launch, and surfaces FastAPI 422 validation arrays
   instead of "Request failed with status 422." Rebuild/restart Mission Control
   and retest both **Confirm and Start** and typed proceed-style confirmation.
1b. **UI report reconciliation before retest.** The 2026-06-18 Mission Control
   report was reviewed against current code. Confirmed fixes now include
   shell-rendered global 404, compatibility aliases for `/history`,
   `/logic-nodes`, and `/repo-import`, clearer header action text (`View
   Missions`), and more useful chat history rows with preview/timestamp. Several
   report items were stale against current code: canonical nav routes, database
   status colors, notification badge, project empty/loading states, and audit
   skeleton loading were already implemented or no longer matched the code.
1c. **Run a fresh full mission after launch works.** Submit a new PM chat mission
   with a long brief and verify the mission does not pause only because of prompt
   truncation. Required proof before EDCP-02+: one full **end-to-end mission to
   COMPLETE** with non-empty generated code/artifacts, not just the PM intake call.
2. **Surface degraded/fallback mode in the UI (review finding #1).** Backend now
   emits `degraded=True` / `source:"fallback"` on the contract; add a Mission
   Control banner (chat + feature-contract panel) so the operator can see when the
   LLM didn't run instead of getting a stub that looks real. Highest UX leverage.
3. **Provider preflight / "Test key" (finding #2).** Make the Settings "Configure"
   action do a real 1-token call to the selected model and report the actual API
   status, so a bad model/key/payload is caught at config time, not mission time.
4. **App-driven provider + model selection (finding #4).** Provider and model
   currently come from `.env` (`LLM_PROVIDER`) + hardcoded profiles, not the
   Settings vault. Plumb the Settings selection through `metadata.vault` →
   `current_vault_secrets` so the packaged Windows app needs no `.env`. (Keys
   already flow; provider/model do not.)
5. **Wire per-agent vault keys.** The vault stores 41 `AGENT-NN-…-API-KEY` slots,
   but the mission proxy only reads a single `GEMINI-API-KEY` slot. Decide whether
   per-agent keys should drive per-agent calls, or collapse to one provider key.
6. **Review the other agents' workflows** (CEO, pod managers, specialists, audit,
   delivery) — same delegation path; verify each produces real output once #1 is green.
7. **Rotate the exposed Gemini key** (`AQ.Ab8RN6L...`) — pasted in chat + in logs.
8. **Optional hardening:** scope the circuit breaker per-(provider,agent) so one
   agent's failures don't blanket-disable a provider for all 41.
9. ~~**Operations `422` (status-bar mislabel).**~~ ✅ **DONE (2026-06-17).**
   Mission Control had polled
   `/v1/operations/agents?mission_limit=0&assignment_limit=0&event_limit=0`, but the
   gateway enforces `ge=50` on those params → `422` → the healthy runtime was shown
   as "Runtime Shell" / offline. The UI now sends the minimum accepted limits.
10. **UI fallback preview `422`.** The chat page's `createBuilderPreview` fallback
    returns `422` even though a direct `POST /v1/builder/preview` returns `200` —
    body/validation mismatch in the `/api/gateway` proxy path. Low urgency now that
    the PM primary path works, but a latent contract bug.

---

## Highest Priority

> **All 4 audit HIGH items from 2026-06-13 are resolved (see CHANGELOG).**

### Immediate operational steps (2026-06-16)

0a. **Rebuild and restart to lock in local fixes.** Three local commits are not
    yet reflected in the running stack: `f726de4` (PM `assumptions` persistence),
    `04e4fef` (standalone-UI gateway proxy 503 / portless `MISSION_API_BASE_URL`
    fix + proxy default → `127.0.0.1`), and `d743d4e` (redact Redis password from
    api-gateway `/health`). After stopping the app, rebuild the `orchestrator`,
    `api-gateway`, and `mission-control` images and relaunch the standalone UI
    via the fixed `start_app.bat` so all three are baked in.

0b. **Push the three local commits to `origin/main`** once the rebuild verifies
    clean. They are currently local-only.

### Recently resolved (2026-06-16)

- Standalone UI "Runtime offline / databases not connected" — root cause was a
  portless `MISSION_API_BASE_URL` produced by cmd parse-time expansion in
  `start_app.bat`; the backend and all data systems (Postgres, Redis, Qdrant,
  Milvus, Neo4j, object storage, Jaeger) were verified healthy via the live
  operations summary. Fixed in `04e4fef`.
- PM feature-contract `assumptions` field now persisted through the normalizer
  and deterministic fallback (`f726de4`).
- api-gateway `/health` no longer leaks the Redis password (`d743d4e`).

---

## Previously Highest Priority (from 2026-06-13 batch 1)

5. **Confirm post-hardening CI is fully green**
   - Check the GitHub Actions run triggered by commit `867d3ec`.
   - Expected production-critical gates on `main`: lint/test, Docker Build
     Validation, SBOM, Electron E2E Smoke, Performance Smoke, Release Trust,
     CodeQL, and security checks.

6. **Run the Gemini live mission proof**
   - Start the local stack with a real `GEMINI_API_KEY` and `KNOWLEDGE_EMBEDDING_PROVIDER=gemini`.
   - Confirm Mission Control starts unlocked and `KNOWLEDGE-EMBEDDING-API-KEY`
     is saved/tested before submitting the mission. The internal service key is
     stack configuration, not a user-facing vault setup step.
   - Submit a BUILD_NEW mission.
   - Capture evidence that the mission reaches COMPLETE with non-empty
     LLM-generated output from `gemini-3.5-flash` and that semantic search
     in the knowledge lake is operational (check Qdrant for indexed vectors).
   - Store evidence under `docs/evidence/` and update
     `docs/IMPLEMENTATION_STATUS.md`.

7. **Execute EDCP load-bearing handoff work after live mission proof**
   - Use `docs/EDCP_Phase_Plan.md` as the phase plan for converting the current
     direct-call mission pipeline into an event-driven control plane.
   - EDCP-01 foundation is complete: bus consumer-group mode, missing
     Omega/Beta/Delta sender helpers, and the disabled-by-default control-plane
     flag are in place.
   - Do not start EDCP-02 until the Gemini live mission proof above produces a
     COMPLETE mission with non-empty generated code.

8. **Confirm production host controls**
   - Enforce branch protection and required status checks in GitHub settings.
   - Confirm secret scanning and push protection are enabled.
   - Confirm release attestation verification is required for release promotion.

---

## Release Readiness Follow-Ups

9. **Produce target-environment DR evidence**
   - Run backup/restore and disaster-recovery checks in the target deployment
     environment.
   - Do not rely on local-only DR evidence for partner-facing claims.

10. **Legal and policy approval**
   - Review `docs/PRIVACY_POLICY.md` and `docs/TERMS_OF_SERVICE.md`.
   - Get approval before external publication or partner distribution.

11. **Long-duration reliability requalification**
    - Re-run the reliability qualification against the current Gemini-first
      baseline and hardened CI policy.
    - Archive the old baseline only after replacement evidence is captured.

---

## Product Validation Backlog

12. **PORT differentiator demo**
    - Run a PORT mission on a real open-source Windows game or utility.
    - Capture output targeting Linux/macOS and evidence the two-phase PORT path.
    - Validate that `extraction_degraded=True` is surfaced in RQCA when AIM
      extraction fails (new flag added 2026-06-13).

13. **Agent scaling live validation**
    - Run a multi-file repo mission with `AGENT_SCALING_ENABLED=true`.
    - Validate partition splitting, execution, and result merge.

14. **Partner-facing proof package**
    - Assemble the current docs index, CI run, SBOM, Release Trust output, live
      Gemini mission evidence, and DR evidence into a concise review package.

---

## Known Non-Issues (do not re-investigate)

- `test_agent_base_unit.py` import error — requires `services/orchestrator` on
  `sys.path`. Not broken; run from the service directory.
- OTel/Jaeger `Failed to export span batch` during tests — Jaeger not running locally.
  Harmless; exporter drops spans on shutdown.
- `docs/archive/2026-06-13/` contains superseded planning docs. Historical only.
