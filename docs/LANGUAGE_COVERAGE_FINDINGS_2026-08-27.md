# Language coverage run, 2026-08-27: findings

20 `BUILD_NEW` / `SPRINT` / `PLAN_ONLY` missions, one per supported target
language, submitted against the local full-dedicated stack.
Batch tag: `test_batch=lang-coverage-2026-08-27`.

## What passed

- **Routing: 20/20.** Every language reached its expected pod (`podA`..`podD`),
  `routing_enforced=true` on all, verified against `/pod-assignment` rather than
  the metadata echo.
- **Generation: 20/20.** Every mission produced `generated_output.source="llm"`
  via `gemini-3.7-flash`. Real generation, no fallback stubs. This independently
  re-confirms the diagnosis in `CANARY_BUILD_ARTIFACT_REGRESSION.md`: the CI
  failure is credential absence, not a packaging defect.
- **Security compliance: 20/20 `passed`.**
- **Equivalence: 20/20 `passed`** (correctness scope).

## Headline finding

**No mission in this run obtained real correctness evidence for its generated
code, yet 17 of 20 completed.**

| Runtime QC outcome | Count | Languages |
| --- | --- | --- |
| `dry_run` -- never executed | 10 | csharp, haskell, java, julia, kotlin, php, r, ruby, scala, typescript |
| `docker_live`, **no arguments derived** -- exit code explicitly "not evidence of correctness" | 7 | c, cpp, go, rust, zig, matlab, mathematica |
| `docker_live` with derived arguments -- **all FAILED** | 3 | javascript, ocaml, python |

The 7 no-argument runs carry the harness's own disclaimer in
`not_exercised_note`: *"executed with no arguments because no invocation could
be derived from the artifact's usage example, so its exit code is not evidence
of correctness."* That note is honest, and it is correct to record it -- but it
means a `COMPLETE` mission in this run asserts nothing about whether the code
works.

## UPDATE-1 -- `## FILE <name>` bundle header is compiled as source

**Severity: high. Affects 20/20 payloads; fatal wherever `#` is not a comment.**

Every `generated_output.generated_code` begins with the source-bundle delimiter:

```
## FILE sum_integers.ml
(** [sum_integers lst] computes ... *)
```

`_SOURCE_BUNDLE_FILE_PATTERN = re.compile(r"^## FILE (.+)$", re.MULTILINE)` in
`build_artifacts.py` is the bundle format. Runtime QC writes the raw bundle text
to `/workspace/<filename>` and compiles it. Neither `rqca_agent.py` nor
`runtime.py` references that pattern anywhere -- nothing strips it.

Proven live on ocaml (`exit=2`):

```
File "/workspace/sum_integers.ml", line 1, characters 0-2:
1 | ## FILE sum_integers.ml
    ^^
Error: Syntax error
```

It survived undetected because most languages in the matrix treat `#` as a line
comment (python, ruby, r, php, shell-likes), and the rest never executed. OCaml,
having no `#` line comment, is the case that exposes it. C/C++/Zig/Go would very
likely fail the same way once they are actually invoked.

**Fix:** parse the bundle and write each file's *body* to the workspace, reusing
`build_artifacts._parse_source_bundle` rather than writing `generated_code`
verbatim.

## UPDATE-2 -- source-code usage examples are shell-split into argv

**Severity: high. Cause of 2 of the 3 live failures.**

`_invocation_from_usage_example` (`rqca_agent.py:267`) derives program arguments
by `shlex.split`-ing the usage example and taking every token *after* the one
naming the artifact. That is correct for a shell invocation
(`go run main.go input.txt`), which is what it was written for.

It misfires when the specialist returns a **library/API** example instead,
because the artifact name then appears as an *identifier in source code* rather
than as a command operand:

| lang | usage_example | derived argv |
| --- | --- | --- |
| ocaml | `let total = sum_integers [1; 2; 3; 4] (* returns 10 *)` | `["[1;","2;","3;","4]","(*","returns","10","*)"]` |
| python | `from math_utilities import sum_integers  total = sum_integers([1,2,3,4]) print(total)` | `["import","sum_integers","total","=",...]` |

The python case then fails as
`python -m unittest discover: error: unrecognized arguments`.

The function's own guard -- "return `[]` when the artifact is not named" -- is
defeated precisely because the artifact *is* named, just not as an operand. The
docstring's conservatism argument is sound; the unhandled case is
"example is source code, not a command".

**Fix:** before deriving args, require the line to look like a shell invocation
(first token is a known runner/executable or the filename itself). If it parses
as source -- contains `=`, `import`, `let`, `(`, `;` in non-shell position --
treat it as "no invocation derived" and take the existing not-exercised path.

## UPDATE-3 -- a failed runtime QC blocks completion silently

**Severity: high (operability).**

javascript, ocaml and python are parked at `VERIFIED` and have not advanced in
over ten minutes. Their chain ends:

```
MISSION_EQUIVALENCE_VERIFIED
MISSION_SECURITY_COMPLIANCE_PASSED
MISSION_INTEGRATION_TESTS_GENERATED
MISSION_TESTDATA_MANIFEST_READY
MISSION_RUNTIME_QC_COMPLETE
```

**No `MISSION_COMPLETION_BLOCKED` event is written**, and no `gate` is recorded.
Every other stop in this lifecycle records a reason; this one does not, so an
operator sees a stalled mission with no cause. This is the same signature as the
three previously-unexplained missions found while investigating the live
`missions-completion-blocked` alert -- reproducing it here with fresh missions
rules out stale state and makes it a live defect.

Note the correlation is exact: the three that ran live QC *and failed* are the
three that stalled; the seventeen that dry-ran or ran without arguments all
completed.

**Fix:** emit `MISSION_COMPLETION_BLOCKED` with `gate: "runtime_qc"` and the QC
verdict/exit code in `details` whenever a failing runtime QC prevents the
advance, matching how `delta_audit` and the artifact gate already report.

## UPDATE-4 -- WITHDRAWN (not a defect)

**Originally filed as "10 languages never execute and do not say why". That was
wrong, and the error was mine: the survey read `not_exercised_note`, which is
the field the *live-but-no-arguments* path uses, and concluded the dry-run path
recorded nothing. The dry-run path records `dry_run_reason`, and it is populated
on every one of those missions.**

Both non-executing paths already disclose their reason:

| Path | Field | Populated |
| --- | --- | --- |
| `execution_type=dry_run` | `dry_run_reason` | 10/10 |
| `execution_type=docker_live`, no args derived | `not_exercised_note` | 7/7 |

No code change is warranted. What the data does show is a genuine
**environment limitation**, not a reporting gap: 9 of the 10 dry runs are

> `artifact requires dependencies that cannot be installed in an offline
> sandbox: <deps>`

naming junit-jupiter (java), vitest (typescript), minitest (ruby), testthat (r),
scalatest (scala), phpunit (php), kotlin-test (kotlin), `Test` (julia) and
`base` (haskell). The specialists generate idiomatic unit tests, and the offline
sandbox cannot install the test framework those tests import, so execution is
skipped before it starts. The tenth is csharp: *"Live execution not supported
for csharp."*

That is a **design question, not a bug**: either vendor the common test
frameworks into the language base images, or accept that unit-test-bearing
artifacts in those languages are verified by syntax/smoke only. Worth deciding
deliberately, since it is the reason most of the matrix produces no correctness
evidence.

It also means the earlier remark questioning `5c14c4f` ("17 of 19 live") was
unfounded -- the runtimes are configured; they are declining to execute for a
stated and legitimate reason.

## Lower-priority observations

- `equivalence_report.behavioural.status = "skipped"`, reason *"no Refined-IR
  module in mission metadata"* -- the known BUILD_NEW equivalence gap. Expected;
  no action here.
- `equivalence_report.findings` on every mission: *"No explicit deliverable
  format was specified in the contract"* and *"Content-based language
  verification is not ..."*. Recurs across all 20; may be prompt/contract
  tuning rather than a defect.
- ocaml reports `base_image_official: false`.
- `runtime_qc_report.qc_assessment.source = "fallback"` with
  `confidence: "LOW"` on the failures -- the assessment layer falls back when
  execution fails, which is reasonable but means the failure summary is not
  LLM-reviewed.

## Suggested order

1. **UPDATE-1** -- one-line-ish fix, unblocks real execution everywhere.
2. **UPDATE-2** -- without it, derived invocations stay wrong for library-style
   artifacts.
3. **UPDATE-3** -- cheap, and stops silent stalls from looking like the
   unrelated `missions-completion-blocked` alert.
4. **UPDATE-4** -- scoping question as much as a fix.

1 and 2 must land together to be meaningful: fixing the header without fixing
argv derivation just moves the failure, and vice versa.

## Reproducing

Missions are tagged `test_batch=lang-coverage-2026-08-27`. Submitter and pollers
used for this run are in the session scratchpad
(`submit_lang_missions.py`, `poll_lang_missions.py`).

---

# Follow-up: readme-demo batch, 2026-08-31

Three `BUILD_NEW` / `STANDARD` / `PLAN_ONLY` missions (python, typescript, rust)
run against the fully-fixed build to produce README screenshots. Reviewing them
turned up one new defect and one open question.

## FINDING-5 -- generated tests were flattened onto one line (FIXED)

**Severity: high. Affected every generated test in every mission.**

`generators_artifacts.py` stored the LLM's test module through `_clean_text`,
which replaces every control character with a space. The newline is a control
character, so a generated test arrived as:

```
import inspect import pytest from sum_integers import sum_integers  def test_empty_list():     assert sum_integers([]) == 0 ...
```

Python cannot import that. The python demo mission failed with
`ImportError: Failed to import test module: test_sum_integers`, and the same
flattening applies to every language the tester agent produces.

`generated_output.generated_code` was never affected -- it goes through
`_strip_code_fences`, which preserves layout. The asymmetry is why this survived:
the artifact under test looked fine, only its tests were broken.

**This inflates the "no correctness evidence" finding above.** Some of the
`docker_live` runs that appeared to fail on their own merits were running tests
that could never have loaded.

**Fix:** `text._clean_code` -- same redaction and ReDoS cap as `_clean_text`,
same removal of genuinely dangerous control characters, but tab, newline and
carriage return are preserved. Wired into the one code-bearing field that used
`_clean_text`. Regression tests in
`tests/services/test_generated_code_sanitizer.py`, including one that pins the
old `_clean_text` behaviour so the distinction cannot be quietly undone.

## OPEN-6 -- library artifacts are compiled as binaries

**Severity: medium. Not fixed; needs a design decision.**

The rust demo produced `src_lib.rs`, a library. Runtime QC ran the language's
standard command, `rustc /workspace/src_lib.rs -o /tmp/a.out && /tmp/a.out`,
which fails:

```
error[E0601]: `main` function not found in crate `src_lib`
```

The harness recorded `verdict=DRY_RUN` with `not_exercised_note` -- "executed
with no arguments because no invocation could be derived ... so its exit code is
not evidence of correctness" -- and the mission completed.

That excuse is right for a CLI that wanted arguments. It is wrong here: the
artifact could not be *built* as a binary at all, and the same treatment would
hide a genuine compile error in a library. The mission's own usage example said
`Execute cargo test`, which is what should have run.

Two things are tangled and worth separating:

1. **A build failure is not a "not exercised" outcome.** Failing to compile says
   the artifact is broken regardless of arguments. Distinguishing build failure
   from run-exited-nonzero would stop that being excused.
2. **Library artifacts need a library verification path** -- `rustc
   --crate-type lib`, `cargo test`, `go test`, `pytest`, and so on -- rather than
   the binary command. This is the same shape as the offline test-framework
   question in UPDATE-4: what does "verified" mean for an artifact that is not a
   program?

Deliberately left open rather than patched, because guessing a per-language
answer here is how the argv defect (UPDATE-2) got introduced in the first place.
