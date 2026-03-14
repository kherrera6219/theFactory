# Gap Analysis

Last updated: 2026-03-13

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

3. `High` Runtime/documentation drift around mission lifecycle defaults.
   - Previous state: core docs described v1.1 as the default production runtime and v2 as a gated future path.
   - Current-cycle action:
     - added `docs/IMPLEMENTATION_STATUS.md` as the current-state source of truth,
     - aligned README, architecture, index, roadmap, completion, and ADR supersession notes to the shipped `MISSION_FLOW_V2_ENABLED=true` defaults,
     - updated lifecycle tests so LangGraph-only coverage disables v2 explicitly.
   - Status: `Addressed in this cycle`.

4. `Medium` Deep production controls not fully enforced.
   - Status: `Addressed (baseline)`.
   - Action taken:
     - Added CI release-trust workflow controls for signed provenance attestation and fail-closed promotion policy enforcement.
     - Added tracing baseline for gateway/orchestrator with Jaeger OTLP export and pager webhook routing in Alertmanager.
     - Added long-duration reliability qualification tooling with sustained load, failure injection, readiness monitoring, and recovery verification.
     - Published baseline evidence artifact: `docs/evidence/reliability_qualification_baseline_2026-03-03.json`.

5. `Medium` Mission Control regression coverage existed, but the suite had drifted from the live UI.
   - Previous state: UI validation focused on TypeScript and Vitest unit coverage without critical-path e2e execution.
   - Current-cycle action:
     - updated the stale heading assertion to match the live mission-detail page,
     - re-ran the full Playwright suite successfully.
   - Status: `Addressed in this cycle`.

6. `Medium` Builder preview and repository intake UX still include partially synthetic behavior.
   - Previous state: builder showed plan-only placeholder rendering and repo import used sample file simulation.
   - Current observed state:
     - repo import is real GitHub metadata/tree ingestion,
     - Builder diff rendering is inferred from preview-plan signals rather than a true patch/apply workflow,
     - repo review gating remains client-side state.
   - Status: `Open`.
   - Required action:
     - carry real repository context through to mission launch,
     - replace synthetic diff generation with a true server-side diff/apply contract,
     - enforce review gating server-side.

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

9. `High` Backend mission-flow regression coverage was present but had drifted from the shipped runtime contract.
   - Previous state: mission-flow tests used fake/in-memory dependencies for most backend paths.
   - Current-cycle action:
     - fixed the v2 runtime to emit `MISSION_COMPLETION_BLOCKED` consistently,
     - aligned runtime and LangGraph unit tests with the shipped v2-default behavior,
     - updated live integration polling to tolerate the queue-first create path until the orchestrator record becomes queryable,
     - re-ran the full backend suite successfully.
   - Status: `Addressed in this cycle`.

10. `Medium` Mission creation is queue-first and therefore eventually consistent.
   - Current observed state:
     - `POST /v1/missions` enqueues to Redis intake and returns before the orchestrator record is always queryable,
     - immediate follow-up reads can briefly return `404` until the intake consumer persists the mission.
   - Status: `Open`.
   - Required action:
     - either document this as the intended contract everywhere it matters,
     - or change mission creation to provide read-after-write consistency.

11. `Medium` Data-system implementation is ahead of some operator-facing docs/UI surfaces.
   - Previous state: Qdrant was listed as reserved and retrieval behavior was primarily PostgreSQL-only.
   - Current observed state:
     - Qdrant readiness is wired into backend health and operations payloads,
     - Neo4j/object-storage readiness is also surfaced in orchestrator runtime payloads when enabled,
     - some Mission Control data-plane copy still presents these adapters as planned rather than active/optional.
   - Status: `Partially addressed`.
   - Required action:
     - align UI copy and architecture docs with the live readiness fields and feature-flagged posture.

12. `Medium` Language-extraction coverage and specialist-routing claims diverged.
   - Previous state: docs described 16 languages and 169 patterns.
   - Current observed state: extractor/catalog expose 20 languages and 232 patterns, while specialist routing remains narrower.
   - Status: `Open`.
   - Required action:
     - either expand specialist coverage to match extraction scope,
     - or reduce docs and marketing claims to the subset with full routing support.

## Structural Gaps Still Open (Planned)

- Mission-create consistency contract.
- Builder and repo workflow completion.
- Audit/data-plane/operator-surface reconciliation.
- Language routing and extraction reconciliation.
