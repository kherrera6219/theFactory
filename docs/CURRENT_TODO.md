# Current TODO

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

This is the active TODO list for theFactory. Superseded sprint plans, historical
backlogs, and old phase notes live under `docs/archive/` and should not be used
as current work.

---

## Current Status

**Most recent work: security/correctness review of the api-gateway —
found 10 routes with zero caller authentication.** `create_mission`,
`get_mission_pod_assignment`, `get_mission_chain_trace`,
`create_pm_feature_contract`, mission logicnodes/knowledge/knowledge-graph/
audit-reports/audit-artifacts/audit-events/build-artifacts/build-artifact/
artifact-download, and `create_builder_preview` all forwarded to the
orchestrator's `/internal/*` routes with no check on the caller's own
credentials — any anonymous request could read mission prompts, source
code, and audit trails, or create missions / trigger paid LLM calls, for any
`mission_id`. All now require `_require_reader_access`. Also fixed: a
hybrid-mode `_require_operator_access` bypass (any non-empty `X-API-Key`
granted access with zero validation), an X-Forwarded-For rate-limit bypass
(new `GATEWAY_TRUST_PROXY_HEADERS` opt-in, default off), `PROMPT_GUARD_MODE`
default changed from `"log"` to `"block"` (user-confirmed product decision —
OWASP LLM01 prompt injection is now rejected by default), an Anthropic
`max_tokens`/`thinking_budget` mismatch that rejected every high-budget
thinking request, a Gemini-3 model-detection gap (`gemini-3.0-pro`/bare
`gemini-3` were missed), and an OpenAI refusal-content extraction gap. Fixed
and test-verified (1337 backend tests, 0 failures), `api-gateway` Docker
image rebuilt and fixes verified inside the rebuilt container. See
"api-gateway Review (2026-07-03)" under Recently Completed for the full
list including investigated-and-refuted candidates.

Before that: correctness review of the agent orchestration core —
found that AIM source-code extraction was silently non-functional in
production.** `agent_base.py`, `agent_registry.py`, `agent_personas.py`,
`agent_integrations.py`, `agent_scaling.py`, `is_agent.py`,
`dependency_absorption.py`, `aim_generator.py` (~5.3k lines). Two independent
bugs stacked in `_extract_file`: (1) the `pod_worker` import path arithmetic
resolved correctly in local dev but to the filesystem root inside the built
container (never verified against a real container before now), so the
import always failed; (2) even when reachable, the code filtered for a
concept `domain == "import"` that the real pattern catalog never produces.
Both were swallowed by a broad exception handler with only a warning log —
`function_count`/`class_count`/`concept_count`/`detected_imports` were
always the empty/zero fallback for every `ANALYZE_ONLY`/`PORT`/
`DEBUG_REPAIR`/`SECURITY_HARDEN`/`REDUCE_DEPENDENCIES` mission. Fixed both,
updated the Dockerfile to ship `pod_worker`, and verified the fix works
*inside a rebuilt container* (not just locally). Also fixed a
scaling-decision idempotency gap that could orphan partition work on retry,
and a Java-detection false negative. Fixed and test-verified (1332 backend
tests, 0 failures), `orchestrator` Docker image rebuilt. See "Agent
Orchestration Core Review (2026-07-02)" under Recently Completed for the
full list including deferred items.

Before that: correctness review of the orchestrator storage layer.
`storage_missions.py`, `storage_artifacts.py`, `storage_agents.py`,
`storage_pods.py`, `storage_logicnodes.py`, `storage_core.py`, `models.py`
(~3.1k lines) — the DB layer underneath every mission-flow phase. Found and
fixed a real concurrency bug: `insert_agent_action_event` read the latest
hash-chain digest and inserted the next event as two unsynchronized
statements, so two concurrent events for the same project could both chain
onto the same predecessor, silently forking the tamper-evident audit chain.
Fixed with a per-project advisory lock. Several other candidates
(object-storage artifact readback, `row_to_mission` column inference, two
`models.py` fields, self-loop event accumulation) were investigated and
refuted as live bugs by tracing actual callers. Fixed and test-verified (1328
backend tests, 0 failures), `orchestrator` Docker image rebuilt. See "Storage
Layer Review (2026-07-02)" under Recently Completed for the full list
including deferred items.

Before that: deep code review of the Mission Flow v2 lifecycle driver
and the LLM delegation layer, fixing 7 backend bugs. Two backend slices —
`services/orchestrator/orchestrator/mission_flow_v2/` and
`services/orchestrator/orchestrator/llm_delegation/` — were reviewed file by
file (not diff-scoped) using parallel finder agents, each candidate verified
against the actual code before fixing. Most serious: a driver re-invocation
bug where every orchestrator restart re-ran the `queued->pm_intake` preparer
for any in-flight mission, silently regenerating and overwriting
`feature_contract`/`mission_charter` with a fresh, non-deterministic LLM call.
Also fixed: duplicate partition-emission on retry, runtime QC re-executing on
every completion-gate retry, a greedy JSON-extraction regex that discarded
valid LLM decisions, an `intake_status` normalizer that failed open instead
of closed, a Windows drive-relative path-traversal edge case, and a defensive
hardening fix for a non-numeric `risk_score`. All fixed and test-verified
(1327 backend tests, 0 failures), `orchestrator` Docker image rebuilt from
this code. See "Mission Flow v2 + LLM Delegation Review (2026-07-02)" under
Recently Completed for the full list, including deferred lower-priority
findings.

Before that: code review of the Mission Control UX lock-in commits,
plus fixes for all five findings. The review covered the five commits
implementing PM clarification, progress visibility, artifact folder discovery,
and follow-up mission continuation. It found and fixed: a critical
stuck-mission regression (generated-output completion gating could swallow a
packaging failure and leave a mission permanently unable to reach
`COMPLETE`), a critical missing-auth gap on the three new local-filesystem
routes (`open-vscode`, `open-output-folder`, `output-folder-status` had no
session check, unlike every other sensitive route), a false-negative PM
clarifying-question suppression (the word "build" — present in almost every
prompt on this platform — silently suppressed the acceptance-criteria
question), a stale `DeliveryPanel` dependency array, and an over-eager
`resetImportResults()` call on unrelated repo-import field edits. All five are
fixed, test-verified (1319 backend tests / 99 Mission Control tests, 0
failures), and committed. A follow-up closing pass then fixed a
`language.ts` "batch" tie-break bug. See "Post-Review Hardening
(2026-07-02)" under Recently Completed for the full list.

Before that: the Mission Control UX lock-in itself — PM clarification,
mission-progress visibility, artifact folder discovery, and follow-up mission
continuation. The implementation is complete and rebuilt into the local Docker
images, but the post-restart browser mission proof is still pending. Evidence:
`docs/evidence/mission_control_ux_lockin_2026-07-02.md`.

- DONE: PM feature-contract normalization now asks clarifying questions for
  underspecified interactive applications/games. Mission Control renders those
  questions as actionable decision cards with recommended defaults, an edit
  path, and a proceed-with-defaults action.
- DONE: Mission Detail now exposes Live Progress with clearer waiting,
  blocked, retrying, stale, working, and finished indicators so long-running
  missions do not look hung without context.
- DONE: Generated Output and Build Artifacts panels now show the real local
  `output/<mission_id>` path, folder/file status, Copy Path, Open Folder, and
  VS Code actions when supported by the local Windows UI process.
- DONE: Continue with PM now loads prior mission summary, build artifacts,
  delivery summary, and output-folder status, then carries that context in the
  follow-up mission metadata.
- DONE: generated-output completion gating now blocks missions that expect a
  generated output artifact from completing with an empty durable artifact set.
- VALIDATED: Mission Control focused Vitest (36/36), `npm run build`,
  `npm run lint`, focused orchestrator pytest (19/19), compose service graph
  resolution, and Docker rebuilds for `mission-control` and `orchestrator`.
- NEXT: after app restart, run a new browser mission for a modern Angular Snake
  game with `start.bat` and verify PM clarification/defaults, live progress,
  output-folder actions, and Continue with PM in the real UI.

**Previous current work: findings remediation from the 2026-06-30 battery (Phases
0-3 committed and offline-verified; Phase 4 live verification incomplete).**
A phased plan (`FIRST_FULL_SYSTEM_RUN_FINDINGS_2026-06-30.md` recommendations +
`docs/STACK_REMEDIATION_PLAN_2026-07-01.md`) was validated against the actual
code, corrected where the source docs were wrong (see below), then executed:

- **Phase 0 (commit `4445b6b`):** pod-audit misrouting fix landed as-is
  (case-insensitive `_POD_AUDIT_AGENTS_BY_LOWER` lookup).
- **Phase 1 (commit `07883d7`):** Beta (PBLA-03) now fires on every normal
  `BUILD_NEW` mission. **Correction to the original findings doc:**
  `generated_output` is actually set in `_prepare_specialist_plan`
  (`phases_build.py`), not `_prepare_specialist_assignment` as §4/§6.1 stated —
  a different, later function in the same file. The Beta emission was added
  there (not "moved" — the existing `_prepare_fusion` call in
  `phases_runtime.py` stays as the legitimate fallback-path emission for
  missions whose first codegen attempt didn't yield usable output; the shared
  `mission_has_generated_output` guard keeps the two sites mutually exclusive).
- **Phase 2 (commit `a63dfaf`):** new `_check_language_content_signature` in
  `equivalence_verifier.py`. **Correction to the original findings doc:** §6.2's
  claim "no verification gate currently catches
  generated-language-vs-requested-language mismatches" is factually wrong — a
  required check (`_check_language_alignment`) already existed and was wired
  in. The real gap: it compares `generated_output["language"]` (self-reported
  by the same LLM call that wrote the code) against the requested language —
  both values trace back to "what was asked for," so a specialist that
  silently substitutes Python can still label its output correctly and the
  check can never catch it. The new check inspects `generated_code` text
  directly for unambiguous Python tells, scoped to target languages least
  likely to be confused with Python (c, cpp, r, go, rust, shell) — verified
  against the real C and R battery artifacts on disk (`fail`) and real
  Go/Rust/C++ artifacts (`pass`, no false positive). `mission_equivalence_enforcement_enabled`
  still defaults to `False`, so this surfaces as a finding today rather than
  blocking — enabling enforcement is a separate, broader decision.
- **Phase 3 (commit `b70d711`):** `AGENT-08-COMPLIANCE` now fires
  unconditionally at delivery, like Security/VC/Tester (user's explicit choice
  among 3 options). Adds `generate_compliance_assessment` (new LLM-delegation
  function, distinct from Security's threat analysis and from
  `security_compliance.py`'s deterministic PII/license scan), a new
  `MISSION_COMPLIANCE_ASSESSMENT_COMPLETE` event type, and a deterministic
  fallback matching Security's honesty convention.
- All four phases: full `tests/services/` suite passed clean after each
  (1311 passed, 5 skipped, 0 failed at the end; `test_agent_base_unit.py`'s
  collection error is pre-existing and untouched by this work), ruff clean on
  every touched file.
- **Phase 4 (live stack + verification) — stack is up and healthy, live
  mission proof NOT yet done.** Rebuilt every buildable image (orchestrator,
  api-gateway, all 41 dedicated agents, mission-control, dashboard,
  protocol-bus-mcp, workers) via the correct two-file compose form so Phases
  0-3's code is actually running. Brought the stack up; the user separately
  ran `start_app.bat` mid-session, which recreated a subset of containers
  non-destructively (`deploy_postgres-data`/`deploy_redis-data` volumes
  confirmed intact throughout — no data loss this time) and additionally
  brought up `minio`/`neo4j` without hitting the prior port conflicts.
  **Current confirmed live state:** 59/59 `deploy-*` containers healthy or Up
  (0 unhealthy, 0 stuck), orchestrator `/readyz` reports `ready: true` across
  every dependency (Redis, Postgres, Qdrant, Milvus, Neo4j, object storage,
  protocol bus), api-gateway ready. **Stack Remediation Finding 3 (Postgres
  credential mismatch): resolved** — `db_ready: true`, no `FATAL: password
  authentication failed` in logs; matches the plan's prediction that a fresh
  `initdb` against the wiped volume would self-resolve it. **Finding 4
  (`INTERNAL_SERVICE_API_KEY` empty at runtime): very likely resolved** —
  `docker compose config` dry-run confirmed a real, non-empty key resolves at
  all three call sites, and a build-artifacts fetch for an old (pre-wipe)
  mission ID returned a clean `404 resource not found` rather than the old
  `503 gateway internal auth is not configured` — but this was **not
  confirmed against a fresh live mission**, which is the stronger proof.
  **Finding 5 (host port collisions):** confirmed not a code issue (host-port
  overrides already exist in compose); this run happened not to collide, but
  that isn't guaranteed on every run.
  **NOT DONE — the actual remaining step:** submit one live mission through the
  real Mission Control chat UI (not the raw API) and confirm, end-to-end: the
  pod-audit fix (submit a Pod B/C/D language), Beta firing (check
  `protocol:beta:*` bus metrics), `MISSION_DEPLOY_READINESS_ASSESSED` firing
  (findings §6.4 re-confirmation), the new language-content-signature check
  behaving correctly on a real mission, and a definitive build-artifacts fetch
  for that fresh mission (closes Finding 4 conclusively). This step was blocked
  on browser selection (two Chrome extensions connected, needs an explicit
  pick) and the session ended before it was resolved — **this is the next
  action for a fresh session, see Next Actions #1 below.**

Before that: the **Protocol Bus Lane Activation (PBLA) Stage 1** producers were
made code-complete and unit-tested — all six lanes have live producers
(PBLA-00 shared discriminators, PBLA-01 Delta, PBLA-02 Omega, PBLA-03 Beta,
PBLA-04 Rho); see the Protocol Bus Program section below. A **cold-start
healthcheck defect** was also found and fixed: the orchestrator `/health` (the
Docker liveness probe the whole `depends_on` chain gates on) ran live
optional-backend readiness probes and timed out under cold-start contention,
wedging every dependent (api-gateway → mission-control → …) in `Created`.
Fixed by adding a probe-free `/livez` and repointing the healthcheck at it —
confirmed working on a live restart before the above battery ran.

Phase 13 backend/API smoke is complete for this pass. The latest committed
smoke evidence is `docs/evidence/phase13_smoke_latest.json` for mission
`mission-ac933664-bda8-4acf-b265-10171c2ccdf6`, which reached
`COMPLETE`, produced one build artifact, and passed Python syntax validation
for that artifact.

Phase 3 verification-hardening evidence is also current at
`docs/evidence/phase3_non_ascii_smoke_latest.json` for mission
`mission-bd5369ec-3777-4099-89fe-81699289a29d`. That run proves the
non-ASCII artifact path preserved 28 non-ASCII characters through codegen,
packaging, and storage readback.

Validated across current evidence:

- gateway and orchestrator readiness
- mission creation through the API gateway
- authenticated mission polling to `COMPLETE`
- mission events and chain trace
- build-artifact listing and artifact detail retrieval
- Python syntax validation for the generated artifact
- non-ASCII codegen, packaging, and storage-readback preservation

The app is still active development, not production-ready. The backend/API happy
path and Phase 3 artifact-encoding regression are proven, but the broader
release gate still needs Mission Control UI smoke, Pong-style UI artifact rerun,
live failure-injection proof, live provider-fallback proof, full validation,
Phase 8 branch-coverage follow-up, provider preflight, and key-rotation coverage.
Production audit now passes 23/23 checks after the INF-008 compose/evidence
correlation update. CodeQL alerts #337-#338 and Trivy OpenSSL alerts #330-#336
have local remediation in main: parser-based RQCA HTML smoke, raster-only
Mission Control file previews, and refreshed Python service base-image digests.

---

## Active Work Queue

### Mission Control UX Lock-In (implemented; live browser proof pending)

Tracked by `docs/evidence/mission_control_ux_lockin_2026-07-02.md`.

- DONE: PM clarification cards and recommended-default flow in Mission Control
  chat.
- DONE: local output-folder status route plus guarded local Open Folder and VS
  Code actions.
- DONE: artifact panels expose the output path/status even when no generated
  artifact is recorded yet.
- DONE: Continue with PM preloads prior mission/output/artifact context for
  follow-up work.
- DONE: Live Progress panel exposes state-specific next actions for waiting,
  blocked, retrying, stale, and finished missions.
- VALIDATED: focused frontend/backend tests, Mission Control build/lint, and
  Docker rebuilds for the changed UI/orchestrator images.
- NEXT: run the post-restart Angular Snake browser mission and confirm the UX
  behaves correctly under a real mission.
- A code review pass since this implementation found and fixed 5 defects in
  this feature area (stuck-mission gating, missing auth on the local-folder
  routes, a suppressed PM clarifying question, and 2 frontend bugs) — see
  "Post-Review Hardening (2026-07-02)" under Recently Completed.

### Repository ZIP Import Migration (active implementation)

Tracked by `docs/REPO_ZIP_IMPORT_MIGRATION_PLAN.md`. This replaces the
GitHub API based repository intake path with local `.zip` repository snapshots
so Mission Control can index source without GitHub credentials or network
access.

- DONE: Phase 1 archive core. Added a safe ZIP archive helper for path
  normalization, common-root stripping, archive SHA-256 hashing, entry limits,
  large-file skipping, selected text reads, and binary detection. Focused
  archive helper tests pass.
- DONE: Phase 2 import route. `POST /api/repo/import` now accepts
  multipart/form-data with an `archive` `.zip` upload plus `display_name`,
  `source_ref`, `subdirectory`, and `max_files`; it indexes the archive locally
  and returns ZIP metadata while enforcing upload-size and truncation signals.
- DONE: Phase 3 review route conversion. `POST /api/repo/review` now accepts
  multipart/form-data ZIP review requests, requires `archive_sha256`, includes
  required selected paths outside the display slice, reads selected file text in
  one ZIP pass, and returns the existing review bundle shape without GitHub API
  calls.
- DONE: Phase 4 UI migration. The `/repo` page now renders a local ZIP file
  selector, source-ref metadata, archive hash/root-prefix summaries, FormData
  import/review calls, and review-gate reset behavior when archive scope changes.
- VALIDATED: Mission Control `npm run lint`, full `npm run test` (87/87), focused
  `npm run test -- app/api/repo` (22/22), and targeted Playwright repo intake
  e2e passed.
- NEXT: Phases 5-7. Add mission launch index guard, repo knowledge ingestion,
  and PM/pod-worker repository context loading so indexed repo content becomes
  available from the internal database.

### Verification & Reporting Hardening (Phase 1-3 complete; verification backlog remains)

Tracked in full by `UPDATE_PLAN_VERIFICATION_HARDENING_2026-06-29.md`. Surfaced
by a live "Modern Neon Pong" chat-intake mission on 2026-06-29 that reached
`COMPLETE` but whose artifact did not match its own contract.

0a. **Phase 1 — verification means correctness** (DONE):
    - DONE (1a): Artifact-format gate in `equivalence_verifier.py` — a `.js`
      artifact against an HTML-file contract now fails verification and blocks
      under enforcement. Verifier tests pass, including a Neon Pong regression.
    - DONE (1b): Replaced the always-`manual_review` `_check_acceptance_criteria`
      with real per-criterion coverage evaluation.
    - DONE (1c): Tagged the artifact verification block
      `verification_scope="integrity"` and the equivalence report
      `verification_scope="correctness"`, clarified the integrity-check copy, and
      updated the Mission Control `EquivalenceReportPanel` so integrity no longer
      reads as "runs."
    - DONE (1d): Closed the follow-up false negatives: prohibited `.js/.css`
      mentions such as "no external .js/.css" no longer expand acceptable
      deliverable formats, and extensionless artifacts fail when the contract
      names a required format.
    - TODO: Live re-run of a Pong-style mission to confirm the gate end-to-end
      (pending stack restart).
0b. **Phase 2** — DONE in main: runnable-artifact smoke evidence now rides the
    existing RQCA path, JavaScript syntax failures short-circuit as real runtime
    QC failures, HTML artifacts get static structure plus inline-script syntax
    smoke with honest browser-load `DRY_RUN` reporting, and an authoritative
    `lifecycle_engine` field is emitted through orchestrator, gateway,
    chain-trace, and Mission Control.
0c. **Phase 3** — DONE in main and live stack: non-ASCII artifact
    regression coverage, packaging-time mojibake guard/repair, codegen / packaging /
    storage-readback diagnostic trace, lifted PM clarifying-question/context
    truncation, and a passing live non-ASCII mission rerun recorded at
    `docs/evidence/phase3_non_ascii_smoke_latest.json`.

1. Run Phase 13 Mission Control UI smoke for the same mission path covered by the
   backend/API smoke.
2. Run Phase 13 failure-injection proof against the live stack: interrupt
   protocol-bus MCP or another runtime dependency mid-mission and verify
   retry/resume or clean user-visible failure.
3. Run Phase 13 provider-fallback proof with an invalid primary provider key and
   confirm fallback is recorded in mission output/evidence.
4. Run full `make validate` in the current environment and capture the result.
5. Raise or explicitly defer the remaining Phase 8 `mission_flow_v2/` branch
   coverage carry-forward. Current evidence: isolated suite 81 passed with
   91.56% line / 71.69% branch, and broader related suite 170 passed with
   92.43% line / 74.70% branch, against the older 90% / 85% strict target.
6. Add Settings provider/key/model preflight that performs a real small provider
   call and reports the actual provider status.
7. Move provider/model selection fully into the Mission Control settings/vault
   path instead of relying on `.env` defaults.
8. Rotate exposed provider keys before any public, partner, or shared deployment.

### Protocol Bus Program (4 staged initiatives)

The full effort to evolve the Protocol Bus from a telemetry sidecar into an
agent-coordination backbone is documented as a staged program in
`PROTOCOL_BUS_PROGRAM_ROADMAP.md`:

- **Stage 1 — PBLA** (`PROTOCOL_BUS_LANE_ACTIVATION_PLAN.md`): real producers on
  all six lanes. Plan validated against code; **PBLA-00 in progress**. Detailed
  below.
- **Stage 2 — EDCP** (`EDCP_PHASE_PLAN.md`): consumers + control-flow inversion.
  Reactivated from archive; EDCP-01 complete, EDCP-02 pending.
- **Stage 3 — Agent Runtime Split** (`AGENT_RUNTIME_SPLIT_PLAN.md`): agents as
  independent bus-participant processes. Stub, not scheduled.
- **Stage 4 — Semantic Bus** (`SEMANTIC_BUS_PLAN.md`): embedding-based routing.
  Stub, not scheduled.

PBLA is the prerequisite for the load-bearing cutovers in EDCP. PBLA only makes
the lanes observable (telemetry); EDCP is what makes them load-bearing.

### Protocol Bus Lane Activation (PBLA, Stage 1) — code complete + live-validated

Status: PBLA-00 (shared discriminators), PBLA-01 (Delta), PBLA-02 (Omega),
PBLA-03 (Beta), and PBLA-04 (Rho) are implemented and unit-tested. **Live
validation ran 2026-06-30**: 20 missions through the real Mission Control chat
UI, all reaching `COMPLETE`. Alpha/Sigma/Delta/Omega confirmed firing with zero
DLQ writes; Rho confirmed via a direct producer smoke test. Full results,
code-artifact review, and recommendations:
`FIRST_FULL_SYSTEM_RUN_FINDINGS_2026-06-30.md` (repo root).

**Two real issues surfaced by the live run — both fixed and committed since
(see Current Status above):**
- **Beta never fired across all 20 missions.** Fixed in commit `07883d7`: the
  emission was added to `_prepare_specialist_plan` (the function that actually
  sets `generated_output`, not `_prepare_specialist_assignment` as originally
  documented). Live re-confirmation still pending — see Current Status.
- **Pod-audit agent misrouting.** Fixed in commit `4445b6b`.

**Also surfaced (not PBLA-specific, but same run):** 2 of 20 missions (C, R)
generated the wrong language entirely (Python simulating the target language)
and still reached `COMPLETE`. **Addressed in commit `a63dfaf`** — see Current
Status for why the originally-suspected "no gate exists" diagnosis was wrong
and what the new check actually does. Live re-confirmation still pending.

**Environment note:** the battery's database state was subsequently wiped by
`stop_app.bat` (`docker compose down -v`). The stack has since been rebuilt and
brought back up (see Current Status) — Postgres and `INTERNAL_SERVICE_API_KEY`
issues from `docs/STACK_REMEDIATION_PLAN_2026-07-01.md` both look resolved,
pending final live-mission confirmation.

- **PBLA-05** (optional): lane observability surfacing in the operations snapshot.

Once the Beta fix lands and the stack remediation is done, Stage 2 (EDCP)
becomes unblocked — its consumers filter PBLA's `pbla_*` discriminators off the
shared broadcast channels.

Tracked in full by `PROTOCOL_BUS_LANE_ACTIVATION_PLAN.md`. Standalone and
independent of the EDCP phase plan — can run before, during, or after it. The
Protocol Bus infrastructure (`protocol-bus-mcp`, all six Pydantic-validated
payload types, HMAC/replay/dedup/backpressure/DLQ) is fully built; the gap is
adoption. A repo-wide trace confirms only two of six lanes have live producers
in the mission pipeline: Alpha (`phases_build.py`) and Sigma (via
`knowledge_lake.broadcast_knowledge_ready` in `phases_intake.py`). This
initiative adds the four missing call sites following the proven Alpha/Sigma
fire-and-forget pattern. No schema changes, no new infrastructure — wiring only.

- PBLA-00 — Foundation: shared emission-discriminator constants in a new
  `orchestrator/protocol_bus_emissions.py`. Do first — PBLA-01..04 and EDCP-02/04
  all import these so producers and consumers cannot drift (consumers tail the
  broadcast channel, so a discriminator is mandatory, not cosmetic).
- PBLA-01 — Delta (audit verdicts) in `phases_build.py`. Lowest risk; insertion
  point, payload fields, and verdict mapping ({PASS,FAIL,WARN}) all confirmed.
  Emit inside the `MISSION_POD_AUDIT_COMPLETE` idempotency guard.
- PBLA-02 — Omega (PM ↔ user handoff) in `phases_delivery.py`. Do not extend
  `OmegaPayload`; handoff metadata + `message_type` discriminator ride inside
  `feature_contract` per the EDCP-02 deferral note in `protocol_bus_producer.py`.
- PBLA-03 — Beta (specialist/LogicNode results) in `phases_runtime.py`
  `_prepare_fusion` (after `generated_output` is set). Insertion point confirmed;
  `language` is present but `logicnode_id`/`confidence_score` must be synthesized
  and clamped to `[0,1]`.
- PBLA-04 — Rho (traffic/rate-limit control) in `llm_delegation/providers.py`
  (`_post_with_retry` 429 path / `_call_provider` finally). Candidate sites
  confirmed; blocker: `settings` is not in scope at the provider layer — pick the
  emit-one-layer-up vs module-accessor vs higher-level-signal option first.
- PBLA-05 — Lane observability surfacing (optional, last): expose per-lane
  activity in the operations snapshot / Mission Control. Read-only, no new
  producers.
- Closing evidence: one live mission showing traffic on all six
  `protocol:{lane}:*` streams, captured under `docs/evidence/` parallel to the
  S1-01 evidence, with a new Current Proof Points row in
  `docs/IMPLEMENTATION_STATUS.md`.

---

## Recently Completed

### api-gateway Review (2026-07-03): 10 unauthenticated routes, plus 5 smaller confirmed bugs

Security/correctness review of `services/api-gateway/api_gateway/main.py`
(~2.8k lines), via four parallel finder agents reading the full file plus a
fifth targeted triage pass, each candidate verified against actual code and
orchestrator-side handlers before fixing:

- Fixed 10 routes with zero caller authentication: `create_mission`,
  `get_mission_pod_assignment`, `get_mission_chain_trace`,
  `create_pm_feature_contract`, `get_mission_logicnodes`,
  `get_mission_knowledge`, `get_mission_knowledge_graph`,
  `get_mission_audit_reports`, `get_mission_audit_artifacts`,
  `get_mission_audit_events`, `get_mission_build_artifacts`,
  `get_mission_build_artifact`, `download_mission_artifact`,
  `create_builder_preview` — all now require `_require_reader_access`.
  `update_mission_state` was checked and confirmed already correct (uses the
  deliberate `_resolve_mutation_forward_headers` pass-through pattern, with
  the orchestrator's own `MUTATION_AUTH_DEP` as the actual enforcement
  authority).
- Fixed a hybrid-mode `_require_operator_access` bypass (any non-empty
  `X-API-Key` granted access with zero validation).
- Fixed an X-Forwarded-For rate-limit bypass in `_client_identifier` (new
  `GATEWAY_TRUST_PROXY_HEADERS` env flag, default `false`).
- Changed `PROMPT_GUARD_MODE` default from `"log"` to `"block"` (explicit
  user product decision) so OWASP LLM01 prompt-injection attempts are
  rejected by default instead of merely logged.
- Fixed an Anthropic `max_tokens`/`thinking_budget` mismatch in
  `_anthropic_builder_preview` (max_tokens now scales with the
  caller-configurable thinking budget instead of a hardcoded 1200, which
  rejected every high-budget thinking-enabled request).
- Fixed a Gemini-3 model-detection gap in `_is_gemini_3_model` (hardcoded
  `3.1-`/`3.5-` prefixes missed `gemini-3.0-pro` and bare `gemini-3`;
  replaced with a generalized regex, verified no new false positives).
- Fixed an OpenAI refusal-content extraction gap in `_extract_openai_text`
  (`refusal`-type content blocks carry text under `refusal`, not `text`).
- Investigated and refuted: silent pod-manager fallback (pure in-process
  dict lookup, no network reachability failure to mask), chain_trace
  forgery (plain read-only proxy, no forgery vector), PII-scan field
  exclusions (attachments carry no inline content through this endpoint),
  `_dependency_status` exception swallowing (exceptions correctly degrade
  health flags — this is the right behavior for `/readyz`), unvalidated
  provider string (falls through safely to the offline fallback),
  markdown-lstrip/mixed-provenance labeling (no such lstrip exists; source
  labeling is consistent on every path). Weak base64/secret regex patterns
  in the PII/prompt-injection scanners were confirmed as a real but accepted
  limitation (heuristic defense-in-depth logging, not a hard control).
- Every fix has a regression test independently proven to fail against the
  pre-fix code via `git stash`. Full backend suite: 1337 passed, 5 skipped.
  `ruff check` clean. `deploy-api-gateway:latest` rebuilt and every fix
  verified directly inside the rebuilt container.
- Deferred/no further action: weak PII/secret regex patterns (documented
  limitation, not a hard control — would need a real entropy/pattern-based
  secret scanner to meaningfully improve, out of scope for this pass).

### Agent Orchestration Core Review (2026-07-02): AIM extraction was silently non-functional in production

Correctness review of `agent_base.py`, `agent_registry.py`,
`agent_personas.py`, `agent_integrations.py`, `agent_scaling.py`,
`is_agent.py`, `dependency_absorption.py`, `aim_generator.py` (~5.3k lines),
via parallel finder agents reading full files, each candidate verified
against actual callers before fixing:

- Fixed the most significant finding of the review effort so far: AIM
  (Application Intelligence Map) source extraction was silently
  non-functional in the deployed orchestrator container. `_extract_file`'s
  `pod_worker` import path used `Path(__file__).resolve().parents[2]`,
  correct in local dev but resolving to the filesystem root inside the
  built container (the Dockerfile only copies `services/orchestrator`'s
  contents to `/app`, no `services/` ancestor exists there) — apparently
  never verified against a real container. Even when reachable, the code
  filtered `result.concepts` for `domain == "import"`, a value the real
  pattern catalog never produces; `ExtractionResult` has its own correctly-
  populated `imports` field that was never used. Both silently fell through
  a broad exception handler to an empty/zero fallback with only a warning
  log. Fixed both: multi-candidate path resolution (checks which location
  actually exists), reads `result.imports` directly, and the Dockerfile now
  copies `services/pod-worker/pod_worker` to `/app/pod_worker` (no new pip
  deps needed). Verified working by running Python directly inside a
  rebuilt container image, not just locally.
- Also fixed the import-count cap: `detected_imports` was capped at
  `sorted(...)[:50]`, alphabetically dropping real dependencies (e.g.
  "requests", "sqlalchemy") for any codebase with 50+ distinct imports.
  Raised to 1,000 and folded into the existing `truncated` signal.
- Fixed a scaling-decision idempotency gap: `_prepare_specialist_plan`
  (`mission_flow_v2/phases_build.py`) recomputed a fresh `ScalingDecision`
  with new random partition IDs on every re-entry (it's explicitly
  re-entrant by design — the PORT two-phase flow re-enters it), orphaning
  already-emitted/completed partition work tracked under the old IDs. Fixed
  with a guard: skip recomputation if a decision already exists.
- Fixed a Java-detection false negative in `is_agent.py`: the detection
  regex was already reasonably Java-specific, but an additional gate
  required the literal word "java" to also appear in the prompt/source,
  silently skipping Java bootstrap-doc indexing for legitimate Java code
  that never mentions "java" by name.
- VALIDATED: full backend suite — 1332 passed, 5 skipped, 0 failed (1328
  baseline + 4 new regression tests). `ruff check` clean. `orchestrator`
  Docker image rebuilt and the AIM fix specifically verified inside the
  rebuilt container.

**Deferred, not fixed this pass:** `make_specialist_for_language`'s
case-sensitive language lookup and `make_agent`'s silent fallback to a
generic `SpecialistAgent` on a registry/factory-map mismatch
(`agent_base.py`) — real risks in principle, but the former has zero
callers anywhere in the codebase today; `dependency_absorption.py`'s
version-conflict-resolution ordering (first source wins, no conflict
surfaced) and stdlib-import miscategorization; `agent_scaling.py`'s silent
clamping of a misconfigured `max_instances` to 1 with no warning.

### Storage Layer Review (2026-07-02): audit-chain fork race fixed

Correctness review of `storage_missions.py`, `storage_artifacts.py`,
`storage_agents.py`, `storage_pods.py`, `storage_logicnodes.py`,
`storage_core.py`, `storage.py`, `models.py` (~3.1k lines), via parallel
finder agents reading full files, each candidate verified against actual
callers before deciding to fix or refute:

- Fixed a real concurrency bug: `insert_agent_action_event`
  (`storage_agents.py`) read the latest hash-chain digest for a `project_id`
  then inserted the next event as two unsynchronized statements (pool
  connections are `autocommit=True`, no transaction/lock around the pair).
  Two concurrent events for the same project could both read the same
  `prev_digest` and both chain onto it, forking the tamper-evident audit
  chain with no error (no unique constraint catches it). Fixed with a
  transaction plus `pg_advisory_xact_lock(hashtextextended(project_id, 0))`
  serializing concurrent writers per project.
- Investigated and refuted as live bugs (traced actual callers, not just
  code in isolation): `get_build_artifact` returning `artifact_text=None`
  for offloaded artifacts (intended — its one real caller,
  `routes/internal.py`, already redirects to a presigned URL);
  `row_to_mission`'s `len(row) >= 7` inference (every real query selects
  exactly 7 columns, the fallback branch is dead); `models.py`'s
  `risk_assessment`/`MissionAttachment.purpose` (zero readers anywhere);
  self-loop `MISSION_COMPLETION_BLOCKED` event accumulation (intentional —
  the code's own comment frames it as a checkpoint event, metrics already
  dedupe it).
- VALIDATED: full backend suite — 1328 passed, 5 skipped, 0 failed (1327
  baseline + 1 new regression test). `ruff check` clean. `orchestrator`
  Docker image rebuilt and verified to contain the fix.

**Deferred, not fixed this pass:** `storage_pods.py` pod-name
case-sensitivity (real risk in principle, one current caller, always
consistently cased); unconditional S3 re-upload on every
`upsert_build_artifact` retry (its main trigger was already closed by the
prior session's `_ensure_verified_build_artifact` lifecycle fix); no
digest verification of caller-supplied `digest_sha256` against actual
`artifact_text`; `models.py`'s `VALID_TRANSITIONS` table is pure
documentation, never enforced by `transition_mission_state` — a real design
gap, but wiring it in is a bigger behavioral change than this pass's scope.

### Mission Flow v2 + LLM Delegation Review (2026-07-02): 7 backend bugs fixed

Deep correctness review of `mission_flow_v2/` and `llm_delegation/`, reading
full files (not diffs) via parallel finder agents, each candidate verified
against the actual code before fixing:

- Fixed a critical recovery re-invocation bug: `advance_mission_lifecycle_v2`
  (`lifecycle.py`) iterated its full transition table from `queued` on every
  call regardless of the mission's actual state. Since the lifecycle-recovery
  loop restarts a driver task for every in-flight mission on every
  orchestrator restart, this silently re-ran `_prepare_pm_intake` and
  overwrote `feature_contract`/`mission_charter` with a fresh, non-
  deterministic LLM call each time. Fixed by reading the mission's actual
  current state once and skipping to the matching transition before running
  any preparer.
- Fixed duplicate partition-emission on retry: `_emit_partition_work_items`
  (`phases_intake.py`) only marked emission complete after every partition
  succeeded, so a mid-batch failure meant a retry re-emitted already-
  succeeded partitions with fresh random event IDs. Now tracks per-partition
  emitted IDs and persists progress on failure.
- Fixed runtime QC re-executing on every completion-gate retry:
  `_prepare_runtime_qc` (`phases_runtime.py`) had no cache-check guard, unlike
  the testdata-manifest step in the same function, so real sandboxed QC
  execution and a second LLM assessment re-ran from scratch on every retry.
  Now short-circuits on a cached, non-skipped report.
- Fixed a greedy JSON-extraction regex (`llm_delegation/text.py`,
  `_extract_decision_payload`) that spanned from the first `{` to the last
  `}` in the whole LLM response, discarding valid agent decisions whenever
  the response had reasoning-with-example-braces or two JSON blocks. Replaced
  with a balanced-brace scanner.
- Fixed `_normalize_pm_feature_contract`'s `intake_status` coercion
  (`normalizers.py`), which defaulted any unrecognized LLM value to `"ready"`
  (fail-open) instead of `"needs_clarification"` (fail-closed).
- Fixed a Windows drive-relative path-traversal edge case in
  `_write_artifact_to_disk` (`phases_build.py`) — a path like `C:evil.txt` is
  neither absolute nor `".."`-prefixed, so the fragment-based guard could
  miss it depending on drive-letter coincidence. Now validates the resolved,
  joined path against the mission directory.
- Defensive hardening: `_build_prompt` (`prompts.py`) now tolerates a
  non-numeric `risk_score` instead of an uncaught crash.
- VALIDATED: full backend suite — 1327 passed, 5 skipped, 0 failed (1319
  baseline + 8 new regression tests). `ruff check` clean. Every fix's test
  confirmed to fail against the pre-fix code via `git stash` before being
  accepted. `orchestrator` Docker image rebuilt from this code.

**Deferred, not fixed this pass** (lower confidence/impact):
- `generators_artifacts.py`: unguarded `int()` cast on LLM-supplied totals
  (`generate_master_logic_stream`); `primary_artifact` selection missing an
  `isinstance` guard on build-artifact list entries.
- `providers.py`: an unrecognized/malformed provider string silently routes
  to the OpenAI backend instead of failing explicitly; the fallback-provider
  path doesn't re-check safety-block state before resending a
  already-known-unsafe prompt.
- `normalizers.py`/`fallbacks.py`: several telemetry-only accuracy issues —
  `eliminated_duplicates` has no upper bound relative to node count, non-dict
  entries in `logicnodes` inflate duplicate counts, no size cap on
  `generated_code`, `_fallback_vc_commit_strategy` skips the `_clean_text`
  sanitization every other fallback builder applies.
- `text.py`/`health.py`: `_normalize_agent_choice` doesn't validate its own
  fallback is in `allowed_ids`; p95 latency computed via floor instead of
  ceiling, understating it for small sample sizes; `coverage_thin` verdict
  message can't distinguish an extraction failure from a dedup-only issue.

### Post-Review Hardening (2026-07-02): stuck missions, auth gap, false-negative clarifying question

Code review of the five Mission Control UX lock-in commits, plus fixes for
every finding:

- Fixed a critical stuck-mission regression: `mission_expects_generated_
  output_artifact()` could require a build artifact for missions with neither
  `generated_output` nor `source_code`; the resulting `ValueError` was
  silently swallowed as a warning, leaving the mission permanently unable to
  clear the `has_successful_build_artifact` completion gate with no visible
  signal. Added `build_missing_source_artifact_failure()`
  (`build_artifacts.py`) so `_ensure_verified_build_artifact`
  (`mission_flow_v2/phases_build.py`) now records a real `FAILED` artifact and
  emits `MISSION_BUILD_ARTIFACT_FAILED` to the chain trace instead of raising.
- Fixed a critical false negative in the PM clarifying-question policy:
  `acceptance_tokens` in `llm_delegation/text.py` included the bare word
  `"build"` via substring match, suppressing the "what counts as done for
  acceptance?" question for almost every prompt on this platform. Converted
  all four token blocks to the existing word-boundary-safe `has_token()`
  helper and dropped `"build"` from `acceptance_tokens`.
- Fixed a critical missing-auth gap: the three new
  `apps/mission-control/app/api/local/*` routes (open-vscode,
  open-output-folder, output-folder-status) had no
  `requireOperatorRequestSession` check, unlike every other sensitive route.
  Two of them spawn host processes from a client-supplied mission ID, and
  Next.js's `request.json()` ignoring `Content-Type` meant a cross-origin
  request using a CORS-safelisted content type could reach them without
  preflight. Added the session check to all three.
- Fixed `DeliveryPanel`'s stale output-folder status (its refresh effect
  depended on `buildArtifacts.length`, missing in-place status transitions)
  and `resetImportResults()` firing on unrelated repo-import field edits
  (display name/source ref/subdirectory/max files), which discarded
  in-progress import/review state on every keystroke.
- Also removed ~200 lines of dead GitHub-API intake code from
  `apps/mission-control/app/api/repo/shared.ts` (zero callers after the ZIP
  import migration's Phase 4 UI cutover).
- VALIDATED: full backend suite (1319 passed, 5 skipped, 0 failed), full
  Mission Control suite (99 passed), `ruff check` clean, `tsc --noEmit` clean.
  New regression tests added for all five findings.
- **Follow-up closing pass (same day):** covered every file in the 5 reviewed
  commits left unexamined by the first pass. Found and fixed one more real
  bug: `language.ts`'s `inferRequestedTargetLanguage` could tie `"batch"` (a
  Windows launcher-script mention) against the mission's real implementation
  language and let it win by accidental array-ordering luck, even though
  `"batch"` has zero backend specialist support. Fixed by excluding `"batch"`
  from the overall winner pick; 2 new regression tests. Everything else
  checked (`smelt-cycle.ts`, `types.ts`, the rest of the e2e spec,
  `phase13_smoke.py`, `start_app.bat`, `globals.css`, `test_runtime_unit.py`)
  was clean, no changes needed. A cold-read independent verifier agent
  re-checked the original fix commit end-to-end and confirmed all five fixes
  correct and complete with no new defects.

### Security Alert Remediation

- Replaced RQCA HTML artifact regex parsing with `HTMLParser`-based structure
  and inline-script extraction for CodeQL alert #338.
- Restricted Mission Control attachment previews to raster image MIME/extension
  types and sanitized filenames before display or source-bundle metadata use for
  CodeQL alert #337.
- Refreshed Python slim-bookworm base-image digests across Python services to
  pick up the fixed Debian OpenSSL package for Trivy alerts #330-#336.
- Validation passed for focused Ruff, runtime-QC unit tests, Mission Control
  lint, orchestrator Docker rebuild, and in-image OpenSSL version check
  (`3.0.20-1~deb12u2`). Local Trivy CLI was not installed for a local rescan.

### Phase 8 Mission Flow v2 Coverage and INF-008

- Added targeted Mission Flow v2 coverage for attachment parsing/degradation,
  PM clarification emit failures, FETCH knowledge-ready broadcast, CEO
  delegation/PORT setup, pod-standard audit/thin coverage, artifact disk
  writing, runtime QC, DEPABS execution, fusion ordering, and completion gates.
- Fixed the fusion Neo4j depth-sort import so the runtime reaches the real
  `orchestrator.neo4j_store` adapter instead of silently skipping the sort.
- Phase 8 line coverage now clears the older 90% target: isolated suite
  91.56% line / 71.69% branch; broader related suite 92.43% line / 74.70%
  branch. The remaining strict carry-forward is branch coverage or explicit
  deferral of the old 85% branch target.
- Production audit now passes 23/23 checks; `INF-008` is closed by fail-closed
  compose service-key defaults plus operations/observability evidence
  correlation for full-dedicated strict mission evidence and DORA metrics.

### Failure-Injection Coverage

- Added failure-injection coverage for storage fallback/readback behavior,
  protocol-bus Redis failure/backpressure paths, worker auth/emit/runtime
  failure handling, and provider fallback/degraded-result paths. Live Phase 13
  failure-injection proof remains a separate release task.

### Phase 13 Backend/API Smoke

- Added `scripts/phase13_smoke.py` and `make phase13-smoke`.
- Fixed MissionEvent schema drift for `MISSION_RUNTIME_QC_SKIPPED` and
  `MISSION_RUNTIME_QC_BLOCKED`.
- Rebuilt/restarted orchestrator and verified the previously failing
  `/events` and `/chain-trace` endpoints return 200.
- Committed passing evidence at `docs/evidence/phase13_smoke_latest.json`.
- Rebuilt the full dedicated-agent Docker stack one final time and reran the
  smoke against the rebuilt stack.

### Phase 12 Documentation Drift

- `make validate` runs documentation validation and OpenAPI drift checks.
- `scripts/validate_documentation.py` validates metadata, links, public
  docstrings, migration-guide drift, and architecture diagram drift.
- Current validation reports 75 metadata-checked docs, 117 link-checked docs,
  and 17 docstring-checked files.

### Phase 11 Mission Control E2E

- Mission Control lint, unit tests, build, and Playwright E2E passed in the
  Phase 11 review.
- Production-audit check `UI-011` verifies Mission Control E2E script/CI parity
  and artifact hygiene.

### Phase 10 Reliability

- Baseline reliability evidence was refreshed at
  `docs/evidence/reliability_qualification_baseline_2026-06-26.json`.
- The run passed with 600 mission requests, 99.00% success, and zero readiness
  failures.

### Phase 9 Security

- Storage-boundary PII and prompt scanning are in place for mission creation.
- Worker startup enforces production service-auth posture.
- Base compose host-published ports default to loopback.
- Object-storage TLS and protocol-bus dedup TTL production controls were aligned.

---

## Current Known Gaps

| Area | Status |
|---|---|
| Artifact correctness | Phase 1+2 code now enforces explicit format mismatch/missing extension and records runnable-smoke evidence; live Pong rerun still needed |
| Artifact encoding | Phase 3 code adds non-ASCII regression coverage, conservative mojibake repair before digest, diagnostic trace, and passing live non-ASCII evidence at `docs/evidence/phase3_non_ascii_smoke_latest.json` |
| Engine reporting | Phase 2 code emits authoritative `lifecycle_engine`; live Mission Detail rerun still needed |
| Production audit | 23/23 checks pass; `INF-008` closed |
| Phase 8 coverage | Line target met; branch target follow-up remains at 74.70% against the older 85% branch target |
| Phase 13 UI | Backend/API smoke passed; Mission Control UI smoke still needed |
| Failure injection | Unit failure-injection coverage refreshed; live Phase 13 interruption proof still needed |
| Provider fallback | Not yet refreshed for Phase 13 |
| Full validation | Focused validation passed; full `make validate` still needs current run |
| Provider settings | Provider/model still partly environment-driven |
| Key hygiene | Exposed provider keys must be rotated before wider use |
| Repository ZIP import | Phase 1 archive core, Phase 2 ZIP import route, Phase 3 ZIP review route, and Phase 4 ZIP UI migration are implemented and locally validated; mission index guard, repo knowledge ingestion, and agent context wiring remain open |
| Protocol Bus lanes | All six lanes have live producers (PBLA-00..04); Beta fix committed (`07883d7`) but not yet re-confirmed live; only Sigma is consumed so far. Four-stage program tracked by `PROTOCOL_BUS_PROGRAM_ROADMAP.md` (PBLA done → EDCP next → Agent Runtime Split → Semantic Bus) |
| Pod-audit routing | Fixed and committed (`4445b6b`); baked into the rebuilt live stack; not yet re-confirmed via a fresh live mission |
| Beta lane (PBLA-03) | Fixed and committed (`07883d7`) — emission added to `_prepare_specialist_plan`, the actual generated_output set-site (the findings doc named the wrong function); baked into the rebuilt live stack; not yet re-confirmed live |
| Generated-language verification | Fixed and committed (`a63dfaf`) — new `_check_language_content_signature` catches Python-fallback substitution for c/cpp/r/go/rust/shell targets; verified offline against the real C/R battery artifacts; not yet re-confirmed against a fresh live mission |
| Compliance trigger | Fixed and committed (`b70d711`) — `AGENT-08-COMPLIANCE` now fires unconditionally at delivery like Security/VC/Tester, per explicit user decision |
| Stack credentials | Postgres credential mismatch (Finding 3): resolved — confirmed `db_ready: true` on the rebuilt stack (old volume was wiped, fresh initdb picked up current `.env`). `api-gateway` `INTERNAL_SERVICE_API_KEY` (Finding 4): very likely resolved (clean 404 instead of the old 503 auth-not-configured error; compose config confirms correct resolution) but not confirmed against a fresh live mission — see Next Actions #1 |
| Database state | `postgres-data`/`redis-data` volumes were wiped once by `stop_app.bat` (`docker compose down -v`) after the 2026-06-30 battery; the stack has since been rebuilt from scratch and is healthy again. A second, non-destructive container recreation happened mid-Phase-4 (via `start_app.bat`) — volumes confirmed intact, no data lost |
| Live verification of Phases 0-3 | Stack is up, healthy, and running the fixed code, but no fresh mission has been run through the chat UI yet to prove the fixes work live end-to-end — this is the single most important next action |

---

## Known Non-Issues

- `.pytest-tmp/` may remain as an untracked local temp directory from prior test
  runs. It is not part of the repository.
- OTel/Jaeger export warnings during tests are expected when Jaeger is not
  running locally and do not by themselves fail tests.
- Files under `docs/archive/` are historical and should not drive active work
  unless reconciled into this file.
