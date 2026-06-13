# Current TODO

Document version: 2026.06.13
Last updated: 2026-06-13
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

This is the active TODO list for theFactory. Superseded sprint plans and
historical backlogs live under `docs/archive/` and should not be treated as
current work.

## Highest Priority

1. **Confirm post-hardening CI is fully green**
   - Check the GitHub Actions run triggered by commit `867d3ec`.
   - Expected production-critical gates on `main`: lint/test, Docker Build
     Validation, SBOM, Electron E2E Smoke, Performance Smoke, Release Trust,
     CodeQL, and security checks.
   - Any skipped production-critical job should be treated as a workflow bug
     unless it is explicitly manual or release-tag-only.

2. **Run the Gemini live mission proof**
   - Start the local stack with a real `GEMINI_API_KEY`.
   - Submit a BUILD_NEW mission.
   - Capture evidence that the mission reaches COMPLETE with non-empty
     LLM-generated output from `gemini-3.5-flash`.
   - Store evidence under `docs/evidence/` and update
     `docs/IMPLEMENTATION_STATUS.md`.

3. **Confirm production host controls**
   - Enforce branch protection and required status checks in GitHub settings.
   - Confirm secret scanning and push protection are enabled.
   - Confirm release attestation verification is required for release
     promotion.

## Release Readiness Follow-Ups

4. **Produce target-environment DR evidence**
   - Run backup/restore and disaster-recovery checks in the target deployment
     environment.
   - Do not rely on local-only DR evidence for partner-facing claims.

5. **Legal and policy approval**
   - Review `docs/PRIVACY_POLICY.md` and `docs/TERMS_OF_SERVICE.md`.
   - Get approval before external publication or partner distribution.

6. **Long-duration reliability requalification**
   - Re-run the reliability qualification against the current Gemini-first
     baseline and hardened CI policy.
   - Archive the old baseline only after replacement evidence is captured.

## Product Validation Backlog

7. **PORT differentiator demo**
   - Run a PORT mission on a real open-source Windows game or utility.
   - Capture output targeting Linux/macOS and evidence the two-phase PORT path.

8. **Agent scaling live validation**
   - Run a multi-file repo mission with `AGENT_SCALING_ENABLED=true`.
   - Validate partition splitting, execution, and result merge.

9. **Partner-facing proof package**
   - Assemble the current docs index, CI run, SBOM, Release Trust output, live
     Gemini mission evidence, and DR evidence into a concise review package.
