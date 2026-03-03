from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class AuditResult:
    check_id: str
    priority: str
    description: str
    passed: bool
    notes: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _result(
    check_id: str,
    priority: str,
    description: str,
    passed: bool,
    notes: str,
) -> AuditResult:
    return AuditResult(
        check_id=check_id,
        priority=priority,
        description=description,
        passed=passed,
        notes=notes,
    )


def check_coverage_gate() -> AuditResult:
    ci_text = _read_text(REPO_ROOT / ".github" / "workflows" / "ci.yml")
    pyproject_text = _read_text(REPO_ROOT / "pyproject.toml")

    ci_match = re.search(r"--cov-fail-under=(\d+)", ci_text)
    pyproject_match = re.search(r"fail_under\s*=\s*(\d+)", pyproject_text)
    ci_gate = int(ci_match.group(1)) if ci_match else -1
    pyproject_gate = int(pyproject_match.group(1)) if pyproject_match else -1
    passed = ci_gate >= 80 and pyproject_gate >= 80

    return _result(
        check_id="TST-001",
        priority="HIGH",
        description="Coverage gate enforced at >=80% in CI and project config",
        passed=passed,
        notes=f"ci={ci_gate}, pyproject={pyproject_gate}",
    )


def check_security_workflow() -> AuditResult:
    security_text = _read_text(REPO_ROOT / ".github" / "workflows" / "security.yml").lower()
    required = ["pip-audit", "bandit", "trivy-action", "gitleaks"]
    missing = [token for token in required if token not in security_text]
    passed = not missing

    return _result(
        check_id="SEC-001",
        priority="CRITICAL",
        description="Security workflow includes dependency/SAST/container/secret scanning",
        passed=passed,
        notes="missing=" + ", ".join(missing) if missing else "all required scanners configured",
    )


def check_non_root_containers() -> AuditResult:
    dockerfiles = [
        REPO_ROOT / "services" / "api-gateway" / "Dockerfile",
        REPO_ROOT / "services" / "orchestrator" / "Dockerfile",
        REPO_ROOT / "services" / "dashboard" / "Dockerfile",
        REPO_ROOT / "services" / "pod-worker" / "Dockerfile",
        REPO_ROOT / "services" / "audit-worker" / "Dockerfile",
        REPO_ROOT / "apps" / "mission-control" / "Dockerfile",
    ]

    failing: list[str] = []
    for dockerfile in dockerfiles:
        text = _read_text(dockerfile)
        users = re.findall(r"^\s*USER\s+([^\s#]+)", text, flags=re.MULTILINE | re.IGNORECASE)
        if not users:
            failing.append(f"{dockerfile}: missing USER")
            continue
        effective_user = users[-1].strip("'\"").lower()
        if effective_user in {"root", "0", "0:0", "root:root"}:
            failing.append(f"{dockerfile}: USER {effective_user}")

    passed = not failing
    return _result(
        check_id="SEC-005",
        priority="HIGH",
        description="Service containers run as non-root users",
        passed=passed,
        notes="; ".join(failing) if failing else "all Dockerfiles set non-root USER",
    )


def check_environment_template() -> AuditResult:
    env_text = _read_text(REPO_ROOT / ".env.example")
    required = [
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "DB_NAME_KNOWLEDGE_LAKE",
        "DB_NAME_STATE_GRAPH",
        "DB_NAME_LOGICNODE_REGISTRY",
        "DB_NAME_TRACEABILITY_LEDGER",
        "DB_NAME_MODEL_STORE",
        "ANTHROPIC_API_KEY_ARCH",
        "ANTHROPIC_API_KEY_PY",
        "ANTHROPIC_API_KEY_JS",
        "ANTHROPIC_API_KEY_TS",
    ]
    missing = [name for name in required if f"{name}=" not in env_text]
    passed = not missing
    return _result(
        check_id="INF-007",
        priority="CRITICAL",
        description="Environment template includes required DB and key variables",
        passed=passed,
        notes="missing=" + ", ".join(missing) if missing else "required variables present",
    )


def check_protocol_contract_artifacts() -> AuditResult:
    required_paths = [
        REPO_ROOT / "protocol" / "topics.yaml",
        REPO_ROOT / "schemas" / "event.envelope.schema.json",
        REPO_ROOT / "schemas" / "logicnode.schema.json",
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    passed = not missing
    return _result(
        check_id="COM-003",
        priority="CRITICAL",
        description="Protocol catalog and core schemas exist in-repo",
        passed=passed,
        notes="missing=" + ", ".join(missing) if missing else "core protocol artifacts present",
    )


def check_operational_docs() -> AuditResult:
    required_docs = [
        REPO_ROOT / "docs" / "OPERATIONS_RUNBOOK.md",
        REPO_ROOT / "docs" / "DEPLOYMENT_DR_PLAYBOOK.md",
        REPO_ROOT / "docs" / "OBSERVABILITY_STACK.md",
        REPO_ROOT / "docs" / "GAP_ANALYSIS.md",
    ]
    missing = [str(path) for path in required_docs if not path.exists()]
    passed = not missing
    return _result(
        check_id="DOC-005",
        priority="HIGH",
        description="Operational runbooks and gap-analysis docs exist",
        passed=passed,
        notes="missing=" + ", ".join(missing) if missing else "required operations docs present",
    )


def check_mission_control_typescript_strict() -> AuditResult:
    tsconfig = _read_text(REPO_ROOT / "apps" / "mission-control" / "tsconfig.json")
    page_tsx = REPO_ROOT / "apps" / "mission-control" / "app" / "page.tsx"
    shell_page_tsx = REPO_ROOT / "apps" / "mission-control" / "app" / "(shell)" / "page.tsx"
    layout_tsx = REPO_ROOT / "apps" / "mission-control" / "app" / "layout.tsx"
    passed = (
        '"strict": true' in tsconfig
        and (page_tsx.exists() or shell_page_tsx.exists())
        and layout_tsx.exists()
        and not (REPO_ROOT / "apps" / "mission-control" / "app" / "page.jsx").exists()
    )
    if passed:
        notes = "strict tsconfig + tsx app files present"
    else:
        notes = "mission-control TS strict setup incomplete"
    return _result(
        check_id="API-002",
        priority="HIGH",
        description="Mission Control uses strict TypeScript configuration",
        passed=passed,
        notes=notes,
    )


def check_design_tokens() -> AuditResult:
    tokens_json = REPO_ROOT / "assets" / "design-tokens" / "tokens.json"
    tokens_css = REPO_ROOT / "assets" / "design-tokens" / "tokens.css"
    passed = tokens_json.exists() and tokens_css.exists()
    return _result(
        check_id="STY-001",
        priority="MEDIUM",
        description="Design token source files exist for style-guide alignment",
        passed=passed,
        notes="tokens.json and tokens.css present" if passed else "missing design tokens artifacts",
    )


def check_release_trust_controls() -> AuditResult:
    ci_text = _read_text(REPO_ROOT / ".github" / "workflows" / "ci.yml").lower()
    policy_path = REPO_ROOT / "deploy" / "promotion-policy.json"
    required_tokens = [
        "attest-build-provenance",
        "gh attestation verify",
        "promotion_gate.py",
        "promotion-policy.json",
    ]
    missing_tokens = [token for token in required_tokens if token not in ci_text]
    missing_items: list[str] = []
    if missing_tokens:
        missing_items.append("workflow tokens missing: " + ", ".join(missing_tokens))
    if not policy_path.exists():
        missing_items.append(f"missing policy file: {policy_path}")
    passed = not missing_items
    return _result(
        check_id="REL-001",
        priority="CRITICAL",
        description="Release attestation and promotion-gate controls are configured",
        passed=passed,
        notes="; ".join(missing_items) if missing_items else "release trust controls present",
    )


def run_audit() -> list[AuditResult]:
    return [
        check_coverage_gate(),
        check_security_workflow(),
        check_non_root_containers(),
        check_environment_template(),
        check_protocol_contract_artifacts(),
        check_operational_docs(),
        check_mission_control_typescript_strict(),
        check_design_tokens(),
        check_release_trust_controls(),
    ]


def print_results(results: list[AuditResult]) -> None:
    width = max(len(result.check_id) for result in results)
    print("== Production Review Audit ==")
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"{result.check_id:<{width}}  {status:<4}  [{result.priority}] {result.description}")
        print(f"  notes: {result.notes}")
    passed = sum(1 for result in results if result.passed)
    print(f"\nSummary: {passed}/{len(results)} checks passed")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Checklist-aligned production audit for theFactory"
    )
    parser.add_argument("--json", action="store_true", help="Output audit results as JSON")
    args = parser.parse_args()

    results = run_audit()
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        print_results(results)

    critical_failures = [
        result for result in results if result.priority == "CRITICAL" and not result.passed
    ]
    return 1 if critical_failures else 0


if __name__ == "__main__":
    sys.exit(main())
