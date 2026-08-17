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


def test_line_floor_fails_when_mixed_still_passes(tmp_path: Path, monkeypatch, capsys) -> None:
    report = tmp_path / "coverage.xml"
    # 79% line + 90% branch = 84.5% mixed. Mixed and branch pass; line must fail.
    _write_cobertura(
        report,
        lines_valid=100,
        lines_covered=79,
        branches_valid=100,
        branches_covered=90,
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
            "80",
        ],
    )
    assert checker.main() == 1
    assert "line coverage 79.00% is below threshold 80.00%" in capsys.readouterr().out


def test_checker_defaults_fail_line_below_80(tmp_path: Path, monkeypatch, capsys) -> None:
    report = tmp_path / "coverage.xml"
    _write_cobertura(
        report,
        lines_valid=100,
        lines_covered=79,
        branches_valid=100,
        branches_covered=90,
        files={},
    )
    monkeypatch.setattr(sys, "argv", ["check_coverage_thresholds.py", "--coverage-file", str(report)])
    assert checker.main() == 1
    assert "line coverage 79.00% is below threshold 80.00%" in capsys.readouterr().out


def test_module_floor_fails_when_global_still_passes(tmp_path: Path, monkeypatch, capsys) -> None:
    report = tmp_path / "coverage.xml"
    _write_cobertura(
        report,
        lines_valid=100,
        lines_covered=90,
        branches_valid=100,
        branches_covered=80,
        files={"services/orchestrator/orchestrator/port_coordinator.py": 0.14},
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
            "services/orchestrator/orchestrator/port_coordinator.py=80",
        ],
    )
    assert checker.main() == 1
    assert "below threshold 80.00% for services/orchestrator/orchestrator/port_coordinator.py" in capsys.readouterr().out


def test_missing_required_module_fails(tmp_path: Path, monkeypatch, capsys) -> None:
    report = tmp_path / "coverage.xml"
    _write_cobertura(
        report,
        lines_valid=100,
        lines_covered=90,
        branches_valid=100,
        branches_covered=80,
        files={},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_coverage_thresholds.py",
            "--coverage-file",
            str(report),
            "--module-threshold",
            "services/orchestrator/orchestrator/sandbox_exec.py=90",
        ],
    )
    assert checker.main() == 1
    assert "module not found in coverage report: services/orchestrator/orchestrator/sandbox_exec.py" in capsys.readouterr().out


def test_invalid_module_threshold_raises() -> None:
    try:
        checker._parse_module_thresholds(["nopath"])
    except ValueError as exc:
        assert "expected path=threshold" in str(exc)
    else:
        raise AssertionError("expected ValueError for invalid --module-threshold")


def test_makefile_and_ci_keep_line_threshold_80() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for text in (makefile, ci):
        assert "--line-threshold 80" in text
        assert "--branch-threshold 70" in text
        assert "--global-threshold 80" in text
        assert "--cov-fail-under=80" in text
        assert "port_coordinator.py=80" in text
        assert "sandbox_exec.py=90" in text
        assert "sandbox_runner.py=90" in text
        assert "sow_store.py=90" in text
        assert "sow_estimator.py=80" in text
        assert "file_tree.py=80" in text
        assert "rqca_agent.py=80" in text
        assert "rqca_agent.py=70" not in text


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
