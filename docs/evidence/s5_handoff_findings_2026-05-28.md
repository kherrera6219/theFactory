# Sprint 5 — Live-Stack Test Mission Findings & Handoff Report
**Date:** 2026-05-28  
**Author:** Claude (session kherrera3250@gmail.com)  
**Purpose:** Full handoff for Codex or next agent to continue from exactly this point.

---

## 1. Stack State at Handoff

| Component | Status | Details |
|---|---|---|
| Docker stack | **Running** | `deploy/docker-compose.yaml --env-file .env` |
| `deploy-postgres-1` | Healthy | Port 5432 (internal) |
| `deploy-redis-1` | Healthy | Port 6379 (internal) |
| `deploy-orchestrator-1` | Running | Port 8001, commit `1a0a878` |
| `deploy-qdrant-1` | Running | Port 6333 (internal) |
| API gateway | **NOT confirmed running** — check `docker compose ps` |
| Mission Control (Electron) | Not started in Docker — desktop app |

**Critical: Always restart the stack with:**
```bash
docker compose -f deploy/docker-compose.yaml --env-file .env up -d
```
Omitting `--env-file .env` causes Postgres auth failure (uses placeholder password from compose file instead of `.env`).

**Credentials location:** `C:/software/Holygrail/theFactory/.env`  
Keys present: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`

---

## 2. Git State

| Branch | Commit | Status |
|---|---|---|
| `main` | `1a0a878` | Local only — **NOT pushed to remote** |

**Push needed:**
```bash
cd C:/software/Holygrail/theFactory
git push origin main
```

**Commits in this session (not yet on remote):**
- `1a0a878` — S5-02 bug fixes (llm_cost_ledger, mission_flow_v2 clarifying TypeError, context var binding)
- Earlier commits (CI fixes, S5-01 runtime.py fix) — already on remote from prior push

---

## 3. Test Missions Conducted

### Mission 1 — S5-01 Validation ✅ COMPLETE
| Field | Value |
|---|---|
| Mission ID | `mission-998b8666-d61a-42c2-87c7-a871052afbf2` |
| Prompt | "Build a Python function that takes a list of integers and returns the top-K most frequent elements, with unit tests." |
| Provider / Model | OpenAI / `gpt-5.5` |
| Final state | `COMPLETE` |
| Generated file | `top_k_frequent.py` (1787 chars) |
| Chain events | 21 events, PM_INTAKE → DELIVERED |
| Security | Low risk, passed |
| Equivalence | Verified |
| Evidence | `docs/evidence/live_demo_sprint5_2026-05-25.json` |

**Bugs discovered and fixed during this mission:**
- `_completion_artifacts_ready` in `runtime.py` always returned `not ready` because it queried `mission_pod_assignments` and `mission_logicnodes` DB tables which are empty in single-orchestrator deployments (those deployments write everything through `metadata_json` on the `missions` table). **Fix:** Added metadata JSON fallback — checks `chain_trace` events (`MISSION_SPECIALIST_ASSIGNED`, `MISSION_LOGIC_FOLDED`) and metadata keys (`assigned_pod_manager_agent_id`, `pod_group_standards`, `master_logic_stream`).

---

### Mission 2 — S5-02 Initial Attempt ❌ STUCK IN QUEUED
| Field | Value |
|---|---|
| Mission ID | `mission-8f6d31e9-e47c-4f48-b88a-e65752dfc064` |
| Prompt | "Build an email validator" |
| Final state | Stuck in `QUEUED` / `CLARIFYING` |
| Errors found | Two bugs (see below) |

**Bugs discovered:**
1. `emit_state_event() got unexpected keyword argument 'app'` — TypeError in `_prepare_pm_intake` at `mission_flow_v2.py`. The clarifying-branch (triggered when `ambiguity_score >= 0.7`) called `emit_state_event_fn` with a hypothetical high-level signature (`app=`, `mission_id=`, `new_state=`, `details=`) that never matched the real function signature (`settings=`, `validator=`, `redis_client=`, `mission=`, `event_type=`). **Fix:** Replaced with `storage.transition_mission_state` + correct `emit_state_event_fn` call.
2. `llm_usage_events` never populated (two root causes — see Section 4).

**Note:** "email validator" prompt scored `ambiguity_score >= 0.7` because the PM agent considers it underspecified (no language, no framework, no scope specified). Use an explicit prompt for the next test.

---

### Mission 3 — S5-02 Verification ⏳ NOT YET RUN
This is the next thing to do. See Section 5.

---

## 4. Bugs Fixed This Session (All Committed to `1a0a878`)

### Bug A — `emit_state_event` wrong signature in clarifying branch
**File:** `services/orchestrator/orchestrator/mission_flow_v2.py`  
**Function:** `_prepare_pm_intake` (~line 625)  
**Symptom:** `TypeError: emit_state_event() got an unexpected keyword argument 'app'` whenever a mission prompt scored `ambiguity_score >= 0.7`, crashing the entire lifecycle task.  
**Root cause:** Leftover from a refactor — the call used a hypothetical state-machine dispatcher interface instead of the real Redis publisher interface.  
**Fix applied:**
```python
# Before (WRONG):
await emit_state_event_fn(
    app=app, mission_id=mission_id,
    new_state=MissionState.clarifying, event_type="MISSION_CLARIFYING",
    details={...},
)

# After (CORRECT):
await asyncio.to_thread(storage.update_mission_metadata, settings, mission_id, metadata)
clarifying_record = await asyncio.to_thread(
    storage.transition_mission_state, settings, mission_id,
    MissionState.pm_intake, MissionState.clarifying, "MISSION_CLARIFYING",
)
if clarifying_record is not None:
    redis_ready = bool(getattr(app.state, "redis_ready", False))
    redis_client = getattr(app.state, "redis", None)
    if redis_ready and redis_client is not None:
        await emit_state_event_fn(
            settings=settings, validator=validator,
            redis_client=redis_client, mission=clarifying_record,
            event_type="MISSION_CLARIFYING",
        )
```

---

### Bug B — `llm_cost_ledger.py` async/sync mismatch
**File:** `services/orchestrator/orchestrator/llm_cost_ledger.py`  
**Functions:** `record_llm_usage`, `get_mission_token_usage`  
**Symptom:** `llm_usage_events` table always empty — no rows ever inserted.  
**Root cause:** `db_connect()` returns a **synchronous** psycopg3 connection, but the code used `async with db_connect()` and `await cur.execute()` — this raises a `TypeError` which is silently swallowed by the bare `except Exception: pass`.  
**Fix applied:** Extracted `_insert_usage_sync` and `_fetch_usage_rows_sync` synchronous helpers, called via `asyncio.to_thread`.

---

### Bug C — `current_mission_id` ContextVar never set
**File:** `services/orchestrator/orchestrator/mission_flow_v2.py` and `runtime.py`  
**Function:** `advance_mission_lifecycle_v2` / `advance_mission_lifecycle`  
**Symptom:** `_record_usage_event` in `llm_delegation.py` always exits early because `mission_id = current_mission_id.get()` returns `None`.  
**Root cause:** The three ContextVars (`current_mission_id`, `current_settings`, `current_agent_id`) are declared in `llm_delegation.py` but never set by any caller. The docs assume they'd be set at the lifecycle entry point, but that wire was never done.  
**Fix applied:**
- `mission_flow_v2.py`: Import `current_mission_id as _llm_current_mission_id` and `current_settings as _llm_current_settings` from `llm_delegation`, set them at the top of `advance_mission_lifecycle_v2`.
- `runtime.py:advance_mission_lifecycle`: Added try/finally to set+reset both vars around `engine.advance(app, mission_id)`.

---

### Bug D — `_completion_artifacts_ready` always returned not-ready (fixed in prior commit)
**File:** `services/orchestrator/orchestrator/runtime.py`  
**Function:** `_completion_artifacts_ready`  
**Symptom:** Missions stuck in `VERIFIED` state forever, never reaching `COMPLETE`.  
**Root cause:** Read from `mission_pod_assignments` and `mission_logicnodes` DB tables, which are empty in single-orchestrator deployments (writes go through `metadata_json` on the `missions` table).  
**Fix applied:** Added fallback check against metadata JSON: checks `chain_trace` events (`MISSION_SPECIALIST_ASSIGNED`, `MISSION_LOGIC_FOLDED`) and metadata keys (`assigned_pod_manager_agent_id`, `pod_group_standards`, `master_logic_stream`). **This fix is what enabled S5-01 to reach COMPLETE.**

---

## 5. Immediate Next Step — Complete S5-02

The orchestrator is rebuilt with all fixes and running clean. One mission test is all that's needed.

### Step 1 — Confirm stack is up
```bash
cd C:/software/Holygrail/theFactory
docker compose -f deploy/docker-compose.yaml --env-file .env ps
```
Expected: `deploy-orchestrator-1` is `running (healthy)` or `running`.

### Step 2 — Confirm `llm_usage_events` table exists
```bash
docker exec deploy-postgres-1 psql -U factory_user -d factory_db -c "\d llm_usage_events"
```
If table doesn't exist, run migration:
```bash
docker exec deploy-postgres-1 psql -U factory_user -d factory_db -f /migrations/V007_llm_usage_ledger_schema.sql
```
Or trigger via orchestrator startup (it auto-runs `ensure_db_schema` on boot — check logs for any migration errors).

### Step 3 — Submit a clear, non-ambiguous mission
Use an explicit prompt so `ambiguity_score < 0.7` and it doesn't enter the clarifying branch.
```bash
MID="mission-s502-$(date +%s)"
echo "Mission ID: $MID"

curl -s -X POST http://localhost:8001/v1/missions \
  -H "Content-Type: application/json" \
  -d "{
    \"mission_id\": \"$MID\",
    \"prompt\": \"Write a Python function called count_vowels(s: str) -> int that returns the count of vowel characters (a, e, i, o, u, case-insensitive). Include a NumPy-style docstring and 5 pytest unit tests covering edge cases.\",
    \"requested_target_language\": \"python\",
    \"metadata\": {
      \"mission_type\": \"BUILD_NEW\",
      \"depth_mode\": \"STANDARD\",
      \"output_mode\": \"FULL_BUILD\"
    }
  }" | python -m json.tool
```

If port 8001 returns empty reply, try the API gateway port (check `docker compose ps` for the gateway container's published port, likely 8000).

### Step 4 — Poll for completion (do this in a loop, not one long sleep)
```bash
# Poll every 30 seconds, print status each time
for i in $(seq 1 20); do
  STATE=$(curl -s http://localhost:8001/v1/missions/$MID | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('state','?'))" 2>/dev/null)
  echo "$(date '+%H:%M:%S') — state: $STATE"
  [ "$STATE" = "COMPLETE" ] && break
  [ "$STATE" = "FAILED" ] && break
  sleep 30
done
```

### Step 5 — Verify `llm_usage_events` populated
```bash
docker exec deploy-postgres-1 psql -U factory_user -d factory_db \
  -c "SELECT agent_id, provider, model, input_tokens, output_tokens, estimated_cost_usd FROM llm_usage_events WHERE mission_id='$MID' ORDER BY created_at;"
```
**Expected:** Multiple rows (one per LLM call — PM, CEO, pod managers, specialists, etc.)

### Step 6 — Verify token-usage API endpoint
```bash
curl -s http://localhost:8001/v1/missions/$MID/token-usage | python -m json.tool
```
**Expected:** JSON with `total_tokens`, `estimated_cost_usd`, `by_provider`, `by_agent` populated.

### Step 7 — Save evidence
```bash
curl -s http://localhost:8001/v1/missions/$MID/token-usage > docs/evidence/s502_cost_ledger_live_2026-05-28.json
curl -s http://localhost:8001/v1/missions/$MID >> docs/evidence/s502_cost_ledger_live_2026-05-28.json
```

### Step 8 — Mark S5-02 complete in SPRINT_BACKLOG.md
Update the `[ ]` on the S5-02 line to `[x]` and add completion date + evidence reference.

---

## 6. Full Sprint 5 Remaining Work (in order)

| Item | Status | Blocker |
|---|---|---|
| **S5-02** — Token cost ledger | Code done, **verification pending** | Run one mission (Section 5 above) |
| **S5-03** — Gemini embeddings live | Not started | S5-02 done + GEMINI_API_KEY in .env |
| **S5-04** — PORT two-phase live demo | Not started | S5-02 done + open-source source project |
| **S5-05** — Agent scaling (20+ files) | Not started | `AGENT_SCALING_ENABLED=true` in .env |
| **S5-06** — Qualification evidence refresh | Not started | `make promotion-gate` command |
| **S5-07** — Reliability re-qual (4h) | Not started | Stack up for 4+ continuous hours |
| **S4-03** (also S5-05) | Not started | Same as S5-05 |
| **S4-06** (also S5-06) | Not started | Same as S5-06 |

---

## 7. S5-03 Instructions (run after S5-02 verified)

```bash
# Confirm GEMINI_API_KEY is in .env (it is, as of 2026-05-24)
grep GEMINI_API_KEY C:/software/Holygrail/theFactory/.env

# KNOWLEDGE_EMBEDDING_PROVIDER is already defaulted to "gemini" (set 2026-05-24)
# Verify:
grep KNOWLEDGE_EMBEDDING_PROVIDER C:/software/Holygrail/theFactory/.env

# Run another BUILD_NEW mission (same curl as S5-02 Step 3, different MID)
# Then check knowledge retrieval in logs:
docker logs deploy-orchestrator-1 2>&1 | grep -i "embedding\|gemini\|knowledge"

# Save evidence:
# docs/evidence/s503_gemini_embeddings_live_2026-05-28.json
```

---

## 8. Architecture Notes for Codex

### How LLM cost tracking flows
```
advance_mission_lifecycle (runtime.py)
  └─ sets current_mission_id + current_settings ContextVars
  └─ calls engine.advance(app, mission_id)
       └─ advance_mission_lifecycle_v2 (mission_flow_v2.py)
            └─ also sets ContextVars (redundant but harmless)
            └─ calls _prepare_pm_intake, _prepare_fetch_phase, etc.
                 └─ each phase calls llm_delegation.py functions
                      └─ _record_usage_event reads ContextVars
                           └─ calls record_llm_usage (llm_cost_ledger.py)
                                └─ asyncio.to_thread(_insert_usage_sync)
                                     └─ psycopg3 sync INSERT into llm_usage_events
```

### Why single-orchestrator deployments bypass pod tables
The multi-orchestrator design has separate services writing to `mission_pod_assignments` and `mission_logicnodes`. In single-orchestrator mode, all phases run in-process and the orchestrator writes results directly into `metadata_json` on the `missions` row. The `_completion_artifacts_ready` function was only checking the normalized tables, causing it to block forever.

### Key files
| File | What it does |
|---|---|
| `services/orchestrator/orchestrator/runtime.py` | Lifecycle task management, Redis stream consumer, `_completion_artifacts_ready` |
| `services/orchestrator/orchestrator/mission_flow_v2.py` | All 11 mission phases (PM → CEO → Pod → Fusion → Verified → Complete) |
| `services/orchestrator/orchestrator/llm_delegation.py` | All LLM API calls, ContextVar declarations, `_record_usage_event` |
| `services/orchestrator/orchestrator/llm_cost_ledger.py` | DB write/read for `llm_usage_events`, cost estimation |
| `services/orchestrator/orchestrator/storage_missions.py` | `transition_mission_state`, `update_mission_metadata`, `fetch_mission` |
| `deploy/docker-compose.yaml` | Stack definition — always use with `--env-file .env` |

### Docker stack management
```bash
# Full rebuild + restart:
docker compose -f deploy/docker-compose.yaml --env-file .env build orchestrator
docker compose -f deploy/docker-compose.yaml --env-file .env up -d orchestrator

# View logs:
docker logs deploy-orchestrator-1 --tail=50 -f

# Check postgres:
docker exec deploy-postgres-1 psql -U factory_user -d factory_db -c "SELECT state, COUNT(*) FROM missions GROUP BY state;"
```

---

## 9. Constraints (do not change these)

- **Do NOT change model strings** `gpt-5.5` and `gemini-3.5-flash` in `llm_cost_ledger.py` or anywhere else — these are intentional and correct for this project.
- **`GATEWAY_ADMIN_BYPASS` defaults to `true`** — dev bypass enabled. Production sets it `false`.
- **Publisher is Kevin Herrera** — auto-update removed from Electron (manual installer updates only).
- **Push command:** `git push origin main` — needs explicit user authorization before pushing.
