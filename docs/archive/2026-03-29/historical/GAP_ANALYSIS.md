# Gap Analysis

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Historical Archive

> Historical note (2026-03-29): This document predates the current 38-agent runtime. Treat any `35-agent` references below as historical planning terminology unless explicitly updated in a newer canonical document.

Last updated: 2026-03-26

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

6. `Medium` Builder preview and repository workflow previously included partially synthetic behavior.
   - Previous state: builder showed plan-only placeholder rendering and repo import used sample file simulation.
   - Current-cycle action:
     - repo import remains real GitHub metadata/tree ingestion,
     - repo review approval now persists through a server-side approval receipt route,
     - Builder review now inspects real local workspace files, emits a stable review fingerprint, produces a grounded patch contract plus launchable `source_code` bundle, and launches missions from that approved artifact,
     - chat intake no longer hardcodes Python and now infers `requested_target_language`.
   - Status: `Addressed in this cycle`.

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
     - changed gateway mission creation to persist through the orchestrator before returning `201 Created`,
     - added direct scaling tests for partition-event emission, partition execution, and partition-result ingestion,
     - re-ran the affected backend suites successfully.
   - Status: `Addressed in this cycle`.

10. `Medium` Mission creation previously behaved as queue-first/eventually consistent.
   - Previous state:
     - `POST /v1/missions` published intake first and record visibility depended on consumer timing,
     - immediate follow-up reads could briefly return `404`.
   - Current-cycle action:
     - gateway mission creation now synchronously persists through the orchestrator before returning,
     - Mission Control retry logic remains as a defensive fallback rather than a required contract.
   - Status: `Addressed in this cycle`.

11. `Medium` Data-system implementation is ahead of some operator-facing docs/UI surfaces.
   - Previous state: Qdrant was listed as reserved and retrieval behavior was primarily PostgreSQL-only.
   - Current observed state:
     - Qdrant readiness is wired into backend health and operations payloads,
     - Neo4j/object-storage readiness is also surfaced in orchestrator runtime payloads when enabled,
     - some Mission Control data-plane copy still presents these adapters as planned rather than active/optional.
   - Status: `Partially addressed`.
   - Required action:
     - align UI copy and architecture docs with the live readiness fields and feature-flagged posture.

12. `Medium` Language-count and routing claims diverged across documentation.
   - Previous state: docs described 16 languages and 169 patterns.
   - Current observed state:
     - specialist routing now covers 20 language keys, including Go, Haskell, and OCaml,
     - some current docs still carry older 16-key and 19-key claims,
     - the remaining gap is now primarily documentation reconciliation, not missing routing support.
   - Status: `Partially addressed`.
   - Required action:
     - normalize all canonical docs to the current routing matrix and extraction counts.

13. `Critical + High` Security baseline: hardcoded keys, unauthenticated vault, prompt injection, missing HEALTHCHECK.
   - Previous state: trivial default secrets in service settings; vault routes open to anyone; no LLM context sanitisation; Dockerfiles lacked HEALTHCHECK.
   - Status: `Addressed in this cycle`.
   - Action taken:
     - Removed all hardcoded key defaults; `CHANGE_ME_` placeholders enforced in `.env.example`.
     - Vault admin routes gated behind `x-vault-admin-key` header with RBAC check.
     - `_safe_context_json` allowlist strips `prompt`, `source_code`, `chain_trace` before LLM forwarding; hard 4 KB cap.
     - HEALTHCHECK added to all 7 service Dockerfiles.
     - `CONTRIBUTING.md` and `SECURITY.md` created.

14. `Medium` Type annotation defects: `_as_bool(raw: str)` accepted `None` at runtime but the type said otherwise; `MissionEvent.event_type` was unvalidated `str`.
   - Status: `Addressed in this cycle`.
   - Action taken:
     - `_as_bool` signature changed to `raw: str | None`.
     - `EventType` Literal (19 values) added to `models.py`; `MissionEvent.event_type` is now Pydantic-validated.

15. `Medium` LLM provider calls had no retry logic; a single transient network error or 5xx silently returned `None`.
   - Status: `Addressed in this cycle`.
   - Action taken:
     - `_post_with_retry()` helper added with exponential backoff (1s/2s/4s, 3 attempts) for all three LLM providers.

16. `Medium` Docker images were single-stage; pip and build artefacts were shipped in the production layer.
   - Status: `Addressed in this cycle`.
   - Action taken:
     - All 7 Dockerfiles converted to two-stage builds (builder installs into `/opt/venv`; runtime copies only the venv).
     - `.dockerignore` expanded with venv dirs, certs, test artefacts, and docs source.

17. `Medium` Accessibility: no skip-to-content link; `:focus-visible` styles incomplete for links and secondary buttons.
   - Status: `Addressed in this cycle`.
   - Action taken:
     - `<a href="#main-content">` skip link added to shell layout (CSS was pre-defined).
     - `:focus-visible` extended to `a`, `[role=button]`, `[tabindex]`, `.secondary-button`, `.shell-link-button`.

18. `Low` Builder review route rescanned the entire workspace on every request (no caching).
   - Status: `Addressed in this cycle`.
   - Action taken:
     - `collectFilesCached()` with 30 s module-level TTL added.

19. `Low` No GitHub issue / PR templates; privacy and compliance documentation absent.
   - Status: `Addressed in this cycle`.
   - Action taken:
     - `.github/PULL_REQUEST_TEMPLATE.md` with security and CI checklist.
     - Three issue templates: `bug_report.md`, `feature_request.md`, `security_report.md`.
     - `docs/PRIVACY_POLICY.md` with data classification, LLM forwarding scope, retention, GDPR/SOC 2 mapping.

20. `Low` AI eval suite absent; no golden dataset or prompt-regression tests for delegation routing.
   - Status: `Addressed in this cycle`.
   - Action taken:
     - `tests/eval/golden_delegation_cases.json` — 6-case golden dataset.
     - `tests/eval/test_llm_delegation_golden.py` — parametrised suite for routing, injection resilience, fallback.
     - `tests/services/test_type_annotations.py` — regression guard for `_as_bool` and `MissionEvent.event_type`.

## Structural Gaps Still Open (Planned)

- Audit/data-plane/operator-surface reconciliation.
- Language-count and extraction/routing documentation reconciliation.
- Real build/package artifact pipeline.


