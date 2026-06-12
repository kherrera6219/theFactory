# theFactory — Production Code Review
## Date: 2026-05-22 | Scope: Full codebase

---

## Headline Metrics

| Metric | Value | Gate / Target |
|--------|-------|---------------|
| Line coverage | 91.8% | ≥80% ✅ |
| Branch coverage | 80.3% | ≥80% ✅ |
| Test functions | 957 across 83 files | — ✅ |
| Dependencies pinned | 100% all 7 services | — ✅ |
| TODO/FIXME markers | 0 | 0 ✅ |
| `nosec` suppressions | 5 | Low ✅ |
| Broad `except Exception` | 170 | — ⚠ |
| Missing return annotations | 335 functions | — ⚠ |
| Untested orchestrator modules | 30 | — ❌ |

---

## CRITICAL

### CR-01 — Model strings unvalidated against live APIs
**File:** `services/orchestrator/orchestrator/agent_integrations.py` lines 26–95

All exec agents and code specialists use `gpt-5.5`; math/IS agents use `gemini-3.5-flash`. Neither string has been confirmed valid against live provider endpoints. If invalid, every LLM call silently falls through to deterministic fallback routing — missions complete but produce stub output only. The entire intelligence layer is blocked until these are confirmed.

**Fix:** Before next live run, call each provider's model-list endpoint and confirm exact model IDs. Update `_LLM_PROFILES` to validated strings.

### CR-02 — `advance_mission_lifecycle_v2` is 400 lines
**File:** `services/orchestrator/orchestrator/mission_flow_v2.py:2615`

The primary dispatch function handles every state transition, error recovery, metadata mutation, and event emission in a single 400-line body. It is the highest change-risk function in the codebase. A regression in any branch can silently corrupt mission state for unrelated transitions.

**Fix:** Continue the existing per-state handler extraction pattern. Extract `_advance_*` helpers for the remaining inline branches.

---

## HIGH

### H-01 — 30 orchestrator modules with no dedicated unit test file
Key modules with no matching `test_<module>.py`: `auth.py`, `heartbeat_service.py`, `review_policy.py`, `llm_cost_ledger.py`, `knowledge_lake.py`, `is_agent.py`, `storage_missions.py`, `storage_artifacts.py`, `storage_agents.py`, `models.py`, `lifecycle_recovery.py`.

The 91.8% line coverage is real but comes from integration tests that incidentally cover these files. A targeted regression in any of them won't be caught by a focused test run.

**Fix:** Prioritize isolated unit tests for `auth.py`, `review_policy.py`, `storage_missions.py` — highest blast radius.

### H-02 — 170 broad `except Exception` catches
Top 5 files: api-gateway (19), mission_flow_v2 (14), pod-worker (13), runtime (10), routes/internal (9). Several are in request handlers where a swallowed exception returns a 500 with no diagnostic context.

**Fix:** Audit api-gateway handlers specifically. Tag all intentional resilience catches with a `# resilience: <reason>` comment to distinguish them from accidental suppression.

### H-03 — No Docker image digest pinning
All 7 Python Dockerfiles and mission-control Dockerfile use tag-only references (`python:3.11-slim-bookworm`, `node:22-alpine3.20`). Acknowledged as deferred in April 2026 remediation — still open.

**Fix:** `docker pull python:3.11-slim-bookworm --platform linux/amd64`, extract the `@sha256:...` digest, pin all FROM lines.

### H-04 — `create_mission` route handler is 206 lines
**File:** `services/api-gateway/api_gateway/main.py:1429`

Handles auth, idempotency, rate limiting, metadata normalization, validation, Redis write, and response assembly inline. Three nearly-identical LLM builder preview functions (64–97 lines each) exist in the same file with duplicated structure.

**Fix:** Extract metadata normalization and stream-write into helpers. Unify the three builder preview functions behind a single `_call_llm_builder_preview(provider, ...)` dispatcher.

### H-05 — 46 silent LLM fallback paths with no observable signal
Every `generate_*` function in `llm_delegation.py` has a `_fallback_*` that returns a structured stub. There is no Prometheus counter, no alert rule, and no chain trace marker distinguishing a real LLM completion from a fallback. Operators cannot tell whether a completed mission used real cognition.

**Fix:** Add `llm_fallback_total{agent_id, reason}` Prometheus counter in each fallback path. Surface `source=fallback` as a warning badge in Mission Control mission detail.

---

## MEDIUM

### M-01 — 335 functions missing return type annotations
Worst files: `llm_delegation.py` (51), `api_gateway/main.py` (39), `routes/internal.py` (23), `mission_flow_v2.py` (22). The dataclass-heavy storage and model layers are well-typed; the intelligence layer is not.

### M-02 — 39 `asyncio.to_thread` calls with unbounded thread pool
Synchronous psycopg calls are correctly wrapped in `asyncio.to_thread` but no `max_workers` is set on the default executor. Under concurrent mission load, thread pool exhaustion can stall the event loop.

**Fix:** Add `loop.set_default_executor(ThreadPoolExecutor(max_workers=20))` in the FastAPI lifespan handler.

### M-03 — 23 `CHANGE_ME` defaults in docker-compose with no startup validation
Running `make up` without `.env` produces a working stack with insecure placeholder credentials and no warning.

**Fix:** Add `make check-env` target that greps `.env` for `CHANGE_ME` and fails with an actionable list of missing values.

### M-04 — `_depabs_recommendation` defined but never called
**File:** `llm_delegation.py:358`

The function appears only once (its own definition). Either the DEPABS agent uses a different recommendation path, or this was intended for a call that was never wired.

**Fix:** Wire into `dependency_absorption.py` or remove.

---

## LOW / POSITIVE

- ✅ Zero `time.sleep` or blocking calls in async service paths
- ✅ Zero `print()` statements in production code (all output via structured LOGGER)
- ✅ Zero bare `assert` in production code
- ✅ Zero TODO/FIXME/HACK markers in entire codebase
- ✅ All `__init__.py` files present in every service package
- ✅ All 7 requirements.txt files fully pinned (0 unpinned dependencies)
- ✅ TLS private keys confirmed absent from git history (0 commits)
- ✅ Production audit 22/22 checks passing
- ✅ `nosec` suppression count is 5 — no evidence of broad security scanner suppression
- ✅ 7 versioned, checksum-tracked DB migrations — no schema drift

---

## Priority Action Plan

| Priority | Item | Effort |
|----------|------|--------|
| 1 | Validate `gpt-5.5` and `gemini-3.5-flash` against live APIs | 1 hour |
| 2 | Add `llm_fallback_total` Prometheus counter + Mission Control warning badge | 2–3 hours |
| 3 | Add unit tests for `auth.py`, `review_policy.py`, `storage_missions.py` | 1–2 days |
| 4 | Pin Docker image digests | 1 hour |
| 5 | Add `make check-env` CHANGE_ME validation target | 30 min |
| 6 | Set thread pool `max_workers` in orchestrator lifespan | 30 min |
| 7 | Wire or remove `_depabs_recommendation` | 30 min |
| 8 | Add return type annotations to `llm_delegation.py` | 2–3 days |
| 9 | Factor `create_mission` route handler | 1 day |
| 10 | Begin `advance_mission_lifecycle_v2` decomposition | 2–3 days |

---

*Generated by live codebase sweep — 2026-05-22*
