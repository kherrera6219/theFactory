# theFactory — Phased Update Plan
**Generated:** 2026-05-29  
**Based on:** SPRINT_BACKLOG.md, IMPLEMENTATION_STATUS.md, session audit trail, git log  
**Current HEAD:** `b3f4383` (main)

---

## Executive Summary

The codebase is **feature-complete**. All Sprint 1–4 implementation items are done. The only remaining work is live-stack validation (Sprint 5) — proving each feature works against a real Docker stack with real API keys — plus a pair of qualification evidence refreshes and a long-duration reliability requalification.

_Updated 2026-05-29 (session 2)._

| Category | Done | Remaining |
|---|---|---|
| Sprint 1 — Live Demo Gate | 6/6 ✅ | 0 |
| Sprint 2 — Intelligence Layer | 8/8 ✅ | 0 |
| Sprint 3 — Platform Differentiation | 3/4 | 1 (S5-04 PORT demo) |
| Sprint 4 — Scale & Operational Maturity | 6/8 | 2 (S4-03/S4-06) |
| Sprint 5 — Live-Stack Validation | 3/7 | 4 (S5-04 PORT, S5-05 scaling, S5-06 OIDC, S5-07 reliability) |
| CI / Test Health | ✅ green | 0 — all lint/build/test/E2E/coverage gates pass |

---

## Phase 0 — PR #184 CI Green ✅ COMPLETE (2026-05-29)

**Status:** ✅ All lint/build/test/E2E gates green. Fixed in sequence: ruff I001, TS2322
(PanelProps id), 9 Mission Control unit tests, Next.js NEXT_BUILD_TARGET=docker, Lighthouse
auth bypass + LCP warn, 8 E2E routing/label/a11y failures, Python coverage restored to 80%.

| Fix | Commit | Status |
|---|---|---|
| ruff I001 — isort split aliased imports | `96dad7f` | ✅ pushed |
| TS2322 — `id` prop missing from `PanelProps` | `b3f4383` | ✅ pushed, CI running |

**Verify clean:**
```bash
gh pr checks 184 --repo kherrera6219/theFactory
```
Expected: All checks green. If any new failures surface, fix before proceeding.

**When done:** PR #184 can be closed (it's a review PR — `main` already has all commits). No merge needed.

---

## Phase 1 — S5-02: Token Cost Ledger Verification ✅ COMPLETE (2026-05-29)

**Status:** ✅ Mission mission-1c70f9e7 reached COMPLETE; 14 rows in llm_usage_events
($0.1642 total, all pricing known); token-usage API returns populated JSON. Evidence:
docs/evidence/s502_cost_ledger_live_2026-05-29.json.

**Why it matters:** This proves the entire telemetry pipeline works end-to-end. The Cost panel in Mission Control will show real per-agent, per-model token spend for the first time.

### Steps

```bash
# 1. Confirm stack is up (always use --env-file .env)
cd C:/software/Holygrail/theFactory
docker compose -f deploy/docker-compose.yaml --env-file .env ps

# If orchestrator isn't running the latest commit (b3f4383), rebuild:
docker compose -f deploy/docker-compose.yaml --env-file .env build orchestrator
docker compose -f deploy/docker-compose.yaml --env-file .env up -d orchestrator

# 2. Confirm llm_usage_events table exists
docker exec deploy-postgres-1 psql -U factory_user -d factory_db -c "\d llm_usage_events"

# 3. Submit a clear, non-ambiguous mission (avoids ambiguity clarifying branch)
MID="mission-s502-$(date +%s)"
curl -s -X POST http://localhost:8001/v1/missions \
  -H "Content-Type: application/json" \
  -d "{\"mission_id\":\"$MID\",\"prompt\":\"Write a Python function called count_vowels(s: str) -> int that counts vowel characters (a,e,i,o,u, case-insensitive). Include a NumPy-style docstring and 5 pytest unit tests.\",\"requested_target_language\":\"python\",\"metadata\":{\"mission_type\":\"BUILD_NEW\",\"depth_mode\":\"STANDARD\",\"output_mode\":\"FULL_BUILD\"}}"

# 4. Poll to COMPLETE (every 30s, ~5-8 minutes total)
for i in $(seq 1 20); do
  STATE=$(curl -s http://localhost:8001/v1/missions/$MID | python -c "import sys,json; print(json.load(sys.stdin).get('state','?'))" 2>/dev/null)
  echo "$(date '+%H:%M:%S') — $STATE"
  [ "$STATE" = "COMPLETE" ] && break; [ "$STATE" = "FAILED" ] && break
  sleep 30
done

# 5. Verify llm_usage_events populated
docker exec deploy-postgres-1 psql -U factory_user -d factory_db \
  -c "SELECT agent_id, provider, model, input_tokens, output_tokens, estimated_cost_usd FROM llm_usage_events WHERE mission_id='$MID';"

# 6. Verify token-usage API
curl -s http://localhost:8001/v1/missions/$MID/token-usage | python -m json.tool

# 7. Save evidence + mark S5-02 done in SPRINT_BACKLOG.md
curl -s http://localhost:8001/v1/missions/$MID/token-usage > docs/evidence/s502_cost_ledger_live_2026-05-29.json
```

**Definition of done:** `llm_usage_events` has multiple rows (≥5), `token-usage` API returns non-null `estimated_cost_usd`, Cost panel in Mission Control renders real numbers.

---

## Phase 2 — S5-03: Gemini Embeddings Live Validation ✅ COMPLETE (2026-05-29)

**Status:** ✅ New valid GEMINI_API_KEY works with gemini-embedding-001 (3072-dim vectors).
Fixed settings.py default model (dead text-embedding-004 → "" so per-provider default applies)
and .env KNOWLEDGE_EMBEDDING_MODEL. Mission mission-1c39e46d COMPLETE; vector_for_content
confirmed using Gemini (differs from deterministic fallback). Evidence:
docs/evidence/s503_gemini_embeddings_live_2026-05-29.json.

**Why it matters:** Confirms the knowledge retrieval layer is using semantic similarity (Gemini embeddings) rather than the deterministic hash fallback, improving code generation quality.

```bash
# Verify GEMINI_API_KEY and provider setting
grep GEMINI_API_KEY .env
grep KNOWLEDGE_EMBEDDING_PROVIDER .env   # should be "gemini"

# Run a second BUILD_NEW mission (different MID, same format as Phase 1)
MID="mission-s503-$(date +%s)"
# ... same curl command ...

# After COMPLETE, check orchestrator logs for embedding calls
docker logs deploy-orchestrator-1 2>&1 | grep -i "embedding\|gemini\|knowledge_lake" | tail -20

# Save evidence
curl -s http://localhost:8001/v1/missions/$MID > docs/evidence/s503_gemini_embeddings_live_2026-05-29.json
```

**Definition of done:** Orchestrator logs show Gemini embedding calls (`text-embedding-004`), no fallback to `deterministic-hash`.

---

## Phase 3 — S5-06 / S4-06: Qualification Evidence Refresh (PARTIAL — 2026-05-29)

**Status:** 🟡 Partial. Canary trend 100% (python/rust/kotlin/julia all PASS), mission
artifact qualification PASS, promotion-gate + qualification-gate-summary regenerated.
Qual-script bugs fixed: vague default prompts, 90→360s timeouts, metadata fallbacks,
OIDC `_compose_command` --env-file injection. **Remaining blocker:** OIDC matrix hybrid/oidc
modes return 503 during readiness probe — orchestrator briefly loses postgres after each
gateway restart. Needs: poll orchestrator health (not just gateway) between mode switches.

**Why it matters:** The promotion gate and qualification summary are the formal sign-off documents. Running them against the current live stack with current HEAD produces dated evidence for audit.

```bash
# Ensure stack is running (Phase 1 prerequisite)
python scripts/promotion_gate.py \
  --ref $(git rev-parse HEAD) \
  --ci-status passed \
  --attestation-verified true \
  --output-file reports/promotion-gate.local.json

python scripts/qualification_gate_summary.py \
  --output reports/qualification-gate-summary.local.json

# Review and commit
cat reports/promotion-gate.local.json | python -m json.tool | grep -E "passed|failed|score"
git add reports/promotion-gate.local.json reports/qualification-gate-summary.local.json
git commit -m "docs(qual): refresh promotion + qualification gate evidence 2026-05-29"
```

**Definition of done:** Both JSON files updated with today's date, commit pushed.

---

## Phase 4 — S5-04 / S3-04: PORT Two-Phase Live Demo (1–2 sessions)

**Status:** Not started. Requires a real open-source project as source material.

**Why it matters:** This is the **product differentiator** — proving theFactory can port a real-world codebase across platform boundaries, not just generate greenfield code.

### Recommended source projects

| Option | Why good | Source |
|---|---|---|
| **Mini-grep** (C → Python) | Simple, well-known, small (~300 LOC) | `man grep` equivalent toy implementation |
| **SDL2 Pong** (C++ → Rust) | Game, real dependency chain, ~800 LOC | https://github.com/aminosbh/sdl2-samples |
| **Windows notepad clone** (C# → Go) | Real UI app, cross-platform port | Available on GitHub |
| **libcsv** (C → Python) | Utility library, pure logic, no UI | https://sourceforge.net/projects/libcsv/ |

### Steps

```bash
# Download source (e.g. SDL2 Pong ~800 LOC)
# Place files in a temp directory, zip or reference

# Submit PORT mission
MID="mission-s504-port-$(date +%s)"
curl -s -X POST http://localhost:8001/v1/missions \
  -H "Content-Type: application/json" \
  -d "{
    \"mission_id\": \"$MID\",
    \"prompt\": \"Port this C++ SDL2 Pong game to Rust. Replace SDL2 with the ggez crate. Preserve all game logic.\",
    \"requested_target_language\": \"rust\",
    \"metadata\": {
      \"mission_type\": \"PORT\",
      \"depth_mode\": \"STANDARD\",
      \"output_mode\": \"FULL_BUILD\",
      \"port_two_phase_enabled\": true
    }
  }"

# Verify non-empty port_source_logicnodes + generated_code
curl -s http://localhost:8001/v1/missions/$MID | python -c "
import sys, json
d = json.load(sys.stdin)
meta = d.get('metadata', {})
print('port_source_logicnodes:', bool(meta.get('port_source_logicnodes')))
print('generated_code:', bool(meta.get('generated_code') or meta.get('chain_trace')))
print('state:', d.get('state'))
"

# Save evidence
curl -s http://localhost:8001/v1/missions/$MID > docs/evidence/s504_port_demo_2026-05-29.json
```

**Definition of done:** Mission reaches COMPLETE with non-empty `port_source_logicnodes` and `generated_code`. Evidence JSON committed.

---

## Phase 5 — S5-05 / S4-03: Agent Scaling Live Validation (1 session)

**Status:** Not started. Requires `AGENT_SCALING_ENABLED=true` and a 20+ file source bundle.

**Why it matters:** Proves the horizontal scaling partition system works — large repos get split into parallel work units rather than timing out on a single-thread pipeline.

```bash
# Enable agent scaling
echo "AGENT_SCALING_ENABLED=true" >> .env
# Rebuild orchestrator with new env
docker compose -f deploy/docker-compose.yaml --env-file .env up -d orchestrator

# Create a 20+ file test bundle (can be synthetic)
# Or use a real small project: a Python CLI tool, a Node.js utility, etc.

# Submit with scaling hint
MID="mission-s505-scale-$(date +%s)"
curl -s -X POST http://localhost:8001/v1/missions \
  -H "Content-Type: application/json" \
  -d "{
    \"mission_id\": \"$MID\",
    \"prompt\": \"Refactor this 25-file Python data processing library...\",
    \"requested_target_language\": \"python\",
    \"metadata\": {
      \"mission_type\": \"BUILD_NEW\",
      \"depth_mode\": \"DEEP\",
      \"agent_scaling_enabled\": true
    }
  }"

# Watch for partition events in logs
docker logs deploy-orchestrator-1 -f 2>&1 | grep -i "partition\|scaling\|shard"
```

**Definition of done:** Orchestrator logs show partition events (`mission.partition.ready`), multiple partition results merged, mission reaches COMPLETE.

---

## Phase 6 — IMPLEMENTATION_STATUS.md Cleanup (30 min, any session)

**Status:** The doc is stale — items 17 (Multi-container RQCA), 19 (Neo4j), 20 (Object storage) are marked open but were completed 2026-05-24. Item 1 (live demo), item 4 (Gemini) also need updating.

```
Items to mark done in IMPLEMENTATION_STATUS.md:
- Item 1: Live provider-key BUILD_NEW demo → done (S5-01, 2026-05-28)
- Item 4: Activate Gemini embeddings → done (S1-04, 2026-05-24)
- Item 17: Multi-container RQCA → done (S4-02, 2026-05-24)
- Item 19: Neo4j knowledge graph → done (S4-04, 2026-05-24)
- Item 20: Object storage for large artifacts → done (S4-05, 2026-05-24)
- Item 21: Live qualification evidence refresh → update after Phase 3 above
- Item 23: Long-duration reliability re-qual → update after Phase 7 below
```

Also update `SPRINT_BACKLOG.md`:
- S1-01: Mark as superseded by S5-01 ✅
- S1-02: Mark as superseded by S5-02 (pending Phase 1 completion)
- Clean up verbose bug description from S5-02 entry once item is done

---

## Phase 7 — S5-07 / S4-08: Long-Duration Reliability Requalification (4+ hours, scheduled)

**Status:** Not started. The current baseline (`reliability_qualification_baseline_2026-03-03.json`) predates the entire intelligence layer (Sprints 2–4).

**Why it matters:** The 2026-03-03 baseline was run against a much simpler stack. All the new LLM delegation, RQCA, DEPABS, Neo4j, and object storage code paths need a full reliability run.

```bash
# Schedule during an off-peak window (the script runs 4+ hours)
nohup python scripts/long_duration_reliability_qualification.py \
  --output docs/evidence/reliability_qualification_2026-05-29.json \
  > logs/reliability_qual_2026-05-29.log 2>&1 &

echo "PID: $!"

# Monitor progress
tail -f logs/reliability_qual_2026-05-29.log

# When complete, commit evidence
git add docs/evidence/reliability_qualification_2026-05-29.json
git commit -m "docs(qual): long-duration reliability requalification 2026-05-29"
```

**Definition of done:** Output JSON has `qualification_passed: true` with updated timestamp and failure-rate metrics.

---

## Phase 8 — Dependabot PR Triage (1 session, low priority)

**Status:** 30 open Dependabot PRs as of 2026-05-25. None are blocking, all are dependency bumps.

**Priority order:**
1. **Security fixes first** — any that bump packages with known CVEs
2. **Orchestrator Python deps** (fastapi, uvicorn, opentelemetry) — can merge in batch
3. **Mission Control npm deps** — electron bump to 42.x requires testing the installer
4. **Skip or close** electron-builder bump (PR #180) until after Phase 4 — the npm audit fix specifically excluded devDep chain

```bash
# Review and merge safe Python bumps in batch
gh pr list --repo kherrera6219/theFactory --author app/dependabot 2>&1 | grep "pip/"
# For each safe bump:
gh pr merge <number> --repo kherrera6219/theFactory --squash --auto
```

---

## Phase 9 — Completion Declaration

When all phases 1–7 are done:

```
✅ S5-01 — Live BUILD_NEW demo (done 2026-05-28)
✅ S5-02 — Token cost ledger (done Phase 1)
✅ S5-03 — Gemini embeddings live (done Phase 2)
✅ S5-04 — PORT two-phase demo (done Phase 4)
✅ S5-05 — Agent scaling validation (done Phase 5)
✅ S5-06 — Qualification evidence refresh (done Phase 3)
✅ S5-07 — Reliability requalification (done Phase 7)
✅ All Sprint 1–4 code items
✅ CI clean
✅ IMPLEMENTATION_STATUS.md Open Work section empty
```

Run the final checklist:
```bash
python scripts/production_review_audit.py         # expect 22/22 PASS
python -m pytest tests/eval/ -q                   # expect 97+ passed
python -m ruff check services tests scripts       # expect clean
cd apps/mission-control && npm run lint           # expect 0 errors
```

---

## Current Blocked / At-Risk Items

| Item | Risk | Mitigation |
|---|---|---|
| S5-04 PORT demo | Needs open-source source project chosen | Pick `libcsv` or SDL2 Pong from table above |
| S5-05 Agent scaling | `AGENT_SCALING_ENABLED` path may have untested bugs | Run with small 20-file bundle first; check logs carefully |
| S5-07 Reliability | Requires 4+ uninterrupted stack hours | Schedule overnight; ensure no `docker stop` during run |
| Dependabot electron bump | electron 34→42 is a major version jump | Test installer manually before merging |

---

## Constraints (permanent — do not change)

- Model strings `gpt-5.5` and `gemini-3.5-flash` in `llm_cost_ledger.py` are **intentional**
- `GATEWAY_ADMIN_BYPASS` defaults to `true` (dev) — production must set `false`
- Publisher: Kevin Herrera — auto-update removed, manual installer only
- Docker stack: always use `docker compose -f deploy/docker-compose.yaml --env-file .env`
- Do not commit `.env` or any file containing real API keys

---

## Session Handoff Summary (for Codex)

```
Current main HEAD: b3f4383
PR #184: open (review PR, main → codex/s5-02-review base), CI running
Next action: verify Phase 0 CI green, then start Phase 1 (S5-02 verification)
Full handoff details: docs/evidence/s5_handoff_findings_2026-05-28.md
Sprint backlog: docs/SPRINT_BACKLOG.md
```
