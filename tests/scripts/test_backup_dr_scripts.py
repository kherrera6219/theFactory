import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _powershell_executable() -> str:
    for candidate in ("pwsh", "powershell"):
        found = shutil.which(candidate)
        if found:
            return found
    pytest.skip("PowerShell executable not available in test environment.")


def _run_powershell(script_path: str, *args: str) -> subprocess.CompletedProcess[str]:
    executable = _powershell_executable()
    command = [
        executable,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        script_path,
        *args,
    ]
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)


def test_backup_script_dry_run_creates_sql_artifact() -> None:
    timestamp = f"20990101_{uuid.uuid4().hex[:8]}"
    backup_path = ROOT / "backups" / f"ulr_{timestamp}.sql"
    if backup_path.exists():
        backup_path.unlink()

    result = _run_powershell("scripts/backup_postgres.ps1", "-DryRun", "-Timestamp", timestamp)

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert backup_path.exists()
    content = backup_path.read_text(encoding="utf-8")
    assert "dry-run backup artifact" in content
    assert "INSERT INTO missions" in content

    backup_path.unlink(missing_ok=True)


def test_dr_drill_dry_run_executes_without_runtime_dependencies() -> None:
    timestamp = f"20990101_{uuid.uuid4().hex[:8]}"
    backup_path = ROOT / "backups" / f"ulr_{timestamp}.sql"
    if backup_path.exists():
        backup_path.unlink()

    result = _run_powershell("scripts/dr_drill.ps1", "-DryRun", "-Timestamp", timestamp)
    combined_output = f"{result.stdout}\n{result.stderr}"

    assert result.returncode == 0, combined_output
    assert "Dry-run mode enabled. Skipping readiness HTTP checks." in combined_output
    assert "Dry-run mode enabled. Skipping postgres mission-count query." in combined_output
    assert "DR drill complete." in combined_output
    assert backup_path.exists()

    backup_path.unlink(missing_ok=True)
