# theFactory — Updated Completion TODO

**Last updated:** 2026-03-14

---

## ✅ Documentation Alignment (Completed 2026-03-13)

All of the following code-vs-docs mismatches have been fixed:

- [x] README: Audit badge → 17/17 (was 13/13)
- [x] README: Pod A agent table — added TypeScript
- [x] README: Extraction table — removed Go from Pod B, Haskell/OCaml from Pod D
- [x] README: RBAC roles `operator`/`reader` → `mutate`/`read`/`worker`/`internal`
- [x] README: `GATEWAY_API_KEY` → actual env var names (`ORCHESTRATOR_ADMIN_API_KEY`, etc.)
- [x] README: `LANGGRAPH_CHECKPOINTER` default `memory` → `none`
- [x] README: Config section expanded with missing env vars (OTEL, scaling, MCP, LLM_PROVIDER)
- [x] README: Pod A `SUPPORTED_LANGUAGES` includes `typescript`
- [x] README: `AGENT_BINDING` example updated to `AGENT-14-PYTHON`
- [x] ROADMAP: Phase 6 status → Complete
- [x] `.env.example`: `GEMINI_MODEL` → `gemini-3-flash-preview`
- [x] CHANGELOG: Extraction engine entry corrected (232 patterns, added Zig + TS)

---

## 🔴 Remaining Open Work Items

### P0 — Highest Priority

#### 1. Mission Create Read-After-Write Consistency
- **Status:** Partially addressed. Mission Control now retries brief eventual-consistency `404` reads via `getMission`, but the backend contract is still queue-first rather than true read-after-write.
- **Action:** Either keep the queue-first contract and document it consistently, or change mission creation so the mission record is queryable immediately after `POST /v1/missions`.

#### 2. ✅ Gateway Routing for Go / Haskell / OCaml
- **Status:** Completed. Go, Haskell, and OCaml now have fully dedicated specialist agents, are in compose `SUPPORTED_LANGUAGES`, and mapped in the orchestrator.

### P1 — Important

#### 3. Builder & Repository Workflow Completion
- **Status:** Partially addressed.
- **Issue:** Repository review is now server-backed and repo mission launch carries a real `source_code` bundle plus inferred target language, but Builder diff preview is still inferred/synthetic, repo approval is still UI-local state, and chat launch still hardcodes `requested_target_language: "python"`.
- **Action:** Implement a true Builder diff/apply contract, decide whether repo approval must be stored server-side, and remove the chat language hardcode.
- **Files:** `apps/mission-control/app/(shell)/builder/page.tsx`, `apps/mission-control/app/(shell)/repo/page.tsx`, `apps/mission-control/app/(shell)/chat/page.tsx` (line 256)

#### 4. Audit/Event Documentation Alignment
- **Status:** Open.
- **Issue:** Some docs still describe older audit stream design; Mission Control data-plane surfaces still lag backend readiness.
- **Action:** Align audit docs with `missions.state` / `mission_audit_reports` implementation. Update UI copy for optional adapters.
- **Files:** `docs/ARCHITECTURE.md`, Mission Control database page

### P2 — Nice-to-Have

#### 5. Audit Worker Artifact Packaging Pipeline
- **Status:** Open.
- **Issue:** "Binary ready" semantics in docs are stronger than the actual implementation.
- **Action:** Implement real build/package path OR remove the overstated claims.

#### 6. Dynamic Agent Scaling End-to-End Wiring
- **Status:** Open.
- **Issue:** `agent_scaling.py` is complete but `AGENT_SCALING_ENABLED` defaults to false and pod-worker has no partition-claim logic.
- **Action:** Wire pod-worker to read partition assignments, implement result fusion in orchestrator, add integration tests.
- **Files:** `services/orchestrator/orchestrator/agent_scaling.py`, `services/orchestrator/orchestrator/mission_flow_v2.py`, `services/pod-worker/pod_worker/main.py`
