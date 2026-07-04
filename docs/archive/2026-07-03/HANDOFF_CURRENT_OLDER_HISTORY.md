# HANDOFF_CURRENT.md Older History (archived 2026-07-03)

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Historical
Audience: Maintainers and auditors

This file holds the older "Latest Completed Work" entries pruned out of
`docs/HANDOFF_CURRENT.md` during the 2026-07-03 documentation
inventory/reduction pass, so that the live handoff document stays focused on
current status plus recent history instead of growing without bound. These
entries are historical narrative only — they are not the current source of
truth for anything they describe; see `docs/HANDOFF_CURRENT.md` and
`docs/IMPLEMENTATION_STATUS.md` for current state.

---

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

