# Combined Work Queue

Document version: 2026.08.21
Last updated: 2026-08-21
Status: Canonical execution order
Audience: Maintainers and AI coding agents

One ordered, de-duplicated queue merged from `PRODUCTION_COMPLETION_PLAN.md`,
`docs/HANDOFF_CURRENT.md` (Next Actions), and `docs/CURRENT_TODO.md`. Those
remain the source of detail; this file is the order of work and the single place
that says what is actually next.

Items already verified complete against live source are **not** listed. See the
"Validation against live source" table in `PRODUCTION_COMPLETION_PLAN.md` for
what was dropped and why — Sprints 0.1 and 1.3 were already done, and the
substantive half of 3.1 as well.

## Ordering rationale

Verification integrity comes first. Several downstream exit criteria read "live
suites still green", and that criterion can currently pass having verified
nothing — so the gates get fixed before they are used to certify anything else.
Cheap self-contained hardening follows, then evidence, then features.

---

## Tier 1 — Fix the gates before trusting them

| # | Item | Source | Why first |
|---|---|---|---|
| 1 | Live suite silently skips: `LIVE_HTTP_TIMEOUT_SECONDS` defaults to 4.0s, the probe reads the resulting `OSError` as "stack unreachable", and the run reports **exit 0 having verified nothing** | Handoff NA-3 | Every later evidence item depends on this suite meaning something |
| 2 | Mission Control polling exhausts the gateway rate limit (120/min shared key, ~13 req/poll) so mission creation 429s for every other client | Handoff NA-4 | Blocks running the live suite without stopping the UI |
| 3 | Pin `kotlin` / `scala` / `zig` / `ocaml` sandbox images by digest — no official image, mutable tags, `euantorano/zig:master` moves | Handoff NA-2 | These images are the containment for untrusted generated code |

## Tier 2 — Evidence

| # | Item | Source |
|---|---|---|
| 4 | Sprint 0.2 — durable S1-01 / UPG-20 evidence file under `docs/evidence/` | Plan 0.2 |
| 5 | Sprint 1.1 — multi-mission live proof matrix: UI-driven mission, a PORT/transform, a non-Python language, failure injection, provider fallback | Plan 1.1 |

## Tier 3 — Features and decisions

| # | Item | Source | Note |
|---|---|---|---|
| 6 | Sprint 2.1 — Delta consumer as pod-audit gate (`main.py:505` still `handlers = {"sigma": …}`) | Plan 2.1 | First lane where a down consumer must block a mission |
| 7 | Sprint 1.2 — BUILD_NEW behavioural-equivalence decision | Plan 1.2 | Option 2 is now far cheaper: artifact execution exists for 19 languages |
| 8 | Sprint 3.2 — Repo ZIP import **UI trigger seam** (backend Phases 5–7 already in source; arm `metadata.repo_import` + call `POST /api/repo/index` after createMission) | Plan 3.2 | See `docs/evidence/repo_zip_phases_5_7_verification_20260821.md` |
| 9 | Sprint 3.1 — Electron: the three lifecycle decisions + installer/uninstall tests | Plan 3.1 | **Needs user sign-off**, not just code |
| 10 | Sprint 3.3 — operator polish; real LogicNode graph needs a transform mission | Plan 3.3 | |

## Tier 4 — Production hardening and release

| # | Item | Source | Note |
|---|---|---|---|
| 11 | Move sandbox execution out of the orchestrator into `agent-41-rqca` | Handoff NA-5 | **Done (2026-08-17; verified in full-dedicated 2026-08-19):** `sandbox-runner` owns `docker.sock`; orchestrator uses `SANDBOX_EXECUTOR_URL`. AGENT-41-RQCA still owns the verdict. Dedicated overlay can point the same URL at a worker that serves `/internal/sandbox/execute`. |
| 12 | C# offline runtime (`dotnet-script` uninstallable with `--network=none`) | Language matrix | Currently an honest DRY_RUN; lowest priority |
| 13 | Sprint 4.1 — measurement before enforcement; ≥20 missions before raising `MISSION_EQUIVALENCE_ENFORCEMENT_ENABLED` | Plan 4.1 | |
| 14 | Sprint 4.2 — final documentation and promotion package | Plan 4.2 | |
| 15 | Resolve the date skew: plan says 2026-08-07, harness says 2026-08-10, container clocks say 2026-08-11 | Plan validation | Evidence filenames are minted by date and the promotion gate consumes them |

---

## Progress

- [x] **1 — live-suite silent skip** *(2026-08-11)*. Root cause was not the
  timeout: `localhost` resolves `::1` first on Windows while compose binds IPv4
  only, measured at **2.09s vs 0.02s**, which pushed the first request past the
  4.0s budget. Both suites now default to `127.0.0.1`, share one timeout policy
  via `live_stack_auth` (they had drifted to 4.0s and 30.0s), and every skip
  says **"NOTHING WAS VERIFIED"**. `LIVE_STACK_REQUIRED=1` turns any skip into a
  failure — set it for any run whose output becomes evidence.
  **Live-verified 2026-08-11**: the suite runs with zero env overrides and
  under `LIVE_STACK_REQUIRED=1`; it previously needed a 30s override or it
  skipped green.
- [x] **2 — UI rate-limit exhaustion** *(2026-08-11)*. Read and write traffic
  now use separate Redis buckets: polling a dashboard is not abuse, and
  counting ~13 GETs per cycle against the same 120/min allowance as mission
  creation let one open browser tab 429 every other client. Writes keep the
  tighter budget (`API_RATE_LIMIT_PER_MINUTE`); reads get
  `API_READ_RATE_LIMIT_PER_MINUTE` (600). This separates the buckets, it does
  not relax the write limit.
- [x] **3 — pin non-official sandbox images by digest** *(2026-08-11)*. Seven
  pinned, not the four originally scoped: `mathicsorg/mathics:latest`,
  `denoland/deno:latest` and `euantorano/zig:master` were all floating.
  `test_non_official_sandbox_images_are_pinned_by_digest` fails if one reverts
  to a mutable tag.
- [x] **4 — S1-01 evidence** *(2026-08-12)*. `docs/evidence/s1_01_live_generation_go_20260811.json`, captured by the new `scripts/capture_live_mission_evidence.py`. Mission `mission-f8a5accf-63fa-47a6-9f33-3f76346db650`, **Go**, reached COMPLETE with 25 chain events, a 1298-byte generated_code artifact, and a pod-assignment record on **podB** (`assigned_by: orchestrator`) — the record that used to 404. Deliberately non-Python: Go is Python-dissimilar, so `language_content_signature` was in scope and **passed**, and 0 logicnodes is correct for BUILD_NEW.
- [x] **5 — multi-mission live proof matrix** *(closed 2026-08-17)*.
  PORT-through-SOW `mission-dc0c8c4e`. Failure injection
  `mission-6ee8b1fe` (bus restarted at FETCH; 21 events, visible
  VERIFIED). Provider fallback `mission-db901d98` (`generated_output.source=fallback`
  after invalid Gemini). Evidence:
  `docs/evidence/remaining_live_proof_20260817.json`.
- [x] **6 — Delta consumer gate (EDCP-02a)** *(2026-08-11)*. `handlers` now
  registers `delta`; a consumed verdict is recorded on the mission and
  `_advance_verified_to_complete` refuses COMPLETE without a *passing* one.
  Absence blocks — that is the exit criterion: a **down consumer stalls the
  mission visibly** instead of letting it complete as though audited.
  Correlation is prefix-parsed, never compared for equality. Inert unless
  `EVENT_DRIVEN_CONTROL_PLANE_ENABLED`. **Live-bus 2026-08-17:**
  `mission-56bfd2dc` consumed Delta
  `delta-mission-56bfd2dc-…-podA` onto `delta_audit_gate` (prefix parse).
- [ ] 7 — BUILD_NEW equivalence decision
- [ ] **8 — repo ZIP Phases 5–7 UI trigger** *(backend verified present 2026-08-21; UI seam open)* — see `docs/evidence/repo_zip_phases_5_7_verification_20260821.md`. Do **not** rebuild Phase 5 guard, `/api/repo/index`, `/internal/.../repo-import-index`, `load_repo_context`, or pod-worker `_fetch_doc_context`. Wire `metadata.repo_import` + post-create index call only.
- [ ] 9 — Electron decisions *(blocked on user sign-off)*
- [ ] 10 — operator polish
- [x] **11 — sandbox out of the orchestrator** *(closed 2026-08-19)*. Verified
  live in **full-dedicated** (56 containers), not only condensed: the
  orchestrator has no `/var/run/docker.sock` at all, `sandbox-runner` holds it,
  and `/internal/sandbox/health` answers the orchestrator's bearer token. Proved
  by execution rather than presence — a valid Python file returned exit 0 with
  real stdout, and a deliberately broken one returned exit 1 with a real
  `SyntaxError`, so the runner is not passing everything.
- [ ] 12 — C# offline runtime
- [ ] 13 — measurement before enforcement
- [ ] 14 — release package
- [x] **CI and Weekly Qualification restored** *(2026-08-19)*. CI had been red on
  `main` for five consecutive pushes and Weekly Qualification for every run since
  at least 2026-08-03; neither was visible from a local test run, and none of it
  was a product defect. CI: two Playwright tests still asserted the pre-SOW repo
  flow. Qualification: three faults stacked in series — missing TLS certs (postgres
  exited 0.5s after start), a stack missing neo4j/minio/milvus while their
  `*_ENABLED` flags were true (orchestrator readiness unsatisfiable by
  construction), and a canary that sent no API credential (every mission creation
  401). Consequence worth remembering: the 80% coverage floors added 2026-08-17 sit
  after the E2E step, so they **never ran on `main`** for those five pushes.
  Details in `docs/reviews/theFactory_Deep_Code_Review_2026-08-18.md` (P3-6, P3-7).
- [x] **15 — date skew** *(2026-08-11)*. Resolved: host and container clocks
  agree on **2026-08-11**. Docs written earlier in the session carried
  2026-08-06, taken from a container timestamp read during a long-running
  session; 19 occurrences corrected.
- [x] **P1 — no install into `--network=none`** *(2026-08-12)*. Unmet
  third-party deps are DRY_RUN, never PASS.
- [x] **P2 — classify before verifying** *(2026-08-12, tightened 2026-08-17)*.
  CLI / GUI / library / server / interactive. `while True` and bare `.listen(`
  are not enough. Syntax-only success is ADVISORY. Generated tests run when
  present.
- [x] **P3 — approval-shaped chat confirm** *(2026-08-12, `d84d64e`)*.
- [x] **Honesty / Gemini 3.7 / tests-as-QC** *(2026-08-16/17, PR #460)*.
  `started_only` never PASS; all agents on `gemini-3.7-flash`; Tester output
  is the sandbox command; `main` at `0b6ee4c`.

---

## Next up

**Immediate implementation candidate:** item **#8** UI trigger seam for repo ZIP
indexing (metadata + `POST /api/repo/index` after mission create). Backend
Phases 5–7 are already in source — do not re-implement them.

**Product decision (not code cleanup):** item **#7** BUILD_NEW equivalence.

**Later / blocked:** #9 Electron (user sign-off), then #10 polish, #13–#14 release.

Compose default is `RQCA_ENFORCEMENT_ENABLED=true`. A local `.env` may still
set `false` — that override is not the product default.

---

## Runtime QC now verifies behaviour, not just startup (2026-08-12)

The false FAIL is fixed and verified live. `mission-03f88983` (Go word counter):

```
run_command    : go build -o /tmp/a.out /workspace/main.go && /tmp/a.out
invocation_args: ['input.txt']
verified_scope : executed
verdict        : PASS | exit 0 | docker_live
stdout         : "test 1
"
```

The program compiled, read the input file, counted the words and printed the
result. That is a functional verification, not a smoke test.

**Nothing new had to be invented — two existing fields were simply never
consumed.** The codegen prompt has always asked the specialist for "one short
usage example" and it answers with the real invocation
(`"go run main.go input.txt"`); the manifest has always carried
`synthetic_inputs`, which nothing ever wrote to disk. Arguments are now derived
from the example, any file operand is materialised into the workspace before it
is mounted read-only, and the arguments are appended to the run step.

**Enabling the TESTDATA agent would not have fixed this** — worth recording,
because it is the obvious-looking answer. It is a stub (`_ = mission_contract,
settings`) that emits the same argument-free command and never writes its own
`synthetic_inputs` anywhere.

Derivation is conservative by design: arguments come only from after the token
naming the artifact, and an unrecognised example derives nothing. A first
version stripped runner words instead and turned the nonsense example
`"just run it"` into arguments `["run", "it"]` — it would have created files
called `run` and `it` and handed them to the program. Fabricating an invocation
is worse than deriving none.

When no invocation can be derived the report says `verified_scope_detail:
"started_only"` and a non-zero exit is no longer a failure, since nothing told
the program what to do. The check that matters is untouched: a build failure
short-circuits the `&&` before the program runs, so wrong-language and
non-compiling artifacts still FAIL.

### On `RQCA_ENFORCEMENT_ENABLED`

**Superseded 2026-08-17.** The shipped default is `true`. FAIL blocks;
`started_only`, syntax-only, `DRY_RUN`, `SKIPPED`, and `ADVISORY` do not.
A local `.env` may still pin `false`. Watch for `verified_scope_detail:
"started_only"` on missions that should have been exercised — that means
the usage example did not yield invocation args and tests did not run.
