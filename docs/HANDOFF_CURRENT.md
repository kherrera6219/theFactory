# Current Handoff

Document version: 2026.07.02
Last updated: 2026-07-02
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

**If you are picking this up cold:** the newest completed work is a code
review of the Mission Control UX lock-in commits (PM clarification, progress
visibility, artifact output folder discovery, Continue with PM) plus fixes for
every finding it surfaced, including a critical stuck-mission regression, a
missing-auth gap on the new local-filesystem routes, and a suppressed PM
clarifying question. All fixes are committed and test-verified (1319 backend
tests, 99 Mission Control tests, 0 failures). See "Post-Review Hardening
(2026-07-02)" below for the full list.

Before that: the Mission Control UX lock-in itself (PM clarification, progress
visibility, artifact output folder discovery, and Continue with PM). The code
is implemented, focused tests pass, and the `mission-control` / `orchestrator`
Docker images have been rebuilt. The next live action is to restart the app
and run a real browser mission asking for a modern Angular Snake game with
`start.bat`, then verify that clarification/defaults, progress indicators,
output-folder actions, and follow-up context all behave correctly. Evidence:
`docs/evidence/mission_control_ux_lockin_2026-07-02.md`.

Previous high-priority context: Phases 0-3 of the findings-remediation work
(pod-audit fix, Beta fix, language-content-signature check, unconditional
Compliance) are all committed and offline-verified, and the live stack was
rebuilt healthy, but a fresh live mission proof remains pending.

Use this file with `docs/CURRENT_TODO.md` and
`docs/IMPLEMENTATION_STATUS.md`. Historical phase notes are archived and should
not override these current files.

---

## Current Application State

theFactory is an active local-first AI software factory application. It is not a
production-ready release.

The current validated backend/API proof is `docs/evidence/phase13_smoke_latest.json`
for mission `mission-ac933664-bda8-4acf-b265-10171c2ccdf6`, which reached
`COMPLETE`, returned mission events and chain trace, produced one build
artifact, and passed Python syntax validation for that artifact.

The current Phase 3 artifact-encoding proof is
`docs/evidence/phase3_non_ascii_smoke_latest.json` for mission
`mission-bd5369ec-3777-4099-89fe-81699289a29d`, which preserved 28
non-ASCII characters through codegen, packaging, and storage readback.

The latest public README/status-doc refresh now also records the Phase 8 line
coverage improvement and production-audit closure: `INF-008` is resolved and
the audit passes 23/23 checks. The active development / not-production-ready
boundary remains in place.

The current security-alert remediation pass fixed CodeQL alerts #337-#338 in
Mission Control and RQCA HTML handling, refreshed Python service base-image
digests for Trivy OpenSSL alerts #330-#336, and verified the rebuilt
orchestrator image reports OpenSSL `3.0.20-1~deb12u2`.

The latest Mission Control UX lock-in adds PM clarification cards/defaults,
Live Progress status/next-action indicators, guarded local output-folder status
and open actions, VS Code launch, and follow-up mission context loading. The
running stack was not restarted during this lock-in pass; the post-restart
browser mission proof remains the next action.

---

## Active Work

### Mission Control UX Lock-In (implemented; restart/browser proof pending)

Implementation complete:

- PM feature-contract normalization now asks clarifying questions for
  underspecified interactive applications/games instead of immediately creating
  a launchable plan.
- Mission Control chat renders those questions as decision cards with
  recommended defaults, editable answers, and a proceed-with-defaults action.
- Mission Detail now has a Live Progress panel that distinguishes waiting,
  blocked, retrying, stale, working, and finished states with user-facing next
  actions.
- Generated Output and Build Artifacts panels show the local
  `output/<mission_id>` path, file status, Copy Path, Open Folder, and VS Code
  actions.
- Continue with PM loads prior mission summary, build artifacts, delivery
  summary, and output-folder status, then carries that context in follow-up
  mission metadata.
- generated-output artifact gating now blocks expected generated-output
  missions from completing without a durable generated output artifact.

Validation passed:

- Mission Control focused Vitest: 36/36.
- Mission Control `npm run build`.
- Mission Control `npm run lint`.
- Focused orchestrator PM/build-artifact pytest: 19/19.
- Compose full-dedicated service graph resolution.
- Docker rebuilds for `deploy-mission-control:latest` and
  `deploy-orchestrator:latest`.

Next action: after restart, run the Angular Snake browser mission and confirm
the four user-facing behaviors above in the real UI.

### Repository ZIP Import Migration (active implementation)

The current repo-intake migration is tracked in
`docs/REPO_ZIP_IMPORT_MIGRATION_PLAN.md`. The implementation has started in
Mission Control:

- Phase 1 is complete: `apps/mission-control/app/api/repo/archive.ts` provides
  safe ZIP indexing/read helpers and `archive.test.ts` covers root stripping,
  traversal rejection, subdirectory filtering, text reads, and binary detection.
- Phase 2 is complete locally: `apps/mission-control/app/api/repo/import/route.ts`
  accepts multipart ZIP uploads, validates source refs/subdirectories, indexes
  files without GitHub API calls, rejects oversized uploads, and returns ZIP
  metadata with archive truncation signals.
- Route tests now focus on ZIP intake: accepted archive, missing archive,
  non-ZIP rejection, invalid source ref, and operator-session enforcement.
- Phase 3 is complete locally: `apps/mission-control/app/api/repo/review/route.ts`
  accepts multipart ZIP review requests, requires `archive_sha256`, re-indexes
  the uploaded archive with required selected-path inclusion, reads selected file
  text from normalized ZIP paths in one pass, and returns the existing review
  artifact/source-bundle shape without GitHub API calls.
- Phase 4 is complete locally: `apps/mission-control/app/(shell)/repo/page.tsx`
  now renders a ZIP file selector, archive metadata summaries, FormData-backed
  import/review calls, and review-gate reset behavior for archive scope changes.
- Validation passed: Mission Control `npm run lint`, full `npm run test`
  (87/87), focused `npm run test -- app/api/repo` (22/22), and targeted
  Playwright repo-intake e2e.

Important boundary: repo ZIP launch still uses the approved source bundle only.
Mission index guard, repo knowledge ingestion, and PM/pod-worker repository
context loading remain the next migration phases.

### Verification & Reporting Hardening (Phase 1-3 complete; verification backlog remains)

A live "Modern Neon Pong" mission, created through the Mission Control chat
intake on 2026-06-29, reached `COMPLETE` and produced a working artifact, but
exposed three gaps that automated verification did not catch: the deliverable was
a `.js` file rather than the contracted single self-contained HTML file; non-ASCII
characters were corrupted (mojibake); and the run was mislabeled `LEGACY V1`
despite executing the Mission Flow v2 pipeline.

The full plan is `UPDATE_PLAN_VERIFICATION_HARDENING_2026-06-29.md`. Phase 1 is
complete: 1a (artifact-format gate), 1b (per-criterion acceptance evaluation),
1c (integrity vs correctness split — artifact `verification` tagged
`verification_scope="integrity"`, equivalence report tagged
`verification_scope="correctness"`, Mission Control `EquivalenceReportPanel`
copy updated), and the follow-up false-negative fixes for prohibited extension
mentions plus extensionless artifacts. Phase 2 code is also complete:
RQCAs now attach runnable-smoke evidence, JavaScript syntax failures become real
runtime-QC failures, HTML artifacts get static structure plus inline-script
syntax smoke with honest browser-load `DRY_RUN` reporting, and authoritative
`lifecycle_engine` is emitted through the backend/API/UI path. Phase 3 code is complete and live-validated: non-ASCII artifact regression coverage,
packaging-time mojibake guard/repair, codegen / packaging / storage-readback
diagnostic trace, lifted PM clarifying-question/context truncation, and a
passing live non-ASCII mission rerun recorded at
`docs/evidence/phase3_non_ascii_smoke_latest.json`. Focused backend tests,
docs validation, Mission Control tsc, standard live smoke, and live non-ASCII smoke pass.
Remaining outside Phase 3: Pong-style UI artifact rerun for the broader verification backlog.

### Protocol Bus Program (4 stages) — Stage 1 producers code-complete; live validation pending

The full bus program is documented in `PROTOCOL_BUS_PROGRAM_ROADMAP.md` as four
staged initiatives: Stage 1 PBLA (`PROTOCOL_BUS_LANE_ACTIVATION_PLAN.md`,
producers/telemetry, **PBLA-00..04 implemented and unit-tested; live six-lane
validation pending**), Stage 2 EDCP (`EDCP_PHASE_PLAN.md`,
consumers + control-flow inversion, reactivated from archive; EDCP-01 complete,
EDCP-02 pending), Stage 3 Agent Runtime Split (`AGENT_RUNTIME_SPLIT_PLAN.md`,
stub), and Stage 4 Semantic Bus (`SEMANTIC_BUS_PLAN.md`, stub). Stages must land
in order; PBLA only makes lanes observable, EDCP makes them load-bearing.

The PBLA plan is fully specified as phases PBLA-00 through PBLA-05 and has been
validated end-to-end against current source (insertion points, payload bounds,
agent-id validity, helper signatures, and in-scope imports all checked).
**All five PBLA code phases are implemented and unit-tested** — the four dark
lanes now have live producers: **PBLA-00** (shared emission-discriminator
contract, `protocol_bus_emissions.py`), **PBLA-01** (Delta in `phases_build.py`,
inside the `MISSION_POD_AUDIT_COMPLETE` guard), **PBLA-02** (Omega in
`phases_delivery.py`, after `delivery_summary`), **PBLA-03** (Beta in
`phases_runtime.py` `_prepare_fusion`, codegen success path, with
`logicnode_id`/`confidence_score` synthesized + clamped), and **PBLA-04** (Rho in
`llm_delegation/providers.py` `_post_with_retry` 429 branch, bus config via
`load_settings()`, sender `AGENT-03-BROKER`). Emission contract tests +
Delta/Omega/Beta/Rho helper tests pass; the full mission_flow_v2 and
llm_delegation suites pass (150+ combined); ruff clean.

**Live validation ran on 2026-06-30 — 20 missions through the real Mission
Control chat UI** (one per language specialist + one modernize/debug-repair
mission), each going through the PM Agent's actual clarification dialogue. Full
results, code review, and recommendations: `FIRST_FULL_SYSTEM_RUN_FINDINGS_2026-06-30.md`
(repo root); the full chronological session narrative is
`MISSION_TESTS_SESSION_LOG_2026-06-30.md` (repo root, read this one first if
picking up this work cold). Headline results:

- **20/20 missions reached `COMPLETE`.** Alpha, Sigma, Delta, Omega all fired
  correctly with zero DLQ writes. Rho confirmed via a direct producer smoke
  test (real rate-limit traffic wasn't hit organically).
- **Real bug found + fixed + unit-tested + committed (`4445b6b`):**
  `generate_pod_audit_verdict` lower-cased `pod_name` before matching
  mixed-case `_POD_AUDIT_AGENTS` keys, so every non-Pod-A mission's audit (and
  its PBLA-01 Delta emission) silently misrouted to `AGENT-13-PODA-AUDIT`.
  Fixed via a case-insensitive lookup; regression test covers all 4 pods.
- **Real bug found, fixed, and committed (`07883d7`): Beta (PBLA-03) never
  fired across all 20 missions.** Root cause confirmed — but the original
  diagnosis above named the wrong function. `generated_output` is actually set
  in `_prepare_specialist_plan` (`phases_build.py`), not
  `_prepare_specialist_assignment` — a different, later function in the same
  file, confirmed by tracing the actual `lifecycle.py` state-machine call
  order (`pod_assigned → _prepare_specialist_assignment → specialist_assigned
  → _prepare_specialist_plan`). The fix adds the Beta emission there. The
  original `_prepare_fusion` (`phases_runtime.py`) call was **not** removed —
  it remains the legitimate fallback-path emission for missions whose first
  codegen attempt didn't yield usable output; the shared
  `mission_has_generated_output` guard keeps the two call sites mutually
  exclusive by construction, so no new idempotency tracking was needed.
- **2 of 20 missions (C, R) generated the wrong language entirely** (both
  produced Python that simulates the target language instead of real C/R
  source) and still reached `COMPLETE`. **Fixed and committed (`a63dfaf`)** —
  but the original diagnosis above was also wrong: a required check
  (`_check_language_alignment`) already existed. The real gap is that it
  compares `generated_output["language"]` (self-reported by the same LLM call
  that wrote the code) against the requested language, so a specialist that
  silently substitutes Python can still label its output correctly and the
  check can never catch it. The new `_check_language_content_signature`
  inspects the actual code text for unambiguous Python tells, scoped to target
  languages least likely to be confused with Python (c, cpp, r, go, rust,
  shell) — verified against the real C/R battery artifacts on disk (correctly
  fails) and real Go/Rust/C++ artifacts (correctly passes, no false positive).
- **Also fixed and committed (`b70d711`), beyond the original findings scope:**
  `AGENT-08-COMPLIANCE`'s activation was a literal `"COMPLIANCE"` keyword
  substring match that essentially never fired for ordinary prompts (findings
  §6.3). Per the user's explicit choice among 3 presented options, Compliance
  now fires unconditionally at delivery like Security/VC/Tester, via a new
  `generate_compliance_assessment` function and `MISSION_COMPLIANCE_ASSESSMENT_COMPLETE`
  event.
- PBLA-05 (operations-snapshot lane surfacing) remains optional/undone.
- **All four fixes above passed the full `tests/services/` suite** (1311
  passed, 5 skipped, 0 failed) and ruff on every touched file, run after each
  commit.

**Environment note:** after the battery, `stop_app.bat` →
`scripts/force_stop.py` → `make down` ran `docker compose down -v`, which
deleted the `postgres-data`/`redis-data` volumes (mission/chain-trace DB gone;
generated code artifacts survived — `output/` is a host bind-mount, not a
volume). A live-restart cascade also surfaced a Postgres credential mismatch
and an `api-gateway` internal-auth key that resolves empty at runtime.
**Both now look resolved** after rebuilding all images (correct two-file
compose form) and bringing the stack up fresh: `db_ready: true` with no
`FATAL` auth errors (Finding 3), and a clean `404` instead of the old `503
gateway internal auth is not configured` when fetching build-artifacts for an
old mission ID (Finding 4 — strong evidence, not yet proven via a fresh live
mission). Full remediation plan: `docs/STACK_REMEDIATION_PLAN_2026-07-01.md`.
See "Findings Remediation (Phases 0-4)" below for the full current state.

#### Stage 1 — Protocol Bus Lane Activation (PBLA)

A standalone initiative, fully specified in
`PROTOCOL_BUS_LANE_ACTIVATION_PLAN.md` and tracked in `CURRENT_TODO.md`. The
Protocol Bus is fully built, but a repo-wide producer trace confirms only two of
six lanes have live callers in the mission pipeline: Alpha (`phases_build.py`)
and Sigma (`knowledge_lake.broadcast_knowledge_ready` from `phases_intake.py`).
PBLA adds the four missing producers — Delta, Omega, Beta, Rho — following the
proven Alpha/Sigma fire-and-forget pattern (private `_send_<lane>_<event>`
helper, local `send_*` import, `asyncio.to_thread` dispatch, swallow-and-log so
a bus outage never blocks a mission). No schema changes, no new infrastructure.
Independent of EDCP; recommended before it so all six lanes carry real traffic
when EDCP starts inverting control flow onto the bus. Start with PBLA-01 (Delta)
— lowest risk, insertion point confirmed.

---

## Latest Completed Work

### Post-Review Hardening (2026-07-02): stuck missions, auth gap, false-negative clarifying question

A code review of the five Mission Control UX lock-in commits (repo ZIP
hardening, language pod manager routing, Mission Control UX lock-in, browser
auto-open, CI import ordering) surfaced five findings. All five are fixed and
test-verified:

- **Critical — missions could get stuck at `verified` forever with no visible
  signal.** `mission_expects_generated_output_artifact()` (added by this same
  work to gate mission completion on a real generated-output artifact) could
  return `True` even when a mission had neither `generated_output` nor
  `source_code`. `_ensure_verified_build_artifact` then called
  `build_source_bundle_artifact`, which raises `ValueError` on empty
  `source_code`; that exception was caught in `mission_flow_v2/lifecycle.py`
  and only logged as a warning, leaving no build-artifact record at all. The
  completion gate (`_completion_artifacts_ready` in `runtime.py`) then
  permanently required `has_successful_build_artifact`, which could never
  become true. Fixed by adding `build_missing_source_artifact_failure()` in
  `services/orchestrator/orchestrator/build_artifacts.py`, which
  `_ensure_verified_build_artifact` (`mission_flow_v2/phases_build.py`) now
  calls instead of raising — this produces a `status="FAILED"` artifact record
  that flows through the existing `record_build_artifact_metadata` routing and
  emits a real `MISSION_BUILD_ARTIFACT_FAILED` chain-trace event, so the
  failure is diagnosable in the mission's chain trace and build-artifacts list
  instead of a silently swallowed exception. The pre-existing legacy
  `runtime.py._ensure_verified_build_artifact` has a similar unconditional call
  pattern but was not touched by the reviewed commits and was left out of
  scope.
- **Critical — PM acceptance-criteria clarifying question silently suppressed
  for the common case.** `acceptance_tokens` in
  `llm_delegation/text.py`'s `_pm_product_clarifying_questions` included the
  bare word `"build"`, matched via plain substring. Since almost every prompt
  on this code-generation platform starts with "Build a...", the "what counts
  as done for acceptance?" question was suppressed for the majority of real
  prompts — exactly the case it exists to catch. Fixed by converting all four
  token blocks (style/gameplay/packaging/acceptance) to the function's
  existing word-boundary-safe `has_token()` helper (already used for
  `is_game`/`is_interactive_app` but inconsistently applied elsewhere) and
  removing `"build"` from `acceptance_tokens` entirely, since it is a noise
  word on this platform, not a real acceptance-criteria signal.
- **Critical — three new local-filesystem/process routes had no session
  auth.** `apps/mission-control/app/api/local/{open-vscode,open-output-folder,
  output-folder-status}/route.ts` (new in this work, backing the Open
  Folder/VS Code actions) did not call `requireOperatorRequestSession`, unlike
  every other sensitive Mission Control route including the sibling
  `repo/import`/`repo/review` routes. Two of the three spawn host processes
  (`cmd.exe /c code "..."`, `explorer.exe`) from a client-supplied mission ID.
  Because Next.js's `request.json()` parses the raw body regardless of
  `Content-Type`, a cross-origin request using a CORS-safelisted type (e.g.
  `text/plain`) skips preflight and would still be parsed and acted on — the
  same vulnerability class behind several real Electron/dev-server CVEs. This
  could not be fixed by configuration alone: `OPERATOR_SESSION_BYPASS`
  defaults to `true` in compose, but even a hardened deployment with the
  bypass disabled had no way to protect these three routes, since the check
  was absent from the code path entirely. Fixed by adding
  `requireOperatorRequestSession` to all three routes, with new tests
  confirming the session gate runs before any process-spawn or filesystem
  call.
- **`DeliveryPanel` output-folder status could go stale.** Its refresh
  `useEffect` depended on `buildArtifacts.length`, which does not change when
  an existing artifact transitions status (e.g. packaging → complete — the
  exact moment the output folder is written to disk). Fixed to also depend on
  the latest `updated_at` across build artifacts, matching the pattern already
  used correctly in `GeneratedOutputPanel`.
- **`resetImportResults()` wiped import/review progress on unrelated field
  edits.** The repo-ZIP-import page's display-name, source-ref, subdirectory,
  and max-files inputs each called `resetImportResults()` on every keystroke,
  discarding an already-imported file list, mission type, and description with
  no confirmation — even though those fields are only import *parameters*
  that take effect on the next explicit "Import ZIP" click (which already
  resets state itself). Removed the reset call from those four handlers; the
  archive-file input still resets on change, since a new archive genuinely
  invalidates the prior import.

Validation: full backend suite `python -m pytest tests/services/
--ignore=tests/services/test_agent_base_unit.py` — 1319 passed, 5 skipped, 0
failed. Full Mission Control suite `npm run test` — 99 passed. `ruff check` and
`tsc --noEmit` clean on every touched file. New regression tests added for
each of the five findings.

**Follow-up pass (same day):** the initial review left several small files in
the 5 reviewed commits unexamined. A closing pass covered all of them
(`globals.css`, `language.ts`/`language.test.ts`, `navigation.ts`,
`smelt-cycle.ts`/`smelt-cycle.test.ts`, `types.ts`, the full
`e2e/mission-control.spec.ts` diff, `scripts/phase13_smoke.py` +
`test_phase13_smoke.py`, `start_app.bat`, `test_runtime_unit.py`) plus an
independent re-verification of the fix commit itself:

- **Fixed:** `apps/mission-control/app/lib/language.ts`'s
  `inferRequestedTargetLanguage` could tie `"batch"` (a Windows launcher
  script mention, e.g. `start.bat`) against the mission's real implementation
  language — for the Angular-Snake-game-with-`start.bat` scenario both scored
  5-5 at the actual mission-launch call site, resolved to `"typescript"` only
  by the accidental ordering of `PROMPT_HINTS` in the source array, not by
  design. `"batch"` has zero backend specialist support (confirmed: no pod
  recognizes it), so a reordering or slightly different prompt phrasing could
  have silently produced `requested_target_language: "batch"` and routed a
  mission to a nonexistent specialist. Fixed by excluding `"batch"` from ever
  winning the overall pick — it is packaging metadata, never a real target
  language. 2 new regression tests.
- **Verified clean, no changes needed:** `smelt-cycle.ts`'s
  `Number.isInteger(mapped)` check (already a correct fix for a `NaN`-
  poisoning bug from `Record<string, number>` returning `undefined` for
  missing keys, which `!== null` used to miss); `types.ts`'s new/updated
  response types (verified field-by-field against the actual backend route
  shapes); the rest of the e2e spec diff (already covered by the earlier
  finder agent — the repo-review mock's hardcoded `selected_files`); the
  `phase13_smoke.py` routing-mismatch check (`expected_pod_manager_agent_id`/
  `expected_specialist_agent_id` are real, populated metadata fields, not dead
  code); `start_app.bat`'s bounded browser-auto-open wait loop; `globals.css`
  (purely additive, no selector collisions); `test_runtime_unit.py`'s new
  completion-gate test (exercises the gate's own intentional strictness, no
  conflict with the build-artifact fix).
- An independent verifier agent, given the fix commit cold with no prior
  review context, re-checked all five original findings' fixes plus the
  `shared.ts` deletion end-to-end and confirmed every one correct and
  complete with no new defects introduced.

Also removed in this pass: ~200 lines of dead GitHub-API intake code
(`GithubApiError`, `parseGithubRepoUrl`, `resolveGithubToken`,
`fetchGithubFileText`, etc.) from `apps/mission-control/app/api/repo/shared.ts`
— confirmed zero callers anywhere in the app before deletion, left over from
the repo ZIP import migration's Phase 4 UI cutover.

### Findings Remediation (Phases 0-4): pod-audit, Beta, language check, Compliance, stack rebuild

A phased plan was written (validated against the actual code first — two
corrections found, see below), then executed as four separate commits plus a
live-stack rebuild:

- **Phase 0 (`4445b6b`, `aafe416`):** committed the already-fixed pod-audit
  bug and all of the prior session's findings/remediation docs. Added an
  explicit "always use both compose files together" warning to the top of
  `docs/OPERATIONS_RUNBOOK.md`, since a single-file `docker compose` command
  was the root cause of the whole prior-session restart cascade.
- **Phase 1 (`07883d7`):** Beta (PBLA-03) now fires on every normal
  `BUILD_NEW` mission — added to `_prepare_specialist_plan`
  (`phases_build.py`), not `_prepare_specialist_assignment` as the original
  findings report said (a real doc error, corrected here). The `_prepare_fusion`
  call in `phases_runtime.py` is untouched — it is the fallback-path emission
  for missions whose first codegen attempt didn't produce usable output, kept
  mutually exclusive from the new call site by the existing
  `mission_has_generated_output` guard.
- **Phase 2 (`a63dfaf`):** new `_check_language_content_signature` check in
  `equivalence_verifier.py`. The original findings report's claim that "no
  gate exists" for generated-language-vs-requested-language mismatches was
  wrong — `_check_language_alignment` already existed, but it structurally
  cannot catch self-report drift (both sides of its comparison trace back to
  the same LLM call). The new check inspects the actual generated code text
  for unambiguous Python syntax tells, deliberately scoped to only the target
  languages least likely to be confused with Python (c, cpp, r, go, rust,
  shell) rather than all 19 supported languages, to avoid false positives on
  languages with real syntactic overlap. Verified directly against the real C
  mission artifact (`output/mission-508b752b.../generator_harness.py`) and R
  mission artifact (`output/mission-91ac234b.../vectorized_math.py`) from the
  2026-06-30 battery — both correctly flagged as Python-fallback substitutions
  — plus real Go/Rust/C++ artifacts from the same battery, confirming no false
  positive. `mission_equivalence_enforcement_enabled` still defaults to
  `False`, so this surfaces as a `review_required` finding today, not a
  blocker; enabling enforcement is left as a separate decision (Next Actions).
- **Phase 3 (`b70d711`):** `AGENT-08-COMPLIANCE` now fires unconditionally at
  delivery, matching Security/VC/Tester — the user's explicit choice among
  three presented options (unconditional / broadened keyword trigger /
  leave-as-is). Adds `generate_compliance_assessment` (new LLM-delegation
  function, deliberately distinct from Security's vulnerability/threat
  analysis and from `security_compliance.py`'s deterministic PII/license
  scan — assesses data-handling, third-party licensing, and audit-trail
  considerations instead) plus a `MISSION_COMPLIANCE_ASSESSMENT_COMPLETE`
  event and a deterministic fallback matching Security's
  `status="degraded"`/`passed=False` honesty convention.
- **Offline verification after every phase:** full `tests/services/` suite —
  1311 passed, 5 skipped, 0 failed (`test_agent_base_unit.py`'s collection
  error is pre-existing, untouched by this work, unrelated import-path issue).
  Ruff clean on every touched file.
- **Phase 4 (live stack, in progress — not fully closed):** rebuilt every
  buildable image (orchestrator, api-gateway, all 41 dedicated agents,
  mission-control, dashboard, protocol-bus-mcp, workers) via
  `docker compose --env-file .env -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents build`
  so Phases 0-3's code is actually in the running containers. Brought the
  stack up. Mid-session, the user separately ran `start_app.bat`, which
  recreated a subset of containers (non-destructively — `deploy_postgres-data`
  and `deploy_redis-data` volumes confirmed intact before and after) and
  additionally brought up `minio`/`neo4j` (stack-plan Finding 5's port
  conflict did not recur this run, though that isn't guaranteed permanently).
  **Confirmed live:** 59/59 `deploy-*` containers healthy or Up (0 unhealthy,
  0 stuck); orchestrator `/readyz` reports `ready: true` across every
  dependency (Redis, Postgres, Qdrant, Milvus, Neo4j, object storage,
  protocol bus); api-gateway ready. Stack-plan **Finding 3 (Postgres
  credential mismatch): resolved** (`db_ready: true`, no `FATAL` auth errors —
  matches the plan's prediction that a fresh `initdb` against the
  already-wiped volume would self-resolve it). **Finding 4
  (`INTERNAL_SERVICE_API_KEY` empty at runtime): very likely resolved**
  (`docker compose config` confirms a real key resolves at all three call
  sites; a build-artifacts fetch for an old mission ID returned a clean `404
  resource not found` instead of the old `503 gateway internal auth is not
  configured`) but **not yet proven against a fresh live mission**.
  **NOT DONE:** submitting an actual live mission through the real Mission
  Control chat UI to prove the pod-audit fix, Beta emission, the new language
  check, and `MISSION_DEPLOY_READINESS_ASSESSED` (findings §6.4) all work
  end-to-end on the rebuilt stack. Blocked on selecting between two connected
  Chrome browser extensions; session ended (credit limit) before this was
  resolved. **This is the top-priority next action** — see Next Actions #1.

### Cold-start healthcheck fix (dependent chain wedged in "Created")

Root cause: the orchestrator `/health` endpoint — used as the Docker liveness
probe and gated on by the whole `depends_on` chain (api-gateway →
mission-control → dashboard → agents → workers) — performed serial live
readiness probes to the optional backends (Qdrant/Milvus/Neo4j/object storage)
plus DB queries on every call. Under cold-start contention that exceeded the
healthcheck's `urlopen` timeout, marking the orchestrator unhealthy and leaving
every dependent stuck in `Created`, so `docker compose up` failed "at the end"
(when the frontend was about to come up). api-gateway compounded it by probing
the slow orchestrator `/health` in its own `_dependency_status`.

Fix (no `/health` or `/readyz` payload change — both keep their full bodies):
- Added orchestrator `/livez` — instant 200, no blocking probes — and pointed
  the orchestrator Docker healthcheck at it (timeout 6s→10s, start_period
  60s→90s, urlopen 4s→8s).
- api-gateway `_dependency_status` now probes orchestrator `/livez` not `/health`.
- Modest cold-start headroom: api-gateway and mission-control `start_period`
  30s→45s; mission-control healthcheck timeout 3s→5s.
- `tests/services/test_health.py` adds a `/livez` lightweight-contract test
  (asserts no optional-backend keys). 72 tests pass across the touched areas;
  `docker compose config` validates; ruff clean.

**Confirmed on a live restart (this session):** after rebuilding orchestrator +
api-gateway, the full dedicated-agent stack came up clean — orchestrator healthy
in ~39s (its `/livez` responds in ~20ms), and every dependent including
mission-control (which previously failed) reached `healthy`; fleet showed 0
unhealthy, 0 stuck-`Created`, 0 exited. Rebuild note: the fix changed
orchestrator + api-gateway **code** (rebuild those images); the compose
healthcheck/timing changes apply on the next `up`.

### Security Alert Remediation

- Replaced regex-based RQCA HTML artifact smoke parsing with `HTMLParser`.
- Restricted Mission Control attachment previews to raster images and sanitized
  filenames before UI display, source-bundle labels, and metadata use.
- Updated Python service Dockerfile base-image digests across orchestrator,
  gateway, workers, dashboard, protocol-bus, and agent-runtime.
- Rebuilt the orchestrator image and verified the fixed OpenSSL package version
  from inside the container.

### Phase 8 Coverage and INF-008

- Added targeted Mission Flow v2 tests for strict-mode phase helpers, runtime
  QC/DEPABS/fusion paths, lifecycle completion gates, and build/intake branch
  handling.
- Fixed the Mission Flow v2 fusion Neo4j depth-sort import.
- Current coverage evidence: isolated Mission Flow v2 suite 81 passed with
  91.56% line / 71.69% branch; broader related suite 170 passed with 92.43%
  line / 74.70% branch. Branch coverage remains the only Phase 8 strict
  carry-forward.
- Closed `INF-008`; production audit now passes 23/23 checks with compose
  service-key hardening and operations/observability evidence correlation.

### Phase 13 Backend/API Smoke

- Added `scripts/phase13_smoke.py`.
- Added `make phase13-smoke`.
- Added regression tests in `tests/scripts/test_phase13_smoke.py`.
- Fixed orchestrator `MissionEvent` literals for
  `MISSION_RUNTIME_QC_SKIPPED` and `MISSION_RUNTIME_QC_BLOCKED`.
- Rebuilt/restarted orchestrator during validation.
- Verified the original failed mission's `/events` and `/chain-trace`
  endpoints returned 200 after the fix.
- Rebuilt the full dedicated-agent Docker stack and ran a fresh smoke mission
  that passed end to end.

### Documentation Current-State Cleanup

- Added `docs/README.md`.
- Updated root `README.md` and `docs/DOCUMENTATION_INDEX.md`.
- Refreshed the public README current-state language in commit `3439124` (`refresh-public-readme-status`).
- Replaced stale current-state TODO/handoff/status content with concise current
  snapshots.

---

## Validation Snapshot

Findings-remediation validation (Phases 0-3, this pass):

- `python -m pytest -o addopts= --basetemp .pytest-tmp tests/services/ --ignore=tests/services/test_agent_base_unit.py`
  passed 1311, skipped 5, failed 0 (run after Phase 3; the ignored file has a
  pre-existing, unrelated import-path collection error).
- `python -m ruff check` clean on every file touched across all three phases
  (`generators_artifacts.py`, `fallbacks.py`, `llm_delegation/__init__.py`,
  `phases_build.py`, `phases_delivery.py`, `equivalence_verifier.py`,
  `models.py`, and their test files).
- `docker compose --env-file .env -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents build`
  — exit 0, all ~48 buildable services built successfully.
- `docker compose ... up -d --scale minio=0 --scale neo4j=0` (later
  superseded by the user's own `start_app.bat` run, which brought
  `minio`/`neo4j` up too) — exit 0.
- Live fleet check: 59/59 `deploy-*` containers healthy or Up, 0 unhealthy, 0
  stuck.
- `curl http://127.0.0.1:8101/readyz` → `ready: true`, all dependencies
  healthy including `db_ready`, `neo4j_ready`, `object_storage_ready`.
- `curl http://127.0.0.1:8100/readyz` → `ready: true`.

Passing checks from the prior work:

- `python -m pytest -o addopts= --basetemp .pytest-tmp tests/services/test_equivalence_verifier_unit.py tests/services/test_runtime_qc_unit.py tests/services/test_lifecycle_interface_unit.py tests/services/test_storage_missions_unit.py tests/services/test_api_gateway_helpers_unit.py tests/services/test_orchestrator_endpoints_extra.py`
  passed with 88 tests.
- `python -m pytest -o addopts= --basetemp .pytest-tmp tests/services/test_build_artifacts_unit.py tests/services/test_storage_unit.py tests/services/test_llm_delegation_unit.py`
  passed with 98 tests.

- Full dedicated-agent Docker rebuild completed successfully.
- API gateway `/readyz` returned ready with orchestrator and Redis healthy.
- Orchestrator `/readyz` returned ready with Redis, Postgres, Qdrant, Milvus,
  Neo4j, object storage, and protocol-bus dependencies healthy.
- Mission Control returned the production shell at `http://127.0.0.1:3100`.
- `python scripts\phase13_smoke.py --gateway-base-url http://127.0.0.1:8100 --orchestrator-base-url http://127.0.0.1:8101 --timeout-seconds 240 --poll-seconds 5 --output-file docs\evidence\phase13_smoke_latest.json`
- `C:\Users\kevin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe scripts\validate_documentation.py`
- `git diff --check`

Phase 13 validation also completed in the prior slice:

- `python scripts\phase13_smoke.py --timeout-seconds 240 --poll-seconds 5 --output-file docs\evidence\phase13_smoke_latest.json`
- focused Phase 13 pytest and Ruff checks
- `scripts/export_openapi.py --check`

Production audit status is now 23/23; `INF-008` is closed.

Latest Phase 8 / INF-008 validation:

- `python -m pytest -o addopts= --basetemp .pytest-tmp-phase8 tests/services/test_mission_flow_v2.py --cov=services/orchestrator/orchestrator/mission_flow_v2 --cov-report=term-missing --cov-report=xml:coverage-phase8.xml` passed with 81 tests and 91.56% line / 71.69% branch coverage.
- `python -m pytest -o addopts= --basetemp .pytest-tmp-phase8-combined tests/services/test_mission_flow_v2.py tests/services/test_lifecycle_interface_unit.py tests/services/test_runtime_unit.py tests/services/test_orchestrator_endpoints_extra.py tests/services/test_storage_missions_unit.py --cov=services/orchestrator/orchestrator/mission_flow_v2 --cov-report=term-missing --cov-report=xml:coverage-phase8-combined.xml` passed with 170 tests and 92.43% line / 74.70% branch coverage.
- `python scripts/production_review_audit.py --json` passed 23/23 checks.

Security alert remediation validation:

- `python -m ruff check services\orchestrator\orchestrator\rqca_agent.py tests\services\test_runtime_qc_unit.py`
- `python -m pytest -o addopts= tests/services/test_runtime_qc_unit.py --basetemp .pytest-tmp` passed with 14 tests.
- Mission Control `npm run lint` passed.
- `docker build --pull -f services\orchestrator\Dockerfile -t thefactory-orchestrator:security-refresh .` passed.
- In-image `dpkg-query` reported OpenSSL `3.0.20-1~deb12u2`.
- Local Trivy CLI was not installed, so a local Trivy rescan was not run.

---

## Next Actions

1. **Post-restart Mission Control UX proof.** Restart the app, then submit a
   real browser mission through Mission Control asking for a modern Angular
   Snake game with a `start.bat` file. Confirm: (a) PM clarification cards
   appear or defaults can be accepted; (b) Live Progress shows ongoing work
   instead of looking hung; (c) Generated Output / Build Artifacts expose the
   real output-folder path and local open actions; (d) Continue with PM
   preloads prior mission context for follow-up work.
2. **Active repo ZIP migration next step.** Add the mission launch index guard,
   repo knowledge ingestion, and PM/pod-worker repository context loading so
   ZIP-imported repositories become internal database context rather than only
   approved source bundles.
3. **Existing live-stack top priority.** Submit one live mission through the
   real Mission Control chat UI (`http://127.0.0.1:3100/chat`, not the raw
   API — the stack is already up, rebuilt, and healthy). Pick a Pod B/C/D
   language that is also Python-dissimilar (Go, Rust, or C are all in scope
   for the new content-signature check) so one mission proves everything at
   once: (a) `pod_audit_verdicts.<pod>.agent_id` matches the pod's own audit
   agent, not `AGENT-13-PODA-AUDIT`; (b) the Beta lane fires — check
   `protocol:beta:*` on `protocol-bus-mcp` (port 8102) metrics/DLQ; (c)
   `MISSION_DEPLOY_READINESS_ASSESSED` appears in the chain trace (findings
   §6.4); (d) the mission's `equivalence_report.checks` includes
   `language_content_signature` with a sensible result; (e) fetch that
   mission's build-artifacts through `api-gateway` (`/v1/missions/<id>/build-artifacts`)
   to conclusively close stack-plan Finding 4 (a fresh mission, not an old
   pre-wipe ID). Two Chrome browser extensions are currently connected — pick
   one explicitly (via `list_connected_browsers`/`select_browser`) before
   driving the UI.
4. Decide whether to also flip `mission_equivalence_enforcement_enabled`
   (still `False`) now that the new language-content-signature check exists —
   this is a broader decision than Phase 2 scoped, since it would also start
   blocking on the pre-existing `artifact_format_matches_contract` and
   `language_alignment` checks, not just the new one.
5. Rerun a Pong-style UI artifact mission through the current PlanBuild path.
6. Run Mission Control UI smoke for Phase 13.
7. Run protocol-bus failure injection for Phase 13.
8. Run provider fallback proof for Phase 13.
9. Run full `make validate` and capture the current result.
10. Raise remaining Phase 8 `mission_flow_v2/` branch coverage or explicitly defer the old 85% branch target.
11. Add provider/key/model preflight in Settings.
12. Move provider/model selection into the app settings/vault path.
13. Rotate exposed provider keys before public or shared use.
14. ~~Fix pod-audit, Beta, generated-language verification, Compliance
    trigger~~ — **done**: commits `4445b6b`, `07883d7`, `a63dfaf`, `b70d711`.
    Live re-confirmation is Next Action #3 above.

---

## Operational Notes

- The default runtime path is Mission Flow v2.
- LangGraph remains optional and disabled by default.
- The current backend/API smoke proves the API path, not the full UI path.
- Archive docs are historical only.
- The local `.pytest-tmp/` warning can appear in `git status`; it is local
  generated output and should not be committed.
