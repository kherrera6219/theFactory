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

## Long-Duration Reliability Qualification

- Run sustained-load qualification:
  - `powershell -ExecutionPolicy Bypass -File scripts/reliability_qualification.ps1 -InjectOrchestratorRestart`
- The script runs time-based load, monitors readiness endpoints, injects an orchestrator restart, validates recovery, and emits a JSON evidence artifact.

## Mission Control E2E Regression

- Run Mission Control critical-path e2e suite:
  - `cd apps/mission-control && npm run test:e2e`
- Covers mission lifecycle, operations views, settings/vault workflows, and error-state handling.
