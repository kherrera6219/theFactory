# Current Handoff

Document version: 2026.06.14-a
Last updated: 2026-06-14
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

Use this file, `docs/CURRENT_TODO.md`, and `docs/IMPLEMENTATION_STATUS.md`
before consulting archived plans.

---

## Current Branch State

- Branch: `main`
- Current change set: Mission Control operator setup, embedding key UI, live
  agent validation, and runtime label polish.
- All tests pass (except `test_agent_base_unit.py` which requires the orchestrator
  package on PYTHONPATH — it always fails in isolation; run from
  `services/orchestrator/` or via the services test runner).
- Runtime model policy: all 41 agents default to `gemini/gemini-3.5-flash` with
  high thinking.
- Mission Control model selector: ChatGPT 5.5, Claude Opus 4.8, Gemini Flash 3.5.
- Mission Control privileged PM/review flows require both an operator unlock
  session and `OPERATOR-API-KEY` saved in the vault.
- Agent grid runtime labels:
  - `WORKER`: shared pod-worker runtime for specialists, pod managers, and pod audits.
  - `MANAGED`: orchestrator-managed interface/executive/support role heartbeat.
  This is intentional in the condensed local topology; dedicated per-agent
  containers are optional deployment scope, not a current requirement.

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

## Work Completed in This Session (2026-06-13, batch 3)

### Mission Control Operator Recovery + Key Setup

**Problem:** PM Agent chat failed with `Operator authentication required` and a
fallback timeout, leaving the operator without a recovery path. Settings
documented embedding environment variables but did not expose an embedding key
slot in the vault table.

| File | Change |
|------|--------|
| `apps/mission-control/app/(shell)/chat/page.tsx` | Converts operator auth/key failures into a user-facing recovery message with an `Open Settings` action |
| `apps/mission-control/app/api/pm/feature-contract/route.ts` | Missing `OPERATOR-API-KEY` now returns actionable setup guidance |
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
4. **Sigma lane handler binding unverified** — the sigma (knowledge-ready) lane is
   defined in `protocol_bus_consumer.py` but the handler registration path was not
   confirmed end-to-end in the audit.

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
