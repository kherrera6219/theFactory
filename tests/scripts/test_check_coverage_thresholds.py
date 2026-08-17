"""Line vs branch floors for the coverage gate."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_coverage_thresholds as checker  # noqa: E402


def _write_cobertura(path: Path, *, lines_valid: int, lines_covered: int, branches_valid: int, branches_covered: int, files: dict[str, float]) -> None:
    classes = []
    for filename, rate in files.items():
        classes.append(
            f'<class name="{filename}" filename="{filename}" line-rate="{rate}" branch-rate="1" complexity="0"/>'
        )
    path.write_text(
        '<?xml version="1.0" ?>\n'
        f'<coverage lines-valid="{lines_valid}" lines-covered="{lines_covered}" '
        f'branches-valid="{branches_valid}" branches-covered="{branches_covered}">'
        f'<packages><package name=".">{"".join(classes)}</package></packages></coverage>\n',
        encoding="utf-8",
    )


def test_line_and_branch_floors_are_reported_separately(tmp_path: Path, capsys, monkeypatch) -> None:
    report = tmp_path / "coverage.xml"
    _write_cobertura(
        report,
        lines_valid=100,
        lines_covered=86,
        branches_valid=100,
        branches_covered=76,
        files={"services/orchestrator/orchestrator/sandbox_exec.py": 0.91},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_coverage_thresholds.py",
            "--coverage-file",
            str(report),
            "--line-threshold",
            "80",
            "--branch-threshold",
            "70",
            "--global-threshold",
            "80",
            "--module-threshold",
            "services/orchestrator/orchestrator/sandbox_exec.py=90",
        ],
    )
    assert checker.main() == 0
    out = capsys.readouterr().out
    assert "Line coverage: 86.00%" in out
    assert "Branch coverage: 76.00%" in out


def test_branch_floor_fails_when_mixed_still_passes(tmp_path: Path, monkeypatch, capsys) -> None:
    report = tmp_path / "coverage.xml"
    # 90% line + 50% branch = 70% mixed if equal weights... use 90 line / 50 branch of 100/100
    # mixed = 140/200 = 70. Set mixed threshold 60 so only branch fails.
    _write_cobertura(
        report,
        lines_valid=100,
        lines_covered=90,
        branches_valid=100,
        branches_covered=50,
        files={},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_coverage_thresholds.py",
            "--coverage-file",
            str(report),
            "--line-threshold",
            "80",
            "--branch-threshold",
            "70",
            "--global-threshold",
            "60",
        ],
    )
    assert checker.main() == 1
    assert "branch coverage 50.00% is below threshold 70.00%" in capsys.readouterr().out
