# Phase 26 — Production Hardening and Release Gate

**Status:** Planned
**Last updated:** 2026-05-18
**Depends on:** Phase 17 (DR hardening planned), Phase 25 (AI safety evals),
Phase 18 (demo missions), Release Completion Plan Phases 1–6

---

## Problem

The release completion plan (`docs/RELEASE_COMPLETION_PLAN.md`) defines six
conditions that must all be true before theFactory is production-ready. After
Phases 15–25, all capability gaps are closed but four release blockers remain:

1. **Git history contains committed TLS private keys** — flagged in the March
   2026 master audit. History scrub with `git-filter-repo` has been documented
   but not executed.
2. **Qualification evidence is stale** — several `docs/evidence/` files were
   generated against earlier builds and haven't been refreshed since the
   Phase 1–14 intelligence layer work.
3. **DR drill has never been executed live** — `scripts/dr_drill.ps1` exists
   but no `dr_drill_phase17_*.json` evidence file exists.
4. **Final release gate checklist** — the `scripts/promotion_gate.py` exists
   but several check IDs that cover intelligence-layer features are not yet
   wired.

This phase closes all four blockers and produces the evidence package required
for a production release claim.

---

## Change 1 — Git history scrub

Execute the private key removal from git history:

```bash
# Install
pip install git-filter-repo

# Remove both committed key files
git filter-repo --path deploy/postgres/certs/server.key --invert-paths
git filter-repo --path deploy/redis/certs/redis.key --invert-paths

# Regenerate fresh development certs
make tls-certs

# Verify history is clean
git log --all -- deploy/postgres/certs/server.key
# Expected: no output

git log --all -- deploy/redis/certs/redis.key
# Expected: no output
```

After scrub, force-push all branches and tags:
```bash
git push --force --all origin
git push --force --tags origin
```

Update `.gitleaks.toml` to add the cert paths to the allow-list so the
pre-commit hook does not re-flag the now-scrubbed history entries.

Add audit check in `scripts/production_review_audit.py`:
```python
def check_no_committed_keys() -> AuditResult:
    import subprocess
    for path in ["deploy/postgres/certs/server.key", "deploy/redis/certs/redis.key"]:
        result = subprocess.run(
            ["git", "log", "--all", "--", path],
            capture_output=True, text=True
        )
        if result.stdout.strip():
            return _result(
                check_id="SEC-KEY-001",
                priority="CRITICAL",
                description=f"Private key found in git history: {path}",
                passed=False,
            )
    return _result(
        check_id="SEC-KEY-001",
        priority="CRITICAL",
        description="No private keys in git history",
        passed=True,
    )
```

---

## Change 2 — DR drill execution and evidence

Execute the live DR drill procedure defined in `Phase_17_DR_Evidence.md`
(from `Phase_12_to_18_Quality_Production.md`):

```bash
# Step 1: backup
make backup
# Records to backups/ with manifest and SHA256

# Step 2: record stack state
python scripts/qualification_gate_summary.py \
  --output reports/pre-dr-state.json

# Step 3: stop all services
make down

# Step 4: restart and time recovery
time make up

# Step 5: verify backup integrity
python scripts/verify_backup_artifacts.py \
  --output reports/dr-drill-latest.json

# Step 6: run full test suite against restored stack
make test
```

Record RTO (time from `make down` to all services healthy).

Store evidence:
```
docs/evidence/dr_drill_phase26_2026-MM-DD.json
```

Evidence schema:
```json
{
  "drill_date": "2026-MM-DD",
  "phase": "26",
  "rto_seconds": 142,
  "services_recovered": ["redis", "postgres", "qdrant", "orchestrator",
                          "api-gateway", "pod-worker", "audit-worker",
                          "mission-control"],
  "backup_verified": true,
  "test_suite_result": "pass",
  "operator": "kevin"
}
```

Add `DR-001` check to `production_review_audit.py` (already defined in
Phase 17 plan — wire it here).

---

## Change 3 — Qualification evidence refresh

Re-run all stale qualification scripts against the current codebase and
replace evidence files:

```bash
# Promotion gate
python scripts/promotion_gate.py \
  --output reports/promotion-gate.local.json

# Qualification summary
python scripts/qualification_gate_summary.py \
  --output reports/qualification-gate-summary.local.json

# Master audit
python scripts/production_review_audit.py \
  --output reports/master_audit_$(date +%Y-%m-%d).md

# Mission artifact qualification
python scripts/mission_artifact_qualification.py \
  --output docs/evidence/mission_artifact_qualification_phase26.json

# Operator route auth matrix
python scripts/operator_route_auth_matrix_qualification.py \
  --output docs/evidence/operator_route_oidc_matrix_phase26.json
```

All output files go to their canonical paths. Stale pre-May-2026 evidence
files in `docs/evidence/` are NOT deleted — they remain as historical
record, but `docs/IMPLEMENTATION_STATUS.md` is updated to point to the
Phase 26 evidence as current.

---

## Change 4 — Wire intelligence-layer checks into promotion gate

`scripts/promotion_gate.py` currently has checks for infrastructure,
security, and baseline mission flow. Add checks for the intelligence-layer
capabilities added in Phases 15–25:

```python
def check_pm_contract_in_chain_trace() -> GateResult: ...
    # Verify a recent COMPLETE mission has feature_contract in chain trace

def check_ceo_logic_clusters() -> GateResult: ...
    # Verify a recent COMPLETE mission has logic_clusters with >= 1 cluster

def check_generated_code_artifact() -> GateResult: ...
    # Verify at least one COMPLETE BUILD_NEW mission has generated_code artifact

def check_equivalence_report_present() -> GateResult: ...
    # Verify a recent BUILD_NEW COMPLETE mission has equivalence_report

def check_security_compliance_report() -> GateResult: ...
    # Verify a recent COMPLETE mission has security_compliance_report

def check_token_ledger_table() -> GateResult: ...
    # Verify llm_usage_events table exists (Phase 15 migration)

def check_demo_mission_passes() -> GateResult: ...
    # Run the Phase 18 smoke demo against live stack and verify COMPLETE
```

Each check is skipped (not failed) when the live stack is unavailable,
so `make promotion-gate` still passes in CI without a running stack.

---

## Change 5 — Secret scanning enforcement in CI

Add `detect-secrets` to `.github/workflows/security.yml`:

```yaml
- name: Scan for committed secrets
  run: |
    pip install detect-secrets
    detect-secrets scan --baseline .secrets.baseline
    detect-secrets audit .secrets.baseline --only-allowlisted
```

Generate initial baseline from current clean state:
```bash
detect-secrets scan > .secrets.baseline
```

Commit `.secrets.baseline` to the repository.

---

## Change 6 — `IMPLEMENTATION_STATUS.md` refresh

Update `docs/IMPLEMENTATION_STATUS.md` with the Phase 26 evidence:

- Change "Current active phase: Phase 15" to reflect actual current state
  after all phases 15–25 complete.
- Add "Phase 26 — Production Hardening" section documenting DR drill RTO,
  git history clean status, and promotion gate result.
- Update "Release blockers" section: all four blockers resolved.

---

## Exit criteria — this phase is complete when

- [ ] `git log --all -- deploy/postgres/certs/server.key` returns no output.
- [ ] `git log --all -- deploy/redis/certs/redis.key` returns no output.
- [ ] `docs/evidence/dr_drill_phase26_*.json` exists with `test_suite_result: pass`.
- [ ] `reports/promotion-gate.local.json` shows all gates green or explicitly
      documented as skipped (no red gates).
- [ ] `reports/master_audit_2026-*.md` exists and dated within 7 days.
- [ ] `SEC-KEY-001` audit check passes in `production_review_audit.py`.
- [ ] `DR-001` audit check passes in `production_review_audit.py`.
- [ ] `make eval` passes (Phase 25 eval suite).
- [ ] `make test` passes full suite.
- [ ] `make validate` passes (lint + schema + pytest + npm lint/test).
- [ ] `docs/IMPLEMENTATION_STATUS.md` updated with Phase 26 evidence.

---

## Validation

- [ ] SEC-KEY-001 check passes.
- [ ] DR-001 check passes with evidence file present.
- [ ] Intelligence-layer promotion gate checks all return PASS or SKIP.
- [ ] `detect-secrets scan` finds no new secrets.
- [ ] `python -m pytest -q` green. `ruff check` green. `npm run lint` green.
