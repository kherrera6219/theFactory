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
        tmp_path / "services" / "agent-runtime" / "Dockerfile",
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
        tmp_path / "services" / "agent-runtime" / "Dockerfile",
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
        "INF-008",
        "COM-003",
        "DOC-005",
        "API-002",
        "UI-011",
        "STY-001",
        "REL-001",
        "REL-002",
        "OBS-009",
        "OBS-010",
        "OBS-011",
        "PERF-010",
        "GRC-012",
        "SEC-KEY-001",
        "DR-001",
        "AI-001",
        "AI-002",
        "PHASE-001",
    ]


def test_check_release_trust_controls_passes_with_required_artifacts(tmp_path, monkeypatch) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        """
name: CI
on:
  push:
    tags:
      - "v*"
jobs:
  release-trust:
    steps:
      - uses: actions/attest-build-provenance@v2
      - run: gh attestation verify reports/release-manifest.json --repo org/repo
      - run: git tag -v v1.2.3
      - run: cosign sign-blob --yes reports/release-manifest.json
      - run: cosign verify-blob reports/release-manifest.json
      - run: |
          python scripts/promotion_gate.py \
            --policy-file deploy/promotion-policy.json \
            --signed-tag-verified true \
            --output-file reports/promotion.json
""".strip(),
    )
    _write(
        tmp_path / "deploy" / "promotion-policy.json",
        '{"version":1,"fail_closed":true,"allowed_ref_patterns":["^refs/heads/main$"],"requirements":{"ci_status":"success","attestation_verified":true,"signed_tag_verified":true}}',
    )
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)

    result = audit.check_release_trust_controls()
    assert result.passed is True


def test_check_release_trust_controls_fails_when_missing(tmp_path, monkeypatch) -> None:
    _write(tmp_path / ".github" / "workflows" / "ci.yml", "name: CI")
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    result = audit.check_release_trust_controls()
    assert result.passed is False
    assert "missing policy file" in result.notes


def test_check_compose_environment_profile_controls_passes(tmp_path, monkeypatch) -> None:
    _write(
        tmp_path / "deploy" / "docker-compose.yaml",
        (
            "services:\n"
            "  api:\n"
            "    cap_drop: [ALL]\n"
            "    oom_score_adj: -500\n"
            "    volumes:\n"
            "      - ./redis/entrypoint.sh:/usr/local/bin/docker-entrypoint-init-tls.sh:ro\n"
            "      - ./.local/postgres-certs:/run/postgres-certs:ro\n"
            "    environment:\n"
            "      INTERNAL_SERVICE_API_KEY: ${INTERNAL_SERVICE_API_KEY:-}\n"
            "      REDIS_URL: rediss://redis:6380/0?ssl_cert_reqs=required&ssl_ca_certs=/run/redis-certs/ca.crt\n"
            "      POSTGRES_URL: postgresql://postgres:postgres@postgres:5432/ulr?sslmode=verify-full&sslrootcert=/run/postgres-certs/ca.crt\n"
        ),
    )
    _write(tmp_path / "deploy" / "docker-compose.dev.yaml", "services: {}\n")
    _write(tmp_path / "deploy" / "docker-compose.staging.yaml", "services: {}\n")
    _write(
        tmp_path / "deploy" / "docker-compose.full-dedicated-agents.yaml",
        (
            "x-redis-client-certs:\n"
            "  - ./.local/redis-certs:/run/redis-certs:ro\n"
            "services:\n"
            "  agent-36-go:\n"
            "    image: local\n"
            "  agent-37-haskell:\n"
            "    image: local\n"
            "  agent-38-ocaml:\n"
            "    image: local\n"
        ),
    )
    _write(
        tmp_path / "deploy" / "docker-compose.prod.yaml",
        "services:\n  api:\n    environment:\n      AGENT_SERVICE_KEY_MODE: strict\n",
    )
    _write(tmp_path / "docs" / "COMPOSE_ENVIRONMENT_PROFILES.md", "# Profiles\n")
    _write(
        tmp_path / "Makefile",
        (
            "up-full-dedicated:\n"
            "\tdocker compose up minio milvus neo4j "
            "agent-36-go agent-37-haskell agent-38-ocaml\n"
        ),
    )
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)

    result = audit.check_compose_environment_profile_controls()
    assert result.passed is True


def test_check_model_governance_and_qualification_controls_passes(
    tmp_path, monkeypatch
) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        (
            "python scripts/export_agent_model_inventory.py\n"
            "python scripts/qualification_gate_summary.py\n"
        ),
    )
    _write(
        tmp_path / ".github" / "workflows" / "qualification.yml",
        "on:\n  schedule:\n    - cron: '0 8 * * 1'\n",
    )
    _write(
        tmp_path / "deploy" / "promotion-policy.json",
        '{"version":2,"fail_closed":true,"allowed_ref_patterns":["^refs/heads/main$"],"requirements":{"ci_status":"success","attestation_verified":true,"model_governance":{},"qualification_gates":{}}}',
    )
    _write(tmp_path / "scripts" / "export_agent_model_inventory.py", "print('ok')\n")
    _write(tmp_path / "scripts" / "qualification_gate_summary.py", "print('ok')\n")
    _write(tmp_path / "docs" / "MODEL_PROMOTION_GOVERNANCE.md", "# Governance\n")
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)

    result = audit.check_model_governance_and_qualification_controls()
    assert result.passed is True


def test_check_environment_template_requires_agent_keys_and_redis_tls(
    tmp_path, monkeypatch
) -> None:
    _write(
        tmp_path / ".env.example",
        "\n".join(
            [
                "REDIS_URL=rediss://redis:6380/0?ssl_cert_reqs=required&ssl_ca_certs=deploy/redis/certs/ca.crt",
                "POSTGRES_URL=postgresql://postgres:postgres@postgres:5432/ulr?sslmode=verify-full&sslrootcert=deploy/postgres/certs/ca.crt",
                "POSTGRES_USER=postgres",
                "POSTGRES_PASSWORD=postgres",
                "POSTGRES_DB=ulr",
                "DB_NAME_KNOWLEDGE_LAKE=knowledge_lake",
                "DB_NAME_STATE_GRAPH=state_graph",
                "DB_NAME_LOGICNODE_REGISTRY=logicnode_registry",
                "DB_NAME_TRACEABILITY_LEDGER=traceability_ledger",
                "DB_NAME_MODEL_STORE=model_store",
                "ANTHROPIC_API_KEY_ARCH=",
                "ANTHROPIC_API_KEY_PY=",
                "ANTHROPIC_API_KEY_JS=",
                "ANTHROPIC_API_KEY_TS=",
                "AGENT_01_PM_SERVICE_API_KEY=",
                "AGENT_10_TESTER_SERVICE_API_KEY=",
                "AGENT_14_PYTHON_SERVICE_API_KEY=",
                "AGENT_35_MATHEMATICA_SERVICE_API_KEY=",
                "AGENT_36_GO_SERVICE_API_KEY=",
                "AGENT_37_HASKELL_SERVICE_API_KEY=",
                "AGENT_38_OCAML_SERVICE_API_KEY=",
            ]
        ),
    )
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)

    result = audit.check_environment_template()
    assert result.passed is True


def test_check_mission_control_typescript_strict_accepts_shell_page(tmp_path, monkeypatch) -> None:
    _write(tmp_path / "apps" / "mission-control" / "tsconfig.json", '{"strict": true}')
    _write(
        tmp_path / "apps" / "mission-control" / "app" / "layout.tsx",
        "export default function Layout() { return null; }",
    )
    _write(
        tmp_path / "apps" / "mission-control" / "app" / "(shell)" / "page.tsx",
        "export default function Page() { return null; }",
    )
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    result = audit.check_mission_control_typescript_strict()
    assert result.passed is True


def test_check_mission_control_e2e_controls_passes(tmp_path, monkeypatch) -> None:
    _write(
        tmp_path / "apps" / "mission-control" / "package.json",
        '{"scripts":{"test:e2e":"playwright test"}}',
    )
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        """
name: CI
jobs:
  lint-test:
    steps:
      - name: Install Playwright Browser (Chromium)
        run: npx playwright install --with-deps chromium
      - name: Mission Control E2E Tests
        run: npm run test:e2e
""".strip(),
    )
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    result = audit.check_mission_control_e2e_controls()
    assert result.passed is True


def test_check_mission_control_e2e_controls_fails_when_missing(tmp_path, monkeypatch) -> None:
    _write(tmp_path / "apps" / "mission-control" / "package.json", '{"scripts":{"test":"vitest"}}')
    _write(tmp_path / ".github" / "workflows" / "ci.yml", "name: CI")
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    result = audit.check_mission_control_e2e_controls()
    assert result.passed is False
    assert "e2e" in result.notes


def test_check_tracing_and_pager_controls_passes(tmp_path, monkeypatch) -> None:
    _write(
        tmp_path / "deploy" / "docker-compose.yaml",
        """
services:
  jaeger:
    image: jaegertracing/all-in-one:1.59
  api-gateway:
    environment:
      OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: http://jaeger:4318/v1/traces
""".strip(),
    )
    _write(
        tmp_path / "deploy" / "docker-compose.monitoring.yaml",
        """
services:
  alertmanager:
    command:
      - --config.expand-env
    environment:
      PAGER_WEBHOOK_URL: http://localhost:9999/pager
""".strip(),
    )
    _write(
        tmp_path / "deploy" / "monitoring" / "alertmanager" / "alertmanager.yml",
        """
route:
  routes:
    - matchers:
        - severity =~ critical|high
      receiver: pager
receivers:
  - name: pager
    webhook_configs:
      - url: ${PAGER_WEBHOOK_URL}
""".strip(),
    )
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    result = audit.check_tracing_and_pager_controls()
    assert result.passed is True


def test_check_tracing_and_pager_controls_fails_when_missing(tmp_path, monkeypatch) -> None:
    _write(tmp_path / "deploy" / "docker-compose.yaml", "services: {}")
    _write(tmp_path / "deploy" / "docker-compose.monitoring.yaml", "services: {}")
    _write(tmp_path / "deploy" / "monitoring" / "alertmanager" / "alertmanager.yml", "route: {}")
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    result = audit.check_tracing_and_pager_controls()
    assert result.passed is False
    assert "missing jaeger service" in result.notes


def test_check_optional_data_plane_observability_controls_passes(tmp_path, monkeypatch) -> None:
    _write(
        tmp_path / "deploy" / "monitoring" / "prometheus" / "rules" / "thefactory-alerts.yml",
        """
groups:
  - name: thefactory-optional-data-plane
    rules:
      - alert: Neo4jAdapterNotReady
        annotations:
          runbook: docs/runbooks/optional_data_plane_incident_runbook.md
      - alert: ObjectStorageAdapterNotReady
      - alert: Neo4jMirrorWriteErrorRateHigh
      - alert: ObjectStorageMirrorWriteErrorRateHigh
      - alert: Neo4jMirrorWriteLatencyP95High
      - alert: ObjectStorageMirrorWriteLatencyP95High
""".strip(),
    )
    _write(
        tmp_path
        / "deploy"
        / "monitoring"
        / "grafana"
        / "provisioning"
        / "dashboards"
        / "json"
        / "thefactory-overview.json",
        '{"panels":[{"targets":[{"expr":"orchestrator_optional_adapter_mirror_writes_total"}]}]}',
    )
    _write(
        tmp_path / "docs" / "runbooks" / "optional_data_plane_incident_runbook.md",
        "# runbook\nNeo4jAdapterNotReady\n",
    )
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    result = audit.check_optional_data_plane_observability_controls()
    assert result.passed is True


def test_check_optional_data_plane_observability_controls_fails_when_missing(
    tmp_path, monkeypatch
) -> None:
    _write(
        tmp_path / "deploy" / "monitoring" / "prometheus" / "rules" / "thefactory-alerts.yml",
        "groups: []\n",
    )
    _write(
        tmp_path
        / "deploy"
        / "monitoring"
        / "grafana"
        / "provisioning"
        / "dashboards"
        / "json"
        / "thefactory-overview.json",
        '{"panels":[]}',
    )
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    result = audit.check_optional_data_plane_observability_controls()
    assert result.passed is False
    assert "missing alert rule" in result.notes


def test_check_slo_and_dora_controls_passes(tmp_path, monkeypatch) -> None:
    _write(
        tmp_path / "deploy" / "monitoring" / "prometheus" / "rules" / "thefactory-alerts.yml",
        """
groups:
  - name: slo
    rules:
      - alert: ApiGatewayErrorBudgetBurnFast
      - alert: ApiGatewayErrorBudgetBurnSlow
      - alert: OrchestratorErrorBudgetBurnFast
      - alert: OrchestratorErrorBudgetBurnSlow
      - alert: PodWorkerAgentLatencyP99High
      - alert: DedicatedAgentRuntimeLatencyP99High
      - alert: AuditWorkerAgentLatencyP99High
""".strip(),
    )
    _write(
        tmp_path
        / "deploy"
        / "monitoring"
        / "grafana"
        / "provisioning"
        / "dashboards"
        / "json"
        / "thefactory-overview.json",
        '{"panels":[{"title":"Error Budget Burn (x)"},{"title":"Per-Agent Task p99 (s)"}]}',
    )
    _write(
        tmp_path / ".github" / "workflows" / "qualification.yml",
        "steps:\n  - run: python scripts/dora_metrics_summary.py\n",
    )
    _write(
        tmp_path / "Makefile",
        ".PHONY: dora-metrics\ndora-metrics:\n\tpython scripts/dora_metrics_summary.py\n",
    )
    _write(tmp_path / "scripts" / "dora_metrics_summary.py", "print('ok')\n")
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)

    result = audit.check_slo_and_dora_controls()
    assert result.passed is True


def test_check_slo_and_dora_controls_fails_when_missing(tmp_path, monkeypatch) -> None:
    _write(
        tmp_path / "deploy" / "monitoring" / "prometheus" / "rules" / "thefactory-alerts.yml",
        "groups: []\n",
    )
    _write(
        tmp_path
        / "deploy"
        / "monitoring"
        / "grafana"
        / "provisioning"
        / "dashboards"
        / "json"
        / "thefactory-overview.json",
        '{"panels":[]}',
    )
    _write(tmp_path / ".github" / "workflows" / "qualification.yml", "steps: []\n")
    _write(tmp_path / "Makefile", ".PHONY: all\n")
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)

    result = audit.check_slo_and_dora_controls()
    assert result.passed is False
    assert "missing slo alert rule" in result.notes


def test_check_long_duration_reliability_controls_passes(tmp_path, monkeypatch) -> None:
    _write(
        tmp_path / "Makefile",
        """
.PHONY: reliability
reliability:
\tpowershell -ExecutionPolicy Bypass -File scripts/reliability_qualification.ps1
""".strip(),
    )
    _write(tmp_path / "scripts" / "reliability_qualification.py", "print('ok')\n")
    _write(tmp_path / "scripts" / "reliability_qualification.ps1", "Write-Host 'ok'\n")
    _write(
        tmp_path / "docs" / "OPERATIONS_RUNBOOK.md",
        "powershell -ExecutionPolicy Bypass -File scripts/reliability_qualification.ps1\n",
    )
    _write(tmp_path / "docs" / "CURRENT_TODO.md", "# Current TODO\n")
    _write(
        tmp_path
        / "docs"
        / "archive"
        / "2026-06-13"
        / "LONG_DURATION_RELIABILITY_QUALIFICATION.md",
        "# Reliability\n",
    )
    _write(
        tmp_path / "docs" / "evidence" / "reliability_qualification_baseline_2026-03-03.json",
        "{}\n",
    )
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    result = audit.check_long_duration_reliability_controls()
    assert result.passed is True


def test_check_long_duration_reliability_controls_fails_when_missing(tmp_path, monkeypatch) -> None:
    _write(tmp_path / "Makefile", ".PHONY: all\n")
    _write(tmp_path / "docs" / "OPERATIONS_RUNBOOK.md", "# runbook\n")
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    result = audit.check_long_duration_reliability_controls()
    assert result.passed is False
    assert "missing artifact" in result.notes


def test_check_compliance_evidence_mapping_passes(tmp_path, monkeypatch) -> None:
    _write(
        tmp_path / "docs" / "COMPLIANCE_EVIDENCE_MAPPING.md",
        """
# map
SOC2 controls
CMMC controls
evidence artifact references
""".strip(),
    )
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    result = audit.check_compliance_evidence_mapping()
    assert result.passed is True


def test_check_compliance_evidence_mapping_fails_when_missing(tmp_path, monkeypatch) -> None:
    _write(tmp_path / "docs" / "COMPLIANCE_EVIDENCE_MAPPING.md", "# map\nSOC2 only\n")
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    result = audit.check_compliance_evidence_mapping()
    assert result.passed is False
    assert "cmmc" in result.notes.lower()
