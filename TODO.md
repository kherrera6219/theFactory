# theFactory — Updated Todo List
## Source: Production Code Review 2026-05-22 + Demo Session 2026-05-23
## Last reviewed: 2026-05-24 (all items resolved)
**0 open · 11 closed/corrected**

---

## ✅ Completed (validated)

- [x] **CR-01** LLM model strings in `agent_integrations.py`
  - `"gpt-5.5"` and `"gemini-3.5-flash"` confirmed intentional — not placeholder strings
  - User confirmed these are the correct target models for the project
  - **CLOSED — no change required**

- [x] **H-02** Audit api-gateway broad exception handlers
  - All 19 `except Exception` catches audited in `api_gateway/main.py`
  - 7 httpx network catches narrowed to `httpx.RequestError`
  - 6 Redis operation catches narrowed to `(ConnectionError, TimeoutError, OSError)`
  - 1 JSON parse catch narrowed to `ValueError`
  - 3 intentionally broad catches kept (SSE loop, OIDC decoder, idempotency re-raise) — each annotated with specific reason
  - All duplicate `LOGGER.warning("gateway operation failed")` lines removed
  - **DONE**

- [x] **H-06** Mission Control unlock gate rebuild
  - `OPERATOR_SESSION_BYPASS=true` active in docker-compose and `.env`
  - Root causes fixed: `output: "export"` → conditional on `NEXT_BUILD_TARGET`, start port corrected (3100→3000), api-gateway healthcheck timeout raised (2s→10s), healthcheck endpoint switched to `/health`
  - Bypass verified: `{"authenticated":true,"ttl_seconds":28800,"bypass":true}`
  - `http://localhost:3100` goes straight to app, no unlock form
  - **DONE**

- [x] **CR-02** Decompose `advance_mission_lifecycle_v2`
  - Completion gate already extracted to `_advance_verified_to_complete` (line 2671) in prior session
  - `advance_mission_lifecycle_v2` delegates to it at line 3028
  - **DONE (completed in prior session)**

- [x] **H-03** Docker image digest pinning — all Dockerfiles now pinned
  - `python:3.11-slim-bookworm@sha256:8dca233...` across all 7 Python services
  - `node:22-alpine3.20@sha256:2289fb1...` across all 3 mission-control stages
  - **DONE**

- [x] **H-01** Unit tests for `auth.py`, `review_policy.py`, `storage_missions.py`
  - All 3 test files confirmed present: `test_auth_unit.py`, `test_review_policy_unit.py`, `test_storage_missions_unit.py`
  - **DONE**

- [x] **H-05** `llm_fallback_total` counter + Mission Control badge
  - `LLM_FALLBACK_TOTAL` imported from `orchestrator_metrics` and incremented in 9 fallback functions
  - `missions/detail/page.tsx` renders fallback warning when `metadata.source === "fallback"`
  - **DONE**

- [x] **H-04** Factor `create_mission` + unify builder previews
  - `create_mission` reduced from 206 → 74 lines
  - Unified `create_builder_preview` dispatcher added
  - **DONE**

- [x] **M-03** `make check-env`
  - `check-env` target present, wired as prerequisite to `make up`
  - **DONE**

- [x] **M-02** Bound async thread pool executor
  - `ThreadPoolExecutor(max_workers=20)` set on the running loop
  - **DONE**

- [x] **M-04** `_depabs_recommendation` — confirmed NOT dead code
  - Called from `dependency_absorption.py:867` via lazy import
  - **CLOSED — was a false positive**

---

*Last updated: 2026-05-24*
