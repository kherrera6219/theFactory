# Current TODO

Document version: 2026.08.17
Last updated: 2026-08-17
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

This is the active TODO list for theFactory. Superseded sprint plans, historical
backlogs, and old phase notes live under `docs/archive/` and should not be used
as current work.

---

## Current Status

**NEW — 2026-08-17: next initiative is the PM-led SOW factory.** End state:
the user talks to the PM (product + program + sales for the factory) to
**create** software or **import** existing software for rework / port /
update. They get a real Statement of Work — including a factory cost
estimate — **before** they approve. Work is tested, QC'd, and saved locally.

Canonical plan: [`docs/PM_SOW_FACTORY_PLAN_2026-08-17.md`](PM_SOW_FACTORY_PLAN_2026-08-17.md).
**P0–P4 are on `main`.** Chat ZIP attach + repo page handoff into the PM
SOW; codegen can emit a file tree; CostPanel shows quoted vs actual vs
cap; continue-with-PM is a change order; sandbox `docker.sock` lives on
`sandbox-runner` (`SANDBOX_EXECUTOR_URL`). Local `.env` enforcement is
`true` (gitignored).

**Coverage gates** (PR #463, `dd13785`, floors raised `98c165d`): line ≥80%,
branch ≥70%, mixed ≥80%, plus per-file floors. Every critical file is at
**at least 80%** (`rqca_agent` 80%, `sow_estimator` 80%, `file_tree` 80%,
sandbox/SOW 90%). Mission Control measures `app/lib/**` via
`npm run test:coverage`.

**Rebuild (2026-08-17, after 80% critical floors):** full-dedicated stack
rebuilt with `sandbox-runner`. `sandbox-runner`, orchestrator, api-gateway,
mission-control, and all 41 dedicated agents reported healthy.

**Live proof (2026-08-17):** both unique-factory claims ran on the rebuilt
full-dedicated stack. Evidence:
`docs/evidence/end_state_live_proof_20260817.json`.

- **PORT through accepted SOW** — `mission-dc0c8c4e` `COMPLETE`. Official
  type `PORT`. Output `go.mod` + `main.go` (Python adder → Go).
- **Failing tests block COMPLETE** — `mission-8db1af71` stayed `VERIFIED`.
  RQCA `qc_verdict=FAIL`, event `MISSION_RUNTIME_QC_BLOCKED`. Not delivered.

Fix required for the QC proof: after `docker.sock` left the orchestrator,
RQCA still ran local `docker info` and every mission became `DRY_RUN`.
It now probes `SANDBOX_EXECUTOR_URL`. Python QC tests run via stdlib
`unittest` because `python:3.11-slim` has no pytest.

**Coverage line floor** is locked in tests: mixed >80% cannot hide line
<80%; Makefile and CI must keep `--line-threshold 80`. Every critical
file is floored at **at least 80%** (`rqca_agent` raised from 70%).

**Next action:** EDCP live-bus, failure injection, provider fallback.
Chat ZIP through the UI (this proof used the same SOW+mission APIs the
Chat Accept path calls).

---

**NEW — 2026-08-16/17: honesty gates, Gemini 3.7 Flash, and tests-as-QC
landed on `main` (PR #460, `0b6ee4c`).** Session work after the 2026-08-12
gates-opened pass. Live Snake mission
`mission-911a6b3f-06a7-451f-a49b-57f6cc73a951` reached `COMPLETE` and exposed
four role failures; those plus a follow-up code review were fixed and rebuilt
into the full-dedicated stack.

| What shipped | Detail |
|---|---|
| Honesty gates | `started_only` is `DRY_RUN` / `ADVISORY`, never PASS. Agent-off + `RQCA_ENFORCEMENT_ENABLED` is not-ready (skip is not a QC result). `AUTH_MODE` fails in every environment; `check_env.py` validates `AUTH_MODE` and rejects empty `SANDBOX_WORKSPACE_HOST_ROOT=`. |
| Gemini 3.7 Flash | All agent routes, vault, gateway allow-list, compose, and cost ledger. |
| BUILD_NEW role honesty | Specialist IR/PEP boilerplate is replaced from the contract; pod-audit is WARN/unscored on empty or routing-stub LogicNodes; specified stdlib/CLI games no longer get arcade PM questions. |
| Tests are the QC command | Integration tests generate **before** the testdata manifest. `_select_sandbox_command` prefers the language test runner over a default `run_command`. Python uses stdlib `unittest` (`python:3.11-slim` has no pytest). Interactive/gui/server/library run those tests when present; syntax-only success is ADVISORY. `while True` and bare `.listen(` no longer force compile-only. Cached `started_only` PASS reports are re-assessed. |
| Electron dual-launch | Packaged Mission Control uses `/api/gateway`, not a bare `:8100` call. |

**Local `.env` override:** compose default is `RQCA_ENFORCEMENT_ENABLED=true`.
A checked-in local `.env` may still set `false` — FAIL will not block delivery
until that line is `true`. Do not treat the local override as the product
default.

**On GitHub:** `main` includes the PM SOW factory, `sandbox-runner`,
coverage floors (PR #463), and live PORT + fail-QC evidence (`d9e3b3e`).

**Still owed after the SOW factory (see `docs/WORK_QUEUE.md`):** failure
injection, provider fallback, and Phase 6 EDCP live-bus. PORT-through-SOW
and failing-QC-blocks-COMPLETE are recorded. Sandbox privilege is on
`sandbox-runner`.

---

**NEW — 2026-08-05: legal-hold audit artifacts were never being stored, and the
two live test suites never authenticated.** Both were silent failures that a
green suite actively concealed.

**Object Lock.** `object_store.ensure_bucket()` created the artifact bucket
without `ObjectLockEnabledForBucket`, while `put_audit_report()` correctly
refuses to write a legal-hold object to a bucket that cannot hold one. Object
Lock can only be enabled **at bucket creation** in S3 and MinIO, so every audit
report with status `FAIL`/`FAILED`/`REJECT`/`REJECTED`/`ERROR` was dropped while
`/internal/audit-reports` still returned 200. Proven live: the same report
posted `PASSED` mirrored and appeared in `audit-artifacts`; posted `FAILED` it
returned 200 and the listing stayed empty.

The refusal is correct and **must not be relaxed**. Fixed by creating a
lock-capable bucket and making its absence impossible to miss:

| Change | Detail |
|---|---|
| `ensure_bucket()` | requests `ObjectLockEnabledForBucket=True` when `object_storage_legal_hold_on_fail` is set; falls back to unlocked only if the backend rejects it |
| `_bucket_has_object_lock()` | returns `True`/`False`/**`None`** — an auth or network failure is *unknown*, never "no lock" (an earlier cut alarmed on a credentials typo) |
| Surfacing | ERROR log at startup + `orchestrator_optional_adapter_object_lock_enabled` gauge + `object_storage_object_lock_ready` on `/health` and `/readyz` |
| `LegalHoldUnavailableError` | lets callers separate a permanent misconfiguration from a transient outage; `/internal/audit-reports` returns `object_storage_mirror: {stored, legal_hold_refused, detail}` |

**`object_storage_object_lock_ready` is deliberately not folded into
`object_storage_ready` or `/readyz`'s `ready`** — reachability and compliance
capability are different facts, and failing readiness would make the live
data-plane test *skip* rather than fail, trading one silent non-verification for
another.

**Local bucket migrated non-destructively.** The three existing objects were
backed up (SHA-256 verified in two locations), `.env` now sets
`OBJECT_STORAGE_BUCKET=mission-audit-artifacts-locked`, the orchestrator's own
`ensure_bucket()` created it **with** Object Lock on startup, and the objects
were restored. The old bucket is untouched and is the rollback path. A `FAILED`
report now stores with `X-Amz-Object-Lock-Legal-Hold: ON`, `Mode: COMPLIANCE`,
retained to 2026-11-03. **Fresh environments need no override** — they get a
locked bucket under the default name.

**Live test authentication.** Both suites posted to gateway `/v1/*` with no
`x-api-key` under `AUTH_MODE=api_key`, so every call 401'd when the stack was up
and passed trivially when it was down. `tests/services/live_stack_auth.py` now
resolves the credential for both (so they cannot drift apart again) from
`LIVE_INTERNAL_SERVICE_API_KEY` → `INTERNAL_SERVICE_API_KEY` → the repo `.env`,
walking upward from `__file__` so it resolves from a git worktree too. **No
well-known placeholder default.** The header is injected inside `_request_json`
so no request can go out bare, and the extended suite carries module-level
`skipif` markers keyed on gateway reachability.

**`test_live_mission_chain_and_artifact_integrity` could never have run.** It
waited for `COMPLETE` with a prompt that scored the maximum `ambiguity_score` of
**1.0**, parking every run in `CLARIFYING`. A far more detailed replacement also
scored 1.0 — the PM will find something to ask about almost any prompt, which is
why the design pairs clarifying questions with a *proceed-with-defaults*
operator action. The test now drives that documented path via
`POST {orchestrator}/missions/{id}/clarify` and asserts the four delegation-chain
events it actually inspects, then the build artifact. It runs a real mission to
`VERIFIED` with a 20-event chain.

**Full suite: 1929 passed, 4 skipped, 0 failed**, both live suites green against
a running stack.

**NEW — 2026-08-04: the first BUILD_NEW mission to reach `COMPLETE`.** Four live
runs of the same CSV-to-JSON CLI mission were needed. Runs 1–3 all stranded at
`VERIFIED` on the same cascade, each time for a *different* string in the
contract:

```
artifact_format_matches_contract FAILS (required, false positive)
  -> equivalence passed = false
    -> security_compliance: "no passing equivalence evidence"
      -> status = blocked, blocking = TRUE  -> stuck at VERIFIED
```

An advisory check reaching through security compliance to hard-block a correct
mission. The three triggers, in order:

| Run | Trigger | Field | Fix |
|---|---|---|---|
| 1 | `"a valid CSV file"` | `acceptance_criteria` | operand detection (`<format> file` the tool *operates on*) |
| 2 | `` `csv2json input.csv -o output.json` `` | `acceptance_criteria` | filename-literal detection (a dot after a word char is a usage example) |
| 3 | `"-o/--output to specify output JSON file destination"` | **`functional_requirements`** | runtime-output detection, keyed on a `--flag` token |

**The process lesson is the durable one.** Fixes 1 and 2 each passed their own
tests and still failed live, because both were validated against
`acceptance_criteria` alone while `_contract_format_text` reads **five fields
across two contracts** (`summary`, `title`, `functional_requirements`,
`acceptance_criteria`, `deliverables`). A test now runs through
`_contract_format_text` itself, so a format demand hiding in an untested field
cannot pass unnoticed again.

Run 3's fix deliberately keys on a `--flag` token rather than the word
"output": keying on "output" would suppress *"the output must be a single HTML
file"*, and "command-line" would suppress *"a command-line tool delivered as a
single HTML file"* — both genuine deliverable demands. A false negative in this
check is silent, so the narrow signal wins. Tests pin both directions.

**Run 4 evidence (UPG-20 candidate).** `mission-7a098d0f-f695-47b5-9c0f-79f18e58afd6`
reached `COMPLETE`; equivalence `passed=true`, security compliance `passed` with
no findings. The delivered `csv2json.py` (3111 bytes) was executed independently
and satisfies every acceptance criterion: int/float/bool/null inference,
case-insensitive booleans, `-o` writes a file with no stdout, `--help` works.
It also preserves leading zeros (`01234` stays a string) — behaviour beyond the
contract, documented in its own docstring.

**Behavioural equivalence remains honestly `skipped`** with reason
`"no Refined-IR module in mission metadata"`. This is architectural, not a bug:
BUILD_NEW missions have no source to extract LogicNodes *from*, so there is
nothing to project equivalence vectors out of. Phase 5 currently verifies
missions that transform existing code, not missions that create new code. See
the open decision below.

**Also fixed 2026-08-04: compose topology detection was a census, now a fact.**
`scripts/compose_topology.py` decided topology by asking "is `agent-01-pm` up?",
which made `CONDENSED` a *fallback* — mid-startup, a crashed `agent-01-pm`, and
a partial teardown all read as condensed, and the guard then refused a
legitimate full-dedicated start. The crashed case locked the operator out of
restarting the very stack the guard protects. It now reads the
`com.docker.compose.project.config_files` label Docker stamps at container
creation, so a single surviving container reports the truth. Hit live when a
start ran while `up` was still creating containers.

**NEW — 2026-08-01: a full design-vs-build audit was completed and an
upgrade plan now supersedes ad-hoc prioritisation.** Two new documents in
`docs/` are canonical for all forward work:

- `docs/DESIGN_VS_BUILD_AUDIT_2026-08-01.md` — read-only comparison of the built
  application against the Holy Grail Refinery design corpus (143 design
  documents). Verdict: the infrastructure, security, bus, data plane, UI, and
  test surface meet or exceed the design; the **semantic engine does not**.
  LogicNodes are 7-field envelopes rather than the designed 30-field semantic
  nodes; the Refined-IR projection is templated, not extracted; "equivalence
  verification" checks contract conformance rather than behaviour; the
  14→4→1 comprehension model, the Doc 30 LogicNode Registry, and binary
  synthesis have no implementation. Three of the six bus lanes' worth of
  work is done — all six now have live producers, but only Sigma is consumed.
- `docs/UPGRADE_RECONCILIATION_PLAN_2026-08-01.md` — the ordered execution plan
  that closes it, **Phases 1–7**. **Start at its §0 (Cold start) if you are
  picking this up with no context.** Work item IDs are `UPG-<phase><item>`
  (`UPG-1x` = Phase 1, `UPG-2x` = Phase 2, …); Phase 6 uses the `EDCP-*` IDs
  from `docs/EDCP_PHASE_PLAN.md`.

**Three decisions are settled and are not open questions:**

| # | Decision | Chosen |
|---|---|---|
| D1 | Semantic engine | **Pragmatic middle** — enrich LogicNodes additively, make RIR extraction real where AST support already exists, build execution-based equivalence for a language subset. **No 4-pod fan-out.** |
| D2 | Binary synthesis / LLVM | **Formally killed** — ADR + docs + agent role text |
| D3 | Protocol Bus | **Commit to EDCP** — the bus becomes load-bearing, starting with a Delta consumer that can gate a mission |

**DONE — UPGRADE plan Phase 1 (2026-08-01).** All five exit criteria met.
`docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md` is now the **governing verdict
document** — one Implemented/Superseded/Deferred verdict per design area, and it
outranks the numbered design corpus. `docs/DESIGN_TRACEABILITY.md` maps all 64
design documents to implementing modules. `docs/IMPLEMENTATION_STATUS.md` is
rescoped ("feature-complete against the v1.3 mission-pipeline scope", plus an
explicit "Semantic depth — scoped out" row) and no longer contradicts
`docs/LOGICNODE_SCHEMA.md`. Binary synthesis is formally retired: `AGENT-11-DEPLOY`
→ *"Artifact packaging, delivery, and environment setup"*, `AGENT-09-HW` →
*"Reserved: target-profile hints for generation (no compilation role)"*.

**Three plan premises failed validation against live code and were deliberately
not executed as written** — full detail in the ADR's "Corrections to the audit and
plan" section: (1) `agent_personas.py`'s LLVM reference was **kept**, because it
accurately describes Julia's own compiler rather than claiming theFactory emits
LLVM IR; (2) UPG-11's "strip binary claims from `docs/`" and (3) UPG-13's "remove
the 0.0001% figure" were both **already satisfied** by the 2026-07-03
documentation audit — the surviving occurrences are meta-references that name the
claims in order to retire them.

**One out-of-scope defect found and fixed:** `IMPLEMENTATION_STATUS.md` documented
`RQCA_ENFORCEMENT_ENABLED` as `false` / "Advisory by default" while
`settings.py:98` and `:228` default it to **`true`** (flipped by remediation
Phase 0, never reflected in the doc). A stale shipped *default* misleads operators
about whether a gate blocks. Corrected, plus two missing enforcement-flag rows.

**PARTIAL — UPGRADE plan Phase 2 (2026-08-01): UPG-21, UPG-22, UPG-23 DONE;
UPG-20 NOT STARTED.** Full backend suite 1768 passed / 5 skipped / 1 xfailed
(by design) / 0 failed; ruff clean; docs validation passes.

**UPG-22 was a live bug, not cosmetic drift.** `DEFAULT_EVENT_PRIORITY` is
operator-settable (`settings.py:290`) and was written into the event envelope
unvalidated while `schemas/event.envelope.schema.json` accepted only
`NORMAL|HIGH` — so setting it to a lowercase Protocol Bus value (the natural
thing to type, since the bus `/send` API uses `low|normal|high|critical`) made
**every mission state envelope fail validation**. Three write sites affected;
`phases_intake.py` degraded silently to a warning and dropped the partition
envelope. Fixed additively: the schema now accepts all six values, writers
normalise via new `shared_runtime.protocol.to_event_priority`, output stays
byte-identical for existing configs, and an unknown value raises at the write
site. Six regression tests proven to fail against pre-fix source.
New `docs/PROTOCOL_ENVELOPES.md` documents both transports.

**A plan premise was wrong and is corrected there:** UPG-22 says
`correlation_id` carries `mission_id` on both paths. It does not and **cannot** —
the bus reuses `correlation_id` as both the replay-rejection key
(`mcp_server.py:624`) and the dedup key (`:650`), so producers send a composite
(`delta-{mission_id}-{pod_name}`). A bare `mission_id` would make the second
emission for a mission look like a replay and be dropped. **The transports join
by prefix parse, never equality** — a Phase 6 Delta consumer that queries by
equality finds nothing and fails silently.

**UPG-21:** the flag's two exit criteria contradicted each other (one wants a
failing test while the flag has no consumer, the other wants a green suite).
Resolved with `xfail(strict=True)` — green today, turns red on purpose the
moment Phase 5 wires the flag.

**UPG-23 scope note:** `pod="Pod D"` is a **routing key**
(`mission_flow_v2/base.py:151` → `podD`), not a label. Only descriptive strings
changed; all four pod keys and agent counts verified intact after the edit.

**DONE — UPGRADE plan Phase 3 (2026-08-01): LogicNode schema v2.** All five exit
criteria met. Full backend suite **1796 passed, 0 failed, 0 errors** (up from
1768 — 28 new tests). `scripts/validate_schemas.py` passes; ruff clean.

UPG-30 promoted `domain`, `concept`, `confidence`, `source_language`, and
`extraction_method` to first-class **optional** top-level properties, and
reserved `paradigm`, `purity`, `complexity`, `source_license`, `tags` in the
schema without populating them (an absent field means "not determined" — a
default would be a false claim; `purity` is Phase 4's job). `payload` still
carries every value it carried before, so no existing reader breaks.

UPG-31 populated `types.in`/`types.out`, which were previously **always empty**.

**⚠ UPG-31 was not the "wiring, not new analysis" the plan described.** Every
AST extractor's structured output was being **flattened to
`FunctionInfo(name, line, signature)`** on entry to `ExtractionResult` —
`language_extractor.py:348` discarded Python's `arg_types`/`return_annotation`
outright. And of the seven languages the plan named, only **Python** and
**Java** carry structured types at all; **Haskell** has a parseable declared
signature. Go carries `receiver`, OCaml `is_recursive`, Julia and JS/TS only a
raw signature string — extracting types from those *is* new analysis, so they
stay honestly empty. Two unanticipated changes were needed: `FunctionInfo` was
widened additively, and a concept→function correlation step was added (nodes are
built per concept, signatures are per function, and the two arrive as unlinked
sibling lists). The correlation refuses to guess and cannot invent types.

**DONE — UPG-20 durable evidence (2026-08-12).**
`docs/evidence/s1_01_live_generation_go_20260811.json` — Go BUILD_NEW
`mission-f8a5accf` reached `COMPLETE`. Additional live proofs since: chat
PyQt6 `mission-e42fd7e2`, Snake `mission-911a6b3f`. Phase 6 (EDCP) is no
longer blocked on S1-01; it is still off
(`EVENT_DRIVEN_CONTROL_PLANE_ENABLED=false`) and not live-bus proven.

**Stack ops: both former footguns are fixed (2026-08-03).** Teardown now
preserves volumes by default (`make down-wipe` or `force_stop.py --wipe-volumes`
to delete), and `start_app.bat` refuses to start a topology that conflicts
with what is already running. `make topology` reports the running topology
and its correct paired commands.

**DONE — UPGRADE plan Phase 4 (2026-08-01): real Refined-IR projection.** All
six exit criteria met. Full backend suite **1816 passed, 0 failed, 0 errors**
(up from 1796 — 20 new tests).

Refined-IR is no longer "schema-valid but semantically empty". For AST-backed
input: real typed signatures, a real statement-level op stream (a 2-branch
function yields 7 ops where there was 1), `purity` from genuine side-effect
analysis (`PURE` vs `IMPURE` with `effects: ["io.filesystem"]`), and executable
equivalence vectors of concrete typed arguments. `projection_method`
(`templated_v1`/`ast_v1`/`mixed_v1`) makes the artifact self-describing, so the
honesty no longer lives only in prose. The templated path **remains** for
languages with no recoverable signature.

**Two additions beyond the plan, both for honesty:** `purity` gained
**`UNKNOWN`** — analysis cannot always decide, and reporting `PURE` for a
function that calls something unresolvable would be a false claim; and
`projection_method` gained **`mixed_v1`** at module level, because one file
legitimately mixes AST-backed and regex-only extraction.

**UPG-42 deliberately stops short of inventing expected outputs.** Vectors carry
concrete arguments but `expected: null` — the expected output isn't knowable
until something executes the artifact, and fabricating one would recreate the
"vector that can never fail" problem. Phase 5 fills it by execution.

**DONE — UPGRADE plan Phase 5 (2026-08-02): behavioural equivalence.** All six
exit criteria met. Full backend suite **1843 passed, 0 failed, 0 errors**.

`equivalence_verifier.py` answered *does the artifact match its contract*. It is
now joined by a second scope that answers *does it actually behave*: the
mission's Phase 4 equivalence vectors are executed against the artifact in a
sandbox and a real pass ratio is recorded. Both scopes render separately in
Mission Control.

**The sandbox is genuinely shared, not copied.** The hardened `docker run`
invocation moved to `orchestrator/sandbox_exec.py` and **RQCA was refactored to
call it**, so security flags are defined in exactly one place. A test asserts
both callers reference the same function object *and* that neither module
contains its own `--network=none` — a future copy-paste executor fails the suite
rather than passing review.

**UPG-21's strict-xfail fired exactly as designed**, two phases after it was
written: wiring the flag made the test pass unexpectedly, turning the suite red
on purpose. Marker removed, assertion now live.

**The honesty rule to preserve through any future change:** a vector that merely
*ran* is reported as `executed_without_error`, never `passed`. Phase 4 leaves
`expected: null` deliberately, and counting execution as verification would
recreate the "check that can never fail" this phase exists to remove — a
regression that would make every number look better.

**DONE — UPGRADE plan Phase 7 (2026-08-03): consolidation.** All four items.
Mission Control **146 tests pass**, `tsc --noEmit` clean.

- **UPG-70** — LogicNode dependency graph on the LogicNodes page. **No graph
  library added** — the page runs under a CSP forbidding `unsafe-eval` and the
  layered type-flow layout is small enough to render as plain SVG. Derivation is
  a pure module (`lib/logicnode-graph.ts`) with 15 unit tests. Edges are **type
  flow**; where no types were recovered there are no edges and the UI says why.
- **UPG-71** — Doc 14 formally **Superseded** by `mission_flow_v2/transitions.py`.
  Removing the 730-line disabled engine is scoped in the ADR but deliberately
  deferred until after UPG-20, so a lifecycle change isn't competing with a
  lifecycle validation.
- **UPG-72** — `docs/MISSION_TAXONOMY.md`, written from the code.
- **UPG-73** — Doc 30 deferral formalised with a measurable trigger.

**UPG-72 surfaced a real defect, recorded not patched:** `type_strategy` in
`llm_delegation/prompts.py` covers only 7 of 10 mission types, so `RUN_QC`,
`ARCHITECTURE_DOCS`, and `SELF_ANALYZE` silently get **`BUILD_NEW`'s** routing
instruction — "strongest code generation capability" — for missions that generate
no code. Writing the three missing strategies is a product decision, not a
mechanical fix.

**Everything that can be done offline is now done.** The remaining upgrade-plan
work is **UPG-20** (live mission evidence) and **Phase 6 (EDCP)**, which UPG-20
blocks. Next step is the rebuild + live test.

**Note on the Electron/Windows work:** Phase 4 of the Full Whole-App Remediation
Plan (below) is *orthogonal* to the upgrade plan and is not blocked by it. Either
can proceed first. The upgrade plan's Phase 1 is cheaper and removes more risk.

---

**Previous work: Phase 3 of the Full Whole-App Remediation Plan is done
and verified.** `docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §6 —
documentation accuracy (findings #15/#28). `docs/METRICS_SOURCE_MODULES.md`
(rewritten 2026-07-03) turned out to omit four entire source modules, not
just four metric names: `llm_delegation/metrics.py`, `pod-worker/main.py`,
`audit-worker/main.py`, and `agent-runtime/main.py` were undocumented in
full, even though the four specific metrics the finding named
(`pod_worker_task_latency_seconds`, `agent_runtime_task_latency_seconds`,
`audit_worker_task_latency_seconds`, `factory_llm_tokens_total`) were already
referenced by real alert rules and Grafana dashboards. Rather than patch in
just those four names, added complete, source-verified metric tables for
all four modules (matching this doc's own stated "verified against source"
standard) — 23 additional metrics now documented that weren't before. Also
fixed the stale casing mismatch (finding #28): `factory_missions_active`'s
label values and `orchestrator_metrics.py:57`'s comment both said lowercase
`queued`/`running`/`verified`; the real `_ACTIVE_GAUGE_STATES` set and the
`MissionStuckInRunning` alert use uppercase — both now read
`QUEUED`/`RUNNING`/`VERIFIED`. Verified: `scripts/validate_documentation.py`
passes, `ruff check` clean on the one touched `.py` file (comment-only
change, no behavior difference). **Next action: Phase 4** (Electron/Windows
installer buildout) — see `docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §7
and the Active Work Queue below; three sub-decisions there need explicit
user sign-off before implementation (§7.2, §7.4, §7.7).

Before that: Phase 2 of the Full Whole-App Remediation Plan was done
and verified. `docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §5 — frontend
UI correctness/accessibility (findings #3/#11/#12/#13/#14/#21/#22 plus
`global-search.tsx` dead-code cleanup; CSP `unsafe-inline` deferred to Phase
4 per the plan). Alerts "Acknowledge"/"Mark Resolved" (finding #3) needed
real new backend surface — alerts are recomputed fresh from live health
signals with no incident-record table, so per user decision a Redis-backed
ack overlay (`alert:ack:{alert_id}`, 24h TTL) plus a new
`POST /internal/operations/alerts/{alert_id}/state` endpoint were added.
Stale-response races (finding #11) fixed with a monotonic request-id ref in
`useArtifactData.ts`, `missions/detail/page.tsx`, and `missions/page.tsx`.
Non-semantic clickable divs (finding #12) fixed: a real `<button>` for the
output-page path card, `role`/`tabIndex`/`onKeyDown` for the protocol-bus
event `<tr>` (can't be a button — contains `<td>`s). Guided-tour keyboard
trap (finding #13) fixed and verified live in a browser — the card never
called `.focus()`, so its keyboard handler never received an event. Five
raw `\uXXXX` escape sequences (finding #14 named one, four more found
alongside it) fixed in `missions/detail/page.tsx`. Chat session retention
(finding #21) — per user decision, added a 30-day time-based expiry
alongside the existing count cap. Inconsistent 401/403 handling (finding
#22) — extracted a shared `isOperatorAuthError`/`operatorRecoveryMessage`
heuristic and `<OperatorAuthErrorAction>` component, applied consistently
across 5 pages; `app/unlock/page.tsx` was already a legitimate redirect, not
a dead stub. Verified: full Mission Control Vitest suite (113 tests),
`tsc --noEmit`, `npm run build`, full backend suite, `ruff check .` all
clean; guided-tour behavior verified live in a browser (frontend dev server
only — backend stack wasn't running, so the Alerts round-trip and
fast-navigation race couldn't be exercised end-to-end). **Next action:
Phase 3 (documentation accuracy)** — see
`docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §6 and the Active Work
Queue below.

Before that: Phase 1 of the Full Whole-App Remediation Plan was done
and verified. `docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §4 — script/
tooling safety guardrails (findings #6/#7/#8/#9/#10/#19/#20/#24/#25/#27/#29).
Every destructive script now defaults to a safe preview requiring an
explicit `--execute`/`-Execute`/`-Yes` flag to mutate anything, and the
actual root cause of Phase 0's one noted "pre-existing, unrelated" test
flake was found and fixed. Full details in `docs/HANDOFF_CURRENT.md`'s
"Latest Completed Work" section.

Before that: Phase 0 of the Full Whole-App Remediation Plan was done
and verified. `docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §3 — hardened
five production runtime defaults (findings #1/#2/#18/#23/#26):
`RQCA_ENFORCEMENT_ENABLED` (compose default `false`→`true`, plus a
`load_settings()` fail-fast guard in production), MinIO/object-storage
default credentials (prod compose overlay now requires real values via
`:?`, plus a matching app-level guard against the literal
`minioadmin`/`minioadmin123`), `GATEWAY_ADMIN_BYPASS` (warn-only →
`RuntimeError` in production, matching the adjacent CORS-wildcard check),
`CORS_ALLOW_ORIGINS` (env-overridable, required explicit value in prod), and
agent-runtime's `SERVICE_API_KEY` (removed the `"worker-key"` fallback,
fails fast at import if unset). Verified: full backend suite (only one
pre-existing, unrelated order-dependent flake remains — confirmed identical
on the pre-Phase-0 baseline), `ruff check .` clean, `docker compose config`
merge re-verified for dev and prod overlays, and all three code-level guards
confirmed raising `RuntimeError` inside rebuilt `deploy-orchestrator`/
`deploy-api-gateway` containers under production settings (agent-runtime's
image lives in a separate, not-built-by-default overlay, so that fix was
instead verified via a subprocess-level regression test). Two new regression
test files added; 3 existing test files fixed to stay self-contained against
ambient environment state or to stop leaking `SERVICE_API_KEY` globally at
import time (a bug introduced and fixed within this same pass). Every
new/changed test proven to fail against the pre-fix code via `git stash`.
**Next action: Phase 1 (script/tooling safety guardrails)** — see
`docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` §4 and the Active Work Queue
below.

Before that: a full whole-application, read-only code review — findings
documented, nothing fixed yet. Every part of the app was reviewed, not just
the Windows/Electron packaging layer that was the initial scope ask: Mission
Control frontend UI, Electron/Windows packaging, the dedicated `agent-runtime`
service, deploy/infrastructure/CI, and `scripts/`. Full report:
`docs/FULL_APP_CODE_REVIEW_FINDINGS_2026-07-05.md`. Explicit instruction for
this pass was review-only ("dont fix anything as you go") so a single ordered
remediation/upgrade plan can be written next, as a separate step — **that plan
does not exist yet and is the next action.** Headline findings: the
compose-level `RQCA_ENFORCEMENT_ENABLED` default silently reverts this
session's own hardened code default back to `false` in every profile including
production; production MinIO credentials fall back to
`minioadmin`/`minioadmin123`; the packaged Electron app's 14 `app/api/*` routes
cannot function at all because the Electron build's static-export mode
physically hides `app/api` to work around a Next.js incompatibility; Mission
Control's Alerts "Acknowledge"/"Mark Resolved" actions don't persist. See
"Full Whole-App Code Review (2026-07-05)" under Recently Completed for the
full ~30-finding list, and the Active Work Queue below for the tracked
next-step item (write the remediation plan).

Before that: full documentation audit and reduction, plus one real
code bug found incidentally. Inventoried all ~105 active docs, deleted 3
that described entirely fictional systems (`EQUIVALENCE_VERIFIER.md`,
`IS_AGENT.md`, `PORT_COORDINATOR_AND_LOGICNODE_SCHEMA.md` — the real
modules are now documented in `SUPPORTING_MODULES.md`), archived 8
completed point-in-time plans/incidents to `docs/archive/2026-07-03/`, and
split `HANDOFF_CURRENT.md`/this file's ever-growing history sections into
their own archive files. Found two critical inaccuracies:
`LICENSE_STRATEGY.md` claimed MIT (repo is actually Dual AGPL-3.0/
Commercial with a mandatory CLA — README badge also fixed); `DATA_
CLASSIFICATION_POLICY.md` described a fictional 4-tier taxonomy not matching
the real `DataClassification` enum. 7 more docs were rewritten after a
verification pass found they described nonexistent class-based APIs
(`AGENT_SCALING_AND_HEARTBEAT.md`, `LLM_DELEGATION.md`, `PROMPT_REGISTRY_
AND_ASSETS.md`, `LLM_SAFETY_AND_DOCUMENT_PARSER.md`, `METRICS_SOURCE_
MODULES.md`, `OBSERVABILITY_STACK.md`, `DEPENDENCY_ABSORPTION_DOCTRINE.md`).
**Incidentally found and fixed a real bug**: the api-gateway tagged
sensitive-input missions with the invented string `"TIER_2_RESTRICTED"`,
which never matched the orchestrator's real enum value
(`"TIER_2_SENSITIVE"`) — `security_compliance.py`'s classification checks
silently never recognized these missions. Fixed and test-verified (1348
backend tests, 0 failures), `api-gateway` Docker image rebuilt. See
"Documentation Audit and Reduction (2026-07-03)" under Recently Completed
for the full list.

Before that: security review of the Mission Control frontend's
Next.js API routes — found the vault CRUD routes and the gateway catch-all
proxy had zero authentication. `apps/mission-control/app/api/`. Vault
routes (`GET`/`POST`/`DELETE /api/vault`, `POST /api/vault/test`) never
called `isAuthorizedVaultRequest` (dead code that existed and was tested
but never wired in) — any unauthenticated caller could list, overwrite, or
delete every vault secret including `OPERATOR-API-KEY`. The
`/api/gateway/[...path]` catch-all proxy — the path used for nearly all
backend traffic including mission creation — had no operator-session gate
at all, unlike every sibling privileged route. Both fixed by wiring in the
existing auth helpers (`isAuthorizedVaultRequest`,
`requireOperatorRequestSession`), the same pattern already used correctly
elsewhere in this app. Fixed and test-verified (104 frontend tests, 0
failures; `tsc --noEmit` clean). This was the final "everything else" slice
of the systematic backend+frontend review effort. See "Mission Control API
Routes Review (2026-07-03)" under Recently Completed for the full list,
including several findings judged consistent with this app's established
single-operator-role design rather than fixed as anomalies.

Before that: review of `shared_runtime/` — found an artifact
re-verification gap and a diagnostic-bundle secret leak.
`get_build_artifact` only recomputed an artifact's `verified` flag from a
real cryptographic check when a `signature_record` was present; for
artifacts where signing failed at build time (swallowed by a broad
`except`), `verified: true` was a write-time-only assertion never
re-checked against the currently stored bytes. Now falls back to
independently re-hashing and comparing against the recorded digest when
unsigned. Also fixed the maintenance diagnostic-bundle env-var sanitizer,
which only excluded names containing `_KEY`/`_SECRET`/`_PASSWORD` — real
vars (`VAULT_TOKEN`, `VAULT_ROLE_ID`) and connection-string vars
(`POSTGRES_URL`, `REDIS_URL`) with embedded plaintext passwords slipped
through. Fixed and test-verified (1348 backend tests, 0 failures),
`orchestrator`/`api-gateway`/`pod-a-worker` Docker images rebuilt (all
three import `shared_runtime`) and fixes verified inside the rebuilt
containers. See "shared_runtime Review (2026-07-03)" under Recently
Completed for the full list, including several accepted design tradeoffs
(RIR-module signature verification is explicitly "best effort"/non-fatal, a
low-blast-radius TOCTOU race in first-time signing-key creation).

Before that: review of the verification/compliance gate layer —
found both `MISSION_SECURITY_COMPLIANCE_ENFORCEMENT_ENABLED` and
`RQCA_ENFORCEMENT_ENABLED` defaulted to `false`, making the security-
compliance and RQCA runtime-QC gates warn-only rather than blocking out of
the box.** `equivalence_verifier.py`, `port_coordinator.py`,
`security_compliance.py`, `rqca_agent.py`. A mission with a detected
hardcoded secret, or one that failed runtime QC, proceeded straight to
delivery by default — `status` read `"warned"`, never `"blocked"`, unless
an operator explicitly opted in. **User-confirmed product decision: both
now default to `true`** (same pattern as the `PROMPT_GUARD_MODE` default
change from the api-gateway review), with env-var opt-out still available
for staged rollouts. Also fixed: a PORT two-phase extraction-phase
re-entrancy gap (the only sibling branch in `_prepare_specialist_plan`
with no `_chain_event_exists` guard — a second invocation while
`port_phase` stayed `"extraction"` would re-run two LLM calls and mint
fresh non-deterministic extraction results) and a security-compliance
report idempotency gap (unconditionally rebuilt and re-signed on every
completion-gate retry, overwriting the prior `signature_record`, with an
un-deduplicated audit event firing on every retry — now cached like the
existing RQCA report cache). Fixed and test-verified (1346 backend tests, 0
failures), `orchestrator` Docker image rebuilt and the new enforcement
defaults verified inside the rebuilt container. See "Verification &
Compliance Gates Review (2026-07-03)" under Recently Completed for the
full list, including several disclosed advisory-only heuristic limitations
left as architectural tradeoffs rather than quick patches.

Before that: correctness review of the pod-worker service — found
that `_consumer_loop`'s catch-all exception handler could silently and
permanently orphan/drop stream entries.** `services/pod-worker/pod_worker/`
(~5.1k lines). Two stacked data-loss bugs: (1) the generic `except Exception`
branch in `_consumer_loop` never acknowledged or DLQ'd a failed entry — with
no `XCLAIM`/`XAUTOCLAIM` recovery anywhere in this service, an unexpected
exception permanently orphaned the message in the consumer group's
pending-entries list; (2) `_write_dlq` itself could fail (e.g. a transient
Redis blip) while callers still unconditionally acknowledged the original
entry, silently dropping it forever even when the intent was to preserve it
in the DLQ. Both fixed: the catch-all now DLQs + acknowledges like the other
branches, and `_write_dlq` returns success/failure so callers only
acknowledge when the DLQ write actually landed. Also fixed: a `refined_ir.py`
bug that produced the literal string `"None"` as a function name instead of
falling back to the concept name, a JS/TS regex that silently dropped every
paren-less arrow function (`x => x + 1`) from extraction, a
`PythonAstExtractor` inconsistency that bypassed the 512 KB size guard for
AST parsing, and a Java static-import edge case that could inject an
empty-string import entry. Fixed and test-verified (1342 backend tests, 0
failures), `pod-worker` and `orchestrator` Docker images rebuilt (the
orchestrator image bundles `pod_worker.language_extractor` for AIM
generation) and fixes verified inside the rebuilt containers. One
architectural finding — `_run_agent_pipeline` runs agent execution
synchronously inside the async event loop, blocking the consumer/heartbeat
loops during CPU-bound work — was deferred as needing a scoped design
review rather than a reflexive `asyncio.to_thread` patch. See "pod-worker
Review (2026-07-03)" under Recently Completed for the full list.

Before that: security/correctness review of the api-gateway —
found 10 routes with zero caller authentication.** `create_mission`,
`get_mission_pod_assignment`, `get_mission_chain_trace`,
`create_pm_feature_contract`, mission logicnodes/knowledge/knowledge-graph/
audit-reports/audit-artifacts/audit-events/build-artifacts/build-artifact/
artifact-download, and `create_builder_preview` all forwarded to the
orchestrator's `/internal/*` routes with no check on the caller's own
credentials — any anonymous request could read mission prompts, source
code, and audit trails, or create missions / trigger paid LLM calls, for any
`mission_id`. All now require `_require_reader_access`. Also fixed: a
hybrid-mode `_require_operator_access` bypass (any non-empty `X-API-Key`
granted access with zero validation), an X-Forwarded-For rate-limit bypass
(new `GATEWAY_TRUST_PROXY_HEADERS` opt-in, default off), `PROMPT_GUARD_MODE`
default changed from `"log"` to `"block"` (user-confirmed product decision —
OWASP LLM01 prompt injection is now rejected by default), an Anthropic
`max_tokens`/`thinking_budget` mismatch that rejected every high-budget
thinking request, a Gemini-3 model-detection gap (`gemini-3.0-pro`/bare
`gemini-3` were missed), and an OpenAI refusal-content extraction gap. Fixed
and test-verified (1337 backend tests, 0 failures), `api-gateway` Docker
image rebuilt and fixes verified inside the rebuilt container. See
"api-gateway Review (2026-07-03)" under Recently Completed for the full
list including investigated-and-refuted candidates.

Before that: correctness review of the agent orchestration core —
found that AIM source-code extraction was silently non-functional in
production.** `agent_base.py`, `agent_registry.py`, `agent_personas.py`,
`agent_integrations.py`, `agent_scaling.py`, `is_agent.py`,
`dependency_absorption.py`, `aim_generator.py` (~5.3k lines). Two independent
bugs stacked in `_extract_file`: (1) the `pod_worker` import path arithmetic
resolved correctly in local dev but to the filesystem root inside the built
container (never verified against a real container before now), so the
import always failed; (2) even when reachable, the code filtered for a
concept `domain == "import"` that the real pattern catalog never produces.
Both were swallowed by a broad exception handler with only a warning log —
`function_count`/`class_count`/`concept_count`/`detected_imports` were
always the empty/zero fallback for every `ANALYZE_ONLY`/`PORT`/
`DEBUG_REPAIR`/`SECURITY_HARDEN`/`REDUCE_DEPENDENCIES` mission. Fixed both,
updated the Dockerfile to ship `pod_worker`, and verified the fix works
*inside a rebuilt container* (not just locally). Also fixed a
scaling-decision idempotency gap that could orphan partition work on retry,
and a Java-detection false negative. Fixed and test-verified (1332 backend
tests, 0 failures), `orchestrator` Docker image rebuilt. See "Agent
Orchestration Core Review (2026-07-02)" under Recently Completed for the
full list including deferred items.

Before that: correctness review of the orchestrator storage layer.
`storage_missions.py`, `storage_artifacts.py`, `storage_agents.py`,
`storage_pods.py`, `storage_logicnodes.py`, `storage_core.py`, `models.py`
(~3.1k lines) — the DB layer underneath every mission-flow phase. Found and
fixed a real concurrency bug: `insert_agent_action_event` read the latest
hash-chain digest and inserted the next event as two unsynchronized
statements, so two concurrent events for the same project could both chain
onto the same predecessor, silently forking the tamper-evident audit chain.
Fixed with a per-project advisory lock. Several other candidates
(object-storage artifact readback, `row_to_mission` column inference, two
`models.py` fields, self-loop event accumulation) were investigated and
refuted as live bugs by tracing actual callers. Fixed and test-verified (1328
backend tests, 0 failures), `orchestrator` Docker image rebuilt. See "Storage
Layer Review (2026-07-02)" under Recently Completed for the full list
including deferred items.

Before that: deep code review of the Mission Flow v2 lifecycle driver
and the LLM delegation layer, fixing 7 backend bugs. Two backend slices —
`services/orchestrator/orchestrator/mission_flow_v2/` and
`services/orchestrator/orchestrator/llm_delegation/` — were reviewed file by
file (not diff-scoped) using parallel finder agents, each candidate verified
against the actual code before fixing. Most serious: a driver re-invocation
bug where every orchestrator restart re-ran the `queued->pm_intake` preparer
for any in-flight mission, silently regenerating and overwriting
`feature_contract`/`mission_charter` with a fresh, non-deterministic LLM call.
Also fixed: duplicate partition-emission on retry, runtime QC re-executing on
every completion-gate retry, a greedy JSON-extraction regex that discarded
valid LLM decisions, an `intake_status` normalizer that failed open instead
of closed, a Windows drive-relative path-traversal edge case, and a defensive
hardening fix for a non-numeric `risk_score`. All fixed and test-verified
(1327 backend tests, 0 failures), `orchestrator` Docker image rebuilt from
this code. See "Mission Flow v2 + LLM Delegation Review (2026-07-02)" under
Recently Completed for the full list, including deferred lower-priority
findings.

Before that: code review of the Mission Control UX lock-in commits,
plus fixes for all five findings. The review covered the five commits
implementing PM clarification, progress visibility, artifact folder discovery,
and follow-up mission continuation. It found and fixed: a critical
stuck-mission regression (generated-output completion gating could swallow a
packaging failure and leave a mission permanently unable to reach
`COMPLETE`), a critical missing-auth gap on the three new local-filesystem
routes (`open-vscode`, `open-output-folder`, `output-folder-status` had no
session check, unlike every other sensitive route), a false-negative PM
clarifying-question suppression (the word "build" — present in almost every
prompt on this platform — silently suppressed the acceptance-criteria
question), a stale `DeliveryPanel` dependency array, and an over-eager
`resetImportResults()` call on unrelated repo-import field edits. All five are
fixed, test-verified (1319 backend tests / 99 Mission Control tests, 0
failures), and committed. A follow-up closing pass then fixed a
`language.ts` "batch" tie-break bug. See "Post-Review Hardening
(2026-07-02)" under Recently Completed for the full list.

Before that: the Mission Control UX lock-in itself — PM clarification,
mission-progress visibility, artifact folder discovery, and follow-up mission
continuation. The implementation is complete and rebuilt into the local Docker
images, but the post-restart browser mission proof is still pending. Evidence:
`docs/evidence/mission_control_ux_lockin_2026-07-02.md`.

- DONE: PM feature-contract normalization now asks clarifying questions for
  underspecified interactive applications/games. Mission Control renders those
  questions as actionable decision cards with recommended defaults, an edit
  path, and a proceed-with-defaults action.
- DONE: Mission Detail now exposes Live Progress with clearer waiting,
  blocked, retrying, stale, working, and finished indicators so long-running
  missions do not look hung without context.
- DONE: Generated Output and Build Artifacts panels now show the real local
  `output/<mission_id>` path, folder/file status, Copy Path, Open Folder, and
  VS Code actions when supported by the local Windows UI process.
- DONE: Continue with PM now loads prior mission summary, build artifacts,
  delivery summary, and output-folder status, then carries that context in the
  follow-up mission metadata.
- DONE: generated-output completion gating now blocks missions that expect a
  generated output artifact from completing with an empty durable artifact set.
- VALIDATED: Mission Control focused Vitest (36/36), `npm run build`,
  `npm run lint`, focused orchestrator pytest (19/19), compose service graph
  resolution, and Docker rebuilds for `mission-control` and `orchestrator`.
- NEXT: after app restart, run a new browser mission for a modern Angular Snake
  game with `start.bat` and verify PM clarification/defaults, live progress,
  output-folder actions, and Continue with PM in the real UI.

**Previous current work: findings remediation from the 2026-06-30 battery (Phases
0-3 committed and offline-verified; Phase 4 live verification incomplete).**
A phased plan (`FIRST_FULL_SYSTEM_RUN_FINDINGS_2026-06-30.md` recommendations +
`docs/archive/2026-07-03/STACK_REMEDIATION_PLAN_2026-07-01.md`) was validated against the actual
code, corrected where the source docs were wrong (see below), then executed:

- **Phase 0 (commit `4445b6b`):** pod-audit misrouting fix landed as-is
  (case-insensitive `_POD_AUDIT_AGENTS_BY_LOWER` lookup).
- **Phase 1 (commit `07883d7`):** Beta (PBLA-03) now fires on every normal
  `BUILD_NEW` mission. **Correction to the original findings doc:**
  `generated_output` is actually set in `_prepare_specialist_plan`
  (`phases_build.py`), not `_prepare_specialist_assignment` as §4/§6.1 stated —
  a different, later function in the same file. The Beta emission was added
  there (not "moved" — the existing `_prepare_fusion` call in
  `phases_runtime.py` stays as the legitimate fallback-path emission for
  missions whose first codegen attempt didn't yield usable output; the shared
  `mission_has_generated_output` guard keeps the two sites mutually exclusive).
- **Phase 2 (commit `a63dfaf`):** new `_check_language_content_signature` in
  `equivalence_verifier.py`. **Correction to the original findings doc:** §6.2's
  claim "no verification gate currently catches
  generated-language-vs-requested-language mismatches" is factually wrong — a
  required check (`_check_language_alignment`) already existed and was wired
  in. The real gap: it compares `generated_output["language"]` (self-reported
  by the same LLM call that wrote the code) against the requested language —
  both values trace back to "what was asked for," so a specialist that
  silently substitutes Python can still label its output correctly and the
  check can never catch it. The new check inspects `generated_code` text
  directly for unambiguous Python tells, scoped to target languages least
  likely to be confused with Python (c, cpp, r, go, rust, shell) — verified
  against the real C and R battery artifacts on disk (`fail`) and real
  Go/Rust/C++ artifacts (`pass`, no false positive). `mission_equivalence_enforcement_enabled`
  still defaults to `False`, so this surfaces as a finding today rather than
  blocking — enabling enforcement is a separate, broader decision.
- **Phase 3 (commit `b70d711`):** `AGENT-08-COMPLIANCE` now fires
  unconditionally at delivery, like Security/VC/Tester (user's explicit choice
  among 3 options). Adds `generate_compliance_assessment` (new LLM-delegation
  function, distinct from Security's threat analysis and from
  `security_compliance.py`'s deterministic PII/license scan), a new
  `MISSION_COMPLIANCE_ASSESSMENT_COMPLETE` event type, and a deterministic
  fallback matching Security's honesty convention.
- All four phases: full `tests/services/` suite passed clean after each
  (1311 passed, 5 skipped, 0 failed at the end; `test_agent_base_unit.py`'s
  collection error is pre-existing and untouched by this work), ruff clean on
  every touched file.
- **Phase 4 (live stack + verification) — stack is up and healthy, live
  mission proof NOT yet done.** Rebuilt every buildable image (orchestrator,
  api-gateway, all 41 dedicated agents, mission-control, dashboard,
  protocol-bus-mcp, workers) via the correct two-file compose form so Phases
  0-3's code is actually running. Brought the stack up; the user separately
  ran `start_app.bat` mid-session, which recreated a subset of containers
  non-destructively (`deploy_postgres-data`/`deploy_redis-data` volumes
  confirmed intact throughout — no data loss this time) and additionally
  brought up `minio`/`neo4j` without hitting the prior port conflicts.
  **Current confirmed live state:** 59/59 `deploy-*` containers healthy or Up
  (0 unhealthy, 0 stuck), orchestrator `/readyz` reports `ready: true` across
  every dependency (Redis, Postgres, Qdrant, Milvus, Neo4j, object storage,
  protocol bus), api-gateway ready. **Stack Remediation Finding 3 (Postgres
  credential mismatch): resolved** — `db_ready: true`, no `FATAL: password
  authentication failed` in logs; matches the plan's prediction that a fresh
  `initdb` against the wiped volume would self-resolve it. **Finding 4
  (`INTERNAL_SERVICE_API_KEY` empty at runtime): very likely resolved** —
  `docker compose config` dry-run confirmed a real, non-empty key resolves at
  all three call sites, and a build-artifacts fetch for an old (pre-wipe)
  mission ID returned a clean `404 resource not found` rather than the old
  `503 gateway internal auth is not configured` — but this was **not
  confirmed against a fresh live mission**, which is the stronger proof.
  **Finding 5 (host port collisions):** confirmed not a code issue (host-port
  overrides already exist in compose); this run happened not to collide, but
  that isn't guaranteed on every run.
  **NOT DONE — the actual remaining step:** submit one live mission through the
  real Mission Control chat UI (not the raw API) and confirm, end-to-end: the
  pod-audit fix (submit a Pod B/C/D language), Beta firing (check
  `protocol:beta:*` bus metrics), `MISSION_DEPLOY_READINESS_ASSESSED` firing
  (findings §6.4 re-confirmation), the new language-content-signature check
  behaving correctly on a real mission, and a definitive build-artifacts fetch
  for that fresh mission (closes Finding 4 conclusively). This step was blocked
  on browser selection (two Chrome extensions connected, needs an explicit
  pick) and the session ended before it was resolved — **this is the next
  action for a fresh session, see Next Actions #1 below.**

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

### Design Reconciliation & Semantic Engine Upgrade (Phases 1, 3, 4, 5, 7 done; Phase 2 partial; Phase 6 blocked)

Audit: `docs/DESIGN_VS_BUILD_AUDIT_2026-08-01.md`. Ordered execution plan:
`docs/UPGRADE_RECONCILIATION_PLAN_2026-08-01.md`. Decisions D1/D2/D3 are
settled — see Current Status above and the plan's §1. Non-goals are listed in
the plan's §11 and must be refused if they resurface; §14 lists what must not
be weakened.

1. **DONE (2026-08-01) — Phase 1** (plan §4) — truth reconciliation,
   documentation only. UPG-10 `docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md`
   (19 verdict rows; **governing document — outranks the numbered design
   corpus**) · UPG-11 binary synthesis formally retired, `AGENT-11-DEPLOY` and
   `AGENT-09-HW` role strings rewritten in `agent_registry.py` · UPG-12
   `docs/IMPLEMENTATION_STATUS.md` rescoped to the v1.3 mission-pipeline surface
   with an explicit "Semantic depth — scoped out" row · UPG-13 tolerance claim
   retired, replacement metrics recorded in ADR row 9 · UPG-14
   `docs/DESIGN_TRACEABILITY.md` (all 64 design docs → status → module →
   evidence) · UPG-15 corpus README at
   `docs/archive/2026-03-29/legacy-workspace/root-legacy-documentation/README.md`
   plus a 2026-08-01 staleness block on
   `docs/archive/2026-06-12/HGR_Gap_Report_1.md`.
   All five exit criteria met — per-criterion evidence is in the plan's §4 exit
   table. **Read the ADR's "Corrections to the audit and plan" section** before
   assuming any UPG-1x item was skipped: three plan premises failed validation
   against live code and were deliberately not executed as written.
   **The likely confusion was honoured:** retiring binary *synthesis* did not
   remove `toolchains.py` *syntax validation*, which stays.
2. **DONE — Phase 2** (plan §5). UPG-21 / UPG-22 / UPG-23 landed 2026-08-01.
   **UPG-20 durable evidence landed 2026-08-12**
   (`docs/evidence/s1_01_live_generation_go_20260811.json`). Phase 6 is no
   longer blocked on S1-01.
3. **Phase 3** (plan §6) — LogicNode schema v2, additive. Single insertion
   point: `services/pod-worker/pod_worker/main.py:_build_schema_node` (~L265),
   through which both `_coerce_schema_node` (~L317) and
   `_logicnodes_from_extraction` (~L394) route. Promote descriptive fields out
   of the free-form `payload` as *optional* top-level properties, and populate
   `types.in`/`types.out` from AST signatures that already exist
   (`JsFunctionInfo.signature`, `JavaMethodInfo.parameters/return_type`, Python
   `ast` annotations). Gets more expensive with every mission that accumulates
   rows in `mission_logicnodes`.
4. **Phase 4** (plan §7) — real Refined-IR projection. UPG-40 (`projection_method`
   field, `"templated_v1"` vs `"ast_v1"`) ships even if the rest slips.
5. **Phase 5** (plan §8) — behavioural equivalence, executed inside RQCA's
   existing hardened Docker sandbox (`rqca_agent.py:649-661` —
   `--network=none --read-only --cap-drop=ALL`, 60s, 512MB). **Do not build a
   second execution path.**
   **OPEN DECISION (raised 2026-08-04, not yet made): Phase 5 cannot verify
   BUILD_NEW missions at all.** Behavioural equivalence projects vectors from
   LogicNodes, and LogicNodes come from *extracting* existing source. A
   BUILD_NEW mission has no source to extract from, so it produces **zero**
   LogicNodes and the gate reports `skipped` /
   `"no Refined-IR module in mission metadata"` — correctly and permanently, on
   every such mission. Phase 5 as designed verifies missions that *transform*
   code, not missions that *create* it. The candidate answer is to project
   vectors from the **generated artifact's own AST** and execute them against
   the contract's acceptance criteria, which turns the gate from
   "old behaviour == new behaviour" into "delivered behaviour == contracted
   behaviour". That is a genuine scope change to D1 and needs an ADR amendment
   before any code. Until it is decided, `skipped` is the honest result and must
   not be papered over by relaxing the gate.
6. **Phase 6** (plan §9) — EDCP. Execute `docs/EDCP_PHASE_PLAN.md` as written,
   with one inserted sub-phase first: **EDCP-02a**, a Delta consumer as the
   pod-audit gate. Delta already has two live producer call sites
   (`phases_build.py:250`, `:816`) and a natural gate in
   `lifecycle.py:_advance_verified_to_complete`, making it the cheapest way to
   make a lane genuinely load-bearing. S1-01/UPG-20 is closed; remaining
   work is a live-bus exercise with `EVENT_DRIVEN_CONTROL_PLANE_ENABLED`.
7. **Phase 7** (plan §10) — consolidation: LogicNode dependency graph in
   Mission Control (needs Phase 3's data; must respect the CSP work deferred
   from remediation Phase 4), LangGraph decision, `docs/MISSION_TAXONOMY.md`,
   formal deferral of the Doc 30 registry.

### Full Whole-App Code Review Remediation (Phases 0-3 done; Phase 4 remaining)

Findings: `docs/FULL_APP_CODE_REVIEW_FINDINGS_2026-07-05.md`. Ordered
execution plan: `docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md` (validated
against external standards/industry practice — OWASP secure-defaults
guidance, the Terraform/Ansible/kubectl dry-run-by-default pattern, the
community-standard embedded-standalone-server approach for Next.js-in-
Electron, and the 2024 Microsoft SmartScreen policy change that favors
Azure Artifact Signing over an EV certificate).

1. **DONE — Phase 0** (`docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md`
   §3) — harden production runtime defaults: `RQCA_ENFORCEMENT_ENABLED`
   compose default (`deploy/docker-compose.yaml:326`, now `:-true`, plus a
   `load_settings()` production fail-fast guard), production MinIO
   credentials (prod overlay now requires real values via compose `:?`
   syntax, plus an app-level guard against the literal
   `minioadmin`/`minioadmin123`), `GATEWAY_ADMIN_BYPASS` warn-only-in-prod
   inconsistency (`api_gateway/main.py:1663-1667`, now raises
   `RuntimeError`), `CORS_ALLOW_ORIGINS` (env-overridable, required
   explicit value in prod), and `agent-runtime`'s `SERVICE_API_KEY` weak
   default (`"worker-key"` fallback removed, fails fast at import). Full
   verification evidence in `docs/HANDOFF_CURRENT.md`'s "Latest Completed
   Work" section.
2. **DONE — Phase 1** (script/tooling safety guardrails — dry-run-by-default
   for destructive scripts). Full per-item list and verification evidence
   in `docs/HANDOFF_CURRENT.md`'s "Latest Completed Work" section. Also
   fixed in passing: the actual root cause of Phase 0's one noted
   "pre-existing, unrelated" test flake.
3. **DONE — Phase 2** (frontend UI correctness/accessibility/data-integrity).
   Full per-item list and verification evidence in
   `docs/HANDOFF_CURRENT.md`'s "Latest Completed Work" section. Two findings
   (Alerts persistence, chat session retention) needed genuine decisions
   rather than mechanical fixes — both resolved with explicit user sign-off.
4. **DONE — Phase 3** (documentation accuracy — findings #15/#28).
   `docs/METRICS_SOURCE_MODULES.md` now documents all four previously-missing
   source modules (`llm_delegation/metrics.py`, `pod-worker/main.py`,
   `audit-worker/main.py`, `agent-runtime/main.py`) in full, and the stale
   lowercase mission-state casing in `orchestrator_metrics.py:57` and the doc
   is now uppercase. Full detail in `docs/HANDOFF_CURRENT.md`'s "Latest
   Completed Work" section. **NEXT: Phase 4.**
5. Phase 4 (Electron/Windows installer buildout) last — the only phase
   with real architecture decisions (build-mode reconciliation via an
   embedded standalone Next.js server, code signing, NSIS install/uninstall
   hooks). Three sub-decisions are explicitly flagged in the plan as
   needing user sign-off before implementation: Docker-lifecycle-on-quit
   behavior (§7.2), the Docker Desktop/WSL2 prerequisite story (§7.4), and
   the auto-start decision (§7.7).
6. Do not fix individual findings out of this order — the plan's
   sequencing rationale (§2 of the plan doc) is deliberate: cheapest/
   highest-exposure fixes first, architecture-decision work last so its
   rebuild inherits every earlier phase's fixes.

### Mission Control UX Lock-In (implemented; live browser proof pending)

Tracked by `docs/evidence/mission_control_ux_lockin_2026-07-02.md`.

- DONE: PM clarification cards and recommended-default flow in Mission Control
  chat.
- DONE: local output-folder status route plus guarded local Open Folder and VS
  Code actions.
- DONE: artifact panels expose the output path/status even when no generated
  artifact is recorded yet.
- DONE: Continue with PM preloads prior mission/output/artifact context for
  follow-up work.
- DONE: Live Progress panel exposes state-specific next actions for waiting,
  blocked, retrying, stale, and finished missions.
- VALIDATED: focused frontend/backend tests, Mission Control build/lint, and
  Docker rebuilds for the changed UI/orchestrator images.
- NEXT: run the post-restart Angular Snake browser mission and confirm the UX
  behaves correctly under a real mission.
- A code review pass since this implementation found and fixed 5 defects in
  this feature area (stuck-mission gating, missing auth on the local-folder
  routes, a suppressed PM clarifying question, and 2 frontend bugs) — see
  "Post-Review Hardening (2026-07-02)" under Recently Completed.

### Repository ZIP Import Migration (active implementation)

Tracked by `docs/REPO_ZIP_IMPORT_MIGRATION_PLAN.md`. This replaces the
GitHub API based repository intake path with local `.zip` repository snapshots
so Mission Control can index source without GitHub credentials or network
access.

- DONE: Phase 1 archive core. Added a safe ZIP archive helper for path
  normalization, common-root stripping, archive SHA-256 hashing, entry limits,
  large-file skipping, selected text reads, and binary detection. Focused
  archive helper tests pass.
- DONE: Phase 2 import route. `POST /api/repo/import` now accepts
  multipart/form-data with an `archive` `.zip` upload plus `display_name`,
  `source_ref`, `subdirectory`, and `max_files`; it indexes the archive locally
  and returns ZIP metadata while enforcing upload-size and truncation signals.
- DONE: Phase 3 review route conversion. `POST /api/repo/review` now accepts
  multipart/form-data ZIP review requests, requires `archive_sha256`, includes
  required selected paths outside the display slice, reads selected file text in
  one ZIP pass, and returns the existing review bundle shape without GitHub API
  calls.
- DONE: Phase 4 UI migration. The `/repo` page now renders a local ZIP file
  selector, source-ref metadata, archive hash/root-prefix summaries, FormData
  import/review calls, and review-gate reset behavior when archive scope changes.
- VALIDATED: Mission Control `npm run lint`, full `npm run test` (87/87), focused
  `npm run test -- app/api/repo` (22/22), and targeted Playwright repo intake
  e2e passed.
- NEXT: Phases 5-7. Add mission launch index guard, repo knowledge ingestion,
  and PM/pod-worker repository context loading so indexed repo content becomes
  available from the internal database.

### Verification & Reporting Hardening (Phase 1-3 complete; verification backlog remains)

Tracked in full by `docs/archive/2026-07-03/UPDATE_PLAN_VERIFICATION_HARDENING_2026-06-29.md`. Surfaced
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

- **Stage 1 — PBLA** (`docs/archive/2026-07-03/PROTOCOL_BUS_LANE_ACTIVATION_PLAN.md`): real producers on
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

**Two real issues surfaced by the live run — both fixed and committed since
(see Current Status above):**
- **Beta never fired across all 20 missions.** Fixed in commit `07883d7`: the
  emission was added to `_prepare_specialist_plan` (the function that actually
  sets `generated_output`, not `_prepare_specialist_assignment` as originally
  documented). Live re-confirmation still pending — see Current Status.
- **Pod-audit agent misrouting.** Fixed in commit `4445b6b`.

**Also surfaced (not PBLA-specific, but same run):** 2 of 20 missions (C, R)
generated the wrong language entirely (Python simulating the target language)
and still reached `COMPLETE`. **Addressed in commit `a63dfaf`** — see Current
Status for why the originally-suspected "no gate exists" diagnosis was wrong
and what the new check actually does. Live re-confirmation still pending.

**Environment note:** the battery's database state was subsequently wiped by
`stop_app.bat` (`docker compose down -v`). The stack has since been rebuilt and
brought back up (see Current Status) — Postgres and `INTERNAL_SERVICE_API_KEY`
issues from `docs/archive/2026-07-03/STACK_REMEDIATION_PLAN_2026-07-01.md` both look resolved,
pending final live-mission confirmation.

- **PBLA-05** (optional): lane observability surfacing in the operations snapshot.

Once the Beta fix lands and the stack remediation is done, Stage 2 (EDCP)
becomes unblocked — its consumers filter PBLA's `pbla_*` discriminators off the
shared broadcast channels.

Tracked in full by `docs/archive/2026-07-03/PROTOCOL_BUS_LANE_ACTIVATION_PLAN.md`. Standalone and
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

### Full Whole-App Code Review (2026-07-05): read-only, five slices, ~30 findings, remediation plan pending

A full, read-only code review of the entire application (not just the
Windows/Electron packaging layer originally scoped), via four parallel
background review agents (frontend UI, Electron/Windows, deploy/infra/CI,
scripts — each explicitly read-only) plus a direct 3-file self-review of
`services/agent-runtime/`. Full report:
`docs/FULL_APP_CODE_REVIEW_FINDINGS_2026-07-05.md`. Explicit instruction:
findings-only, nothing fixed in this pass.

- Established that the app currently runs as a web app (`start_app.bat` →
  Docker Compose + a plain Next.js server opened in the default browser),
  not as a packaged Electron app — the Electron build is a separate,
  parallel path.
- Slice A (frontend UI): 13 findings — Alerts "Acknowledge"/"Mark Resolved"
  don't persist (local state only); stale-response races in mission/detail/
  artifact data fetching; a literal `✕` renders as raw escaped text; two
  non-semantic clickable `<div>`s with no keyboard access; guided-tour
  dialog never calls `.focus()`. No XSS vector found.
- Slice B (Electron/Windows packaging): the packaged app's 14 `app/api/*`
  routes cannot function at all — static export (required for Electron)
  physically hides `app/api` at build time because Next.js static export is
  incompatible with dynamic App Router routes; confirmed via
  `scripts/build-electron.mjs` explicitly renaming the directory away and
  back. Also: cosmetic-only Docker check, zero Docker-lifecycle code in the
  Electron main process, unsigned release artifacts, no NSIS
  install/uninstall hooks, `deleteAppDataOnUninstall` doesn't touch the real
  vault file. Full 7-point gap list for a real installer in §8 of the
  findings doc.
- Slice C (`services/agent-runtime/`): clean; one weak-default-secret
  finding (`SERVICE_API_KEY` defaults to `"worker-key"`).
- Slice D (deploy/infra/CI): `RQCA_ENFORCEMENT_ENABLED` compose default
  silently reverts the hardened code default back to `false` in every
  profile including production; production MinIO credentials fall back to
  `minioadmin`/`minioadmin123`; `GATEWAY_ADMIN_BYPASS=true` only warns in
  prod instead of failing fast; `METRICS_SOURCE_MODULES.md` omits 4 real
  in-use metrics. Dockerfile hygiene and CI security scanning both clean.
- Slice E (`scripts/`, 58 scripts, + `Makefile`): duplicate `demo:` target
  silently shadows the intended one; real DR drill and two qualification
  scripts default to destructive live mutation with no confirmation; the
  git-history-scrub script unconditionally rewrites history with no
  dry-run/backup; the operations runbook's own recovery steps violate its
  own compose-pairing warning. No SQL injection or shell command injection
  found anywhere in the ~25 scripts with no material findings.
- `scripts/validate_documentation.py` passes with the new findings doc
  included.
- **Not done in this pass (deliberately deferred):** no fixes. The
  remediation plan derived from these findings was written separately —
  see "Full Whole-App Remediation Plan" below.

### Full Whole-App Remediation Plan (2026-07-05): 4-phase ordered plan, validated against external standards, execution not started

Ordered execution plan derived from the findings above:
`docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md`. Each phase cites the
specific findings it closes and, where a genuine design decision was
needed rather than an obvious bug fix, the external standard/industry
practice consulted.

- **Phase 0 — harden production runtime defaults** (closes findings
  #1/#2/#18/#23/#26): `RQCA_ENFORCEMENT_ENABLED` compose default, MinIO
  default credentials, `GATEWAY_ADMIN_BYPASS` warn-vs-fail-fast
  inconsistency, hardcoded `CORS_ALLOW_ORIGINS`, agent-runtime weak
  default secret. Grounded in OWASP Top 10:2025 A02 (Security
  Misconfiguration) and this codebase's own existing fail-fast precedent
  (the adjacent CORS-wildcard check in `api_gateway/main.py`).
- **Phase 1 — script/tooling safety guardrails** (closes findings
  #6/#7/#8/#9/#10/#19/#20/#24/#25/#27/#29): inverts every destructive
  script's default to dry-run-first, following the same shape as
  Terraform plan/apply, Ansible `--check`, and `kubectl --dry-run`; the
  git-history-scrub fix specifically aligns with `git-filter-repo`'s own
  fresh-clone safety model.
- **Phase 2 — frontend UI correctness/accessibility** (closes findings
  #3/#11/#12/#13/#14/#21/#22, plus the CSP `unsafe-inline` and
  `global-search.tsx` dead-code items): straightforward fixes, no
  architecture decisions; flags the CSP nonce trade-off as best deferred
  until Phase 4 lands (dynamic rendering will be required anyway).
- **Phase 3 — documentation accuracy** (closes findings #15/#28): the
  `METRICS_SOURCE_MODULES.md` omissions and the stale mission-state-casing
  mismatch.
- **Phase 4 — Electron/Windows installer buildout** (closes findings
  #4/#5/#16/#17 plus the §8 gap list): the only phase with real
  architecture decisions. Core decision — replace static export with the
  same `output: 'standalone'` Next.js server the Docker/web-app path
  already runs, launched as a child process from the Electron main
  process, following the community-standard pattern for exactly this
  Next.js/Electron problem; this resolves the build-mode split and the
  broken-API-routes finding in one change. Code signing recommendation:
  Azure Artifact Signing over an EV certificate, since a 2024 Microsoft
  SmartScreen policy change means EV no longer bypasses the warning any
  better than OV. Three sub-decisions flagged for explicit user sign-off
  rather than an assumed default: Docker-lifecycle-on-quit behavior,
  Docker Desktop/WSL2 prerequisite handling, and an auto-start decision.
- Sequencing rationale (plan §2): cheapest/highest-exposure fixes first
  (Phase 0), architecture-decision work last (Phase 4) so its rebuild
  inherits every earlier phase's fixes instead of needing a second pass.
- **Not done in this pass:** no implementation — this is a sequencing and
  justification document only. See "Full Whole-App Code Review
  Remediation" under Active Work Queue for the tracked next step (execute
  Phase 0).

### Documentation Audit and Reduction (2026-07-03): fictional docs deleted, license/classification errors fixed, one real code bug found

Full inventory-and-accuracy audit of theFactory's documentation, done in
two passes (initial inventory/classification/reduction, then a targeted
verification pass over docs not deeply checked in the first pass).

- Inventoried 105 active docs (89 under `docs/`, 16 root/app/GitHub-template
  files) plus 212 already-segregated historical files under
  `docs/archive/`/`docs/evidence/`.
- Deleted 3 docs describing entirely fictional systems: `EQUIVALENCE_
  VERIFIER.md`, `IS_AGENT.md`, `PORT_COORDINATOR_AND_LOGICNODE_SCHEMA.md`
  (plus `diagrams/ENTERPRISE_ARCHITECTURE_DIAGRAMS.md`, redundant with
  `ARCHITECTURE_DIAGRAMS.md`). The real `equivalence_verifier.py`/
  `is_agent.py`/`port_coordinator.py` modules are now documented accurately
  in `SUPPORTING_MODULES.md`.
- Archived 8 completed point-in-time plans/incidents to
  `docs/archive/2026-07-03/`: `AUDIT_PLAN.md`, the 2026-06-30 findings/
  session-log pair, `PROTOCOL_BUS_LANE_ACTIVATION_PLAN.md`,
  `PROTOCOL_BUS_MISSION_BATTERY_PLAN.md`, `UPDATE_PLAN_VERIFICATION_
  HARDENING_2026-06-29.md`, `STACK_REMEDIATION_PLAN_2026-07-01.md`,
  `AGENT_PROTOCOL_BUS_DATA_SYSTEMS_PLAN.md`.
- Pruned `HANDOFF_CURRENT.md` (1504 lines) and this file (1120 lines) down
  to current status plus the most recent review sweep; older entries moved
  to `docs/archive/2026-07-03/{HANDOFF_CURRENT,CURRENT_TODO}_OLDER_HISTORY.md`.
- Fixed two critical inaccuracies: `LICENSE_STRATEGY.md` claimed MIT with
  quoted MIT text (repo is Dual AGPL-3.0/Commercial with a mandatory CLA;
  fixed the README license badge too); `DATA_CLASSIFICATION_POLICY.md`
  described a fictional 4-tier taxonomy not matching the real
  `DataClassification` enum.
- Rewrote 7 docs that described entire class-based APIs/config keys that
  don't exist, while omitting the real (differently-designed) modules:
  `AGENT_SCALING_AND_HEARTBEAT.md`, `LLM_DELEGATION.md`, `PROMPT_REGISTRY_
  AND_ASSETS.md`, `LLM_SAFETY_AND_DOCUMENT_PARSER.md`, `METRICS_SOURCE_
  MODULES.md`, `OBSERVABILITY_STACK.md` (fictional metric/alert names that
  would return zero results against real Prometheus/Grafana),
  `DEPENDENCY_ABSORPTION_DOCTRINE.md` (added a status section separating
  real code from aspirational governance policy).
- Fixed several minor inaccuracies: `SENSITIVE_CODE_HANDLING_POLICY.md`,
  `COMPLIANCE_EVIDENCE_MAPPING.md`, `LOCAL_FIRST_COMPLIANCE_PLAN.md` (3
  already-shipped items still marked "Outstanding"), `SETTINGS_
  REFERENCE.md` (3 undocumented fields), `KNOWLEDGE_LAKE_AND_EMBEDDINGS.md`,
  `DEPLOYMENT_DR_PLAYBOOK.md` (check-count inconsistency, real count is
  23), `dr_validation_runbook.md` (RTO/MTTR conflation, missing
  compose-file pairing flags matching the documented `docker compose
  down -v` gotcha, stale drill schedule), `dedicated_agent_canary_
  runbook.md` (outdated compose profile invocation).
- **Found and fixed a real code bug incidentally**: the api-gateway tagged
  sensitive-input missions with the invented string `"TIER_2_RESTRICTED"`,
  never matching the orchestrator's real `DataClassification` enum value
  (`"TIER_2_SENSITIVE"`) — `security_compliance.py`'s classification checks
  silently never recognized these missions as anything but unclassified.
  Fixed with a regression test proven to fail pre-fix via `git stash`.
- `scripts/validate_documentation.py` passing throughout. Full backend
  suite after the code-bug fix: 1348 passed, 5 skipped. `ruff check`
  clean. `api-gateway` Docker image rebuilt and the fix verified inside
  the container.

### Mission Control API Routes Review (2026-07-03): vault and gateway proxy had zero authentication

Security review of the Mission Control frontend's Next.js API routes
(`apps/mission-control/app/api/`, ~6.1k lines including `lib/server/`), via
two parallel finder passes (one relaunched after an initial premature
result), each candidate verified against actual code before fixing. Final
"everything else" slice of the systematic review effort spanning both
sessions.

- Fixed vault CRUD routes (`vault/route.ts`, `vault/test/route.ts`) having
  zero authentication — `isAuthorizedVaultRequest` existed, was tested, and
  was clearly intended to gate these routes, but was dead code never wired
  into any handler. Any unauthenticated caller could list/overwrite/delete
  every vault secret including `OPERATOR-API-KEY`. Fixed by wiring it into
  all four handlers.
- Fixed the `/api/gateway/[...path]` catch-all proxy — the path used for
  nearly all backend traffic including mission creation — having no
  operator-session gate at all, unlike every sibling privileged route.
  Fixed with the same `requireOperatorRequestSession` gate used elsewhere.
- Investigated and judged consistent with established design, not fixed as
  anomalies: `operator/mission-state`/`pm/feature-contract`/`review/approve`/
  `review/verify` all resolve to a single shared privileged backend
  credential rather than a per-caller one — matches this app's
  single-operator-role session model consistently, not an isolated
  deviation; the dev-bypass env flags are explicit opt-in with no
  default-on path (same accepted pattern as the backend's
  `GATEWAY_ADMIN_BYPASS`); `builder/review`'s file-content embedding is
  root-constrained and session-gated (a preexisting-secret-in-repo hygiene
  concern, not a route bug); ZIP archive handling was re-verified as still
  correctly hardened against zip-slip/decompression bombs; `open-vscode`'s
  `cmd.exe` string construction is a code smell but not currently
  exploitable given upstream regex validation.
- Confirmed after fixing: every `route.ts` in the API surface now has an
  auth check except `session/unlock`/`session/logout`, which is correct by
  design.
- Every fix has a regression test independently proven to fail against the
  pre-fix code via `git stash`. Frontend suite: 104 passed (20 test files).
  `tsc --noEmit` clean.

### shared_runtime Review (2026-07-03): artifact re-verification gap and diagnostic-bundle secret leak

Security/correctness review of `shared_runtime/` (~1.7k lines across 11
files: `agent_auth.py`, `agent_keys.py`, `crypto_keystore.py`,
`crypto_signing.py`, `prompt_guard.py`, `pii_guard.py`, `atomic_io.py`,
`protocol.py`, `errors.py`, `logging_config.py`, `__init__.py`), via two
parallel finder passes, each candidate verified against actual code and
callers before fixing:

- Fixed `get_build_artifact` (`orchestrator/routes/internal.py`) only
  re-verifying `verified` when a `signature_record` was present — unsigned
  artifacts (signing can fail via a swallowed broad `except`) reported a
  write-time-only `verified: true` never re-checked against currently
  stored bytes. Now falls back to re-hashing and comparing against the
  recorded digest via `hmac.compare_digest` when unsigned.
- Fixed the maintenance diagnostic-bundle env-var sanitizer
  (`system_maintenance.py`) only excluding names containing
  `_KEY`/`_SECRET`/`_PASSWORD` — missed `VAULT_TOKEN`/`VAULT_ROLE_ID`
  (no matching substring) and connection-string vars (`POSTGRES_URL`,
  `REDIS_URL`) that embed a plaintext password in the URL regardless of var
  name. Expanded the name denylist and added value-level userinfo
  redaction for any URL-shaped value.
- Investigated and refuted / deferred as accepted tradeoffs: RIR-module
  signature verification failures are explicitly documented as "best
  effort" and non-fatal (logged, never block the mission) — looks
  intentional, flagged for revisiting now that signing is load-bearing for
  compliance reports too, not changed in this pass. A TOCTOU race in
  `load_or_create_signing_key` on first-time key creation is real but
  low-blast-radius (each artifact's public key travels with its own
  signature record, so per-artifact verification is unaffected). The
  plaintext signing-key fallback default matches documented dev/staging
  convenience intent. A stale `pii_guard.py` docstring referencing a
  nonexistent `scan_envelope()` function was fixed. `atomic_io.py`'s
  reliance on `tempfile.mkstemp`'s default 0600 mode was reviewed and
  confirmed not loosened by umask on POSIX (umask only removes bits, never
  adds them) — no fix needed.
- Every fix has a regression test independently proven to fail against the
  pre-fix code via `git stash`. Full backend suite: 1348 passed, 5 skipped.
  `ruff check` clean. Rebuilt `deploy-orchestrator`, `deploy-api-gateway`,
  and `deploy-pod-a-worker` (all three import `shared_runtime`) and
  verified the fixes directly inside the rebuilt containers.

### Verification & Compliance Gates Review (2026-07-03): permissive-by-default gates, plus 2 confirmed idempotency bugs

Correctness/security review of `equivalence_verifier.py`,
`port_coordinator.py`, `security_compliance.py`, `rqca_agent.py`
(~2.1k lines total), via two parallel finder passes (one re-run after an
initial premature/empty result), each candidate verified against actual
code and callers before fixing:

- Confirmed (two independent passes): `MISSION_SECURITY_COMPLIANCE_ENFORCEMENT_ENABLED`
  and `RQCA_ENFORCEMENT_ENABLED` both defaulted to `false` — a mission with
  a detected hardcoded secret or a failing runtime QC verdict proceeded to
  delivery by default (`status: "warned"`, never `"blocked"`). User-
  confirmed decision: both now default to `true`; env-var opt-out remains
  available.
- Fixed a PORT extraction-phase re-entrancy gap in `_prepare_specialist_plan`
  (`mission_flow_v2/phases_build.py`) — the only sibling branch without a
  `_chain_event_exists` guard, risking duplicate LLM-derived extraction
  results and a duplicate `MISSION_PORT_EXTRACTION_COMPLETE` event on
  re-entry.
- Fixed a security-compliance report idempotency gap in
  `_prepare_security_compliance_report` (`mission_flow_v2/phases_delivery.py`)
  — no cache check (unlike its RQCA sibling), so the report was rebuilt and
  re-signed on every completion-gate retry, overwriting the prior
  `signature_record`, with an un-deduplicated audit event firing each retry.
  Now cached and reused like `_prepare_runtime_qc`.
- Investigated and refuted / deferred as architectural: advisory-only
  (`required=False`) acceptance-criteria/concept-coverage keyword heuristics
  in `equivalence_verifier.py` (disclosed, cannot flip the load-bearing
  verdict); the Python-fallback language-content-signature detector's
  8-of-19-language coverage (disclosed in its own docstring, left for a
  scoped follow-up); `port_coordinator.py`'s `extraction_degraded` flag
  being computed but never consumed by a downstream gate (a real wiring
  gap, but fixing it requires a design decision on whether degraded
  extraction should become a required check); RQCA's Docker-unavailable
  `DRY_RUN`→`ADVISORY` fallback never blocking (an inherent "couldn't
  execute" limitation, not part of the enforcement-default decision above);
  regex-based secret/dangerous-pattern scanners being trivially evadable by
  generated code (accepted heuristic-scanner limitation, same category as
  the weak-regex finding accepted in the api-gateway review); silently
  swallowed report-signing failures leaving an unsigned report with no
  marker (minor, not patched).
- Every fix has a regression test independently proven to fail against the
  pre-fix code via `git stash`. Full backend suite: 1346 passed, 5 skipped.
  `ruff check` clean. Rebuilt `deploy-orchestrator` and verified the new
  enforcement defaults directly inside the rebuilt container.

### pod-worker Review (2026-07-03): poison-message data loss, plus 4 smaller confirmed bugs

Correctness review of `services/pod-worker/pod_worker/` (~5.1k lines:
`main.py`, `language_extractor.py`, `ast_extractor.py`, `js_ast_extractor.py`,
`java_ast_extractor.py`, `concept_catalog.py`, `refined_ir.py`,
`tracing.py`), via three parallel finder agents reading full files, each
candidate verified against actual code before fixing:

- Fixed `_consumer_loop`'s catch-all exception handler permanently
  orphaning failed stream entries (no DLQ write, no acknowledge, and no
  `XCLAIM`/`XAUTOCLAIM` anywhere in this service to ever reclaim them) — now
  routes to the DLQ and acknowledges, matching the existing pattern for the
  four explicitly-handled exception types.
- Fixed a companion bug in `_write_dlq`: a failed DLQ write was only logged
  while the caller still unconditionally acknowledged the original entry,
  silently losing it forever on a transient Redis blip. `_write_dlq` now
  returns success/failure; callers only acknowledge on success.
- Fixed `refined_ir.py`'s `build_refined_ir_module` producing the literal
  string `"None"` as a function name when a LogicNode payload omitted
  `node_name`, instead of falling back to the concept name.
- Fixed `JavaScriptExtractor`'s function-detection regex silently dropping
  every paren-less single-arg arrow function (`x => x + 1`) from extraction.
- Fixed `PythonAstExtractor` receiving the untruncated source for AST
  parsing while the regex pass truncated to 512 KB — bypassed the size
  guard and produced inconsistent line numbers for large files.
- Fixed `JavaAstExtractor` injecting an empty-string entry into the imports
  list when `javalang`'s `path` attribute is empty/None on a malformed
  parse.
- Investigated and refuted: broad exception handling in the JS/Java AST
  extractors is correctly defensive (returns `success=False`, callers
  fall back to regex — no crash, no silent-wrong-success); `__init__.py`
  being empty is a non-issue (submodule import, not package import);
  `refined_ir.py`'s `effects`/`purity` naming is confusing but not
  functionally wrong; duplicate `concept_id`s across languages are
  currently harmless (per-language dedup scope) but noted as a latent
  cross-language trap; JS dynamic `import()`/`export ... from` and
  arrow-as-callback coverage gaps are real but scoped enhancements behind
  a disabled-by-default flag (`JS_AST_EXTRACTOR_ENABLED=false`), not
  correctness bugs.
- Deferred: `_run_agent_pipeline` runs `agent.execute()`/`.validate()`/
  `.report()` synchronously inside the async event loop with no
  `asyncio.to_thread`/executor offload, blocking the consumer and heartbeat
  loops during CPU-bound or blocking agent work. This needs a scoped review
  of `agent_base.py`'s execution/thread-safety model before changing — a
  reflexive `asyncio.to_thread` wrap risks introducing new bugs if agent
  internals assume single-threaded execution. Left as a flagged
  architectural item, not patched in this pass.
- Every fix has a regression test independently proven to fail against the
  pre-fix code via `git stash`. Full backend suite: 1342 passed, 5 skipped.
  `ruff check` clean. Rebuilt `deploy-pod-a-worker` and `deploy-orchestrator`
  images (the orchestrator image bundles `pod_worker.language_extractor` for
  AIM generation) and verified every fix directly inside the rebuilt
  containers.

### api-gateway Review (2026-07-03): 10 unauthenticated routes, plus 5 smaller confirmed bugs

Security/correctness review of `services/api-gateway/api_gateway/main.py`
(~2.8k lines), via four parallel finder agents reading the full file plus a
fifth targeted triage pass, each candidate verified against actual code and
orchestrator-side handlers before fixing:

- Fixed 10 routes with zero caller authentication: `create_mission`,
  `get_mission_pod_assignment`, `get_mission_chain_trace`,
  `create_pm_feature_contract`, `get_mission_logicnodes`,
  `get_mission_knowledge`, `get_mission_knowledge_graph`,
  `get_mission_audit_reports`, `get_mission_audit_artifacts`,
  `get_mission_audit_events`, `get_mission_build_artifacts`,
  `get_mission_build_artifact`, `download_mission_artifact`,
  `create_builder_preview` — all now require `_require_reader_access`.
  `update_mission_state` was checked and confirmed already correct (uses the
  deliberate `_resolve_mutation_forward_headers` pass-through pattern, with
  the orchestrator's own `MUTATION_AUTH_DEP` as the actual enforcement
  authority).
- Fixed a hybrid-mode `_require_operator_access` bypass (any non-empty
  `X-API-Key` granted access with zero validation).
- Fixed an X-Forwarded-For rate-limit bypass in `_client_identifier` (new
  `GATEWAY_TRUST_PROXY_HEADERS` env flag, default `false`).
- Changed `PROMPT_GUARD_MODE` default from `"log"` to `"block"` (explicit
  user product decision) so OWASP LLM01 prompt-injection attempts are
  rejected by default instead of merely logged.
- Fixed an Anthropic `max_tokens`/`thinking_budget` mismatch in
  `_anthropic_builder_preview` (max_tokens now scales with the
  caller-configurable thinking budget instead of a hardcoded 1200, which
  rejected every high-budget thinking-enabled request).
- Fixed a Gemini-3 model-detection gap in `_is_gemini_3_model` (hardcoded
  `3.1-`/`3.5-` prefixes missed `gemini-3.0-pro` and bare `gemini-3`;
  replaced with a generalized regex, verified no new false positives).
- Fixed an OpenAI refusal-content extraction gap in `_extract_openai_text`
  (`refusal`-type content blocks carry text under `refusal`, not `text`).
- Investigated and refuted: silent pod-manager fallback (pure in-process
  dict lookup, no network reachability failure to mask), chain_trace
  forgery (plain read-only proxy, no forgery vector), PII-scan field
  exclusions (attachments carry no inline content through this endpoint),
  `_dependency_status` exception swallowing (exceptions correctly degrade
  health flags — this is the right behavior for `/readyz`), unvalidated
  provider string (falls through safely to the offline fallback),
  markdown-lstrip/mixed-provenance labeling (no such lstrip exists; source
  labeling is consistent on every path). Weak base64/secret regex patterns
  in the PII/prompt-injection scanners were confirmed as a real but accepted
  limitation (heuristic defense-in-depth logging, not a hard control).
- Every fix has a regression test independently proven to fail against the
  pre-fix code via `git stash`. Full backend suite: 1337 passed, 5 skipped.
  `ruff check` clean. `deploy-api-gateway:latest` rebuilt and every fix
  verified directly inside the rebuilt container.
- Deferred/no further action: weak PII/secret regex patterns (documented
  limitation, not a hard control — would need a real entropy/pattern-based
  secret scanner to meaningfully improve, out of scope for this pass).

### Agent Orchestration Core Review (2026-07-02): AIM extraction was silently non-functional in production

Correctness review of `agent_base.py`, `agent_registry.py`,
`agent_personas.py`, `agent_integrations.py`, `agent_scaling.py`,
`is_agent.py`, `dependency_absorption.py`, `aim_generator.py` (~5.3k lines),
via parallel finder agents reading full files, each candidate verified
against actual callers before fixing:

- Fixed the most significant finding of the review effort so far: AIM
  (Application Intelligence Map) source extraction was silently
  non-functional in the deployed orchestrator container. `_extract_file`'s
  `pod_worker` import path used `Path(__file__).resolve().parents[2]`,
  correct in local dev but resolving to the filesystem root inside the
  built container (the Dockerfile only copies `services/orchestrator`'s
  contents to `/app`, no `services/` ancestor exists there) — apparently
  never verified against a real container. Even when reachable, the code
  filtered `result.concepts` for `domain == "import"`, a value the real
  pattern catalog never produces; `ExtractionResult` has its own correctly-
  populated `imports` field that was never used. Both silently fell through
  a broad exception handler to an empty/zero fallback with only a warning
  log. Fixed both: multi-candidate path resolution (checks which location
  actually exists), reads `result.imports` directly, and the Dockerfile now
  copies `services/pod-worker/pod_worker` to `/app/pod_worker` (no new pip
  deps needed). Verified working by running Python directly inside a
  rebuilt container image, not just locally.
- Also fixed the import-count cap: `detected_imports` was capped at
  `sorted(...)[:50]`, alphabetically dropping real dependencies (e.g.
  "requests", "sqlalchemy") for any codebase with 50+ distinct imports.
  Raised to 1,000 and folded into the existing `truncated` signal.
- Fixed a scaling-decision idempotency gap: `_prepare_specialist_plan`
  (`mission_flow_v2/phases_build.py`) recomputed a fresh `ScalingDecision`
  with new random partition IDs on every re-entry (it's explicitly
  re-entrant by design — the PORT two-phase flow re-enters it), orphaning
  already-emitted/completed partition work tracked under the old IDs. Fixed
  with a guard: skip recomputation if a decision already exists.
- Fixed a Java-detection false negative in `is_agent.py`: the detection
  regex was already reasonably Java-specific, but an additional gate
  required the literal word "java" to also appear in the prompt/source,
  silently skipping Java bootstrap-doc indexing for legitimate Java code
  that never mentions "java" by name.
- VALIDATED: full backend suite — 1332 passed, 5 skipped, 0 failed (1328
  baseline + 4 new regression tests). `ruff check` clean. `orchestrator`
  Docker image rebuilt and the AIM fix specifically verified inside the
  rebuilt container.

**Deferred, not fixed this pass:** `make_specialist_for_language`'s
case-sensitive language lookup and `make_agent`'s silent fallback to a
generic `SpecialistAgent` on a registry/factory-map mismatch
(`agent_base.py`) — real risks in principle, but the former has zero
callers anywhere in the codebase today; `dependency_absorption.py`'s
version-conflict-resolution ordering (first source wins, no conflict
surfaced) and stdlib-import miscategorization; `agent_scaling.py`'s silent
clamping of a misconfigured `max_instances` to 1 with no warning.

### Storage Layer Review (2026-07-02): audit-chain fork race fixed

Correctness review of `storage_missions.py`, `storage_artifacts.py`,
`storage_agents.py`, `storage_pods.py`, `storage_logicnodes.py`,
`storage_core.py`, `storage.py`, `models.py` (~3.1k lines), via parallel
finder agents reading full files, each candidate verified against actual
callers before deciding to fix or refute:

- Fixed a real concurrency bug: `insert_agent_action_event`
  (`storage_agents.py`) read the latest hash-chain digest for a `project_id`
  then inserted the next event as two unsynchronized statements (pool
  connections are `autocommit=True`, no transaction/lock around the pair).
  Two concurrent events for the same project could both read the same
  `prev_digest` and both chain onto it, forking the tamper-evident audit
  chain with no error (no unique constraint catches it). Fixed with a
  transaction plus `pg_advisory_xact_lock(hashtextextended(project_id, 0))`
  serializing concurrent writers per project.
- Investigated and refuted as live bugs (traced actual callers, not just
  code in isolation): `get_build_artifact` returning `artifact_text=None`
  for offloaded artifacts (intended — its one real caller,
  `routes/internal.py`, already redirects to a presigned URL);
  `row_to_mission`'s `len(row) >= 7` inference (every real query selects
  exactly 7 columns, the fallback branch is dead); `models.py`'s
  `risk_assessment`/`MissionAttachment.purpose` (zero readers anywhere);
  self-loop `MISSION_COMPLETION_BLOCKED` event accumulation (intentional —
  the code's own comment frames it as a checkpoint event, metrics already
  dedupe it).
- VALIDATED: full backend suite — 1328 passed, 5 skipped, 0 failed (1327
  baseline + 1 new regression test). `ruff check` clean. `orchestrator`
  Docker image rebuilt and verified to contain the fix.

**Deferred, not fixed this pass:** `storage_pods.py` pod-name
case-sensitivity (real risk in principle, one current caller, always
consistently cased); unconditional S3 re-upload on every
`upsert_build_artifact` retry (its main trigger was already closed by the
prior session's `_ensure_verified_build_artifact` lifecycle fix); no
digest verification of caller-supplied `digest_sha256` against actual
`artifact_text`; `models.py`'s `VALID_TRANSITIONS` table is pure
documentation, never enforced by `transition_mission_state` — a real design
gap, but wiring it in is a bigger behavioral change than this pass's scope.

### Mission Flow v2 + LLM Delegation Review (2026-07-02): 7 backend bugs fixed

Deep correctness review of `mission_flow_v2/` and `llm_delegation/`, reading
full files (not diffs) via parallel finder agents, each candidate verified
against the actual code before fixing:

- Fixed a critical recovery re-invocation bug: `advance_mission_lifecycle_v2`
  (`lifecycle.py`) iterated its full transition table from `queued` on every
  call regardless of the mission's actual state. Since the lifecycle-recovery
  loop restarts a driver task for every in-flight mission on every
  orchestrator restart, this silently re-ran `_prepare_pm_intake` and
  overwrote `feature_contract`/`mission_charter` with a fresh, non-
  deterministic LLM call each time. Fixed by reading the mission's actual
  current state once and skipping to the matching transition before running
  any preparer.
- Fixed duplicate partition-emission on retry: `_emit_partition_work_items`
  (`phases_intake.py`) only marked emission complete after every partition
  succeeded, so a mid-batch failure meant a retry re-emitted already-
  succeeded partitions with fresh random event IDs. Now tracks per-partition
  emitted IDs and persists progress on failure.
- Fixed runtime QC re-executing on every completion-gate retry:
  `_prepare_runtime_qc` (`phases_runtime.py`) had no cache-check guard, unlike
  the testdata-manifest step in the same function, so real sandboxed QC
  execution and a second LLM assessment re-ran from scratch on every retry.
  Now short-circuits on a cached, non-skipped report.
- Fixed a greedy JSON-extraction regex (`llm_delegation/text.py`,
  `_extract_decision_payload`) that spanned from the first `{` to the last
  `}` in the whole LLM response, discarding valid agent decisions whenever
  the response had reasoning-with-example-braces or two JSON blocks. Replaced
  with a balanced-brace scanner.
- Fixed `_normalize_pm_feature_contract`'s `intake_status` coercion
  (`normalizers.py`), which defaulted any unrecognized LLM value to `"ready"`
  (fail-open) instead of `"needs_clarification"` (fail-closed).
- Fixed a Windows drive-relative path-traversal edge case in
  `_write_artifact_to_disk` (`phases_build.py`) — a path like `C:evil.txt` is
  neither absolute nor `".."`-prefixed, so the fragment-based guard could
  miss it depending on drive-letter coincidence. Now validates the resolved,
  joined path against the mission directory.
- Defensive hardening: `_build_prompt` (`prompts.py`) now tolerates a
  non-numeric `risk_score` instead of an uncaught crash.
- VALIDATED: full backend suite — 1327 passed, 5 skipped, 0 failed (1319
  baseline + 8 new regression tests). `ruff check` clean. Every fix's test
  confirmed to fail against the pre-fix code via `git stash` before being
  accepted. `orchestrator` Docker image rebuilt from this code.

**Deferred, not fixed this pass** (lower confidence/impact):
- `generators_artifacts.py`: unguarded `int()` cast on LLM-supplied totals
  (`generate_master_logic_stream`); `primary_artifact` selection missing an
  `isinstance` guard on build-artifact list entries.
- `providers.py`: an unrecognized/malformed provider string silently routes
  to the OpenAI backend instead of failing explicitly; the fallback-provider
  path doesn't re-check safety-block state before resending a
  already-known-unsafe prompt.
- `normalizers.py`/`fallbacks.py`: several telemetry-only accuracy issues —
  `eliminated_duplicates` has no upper bound relative to node count, non-dict
  entries in `logicnodes` inflate duplicate counts, no size cap on
  `generated_code`, `_fallback_vc_commit_strategy` skips the `_clean_text`
  sanitization every other fallback builder applies.
- `text.py`/`health.py`: `_normalize_agent_choice` doesn't validate its own
  fallback is in `allowed_ids`; p95 latency computed via floor instead of
  ceiling, understating it for small sample sizes; `coverage_thin` verdict
  message can't distinguish an extraction failure from a dedup-only issue.

### Older History (archived 2026-07-03)

Entries older than the 2026-07-02/07-03 review sweep above (Post-Review
Hardening, Security Alert Remediation, Phase 8-13 backend items) were moved
to `docs/archive/2026-07-03/CURRENT_TODO_OLDER_HISTORY.md` to keep this file
focused on the active queue plus recent history.

---

## Current Known Gaps

| Area | Status |
|---|---|
| Design/implementation reconciliation | **CLOSED 2026-08-01 (Phase 1).** `docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md` assigns an Implemented/Superseded/Deferred verdict to every design area and formally outranks the Feb–Mar 2026 corpus, which now carries a supersession README. `docs/DESIGN_TRACEABILITY.md` maps all 64 design documents to implementing modules |
| LogicNode semantic depth | **CLOSED 2026-08-01 (Phase 3).** Schema v2 promotes 5 descriptive fields to optional top-level properties and reserves 5 more; `payload` unchanged so no reader breaks. `types.in`/`types.out` now carry real signatures for **Python, Java, Haskell** — the only extractors that genuinely recover them. Go/OCaml/Julia/JS-TS stay empty by design, and that emptiness is now informative. The designed ~30-field semantic node remains **Superseded** per ADR row 6 |
| Refined-IR projection | **CLOSED 2026-08-01 (Phase 4).** For AST-backed languages the projection now carries real typed signatures, a real statement-level op stream (7 ops where there was 1), purity from genuine side-effect analysis, and executable equivalence vectors. Regex-only languages keep the templated path, now **labelled** `projection_method: "templated_v1"` so the artifact itself is honest rather than only the docs. RIR catalog populates on every write |
| Behavioural equivalence | **CLOSED 2026-08-02 (Phase 5).** A real `"verification_scope": "behavioural"` section now executes Phase 4's vectors in the shared hardened sandbox and reports a genuine pass ratio. Python only; other languages record an honest `skipped`. `MISSION_EQUIVALENCE_PYTHON_EXECUTION_ENABLED` is **wired** (UPG-21's strict-xfail fired as designed and was removed). Advisory until pass rates are measured across ≥20 real missions (UPG-53) |
| Envelope vocabulary mismatch | **CLOSED 2026-08-01 (UPG-22).** Turned out to be **live, not latent**: an operator setting `DEFAULT_EVENT_PRIORITY` to a lowercase bus value made every state envelope fail validation. Reconciled additively (schema accepts all six values; writers normalise via `to_event_priority`); `docs/PROTOCOL_ENVELOPES.md` documents both transports and corrects the plan's wrong premise about the correlation contract |
| Binary synthesis / LLVM | **CLOSED 2026-08-01 (Phase 1 / UPG-11).** Decision D2 recorded in the ADR; `AGENT-11-DEPLOY` and `AGENT-09-HW` role strings rewritten. `toolchains.py` syntax validation deliberately retained. The `agent_personas.py` Julia LLVM reference was **kept on purpose** — it describes Julia's own compiler, not a theFactory capability |
| LogicNode Registry (design Doc 30) | **Deferred, formalised 2026-08-03 (UPG-73).** Revisit trigger is now measurable against the RIR catalog's `projection_method`: a majority of modules reporting `ast_v1` **and** behavioural equivalence measured across 20+ real missions. Note condition 1 is gated by language coverage — only Python/Java/Haskell produce `ast_v1` today |
| RIR catalog | **CLOSED 2026-08-01 (UPG-43).** Upserted atomically on every module write, keyed by path so a re-run replaces rather than duplicates. Records carry `projection_method`/`ast_projected_fn_count`. Shape shared with `scripts/build_refined_ir_catalog.py` so rebuild and incremental update cannot drift |
| Pod taxonomy | **CLOSED 2026-08-01 (UPG-23).** Pod D relabelled "Mathematical & Functional" across registry role text, source comments, README, AGENTS.md, ARCHITECTURE docs, and diagrams. `pod="Pod D"` is a routing key and was deliberately left unchanged. Pods remain uneven (A:4, B:5, C:4, D:6 specialists) — renamed rather than restructured, per the plan |
| LangGraph | **DECIDED 2026-08-03 (UPG-71).** Doc 14 formally **Superseded** by `mission_flow_v2/transitions.py`; per-agent state machines are not being built. The disabled engine (730 lines + 2 pip deps + 9 test files) is retained for now — removal is scoped in the ADR with a trigger of "after UPG-20 lands", so a lifecycle change does not compete with a lifecycle validation. Imports are already guarded, so carrying cost is low |
| Mission taxonomy specification | **CLOSED 2026-08-03 (UPG-72).** `docs/MISSION_TAXONOMY.md` specifies all 27 values from the code, including which are inert (3 of 4 `DataClassification` tiers and 3 of 5 `DepthMode` values change no behaviour) and a checklist of every site that must be updated before adding a value. **Open defect it surfaced:** `type_strategy` covers 7 of 10 mission types, so `RUN_QC`/`ARCHITECTURE_DOCS`/`SELF_ANALYZE` silently receive `BUILD_NEW`'s codegen routing instruction |
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
| Repository ZIP import | Phase 1 archive core, Phase 2 ZIP import route, Phase 3 ZIP review route, and Phase 4 ZIP UI migration are implemented and locally validated; mission index guard, repo knowledge ingestion, and agent context wiring remain open |
| Protocol Bus lanes | All six lanes have live producers (PBLA-00..04); Beta fix committed (`07883d7`) but not yet re-confirmed live; only Sigma is consumed so far. Four-stage program tracked by `PROTOCOL_BUS_PROGRAM_ROADMAP.md` (PBLA done → EDCP next → Agent Runtime Split → Semantic Bus) |
| Pod-audit routing | Fixed and committed (`4445b6b`); baked into the rebuilt live stack; not yet re-confirmed via a fresh live mission |
| Beta lane (PBLA-03) | Fixed and committed (`07883d7`) — emission added to `_prepare_specialist_plan`, the actual generated_output set-site (the findings doc named the wrong function); baked into the rebuilt live stack; not yet re-confirmed live |
| Generated-language verification | Fixed and committed (`a63dfaf`) — new `_check_language_content_signature` catches Python-fallback substitution for c/cpp/r/go/rust/shell targets; verified offline against the real C/R battery artifacts; not yet re-confirmed against a fresh live mission |
| Compliance trigger | Fixed and committed (`b70d711`) — `AGENT-08-COMPLIANCE` now fires unconditionally at delivery like Security/VC/Tester, per explicit user decision |
| Stack credentials | Postgres credential mismatch (Finding 3): resolved — confirmed `db_ready: true` on the rebuilt stack (old volume was wiped, fresh initdb picked up current `.env`). `api-gateway` `INTERNAL_SERVICE_API_KEY` (Finding 4): very likely resolved (clean 404 instead of the old 503 auth-not-configured error; compose config confirms correct resolution) but not confirmed against a fresh live mission — see Next Actions #1 |
| Database state | `postgres-data`/`redis-data` volumes were wiped once by `stop_app.bat` (`docker compose down -v`) after the 2026-06-30 battery; the stack has since been rebuilt from scratch and is healthy again. A second, non-destructive container recreation happened mid-Phase-4 (via `start_app.bat`) — volumes confirmed intact, no data lost |
| Live verification of Phases 0-3 | Stack is up, healthy, and running the fixed code, but no fresh mission has been run through the chat UI yet to prove the fixes work live end-to-end — this is the single most important next action |
| Legal-hold audit artifacts | **CLOSED 2026-08-05.** `ensure_bucket()` now creates the bucket with Object Lock, absence is reported three ways (ERROR log, `orchestrator_optional_adapter_object_lock_enabled` gauge, `object_storage_object_lock_ready` on `/health` and `/readyz`), and `/internal/audit-reports` returns `object_storage_mirror`. The local bucket was migrated non-destructively to `mission-audit-artifacts-locked`; a `FAILED` report now stores with `Legal-Hold: ON`, `Mode: COMPLIANCE`. **Do not relax `put_audit_report`'s refusal** — a legal hold that silently degrades to an unprotected write is worse than a loud failure |
| Live test authentication | **CLOSED 2026-08-05.** Both live suites authenticate via the shared `tests/services/live_stack_auth.py`; no well-known placeholder credential; the extended suite skips loudly when the gateway is unreachable so a non-verifying run cannot read as green |
| **Pod-assignment and logicnodes missing on the v2 path** | **FIXED IN CODE 2026-08-05, not yet re-confirmed live.** Diagnosis corrected one premise: there are not two execution paths. `mission_flow_v2` is the only lifecycle driver (`lifecycle_interface.get_lifecycle_engine`); the pod worker is a *side consumer* of `missions.state` that happened to be the sole writer of both record types. **Pod assignment:** `_prepare_pod_assignment` now writes the record as it emits `MISSION_POD_MANAGER_ASSIGNED`, marked `assigned_by: "orchestrator"` and written `provisional=True`. `upsert_pod_assignment` enforces directional precedence in SQL — a worker claim supersedes a provisional row, a provisional write can never overwrite a claim — and the worker's `_has_assignment` ignores provisional rows so it still claims and runs its pipeline. **Root cause of *this* mission's 404:** the CEO's `pod_manager_agent_id` was constrained to "one of the four pod managers" but not to the one owning the mission's language, and the two pod-worker gates key off different fields (language vs. bound agent id) — a cross-pod choice makes a mission invisible to *every* pod, silently. `_prepare_pod_assignment` now prefers the registry when the language is known, records the override in `metadata.pod_manager_routing_correction`, and the language gate increments `pod_worker_binding_skips_total{reason="language-mismatch"}` instead of returning silently. **LogicNodes:** empty is correct for `BUILD_NEW` — both writers require source code to extract from; the analogue for generative missions is `logic_clusters` → `pod_group_standards` → `master_logic_stream`, which lives in mission metadata. The misleading part was the UI, now mission-type aware. `test_live_mission_chain_and_artifact_integrity` asserts the assignment record again, plus a shape/health check on logicnodes rather than a non-empty set. Evidence mission: `mission-008af057-8eaf-4935-ba2c-25398ea5e118` |
| **Gate-failure events made missions unopenable** | **FIXED AND VERIFIED LIVE 2026-08-05.** Found while inspecting the rebuilt UI. `MISSION_EQUIVALENCE_BLOCKED`, `MISSION_SECURITY_COMPLIANCE_BLOCKED` and `MISSION_DEPENDENCY_ABSORPTION_BLOCKED` are written to `mission_events` by `mission_flow_v2.lifecycle`, but none were in the `EventType` Literal in `models.py` — only the happy-path siblings had ever been added. `EventType` is the response model, so one unlisted value makes pydantic reject the entire payload: `/missions/{id}/events`, `/chain-trace` and `/operations/alerts` all 500 → **502 at the gateway**, and any mission that failed a gate could not be opened in Mission Control at all — precisely the mission an operator needs to read. Observed on `mission-2eb92c32-0a7b-456b-9c40-bdff2d98a805`, whose detail page hung on "Loading mission diagnostics". All three added; a regression guard in `tests/services/test_regression_contracts.py` scans every `insert_mission_event` / `transition_mission_state` site (including the `asyncio.to_thread(fn, ...)` form, which an earlier version of the guard missed) and fails if any persisted event type is undeclared. Verified live after rebuild: all three endpoints 200, mission detail loads |
| **Intake parked 100% of missions / runtime QC never ran** | **BOTH GATES OPENED 2026-08-12; invocation + honesty closed 2026-08-12→17.** Intake: `PM_AUTO_ACCEPT_DEFAULTS_ENABLED` (default **true**) takes the `user_intent="finalize_plan"` path. Runtime QC is reachable without the testdata agent. The false FAIL (CLI invoked with no args) was fixed by deriving `invocation_args` from `usage_example`. `started_only` / syntax-only are ADVISORY. Generated tests, when present, are the sandbox command. Compose default is `RQCA_ENFORCEMENT_ENABLED=true` (local `.env` may still override to `false`). |
| **Pod-language runtime verification** | **19 of 19 languages verified live 2026-08-11, with negative controls.** Was 1 (Python). Every language now runs a hello-world through the real sandbox AND rejects a realistic Python-fallback artifact — the substitution this gate exists to catch. `matlab` and `mathematica` run on licence-free subset interpreters (`gnuoctave/octave:9.2.0`, `mathicsorg/mathics:latest`) because the product must work with **no external requirements** and a per-clone vendor licence is not an option; reports carry `runtime_substitute` and `verified_scope` so a pass can never read as full vendor compatibility. Mathics additionally needs `failure_patterns` (`Syntax::`) because Wolfram self-evaluates undefined symbols and exits 0 on Python source. **Two false-PASS holes were found by the negative control and would not have been found by review:** PHP echoed a file with no `<?php` tag and exited 0 (Python renamed `.php` PASSED — now guarded), and TypeScript on `node` failed every genuinely typed artifact (now Deno, which type-checks). Re-run `scripts/rqca_language_audit.py` after touching `_LANGUAGE_RUNTIMES`. Still absent: `csharp` (`dotnet-script` uninstallable offline). **Open:** kotlin/scala/zig/ocaml use third-party images by mutable tag; pin by digest |

---

## Known Non-Issues

- `.pytest-tmp/` may remain as an untracked local temp directory from prior test
  runs. It is not part of the repository.
- OTel/Jaeger export warnings during tests are expected when Jaeger is not
  running locally and do not by themselves fail tests.
- Files under `docs/archive/` are historical and should not drive active work
  unless reconciled into this file.
