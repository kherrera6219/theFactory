# theFactory — Updated Todo List
## Source: Production Code Review 2026-05-22 + Demo Session 2026-05-23
## Last reviewed: 2026-05-24 (all items resolved)
**0 open · 11 closed/corrected**

> **Active workstream (2026-05-29): Local-First Compliance — Bucket A.**
> See [docs/LOCAL_FIRST_COMPLIANCE_PLAN.md](docs/LOCAL_FIRST_COMPLIANCE_PLAN.md) for the
> validated, outstanding-only plan derived from the Local-First Security & Error-Handling
> Standards. Bucket A items (A1–A9) are tracked below; Bucket B (infra re-platform) is a
> separate product decision and is NOT in progress.

---

## 🔧 Local-First Compliance — Bucket A ✅ COMPLETE (2026-05-29)

- [x] **A5** Error framework — `shared_runtime/errors.py` (ErrorCategory/ErrorSeverity enums,
  FactoryError standard object) + `docs/ERROR_CODES.md` registry
- [x] **A6** User-facing error format in Mission Control (four-line §4 format; `ErrorMessage`
  component + structured parse + orchestrator FactoryError handler)
- [x] **A4** Atomic file writes — `shared_runtime/atomic_io.py` (temp→fsync→verify→replace→.bak);
  wired into diagnostics writer
- [x] **A7** DB transaction discipline — audited all storage modules; wrapped the one gap
  (`upsert_agent_heartbeat` two-write path) in `conn.transaction()`
- [x] **A1** ECDSA P-256 signing — `shared_runtime/crypto_signing.py` (sign/verify + payload records)
- [x] **A2** Signing-key protection — `shared_runtime/crypto_keystore.py` (Windows DPAPI via
  ctypes + documented backend fallback, atomic key persistence)
- [x] **A3** Template integrity verification — `prompt_registry` fail-closed vs
  `prompt_assets/manifest.json` (+ `scripts/generate_prompt_manifest.py`)
- [x] **A8** Electron crash handling — `electron/diagnostics.ts` boundary handlers + safe restart
- [x] **A9** Offline diagnostics bundle — 6 §18 artifacts under `%LOCALAPPDATA%/…/Diagnostics`,
  desktop button in Settings

**Remaining (incremental, noted in plan):** wire `sign_payload`/`verify_payload` into the
build-artifact / compliance-report / audit-bundle write+import paths (needs the signing key in
orchestrator app-state). **Bucket B** (infra re-platform) remains a separate product decision.

_Test coverage added this work: error framework (8), atomic_io (6), FactoryError handler (3),
crypto signing+keystore (11), prompt integrity (5), api-client structured errors (3)._

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
