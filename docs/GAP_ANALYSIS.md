# Gap Analysis

Last updated: 2026-03-03

## Scope

- Local design requirements: `C:\software\Holygrail` documentation set.
- External production references:
  - OWASP (Top 10, ASVS)
  - NIST (CSF, AI RMF, SSDF, incident response)
  - ISO/IEC (27001, 42001)
- Reviewed implementation: `C:\software\Holygrail\theFactory`.

## Findings and Disposition

1. `High` Missing full 8-part agent personas in runtime APIs.
   - Previous state: operations APIs exposed only runtime metadata and LLM routing.
   - Status: `Addressed`.
   - Action taken:
     - Added persona builder and payload integration for all 35 agents.
     - Added standards alignment and evidence source links per agent profile.
     - Added UI rendering and test assertions for persona completeness.

2. `Medium` Limited production-governance traceability from role definitions to external standards.
   - Previous state: standards references existed in docs, but were not tied to agent runtime records.
   - Status: `Addressed`.
   - Action taken:
     - Added `persona_profile.standards_alignment`.
     - Added `persona_profile.evidence_sources`.
     - Added integration metadata fields indicating profile framework/extensions and evidence verification date.

3. `Medium` Documentation consistency gap after rapid implementation phases.
   - Previous state: partial mismatch between architecture, roadmap, runbook, and readme detail depth.
   - Status: `Addressed in this cycle`.
   - Action taken:
     - Refreshed root README and core docs set with aligned architecture, roadmap, operations, and audit content.
     - Added `docs/DOCUMENTATION_INDEX.md` for central navigation.

4. `Medium` Deep production controls not fully enforced.
   - Status: `Addressed (baseline)`.
   - Action taken:
     - Added CI release-trust workflow controls for signed provenance attestation and fail-closed promotion policy enforcement.
     - Added tracing baseline for gateway/orchestrator with Jaeger OTLP export and pager webhook routing in Alertmanager.
     - Added long-duration reliability qualification tooling with sustained load, failure injection, readiness monitoring, and recovery verification.
     - Published baseline evidence artifact: `docs/evidence/reliability_qualification_baseline_2026-03-03.json`.

5. `Medium` Mission Control regression coverage was limited to unit tests.
   - Previous state: UI validation focused on TypeScript and Vitest unit coverage without critical-path e2e execution.
   - Status: `Addressed (baseline)`.
   - Action taken:
     - Added Playwright e2e suite for mission lifecycle, operations views, settings/vault, and error states.
     - Added CI browser provisioning and Mission Control e2e execution.
     - Added audit control `UI-011` to verify e2e gating remains configured.

6. `Medium` Builder preview and repository intake UX included placeholder/simulated behaviors.
   - Previous state: builder showed plan-only placeholder rendering and repo import used sample file simulation.
   - Status: `Addressed (baseline)`.
   - Action taken:
     - Implemented functional diff/file-impact preview rendering in Builder workspace.
     - Added real GitHub metadata/tree import API with input validation, tokenized access, truncation/large-file handling, and error mapping.
     - Added unit and e2e regression coverage for both pathways.

7. `Medium` Backup and disaster-recovery scripts lacked direct automated regression tests.
   - Previous state: perf/audit script checks existed, but backup/DR PowerShell flows were untested in automation.
   - Status: `Addressed (baseline)`.
   - Action taken:
     - Added `-DryRun` execution path and integrity checks to backup/DR scripts.
     - Added PowerShell regression tests in `tests/scripts/test_backup_dr_scripts.py`.

8. `Low` Legacy roadmap and Mission Control runtime-port assumptions were not explicitly reconciled in canonical docs.
   - Previous state: legacy artifacts implied single-port or advanced-scope commitments without canonical disposition mapping.
   - Status: `Addressed (baseline)`.
   - Action taken:
     - Added canonical reconciliation note with adopted/deferred/deprecated legacy scope mapping.
     - Documented explicit Mission Control port policy for Docker-host and direct-dev modes.

## Structural Gaps Still Open (Planned)

- Real-dependency integration tests:
  - Expand mission-flow tests that exercise live Redis/Postgres/service wiring instead of mock-heavy paths.
- Data-systems reconciliation:
  - Activate Qdrant retrieval paths and finalize Neo4j/object-storage scope decision with updated canonical docs.
