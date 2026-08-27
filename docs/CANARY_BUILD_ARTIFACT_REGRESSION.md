# Canary regression: `MISSION_BUILD_ARTIFACT_FAILED`

**Status:** root cause identified, fix not yet chosen.
**Found:** 2026-08-26, from Weekly Qualification run `32707536901` (2026-08-24).

## Symptom

Weekly Qualification fails at step *Dedicated-agent canary trend* with
`pass_rate=0.0%`. All four languages (python, rust, kotlin, julia) halt at
`VERIFIED` and never reach `COMPLETE`.

This is **not** the known behavioural-equivalence gap. That gate emits
`MISSION_EQUIVALENCE_BLOCKED`; it never fires here because the mission never
reaches it. The chain ends:

```
MISSION_LOGIC_FOLDED
MISSION_BUILD_ARTIFACT_FAILED   <- cause
MISSION_COMPLETION_BLOCKED      <- consequence
```

`MISSION_BUILD_ARTIFACT_FAILED` appears in no archived canary run before
2026-08-24.

| Run | Result | Artifact event |
| --- | --- | --- |
| 2026-03-08 | 4/4 COMPLETE | — |
| 2026-05-29 | 4/4 COMPLETE | — |
| 2026-08-24 | 0/4, all VERIFIED | `MISSION_BUILD_ARTIFACT_FAILED` |

## Root cause

Three independently reasonable changes compose into the failure. Only the third
armed the other two.

1. **`0c90b3a` (2026-05-16)** — `mission_has_generated_output()` returns `False`
   when `generated_output["source"] == "fallback"`.
2. **`e4a0c21` (2026-05-31)** — `mission_flow_v2/base.py:438` hardcodes
   `"expected_artifacts": ["mission_contract", "logic_clusters", "generated_output"]`
   on every v2 mission.
3. **`d27a0ff` (2026-07-01)** — adds a third clause to
   `mission_requires_build_artifact()`:

   ```diff
   -    return isinstance(source_code, str) and bool(source_code.strip())
   +    if isinstance(source_code, str) and bool(source_code.strip()):
   +        return True
   +    return mission_expects_generated_output_artifact(metadata)
   ```

   The new predicate reads the field from (2), so it is `True` for *every* v2
   mission.

The qualification workflow defines **no LLM credentials** (`qualification.yml`
contains no `secrets.*`, no API-key env). So `aim_generator.py:177`
(`source="llm" if isinstance(parsed, dict) else "fallback"`) always yields
`fallback` in CI.

Composed:

```
requires_build_artifact = True    (via 3 -> 2)
has_generated_output    = False   (via 1, source == "fallback")
source_code             = absent
  -> build_missing_source_artifact_failure()
  -> status "FAILED"  (build_artifacts.py:351, the only non-SUCCESS producer)
  -> MISSION_BUILD_ARTIFACT_FAILED  (build_artifacts.py:386)
  -> MISSION_COMPLETION_BLOCKED
```

Before `d27a0ff`, a fallback-only mission returned `False` from
`mission_requires_build_artifact`, packaging was skipped, and the mission
completed. That is why 2026-05-29 passed with ingredients (1) and (2) already
in place.

Uniformity across four unrelated languages is consistent with this: every step
in the chain is language-agnostic.

## Fix options (not yet decided)

The real question is what the canary is meant to prove. Pick deliberately.

1. **Give CI real LLM credentials.** The canary then exercises the true path and
   proves what it claims to prove. Costs money per scheduled run and makes a
   scheduled job depend on a third-party API's availability.
2. **Make the canary assert the fallback outcome.** Honest about what a
   credential-less environment can verify, but it stops being evidence that
   mission generation works — it only proves the pipeline is wired.
3. **Let a fallback artifact package as a degraded-but-real artifact** (new
   status, e.g. `DEGRADED`, that satisfies packaging without claiming success).
   Keeps the canary green and preserves the signal that output was synthetic.
   Largest blast radius — `equivalence_verifier.py:100` applies the same
   `source == "fallback"` rejection and would need the same treatment.

**Do not** simply drop the `source == "fallback"` check in
`mission_has_generated_output()`. That check exists so a fallback stub cannot
masquerade as generated code, and removing it re-creates the silent-success
failure that several 2026-08 commits were written to close.

## Reproducing

No live stack needed to confirm the reasoning; the evidence is in the run
artifacts:

```
gh run download 32707536901 -R kherrera6219/theFactory -D <dir>
# then: <dir>/weekly-qualification-artifacts/canary-runs/*20260824T084541Z.json
```

Each file carries `chain_event_types`, `final_state`, and `failure_reasons`. It
does **not** carry the artifact record's `status`/`storage_ref` detail, so
confirming the exact `failure_reason` string end-to-end requires either the
mission metadata `chain_trace` from the CI database or a local repro.
