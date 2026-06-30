# Current Handoff

Document version: 2026.06.29-a
Last updated: 2026-06-29
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

Use this file with `docs/CURRENT_TODO.md` and
`docs/IMPLEMENTATION_STATUS.md`. Historical phase notes are archived and should
not override these current files.

---

## Current Application State

theFactory is an active local-first AI software factory application. It is not a
production-ready release.

The current validated runtime proof is the final full-dedicated Docker rebuild
on 2026-06-27 followed by Phase 13 smoke mission
`mission-b95ea912-94f8-4be8-8f7e-3cdce61cb7a7`, which reached `COMPLETE`,
returned mission events and chain trace, produced one build artifact, and passed
Python syntax validation for that artifact.

The most recent docs cleanup added `docs/README.md` as the GitHub docs landing
page and updated README/index status language to match the Phase 13 proof and
remaining gaps.

---

## Active Work

### Verification & Reporting Hardening (branch `verification-correctness-hardening`)

A live "Modern Neon Pong" mission, created through the Mission Control chat
intake on 2026-06-29, reached `COMPLETE` and produced a working artifact, but
exposed three gaps that automated verification did not catch: the deliverable was
a `.js` file rather than the contracted single self-contained HTML file; non-ASCII
characters were corrupted (mojibake); and the run was mislabeled `LEGACY V1`
despite executing the Mission Flow v2 pipeline.

The full plan is `UPDATE_PLAN_VERIFICATION_HARDENING_2026-06-29.md`. Phase 1
(verification correctness: artifact-format gate, real acceptance-criteria
evaluation, integrity-vs-correctness split in `equivalence_verifier.py`) is in
progress. Phases 2 and 3 follow.

---

## Latest Completed Work

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
- Replaced stale current-state TODO/handoff/status content with concise current
  snapshots.

---

## Validation Snapshot

Passing checks from the latest work:

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

Production audit status remains 22/23 because `INF-008` is still open.

---

## Next Actions

1. Complete Verification & Reporting Hardening Phase 1 (artifact-format gate,
   acceptance-criteria evaluation, integrity-vs-correctness split), then Phases 2
   and 3. See `UPDATE_PLAN_VERIFICATION_HARDENING_2026-06-29.md`.
2. Run Mission Control UI smoke for Phase 13.
2. Run protocol-bus failure injection for Phase 13.
3. Run provider fallback proof for Phase 13.
4. Run full `make validate` and capture the current result.
5. Fix or explicitly defer the Phase 8 `mission_flow_v2/` strict coverage gap.
6. Resolve `INF-008`.
7. Add provider/key/model preflight in Settings.
8. Move provider/model selection into the app settings/vault path.
9. Rotate exposed provider keys before public or shared use.

---

## Operational Notes

- The default runtime path is Mission Flow v2.
- LangGraph remains optional and disabled by default.
- The current backend/API smoke proves the API path, not the full UI path.
- Archive docs are historical only.
- The local `.pytest-tmp/` warning can appear in `git status`; it is local
  generated output and should not be committed.
