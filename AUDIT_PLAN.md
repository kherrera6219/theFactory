# theFactory — Production Audit Master Plan
**Repository:** [kherrera6219/theFactory](https://github.com/kherrera6219/theFactory)  
**Audit Initiated:** 2026-06-21  
**Status:** IN PROGRESS  
**Auditor:** Kevin Herrera  

---

> **Audit Doctrine:** What is documented must match what is configured must match what is wired must match what executes.  
> Code is truth. Docs are kept in sync. Stubs are not shipped. Everything is production-grade or it doesn't merge.

---

## 0. Plan Validation Against Current Application State

**Validated:** 2026-06-21
**Validation status:** APPLICABLE WITH ADJUSTMENTS
**Current repository baseline:** `main` at `5c9c768` (`focus application scope and surface PM fallback state`)

This plan remains the correct master audit framework for the application, but the
first pass must adapt several checklist assumptions to the current repo shape:

- The audit scope is application-only: Mission Control, backend services,
  shared runtime, schemas, deploy, tests, scripts, and docs.
- `sites/` is intentionally absent. The marketing site package was removed from
  the application worktree and is no longer an audit target.
- Service entrypoints are package-level ASGI targets, not always literal
  `main.py` files directly under `services/<service>/`. Validate Docker `CMD`
  targets such as `protocol_bus.mcp_server:app` in addition to `main.py`.
- Service tests are centralized under `tests/services/*.py` with a small
  `services/orchestrator/tests/` package. Do not require a `tests/` subdirectory
  inside every service unless the repo is intentionally reorganized.
- Ignored generated output folders such as `apps/mission-control/out/`,
  `apps/mission-control/output_extracted/`, and root `MagicMock/` are local build
  or runtime residue. They should be excluded from source audit findings unless
  the task is explicit disk hygiene.
- Current app status is active development, not production-ready. Audit findings
  should be framed as release-readiness blockers/warnings, not regressions from a
  shipped production product.

Initial validation evidence:

- All seven backend services have tracked Dockerfiles and requirements files.
- Six services expose package `main.py` ASGI entrypoints; `protocol-bus-mcp`
  exposes `protocol_bus.mcp_server:app` via Docker `CMD`.
- Mission Control has the expected Next.js application files and build tooling.
- `sites/` is missing by design.
- No production star imports were found; the only `from os.path import *` match is
  a test fixture string in `tests/services/test_ast_extractor.py`.

---

## Table of Contents

0. [Plan Validation Against Current Application State](#0-plan-validation-against-current-application-state)
1. [Audit Goals & Scope](#1-audit-goals--scope)
2. [Severity Classification](#2-severity-classification)
3. [Phase 1 — Structural Integrity](#3-phase-1--structural-integrity)
4. [Phase 2 — Naming Conventions & Repo Layout](#4-phase-2--naming-conventions--repo-layout)
5. [Phase 3 — Configuration & Dependency Wiring](#5-phase-3--configuration--dependency-wiring)
6. [Phase 4 — Backend Service Audit](#6-phase-4--backend-service-audit)
7. [Phase 5 — Agent & Orchestrator Wiring](#7-phase-5--agent--orchestrator-wiring)
8. [Phase 6 — Frontend Audit (Mission Control)](#8-phase-6--frontend-audit-mission-control)
9. [Phase 7 — Shared Runtime Audit](#9-phase-7--shared-runtime-audit)
10. [Phase 8 — Test Coverage & Quality Gates](#10-phase-8--test-coverage--quality-gates)
11. [Phase 9 — Security Audit](#11-phase-9--security-audit)
12. [Phase 10 — Error Handling Standards](#12-phase-10--error-handling-standards)
13. [Phase 11 — Duplicate Code & Dead Code Elimination](#13-phase-11--duplicate-code--dead-code-elimination)
14. [Phase 12 — Documentation Drift](#14-phase-12--documentation-drift)
15. [Phase 13 — End-to-End Smoke Test](#15-phase-13--end-to-end-smoke-test)
16. [Findings Tracker](#16-findings-tracker)
17. [Definition of Done — Audit Complete](#17-definition-of-done--audit-complete)

---

## 1. Audit Goals & Scope

### Primary Objectives

- **Fix everything found** — no open finding closes without a merged fix or a documented, approved deferral
- **Eliminate duplicate systems** — no two modules should own the same responsibility
- **Validate end-to-end wiring** — every declared component connects to something real
- **Zero stubs in production paths** — `pass`, `TODO`, `raise NotImplementedError`, and `...` bodies in non-abstract classes are blockers
- **Production-grade standard** — error handling, logging, retries, circuit breakers, input validation, and observability on every service boundary
- **Security at every layer** — secrets hygiene, auth enforcement, input sanitization, replay protection
- **Test coverage that reflects real behavior** — integration tests for event-driven paths, not just mocked unit tests
- **Frontend/backend contract alignment** — UI reflects real backend behavior; no hardcoded states or phantom data
- **Standards compliance** — PEP 8/Ruff (Python), strict TypeScript, Next.js App Router conventions, OWASP for all web surfaces

### In Scope

| Layer | Scope |
|---|---|
| `services/orchestrator` | Full audit — highest criticality |
| `services/api-gateway` | Full audit — auth, routing, error handling |
| `services/pod-worker` | Full audit — extraction engine, agent wiring |
| `services/audit-worker` | Full audit — completeness of audit trail |
| `services/protocol-bus-mcp` | Full audit — event routing, stream naming, replay detection |
| `services/dashboard` | Full audit — wiring to real backend data |
| `apps/mission-control` | Full audit — TypeScript strictness, API contract alignment, e2e coverage |
| `shared_runtime/` | Full audit — every module used by all services must be bulletproof |
| `schemas/` | Full audit — schema consumers validated, orphans removed |
| `config/` | Full audit — fail-fast validation, no silent defaults |
| `tests/` | Full audit — coverage gaps, fixture realism, integration vs. unit ratio |
| `scripts/` | Full audit — operational tooling completeness |
| `deploy/` | Full audit — Docker compose correctness, secret injection paths |
| `docs/` | Drift audit — docs must match current code state |

---

## 2. Severity Classification

Every finding is assigned one of three severities. **No finding is closed without a fix or explicit deferral.**

| Severity | Symbol | Criteria | Merge Policy |
|---|---|---|---|
| **Blocker** | 🔴 | System won't function correctly; stubs in production paths; security hole; data loss risk | Must fix before any other work proceeds on that component |
| **Warning** | 🟡 | Works today but will fail under load, edge cases, or partial failures; missing error handling on non-critical paths | Fix within current sprint |
| **Improvement** | 🟢 | Code quality, naming, DRY violations, missing tests for secondary paths, doc drift | Fix within two sprints; tracked in backlog |

---

## 3. Phase 1 — Structural Integrity

**Goal:** Verify the repo skeleton matches what is claimed in AGENTS.md, README.md, and the codebase itself.

### Checklist

- [ ] **Directory contract** — every directory in `AGENTS.md` Repository Structure section exists on disk
- [ ] **Service completeness** — each service in `services/` has:
  `Dockerfile`, `requirements.txt`, and a runnable ASGI entrypoint. Accept
  package-level targets such as `protocol_bus.mcp_server:app`. Tests may live in
  centralized `tests/services/*.py` files instead of per-service `tests/`
  directories.
- [ ] **App completeness** — `apps/mission-control` has: `package.json`, `tsconfig.json`, `next.config.*`, `app/` directory, `playwright.config.*`, and test directories
- [ ] **Schema consumers** — every file in `schemas/` is imported by at least one module; orphaned schemas are removed or documented
- [ ] **Protocol directory** — `protocol/` contents are referenced in code; not a documentation artifact
- [ ] **Ledger directory** — `ledger/` has a writer and a reader; verify both exist and are called
- [ ] **`shared_runtime` imports** — every module in `shared_runtime/` is imported by at least one service; unused modules are either justified or removed
- [x] **`examples/` validity** — static JSON examples are covered by
  `tests/test_examples_schema.py`, which validates LogicNode and RIR examples
  against the canonical schemas.
- [x] **`sites/` contents** — `sites/` is intentionally absent after the
  2026-06-21 application-only cleanup. Do not reintroduce marketing-site scope
  into the application audit.
- [ ] **`conftest.py`** — fixtures map to real runtime conditions; no all-mock fixtures masking real integration needs
- [ ] **`start_app.bat` / `stop_app.bat`** — tested on clean environment; all referenced services start successfully; no silent failures

### Files to Inspect

- `AGENTS.md` — ground truth for architecture claims
- `README.md` — verify all referenced paths and commands work
- `Makefile` — verify every target executes successfully
- `deploy/` — verify all compose services resolve

---

## 4. Phase 2 — Naming Conventions & Repo Layout

**Goal:** Enforce consistent naming across the entire codebase. Inconsistency is a maintenance tax and a source of import errors.

### Python Naming Standards

| Element | Convention | Example |
|---|---|---|
| Files/modules | `snake_case` | `mission_flow_v2.py` |
| Classes | `PascalCase` | `MissionFlowV2Engine` |
| Functions/methods | `snake_case` | `emit_state_event()` |
| Constants | `SCREAMING_SNAKE_CASE` | `MISSION_FLOW_V2_ENABLED` |
| Private members | `_snake_case` prefix | `_write_intake_dlq()` |
| Abstract methods | `snake_case` with `raise NotImplementedError` only in ABC | — |

### TypeScript/React Naming Standards

| Element | Convention | Example |
|---|---|---|
| Components | `PascalCase` | `MissionCard.tsx` |
| Hooks | `camelCase` with `use` prefix | `useMissionStatus.ts` |
| Route handlers | App Router file conventions | `route.ts`, `page.tsx`, `layout.tsx` |
| Utility functions | `camelCase` | `formatTimestamp()` |
| Types/interfaces | `PascalCase` | `MissionPayload`, `AgentStatus` |
| Enums | `PascalCase` | `LifecyclePhase` |
| Constants | `SCREAMING_SNAKE_CASE` | `MAX_RETRY_COUNT` |

### Repo Layout Standards

- [ ] **Services use kebab-case** — `api-gateway`, `pod-worker`, `protocol-bus-mcp` ✅ (already correct)
- [ ] **Python package dirs match service names** — `services/orchestrator/orchestrator/`, `services/api-gateway/api_gateway/` (verify internal package name uses underscores)
- [ ] **No mixed case in directory names** — scan tracked source directories for
  any CamelCase or UPPERCASE directory names. Exclude ignored generated/runtime
  output such as `MagicMock/` and Mission Control static export folders unless
  performing local disk hygiene.
- [ ] **Test mirror structure** — `tests/services/` mirrors `services/`; every service has a corresponding test subdirectory
- [ ] **No `utils.py` catch-alls** — if a `utils.py` exists, audit its contents and split into named modules
- [ ] **No `helpers.py` catch-alls** — same rule
- [ ] **`__init__.py` exports** — every package `__init__.py` explicitly declares its public API; no silent star imports

### Audit Actions

- Run: `find . -name "*.py" | xargs grep -l "^from .* import \*"` — flag all star imports
- Run: `find . -type d | grep -E "[A-Z]"` — flag any CamelCase or UPPERCASE directories
- Run: `find . -name "utils.py" -o -name "helpers.py"` — review each for catch-all patterns

---

## 5. Phase 3 — Configuration & Dependency Wiring

**Goal:** Every config key has a consumer; every consumer has a declared key. Dependencies are pinned and conflict-free.

### `.env.example` Audit

- [ ] **Key coverage forward** — every key in `.env.example` (14KB, comprehensive) has at least one `os.getenv()` or `settings.*` call in the codebase
- [ ] **Key coverage reverse** — every `os.getenv()` and `settings.*` reference in the codebase has a corresponding entry in `.env.example`
- [ ] **Required vs. optional documentation** — each key in `.env.example` is marked as required or optional with a comment
- [ ] **No default secrets** — no key ships with a real API key, token, or password as the example value
- [ ] **Type coercion documented** — boolean flags (`true`/`false` strings) and integer values are documented with expected types

### Settings Validation

- [ ] **`settings.py` fail-fast** — `services/orchestrator/orchestrator/settings.py` uses validators that raise at startup for missing required values, not at runtime when the key is first accessed
- [ ] **No `or None` silent defaults on required fields** — `os.getenv("REQUIRED_KEY") or None` should be `os.getenv("REQUIRED_KEY")` with a validator that raises on None
- [ ] **Pydantic Settings model** — verify settings use `pydantic-settings` `BaseSettings` with field validators; not raw `os.getenv` scattered across files
- [ ] **Per-service settings isolation** — each service defines its own `Settings` class; no cross-service settings imports

### Dependency Audit

- [ ] **`pyproject.toml` vs per-service `requirements.txt`** — reconcile: which is the source of truth for each service?
- [ ] **All dependencies pinned** — no unpinned `package>=x.y` in production requirements; use `==` for prod, `>=` only in dev
- [ ] **`pip check`** — run in each service venv; zero conflicts required
- [ ] **`requirements-dev.txt` separation** — dev tools (pytest, ruff, mypy) are not in production requirements
- [ ] **Optional deps marked** — LangGraph, esprima, javalang are optional; their absence must not crash startup when their feature flags are disabled
- [ ] **Docker layer caching** — each Dockerfile's `COPY requirements.txt` precedes `COPY .` to enable layer caching

### Config Directory

- [ ] **Every config file has a loader** — files in `config/` are read by a specific module; not just documentation
- [ ] **Config is validated at load time** — not lazily validated when first accessed in a request handler
- [ ] **Config changes don't require code changes** — runtime behavior should be adjustable via env vars without touching source files

---

## 6. Phase 4 — Backend Service Audit

**Goal:** Every service is production-complete: real implementation, no stubs, proper error handling, health endpoints, and metrics.

### Per-Service Audit Checklist (apply to each)

Services: `api-gateway` · `orchestrator` · `pod-worker` · `audit-worker` · `protocol-bus-mcp` · `dashboard`

#### Completeness

- [ ] No `pass` or `...` bodies in non-abstract production classes
- [ ] No `# TODO` or `# FIXME` in any path that executes during normal operation
- [ ] No `raise NotImplementedError` outside of ABC/abstract base definitions
- [ ] All route handlers return documented response models, not raw dicts
- [ ] All async functions are properly `await`ed; no fire-and-forget without error handling

#### API Design

- [ ] All routes have explicit HTTP status codes — no `200` returned on error conditions
- [ ] All request bodies are validated via Pydantic models before processing
- [ ] All response bodies use Pydantic response models with `response_model=` in FastAPI routes
- [ ] Pagination implemented for all list endpoints (`limit`, `offset` or cursor-based)
- [ ] OpenAPI spec is accurate and generated from live code (`make validate` runs `openapi` export)

#### Error Handling

- [ ] Every external I/O call (Redis, PostgreSQL, Qdrant, LLM APIs) is wrapped in try/except with typed exceptions from `shared_runtime/errors.py`
- [ ] No bare `except Exception as e: pass` — all exceptions are logged and either re-raised or returned as error responses
- [ ] Circuit breakers implemented on LLM provider calls — a provider outage does not cascade to service failure
- [ ] Retry logic with exponential backoff on transient failures (Redis disconnects, DB timeouts)
- [ ] Timeout enforcement on all LLM API calls — no indefinite hangs

#### Health & Observability

- [ ] `/health` endpoint returns `{"status": "ok"}` with 200 only when all critical dependencies are reachable
- [ ] `/ready` endpoint (separate from `/health`) confirms service is ready to accept traffic
- [ ] `/metrics` endpoint exposes Prometheus-compatible metrics
- [ ] Structured logging (JSON) on all services — every log entry includes `service`, `trace_id`, `mission_id` where applicable
- [ ] `tracing.py` is wired to all services — not just orchestrator
- [ ] Log levels are configurable via env var; default `INFO` in prod, `DEBUG` in dev

#### `services/orchestrator` Specific

- [ ] `main.py` — audit for any inline business logic that should be in a dedicated module
- [ ] `mission_flow_v2.py` (~3004 lines) — **critical**: audit for unreachable branches, dead phase transitions, missing error recovery between phases
- [ ] `mission_flow_v2/` directory vs `mission_flow_v2.py` file — confirm there is no naming collision or import ambiguity between these two
- [ ] `mission_flow.py` (legacy v1 shim) — confirm it is truly a shim only; no business logic that isn't also in v2
- [ ] `storage.py` (façade) — verify all domain storage modules are re-exported correctly with no gaps
- [ ] `storage_*.py` modules — each domain module (agents, artifacts, core, logicnodes, missions, pods) has a clear boundary; no cross-domain direct calls bypassing the façade
- [ ] `agent_base.py` — audit for methods that are stubs in the base but have no concrete override in subclasses
- [ ] `agent_personas.py` — the unified `AgentPersona` dataclass is used consistently; no parallel dict patterns remain
- [ ] `langgraph_lifecycle.py` — confirm it is fully isolated behind `LANGGRAPH_ENABLED` flag; disabled by default and its absence does not affect v2 engine
- [ ] `milvus_store.py` vs `qdrant_store.py` vs `neo4j_store.py` — **duplicate detection**: are all three vector/graph stores actively used or is one superseded?
- [ ] `dependency_absorption.py` — audit for completeness; all 20 language keys handled
- [ ] `knowledge_lake.py` vs `knowledge_embeddings.py` — verify clean separation: lake = storage/retrieval, embeddings = vector computation; no overlap
- [ ] `llm_cost_ledger.py` — confirm writes to `ledger/`; confirm reads exist somewhere for reporting
- [ ] `object_store.py` — confirm it is not a duplicate of S3/MinIO functionality already in another module

#### `services/api-gateway` Specific

- [ ] Auth mode `AUTH_MODE` hard-fails on invalid value; verify in code
- [ ] Rate limiting is enforced per-key, not globally
- [ ] All routes require API key validation before reaching handlers
- [ ] CORS policy is explicit and restrictive; `*` is not permitted in production
- [ ] Request/response logging does not log sensitive headers or body fields containing secrets

#### `services/pod-worker` Specific

- [ ] `GoAgent`, `HaskellAgent`, `OcamlAgent` are concrete subclasses; verify no `BaseAgent` fallback remains
- [ ] All 4 pod families (A/B/C/D) have complete language routing with no `language not found` silent fallback
- [ ] AST extractors (Python, JS/TS, Java) — feature flags respected; fallback to regex is logged, not silent
- [ ] Extractors have fixture comparison tests (old vs. new output) for every supported language
- [ ] Workspace creation is atomic; partial workspace creation is impossible
- [ ] Workspace cleanup runs even on task failure (use `try/finally`)

#### `services/protocol-bus-mcp` Specific

- [ ] All 6 Redis protocol streams (α, β, δ, σ, ω, ρ) are declared and consumed
- [ ] Replay detection returns 409 on duplicate message IDs; verify test coverage
- [ ] Redis failures return 503 — not silent pass-through
- [ ] Stream naming is consistent across all producers and consumers
- [ ] Dead Letter Queue (DLQ) is implemented on all streams, not just intake

#### `services/audit-worker` Specific

- [ ] Every agent action that should produce an audit event does produce one
- [ ] Audit events are immutable after write — no update/delete paths
- [ ] Audit worker failure does not block mission execution (async, non-blocking write)
- [ ] Audit trail is queryable by mission ID, agent ID, and timestamp range

---

## 7. Phase 5 — Agent & Orchestrator Wiring

**Goal:** Every agent in the 41-agent registry is accounted for, reachable, and correctly routed.

### Agent Registry Audit (`agent_registry.py`)

- [ ] **41-agent inventory** — export the full registry; for each agent confirm: `runtime_class`, `pod_assignment`, `language_keys`, and whether it is a real process or synthesized heartbeat
- [ ] **No ghost agents** — every agent in the registry either has a concrete implementation class OR is explicitly documented as `synthesized_heartbeat`
- [ ] **No orphaned implementations** — every `*Agent` class defined in the codebase is registered in `agent_registry.py`
- [ ] **`AgentPersona` consistency** — every registered agent has a corresponding `AgentPersona` dataclass entry with no field gaps

### Smelt Cycle Wiring (INTAKE → FETCH → SMELT → GATING → FUSION → SQUEEZE → DELIVERY)

- [ ] Each phase has a discrete handler function — no phase logic inlined in the orchestrator loop
- [ ] Phase transitions are guarded — a mission cannot skip a phase without explicit gating logic
- [ ] Phase failures are recoverable — `lifecycle_recovery.py` is invoked on phase failure, not just on total mission failure
- [ ] Phase state is persisted to storage before transitioning — crash recovery can resume from any phase

### MissionFlowV2 Phases (11-phase state machine)

- [ ] All 11 phases are implemented (no stub phases)
- [ ] Phase entry/exit emits `emit_state_event()` — observable from dashboard
- [ ] `mission_flow_v2/` subdirectory modules (if any) are all imported by `mission_flow_v2.py` — no orphaned phase files
- [ ] Intelligence items are fully wired through `mission_flow_v2.py` as documented in AGENTS.md

### Event Bus Completeness

- [ ] **Publisher inventory** — list every `xadd` / Redis publish call; each has a documented stream and schema
- [ ] **Subscriber inventory** — list every `xread` / Redis subscribe call; each has a named handler
- [ ] **Dead events** — every published event type has at least one subscriber; events published into the void are blockers
- [ ] **Schema enforcement** — `jsonschema.validate()` is called on every message before publishing; verify coverage

### LangGraph Engine (Experimental Path)

- [ ] Confirm `LANGGRAPH_ENABLED=false` is the default
- [ ] Confirm the LangGraph path does not share mutable state with the MissionFlowV2 path
- [ ] Confirm graceful degradation: if `langgraph` pip package is absent, the flag being `true` logs a warning and falls back cleanly

---

## 8. Phase 6 — Frontend Audit (Mission Control)

**Goal:** The Next.js UI reflects actual backend behavior, has zero `any` types, full test coverage, and is production-deployable.

### TypeScript & Code Quality

- [ ] `tsc --noEmit` passes with zero errors in strict mode
- [ ] Zero `any` types in application code — OpenAPI-generated types enforced; verify no regressions
- [ ] Zero `// @ts-ignore` or `// @ts-expect-error` without a documented reason
- [ ] ESLint passes with zero errors
- [ ] All API call sites use the generated OpenAPI client — no manual `fetch` with hardcoded endpoints
- [ ] All async operations have error boundaries — no unhandled promise rejections

### App Router Conventions

- [ ] All pages follow `app/` directory conventions: `page.tsx`, `layout.tsx`, `loading.tsx`, `error.tsx`
- [ ] Every route that has an async data fetch has a corresponding `loading.tsx` skeleton
- [ ] Every route has an `error.tsx` with a user-friendly error state and retry action
- [ ] No `pages/` directory remnants (legacy Next.js routing)

### API Contract Alignment

- [ ] Every API call in the frontend maps to a real, documented backend endpoint
- [ ] No hardcoded mock data in production components — only in test fixtures
- [ ] No hardcoded status strings — all status values come from shared enums/types
- [ ] WebSocket / SSE connections for live mission status have reconnection logic
- [ ] Vault endpoints (`/api/vault`, `/api/vault/test`) are tested and not exposing keys to the client

### Component & State Quality

- [ ] No component is fetching data and also managing complex local state — separate data-fetching from presentation
- [ ] All forms use controlled components with validation before submission
- [ ] Empty states are designed for every data-loading component (not blank divs)
- [ ] Error states are designed for every API call component
- [ ] Loading skeletons match the shape of the real loaded content

### Testing

- [ ] All Vitest unit tests pass: `make test-ui`
- [ ] All Playwright e2e tests pass: `make test-ui-e2e`
- [ ] Coverage threshold met for UI unit tests
- [ ] E2e tests cover the primary happy path: submit mission → observe phases → view output
- [ ] E2e tests cover failure scenarios: backend unavailable, invalid mission input

---

## 9. Phase 7 — Shared Runtime Audit

**Goal:** `shared_runtime/` is the foundation trusted by all services. Every module must be bulletproof.

### Module-by-Module Review

| Module | Audit Focus |
|---|---|
| `agent_auth.py` | Token generation/validation is cryptographically sound; no hardcoded secrets |
| `agent_keys.py` | Key rotation is possible without service restart; key derivation is deterministic and documented |
| `atomic_io.py` | File operations use OS-level atomic write patterns (`tempfile` + `rename`); no partial writes possible |
| `crypto_keystore.py` | Keys are stored encrypted at rest; memory is cleared after use (`del key`) |
| `crypto_signing.py` | Signing algorithm is documented; verification is tested with known vectors |
| `errors.py` | All custom exception classes have meaningful messages; no bare `Exception` subclasses |
| `logging_config.py` | JSON structured logging; no PII in log output; log levels configurable |
| `pii_guard.py` | PII detection covers all field types declared in the system; tested against real payloads |
| `prompt_guard.py` | Injection detection patterns are up to date; test coverage includes adversarial inputs |
| `protocol.py` | Envelope schema matches `schemas/`; no divergence between runtime and schema files |

### Cross-Service Contract

- [ ] `shared_runtime` is imported as a package, not copied per-service
- [ ] Any change to `shared_runtime` requires all services to be re-tested before deploy
- [ ] `shared_runtime/__init__.py` exports only the public API — internal modules are not exposed

---

## 10. Phase 8 — Test Coverage & Quality Gates

**Goal:** Coverage numbers reflect real behavior coverage, not line-hit theater.

### Coverage Policy Enforcement

- [ ] Global backend coverage: `>= 80%`
- [ ] Per-module floors enforced via `scripts/check_coverage_thresholds.py`
- [ ] `mission_flow_v2.py`: `>= 90%` line + `>= 85%` branch (critical path)
- [ ] `runtime.py`: `>= 80%` (verify no regression from current 100% line / 99% branch)
- [ ] `storage_*.py` modules: `>= 80%` each
- [ ] `shared_runtime/` modules: `>= 85%` each (foundation layer)
- [ ] `api-gateway/`: `>= 80%` including auth paths

### Test Quality Checks

- [ ] **No test passes by asserting on mock return values it set up itself** — tests must assert on observable side effects
- [ ] **Integration tests for every event bus path** — fire real Redis message, assert real handler state change
- [ ] **Fixture realism** — `tests/fixtures/` payloads match current schema versions; stale fixtures are blockers
- [ ] **No `time.sleep()` in tests** — use event-driven assertions with timeouts (`pytest-timeout`)
- [ ] **Deterministic test ordering** — `pytest-randomly` is enabled but tests do not depend on order
- [ ] **No skipped tests without a GitHub issue reference** — `@pytest.mark.skip(reason="issue #XYZ")`

### Test Directory Structure

```
tests/
├── eval/           # LLM output quality evaluation tests
├── fixtures/       # Shared test data — must match current schemas
├── load/           # Load/stress tests — run separately from unit tests
├── scripts/        # Tests for operational scripts
├── security/       # Security-specific tests (injection, auth bypass, replay)
├── services/       # Service integration tests (one subdir per service)
└── shared_runtime/ # Unit tests for shared_runtime modules
```

- [ ] Every service in `services/` has a matching directory under `tests/services/`
- [ ] `tests/security/` has tests for: prompt injection, API key bypass attempts, replay attack simulation, PII leakage
- [ ] `tests/load/` has a baseline load test for the primary mission submission endpoint

---

## 11. Phase 9 — Security Audit

**Goal:** No secrets in code or history; all service boundaries are authenticated; all inputs are validated.

### Secrets Hygiene

- [ ] `gitleaks detect --source . --log-opts="--all"` — zero findings across full commit history
- [ ] `.gitleaks.toml` is up to date with custom patterns for theFactory-specific secret formats
- [ ] `git log --all --full-history -- "*.env" "*.pem" "*.key"` — no real credential files ever committed
- [ ] Pre-commit hook blocks commits containing secret patterns — tested with a dry-run injection
- [ ] `.env` is in `.gitignore`; local certs (`deploy/.local/`) are in `.gitignore`

### Authentication & Authorization

- [ ] `AUTH_MODE` hard-fails on invalid value in production; test coverage verified
- [ ] `MCP_API_KEY` auto-gen is stable in production; dev warns loudly; verify
- [ ] All service-to-service calls are authenticated — pod-worker → orchestrator, orchestrator → protocol-bus, etc.
- [ ] `agent_auth.py` and `agent_keys.py` tokens are short-lived and rotatable
- [ ] No service accepts requests from `localhost` without auth in production mode

### Input Validation

- [ ] All LLM prompt inputs are passed through `prompt_guard.py` before sending to provider
- [ ] All user-submitted mission text is scanned by `pii_guard.py` before storage
- [ ] File uploads (PDF, images via PM Agent) are validated for type, size, and content before processing
- [ ] All database query inputs use parameterized queries — no string interpolation in SQL

### Network Security

- [ ] TLS enforced on PostgreSQL and Redis connections in production (`make tls-certs`)
- [ ] Cert paths are consistent between `.env.example` and `docker-compose`; verify
- [ ] No service exposes a debug endpoint (`/debug`, `/admin`) without auth
- [ ] Docker containers do not run as root

### Replay & Deduplication

- [ ] Replay detection returns 409 on all protocol bus streams; verify full coverage
- [ ] Message IDs are globally unique — UUIDs, not sequential integers
- [ ] Idempotency keys are enforced on all state-mutating endpoints

---

## 12. Phase 10 — Error Handling Standards

**Goal:** Every failure mode is handled explicitly. Nothing silently swallows errors.

### Standards to Enforce

```python
# PROHIBITED — silent swallow
try:
    do_thing()
except Exception:
    pass

# PROHIBITED — catch-all with no re-raise
try:
    do_thing()
except Exception as e:
    logger.error(e)

# REQUIRED — typed exception, structured log, explicit recovery or re-raise
try:
    do_thing()
except RedisConnectionError as e:
    logger.error("redis_connection_failed", extra={"error": str(e), "trace_id": ctx.trace_id})
    raise ServiceUnavailableError("Protocol bus unreachable") from e
```

### Audit Actions

- [ ] `grep -r "except Exception" services/ shared_runtime/` — review every match; flag bare `pass` as 🔴
- [ ] `grep -r "except:" services/ shared_runtime/` — bare `except:` clauses are 🔴 blockers
- [ ] `grep -rn "pass$" services/ shared_runtime/` — flag any `pass` in non-abstract, non-`__init__` contexts
- [ ] All HTTP 5xx responses include a `trace_id` for correlation with logs
- [ ] LLM API failures return a user-facing message, not a raw provider error
- [ ] Database migration failures abort startup — not logged and continued

---

## 13. Phase 11 — Duplicate Code & Dead Code Elimination

**Goal:** One system owns each responsibility. No two modules do the same thing.

### Known Duplication Risks to Investigate

| Potential Duplicate Pair | Investigation Required |
|---|---|
| `orchestrator/protocol.py` vs `shared_runtime/protocol.py` | Are these the same schema? One should re-export the other |
| `milvus_store.py` vs `qdrant_store.py` | Are both actively used, or is one superseded? |
| `mission_flow.py` (shim) vs `mission_flow_v2/` (active) | Confirm shim has zero business logic; plan for removal |
| `knowledge_lake.py` vs `knowledge_embeddings.py` | Verify clean boundary: no overlapping function signatures |
| `object_store.py` vs artifact storage in `storage_artifacts.py` | Confirm these are different concerns |
| `neo4j_store.py` — is Neo4j still in the active stack? | Confirm it is used or schedule removal |
| `hw_agent.py` (2KB) — is this a Hello World test agent? | Confirm purpose or remove |
| `testdata_agent.py` — test fixture or production agent? | Must live in `tests/`, not `services/orchestrator/` |

### Dead Code Scan

- [ ] Run `vulture services/ shared_runtime/ --min-confidence 80` — review all reported dead code
- [ ] Remove any function/class not imported anywhere and not registered in agent registry
- [ ] Remove any feature flag path where the flag has been `true` by default for 3+ months — promote to always-on

### DRY Violations

- [ ] `grep -r "def emit_state_event" services/` — should exist in exactly one place
- [ ] `grep -r "def validate_envelope" services/ shared_runtime/` — should exist in exactly one place
- [ ] Any utility function duplicated across 2+ services is extracted to `shared_runtime/`

---

## 14. Phase 12 — Documentation Drift

**Goal:** Docs describe what the code actually does today. Every stale claim is corrected.

### Drift Checklist

- [ ] **AGENTS.md** — re-validate against current codebase after all fixes
- [ ] **README.md** — all commands, paths, and architecture descriptions match current state
- [ ] **CHANGELOG.md** — entries through current date; all recent changes documented
- [ ] **`docs/codex/DEFINITION_OF_DONE.md`** — matches audit DoD in this document
- [ ] **`docs/codex/REVIEW_CHECKLIST.md`** — matches current standards; not a stale copy
- [ ] **OpenAPI spec** — regenerated after any route changes; `make validate` enforces this
- [ ] **Inline docstrings** — every public function in `shared_runtime/` and all `storage_*.py` modules has a docstring
- [ ] **Architecture diagrams** — if any exist in `docs/`, they match current topology modes
- [ ] **MIGRATION.md** — covers all breaking changes; runbook steps are accurate

### Post-Audit Doc Update

After all findings are resolved, the following documents must be updated:
- `AGENTS.md` — timestamp updated, Known Open Gaps table cleared
- `CHANGELOG.md` — audit findings and fixes summarized
- `docs/` — new runbook entry for audit process and outcomes

---

## 15. Phase 13 — End-to-End Smoke Test

**Goal:** The system runs from cold start to successful mission delivery with no manual intervention.

### Smoke Test Sequence

```
1. Cold start
   make tls-certs
   make up
   → All 7 services healthy within 60s
   → /health returns 200 on all services
   → /ready returns 200 on all services

2. Mission submission (minimal)
   POST /missions { "prompt": "write a Python function that reverses a string" }
   → 202 Accepted with mission_id

3. Phase progression
   GET /missions/{mission_id}/status  (poll every 2s for up to 120s)
   → Observe: INTAKE → FETCH → SMELT → GATING → FUSION → SQUEEZE → DELIVERY

4. Output validation
   GET /missions/{mission_id}/artifacts
   → Contains at least one code artifact
   → Artifact content is valid Python (ast.parse() succeeds)

5. Audit trail
   GET /missions/{mission_id}/audit
   → Contains events for each phase transition
   → No phase gaps in the timeline

6. Ledger entry
   → Confirm LLM cost entry written to ledger/ for the mission

7. Workspace cleanup
   → Confirm no ephemeral workspace directory remains after DELIVERY

8. Mission Control UI
   → Open browser, submit same mission via UI
   → Observe real-time phase progression without page refresh
   → Download artifact from UI

9. Failure injection
   → Kill protocol-bus-mcp mid-mission
   → Confirm orchestrator logs error and queues for retry
   → Restart protocol-bus-mcp
   → Confirm mission resumes (or fails cleanly with user-visible error)

10. Provider fallback
    → Set primary LLM provider key to invalid value
    → Submit mission
    → Confirm fallback provider activates
    → Confirm mission completes with fallback provider noted in output
```

---

## 16. Findings Tracker

> All findings discovered during the audit are logged here. Status moves from `OPEN` → `IN PROGRESS` → `FIXED` → `VERIFIED`.

| ID | Phase | Severity | File | Description | Status | Fix PR |
|---|---|---|---|---|---|---|
| A-001 | Phase 1 | Improvement | `AUDIT_PLAN.md` | Original plan treated `sites/` as an active audit target; current application scope intentionally removed it. | FIXED | `5c9c768` |
| A-002 | Phase 1 | Improvement | `services/protocol-bus-mcp/Dockerfile` | Service entrypoint is `protocol_bus.mcp_server:app`, not `main.py`/`app.py`; checklist updated to validate ASGI targets from Docker CMD. | FIXED | local plan validation |
| A-003 | Phase 1 | Improvement | `tests/services/` | Tests are centralized by file naming instead of mirrored per-service subdirectories; plan adjusted so this layout is not reported as a false structural defect. | FIXED | local plan validation |
| A-004 | Phase 2 | Improvement | `.gitignore` | Mixed-case/generated-output scans must exclude ignored runtime/build residue (`MagicMock/`, `apps/mission-control/out/`, `apps/mission-control/output_extracted/`) unless doing local disk hygiene. | FIXED | local plan validation |
| A-005 | Phase 3/12 | Warning | README.md, docs/ARCHITECTURE.md, ledger/schema.sql | Docs claimed the stale SQLite ledger/schema.sql was the active traceability ledger; documentation now points to the active Postgres audit, LLM usage, and immutable ledger migrations, and the SQLite schema is labeled legacy. | FIXED | local working tree |
| A-006 | Phase 1 | Warning | schemas/rir.*.schema.json, tests/services/test_refined_ir_unit.py | Refined IR schemas had active producer code but no focused regression test proving generated RIR stays aligned with the canonical JSON schemas. | FIXED | local working tree |
| A-007 | Phase 1 | Warning | `examples/`, `tests/test_examples_schema.py` | Static examples had no regression test proving they stayed aligned with the current LogicNode and RIR schemas. | FIXED | local working tree |

---

## 17. Definition of Done — Audit Complete

The audit is complete when **all** of the following are true:

- [ ] Zero 🔴 Blocker findings remain open
- [ ] Zero `pass` / `...` / `raise NotImplementedError` in non-abstract production code paths
- [ ] `make validate` passes clean: lint + schema validation + pytest + npm lint/test
- [ ] `make test` achieves >= 80% global coverage with all per-module floors met
- [ ] `make test-ui-e2e` passes all Playwright scenarios including failure injection
- [ ] `gitleaks detect --log-opts="--all"` returns zero findings
- [ ] `tsc --noEmit` returns zero errors in strict mode
- [ ] All 7 services pass `/health` and `/ready` checks on cold start
- [ ] End-to-end smoke test (Phase 13) completes with zero manual intervention
- [ ] `AGENTS.md` timestamp updated; Known Open Gaps table reflects current state
- [ ] `CHANGELOG.md` updated with audit summary
- [ ] All 🟡 Warning findings are either fixed or have a tracked issue with a sprint assignment
- [ ] Findings Tracker (Section 16) has no OPEN or IN PROGRESS rows

---

*This document is the living record of the theFactory production audit. Update Section 16 (Findings Tracker) as issues are discovered and resolved. When the Definition of Done is satisfied, archive this document to `docs/audits/audit-2026-06-21.md`.*
