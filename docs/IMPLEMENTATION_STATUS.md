# Implementation Status

Document version: 2026.05.16
Last updated: 2026-05-18
Status: Canonical
Audience: Operators, developers, maintainers, and auditors

This document is the canonical current-state snapshot for theFactory. Use it as the source of truth for shipped defaults, active runtime behavior, current qualification status, and known follow-up work. Date-stamped ADRs, roadmap phases, audits, and completion checklists remain useful historical records, but some of them no longer describe the current default runtime exactly.

## Project Status

As of 2026-05-18, Phases 1-14 are implemented and validated locally.

- **Implemented:** model governance and fallback LLM validation, durable PM/CEO contracts, first generated-output artifact support, PM feature contract and mission charter persistence, CEO logic-cluster decomposition, pod group standards, JavaScript/TypeScript/Java AST-backed extraction, Phase 8 FETCH/knowledge context, Phase 9 FUSION/master logic stream, Phase 10 DELIVERY/PM verification, Phase 11 Application Intelligence Map, Phase 12 equivalence reports, Phase 13 security/compliance reports for generated outputs, and Phase 14 dependency inventory/classification with advisory absorption planning.
- **Current active phase:** Phase 15 - Token and Cost Ledger.
- **Still planned:** Tier 4/5 trust, cost, knowledge-lake, DR, and demo hardening.
- **Release blockers:** live provider-key BUILD_NEW demo, stale qualification-evidence refresh, and remaining forward-looking docs cleanup.

## Mission Control UI — Vault and Settings (2026-04-16)

- **API Key Vault Slots table** in `/settings` now populates all 35 agent slots offline via a static roster fallback. The orchestrator does not need to be running to enter or save API keys.
- **Vault persistence** is active when `MISSION_CONTROL_ADMIN_KEY` is set to a 64-hex-char value in `apps/mission-control/.env.local`. Keys are stored as AES-256-GCM ciphertext in `~/.thefactory/vault.json`. The server must be restarted after `.env.local` changes.
- **Vault backend selection** (from `vault.ts`): HashiCorp Vault if `VAULT_ADDR` is set, local-encrypted file if `MISSION_CONTROL_ADMIN_KEY` is valid, in-memory fallback otherwise.
- **Databases page** now shows an actionable amber banner ("Start the Docker stack") instead of a raw "Failed to fetch" when the orchestrator is unreachable.

---

## Shipped Defaults

- `MISSION_FLOW_V2_ENABLED=true` by default in `.env.example`, `deploy/docker-compose.yaml`, and `services/orchestrator/orchestrator/settings.py`.
- `LANGGRAPH_ENABLED=false` by default. The LangGraph lifecycle remains optional and is not the shipped default path.
- OpenAI coding defaults now use `gpt-5.3-codex` for VC and OpenAI-backed specialist routes. `gpt-5.5` is configured for OpenAI operations and executive routing after official OpenAI model-catalog verification on 2026-05-17. Anthropic deep-audit routes use `claude-opus-4-7`, Sonnet workhorse routes use `claude-sonnet-4-6`, and Gemini deep-reasoning routes use `gemini-3.1-pro-preview` with preview lifecycle called out for promotion governance. Deterministic no-key delegation smoke coverage is available through `scripts/smoke_ceo_delegation.py`.
- PM intake now produces `feature_contract` and schema-validated `mission_charter` metadata through LLM-or-fallback generation during Mission Flow v2. Chain trace exposes both artifacts for Mission Control/API consumers.
- Mission Control Chat now previews PM feature contracts through the routed backend PM endpoint (`/api/pm/feature-contract` -> `/v1/pm/feature-contract` -> `/internal/pm/feature-contract`) and keeps the local builder preview as an offline fallback.
- CEO delegation now produces a durable `mission_contract` after routing. The contract is stored in mission metadata, audit logged, exposed in chain trace, and uses PM feature-contract context when available.
- CEO delegation now decomposes the mission contract into `logic_clusters` with domain, priority, pod-manager, specialist, requirement references, and rationale. Cluster metadata is audit logged, emitted as a chain event, exposed in chain trace, and passed into pod-manager delegation context.
- Phase 8 FETCH now adds an IS-agent `FETCH` lifecycle step. It indexes deterministic bootstrap language docs, mirrors them into mission-scoped knowledge, exposes `fetch_result` in chain trace, and lets pod workers pass documentation context into extraction.
- Phase 9 FUSION now folds pod group standards into `master_logic_stream`, exposes that stream in chain trace/Mission Control, and uses it to replace missing or fallback generated output when code generation is eligible.
- Phase 14 dependency absorption now creates `dependency_inventory`, `dependency_classification_report`, `dependency_absorption_report`, and `dependency_survival_justifications` metadata for dependency-bearing missions. Safety-blocked families are retained/wrapped/pinned, small pure utilities can receive advisory replacement plans, and Mission Control renders the evidence.
- Pod workers now consume CEO logic-cluster domain focus during extraction and boost matching concept confidence for the assigned pod.
- Pod managers now produce `pod_group_standards` during the Mission Flow v2 GATING phase. Standards consolidate specialist LogicNodes into canonical pod-level nodes, record duplicate elimination counts, emit `MISSION_POD_GROUP_STANDARD_PRODUCED`, and are exposed through chain trace and Mission Control.
- Specialist planning now attempts narrow contract-driven generated-output creation for non-`ANALYZE_ONLY` missions. Successful LLM output is stored as `metadata.generated_output`; fallback output is marked as fallback and is not packaged as a successful generated-code artifact.
- Build artifact packaging now prefers valid `generated_output` and writes a `generated_code` artifact; otherwise it preserves the existing source-bundle artifact path. API Gateway exposes `GET /v1/missions/{mission_id}/artifact?artifact_type=generated_code` for generated artifact download.
- Mission Detail now displays PM feature contracts, mission charters, CEO mission contracts, logic clusters, pod group standards, generated output metadata, generated code preview text when available, and a generated-code download action.
- `services/orchestrator/orchestrator/runtime.py` executes mission flow via the `LifecycleEngine` protocol (Phase 5):
  1. `MissionFlowV2Engine` when `MISSION_FLOW_V2_ENABLED=true`
  2. `LangGraphEngine` when v2 is disabled and `LANGGRAPH_ENABLED=true`
  3. `LegacyV1Engine` fallback (compatibility shim preserving the original inline code path)
- Engine selection is centralized in `lifecycle_interface.get_lifecycle_engine(settings)` — the runtime no longer contains an inline `if/elif/else` branch.

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
- Mission intake now resolves and persists a durable `project_id`; reporting no longer depends on deriving a fake project boundary from `metadata.source`.
- Dynamic scaling is now wired end-to-end behind `AGENT_SCALING_ENABLED`: the orchestrator computes partition work, emits `mission.partition.ready`, pod-workers execute partitions, results are merged into mission metadata, and lifecycle resumes once all partitions complete.

### Audit flow

- The audit worker consumes `missions.state`, not a separate `missions.audit` stream.
- Audit results are persisted through the orchestrator audit-report path into `mission_audit_reports`.
- The orchestrator now maintains an append-only `agent_action_events` ledger keyed by `project_id`, `mission_id`, and `agent_id`.
- Audit events capture mission creation/state updates, pod assignment, LogicNode writes, knowledge writes, audit reports, partition results, agent execution start/end, and worker tool/HTTP usage.
- Audit rows carry `trace_id`, `span_id`, per-project digest chaining, payload summaries, and optional content hashes or blob references.
- New operator-facing APIs exist at `/v1/missions/{mission_id}/audit-events` and `/v1/operations/projects/{project_id}/audit-events`.
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
- Mission Control now includes a `Projects` audit surface that renders the per-project agent action timeline from the gateway/orchestrator audit APIs.
- The repository import path is real GitHub metadata/tree ingestion.
- Repository review is now server-backed: Mission Control fetches selected GitHub file content, builds a review artifact with a stable fingerprint, infers `requested_target_language`, and launches repo missions with a real `source_code` bundle.
- Builder review is now server-backed against the local workspace: it selects real files, emits a stable `builder_fingerprint`, produces a grounded patch contract plus `source_code` bundle, and can launch missions from that approved artifact.
- Review approval is now persisted server-side for both Builder and repository review flows through durable orchestrator-backed approval records before mission launch.
- The chat intake page now infers `requested_target_language` from attached files and prompt hints instead of hardcoding `python`.
- The mission detail page now surfaces stored build/package artifacts, including status, digest, storage backend, and size.
- The databases page and some UX copy still lag live backend readiness details.

### Phase 6 UI Enhancements (2026-04-15)

- **Active Runtime vs Conceptual Architecture toggle** (agents page): filters agents by `heartbeat_source === "live"` (or `runtime_class === "shared_worker"` as a fallback when `heartbeat_source` is absent). Operators can switch to Conceptual Architecture view to see the full 38-agent registry.
- **Lifecycle engine badge** (mission detail): derived from `phaseDescriptor.model` and `chainTrace.routing_version`; maps to MissionFlow V2 / LangGraph / Legacy V1. Rendered as a color-coded `.connection-chip` in the Mission Signals panel.
- **Audit Evidence panel** (mission detail): fetches from `/internal/missions/{id}/audit-reports` with `.catch(() => [])` fault tolerance. Renders status chip, score, summary, and findings list per audit report.
- **Feature flag warning banners** (agents page): structured `role="alert"` block in Runtime Dependencies; warns when `consumer_running`, `protocol_ready`, `redis_ready`, or `db_ready` are false, and when `langgraph_enabled === false`. The LangGraph-disabled warning now correctly states that Mission Flow V2 remains the default runtime path.

## Language Extraction Status

- Specialist routing currently covers 20 language keys across four pods. TypeScript is accepted as a routed key but aliases to the JavaScript specialist.
- Go, Haskell, and OCaml are registered in the agent registry, supported by the language extraction engine, and now have dedicated services in the `full-dedicated-agents` profile and `up-full-dedicated` launch target.
- Historical and archived documentation artifacts may still contain older language-count or topology claims, but the canonical docs now reflect the current 20-key routing matrix and full strict dedicated topology.

### Phase 7 Extraction Enhancements (2026-04-15)

- **`ExtractedConcept` provenance fields**: `extraction_method` (`"ast"` | `"regex"`) and `source_range` (`{start_line, end_line}`) added to the dataclass; LogicNode payloads in `pod_worker/main.py` now include these fields.
- **Fixture corpus**: extractor test fixtures externalized to `tests/fixtures/extractors/` (Python sample, JS sample, Java sample).
- **Golden tests** (`test_language_extractor_golden.py`): regression suite locking function/class/concept extraction output for all three languages.
- **AST vs regex comparison report** (`reports/ast_vs_regex_comparison.json`): generated by running both `PythonExtractor` (regex) and `extract_python_ast` (AST) on the Python fixture; both agree on all 6 functions and 2 classes; AST-exclusive: `is_async`, return types, arg types; regex-exclusive: concept catalog matching, parse-resilience.
- **Python AST extractor** (`pod_worker/ast_extractor.py` + `PythonAstExtractor`): available behind `PYTHON_AST_EXTRACTOR_ENABLED=true`; the default shipped extraction path remains regex-first unless that flag is enabled.
- **JS/TypeScript AST extractor** (`pod_worker/js_ast_extractor.py` + `JavaScriptAstExtractor`): active behind `JS_AST_EXTRACTOR_ENABLED=true`; uses `esprima` for structural function/class/import extraction, including class shorthand methods and arrow/function-expression assignments, while preserving regex concept detection and fallback.
- **Java AST extractor** (`pod_worker/java_ast_extractor.py` + `JavaAstExtractor`): active behind `JAVA_AST_EXTRACTOR_ENABLED=true`; uses `javalang` for package/import/class/method/constructor extraction while preserving regex concept detection and fallback.

## Orchestrator Decomposition Status (Phase 5 complete as of 2026-04-14)

- `services/orchestrator/orchestrator/main.py` reduced from **2065 → 1250 → 423 lines** across Phase 3 and Phase 5 extractions.
- **Phase 5 domain modules** extracted from `main.py`:
  - `storage/` — 6-module façade package (`missions.py`, `agents.py`, `artifacts.py`, `knowledge.py`, `audit.py`, `scaling.py`); `storage.py` becomes a thin re-export shim.
  - `heartbeat_service.py` — `_build_non_pod_heartbeat_payloads`, `_emit_agent_telemetry_event`, `agent_heartbeat_loop`.
  - `review_policy.py` — all review approval validation and HMAC-verification logic.
  - `lifecycle_recovery.py` — `_recover_inflight_lifecycle_tasks`.
  - `lifecycle_interface.py` — `LifecycleEngine` Protocol, `MissionFlowV2Engine`, `LangGraphEngine`, `LegacyV1Engine`, `get_lifecycle_engine` factory.
- `models.py` is now the single source of truth for `VALID_TRANSITIONS`; the duplicate copy in `mission_flow_v2.py` was removed.
- All re-exports and backward-compat shims are in place so routes calling `_main.xxx` still resolve.

## Security Hardening (Phase 0–4 complete as of 2026-03-31)

- **PII detection & redaction** (`shared_runtime/pii_guard.py`): SSN, credit card, email, phone, JWT, API key, password KV pairs; integrated at API Gateway in production (`PII_GUARD_MODE=redact`)
- **Prompt injection guard** (`shared_runtime/prompt_guard.py`): system-tag smuggling, INST injection, role-override, jailbreak detection; `PROMPT_GUARD_MODE=block` in production
- **HMAC-signed review approvals**: approval records carry `issued_at`, `expires_at`, HMAC-SHA256 digest; configurable 24h TTL
- **Structured audit log** at API Gateway: every request logged as structured JSON with hashed client IP and trace ID
- **Event replay detection** (`shared_runtime/protocol.py`): in-process `_InProcessReplayGuard` with TTL eviction
- **Message deduplication** in semantic bus: Redis SET NX EX on `correlation_id`; backpressure 503 + `Retry-After: 5` when queue > limit
- **Circuit breaker** in agent-runtime: CLOSED/OPEN/HALF-OPEN state machine; configurable failure threshold and recovery window
- **Secret hygiene**: gitleaks full-history scan, `.pre-commit-config.yaml` with staged-secret protection, `.gitleaks.toml` custom patterns

## Validation Snapshot

As of 2026-05-18:

- `python -m pytest -q` is green after the Phase 7 extractor work.
- All new Phase 5–7 modules have unit test coverage (lifecycle engine protocol, heartbeat service, storage façade, extractor provenance fields, golden tests, AST vs regex comparison).
- `apps/mission-control` TypeScript check is green (`tsc --noEmit`, 0 errors).
- `apps/mission-control` unit tests are green (`npm test`, **55 tests**, 15 test files).
- `apps/mission-control` Playwright: original 7 tests plus 13 new extended tests from Phase 1 E2E expansion.
- Repository-wide `python -m ruff check services tests scripts` is green.
- Orchestrator `main.py` reduced from **2065 → 423 lines** via route decomposition (Phase 3) and domain module extraction (Phase 5).
- Targeted post-audit-rollout verification is green:
  - `python -m ruff check services tests scripts`
  - `python -m pytest -q tests/services/test_api_gateway_helpers_unit.py tests/services/test_storage_unit.py tests/services/test_orchestrator_endpoints_extra.py tests/services/test_runtime_unit.py tests/services/test_lifecycle_interface_unit.py tests/services/test_mission_flow_v2.py tests/services/test_orchestrator_main_helpers_unit.py tests/services/test_language_extractor_golden.py`
  - `npm --prefix apps/mission-control run lint`
  - `npm --prefix apps/mission-control run test`
- Phase 6 focused validation is green:
  - `python -m pytest tests\services\test_llm_delegation_unit.py tests\services\test_mission_flow_v2.py tests\services\test_orchestrator_endpoints_extra.py -q`
  - `python -m ruff check services\orchestrator\orchestrator\llm_delegation.py services\orchestrator\orchestrator\mission_flow_v2.py services\orchestrator\orchestrator\routes\internal.py tests\services\test_llm_delegation_unit.py tests\services\test_mission_flow_v2.py tests\services\test_orchestrator_endpoints_extra.py`
  - `npm --prefix apps\mission-control run lint`
- Phase 7 focused validation is green:
  - `python -m pip install javalang==0.13.0 esprima==4.0.1`
  - `python -m pytest tests\services\test_language_extractor_golden.py tests\services\test_language_extractor.py -q`
  - `python -m ruff check services\pod-worker tests\services\test_language_extractor_golden.py`
- Phase 8/9 focused validation is green:
  - `python -m pytest tests\services\test_mission_flow_v2.py tests\services\test_orchestrator_endpoints_extra.py tests\services\test_pod_worker_unit.py tests\services\test_language_extractor.py tests\services\test_llm_delegation_unit.py -q`
  - `python -m ruff check services\orchestrator\orchestrator services\pod-worker tests\services\test_mission_flow_v2.py tests\services\test_orchestrator_endpoints_extra.py tests\services\test_pod_worker_unit.py tests\services\test_language_extractor.py tests\services\test_llm_delegation_unit.py`
  - `npm --prefix apps\mission-control run lint`
- Phase 10 focused validation is green:
  - `python -m pytest tests\services\test_mission_flow_v2.py tests\services\test_orchestrator_endpoints_extra.py tests\services\test_build_artifacts_unit.py tests\services\test_llm_delegation_unit.py -q`
  - `python -m ruff check services\orchestrator\orchestrator tests\services\test_mission_flow_v2.py tests\services\test_orchestrator_endpoints_extra.py tests\services\test_build_artifacts_unit.py tests\services\test_llm_delegation_unit.py`
  - `npm --prefix apps\mission-control run lint`
- Phase 14 focused validation is green:
  - `python -m ruff check services\orchestrator\orchestrator\dependency_absorption.py services\orchestrator\orchestrator\mission_flow_v2.py services\orchestrator\orchestrator\routes\internal.py tests\services\test_dependency_absorption_unit.py tests\services\test_mission_flow_v2.py tests\services\test_orchestrator_endpoints_extra.py`
  - `python -m pytest tests\services\test_dependency_absorption_unit.py tests\services\test_mission_flow_v2.py tests\services\test_orchestrator_endpoints_extra.py tests\services\test_security_compliance_unit.py tests\services\test_equivalence_verifier_unit.py -q`
  - `npm --prefix apps\mission-control run lint`
  - `npm --prefix apps\mission-control run test`
- Full post-Phase-7 validation is green:
  - `python -m ruff check services tests scripts`
  - `python -m pytest -q`
  - `npm --prefix apps\mission-control run lint`
  - `npm --prefix apps\mission-control run test`
- Strict full-dedicated live qualification is green:
  - `python scripts/mission_artifact_qualification.py --profile-label full-dedicated-local-2026-04-15 --output-file docs/evidence/mission_artifact_qualification_full_dedicated_local_2026-04-15.json --history-file docs/evidence/mission_artifact_qualification_history.jsonl`
  - `python scripts/dedicated_agent_canary_rollout.py --profile-label full-dedicated-local-2026-04-15 --output-file docs/evidence/dedicated_agent_canary_full_dedicated_local_2026-04-15.json`

The repository should therefore be treated as a strong local development baseline with defense-in-depth security hardening and improved maintainability. It is not yet launch-complete because the live provider-key demo, stale qualification-evidence refresh, and remaining forward-looking docs cleanup are still open.

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

1. Implement Phase 15 token/cost ledger before making cost or budget claims.
2. Complete a live provider-key BUILD_NEW demo through the implemented PM/CEO/FETCH/FUSION/DELIVERY/AIM/equivalence/security-compliance/dependency loop.
3. Refresh stale qualification evidence before launch claims.
4. Update the remaining Mission Control data-plane surfaces and copy to reflect live optional-adapter readiness.
5. Extend build/package execution beyond source-bundle packaging to any future binary/container/package builders and wire those outputs into the same artifact contract.
6. Automate strict full-dedicated smoke qualification in CI or scheduled qualification runs so topology regressions fail earlier.
7. Execute the remaining release phases in [`RELEASE_COMPLETION_PLAN.md`](RELEASE_COMPLETION_PLAN.md), including AI safety governance, shared-state durability, DR evidence, and final release qualification.
8. `test_storage_unit.py` requires a live `postgres` host when run as an integration test; run it in a Docker-compose integration environment when validating storage against live Postgres.
9. `test_agent_base_unit.py` has a pre-existing broken import; excluded pending upstream fix.
