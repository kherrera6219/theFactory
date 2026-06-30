# Update Plan: Verification & Reporting Hardening

Document version: 2026.06.29-a
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

## Phase 1: Make verification mean correctness

Backend-only verification logic. Small, high-leverage, no infrastructure.

- **1a. Artifact-format gate** — add `_check_artifact_format` to
  `equivalence_verifier.py`. When the feature contract declares a target
  artifact format / entry point, require the artifact `manifest.filename`
  extension and entry point to match. `required=True` when the contract is
  explicit. This check would have failed the Pong mission.
- **1b. Acceptance-criteria evaluation** — replace the always-`manual_review`
  body of `_check_acceptance_criteria` with a per-criterion structured
  evaluation (heuristic keyword/AST matching first), emitting `criteria_status`.
  Advisory by default, promotable to `required` under `RQCA_ENFORCEMENT_ENABLED`.
- **1c. Separate integrity from correctness** — add a `correctness_verification`
  block distinct from the sha256/ECDSA `verification` block so `VERIFIED` no
  longer implies "runs."

Exit: new unit tests; a Pong-style mission shows the format gate flagging
`.js`-vs-HTML.

## Phase 2: Runnable smoke and honest engine reporting

- **2a. Runnable-artifact verifier** — reuse the existing `rqca_agent.py` /
  `RQCA_*` plumbing to sandbox-load web/script artifacts (headless browser for
  HTML; `node --check` / import for scripts) and assert no fatal errors plus a
  basic acceptance signal. Advisory by default, required under enforcement. This
  same harness lets the Phase 13 UI-smoke and provider-fallback proofs be
  automated.
- **2b. Authoritative lifecycle-engine field** — add `lifecycle_engine: str` to
  the mission record / API response from `get_lifecycle_engine(settings)`; have
  the UI consume it directly and keep client inference only as a fallback. Fix
  the chat-intake create path so it stamps the same routing metadata as the
  standard create path (the omission is why the badge mis-derived).

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
