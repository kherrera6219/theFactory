from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_RELEASE_FILES = (
    "scripts/backup_postgres.ps1",
    "scripts/restore_postgres.ps1",
    "scripts/dr_drill.ps1",
    "scripts/verify_release_evidence.py",
    "scripts/promotion_gate.py",
    "scripts/qualification_gate_summary.py",
)


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _text_contains(path: Path, needle: str) -> bool:
    if not path.exists():
        return False
    try:
        return needle in path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _file_check(root: Path, relative_path: str, *, contains: str | None = None) -> dict[str, Any]:
    path = root / relative_path
    exists = path.exists()
    contains_expected = True if contains is None else _text_contains(path, contains)
    return {
        "path": relative_path,
        "exists": exists,
        "contains": contains if contains else None,
        "passed": exists and contains_expected,
    }


def _release_gate_status(qualification_summary: dict[str, Any]) -> str:
    if not qualification_summary:
        return "blocked_missing_qualification_summary"
    if bool(qualification_summary.get("passed")):
        return "ready"
    reasons = [
        str(reason).lower()
        for reason in qualification_summary.get("failure_reasons", [])
        if str(reason).strip()
    ]
    if any("age" in reason or "stale" in reason for reason in reasons):
        return "blocked_stale_qualification"
    return "blocked_qualification_failure"


def build_evidence(
    *,
    root: Path,
    dr_report_file: Path,
    qualification_summary_file: Path,
) -> dict[str, Any]:
    root = root.resolve()
    dr_report_path = _resolve(root, dr_report_file)
    qualification_summary_path = _resolve(root, qualification_summary_file)

    dr_report = _load_json(dr_report_path)
    qualification_summary = _load_json(qualification_summary_path)
    file_checks = [
        _file_check(root, relative_path)
        for relative_path in REQUIRED_RELEASE_FILES
    ]
    file_checks.extend(
        [
            _file_check(root, ".gitleaks.toml", contains="gitleaks"),
            _file_check(root, ".pre-commit-config.yaml", contains="gitleaks"),
        ]
    )

    dr_passed = bool(dr_report.get("passed"))
    rto_target_minutes = dr_report.get("rto_target_minutes")
    duration_seconds = dr_report.get("duration_seconds")
    rto_met = (
        isinstance(duration_seconds, int | float)
        and isinstance(rto_target_minutes, int | float)
        and duration_seconds <= float(rto_target_minutes) * 60
    )
    local_evidence_passed = dr_passed and rto_met and all(check["passed"] for check in file_checks)
    release_gate_status = _release_gate_status(qualification_summary)
    dirty_paths = [
        line for line in _git(root, "status", "--porcelain").splitlines() if line.strip()
    ]

    return {
        "schema_version": "phase17_release_hardening_evidence.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "phase": 17,
        "branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "commit": _git(root, "rev-parse", "HEAD"),
        "working_tree_dirty_paths": dirty_paths,
        "dr_drill": {
            "report_file": str(dr_report_path.relative_to(root))
            if dr_report_path.is_relative_to(root)
            else str(dr_report_path),
            "passed": dr_passed,
            "dry_run": bool(dr_report.get("dry_run")),
            "duration_seconds": duration_seconds,
            "rto_target_minutes": rto_target_minutes,
            "rpo_target_hours": dr_report.get("rpo_target_hours"),
            "rto_met": rto_met,
            "latest_backup_manifest": dr_report.get("latest_backup_manifest"),
        },
        "release_hardening": {
            "file_checks": file_checks,
            "secret_history_controls_present": all(
                check["passed"]
                for check in file_checks
                if check["path"] in {".gitleaks.toml", ".pre-commit-config.yaml"}
            ),
        },
        "qualification_summary": {
            "summary_file": str(qualification_summary_path.relative_to(root))
            if qualification_summary_path.is_relative_to(root)
            else str(qualification_summary_path),
            "passed": bool(qualification_summary.get("passed")),
            "generated_at": qualification_summary.get("generated_at"),
            "failure_reasons": qualification_summary.get("failure_reasons", []),
        },
        "local_evidence_passed": local_evidence_passed,
        "release_gate_passed": release_gate_status == "ready",
        "release_gate_status": release_gate_status,
        "passed": local_evidence_passed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 17 DR and release-hardening evidence."
    )
    parser.add_argument(
        "--dr-report-file",
        default="reports/dr-drill-latest.json",
        help="Path to the latest DR drill JSON report.",
    )
    parser.add_argument(
        "--qualification-summary-file",
        default="reports/qualification-gate-summary.phase17.json",
        help="Path to a freshly generated qualification gate summary.",
    )
    parser.add_argument(
        "--output-file",
        default="docs/evidence/phase17_dr_release_hardening_latest.json",
        help="Path where the Phase 17 evidence JSON should be written.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_file = _resolve(ROOT, Path(args.output_file))
    evidence = build_evidence(
        root=ROOT,
        dr_report_file=Path(args.dr_report_file),
        qualification_summary_file=Path(args.qualification_summary_file),
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote Phase 17 evidence to {output_file}")
    print(f"Local evidence passed: {evidence['local_evidence_passed']}")
    print(f"Release gate status: {evidence['release_gate_status']}")
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
