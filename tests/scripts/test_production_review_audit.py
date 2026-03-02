import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "production_review_audit.py"

spec = importlib.util.spec_from_file_location("production_review_audit", MODULE_PATH)
assert spec is not None and spec.loader is not None
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_check_coverage_gate_passes_with_required_thresholds(tmp_path, monkeypatch) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "pytest --cov=services --cov-fail-under=80",
    )
    _write(tmp_path / "pyproject.toml", "[tool.coverage.report]\nfail_under = 80\n")
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)

    result = audit.check_coverage_gate()
    assert result.passed is True
    assert result.check_id == "TST-001"


def test_check_coverage_gate_fails_when_threshold_missing(tmp_path, monkeypatch) -> None:
    _write(tmp_path / ".github" / "workflows" / "ci.yml", "pytest --cov=services")
    _write(tmp_path / "pyproject.toml", "[tool.coverage.report]\nfail_under = 70\n")
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)

    result = audit.check_coverage_gate()
    assert result.passed is False
    assert "ci=" in result.notes


def test_check_security_workflow_detects_missing_scanners(tmp_path, monkeypatch) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "security.yml",
        "name: security\nsteps:\n  - run: pip-audit\n  - run: bandit\n",
    )
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)

    result = audit.check_security_workflow()
    assert result.passed is False
    assert "trivy-action" in result.notes
    assert "gitleaks" in result.notes


def test_check_non_root_containers_passes_for_non_root_users(tmp_path, monkeypatch) -> None:
    dockerfiles = [
        tmp_path / "services" / "api-gateway" / "Dockerfile",
        tmp_path / "services" / "orchestrator" / "Dockerfile",
        tmp_path / "services" / "dashboard" / "Dockerfile",
        tmp_path / "services" / "pod-worker" / "Dockerfile",
        tmp_path / "services" / "audit-worker" / "Dockerfile",
        tmp_path / "apps" / "mission-control" / "Dockerfile",
    ]
    for dockerfile in dockerfiles:
        _write(dockerfile, "FROM python:3.12-slim\nUSER appuser\n")

    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    result = audit.check_non_root_containers()
    assert result.passed is True


def test_check_non_root_containers_fails_for_root(tmp_path, monkeypatch) -> None:
    dockerfiles = [
        tmp_path / "services" / "api-gateway" / "Dockerfile",
        tmp_path / "services" / "orchestrator" / "Dockerfile",
        tmp_path / "services" / "dashboard" / "Dockerfile",
        tmp_path / "services" / "pod-worker" / "Dockerfile",
        tmp_path / "services" / "audit-worker" / "Dockerfile",
        tmp_path / "apps" / "mission-control" / "Dockerfile",
    ]
    for dockerfile in dockerfiles:
        _write(dockerfile, "FROM python:3.12-slim\nUSER appuser\n")
    _write(tmp_path / "services" / "dashboard" / "Dockerfile", "FROM python:3.12-slim\nUSER root\n")

    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    result = audit.check_non_root_containers()
    assert result.passed is False
    assert "USER root" in result.notes


def test_run_audit_returns_expected_checks() -> None:
    results = audit.run_audit()
    check_ids = [result.check_id for result in results]
    assert check_ids == [
        "TST-001",
        "SEC-001",
        "SEC-005",
        "INF-007",
        "COM-003",
        "DOC-005",
        "API-002",
        "STY-001",
    ]
