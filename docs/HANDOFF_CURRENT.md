# Current Handoff

Document version: 2026.08.12
Last updated: 2026-08-12
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

---

## If you are picking this up cold — start here

**Read these three, in this order, before touching anything:**

1. `docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md` — **the governing document.**
   One Implemented / Superseded / Deferred verdict per design area. It outranks
   the numbered design corpus. Its "Corrections to the audit and plan" section
   records where the plan's own premises failed validation against live code.
2. `docs/UPGRADE_RECONCILIATION_PLAN_2026-08-01.md` — **§0 "Cold start"**, then §1
   (Decisions taken), §11 (Explicit non-goals), §5 (**Phase 2** — the current
   task; Phase 1 in §4 is complete).
3. `docs/DESIGN_VS_BUILD_AUDIT_2026-08-01.md` — §1–§2 for the gap, §4 for the
   divergences with file/line evidence.

`docs/DESIGN_TRACEABILITY.md` answers "design document N — where is it
implemented?" without re-reading the corpus.

Then `docs/CURRENT_TODO.md` → "Active Work Queue" → the *Design Reconciliation
& Semantic Engine Upgrade* section for what is actually next.

The plan runs **Phases 1–7**. Work item IDs are `UPG-<phase><item>` — `UPG-1x`
is Phase 1, `UPG-2x` is Phase 2, and so on. Phase 6 uses the `EDCP-*` IDs from
`docs/EDCP_PHASE_PLAN.md` instead.

### What happened on 2026-08-12 (most recent)

Read `docs/WORK_QUEUE.md` first from now on -- it is the single ordered queue,
merged from this file's Next Actions, `PRODUCTION_COMPLETION_PLAN.md` and
`docs/CURRENT_TODO.md`, and it says what is actually next.

**`RQCA_ENFORCEMENT_ENABLED` is `false` and should stay off for now** -- not
because anything is known to be broken, but because it has been correct for
exactly one mission. Run a handful across languages first; enabling a gate on one
data point is the pattern this work exists to break.

**Two gates were opened, each of which had made a whole subsystem unreachable.**

**Intake -- fixed, verified live.** 100% of missions used to stop for an
operator. Across 12 consecutive real missions the ambiguity score was 0.95-1.0
against a 0.7 gate, including prompts specifying sort order, separator, exit code
and error behaviour. The threshold was never the problem: `normalizers.py`
overwrites the LLM's score with `_pm_ambiguity_score`, which sums signals a
*thorough* PM emits on any prompt -- 0.55 for its own `needs_clarification` flag,
0.15 per question, 0.10 per risk note -- so it measures how much the PM said, not
how unclear the request was, and it is circular, since that flag alone supplies
0.55 of the 0.7.

The fix does not touch the score. The PM prompt already requires "a recommended
default in each question" and already defines the escape: with
`user_intent="finalize_plan"` it must return `intake_status: ready` and list every
assumption. That is what an operator triggers by answering "proceed with the
defaults", so intake now takes the same path instead of inventing a second one.
The questions stay recorded under `metadata.pm_auto_accepted_defaults`.
`PM_AUTO_ACCEPT_DEFAULTS_ENABLED` defaults to **true** -- against the usual
convention -- because off is not the safe value here, it is the broken one.
Verified: `mission-24fe7ed8` ran `QUEUED -> PM_INTAKE -> FETCH -> ...` with no
CLARIFYING stop. **Missions run unattended.**

**Runtime QC -- reachable, not yet trustworthy.** `phases_runtime` used to skip
on `TESTDATA_AGENT_ENABLED` *before* consulting `RQCA_AGENT_ENABLED`, so no
mission ever reached the sandbox and the 19-language matrix described a component
the pipeline never called. The gate now skips only when there is neither a
manifest generator nor a known runtime. The first two live runs then produced a
wrong verdict each, for opposite reasons:

1. **A vacuous PASS, fixed in `e5c2316`.** `PASS / docker_live` with stdout
   containing the Go source -- the command was `cat /workspace/main.go`.
   `testdata_agent` carried a *second* language table whose fallback was `cat`,
   and because it writes both image and command into the manifest, RQCA's
   `setdefault` never fired and the verified `_LANGUAGE_RUNTIMES` table was
   bypassed. Now one table, with a guard test that fails if they split again.
2. **A false FAIL, now fixed and verified.** With the real command the program
   compiled and ran, then exited 1 with `"Error: missing file path argument"` --
   correct behaviour for a tool the harness invoked with no arguments and no
   input file. Two fields already held what was needed and neither was consumed:
   `generated_output.usage_example` (`"go run main.go input.txt"`, which the
   codegen prompt has always requested) and the manifest's decorative
   `synthetic_inputs`. Arguments are now derived from the example and any file
   operand is materialised into the workspace. Verified on `mission-03f88983`:
   `invocation_args ['input.txt']`, scope `executed`, `PASS`, stdout `"test 1"` --
   the counter actually counted. Enabling the TESTDATA agent would NOT have
   fixed this; it is a stub that emits the same argument-free command.

Worth internalising: opening the gate produced a false PASS, fixing that produced
a false FAIL, and only the second run executed anything real. The false PASS was
the more dangerous -- it would have been captured as evidence.

**Everything else that changed**

- **Security Checks was failing on `main`**, which is why all 18 open Dependabot
  PRs showed three failing checks -- they inherited a broken workflow rather than
  being broken. Two root causes: `nanoid 3.3.16` (one bump cleared both the Node
  Audit and Trivy jobs -- they reported the same package), and two Bandit
  findings introduced the previous day. B608 was removed rather than suppressed
  by writing the two pod-assignment statements out as complete literals instead
  of interpolating a predicate; B108 (`SANDBOX_BUILD_DIR = "/tmp"`) is suppressed
  with reasoning, since it names a tmpfs inside a throwaway container, not a host
  temp path.
- **`DOC-006` was failing** because it asserted the literal string
  `"Last validated: 2026-06-26"` in `AGENTS.md`. Revalidating that file broke the
  check, and the only way to pass was to backdate the timestamp -- inverting the
  purpose of a staleness check. Now parsed against a floor. The audit was 22/23,
  not the 23/23 several documents cite as a release gate.
- **14 Dependabot PRs applied as one verified batch** rather than 14 CI cycles:
  fastapi 0.140->0.141, uvicorn 0.51->0.52.1 across seven services, redis, boto3,
  and three SHA-pinned action bumps taken from the PR diffs so the pin and its
  version comment cannot disagree. Dependabot auto-closed all 14. The four left
  open -- electron 43 (a major), next-ecosystem, vitest, playwright -- are held
  deliberately: CI cannot catch what they would break, they need the app
  exercised in a browser.
- **The live suites could pass having verified nothing.** Root cause was not the
  timeout it looked like: `localhost` resolves `::1` first on Windows while
  compose binds IPv4 only (2.09s vs 0.02s), which pushed the first request past
  the mission-flow suite's 4.0s budget, and the probe read that `OSError` as
  "stack unreachable". Both suites now default to `127.0.0.1` and share one
  timeout policy through `live_stack_auth`; they had drifted to 4.0s and 30.0s.
  Every skip says **NOTHING WAS VERIFIED**, and `LIVE_STACK_REQUIRED=1` turns a
  skip into a failure. **Set that for any run whose output becomes evidence.**
- **A polling dashboard could deny service to everything else.** Read and write
  traffic now use separate rate-limit buckets; ~13 GETs per Mission Control poll
  cycle were exhausting the same 120/min budget as mission creation, returning
  429 to every other client including the live suite.
- **The Delta lane is load bearing** (EDCP-02a). A consumed verdict is recorded
  on the mission and `_advance_verified_to_complete` refuses COMPLETE without a
  passing one -- absence blocks, because that is what a down consumer looks like.
  Inert unless `EVENT_DRIVEN_CONTROL_PLANE_ENABLED`. Unit-covered only; not yet
  exercised against a live bus.
- **First S1-01 evidence file**:
  `docs/evidence/s1_01_live_generation_go_20260811.json`, written by
  `scripts/capture_live_mission_evidence.py`. Mission
  `mission-f8a5accf-63fa-47a6-9f33-3f76346db650`, **Go**, COMPLETE, 25 chain
  events, a 1298-byte artifact, and a pod-assignment record on podB -- the record
  that returned 404 at the start of this work. Go rather than Python on purpose:
  it is Python-dissimilar, so `language_content_signature` was in scope and
  passed, which a Python mission cannot demonstrate.

### What happened on 2026-08-11

Five commits: `87ed6bc`, `4924e9e`, `613e57f`, `4c5991a`, `5c14c4f`. Two defects
found by inspection, then the code-execution sandbox made functional, then 11
more languages brought up to the same level.

**Headline: runtime verification went from 1 language to 17.**

**1. `MISSION_POD_MANAGER_ASSIGNED` was emitted with no assignment record**
(`87ed6bc`). One premise of the original report was wrong and is worth not
re-deriving: **there are not two execution paths.** `mission_flow_v2` is the only
lifecycle driver (`lifecycle_interface.get_lifecycle_engine`); the pod worker is
a *side consumer* of `missions.state` that merely happened to be the sole writer
of `mission_pod_assignments`. It writes when it *claims* execution -- a different
fact from "the CEO delegated to pod manager X", and one that never happens for a
mission no worker picks up. `_prepare_pod_assignment` now writes the record as it
emits the event, marked `assigned_by: "orchestrator"` and written
`provisional=True`. Precedence is directional and enforced in the
`ON CONFLICT ... DO UPDATE ... WHERE` predicate, so no read-then-write race
exists: a worker claim supersedes a provisional row, a provisional write can
never overwrite a claim. The worker's `_has_assignment` ignores provisional rows
-- without that every mission would look claimed and no worker would ever run.

**Root cause of the original 404:** the CEO's `pod_manager_agent_id` was
constrained to "one of the four pod managers" but not to the one owning the
mission's *language*, and the two pod-worker gates key off different fields
(language vs. bound agent id). A cross-pod choice therefore made a mission
invisible to *every* pod, silently -- Pod A rejects on binding, Pod C on
language, neither logs. The registry now wins when the language is known, the
override is recorded in `metadata.pod_manager_routing_correction`, and the
language gate increments `pod_worker_binding_skips_total{reason="language-mismatch"}`.
**Proven live:** `mission-03753eb7-a92b-4741-a181-c72ebcc37ec9` reached VERIFIED
with `/pod-assignment` returning 200.

**2. Gate-failure events made failed missions unopenable** (`4924e9e`).
`MISSION_EQUIVALENCE_BLOCKED`, `MISSION_SECURITY_COMPLIANCE_BLOCKED` and
`MISSION_DEPENDENCY_ABSORPTION_BLOCKED` are written to `mission_events`, but none
were in the `EventType` Literal -- only their happy-path siblings had ever been
added. `EventType` is the *response model*, so a single unlisted value made
pydantic reject the entire payload: `/missions/{id}/events`, `/chain-trace` and
`/operations/alerts` all 500, surfacing as 502 at the gateway. Any mission that
failed a gate could not be opened in Mission Control at all -- precisely the
mission an operator needs to read. A guard in
`tests/services/test_regression_contracts.py` now scans every
`insert_mission_event` / `transition_mission_state` site. It must follow the
`asyncio.to_thread(storage.insert_mission_event, ..., "EVENT")` form, where the
function name is an *argument* rather than a call: a first version matched only
`name(`, passed cleanly against the broken file, and caught none of the three
events it was written for.

**3. The RQCA / behavioural-equivalence sandbox now actually executes code**
(`613e57f`, `4c5991a`). `RQCA_AGENT_ENABLED` was off and nobody remembered why.
The flag was never the blocker -- **four independent defects each guaranteed
failure, and the first made the other three unobservable**:

- The orchestrator container had neither the docker CLI nor a socket, so every
  mission returned `DRY_RUN, "Docker not available"`. Harmless, and useless.
  This is almost certainly why it was switched off, and it was reasonable.
- Compiled languages could never have worked: the configs compiled into
  `/workspace/a.out` while `/workspace` is mounted read-only. Fixing that
  exposed the next layer -- Docker mounts tmpfs `noexec` by default, so the
  binary could not be executed. Build output now goes to `SANDBOX_BUILD_DIR`
  (`/tmp`) and the tmpfs carries `exec`. **No load-bearing protection was
  relaxed:** rootfs read-only, workspace `:ro`, `--network=none`,
  `--cap-drop=ALL` and `no-new-privileges` are all unchanged.
- C# was configured but unrunnable (`dotnet-script` is absent from
  `mcr.microsoft.com/dotnet/sdk:8.0` and cannot be installed offline). Removed
  -- see the DRY_RUN-vs-FAIL rule below.
- Interpreted languages ran in the wrong image: only compiled languages had
  base-image injection, so a JavaScript mission ran `node` inside
  `python:3.11-slim` and reported "node: not found" as a defect in the
  generated code.

Two further problems appeared only once execution was real: **sibling-container
path resolution** (the daemon resolves `--volume` sources on the *host*, so the
orchestrator's own tempdir mounts as an empty directory the daemon silently
creates -- hence `SANDBOX_WORKSPACE_ROOT` + `SANDBOX_WORKSPACE_HOST_ROOT` and
`daemon_workspace_path`), and **`--cap-drop=ALL` removing `CAP_DAC_OVERRIDE`**,
which makes the sandbox's root subject to ordinary permission bits so it could
not read `tempfile`'s 0700 directory (`main.c: Permission denied`, which reads
like broken code rather than a mount problem).

**4. Eleven more pod languages** (`5c14c4f`). ruby, php, r, julia, ocaml, go,
zig, haskell, java, kotlin and scala joined c/cpp/rust/python/javascript/
typescript. The two partial tables (`_EXECUTABLE_LANGUAGE_IMAGES`,
`_COMPILED_LANGUAGE_CONFIG`) were replaced by a single `_LANGUAGE_RUNTIMES`, and
`_ALL_LIVE_LANGUAGES` is derived from it -- so "which languages are live" can no
longer drift from "how do we run them". That split was the direct cause of the
JavaScript-in-the-Python-image bug. Verified by executing a hello-world through
the real sandbox: **17 of 17 PASS**, MATLAB correctly `DRY_RUN`.

**The rule that governs this table:** a language listed but unable to run is
*worse* than an absent one. Listed-but-broken yields `FAIL`, and
`RQCA_ENFORCEMENT_ENABLED=true` turns `FAIL` into a **blocked mission**; an
absent language degrades to an honest `DRY_RUN`. That is why `matlab`,
`mathematica` and `csharp` are currently out.

**Correction to that reasoning, 2026-08-11.** The first pass rejected MATLAB and
Mathematica as "licence-blocked, nothing we can do", and rejected GNU Octave on
the grounds that passing Octave asserts something untrue about MATLAB. That
conflated two different claims. This product is meant to run **with no external
requirements** -- a per-clone licence is not an option -- so a licence-free
runtime is the only acceptable design, and the question is what a licence-free
runtime can honestly verify. The dominant failure mode this gate exists to catch
is a specialist **silently emitting Python** while labelling it as the target
language (the 2026-06-30 battery caught exactly that for C and R). Detecting
*that* needs a parser for the target language, not a bit-exact MATLAB. Provided
the report never claims more than it checked, a subset runtime is honest and
useful. See Next Action 1 for the plan and the evidence already gathered.

### What happened on 2026-08-05

**Legal-hold audit artifacts were never being written, and nothing said so.**
`object_store.ensure_bucket()` created the artifact bucket without
`ObjectLockEnabledForBucket`, while `put_audit_report()` correctly *refuses* to
write a legal-hold object to a bucket that cannot hold one. Object Lock can only
be enabled **at bucket creation** in both S3 and MinIO — there is no API that
retrofits it — so every audit report with status `FAIL`/`FAILED`/`REJECT`/
`REJECTED`/`ERROR` was silently dropped while `/internal/audit-reports` still
returned 200. Live proof: an identical report posted as `PASSED` mirrored fine
and appeared in `audit-artifacts`; posted as `FAILED` it returned 200 and the
listing stayed empty.

The refusal in `put_audit_report` is correct and **must not be relaxed** — a
legal hold that silently degrades to an unprotected write is worse than a loud
failure. What was missing was creating a lock-capable bucket and saying so when
one isn't. Now:

- `ensure_bucket()` requests `ObjectLockEnabledForBucket=True` whenever
  `object_storage_legal_hold_on_fail` is set, and falls back to an unlocked
  bucket only if the backend rejects the parameter.
- `_bucket_has_object_lock()` returns `True`/`False`/**`None`** — an auth or
  network failure is *unknown*, not "no lock". An early version returned `False`
  on any exception, which raised a full compliance alarm for a credentials typo.
- Three independent signals: an ERROR log at startup, the
  `orchestrator_optional_adapter_object_lock_enabled` gauge, and a new
  `object_storage_object_lock_ready` field on `/health` and `/readyz`.
- `LegalHoldUnavailableError` lets callers tell a permanent misconfiguration
  from a transient outage; `/internal/audit-reports` now returns
  `object_storage_mirror: {stored, legal_hold_refused, detail}`.

**`object_storage_object_lock_ready` is deliberately NOT folded into
`object_storage_ready` or into `/readyz`'s `ready`.** Reachability and
compliance capability are different facts. Failing readiness would take the
orchestrator out of rotation for a config problem, and — worse — would make the
live data-plane test *skip* rather than fail, trading one silent
non-verification for another.

**The local bucket was migrated, non-destructively.** `mission-audit-artifacts`
already existed without Object Lock and cannot be upgraded in place. The three
objects in it were backed up (verified by SHA-256 in two locations), `.env` now
sets `OBJECT_STORAGE_BUCKET=mission-audit-artifacts-locked`, the orchestrator's
own `ensure_bucket()` created that bucket **with** Object Lock on startup, and
the objects were restored into it. The old bucket is untouched and is the
rollback path. A `FAILED` audit report now stores with
`X-Amz-Object-Lock-Legal-Hold: ON`, `Mode: COMPLIANCE`, retained to 2026-11-03.
Fresh environments need no override — they get a locked bucket under the default
name automatically.

**Both live test suites authenticate now.** They posted to gateway `/v1/*`
routes with no `x-api-key` while the gateway runs `AUTH_MODE=api_key`, so every
call 401'd whenever the stack was up — and passed trivially when it was down.
The credential is resolved by `tests/services/live_stack_auth.py` (shared, so
the two suites cannot drift apart again) from `LIVE_INTERNAL_SERVICE_API_KEY` →
`INTERNAL_SERVICE_API_KEY` → the repo `.env`, walking upward from `__file__` so
it also resolves from a git worktree where `.env` does not exist. **No
well-known placeholder default** — an unresolvable key skips with a reason
rather than sending a guess and reporting an opaque 401. The header is injected
inside `_request_json`, so no request can go out bare.
`test_live_extended_data_plane_integration.py` also carries module-level
`skipif` markers keyed on gateway reachability, so a run that verified nothing
says so at collection time.

**`test_live_mission_chain_and_artifact_integrity` was asserting the wrong
things, and its prompt could never run.** It waited for `COMPLETE` with a vague
prompt, but intake parks any mission scoring `ambiguity_score >= 0.7` in
`CLARIFYING` for an operator — the test's prompt scored **1.0**, and so did a
much more detailed replacement (the PM only wanted the output separator and
ASCII-vs-Unicode). Chasing an unaskable prompt is the wrong fix: the design
pairs clarifying questions with a *proceed-with-defaults* operator action, so
the test now drives that documented path via
`POST {orchestrator}/missions/{id}/clarify` and then waits for the four
delegation-chain events it actually inspects. With that, it runs a real mission
to `VERIFIED` with a 20-event chain and a real build artifact.

**It also stopped asserting `pod-assignment` and `logicnodes`** — see the open
item in `docs/CURRENT_TODO.md`. Those records are written only by the
**pod-worker** execution path (`assigned_by: "pod-worker"`); a mission driven
in-process by `mission_flow_v2` emits `MISSION_POD_MANAGER_ASSIGNED`, reaches
`VERIFIED`, and produces neither. Asserting them tested which code path happened
to run. The test now asserts the build artifact — the actual deliverable — and
the two-path gap is recorded rather than hidden.

**Full suite: 1929 passed, 4 skipped, 0 failed**, with both live suites green
against a running stack.

### What happened on 2026-08-04

**A BUILD_NEW mission reached `COMPLETE` for the first time.** It took four live
runs of the same CSV-to-JSON CLI mission. Runs 1–3 each stranded at `VERIFIED`
on the same cascade — `artifact_format_matches_contract` raising a false
required failure, which flipped `equivalence.passed` to false, which made
security compliance report "no passing equivalence evidence" and hard-block.
Each run tripped on a *different* string in the contract; the full table is in
`docs/CURRENT_TODO.md` → Current Status.

**Read this before touching `equivalence_verifier.py`:** the first two fixes
each passed their own tests and still failed live, because both were validated
against `acceptance_criteria` alone while `_contract_format_text` reads **five
fields across two contracts**. If you change format detection, test through
`_contract_format_text`, not through one field.

The check's failure modes are asymmetric and that asymmetry drives its design.
A false *positive* is loud — it blocks a correct mission, and you find it in one
run. A false *negative* is silent — it lets a wrong deliverable through, which
is the incident the check was built for. So detection deliberately keys on
narrow, unambiguous signals (a `--flag` token) rather than plausible ones (the
words "output" or "command-line", both of which appear in genuine deliverable
demands). Tests pin both directions; do not relax them to make a mission pass.

**Behavioural equivalence is `skipped` on BUILD_NEW missions and that is
correct.** There is no source to extract LogicNodes from, so there are no
vectors to project. This is a design gap, not a bug, and there is an **open
decision** about it in `docs/CURRENT_TODO.md` (Active Work Queue, Phase 5). Do
not "fix" it by relaxing the gate.

**Two operational fixes landed the same day.** `scripts/compose_topology.py` now
reads Docker's `com.docker.compose.project.config_files` label instead of taking
a census of running services — the census made `CONDENSED` a fallback, so a
crashed `agent-01-pm` or a mid-startup stack read as condensed and the guard
refused a legitimate full-dedicated start, locking the operator out of
restarting the stack it protects.

Also noted that day, **fixed 2026-08-05**:
`tests/services/test_live_extended_data_plane_integration.py` failed with 401
whenever the stack was **up**, because it posted a mission with no credentials,
and passed trivially when the stack was down. See the 2026-08-05 section above.

### What happened on 2026-08-01

A full read-only design-vs-build audit was completed: 143 project-knowledge
design documents compared against live source. **No application code was
changed** during the audit itself. Two new documents were produced and are
canonical for forward work: `docs/DESIGN_VS_BUILD_AUDIT_2026-08-01.md` and
`docs/UPGRADE_RECONCILIATION_PLAN_2026-08-01.md`.

The same session then made **documentation-only** changes to wire them in:
this file, `docs/CURRENT_TODO.md`, and `AGENTS.md`. It also deleted a stale
duplicate of `FULL_APP_REMEDIATION_PLAN_2026-07-05.md` that sat at the repo
root (29,224 bytes) alongside the canonical `docs/` copy (29,701 bytes) — 27
references pointed at `docs/`, 1 at the root orphan. **No `services/`,
`apps/`, `schemas/`, or `deploy/` file was touched.**

**The finding in one sentence:** theFactory is a stronger production system than
the design ever specified and a weaker semantic engine than the design promised
— infrastructure, security, the Protocol Bus, the data plane, the UI, and the
test surface all meet or exceed specification, while the 14→4→1 comprehension
model, semantic Refined-IR, formal equivalence verification, the Doc 30
LogicNode Registry, and binary synthesis were never built.

**Specifically, verified against source:**

- A mission routes to **one pod and one specialist** resolved from
  `requested_target_language` (`mission_flow_v2/phases_build.py:328+`). There is
  no parallel pod fan-out and no cross-language fusion. The four-pod structure
  is routing metadata.
- `schemas/logicnode.schema.json` has **7 required fields** against the designed
  ~30. Everything descriptive lives in a free-form `payload` object.
  `types.in`/`types.out` are always empty.
- `refined_ir.build_refined_ir_module()` emits exactly one `EXTRACT_CONCEPT` op
  per function, sets `purity = "IMPURE" if payload.get("intent") else "PURE"`,
  and writes equivalence vectors that restate the node's own identifiers.
  Schema-valid, semantically empty.
- `equivalence_verifier.py` (693 lines) is a **contract-conformance** checker
  (`"verification_scope": "correctness"`), not behavioural verification. The
  0.0001% tolerance figure from the design corpus is computed nowhere.
- **All six bus lanes now have live producers** (Alpha/Delta in `phases_build.py`,
  Beta in `phases_build.py` + `phases_runtime.py`, Sigma in `knowledge_lake.py`,
  Omega in `phases_delivery.py`, Rho in `llm_delegation/providers.py`) — PBLA is
  genuinely complete. But there is exactly **one consumer** in the whole
  application (`main.py:505`, `{"sigma": _handle_sigma_knowledge_ready}`) and
  every send is fire-and-forget. The bus is an observability spine.
- No LLVM, no compilation, no binary output anywhere — 3 incidental string
  matches across all of `services/`.
- `mission_equivalence_python_execution_enabled` is declared at `settings.py:88`,
  loaded at `:384`, and **read nowhere**. A dead flag.
- `docs/IMPLEMENTATION_STATUS.md` claims "100% feature-complete" and "Refined-IR
  … 100% operational" while `docs/LOGICNODE_SCHEMA.md` in the same repository
  states the RIR projection is templated/synthetic. This is the one genuine
  credibility exposure and Phase 1 closes it (UPG-12).

### Decisions already taken — do not reopen

| # | Decision | Chosen |
|---|---|---|
| D1 | Semantic engine | **Pragmatic middle.** Enrich LogicNodes additively, make RIR extraction real where AST support already exists, build execution-based equivalence for a language subset. **Keep single-specialist routing — no 4-pod fan-out.** |
| D2 | Binary synthesis / LLVM | **Formally killed.** ADR + docs + `AGENT-11-DEPLOY`/`AGENT-09-HW` role strings. Note: retiring binary *synthesis* does **not** remove `toolchains.py` syntax *validation*, which stays. |
| D3 | Protocol Bus | **Commit to EDCP.** Make it load-bearing, starting with a Delta consumer that can gate a mission (new EDCP-02a). |

### Phase 1 — DONE (2026-08-01)

**UPG-10 through UPG-15 are complete.** All five exit criteria met;
per-criterion evidence is in the plan's §4 exit table.

New governing documents:

- **`docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md`** — 19 rows, each an
  Implemented / Superseded / Deferred verdict with source-verified evidence.
  **This document outranks the numbered design corpus.** A Superseded verdict is
  a closed decision; reopening one requires an ADR amendment, not a plan edit.
- **`docs/DESIGN_TRACEABILITY.md`** — all 64 design documents → status →
  implementing module → evidence, plus a table of nine capabilities built with no
  design document at all.

Code changed: **one file, two strings.** `agent_registry.py` — `AGENT-11-DEPLOY`
role is now *"Artifact packaging, delivery, and environment setup"*,
`AGENT-09-HW` is now *"Reserved: target-profile hints for generation (no
compilation role)"*. Ruff clean, 39 registry/persona tests pass, registry loads
with 41 agents intact. No runtime behaviour changed.

**Read the ADR's "Corrections to the audit and plan" section before assuming any
UPG-1x item was skipped.** Three plan premises failed validation against live
code:

1. `agent_personas.py`'s LLVM reference was **kept**. The line describes Julia's
   own LLVM-based compiler and is accurate persona guidance — removing it would
   make the persona less correct, not more honest.
2. UPG-11's "strip binary/LLVM claims from `docs/`" was **already satisfied** by
   the 2026-07-03 documentation audit.
3. UPG-13's "remove the 0.0001% figure from `docs/`" was **already satisfied**.
   Surviving occurrences are meta-references that name the claim in order to
   retire it, plus `docs/evidence/word_doc_extraction_2026-03-08.json` — an
   immutable evidence record, deliberately not rewritten.

**One out-of-scope defect found and fixed:** `IMPLEMENTATION_STATUS.md`
documented `RQCA_ENFORCEMENT_ENABLED` as `false` / "Advisory by default", but
`settings.py:98` and `:228` both default it to **`true`** — flipped by
remediation Phase 0 and never reflected in the doc. A stale shipped *default* is
worse than an overstated status claim: an operator would believe a failing
runtime-QC gate lets missions through when it now blocks them. Corrected, plus
two previously-missing enforcement-flag rows
(`MISSION_SECURITY_COMPLIANCE_ENFORCEMENT_ENABLED`,
`MISSION_EQUIVALENCE_ENFORCEMENT_ENABLED`).

### Phase 2 — PARTIAL (2026-08-01): UPG-21/22/23 done, UPG-20 outstanding

Full backend suite **1768 passed, 5 skipped, 1 xfailed (by design), 0 failed**;
`ruff check` clean across `services/`, `shared_runtime/`, `tests/`; docs
validation passes.

**UPG-22 — the envelope mismatch was a live bug, not cosmetic drift.**
`DEFAULT_EVENT_PRIORITY` is operator-settable (`settings.py:290`) and was written
into the event envelope unvalidated, while
`schemas/event.envelope.schema.json` accepted only `NORMAL|HIGH`. Setting it to a
lowercase Protocol Bus value — the natural thing to type, since the bus `/send`
API uses `low|normal|high|critical` — made **every mission state envelope raise
`ProtocolValidationError`**. Three write sites were affected;
`phases_intake.py` degraded silently to a warning and dropped the partition
envelope rather than raising.

Fixed additively: the schema accepts all six values (nothing previously valid
became invalid), writers normalise through new
`shared_runtime.protocol.to_event_priority` / `to_bus_priority` so output is
byte-identical for every existing configuration, and an unrecognised value raises
at the write site instead of silently downgrading priority. Six regression tests
proven to fail against pre-fix source via `git stash`, with the exact error
`'critical' is not one of ['NORMAL', 'HIGH']`.

**⚠ The plan's correlation-contract premise is wrong — read
`docs/PROTOCOL_ENVELOPES.md` §4 before writing any bus consumer.** UPG-22 states
`correlation_id` carries `mission_id` on both paths. It does not, and **cannot**:
`mcp_server.py` reuses `correlation_id` as both the replay-rejection key (`:624`)
and the dedup key (`:650`), so every bus producer sends a composite —
`alpha-{mission_id}-{agent}`, `delta-{mission_id}-{pod}`,
`beta-{mission_id}-{logicnode}`. A bare `mission_id` would make the second
emission for a mission look like a replay and be silently dropped. **The two
transports join by prefix parse, never by equality.** A Phase 6 Delta consumer
that queries `correlation_id == mission_id` finds nothing, raises nothing, and
appears to work.

**UPG-21 — the flag is still dead, now guarded.**
`mission_equivalence_python_execution_enabled` remains declared at
`settings.py:88`, loaded at `:384`, read nowhere. Phase 2's exit criteria 2 and 5
contradict each other here, so the wiring assertion ships as
`xfail(strict=True)`: green today, and the moment Phase 5 (UPG-51) wires the flag
the unexpected pass turns the suite red on purpose, forcing the marker's removal.
Verified the consumer detector fires correctly when a consumer exists.

**UPG-23 — Pod D relabelled "Mathematical & Functional".** Descriptive strings
only. `pod="Pod D"` is a **routing key** consumed by
`mission_flow_v2/base.py:151` (`"Pod D"` → `"podD"`) and constrained by
`MODELS_AND_DOMAIN_SCHEMA.md`; it is deliberately unchanged. All four pod keys
and their agent counts verified intact after the edit. Pods remain uneven
(A:4, B:5, C:4, D:6 specialists) — renamed, not restructured, per the plan.
`AGENT-36-GO` is **Pod B**, not Pod D.

### Phase 3 — DONE (2026-08-01): LogicNode schema v2

All five exit criteria met. Full backend suite **1796 passed, 0 failed, 0
errors** (up from 1768 — 28 new tests). `scripts/validate_schemas.py` passes,
ruff clean.

**UPG-30** promoted `domain`, `concept`, `confidence`, `source_language`,
`extraction_method` to first-class **optional** properties and reserved
`paradigm`, `purity`, `complexity`, `source_license`, `tags` without populating
them. `payload` still carries every value it carried before — the promoted
fields are **duplicates, not moves**, so nothing reading `payload.domain`
breaks. An absent reserved field means *"not determined"*; do not read a missing
`purity` as `PURE`.

**UPG-31** populated `types.in`/`types.out`, previously always empty.

**⚠ Read this before trusting the plan's Phase 4/5 scoping.** UPG-31 claimed the
data "already exists… this is **wiring, not new analysis**". It wasn't. Every
AST extractor's structured output was **flattened to
`FunctionInfo(name, line, signature)`** on entry to `ExtractionResult`:
`language_extractor.py:348` discarded Python's `arg_types`/`return_annotation`
outright, and the Java converter did the same. Of the seven languages the plan
named, the reality is:

| Language | Type data | Status |
|---|---|---|
| Python | `arg_types` / `return_annotation` | ✅ structured |
| Java | `parameters` / `return_type` (javalang) | ✅ structured |
| Haskell | declared `f :: Int -> Bool` signature | ✅ parsed depth-aware |
| Go | only `receiver` + raw signature | ❌ empty by design |
| OCaml | only `is_recursive` + raw signature | ❌ empty by design |
| Julia, JS/TS | raw signature string only | ❌ empty by design |

Two changes the plan did not anticipate were required: `FunctionInfo` was
**widened additively** (`arg_types`, `return_type`, both defaulted, so every
existing construction site still works), and a **concept→function correlation
step** was added — nodes are built per *concept* while signatures are per
*function*, and the two arrive as sibling lists with no link.
`_enclosing_function_for_line` correlates by position and deliberately refuses
to guess: a concept above the first function gets no types, and a match is only
used when the function actually carries type data, so a mis-correlation cannot
invent types that were never declared. `payload.types_source` records
`ast_signature:<name>` as machine-readable provenance.

`docs/LOGICNODE_SCHEMA.md` documents all of this.

### Phase 4 — DONE (2026-08-01): real Refined-IR projection

All six exit criteria met. Full backend suite **1816 passed, 0 failed, 0
errors** (up from 1796 — 20 new tests).

Refined-IR was "a schema-valid artifact carrying no semantic content". It no
longer is. For AST-backed input it carries real typed signatures, a real
statement-level op stream (a 2-branch function yields
`ASSIGN, BRANCH, ASSIGN, ASSIGN, LOOP, ASSIGN, RETURN` where there was one
synthetic `EXTRACT_CONCEPT`), `purity` from genuine side-effect analysis
(`classify` → `PURE`, `persist` → `IMPURE` with `effects: ["io.filesystem"]`),
and equivalence vectors of concrete typed arguments.

`projection_method` (`templated_v1` / `ast_v1` / `mixed_v1`) makes the artifact
**self-describing** — the honesty no longer lives only in prose in
`LOGICNODE_SCHEMA.md`. **Read that field rather than assuming either path.**

The templated path **remains unchanged** for languages with no recoverable
signature. That is the correct output when nothing was recovered; the
alternative would be inventing content.

**Two additions beyond the plan, both for honesty:**

1. **`purity` gained `UNKNOWN`.** Analysis cannot always decide — a function
   calling something unresolvable could do anything. Reporting it `PURE` would
   be a false claim and `IMPURE` a slander. **Absence of detected effects is
   not evidence of purity**, and that rule is what makes the other two values
   worth trusting. Added to both `rir.fn.schema.json` and the LogicNode schema.
2. **`projection_method` gained `mixed_v1`** at module level, because one source
   file legitimately mixes AST-backed and regex-only extraction and collapsing
   that to either extreme misreports the module. Per-function values remain the
   two the plan specified.

**UPG-42 deliberately does not invent expected outputs.** Vectors carry
concrete typed arguments but `expected: null`, because the expected output is
not knowable until something executes the artifact — fabricating one would
recreate the "vector that can never fail" problem in a new form. Every vector
carries `executable: true|false` so Phase 5 can skip what it cannot run.

**One bug caught by its own test:** Haskell list types (`[Int]`) were being
normalised to an empty string before the bracket check ran, silently dropping
every vector for the language — and Haskell is one of only three whose
signatures are recovered at all.

### Phase 5 — DONE (2026-08-02): behavioural equivalence

All six exit criteria met. Full backend suite **1843 passed, 0 failed, 0
errors**. Mission Control `tsc --noEmit` and lint clean.

`equivalence_verifier.py` answered *does the artifact match its contract*. It is
now joined by a second scope answering *does it actually behave*: Phase 4's
equivalence vectors are executed against the artifact in a sandbox, and a real
pass ratio is recorded. Both scopes render as separate sections in
`EquivalenceReportPanel.tsx`.

**The sandbox is genuinely shared.** The hardened `docker run` invocation was
extracted to `orchestrator/sandbox_exec.py` and **RQCA was refactored to call
it** — this is real sharing, not a parallel copy. `SANDBOX_SECURITY_FLAGS` is
the single source of truth for `--network=none`, `--read-only`, `--cap-drop=ALL`,
`--memory-swap=0`, `--cpus=1`, `no-new-privileges`, and the 64 MB tmpfs; the
workspace is mounted `:ro`. A test asserts both callers reference the same
function object *and* that neither module contains its own `--network=none`
string, so a future copy-paste executor fails the suite rather than passing
review. **Do not add a second `docker run` anywhere.**

**UPG-21's strict-xfail fired exactly as designed**, two phases after it was
written. Wiring `mission_equivalence_python_execution_enabled` in
`phases_delivery.py` made `test_flag_has_at_least_one_consumer` pass
unexpectedly, turning the suite red on purpose. The marker was removed and the
assertion is now live.

> **The honesty rule that shapes this whole report — preserve it.** Phase 4
> deliberately leaves `expected: null` on vectors, so a vector that merely *ran*
> is counted as `executed_without_error`, **never** `passed`. Making those count
> as passes would improve every number on the report and would be a genuine
> regression: it recreates the "check that can never fail" that this phase
> exists to remove. Likewise a sandbox **timeout is recorded as `skipped`, not
> failed** — it means no verdict was produced, so blaming the code under test
> would be wrong. Docker being unavailable records `skipped`, never `passed`.

**Advisory by design (UPG-53).** Behavioural failures do not block delivery.
`attach_behavioural_report` deliberately leaves the correctness
`status`/`passed`/`blocking` fields untouched. Enforcing an unmeasured gate is
how you teach operators to disable gates — measure across ≥20 real missions
first.

**Deliberately not done:** extending beyond Python. Only `_build_driver` is
language-specific so this is additive, but shipping Python-only with an honest
`skipped` beats three half-tested drivers.

### Next action — two options

**Option A: Phase 7** (consolidation, plan §10) — **unblocked**. UPG-70's
LogicNode dependency graph now has Phase 3/4 data to render (pick a library
compatible with the CSP work deferred from the remediation plan — nothing
requiring `unsafe-inline` or `unsafe-eval`). UPG-71 (LangGraph disposition),
UPG-72 (`MISSION_TAXONOMY.md`), and UPG-73 (formally defer Doc 30) are decision
and documentation work.

**Option B: UPG-20** — the last Phase 2 item, and the **hard blocker for Phase 6
(EDCP)**. Needs the live stack.

#### Option B detail — UPG-20

Not started: it needs the live stack, and Docker Desktop was not running on
2026-08-01. Run a **non-trivial** `BUILD_NEW` mission — multiple acceptance
criteria and a required artifact format, *not* another 22-line string reverser —
through to `COMPLETE`, then commit the result as
`docs/evidence/s1_01_live_generation_2026-08-XX.json` and close the gate in
`CURRENT_TODO.md` and `EDCP_PHASE_PLAN.md`'s hard-prerequisites section.

EDCP's own plan is explicit about why this blocks: *"Do not invert control flow on
a pipeline that has not yet been proven to produce real output end to end."*

**Stack operations — both former footguns are now fixed (2026-08-03):**

- **Teardown preserves data.** `make down*` and `scripts/force_stop.py` no
  longer pass `-v`. Deleting volumes is an explicit opt-in: `make down-wipe` /
  `make down-condensed-wipe`, or `force_stop.py --wipe-volumes`. Previously an
  ordinary stop destroyed the mission database, every knowledge store, and the
  operator vault (provider API keys) — it wiped the database once, on
  2026-06-30.
- **Topology mismatch is blocked.** `start_app.bat` now runs
  `scripts/compose_topology.py` before starting and refuses to bring up the
  condensed (base-file-only) form against a live full-dedicated stack. Run
  `make topology` any time to see what is running and the correct paired
  commands for it.
- A live mission still makes real, paid LLM provider calls.

Everything else in Phase 2 is closed, so **Phase 3 (LogicNode schema v2) can
start in parallel** — it has no dependency on UPG-20. Only Phase 6 is blocked.

**Hard dependency to remember:** Phase 6 (EDCP) is blocked by UPG-20 (S1-01
evidence from a non-trivial live mission). The existing S1-01 proof —
`output/mission-ac933664-.../reverser.py`, produced by the 2026-06-30 Phase 13
smoke — is real LLM output with passing tests, but it is a 22-line string
reverser and does not meaningfully exercise the pipeline. EDCP's own plan says:
*"Do not invert control flow on a pipeline that has not yet been proven to
produce real output end to end."*

### Also still open, unchanged by the audit

Phase 4 of the Full Whole-App Remediation Plan
(`docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §7 — Electron/Windows installer)
remains outstanding and is **orthogonal** to the upgrade plan. Either can go
first; three sub-decisions there (§7.2 Docker-lifecycle-on-quit, §7.4 Docker
Desktop/WSL2 prerequisite story, §7.7 auto-start) still need explicit user
sign-off. Detail preserved below.

---

## Previous handoff (2026-07-06) — Full Whole-App Remediation, Phases 0–3

Phase 3 of the Full Whole-App
Remediation Plan (`docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §6) is
**done and verified** — documentation accuracy, closing findings #15/#28.
`docs/METRICS_SOURCE_MODULES.md` (rewritten 2026-07-03 as part of the prior
documentation audit) turned out to omit four entire source modules, not just
four metric names as the finding's headline suggested:
`llm_delegation/metrics.py`, `services/pod-worker/pod_worker/main.py`,
`services/audit-worker/audit_worker/main.py`, and
`services/agent-runtime/agent_runtime/main.py` had zero coverage, even though
the four specifically-named metrics (`pod_worker_task_latency_seconds`,
`agent_runtime_task_latency_seconds`, `audit_worker_task_latency_seconds`,
`factory_llm_tokens_total`) were already live in real alert rules
(`deploy/monitoring/prometheus/rules/thefactory-alerts.yml`) and Grafana
dashboards. Rather than patch in just those four names and leave the other
real metrics in the same modules undocumented, added complete
source-verified metric tables for all four modules — matching this doc's own
stated "verified against source" standard — bringing 23 additional metrics
under documentation that weren't listed before (e.g.
`pod_worker_tasks_processed_total`, `agent_runtime_circuit_open_total`,
`factory_llm_estimated_cost_usd_total`). Also fixed the stale casing
mismatch (finding #28): both `docs/METRICS_SOURCE_MODULES.md:19`'s
`factory_missions_active` label values and `orchestrator_metrics.py:57`'s
inline comment said lowercase `queued`/`running`/`verified`, but the real
`_ACTIVE_GAUGE_STATES` set (`orchestrator_metrics.py:79`) and the
`MissionStuckInRunning` alert query both use uppercase — both now read
`QUEUED`/`RUNNING`/`VERIFIED`, comment-only change with no behavior
difference. Verified: `scripts/validate_documentation.py` passes (76
metadata files, 119 link files, 17 docstring files validated), `ruff check`
clean on the one touched `.py` file. This was a documentation-only phase
with no code-behavior changes, so no test suite or Docker rebuild was
needed — matching the plan's own §6 exit criteria (docs validation only).
**Next action: Phase 4** (Electron/Windows installer buildout) — see
`docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §7. Three sub-decisions there
need explicit user sign-off before implementation, not an assumed default:
Docker-lifecycle-on-quit behavior (§7.2), the Docker Desktop/WSL2
prerequisite story (§7.4), and an auto-start decision (§7.7).

Before that: Phase 2 of the Full Whole-App
Remediation Plan (`docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §5) was
**done and verified** — frontend UI correctness/accessibility/data-integrity
fixes, closing findings #3/#11/#12/#13/#14/#21/#22 plus the `global-search.tsx`
dead-code cleanup (CSP `unsafe-inline` is explicitly deferred to Phase 4 per
the plan). Alerts "Acknowledge"/"Mark Resolved" (finding #3) turned out to
need real new backend surface, not just wiring: `_build_operational_alerts()`
(`orchestrator/routes/operations.py`) recomputes every alert fresh from live
health signals on every request with no incident-record table at all — per
user decision, added a Redis-backed ack overlay (`alert:ack:{alert_id}`,
24h TTL) plus a new `POST /internal/operations/alerts/{alert_id}/state`
endpoint (proxied via api-gateway) so acknowledge/resolve now survives a
refresh instead of reverting. Stale-response races (finding #11) fixed with
a monotonic request-id ref in `useArtifactData.ts`, `missions/detail/page.tsx`,
and `missions/page.tsx` — a response for a mission the user has since
navigated away from can no longer overwrite the mission actually being
viewed. Non-semantic clickable `<div>`s (finding #12) fixed: the
`missions/output/page.tsx` path card converted to a real `<button>`; the
`protocol-bus/page.tsx` event `<tr>` (can't be a `<button>` — it contains
`<td>`s) got `role="button"`/`tabIndex={0}`/`onKeyDown`, already covered by
an existing global `[role="button"]:focus-visible` CSS rule. Guided-tour
keyboard trap (finding #13) fixed and verified live in a browser: the card
had `tabIndex={-1}` but nothing ever called `.focus()`, so its
Escape/Arrow/Enter handler never received a single keyboard event — added
focus-on-open/step-change plus previous-focus restore on close. Five literal
`\uXXXX` escape sequences rendering as raw text (finding #14 named one,
four more of the identical bug were found and fixed alongside it) in
`missions/detail/page.tsx`. Chat session retention (finding #21) — per user
decision, added a time-based expiry (30 days) alongside the existing
30-session count cap, extracted to a testable `lib/chat-session-retention.ts`.
Inconsistent 401/403 handling (finding #22) — extracted `chat/page.tsx`'s
`isOperatorAuthError`/`operatorRecoveryMessage` heuristic into
`lib/operator-auth-error.ts` plus a shared `<OperatorAuthErrorAction>`
component, applied consistently across chat/missions/missions-detail/alerts/
protocol-bus; `app/unlock/page.tsx` was already a legitimate intentional
redirect to Settings, not a dead stub — left unchanged. Verified: full
Mission Control Vitest suite (113 tests), `tsc --noEmit`, `npm run build`,
full backend suite, `ruff check .` all clean; guided-tour keyboard behavior
and page rendering verified live in a browser (frontend dev server only —
the backend stack wasn't running, so live-data flows like the actual
Alerts acknowledge round-trip and the fast-navigation stale-response race
could not be exercised end-to-end; say so explicitly rather than claim full
live coverage). **Next action: Phase 3** (documentation accuracy) — see
`docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §6.

Before that: Phase 1 of the Full Whole-App
Remediation Plan (`docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §4) is
**done and verified** — script/tooling safety guardrails, closing findings
#6/#7/#8/#9/#10/#19/#20/#24/#25/#27/#29. Every destructive script now
defaults to a safe preview and requires an explicit `--execute` (or
`-Execute`/`-Yes`) flag to actually mutate anything: `run_automated_dr_drill.py`
(real drill was previously the default), `operator_route_auth_matrix_qualification.py`
and `langgraph_postgres_recovery_qualification.py` (both previously
force-recreated/restarted live containers unconditionally — CI's
`qualification.yml` was updated to pass `--execute` explicitly, since that
job's stack is genuinely disposable), `execute_git_history_scrub.py`/`.ps1`
(removed the `--force` override to git-filter-repo, restoring its own
fresh-clone safety check), `restore_postgres.ps1` (added a confirmation
prompt, pre-restore snapshot, and manifest/checksum verification —
`run_automated_dr_drill.py`'s automated path passes `-Yes` since its own
`--execute` already represents the confirmation), and
`normalize_document_headers.py` (which had **zero** safety gate at all —
discovered the hard way mid-fix when a `--help` typo triggered its real,
unguarded write path against the live `docs/` tree, clobbering 64 files'
headers; reverted with user sign-off, then fixed properly). Also fixed:
the duplicate `Makefile` `demo:` target (renamed the shadowing one to
`demo-live:`), `force_stop.py`'s condensed-vs-full-dedicated teardown
mismatch (now detects topology via `docker ps` before choosing the
teardown form), a documented compose-pairing self-contradiction in
`OPERATIONS_RUNBOOK.md`'s own "Recovery Steps" section, weak well-known
default secrets in the auth-matrix qualification script (`operator-key`
removed with no fallback; `dev-oidc-shared-secret` now auto-generated
per run since the script self-injects it into the target gateway anyway),
atomic writes added to `generate_agent_service_keys.py`/
`generate_postgres_tls_certs.py` (plus a `--force` guard on the latter)
and `rotate_secrets.sh` (rotates a scratch copy, then atomically `mv`s it
into place — a crash mid-loop no longer leaves `.env` with a mix of old
and new secrets), `dr_drill.ps1`'s native-command exit codes now checked
(PowerShell's `-Stop` preference doesn't catch `curl.exe`/`psql`
failures automatically, which is why `passed=$true` was previously
unconditional), and `run_demo_mission.py`'s hardcoded placeholder API-key
fallback removed (fails fast with a clear message instead). **Also fixed
in passing:** `operator_route_auth_matrix_qualification.py`'s
`_load_env_file()` used to unconditionally overwrite `os.environ` from the
repo's `.env` at import time — confirmed as the actual root cause of the
one "pre-existing, unrelated" test flake noted at the end of Phase 0
(`test_prompt_guard_mode_defaults_to_block`); now returns a local dict
instead of mutating global state, and the full backend suite is 100% clean.
Verified: full suite passes, `ruff check .` clean, `scripts/validate_documentation.py`
passes, all three compose profile forms (`dev`, `prod`, `full-dedicated-agents`)
resolve, and every changed script's dry-run/refuse-to-overwrite path was
exercised directly (in an isolated scratch directory for the ones that
touch real files, never against the live stack). **Next action: Phase 2**
(frontend UI correctness/accessibility) — see
`docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §5.

Before that: Phase 0 of the Full Whole-App
Remediation Plan (`docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §3) is
**done and verified** — the five production-runtime-default hardening items
(findings #1/#2/#18/#23/#26). All five now fail fast at process start when
`ENVIRONMENT=production` resolves an insecure default, mirroring the
existing CORS-wildcard precedent in `api_gateway/main.py`:
`RQCA_ENFORCEMENT_ENABLED` (compose default flipped `false`→`true`, plus a
new `load_settings()` guard), MinIO/object-storage default credentials
(`docker-compose.prod.yaml` now requires `MINIO_ROOT_USER`/
`MINIO_ROOT_PASSWORD`/`OBJECT_STORAGE_ACCESS_KEY`/`OBJECT_STORAGE_SECRET_KEY`
via compose's `:?` required-var syntax, plus a matching `load_settings()`
guard against the literal `minioadmin`/`minioadmin123` strings),
`GATEWAY_ADMIN_BYPASS` (warn-only → `RuntimeError` in production),
`CORS_ALLOW_ORIGINS` (now overridable via env var in the base compose file,
with a required explicit value in the prod overlay), and agent-runtime's
`SERVICE_API_KEY` (removed the `"worker-key"` literal fallback; fails fast
at import if unset). Verified: full backend suite passes (only the one
pre-existing, order-dependent `test_prompt_guard_mode_defaults_to_block`
flake remains, confirmed identical on the pre-Phase-0 baseline and unrelated
to this work); `ruff check .` clean; `docker compose config` merge
re-verified for both the dev and prod overlays (dev resolves
`RQCA_ENFORCEMENT_ENABLED: "true"`; the prod overlay fails the merge outright
if `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` are unset, and resolves cleanly
with real values supplied); rebuilt `deploy-orchestrator`/`deploy-api-gateway`
images and confirmed all three code-level guards raise `RuntimeError` inside
the rebuilt containers under production settings, and stay silent under dev
defaults. agent-runtime's own image lives in the separate
`docker-compose.full-dedicated-agents.yaml` overlay (41-container profile,
not built by default) — that fix was instead verified via a subprocess-level
regression test (`tests/services/test_agent_runtime_service_api_key_guard_unit.py`)
that imports the module in a fresh process with `SERVICE_API_KEY` unset and
confirms the fail-fast. Two regression-test files added (production runtime
guards, agent-runtime key guard) plus fixes to 3 existing test files that
either leaked `SERVICE_API_KEY` globally at import time (a bug introduced and
then fixed within this same pass) or needed to explicitly pin the new
guards' env vars to stay self-contained against ambient environment state.
Every new/changed test proven to fail against the pre-fix code via `git
stash`. **Next action: Phase 1 (script/tooling safety guardrails)** — see
`docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §4 and `docs/CURRENT_TODO.md`'s
Active Work Queue.

Before that: a full
whole-application, read-only code review — every part of theFactory, not
just the Windows/Electron packaging layer that was the initial scope ask.
**This was a findings-only pass: nothing was fixed.** The complete report
is `docs/FULL_APP_CODE_REVIEW_FINDINGS_2026-07-05.md` — read that file, not
just this summary, before starting any remediation. It covers five slices
(Mission Control frontend UI, Electron/Windows packaging, the dedicated
`agent-runtime` service, deploy/infrastructure/CI, and `scripts/`) plus a
dedicated §8 enumerating what's needed to turn this into a real Windows
Electron installer with working install/uninstall, grounded in the fact
that **the app currently runs as a web app**: `start_app.bat` starts the
Docker Compose backend plus a plain Next.js standalone server opened in the
default browser via `Start-Process` — not the packaged Electron build,
which is a separate, parallel path with its own currently-broken build
pipeline. Headline findings: the compose-level `RQCA_ENFORCEMENT_ENABLED`
default (`false`, in `deploy/docker-compose.yaml:326`) silently reverts
this session's own hardened code-level default (`true`) back off in every
profile including production, and no override exists in
`docker-compose.prod.yaml`; the production overlay never sets MinIO
credentials either, so it falls back to `minioadmin`/`minioadmin123`; the
packaged Electron app's 14 `app/api/*` routes (vault, session,
review/approve, gateway proxy, etc.) cannot function at all today because
the Electron build's static-export mode physically hides `app/api` at
build time to work around a Next.js incompatibility
(`scripts/build-electron.mjs`); and the Mission Control Alerts page's
"Acknowledge"/"Mark Resolved" actions only mutate local React state with no
backing API call, so they silently revert on refresh. **The next step for a
fresh session is to read the findings doc in full and write one ordered
remediation/upgrade plan covering both the bug backlog and the
Electron/Windows installer buildout** — deliberately not started yet, since
the user wants to review findings before that plan is written. See
`docs/CURRENT_TODO.md`'s Active Work Queue for the tracked next-step entry.

Before that: a full
documentation audit and reduction of the entire `docs/` set (plus root/app
docs), done in two passes. **Deleted 3 docs that described entirely
fictional systems** (`EQUIVALENCE_VERIFIER.md`, `IS_AGENT.md`,
`PORT_COORDINATOR_AND_LOGICNODE_SCHEMA.md` — classes/functions that were
documented but never implemented; the real modules are now documented
accurately in `SUPPORTING_MODULES.md`). **Archived 8 completed point-in-time
plans/incident reports** to `docs/archive/2026-07-03/`, and split
`HANDOFF_CURRENT.md`/`CURRENT_TODO.md`'s ever-growing "Latest/Recently
Completed" sections into their own history files there too. **Found two
critical inaccuracies**: `LICENSE_STRATEGY.md` claimed MIT with quoted MIT
text — the repo is actually Dual AGPL-3.0/Commercial with a mandatory CLA
(the README license badge was also wrong, now fixed); `DATA_CLASSIFICATION_
POLICY.md` described a fictional 4-tier taxonomy that didn't match the real
`DataClassification` enum. **7 more docs were substantially rewritten**
after a verification pass found they described entire class-based APIs
that don't exist (`AGENT_SCALING_AND_HEARTBEAT.md`, `LLM_DELEGATION.md`,
`PROMPT_REGISTRY_AND_ASSETS.md`, `LLM_SAFETY_AND_DOCUMENT_PARSER.md`,
`METRICS_SOURCE_MODULES.md`, `OBSERVABILITY_STACK.md`,
`DEPENDENCY_ABSORPTION_DOCTRINE.md`). **One real code bug was found
incidentally and fixed**: the api-gateway tagged sensitive-input missions
with the invented string `"TIER_2_RESTRICTED"`, which never matched the
orchestrator's real enum value `"TIER_2_SENSITIVE"` — `security_compliance.
py`'s classification checks silently never recognized these missions as
anything but unclassified. See "Documentation Audit and Reduction
(2026-07-03)" below for the full list.

Before that: a security
review of the Mission Control frontend's Next.js API routes
(`apps/mission-control/app/api/`, ~6.1k lines including `lib/server/`).
**Critical finding, confirmed by two independent review passes: the vault
CRUD routes (`GET`/`POST`/`DELETE /api/vault`, `POST /api/vault/test`) had
zero authentication.** `isAuthorizedVaultRequest` (in `vault/auth.ts`)
existed, was tested, and clearly intended to gate these routes, but was
dead code — never imported or called by the actual route handlers. Any
unauthenticated local request could list every vault slot, overwrite
`OPERATOR-API-KEY`/provider keys with attacker-controlled values, delete
them outright, or probe whether a slot was populated. **Also critical: the
`/api/gateway/[...path]` catch-all proxy — the path the browser client uses
for nearly all backend traffic, including mission creation — had no
operator-session gate at all**, unlike every sibling privileged route
(`local/*`, `repo/*`); it injects the operator/internal API key itself
regardless of caller identity, so any request reaching the Next.js server
could act with that privilege. Both fixed by wiring in the existing
`isAuthorizedVaultRequest`/`requireOperatorRequestSession` helpers,
respectively — the same pattern already used correctly by every other
privileged route in this app. See "Mission Control API Routes Review
(2026-07-03)" below for the full list, including several findings judged
consistent with this app's established single-operator-role design (not
fixed as anomalies).

Before that: a review
of `shared_runtime/` (the security/crypto library imported by every backend
service — ~1.7k lines across `agent_auth.py`, `agent_keys.py`,
`crypto_keystore.py`, `crypto_signing.py`, `prompt_guard.py`, `pii_guard.py`,
`atomic_io.py`, `protocol.py`, `errors.py`, `logging_config.py`). Two
findings fixed: (1) `get_build_artifact` (orchestrator) only re-verified an
artifact's `verified` flag when a cryptographic `signature_record` was
present; for artifacts where signing failed at build time (a real, broad
`except Exception` swallows that failure), `verified: true` was a
write-time-only assertion never re-checked against the currently stored
bytes — a corrupted/tampered `artifact_text` would report verified forever.
Now independently re-hashes and compares against the recorded digest when
no signature exists, exactly mirroring the signature-verification branch.
(2) The orchestrator's diagnostic-bundle env-var sanitizer
(`system_maintenance.py`) only excluded names containing `_KEY`/`_SECRET`/
`_PASSWORD` — real vars like `VAULT_TOKEN`/`VAULT_ROLE_ID` carried no
matching substring, and connection-string vars like `POSTGRES_URL`/
`REDIS_URL` embed a plaintext password in the URL's userinfo segment
regardless of the var name. Expanded the name denylist and added
value-level userinfo redaction for any URL-shaped value. See "shared_runtime
Review (2026-07-03)" below for the full list, including several
lower-severity findings (a documented "best-effort" RIR-module signature
gate, a low-blast-radius TOCTOU race in first-time signing-key creation, a
stale docstring) left as accepted/deferred.

Before that: a deep code
review of the verification/compliance gate layer
(`equivalence_verifier.py`, `port_coordinator.py`, `security_compliance.py`,
`rqca_agent.py`). Most significant finding, confirmed by two independent
review passes: **`MISSION_SECURITY_COMPLIANCE_ENFORCEMENT_ENABLED` and
`RQCA_ENFORCEMENT_ENABLED` both defaulted to `false`** — the security-
compliance gate (hardcoded-secret detection) and the RQCA runtime-QC gate
always ran and always recorded their real verdict, but a *failing* required
check only produced a `"warned"` status, not a `"blocked"` one, unless an
operator explicitly opted in to enforcement. A mission with a detected
hardcoded secret, or one that failed its runtime QC check, proceeded straight
to delivery by default. **User-confirmed product decision: both now default
to `true`** (mirrors the `PROMPT_GUARD_MODE` default change from the
api-gateway review) — operators can still opt out via env var for staged
rollouts. Also fixed: a PORT two-phase extraction-phase re-entrancy gap
(`_prepare_specialist_plan`'s extraction branch was the only sibling branch
in that function with no `_chain_event_exists` guard — a second invocation
while `port_phase` was still `"extraction"` would re-run two LLM calls and
mint fresh non-deterministic extraction results) and a security-compliance
report idempotency gap (the report was unconditionally rebuilt and
re-signed on every completion-gate retry, overwriting the prior
`signature_record`, and its audit event fired again on every retry since it
wasn't deduplicated the way the chain-event append was — now cached and
reused like the existing RQCA report cache). See "Verification & Compliance
Gates Review (2026-07-03)" below for the full list, including several
disclosed-but-unfixed advisory-only heuristic limitations (regex-based
secret/dangerous-pattern detection is trivially evadable by generated code,
and a Docker-unavailable RQCA fallback reports `DRY_RUN`/advisory rather
than blocking) that are architectural tradeoffs, not quick patches.

Before that: a deep code
review of the pod-worker service (`services/pod-worker/pod_worker/`, ~5.1k
lines across `main.py`, `language_extractor.py`, `ast_extractor.py`,
`js_ast_extractor.py`, `java_ast_extractor.py`, `concept_catalog.py`,
`refined_ir.py`, `tracing.py`). Most significant finding: **`_consumer_loop`'s
catch-all exception handler never acknowledged or DLQ'd a failed stream
entry** — since nothing in this loop ever `XCLAIM`/`XAUTOCLAIM`s pending
entries, an unexpected exception (e.g. an httpx error deep in
`_handle_running_mission`) permanently orphaned the message in the consumer
group's pending-entries list: never processed again, never visible in the
DLQ, no operator signal beyond a single log line. Fixed to route to the DLQ
and acknowledge, matching the pattern already used for the four
explicitly-handled exception types. Also fixed a companion bug in
`_write_dlq` itself: a transient Redis failure during the DLQ write was only
logged, while the caller still unconditionally acknowledged (and thus
permanently discarded) the original entry — `_write_dlq` now returns
whether the write actually succeeded, and callers only acknowledge on
success. Also fixed: a `refined_ir.py` bug where a LogicNode payload missing
`node_name` produced the literal string `"None"` as the function name
instead of falling back to the concept name; a JS/TS function-detection
regex that silently dropped every paren-less single-arg arrow function
(`x => x + 1`, a common JS idiom) from extraction; a `PythonAstExtractor`
inconsistency where the regex pass truncated source to 512 KB but the AST
pass received the untruncated original, bypassing the size guard and
producing line numbers past what the regex pass ever saw; and a Java
static-import edge case where a malformed/partial `javalang` parse could
inject an empty-string entry into the imports list. See "pod-worker Review
(2026-07-03)" below for the full list, including a deferred architectural
finding (agent execution runs synchronously inside the async event loop,
blocking the consumer/heartbeat loops during CPU-bound or blocking work) that
needs a scoped design decision rather than a quick patch.

Before that: a deep code
review of `services/api-gateway/api_gateway/main.py` (~2.8k lines) — the
single most significant finding: **10 mission/builder routes had zero caller
authentication** (`create_mission`, `get_mission_pod_assignment`,
`get_mission_chain_trace`, `create_pm_feature_contract`, mission
logicnodes/knowledge/knowledge-graph/audit-reports/audit-artifacts/
audit-events/build-artifacts/build-artifact/artifact-download, and
`create_builder_preview`) — any caller could read or create missions,
including prompts and source code, for any `mission_id` with no credentials
at all. All now require `_require_reader_access`. Also fixed: a hybrid-mode
`_require_operator_access` bypass (granted access on any non-empty
`X-API-Key` with zero validation), an X-Forwarded-For rate-limit bypass (any
anonymous caller could spoof a fresh IP per request to defeat IP-based rate
limiting — now gated behind an explicit `GATEWAY_TRUST_PROXY_HEADERS`
opt-in), a permissive `PROMPT_GUARD_MODE` default (was `"log"`, now
`"block"` — OWASP LLM01 prompt-injection attempts are now rejected out of
the box instead of merely logged while the mission proceeds), an Anthropic
`max_tokens`/`thinking_budget` mismatch (max_tokens was hardcoded to 1200
while thinking_budget is caller-configurable up to 65536, so any request
with a large budget was rejected by Anthropic on every call), a Gemini-3
model-detection gap (hardcoded `3.1-`/`3.5-` prefixes missed plausible names
like `gemini-3.0-pro` and the bare `gemini-3`), and an OpenAI refusal-content
extraction gap (`refusal`-type content blocks carry text under `refusal`,
not `text`). See "api-gateway Review (2026-07-03)" below for the full list
of what was checked and why.

Before that: a deep code
review of the agent orchestration core (`agent_base.py`, `agent_registry.py`,
`agent_personas.py`, `agent_integrations.py`, `agent_scaling.py`,
`is_agent.py`, `dependency_absorption.py`, `aim_generator.py`). The single
most significant finding of the entire review effort so far: **AIM
(Application Intelligence Map) source-code extraction — `function_count`,
`class_count`, `concept_count`, and `detected_imports`, used for every
`ANALYZE_ONLY`/`PORT`/`DEBUG_REPAIR`/`SECURITY_HARDEN`/`REDUCE_DEPENDENCIES`
mission — has been silently non-functional in the actual deployed
orchestrator container this whole time.** Two independent bugs stacked: (1)
`aim_generator.py`'s path arithmetic for importing the `pod_worker` code-
extraction package resolved correctly in local dev but to the filesystem
root inside the built container, since only `services/orchestrator`'s
*contents* are copied to `/app` there (never verified against the actual
container until now); (2) even when reachable, the extraction code filtered
for a concept `domain == "import"` that the real pattern catalog never
produces (real import concepts are tagged `"module_patterns"`), instead of
using `ExtractionResult`'s own dedicated, correctly-populated `imports`
field. Both silent failures meant every AIM extraction call returned an
empty/zero fallback with only a swallowed-exception warning log, no error
surfaced anywhere. Fixed both, plus the Dockerfile now ships `pod_worker`
into the image and it was verified working *inside a rebuilt container*, not
just locally. Also fixed: a scaling-decision idempotency gap
(`_prepare_specialist_plan` could mint a fresh scaling decision with new
random partition IDs on re-entry, orphaning already-emitted/completed
partition work) and a Java-detection false-negative in `is_agent.py`. See
"Agent Orchestration Core Review (2026-07-02)" below for the full list.

Before that: a deep code review of the orchestrator storage layer
(`storage_missions.py`, `storage_artifacts.py`, `storage_agents.py`,
`storage_pods.py`, `storage_logicnodes.py`, `models.py`) — the DB layer
underneath every mission-flow phase. Found and fixed a real concurrency bug:
`insert_agent_action_event` read the latest hash-chain digest and inserted
the next event as two unsynchronized statements, so two concurrent events
for the same `project_id` could both chain onto the same predecessor,
silently forking the tamper-evident audit chain. Fixed with a per-project
advisory lock. See "Storage Layer Review (2026-07-02)" below for the full
list of what was checked and why.

Before that: a deep code review of the Mission Flow v2 lifecycle driver
(`mission_flow_v2/`) and the LLM delegation layer (`llm_delegation/`), finding
and fixing 7 real backend bugs — most seriously, a driver re-invocation bug
(triggered by every orchestrator restart while a mission is in flight) that
silently regenerated and overwrote a mission's `feature_contract`/
`mission_charter` with a fresh, non-deterministic LLM call. See "Mission Flow
v2 + LLM Delegation Review (2026-07-02)" below for the full list.

Before that: a code review of the Mission Control UX lock-in commits (PM
clarification, progress visibility, artifact output folder discovery,
Continue with PM) plus fixes for every finding it surfaced, including a
critical stuck-mission regression, a missing-auth gap on the new
local-filesystem routes, and a suppressed PM clarifying question, plus a
follow-up closing pass that fixed a `language.ts` tie-break bug. See
"Post-Review Hardening (2026-07-02)" below.

Before that: the Mission Control UX lock-in itself (PM clarification, progress
visibility, artifact output folder discovery, and Continue with PM). The
next live action for that thread is still to restart the app and run a real
browser mission asking for a modern Angular Snake game with `start.bat`, then
verify that clarification/defaults, progress indicators, output-folder
actions, and follow-up context all behave correctly. Evidence:
`docs/evidence/mission_control_ux_lockin_2026-07-02.md`.

Previous high-priority context: Phases 0-3 of the findings-remediation work
(pod-audit fix, Beta fix, language-content-signature check, unconditional
Compliance) are all committed and offline-verified, and the live stack was
rebuilt healthy, but a fresh live mission proof remains pending.

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

The latest Mission Control UX lock-in adds PM clarification cards/defaults,
Live Progress status/next-action indicators, guarded local output-folder status
and open actions, VS Code launch, and follow-up mission context loading. The
running stack was not restarted during this lock-in pass; the post-restart
browser mission proof remains the next action.

---

## Active Work

### Full Whole-App Code Review Remediation (Phases 0-3 done; Phase 4 remaining)

The read-only findings report is
`docs/FULL_APP_CODE_REVIEW_FINDINGS_2026-07-05.md`; the ordered execution
plan derived from it is `docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md`
(4 phases, each grounded in an external standard or industry practice
where a genuine design decision was needed — OWASP secure-defaults
guidance for the compose/gateway hardening phase, the dry-run-by-default
pattern from Terraform/Ansible/kubectl for the destructive-script phase,
and the community-standard embedded-standalone-server pattern for
reconciling Next.js's two build modes inside Electron, including a
2024 Microsoft SmartScreen policy change that steers code signing toward
Azure Artifact Signing over an EV certificate). **Phases 0, 1, 2, and 3 are
done and verified** — see the top of this file for the full list of fixes
and verification evidence. Phase order: Phase 0 (done), Phase 1 (done),
Phase 2 (done), Phase 3 (done), Phase 4 (Electron/Windows
installer buildout — the only phase with real architecture decisions, done
last so its rebuild inherits every other phase's fixes). **Next action for
a fresh session: start Phase 4** (Electron/Windows installer buildout) — see
`docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §7 for exact scope.
Three product-scope decisions in Phase 4 (§7.2 Docker-lifecycle-on-
quit behavior, §7.4 Docker Desktop/WSL2 prerequisite story, §7.7 auto-start
decision) are explicitly flagged in the plan as needing user sign-off before
implementation, not inferred defaults. See `docs/CURRENT_TODO.md`'s Active
Work Queue entry for the same tracked item.

### Mission Control UX Lock-In (implemented; restart/browser proof pending)

Implementation complete:

- PM feature-contract normalization now asks clarifying questions for
  underspecified interactive applications/games instead of immediately creating
  a launchable plan.
- Mission Control chat renders those questions as decision cards with
  recommended defaults, editable answers, and a proceed-with-defaults action.
- Mission Detail now has a Live Progress panel that distinguishes waiting,
  blocked, retrying, stale, working, and finished states with user-facing next
  actions.
- Generated Output and Build Artifacts panels show the local
  `output/<mission_id>` path, file status, Copy Path, Open Folder, and VS Code
  actions.
- Continue with PM loads prior mission summary, build artifacts, delivery
  summary, and output-folder status, then carries that context in follow-up
  mission metadata.
- generated-output artifact gating now blocks expected generated-output
  missions from completing without a durable generated output artifact.

Validation passed:

- Mission Control focused Vitest: 36/36.
- Mission Control `npm run build`.
- Mission Control `npm run lint`.
- Focused orchestrator PM/build-artifact pytest: 19/19.
- Compose full-dedicated service graph resolution.
- Docker rebuilds for `deploy-mission-control:latest` and
  `deploy-orchestrator:latest`.

Next action: after restart, run the Angular Snake browser mission and confirm
the four user-facing behaviors above in the real UI.

### Repository ZIP Import Migration (active implementation)

The current repo-intake migration is tracked in
`docs/REPO_ZIP_IMPORT_MIGRATION_PLAN.md`. The implementation has started in
Mission Control:

- Phase 1 is complete: `apps/mission-control/app/api/repo/archive.ts` provides
  safe ZIP indexing/read helpers and `archive.test.ts` covers root stripping,
  traversal rejection, subdirectory filtering, text reads, and binary detection.
- Phase 2 is complete locally: `apps/mission-control/app/api/repo/import/route.ts`
  accepts multipart ZIP uploads, validates source refs/subdirectories, indexes
  files without GitHub API calls, rejects oversized uploads, and returns ZIP
  metadata with archive truncation signals.
- Route tests now focus on ZIP intake: accepted archive, missing archive,
  non-ZIP rejection, invalid source ref, and operator-session enforcement.
- Phase 3 is complete locally: `apps/mission-control/app/api/repo/review/route.ts`
  accepts multipart ZIP review requests, requires `archive_sha256`, re-indexes
  the uploaded archive with required selected-path inclusion, reads selected file
  text from normalized ZIP paths in one pass, and returns the existing review
  artifact/source-bundle shape without GitHub API calls.
- Phase 4 is complete locally: `apps/mission-control/app/(shell)/repo/page.tsx`
  now renders a ZIP file selector, archive metadata summaries, FormData-backed
  import/review calls, and review-gate reset behavior for archive scope changes.
- Validation passed: Mission Control `npm run lint`, full `npm run test`
  (87/87), focused `npm run test -- app/api/repo` (22/22), and targeted
  Playwright repo-intake e2e.

Important boundary: repo ZIP launch still uses the approved source bundle only.
Mission index guard, repo knowledge ingestion, and PM/pod-worker repository
context loading remain the next migration phases.

### Verification & Reporting Hardening (Phase 1-3 complete; verification backlog remains)

A live "Modern Neon Pong" mission, created through the Mission Control chat
intake on 2026-06-29, reached `COMPLETE` and produced a working artifact, but
exposed three gaps that automated verification did not catch: the deliverable was
a `.js` file rather than the contracted single self-contained HTML file; non-ASCII
characters were corrupted (mojibake); and the run was mislabeled `LEGACY V1`
despite executing the Mission Flow v2 pipeline.

The full plan is `docs/archive/2026-07-03/UPDATE_PLAN_VERIFICATION_HARDENING_2026-06-29.md`. Phase 1 is
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
staged initiatives: Stage 1 PBLA (`docs/archive/2026-07-03/PROTOCOL_BUS_LANE_ACTIVATION_PLAN.md`,
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
- **Real bug found + fixed + unit-tested + committed (`4445b6b`):**
  `generate_pod_audit_verdict` lower-cased `pod_name` before matching
  mixed-case `_POD_AUDIT_AGENTS` keys, so every non-Pod-A mission's audit (and
  its PBLA-01 Delta emission) silently misrouted to `AGENT-13-PODA-AUDIT`.
  Fixed via a case-insensitive lookup; regression test covers all 4 pods.
- **Real bug found, fixed, and committed (`07883d7`): Beta (PBLA-03) never
  fired across all 20 missions.** Root cause confirmed — but the original
  diagnosis above named the wrong function. `generated_output` is actually set
  in `_prepare_specialist_plan` (`phases_build.py`), not
  `_prepare_specialist_assignment` — a different, later function in the same
  file, confirmed by tracing the actual `lifecycle.py` state-machine call
  order (`pod_assigned → _prepare_specialist_assignment → specialist_assigned
  → _prepare_specialist_plan`). The fix adds the Beta emission there. The
  original `_prepare_fusion` (`phases_runtime.py`) call was **not** removed —
  it remains the legitimate fallback-path emission for missions whose first
  codegen attempt didn't yield usable output; the shared
  `mission_has_generated_output` guard keeps the two call sites mutually
  exclusive by construction, so no new idempotency tracking was needed.
- **2 of 20 missions (C, R) generated the wrong language entirely** (both
  produced Python that simulates the target language instead of real C/R
  source) and still reached `COMPLETE`. **Fixed and committed (`a63dfaf`)** —
  but the original diagnosis above was also wrong: a required check
  (`_check_language_alignment`) already existed. The real gap is that it
  compares `generated_output["language"]` (self-reported by the same LLM call
  that wrote the code) against the requested language, so a specialist that
  silently substitutes Python can still label its output correctly and the
  check can never catch it. The new `_check_language_content_signature`
  inspects the actual code text for unambiguous Python tells, scoped to target
  languages least likely to be confused with Python (c, cpp, r, go, rust,
  shell) — verified against the real C/R battery artifacts on disk (correctly
  fails) and real Go/Rust/C++ artifacts (correctly passes, no false positive).
- **Also fixed and committed (`b70d711`), beyond the original findings scope:**
  `AGENT-08-COMPLIANCE`'s activation was a literal `"COMPLIANCE"` keyword
  substring match that essentially never fired for ordinary prompts (findings
  §6.3). Per the user's explicit choice among 3 presented options, Compliance
  now fires unconditionally at delivery like Security/VC/Tester, via a new
  `generate_compliance_assessment` function and `MISSION_COMPLIANCE_ASSESSMENT_COMPLETE`
  event.
- PBLA-05 (operations-snapshot lane surfacing) remains optional/undone.
- **All four fixes above passed the full `tests/services/` suite** (1311
  passed, 5 skipped, 0 failed) and ruff on every touched file, run after each
  commit.

**Environment note:** after the battery, `stop_app.bat` →
`scripts/force_stop.py` → `make down` ran `docker compose down -v`, which
deleted the `postgres-data`/`redis-data` volumes (mission/chain-trace DB gone;
generated code artifacts survived — `output/` is a host bind-mount, not a
volume). A live-restart cascade also surfaced a Postgres credential mismatch
and an `api-gateway` internal-auth key that resolves empty at runtime.
**Both now look resolved** after rebuilding all images (correct two-file
compose form) and bringing the stack up fresh: `db_ready: true` with no
`FATAL` auth errors (Finding 3), and a clean `404` instead of the old `503
gateway internal auth is not configured` when fetching build-artifacts for an
old mission ID (Finding 4 — strong evidence, not yet proven via a fresh live
mission). Full remediation plan: `docs/archive/2026-07-03/STACK_REMEDIATION_PLAN_2026-07-01.md`.
See "Findings Remediation (Phases 0-4)" below for the full current state.

#### Stage 1 — Protocol Bus Lane Activation (PBLA)

A standalone initiative, fully specified in
`docs/archive/2026-07-03/PROTOCOL_BUS_LANE_ACTIVATION_PLAN.md` and tracked in `CURRENT_TODO.md`. The
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

### Full Whole-App Remediation Plan Phase 3 (2026-07-06): documentation accuracy

Executed `docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §6, closing findings
#15/#28. `docs/METRICS_SOURCE_MODULES.md` (rewritten 2026-07-03) omitted
four entire source modules, not just the four metric names the finding
headline named: `services/orchestrator/orchestrator/llm_delegation/metrics.py`,
`services/pod-worker/pod_worker/main.py`,
`services/audit-worker/audit_worker/main.py`, and
`services/agent-runtime/agent_runtime/main.py` had no coverage at all, even
though `pod_worker_task_latency_seconds`, `agent_runtime_task_latency_seconds`,
`audit_worker_task_latency_seconds`, and `factory_llm_tokens_total` were
already live in real alert rules
(`deploy/monitoring/prometheus/rules/thefactory-alerts.yml`) and Grafana
dashboards. Added complete, source-verified metric tables for all four
modules rather than patching in just the four named metrics — matching this
doc's own stated "verified against source" standard — bringing 23 additional
real metrics under documentation (e.g. `pod_worker_tasks_processed_total`,
`agent_runtime_circuit_open_total`, `factory_llm_estimated_cost_usd_total`,
`factory_llm_requests_total`). Also fixed the stale casing mismatch (finding
#28): `docs/METRICS_SOURCE_MODULES.md:19`'s `factory_missions_active` label
values and `orchestrator_metrics.py:57`'s comment both said lowercase
`queued`/`running`/`verified`; the real `_ACTIVE_GAUGE_STATES` set
(`orchestrator_metrics.py:79`) and the `MissionStuckInRunning` alert query
both use uppercase — fixed both to `QUEUED`/`RUNNING`/`VERIFIED`
(comment-only change in the `.py` file, no behavior difference). Verified:
`scripts/validate_documentation.py` passes (76 metadata files, 119 link
files, 17 docstring files, 1 migration guide, 3 architecture diagram sets),
`ruff check` clean on the one touched Python file. Documentation-only phase
— no test suite run or Docker rebuild needed, matching the plan's own §6
exit criteria. Next: Phase 4 (Electron/Windows installer buildout).

### Full Whole-App Remediation Plan Phase 2 (2026-07-06): frontend UI correctness/accessibility

Executed `docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §5, closing findings
#3/#11/#12/#13/#14/#21/#22 plus the `global-search.tsx` dead-code cleanup
(CSP `unsafe-inline` explicitly deferred to Phase 4 per the plan). See the
top of this file ("If you are picking this up cold") for the full per-item
list. Two findings needed a genuine decision rather than a mechanical fix,
both resolved with explicit user sign-off: Alerts persistence required new
backend surface (a Redis-backed ack overlay plus a new
`POST /internal/operations/alerts/{alert_id}/state` endpoint, since the
alerts have no incident-record table — they're recomputed fresh from live
health signals on every request) and chat session retention (a time-based
30-day expiry alongside the existing 30-session count cap, rather than
building new server-side encrypted storage). The guided-tour keyboard-trap
fix was verified live in a browser (`document.activeElement` confirmed
receiving focus, Escape correctly dismissed and restored prior focus) —
previously the card had `tabIndex={-1}` with no `.focus()` call, so its
keyboard handler never received a single event. Verified: full Mission
Control Vitest suite (113 tests), `tsc --noEmit`, `npm run build`, full
backend suite, `ruff check .` — all clean. Live-data flows (the actual
Alerts acknowledge round-trip, the fast-navigation stale-response race)
were not exercised end-to-end since the backend stack wasn't running during
this pass — noted explicitly rather than claimed as verified. Next: Phase 3
(documentation accuracy).

### Full Whole-App Remediation Plan Phase 1 (2026-07-06): script/tooling safety guardrails

Executed `docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §4, closing findings
#6/#7/#8/#9/#10/#19/#20/#24/#25/#27/#29. See the top of this file ("If you
are picking this up cold") for the full per-item list. Highlights: every
destructive script now defaults to a safe preview requiring an explicit
`--execute`/`-Execute`/`-Yes` flag to mutate anything (DR drill, both
qualification scripts, git-history-scrub, Postgres restore); CI's
`qualification.yml` explicitly passes `--execute` since that job's stack is
disposable; `normalize_document_headers.py` had **zero** safety gate at
all — discovered mid-fix when a stray invocation clobbered 64 docs' headers
(reverted with explicit user sign-off, then fixed with a `--execute` gate
plus atomic writes); `force_stop.py` now detects condensed-vs-full-dedicated
topology via `docker ps` before choosing the teardown form; found and fixed
`operator_route_auth_matrix_qualification.py`'s `_load_env_file()`
unconditionally overwriting `os.environ` from `.env` at import time — the
actual root cause of the "pre-existing, unrelated" test flake
(`test_prompt_guard_mode_defaults_to_block`) noted as left-untouched at the
end of Phase 0; the full backend suite is now 100% clean (0 failures).
Verified: full suite, `ruff check .`, `scripts/validate_documentation.py`,
all three compose profile forms resolve, and every changed script's
dry-run/refuse path exercised directly. Next: Phase 2 (frontend UI
correctness/accessibility).

### Full Whole-App Remediation Plan Phase 0 (2026-07-05): production runtime defaults hardened

Executed `docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §3, closing findings
#1/#2/#18/#23/#26. See the top of this file ("If you are picking this up
cold") for the full per-item list and verification evidence (full backend
suite, `ruff check .`, `docker compose config` merge re-verification for
both dev and prod overlays, and in-container guard verification against the
rebuilt `deploy-orchestrator`/`deploy-api-gateway` images). One pre-existing,
unrelated test flake (`test_prompt_guard_mode_defaults_to_block`, an
order-dependent full-suite-only failure) was confirmed identical on the
pre-Phase-0 baseline at the time — **later root-caused and fixed during
Phase 1** (see above), not left permanently unaddressed.

### Full Whole-App Remediation Plan (2026-07-05): 4-phase ordered plan, validated against external standards, execution not started

`docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` turns the findings below into
an ordered execution sequence. Each phase cites the findings it closes and,
for genuine design decisions, the external standard consulted — this is a
sequencing/justification document only, no implementation.

- **Phase 0 — harden production runtime defaults** (findings #1/#2/#18/#23/
  #26): `RQCA_ENFORCEMENT_ENABLED` compose default, MinIO default
  credentials, `GATEWAY_ADMIN_BYPASS` warn-vs-fail-fast inconsistency,
  hardcoded `CORS_ALLOW_ORIGINS`, agent-runtime weak default secret.
  Grounded in [OWASP Top 10:2025 A02 Security Misconfiguration](https://owasp.org/Top10/2025/A02_2025-Security_Misconfiguration/)
  and this codebase's own existing fail-fast precedent (the adjacent
  CORS-wildcard check already in `api_gateway/main.py`).
- **Phase 1 — script/tooling safety guardrails** (findings #6/#7/#8/#9/#10/
  #19/#20/#24/#25/#27/#29): inverts every destructive script to
  dry-run-by-default, following the Terraform/Ansible/`kubectl --dry-run`
  pattern; the git-history-scrub fix aligns with `git-filter-repo`'s own
  fresh-clone safety model.
- **Phase 2 — frontend UI correctness/accessibility** (findings #3/#11/#12/
  #13/#14/#21/#22 plus CSP `unsafe-inline` and `global-search.tsx`
  dead-code): straightforward, no architecture decisions; the CSP
  nonce-vs-`unsafe-inline` trade-off is flagged as best resolved together
  with Phase 4, once dynamic rendering is required anyway.
- **Phase 3 — documentation accuracy** (findings #15/#28).
- **Phase 4 — Electron/Windows installer buildout** (findings #4/#5/#16/
  #17 plus the §8 gap list), last, since it's the only phase with real
  architecture decisions and its rebuild should inherit every earlier
  phase's fixes. Core decision: replace static export with the same
  `output: 'standalone'` Next.js server the Docker/web-app path already
  runs, launched as an Electron-main-process child process — the
  community-standard pattern for this exact Next.js/Electron problem
  ([DoltHub](https://www.dolthub.com/blog/2024-09-11-building-an-electron-app-with-nextjs/)),
  resolving the build-mode split and the broken-API-routes finding in one
  change. Code signing: Azure Artifact Signing over an EV certificate,
  since a 2024 Microsoft SmartScreen policy change means EV no longer
  bypasses the warning any better than OV
  ([Microsoft Learn](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)).
  Three sub-decisions explicitly flagged for user sign-off rather than an
  assumed default: Docker-lifecycle-on-quit behavior, the Docker
  Desktop/WSL2 prerequisite story, and an auto-start decision.
- Full reference list (11 external sources) in the plan doc's §10.
- **Not done in this pass:** no implementation. Next action: execute
  Phase 0 — see "Full Whole-App Code Review Remediation" under Active Work
  above.

### Full Whole-App Code Review (2026-07-05): read-only, five slices, ~30 findings, remediation plan pending

A full, read-only code review of the entire application, requested after an
initial Electron/Windows-only review plan was expanded to cover "every part
of the app." Explicit user instruction: **findings-only, don't fix anything
as you go**, so a single ordered upgrade plan can be written afterward as a
separate step. Full report: `docs/FULL_APP_CODE_REVIEW_FINDINGS_2026-07-05.md`.

- **Established ground truth first:** the app currently runs as a web app —
  `start_app.bat` starts the Docker Compose backend, then opens a plain
  Next.js standalone server in the default browser — not as a packaged
  Electron app. The Electron build is a separate, parallel path.
- **Slice A — Mission Control frontend UI:** 13 findings. Most notable:
  Alerts page "Acknowledge"/"Mark Resolved" only mutate local React state
  with no API call (reverts on refresh, misleads operators); mission/detail/
  artifact data fetches have no stale-response guard (wrong mission's data
  can render under a new mission's header after fast navigation); a literal
  `✕` renders as 6 raw characters instead of "✕" in mission detail
  (unquoted JSX text); non-semantic clickable `<div>`s with no keyboard
  access in two places; the guided-tour dialog never calls `.focus()`. No
  XSS vector found anywhere (no `dangerouslySetInnerHTML` in scope).
- **Slice B — Electron/Windows packaging:** the single most architecturally
  significant finding of the whole review — **the packaged Electron app's
  14 `app/api/*` routes (vault, session, review/approve, gateway proxy,
  etc.) cannot function at all**, because Next.js static export (required
  for the Electron build) is incompatible with dynamic App Router routes;
  `scripts/build-electron.mjs` physically renames `app/api` out of the way
  before building, proving the authors already know this. Also: zero
  Docker-lifecycle code anywhere in the Electron main process (the Docker
  check is cosmetic — a non-blocking dialog, window loads regardless);
  release artifacts are unsigned (no `CSC_LINK`/cert anywhere); NSIS has no
  dependency checks and no custom install/uninstall scripts;
  `deleteAppDataOnUninstall` doesn't touch the real vault at
  `~/.thefactory/vault.json`. See §8 of the findings doc for the 7-point gap
  list on what a real one-click installer needs.
- **Slice C — `services/agent-runtime/`:** clean overall (real circuit
  breaker, bounded retry/backoff, correct consumer-group ack semantics).
  One finding: `SERVICE_API_KEY` defaults to the well-known literal
  `"worker-key"` if unset.
- **Slice D — Deploy/infra/CI:** most notable — `deploy/docker-compose.
  yaml:326` sets `RQCA_ENFORCEMENT_ENABLED: ${RQCA_ENFORCEMENT_ENABLED:
  -false}`, silently reverting this session's own hardened code-level
  default (`true`) back to `false` in every profile including production,
  confirmed via `docker compose config` merge; the production overlay never
  overrides MinIO credentials either, falling back to `minioadmin`/
  `minioadmin123`. Also: `GATEWAY_ADMIN_BYPASS=true` in prod only warns
  instead of failing fast like the adjacent CORS-wildcard check;
  `docs/METRICS_SOURCE_MODULES.md` (rewritten in the prior documentation
  audit) omits 4 real in-use metrics. Dockerfile hygiene and CI security
  scanning (pip-audit/bandit/Trivy/gitleaks) both confirmed clean.
- **Slice E — `scripts/` (58 scripts) and `Makefile`:** most notable — a
  duplicate `demo:` Makefile target silently shadows the intended one; the
  real (non-dry-run) DR drill and two qualification scripts default to
  destructive live-container/auth mutation with no confirmation gate; the
  git-history-scrub script unconditionally rewrites history with no
  dry-run/backup; `OPERATIONS_RUNBOOK.md`'s own recovery steps violate its
  own compose-file-pairing warning. ~25 scripts reviewed with no material
  findings; no SQL injection or `shell=True` command-injection found
  anywhere.
- Four background review agents (one per slice A/B/D/E) ran in parallel,
  each explicitly instructed read-only; Slice C was a direct 3-file
  self-review. All four agents returned substantive, non-placeholder
  findings on this run.
- `scripts/validate_documentation.py` passes with the new findings doc
  included.

### Documentation Audit and Reduction (2026-07-03): fictional docs deleted, license/classification errors fixed, one real code bug found

A full inventory-and-accuracy audit of theFactory's documentation, requested
to reduce the doc set to what a production application should ship and
ensure the survivors reflect current code. Two passes: an initial
inventory/classification/reduction pass, then a targeted verification pass
over the ~40 docs not deeply checked in the first pass.

- **Inventory:** 105 "active" docs (89 under `docs/`, 16 root/app/GitHub-
  template files) plus 212 already-segregated historical files under
  `docs/archive/`/`docs/evidence/`.
- **Deleted 3 docs with no salvageable content** — they described systems
  that were never implemented: `EQUIVALENCE_VERIFIER.md` (a fictional
  `EquivalenceReport`/3-plane AIM-comparison system; the real
  `equivalence_verifier.py` is a deterministic per-check contract
  validator), `IS_AGENT.md` (a fictional "Integration Specialist" agent
  class; the real `is_agent.py` seeds Knowledge Lake bootstrap docs),
  `PORT_COORDINATOR_AND_LOGICNODE_SCHEMA.md` (a fictional Redis ephemeral
  port allocator; the real `port_coordinator.py` orchestrates PORT-mission
  two-phase extraction — and its LogicNode-schema half duplicated content
  already correctly superseded by `LOGICNODE_SCHEMA.md`). Also dropped
  `diagrams/ENTERPRISE_ARCHITECTURE_DIAGRAMS.md` (redundant with
  `ARCHITECTURE_DIAGRAMS.md`, with unverified claims). The real
  `equivalence_verifier.py`/`is_agent.py`/`port_coordinator.py` modules are
  now documented accurately as new sections in `SUPPORTING_MODULES.md`.
- **Archived 8 completed, point-in-time plans/incident reports** to
  `docs/archive/2026-07-03/`: `AUDIT_PLAN.md`, the 2026-06-30 findings/
  session-log pair, `PROTOCOL_BUS_LANE_ACTIVATION_PLAN.md` (PBLA Stage 1,
  now code-complete), `PROTOCOL_BUS_MISSION_BATTERY_PLAN.md`,
  `UPDATE_PLAN_VERIFICATION_HARDENING_2026-06-29.md`,
  `STACK_REMEDIATION_PLAN_2026-07-01.md`,
  `AGENT_PROTOCOL_BUS_DATA_SYSTEMS_PLAN.md`.
- **Pruned this file and `CURRENT_TODO.md`** — both had accumulated months
  of dated "Latest/Recently Completed" entries (1504 and 1120 lines).
  Trimmed to current status plus the most recent review sweep; older
  entries moved to `docs/archive/2026-07-03/{HANDOFF_CURRENT,CURRENT_TODO}_
  OLDER_HISTORY.md`.
- **Critical: `LICENSE_STRATEGY.md` claimed the repo was MIT-licensed**,
  quoting MIT text and describing a forward-looking "open-core" plan built
  on that premise. The real root `LICENSE` is a **Dual AGPL-3.0/Commercial**
  license with a patent notice covering the core architecture, and a CLA
  that is **already mandatory today** (not "may be added later" as the doc
  claimed). Rewrote the doc from the real `LICENSE` file, and fixed the
  README license badge, which was also wrong (said MIT, linked to the real
  dual-license file).
- **Critical: `DATA_CLASSIFICATION_POLICY.md` described a fictional 4-tier
  `PUBLIC`/`INTERNAL`/`CONFIDENTIAL`/`RESTRICTED` taxonomy** with an
  elaborate retention/access-control matrix, none of which exists in code.
  Rewrote grounded in the real `DataClassification` enum
  (`TIER_0_PUBLIC`/`TIER_1_INTERNAL`/`TIER_2_SENSITIVE`/`TIER_3_REGULATED`)
  and its actual (much thinner) enforcement — a single binary
  regulated-vs-not gate in `security_compliance.py`, not a four-tier
  handling framework.
- **7 more docs substantially rewritten** after a verification pass found
  they described entire class-based APIs, config keys, and exception types
  that don't exist, while omitting the real (differently-designed) modules:
  `AGENT_SCALING_AND_HEARTBEAT.md` (no `AgentScaler`/`HeartbeatService`
  classes — both real modules are function-based), `LLM_DELEGATION.md` (no
  `LLMDelegator`/`PROVIDER_REGISTRY`/Ollama offline mode — the real package
  is 12 flat function-based modules with a real circuit breaker in
  `health.py`), `PROMPT_REGISTRY_AND_ASSETS.md` (no `PromptRegistry`
  class — real assets are flat `{prompt_id}.v{N}.json` files with a real
  SHA-256 integrity-manifest feature the old doc omitted entirely),
  `LLM_SAFETY_AND_DOCUMENT_PARSER.md` (no `LLMSafetyFilter`/
  `LocalOnlyViolation` — omitted the real `shared_runtime/prompt_guard.py`/
  `pii_guard.py` it was supposed to document), `METRICS_SOURCE_MODULES.md`
  and `OBSERVABILITY_STACK.md` (documented ~30 metric and 6 alert names
  that would return zero results against real Prometheus/Grafana — e.g.
  `GatewayDown`/`HighErrorRate` instead of the real `ApiGatewayDown`/
  `ApiGateway5xxRateHigh`), `DEPENDENCY_ABSORPTION_DOCTRINE.md` (added a
  "Current Implementation Status" section distinguishing the real 6-outcome
  classifier from the doc's aspirational 7-step decision hierarchy and
  Shadow Equivalence Mode, since most of this doc is intentionally
  forward-looking policy, not a description of shipped behavior).
- **Several minor fixes**: `SENSITIVE_CODE_HANDLING_POLICY.md`'s fictional
  `pii_guard.py` tier-branching and LLM-routing-override claims;
  `COMPLIANCE_EVIDENCE_MAPPING.md`'s nonexistent `deploy/redis/certs/*`
  path; `LOCAL_FIRST_COMPLIANCE_PLAN.md`'s three already-shipped items
  still marked "Outstanding" (`shared_runtime/atomic_io.py`,
  `shared_runtime/errors.py`, Electron crash handling); `SETTINGS_
  REFERENCE.md`'s 3 undocumented settings fields;
  `KNOWLEDGE_LAKE_AND_EMBEDDINGS.md`'s `index_documentation()` dead-code
  claim; `DEPLOYMENT_DR_PLAYBOOK.md`'s internal check-count inconsistency
  (said 17 in one place, 13 in another; the real count is 23, matching the
  README badge); `dr_validation_runbook.md`'s RTO/MTTR conflation (15 min
  vs. the canonical 30 min), missing compose-file pairing flags (the exact
  `docker compose down -v` gotcha documented in project history), and a
  stale all-"NOT RUN" drill schedule; `dedicated_agent_canary_runbook.md`'s
  outdated compose profile invocation.
- **One real code bug found incidentally during the audit, not a doc fix:**
  the api-gateway's `_build_sensitive_input_scan` handler tagged
  sensitive-input missions with the invented string `"TIER_2_RESTRICTED"`,
  which never matched the orchestrator's real `DataClassification` enum
  value (`"TIER_2_SENSITIVE"`). This didn't crash anything (a different,
  defensively-guarded metadata key is what `storage_missions.py` actually
  parses into the enum), but `security_compliance.py`'s classification-
  based checks silently never recognized an api-gateway-tagged mission as
  anything but unclassified. Fixed to write `"TIER_2_SENSITIVE"` directly,
  with a regression test proving the mismatch via `git stash` and a
  cross-service consistency assertion (`DataClassification(value)` must
  not raise).
- Ran `scripts/validate_documentation.py` after every batch of changes —
  passing throughout. Full backend suite re-run after the code-bug fix:
  1348 passed, 5 skipped. `ruff check` clean. `api-gateway` Docker image
  rebuilt and the fix verified inside the container.

### Mission Control API Routes Review (2026-07-03): vault and gateway proxy had zero authentication

A security review of the Mission Control frontend's Next.js API routes
(`apps/mission-control/app/api/`, ~6.1k lines including `lib/server/`) — the
final "everything else" slice of the systematic backend review effort. Two
parallel finder passes covered the whole slice (local/repo/gateway routes,
and vault/session/review/operator/pm/builder routes + `lib/server/`); one
sub-agent needed relaunching after an initial premature/placeholder result.

- **Critical, confirmed by two independent passes: vault CRUD routes had
  zero authentication.** `GET`/`POST`/`DELETE /api/vault`
  (`vault/route.ts`) and `POST /api/vault/test` (`vault/test/route.ts`)
  imported only the vault storage functions — never
  `isAuthorizedVaultRequest` (defined in `vault/auth.ts`, which correctly
  supports either a timing-safe `x-vault-admin-key` header compare or an
  operator session) or `requireOperatorRequestSession`. `isAuthorizedVaultRequest`
  is unit-tested in `auth.test.ts` but was dead code — never wired into any
  route handler. Any unauthenticated local caller could: list every vault
  slot (`GET`), overwrite any secret including `OPERATOR-API-KEY` with an
  attacker-controlled value (`POST`), delete any secret outright (`DELETE`),
  or probe whether a slot was populated and get back its format-validity
  verdict without ever unlocking the app (`test`). Fixed by wiring
  `isAuthorizedVaultRequest` into all four handlers, returning 401 when
  unauthorized.
- **Critical: the gateway catch-all proxy had no operator-session gate at
  all.** `/api/gateway/[...path]` (`gateway/[...path]/route.ts`) is the path
  the browser client uses for nearly all backend traffic (mission creation,
  every `/v1/*` and `/internal/*` call) — unlike every sibling privileged
  route (`local/open-vscode`, `local/open-output-folder`,
  `local/output-folder-status`, `repo/import`, `repo/review`, all of which
  call `requireOperatorRequestSession` as their first line), this route
  never checked the caller's session at all. It injects the
  operator/internal API key itself from the vault regardless of caller
  identity, so any request reaching the Next.js server — not just requests
  from within the unlocked app UI — could act with that privilege,
  including auto-injecting live Gemini/OpenAI/Anthropic provider keys into
  mission-creation payloads. Fixed by adding the same
  `requireOperatorRequestSession` gate used by every sibling route, as the
  first statement in the shared `proxy()` handler.
- **Investigated and judged consistent with established design, not fixed
  as anomalies:** `operator/mission-state`, `pm/feature-contract`,
  `review/approve`, and `review/verify` all resolve to a single shared
  privileged backend credential (vault `OPERATOR-API-KEY` or the
  server-wide `INTERNAL_SERVICE_API_KEY`) after passing the operator-session
  gate, rather than forwarding any per-caller credential — but this matches
  this app's single-operator-role session model consistently across every
  privileged route, not a deviation isolated to these four; treating it as
  a bug would require a larger multi-operator authorization redesign, not a
  targeted patch. The `MISSION_CONTROL_BYPASS_AUTH`/`OPERATOR_SESSION_BYPASS`
  dev-bypass flags are explicit opt-in env vars with no default-on path,
  matching the same accepted pattern as `GATEWAY_ADMIN_BYPASS` on the
  backend side. `builder/review`'s file-content embedding into responses is
  constrained to a hardcoded root list (no path traversal) and gated by the
  operator session; a preexisting-secret-in-repo hygiene concern, not a
  logic bug in the route itself. ZIP archive handling (`repo/archive.ts`)
  was independently re-verified as correctly hardened against zip-slip and
  decompression bombs (bounded entry count, bounded total/per-file bytes,
  in-memory streaming with no filesystem extraction target to traverse
  into) — the prior "Harden repo ZIP import flow" fix holds up under this
  pass. `open-vscode/route.ts`'s `cmd.exe` command-string construction is a
  code smell (manual quote-escaping rather than argv-array passing used
  everywhere else) but not currently exploitable, since the only path
  reaching it is validated against a strict `mission-\w+` regex upstream —
  flagged for future hardening if that validation is ever loosened, not
  patched in this pass.
- Confirmed after fixing: grepped every `route.ts` in the API surface for
  the auth-check call; only `session/unlock` and `session/logout` lack one,
  which is correct by design (unlock is the auth entry point itself; logout
  must be callable to clear a session without first requiring one).
- Every fix has a regression test independently proven to fail against the
  pre-fix code via `git stash`. Frontend suite: 104 passed (20 test files).
  `tsc --noEmit` clean.

### shared_runtime Review (2026-07-03): artifact re-verification gap and diagnostic-bundle secret leak

A security/correctness review of `shared_runtime/` (~1.7k lines: `agent_auth.py`,
`agent_keys.py`, `crypto_keystore.py`, `crypto_signing.py`, `prompt_guard.py`,
`pii_guard.py`, `atomic_io.py`, `protocol.py`, `errors.py`,
`logging_config.py`, `__init__.py`) — the shared security library imported
by every backend service (orchestrator, api-gateway, pod-worker). Two
parallel finder passes covered the whole slice.

- **Fixed an artifact re-verification gap.** `get_build_artifact`
  (`orchestrator/routes/internal.py`) only recomputed an artifact's
  `verified` flag from a real cryptographic check when a `signature_record`
  was present in the stored record. `build_artifacts.py` sets
  `verification["verified"] = True` unconditionally at build time and only
  *adds* a `signature_record` if signing succeeds — a broad `except
  Exception` swallows signing failures (keystore unavailable, disk full,
  etc.) with just a log line. For any artifact that was never signed, the
  `verified: true` flag was therefore a write-time-only assertion, never
  independently re-checked against the artifact's currently stored bytes —
  a corrupted or tampered `artifact_text` would report `verified: true`
  forever. Fixed by adding a fallback branch: when no signature exists but
  a `artifact_digest_sha256`/`bundle_digest_sha256` was recorded, re-hash
  the currently stored `artifact_text` and compare via
  `hmac.compare_digest`, exactly mirroring the signature-verification
  branch's re-check-at-read-time behavior.
- **Fixed a diagnostic-bundle secret leak.** `MaintenanceManager.create_diagnostic_bundle`
  (`system_maintenance.py`) sanitized environment variables for
  `POST /internal/maintenance/diagnostics` bundles by excluding only names
  containing `_KEY`/`_SECRET`/`_PASSWORD` — real vars shipped in this
  repo's own `.env.example` (`VAULT_TOKEN`, `VAULT_ROLE_ID`) carried no
  matching substring and were included verbatim, and connection-string vars
  (`POSTGRES_URL`, `REDIS_URL`, `LANGGRAPH_CHECKPOINTER_POSTGRES_URL`) embed
  a plaintext password in the URL's userinfo segment regardless of the var
  name (`postgresql://postgres:CHANGE_ME_...@postgres:5432/...`). Fixed by
  expanding the name-based denylist (`_TOKEN`, `_CREDENTIAL`, `_ROLE_ID`
  added) and adding value-level regex redaction of any `scheme://user:pass@`
  userinfo segment, applied to every retained env var regardless of name.
- **Investigated and refuted / deferred as accepted design tradeoffs:**
  RIR-module signature verification failures are explicitly documented as
  "best effort" and non-fatal (`phases_runtime.py`'s
  `_verify_rir_module_signatures`, `pod_worker/refined_ir.py`'s
  `write_refined_ir_module`) — logged but never block the mission; this
  looks intentional given the docstring's own framing, not an oversight,
  but is worth revisiting now that signing is load-bearing for compliance
  reports too. `crypto_keystore.load_or_create_signing_key` has a low-blast-
  radius TOCTOU race if two processes race to create a signing key against
  an empty shared keystore path simultaneously — each artifact's public key
  travels with its own signature record so per-artifact verification still
  succeeds either way; no consumer was found that trusts a keystore-derived
  public key independent of the embedded one, so practical impact looks
  limited. The plaintext signing-key fallback (`ARTIFACT_SIGNING_KEY_SOURCE=auto`)
  is permitted by default off any `ENVIRONMENT` string other than exactly
  `"production"` — matches documented dev/staging convenience intent, a
  soft string-match gate rather than a hard one, not changed. A stale
  docstring in `pii_guard.py` referenced a `scan_envelope()` function that
  doesn't exist — fixed to list the real exported functions. `atomic_io.py`
  writes rely on `tempfile.mkstemp`'s default 0600 mode (which `os.replace`
  preserves) rather than setting permissions explicitly — reviewed and
  confirmed this is not actually loosened by umask on POSIX (umask can only
  remove bits from a requested mode, never add them), so the originally
  suspected world-readable-diagnostic-bundle risk doesn't materialize in
  practice; left unchanged.
- Every fix has a regression test independently proven to fail against the
  pre-fix code via `git stash`. Full backend suite: 1348 passed, 5 skipped.
  `ruff check` clean on all touched files. Rebuilt `deploy-orchestrator`,
  `deploy-api-gateway`, and `deploy-pod-a-worker` (all three import
  `shared_runtime`) and verified the fixes directly inside the rebuilt
  containers.

### Verification & Compliance Gates Review (2026-07-03): permissive-by-default gates, plus 2 confirmed idempotency bugs

A correctness/security review of theFactory's PORT-mission verification and
compliance-gate layer: `equivalence_verifier.py` (693 lines),
`port_coordinator.py` (252 lines), `security_compliance.py` (333 lines),
`rqca_agent.py` (792 lines). Two parallel finder passes covered the whole
slice (equivalence + port coordination, and security-compliance + RQCA),
with a third targeted re-run after the first compliance/RQCA pass returned
a premature placeholder with no real findings.

- **Critical, confirmed by two independent review passes: the
  security-compliance and RQCA enforcement flags defaulted to `false`,
  making both gates warn-only rather than blocking out of the box.**
  `security_compliance.py`'s `should_block = bool(failed_required) and
  (enforcement_enabled or regulated_context)` and `phases_runtime.py`'s
  `blocked = rqca_enforcement_enabled and qc_verdict == "FAIL"` both only
  block when the corresponding `Settings` flag is explicitly enabled (or,
  for security-compliance, when the mission is separately tagged
  `REGULATED`/`TIER_3_REGULATED`). With default settings, a mission whose
  generated code contains a hardcoded secret (`_check_secret_patterns`
  fails, `required=True`) or whose runtime QC verdict is `FAIL` still gets
  `security_compliance_ready=True`/`runtime_qc_ready=True` and proceeds
  straight to delivery — `status` reads `"warned"`, not `"blocked"`, with no
  distinct audit-event signal to distinguish "detected but not enforced"
  from "no issue found" without reading into the stored report body.
  **User-confirmed product decision (mirrors the `PROMPT_GUARD_MODE` default
  change from the api-gateway review): both
  `MISSION_SECURITY_COMPLIANCE_ENFORCEMENT_ENABLED` and
  `RQCA_ENFORCEMENT_ENABLED` now default to `true`.** Operators can still
  opt out via env var for staged rollouts.
- **Fixed a PORT two-phase extraction re-entrancy gap.** `_prepare_specialist_plan`'s
  extraction branch (`mission_flow_v2/phases_build.py`) was the only
  sibling branch in that function with no `_chain_event_exists` guard —
  every other expensive/state-mutating branch checks a completion chain
  event before re-running (a comment immediately below this exact branch,
  for the scaling-decision fix, explicitly documents this same bug class
  having been found and fixed there already). Mission state stays at
  `specialist_assigned` for the entire extraction+generation two-phase
  flow, so nothing in the transition-based dedup protects a second
  invocation while `port_phase` is still `"extraction"` — it would re-run
  two LLM calls (`generate_aim`, `generate_specialist_plan`), mint fresh
  non-deterministic `port_source_aim`/`port_source_logicnodes`, and append
  a duplicate `MISSION_PORT_EXTRACTION_COMPLETE` chain event. Fixed with the
  same guard pattern used by every sibling branch.
- **Fixed a security-compliance report idempotency gap.** `_prepare_security_compliance_report`
  (`mission_flow_v2/phases_delivery.py`) had no cache check, unlike its RQCA
  sibling (`_prepare_runtime_qc`, which explicitly caches `runtime_qc_report`
  with a documented rationale for exactly this scenario). Since this
  completion-gate preparer re-runs its entire body on every retry (e.g. an
  orchestrator restart recovering a mission still blocked by a later gate),
  the report was unconditionally rebuilt and re-signed every retry —
  overwriting the prior `signature_record` — and `record_audit_event` fired
  again on every retry since it (unlike the chain-event append immediately
  above it) was never deduplicated. Fixed with the same cache-and-reuse
  pattern as `_prepare_runtime_qc`.
- **Investigated and refuted / deferred as architectural, not quick-patch,
  items:** `equivalence_verifier.py`'s acceptance-criteria/concept-coverage
  checks are disclosed, advisory-only (`required=False`) keyword heuristics
  — a real false-negative risk in principle, but cannot itself flip a
  `passed`/`blocking` verdict since the load-bearing checks
  (`generated_output_exists`, `artifact_format_matches_contract`,
  `language_content_signature`, etc.) are separate and required. The
  Python-fallback language-content-signature detector only covers 8 of ~19
  supported target languages — a real, disclosed coverage gap (documented
  in the check's own docstring referencing a real prior incident), left
  as-is pending a scoped follow-up rather than expanded in this pass.
  `port_coordinator.py`'s `extraction_degraded` flag is computed but never
  consumed by any downstream gate — a real "write-only" wiring gap, but
  fixing it properly requires deciding whether a degraded extraction should
  become a required (blocking) check in `equivalence_verifier.py`, which is
  a design decision better scoped on its own. RQCA's Docker-unavailable
  fallback (`_dry_run_report`) reports `verdict: DRY_RUN` → `qc_verdict:
  ADVISORY`, which never blocks regardless of `rqca_enforcement_enabled` —
  this is an inherent limitation of "we couldn't actually execute the code"
  rather than a bug to patch reflexively; blocking on environmental Docker
  unavailability would fail closed for a different, non-security reason and
  wasn't part of the user's enforcement-default decision above. The regex-
  based secret/dangerous-pattern scanners in `security_compliance.py` are
  trivially evadable by generated code (string-concatenated secrets,
  `getattr`-obfuscated `eval`/`exec`, `os.system`/`getattr(subprocess,
  "run")` forms the `(Popen|run|call)` alternation misses) — accepted as a
  known heuristic-scanner limitation, same category as the weak-regex
  finding accepted in the api-gateway review. Report-signing failures are
  silently swallowed with only a log line, leaving an unsigned report with
  no distinguishing marker — a minor integrity-observability gap, not
  patched in this pass.
- Every fix has a regression test independently proven to fail against the
  pre-fix code via `git stash`. Full backend suite: 1346 passed, 5 skipped.
  `ruff check` clean on all touched files. Rebuilt `deploy-orchestrator` and
  verified the new enforcement defaults directly inside the rebuilt
  container via `docker run --rm deploy-orchestrator:latest python -c
  "from orchestrator.settings import load_settings; ..."`.

### pod-worker Review (2026-07-03): poison-message data loss, plus 4 smaller confirmed bugs

A correctness review of `services/pod-worker/pod_worker/` (~5.1k lines:
`main.py`, `language_extractor.py`, `ast_extractor.py`, `js_ast_extractor.py`,
`java_ast_extractor.py`, `concept_catalog.py`, `refined_ir.py`,
`tracing.py`) — the service that executes agent work items dispatched by
the orchestrator and performs source-code extraction for AIM generation.
Three parallel finder agents covered the whole slice (main/tracing,
language-extraction layer, AST extractors + refined_ir/`__init__`).

- **Critical: `_consumer_loop`'s catch-all exception handler silently
  orphaned failed stream entries forever.** `main.py` (`_consumer_loop`, the
  Redis-Streams consumer group loop): the branch for the four
  explicitly-handled exception types (`ProtocolValidationError`,
  `json.JSONDecodeError`, `KeyError`, `TypeError`) correctly writes to the
  DLQ and acknowledges the entry, but the generic `except Exception` branch
  only logged a warning — `acknowledge` stayed `False` and no DLQ write
  happened. Since nothing in this loop ever calls `XCLAIM`/`XAUTOCLAIM` to
  reclaim pending entries, an unexpected exception (e.g. an httpx timeout
  deep in `_handle_running_mission`) permanently orphaned that message in
  the consumer group's pending-entries list: never processed again, never
  visible in the DLQ, no operator signal beyond one log line. Fixed to match
  the existing pattern: write to DLQ, then acknowledge.
- **Fixed a companion silent-data-loss bug in `_write_dlq`.** The function
  caught its own `xadd` failures and only logged them, while both call
  sites in `_consumer_loop` still unconditionally set `acknowledge = True`
  regardless of whether the DLQ write actually succeeded — a transient
  Redis blip during the DLQ write would silently and permanently drop the
  original message (removed from the pending-entries list, never landing in
  the DLQ). `_write_dlq` now returns whether the write succeeded, and both
  call sites only acknowledge on success; on failure the entry stays
  unacknowledged and visible via `XPENDING`.
- **Fixed a `refined_ir.py` name-field bug.** `build_refined_ir_module`
  computed a `RefinedIRFunction`'s `name` as
  `str(node_payload.get("node_name") if isinstance(node_payload, dict) else concept)`
  — since `node_name` is opportunistic (not a required LogicNode field), a
  payload dict that simply omitted the key returned `None` from `.get()`,
  and `str(None)` is the literal string `"None"`, not empty, so it slipped
  past validation and silently corrupted the RIR's `name` field instead of
  falling back to the concept name. Fixed with an explicit
  `node_name if node_name else concept` fallback.
- **Fixed a JS/TS function-detection regex gap.** `JavaScriptExtractor`'s
  `_function_pattern` only matched parenthesized arrow-function arg lists
  (`(x) => ...`) and `function` expressions, silently dropping every
  paren-less single-arg arrow function (`x => x + 1`) — a mainstream JS
  idiom — from `ExtractionResult.functions` with no error or log. Added a
  `\w+\s*=>` alternative.
- **Fixed a `PythonAstExtractor` truncation inconsistency.** The regex pass
  (`super().extract()`) truncates source to `_MAX_SOURCE_LENGTH` (512 KB)
  internally before scanning, but `extract_python_ast()` was called with the
  original, untruncated source — for files over the cap, AST-derived
  `functions`/`classes` could report line numbers past what the regex pass
  ever saw (inconsistent with `ExtractionResult.concepts`), and the size
  guard meant to bound `ast.parse()` cost was silently bypassed for the AST
  path only. Fixed by passing the same truncated source to both.
- **Fixed a Java static-import edge case.** `JavaAstExtractor.extract`
  built `result.imports` directly from `ast_result.imports` without
  filtering; a malformed/partial `javalang` parse can leave
  `JavaImportInfo.qualified_name` as an empty string, which was injected
  into the imports list as a bare `""` entry. Added a truthy filter.
- **Investigated and refuted / deferred:** `_dependency_status`-style
  broad exception handling in the JS/Java AST extractors is correctly
  defensive (both wrap parsing in `try/except`, return `success=False` with
  an error string, and every caller falls back to the regex-derived result
  on failure — no crash risk, no silent wrong-but-successful result).
  `pod_worker/__init__.py` being empty is a non-issue (the orchestrator
  imports the `pod_worker.language_extractor` submodule directly, not
  `pod_worker` itself). `refined_ir.py`'s `effects`/`purity` field semantics
  are confusingly named (an "extraction confidence" threshold gates an
  `effects` list that reads like a runtime-purity marker) but not
  functionally wrong — left as-is, flagged for a future naming cleanup.
  Duplicate `concept_id`s reused across languages in `concept_catalog.py`
  are currently harmless (dedup is scoped per single-language, per-call) but
  noted as a latent trap if any future code aggregates `concept_id` as a
  cross-language key. JS dynamic `import()`/`export ... from` extraction and
  arrow-function-as-callback-argument coverage gaps are real but scoped
  enhancements, not correctness bugs, and the AST extractor path they'd
  affect is disabled by default (`JS_AST_EXTRACTOR_ENABLED=false`).
  **Deferred (needs a design decision, not a quick patch): `_run_agent_pipeline`
  invokes `agent.execute()`/`.validate()`/`.report()` synchronously inside
  the async event loop with no `asyncio.to_thread`/executor offload — a
  CPU-bound or blocking specialist agent call stalls the entire consumer
  loop and heartbeat loop for the process.** A scoped fix (wrapping the call
  in `asyncio.to_thread`) risks introducing thread-safety bugs if agent
  internals assume single-threaded execution; this needs its own review of
  `agent_base.py`'s execution model before changing, not a reflexive patch.
- Every fix has a regression test independently proven to fail against the
  pre-fix code via `git stash`. Full backend suite: 1342 passed, 5 skipped.
  `ruff check` clean on all touched files. Rebuilt both `deploy-pod-a-worker`
  and `deploy-orchestrator` images (the orchestrator image bundles
  `pod_worker.language_extractor` for AIM generation) and verified every fix
  directly inside the rebuilt containers via `docker run --rm ... python -c
  "..."`.

### api-gateway Review (2026-07-03): 10 unauthenticated routes, plus 5 smaller confirmed bugs

A correctness/security review of `services/api-gateway/api_gateway/main.py`
(~2.8k lines) — the single caller-facing entry point that proxies to the
orchestrator's `/internal/*` routes. Four parallel finder passes covered the
whole file (auth/security helpers, mission-creation+scanning, LLM
builder-preview proxy, mission/operations routes), followed by a fifth
targeted pass to triage 11 additional candidate findings against the actual
code and orchestrator-side handlers.

- **Critical: 10 routes had zero caller authentication.** By systematically
  grepping every `@app.get`/`@app.post` route against every
  `_require_reader_access`/`_require_operator_access` call site: `create_mission`
  (`POST /v1/missions`), `get_mission_pod_assignment`, `get_mission_chain_trace`,
  `create_pm_feature_contract`, `get_mission_logicnodes`, `get_mission_knowledge`,
  `get_mission_knowledge_graph`, `get_mission_audit_reports`,
  `get_mission_audit_artifacts`, `get_mission_audit_events`,
  `get_mission_build_artifacts`, `get_mission_build_artifact`,
  `download_mission_artifact`, and `create_builder_preview` all forwarded
  straight to the orchestrator's `/internal/*` endpoints (using the
  gateway's own privileged internal-service key) with no check on the
  *caller's* credentials at all — any anonymous request could read mission
  prompts, source code, audit trails, and build artifacts for any
  `mission_id`, or create new missions / trigger a paid LLM builder-preview
  call. Fixed by adding `x_api_key`/`authorization` header params plus a
  `_require_reader_access(...)` call as the first line of each, matching the
  existing correct pattern already used by `get_mission`/`list_missions`/
  `get_mission_events`. `update_mission_state` was checked and confirmed
  already correct — it uses a different, deliberate pass-through pattern
  (`_resolve_mutation_forward_headers`) that forwards the caller's own key to
  the orchestrator, which is the actual enforcement authority for mutation
  routes via its own `MUTATION_AUTH_DEP`; this is by design, not a gap.
- **Fixed a hybrid-mode operator-access bypass.** `_require_operator_access`'s
  `hybrid`-mode `X-API-Key` branch granted access on any non-empty header
  with zero validation against configured gateway keys — inconsistent with
  its own `api_key`-mode branch and with `_require_reader_access`'s hybrid
  branch, both of which correctly call `_require_api_key_role`. Fixed to
  match.
- **Fixed an X-Forwarded-For rate-limit bypass.** `_client_identifier`
  trusted the caller-supplied `X-Forwarded-For` header unconditionally, with
  no reverse-proxy config anywhere in `deploy/` that strips or overwrites it
  — any anonymous caller (no `x-api-key`) could set a fresh random value on
  every request and trivially bypass IP-based rate limiting. Fixed with a new
  `GATEWAY_TRUST_PROXY_HEADERS` env flag (default `false`); the header is
  only honored when an operator explicitly confirms a trusted proxy sits in
  front of the service.
- **Changed `PROMPT_GUARD_MODE` default from `"log"` to `"block"`** (user
  confirmed via explicit product decision). Previously, critical/high-risk
  prompt-injection attempts (OWASP LLM01) were recorded in
  `sensitive_input_scan`/`prompt_input_scan` metadata but the mission
  proceeded to persistence anyway — a permissive-by-default posture
  inconsistent with the stated design intent. Operators can still opt back
  into observability-only mode via `PROMPT_GUARD_MODE=log`.
- **Fixed an Anthropic `max_tokens`/`thinking_budget` mismatch.**
  `_anthropic_builder_preview` hardcoded `max_tokens: 1200` while
  `thinking.budget_tokens` scales with the caller-configurable
  `thinking_budget` (up to 65536 via `BuilderPreviewRequest`). Anthropic
  requires `max_tokens` strictly greater than `thinking.budget_tokens`, so
  any request with `thinking_mode="enabled"` and a budget >= 1200 was
  rejected by Anthropic on every call, silently degrading to the offline
  fallback. Fixed by scaling `max_tokens` to `budget_tokens + 1200`
  (fixed output headroom) whenever thinking is enabled.
- **Fixed a Gemini-3 model-detection gap.** `_is_gemini_3_model` only
  matched hardcoded `gemini-3-`/`gemini-3.1-`/`gemini-3.5-` prefixes, missing
  plausible real model names like `gemini-3.0-pro` (a very likely name given
  3.1/3.5 imply a 3.0 predecessor) and the bare `gemini-3`. Both would
  silently fall into the legacy `thinkingBudget` config path instead of
  Gemini 3's `thinkingLevel` config. Replaced with a regex
  (`^gemini-3(\.\d+)?(-|$)`) that generalizes to any `gemini-3[.minor]`
  model id without introducing false positives (verified `gemini-30-ultra`
  still correctly returns `False`).
- **Fixed an OpenAI refusal-content extraction gap.** `_extract_openai_text`
  only read `block.get("text")` from Responses API content blocks; a
  `refusal`-type block carries its text under the `refusal` key instead,
  so a refusal-only response silently extracted to `None` with no
  diagnostic detail. Fixed to fall back to `block.get("refusal")`.
- **Investigated and refuted** (finder-agent candidates that turned out to
  be false positives or by-design behavior, each independently re-verified
  against the actual code before being dismissed): a "silent pod-manager
  fallback" (pod-manager routing is a pure in-process dict lookup with a
  static default — there's no network call or reachability failure to mask);
  "chain_trace forgery" (`get_mission_chain_trace` is a plain read-only GET
  proxy with no caller-supplied body — no forgery vector exists); "PII-scan
  field exclusions" (attachments only carry file metadata, never inline
  content, through this endpoint — there's no file-content field to miss);
  "`_dependency_status` exception swallowing" (caught exceptions correctly
  degrade the health flag to `False` and log a warning — this is exactly the
  right behavior for `/readyz`); "unvalidated provider string" (an unknown
  provider safely falls through to the offline fallback via a dict `.get()`
  returning `None`); "markdown lstrip over-stripping / mixed-provenance
  labeling" (no such lstrip exists in this file, and the `source` field is
  set consistently and correctly for every response path). One item —
  weak base64/secret regex patterns in the PII/prompt-injection scanners —
  was confirmed as a real but *documented, accepted* limitation: broad
  heuristic detection, not a hard security control, acceptable as
  defense-in-depth logging.
- Added regression tests for every fix, each independently proven to fail
  against the pre-fix code via `git stash`. Full backend suite
  (`pytest tests/services/ --ignore=tests/services/test_agent_base_unit.py`):
  1337 passed, 5 skipped. `ruff check` clean on all touched files. Rebuilt
  `deploy-api-gateway:latest` and verified every fix (auth params present,
  `PROMPT_GUARD_MODE=="block"`, `GATEWAY_TRUST_PROXY_HEADERS==False`,
  Gemini-3 detection, refusal extraction) directly inside the rebuilt
  container via `docker run --rm deploy-api-gateway:latest python -c "..."`.

### Agent Orchestration Core Review (2026-07-02): AIM extraction was silently non-functional in production

A correctness review of `agent_base.py`, `agent_registry.py`,
`agent_personas.py`, `agent_integrations.py`, `agent_scaling.py`,
`is_agent.py`, `dependency_absorption.py`, `aim_generator.py` (~5.3k lines) —
the layer that runs each of the 40+ specialist/pod agents and builds the
Application Intelligence Map for source-analysis missions.

- **Critical, most significant finding of the review effort so far: AIM
  source-code extraction was silently non-functional in the deployed
  orchestrator container.** Two independent bugs, both masked by a broad
  `except Exception` in `_extract_file` that only logged a warning and
  returned an empty/zero fallback:
  1. `_extract_file`'s import of `pod_worker.language_extractor` computed its
     search path as `Path(__file__).resolve().parents[2]` — correct in
     local dev (`services/pod-worker` is a sibling of `services/orchestrator`)
     but resolving to the filesystem root inside the built container, since
     the Dockerfile only copies `services/orchestrator`'s *contents* to
     `/app` (no `services/` ancestor exists there at all). This had
     apparently never been verified against an actual built container.
  2. Even when reachable, the code filtered `result.concepts` for
     `domain == "import"` — a domain value the real pattern catalog never
     produces (real import-like concepts are tagged `"module_patterns"`
     alongside unrelated module declarations). `ExtractionResult` has its
     own dedicated, correctly-populated `imports` field that the code never
     used at all.
  - Fixed both: `aim_generator.py` now tries both the local-dev and
    container candidate paths (checking which actually exists) and reads
    `result.imports` directly; the Dockerfile now copies
    `services/pod-worker/pod_worker` to `/app/pod_worker` (no new pip
    dependencies — the extractor modules only need the standard library,
    with optional AST libraries for JS/Java that already gracefully degrade
    to regex-only extraction when absent). **Verified working inside a
    freshly rebuilt container**, not just locally — `docker run --rm
    deploy-orchestrator:latest python -c "..."` confirms `detected_imports`
    and `function_count` are now populated for real source text.
  - Also fixed the import-count cap: `detected_imports` was capped at
    `sorted(...)[:50]`, alphabetically favoring early-alphabet names and
    silently dropping real dependencies (e.g. "requests", "sqlalchemy",
    "uvicorn") for any codebase with 50+ distinct imports — these fed into
    `dependency_absorption.py`'s inventory as the AIM's fallback
    `detected_dependencies` source of truth. Raised the cap to 1,000 and
    folded it into the existing `truncated` signal instead of a silent cut.
- **Fixed a scaling-decision idempotency gap.** `_prepare_specialist_plan`
  (`mission_flow_v2/phases_build.py`) computed a fresh `ScalingDecision`
  (with new random partition IDs) every time it ran, with no "already
  decided" guard — unlike every other side effect in the same function. This
  function is explicitly re-entrant by design (the PORT two-phase flow
  re-enters it, and any retry while the mission is still at
  `specialist_assigned` would too), so a second invocation would mint fresh
  partition IDs that don't match the emitted-partition-ID tracking from the
  earlier `_emit_partition_work_items` fix, orphaning already-emitted or
  completed partition work. Fixed with a guard: skip recomputation if
  `metadata["scaling_decision"]` already exists.
- **Fixed a Java-detection false negative.** `detect_required_languages`
  (`is_agent.py`) already had a reasonably Java-specific regex
  (`^import [A-Z]|^package [a-z]`) but then required the literal word
  "java" to *also* appear somewhere in the prompt or source text before
  indexing Java bootstrap docs — legitimate Java code with a prompt like
  "port this billing module" never mentions "java" by name and was silently
  skipped. Removed the redundant gate.
- **Investigated and deferred as lower-confidence/lower-impact:**
  `make_specialist_for_language`'s case-sensitive language lookup (agent_base.py)
  and `make_agent`'s silent fallback to a generic `SpecialistAgent` on a
  registry/factory-map mismatch — both real risks in principle, but zero
  callers of the former exist anywhere in the codebase today;
  `dependency_absorption.py`'s version-conflict-resolution ordering (first
  source wins, no conflict surfaced) and stdlib-import miscategorization;
  `agent_scaling.py`'s silent clamping of a misconfigured `max_instances`.

Validation: full backend suite — 1332 passed, 5 skipped, 0 failed (1328
baseline + 4 new regression tests). `ruff check` clean. `orchestrator` Docker
image rebuilt and the AIM extraction fix specifically verified by running
Python directly inside the rebuilt container image.

### Storage Layer Review (2026-07-02): audit-chain fork race fixed, several candidates refuted

A correctness review of the orchestrator's DB storage layer
(`storage_missions.py`, `storage_artifacts.py`, `storage_agents.py`,
`storage_pods.py`, `storage_logicnodes.py`, `storage_core.py`, `storage.py`,
`models.py`, ~3.1k lines) — the layer every mission-flow phase reads and
writes through, and the layer underneath every fix from the previous review
pass.

- **Fixed: tamper-evident audit chain could silently fork.**
  `insert_agent_action_event` (`storage_agents.py`) read the latest
  `event_digest_sha256` for a `project_id` and inserted the next
  hash-chained event as two separate, unsynchronized statements (pool
  connections are `autocommit=True`, and there was no transaction or lock
  around the pair). Two concurrent events for the same project could both
  read the same `prev_digest` and both chain onto it — no unique constraint
  or trigger would catch this, since `agent_action_events` has no such
  guard. Fixed by wrapping the read-then-chain sequence in a transaction with
  a `pg_advisory_xact_lock(hashtextextended(project_id, 0))` at the top,
  serializing concurrent writers per project.
- **Investigated and refuted as live bugs** (verified against actual callers,
  not just the code in isolation):
  - `get_build_artifact` returning `artifact_text=None` for object-storage-
    offloaded artifacts — this is the intended design; its one real caller
    (`routes/internal.py`'s `GET /internal/missions/{id}/build-artifacts/{id}`)
    already checks `storage_backend == "s3"` and redirects to a presigned URL
    instead of expecting inline text.
  - `row_to_mission`'s `len(row) >= 7` column-count inference — every actual
    SQL query in the file selects exactly 7 columns; the "6-column" fallback
    branch is dead code, never exercised.
  - `models.py`'s `MissionRecord.risk_assessment` and
    `MissionAttachment.purpose` inconsistent-Optional/free-form-string
    concerns — both fields have zero readers anywhere in the codebase today.
  - Self-loop `MISSION_COMPLETION_BLOCKED` events accumulating rows in
    `mission_state_events` — intentional design (the code's own comment
    frames it as a checkpoint event); the metrics layer already avoids
    double-counting it.
- **Deferred, not fixed this pass** (lower confidence/impact — see
  `docs/CURRENT_TODO.md` for the full list): `storage_pods.py` pod-name
  case-sensitivity (real risk in principle, but only one current caller and
  it's always consistently cased); unconditional S3 re-upload on every
  `upsert_build_artifact` retry (efficiency, and its main trigger was already
  closed by the previous session's lifecycle fix); no digest verification of
  caller-supplied `digest_sha256` against actual `artifact_text`;
  `models.py`'s `VALID_TRANSITIONS` table being pure documentation, never
  actually enforced by `transition_mission_state` (a real design gap, but
  wiring it in is a bigger behavioral change than this pass's scope).

Validation: full backend suite — 1328 passed, 5 skipped, 0 failed (1327
baseline + 1 new regression test). `ruff check` clean. `orchestrator` Docker
image rebuilt and verified to contain the fix.

### Mission Flow v2 + LLM Delegation Review (2026-07-02): 7 backend bugs fixed

A deep correctness review of two backend slices — the Mission Flow v2
lifecycle driver (`services/orchestrator/orchestrator/mission_flow_v2/`) and
the LLM delegation layer (`services/orchestrator/orchestrator/llm_delegation/`)
— using parallel finder agents reading full files (not diffs), each candidate
independently verified against the actual code before fixing. Seven real bugs
found and fixed, all with new regression tests:

- **Critical — recovery re-invocation silently regenerated PM feature
  contracts on every orchestrator restart.** `advance_mission_lifecycle_v2`
  (`mission_flow_v2/lifecycle.py`) iterated its full transition table from
  `queued` on every call, regardless of the mission's actual current state.
  The lifecycle-recovery loop (`lifecycle_recovery.py`) restarts one of these
  driver tasks for every mission sitting in `queued`/`running`/`verified` on
  every orchestrator startup — so any in-flight mission had its
  `queued->pm_intake` preparer (`_prepare_pm_intake`) unconditionally
  re-invoked, burning a fresh LLM call and overwriting
  `metadata["feature_contract"]`/`metadata["mission_charter"]` with a new,
  non-deterministic result before the atomic `transition_mission_state`
  compare-and-swap finally caught the state mismatch and exited. Fixed by
  reading the mission's actual current state once at the top and skipping to
  the matching transition-table entry before running any preparer.
- **Partition-emission retry could duplicate already-succeeded work.**
  `_emit_partition_work_items` (`mission_flow_v2/phases_intake.py`) only
  marked emission complete after every partition in a scaling batch
  succeeded; a mid-batch validation or Redis failure meant a retry re-emitted
  every partition from scratch — including ones that already succeeded, with
  a fresh random `event_id` each time that defeats event-level dedup. Fixed
  by tracking per-partition emitted IDs and persisting progress on failure so
  a retry only emits the remaining partitions.
- **Runtime QC re-executed on every completion-gate retry.**
  `_prepare_runtime_qc` (`mission_flow_v2/phases_runtime.py`) had no cache
  check, unlike the testdata-manifest step right above it in the same
  function — every retry of the verified→complete completion gate (which
  recurs on every orchestrator restart while blocked by an earlier gate)
  re-ran the real sandboxed QC execution and a second LLM assessment call
  from scratch. Fixed with a cached-report short-circuit.
- **Greedy JSON-extraction regex discarded valid LLM decisions.**
  `_extract_decision_payload` (`llm_delegation/text.py`) used
  `re.compile(r"\{.*\}", re.DOTALL)`, which spans from the first `{` to the
  last `}` in the *entire* response — any reasoning-with-example-braces or a
  second JSON block anywhere in the text merges into one unparseable blob,
  silently discarding a perfectly valid agent decision and falling back to a
  degraded default. Replaced with a proper balanced-brace scanner
  (string/escape aware) that tries top-level JSON objects from last to
  first, matching the common "reasoning, then the actual answer" LLM output
  shape.
- **Unrecognized `intake_status` values failed open instead of closed.**
  `_normalize_pm_feature_contract` (`llm_delegation/normalizers.py`) defaulted
  any LLM `intake_status` value outside `{"ready", "needs_clarification"}`
  (e.g. a hallucinated "unclear"/"pending") to `"ready"` — silently letting a
  genuinely underspecified mission skip clarification. Fixed to default to
  `"needs_clarification"`, the safe/conservative option.
- **Windows drive-relative path could bypass the source-bundle traversal
  guard.** `_write_artifact_to_disk` (`mission_flow_v2/phases_build.py`)
  checked the raw path fragment for `".."`-prefix/`os.path.isabs()` before
  writing a generated file — a Windows drive-relative path like
  `C:evil.txt` is neither, and pathlib's join behavior for such fragments is
  drive-letter-dependent (verified live: it can silently discard the mission
  directory and resolve elsewhere entirely). Fixed by validating the actual
  resolved, joined path is still inside the mission directory rather than
  pattern-matching the fragment.
- **Defensive hardening:** `_build_prompt` (`llm_delegation/prompts.py`) now
  tolerates a non-numeric `risk_score` instead of an uncaught `float()`
  crash mid-CEO-delegation-prompt-build (not a demonstrated live bug — the
  field is currently always LLM-normalizer-controlled — but cheap, safe
  insurance in a mission-critical path).

Validation: full backend suite (`python -m pytest tests/services/
--ignore=tests/services/test_agent_base_unit.py`) — 1327 passed, 5 skipped, 0
failed (1319 baseline + 8 new regression tests). `ruff check` clean on every
touched file. Each fix's regression test was confirmed to fail against the
pre-fix code (via `git stash`) before being accepted.

**Deferred, not fixed this pass** (lower confidence or lower impact — see
`docs/CURRENT_TODO.md` for the full list): unguarded `int()` cast on LLM
totals and a missing `isinstance` guard in `generators_artifacts.py`; an
unrecognized provider string silently routing to OpenAI and a fallback path
that doesn't re-check safety-block state in `providers.py`; several
telemetry-only accuracy issues in `normalizers.py`/`fallbacks.py`
(uncapped duplicate counts, no size cap on `generated_code`, missing
sanitization in `_fallback_vc_commit_strategy`); a p95-latency
floor-vs-ceiling inaccuracy in `health.py`.

### Older History (archived 2026-07-03)

Entries older than the 2026-07-02/07-03 review sweep above (Post-Review
Hardening, Findings Remediation Phases 0-4, Cold-start healthcheck fix,
Security Alert Remediation, Phase 8 Coverage, Phase 13 Backend/API Smoke,
Documentation Current-State Cleanup) were moved to
`docs/archive/2026-07-03/HANDOFF_CURRENT_OLDER_HISTORY.md` to keep this file
focused on current status plus recent history.

---

## Validation Snapshot

Findings-remediation validation (Phases 0-3, this pass):

- `python -m pytest -o addopts= --basetemp .pytest-tmp tests/services/ --ignore=tests/services/test_agent_base_unit.py`
  passed 1311, skipped 5, failed 0 (run after Phase 3; the ignored file has a
  pre-existing, unrelated import-path collection error).
- `python -m ruff check` clean on every file touched across all three phases
  (`generators_artifacts.py`, `fallbacks.py`, `llm_delegation/__init__.py`,
  `phases_build.py`, `phases_delivery.py`, `equivalence_verifier.py`,
  `models.py`, and their test files).
- `docker compose --env-file .env -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents build`
  — exit 0, all ~48 buildable services built successfully.
- `docker compose ... up -d --scale minio=0 --scale neo4j=0` (later
  superseded by the user's own `start_app.bat` run, which brought
  `minio`/`neo4j` up too) — exit 0.
- Live fleet check: 59/59 `deploy-*` containers healthy or Up, 0 unhealthy, 0
  stuck.
- `curl http://127.0.0.1:8101/readyz` → `ready: true`, all dependencies
  healthy including `db_ready`, `neo4j_ready`, `object_storage_ready`.
- `curl http://127.0.0.1:8100/readyz` → `ready: true`.

Passing checks from the prior work:

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

### Priorities — refreshed 2026-08-12

`docs/WORK_QUEUE.md` is the authoritative ordered list; this is the summary.

1. **Give runtime QC a real invocation** so its verdict can be trusted, then and
   only then consider `RQCA_ENFORCEMENT_ENABLED=true`. Today it fails every
   argument-taking CLI program for a reason that is not the code's fault.
2. **Finish the live proof matrix.** A UI-driven mission, a PORT/transform,
   failure injection and provider fallback are still owed; the suite, an
   unattended run and a non-Python mission are done.
3. **Move sandbox execution out of the orchestrator** into `agent-41-rqca`. The
   orchestrator mounts `/var/run/docker.sock` -- effectively host root. Fine for
   local dev, must not ship.
4. **The four held Dependabot PRs**: electron 43, next-ecosystem, vitest,
   playwright. All frontend; they need the app exercised in a browser.
5. **Exercise the Delta gate against a live bus** with
   `EVENT_DRIVEN_CONTROL_PLANE_ENABLED=true` on ONE mission first -- if producer
   and consumer do not line up it stalls every mission at VERIFIED.
6. **Electron decisions still need sign-off**: Docker lifecycle on quit, the
   Docker Desktop/WSL2 prerequisite story, auto-start.

DONE since this list was written: licence-free MATLAB/Mathematica runtimes, image
digest pinning, the live-suite silent skip, rate-limit starvation, the intake
gate, and reachability of runtime QC.
1. **Post-restart Mission Control UX proof.** Restart the app, then submit a
   real browser mission through Mission Control asking for a modern Angular
   Snake game with a `start.bat` file. Confirm: (a) PM clarification cards
   appear or defaults can be accepted; (b) Live Progress shows ongoing work
   instead of looking hung; (c) Generated Output / Build Artifacts expose the
   real output-folder path and local open actions; (d) Continue with PM
   preloads prior mission context for follow-up work.
2. **Active repo ZIP migration next step.** Add the mission launch index guard,
   repo knowledge ingestion, and PM/pod-worker repository context loading so
   ZIP-imported repositories become internal database context rather than only
   approved source bundles.
3. **Existing live-stack top priority.** Submit one live mission through the
   real Mission Control chat UI (`http://127.0.0.1:3100/chat`, not the raw
   API — the stack is already up, rebuilt, and healthy). Pick a Pod B/C/D
   language that is also Python-dissimilar (Go, Rust, or C are all in scope
   for the new content-signature check) so one mission proves everything at
   once: (a) `pod_audit_verdicts.<pod>.agent_id` matches the pod's own audit
   agent, not `AGENT-13-PODA-AUDIT`; (b) the Beta lane fires — check
   `protocol:beta:*` on `protocol-bus-mcp` (port 8102) metrics/DLQ; (c)
   `MISSION_DEPLOY_READINESS_ASSESSED` appears in the chain trace (findings
   §6.4); (d) the mission's `equivalence_report.checks` includes
   `language_content_signature` with a sensible result; (e) fetch that
   mission's build-artifacts through `api-gateway` (`/v1/missions/<id>/build-artifacts`)
   to conclusively close stack-plan Finding 4 (a fresh mission, not an old
   pre-wipe ID). Two Chrome browser extensions are currently connected — pick
   one explicitly (via `list_connected_browsers`/`select_browser`) before
   driving the UI.
4. Decide whether to also flip `mission_equivalence_enforcement_enabled`
   (still `False`) now that the new language-content-signature check exists —
   this is a broader decision than Phase 2 scoped, since it would also start
   blocking on the pre-existing `artifact_format_matches_contract` and
   `language_alignment` checks, not just the new one.
5. Rerun a Pong-style UI artifact mission through the current PlanBuild path.
6. Run Mission Control UI smoke for Phase 13.
7. Run protocol-bus failure injection for Phase 13.
8. Run provider fallback proof for Phase 13.
9. Run full `make validate` and capture the current result.
10. Raise remaining Phase 8 `mission_flow_v2/` branch coverage or explicitly defer the old 85% branch target.
11. Add provider/key/model preflight in Settings.
12. Move provider/model selection into the app settings/vault path.
13. Rotate exposed provider keys before public or shared use.
14. ~~Fix pod-audit, Beta, generated-language verification, Compliance
    trigger~~ — **done**: commits `4445b6b`, `07883d7`, `a63dfaf`, `b70d711`.
    Live re-confirmation is Next Action #3 above.

---

## Operational Notes

- The default runtime path is Mission Flow v2.
- LangGraph remains optional and disabled by default.
- The current backend/API smoke proves the API path, not the full UI path.
- Archive docs are historical only.
- The local `.pytest-tmp/` warning can appear in `git status`; it is local
  generated output and should not be committed.

### Running the live-stack suite (added 2026-08-11)

Two settings are required or the run is worthless, and **both fail quietly**:

```bash
docker stop deploy-mission-control-1
LIVE_STACK_ENABLED=1 LIVE_HTTP_TIMEOUT_SECONDS=30 \
  LIVE_MISSION_CHAIN_TIMEOUT_SECONDS=600 OTEL_SDK_DISABLED=true \
  python -m pytest tests/services/test_live_mission_flow_integration.py -q -rs
docker start deploy-mission-control-1
```

Always pass `-rs`. Without the timeout override the suite **skips and still
exits 0**; without stopping the UI, mission creation returns 429. An `s` in the
output means nothing was verified, whatever the exit code says.

### RQCA / sandbox execution config (added 2026-08-11)

`.env` is gitignored, so these are **local-only** -- a fresh clone silently
returns `DRY_RUN` for every language until they are set. See `.env.example`,
which documents them and keeps the safe default of `false`.

- `RQCA_AGENT_ENABLED=true` -- inert on its own; needs the socket and workspace
  below, both of which compose provides.
- `SANDBOX_WORKSPACE_HOST_ROOT=<absolute host path>` -- required whenever the
  orchestrator runs in a container. Sandboxes are *sibling* containers, so the
  daemon resolves `--volume` sources on the host, not inside the orchestrator.
  Without it the daemon mounts an empty directory it created itself and every
  run fails with "no such file".
- The compose orchestrator service mounts `/var/run/docker.sock` and sets
  `group_add: ["0"]` -- the socket is `root:root` 0660 and the service runs as
  uid 10001, so the group is the smallest grant that works.

**To add a language:** add one entry to `_LANGUAGE_RUNTIMES` in `rqca_agent.py`
(`base_image` + `run_command`, with `{filename}` and `{stem}` substituted).
Constraints that are invisible from the config file and each of which broke a
language during bring-up:

- `/workspace` is **read-only** -- build output and caches must go under `/tmp`.
- `HOME` is not writable -- go, ghc, kotlinc, julia, R and zig all need `HOME`
  or their cache directory redirected there explicitly.
- There is **no network** -- nothing may fetch a compiler or package at run time.
- `--entrypoint=sh` is pinned, because `ocaml/opam` prefixes `opam exec --` and
  `sbtscala` launches sbt; otherwise a language's behaviour depends on an image
  default rather than on its config.

`test_every_runtime_respects_the_sandbox_constraints` renders every command and
fails on workspace writes or toolchain fetches, so adding language 20 does not
require re-running all 19. Still verify a new language with a real hello-world
through the sandbox before trusting it.
