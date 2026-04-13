# Release Completion Plan

Document version: 2026.04.12
Last updated: 2026-04-12
Status: Canonical
Audience: Maintainers, technical leads, release owners, and auditors

This is the canonical completion plan for theFactory. Use it to sequence the remaining work required to move from a strong internal baseline to a first production-ready release.

This plan tracks phase completion through evidence files in `docs/evidence/phase40_*` through `docs/evidence/phase45_*` and release gate automation in `scripts/release_readiness_check.py`.

## Repo-Local Execution Status

As of 2026-04-12, all repo-local implementation work for Phases 1 through 7 has been completed and evidenced. `python scripts/release_readiness_check.py` reports 6/6 gates READY. Test suite: **992 passed, 5 skipped**.

Remaining release blockers are out-of-band and still require human or infrastructure action:

- scrub previously committed key material from git history and rotate any affected secrets or certificates
- enforce repository and organization settings for branch protection, secret scanning, and release attestation verification
- complete production infrastructure rollout, backup retention operations, and DR evidence in the target environment
- approve legal and policy documents before external publication

## Completion Definition

TheFactory is complete for a first serious production release only when all of the following are true:

- Mission lifecycle completion semantics are backed by a real build/package artifact pipeline.
- Mission Control reflects live backend readiness, adapters, and artifact state accurately.
- Security posture is fail-closed by default, with rotated secrets, scrubbed git history, and signed release provenance.
- Shared mutable state required for operations is stored durably and supports horizontal scaling.
- AI safety controls, prompt governance, and evaluation gates are implemented across all LLM paths.
- Backup/restore, disaster recovery, and incident response are tested and evidenced rather than documented only.
- Release gating includes backend tests, frontend tests, E2E coverage, contract checks, security scans, and AI evals.

## Standards Basis

The phases below are grounded in the following current standards and official guidance:

- NIST SP 800-218 (SSDF): integrate secure development practices into the SDLC and reduce released vulnerabilities.
- NIST AI RMF 1.0 and NIST AI 600-1 (Generative AI Profile): govern, map, measure, and manage AI-specific risk throughout design, development, deployment, and evaluation.
- NIST AI RMF Playbook: operational actions for the Govern / Map / Measure / Manage functions.
- NIST SP 800-61 Rev. 3: incident response recommendations and community-profile alignment for CSF 2.0.
- NIST SP 800-34 Rev. 1: contingency planning, business impact analysis, and recovery planning.
- OWASP ASVS: verification baseline for web application technical controls.
- OWASP Top 10 for LLM Applications: prompt injection, insecure output handling, excessive agency, and other LLM-specific risks.
- CISA Secure by Design: eliminate insecure defaults, take ownership of customer security outcomes, and favor secure defaults over opt-in hardening.
- NCSC secure AI system development guidance: secure deployment, secure operation, input/output monitoring, secure updates, and versioned model/prompt changes.
- GitHub artifact attestations and SLSA build guidance: signed build provenance, SBOM attestations, and reusable trusted build workflows.
- OpenTelemetry semantic conventions: consistent attributes for traces, metrics, logs, and error telemetry.
- PostgreSQL PITR guidance and Redis persistence guidance: tested backup/restore and recovery strategy.
- WCAG 2.2: accessibility baseline for Mission Control.
- OpenAPI 3.1: stable, versioned API contracts.

## Delivery Rules

- Every phase must land as a small number of reviewable PRs with clear exit criteria.
- Every phase must end with a debug/error sweep before the next phase starts.
- Every phase must add or update documentation in the same change set as the implementation.
- Every phase must produce evidence under `docs/evidence/` or `docs/runbooks/` where applicable.
- Do not reintroduce permissive defaults, hidden feature semantics, or undocumented operator behavior.

## Mandatory Post-Phase Debug/Error Sweep

Run this sweep after every phase and do not mark the phase complete until the sweep is green or a variance is documented.

### Core sweep

```bash
python -m pytest -q
python -m pytest --cov=services --cov-report=term-missing --cov-report=xml --cov-fail-under=80
```

### Frontend sweep

```bash
cd apps/mission-control
npm run lint
npm test
```

If the phase touches operator flows, also run:

```bash
npm run test:e2e
```

### Runtime/config sweep

```bash
docker compose -f deploy/docker-compose.yaml config -q
ruff check services tests scripts
```

### Manual sweep checklist

- Verify no new secrets, tokens, or private keys were introduced into tracked files.
- Verify health/readiness endpoints still behave correctly for touched services.
- Verify logs include enough context to diagnose the new code path.
- Verify updated docs match the live behavior, names, flags, and API contracts.

### Required evidence

For every completed phase, add:

- one phase summary under `docs/evidence/`
- one checklist of commands run and pass/fail status
- any new or updated runbook links

## Phase 1 - Supply Chain Integrity and Secret Hygiene

### Objective

Remove the remaining release blockers in supply-chain trust, secret handling, and repository hygiene.

### Standards mapped

- NIST SP 800-218
- CISA Secure by Design
- GitHub artifact attestations
- SLSA build provenance guidance
- NCSC secure build and deployment pipeline guidance

### Build this into the application

- Purge previously committed TLS private keys from git history and rotate any affected local/dev material.
- Move all runtime secrets to environment or secret-manager injection with no fallback secrets in tracked config.
- Require signed build provenance and SBOM attestations for release artifacts and container images.
- Pin and verify critical GitHub Actions and release workflows.
- Enforce branch protections for release branches with required CI, security, and attestation checks.
- Add a release verification command path that validates attestations before promotion.

### Code and config areas

- `.github/workflows/*`
- `deploy/docker-compose*.yaml`
- `.env.example`
- release/build scripts
- `docs/RELEASE_TRUST_PROMOTION_GATE.md`
- `SECURITY.md`

### Exit criteria

- No private keys or live secret material remain in git history.
- All release artifacts have signed provenance and SBOM attestations.
- Release promotion fails closed when provenance or required checks are missing.
- Secret scanning is required in CI and branch protection.

### Debug/error sweep focus

- run the mandatory post-phase sweep
- verify attestation generation and offline verification for at least one build artifact
- run targeted auth and config regression tests
- verify release workflow permissions are minimal and explicit

### Documentation updates

- `SECURITY.md`
- `README.md`
- `docs/RELEASE_TRUST_PROMOTION_GATE.md`
- `docs/COMPOSE_ENVIRONMENT_PROFILES.md`
- `docs/evidence/phase40_supply_chain_and_secret_hygiene.md`

## Phase 2 - Real Build and Package Artifact Pipeline

### Objective

Make mission completion mean a real build/package result exists, not just that orchestration reached a terminal state.

### Standards mapped

- NIST SP 800-218
- CISA Secure by Design
- OpenAPI 3.1
- GitHub artifact attestations

### Build this into the application

- Define a canonical artifact contract: artifact type, storage location, digest, build logs, status, and verification metadata.
- Add a real builder/package execution path for supported mission types.
- Persist artifact metadata durably and expose it through API Gateway, Orchestrator, and Mission Control.
- Reintroduce bundle-ready semantics only when a verified artifact exists.
- Distinguish clearly between source review, plan generation, execution, build, verification, and packaging outcomes.

### Code and config areas

- `services/orchestrator/orchestrator/main.py`
- `services/orchestrator/orchestrator/runtime.py`
- `services/orchestrator/orchestrator/object_store.py`
- Mission Control mission detail and builder/repo review flows
- API contracts under `docs/openapi/`

### Exit criteria

- A build-capable mission can produce a stored artifact with digest and retrieval metadata.
- Terminal mission states reflect whether an artifact exists, failed, or was not applicable.
- API and UI display artifact status and evidence consistently.

### Debug/error sweep focus

- run the mandatory post-phase sweep
- add integration tests for create mission -> build -> verify -> artifact retrieval
- add negative tests for build failure, partial artifact failure, and missing artifact metadata
- verify event timeline and audit report semantics still match the stored outcome

### Documentation updates

- `docs/IMPLEMENTATION_STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/API_INTEGRATION_GUIDE.md`
- `docs/api/README.md`
- `docs/user/GETTING_STARTED.md`
- `docs/evidence/phase41_build_and_package_artifact_pipeline.md`

## Phase 3 - Shared State, API Contract Convergence, and Scale Readiness

### Objective

Remove local-state bottlenecks and make the control plane safe to scale horizontally.

### Standards mapped

- OWASP ASVS
- OWASP API Security Top 10
- NCSC HTTP API security guidance
- OpenAPI 3.1
- OpenTelemetry semantic conventions

### Build this into the application

- Move `.runtime/review-approvals` and similar operational receipts to PostgreSQL or object storage.
- Normalize error envelopes and status-code behavior across gateway and orchestrator routes.
- Ensure rate limiting, pagination, validation, and auth behavior are consistent on public and internal APIs.
- Add correlation IDs and standard error metadata to every request path.
- Lock OpenAPI exports to tested behavior and use contract tests to prevent drift.

### Code and config areas

- `services/api-gateway/api_gateway/main.py`
- `services/orchestrator/orchestrator/main.py`
- storage and approval receipt paths
- `docs/openapi/*`
- frontend API client and error handling

### Exit criteria

- No release-critical mutable state depends on local filesystem writes.
- Public and internal routes return consistent shaped errors.
- Contract tests fail on undocumented API changes.
- Horizontal scale no longer depends on sticky local state.

### Debug/error sweep focus

- run the mandatory post-phase sweep
- add concurrency and retry tests around approval persistence and mission updates
- add API contract checks against exported OpenAPI
- verify correlation IDs appear in logs for gateway and orchestrator paths

### Documentation updates

- `docs/ARCHITECTURE.md`
- `docs/api/README.md`
- `docs/API_INTEGRATION_GUIDE.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/evidence/phase42_shared_state_and_api_convergence.md`

## Phase 4 - AI Safety, Prompt Governance, and Evaluation Gates

### Objective

Make AI behavior governable, testable, and safe enough for release gating.

### Standards mapped

- NIST AI RMF 1.0
- NIST AI 600-1
- NIST AI RMF Playbook
- OWASP Top 10 for LLM Applications
- NCSC secure AI deployment and operation guidance

### Build this into the application

- Externalize high-risk prompts into versioned prompt assets with owner, change history, and rollback support.
- Add a centralized safety layer for prompt injection defense, outbound secret/PII checks, unsafe tool-call blocking, and high-risk action gating.
- Add explicit classification for which mission content may be sent to third-party LLM providers.
- Instrument all LLM calls with model, prompt version, latency, token counts, retry behavior, and cost metadata.
- Expand evals into a real regression gate: prompt injection, insecure output handling, tool misuse, hallucination containment, and mission-completion accuracy.
- Require preview/versioning behavior for major model or prompt changes.

### Code and config areas

- `services/orchestrator/orchestrator/llm_delegation.py`
- prompt construction across orchestrator and Mission Control review flows
- AI evals under `tests/eval/`
- privacy and model governance docs

### Exit criteria

- All LLM entry and exit paths pass through shared policy enforcement.
- Prompt assets are versioned and auditable.
- AI evals block regressions for safety-critical and mission-critical cases.
- Operator-facing docs explain model behavior, data forwarding, and rollback policy.

### Debug/error sweep focus

- run the mandatory post-phase sweep
- add red-team tests for prompt injection, insecure output handling, and excessive agency
- add PII-detection and sensitive-data-forwarding tests
- verify logs and traces retain enough context without leaking payload secrets

### Documentation updates

- `docs/MODEL_PROMOTION_GOVERNANCE.md`
- `docs/PRIVACY_POLICY.md`
- `docs/DATA_CLASSIFICATION_POLICY.md`
- new AI safety/eval runbook if introduced
- `docs/evidence/phase43_ai_safety_prompt_governance_eval_gates.md`

## Phase 5 - Infrastructure as Code, Backup/Restore, and Incident Readiness

### Objective

Turn the current local-first deployment posture into a repeatable, recoverable production foundation.

### Standards mapped

- NIST SP 800-34 Rev. 1
- NIST SP 800-61 Rev. 3
- OpenTelemetry semantic conventions
- PostgreSQL PITR guidance
- Redis persistence guidance
- CISA Secure by Design

### Build this into the application

- Add production-grade IaC for the target hosting model with environment separation.
- Define RTO and RPO for PostgreSQL, Redis, and release artifacts.
- Implement tested PostgreSQL backup + PITR and Redis persistence/restore policy.
- Add scheduled restore drills and capture evidence.
- Complete incident runbooks for service outages, data corruption, AI misuse, and dependency compromise.
- Ensure alerting and dashboards cover gateway, orchestrator, workers, queue depth, DB health, and AI-provider failures.

### Code and config areas

- deployment/IaC assets
- backup and restore scripts
- monitoring configs
- `docs/runbooks/*`
- `docs/DEPLOYMENT_DR_PLAYBOOK.md`
- `docs/OBSERVABILITY_STACK.md`

### Exit criteria

- Production environments are reproducible from versioned IaC.
- Backup and restore are tested, evidenced, and owned.
- RTO and RPO are documented and proven by drill evidence.
- Critical alerts map to named runbooks and owners.

### Debug/error sweep focus

- run the mandatory post-phase sweep
- execute at least one PostgreSQL restore drill and one Redis recovery drill
- verify alert generation for forced dependency failures
- verify readiness and health endpoints degrade predictably under partial failure

### Documentation updates

- `docs/DEPLOYMENT_DR_PLAYBOOK.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/OBSERVABILITY_STACK.md`
- `docs/runbooks/*`
- `docs/evidence/phase44_infrastructure_backup_restore_incident_readiness.md`

## Phase 6 - Mission Control Convergence and Final Release Qualification

### Objective

Finish the operator experience, close documentation drift, and enforce final release gates.

### Standards mapped

- WCAG 2.2
- Playwright E2E best practices
- OpenAPI 3.1
- OWASP ASVS
- NIST SSDF verification expectations

### Build this into the application

- Align all Mission Control surfaces with real backend states, adapters, artifacts, and failures.
- Remove or replace any remaining placeholder copy, stale labels, or dead operator paths.
- Expand E2E coverage to include builder review, repo review, artifact visibility, adapter readiness, and failure recovery.
- Add accessibility regression checks for key flows and reduce hardcoded styling drift.
- Reconcile all current-source docs so product, API, security, and runbook docs describe the same system.

### Code and config areas

- `apps/mission-control/app/**`
- `apps/mission-control/e2e/**`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/DOCUMENTATION_INDEX.md`
- current-source README and API docs

### Exit criteria

- Mission Control reflects the live product accurately.
- Critical operator journeys are covered by E2E tests.
- Current-source docs contain no known state drift.
- Accessibility and release gates are part of normal CI.

### Debug/error sweep focus

- run the mandatory post-phase sweep
- run Lighthouse/a11y checks for the high-traffic views
- verify error, empty, loading, and recovery states in the UI
- re-run full release checklist with a clean environment

### Documentation updates

- `README.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/DOCUMENTATION_INDEX.md`
- `docs/user/GETTING_STARTED.md`
- `apps/mission-control/README.md`
- `docs/evidence/phase45_mission_control_convergence_and_final_release_qualification.md`

## Final Release Gate

Do not call theFactory complete until the following release gate is green in a clean environment:

- backend tests green
- services coverage gate green
- frontend lint/unit tests green
- operator E2E green
- security scans green
- artifact attestation verification green
- AI eval gate green
- backup/restore drill evidence current
- docs updated for the release candidate

## Suggested Execution Order

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 5
6. Phase 6

This order is intentional. Phase 2 depends on Phase 1 release trust. Phase 3 should happen before broad scale claims. Phase 4 should happen before exposing more AI autonomy. Phase 5 is required before production claims. Phase 6 is the final convergence and qualification phase, not the first one.
