# Implementation Status

Document version: 2026.03.31
Last updated: 2026-03-31
Status: Canonical
Audience: Operators, developers, maintainers, and auditors

This document is the canonical current-state snapshot for theFactory. Use it as the source of truth for shipped defaults, active runtime behavior, and known gaps. Date-stamped ADRs, roadmap phases, audits, and completion checklists remain useful historical records, but some of them no longer describe the current default runtime exactly.

## Shipped Defaults

- `MISSION_FLOW_V2_ENABLED=true` by default in `.env.example`, `deploy/docker-compose.yaml`, and `services/orchestrator/orchestrator/settings.py`.
- `LANGGRAPH_ENABLED=false` by default. The LangGraph lifecycle remains optional and is not the shipped default path.
- `services/orchestrator/orchestrator/runtime.py` executes mission flow in this order:
  1. v2 lifecycle when `MISSION_FLOW_V2_ENABLED=true`
  2. LangGraph lifecycle when v2 is disabled and `LANGGRAPH_ENABLED=true`
  3. legacy lifecycle fallback

## Runtime Topology

- The orchestrator maintains a 38-agent registry with persona and integration metadata.
- The default deployment is still the condensed topology:
  - API Gateway
  - Orchestrator
  - shared pod-worker instances
  - audit-worker
  - Mission Control
- The fully isolated per-agent runtime exists, but only through optional dedicated profiles in `deploy/docker-compose.yaml` and `deploy/docker-compose.full-dedicated-agents.yaml`.
- In the condensed topology, some interface, executive, and support-agent heartbeats are synthesized by the orchestrator rather than emitted by separate long-running worker processes.

## Current Control-Plane Behavior

### Mission lifecycle

- Canonical external mission states remain `QUEUED -> RUNNING -> VERIFIED -> COMPLETE | FAILED`.
- Smelt-cycle checkpoint events are still the operator-facing phase model.
- The shipped default runtime routes through the v2 lifecycle implementation.
- `POST /v1/missions` now persists through the orchestrator before returning `201 Created`, so the mission record is queryable immediately after create.
- Dynamic scaling is now wired end-to-end behind `AGENT_SCALING_ENABLED`: the orchestrator computes partition work, emits `mission.partition.ready`, pod-workers execute partitions, results are merged into mission metadata, and lifecycle resumes once all partitions complete.

### Audit flow

- The audit worker consumes `missions.state`, not a separate `missions.audit` stream.
- Audit results are persisted through the orchestrator audit-report path into `mission_audit_reports`.
- `MISSION_COMPLETE` now maps to `mission.state.complete`.
- Source-bundle missions now package a real build artifact at `VERIFIED`: the orchestrator stores a Postgres-backed build/package record with digest, manifest, verification metadata, and build log before allowing completion.
- Build-complete semantics are therefore now stronger for supported mission types: `COMPLETE` requires both the existing pod/LogicNode evidence and a successful stored build artifact when `metadata.source_code` is present.

### Data plane

- PostgreSQL is deployed as a single application database by default (`POSTGRES_DB=ulr`).
- Primary tables are created by versioned migrations in `services/orchestrator/orchestrator/migrations/`, including `mission_build_artifacts` in `V002_build_artifact_runtime_schema.sql`.
- Redis Streams remain the event backbone:
  - `missions.intake`
  - `missions.state`
  - `missions.pod.A|B|C|D`
  - `agents.heartbeats`
- Qdrant is active in the core compose stack.
- Neo4j and object storage remain optional feature-flagged adapters.

## Mission Control Status

- Mission Control is a real Next.js operator console with chat, missions, agents, semantic-bus, builder, repo-import, databases, settings, and supporting diagnostics views.
- The repository import path is real GitHub metadata/tree ingestion.
- Repository review is now server-backed: Mission Control fetches selected GitHub file content, builds a review artifact with a stable fingerprint, infers `requested_target_language`, and launches repo missions with a real `source_code` bundle.
- Builder review is now server-backed against the local workspace: it selects real files, emits a stable `builder_fingerprint`, produces a grounded patch contract plus `source_code` bundle, and can launch missions from that approved artifact.
- Review approval is now persisted server-side for both Builder and repository review flows through durable orchestrator-backed approval records before mission launch.
- The chat intake page now infers `requested_target_language` from attached files and prompt hints instead of hardcoding `python`.
- The mission detail page now surfaces stored build/package artifacts, including status, digest, storage backend, and size.
- The databases page and some UX copy still lag live backend readiness details.

## Language Extraction Status

- Specialist routing currently covers 20 language keys across four pods. TypeScript is accepted as a routed key but aliases to the JavaScript specialist.
- Go, Haskell, and OCaml are registered in the agent registry and supported by the language extraction engine. Dedicated agent containers for `agent-36-go` (Pod B), `agent-37-haskell` (Pod D), and `agent-38-ocaml` (Pod D) are now defined in `deploy/docker-compose.full-dedicated-agents.yaml` and included in the `make up-full-dedicated` Makefile target. All 38 agents are present in both condensed and full-dedicated topologies.
- Some documentation artifacts still carry older language-count claims and need reconciliation to the current routing matrix.

## Security Hardening (Phase 0–4 complete as of 2026-03-31)

- **PII detection & redaction** (`shared_runtime/pii_guard.py`): SSN, credit card, email, phone, JWT, API key, password KV pairs; integrated at API Gateway in production (`PII_GUARD_MODE=redact`)
- **Prompt injection guard** (`shared_runtime/prompt_guard.py`): system-tag smuggling, INST injection, role-override, jailbreak detection; `PROMPT_GUARD_MODE=block` in production
- **HMAC-signed review approvals**: approval records carry `issued_at`, `expires_at`, HMAC-SHA256 digest; configurable 24h TTL
- **Structured audit log** at API Gateway: every request logged as structured JSON with hashed client IP and trace ID
- **Event replay detection** (`shared_runtime/protocol.py`): in-process `_InProcessReplayGuard` with TTL eviction
- **Message deduplication** in semantic bus: Redis SET NX EX on `correlation_id`; backpressure 503 + `Retry-After: 5` when queue > limit
- **Circuit breaker** in agent-runtime: CLOSED/OPEN/HALF-OPEN state machine; configurable failure threshold and recovery window
- **AST-based Python extraction** (`pod_worker/ast_extractor.py`): replaces regex for function/class/import detection with accurate `ast` module parsing
- **Secret hygiene**: gitleaks full-history scan, `.pre-commit-config.yaml` with staged-secret protection, `.gitleaks.toml` custom patterns

## Validation Snapshot

As of 2026-03-31:

- `python -m pytest -q` is green: **770 passed, 5 skipped** (excludes one pre-existing broken import test).
- All new Phase 2–4 modules have 100% test coverage (PII guard, prompt guard, AST extractor, circuit breaker, semantic bus dedup).
- `apps/mission-control` TypeScript check is green (`npm run lint`).
- `apps/mission-control` unit tests are green (`npm test`, `45` tests).
- `apps/mission-control` Playwright: original 7 tests plus 13 new extended tests from Phase 1 E2E expansion.
- Repository-wide `python -m ruff check services tests scripts` still has documented pre-existing variance in untouched files.
- Orchestrator `main.py` reduced from 2065 to 1250 lines via route decomposition into `routes/` subpackage.

The repository should therefore be treated as a production-ready baseline with defense-in-depth security hardening and improved maintainability.

## Current Hardening Baseline

Repo-local hardening work has improved the baseline materially:

- insecure default compose fallbacks for internal service keys were removed
- API gateway internal forwarding now fails closed
- Qdrant and Neo4j outbound URL fetches validate scheme before request
- LLM delegation retries 429 responses with `Retry-After`
- service coverage gating is currently green at `>=80%`
- the current-source docs are reconciled to the 38-agent runtime

Release completion work is now sequenced in [`RELEASE_COMPLETION_PLAN.md`](RELEASE_COMPLETION_PLAN.md), and the latest cross-suite repository posture is tracked in [`../reports/master_audit_2026-03-29.md`](../reports/master_audit_2026-03-29.md).

## Open Gaps For Completion

1. ~~Align audit/event documentation with the actual `missions.state`, `mission.state.complete`, and `mission_audit_reports` implementation.~~ **Resolved (2026-04-12):** `docs/ARCHITECTURE_DIAGRAMS.md` corrected to remove the non-existent `missions.audit` stream. `docs/ARCHITECTURE.md` already stated this correctly. `docs/evidence/pod_language_extraction_2026-03-03.md` updated with a reconciliation note.
2. Update the remaining Mission Control data-plane surfaces and copy to reflect live optional-adapter readiness. The databases page (`apps/mission-control/app/(shell)/databases/page.tsx`) correctly surfaces Qdrant, Neo4j, and object-storage adapter status from the live runtime. Optional adapters display as "Optional adapter disabled" when not enabled. UX copy is current.
3. ~~Reconcile language-count and extraction/routing claims across docs with the current 20-key routing matrix.~~ **Resolved (2026-04-12):** Evidence file updated with reconciliation note. Stale "14-language" and "16-language" references exist only in `docs/archive/2026-03-29/legacy-workspace/` (appropriately archived). Canonical docs (`IMPLEMENTATION_STATUS.md`, `ARCHITECTURE.md`) state 20 language keys.
4. ~~Extend build/package execution beyond source-bundle packaging to any future binary/container/package builders and wire those outputs into the same artifact contract.~~ **Resolved (2026-04-12):** `build_artifacts.py` now implements `build_binary_artifact()`, `build_container_artifact()`, and `dispatch_build_artifact()`. Mission metadata field `builder_type` (`source_bundle` | `binary` | `container`) selects the builder. All types share the same artifact contract, Postgres storage, and API surface.
5. ~~Execute Phase 4 (AI safety governance): versioned prompt templates, LLM instrumentation, data-leakage red-team eval suite, and classification policy.~~ **Resolved (2026-04-12):** See "Resolved Since Last Snapshot" below.
6. Execute the remaining release phases in [`RELEASE_COMPLETION_PLAN.md`](RELEASE_COMPLETION_PLAN.md), including shared-state durability (Phase 5), DR evidence, and final release qualification.

## Resolved Since Last Snapshot

- **2026-04-12:** Dedicated topology gap closed — `agent-36-go`, `agent-37-haskell`, `agent-38-ocaml` container definitions added to `deploy/docker-compose.full-dedicated-agents.yaml` and `make up-full-dedicated`.
- **2026-04-12:** One-click launcher added — `Launch-TheFactory.bat` / `Launch-TheFactory.ps1` at repo root. Handles `.env` generation with CSPRNG secrets, TLS cert generation, stack startup, readiness polling, and browser launch.
- **2026-04-12:** Audit/event and language-count documentation drift resolved (see gap 1 and 3 above).
- **2026-04-12:** Build artifact pipeline extended to `binary` and `container` builder types. `dispatch_build_artifact()` selects the correct builder from `metadata.builder_type`. All three builder types produce the same artifact contract shape and persist via the existing Postgres/API surface. Test suite expanded from 770 to 946 passing tests.
- **2026-04-12 (Phase 4 — AI Safety / Prompt Governance):**
  - Versioned prompt templates introduced: `prompts/v1/ceo_delegation.txt`, `pod_manager_delegation.txt`, `specialist_planning.txt`. Templates are static policy assets with no user-controlled placeholders. Active version pinnable via `PROMPT_VERSION` env var without redeployment.
  - `prompt_loader.py` added: `lru_cache`-backed template loader with `render_prompt()` raising `KeyError` on missing placeholders (never silently malformed).
  - `llm_delegation.py` updated: all three `_build_*_prompt` functions replaced with `render_prompt()` calls; `_call_with_recommendation()` now emits structured `llm_call` log lines with `provider`, `model`, `route`, `latency_ms`, `prompt_version`, and `status` fields.
  - `PROMPT_GUARD_MODE` default changed from `log` to `block` in `.env.example`.
  - Red-team eval suite expanded: `tests/eval/test_llm_delegation_golden.py` now covers 12-field forbidden-context list, PII redaction (email, API-key patterns), Unicode/homoglyph rejection, control-character stripping, context size cap, and all three prompt templates. Total eval test count: 93.
  - `docs/DATA_CLASSIFICATION_POLICY.md` updated with LLM delegation data controls section — maps every mission metadata field to PUBLIC/INTERNAL/CONFIDENTIAL/RESTRICTED and documents all enforcement points.
  - `docs/MODEL_PROMOTION_GOVERNANCE.md` updated with full 5-gate promotion lifecycle: capability eval, prompt compatibility, red-team verification, security sign-off, and staged rollout. Rollback procedure documented.
