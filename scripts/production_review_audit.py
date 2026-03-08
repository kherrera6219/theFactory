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


def check_mission_control_e2e_controls() -> AuditResult:
    package_json = _read_text(REPO_ROOT / "apps" / "mission-control" / "package.json").lower()
    ci_text = _read_text(REPO_ROOT / ".github" / "workflows" / "ci.yml").lower()

    missing_items: list[str] = []
    if '"test:e2e"' not in package_json or "playwright test" not in package_json:
        missing_items.append("mission-control package.json missing playwright test:e2e script")
    if "mission control e2e tests" not in ci_text and "npm run test:e2e" not in ci_text:
        missing_items.append("ci workflow missing mission-control e2e test step")
    if "playwright install" not in ci_text:
        missing_items.append("ci workflow missing playwright browser install step")

    passed = not missing_items
    return _result(
        check_id="UI-011",
        priority="HIGH",
        description="Mission Control critical e2e regression tests run in CI",
        passed=passed,
        notes="; ".join(missing_items) if missing_items else "mission-control e2e controls present",
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


def check_tracing_and_pager_controls() -> AuditResult:
    app_compose = _read_text(REPO_ROOT / "deploy" / "docker-compose.yaml").lower()
    monitoring_compose = _read_text(REPO_ROOT / "deploy" / "docker-compose.monitoring.yaml").lower()
    alertmanager_config = _read_text(
        REPO_ROOT / "deploy" / "monitoring" / "alertmanager" / "alertmanager.yml"
    ).lower()

    missing_items: list[str] = []
    if "jaeger" not in app_compose:
        missing_items.append("missing jaeger service in deploy/docker-compose.yaml")
    if "otel_exporter_otlp_traces_endpoint" not in app_compose:
        missing_items.append("missing OTEL exporter endpoint wiring in app compose")
    if "--config.expand-env" not in monitoring_compose:
        missing_items.append("missing alertmanager env expansion flag")
    if "pager_webhook_url" not in monitoring_compose:
        missing_items.append("missing pager webhook env in monitoring compose")
    if "receiver: pager" not in alertmanager_config:
        missing_items.append("missing pager receiver route")
    if "severity =~ critical|high" not in alertmanager_config:
        missing_items.append("missing high/critical pager matcher")

    passed = not missing_items
    return _result(
        check_id="OBS-009",
        priority="HIGH",
        description="Distributed tracing and pager alert routing controls are configured",
        passed=passed,
        notes="; ".join(missing_items) if missing_items else "tracing and pager controls present",
    )


def check_optional_data_plane_observability_controls() -> AuditResult:
    alerts_text = _read_text(
        REPO_ROOT / "deploy" / "monitoring" / "prometheus" / "rules" / "thefactory-alerts.yml"
    ).lower()
    dashboard_text = _read_text(
        REPO_ROOT
        / "deploy"
        / "monitoring"
        / "grafana"
        / "provisioning"
        / "dashboards"
        / "json"
        / "thefactory-overview.json"
    ).lower()
    runbook_path = REPO_ROOT / "docs" / "runbooks" / "optional_data_plane_incident_runbook.md"
    runbook_text = _read_text(runbook_path).lower()

    missing_items: list[str] = []
    required_alerts = [
        "neo4jadapternotready",
        "objectstorageadapternotready",
        "neo4jmirrorwriteerrorratehigh",
        "objectstoragemirrorwriteerrorratehigh",
        "neo4jmirrorwritelatencyp95high",
        "objectstoragemirrorwritelatencyp95high",
    ]
    for alert_name in required_alerts:
        if alert_name not in alerts_text:
            missing_items.append(f"missing alert rule: {alert_name}")

    if "optional_data_plane_incident_runbook.md" not in alerts_text:
        missing_items.append("missing runbook mapping in optional data-plane alert annotations")
    if not runbook_path.exists():
        missing_items.append(f"missing runbook file: {runbook_path}")
    if "neo4jadapternotready" not in runbook_text:
        missing_items.append("runbook missing optional data-plane alert references")
    if "orchestrator_optional_adapter_mirror_writes_total" not in dashboard_text:
        missing_items.append("dashboard missing optional data-plane mirror-write metrics")

    passed = not missing_items
    return _result(
        check_id="OBS-010",
        priority="HIGH",
        description=(
            "Optional data-plane observability controls (metrics/alerts/runbook) are configured"
        ),
        passed=passed,
        notes="; ".join(missing_items)
        if missing_items
        else "optional data-plane observability controls present",
    )


def check_long_duration_reliability_controls() -> AuditResult:
    makefile_text = _read_text(REPO_ROOT / "Makefile").lower()
    runbook_text = _read_text(REPO_ROOT / "docs" / "OPERATIONS_RUNBOOK.md").lower()
    evidence_dir = REPO_ROOT / "docs" / "evidence"
    evidence_files = sorted(evidence_dir.glob("reliability_qualification_baseline_*.json"))

    required_paths = [
        REPO_ROOT / "scripts" / "reliability_qualification.py",
        REPO_ROOT / "scripts" / "reliability_qualification.ps1",
        REPO_ROOT / "docs" / "LONG_DURATION_RELIABILITY_QUALIFICATION.md",
    ]
    missing_items = [f"missing artifact: {path}" for path in required_paths if not path.exists()]
    if not evidence_files:
        missing_items.append("missing reliability evidence report in docs/evidence")
    if "reliability:" not in makefile_text:
        missing_items.append("missing make reliability target")
    if "reliability_qualification.ps1" not in runbook_text:
        missing_items.append("operations runbook missing reliability qualification command")

    passed = not missing_items
    notes = "reliability controls and evidence present"
    if evidence_files and passed:
        notes = f"reliability controls and evidence present ({evidence_files[-1].name})"
    return _result(
        check_id="PERF-010",
        priority="HIGH",
        description="Long-duration reliability qualification controls and evidence are configured",
        passed=passed,
        notes="; ".join(missing_items) if missing_items else notes,
    )


def check_compliance_evidence_mapping() -> AuditResult:
    mapping_path = REPO_ROOT / "docs" / "COMPLIANCE_EVIDENCE_MAPPING.md"
    mapping_text = _read_text(mapping_path).lower()
    missing_items: list[str] = []
    if not mapping_path.exists():
        missing_items.append(f"missing mapping document: {mapping_path}")
    if "soc2" not in mapping_text:
        missing_items.append("mapping missing soc2 references")
    if "cmmc" not in mapping_text:
        missing_items.append("mapping missing cmmc references")
    if "evidence artifact" not in mapping_text:
        missing_items.append("mapping missing evidence artifact references")

    passed = not missing_items
    return _result(
        check_id="GRC-012",
        priority="MEDIUM",
        description="Compliance evidence mapping covers SOC2/CMMC control traceability",
        passed=passed,
        notes="; ".join(missing_items) if missing_items else "compliance evidence mapping present",
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
        check_mission_control_e2e_controls(),
        check_design_tokens(),
        check_release_trust_controls(),
        check_tracing_and_pager_controls(),
        check_optional_data_plane_observability_controls(),
        check_long_duration_reliability_controls(),
        check_compliance_evidence_mapping(),
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
