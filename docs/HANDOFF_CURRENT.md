# Current Handoff

Document version: 2026.06.30
Last updated: 2026-06-30
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

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

---

## Active Work

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

### Protocol Bus Program (4 stages) — Stage 1 in progress (PBLA-00 starting)

The full bus program is documented in `PROTOCOL_BUS_PROGRAM_ROADMAP.md` as four
staged initiatives: Stage 1 PBLA (`PROTOCOL_BUS_LANE_ACTIVATION_PLAN.md`,
producers/telemetry, **plan validated against code; PBLA-00 implementation
starting**), Stage 2 EDCP (`EDCP_PHASE_PLAN.md`,
consumers + control-flow inversion, reactivated from archive; EDCP-01 complete,
EDCP-02 pending), Stage 3 Agent Runtime Split (`AGENT_RUNTIME_SPLIT_PLAN.md`,
stub), and Stage 4 Semantic Bus (`SEMANTIC_BUS_PLAN.md`, stub). Stages must land
in order; PBLA only makes lanes observable, EDCP makes them load-bearing.

The PBLA plan is fully specified as phases PBLA-00 through PBLA-05 and has been
validated end-to-end against current source (insertion points, payload bounds,
agent-id validity, helper signatures, and in-scope imports all checked).
**PBLA-00** (shared emission-discriminator contract,
`orchestrator/protocol_bus_emissions.py`) and **PBLA-01** (Delta audit-verdict
emission in `phases_build.py`, inside the `MISSION_POD_AUDIT_COMPLETE` guard) are
**implemented and unit-tested** — emission contract tests, Delta helper/mapping
tests, and the full mission_flow_v2 suite pass; ruff clean. Remaining for PBLA-01:
live six-lane mission validation (needs a running stack). PBLA-02 (Omega) is next.

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

Passing checks from the latest work:

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

1. Rerun a Pong-style UI artifact mission through the current PlanBuild path.
2. Run Mission Control UI smoke for Phase 13.
3. Run protocol-bus failure injection for Phase 13.
4. Run provider fallback proof for Phase 13.
5. Run full `make validate` and capture the current result.
6. Raise remaining Phase 8 `mission_flow_v2/` branch coverage or explicitly defer the old 85% branch target.
7. Add provider/key/model preflight in Settings.
8. Move provider/model selection into the app settings/vault path.
9. Rotate exposed provider keys before public or shared use.
10. Begin Protocol Bus Lane Activation (PBLA) starting with PBLA-01 (Delta) per
    `PROTOCOL_BUS_LANE_ACTIVATION_PLAN.md`.

---

## Operational Notes

- The default runtime path is Mission Flow v2.
- LangGraph remains optional and disabled by default.
- The current backend/API smoke proves the API path, not the full UI path.
- Archive docs are historical only.
- The local `.pytest-tmp/` warning can appear in `git status`; it is local
  generated output and should not be committed.
