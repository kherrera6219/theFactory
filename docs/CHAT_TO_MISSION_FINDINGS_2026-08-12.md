# First full chat → mission run: findings and plan

Document version: 2026.08.12
Last updated: 2026-08-12
Status: Active
Audience: Maintainers and AI coding agents

The first mission driven end to end through the **Mission Control chat UI**
rather than the API. Closes the UI-driven gap in `docs/WORK_QUEUE.md` item 5 and
is the first observation of the PM's SOW-building loop working against a real
backend.

**Mission:** `mission-e42fd7e2-55cd-44ea-9ee3-02bde5e6366e` — "Home Lab Server
Monitoring Desktop Application with Email Alerts", Python/PyQt6, reached
`COMPLETE` with a 26,204-character artifact.

---

## What works, observed rather than assumed

The PM behaves like a product manager, which is the core product expectation:

1. **Turn 1** — a deliberately vague request ("I want a desktop app to track my
   home lab servers") produced **five genuine product decisions**, each with a
   recommended default: GUI framework (PyQt6 / Tauri / Electron), monitoring
   depth (ICMP+HTTP vs SSH/SNMP), storage (JSON vs SQLite), packaging, and
   acceptance criteria. The right-hand panel showed **WAITING FOR ANSWERS** with
   *Proceed with Defaults* / *Edit Answers*.
2. **Turn 2** — a follow-up requirement ("can it also alert me by email") was
   folded into both the title and the scope, and a full **Feature Contract**
   appeared with scope, language, estimated duration and *Confirm and Start*.
3. **Confirm** → mission created, full delegation chain, `COMPLETE`.
4. `PM_AUTO_ACCEPT_DEFAULTS_ENABLED` correctly did **not** fire
   (`user_intent=finalize_plan`, `pm_auto_accepted_defaults` absent), confirming
   the auto-accept path is scoped to API/automated missions only and leaves the
   conversational product experience untouched.
5. The mission-type-aware LogicNode panel correctly reported "Not applicable"
   for a BUILD_NEW mission.

---

## Defects found

### D1 — The sandbox generates install commands that can never succeed

`testdata_agent._install_commands` emitted `pip install PyQt6`. The sandbox runs
`--network=none` **by design** — untrusted generated code must not reach the
network — so the install failed with DNS resolution errors and the application
never started:

```
WARNING: Retrying ... Failed to establish a new connection:
[Errno -3] Temporary failure in name resolution
```

This affects every artifact with a third-party dependency, in Python
(`pip install`) and JavaScript/TypeScript (`npm install`). It is not a
misconfiguration to be fixed by enabling the network; run-time installation is
incompatible with the sandbox's central security property.

### D2 — The report blamed the wrong cause

With the install broken the artifact never ran, and the verdict recorded
`not_exercised_note: "no invocation could be derived from the artifact's usage
example"`. The real cause was unmet dependencies. The note is written into
evidence, so a misattributed reason is worse than a vague one.

### D3 — Some artifact classes cannot be verified by execution at all

A PyQt6 desktop application needs a display server; running it headless proves
nothing even with its dependencies present. The same is true of servers (which
do not exit) and libraries (which have no entry point). Runtime QC currently
assumes every artifact is a CLI program that runs to completion.

### D4 — `detectUserIntent` matches "proceed" as a substring

`apps/mission-control/app/(shell)/chat/page.tsx:207` treats any message
containing `proceed`, `finalize`, `procced`, `procede` … as approval, and
`confirmAndLaunch` fires whenever a contract already exists. It did not bite
during this run only because no contract existed after turn 1 — the clarification
panel does not set one. Once the contract is on screen, *"before we proceed, can
it also do X?"* launches the mission instead of revising scope, which is exactly
the phrasing a user reaches for at that moment.

### D5 — PASS on an artifact that never executed

The verdict was `PASS` with `verified_scope_detail: started_only`. Honest about
scope, but "PASS" overstates it: nothing ran. An artifact whose dependencies
could not be installed is **not verifiable**, which is a different outcome from
"verified as far as startup".

---

## Plan

Ordered by whether the defect can produce a wrong answer that someone acts on.

### P1 — Stop attempting impossible installs; report unmet dependencies honestly
**Fixes D1, D2, D5.**

- `_install_commands` must not emit `pip install` / `npm install` for the
  offline sandbox. Emitting a command known to fail is what produced both the
  wasted run and the misattributed reason.
- Before executing, compare `generated_output.dependencies` against what the
  base image provides. If any are unmet, return
  `verdict: DRY_RUN`, `reason: "artifact requires dependencies that cannot be
  installed in an offline sandbox: <names>"` — never `PASS`.
- Keep `not_exercised_note` for its actual case (no derivable invocation) so the
  two reasons stay distinguishable in evidence.
- Follow-up, not required for correctness: curated images with common
  dependencies pre-baked, which converts some of these from DRY_RUN to executed.

### P2 — Classify the artifact before deciding how to verify it
**Fixes D3.**

Runtime QC should choose a strategy from what the artifact is:

| Class | Verification |
|---|---|
| CLI taking arguments | execute with the derived invocation *(works today)* |
| GUI / desktop | parse-or-compile only; record `verified_scope: compiled_only` |
| Library / module | import check |
| Server / daemon | start, probe, terminate *(later)* |

The signal is already available: the mission contract's `output_mode`, the
dependency list, and the usage example. A PyQt6 app should reach
`compiled_only` — `python -m py_compile` proves it parses without needing PyQt6
installed — rather than a meaningless execution attempt.

### P3 — Require approval-shaped confirmation in chat
**Fixes D4.**

Replace the substring test with a match that will not fire inside a question:
ignore messages ending in `?`, require the approval token near the start or as
the whole message, and keep the explicit *Confirm and Start* button as the
primary path. A mis-fire here launches a build the user did not ask for, which
is the most user-visible failure of the four.

### P4 — Re-run this scenario after P1–P3

Same prompt, same path, and confirm: the report distinguishes "unmet
dependencies" from "no invocation", a GUI artifact reaches `compiled_only`
rather than a doomed execution, and a follow-up question phrased with "proceed"
revises scope instead of launching.

---

## Not changed

`RQCA_ENFORCEMENT_ENABLED` stays `false`. D5 is precisely the class of wrong
verdict that enforcement would convert into a blocked mission, and P1 has to land
first.
