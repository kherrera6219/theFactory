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

#### 1. ✅ Mission Create Read-After-Write Consistency
- **Status:** Completed (2026-03-15).
- **Action taken:** `POST /v1/missions` now persists via the orchestrator before returning `201 Created`, so immediate follow-up reads can query the mission record without depending on intake-stream consumption timing.

#### 2. ✅ Gateway Routing for Go / Haskell / OCaml
- **Status:** Completed. Go, Haskell, and OCaml now have fully dedicated specialist agents, are in compose `SUPPORTED_LANGUAGES`, and mapped in the orchestrator.

### P1 — Important

#### 3. ✅ Builder, Repository Review, and Chat Intake Contract
- **Status:** Completed (2026-03-14).
- **Action taken:**
  - Builder review now inspects real local workspace files, emits a stable `builder_fingerprint`, produces a grounded patch contract and launchable `source_code` bundle, and launches missions from the approved artifact.
  - Repository review approval now persists server-side as a local approval receipt record before launch.
  - Chat intake now infers `requested_target_language` from attached files and prompt hints instead of hardcoding Python.
- **Files:** `apps/mission-control/app/(shell)/builder/page.tsx`, `apps/mission-control/app/api/builder/review/route.ts`, `apps/mission-control/app/api/review/approve/route.ts`, `apps/mission-control/app/(shell)/repo/page.tsx`, `apps/mission-control/app/(shell)/chat/page.tsx`

#### 4. Audit/Event Documentation Alignment
- **Status:** Open.
- **Issue:** Some docs still describe older audit stream design; Mission Control data-plane surfaces still lag backend readiness.
- **Action:** Align audit docs with `missions.state` / `mission_audit_reports` implementation. Update UI copy for optional adapters.
- **Files:** `docs/ARCHITECTURE.md`, Mission Control database page

### P2 — Nice-to-Have

#### 5. Audit Worker Artifact Packaging Pipeline
- **Status:** Open.
- **Issue:** The runtime now correctly uses `mission.state.complete` for lifecycle completion, but there is still no real build/package artifact pipeline.
- **Action:** Implement a real package/bundle writer and only then reintroduce bundle-ready semantics.

#### 6. ✅ Dynamic Agent Scaling End-to-End Wiring
- **Status:** Completed (2026-03-15).
- **Action taken:** the orchestrator now emits `mission.partition.ready` work items from v2 specialist plans, pod-workers execute partition-specific work, partition results are persisted and merged in mission metadata, and lifecycle resumes once all partition results complete.
- **Files:** `services/orchestrator/orchestrator/agent_scaling.py`, `services/orchestrator/orchestrator/mission_flow_v2.py`, `services/orchestrator/orchestrator/main.py`, `services/orchestrator/orchestrator/storage.py`, `services/pod-worker/pod_worker/main.py`
