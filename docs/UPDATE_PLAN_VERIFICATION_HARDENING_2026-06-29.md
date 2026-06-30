# Update Plan: Verification & Reporting Hardening

Document version: 2026.06.29-c
Last updated: 2026-06-29
Status: Active plan
Audience: Maintainers, operators, and AI coding agents

This plan captures correctness-verification and reporting gaps discovered while
running a live end-to-end mission through the Mission Control chat intake (a
"Modern Neon Pong" code-generation mission) on 2026-06-29. The mission reached
`COMPLETE` and produced a working artifact, but the run exposed gaps between what
the factory *verifies* and what it *promises*. Use this with
`CURRENT_TODO.md` and `HANDOFF_CURRENT.md`.

---

## Background: what the Pong mission exposed

The mission was created through the operator chat, the PM agent produced a
feature contract ("single self-contained HTML file", Player-vs-AI and local
2-player, score to 11), the mission ran the full Mission Flow v2 pipeline, and
the delivered artifact was a complete, well-structured Pong implementation.

Three real defects surfaced that automated verification did not catch:

1. The deliverable was a `.js` file, not the contracted **single self-contained
   HTML file**. A `.js` file cannot be opened in a browser on its own, so it did
   not satisfy the contract's own acceptance criteria — yet the mission reached
   `VERIFIED` and `COMPLETE`.
2. Non-ASCII characters were corrupted (title-screen arrows `►`/`◄`
   rendered as mojibake). The artifact digest is computed after corruption, so
   integrity checks pass on corrupted bytes.
3. The Mission Detail UI labeled the run `LEGACY V1` even though it demonstrably
   executed the Mission Flow v2 phase pipeline.

---

## Root causes (pinned in code)

| ID | Finding | Location |
|----|---------|----------|
| A | "Verification" is integrity only. `verified:True` / `verification_method:"sha256"` is set unconditionally. | `services/orchestrator/orchestrator/build_artifacts.py` |
| B | Acceptance criteria are never machine-checked. `_check_acceptance_criteria` always returns `manual_review` / `required=False`. | `services/orchestrator/orchestrator/equivalence_verifier.py` |
| C | No artifact-format gate. `_check_language_alignment` compares language strings only; nothing checks the contracted artifact form (HTML vs `.js`). | `services/orchestrator/orchestrator/equivalence_verifier.py` |
| D | Mojibake origin is upstream of packaging. Provider decode uses `response.json()` and packaging uses `encode("utf-8")` — both correct — so corruption comes from the raw LLM output or a metadata storage round-trip. | `services/orchestrator/orchestrator/llm_delegation/providers.py`, storage layer |
| E | Lifecycle-engine badge is inferred client-side and defaults to "Legacy V1" when the v2 routing marker is absent on the mission record. | `apps/mission-control/app/(shell)/missions/detail/page.tsx` |

The unifying theme: the factory treats "we hashed the bytes" as "the deliverable
is correct." Each Tier-1 gap is a facet of that single missing dimension.

---

## Progress

- **2026-06-29 — Phase 1 complete** (branch
  `verification-correctness-hardening`). Phase 1a (artifact-format gate) and 1b
  (per-criterion acceptance evaluation) landed in `equivalence_verifier.py`.
  Phase 1c separated integrity from correctness: the artifact `verification`
  block is now tagged `verification_scope="integrity"`, the equivalence report is
  tagged `verification_scope="correctness"`, the integrity check copy clarifies
  it attests bytes-intact (not runnable), and the Mission Control
  `EquivalenceReportPanel` explains the distinction. Phase 2 branch code now
  adds RQCA artifact-smoke evidence and authoritative lifecycle-engine reporting.
  Focused backend tests, targeted Ruff, Mission Control `tsc` lint,
  documentation validation, and OpenAPI drift checks pass. Phase 3 remains.
  End-to-end live re-run of a Pong-style mission is still pending a stack restart.

## Phase 1: Make verification mean correctness

Backend-only verification logic. Small, high-leverage, no infrastructure.

- **1a. Artifact-format gate — DONE.** Added `_check_artifact_format` to
  `equivalence_verifier.py`. When the feature contract names a deliverable
  format, the packaged artifact extension must match (`required=True`). A `.js`
  file against a "single self-contained HTML file" contract now fails
  verification and blocks under enforcement.
- **1b. Acceptance-criteria evaluation — DONE.** Replaced the always-
  `manual_review` body of `_check_acceptance_criteria` with per-criterion keyword
  coverage against the generated code and description, emitting `criteria_status`
  and reporting which criteria are unaddressed. Advisory by default.
- **1c. Separate integrity from correctness — DONE.** Tagged the artifact
  `verification` block `verification_scope="integrity"` and the equivalence
  report `verification_scope="correctness"`; clarified the integrity check copy
  to state it attests bytes-intact, not runnable; and updated the Mission Control
  `EquivalenceReportPanel` to explain that a passing integrity check does not
  mean the artifact runs or meets the contract.

Exit: new unit tests (done); a Pong-style mission shows the format gate flagging
`.js`-vs-HTML (pending live re-run after stack restart).

## Phase 2: Runnable smoke and honest engine reporting

- **2a. Runnable-artifact verifier** — DONE in branch via the existing
  `rqca_agent.py` / `RQCA_*` plumbing. Runtime QC now attaches
  `artifact_smoke` evidence; JavaScript/TypeScript artifacts run a `node
  --check` syntax smoke and fail before sandbox execution on syntax errors; HTML
  artifacts get static HTML structure plus inline-script syntax smoke and are
  reported as browser-load `DRY_RUN` because the orchestrator image does not
  currently ship a headless browser runtime. Advisory/enforcement behavior still
  follows the existing RQCA flags.
- **2b. Authoritative lifecycle-engine field** — DONE in branch. The backend now
  derives a stable `lifecycle_engine` from lifecycle settings, persists/exposes
  it via mission metadata and `MissionRecord`, includes it in chain-trace
  payloads, stamps gateway intake metadata, and Mission Control consumes it
  before falling back to client inference.

## Phase 3: Encoding trace, PM truncation, tracked backlog

- **3a. Mojibake** — add a temporary raw-bytes capture (provider response +
  post-storage readback) on a non-ASCII mission to localize LLM-output vs
  storage round-trip, then add a permanent UTF-8 validity guard and repair in
  `build_generated_output_artifact` (digest computed after normalization) plus a
  regression test.
- **3b. PM clarifying-question truncation** — locate and lift the length cap that
  clips the PM clarifying questions in the chat intake.
- **3c. Tracked backlog** — `INF-008`, Phase 8 `mission_flow_v2/` strict
  coverage, provider preflight + Settings/vault, key rotation, failure-injection
  and provider-fallback proofs.

---

## Guardrails

- Each phase is gated by `make validate` (Ruff, documentation validation,
  OpenAPI drift, schema validation, full pytest, Mission Control lint/test) plus
  a fresh Phase 13 smoke and a non-ASCII regression mission.
- Work lands on the `verification-correctness-hardening` branch, not `main`.

---

## Sequencing rationale

Phase 1 is pure verification logic — smallest change, highest leverage, and on
its own catches both Pong defects (wrong format, and an unverified-but-`VERIFIED`
artifact). Phase 2 adds sandbox/RQCA wiring and a small schema/API addition.
Phase 3 is investigation and polish.
