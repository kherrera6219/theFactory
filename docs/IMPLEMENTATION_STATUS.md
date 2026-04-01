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
- Go, Haskell, and OCaml are now fully supported with dedicated agents and compose routing.
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

1. Align audit/event documentation with the actual `missions.state`, `mission.state.complete`, and `mission_audit_reports` implementation.
2. Update the remaining Mission Control data-plane surfaces and copy to reflect live optional-adapter readiness.
3. Reconcile language-count and extraction/routing claims across docs with the current 20-key routing matrix.
4. Extend build/package execution beyond source-bundle packaging to any future binary/container/package builders and wire those outputs into the same artifact contract.
5. Execute the remaining release phases in [`RELEASE_COMPLETION_PLAN.md`](RELEASE_COMPLETION_PLAN.md), including AI safety governance, shared-state durability, DR evidence, and final release qualification.
