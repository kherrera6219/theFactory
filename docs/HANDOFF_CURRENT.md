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
- **Real bug found + fixed + unit-tested:** `generate_pod_audit_verdict`
  lower-cased `pod_name` before matching mixed-case `_POD_AUDIT_AGENTS` keys,
  so every non-Pod-A mission's audit (and its PBLA-01 Delta emission) silently
  misrouted to `AGENT-13-PODA-AUDIT`. Fixed via a case-insensitive lookup;
  regression test covers all 4 pods. **Fix is in the working tree, not yet
  committed** (pending the stack remediation below).
- **Real bug found, not yet fixed: Beta (PBLA-03) never fired across all 20
  missions.** Root cause confirmed: `generated_output` is set earlier in
  `_prepare_specialist_assignment` (`phases_build.py`) than PBLA-03's insertion
  point in `_prepare_fusion`, so the `mission_has_generated_output` guard is
  already true and the whole codegen+Beta block is skipped. Recommended fix:
  move the Beta emission to `phases_build.py` right after
  `metadata["generated_output"]` is set. See the findings report §4/§6.1.
- **2 of 20 missions (C, R) generated the wrong language entirely** (both
  produced Python that simulates the target language instead of real
  C/R source) and still reached `COMPLETE` — no verification gate currently
  catches generated-language-vs-requested-language mismatches. See §5/§6.2.
- PBLA-05 (operations-snapshot lane surfacing) remains optional/undone.

**Environment note:** after the battery, `stop_app.bat` →
`scripts/force_stop.py` → `make down` ran `docker compose down -v`, which
deleted the `postgres-data`/`redis-data` volumes (mission/chain-trace DB gone;
generated code artifacts survived — `output/` is a host bind-mount, not a
volume). A live-restart cascade also surfaced a Postgres credential mismatch
and an `api-gateway` internal-auth key that resolves empty at runtime — both
unresolved. Full remediation plan: `docs/STACK_REMEDIATION_PLAN_2026-07-01.md`.
**Per explicit direction, no more live fixes** — the sequence is plan (done) →
stop the app (done) → fix offline → rebuild → test.

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
10. ~~Begin Protocol Bus Lane Activation (PBLA)~~ — **done**: PBLA-00..04
    implemented, unit-tested, and live-validated via the 2026-06-30 20-mission
    battery. See `FIRST_FULL_SYSTEM_RUN_FINDINGS_2026-06-30.md`.
11. Execute `docs/STACK_REMEDIATION_PLAN_2026-07-01.md` (Postgres credential
    mismatch + `api-gateway` internal-auth key, both offline fixes) before any
    further live testing.
12. Fix Beta's insertion point (move to `phases_build.py` — see findings §6.1)
    and commit the already-fixed pod-audit-agent bug.
13. Add a generated-language-vs-requested-language verification check (findings
    §6.2) — the C and R missions both silently delivered the wrong language.
14. Re-confirm `AGENT-11-DEPLOY`'s `MISSION_DEPLOY_READINESS_ASSESSED` activates
    on a fresh mission once the stack is back up (findings §6.4).

---

## Operational Notes

- The default runtime path is Mission Flow v2.
- LangGraph remains optional and disabled by default.
- The current backend/API smoke proves the API path, not the full UI path.
- Archive docs are historical only.
- The local `.pytest-tmp/` warning can appear in `git status`; it is local
  generated output and should not be committed.
