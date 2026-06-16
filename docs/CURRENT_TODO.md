# Current TODO

Document version: 2026.06.16-a
Last updated: 2026-06-16
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

This is the active TODO list for theFactory. Superseded sprint plans and
historical backlogs live under `docs/archive/` and should not be treated as
current work.

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
