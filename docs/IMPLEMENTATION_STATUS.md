# Implementation Status

Document version: 2026.06.21-a
Last updated: 2026-06-26
Status: Canonical
Audience: Operators, developers, maintainers, and auditors

This document is the canonical current-state snapshot for theFactory. Use it as the
source of truth for shipped defaults, active runtime behavior, current qualification
status, and known follow-up work. Historical phase plans, ADRs, and completion
checklists remain useful records but some no longer describe the current default
runtime exactly. When they conflict with this document, this document wins.

---

### Audit Phase 11 Mission Control E2E completed (2026-06-26)

Latest status: Phase 11 is complete for this pass after closing the Phase 10 reliability follow-up. Live review confirms Mission Control exposes `lint`, `test`, `build`, and `test:e2e` scripts; CI installs Chromium and runs Mission Control E2E; and `apps/mission-control/e2e/` contains 23 Playwright tests across mission lifecycle, operations/persona views, settings/vault, builder/repo intake, error states, data-plane views, cost/runtime-QC panels, and accessibility checks. The first Phase 11 fix removes a Settings page hydration warning by rendering vault table `<col>` elements from a data array instead of comments/whitespace inside `<colgroup>`. The final Phase 11 fix strengthens production audit check `UI-011` so it validates E2E script/CI parity, Playwright web config, electron-spec exclusion, trace/list reporter settings, committed web spec coverage, and ignored Playwright report/test-result artifacts.

Validation: Mission Control TypeScript lint passes, Vitest passes (16 files / 74 tests), Playwright E2E passes (23 tests) against the running backend stack, and the production Next.js build passes. Focused production-audit tests and focused Ruff pass for the `UI-011` hardening. Remaining console noise is limited to the expected Next.js development-mode `eval()` warning under CSP; production build is unaffected.

---

### Audit Phase 10 reliability qualification started (2026-06-26)

Latest status: Phase 10 is active after completing tracked Phase 9 security-audit items. The first reliability slice improves evidence quality in `scripts/reliability_qualification.py`: JSON reports now include the target `base_url`, configured `readiness_endpoints`, and `readiness_failure_counts_by_endpoint`. The second reliability slice adds capped `mission_error_samples` and `readiness_failure_samples` to the report and prints the target base URL, readiness endpoints, and endpoint-level readiness failure counts in console output. The third slice updates the PowerShell wrapper and current operator docs so readiness/recovery controls and evidence fields match the live script. The fourth slice adds `scripts/verify_reliability_evidence.py` for offline validation of refreshed reliability evidence shape and pass/fail status. The fifth slice refreshed baseline reliability evidence at `docs/evidence/reliability_qualification_baseline_2026-06-26.json` against a running local Docker stack with orchestrator restart injection. The sixth slice hardens API gateway mission creation with bounded retries for transient `orchestrator unavailable` upstream persistence failures during orchestrator restart windows.

Validation: focused reliability qualification tests pass (8 tests), reliability evidence verifier tests pass (3 tests), API gateway helper tests pass (23 tests), focused Ruff passes, PowerShell parser validation passes for `scripts/reliability_qualification.ps1`, live Docker readiness probes returned 200 for gateway and orchestrator, the refreshed reliability qualification passed with 600 mission requests at 99.00% success and zero readiness failures, and `scripts/verify_reliability_evidence.py` verified the refreshed JSON.

---

### Audit Phase 9 security audit completed (2026-06-26)

Latest status: Phase 9 completed for the tracked security-audit checklist after fast-forwarding to `origin/main` at `266f2a3`. Phase 8 still carries the open `mission_flow_v2/` strict coverage finding and should remain a tracked carry-forward unless fixed or explicitly deferred.

Initial Phase 9 review confirms repo-level secret scanning controls are present: `.gitleaks.toml`, `.pre-commit-config.yaml`, and `.github/workflows/security.yml` cover custom theFactory secret patterns, staged-file gitleaks protection, and full-history CI secret scans. Existing controls already verify production `AUTH_MODE` fail-fast and protocol-bus `MCP_API_KEY` production fail-closed behavior.

First Phase 9 fix adds API gateway storage-boundary sensitive-input scanning for mission creation. Prompt, source code, style directives, attachment descriptors, and submitted metadata are scanned through `shared_runtime.pii_guard` before orchestrator persistence. Metadata stores only field/type/count summaries, never matched values; sensitive missions are tagged and raised to `TIER_2_RESTRICTED` unless already classified higher.

Second Phase 9 fix hardens worker service-boundary auth startup. Pod-worker and audit-worker now call `shared_runtime.agent_keys.enforce_production_service_auth_config()` during lifespan startup. Production mode fails closed unless agent service-key mode is strict, fallback `SERVICE_API_KEY` is non-placeholder and strong, and configured worker identities resolve to strong dedicated keys.

Third Phase 9 fix hardens host-published network boundaries. Base Compose now defaults all host-facing ports to `127.0.0.1` through documented `*_HOST_BIND` controls for data-plane, observability, API gateway, orchestrator, protocol-bus MCP, dashboard, and Mission Control ports. Operators can still intentionally publish a port beyond the workstation by overriding the matching bind variable.

Fourth Phase 9 fix closes an unauthenticated direct-read gap on the orchestrator. `GET /missions/{mission_id}/runtime-qc` now requires the read auth dependency, matching other mission read routes and protecting runtime execution/QC previews.

Fifth Phase 9 fix adds prompt/input validation at the API gateway storage boundary. Mission creation records value-redacted `prompt_input_scan` metadata for prompt-injection indicators in submitted prompt text, style directives, attachment descriptors, and bounded metadata string fields. `PROMPT_GUARD_MODE=block` rejects high-or-higher risk input before idempotency reservation or orchestrator persistence.

Sixth Phase 9 fix hardens production object-storage TLS. Production Compose now sets `OBJECT_STORAGE_REQUIRE_TLS=true` for the orchestrator, and settings documentation requires an HTTPS object-storage endpoint in production. The object-store client rejects non-HTTPS endpoints when TLS is required.

Seventh Phase 9 fix aligns protocol-bus replay/dedup TTL configuration. Production Compose now uses canonical `MCP_DEDUP_TTL_SECONDS=600`, and the MCP service still accepts legacy `MESSAGE_DEDUP_TTL_SECONDS` as a compatibility alias. Replay/dedup verification covers duplicate rejection, idempotent dedup returns, Redis-backed cross-client detection, fail-closed Redis errors, and the production Compose variable.

Phase 9 tracked security-audit items are complete for this pass. Phase 8 still carries the `mission_flow_v2/` strict coverage carry-forward unless explicitly deferred.

Validation: focused API gateway helper tests pass (37 tests with prompt-guard coverage); focused worker/auth tests pass (68 tests); focused compose/object-store tests pass (18 tests, with local pytest addopts overridden because this Python environment lacks `pytest-timeout`); focused route auth tests pass (28 tests, same addopts override); focused protocol-bus replay/dedup tests pass (59 tests, same addopts override, with post-teardown local Jaeger exporter logging but exit 0); focused Ruff passes; `git diff --check` passes; merged production Compose service rendering passes.

---
### Audit Phase 8 test coverage audit started (2026-06-24)

Latest status: Phase 7 closed at `35dfd50`; Phase 8 is active.

Phase 6 qualification: TypeScript passes, production client components have zero raw `fetch` calls, the production `app/` scan has zero explicit `any`/TypeScript-ignore matches, and Vitest passes with 16 files / 74 tests. Generated OpenAPI client adoption, route-specific loading/error review, Playwright E2E, and live browser validation remain carry-forward work.

Phase 7 inventory confirms all ten shared-runtime modules have active import consumers and the package root exposes no accidental symbols.

First Phase 7 fix hardens `atomic_io.py` and was pushed as `a696152` for concurrent writers with unique sibling temp files, per-destination backup/replace locking, bounded Windows sharing-violation retry, guaranteed cleanup, and regression coverage. Bundled Python `py_compile` and a direct 64-write concurrency probe pass; focused pytest remains blocked because the bundled runtime has no `pytest`.

Second Phase 7 fix hardens `crypto_signing.py` and was pushed as `68b86d4`: verification enforces P-256, requires the signed digest with constant-time comparison, rejects malformed base64, and writes signature sidecars atomically. Syntax, direct signing-contract, and artifact-sidecar probes pass; focused pytest remains blocked by the missing `pytest` module.

Third Phase 7 fix hardens `agent_auth.py` and was pushed as `ded42a5`: signing rejects empty identity/secret values, verification validates the hex header and replay window, and future clock skew is limited separately from maximum signature age. Syntax and a direct HMAC freshness probe pass; focused pytest remains blocked by the missing `pytest` module.

Fourth Phase 7 fix hardens `logging_config.py` and was pushed as `ab32fa6`: JSON logging redacts messages, exception text, nested extras, and named credential fields; plain logging redacts fully rendered output; trace/span correlation fields are preserved. Added focused unit coverage. Bundled Python syntax and a direct redaction probe pass; focused pytest remains blocked by the missing `pytest` module.

Fifth Phase 7 fix hardens `errors.py` and was pushed as `563a4d0`: `FactoryError` sanitizes developer messages during construction, preventing direct callers and `wrap_unexpected()` from serializing recognized PII or credentials from exception text. Focused regression coverage, bundled Python syntax, and direct sanitation probes pass; focused pytest remains blocked by the missing `pytest` module.

Final Phase 7 work closes the remaining shared-runtime items. Production signing requires `ARTIFACT_SIGNING_KEY_SOURCE=mounted`, an existing read-only PKCS8 P-256 PEM, and shared mounts for orchestrator/audit-worker; production cannot create plaintext fallback keys. Signing and agent-service key files are reread for no-restart rotation. LLM context redaction now recursively handles nested structures, cycles, and depth limits. Prompt-guard adversarial checks and protocol/schema parity are verified.

Phase 7 qualification: 128 focused shared-runtime/protocol tests pass; the complete repository Python suite passes with 5 intentional skips; full Ruff, merged production Compose validation, and `git diff --check` pass.

Phase 8 inventory: 1,538 tests are collected. CI defines global and per-module coverage checks, but deterministic-order and timeout plugins are absent from `requirements-dev.txt`; skip reasons are not consistently linked to issues; and the audit's proposed per-service directory layout does not match the established centralized test-file convention.

First Phase 8 fix was pushed as `627fa8b` and adds pinned `pytest-randomly` and `pytest-timeout` dependencies plus a 120-second thread-based timeout. The full 1,538-test suite passes under randomized ordering with 5 intentional skips; Ruff, `git diff --check`, and the no-`time.sleep()` scan pass.

Phase 8 remains open. Order-dependent API gateway/protocol-bus failures were fixed at `b77da3c`. Current Phase 8 progress adds stable coverage for storage-domain persistence and Mission Flow v2 helper/runtime gates. Full coverage passes with 1,545 tests, 5 intentional skips, 82.08% total coverage, and `scripts/check_coverage_thresholds.py` passes. The storage coverage gap is closed (`storage_agents.py` 98.04% XML line coverage, `storage_artifacts.py` 99.14% XML line coverage). Do not move to Phase 9 until the stricter critical-path `mission_flow_v2/` coverage gap is raised or explicitly deferred (`83.51%` line / `66.27%` branch vs `90%` / `85%`), mock/fixture quality review is complete, and event-bus integration coverage review is complete.

---
### Audit Phase 5 agent/orchestrator wiring started (2026-06-22)

Latest status: Phase 4 is closed for this audit pass at `3cced29`; Phase 5 is active.

Phase 5 focus is registry/orchestrator truth: 41-agent inventory, ghost/orphan implementation checks, AgentPersona coverage, MissionFlowV2 wiring, and event-bus publisher/subscriber coverage.

First Phase 5 fix: clarified missions now resume correctly by re-queuing with `MISSION_CLARIFICATION_APPLIED`, restarting lifecycle processing, and passing operator clarification into PM intake context. Added `tests/services/test_mission_clarify_route_unit.py` and pushed as `bc00a7a`.

Second Phase 5 fix: `AgentDefinition` now exposes audit-facing `pod_assignment` and `language_keys` aliases with coverage in `tests/services/test_agent_personas_registry.py`. Static inventory confirms 41 agents, 14 synthesized-heartbeat agents, 27 shared-worker agents, no missing personas, no orphan personas, no specialist language-persona gaps, and no missing audit alias fields. Pushed as `b338976`.

Third Phase 5 fix: `tests/services/test_agent_base_unit.py` now permanently verifies synthesized-heartbeat/shared-worker runtime mapping and concrete `BaseAgent` subclass reachability through `AGENT_REGISTRY`. Pushed as `983d571`.

Fourth Phase 5 fix: MissionFlowV2 now resets LLM mission/settings context variables in `finally`, preventing early-return/exception context leakage between missions on a reused worker task. Added `tests/services/test_mission_flow_v2.py` coverage. Pushed as `40d4cee`.

Fifth Phase 5 fix: `ProtocolBusConsumer` now enforces envelope protocol equals the consumed lane protocol before dispatching to a handler, closing a misrouted-event path in the protocol bus. Added `tests/services/test_protocol_bus_consumer.py` coverage. Pushed as `adfc81a`.

Phase 6 Mission Control frontend audit is active. First Phase 6 fix converted Settings vault list/save/test/delete calls from raw `fetch` to shared `fetchJson`, preserving standard timeout and structured error handling; pushed as `db178d2`.

Second Phase 6 fix removes all explicit production `any` usage from `apps/mission-control/app`: maintenance catches use `unknown`, mission-detail panels consume canonical shared types, stale casts are removed, and the event log uses `MissionPhaseModel`. The zero-`any`/ignore scan, TypeScript, and Vitest all pass (16 files / 74 tests); pushed as `7681c4d`.

Third Phase 6 fix converts Repo Import and logout from raw `fetch` to shared `fetchJson`; pushed as `b6d781a`. Production client components now have zero raw `fetch` calls; TypeScript and Vitest pass (16 files / 74 tests). Bundled Python `py_compile` passes for touched backend tests; local focused pytest remains blocked because pytest is not installed in the bundled runtime, and direct MissionFlowV2 runtime import is blocked by missing `httpx`.

---

### Audit Phase 4 backend service audit started (2026-06-21)

Latest status: Phase 4 is active after Phase 3 was pushed as `9e88bad audit-phase-3-config-wiring`.

Current audit target: backend service runtime quality across api-gateway, orchestrator, pod-worker, agent-runtime, audit-worker, protocol-bus-mcp, and dashboard. Initial validation is static because the app is not required to be running for this pass; full pytest/Ruff remains dependent on restoring the local Python tooling environment.

First Phase 4 fix: dashboard now has Prometheus `/metrics`, a pinned `prometheus-client` dependency, and explicit Pydantic response models/status codes for JSON service endpoints.

Second Phase 4 fix: protocol-bus producer helpers now cover all six protocol lanes, including sigma knowledge messages and rho traffic-control messages. Syntax validation passed; focused pytest is blocked until local pytest tooling is restored.

---

### Audit Phase 3 configuration/dependency fix batch (2026-06-21)

Latest local status: Phase 3 static config/dependency wiring checks are complete for tracked files.

- `.env.example` has no duplicate keys and covers tracked Python runtime env lookups.
- Runtime optional knobs, live validation knobs, and demo controls are documented with safe defaults.
- `KNOWLEDGE_EMBEDDING_MODEL` now defaults to `gemini-embedding-001` in the env template.
- Production requirements are pinned; the unpinned `psycopg-pool` line was fixed.
- The stale YAML key sample was removed from active `config/` because the app uses env/vault key configuration.

Qualification status: Phase 3 scan and `git diff --check` pass. Full pytest/Ruff remains blocked by the local Python shim/dependency environment.

---

### Audit Phase 2 naming/layout fix batch (2026-06-21)

Latest local status: Phase 2 static naming/layout checks are complete for tracked source files.

- Service directories and Python package directories match the naming convention.
- Tracked source directories do not contain mixed-case directory names.
- No tracked catch-all `utils.py` or `helpers.py` modules were found.
- No Python star imports were found.
- Package initializers with docstrings/comments now declare explicit empty `__all__` lists when they do not re-export public symbols.

Qualification status: Phase 2 scan, `py_compile` on touched initializers, and `git diff --check` pass. Full pytest/Ruff remains blocked by the local Python shim/dependency environment.

---

### Audit Phase 1 fixes and documentation sync (2026-06-21)

Latest local status: Phase 1 of AUDIT_PLAN.md is being executed as audit-plus-fix, not report-only.

- Generated RIR modules are now covered by canonical RIR JSON-schema regression tests.
- LogicNode and RIR example fixtures are now covered by schema regression tests.
- Traceability-ledger documentation now points at the active Postgres audit/LLM/immutable ledger migrations, and the root SQLite schema is marked legacy.

Qualification status: git diff --check and py_compile passed. Full pytest/Ruff validation is blocked by the local Python shim/dependency environment.
---

### Application-only cleanup and fallback visibility (2026-06-21)

Latest local status: the marketing website package has been removed from the
application worktree, and Mission Control now preserves degraded/fallback PM
contract metadata through the chat display layer.

- `sites/thefactory-site` has been removed because it is not part of the
  application runtime and was distracting from the current Mission Control and
  agent-pipeline audit.
- The Feature Contract panel now warns when PM planning output is fallback or
  degraded instead of presenting it as normal live LLM output.
- The README and active status docs continue to describe the app as in
  development, not production-ready.

Qualification status: Mission Control lint/build, focused backend
mission/runtime tests, and `git diff --check` pass for the combined cleanup.

### MissionFlow V2 clarification and artifact visibility rebuild (2026-06-18)

Latest local rebuild status: patched, validated, and full-dedicated Docker images rebuilt successfully.

- MissionFlow V2 ready-path transitions were corrected so normal missions no longer pass through `MISSION_CLARIFYING`. The clarification state remains available for true high-ambiguity PM intake.
- Runtime QC disabled/skipped paths now persist a visible `runtime_qc_report` and `MISSION_RUNTIME_QC_SKIPPED` event instead of returning an invisible skip tuple.
- Mission Detail now fetches generated-code artifact details and displays database-backed artifact metadata, including filename, storage backend, status, digest, and byte size.
- Runtime QC UI now shows skipped status and reason instead of hiding missing QC evidence.

Qualification status: focused backend tests, Ruff, Mission Control TypeScript lint, Mission Control production build, and `git diff --check` passed. The next product proof is still a fresh mission after restart.

## Project Status

**Version: v1.2.0** (current baseline with Gemini-first model routing and
PM/mission launch-context hardening, 2026-06-18).

As of 2026-06-13, Phases 1–27 are complete. The platform has a full Smelt-Cycle
pipeline (INTAKE → FETCH → SMELT → GATING → FUSION → SQUEEZE → DELIVERY), a 41-agent
registry, versioned prompt assets with LLM safety governance, a 22/22-passing production
review audit, 97 offline eval and unit tests, and a 23-spec Playwright E2E suite. Git
history is clean of private keys. Disaster recovery RTO is 37.13s.

**Current active phase:** Gemini-first operator validation, followed by EDCP-02
PM-to-CEO handoff work. EDCP-01 foundation is complete. PM feature-contract calls
are proven at the API level against Gemini, and the Mission Control chat/launch
handoff now preserves long operator briefs plus PM conversation context. The
browser-side launch action from an existing Feature Contract is still not proven:
`edb7846` attempted to route typed proceed-style confirmations into mission
creation, but the operator reported the live retest still failed. The next
required step is restarting the rebuilt app, capturing the failing launch
request/response, and then confirming a fresh BUILD_NEW mission reaches COMPLETE
with non-empty `generated_code`. Do not start load-bearing EDCP control-plane
inversion until that proof passes.

**Release blockers:** None for the Phases 1–27 implementation baseline. The only
remaining blocker for a public launch claim after the model-routing update is a
fresh live Gemini provider-key demo.

---

## What Is Implemented

### PM/LLM workflow and mission launch hardening (2026-06-17 to 2026-06-18)

Commits `4fdab0a`, `44f557f`, `b6d0848`, `664a5cd`, `1921ddc`, `525b930`,
`37f0779`, `edb7846`:

- Agent routing now honors `LLM_PROVIDER=gemini` even for OpenAI-pinned persona
  profiles; provider calls no longer silently cascade across providers when a
  provider is explicitly pinned.
- Mission Control vault keys are read from the active LLM delegation context, and
  Gemini requests use `generationConfig.thinkingConfig.thinkingLevel`.
- Deterministic PM fallback contracts are marked degraded so UI work can surface
  fallback mode explicitly.
- API Gateway waits up to 90 seconds for `/internal/pm/feature-contract`, matching
  the real Gemini latency observed locally instead of returning a false
  "orchestrator unavailable" after 4 seconds.
- PM chat sends compact conversation context, decision memory, working contract,
  attachment labels, and finalize intent into PM contract generation.
- Mission launch now sends full user-authored brief/history text with a larger cap
  and carries `conversation_context` plus `user_intent` into mission-flow v2 intake.
- Mission Control operations polling now satisfies the gateway's minimum limit
  constraints, removing the `422` status-bar/runtime-label false negative.
- `edb7846` attempts to map typed proceed-style confirmations, including
  `procced`, onto the existing Feature Contract launch path instead of sending a
  new PM/preview request. This is build-validated but not live-proven.
- Mission Control UI report follow-up now preserves the shell on global 404,
  adds compatibility aliases for stale `/history`, `/logic-nodes`, and
  `/repo-import` links, clarifies the header action as `View Missions`, and adds
  persisted preview/timestamp metadata to PM chat history rows.

Current limitation: one pre-fix Iron Meridian mission is paused in `CLARIFYING`
because the old launch path truncated the prompt at `Defeat c`. That mission is
diagnostic evidence for the old bug, not a valid proof of the current fix. A
2026-06-18 live Playwright probe then proved mission creation itself works, but
also proved the PM chat still allowed launch after `intake_status:
needs_clarification` and persisted `user_intent: draft`; the fresh probe mission
entered `CLARIFYING` with `last_ambiguity_score=1.0`. The active fix gates
launch on PM clarifying questions, forces `finalize_plan` on explicit launch,
compacts launch metadata, restores structured contracts from chat history, and
surfaces FastAPI 422 validation details.

### Knowledge Lake hardening + multiagent audit fixes (2026-06-13, batch 2)

Commits `d52d978`, `bdf73b2`, `c07da61`, `44cb9c8`, `41d76c6`, `364a086`:

**Embedding pipeline fixes:**
- Added `KNOWLEDGE_EMBEDDING_API_KEY` env var — dedicated key for embedding calls,
  overriding `GEMINI_API_KEY` / `OPENAI_API_KEY` for separate quota management. Wired
  through `settings.py`, `knowledge_embeddings.py`, and `docker-compose.yaml`.
- Fixed `_vector_search`: was passing a JSON-serialised dict as query text and using
  `RETRIEVAL_DOCUMENT` task type for search queries. Now passes
  `content={"combined_text": concept_key}` and `task_type="RETRIEVAL_QUERY"`.
- `_semantic_search_enabled()` now requires all three: Qdrant enabled + real provider +
  non-empty API key. Previously enabled even when no key was configured.
- `QDRANT_VECTOR_SIZE` default raised 64 → 256 (64 too low for cosine separation).
- New `_embedding_key_available()` helper in `knowledge_lake.py`.

**LangGraph guard:**
- `LANGGRAPH_CHECKPOINTER=postgres` with empty `LANGGRAPH_CHECKPOINTER_POSTGRES_URL`
  now logs CRITICAL and returns False instead of silently falling back to the PgBouncer
  URL (transaction-pool mode drops session-level advisory locks, corrupting checkpoint
  state).

**Documentation rewrites (previously drifted from code):**
- `KNOWLEDGE_LAKE_AND_EMBEDDINGS.md`: complete rewrite — module-level function API,
  Postgres-first design, three embedding providers, `task_type` usage, semantic search
  gate conditions. Removed fictional `KnowledgeLake` class description.
- `STORAGE_LAYER.md`: complete rewrite — accurate module names, correct table names
  (`mission_state_events`, `mission_pod_assignments`, `mission_knowledge`,
  `agent_runtime_heartbeats`, `agent_action_events`), accurate function tables per module.
- `README.md` Data Systems table: Milvus/Neo4j/MinIO corrected from `✅ Active` to
  `⚙️ Integrated / off by default` *(later reversed in batch 3 — see below)*.

**Settings UI:**
- New "3. Knowledge Embeddings" panel in Mission Control Settings explaining
  `KNOWLEDGE_EMBEDDING_PROVIDER`, `KNOWLEDGE_EMBEDDING_API_KEY`, compose defaults,
  and how to enable semantic search.

**New unit tests (43 total — zero coverage existed before):**
- `test_knowledge_lake_unit.py` (37 tests): `_embedding_key_available`,
  `_semantic_search_enabled`, `is_stocked`, `index_documentation`, `_mirror_to_qdrant`,
  `query_documentation` routing, `_vector_search` RETRIEVAL_QUERY regression,
  `_keyword_search`, `get_language_context`.
- `test_knowledge_embeddings_unit.py` (+5): Gemini happy path, task_type forwarding,
  `KNOWLEDGE_EMBEDDING_API_KEY` overriding both global keys.
- `test_langgraph_lifecycle_unit.py` (+1): empty URL → returns False (PgBouncer guard).

**Multiagent system audit — 4 critical silent-exception fixes:**
- `is_agent.py` — `_knowledge_is_indexed` and `_knowledge_is_current` now log DEBUG
  on storage errors (were silently returning False).
- `dependency_absorption.py` — DEPABS LLM failure now logs WARNING; added missing
  `logging` module + `LOGGER`; returns `{"error": str(exc)}` so callers detect it.
- `knowledge_embeddings.py` — cost-ledger outer except now logs DEBUG.
- `port_coordinator.py` — AIM extraction and specialist plan failures now log WARNING;
  `coordinate_port_extraction()` returns `extraction_degraded: bool`.

**Multiagent audit — 4 HIGH items resolved:**
- LangGraph stable thread_id documented + DEBUG log added for traceability.
- Heartbeat interval mismatch guard added to `heartbeat_service.py` (warns when
  stale threshold < 3× interval).
- `/health` endpoint extended: `agents_total`, `agents_with_heartbeat`,
  `agents_missing_heartbeat`, `agents_missing_ids` fields + WARNING log for gaps.
- Sigma lane handler confirmed wired at `main.py:505`; no code change needed.

### All extended data stores enabled by default (2026-06-13, batch 3)

Commit `6cd65f5`:

- `settings.py`: `milvus_enabled`, `neo4j_enabled`, and `object_storage_enabled`
  dataclass defaults and `from_env()` fallbacks changed `False → True`.
- `docker-compose.yaml`: `MILVUS_ENABLED` default changed `false → true` (Neo4j and
  MinIO were already `true` in compose but `False` in the Python defaults — now consistent).
- `docker-compose.dev.yaml`: removed hard `NEO4J_ENABLED: "false"` and
  `OBJECT_STORAGE_ENABLED: "false"` overrides so dev now inherits the base defaults.
- `README.md`, `SETTINGS_REFERENCE.md`, `DEVELOPER_ONBOARDING_GUIDE.md`,
  `ARCHITECTURE.md`, `COMPOSE_ENVIRONMENT_PROFILES.md` all updated.

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

### EDCP plan and PM intake correction (2026-06-14)

- Added `docs/EDCP_Phase_Plan.md`, the event-driven control-plane roadmap for
  turning the current direct-call lifecycle into bus-driven PM to CEO to
  support/pod handoffs.
- PM feature-contract normalization now preserves `intake_status`; when the PM
  marks a request `needs_clarification`, ambiguity scoring reliably pauses the
  mission for clarifying questions instead of creating a generic plan.
- Mission charters now include a PM planning package: statement of work, product
  requirements, phased build plan, risk register, and test strategy.
- Mission Control chat now displays PM clarifying questions and withholds the
  launchable contract until scope is ready.
- Local Mission Control remains unlocked by default. The internal service key is
  stack configuration, not a user-facing Operator Runtime Key vault row.

### EDCP-01 bus durability foundation (2026-06-14)

- `ProtocolBusConsumer` now supports opt-in Redis consumer-group mode with
  `XGROUP CREATE`, `XREADGROUP`, and `XACK`. The existing `XREAD` path remains
  the default while `EVENT_DRIVEN_CONTROL_PLANE_ENABLED=false`.
- Added `EVENT_DRIVEN_CONTROL_PLANE_ENABLED=false` to orchestrator settings,
  `.env.example`, and compose.
- Added Protocol Bus producer helpers for future handoffs/results:
  `send_omega_message`, `send_beta_result`, and `send_delta_audit`.
- Added regression tests for grouped consumption/ack behavior, failed-handler
  non-ack behavior, payload schema validation, and settings flag parsing.
- EDCP-02 through EDCP-05 remain pending.

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
| `MILVUS_ENABLED` | `true` | Extended vector store; on by default |
| `NEO4J_ENABLED` | `true` | Knowledge graph adapter; on by default |
| `OBJECT_STORAGE_ENABLED` | `true` | MinIO/S3 artifact retention; on by default |
| `KNOWLEDGE_EMBEDDING_PROVIDER` | `deterministic` (compose) / `gemini` (settings.py) | Compose default is SHA-256 hash vectors (no API key needed). Set to `gemini` or `openai` + supply key for real semantic search |
| `KNOWLEDGE_EMBEDDING_API_KEY` | *(empty)* | Dedicated embedding key; overrides `GEMINI_API_KEY` / `OPENAI_API_KEY` for separate quota |
| `QDRANT_VECTOR_SIZE` | `256` | Raised from 64 (2026-06-13) — minimum for meaningful cosine separation |
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
Mission Control labels these orchestrator-managed control/support roles as `MANAGED`.
Specialist, pod-manager, and pod-audit agents run through shared pod-worker
containers and are labeled `WORKER`. A one-container-per-agent topology is not
required for the default local product path; use the full dedicated-agent compose
profile only when strict runtime isolation is a deployment requirement.

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
- **Neo4j**: active by default; `NEO4J_ENABLED=true`.
- **Milvus**: active by default; `MILVUS_ENABLED=true`.
- **Object storage**: active by default; `OBJECT_STORAGE_ENABLED=true`.

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
- **Local unlocked UX**: PM Agent chat treats auth/key failures as local runtime
  configuration issues, not user credential setup. There is no user-facing
  Operator Runtime Key vault row; internal service authentication comes from
  stack configuration.
- **Embedding setup visibility**: Settings exposes
  `KNOWLEDGE-EMBEDDING-API-KEY` in the vault table and Knowledge Embeddings
  panel. The orchestrator still consumes `KNOWLEDGE_EMBEDDING_API_KEY` from the
  container environment, so local stack startup must mirror the vault value into
  the runtime environment for semantic search.
- **Live runtime validation (2026-06-13)**: full dedicated stack returned 41/41
  agents with live heartbeats through `/v1/operations/agents`; all agents were
  idle and all data-plane/runtime readiness flags were healthy. The local Google
  test key saved to `KNOWLEDGE-EMBEDDING-API-KEY` also succeeded against the
  Gemini `gemini-embedding-001` endpoint and returned a 3072-dimension vector.
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

## Validation Snapshot (as of 2026-06-18)

| Check | Result |
|---|---|
| `npm --prefix apps\mission-control run build` | ✅ Clean after PM launch clarification/intent fix |
| `npm --prefix apps\mission-control run lint` | ✅ TypeScript clean after PM launch clarification/intent fix |
| `npm --prefix apps\mission-control test -- app/lib/api-client.test.ts` | ✅ 24/24 passing after 422 parsing and mission-create coverage |
| Docker image rebuild after app stop | ✅ `orchestrator`, `api-gateway`, and `mission-control` rebuilt; stack left stopped |
| Focused PM/storage backend tests | ✅ `test_generate_pm_feature_contract_uses_context_and_finalize_intent` and `test_list_project_agent_action_events_casts_nullable_filters` pass |
| Focused `ruff` over PM mission-flow/LLM delegation files | ✅ Clean |
| `git diff --check` | ✅ Clean after 2026-06-21 UI/docs cleanup |
| `python -m ruff check services tests scripts` | ✅ Clean |
| `python -m pytest -q` (full suite, excl. `test_agent_base_unit.py`) | ✅ Green — 58 new tests pass |
| `python -m pytest tests/eval/ -q` (97 eval tests) | ✅ 97 passing in 1.65s |
| `python -m pytest tests/services/test_knowledge_lake_unit.py` | ✅ 37/37 new tests pass (first coverage of `knowledge_lake.py`) |
| `python -m pytest tests/services/test_knowledge_embeddings_unit.py` | ✅ 8/8 (3 existing + 5 new) |
| `python -m pytest tests/services/test_langgraph_lifecycle_unit.py` | ✅ 14/14 (13 existing + 1 new PgBouncer guard) |
| `npm run lint` (TypeScript) | ✅ 0 errors |
| Playwright E2E (23 specs) | ✅ 23/23 passing |
| `python scripts/production_review_audit.py` | ✅ 22/22 PASS |
| `git log --all -- deploy/postgres/certs/server.key` | ✅ No output |
| `git log --all -- deploy/redis/certs/redis.key` | ✅ No output |
| DR drill RTO | ✅ 37.13s (target: ≤30 min) |
| Coverage gate | ✅ ≥80% enforced in CI and pyproject.toml |
| `runtime.py` per-module coverage floor | ✅ Raised 60% → 80% (#192); actual 100% line / 99% branch |

> `test_agent_base_unit.py` requires `services/orchestrator` on `sys.path` — run from that directory or via the services test runner. Not broken; excluded from root `pytest` invocation.

---

## Current Backlog

The archived sprint backlog is no longer the source of truth. Use this section
and `docs/CURRENT_TODO.md` for active work.

### Completed today (2026-06-13)

**Batch 2 (this session):**
- Dedicated embedding API key (`KNOWLEDGE_EMBEDDING_API_KEY`) wired through settings,
  compose, and embeddings code.
- Fixed query-side embedding bug: `RETRIEVAL_QUERY` task type and natural-language text
  now used in `_vector_search` (was JSON-serialised dict + wrong task type).
- LangGraph PgBouncer guard: empty `LANGGRAPH_CHECKPOINTER_POSTGRES_URL` now returns
  False with CRITICAL log instead of silently corrupting checkpoint state.
- `KNOWLEDGE_LAKE_AND_EMBEDDINGS.md` and `STORAGE_LAYER.md` completely rewritten to
  match actual code (previous versions described fictional classes/modules).
- 43 new unit tests for knowledge lake, embeddings, and LangGraph lifecycle.
- 4 silent `except Exception: pass` handlers fixed with proper WARNING/DEBUG logging.
- `/health` endpoint extended with agent heartbeat coverage (`agents_total`,
  `agents_with_heartbeat`, `agents_missing_heartbeat`).
- Heartbeat interval mismatch guard added to `heartbeat_service.py`.
- `extraction_degraded` flag added to `port_coordinator.py` return value.
- All 4 HIGH audit items resolved; sigma lane confirmed wired.
- `HANDOFF_CURRENT.md`, `CURRENT_TODO.md`, `IMPLEMENTATION_STATUS.md` updated.

**Batch 1 (earlier today):**
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

1. **Mission Control launch proof**: restart/rebuild the local app so the PM
   launch clarification/intent fix is live, verify PM clarifying responses do not
   expose a launch action, then verify **Confirm and Start** and typed
   proceed-style confirmation create a mission with `user_intent=finalize_plan`.
2. **Fresh Gemini live mission proof**: after launch works, submit a new
   long-brief BUILD_NEW mission and capture evidence that the PM handoff no
   longer truncates context and the mission reaches COMPLETE with non-empty
   LLM-generated output.
3. **CI green after production-gate hardening**: confirm the post-`867d3ec`
   GitHub Actions run completes with all production-critical gates running and
   passing.
4. **Repository-host protections**: enforce branch protection, required status
   checks, secret scanning, and release attestation verification in GitHub
   settings.
5. **Production-environment evidence**: produce target-environment DR,
   retention, backup/restore, and operational evidence outside the local repo.
6. **Legal/policy approval**: review and approve privacy, terms, and external
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
