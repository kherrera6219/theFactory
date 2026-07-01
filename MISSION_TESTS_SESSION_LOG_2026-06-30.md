# Mission Tests Session Log — 2026-06-30 / 2026-07-01

Companion to `FIRST_FULL_SYSTEM_RUN_FINDINGS_2026-06-30.md`. That document is
the *analysis* (what was found, code review, recommendations). This document
is the *chronological narrative* — what actually happened, in order, across
the whole session, so a new agent picking this up cold can get fully up to
speed without re-deriving any of it. Read this once, then the findings report,
then `docs/STACK_REMEDIATION_PLAN_2026-07-01.md` for the immediate next steps.

**If you are a fresh agent reading this:** the single most important fact is
in Chapter 8 — do not assume any fix described here is live in the running
stack. Check `git log` / `git status` first.

---

## Chapter 0 — Starting point

Session began continuing from prior work: `PROTOCOL_BUS_LANE_ACTIVATION_PLAN.md`
(PBLA) had been reviewed, corrected against live code, and validated. Commit
history up to `3805397` already contained:

- PBLA-00 through PBLA-04 (all six Protocol Bus lane producers implemented and
  unit-tested — commits `665422b`, `bffbdac`, `20671dc`, `48c4ef7`, `15213e1`)
- A cold-start healthcheck fix (`f0eb0a8`) — orchestrator's Docker healthcheck
  was hitting `/health` (which does live optional-backend probes and can be
  slow) instead of a new, fast `/livez` endpoint, which had been wedging the
  whole dependent service chain in `Created` state on cold starts. This was
  confirmed fixed on a live restart before this session's events began.
- Docs (`CURRENT_TODO.md`, `HANDOFF_CURRENT.md`) recording the above as of
  commit `3805397`.

The stated goal for this session: run tests to verify each protocol system
works — specifically, run missions that exercise different agents/protocols,
and design a battery of ~10-20 missions to test every agent over time.

---

## Chapter 1 — First attempt: raw-API mission battery (abandoned)

Wrote `scripts/protocol_bus_mission_battery.py`: a script that POSTs 20
mission payloads directly to the API gateway (`/v1/missions`), one per
language specialist, bypassing the Mission Control chat UI entirely. Launched
it as a background task.

**This attempt was abandoned mid-run.** Checking progress showed several
missions stuck in `CLARIFYING` state — the PM Agent's ambiguity gate
(`ambiguity_score >= 0.7`) had correctly flagged the deliberately-terse prompts
("takes two numbers") as ambiguous for statically-typed languages (Go's actual
clarifying question asked int vs float64 vs generics), but the script had no
logic to answer clarifying questions, so those missions would never resolve.

First fix attempt: made the prompts more type-explicit ("64-bit integer
parameters a and b") and relaunched with a shorter timeout. This *also* got
interrupted — a background-task management error (a `nohup ... &` nested
inside an already-backgrounded tool call) meant the relaunch wasn't actually
being tracked correctly.

**User intervened at this point** with critical guidance: real users will not
bypass the PM Agent's clarification dialogue — the clarifying-question
behavior is itself part of what needs to be tested, and some missions should
deliberately use vague prompts (testing clarification) while others should use
detailed statements of work (testing the direct-to-launch path). This
reframed the whole approach: **missions must be created one at a time through
the real Mission Control chat UI**, with a human-like operator answering (or
explicitly deferring via "proceed with assumptions") the PM's questions.

The orphaned background battery process was killed. `scripts/protocol_bus_mission_battery.py` remains in the repo as a
(now largely superseded) reference for the mission-spec shape, but was not
used for the actual validation run.

---

## Chapter 2 — Second attempt: chat-driven mission battery (successful)

Connected to the user's local Chrome browser via the `Claude_in_Chrome` MCP
tools (already-installed extension, selected via `list_connected_browsers` /
`select_browser`). Drove Mission Control's real chat UI
(`http://127.0.0.1:3100/chat`) end to end, mission by mission.

**Established interaction pattern** (after working through some coordinate/
timing flakiness — the page reliably loads scrolled to the bottom of the
previous conversation, so every new mission required: navigate fresh to
`/chat` → scroll up → click "+ New Chat" → verify empty session via screenshot
→ type prompt → Send → wait ~7-8s → screenshot to read the PM's response →
answer clarifying questions (or type "proceed with assumptions") → scroll down
→ click "Confirm and Start" → capture the resulting `mission-<uuid>` from the
URL).

**20 missions were submitted this way**, deliberately varying the interaction
style across three patterns to get realistic coverage:
- *vague prompt, answered explicitly* (Go, Zig, C#, R, OCaml)
- *vague prompt, "proceed with assumptions"* (C, Java, Scala, Mathematica,
  Python-build, Ruby)
- *detailed Statement-of-Work, skips clarification entirely* (Rust, C++,
  Kotlin, MATLAB, Julia, Haskell, JavaScript, PHP)
- plus one combined IMPORT_MODERNIZE + DEBUG_REPAIR mission (legacy Python
  snippet with an off-by-one bug, described inline)

One real UI-input bug was discovered along the way: typing a message with
literal embedded newlines (`\n`) into the chat textbox causes each newline to
submit the message early (Enter = Send in that box), fragmenting one intended
message into several partial ones. Worked around by describing multi-line code
snippets as single-line prose instead of pasting literal source with line
breaks.

**Result: all 20 missions reached `COMPLETE`.** Full list of mission IDs,
languages, and interaction styles is in
`scripts/protocol_bus_mission_battery_verify.py`'s `BATTERY_MISSIONS` list
(this script was repurposed from a submission tool into a polling/verification
tool once missions were being created via the chat UI instead of the API).

---

## Chapter 3 — Live bus/DLQ evidence, captured before anything broke

Before and during the battery, protocol-bus-mcp's Prometheus metrics
(`/metrics`) and DLQ endpoint (`/dlq?protocol=...`) were checked directly.
Baseline before the battery: all six lanes at zero, zero DLQ. Mid-battery
snapshot (captured before a later container restart reset the in-memory
counters):

```
alpha = 26, delta = 26, omega = 26, sigma = 9, rho = 1 (manual smoke test only), beta = 0
```

Zero DLQ writes across every lane, throughout. `beta = 0` turned out to be a
real, separate bug — see Chapter 5.

Rho was separately confirmed via a **direct, isolated invocation** of the
`_send_rho_traffic_control` helper inside the orchestrator container (not
through a real rate-limit event, since none of the battery's simple prompts
triggered one) — this proved the Rho producer→bus wiring end-to-end without
touching the live provider-retry path. `protocol:rho:broadcast` showed exactly
one message afterward, sender `AGENT-03-BROKER`, discriminator
`metadata.emission = "pbla_traffic_telemetry"` matching the unit tests exactly.

---

## Chapter 4 — Bug found: pod-audit agent misrouting (FIXED, uncommitted)

While reviewing the battery's per-mission chain-trace/agent-routing data
(`scripts/protocol_bus_mission_battery_verify.py`'s output), a pattern jumped
out: **every non-Pod-A mission's audit verdict was attributed to
`AGENT-13-PODA-AUDIT`** instead of its own pod's real audit agent
(`AGENT-19-PODB-AUDIT` / `AGENT-25-PODC-AUDIT` / `AGENT-31-PODD-AUDIT`).

Root-caused by reading `generate_pod_audit_verdict` in
`services/orchestrator/orchestrator/llm_delegation/generators_artifacts.py`:
it lower-cased `pod_name` (`"podB"` → `"podb"`) before looking it up in the
`_POD_AUDIT_AGENTS` dict, whose keys are mixed-case (`"podA"`, `"podB"`, ...).
The lookup never matched for any pod, so every mission silently fell back to
the default (`AGENT-13-PODA-AUDIT`) — masked for Pod A only, because the
default happens to equal Pod A's own audit agent.

**Fixed** by adding a case-insensitive `_POD_AUDIT_AGENTS_BY_LOWER` lookup
table. **Regression test added**:
`tests/services/test_llm_delegation_unit.py::test_generate_pod_audit_verdict_resolves_correct_agent_per_pod`
(4 parametrized cases, one per pod). Full regression run at the time: 163
tests passed across `test_llm_delegation_unit.py`, `test_mission_flow_v2.py`,
`test_mission_flow_v2_phases_build.py`; ruff clean.

**This fix was still sitting uncommitted in the working tree as of the end of
this session** (see Chapter 9) — it needed to be baked into a rebuilt
orchestrator image, which is what triggered Chapters 6-8.

---

## Chapter 5 — Bug found: Beta (PBLA-03) never fires (ROOT-CAUSED, NOT fixed)

Investigated separately, after noticing `beta = 0` in the mid-battery metrics
snapshot (Chapter 3) despite 20 successful codegen missions. Traced through
the actual code:

- PBLA-03's Beta emission lives in `_prepare_fusion`
  (`mission_flow_v2/phases_runtime.py`), guarded by
  `not build_artifact_support.mission_has_generated_output(metadata)`.
- But `generated_output` is actually set **earlier**, in
  `_prepare_specialist_assignment` (`mission_flow_v2/phases_build.py`, around
  line 450, right where the `GENERATED_OUTPUT_CREATED` chain event fires) —
  confirmed directly against the Go mission's saved chain trace, where
  `GENERATED_OUTPUT_CREATED` appears well before `MISSION_POD_GROUP_STANDARD_PRODUCED`
  or `MISSION_LOGIC_FOLDED` (fusion).
- By the time `_prepare_fusion` runs, the guard is already satisfied (output
  already exists), so the entire codegen-and-Beta block in `_prepare_fusion`
  is dead code for every normal `BUILD_NEW` mission.

**Recommended fix (not yet applied):** move the Beta emission from
`_prepare_fusion` to `_prepare_specialist_assignment` in `phases_build.py`,
right after `metadata["generated_output"] = generated_output` is set. Tracked
in the findings report §4/§6.1 and in `docs/CURRENT_TODO.md`.

---

## Chapter 6 — Attempting to ship the pod-audit fix live: rebuild + restart cascade

To get the Chapter 4 fix live, rebuilt the orchestrator image and restarted it
via `docker compose -f deploy/docker-compose.yaml up -d orchestrator`.

**This was the wrong compose invocation** — see
`project_stack_ops_gotchas_2026-07-01.md` (Claude memory) and
`docs/STACK_REMEDIATION_PLAN_2026-07-01.md` Finding 2 for the full detail. In
short: this deployment's actual topology (41 dedicated per-language agent
containers) is defined by **layering two compose files**
(`-f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml`
together); the second file is an overlay only. Using the base file alone
recreated `orchestrator` (and, transitively, `api-gateway`, `mission-control`,
`neo4j`, `audit-worker`, and the 4 shared pod-workers on a later broader `up`)
under a *different* topology/environment than the 41 still-running dedicated
agent containers, which were never touched and kept their original
environment.

Symptoms that followed: 401 Unauthorized on every agent's heartbeat POST to
orchestrator; a live Rust confirmation mission landed in a PM "fallback
planning output — pm_feature_contract_unavailable" degraded state with
`Languages: Auto-detect`; `orchestrator`'s `/health` began reporting
`db_ready: false` and `/readyz` returned 503, with `pgbouncer` logging
`FATAL: password authentication failed for user "postgres"`.

Root-caused (all read-only, no guessed fixes applied):
- Postgres's own stored password and orchestrator's configured password
  *agreed with each other* (confirmed via first-4-character prefix comparison
  only — never printed a full credential) — but neither matched what was
  currently in the repo-root `.env` file. Leading hypothesis: `.env`'s
  `POSTGRES_PASSWORD` was rotated *after* the Postgres data volume was first
  initialized (Postgres only applies that env var at first `initdb`, not on
  container recreation).
- `api-gateway`'s `INTERNAL_SERVICE_API_KEY` resolved to an empty string at
  runtime despite `.env` having a real 64-character value — root cause not
  confirmed even after a `--force-recreate` with the *correct* two-file
  compose combination.
- Bringing the full corrected two-file stack up also hit **two unrelated host
  port conflicts**: `minio` (port 9000) and `neo4j` (port 7474) were already
  bound by two entirely separate, independently-running Docker projects on
  this machine (`devonz-minio`/`devonz-neo4j` from `C:\software\Devonz`, and
  `ukg-neo4j` from `C:\software\DataLogicEngine` — confirmed via
  `docker inspect` compose-project labels, not touched or removed). Both
  services were skipped (`--scale minio=0 --scale neo4j=0`) to get the rest of
  the stack running; both are feature-flagged optional adapters in
  theFactory, so the app runs fine without them.

**At this point the user gave explicit direction: stop attempting live fixes.**
The correct sequence going forward is: write a detailed plan → stop the app →
fix offline → rebuild → bring the stack up once, cleanly → test. This is now
recorded as a standing behavioral rule in Claude memory
(`feedback_no_live_infra_fixes.md`).

---

## Chapter 7 — Remediation plan written, app stopped

Wrote `docs/STACK_REMEDIATION_PLAN_2026-07-01.md`, documenting all of Chapter
6's findings as five numbered items (pod-audit bug — already fixed;
compose-file-pairing requirement — root cause of the cascade; Postgres
credential mismatch — unresolved, needs the user's decision on which
credential wins before any fix; `api-gateway` auth-key issue — unresolved,
needs offline `docker compose config` inspection; foreign-project port
collisions — confirmed not-a-bug, no action needed) plus a recommended fix
sequence and a definition of done.

Then, per that plan's step 1: stopped the app cleanly —
`docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml stop`
(not `down`, no `-v` — non-destructive, data-preserving) for the base+overlay
services, plus a plain `docker stop` for the 41 dedicated-agent containers
(which compose considered "orphans" relative to that command and didn't
include). Confirmed zero running `deploy-*` containers afterward.

---

## Chapter 8 — Discovery: the user's own `stop_app.bat` had already wiped the database

When starting the mission-artifact review (next request from the user), tried
to bring back just `postgres`/`redis` via plain `docker start` (not `compose
up`, to avoid re-triggering Chapter 6) to query the battery's mission/chain-
trace data directly. **Both containers no longer existed at all** — not
stopped, removed. `docker volume ls` confirmed `deploy_postgres-data` and
`deploy_redis-data` were both gone entirely (`docker volume inspect` returned
"no such volume" for both).

**This was not caused by anything run in this session** — only `stop`
commands had been issued, never `down`, `rm`, or `prune`. The user clarified
they had separately run `C:\software\Holygrail\theFactory\stop_app.bat`.
Reading that script's call chain (`stop_app.bat` → `scripts/force_stop.py` →
`make down` → `docker compose ... down -v`, with an identical `down -v`
fallback if `make down` fails) confirmed the `-v` flag deletes named volumes,
including `postgres-data` and `redis-data`. **This is what wiped the
database.** Generated code artifacts survived because `output/` is a host
bind-mount directory, not a Docker-managed volume.

This is now recorded as a standing gotcha in Claude memory
(`project_stack_ops_gotchas_2026-07-01.md`): `stop_app.bat` is destructive, not
a plain stop, and should come with a warning before being suggested or run.

The user confirmed: proceed with reviewing whatever survived (the `output/`
code artifacts, plus the evidence JSON and scratchpad JSON files saved to disk
*before* the wipe) rather than trying to recover the database.

---

## Chapter 9 — Findings compiled from surviving data

Reviewed all 20 missions' generated code directly from `output/mission-<id>/`
(survived), cross-referenced against
`docs/evidence/protocol_bus_mission_battery_latest.json` (the verify script's
saved output, captured before the wipe — has final state, missing-chain-events,
and audit-agent-routing per mission) and one full chain trace
(`chat-go`/`mission-3c760af1-...`) that had been fetched and saved to the local
scratchpad directory earlier in the session, before the wipe.

This produced two new findings beyond Chapters 4-5:
- **2 of 20 missions (the C and R missions) generated code in the wrong
  language entirely** — both produced Python that *simulates* the requested
  language's behavior (a `ctypes`-based C-code-generator script for C; a
  Python function replicating R's vectorization/recycling/NA-coercion rules
  for R) rather than real C/R source files. **Both missions still reached
  `COMPLETE`** — no verification gate currently catches
  generated-language-vs-requested-language mismatches.
- **Support-ring usage was only partial.** Security, VC, and Tester fire
  unconditionally on every mission (confirmed in the Go trace). Compliance's
  activation is a narrow keyword-substring match on the CEO's delegation
  rationale text (`_extract_support_agent_flags` in `mission_flow_v2/base.py`)
  — essentially unreachable by the battery's ordinary prompts. Deploy's
  `MISSION_DEPLOY_READINESS_ASSESSED` event did not appear in the one captured
  trace, but this could not be re-verified due to the data wipe.

All of this — plus the 18/20 artifacts that *were* correct (several,
especially the Ruby and Haskell missions and the modernize-mission Python fix,
genuinely excellent) — is written up in full in
`FIRST_FULL_SYSTEM_RUN_FINDINGS_2026-06-30.md`, including a §6 recommendations
section (Beta insertion-point fix, a proposed generated-language verification
gate, reconsidering Compliance's trigger, re-confirming Deploy, and a process
recommendation to keep validating through the real chat UI going forward).

---

## Chapter 10 — Docs and memory updated

Updated `docs/CURRENT_TODO.md` and `docs/HANDOFF_CURRENT.md` to record
everything above (Current Status section, Protocol Bus Program section, Known
Gaps table, Next Actions list) — all still uncommitted as of this writing (see
Chapter 11).

Updated Claude's persistent memory
(`C:\Users\kevin\.claude\projects\C--software-Holygrail-theFactory\memory\`):
- `project_pbla_first_full_run_2026-06-30.md` — the PBLA/battery outcome and
  both bugs, with an explicit instruction to re-check whether fixes have
  landed before assuming so.
- `project_stack_ops_gotchas_2026-07-01.md` — the `stop_app.bat` and
  compose-file-pairing gotchas, plus the confirmed-non-issue on foreign
  container naming.
- `feedback_no_live_infra_fixes.md` — the explicit behavioral correction from
  Chapter 6/7.
- `MEMORY.md` index updated with pointers to all three.

---

## Chapter 11 — Current state as of the end of this session (READ THIS BEFORE DOING ANYTHING)

**The app is stopped.** All `deploy-*` containers (including the 41 dedicated
agents) are stopped; the `postgres-data`/`redis-data` volumes are gone
(everything else's volumes are intact). `output/` on the host still has all
20 missions' generated code.

**Nothing from this session has been committed.** `git status` at end of
session showed, all still untracked/modified:

```
 M docs/CURRENT_TODO.md
 M docs/HANDOFF_CURRENT.md
 M services/orchestrator/orchestrator/llm_delegation/generators_artifacts.py   <- the pod-audit fix
 M tests/services/test_llm_delegation_unit.py                                  <- its regression test
?? FIRST_FULL_SYSTEM_RUN_FINDINGS_2026-06-30.md
?? MISSION_TESTS_SESSION_LOG_2026-06-30.md   (this file)
?? docs/PROTOCOL_BUS_MISSION_BATTERY_PLAN.md
?? docs/STACK_REMEDIATION_PLAN_2026-07-01.md
?? docs/evidence/protocol_bus_mission_battery_latest.json
?? scripts/protocol_bus_mission_battery.py             <- superseded, kept for reference
?? scripts/protocol_bus_mission_battery_verify.py       <- the actual verify tool used
```

(`docs/REPO_ZIP_IMPORT_MIGRATION_PLAN.md` also shows untracked — this was
**not created by this session**, do not attribute it here, and do not assume
its contents relate to any of the above.)

Last real commit on `main`: `3805397` ("docs: record PBLA Stage-1 completion
and live-proven cold-start fix").

**Immediate next steps, in order** (per
`docs/STACK_REMEDIATION_PLAN_2026-07-01.md`):
1. Resolve the Postgres credential mismatch — requires the operator's
   decision on which value (current `.env` vs. whatever the volume held) is
   correct. **The volume is gone now anyway** (Chapter 8), so this may be moot
   for that specific volume — a fresh `up` will `initdb` a new Postgres using
   whatever is currently in `.env`, so this finding is likely self-resolving
   once volumes are recreated from scratch. Worth a quick sanity check rather
   than assuming.
2. Resolve the `api-gateway` `INTERNAL_SERVICE_API_KEY`-resolves-empty issue —
   root cause still unconfirmed; start with `docker compose ... config` output
   inspection (no containers needed).
3. Decide whether to commit the pod-audit fix (Chapter 4) as-is, and whether
   to also apply the Beta fix (Chapter 5) before or after the next rebuild.
4. Rebuild `orchestrator` + `api-gateway` using the correct **two-file**
   compose combination (never the base file alone — Chapter 6).
5. Bring the stack up once, cleanly, and confirm full fleet health (0
   unhealthy, 0 stuck-`Created`) before running anything else.
6. Only then: re-run a fresh live mission to confirm the pod-audit fix and
   (if applied) the Beta fix, this time through the chat UI again — not the
   raw API (Chapter 1's lesson still holds).
