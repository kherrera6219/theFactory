# CURRENT_TODO.md Older History (archived 2026-07-03)

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Historical
Audience: Maintainers and auditors

This file holds the older "Recently Completed" entries pruned out of
`docs/CURRENT_TODO.md` during the 2026-07-03 documentation
inventory/reduction pass, so that the live TODO document stays focused on
the active queue plus recent history instead of growing without bound.
These entries are historical narrative only — see `docs/CURRENT_TODO.md`
and `docs/IMPLEMENTATION_STATUS.md` for current state.

---

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
