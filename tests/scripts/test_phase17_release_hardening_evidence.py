"""Regression tests for Phase 17 DR/release-hardening evidence."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "phase17_release_hardening_evidence.py"

spec = importlib.util.spec_from_file_location("phase17_release_hardening_evidence", MODULE_PATH)
assert spec is not None and spec.loader is not None
phase17 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = phase17
spec.loader.exec_module(phase17)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_required_files(root: Path) -> None:
    for relative_path in phase17.REQUIRED_RELEASE_FILES:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder\n", encoding="utf-8")
    (root / ".gitleaks.toml").write_text("title = 'gitleaks config'\n", encoding="utf-8")
    (root / ".pre-commit-config.yaml").write_text("repos:\n- repo: gitleaks\n", encoding="utf-8")


def test_phase17_evidence_passes_local_checks_but_blocks_stale_release_gate(
    tmp_path: Path,
) -> None:
    _write_required_files(tmp_path)
    dr_report = tmp_path / "reports" / "dr.json"
    summary = tmp_path / "reports" / "qualification.json"
    _write_json(
        dr_report,
        {
            "passed": True,
            "dry_run": True,
            "duration_seconds": 2.5,
            "rto_target_minutes": 30,
            "rpo_target_hours": 24,
            "latest_backup_manifest": "backups/ulr_test.sql.json",
        },
    )
    _write_json(
        summary,
        {
            "passed": False,
            "generated_at": "2026-05-19T00:00:00+00:00",
            "failure_reasons": ["operator_route_oidc_matrix: latest evidence age 76d exceeds 8d"],
        },
    )

    evidence = phase17.build_evidence(
        root=tmp_path,
        dr_report_file=dr_report,
        qualification_summary_file=summary,
    )

    assert evidence["passed"] is True
    assert evidence["local_evidence_passed"] is True
    assert evidence["release_gate_passed"] is False
    assert evidence["release_gate_status"] == "blocked_stale_qualification"
    assert evidence["release_hardening"]["secret_history_controls_present"] is True


def test_phase17_evidence_fails_when_dr_rto_is_missed(tmp_path: Path) -> None:
    _write_required_files(tmp_path)
    dr_report = tmp_path / "reports" / "dr.json"
    summary = tmp_path / "reports" / "qualification.json"
    _write_json(
        dr_report,
        {
            "passed": True,
            "dry_run": True,
            "duration_seconds": 1900,
            "rto_target_minutes": 30,
            "rpo_target_hours": 24,
        },
    )
    _write_json(summary, {"passed": True, "failure_reasons": []})

    evidence = phase17.build_evidence(
        root=tmp_path,
        dr_report_file=dr_report,
        qualification_summary_file=summary,
    )

    assert evidence["passed"] is False
    assert evidence["dr_drill"]["rto_met"] is False
    assert evidence["release_gate_status"] == "ready"


def test_phase17_evidence_reports_missing_qualification_summary(tmp_path: Path) -> None:
    _write_required_files(tmp_path)
    dr_report = tmp_path / "reports" / "dr.json"
    _write_json(
        dr_report,
        {
            "passed": True,
            "dry_run": True,
            "duration_seconds": 2,
            "rto_target_minutes": 30,
            "rpo_target_hours": 24,
        },
    )

    evidence = phase17.build_evidence(
        root=tmp_path,
        dr_report_file=dr_report,
        qualification_summary_file=tmp_path / "reports" / "missing.json",
    )

    assert evidence["passed"] is True
    assert evidence["release_gate_status"] == "blocked_missing_qualification_summary"
