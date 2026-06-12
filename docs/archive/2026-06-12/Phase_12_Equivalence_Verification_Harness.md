# Phase 12 - Equivalence Verification Harness

**Status:** Implemented
**Last updated:** 2026-05-18  
**Depends on:** Phase 11 AIM, Phase 10 delivery summaries, build artifact packaging

## Validated Entry State

The repo already has the surfaces Phase 12 should reuse:

- `mission_flow_v2.py` packages source/generated build artifacts and already has
  a `VERIFIED -> COMPLETE` completion gate.
- `build_artifacts.py` records sha256 verification for generated-code and
  source-bundle artifacts.
- `routes/internal.py` exposes chain trace, build artifacts, audit reports, and
  audit artifacts.
- Mission Control renders build artifacts, audit evidence, contracts, FETCH,
  FUSION, DELIVERY, and AIM.
- Phase 11 now provides `application_intelligence_map` for source-bearing
  analysis/import/modernize/debug/security missions.

The missing piece was a durable equivalence report that says whether generated or
transformed output satisfies the contract and available source/AIM evidence.

## Implementation Plan

1. Add `services/orchestrator/orchestrator/equivalence_verifier.py`.
   - Produce `equivalence_report.v1`.
   - Inputs: mission context, `feature_contract`, `mission_contract`,
     `generated_output`, build artifacts, and `application_intelligence_map`.
   - Outputs: `passed`, `blocking`, `checks`, `findings`, `risk_level`,
     `evidence_refs`, `source`, and timestamps.

2. Start with deterministic contract checks.
   - Verify generated output exists when the contract requires a build artifact.
   - Verify artifact digest/verification metadata exists and is successful.
   - Verify generated output language/filename aligns with target language.
   - Verify acceptance criteria are represented as explicit checks.
   - Mark untestable criteria as `manual_review` instead of pretending pass.

3. Wire Mission Flow v2.
   - Generate equivalence after build artifact packaging and before delivery
     summary/COMPLETE.
   - Persist `metadata["equivalence_report"]`.
   - Emit `MISSION_EQUIVALENCE_VERIFIED` on pass or non-blocking review.
   - Emit `MISSION_EQUIVALENCE_BLOCKED` and keep the mission at `VERIFIED` when
     enforcement is enabled and a required check fails.

4. Expose and render evidence.
   - Add `equivalence_report` to chain trace responses.
   - Add Mission Control types and a compact Mission Detail panel.
   - Mirror the report into audit evidence using the existing audit-report
     endpoints/storage shape.

5. Add opt-in Python execution later in the phase.
   - Guard with an explicit setting such as
     `MISSION_EQUIVALENCE_PYTHON_EXECUTION_ENABLED`.
   - Execute only generated artifacts in an isolated temp workspace with timeouts.
   - Do not execute submitted `source_code` or source bundles by default.

## Non-Goals

- Do not build the full Runtime QC/browser automation system here; that belongs
  to the runtime QC phase.
- Do not remove dependencies or run shadow dependency absorption here; Phase 12
  only creates the verification primitive that later dependency absorption can
  reuse.
- Do not claim behavioral equivalence for criteria that were not executable or
  directly checkable.

## Validation

- [x] `BUILD_NEW` with generated output creates `equivalence_report`.
- [x] Generated-code artifact without successful verification blocks when
  enforcement is enabled.
- [x] Source-bundle-only `ANALYZE_ONLY` mission skips equivalence gating unless it
  produces generated output.
- [x] Chain trace exposes `equivalence_report`.
- [x] Mission Detail renders the equivalence panel.
- [x] Targeted pytest covers pass, fail/block, and non-blocking review paths.
- [x] `python -m ruff check services\orchestrator\orchestrator tests\services`
  passes for touched files.
- [x] `npm --prefix apps\mission-control run lint` passes.
