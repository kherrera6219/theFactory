# Stuck missions: what is actually wrong and what to do

Plan only. Nothing in here has been executed against the running stack.

As of 2026-08-27 the local stack shows the `missions-completion-blocked` alert
open, driven by missions parked at `VERIFIED`. They are **not one problem**.
Three groups, and only one of them is live.

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

## Group B -- 10 missions with stale `delta_audit` blocks (NOT live)

Newest block: **2026-08-17**. None have re-blocked since.

`EVENT_DRIVEN_CONTROL_PLANE_ENABLED=false` in the running orchestrator
(confirmed via `docker exec deploy-orchestrator-1 env`), and `_delta_audit_gate`
returns `(True, {})` when the flag is off (`mission_flow_v2/lifecycle.py:100`).
That gate is therefore inert now, and these blocks are residue from when EDCP
was enabled.

**Unresolved:** they are not re-blocking, but they are also not advancing. With
the gate inert, a re-drive should carry them past it to the equivalence stage
and either complete them or emit `MISSION_EQUIVALENCE_BLOCKED`. Neither event
appears. This is the one thread from the 2026-08-27 investigation that was never
closed.

**Do not clear these before understanding that**, since "not advancing and not
recording why" may be the same class of silent stall that
`docs/LANGUAGE_COVERAGE_FINDINGS_2026-08-27.md` UPDATE-3 fixed for runtime QC --
in which case there is a second silent path still unfixed.

**Suggested next step:** read-only. Pick one of the ten, watch an orchestrator
restart, and trace whether `start_lifecycle_task` reaches
`_advance_verified_to_complete` for it at all. Cheap, mutates nothing, and
answers whether a second silent-stall path exists.

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

1. Trace one Group B mission (read-only) -- it may reveal a second silent path.
2. Fail out Group A and Group D once Group B is understood.
3. Leave Group C alone.

Nothing here should run while a mission batch is in flight.
