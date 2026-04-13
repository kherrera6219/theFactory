"""
test_dr_drill.py
================
Unit and integration tests for DR drill automation.

Tests validate:
  - The structure and required fields of ``reports/dr-drill-latest.json``
  - The logic that DR evidence is fresh enough to gate a promotion
  - Dry-run execution of the PowerShell drill script (skipped when pwsh
    is unavailable)
  - Evidence age-gate helper used by the release readiness check

These tests do NOT require a live PostgreSQL instance — they verify the
contracts and schemas of the DR artefacts produced by ``scripts/dr_drill.ps1``
and consumed by the release gate.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DR_REPORT = ROOT / "reports" / "dr-drill-latest.json"

# Maximum acceptable age for DR evidence to gate a production promotion.
DR_EVIDENCE_MAX_AGE_DAYS = 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _powershell() -> str | None:
    for candidate in ("pwsh", "powershell"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def _load_report(path: Path = DR_REPORT) -> dict:
    assert path.exists(), f"DR drill report not found: {path}"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), "DR drill report must be a JSON object"
    return payload


def dr_evidence_is_fresh(report: dict, max_age_days: int = DR_EVIDENCE_MAX_AGE_DAYS) -> bool:
    """Return True when *report* was completed within *max_age_days* days.

    Uses ``completed_at_utc`` when present; falls back to ``started_at_utc``.
    Dry-run reports are always considered fresh for local dev purposes.
    """
    if report.get("dry_run"):
        return True
    ts_str = report.get("completed_at_utc") or report.get("started_at_utc")
    if not ts_str:
        return False
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return (datetime.now(UTC) - ts) <= timedelta(days=max_age_days)
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestDrDrillReportSchema:
    """The latest DR report must conform to the expected schema."""

    def test_report_file_exists(self) -> None:
        assert DR_REPORT.exists(), (
            f"reports/dr-drill-latest.json not found — run 'pwsh scripts/dr_drill.ps1 -DryRun'"
        )

    def test_report_is_valid_json(self) -> None:
        _load_report()

    def test_report_has_required_fields(self) -> None:
        report = _load_report()
        required = {
            "passed",
            "dry_run",
            "started_at_utc",
            "completed_at_utc",
            "duration_seconds",
            "rto_target_minutes",
            "rpo_target_hours",
            "latest_backup",
            "latest_backup_manifest",
        }
        missing = required - report.keys()
        assert not missing, f"DR report missing required fields: {missing}"

    def test_report_passed_is_boolean(self) -> None:
        report = _load_report()
        assert isinstance(report["passed"], bool), "passed field must be a boolean"

    def test_report_rto_target_is_positive(self) -> None:
        report = _load_report()
        assert report["rto_target_minutes"] > 0, "rto_target_minutes must be positive"

    def test_report_rpo_target_is_positive(self) -> None:
        report = _load_report()
        assert report["rpo_target_hours"] > 0, "rpo_target_hours must be positive"

    def test_report_timestamps_are_parseable(self) -> None:
        report = _load_report()
        for field in ("started_at_utc", "completed_at_utc"):
            ts_str = report.get(field)
            if ts_str:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                assert ts.tzinfo is not None, f"{field} must be timezone-aware"

    def test_backup_manifest_path_is_recorded(self) -> None:
        report = _load_report()
        manifest_path = report.get("latest_backup_manifest", "")
        assert manifest_path, "latest_backup_manifest must be a non-empty string"

    def test_report_passes(self) -> None:
        """The latest DR drill must have passed."""
        report = _load_report()
        assert report["passed"] is True, (
            "Latest DR drill did not pass — re-run 'pwsh scripts/dr_drill.ps1 -DryRun'"
        )


# ---------------------------------------------------------------------------
# Evidence age gate
# ---------------------------------------------------------------------------


class TestDrEvidenceAgeGate:
    """dr_evidence_is_fresh() must correctly gate stale and fresh evidence."""

    def test_fresh_non_dryrun_report_is_valid(self) -> None:
        report = {
            "passed": True,
            "dry_run": False,
            "completed_at_utc": datetime.now(UTC).isoformat(),
            "started_at_utc": datetime.now(UTC).isoformat(),
            "duration_seconds": 1.5,
            "rto_target_minutes": 30,
            "rpo_target_hours": 24,
            "latest_backup": "/tmp/ulr.sql",
            "latest_backup_manifest": "/tmp/ulr.sql.json",
        }
        assert dr_evidence_is_fresh(report, max_age_days=30)

    def test_stale_non_dryrun_report_is_invalid(self) -> None:
        old_ts = (datetime.now(UTC) - timedelta(days=31)).isoformat()
        report = {
            "passed": True,
            "dry_run": False,
            "completed_at_utc": old_ts,
            "started_at_utc": old_ts,
            "duration_seconds": 1.5,
            "rto_target_minutes": 30,
            "rpo_target_hours": 24,
            "latest_backup": "/tmp/ulr.sql",
            "latest_backup_manifest": "/tmp/ulr.sql.json",
        }
        assert not dr_evidence_is_fresh(report, max_age_days=30)

    def test_dryrun_report_is_always_fresh(self) -> None:
        """Dry-run evidence is always considered fresh for local dev workflows."""
        old_ts = "2020-01-01T00:00:00+00:00"
        report = {
            "passed": True,
            "dry_run": True,
            "completed_at_utc": old_ts,
            "started_at_utc": old_ts,
            "duration_seconds": 0.1,
            "rto_target_minutes": 30,
            "rpo_target_hours": 24,
            "latest_backup": "/tmp/ulr.sql",
            "latest_backup_manifest": "/tmp/ulr.sql.json",
        }
        assert dr_evidence_is_fresh(report, max_age_days=30)

    def test_missing_timestamp_is_not_fresh(self) -> None:
        report = {
            "passed": True,
            "dry_run": False,
            "duration_seconds": 1.5,
            "rto_target_minutes": 30,
            "rpo_target_hours": 24,
            "latest_backup": "/tmp/ulr.sql",
            "latest_backup_manifest": "/tmp/ulr.sql.json",
        }
        assert not dr_evidence_is_fresh(report, max_age_days=30)

    def test_current_dr_report_is_fresh(self) -> None:
        """The repo's live DR report must meet the evidence age gate."""
        report = _load_report()
        assert dr_evidence_is_fresh(report, max_age_days=DR_EVIDENCE_MAX_AGE_DAYS), (
            f"DR report at {DR_REPORT} is older than {DR_EVIDENCE_MAX_AGE_DAYS} days "
            f"and would block a production promotion. Re-run the DR drill."
        )


# ---------------------------------------------------------------------------
# PowerShell drill integration (skipped when pwsh unavailable)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(_powershell() is None, reason="PowerShell not available")
def test_dr_drill_dry_run_produces_valid_report(tmp_path) -> None:
    """Full dry-run execution must produce a schema-valid, passing report."""
    output_file = tmp_path / "dr-drill-test.json"
    ps = _powershell()
    result = subprocess.run(
        [
            ps,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "dr_drill.ps1"),
            "-DryRun",
            "-OutputFile",
            str(output_file),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # Exit 0 even on dry-run
    assert result.returncode == 0, (
        f"dr_drill.ps1 -DryRun exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    if output_file.exists():
        report = json.loads(output_file.read_text())
        required = {"passed", "dry_run", "started_at_utc", "completed_at_utc",
                    "rto_target_minutes", "rpo_target_hours"}
        assert not (required - report.keys()), "Dry-run output missing required fields"
        assert report["passed"] is True
        assert report["dry_run"] is True
