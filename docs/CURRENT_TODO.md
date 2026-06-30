# Current TODO

Document version: 2026.06.29-c
Last updated: 2026-06-29
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

This is the active TODO list for theFactory. Superseded sprint plans, historical
backlogs, and old phase notes live under `docs/archive/` and should not be used
as current work.

---

## Current Status

Phase 13 backend/API smoke is complete for this pass. After the final
full-dedicated Docker rebuild on 2026-06-27, gateway, orchestrator, and Mission
Control readiness checks passed. The latest committed smoke evidence is
`docs/evidence/phase13_smoke_latest.json` for mission
`mission-b95ea912-94f8-4be8-8f7e-3cdce61cb7a7`.

Validated in that smoke:

- gateway and orchestrator readiness
- mission creation through the API gateway
- authenticated mission polling to `COMPLETE`
- mission events and chain trace
- build-artifact listing and artifact detail retrieval
- Python syntax validation for the generated artifact

The app is still active development, not production-ready. The backend/API happy
path is now proven, but the broader release gate still needs UI, failure-mode,
provider-fallback, and full validation coverage.

---

## Active Work Queue

### Verification & Reporting Hardening (in progress, branch `verification-correctness-hardening`)

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
0b. **Phase 2** — DONE in branch: runnable-artifact smoke evidence now rides the
    existing RQCA path, JavaScript syntax failures short-circuit as real runtime
    QC failures, HTML artifacts get static structure plus inline-script syntax
    smoke with honest browser-load `DRY_RUN` reporting, and an authoritative
    `lifecycle_engine` field is emitted through orchestrator, gateway,
    chain-trace, and Mission Control.
0c. **Phase 3** — DONE in branch for encoding steps 1-3: non-ASCII artifact
    regression coverage, packaging-time mojibake guard/repair, and codegen /
    packaging / storage-readback diagnostic trace. Remaining: lift the PM
    clarifying-question truncation in chat intake and run a live non-ASCII
    mission rerun.

1. Run Phase 13 Mission Control UI smoke for the same mission path covered by the
   backend/API smoke.
2. Run Phase 13 failure-injection proof: interrupt protocol-bus MCP mid-mission
   and verify retry/resume or clean user-visible failure.
3. Run Phase 13 provider-fallback proof with an invalid primary provider key and
   confirm fallback is recorded in mission output/evidence.
4. Run full `make validate` in the current environment and capture the result.
5. Fix or explicitly defer the Phase 8 `mission_flow_v2/` strict coverage
   carry-forward. Current tracked gap: 83.51% line / 66.27% branch against the
   stricter 90% / 85% target.
6. Resolve production-audit finding `INF-008`: compose/internal-caller
   `INTERNAL_SERVICE_API_KEY` wiring.
7. Add Settings provider/key/model preflight that performs a real small provider
   call and reports the actual provider status.
8. Move provider/model selection fully into the Mission Control settings/vault
   path instead of relying on `.env` defaults.
9. Rotate exposed provider keys before any public, partner, or shared deployment.

---

## Recently Completed

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
- Current validation reports 78 metadata-checked docs and 120 link-checked docs
  after adding `docs/README.md`.

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
| Artifact correctness | Phase 1+2 branch code now enforces explicit format mismatch/missing extension and records runnable-smoke evidence; live Pong rerun still needed |
| Artifact encoding | Phase 3 branch code adds non-ASCII regression coverage, conservative mojibake repair before digest, and diagnostic trace; live non-ASCII rerun still needed |
| Engine reporting | Phase 2 branch code emits authoritative `lifecycle_engine`; live Mission Detail rerun still needed |
| Production audit | 22/23 checks pass; `INF-008` remains open |
| Phase 8 coverage | `mission_flow_v2/` strict target remains open |
| Phase 13 UI | Backend/API smoke passed; Mission Control UI smoke still needed |
| Failure injection | Not yet refreshed for Phase 13 |
| Provider fallback | Not yet refreshed for Phase 13 |
| Full validation | Focused validation passed; full `make validate` still needs current run |
| Provider settings | Provider/model still partly environment-driven |
| Key hygiene | Exposed provider keys must be rotated before wider use |

---

## Known Non-Issues

- `.pytest-tmp/` may remain as an untracked local temp directory from prior test
  runs. It is not part of the repository.
- OTel/Jaeger export warnings during tests are expected when Jaeger is not
  running locally and do not by themselves fail tests.
- Files under `docs/archive/` are historical and should not drive active work
  unless reconciled into this file.
