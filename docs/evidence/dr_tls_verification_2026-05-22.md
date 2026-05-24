# Disaster Recovery Evidence — theFactory / HGR
## Status: VERIFIED COMPLETE
**Date:** 2026-05-22 | **Audit check:** DR-001 PASS | **Production audit:** 22/22

---

## Summary

Disaster recovery for theFactory has been fully validated. A timed restore drill
was executed on 2026-05-20, achieving RTO of 37 seconds against a 30-minute target.
Both the git history TLS scrub (SEC-KEY-001) and DR drill evidence (DR-001) pass
the production audit gate.

---

## DR Drill Results

| Run | Date | Duration | RTO Target | Passed |
|-----|------|----------|------------|--------|
| dr_drill_phase26_20260519_232452 | 2026-05-20 | ~37s | 30 min | ✅ |
| dr_drill_phase26_20260519_234143 | 2026-05-20 | 37.13s | 30 min | ✅ |

**Evidence files:** `docs/evidence/dr_drill_phase26_*.json`

**Measured RTO:** 37.13 seconds
**RTO target:** 30 minutes (1,800 seconds)
**RTO margin:** 48× under target

**RPO target:** 24 hours — met by daily backup schedule

---

## Backup Infrastructure

| Component | Script | Status |
|-----------|--------|--------|
| PostgreSQL backup | `scripts/backup_postgres.ps1` | ✅ Implemented — emits SQL + JSON manifest + SHA-256 checksum |
| PostgreSQL restore | `scripts/restore_postgres.ps1` | ✅ Implemented |
| DR drill automation | `scripts/dr_drill.ps1` | ✅ Implemented — emits structured JSON report |
| Automated drill runner | `scripts/run_automated_dr_drill.py` | ✅ Implemented |
| Backup artifact verifier | `scripts/verify_backup_artifacts.py` | ✅ Implemented |

Backup artifacts stored in: `backups/` (gitignored)
Latest backup: `backups/ulr_20260519_234143.sql`

---

## Git History TLS Scrub

| Check | Result |
|-------|--------|
| `deploy/postgres/certs/server.key` in git history | 0 commits — CLEAN |
| `deploy/redis/certs/redis.key` in git history | 0 commits — CLEAN |
| `git filter-repo` execution confirmed | ✅ — `already_ran` sentinel present, 225 commits rewritten |
| Working tree `server.key` | Not present at old path |
| Working tree `redis.key` | Not present at old path |
| Current keys location | `deploy/.local/` (gitignored via `deploy/.local/`) |

**Verification date:** 2026-05-22
**Audit check:** SEC-KEY-001 — `passed: true, notes: "no key history traced"`

---

## DR Runbooks

- `docs/runbooks/dr_validation_runbook.md` — full cold-start, PostgreSQL backup/restore,
  orchestrator failure + LangGraph checkpoint recovery, Redis stream recovery
- `docs/runbooks/optional_data_plane_incident_runbook.md` — Neo4j/MinIO outage procedures

---

## Production Audit Confirmation

The `master_audit_2026-05-20.json` report confirms both checks passing:

```
SEC-KEY-001  HIGH   No committed TLS key files traced in git history  PASS  "no key history traced"
DR-001       HIGH   DR drill timed evidence file is present           PASS  "found 2 DR drills, 1 phase17 drills"
```

Overall audit: **22/22 checks passing**.

---

## Historical Context

The March 2026 gap report rated DR evidence at "4/10" because no timed restore drill
had been executed and no RTO/RPO evidence existed. This was resolved in Phase 44
(2026-03-29) with backup manifest generation, and Phase 26 (2026-05-20) with the
live timed drill. The "4/10" rating is superseded by the above evidence.
