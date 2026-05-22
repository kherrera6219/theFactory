# theFactory / Holy Grail Refinery
## QC Master Checklist
**Run at end of every phase and at final release gate**
**Date format for evidence files: YYYY-MM-DD**

---

## How to Use This Checklist

This checklist has three levels:

- **Phase Gate** — run after every individual phase. Must be 100% before starting the next phase.
- **Tier Gate** — run after each tier (Tiers 1–5). Stricter than phase gate. Blocks release.
- **Release Gate** — run once before marking the system production-ready. Every item must pass.

Each section lists the exact command to run and the exact expected output.
Any deviation is a blocking defect — document it in `reports/qc-defects.md` before proceeding.

---

# SECTION 1 — STATIC ANALYSIS GATE
**Run after:** every phase
**Blocking:** yes

## 1.1 Python linting — zero errors
```bash
ruff check services tests scripts
```
Expected: no output, exit code 0.
Failure modes: import errors, undefined names, unused imports, line length.
Fix before proceeding.

## 1.2 TypeScript strict compilation — zero errors
```bash
cd apps/mission-control
npx tsc --noEmit
```
Expected: no output, exit code 0.
Failure modes: type mismatches, missing properties on interface, `any` escapes.
`any` casts added during intelligence layer work are technical debt — log them
in `reports/ts-debt.md` and fix within 2 phases.

## 1.3 ESLint — zero errors, warnings tolerated
```bash
cd apps/mission-control
npm run lint
```
Expected: 0 errors (warnings acceptable but track them).

## 1.4 Schema validation — all schemas valid
```bash
python scripts/validate_schemas.py
```
Expected: `All schemas valid` for every file in `schemas/`.
New schemas added in Phases 8–11 (AIM, fetch_result) must be added to this script.

## 1.5 Refined-IR catalog build — no import errors
```bash
python scripts/build_refined_ir_catalog.py
```
Expected: exits 0. Any import error means a broken dependency.

---

# SECTION 2 — PYTHON TEST SUITE GATE
**Run after:** every phase
**Blocking:** yes

## 2.1 Full test suite with coverage
```bash
make test
```
Expected:
- All tests pass (0 failures, 0 errors)
- Global coverage ≥ 80%
- Module-level thresholds met:
  - `audit-worker/audit_worker/main.py` ≥ 90%
  - `semantic-bus-mcp/semantic_bus/mcp_server.py` = 100%
  - `orchestrator/protocol.py` = 100%
  - `orchestrator/agent_personas.py` = 100%
  - `orchestrator/agent_integrations.py` = 100%
  - `orchestrator/agent_registry.py` = 100%

If coverage drops below threshold after adding new code:
1. Check `coverage.xml` to identify uncovered lines
2. Add tests before marking phase complete — do not lower the threshold

## 2.2 Fast suite (verify no import-time crashes)
```bash
pytest --collect-only -q 2>&1 | tail -5
```
Expected: `X tests collected` with 0 errors in collection.
Collection errors mean broken imports — fix immediately.

## 2.3 Regression contract tests (protocol topics)
```bash
pytest tests/services/test_regression_contracts.py -v
```
Expected: all PASS. These lock the protocol topic names.
If any new topics were added in a phase, add them to this test.

## 2.4 Golden delegation tests (LLM fallback routing)
```bash
pytest tests/eval/test_llm_delegation_golden.py -v
```
Expected: all PASS. These verify deterministic fallback produces correct agent IDs
for all 20 languages when LLM is offline.

## 2.5 Prompt safety tests
```bash
pytest tests/services/test_llm_delegation_prompt_safety.py -v
```
Expected: all PASS. These verify injection patterns are stripped from prompts.

## 2.6 Agent base unit tests
```bash
pytest tests/services/test_agent_base_unit.py tests/services/test_agent_core_unit.py -v
```
Expected: all PASS.

## 2.7 Mission flow v2 unit tests
```bash
pytest tests/services/test_mission_flow_v2.py tests/services/test_mission_flow_unit.py -v
```
Expected: all PASS. After each phase that modifies `mission_flow_v2.py`,
verify test count has not decreased (new code paths must be tested).

## 2.8 Build artifact tests
```bash
pytest tests/services/test_build_artifacts_unit.py -v
```
Expected: all PASS. After Phase 2 (pipeline validation), verify the
`generated_code` artifact path is tested.

## 2.9 Security tests
```bash
pytest tests/security/ -v
```
Expected: all PASS. Tests for auth bypass, state mutation, pod assignment conflicts.

---

# SECTION 3 — FRONTEND TEST GATE
**Run after:** every phase that touches UI files
**Blocking:** yes

## 3.1 Mission Control unit tests
```bash
cd apps/mission-control
npm run test -- --passWithNoTests
```
Expected: all PASS.

## 3.2 Mission Control build — zero errors
```bash
cd apps/mission-control
npm run build
```
Expected: exits 0, no TypeScript or webpack errors.
Build errors are blocking. Next.js lint warnings during build are acceptable
but must be tracked.

## 3.3 Playwright E2E tests (mocked)
```bash
make test-ui-e2e
```
Expected: all PASS against the mocked API.
After Phases 3 and 10, confirm new E2E scenarios are added for:
- PM chat → feature contract display
- Mission COMPLETE → delivery banner visible
- Download artifact button functional

---

# SECTION 4 — INFRASTRUCTURE GATE
**Run after:** every phase
**Blocking:** yes

## 4.1 Compose config validation — all overlay permutations
```bash
make compose-validate
```
Expected: all 4 compose permutations render without errors.
Failure means a new environment variable was added without updating `.env.example`.

## 4.2 Docker build — all 7 services
```bash
docker compose -f deploy/docker-compose.yaml build --no-cache 2>&1 | tail -20
```
Expected: `Successfully built` for each service. No layer errors.
Most common failure: new Python dependency not in `requirements.txt`.

## 4.3 Stack health — all services report healthy
```bash
make up
sleep 30
docker compose -f deploy/docker-compose.yaml ps
```
Expected: all services show `(healthy)`. Any `(unhealthy)` or `Exit` state
is blocking.

Check individual service logs for unhealthy containers:
```bash
docker logs theFactory-orchestrator-1 --tail 50
docker logs theFactory-api-gateway-1 --tail 50
docker logs theFactory-pod-a-1 --tail 50
```

## 4.4 All health endpoints return ready
```bash
for PORT in 8100 8101 8102 8103 8104; do
  echo -n "Port $PORT: "
  curl -sf http://localhost:$PORT/readyz | python -c "import sys,json; d=json.load(sys.stdin); print('READY' if d.get('ready') else 'NOT READY')" 2>/dev/null || echo "UNREACHABLE"
done
```
Expected: `READY` for each port that has a service.

## 4.5 Redis connectivity
```bash
docker exec theFactory-redis-1 redis-cli ping
```
Expected: `PONG`

## 4.6 PostgreSQL connectivity and migrations
```bash
docker exec theFactory-postgres-1 psql \
  -U ${POSTGRES_USER:-hgr_admin} \
  -d ${POSTGRES_DB:-hgr_runtime} \
  -c "SELECT migration_id FROM schema_migrations ORDER BY applied_at DESC LIMIT 5;"
```
Expected: lists the 5 most recent migration IDs including latest phase migration.
Confirms all V00X migrations applied successfully.

## 4.7 Qdrant health
```bash
curl -sf http://localhost:6333/health | python -m json.tool
```
Expected: `{"status": "ok"}` or similar.

---

# SECTION 5 — PRODUCTION AUDIT GATE
**Run after:** every phase
**Blocking:** CRITICAL and HIGH checks only. MEDIUM may have open items.

## 5.1 Run full audit
```bash
python scripts/production_review_audit.py --json > reports/audit-$(date +%Y-%m-%d).json
python scripts/production_review_audit.py
```
Expected for phase gate:
- All CRITICAL checks: PASS
- All HIGH checks: PASS (or documented exception with resolution date)
- MEDIUM checks: track open items, fix within 2 phases

Save the JSON output to `reports/` for trend tracking.

## 5.2 Model inventory — zero blocked agents
```bash
python scripts/export_agent_model_inventory.py \
  --output-file reports/model-inventory-$(date +%Y-%m-%d).json
python -c "
import json
data = json.load(open('reports/model-inventory-$(date +%Y-%m-%d).json'))
blocked = [a for a in data['agents'] if not a['production_approved']]
print(f'Blocked: {len(blocked)}')
for a in blocked: print(f'  {a[\"agent_id\"]}: {a[\"model\"]} ({a[\"lifecycle\"]})')
assert len(blocked) == 0, 'Model governance failure — blocked agents present'
print('PASS: all agents production-approved')
"
```

## 5.3 Promotion gate
```bash
make promotion-gate
```
Expected: `APPROVED` decision in `reports/promotion-decision.local.json`.
This is a strict gate — do not bypass it.

---

# SECTION 6 — INTELLIGENCE PIPELINE GATE
**Run after:** Phase 2 completion and every subsequent phase
**Blocking:** yes for Tier 1 gate; informational for Phase 1

## 6.1 LLM call smoke test — CEO produces real contract
```bash
LIVE_STACK_ENABLED=1 python - <<'EOF'
import asyncio, json, sys, os
sys.path.insert(0, 'services/orchestrator')
from orchestrator.llm_delegation import (
    generate_ceo_delegation, generate_mission_contract
)

async def main():
    ctx = {"mission_id": "qc-ceo-001", "requested_target_language": "python",
           "routing_version": "v1.1", "prompt": "Write a CSV reader"}
    delegation = await generate_ceo_delegation(
        mission_context=ctx, requested_target_language="python"
    )
    print(f"Delegation source: {delegation.get('source')} (must be 'llm')")
    assert delegation.get('source') == 'llm', "CEO delegation fell back to deterministic"
    
    contract = await generate_mission_contract(
        mission_context=ctx, prompt="Write a CSV reader",
        mission_type="BUILD_NEW", output_mode="FULL_BUILD",
        requested_target_language="python",
        ceo_delegation=delegation,
    )
    print(f"Contract source: {contract.get('source')} (must be 'llm')")
    print(f"LogicNode requirements: {len(contract.get('logicnode_requirements', []))}")
    assert contract.get('source') == 'llm', "Mission contract fell back to deterministic"
    assert len(contract.get('logicnode_requirements', [])) > 0, "Contract has no requirements"
    print("PASS: CEO produces real Refined-IR Contract")

asyncio.run(main())
EOF
```

## 6.2 Specialist code generation smoke test
```bash
LIVE_STACK_ENABLED=1 python - <<'EOF'
import asyncio, sys
sys.path.insert(0, 'services/orchestrator')
from orchestrator.llm_delegation import generate_code_from_contract

async def main():
    contract = {
        "contract_summary": "Write a Python function to count word frequency in a string",
        "target_languages": ["python"],
        "output_format": "standalone_script",
        "logicnode_requirements": [
            {"domain": "string_ops", "concept": "tokenize", "intent": "Split string into words", "priority": "HIGH"},
            {"domain": "data_structures", "concept": "frequency_map", "intent": "Count occurrences of each word", "priority": "HIGH"},
        ],
        "acceptance_criteria": ["function returns dict of word:count", "case-insensitive"],
        "source": "llm",
    }
    result = await generate_code_from_contract(
        mission_context={"mission_id": "qc-codegen-001"},
        specialist_agent_id="AGENT-14-PYTHON",
        mission_contract=contract,
        logicnodes=[],
        target_language="python",
    )
    code = result.get("generated_code") or ""
    print(f"Source: {result.get('source')}")
    print(f"Code length: {len(code)} chars")
    print(f"Filename: {result.get('filename')}")
    print(f"--- Code preview ---\n{code[:400]}\n---")
    assert result.get('source') != 'fallback', "Codegen fell back to deterministic stub"
    assert len(code) > 50, "Generated code is too short to be real"
    assert "def " in code or "function " in code, "No function definition in generated code"
    print("PASS: Specialist generates real code")

asyncio.run(main())
EOF
```

## 6.3 End-to-end mission produces generated artifact
```bash
LIVE_STACK_ENABLED=1 pytest tests/services/test_live_mission_flow_integration.py -v -k "not slow"
```

## 6.4 Generated output artifact — verify build artifact type
After a COMPLETE mission exists on the live stack:
```bash
MISSION_ID=$(curl -sf http://localhost:8100/v1/missions \
  -H "x-api-key: $(grep ADMIN_API_KEY .env | cut -d= -f2)" \
  | python -c "import sys,json; ms=json.load(sys.stdin)['missions']; 
    completed=[m for m in ms if m['state']=='COMPLETE']; 
    print(completed[0]['mission_id'] if completed else 'NONE')")

echo "Checking mission: $MISSION_ID"
curl -sf http://localhost:8100/v1/missions/$MISSION_ID/chain-trace \
  -H "x-api-key: $(grep ADMIN_API_KEY .env | cut -d= -f2)" \
  | python -c "
import sys, json
data = json.load(sys.stdin)
meta = data.get('metadata', {})
artifacts = meta.get('build_artifacts', []) or meta.get('artifacts', [])
generated = meta.get('generated_output', {})
for a in artifacts:
    atype = a.get('artifact_type') or a.get('type', '')
    print(f'  Artifact: {atype} — status: {a.get(\"status\")}')
code = (generated or {}).get('generated_code', '')
print(f'Generated code present: {len(code) > 0} ({len(code)} chars)')
if not code:
    print('FAIL: No generated code in mission output')
    sys.exit(1)
print('PASS: Mission has generated output')
"
```

---

# SECTION 7 — DATA INTEGRITY GATE
**Run after:** any phase modifying storage, migrations, or chain events

## 7.1 Database migrations applied — no pending
```bash
python - <<'EOF'
import sys
sys.path.insert(0, 'services/orchestrator')
from orchestrator.migrations import run_migrations, get_applied_migrations
# Check that all V00X files match applied list
import os
from pathlib import Path
migration_dir = Path('services/orchestrator/orchestrator/migrations')
files = sorted(f.stem for f in migration_dir.glob('V*.sql'))
print(f"Migration files: {files}")
# If connected to live DB, compare against schema_migrations table
print("Run: docker exec theFactory-postgres-1 psql -c 'SELECT * FROM schema_migrations ORDER BY applied_at;'")
EOF
```

## 7.2 LogicNode schema validation — all nodes conform
After a mission produces logicnodes:
```bash
python - <<'EOF'
import json, jsonschema
from pathlib import Path
schema = json.loads(Path('schemas/logicnode.schema.json').read_text())
# Fetch logicnodes from live stack if available
# Or test with example:
example = json.loads(Path('examples/logicnode.example.json').read_text())
jsonschema.validate(instance=example, schema=schema)
print("PASS: Example logicnode validates against schema")
EOF
```

## 7.3 Chain event audit — no orphaned events
```bash
docker exec theFactory-postgres-1 psql \
  -U ${POSTGRES_USER:-hgr_admin} \
  -d ${POSTGRES_DB:-hgr_runtime} \
  -c "SELECT state, COUNT(*) FROM missions GROUP BY state ORDER BY state;"
```
Expected: no missions stuck in intermediate states (`PM_INTAKE`, `RUNNING`) longer than 10 minutes.
Any stuck mission is a lifecycle bug — check orchestrator logs.

## 7.4 Review approval HMAC integrity check
```bash
docker exec theFactory-postgres-1 psql \
  -U ${POSTGRES_USER:-hgr_admin} \
  -d ${POSTGRES_DB:-hgr_runtime} \
  -c "SELECT COUNT(*) FROM review_approvals WHERE hmac_digest IS NULL;"
```
Expected: 0 rows without HMAC digest. Any NULL indicates an approval written
before V004 migration — investigate and recompute digests.

---

# SECTION 8 — SECURITY GATE
**Run after:** Tier 2 (Phases 3–7) and Release Gate
**Blocking:** yes

## 8.1 Dependency vulnerability scan
```bash
pip-audit --requirement services/orchestrator/requirements.txt \
          --requirement services/pod-worker/requirements.txt \
          --requirement services/api-gateway/requirements.txt \
  2>&1 | tail -20
```
Expected: `No known vulnerabilities found` or only informational advisories.
Any HIGH or CRITICAL CVE is blocking — update the dependency before release.

## 8.2 SAST scan (Bandit)
```bash
bandit -r services/ -ll -ii --format json -o reports/bandit-$(date +%Y-%m-%d).json
python -c "
import json
data = json.load(open('reports/bandit-$(date +%Y-%m-%d).json'))
high = [r for r in data['results'] if r['issue_severity'] == 'HIGH']
medium = [r for r in data['results'] if r['issue_severity'] == 'MEDIUM']
print(f'HIGH: {len(high)}, MEDIUM: {len(medium)}')
for r in high:
    print(f'  {r[\"filename\"]}:{r[\"line_number\"]}: {r[\"issue_text\"]}')
if high:
    raise SystemExit(1)
print('PASS: No HIGH severity findings')
"
```

## 8.3 No secrets in working tree
```bash
# Check for API key patterns in staged/committed files
git grep -r "sk-[A-Za-z0-9_-]\{20,\}" -- '*.py' '*.ts' '*.tsx' '*.yaml' '*.yml' '*.json' \
  ':!*.example' ':!tests/' ':!docs/' 2>/dev/null | head -20
echo "Exit code: $?"
```
Expected: no output. Any match is a blocking security defect.

## 8.4 No private keys in git history
```bash
git log --all --full-history -- \
  "deploy/postgres/certs/server.key" \
  "deploy/redis/certs/redis.key" \
  2>/dev/null | head -5
echo "Lines above should be empty"
```
Expected: zero output. If output exists, Phase 17 git scrub was not completed.

## 8.5 Prompt injection hardening — PII guard test
```bash
pytest tests/services/test_pii_guard.py tests/services/test_prompt_guard.py -v
```
Expected: all PASS.

## 8.6 Auth mode not silently downgraded
```bash
grep -r "AUTH_MODE" deploy/ services/api-gateway/ services/orchestrator/ \
  | grep -v ".example\|#\|test" \
  | grep -i "none\|disable\|off" | head -10
echo "Lines above should be empty"
```
Expected: no output. Silent auth bypass patterns must not appear in production config.

---

# SECTION 9 — OBSERVABILITY GATE
**Run after:** Tier 3 (Phases 8–11) and Release Gate

## 9.1 Prometheus scrape targets healthy
```bash
make monitor-up
sleep 10
curl -sf http://localhost:9090/api/v1/targets \
  | python -c "
import sys, json
data = json.load(sys.stdin)
active = data['data']['activeTargets']
down = [t for t in active if t['health'] != 'up']
print(f'Targets: {len(active)} total, {len(down)} down')
for t in down:
    print(f'  DOWN: {t[\"labels\"].get(\"job\", \"?\")} — {t.get(\"lastError\", \"\")}')
"
```
Expected: 0 targets down.

## 9.2 Jaeger receives traces from live missions
After running a mission:
```bash
curl -sf "http://localhost:16686/api/services" \
  | python -c "import sys,json; print(json.load(sys.stdin)['data'])"
```
Expected: `['api-gateway', 'orchestrator', 'pod-worker']` (or similar service names) in output.

## 9.3 Metrics endpoint responds on all services
```bash
for PORT in 8100 8101 8102 8103 8104; do
  COUNT=$(curl -sf http://localhost:$PORT/metrics 2>/dev/null | grep -c "^# HELP" || echo 0)
  echo "Port $PORT: $COUNT metric families"
done
```
Expected: > 0 metric families per service.

## 9.4 Alert rules load without errors
```bash
docker exec theFactory-prometheus-1 \
  promtool check rules /etc/prometheus/rules/thefactory-alerts.yml 2>&1
```
Expected: `SUCCESS: X rules found` with no syntax errors.

---

# SECTION 10 — DEMO MISSION GATE
**Run after:** Phase 2 (first time), then Phase 18 (release gate)
**Blocking:** yes for Tier 1 and Release gate

## 10.1 All canonical demos complete successfully
```bash
DEMO_API_KEY=$(grep ADMIN_API_KEY .env | cut -d= -f2) \
  make demo
```
Expected: all 3 demo tests PASS.
- Demo 1: Python word frequency counter — `state: COMPLETE`, `generated_code` contains `def`
- Demo 2: JavaScript debounce — `state: COMPLETE`, `generated_code` contains function
- Demo 3: Analyze-only Python math — `state: COMPLETE`, logicnodes present

## 10.2 Download endpoint works for each demo
```bash
# After demos complete, test download for last COMPLETE mission
MISSION_ID=$(curl -sf http://localhost:8100/v1/missions \
  -H "x-api-key: $(grep ADMIN_API_KEY .env | cut -d= -f2)" \
  | python -c "import sys,json; ms=json.load(sys.stdin)['missions']; 
    print(next(m['mission_id'] for m in ms if m['state']=='COMPLETE'), end='')")

HTTP_STATUS=$(curl -sf -o /tmp/artifact-download.txt -w "%{http_code}" \
  http://localhost:8100/v1/missions/$MISSION_ID/artifact \
  -H "x-api-key: $(grep ADMIN_API_KEY .env | cut -d= -f2)")

echo "HTTP status: $HTTP_STATUS"
echo "File size: $(wc -c < /tmp/artifact-download.txt) bytes"
[[ "$HTTP_STATUS" == "200" ]] && echo "PASS" || echo "FAIL"
```

---

# SECTION 11 — DISASTER RECOVERY GATE
**Run at:** Tier 5 (Phase 17) and Release Gate

## 11.1 Backup script runs without error
```bash
make backup
ls -la backups/ | tail -5
```
Expected: new backup file created in `backups/` with `.sql` extension and manifest JSON.

## 11.2 DR drill — timed restore
```bash
# Record start time
START=$(date +%s)
make down
make up
sleep 30

# Record end time
END=$(date +%s)
RTO=$((END - START))
echo "RTO: ${RTO}s"

# Verify data survived
docker exec theFactory-postgres-1 psql \
  -U ${POSTGRES_USER:-hgr_admin} \
  -d ${POSTGRES_DB:-hgr_runtime} \
  -c "SELECT COUNT(*) FROM missions;"
```
Expected: `RTO < 300s` (5 minutes). Table row count matches pre-drill count.
Record results in `docs/evidence/dr_drill_$(date +%Y-%m-%d).json`.

## 11.3 DR evidence file present
```bash
ls docs/evidence/dr_drill_*.json 2>/dev/null | head -3
```
Expected: at least one recent file. Missing means Phase 17 was not completed.

---

# SECTION 12 — RELEASE FINAL GATE
**Run once, at the end of Phase 18, before marking production-ready**

All previous section checks must pass PLUS:

## 12.1 Full validate pipeline
```bash
make validate
```
Expected: exits 0.

## 12.2 Full qualification summary
```bash
make qualification-summary
cat docs/evidence/qualification_gate_summary_latest.json | python -c "
import sys, json
data = json.load(sys.stdin)
gates = data.get('gates') or data
print(json.dumps(gates, indent=2))
"
```
Expected: all gates `passed: true`.

## 12.3 DORA metrics — deployment frequency acceptable
```bash
make dora-metrics
cat docs/evidence/dora_metrics_latest.json | python -c "
import sys, json
data = json.load(sys.stdin)
print('Deployment frequency:', data.get('deployment_frequency'))
print('Lead time (median days):', data.get('lead_time_median_days'))
print('Change failure rate:', data.get('change_failure_rate'))
print('MTTR (hours):', data.get('mttr_hours'))
"
```

## 12.4 OpenAPI spec exports without error
```bash
make up
sleep 10
make openapi
ls -la reports/openapi.json
```
Expected: `reports/openapi.json` contains valid OpenAPI 3.x spec.

## 12.5 Final promotion gate
```bash
make promotion-gate
cat reports/promotion-decision.local.json \
  | python -c "import sys,json; d=json.load(sys.stdin); 
    print('Decision:', d.get('decision')); 
    assert d.get('decision') == 'APPROVED', 'Promotion gate BLOCKED'"
```
Expected: `Decision: APPROVED`

## 12.6 IMPLEMENTATION_STATUS.md reflects all 18 phases
```bash
python - <<'EOF'
from pathlib import Path
text = Path('docs/IMPLEMENTATION_STATUS.md').read_text()
phases = [f"Phase {i}" for i in range(1, 19)]
missing = [p for p in phases if p not in text]
print(f"Missing phases in IMPLEMENTATION_STATUS.md: {missing}")
assert not missing, f"Update IMPLEMENTATION_STATUS.md before release"
print("PASS")
EOF
```

---

# SECTION 13 — DEFECT TRACKING

All defects found during QC are recorded in `reports/qc-defects.md`.
Format for each defect:

```markdown
## DEFECT-XXX — [Short title]
- **Found in:** Phase X, Section Y.Z
- **Severity:** CRITICAL | HIGH | MEDIUM | LOW
- **Command that revealed it:** `make test` / `pytest ...` / `curl ...`
- **Observed:** [exact error output]
- **Expected:** [what should have happened]
- **Root cause:** [after investigation]
- **Fix:** [what was changed]
- **Fixed in:** [commit hash or date]
- **Verified:** [ ] re-run check after fix
```

Defects with severity CRITICAL or HIGH must be fixed before the current phase
is marked complete. MEDIUM defects must be fixed within 2 phases. LOW defects
go to the backlog.

---

# PHASE COMPLETION SIGN-OFF TEMPLATE

Copy this block into `docs/IMPLEMENTATION_STATUS.md` when marking a phase complete:

```markdown
## Phase X — [Name] — COMPLETE
**Date:** YYYY-MM-DD
**QC Checks passed:**
- [ ] Section 1: Static analysis (ruff, tsc, eslint, schema validation)
- [ ] Section 2: Python tests (make test — X/Y passing, coverage Z%)
- [ ] Section 3: Frontend tests (npm test, npm build, Playwright)
- [ ] Section 4: Infrastructure (compose validate, docker build, stack health)
- [ ] Section 5: Production audit (X/Y checks passing)
- [ ] Section 6: Intelligence pipeline (LLM calls return source=llm)
- [ ] Section 7: Data integrity (migrations, schema validation)
**Defects found:** [DEFECT-XXX or none]
**Notes:** [anything unusual about this phase]
```
