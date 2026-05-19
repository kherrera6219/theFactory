# Phase 17 - DR Evidence and Release Hardening

## Status

**Local evidence implemented. Live release promotion remains blocked until fresh
qualification evidence is generated.**

Phase 17 now has a repeatable local evidence path for the disaster-recovery drill,
backup artifact validation, release-trust script inventory, and secret-history
control checks. The release gate still fails closed when qualification evidence is
stale or missing; do not use this phase as a launch-ready claim until the live
qualification suites are rerun within policy freshness.

## Completed Scope

- Added a Phase 17 evidence builder: `scripts/phase17_release_hardening_evidence.py`.
- Validated dry-run DR drill output against RTO/RPO metadata.
- Verified release-hardening script coverage for backup, restore, DR drill,
  release evidence verification, promotion gate, and qualification summary.
- Verified repo-level secret-history controls are present through `.gitleaks.toml`
  and `.pre-commit-config.yaml`.
- Captured Phase 17 evidence in `docs/evidence/`.
- Added focused regression coverage in
  `tests/scripts/test_phase17_release_hardening_evidence.py`.

## Evidence Commands

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dr_drill.ps1 -DryRun -Timestamp phase17_20260519
python scripts/qualification_gate_summary.py --output-file docs/evidence/qualification_gate_summary_phase17_2026-05-19.json
python scripts/phase17_release_hardening_evidence.py --dr-report-file reports/dr-drill-latest.json --qualification-summary-file docs/evidence/qualification_gate_summary_phase17_2026-05-19.json --output-file docs/evidence/phase17_dr_release_hardening_2026-05-19.json
```

The qualification summary command is expected to return non-zero when evidence is
older than the promotion policy allows. That is the correct fail-closed behavior.

## Exit Criteria

- **Local Phase 17 evidence:** complete when the DR drill dry-run passes, RTO is
  met, release-hardening files are present, and secret-history controls are
  configured.
- **Launch release gate:** incomplete until the live qualification suites are
  rerun and `scripts/promotion_gate.py` returns an approved decision with fresh
  evidence.
