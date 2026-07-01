# Current TODO

Document version: 2026.06.30
Last updated: 2026-06-30
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

This is the active TODO list for theFactory. Superseded sprint plans, historical
backlogs, and old phase notes live under `docs/archive/` and should not be used
as current work.

---

## Current Status

**Most recent work: the first full, chat-driven system run (2026-06-30).**
20 missions were submitted one at a time through the real Mission Control chat
UI (not the raw API), each going through the PM Agent's actual clarification
dialogue, covering all 19 language specialists across all 4 pods plus one
modernize/debug-repair mission. All 20 reached `COMPLETE`. Full results, code
review, agent/support-ring usage tally, and recommendations:
`FIRST_FULL_SYSTEM_RUN_FINDINGS_2026-06-30.md` (repo root); the full
chronological session narrative (what happened, in order, and exact
end-of-session repo/stack state) is `MISSION_TESTS_SESSION_LOG_2026-06-30.md`
(repo root). Headline: PBLA's
Alpha/Sigma/Delta/Omega lanes all fired correctly with zero DLQ writes; one
real routing bug was found and fixed (pod-audit misrouting); one real dead-code
defect was found and root-caused but not yet fixed (Beta never fires); two
missions silently generated code in the wrong language. **The battery's
database state was subsequently wiped** by `stop_app.bat`'s `docker compose
down -v` — remediation plan at `docs/STACK_REMEDIATION_PLAN_2026-07-01.md`. No
further live fixes until that plan's offline-fix step completes.

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

**Two real issues surfaced by the live run, not yet fixed:**
- **Beta never fired across all 20 missions.** Root cause confirmed:
  `generated_output` is set earlier (`_prepare_specialist_assignment` in
  `phases_build.py`) than PBLA-03's insertion point in `_prepare_fusion`, so the
  `mission_has_generated_output` guard is already true and the codegen+Beta
  block is skipped every time. Fix: move the Beta emission to `phases_build.py`
  right after `generated_output` is set.
- **Pod-audit agent misrouting** (found live, already fixed + unit-tested — see
  below) — fix is in the working tree, not yet committed pending stack
  remediation.

**Also surfaced (not PBLA-specific, but same run):** 2 of 20 missions (C, R)
generated the wrong language entirely (Python simulating the target language)
and still reached `COMPLETE` — no verification gate catches
generated-language-vs-requested-language mismatches. See findings §5/§6.2.

**Environment note:** the battery's database state was subsequently wiped by
`stop_app.bat` (`docker compose down -v`). Remediation plan (Postgres
credential mismatch + `api-gateway` internal-auth key, both unresolved):
`docs/STACK_REMEDIATION_PLAN_2026-07-01.md`. Per explicit direction, no further
live fixes until that plan's offline-fix step is done.

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
| Protocol Bus lanes | All six lanes have live producers (PBLA-00..04) and were live-validated 2026-06-30 (20-mission battery); Beta confirmed non-firing (root-caused, fix pending); only Sigma is consumed so far. Four-stage program tracked by `PROTOCOL_BUS_PROGRAM_ROADMAP.md` (PBLA done → EDCP next → Agent Runtime Split → Semantic Bus) |
| Pod-audit routing | Bug found live 2026-06-30 (case-mismatch caused every non-Pod-A audit to silently misroute); fixed + unit-tested in the working tree, not yet committed |
| Beta lane (PBLA-03) | Never fired across 20 live missions; root cause confirmed (insertion point unreachable for normal `BUILD_NEW` missions); fix identified, not yet applied — see `FIRST_FULL_SYSTEM_RUN_FINDINGS_2026-06-30.md` §6.1 |
| Generated-language verification | No gate catches generated-code-language ≠ requested-target-language; 2 of 20 live missions (C, R) silently delivered Python instead — see findings §6.2 |
| Stack credentials | Postgres password mismatch and `api-gateway` internal-auth key resolve incorrectly after a restart; unresolved, offline fix required — see `docs/STACK_REMEDIATION_PLAN_2026-07-01.md` |
| Database state | `postgres-data`/`redis-data` volumes were wiped by `stop_app.bat` (`docker compose down -v`); all mission/chain-trace history from the 2026-06-30 battery is gone (generated code artifacts survived in `output/`) |

---

## Known Non-Issues

- `.pytest-tmp/` may remain as an untracked local temp directory from prior test
  runs. It is not part of the repository.
- OTel/Jaeger export warnings during tests are expected when Jaeger is not
  running locally and do not by themselves fail tests.
- Files under `docs/archive/` are historical and should not drive active work
  unless reconciled into this file.
