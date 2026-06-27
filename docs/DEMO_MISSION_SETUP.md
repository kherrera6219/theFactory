# Live Demo Mission — Setup Guide
## theFactory / Holy Grail Refinery

Document version: 2026.06.13
Last updated: 2026-06-27
Status: Canonical
Audience: Operators and developers

**Date:** 2026-06-13 | **Prerequisite:** Docker Desktop running, repo cloned

---

## Step 1 — Generate TLS certificates

```powershell
# From repo root (C:\software\Holygrail\theFactory)
make tls-certs
```

This writes certs to `deploy/.local/redis-certs/` and `deploy/.local/postgres-certs/`.
Only needed once per machine. Already done if those directories exist.

---

## Step 2 — Create .env from template

```powershell
Copy-Item .env.example .env
```

---

## Step 3 — Set required secrets in .env

Open `.env` and replace these values. Everything else can stay at defaults for a local run.

### 3a — Generate local service keys (run once, paste results)

Open PowerShell and run:
```powershell
# Generates 6 random 32-char hex keys — paste each into .env
1..6 | ForEach-Object { [System.BitConverter]::ToString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).Replace("-","").ToLower() }
```

Paste the 6 keys into these `.env` fields (one key each):
```
ORCHESTRATOR_ADMIN_API_KEY=<key1>
INTERNAL_SERVICE_API_KEY=<key2>
POD_A_SERVICE_API_KEY=<key3>
POD_B_SERVICE_API_KEY=<key4>
POD_C_SERVICE_API_KEY=<key5>
MCP_API_KEY=<key6>
```

Also set (can reuse or generate more):
```
ORCHESTRATOR_API_KEYS=<key1>=mutate,read
REDIS_PASSWORD=<any 32-char string — must match what's already in deploy/.local if certs generated>
POSTGRES_PASSWORD=<any 32-char string>
APPROVAL_HMAC_SECRET=<any 32-char hex>
```

### 3b — Set LLM provider

**Default test path — Gemini Flash 3.5 (all agents)**
```
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIza...your key...
GEMINI_MODEL=gemini-3.5-flash
GEMINI_THINKING_LEVEL=high
```

Mission Control Settings still lets you select one of three vault-slot model routes:
```
OPENAI_MODEL=gpt-5.5
OPENAI_REASONING_EFFORT=high
ANTHROPIC_MODEL=claude-opus-4-8
GEMINI_MODEL=gemini-3.5-flash
GEMINI_THINKING_LEVEL=high
```

For this test pass, all 41 agents default to Gemini Flash 3.5 with high thinking.

### 3c — Verify model strings are valid

The current model assignments in `agent_integrations.py` are:
- All agents: `gemini-3.5-flash` (Gemini, high thinking)
- Settings dropdown choices: `gpt-5.5`, `claude-opus-4-8`, `gemini-3.5-flash`

If any of these model strings are invalid for your account, the agent falls back
to deterministic routing — the mission will complete but output will be a stub.
Check the `/v1/health` endpoint after stack start to see which providers are live.

---

## Step 4 — Start the stack

```powershell
# From repo root
make up
```

Wait ~45 seconds for all services to become healthy. Check:
```powershell
docker compose -f deploy/docker-compose.yaml ps
```

All services should show `(healthy)`.

---

## Step 5 — Run the demo mission

```powershell
# From repo root — uses ORCHESTRATOR_ADMIN_API_KEY from .env automatically
$env:ORCHESTRATOR_ADMIN_API_KEY = "your-key-from-step-3a"
python scripts/run_demo_mission.py
```

Or specify explicitly:
```powershell
python scripts/run_demo_mission.py --api-key "your-key" --language python
python scripts/run_demo_mission.py --api-key "your-key" --language javascript
python scripts/run_demo_mission.py --api-key "your-key" --dry-run   # connectivity check only
```

---

## Step 6 — Interpret results

### ✅ Full success
```
Final state: COMPLETE
PM Feature Contract   : ✅
CEO Refined-IR Contract: ✅
Generated output      : ✅  fetch_weather.py (python, 847 chars, source=llm)
PM Delivery Summary   : ✅  "Python Weather Fetch Function"
```

### ⚠ Partial — fallback output
```
Generated output: ✅  output.py (python, 0 chars, source=fallback)
⚠ Output is a FALLBACK placeholder — LLM call failed.
```
**Cause:** API key not set, invalid model string, or provider timeout.
**Fix:** Check `docker compose logs orchestrator | tail -100` for the LLM error.

### ❌ FAILED state
```
Final state: FAILED
```
**Diagnose:**
```powershell
docker compose -f deploy/docker-compose.yaml logs orchestrator --tail 100
docker compose -f deploy/docker-compose.yaml logs pod-a-worker --tail 50
```

### ❌ Connectivity error (exit code 2)
```
❌ api-gateway /readyz: UNREACHABLE
```
**Fix:** Stack not up. Run `make up` and wait for healthy status.

---

## Step 7 — View in Mission Control UI

Open `http://localhost:3100` in your browser.

- **Chat page** — submit missions via natural language
- **Missions page** — see live state progression through all 11 phases
- **Mission Detail** — chain trace, LogicNodes, generated output, audit evidence
- **Agents page** — toggle Runtime vs Conceptual view of all 41 agents
- **Protocol Bus** — live Protocol stream monitor

---

## Minimum viable .env checklist

Before running, confirm these are set (not `CHANGE_ME`):

- [ ] `ORCHESTRATOR_ADMIN_API_KEY` — non-default value
- [ ] `INTERNAL_SERVICE_API_KEY` — non-default value
- [ ] `MCP_API_KEY` — non-default value
- [ ] `REDIS_PASSWORD` — consistent with what's used in TLS certs
- [ ] `POSTGRES_PASSWORD` — consistent with DB
- [ ] `LLM_PROVIDER` — set to `gemini` for the default all-agent test path
- [ ] `GEMINI_API_KEY` — set for live LLM output

The script will catch and report missing/disabled provider configuration before submitting.
