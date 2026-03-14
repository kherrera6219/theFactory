# theFactory — Updated Completion TODO

**Last updated:** 2026-03-13

---

## ✅ Documentation Alignment (Completed 2026-03-13)

All of the following code-vs-docs mismatches have been fixed:

- [x] README: Audit badge → 17/17 (was 13/13)
- [x] README: Pod A agent table — added TypeScript
- [x] README: Extraction table — removed Go from Pod B, Haskell/OCaml from Pod D
- [x] README: Language count corrected to 16 (with TypeScript alias note)
- [x] README: RBAC roles `operator`/`reader` → `mutate`/`read`/`worker`/`internal`
- [x] README: `GATEWAY_API_KEY` → actual env var names (`ORCHESTRATOR_ADMIN_API_KEY`, etc.)
- [x] README: `LANGGRAPH_CHECKPOINTER` default `memory` → `none`
- [x] README: Config section expanded with missing env vars (OTEL, scaling, MCP, LLM_PROVIDER)
- [x] README: Pod A `SUPPORTED_LANGUAGES` includes `typescript`
- [x] README: `AGENT_BINDING` example updated to `AGENT-14-PYTHON`
- [x] ROADMAP: Phase 6 status → Complete
- [x] `.env.example`: `GEMINI_MODEL` → `gemini-3-flash-preview`
- [x] IMPLEMENTATION_STATUS: Language count corrected to 16 routable keys
- [x] CHANGELOG: Extraction engine entry corrected (232 patterns, added Zig + TS)

---

## 🔴 Remaining Open Work Items

### P0 — Highest Priority

#### 1. Mission Create Read-After-Write Consistency
- **Issue:** `POST /v1/missions` returns before orchestrator persists the record. Immediate `GET` can 404.
- **Action:** Add synchronous write before response, or document the eventual-consistency contract in the API spec and Mission Control error handling.
- **Files:** `services/api-gateway/api_gateway/main.py`, `services/orchestrator/orchestrator/runtime.py`

#### 2. Gateway Routing for Go / Haskell / OCaml
- **Issue:** Gateway routes these languages to pod managers, but compose `SUPPORTED_LANGUAGES` omits them — missions are silently dropped.
- **Action:** Either add these languages to pod-worker compose entries OR remove them from gateway routing code (`_POD_B_LANGUAGES`, `_POD_D_LANGUAGES` in `api_gateway/main.py`).
- **Files:** `services/api-gateway/api_gateway/main.py` lines 154/156, `deploy/docker-compose.yaml` lines 545/633

### P1 — Important

#### 3. Builder & Repository Workflow Completion
- **Issue:** Builder diff preview is inferred/synthetic; repo review gate is client-side; chat page hardcodes `requested_target_language: "python"`.
- **Action:** Implement server-side diff/apply contract; move review gating server-side; fix chat page hardcode.
- **Files:** `apps/mission-control/app/(shell)/builder/page.tsx`, `apps/mission-control/app/(shell)/repo/page.tsx`, `apps/mission-control/app/(shell)/chat/page.tsx` (line 256)

#### 4. Audit/Event Documentation Alignment
- **Issue:** Some docs still describe older audit stream design; Mission Control data-plane surfaces lag backend readiness.
- **Action:** Align audit docs with `missions.state` / `mission_audit_reports` implementation. Update UI copy for optional adapters.
- **Files:** `docs/ARCHITECTURE.md`, Mission Control database page

### P2 — Nice-to-Have

#### 5. Audit Worker Artifact Packaging Pipeline
- **Issue:** "Binary ready" semantics in docs are stronger than the actual implementation.
- **Action:** Implement real build/package path OR remove the overstated claims.

#### 6. Dynamic Agent Scaling End-to-End Wiring
- **Issue:** `agent_scaling.py` is complete but `AGENT_SCALING_ENABLED` defaults to false and pod-worker has no partition-claim logic.
- **Action:** Wire pod-worker to read partition assignments, implement result fusion in orchestrator, add integration tests.
- **Files:** `services/orchestrator/orchestrator/agent_scaling.py`, `services/orchestrator/orchestrator/mission_flow_v2.py`, `services/pod-worker/pod_worker/main.py`
