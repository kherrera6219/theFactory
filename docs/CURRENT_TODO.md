# Current TODO

Document version: 2026.06.18-c
Last updated: 2026-06-18
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

This is the active TODO list for theFactory. Superseded sprint plans and
historical backlogs live under `docs/archive/` and should not be treated as
current work.

---

## Highest Priority — PM/LLM Workflow (2026-06-18)

The PM agent + mission pipeline was producing canned 1 KB stubs. Routing, vault
keys, the Gemini payload, and the cross-provider cascade were fixed
(`4fdab0a`, `44f557f`, `b6d0848`, `664a5cd`); the **final gate was a gateway
internal-proxy `timeout=4.0` that killed the ~9–19 s Gemini PM call** and returned
`502 "orchestrator unavailable"`. Fixed by making `_proxy_post_internal` accept a
per-call timeout and passing `90.0` for the PM route.

The next failure was in the Mission Control chat/launch handoff, not the LLM:
the chat preview could build a useful PM contract, but mission launch rebuilt the
intake prompt from compact transcript text capped at 1200 characters per message.
A live Iron Meridian test mission (`mission-c228332b-4f4e-4941-8e52-eb7494627045`)
entered `CLARIFYING` because the prompt reached mission intake truncated at
`Defeat c`. Recent fixes:

- `525b930` (`improve-pm-chat-context`) sends compact conversation context,
  decision memory, working contract, attachment labels, and finalize intent into
  the PM feature-contract route; it also fixes operations callers to satisfy the
  gateway's `ge=50` limits.
- `37f0779` (`fix-pm-mission-launch-context`) makes mission launch send full
  user-authored brief/history text with a larger cap and passes
  `conversation_context` plus `user_intent` through mission metadata into
  mission-flow v2 intake.
- `edb7846` (`fix-pm-chat-proceed-launch`) attempts to treat typed proceed-style
  replies, including `procced` and `procede`, as launch confirmation when a
  Feature Contract already exists instead of sending another PM/preview request.
  This was validated by TypeScript/build checks, but the operator reported the
  live retest still did not work, so the browser-side launch action remains the
  next active investigation item.

Current state: code is committed and pushed to `origin/main`; Docker images and
the Next.js production build were rebuilt successfully during validation. After
the `edb7846` retest failed, the operator stopped the app and the local Next.js
production output plus Docker images (`orchestrator`, `api-gateway`,
`mission-control`) were rebuilt again without starting the stack. The old Iron
Meridian mission remains paused in `CLARIFYING` from the pre-fix truncated prompt
and is not expected to auto-prove the fix.

Remaining:

1. ~~**Confirm the happy path.**~~ ✅ **DONE (2026-06-17).** `POST
   /v1/pm/feature-contract` returns `HTTP 200` in 9–19 s with `source: llm`,
   `model_provider: gemini`, `model: gemini-3.5-flash`, `degraded: None` — a real,
   prompt-specific feature contract, verified across three prompts against the
   rebuilt gateway.
1a. **Fix and verify chat launch from an existing Feature Contract.** A live
   Playwright probe on 2026-06-18 proved the rebuilt app can create a mission
   record, but also exposed the real remaining launch bug: the PM preview can
   return `intake_status: needs_clarification` while the UI still exposes a
   launchable Feature Contract, and **Confirm and Start** persisted
   `user_intent: draft`. Mission-flow v2 then correctly paused the fresh mission
   in `CLARIFYING` with `last_ambiguity_score=1.0`. The active fix now gates
   launch when PM asks clarifying questions, persists/restores structured chat
   contracts, compacts mission-launch context, forces `user_intent:
   finalize_plan` on explicit launch, and surfaces FastAPI 422 validation arrays
   instead of "Request failed with status 422." Rebuild/restart Mission Control
   and retest both **Confirm and Start** and typed proceed-style confirmation.
1b. **UI report reconciliation before retest.** The 2026-06-18 Mission Control
   report was reviewed against current code. Confirmed fixes now include
   shell-rendered global 404, compatibility aliases for `/history`,
   `/logic-nodes`, and `/repo-import`, clearer header action text (`View
   Missions`), and more useful chat history rows with preview/timestamp. Several
   report items were stale against current code: canonical nav routes, database
   status colors, notification badge, project empty/loading states, and audit
   skeleton loading were already implemented or no longer matched the code.
1c. **Run a fresh full mission after launch works.** Submit a new PM chat mission
   with a long brief and verify the mission does not pause only because of prompt
   truncation. Required proof before EDCP-02+: one full **end-to-end mission to
   COMPLETE** with non-empty generated code/artifacts, not just the PM intake call.
2. **Surface degraded/fallback mode in the UI (review finding #1).** Backend now
   emits `degraded=True` / `source:"fallback"` on the contract; add a Mission
   Control banner (chat + feature-contract panel) so the operator can see when the
   LLM didn't run instead of getting a stub that looks real. Highest UX leverage.
3. **Provider preflight / "Test key" (finding #2).** Make the Settings "Configure"
   action do a real 1-token call to the selected model and report the actual API
   status, so a bad model/key/payload is caught at config time, not mission time.
4. **App-driven provider + model selection (finding #4).** Provider and model
   currently come from `.env` (`LLM_PROVIDER`) + hardcoded profiles, not the
   Settings vault. Plumb the Settings selection through `metadata.vault` →
   `current_vault_secrets` so the packaged Windows app needs no `.env`. (Keys
   already flow; provider/model do not.)
5. **Wire per-agent vault keys.** The vault stores 41 `AGENT-NN-…-API-KEY` slots,
   but the mission proxy only reads a single `GEMINI-API-KEY` slot. Decide whether
   per-agent keys should drive per-agent calls, or collapse to one provider key.
6. **Review the other agents' workflows** (CEO, pod managers, specialists, audit,
   delivery) — same delegation path; verify each produces real output once #1 is green.
7. **Rotate the exposed Gemini key** (`AQ.Ab8RN6L...`) — pasted in chat + in logs.
8. **Optional hardening:** scope the circuit breaker per-(provider,agent) so one
   agent's failures don't blanket-disable a provider for all 41.
9. ~~**Operations `422` (status-bar mislabel).**~~ ✅ **DONE (2026-06-17).**
   Mission Control had polled
   `/v1/operations/agents?mission_limit=0&assignment_limit=0&event_limit=0`, but the
   gateway enforces `ge=50` on those params → `422` → the healthy runtime was shown
   as "Runtime Shell" / offline. The UI now sends the minimum accepted limits.
10. **UI fallback preview `422`.** The chat page's `createBuilderPreview` fallback
    returns `422` even though a direct `POST /v1/builder/preview` returns `200` —
    body/validation mismatch in the `/api/gateway` proxy path. Low urgency now that
    the PM primary path works, but a latent contract bug.

---

## Highest Priority

> **All 4 audit HIGH items from 2026-06-13 are resolved (see CHANGELOG).**

### Immediate operational steps (2026-06-16)

0a. **Rebuild and restart to lock in local fixes.** Three local commits are not
    yet reflected in the running stack: `f726de4` (PM `assumptions` persistence),
    `04e4fef` (standalone-UI gateway proxy 503 / portless `MISSION_API_BASE_URL`
    fix + proxy default → `127.0.0.1`), and `d743d4e` (redact Redis password from
    api-gateway `/health`). After stopping the app, rebuild the `orchestrator`,
    `api-gateway`, and `mission-control` images and relaunch the standalone UI
    via the fixed `start_app.bat` so all three are baked in.

0b. **Push the three local commits to `origin/main`** once the rebuild verifies
    clean. They are currently local-only.

### Recently resolved (2026-06-16)

- Standalone UI "Runtime offline / databases not connected" — root cause was a
  portless `MISSION_API_BASE_URL` produced by cmd parse-time expansion in
  `start_app.bat`; the backend and all data systems (Postgres, Redis, Qdrant,
  Milvus, Neo4j, object storage, Jaeger) were verified healthy via the live
  operations summary. Fixed in `04e4fef`.
- PM feature-contract `assumptions` field now persisted through the normalizer
  and deterministic fallback (`f726de4`).
- api-gateway `/health` no longer leaks the Redis password (`d743d4e`).

---

## Previously Highest Priority (from 2026-06-13 batch 1)

5. **Confirm post-hardening CI is fully green**
   - Check the GitHub Actions run triggered by commit `867d3ec`.
   - Expected production-critical gates on `main`: lint/test, Docker Build
     Validation, SBOM, Electron E2E Smoke, Performance Smoke, Release Trust,
     CodeQL, and security checks.

6. **Run the Gemini live mission proof**
   - Start the local stack with a real `GEMINI_API_KEY` and `KNOWLEDGE_EMBEDDING_PROVIDER=gemini`.
   - Confirm Mission Control starts unlocked and `KNOWLEDGE-EMBEDDING-API-KEY`
     is saved/tested before submitting the mission. The internal service key is
     stack configuration, not a user-facing vault setup step.
   - Submit a BUILD_NEW mission.
   - Capture evidence that the mission reaches COMPLETE with non-empty
     LLM-generated output from `gemini-3.5-flash` and that semantic search
     in the knowledge lake is operational (check Qdrant for indexed vectors).
   - Store evidence under `docs/evidence/` and update
     `docs/IMPLEMENTATION_STATUS.md`.

7. **Execute EDCP load-bearing handoff work after live mission proof**
   - Use `docs/EDCP_Phase_Plan.md` as the phase plan for converting the current
     direct-call mission pipeline into an event-driven control plane.
   - EDCP-01 foundation is complete: bus consumer-group mode, missing
     Omega/Beta/Delta sender helpers, and the disabled-by-default control-plane
     flag are in place.
   - Do not start EDCP-02 until the Gemini live mission proof above produces a
     COMPLETE mission with non-empty generated code.

8. **Confirm production host controls**
   - Enforce branch protection and required status checks in GitHub settings.
   - Confirm secret scanning and push protection are enabled.
   - Confirm release attestation verification is required for release promotion.

---

## Release Readiness Follow-Ups

9. **Produce target-environment DR evidence**
   - Run backup/restore and disaster-recovery checks in the target deployment
     environment.
   - Do not rely on local-only DR evidence for partner-facing claims.

10. **Legal and policy approval**
   - Review `docs/PRIVACY_POLICY.md` and `docs/TERMS_OF_SERVICE.md`.
   - Get approval before external publication or partner distribution.

11. **Long-duration reliability requalification**
    - Re-run the reliability qualification against the current Gemini-first
      baseline and hardened CI policy.
    - Archive the old baseline only after replacement evidence is captured.

---

## Product Validation Backlog

12. **PORT differentiator demo**
    - Run a PORT mission on a real open-source Windows game or utility.
    - Capture output targeting Linux/macOS and evidence the two-phase PORT path.
    - Validate that `extraction_degraded=True` is surfaced in RQCA when AIM
      extraction fails (new flag added 2026-06-13).

13. **Agent scaling live validation**
    - Run a multi-file repo mission with `AGENT_SCALING_ENABLED=true`.
    - Validate partition splitting, execution, and result merge.

14. **Partner-facing proof package**
    - Assemble the current docs index, CI run, SBOM, Release Trust output, live
      Gemini mission evidence, and DR evidence into a concise review package.

---

## Known Non-Issues (do not re-investigate)

- `test_agent_base_unit.py` import error — requires `services/orchestrator` on
  `sys.path`. Not broken; run from the service directory.
- OTel/Jaeger `Failed to export span batch` during tests — Jaeger not running locally.
  Harmless; exporter drops spans on shutdown.
- `docs/archive/2026-06-13/` contains superseded planning docs. Historical only.
