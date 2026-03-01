# Deployment, Backup, and DR Playbook

Operational scripts for deployment preflight, backup/restore, and disaster-recovery drills.

## Pre-deployment

- Run checks:
  - `powershell -ExecutionPolicy Bypass -File scripts/pre_deploy_check.ps1`
- Checks include compose validation, health/readiness, schema validation, and OpenAPI export.

## Backup

- Create PostgreSQL backup:
  - `powershell -ExecutionPolicy Bypass -File scripts/backup_postgres.ps1`
- Output location:
  - `backups/ulr_YYYYMMDD_HHMMSS.sql`

## Restore

- Restore from backup:
  - `powershell -ExecutionPolicy Bypass -File scripts/restore_postgres.ps1 -BackupFile backups/ulr_YYYYMMDD_HHMMSS.sql`

## DR Drill

- Execute drill:
  - `powershell -ExecutionPolicy Bypass -File scripts/dr_drill.ps1`
- Drill validates:
  - service readiness
  - fresh backup creation
  - backup file integrity
  - database readability post-backup

## Performance Smoke

- Run perf smoke:
  - `powershell -ExecutionPolicy Bypass -File scripts/perf_smoke.ps1`
- The script fails when success-rate or p95 threshold is not met.
