# Production Completion Plan — theFactory

**Repo:** https://github.com/kherrera6219/theFactory  
**Created:** 2026-08-07  
**Baseline:** main (validated against `docs/CURRENT_TODO.md`, `docs/IMPLEMENTATION_STATUS.md`, `docs/UPGRADE_RECONCILIATION_PLAN_2026-08-01.md`, `docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md`, and key source paths)  
**Status:** Planning document — execute starting at Sprint 0.1  

This plan expands the production-readiness path into **phases → sprints**, with concrete files to update/wire, connections that must be made, additional tests, and the same documentation & test standards already used in the project.

---

---

## Validation against live source — 2026-08-11

Every claim below was checked against code, not against the status docs the plan
was built from. Three sprints were already complete when the plan was written;
one of its standards was itself failing.

| Sprint | Verdict | Evidence |
|---|---|---|
| 0.1 Pod-assignment consistency | **DONE** (`87ed6bc`) | `provisional=True` write in `phases_build.py`; live proof `mission-03753eb7-…` returns 200 |
| 0.2 Formalize S1-01 evidence | **OPEN — valid** | no `s1_01*` / UPG-20 file in `docs/evidence/` |
| 1.1 Multi-mission live proof | **OPEN — partially advanced** | one API-driven live mission green; UI / PORT / failure-injection / fallback still owed |
| 1.2 BUILD_NEW equivalence decision | **OPEN — now much cheaper** | its Option 2 needed artifact execution, which now exists for 19 languages |
| 1.3 `type_strategy` coverage | **ALREADY DONE** | all 10 `MissionType` values present; `test_mission_type_routing_coverage.py` exists |
| 2.1 Delta consumer gate | **OPEN — valid** | `main.py:505` — `handlers = {"sigma": _handle_sigma_knowledge_ready}` |
| 3.1 Electron packaging | **PARTIALLY DONE** | `next.config.mjs` already off `output: export` and on `standalone`; the 3 user decisions + installer tests remain |
| 3.2 Repo ZIP import | **OPEN — valid** | migration plan Phases 1–4 complete, 5–7 open |
| 3.3 Operator polish | **OPEN — partially advanced** | LogicNode panel is now mission-type aware; a real graph still needs a transform mission |
| 4.1 Measurement before enforcement | **OPEN — valid** | `MISSION_EQUIVALENCE_ENFORCEMENT_ENABLED=false` |
| 4.2 Final documentation package | **OPEN** | depends on the above |

### Corrections to the plan's own premises

1. **"The durable writers currently live primarily in the pod-worker path"** —
   no longer true, and the framing behind it was wrong. There are not two
   execution paths. `mission_flow_v2` is the only lifecycle driver
   (`lifecycle_interface.get_lifecycle_engine`); the pod worker is a *side
   consumer* of `missions.state` that merely happened to be the sole writer of
   the record. The plan's "Preferred" option is what shipped.
2. **Cited pod-worker lines ~1252 / ~1425 no longer locate the writers.** The
   plan flagged this itself as medium confidence; treat it as confirmed stale.
3. **"`scripts/production_review_audit.py` still 23/23"** was **22/23** when this
   plan was written. DOC-006 asserted the literal string
   `"Last validated: 2026-06-26"` in `AGENTS.md`; revalidating that file on
   2026-08-01 broke the check, and the only way to pass was to backdate the
   timestamp — inverting the purpose of a staleness check. Fixed in `371ad85`
   (parse + floor). Back to 23/23. **Any exit criterion that cites 23/23 was
   citing a number that did not hold.**
4. **"Beta emission site in `phases_build.py`"** — `CURRENT_TODO.md` records that
   the findings doc named the wrong function and the emission went into
   `_prepare_specialist_plan`. Inherited error; re-read before acting on 1.1.
5. **Date skew.** This plan is dated 2026-08-07, the harness reports 2026-08-10,
   and container clocks read 2026-08-11 (the dates used in today's commits and
   handoff). Worth resolving before evidence filenames are minted, since the
   promotion gate consumes them by date.

### Missing from the plan (added 2026-08-11, none of it known when it was written)

The plan predates the RQCA/sandbox work, which changes two of its sprints and
adds five items it does not cover:

- **Runtime verification now covers 19 of 19 pod languages**, each with a
  positive *and* a negative control (`scripts/rqca_language_audit.py`). This is
  the capability Sprint 1.2's Option 2 assumed was missing.
- **Pin `kotlin`/`scala`/`zig`/`ocaml` sandbox images by digest.** They have no
  official image and are referenced by mutable tags; `euantorano/zig:master`
  moves. These images are the containment for untrusted generated code.
- **The live suite silently skips.** `LIVE_HTTP_TIMEOUT_SECONDS` defaults to 4.0s
  and the probe treats the resulting `OSError` as "stack unreachable", so the
  run reports **exit 0 having verified nothing**. Any sprint whose exit criterion
  is "live suites still green" is at risk of passing vacuously.
- **Mission Control polling exhausts the API rate limit** (120/min on the shared
  key, ~13 requests per poll cycle), returning 429 to every other client
  including the live suite.
- **Sandbox execution privilege moved off the orchestrator (2026-08-17).**
  The plan's "sandbox rule" (one `docker run` path) is still honoured.
  Condensed compose mounts `/var/run/docker.sock` on `sandbox-runner` only;
  the orchestrator POSTs to `SANDBOX_EXECUTOR_URL`. AGENT-41-RQCA still owns
  the verdict. Do not put the socket back on the orchestrator.
- **C# has no offline runtime** (`dotnet-script` uninstallable with
  `--network=none`); it returns an honest DRY_RUN.

### Recommended revision to the critical path

Sprint 0.1 is done and 1.3 needs nothing, so the real head of the queue is
**0.2 → 1.1**. Fix the live-suite timeout *before* 1.1, or its evidence may be
produced by a run that verified nothing.

---

## Standards That Apply to Every Sprint (Do Not Relax)

- **Code is truth.** Verify against live source before claiming a gap is closed.
- **Additive + flagged.** Behavioural changes ship behind `*_ENABLED` flags that default to the safe/off value. Flag off ⇒ byte-identical behaviour.
- **Tests first / regression discipline.** New behaviour requires tests that would have failed against the pre-change code (use `git stash` or equivalent to prove it when practical). Keep backend **line ≥80%**, **branch ≥70%**, mixed ≥80%, and existing per-module floors. Every critical file is floored at **at least 80%**. A mixed score above 80% cannot hide a line score below 80%. UI: Vitest + Playwright critical paths.
- **Documentation standards.** Update `docs/CURRENT_TODO.md`, `docs/IMPLEMENTATION_STATUS.md`, and the governing ADR when scope or status changes. Run `scripts/validate_documentation.py` and keep it green. No new claim that contradicts code. Evidence files go under `docs/evidence/`.
- **No silent failure paths.** Prefer loud, observable failure over silent degradation (especially for Object Lock, auth, and bus consumers).
- **Sandbox rule.** All generated-code execution continues to go through `orchestrator/sandbox_exec.py`. Do not introduce a second `docker run` path.
- **Non-goals remain closed.** Do not reopen four-pod fan-out, binary/LLVM synthesis, or the 0.0001% tolerance.

---

## Phase 0 — Stabilize Path Consistency & Formalize Existing Evidence

**Goal:** Close the newest known inconsistency and turn candidate live runs into durable release evidence.  
**Estimated effort:** 1–3 days  
**Hard dependency for later phases:** Yes (especially Phase 2 / EDCP).

### Sprint 0.1 — Pod-assignment / LogicNodes path consistency (v2 vs worker)

**Problem (Verified from CURRENT_TODO 2026-08-05):**  
A pure `mission_flow_v2` mission can emit `MISSION_POD_MANAGER_ASSIGNED`, reach `VERIFIED`, and produce a build artifact while `GET /v1/missions/{id}/pod-assignment` returns 404 and logicnodes remain `[]`. The durable writers currently live primarily in the pod-worker path.

**Files to inspect / update:**

- `services/orchestrator/orchestrator/mission_flow_v2/phases_build.py` (and related phases) — where the assignment *event* is emitted.
- `services/orchestrator/orchestrator/routes/internal.py` — `POST /internal/pod-assignment` upsert endpoint.
- `services/orchestrator/orchestrator/storage_pods.py` (and storage façade) — persistence of the assignment record.
- `services/pod-worker/pod_worker/main.py` — existing writers of the durable record (lines previously cited ~1252 / ~1425).
- `services/orchestrator/orchestrator/runtime.py` — event → agent routing for `MISSION_POD_MANAGER_ASSIGNED`.
- Gateway proxy path that surfaces `/v1/missions/{id}/pod-assignment` and `/logicnodes`.

**Wiring required:**

1. Decide and implement one consistent contract:
   - **Preferred:** When the v2 path emits `MISSION_POD_MANAGER_ASSIGNED`, also write the durable pod-assignment record (call the same storage / internal upsert used by pod-worker, or extract a shared helper).
   - Alternative (only if intentional): Document that the pure-v2 path is event-only and that the API returns 404 until a worker processes it; then update Mission Control and live tests accordingly.
2. Ensure logicnode write path is also consistent for BUILD_NEW vs transform missions (BUILD_NEW currently has no source extraction → empty logicnodes is expected; do not paper over it).

**Tests to add / extend:**

- Unit: pure v2 path that emits the assignment event **must** leave a readable pod-assignment record (or the documented 404 contract must be asserted).
- Integration / live: extend `test_live_mission_chain_and_artifact_integrity` (or successor) to assert both the chain events **and** the durable `/pod-assignment` + expected logicnodes behaviour.
- Regression that fails if only the event is written and the record is missing.

**Docs:** Update the “Known Gaps” section in `docs/CURRENT_TODO.md` and any contract notes in architecture / API docs.

### Sprint 0.2 — Formalize UPG-20 / S1-01 evidence

**Files / artifacts:**

- `docs/evidence/` — create `s1_01_live_generation_2026-08-XX.json` (and any supporting independent execution notes) from the existing `mission-7a098d0f-…` csv2json run and at least one additional non-trivial mission.
- `scripts/demo_missions.py` and live smoke scripts — ensure they can produce the required evidence format.
- `docs/CURRENT_TODO.md`, `docs/IMPLEMENTATION_STATUS.md`, `docs/EDCP_PHASE_PLAN.md` (hard-prerequisite section).

**Actions:**

1. Capture durable evidence (mission ID, chain events, artifact, independent execution against every acceptance criterion).
2. Close or re-scope the S1-01 gate language so Phase 2 is no longer blocked by “no non-trivial evidence.”
3. Keep the honesty note that behavioural equivalence remains `skipped` for pure BUILD_NEW until the open decision in Phase 1 is made.

### Phase 0 Exit Criteria

- Path inconsistency resolved or explicitly contracted and tested.
- Durable S1-01-style evidence committed.
- Live suites still green with auth (`tests/services/live_stack_auth.py`).
- `scripts/validate_documentation.py` green; CURRENT_TODO / IMPLEMENTATION_STATUS updated.

---

## Phase 1 — Live Verification Gates & Product Decisions

**Goal:** Prove realistic end-to-end behaviour and close product decisions that affect honesty of the semantic engine.  
**Estimated effort:** 3–7 days  
**Depends on:** Phase 0.

### Sprint 1.1 — Multi-mission live proof matrix

**Actions:**

- Run additional non-trivial missions through **Mission Control UI** (not only raw API): at least one more BUILD_NEW, one PORT / transform, and preferably one that exercises a non-Python language.
- Record UI smoke, chain traces, artifacts, and independent execution results under `docs/evidence/`.
- Live failure-injection (kill/restart protocol-bus or a dependency mid-mission) and provider-fallback (invalid primary key).
- Full `make validate` + current production audit on the evidence stack.
- Re-confirm earlier fixes (Beta emission site in `phases_build.py`, pod-audit routing, language-content signature check, compliance trigger).

**Tests / scripts:**

- Extend or add live suite cases that assert the four (or more) required chain events **plus** durable records.
- Capture results in evidence JSON that the promotion gate can consume.

### Sprint 1.2 — BUILD_NEW behavioural equivalence decision

**Open decision (from CURRENT_TODO):** Phase 5 equivalence projects from LogicNodes extracted from *existing* source. Pure BUILD_NEW has none → honest `skipped`.

**Options:**

1. Keep honest `skipped` for creation missions (no scope change).
2. Project vectors from the **generated** artifact’s own AST and execute against contract acceptance criteria (scope change to D1 → requires ADR amendment).

**Files if option 2 is chosen:**

- `services/orchestrator/orchestrator/equivalence_verifier.py` / behavioural report path.
- `services/orchestrator/orchestrator/sandbox_exec.py` (reuse only).
- Refined-IR / LogicNode projection path for generated artifacts.
- Mission Control `EquivalenceReportPanel` (already distinguishes scopes).

**Tests:** Vectors that can actually fail; `executed_without_error` must never be counted as `passed`; flag-off remains byte-identical.

### Sprint 1.3 — Mission-type routing coverage (`type_strategy`)

**Current state:** `docs/MISSION_TAXONOMY.md` and CURRENT_TODO report that `RUN_QC`, `ARCHITECTURE_DOCS`, and `SELF_ANALYZE` fell through to BUILD_NEW. Code search shows partial entries and a dedicated test file `tests/services/test_mission_type_routing_coverage.py` already exist — **verify live source first**.

**Files:**

- `services/orchestrator/orchestrator/llm_delegation/prompts.py` — `type_strategy` map.
- `docs/MISSION_TAXONOMY.md`.
- Existing coverage test above.

**Actions:** Confirm every `MissionType` has an intentional strategy (or an explicit documented fallback). Add the three strategies if still missing; update the taxonomy doc and the coverage test so a missing key fails the suite.

### Phase 1 Exit Criteria

- Multiple non-trivial live missions + UI/failure/fallback proofs recorded.
- BUILD_NEW equivalence decision recorded (ADR or taxonomy).
- `type_strategy` fully intentional and tested.
- Documentation and CURRENT_TODO reflect closed items.

---

## Phase 2 — Make the Protocol Bus Load-Bearing (EDCP)

**Goal:** Turn producers from telemetry into a control plane that can gate missions.  
**Estimated effort:** 1–2 weeks  
**Hard prerequisite:** Phase 0/1 evidence (UPG-20).

Execute `docs/EDCP_PHASE_PLAN.md` with the inserted **EDCP-02a**.

### Sprint 2.1 — EDCP-02a: Delta consumer as pod-audit gate

**Why first:** Delta already has live producers (`phases_build.py`), carries pass/fail semantics, and has a natural gate in `lifecycle.py:_advance_verified_to_complete`.

**Files to update / wire:**

- `services/orchestrator/orchestrator/main.py` — `protocol_bus_consumer_loop` / `handlers` dict (currently only `"sigma"`).
- Protocol bus consumer module (`protocol_bus_consumer.py` or equivalent).
- `services/orchestrator/orchestrator/mission_flow_v2/lifecycle.py` — completion gate that must respect a consumed Delta `fail`.
- Producer sites in `phases_build.py` (ensure discriminators and correlation prefixes are correct).
- `docs/PROTOCOL_ENVELOPES.md` — correlation is **prefix parse, never equality** (bus reuses `correlation_id` for replay/dedup).

**Wiring:**

1. Register a Delta handler that can mark a mission blocked / prevent silent COMPLETE.
2. Prove: with consumer suppressed, mission does **not** silently complete.
3. Update any “fire-and-forget telemetry” docstrings for lanes that become load-bearing.

**Tests:**

- Unit: handler receives a fail verdict → mission cannot advance to COMPLETE.
- Integration: consumer-down test (exit criterion from EDCP plan).
- Correlation prefix join tests (no equality queries).

### Sprint 2.2 — Remaining EDCP seams (Omega → CEO→pod → support ring)

Follow the existing EDCP phase plan order. Same standards: flag-gated (`EVENT_DRIVEN_CONTROL_PLANE_ENABLED` or equivalent), additive, tested, documented.

### Phase 2 Exit Criteria

- At least one lane where a down consumer measurably blocks a mission.
- `PROTOCOL_BUS_PROGRAM_ROADMAP.md` Stage 2 advanced.
- No new silent completion paths; docs and producer comments accurate.

**Non-goals:** Agent Runtime Split and Semantic Bus stay deferred.

---

## Phase 3 — Packaging, Installer & Operator Experience Closure

**Goal:** Ship a real local-first desktop experience and finish remaining intake paths.  
**Estimated effort:** 1–2 weeks  
**Can run largely in parallel with Phase 2 after Phase 1.**

### Sprint 3.1 — Electron / Windows installer decisions & implementation

**Files / areas:**

- `apps/mission-control/electron/` (`main.ts`, `preload.ts`, `tray.ts`, `updater.ts`, diagnostics).
- `apps/mission-control/next.config.mjs` and build scripts (static-export vs standalone).
- `scripts/build-electron.mjs` (or equivalent).
- Packaging / NSIS hooks, vault/data cleanup on uninstall.
- `docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` Phase 4 decisions (§7.2, §7.4, §7.7).

**Required decisions (user sign-off):**

1. Docker lifecycle on app quit.
2. Docker Desktop / WSL2 prerequisite story.
3. Auto-start behaviour.

**Implementation direction (from remediation plan):** Prefer embedded standalone Next.js server (same as Docker path) so the 14 `app/api/*` routes work inside the package. Do not leave static-export mode that hides API routes.

**Tests:** Playwright Electron config already exists; add install/uninstall and “API routes reachable inside package” checks where practical. Manual evidence of a clean install → start stack → mission → uninstall cleanup.

### Sprint 3.2 — Repo ZIP import remaining phases

**Tracked by:** `docs/REPO_ZIP_IMPORT_MIGRATION_PLAN.md` (Phases 1–4 done; 5–7 open).

**Remaining:** mission launch index guard, repo knowledge ingestion, PM/pod-worker repository context loading so indexed content is available from the internal DB.

**Files:** Mission Control `/api/repo/*` routes, orchestrator knowledge / mission intake paths, any storage that must hold the indexed snapshot.

**Tests:** Existing archive helper + import/review tests; add launch-guard and “context visible to specialist” tests.

### Sprint 3.3 — Operator surface polish

- Confirm LogicNode dependency graph renders with **real** nodes (needs live stack + Phase 0 consistency).
- Provider/model selection fully driven from Mission Control Settings/vault; real preflight calls.
- Any remaining accessibility / stale-response items already flagged in prior reviews.

### Phase 3 Exit Criteria

- Installable desktop package that starts a working stack and exposes full API surface.
- ZIP path usable end-to-end for mission context.
- Operator UI evidence updated.

---

## Phase 4 — Hardening, Measurement & Release Gate

**Goal:** Measurable, releasable baseline.  
**Estimated effort:** 3–7 days  
**Depends on:** Phases 0–3.

### Sprint 4.1 — Measurement before enforcement

- Run behavioural equivalence across ≥20 real missions (Python first). Only then consider raising `MISSION_EQUIVALENCE_ENFORCEMENT_ENABLED`.
- Formally raise or defer remaining `mission_flow_v2` branch-coverage target; record the decision.
- Key rotation procedure + evidence; purge any remaining placeholder credentials from production profiles.

### Sprint 4.2 — Final documentation & promotion package

**Files:**

- `docs/CURRENT_TODO.md` — move completed items to history / archive as appropriate.
- `docs/IMPLEMENTATION_STATUS.md` — final scoped claims only.
- Governing ADR + any new decision ADRs.
- Evidence bundle under `docs/evidence/` that the release-trust / promotion gate consumes.
- `scripts/production_review_audit.py` still 23/23 (or updated count if checks are extended).

**Actions:**

- Full `make validate`, UI unit + e2e, production audit, documentation validation.
- Tag a “production-ready baseline” only after the evidence package is complete and claims match code.

### Phase 4 Exit Criteria

- All release gates green.
- Documentation and code claims aligned.
- Durable evidence package exists and is referenced from status docs.

---

## Suggested Execution Order (Critical Path)

1. **Sprint 0.1** (path consistency) + **Sprint 0.2** (formalize evidence) — immediately.
2. **Sprint 1.1–1.3** (live proofs + product decisions).
3. **Sprint 2.1** (Delta consumer) as soon as evidence exists; continue EDCP in parallel with packaging.
4. **Sprint 3.1–3.3** (packaging + ZIP + polish).
5. **Sprint 4.1–4.2** (measurement + release package).

---

## Top File Hotspots (Quick Reference)

| Area | Primary files |
|------|----------------|
| Assignment event vs durable record | `mission_flow_v2/phases_build.py`, `routes/internal.py`, `storage_pods.py`, `pod-worker/main.py` |
| Lifecycle gate | `mission_flow_v2/lifecycle.py` |
| Bus consumer | Orchestrator `main.py` handlers, protocol-bus consumer module |
| Equivalence / sandbox | `equivalence_verifier.py`, `sandbox_exec.py`, RQCA path |
| Mission-type routing | `llm_delegation/prompts.py`, `tests/services/test_mission_type_routing_coverage.py` |
| Electron packaging | `apps/mission-control/electron/*`, build scripts, `next.config.mjs` |
| Status / evidence | `docs/CURRENT_TODO.md`, `IMPLEMENTATION_STATUS.md`, `docs/evidence/` |

---

## Confidence & Notes

- **High confidence** on sequencing and the major open items — they are already documented with file/line evidence in the repo’s own audit and TODO files.
- **Medium confidence** on the exact current line numbers for the pure-v2 assignment writer gap (finding is dated 2026-08-05); re-verify against live source in Sprint 0.1 before coding.
- `type_strategy` may already be partially fixed; treat Sprint 1.3 as “verify then complete,” not “assume missing.”
- Keep the same test and documentation discipline that produced the current large green suite and 23/23 audit. Do not trade honesty labels or flag discipline for a prettier status board.

---

## Related Documents

- `docs/CURRENT_TODO.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/EDCP_PHASE_PLAN.md`
- `docs/UPGRADE_RECONCILIATION_PLAN_2026-08-01.md`
- `docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md`
- `docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md`
- `docs/REPO_ZIP_IMPORT_MIGRATION_PLAN.md`
- `docs/MISSION_TAXONOMY.md`
