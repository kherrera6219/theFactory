# Current TODO

Document version: 2026.06.27-b
Last updated: 2026-06-27
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

This is the active TODO list for theFactory. Superseded sprint plans, historical
backlogs, and old phase notes live under `docs/archive/` and should not be used
as current work.

---

## Current Status

Phase 13 backend/API smoke is complete for this pass. The latest committed smoke
evidence is `docs/evidence/phase13_smoke_latest.json` for mission
`mission-e86c99b9-6cc0-4f31-967b-4e192b964a37`.

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
