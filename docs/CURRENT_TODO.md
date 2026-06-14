# Current TODO

Document version: 2026.06.13-b
Last updated: 2026-06-13
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

This is the active TODO list for theFactory. Superseded sprint plans and
historical backlogs live under `docs/archive/` and should not be treated as
current work.

---

## Highest Priority

> **All 4 audit HIGH items from 2026-06-13 are resolved (see CHANGELOG).** Current
> highest priority items are from the prior batch.

---

## Previously Highest Priority (from 2026-06-13 batch 1)

5. **Confirm post-hardening CI is fully green**
   - Check the GitHub Actions run triggered by commit `867d3ec`.
   - Expected production-critical gates on `main`: lint/test, Docker Build
     Validation, SBOM, Electron E2E Smoke, Performance Smoke, Release Trust,
     CodeQL, and security checks.

6. **Run the Gemini live mission proof**
   - Start the local stack with a real `GEMINI_API_KEY` and `KNOWLEDGE_EMBEDDING_PROVIDER=gemini`.
   - Submit a BUILD_NEW mission.
   - Capture evidence that the mission reaches COMPLETE with non-empty
     LLM-generated output from `gemini-3.5-flash` and that semantic search
     in the knowledge lake is operational (check Qdrant for indexed vectors).
   - Store evidence under `docs/evidence/` and update
     `docs/IMPLEMENTATION_STATUS.md`.

7. **Confirm production host controls**
   - Enforce branch protection and required status checks in GitHub settings.
   - Confirm secret scanning and push protection are enabled.
   - Confirm release attestation verification is required for release promotion.

---

## Release Readiness Follow-Ups

8. **Produce target-environment DR evidence**
   - Run backup/restore and disaster-recovery checks in the target deployment
     environment.
   - Do not rely on local-only DR evidence for partner-facing claims.

9. **Legal and policy approval**
   - Review `docs/PRIVACY_POLICY.md` and `docs/TERMS_OF_SERVICE.md`.
   - Get approval before external publication or partner distribution.

10. **Long-duration reliability requalification**
    - Re-run the reliability qualification against the current Gemini-first
      baseline and hardened CI policy.
    - Archive the old baseline only after replacement evidence is captured.

---

## Product Validation Backlog

11. **PORT differentiator demo**
    - Run a PORT mission on a real open-source Windows game or utility.
    - Capture output targeting Linux/macOS and evidence the two-phase PORT path.
    - Validate that `extraction_degraded=True` is surfaced in RQCA when AIM
      extraction fails (new flag added 2026-06-13).

12. **Agent scaling live validation**
    - Run a multi-file repo mission with `AGENT_SCALING_ENABLED=true`.
    - Validate partition splitting, execution, and result merge.

13. **Partner-facing proof package**
    - Assemble the current docs index, CI run, SBOM, Release Trust output, live
      Gemini mission evidence, and DR evidence into a concise review package.

---

## Known Non-Issues (do not re-investigate)

- `test_agent_base_unit.py` import error — requires `services/orchestrator` on
  `sys.path`. Not broken; run from the service directory.
- OTel/Jaeger `Failed to export span batch` during tests — Jaeger not running locally.
  Harmless; exporter drops spans on shutdown.
- `docs/archive/2026-06-13/` contains superseded planning docs. Historical only.
