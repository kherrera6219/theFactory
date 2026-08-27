# Stuck missions: what is actually wrong and what to do

Plan only. Nothing in here has been executed against the running stack.

As of 2026-08-27 the local stack shows the `missions-completion-blocked` alert
open, driven by 17 missions parked at `VERIFIED`.

**Headline, after tracing:** 15 of the 17 are blocked by a failing runtime QC
that recorded nothing an operator could read. The chain trace showed whatever
had blocked them *previously* -- in most cases a `delta_audit` entry from
2026-08-17 -- so the visible reason was months out of date and pointed at the
wrong subsystem. Commit `1b40edc` fixes the silence. Group B below documents the
correction, including the wrong conclusion this document reached on first
draft.

## Group A -- 2 missions in a permanent retry loop (LIVE)

| Mission | Blocks recorded | Last block |
| --- | --- | --- |
| `mission-769bf926` | 26 | 2026-08-27T04:02:11Z |
| `mission-db901d98` | 21 | 2026-08-27T04:02:11Z |

Both re-blocked roughly 90 seconds after a stack rebuild, so this is current
behaviour, not history. Gate details:

```
build_artifact_required:       true
build_artifact_status:         "FAILED"
has_successful_build_artifact: false
```

`lifecycle_recovery` re-drives every `VERIFIED` mission through
`start_lifecycle_task` on each orchestrator start (`lifecycle_recovery.py:40-80`),
which is why the block counts keep climbing. They will retry forever and never
succeed: the artifact is already recorded `FAILED`, and nothing in the retry
path regenerates it.

**Options**

1. **Fail them out.** Move both to `FAILED` with a note. Honest -- they are not
   completable -- and it silences the alert. Loses nothing: the artifacts
   already failed.
2. **Regenerate their artifacts.** Re-run the build-artifact phase so packaging
   is attempted again. Only worth it if the original failure was transient; the
   `FAILED` status suggests it was not.
3. **Leave them.** The alert stays lit, and the block counts keep growing.

**Recommendation: option 1.** These predate today's fixes and there is no path
by which retrying produces a different result.

## Group B -- CORRECTED: not stale, silently blocked by runtime QC (LIVE)

**This section originally read "10 missions with stale delta_audit blocks (NOT
live)". That was wrong, and the error is instructive: it was inferred from the
last *recorded* chain event, and the actual block recorded nothing at all.**

Orchestrator logs settle it:

```
2026-08-27T04:02:11 INFO orchestrator.mission_flow_v2.lifecycle:
  v2: mission mission-7030222d-... blocked by runtime QC report FAIL
```

`docker logs deploy-orchestrator-1 | grep "blocked by runtime QC"` names **15
distinct missions** since the rebuild -- nearly every VERIFIED mission on the
box, including `mission-9730a057` from the 2026-08-27 coverage batch.

So the true breakdown of the 17 is:

| Cause | Count | Recorded a reason before `1b40edc`? |
| --- | --- | --- |
| Runtime QC failure | 15 | **No -- silent** |
| Build artifact FAILED | 2 | Yes |

The `delta_audit` entries dated 2026-08-17 were simply the last block that
*left a trace*, from when EDCP was still on. Every block since has been runtime
QC, writing only to `mission_events` and to the log, never to
`metadata.chain_trace` -- so `/chain-trace` kept showing a months-old
delta_audit reason while the live cause went unrecorded.

**This is the strongest possible argument for UPDATE-3** (commit `1b40edc`): the
silent path was not an edge case affecting three missions from one test batch,
it was hiding the real cause of 15 of 17 stalled missions and actively
misdirecting diagnosis -- including mine, in the first draft of this document.

There is **no second silent-stall path**. There is one, it is this, and it is
fixed.

**What to do:** deploy `1b40edc`, then let recovery re-drive them once. Each
will re-block with `gate: "runtime_qc"`, its verdict, exit code and stderr
excerpt in the chain trace, and the real cause becomes visible per mission. Only
then is it worth deciding which to fail out -- several are likely the same
bundle-header and argv defects that commit also fixes, so a subset may simply
pass on re-run.

## Group C -- 5 missions blocked by security compliance (working as intended)

`MISSION_SECURITY_COMPLIANCE_BLOCKED`. The gate did its job and recorded its
reason. No action; these are correctly stopped.

## Group D -- 3 from the 2026-08-27 language coverage run

javascript, ocaml and python, stalled because their runtime QC executed and
failed on the two defects fixed in commit `1b40edc` (bundle header compiled as
source; source-code usage examples shell-split into argv).

They will **not** self-heal: the fix changes generation-time behaviour for new
missions, not the recorded QC verdict on old ones. After `1b40edc` is deployed,
re-running the coverage batch should produce clean results; these three can be
failed out with the Group A set.

Note that these three were the ones that stalled *silently*. With UPDATE-3 they
would now carry `gate: "runtime_qc"` plus verdict, exit code and stderr excerpt
in the chain trace.

## Order

1. **Done (read-only).** Traced Group B: no second silent path exists. The one
   silent path is the runtime QC block, fixed in `1b40edc`.
2. **Deploy `1b40edc`, then let recovery re-drive once.** Every stalled mission
   then records its real cause. Do this before deciding anything else -- it
   costs one restart and turns 15 unexplained stalls into 15 readable ones.
3. **Re-run the coverage batch** (`test_batch=lang-coverage-2026-08-27`). The
   bundle-header and argv fixes in the same commit may let some of these pass
   outright, which changes how many need failing out.
4. **Then** fail out whatever still cannot complete -- Group A almost certainly,
   plus whichever of the 15 still fail for real reasons.
5. Leave Group C alone; it is working as designed.

Nothing here should run while a mission batch is in flight.
