# theFactory Master Audit Report
Date: 2026-03-29
Auditor role: Senior Principal Engineer / AI Architect / DevOps Lead

## Codebase Profile
- Project name and purpose: `theFactory`, a local-first multi-service AI orchestration platform with a Mission Control UI, an API gateway, an orchestrator, pod workers, an audit worker, and an MCP server for semantic-bus operations.
- Tech stack summary:
  - Backend: Python 3.11, FastAPI, Uvicorn, Redis, PostgreSQL, Qdrant, optional Neo4j/MinIO/Milvus, Prometheus, OpenTelemetry.
  - Frontend: Next.js 16, React 19, TypeScript, Vitest, Playwright, Lighthouse CI.
  - AI: OpenAI, Anthropic, Gemini integration points; offline deterministic provider path; 38-agent orchestrator registry; semantic-bus MCP server.
  - Ops: Docker multi-stage builds, Docker Compose for dev/staging/prod/monitoring, GitHub Actions CI/security/qualification workflows.
- Estimated codebase size:
  - Tracked files: 591
  - Approximate active source/docs/config lines scanned: ~101k
- AI/agent components present: Yes
  - `services/orchestrator/orchestrator/agent_registry.py`
  - `services/orchestrator/orchestrator/agent_personas.py`
  - `services/orchestrator/orchestrator/mission_flow_v2.py`
  - `services/orchestrator/orchestrator/llm_delegation.py`
  - `services/semantic-bus-mcp/semantic_bus/mcp_server.py`
  - `tests/eval/*`
- Current test coverage posture:
  - Python coverage thresholds configured in `pyproject.toml`
  - Frontend unit tests present with Vitest
  - One Playwright E2E suite present
  - Load test scaffold present (`tests/load/locustfile.py`)
  - Coverage is meaningful on core backend services but not broad enough across all UI journeys and API contracts
- Current documentation completeness: ~72%
- Top 3 visible risk areas before deep audit:
  - Committed private keys in `deploy/postgres/certs/server.key` and `deploy/redis/certs/redis.key`
  - Historical documentation drift around 35-agent vs 38-agent runtime and current UI surface names
  - Internal-service auth and compose security defaults were previously permissive or fallback-based

## Suite Summary

### Suite 1 — Debug & Error Sweep
- Fixed:
  - Fail-closed internal-service auth in API gateway instead of forwarding blank internal bearer keys.
  - Removed shell-based command execution from `scripts/reliability_qualification.py`.
  - Added URL scheme validation to Neo4j and Qdrant fetch paths before `urlopen(...)`.
  - Hardened API gateway upstream error handling to avoid leaking raw exception text.
  - Added warning logs for semantic-bus MCP Redis initialization and health-check failures.
- Residual:
  - The repo working tree now deletes tracked TLS cert/key material, but git history cleanup is still required.
  - Some logs still lack stable request/user context outside HTTP middleware.

### Suite 2 — Frontend, UI/UX & Design Audit
- Fixed:
  - Removed dead “Start from Template” CTA in Mission Control projects screen and replaced it with explicit non-availability copy.
  - Added focus restoration, focus trapping, and click-away dismissal to the keyboard shortcuts dialog.
  - Fixed Mission Control fetch timeout cleanup to avoid orphaned abort timers.
- Residual:
  - Styling still depends on a mix of design tokens and hardcoded values in `app/globals.css`.
  - Automated responsive/a11y coverage is still thin for multi-page flows.

### Suite 3 — Backend, API & Data Layer Audit
- Fixed:
  - API gateway mutation forwarding now fails closed when internal auth is not configured.
  - Upstream 429 handling added to LLM delegation retry flow.
  - Additional unsafe raw exception detail leak removed from mission state proxying.
  - API gateway CORS was narrowed from wildcard methods/headers to an explicit browser surface.
- Residual:
  - Some persistence still relies on local filesystem receipts (`.runtime/review-approvals`), which limits horizontal scaling.
  - Error envelopes are not fully uniform across all routes.

### Suite 4 — DevOps, CI/CD, Containers & DR Audit
- Fixed:
  - Removed insecure default compose fallbacks for internal service/API keys in `deploy/docker-compose.yaml`.
  - Removed insecure default worker-key fallbacks from `deploy/docker-compose.full-dedicated-agents.yaml`.
  - Replaced tracked TLS cert delivery with local-only cert bootstrap under `deploy/.local` via `scripts/generate_dev_tls_certs.ps1` and `scripts/generate_dev_tls_certs.sh`.
- Residual:
  - Git history still contains the previously committed TLS private keys and must be cleaned outside the working tree.
  - No production-grade IaC stack is present.
  - DR posture is documented only partially; backup testing and RTO/RPO evidence are not present.

### Suite 5 — AI Agents, Tools, Skills, Sub-Agents & MCP Audit
- Fixed:
  - LLM delegation now retries 429 responses and honors `Retry-After`.
  - MCP Redis init/health failures are now observable in logs.
- Residual:
  - Prompt assets are still largely inline in route and orchestration code instead of versioned prompt files.
  - No centralized moderation or PII redaction layer is visible on all LLM ingress/egress paths.
  - Agent safety/eval coverage exists but is not broad enough to qualify as a comprehensive regression harness.

### Suite 6 — Documentation Audit
- Fixed:
  - Added `.github/CODEOWNERS`.
  - Added `CODE_OF_CONDUCT.md`.
  - Added `docs/user/GETTING_STARTED.md`.
  - Added `docs/api/README.md`.
  - Added `docs/TERMS_OF_SERVICE.md`.
  - Added `docs/ACCESSIBILITY_STATEMENT.md`.
  - Updated `docs/DOCUMENTATION_INDEX.md`.
  - Reconciled key top-level docs and UI metadata from 35-agent to 38-agent where they serve as current source-of-truth.
- Residual:
  - Many historical planning and evidence docs still refer to a 35-agent runtime, but they are now explicitly marked as historical where they are not current-source docs.
  - DPA, cookie policy, and a formal incident-response policy are still absent.

### Suite 7 — Testing Audit
- Fixed:
  - Added regression tests for API gateway auth mode fail-closed behavior.
  - Added unit tests for URL validation in Qdrant and Neo4j stores.
  - Added regression test for shell-safe reliability qualification command execution.
  - Added LLM delegation retry tests for 429 and retry exhaustion.
  - Added frontend unit test for timeout cleanup.
- Residual:
  - E2E coverage is still narrow relative to the product surface.
  - Contract-testing coverage is limited.
  - AI eval coverage exists but is not complete enough for prompt and orchestration regression gating.

## Codebase Health Scorecard

### Suite 1 — Debug & Error Sweep
- Runtime & Logic Errors: 7/10
- Async & Concurrency: 7/10
- Security Posture: 5/10
- Observability: 6/10

### Suite 2 — Frontend & UI/UX
- User Journey Quality: 6/10
- UX Pattern Consistency: 6/10
- Visual Design: 7/10
- Accessibility: 7/10
- Responsive Design: 6/10

### Suite 3 — Backend & API
- API Design: 7/10
- Auth & Authorization: 6/10
- Data Layer: 7/10
- Reliability & Resilience: 7/10

### Suite 4 — DevOps & Infrastructure
- Container & Deployment: 7/10
- CI/CD Pipeline: 8/10
- Security Hardening: 7/10
- Disaster Recovery: 4/10

### Suite 5 — AI & Agent Systems
- LLM Integration: 7/10
- Agent Architecture: 7/10
- Tool & Skill Quality: 7/10
- Sub-Agent Orchestration: 6/10
- AI Safety & Guardrails: 5/10

### Suite 6 — Documentation
- GitHub Repo Docs: 8/10
- API Documentation: 7/10
- User Documentation: 7/10
- Compliance Docs: 6/10

### Suite 7 — Testing
- Unit Test Coverage: 7/10
- Integration Tests: 7/10
- E2E Tests: 5/10
- Security Tests: 7/10
- AI Eval Suite: 5/10

### Overall Codebase Health Score
- Overall: 7.0/10

## Master Issue Log

| Suite | Phase | File / Component | Severity | Issue | Fixed |
| --- | --- | --- | --- | --- | --- |
| 1 / 4 | Security sweep | `deploy/postgres/certs/server.key` | CRITICAL | Private key was committed to repo; working tree now deletes tracked cert material and uses local-only generation under `deploy/.local`, but git history cleanup is still required | Partial |
| 1 / 4 | Security sweep | `deploy/redis/certs/redis.key` | CRITICAL | Private key was committed to repo; working tree now deletes tracked cert material and uses local-only generation under `deploy/.local`, but git history cleanup is still required | Partial |
| 4 / 5 | Secret audit | `deploy/docker-compose.yaml` | CRITICAL | Insecure fallback internal/API keys in compose | Y |
| 4 / 5 | Secret audit | `deploy/docker-compose.full-dedicated-agents.yaml` | CRITICAL | Insecure fallback worker keys in dedicated-agent compose | Y |
| 3 / 2 | Auth audit | `services/api-gateway/api_gateway/main.py` | CRITICAL | Internal mutation forwarding succeeded with blank internal key path instead of fail-closed behavior | Y |
| 1 / 4 | Security sweep | `scripts/reliability_qualification.py` | HIGH | `shell=True` command execution allowed command injection risk | Y |
| 1 / 4 | Security sweep | `services/orchestrator/orchestrator/qdrant_store.py` | HIGH | Unvalidated URL passed to `urlopen(...)` | Y |
| 1 / 4 | Security sweep | `services/orchestrator/orchestrator/neo4j_store.py` | HIGH | Unvalidated URL passed to `urlopen(...)` | Y |
| 3 / 5 | Error resilience | `services/api-gateway/api_gateway/main.py` | HIGH | Raw upstream exception detail leaked to clients on mission state mutation | Y |
| 5 / 1 | LLM integration | `services/orchestrator/orchestrator/llm_delegation.py` | HIGH | 429 rate-limit responses were not retried or delayed using `Retry-After` | Y |
| 2 / 3 | UX pattern audit | `apps/mission-control/app/components/keyboard-shortcuts.tsx` | HIGH | Dialog lacked focus trap and focus restoration | Y |
| 6 / 1 | Repo docs audit | `.github/CODEOWNERS` | HIGH | CODEOWNERS missing; reviewer routing undefined | Y |
| 6 / 9 | Doc consistency | `docs/**`, `apps/mission-control/README.md` | HIGH | Stale 35-agent terminology remains across many documents | Partial |
| 4 / 7 | DR audit | `docs/runbooks`, deployment posture | HIGH | No verified backup/restore evidence or explicit RTO/RPO proof | N |
| 5 / 8 | AI safety audit | AI ingress/egress paths | HIGH | No visible centralized moderation/PII-redaction layer across all LLM flows | N |
| 7 / 4 | E2E audit | `apps/mission-control/e2e/mission-control.spec.ts` | HIGH | E2E coverage too narrow for major user journeys | N |
| 7 / 8 | AI eval audit | `tests/eval/*` | HIGH | Eval coverage present but insufficient for prompt/orchestration regression gating | N |
| 1 / 6 | Observability audit | `services/semantic-bus-mcp/semantic_bus/mcp_server.py` | MEDIUM | Broad exception handling dropped Redis failures without logs | Y |
| 2 / 2 | Journey audit | `apps/mission-control/app/(shell)/projects/page.tsx` | MEDIUM | Dead CTA created false affordance | Y |
| 2 / 6 | Accessibility audit | `apps/mission-control/app/lib/api-client.ts` | MEDIUM | Timeout controller cleanup missing after request resolution | Y |
| 3 / 7 | Config audit | `services/api-gateway/api_gateway/main.py` | MEDIUM | CORS allowed wildcard methods and headers | Y |
| 3 / 4 | Scalability audit | `.runtime/review-approvals` | MEDIUM | Review approval receipts stored on local disk, limiting horizontal scale | N |
| 6 / 8 | Compliance docs audit | repo root / `docs/` | MEDIUM | Privacy Policy existed, but Terms and accessibility docs were missing | Y |
| 2 / 4 | Visual audit | `apps/mission-control/app/globals.css` | MEDIUM | Design tokens coexist with hardcoded presentation values | N |
| 7 / 5 | Contract test audit | API boundary coverage | MEDIUM | No broad consumer-driven contract suite | N |
| 6 / 1 | Repo docs audit | `CODE_OF_CONDUCT.md` | MEDIUM | Code of conduct missing | Y |
| 6 / 6 | User docs audit | `docs/user/GETTING_STARTED.md` | MEDIUM | End-user getting-started guide missing | Y |
| 6 / 3 | API docs audit | `docs/api/README.md` | MEDIUM | API documentation index missing | Y |

## Critical Findings Summary
- Security exposures:
  - Two private TLS keys existed in tracked paths; the working tree now deletes those files and switches to local-only cert generation, but git history cleanup is still required.
  - Example credentials in `.env.example` and compose were replaced with explicit `CHANGE_ME_...` placeholders.
- Agent safety gaps:
  - No single cross-cutting moderation and PII-redaction layer is evident for all LLM entry/exit paths.
  - Prompt assets are still mostly inline, which makes governance, versioning, and safety review harder.
- Data integrity risks:
  - Some operational receipts are still written to local disk instead of durable shared storage.
- Auth bypass vulnerabilities:
  - API gateway internal forwarding used to rely on permissive fallback behavior; this was fixed to fail closed.
- Production stability threats:
  - DR evidence is incomplete.
  - E2E and eval coverage are not strong enough to catch all cross-service and AI-flow regressions before release.

## Master Changelog

| Suite | File | What changed | Why |
| --- | --- | --- | --- |
| 1 / 3 | `services/api-gateway/api_gateway/main.py` | Added fail-closed internal auth helper and sanitized upstream error responses | Prevent blank-key forwarding and exception detail leaks |
| 1 / 4 | `scripts/reliability_qualification.py` | Replaced `shell=True` execution with safe argv parsing | Remove command injection path |
| 1 / 4 | `services/orchestrator/orchestrator/qdrant_store.py` | Added HTTP/HTTPS URL validation before `urlopen(...)` | Prevent unsafe scheme fetches |
| 1 / 4 | `services/orchestrator/orchestrator/neo4j_store.py` | Added HTTP/HTTPS URL validation before `urlopen(...)` | Prevent unsafe scheme fetches |
| 1 / 6 | `services/semantic-bus-mcp/semantic_bus/mcp_server.py` | Added warning logs around Redis init and health failures | Surface previously silent failures |
| 2 / 2 | `apps/mission-control/app/(shell)/projects/page.tsx` | Removed dead template CTA and replaced with explicit muted copy | Eliminate false affordance |
| 2 / 6 | `apps/mission-control/app/components/keyboard-shortcuts.tsx` | Added focus trap, focus restoration, click-away dismissal, and labelled dialog title | Fix keyboard accessibility gap |
| 2 / 3 | `apps/mission-control/app/lib/api-client.ts` | Added timeout cleanup lifecycle and configurable timeouts | Prevent timer leaks on resolved requests |
| 2 / 3 | `apps/mission-control/app/lib/api-client.test.ts` | Added timeout cleanup regression test | Lock in fix |
| 3 / 7 | `services/api-gateway/api_gateway/main.py` | Replaced wildcard CORS methods/headers with an explicit browser surface and exposed response headers | Reduce unnecessary cross-origin surface area |
| 3 / 5 | `services/orchestrator/orchestrator/llm_delegation.py` | Added 429 retry handling using `Retry-After` | Harden LLM provider resilience |
| 4 / 5 | `deploy/docker-compose.yaml` | Removed insecure default API/service-key fallbacks | Prevent accidental insecure deployments |
| 4 / 5 | `deploy/docker-compose.full-dedicated-agents.yaml` | Removed insecure default worker-key fallbacks | Prevent accidental insecure deployments |
| 4 / 5 | `deploy/postgres/certs/*`, `deploy/redis/certs/*`, `.gitignore`, `scripts/generate_dev_tls_certs.ps1`, `scripts/generate_dev_tls_certs.sh`, `Makefile` | Removed tracked TLS cert delivery from the active working tree and introduced local-only cert bootstrap under `deploy/.local` | Stop carrying live private keys in source while keeping local setup workable |
| 6 / 1 | `CODE_OF_CONDUCT.md` | Added repo-level code of conduct | Close repo governance gap |
| 6 / 1 | `.github/CODEOWNERS` | Added reviewer ownership routing to the repository owner | Close repo governance gap |
| 6 / 3 | `docs/api/README.md` | Added API docs entry point | Improve discoverability |
| 6 / 6 | `docs/user/GETTING_STARTED.md` | Added user getting-started guide | Close user-doc gap |
| 6 / 8 | `docs/TERMS_OF_SERVICE.md`, `docs/ACCESSIBILITY_STATEMENT.md` | Added missing policy/accessibility docs | Reduce compliance-doc gaps |
| 6 / 9 | `README.md`, `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_STATUS.md`, `apps/mission-control/app/layout.tsx`, `.env.example`, `docs/DOCUMENTATION_INDEX.md` | Reconciled key current docs and metadata to 38-agent runtime and current UI | Remove high-traffic documentation drift |
| 7 / 2 | `tests/services/test_api_gateway_auth_mode_unit.py` | Added fail-closed auth regression coverage | Verify API gateway hardening |
| 7 / 2 | `tests/services/test_qdrant_store_unit.py` | Added invalid URL rejection test | Verify URL validation |
| 7 / 2 | `tests/services/test_neo4j_store_unit.py` | Added invalid URL rejection test | Verify URL validation |
| 7 / 2 | `tests/scripts/test_reliability_qualification.py` | Added shell-safe command execution test | Verify command hardening |
| 7 / 8 | `tests/services/test_llm_delegation_retry_unit.py` | Added 429 retry and retry-exhaustion tests | Verify LLM resilience logic |
| 7 / 1 | `requirements-dev.txt`, `scripts/check_coverage_thresholds.py` | Added `defusedxml` and switched XML parser | Harden coverage report parsing path |

## Infrastructure Requirements

### Secret Rotation and Repo Hygiene
- Remove committed private keys from the repository history, not just the working tree.
- Rotate any certificate material derived from the committed keys.
- Add secret scanning as a required status check before merge if it is not already branch-protected.

### Deployment and Runtime Security
- Provision real `INTERNAL_SERVICE_API_KEY`, `SERVICE_API_KEY`, `ORCHESTRATOR_API_KEYS`, and `MCP_API_KEY` values per environment through a secret manager.
- Move review-approval receipts and similar mutable operational state from local disk to a shared durable store.

### Disaster Recovery
- Define and document:
  - Backup schedule and retention
  - Restore test cadence
  - RTO and RPO targets
  - Named DR runbook owner
- Produce at least one tested restore artifact for PostgreSQL and Redis.

### AI Governance
- Externalize high-risk prompts into versioned prompt assets with changelog and owner metadata.
- Add centralized moderation / PII-redaction enforcement for LLM ingress and egress.
- Expand eval gating to cover prompt regressions, tool selection accuracy, and safety-policy regressions.

### Repo Governance
- Add legal/compliance docs requiring human/legal review before publication.

## Generated Artifacts Inventory
- New docs:
  - `.github/CODEOWNERS`
  - `CODE_OF_CONDUCT.md`
  - `docs/ACCESSIBILITY_STATEMENT.md`
  - `docs/TERMS_OF_SERVICE.md`
  - `docs/api/README.md`
  - `docs/user/GETTING_STARTED.md`
  - `reports/master_audit_2026-03-29.md`
- New scripts:
  - `scripts/generate_dev_tls_certs.ps1`
  - `scripts/generate_dev_tls_certs.sh`
- New tests:
  - `tests/services/test_llm_delegation_retry_unit.py`
- Updated code/config:
  - `services/api-gateway/api_gateway/main.py`
  - `services/orchestrator/orchestrator/qdrant_store.py`
  - `services/orchestrator/orchestrator/neo4j_store.py`
  - `services/orchestrator/orchestrator/llm_delegation.py`
  - `services/semantic-bus-mcp/semantic_bus/mcp_server.py`
  - `scripts/reliability_qualification.py`
  - `scripts/check_coverage_thresholds.py`
  - `deploy/docker-compose.yaml`
  - `deploy/docker-compose.full-dedicated-agents.yaml`
  - `apps/mission-control/app/lib/api-client.ts`
  - `apps/mission-control/app/lib/api-client.test.ts`
  - `apps/mission-control/app/components/keyboard-shortcuts.tsx`
  - `apps/mission-control/app/(shell)/projects/page.tsx`
  - `README.md`
  - `docs/ARCHITECTURE.md`
  - `docs/IMPLEMENTATION_STATUS.md`
  - `.env.example`
  - `docs/DOCUMENTATION_INDEX.md`

## Technical Debt Register

### High priority
- Remove repo-committed TLS private keys from git history and rotate the replaced material.
  - Effort: M
- Replace remaining 35-agent references in historical docs or archive them explicitly as historical snapshots.
  - Effort: M
- Implement centralized LLM moderation / PII-redaction controls.
  - Effort: M-L
- Expand E2E coverage for onboarding, mission launch, repo import, builder review, failure recovery, and settings/vault flows.
  - Effort: M-L
- Expand AI eval coverage for prompt regressions, tool accuracy, and safety scenarios.
  - Effort: M-L

### Medium priority
- Move local review-approval receipts to shared storage or DB.
  - Effort: M
- Normalize error response envelopes across API routes.
  - Effort: M
- Reduce hardcoded visual values in Mission Control and finish token adoption.
  - Effort: M
- Add contract tests for API boundary compatibility.
  - Effort: M
- Add compliance/legal docs after legal review.
  - Effort: M

### Low priority
- Continue trimming stale planning/evidence documentation or tag it as archival.
  - Effort: S-M
- Add more granular structured logs and correlation metadata in non-request background flows.
  - Effort: M

## Flagged for Human Review
- Architecture decisions:
  - Whether to treat older 35-agent planning docs as historical archives or rewrite them to present tense.
- Security sign-offs:
  - Key rotation, repo history rewrite, and secret scanning policy enforcement.
- Compliance and legal reviews:
  - Privacy Policy, Terms, DPA, incident response disclosure language, accessibility statement.
- Brand and design decisions:
  - Whether to invest in a deeper Mission Control design token refactor and visual cleanup.
- Infrastructure spend approvals:
  - Shared durable storage for approvals/receipts, backup tooling, and AI governance infrastructure.
- AI autonomy boundary changes:
  - Centralized moderation and PII redaction may change failure behavior and need product approval.
- Eval dataset quality judgments:
  - Prompt and safety eval datasets need human-owned ground truth.
- Production maintenance windows:
  - Key rotation and repo history cleanup may require coordinated rollout.
- Breaking API contract changes:
  - Normalizing response envelopes can affect existing clients.
- Tests revealing real bugs:
  - None of the generated tests were written to match known-bad behavior; any future failures on these cases should be treated as regressions.

## Verification Executed
- `python -m pytest -q tests/services/test_api_gateway_auth_mode_unit.py tests/services/test_qdrant_store_unit.py tests/services/test_neo4j_store_unit.py tests/scripts/test_reliability_qualification.py`
- `python -m pytest -q tests/services/test_runtime_unit.py tests/services/test_mission_flow_v2.py tests/services/test_semantic_bus_mcp.py tests/services/test_protocol_and_auth.py tests/services/test_hardened_api_keys.py`
- `python -m pytest -q tests/services/test_llm_delegation_retry_unit.py tests/eval/test_llm_delegation_golden.py`
- `python -m pytest -q tests/scripts/test_production_review_audit.py`
- `npm test` in `apps/mission-control`
- `npm run lint` in `apps/mission-control`
- `docker compose -f deploy/docker-compose.yaml config -q`
- `python -m ruff check` on touched Python files

## Final Assessment
The codebase is viable and materially better than the initial scan suggested. The core architecture is coherent, the CI/security baseline is stronger than average for an internal platform, and the targeted hardening work removed several real security and reliability defects. The remaining blockers to calling this production-hardened are now concentrated in history cleanup and operational maturity: git-history secret scrubbing, incomplete DR evidence, incomplete AI safety/eval coverage, and the remaining historical-document backlog.
