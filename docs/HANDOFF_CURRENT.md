# Current Handoff

Document version: 2026.06.16-b
Last updated: 2026-06-16
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

Use this file, `docs/CURRENT_TODO.md`, and `docs/IMPLEMENTATION_STATUS.md`
before consulting archived plans.

---

## Current Branch State

- Branch: `main` — pushed and in sync with `origin/main`.
- **CI is fully green** as of `941aca9` (run conclusion `success`, all 12 jobs):
  Lint and Test, all 7 Docker Build Validation jobs, SBOM, Performance Smoke,
  Electron E2E Smoke, and Release Trust and Promotion Gate. Security Checks green.
- All extended data stores (Milvus, Neo4j, MinIO/object storage) now on by
  default in code, compose, and the dev overlay.
- Live stack verified healthy 2026-06-16: gateway `/health` ok, `/readyz` 200; operations summary reports db/redis/qdrant/milvus/neo4j/object_storage/jaeger all ready; 41/41 agents healthy.
- Current change set: EDCP-01 bus durability foundation, EDCP phase planning,
  PM clarification gating, richer PM planning artifacts, unlocked-local UX
  cleanup, embedding key UI, live agent validation, and runtime label polish.
- All tests pass (except `test_agent_base_unit.py` which requires the orchestrator
  package on PYTHONPATH — it always fails in isolation; run from
  `services/orchestrator/` or via the services test runner).
- Runtime model policy: all 41 agents default to `gemini/gemini-3.5-flash` with
  high thinking.
- Mission Control model selector: ChatGPT 5.5, Claude Opus 4.8, Gemini Flash 3.5.
- Mission Control local mode starts unlocked. PM/review proxy routes use the
  internal service key from stack configuration; there is no user-facing
  Operator Runtime Key vault row.
- Agent grid runtime labels:
  - `WORKER`: shared pod-worker runtime for specialists, pod managers, and pod audits.
  - `MANAGED`: orchestrator-managed interface/executive/support role heartbeat.
  This is intentional in the condensed local topology; dedicated per-agent
  containers are optional deployment scope, not a current requirement.

---

## Work Completed in This Session (2026-06-16 — Data Stores On-by-Default, Vault Auth Fix, Full CI Green)

### Extended data stores enabled by default
- `settings.py`, `docker-compose.yaml`, and `docker-compose.dev.yaml`: `milvus_enabled`,
  `neo4j_enabled`, `object_storage_enabled` flipped `False → True` everywhere; removed
  the dev overlay's hard `NEO4J_ENABLED=false`/`OBJECT_STORAGE_ENABLED=false` overrides.
- Docs reconciled (README, SETTINGS_REFERENCE, DEVELOPER_ONBOARDING, ARCHITECTURE,
  COMPOSE_ENVIRONMENT_PROFILES, IMPLEMENTATION_STATUS, DOCUMENTATION_INDEX).

### Mission Control databases page "not authorized" — root caused and fixed
- The databases page is healthy; the failure was the **standalone UI on :3000**
  sending a **stale `OPERATOR-API-KEY`** from the host vault
  (`~/.thefactory/vault.json`) which the gateway rejected (401 "invalid api key").
  The Docker UI on :3100 worked because its vault volume was wiped by `down -v`.
- Removed the stale vault slot (host-side, backup saved).
- **Self-heal code fix** (`apps/mission-control/app/api/gateway/[...path]/route.ts`):
  the proxy now retries with `INTERNAL_SERVICE_API_KEY` on a 401/403 from a stale
  operator key, so this can't silently break the operations/databases views again.

### Full CI remediation (was red for many commits; now green)
- **Dependabot**: `vite 8.0.10 → 8.0.16`, `tmp 0.2.6 → 0.2.7` (cleared 3 alerts).
- **E2E**: 4 specs updated to click the Phase 2B mission-detail tabs
  (execution/artifacts/contracts/events) before asserting panels in inactive
  (`hidden`) tabs.
- **Python import**: `runtime.py` now imports `current_vault_secrets` from
  `.llm_delegation.config` (matching the rest of the codebase) — fixed 7 ImportErrors.
- **Lint**: import-block ordering (ruff I001).
- **Coverage**: added `_llm_recommendation_for_agent` branch test to restore
  `agent_integrations.py` to 100%.
- **Release Trust**: build-provenance attestation now skipped on private repos
  (feature unavailable) and run normally on public/org repos.

### Known remaining items (not failures)
- 1 Dependabot **medium** alert: `js-yaml ≤4.1.1`, dev-only transitive via
  `@lhci/cli` (Lighthouse, pins js-yaml 3.x) and `@redocly/openapi-core`. Cannot be
  force-upgraded without breaking the Performance Smoke step; resolve when `@lhci/cli`
  adopts js-yaml 4.x. Does not affect the shipped app.
- CodeQL/code scanning is not enabled (requires GHAS on private repos); several
  actions still target the deprecated Node 20 runner (auto-forced to Node 24).
  Both are non-blocking; deferred.

---

## Work Completed Earlier This Session (2026-06-16 — Runtime Connectivity, PM Assumptions, Health Redaction)

### Standalone UI "Runtime offline / databases not connected" — root caused and fixed

**Problem:** The standalone Mission Control UI (the non-container instance on
port 3000 launched by `start_app.bat`) reported "Runtime offline — Orchestrator
unreachable at port 8100", and the Databases page showed every adapter as
Disabled/Degraded. The backend was actually fully healthy: `docker ps` showed
the gateway, orchestrator, Postgres, Redis, Qdrant and all 41 agents up, and
`curl 127.0.0.1:8100/health` returned `ok:true` with `redis_healthy:true`.

**Root cause:** `start_app.bat` assembled `MISSION_API_BASE_URL` as
`http://127.0.0.1:%_GW_PORT%` *inside* a cmd `if (...)` block, where `%_GW_PORT%`
expands at parse time — before the `set "_GW_PORT=8100"` line in the same block
runs. `API_GATEWAY_HOST_PORT` is not in `.env`, so the result was a portless URL
`http://127.0.0.1:` → port 80 → the Next.js proxy's upstream `fetch` threw →
`/api/gateway/*` returned 503. The Databases page renders every adapter flag as
"Disabled" and Redis/Postgres as "Degraded" whenever the operations-summary
fetch fails, so the screenshot statuses were UI fallback artifacts, not real
backend state.

| File | Change |
|------|--------|
| `start_app.bat` | Assemble `MISSION_API_BASE_URL` as a standalone statement after `_GW_PORT` is set, outside the `if`-block, so the port is included |
| `apps/mission-control/app/api/gateway/[...path]/route.ts` | Hardened `DEFAULT_GATEWAY_BASE` from `http://localhost:8100` to `http://127.0.0.1:8100` so an unset env cannot hit the Windows IPv6 (`::1`) path |

**Verification:** Container UI proxy (`:3100`) returns 200; live operations
summary confirms `db_ready`, redis/protocol, `qdrant_ready`, `milvus_ready`,
`neo4j_ready`, `object_storage_ready`, and `jaeger_ready` all `True`. Commit
`04e4fef`. The running :3000 process still has the stale env until
rebuilt/restarted.

### PM feature-contract `assumptions` field now persisted

**Problem:** The PM prompt asks the model for an `assumptions` list, but the
normalizer and deterministic fallback dropped it, so the field never reached the
mission charter.

| File | Change |
|------|--------|
| `services/orchestrator/orchestrator/llm_delegation/normalizers.py` | Persists `assumptions` (string list, limit 6) on the normalized contract |
| `services/orchestrator/orchestrator/llm_delegation/fallbacks.py` | Sets `assumptions: []` on the deterministic fallback contract |

**Verification:** Ruff clean for the four `llm_delegation` files. Commit `f726de4`.

### api-gateway `/health` no longer leaks the Redis password

**Problem:** `GET /health` returned `redis_url` verbatim, including the Redis
password in the URL userinfo.

| File | Change |
|------|--------|
| `services/api-gateway/api_gateway/main.py` | Added `_redact_url_credentials()`; `/health` now returns `rediss://:***@redis:6380/...` with host/port/cert path preserved |

**Verification:** Ruff clean; redaction confirmed on a sample URL. Commit `d743d4e`.

### Pending before next run

- These three commits (`f726de4`, `04e4fef`, `d743d4e`) are **local only** —
  push to origin when approved.
- The standalone :3000 UI must be rebuilt/restarted to pick up `04e4fef`
  (operator is orchestrating stop → rebuild → restart). The `orchestrator`,
  `api-gateway`, and `mission-control` images should be rebuilt so all three
  commits are baked into the running stack.
- The Gemini live BUILD_NEW proof (S1-01) is still the gate before any
  EDCP-02+ load-bearing control-plane work.

---

## Work Completed in This Session (2026-06-14, batch 2 — EDCP Plan + PM Intake Corrections)

### EDCP-01 Bus Durability Foundation

**Problem:** EDCP could not safely make Protocol Bus events load-bearing while
the orchestrator consumer only used non-durable `XREAD` from `$`.

| File | Change |
|------|--------|
| `services/orchestrator/orchestrator/protocol_bus_consumer.py` | Added opt-in consumer-group mode with `XGROUP CREATE`, `XREADGROUP`, and `XACK`; legacy `XREAD` remains default |
| `services/orchestrator/orchestrator/protocol_bus_producer.py` | Added `send_omega_message`, `send_beta_result`, and `send_delta_audit` helpers |
| `services/orchestrator/orchestrator/settings.py` | Added `event_driven_control_plane_enabled` defaulting false |
| `.env.example`, `deploy/docker-compose.yaml` | Added `EVENT_DRIVEN_CONTROL_PLANE_ENABLED=false` |
| `tests/services/test_protocol_bus_consumer.py` | Added grouped consumption, ack/non-ack, and schema-validation tests |

**Validation:** `test_protocol_bus_consumer.py` and
`test_orchestrator_agent_key_mode.py` pass; Ruff passes for touched Python
files. EDCP-02 through EDCP-05 remain pending.

### Event-Driven Control Plane Phase Plan

**Problem:** The current mission lifecycle is a direct in-process function
pipeline; Protocol Bus messages are mostly telemetry rather than the command
backbone.

| File | Change |
|------|--------|
| `docs/EDCP_Phase_Plan.md` | Added phased plan EDCP-01 through EDCP-05: bus durability, missing lane senders, PM to CEO handoff, CEO to pod Alpha promotion, support-ring Delta gates, and final demotion of `missions.state` to projection-only |

**Key rule:** EDCP-01 foundation is complete. Do not start EDCP-02 or later
load-bearing control-plane inversion until a live Gemini BUILD_NEW mission
reaches COMPLETE with non-empty generated code.

### PM Intake Clarification + Planning Package

**Problem:** The PM Agent could turn a detailed but underspecified request into
a generic launchable plan without asking clarifying questions.

| File | Change |
|------|--------|
| `services/orchestrator/orchestrator/llm_delegation/normalizers.py` | Preserves `intake_status` from PM model output |
| `services/orchestrator/orchestrator/llm_delegation/text.py` | Treats `intake_status=needs_clarification` as authoritative for ambiguity scoring |
| `services/orchestrator/orchestrator/mission_flow_v2/base.py` | Adds SOW, product requirements, phased build plan, risk register, and test strategy fields to mission charters |
| `apps/mission-control/app/(shell)/chat/page.tsx` | Shows clarifying questions instead of creating a launchable contract when PM says scope is not ready |
| `apps/mission-control/app/(shell)/settings/page.tsx` | Removes the user-facing Operator Runtime Key vault row |

**Validation:** Focused PM/mission-flow Python suite passed: 125 tests. Ruff
passed for touched orchestrator packages and tests.

---

## Work Completed in This Session (2026-06-14, batch 1 — UI Polish: Mission Output, Navigation & Editing)

### Mission Output Folder Browser + Dedicated Workspace

**Problem:** Completed missions had no clear path to find the generated code or
release the product. The mission detail page showed metadata only, with no
artifact browser or download/release action accessible from the main UI.

| File | Change |
|------|--------|
| `apps/mission-control/app/(shell)/missions/detail/page.tsx` | Added **Artifacts** tab with full folder tree browser: collapsible directories, file icons by extension, copy-to-clipboard and full text preview per file; release flow wired to download endpoint |
| `apps/mission-control/app/api/missions/[id]/artifacts/route.ts` | New `GET` route returning structured artifact manifest (path, size, type) from the orchestrator artifacts store |
| `services/api-gateway/main.py` | Fixed 404 on `/v1/missions/{id}/artifacts` — route was missing; now delegates to orchestrator artifact list endpoint |
| `apps/mission-control/app/(shell)/missions/detail/page.tsx` | Sub-tabs (Overview / Artifacts / Logs / LogicNodes) now fully wired: active tab renders correct panel, stale empty-state replaced |

**Validation:** TypeScript `--noEmit` clean; `npm run build` passed.

---

### Auto-Expanding Sidebar (Chat page)

**Problem:** The Conversations sidebar on the Chat page was hidden/pushed off-screen
when sidebar content overflowed, wasting horizontal space in the main body.

| File | Change |
|------|--------|
| `apps/mission-control/app/globals.css` | `.chat-history-sidebar` changed from fixed `width: 240px` to `flex: 0 0 240px; min-width: 0; overflow: hidden` so it never overflows its grid cell; `.chat-history-item-title` constrained with `max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap` so long titles no longer cause layout blowout |

---

### Feature Contract Edit Modal

**Problem:** Clicking **Edit** on the Feature Contract panel opened a cramped
inline form with a 3-row textarea — insufficient for long mission descriptions.

| File | Change |
|------|--------|
| `apps/mission-control/app/(shell)/chat/page.tsx` | Added `editTitle`, `editLanguages`, `editScope` state; Edit button pre-populates these and sets `editingContract=true`; inline form removed and replaced by full-screen modal rendered inside the page root div |
| `apps/mission-control/app/globals.css` | Added `.contract-edit-backdrop` (fixed full-screen, blurred overlay), `.contract-edit-modal` (760 px max, 90 vh, spring animation), header/body/footer/input/textarea classes with focus rings; responsive sheet-from-bottom on mobile |

**Modal behaviours:** Escape key, backdrop click, and Cancel button all close
without saving. Save applies `sanitizeUserText` to Title/Languages and trims
Scope before writing back to contract state.

**Validation:** TypeScript `--noEmit` clean; `npm run build` passed.

---

### UI Auth and Settings Fixes

**Problem:** The UI Settings page falsely reported "Runtime offline" and the Databases page reported "Not authorized" because the local Next.js proxy was missing the `INTERNAL_SERVICE_API_KEY` for internal orchestrator routes. The "Real embeddings are off" warning was also hardcoded to always display.

| File | Change |
|------|--------|
| `apps/mission-control/app/api/gateway/[...path]/route.ts` | Modified the proxy to inject `INTERNAL_SERVICE_API_KEY` from the server environment for `/internal/*` routes. |
| `apps/mission-control/app/(shell)/settings/page.tsx` | Conditionally displays the embedding warning (now shows a success badge if the vault slot is set), and `orchestratorOffline` is now only triggered on actual network errors (503 or fetch failure). |
| `start_app.bat` | Exports `INTERNAL_SERVICE_API_KEY` and `MISSION_API_BASE_URL` into the spawned Next.js dev/prod server process so server-side API routes have the key available when running outside Docker. |

**Validation:** UI renders correctly and authenticates against the orchestrator.

---

## Work Completed in This Session (2026-06-13, batch 3)

### Mission Control Operator Recovery + Key Setup

**Problem:** PM Agent chat failed with `Operator authentication required` and a
fallback timeout, leaving the operator without a recovery path. Settings
documented embedding environment variables but did not expose an embedding key
slot in the vault table.

| File | Change |
|------|--------|
| `apps/mission-control/app/(shell)/chat/page.tsx` | Converts runtime auth/key failures into a local-stack recovery message |
| `apps/mission-control/app/api/pm/feature-contract/route.ts` | Internal service key fallback routes PM feature-contract calls without a user-facing operator key slot |
| `apps/mission-control/app/(shell)/settings/page.tsx` | Renders operator unlock, adds `KNOWLEDGE-EMBEDDING-API-KEY` vault row, and adds a Knowledge Embeddings configure action |
| `apps/mission-control/app/lib/server/vault.ts` | Preserves embedding model metadata (`gemini-embedding-001`, `text-embedding-3-*`) |
| `apps/mission-control/app/(shell)/agents/page.tsx` | Renames confusing `SYNTHETIC` badge to `MANAGED` and uses neutral styling |

**Validation:** `npm --prefix apps/mission-control run lint`, focused vault
Vitest suite, and `npm --prefix apps/mission-control run build` passed locally.
Live backend validation also passed after starting the full dedicated stack:
`/v1/operations/agents` returned 41/41 agents with `heartbeat_source=live`,
all in `IDLE`; runtime readiness showed Redis, PostgreSQL, Qdrant, Milvus,
Neo4j, object storage, protocol validation, and consumer task ready/running.
The local Google test key was saved to `KNOWLEDGE-EMBEDDING-API-KEY` and a
real Gemini `gemini-embedding-001:embedContent` call returned a 3072-dimension
embedding vector.

---

## Work Completed in This Session (2026-06-13, batch 2)

### Commit `d52d978` — Knowledge Embedding Key + Semantic Search Gate

**Problem:** No way to set a separate API key for embedding calls; semantic search
enabled even when no real key was available (deterministic SHA-256 hash vectors were
being written to Qdrant silently).

| File | Change |
|------|--------|
| `settings.py` | Added `knowledge_embedding_api_key: str = ""` field; `qdrant_vector_size` default raised 64 → 256 |
| `knowledge_embeddings.py` | `_gemini_embedding` and `_openai_embedding` now prefer `KNOWLEDGE_EMBEDDING_API_KEY`; added `task_type` parameter to `_gemini_embedding` and `vector_for_content` |
| `knowledge_lake.py` | New `_embedding_key_available()` helper; `_semantic_search_enabled()` now requires all three: Qdrant enabled + real provider + non-empty key |
| `deploy/docker-compose.yaml` | Wired `KNOWLEDGE_EMBEDDING_API_KEY` env var; `QDRANT_VECTOR_SIZE` default raised to 256 |
| `apps/mission-control/app/(shell)/settings/page.tsx` | New "3. Knowledge Embeddings" UI panel explaining env vars; old sections 3/4 renumbered to 4/5 |

### Commit `bdf73b2` — Query Embedding Task Type + LangGraph PgBouncer Guard + Doc Reconciliation

**Problem 1:** `_vector_search` was passing `content={"language": ..., "concept": ...}`
(no `combined_text` key) to `vector_for_content`, causing `_content_text()` to
JSON-serialize the dict and send it as the query text to Gemini. Also, it used
`RETRIEVAL_DOCUMENT` (indexing task type) instead of `RETRIEVAL_QUERY` for search
queries — semantically wrong embeddings.

**Problem 2:** `langgraph_lifecycle.py` silently fell back to `settings.postgres_url`
(PgBouncer in transaction-pool mode) when `LANGGRAPH_CHECKPOINTER_POSTGRES_URL` was
not set. PgBouncer transaction-pool drops session-level advisory locks between
statements, silently corrupting LangGraph checkpoint state.

**Problem 3:** `docs/KNOWLEDGE_LAKE_AND_EMBEDDINGS.md` described a fictional
`KnowledgeLake` class with `write/query/get_graph/purge` methods that don't exist.
`docs/STORAGE_LAYER.md` listed fictional module names (`storage_events.py`,
`storage_approvals.py`) instead of the actual five domain modules.

| File | Change |
|------|--------|
| `knowledge_lake.py` | Fixed `_vector_search`: `content={"combined_text": concept_key}`, `task_type="RETRIEVAL_QUERY"` |
| `langgraph_lifecycle.py:683` | Replaced silent PgBouncer fallback with explicit guard: logs CRITICAL and returns False when URL is empty |
| `docs/KNOWLEDGE_LAKE_AND_EMBEDDINGS.md` | Complete rewrite — module-level API, Postgres-first design, embedding pipeline, semantic search gate, `task_type` usage |
| `docs/STORAGE_LAYER.md` | Complete rewrite — accurate module list, correct table names (`mission_state_events`, `mission_pod_assignments`, `mission_knowledge`, `agent_runtime_heartbeats`, `agent_action_events`), accurate function tables |
| `README.md` | Data Systems table: Milvus/Neo4j/MinIO changed from `✅ Active` to `⚙️ Integrated / off by default` |

### Commit `c07da61` — Knowledge Lake Unit Tests (previously zero coverage)

| File | Tests added |
|------|-------------|
| `tests/services/test_knowledge_lake_unit.py` | **37 new tests** — `_embedding_key_available`, `_semantic_search_enabled`, `is_stocked`, `index_documentation`, `_mirror_to_qdrant`, `query_documentation` routing, `_vector_search` RETRIEVAL_QUERY regression, `_keyword_search`, `get_language_context` |
| `tests/services/test_knowledge_embeddings_unit.py` | +5 tests: Gemini happy path, `task_type` forwarding captured from HTTP body, `KNOWLEDGE_EMBEDDING_API_KEY` overriding both `GEMINI_API_KEY` and `OPENAI_API_KEY` |
| `tests/services/test_langgraph_lifecycle_unit.py` | +1 test: empty `LANGGRAPH_CHECKPOINTER_POSTGRES_URL` must return False, not fall back to PgBouncer |

### Commit `44cb9c8` — Multiagent System Bug Fixes (silent failures)

A structured audit of all 41 agents, state machine, Redis routing, heartbeat
infrastructure, and protocol bus identified four files with bare `except Exception`
blocks that swallowed failures with no log output:

| File | Fix |
|------|-----|
| `is_agent.py:182,199` | `_knowledge_is_indexed` and `_knowledge_is_current` now log DEBUG on storage errors; was silently returning False, masking Postgres outages |
| `dependency_absorption.py:966` | DEPABS LLM replacement failure now logs WARNING with language/library; added missing `logging` module + `LOGGER`; returns `{"error": str(exc)}` instead of empty dict |
| `knowledge_embeddings.py:68` | Cost-ledger outer except now logs DEBUG (was `pass`) |
| `port_coordinator.py:189,207` | AIM extraction and specialist plan fallbacks now log WARNING with `mission_id` |
| `port_coordinator.py` return | Added `extraction_degraded: bool` to `coordinate_port_extraction()` return value so RQCA/downstream agents know when fidelity is reduced |

---

## Verified Healthy (from audit)

- **State machine** — `models.py:152-193` — 13 states, no dead ends, no orphan states,
  all transitions bidirectional for v1/v2 compatibility
- **Agent registry** — `agent_registry.py` — all 41 agents with correct IDs, categories,
  pod assignments, language mappings
- **Redis stream routing** — `protocol_bus_consumer.py` — XREAD/XADD/XREADGROUP
  correctly wired; 6 protocol lanes (alpha/beta/delta/sigma/omega/rho)
- **Heartbeat infrastructure** — `heartbeat_service.py` — synthetic heartbeats fire on
  schedule; stale consumer reaping implemented
- **Agent dispatch** — `agent-runtime/main.py` (support agents) and
  `pod-worker/main.py` (specialists) correctly import and call `make_agent().execute()`

**Architectural note:** The orchestrator is a pure state-machine router — it does not
call `make_agent()` directly. Agents execute out-of-process in `agent-runtime` and
`pod-worker`. This is intentional (microservice decomposition) but means: if
`agent-runtime` is down, support-agent missions stall with no in-process fallback.

---

## Remaining Open Issues (see `docs/CURRENT_TODO.md`)

Four HIGH items from the multiagent audit are not yet fixed:

1. **No startup agent health check** — AGENT_REGISTRY is never cross-referenced
   against live heartbeats at boot. If `agent-runtime` is down, missions accept and
   route but never complete.
2. **LangGraph thread ID collision on replay** — thread_id is `{prefix}:{mission_id}`,
   so replaying a mission ID merges checkpoint state with the original run.
3. **Heartbeat interval mismatch** — orchestrator pulses every 5 s
   (`AGENT_HEARTBEAT_INTERVAL_SECONDS`); `agent-runtime` defaults to 15 s. The
   stale threshold must exceed the agent-runtime interval.
4. **Sigma lane handler binding — VERIFIED 2026-06-16.** `main.py`
   `protocol_bus_consumer_loop` registers `handlers = {"sigma": _handle_sigma_knowledge_ready}`
   on a `ProtocolBusConsumer` (agent `AGENT-03-BROKER`), guarded by
   `PROTOCOL_BUS_CONSUMER_ENABLED`. Binding path confirmed end-to-end.

---

## Watch Items

- `test_agent_base_unit.py` requires the orchestrator on `sys.path` — it fails under
  the root `pytest` invocation. Run as `cd services/orchestrator && python -m pytest`
  or add `services/orchestrator` to `PYTHONPATH`.
- The OTel/Jaeger exporter logs `Failed to export span batch` during test teardown
  because Jaeger is not running locally. This is harmless — the exporter retries and
  drops on shutdown. It does not affect test results.
- Archived docs under `docs/archive/2026-06-13/` are historical only. Do not
  resurrect them as active work without reconciling into `CURRENT_TODO.md`.
