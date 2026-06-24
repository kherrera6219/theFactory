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
**Current repository baseline:** `main` at `ff5419f` (`audit-phase-4-complete-protocol-producers`)

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
- Audit-phase helper scripts are temporary tooling only. They must stay outside
  the repository, for example under `C:\\tmp`, and must not be committed as
  phase-named implementation files. Permanent fixes belong in stable,
  domain-named app, test, and documentation files.

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

- [x] **Services use kebab-case** — tracked service directories are `agent-runtime`, `api-gateway`, `audit-worker`, `dashboard`, `orchestrator`, `pod-worker`, and `protocol-bus-mcp`.
- [x] **Python package dirs match service names** — internal package directories use lowercase/underscore names (`agent_runtime`, `api_gateway`, `audit_worker`, `pod_worker`, `protocol_bus`) or the service's canonical package name.
- [x] **No mixed case in directory names** — tracked source directories under `apps/`, `services/`, `shared_runtime/`, `tests/`, `scripts/`, `config/`, `deploy/`, `protocol/`, and `schemas/` have no CamelCase/UPPERCASE directory names. Ignored generated/runtime output remains out of scope.
- [x] **Test mirror structure** — service tests are intentionally centralized as `tests/services/test_*.py` files rather than per-service subdirectories; this matches the current repo convention validated in Phase 1.
- [x] **No `utils.py` catch-alls** — tracked source has no `utils.py` files.
- [x] **No `helpers.py` catch-alls** — tracked source has no `helpers.py` files.
- [x] **`__init__.py` exports** — non-empty package initializers now declare `__all__`; no Python star imports were found in tracked source.

### Audit Actions

- Run: `find . -name "*.py" | xargs grep -l "^from .* import \*"` — flag all star imports
- Run: `find . -type d | grep -E "[A-Z]"` — flag any CamelCase or UPPERCASE directories
- Run: `find . -name "utils.py" -o -name "helpers.py"` — review each for catch-all patterns

---

## 5. Phase 3 — Configuration & Dependency Wiring

**Goal:** Every config key has a consumer; every consumer has a declared key. Dependencies are pinned and conflict-free.

### `.env.example` Audit

- [x] **Key coverage forward** — `.env.example` duplicate keys were removed; remaining intentionally documented keys include compose/UI/service knobs that are consumed outside direct Python `os.getenv()` calls.
- [x] **Key coverage reverse** — tracked Python `os.getenv()`/`os.environ` references are now represented in `.env.example`; live/demo validation knobs are documented separately.
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
- [x] **All dependencies pinned** — production service requirements have no unpinned lines; `psycopg-pool` is pinned.
- [ ] **`pip check`** — run in each service venv; zero conflicts required
- [ ] **`requirements-dev.txt` separation** — dev tools (pytest, ruff, mypy) are not in production requirements
- [ ] **Optional deps marked** — LangGraph, esprima, javalang are optional; their absence must not crash startup when their feature flags are disabled
- [ ] **Docker layer caching** — each Dockerfile's `COPY requirements.txt` precedes `COPY .` to enable layer caching

### Config Directory

- [x] **Every config file has a loader** — stale `config/agent_api_keys.yaml` was removed from the active application tree because runtime key handling uses env vars and Mission Control vault storage.
- [ ] **Config is validated at load time** — not lazily validated when first accessed in a request handler
- [ ] **Config changes don't require code changes** — runtime behavior should be adjustable via env vars without touching source files

---

## 6. Phase 4 — Backend Service Audit

**Goal:** Every service is production-complete: real implementation, no stubs, proper error handling, health endpoints, and metrics.

### Per-Service Audit Checklist (apply to each)

Services: `api-gateway` · `orchestrator` · `pod-worker` · `agent-runtime` · `audit-worker` · `protocol-bus-mcp` · `dashboard`

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
- [x] `/metrics` endpoint exposes Prometheus-compatible metrics — all backend services now expose `/metrics`; dashboard was brought into parity in Phase 4.
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

- [x] Auth mode `AUTH_MODE` hard-fails on invalid value; covered by API gateway startup validation tests.
- [ ] Rate limiting is enforced per-key, not globally
- [ ] All routes require API key validation before reaching handlers
- [x] CORS policy is explicit and restrictive; `*` is not permitted in production by startup validation.
- [ ] Request/response logging does not log sensitive headers or body fields containing secrets

#### `services/pod-worker` Specific

- [ ] `GoAgent`, `HaskellAgent`, `OcamlAgent` are concrete subclasses; verify no `BaseAgent` fallback remains
- [ ] All 4 pod families (A/B/C/D) have complete language routing with no `language not found` silent fallback
- [ ] AST extractors (Python, JS/TS, Java) — feature flags respected; fallback to regex is logged, not silent
- [ ] Extractors have fixture comparison tests (old vs. new output) for every supported language
- [ ] Workspace creation is atomic; partial workspace creation is impossible
- [ ] Workspace cleanup runs even on task failure (use `try/finally`)

#### `services/protocol-bus-mcp` Specific

- [x] All 6 Redis protocol streams (α, β, δ, σ, ω, ρ) are declared and consumed — bus validation and consumer support cover all six; typed producer helpers now exist for alpha, beta, delta, sigma, omega, and rho.
- [ ] Replay detection returns 409 on duplicate message IDs; verify test coverage
- [ ] Redis failures return 503 — not silent pass-through
- [ ] Stream naming is consistent across all producers and consumers
- [ ] Dead Letter Queue (DLQ) is implemented on all streams, not just intake

#### `services/audit-worker` Specific

- [ ] Every agent action that should produce an audit event does produce one
- [ ] Audit events are immutable after write — no update/delete paths
- [ ] Audit worker failure does not block mission execution (async, non-blocking write)
- [ ] Audit trail is queryable by mission ID, agent ID, and timestamp range

### Phase 4 Closeout Status

Phase 4 is closed for this audit pass as of `3cced29`. The app-impacting fixes completed in Phase 4 were dashboard metrics/response contracts, six-lane protocol producer helpers, and API gateway startup validation for auth/CORS safety.

Carry-forward items remain tracked for later hardening rather than being marked done prematurely:
- broad route `response_model=` coverage across all services;
- full pytest/Ruff execution after local Python tooling is restored;
- deeper mission lifecycle recovery behavior under live runtime conditions;
- full request/response model standardization for every FastAPI route.

---

## 7. Phase 5 — Agent & Orchestrator Wiring

**Goal:** Every agent in the 41-agent registry is accounted for, reachable, and correctly routed.

### Agent Registry Audit (`agent_registry.py`)

- [x] **41-agent inventory** — registry scan confirms 41 agents with `runtime_class`, `pod_assignment`, `language_keys`, and real-vs-synthesized runtime class coverage
- [x] **No ghost agents** — every agent in the registry either has a concrete implementation class OR is explicitly documented as `synthesized_heartbeat`
- [x] **No orphaned implementations** — every `*Agent` class defined in the codebase is registered in `agent_registry.py`
- [x] **`AgentPersona` consistency** — every registered agent has a corresponding `AgentPersona` dataclass entry with no field gaps

### Smelt Cycle Wiring (INTAKE → FETCH → SMELT → GATING → FUSION → SQUEEZE → DELIVERY)

- [ ] Each phase has a discrete handler function — no phase logic inlined in the orchestrator loop
- [ ] Phase transitions are guarded — a mission cannot skip a phase without explicit gating logic
- [ ] Phase failures are recoverable — `lifecycle_recovery.py` is invoked on phase failure, not just on total mission failure
- [ ] Phase state is persisted to storage before transitioning — crash recovery can resume from any phase

### MissionFlowV2 Phases (11-phase state machine)

Phase 5 progress: the clarification hold/resume path now re-queues clarified missions, restarts the lifecycle task, and feeds operator clarification back into PM intake context. Registry inventory now confirms 41 agents, 0 missing personas, 0 orphan personas, 0 missing specialist language personas, audit-facing aliases for `runtime_class`, `pod_assignment`, and `language_keys`, and permanent test coverage for synthesized-heartbeat/shared-worker routing plus concrete implementation reachability. MissionFlowV2 now resets LLM mission/settings context variables in `finally` so early returns and exceptions cannot leak one mission context into later LLM calls on the same worker task. Protocol bus consumers now drop lane/protocol mismatches before handler execution. Regression coverage was added in `tests/services/test_mission_clarify_route_unit.py`, `tests/services/test_agent_personas_registry.py`, `tests/services/test_agent_base_unit.py`, `tests/services/test_mission_flow_v2.py`, and `tests/services/test_protocol_bus_consumer.py`; `py_compile` passes, the direct agent implementation invariant check reports 41 registry agents / 24 concrete classes / 24 reachable classes, and the direct protocol lane-guard check drops mismatched envelopes before dispatch; local pytest remains blocked by missing pytest in the bundled runtime.

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

- [x] `tsc --noEmit` passes with zero errors in strict mode � `npm --prefix apps/mission-control run lint` passes as of Phase 6 start
- [ ] Zero `any` types in application code — OpenAPI-generated types enforced; verify no regressions
- [x] Zero `// @ts-ignore` or `// @ts-expect-error` in production `app/` code
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

- [x] All Vitest unit tests pass: `npm --prefix apps/mission-control run test` passes with 16 files / 74 tests
- [ ] All Playwright e2e tests pass: `make test-ui-e2e`
- [ ] Coverage threshold met for UI unit tests
- [ ] E2e tests cover the primary happy path: submit mission → observe phases → view output
- [ ] E2e tests cover failure scenarios: backend unavailable, invalid mission input

---

### Phase 6 Closeout Status

Phase 6 is closed for this offline audit pass as of `b6d781a`. Completed fixes include shared `fetchJson` handling for Settings vault actions, removal of explicit production `any` and stale duplicate panel interfaces, and standardization of Repo Import/logout client requests. TypeScript passes, the production client-component scan has zero raw `fetch` calls, and Vitest passes with 16 files / 74 tests.

Carry-forward work remains open rather than being marked complete: generated OpenAPI client adoption beyond the shared request wrapper, route-specific loading/error boundary review, Playwright E2E, and live browser validation against the running stack.

---
## 9. Phase 7 — Shared Runtime Audit

**Goal:** `shared_runtime/` is the foundation trusted by all services. Every module must be bulletproof.

Phase 7 status: active as of 2026-06-24 after the Phase 6 documentation checkpoint. Package/import inventory confirms all ten modules have active consumers and the package root exposes no accidental internals. Completed fixes now cover concurrent atomic writes, strict P-256 artifact verification, bounded HMAC freshness, and PII/credential redaction for JSON and plain-text shared logging. The production keystore migration remains open because Linux currently permits plaintext fallback and the loader does not yet accept a mounted raw PEM replacement.

### Module-by-Module Review

| Module | Audit Focus |
|---|---|
| `agent_auth.py` | HMAC-SHA256 validation uses constant-time comparison, rejects empty identities/secrets, validates header shape, and separates future clock skew from replay age |
| `agent_keys.py` | Key rotation is possible without service restart; key derivation is deterministic and documented |
| `atomic_io.py` | File operations use OS-level atomic write patterns (`tempfile` + `rename`); unique sibling temp files, per-destination locking, and Windows sharing-violation retry now cover concurrent writers |
| `crypto_keystore.py` | Keys are stored encrypted at rest; memory is cleared after use (`del key`) |
| `crypto_signing.py` | Signing algorithm is documented; verification now enforces P-256, requires the canonical digest, rejects malformed base64, and writes signature sidecars atomically |
| `errors.py` | All custom exception classes have meaningful messages; no bare `Exception` subclasses |
| `logging_config.py` | JSON and plain logging redact PII, exception text, nested extras, and credential fields while preserving trace correlation; log levels remain configurable |
| `pii_guard.py` | PII detection covers all field types declared in the system; tested against real payloads |
| `prompt_guard.py` | Injection detection patterns are up to date; test coverage includes adversarial inputs |
| `protocol.py` | Envelope schema matches `schemas/`; no divergence between runtime and schema files |

### Cross-Service Contract

- [x] `shared_runtime` is imported as a package, not copied per-service - all ten modules have active service/test import consumers
- [ ] Any change to `shared_runtime` requires all services to be re-tested before deploy
- [x] `shared_runtime/__init__.py` exports only the public API - it intentionally declares an empty `__all__`, while consumers import explicit modules/symbols

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
| A-008 | Phase 2 | Warning | `services/*/__init__.py`, `shared_runtime/__init__.py` | Non-empty package initializers had docstrings/comments but no explicit `__all__`, leaving public package exports implicit. Added explicit empty `__all__` declarations where packages do not re-export symbols. | FIXED | local working tree |
| A-009 | Phase 3 | Warning | `.env.example` | `.env.example` contained duplicate core service/data-plane keys and stale `KNOWLEDGE_EMBEDDING_MODEL=text-embedding-004`; deduped the template and aligned the default with Gemini embeddings. | FIXED | local working tree |
| A-010 | Phase 3 | Warning | `.env.example` | Runtime Python env lookups and live/demo script knobs were not fully declared in `.env.example`; added documented optional defaults for service tuning, state topics, DLQ, protocol bus, tracing, safety, live validation, and demo controls. | FIXED | local working tree |
| A-011 | Phase 3 | Warning | `services/orchestrator/requirements.txt` | Production requirement `psycopg-pool>=3.3.1` was unpinned. | FIXED | local working tree |
| A-012 | Phase 3 | Improvement | `config/agent_api_keys.yaml` | Stale YAML key configuration sample was kept under active `config/` but no runtime loader consumed it; active key configuration is env/vault based. Removed it from the active app tree. | FIXED | local working tree |
| A-013 | Phase 4 | Warning | `services/dashboard/dashboard/main.py`, `services/dashboard/requirements.txt` | Dashboard lacked the Prometheus `/metrics` endpoint and dependency used by other backend services; added the endpoint, dependency, and explicit response contracts/status codes for dashboard JSON routes. | FIXED | `0771f12` |
| A-014 | Phase 4 | Warning | `services/orchestrator/orchestrator/protocol_bus_producer.py`, `tests/services/test_protocol_bus_consumer.py` | Generic protocol sends supported all six lanes, but typed producer helpers and helper-schema tests only covered alpha, beta, delta, and omega. Added sigma/rho helpers and schema coverage so all six protocol lanes have standard producer APIs. | FIXED | `ff5419f` |
| A-015 | Phase 4 | Warning | `services/api-gateway/api_gateway/main.py`, `tests/services/test_api_gateway_auth_mode_unit.py` | API gateway startup validation did not hard-fail invalid `AUTH_MODE`, and production CORS allowed `*` if configured. Added fail-fast startup validation and focused unit coverage. | FIXED | `3cced29` |
| A-016 | Phase 5 | Warning | `services/orchestrator/orchestrator/routes/missions.py`, `services/orchestrator/orchestrator/mission_flow_v2/phases_intake.py`, `services/orchestrator/orchestrator/models.py`, `tests/services/test_mission_clarify_route_unit.py` | Missions paused in `CLARIFYING` accepted clarification without reliably resuming PM intake/lifecycle work, and the operator answer was not fed back into the PM contract prompt. Clarification now re-queues, emits `MISSION_CLARIFICATION_APPLIED`, restarts lifecycle processing, and passes `operator_clarification` into PM intake context. | FIXED | `bc00a7a` |
| A-017 | Phase 5 | Improvement | `services/orchestrator/orchestrator/agent_registry.py`, `tests/services/test_agent_personas_registry.py` | The 41-agent registry had the required data but did not expose audit-facing `pod_assignment` and `language_keys` accessors named by the Phase 5 checklist. Added read-only aliases and regression coverage; inventory now reports no missing alias fields. | FIXED | `b338976` |
| A-018 | Phase 5 | Improvement | `tests/services/test_agent_base_unit.py` | The ghost/orphan agent implementation audit was only proven by temporary inventory output and partial factory tests. Added permanent regression coverage that every registry runtime class maps to the documented implementation path and every concrete `BaseAgent` subclass is reachable through `AGENT_REGISTRY`. | FIXED | `983d571` |
| A-019 | Phase 5 | Warning | `services/orchestrator/orchestrator/mission_flow_v2/lifecycle.py`, `tests/services/test_mission_flow_v2.py` | MissionFlowV2 set LLM mission/settings context variables without resetting them, so early returns or exceptions could leak one mission context into later LLM calls on the same worker task. Added `try/finally` reset coverage. | FIXED | `40d4cee` |
| A-020 | Phase 5 | Warning | `services/orchestrator/orchestrator/protocol_bus_consumer.py`, `tests/services/test_protocol_bus_consumer.py` | ProtocolBusConsumer decoded envelopes but did not verify the envelope protocol matched the Redis lane being consumed, so misrouted/corrupted bus entries could reach the wrong handler. Added lane/protocol enforcement and regression coverage. | FIXED | `adfc81a` |
| A-021 | Phase 6 | Warning | `apps/mission-control/app/(shell)/settings/page.tsx` | Settings vault actions used raw `fetch` instead of the shared `fetchJson` client, bypassing standard timeout and structured API error handling. Converted vault list/save/test/delete calls to `fetchJson` with narrow response types. | FIXED | `db178d2` |
| A-022 | Phase 6 | Warning | `apps/mission-control/app/(shell)/missions/detail/`, `apps/mission-control/app/(shell)/settings/page.tsx` | Production Mission Control code still used explicit `any` in maintenance catches, mission-detail panel props, and phase-model dispatch. Replaced catches with `unknown`, reused canonical shared types, removed stale casts, and typed the event model as `MissionPhaseModel`. | FIXED | `7681c4d` |
| A-023 | Phase 6 | Warning | `apps/mission-control/app/(shell)/repo/page.tsx`, `apps/mission-control/app/components/logout-button.tsx` | Repo Import and logout client components still used raw `fetch`, bypassing the shared timeout and structured error client. Converted both to `fetchJson`; production client components now contain zero raw `fetch` calls. | FIXED | `b6d781a` |
| A-024 | Phase 7 | Warning | `shared_runtime/atomic_io.py`, `tests/services/test_atomic_io_unit.py` | Atomic writes reused a fixed `<name>.tmp`, allowing concurrent writers to collide; Windows could also reject simultaneous destination replacement with sharing violations. Added unique sibling temp files, per-destination locking, bounded Windows retry, guaranteed cleanup, and concurrency coverage. | FIXED | `a696152` |
| A-025 | Phase 7 | Warning | `shared_runtime/crypto_signing.py`, `tests/services/test_crypto_signing_unit.py` | Verification advertised `ECDSA-P256-SHA256` but accepted other EC curves and signature records without the required digest; artifact sidecars also used non-atomic writes. Enforced P-256, required constant-time digest comparison, enabled strict base64 validation, and moved sidecars to atomic JSON writes. | FIXED | `68b86d4` |
| A-026 | Phase 7 | Warning | `shared_runtime/agent_auth.py`, `tests/shared_runtime/test_agent_auth.py` | HMAC freshness used an absolute timestamp delta, allowing signatures nearly a full replay window in the future and extending their usable lifetime; signing also accepted empty identities/secrets. Added a separate future-skew bound, header/hex/window validation, narrow exception handling, and fail-closed signing inputs. | FIXED | `ded42a5` |
| A-027 | Phase 7 | Warning | `shared_runtime/logging_config.py`, `tests/services/test_logging_config_unit.py` | Shared JSON logging emitted raw messages, exception text, and arbitrary nested extras; plain logging also emitted raw rendered messages. Added PII redaction for both formats, recursive structured-field handling, credential-name masking, and trace-correlation preservation coverage. | FIXED | `ab32fa6` |
| A-028 | Phase 7 | Warning | `shared_runtime/crypto_keystore.py`, `.env.example`, `deploy/docker-compose.prod.yaml` | Non-Windows runtimes currently default to `PLAINv1` key storage, including production Linux containers, but the loader does not accept a mounted raw PEM replacement. A coordinated mounted-secret/KMS format and migration path is required before plaintext fallback can be disabled safely. | OPEN | tracked Phase 7 follow-up |
| A-029 | Phase 7 | Warning | `shared_runtime/errors.py`, `tests/services/test_errors_unit.py` | The error model promised sanitized developer detail but trusted callers and copied raw `str(exc)` through `wrap_unexpected()`, allowing credentials or PII into serialized error objects. `FactoryError` now sanitizes developer messages at construction with direct and wrapped-error regression coverage. | FIXED | `563a4d0` |

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
