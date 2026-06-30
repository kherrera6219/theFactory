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


def _has_any_path(paths: list[Path]) -> bool:
    return any(path.exists() for path in paths)


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
        REPO_ROOT / "services" / "agent-runtime" / "Dockerfile",
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
        "AGENT_01_PM_SERVICE_API_KEY",
        "AGENT_10_TESTER_SERVICE_API_KEY",
        "AGENT_14_PYTHON_SERVICE_API_KEY",
        "AGENT_35_MATHEMATICA_SERVICE_API_KEY",
        "AGENT_36_GO_SERVICE_API_KEY",
        "AGENT_37_HASKELL_SERVICE_API_KEY",
        "AGENT_38_OCAML_SERVICE_API_KEY",
    ]
    missing = [name for name in required if f"{name}=" not in env_text]
    redis_tls_hardened = "ssl_cert_reqs=required" in env_text and "ssl_ca_certs=" in env_text
    postgres_tls_hardened = "sslmode=verify-full" in env_text and "sslrootcert=" in env_text
    passed = not missing and redis_tls_hardened and postgres_tls_hardened
    return _result(
        check_id="INF-007",
        priority="CRITICAL",
        description="Environment template includes required DB and key variables",
        passed=passed,
        notes=(
            "missing=" + ", ".join(missing)
            if missing
            else (
                "required variables present"
                if redis_tls_hardened and postgres_tls_hardened
                else (
                    "required variables present; REDIS_URL TLS verification not enforced"
                    if not redis_tls_hardened
                    else "required variables present; POSTGRES_URL verify-full not enforced"
                )
            )
        ),
    )


def check_compose_environment_profile_controls() -> AuditResult:
    compose_text = _read_text(REPO_ROOT / "deploy" / "docker-compose.yaml").lower()
    full_dedicated_compose_text = _read_text(
        REPO_ROOT / "deploy" / "docker-compose.full-dedicated-agents.yaml"
    ).lower()
    prod_compose_text = _read_text(REPO_ROOT / "deploy" / "docker-compose.prod.yaml").lower()
    makefile_text = _read_text(REPO_ROOT / "Makefile").lower()
    operations_runbook_text = _read_text(REPO_ROOT / "docs" / "OPERATIONS_RUNBOOK.md").lower()
    observability_text = _read_text(REPO_ROOT / "docs" / "OBSERVABILITY_STACK.md").lower()
    required_paths = [
        REPO_ROOT / "deploy" / "docker-compose.dev.yaml",
        REPO_ROOT / "deploy" / "docker-compose.staging.yaml",
        REPO_ROOT / "deploy" / "docker-compose.prod.yaml",
        REPO_ROOT / "deploy" / "docker-compose.full-dedicated-agents.yaml",
        REPO_ROOT / "docs" / "COMPOSE_ENVIRONMENT_PROFILES.md",
    ]
    missing_items = [f"missing artifact: {path}" for path in required_paths if not path.exists()]
    if "cap_drop" not in compose_text:
        missing_items.append("docker-compose missing cap_drop hardening")
    if "oom_score_adj" not in compose_text:
        missing_items.append("docker-compose missing oom_score_adj policy")
    if "ssl_cert_reqs=required" not in compose_text:
        missing_items.append("docker-compose missing redis tls client verification")
    if "ssl_cert_reqs=none" in compose_text:
        missing_items.append("docker-compose still allows redis insecure tls mode")
    # verify-full TLS to Postgres is now terminated by the PgBouncer sidecar
    # (PGBOUNCER_SERVER_TLS_SSLMODE: verify-full); the orchestrator->PgBouncer
    # hop stays on the internal network. Accept either the legacy direct URL
    # form (sslmode=verify-full) or the PgBouncer server-TLS form.
    if (
        "sslmode=verify-full" not in compose_text
        and "pgbouncer_server_tls_sslmode: verify-full" not in compose_text
    ):
        missing_items.append("docker-compose missing postgres verify-full wiring")
    if "./.local/postgres-certs" not in compose_text:
        missing_items.append("docker-compose missing postgres client/server cert mounts")
    if "./redis/entrypoint.sh:/usr/local/bin/docker-entrypoint-init-tls.sh:ro" not in compose_text:
        missing_items.append("docker-compose missing redis tls staging entrypoint")
    if "internal_service_api_key: ${internal_service_api_key:-}" not in compose_text:
        missing_items.append(
            "docker-compose missing INTERNAL_SERVICE_API_KEY "
            "wiring for internal callers"
        )
    if "agent_service_key_mode: strict" not in prod_compose_text:
        missing_items.append("prod overlay missing strict agent service key mode")
    if "./.local/redis-certs:/run/redis-certs:ro" not in full_dedicated_compose_text:
        missing_items.append("full dedicated overlay missing redis client cert mount parity")
    if "./redis/certs:/run/redis-certs:ro" in full_dedicated_compose_text:
        missing_items.append("full dedicated overlay still uses stale redis cert mount path")
    if "dev-redis-password-change-me-32chars" in full_dedicated_compose_text:
        missing_items.append("full dedicated overlay still uses stale redis password default")
    for service_name in ("agent-36-go:", "agent-37-haskell:", "agent-38-ocaml:"):
        if service_name not in full_dedicated_compose_text:
            missing_items.append(f"full dedicated overlay missing {service_name[:-1]} service")
    for service_name in (
        "minio",
        "milvus",
        "neo4j",
        "agent-36-go",
        "agent-37-haskell",
        "agent-38-ocaml",
    ):
        if service_name not in makefile_text:
            missing_items.append(f"make up-full-dedicated missing {service_name}")
    if "mission_artifact_qualification_full_dedicated_strict" not in operations_runbook_text:
        missing_items.append("runbook missing full-dedicated strict artifact evidence command")
    if "dedicated_agent_canary_full_dedicated_strict" not in operations_runbook_text:
        missing_items.append("runbook missing full-dedicated strict canary evidence command")
    if "dora_metrics_latest.json" not in observability_text:
        missing_items.append("observability docs missing qualification evidence correlation")

    passed = not missing_items
    return _result(
        check_id="INF-008",
        priority="HIGH",
        description=(
            "Compose overlays, hardening controls, full dedicated topology, "
            "and evidence correlation are configured"
        ),
        passed=passed,
        notes="; ".join(missing_items)
        if missing_items
        else "compose overlays, hardening controls, and evidence correlation present",
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
        REPO_ROOT / "docs" / "IMPLEMENTATION_STATUS.md",
        REPO_ROOT / "docs" / "CURRENT_TODO.md",
        REPO_ROOT / "docs" / "HANDOFF_CURRENT.md",
    ]
    missing = [str(path) for path in required_docs if not path.exists()]
    release_plan_reference = [
        REPO_ROOT / "docs" / "RELEASE_TRUST_PROMOTION_GATE.md",
        REPO_ROOT / "docs" / "archive" / "2026-06-13" / "RELEASE_COMPLETION_PLAN.md",
    ]
    if not _has_any_path(release_plan_reference):
        missing.append("missing current release gate doc or archived release completion plan")
    passed = not missing
    return _result(
        check_id="DOC-005",
        priority="HIGH",
        description="Operational runbooks and release-status docs exist",
        passed=passed,
        notes=(
            "missing=" + ", ".join(missing)
            if missing
            else "required operations and release-status docs present"
        ),
    )


def check_documentation_drift_controls() -> AuditResult:
    makefile = _read_text(REPO_ROOT / "Makefile")
    agents = _read_text(REPO_ROOT / "AGENTS.md")
    changelog = _read_text(REPO_ROOT / "CHANGELOG.md")
    docs_index = _read_text(REPO_ROOT / "docs" / "DOCUMENTATION_INDEX.md")
    definition_of_done = _read_text(REPO_ROOT / "docs" / "codex" / "DEFINITION_OF_DONE.md")
    review_checklist = _read_text(REPO_ROOT / "docs" / "codex" / "REVIEW_CHECKLIST.md")
    api_readme = _read_text(REPO_ROOT / "docs" / "api" / "README.md")
    docs_validator = _read_text(REPO_ROOT / "scripts" / "validate_documentation.py")

    required_paths = [
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "README.md",
        REPO_ROOT / "CHANGELOG.md",
        REPO_ROOT / "docs" / "codex" / "DEFINITION_OF_DONE.md",
        REPO_ROOT / "docs" / "codex" / "REVIEW_CHECKLIST.md",
        REPO_ROOT / "scripts" / "validate_documentation.py",
        REPO_ROOT / "scripts" / "export_openapi.py",
        REPO_ROOT / "docs" / "openapi" / "api-gateway.v1.json",
        REPO_ROOT / "docs" / "openapi" / "orchestrator.v1.json",
    ]
    missing_items = [f"missing {path.relative_to(REPO_ROOT)}" for path in required_paths if not path.exists()]

    if "python scripts/validate_documentation.py" not in makefile:
        missing_items.append("make validate does not run documentation validation")
    if "python scripts/export_openapi.py --check" not in makefile:
        missing_items.append("make validate does not enforce OpenAPI drift checks")
    if "Last validated: 2026-06-26" not in agents:
        missing_items.append("AGENTS.md last validated timestamp is not current")
    if "Audit Phase 12 Documentation Drift" not in changelog:
        missing_items.append("CHANGELOG.md missing current Phase 12 audit entry")
    if "DOCUMENTATION_INDEX.md" not in docs_index and "Documentation Index" not in docs_index:
        missing_items.append("documentation index is missing or malformed")
    if "make validate" not in definition_of_done or "make validate" not in review_checklist:
        missing_items.append("Codex DoD/review checklist do not require make validate")
    if "scripts/export_openapi.py --check" not in api_readme:
        missing_items.append("API docs do not document OpenAPI drift checking")
    if (
        "public_docstring_targets" not in docs_validator
        or "validate_public_docstrings" not in docs_validator
    ):
        missing_items.append("documentation validator does not enforce public docstrings")
    if "validate_migration_guide" not in docs_validator:
        missing_items.append("documentation validator does not enforce MIGRATION.md coverage")
    if "validate_architecture_diagram_drift" not in docs_validator:
        missing_items.append("documentation validator does not enforce architecture diagram drift")

    passed = not missing_items
    return _result(
        check_id="DOC-006",
        priority="HIGH",
        description="Documentation drift controls are current and enforced",
        passed=passed,
        notes=(
            "; ".join(missing_items)
            if missing_items
            else (
                "docs validation, public docstrings, OpenAPI drift check, "
                "architecture diagrams, migration guide, Codex standards, "
                "and current audit notes present"
            )
        ),
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
    playwright_config = _read_text(REPO_ROOT / "apps" / "mission-control" / "playwright.config.ts").lower()
    gitignore = _read_text(REPO_ROOT / ".gitignore").lower()
    e2e_dir = REPO_ROOT / "apps" / "mission-control" / "e2e"
    required_specs = [
        "mission-control.spec.ts",
        "mission-control-extended.spec.ts",
        "mission-build-new-complete.spec.ts",
        "mission-cost-panel.spec.ts",
        "mission-reduce-deps.spec.ts",
        "mission-runtime-qc.spec.ts",
    ]

    missing_items: list[str] = []
    if '"test:e2e"' not in package_json or "playwright test" not in package_json:
        missing_items.append("mission-control package.json missing playwright test:e2e script")
    if "mission control e2e tests" not in ci_text and "npm run test:e2e" not in ci_text:
        missing_items.append("ci workflow missing mission-control e2e test step")
    if "playwright install" not in ci_text:
        missing_items.append("ci workflow missing playwright browser install step")
    if 'testdir: "./e2e"' not in playwright_config or "testignore" not in playwright_config:
        missing_items.append("mission-control Playwright config missing web e2e directory or electron exclusion")
    if 'trace: "on-first-retry"' not in playwright_config or 'reporter: "list"' not in playwright_config:
        missing_items.append("mission-control Playwright config missing trace/report hygiene")
    missing_specs = [spec for spec in required_specs if not (e2e_dir / spec).exists()]
    if missing_specs:
        missing_items.append(f"mission-control e2e suite missing specs: {', '.join(missing_specs)}")
    for artifact_path in (
        "apps/mission-control/playwright-report/",
        "apps/mission-control/test-results/",
    ):
        if artifact_path not in gitignore:
            missing_items.append(f".gitignore missing generated artifact path {artifact_path}")

    passed = not missing_items
    return _result(
        check_id="UI-011",
        priority="HIGH",
        description="Mission Control critical e2e regression tests run in CI",
        passed=passed,
        notes=(
            "; ".join(missing_items)
            if missing_items
            else "mission-control e2e CI, Playwright config, spec coverage, and artifact hygiene present"
        ),
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
        "git tag -v",
        "cosign sign-blob",
        "cosign verify-blob",
        "promotion_gate.py",
        "promotion-policy.json",
        "--signed-tag-verified",
    ]
    missing_tokens = [token for token in required_tokens if token not in ci_text]
    missing_items: list[str] = []
    if missing_tokens:
        missing_items.append("workflow tokens missing: " + ", ".join(missing_tokens))
    if not policy_path.exists():
        missing_items.append(f"missing policy file: {policy_path}")
    if 'tags:' not in ci_text or '"v*"' not in ci_text:
        missing_items.append("ci workflow missing release tag push trigger")
    passed = not missing_items
    return _result(
        check_id="REL-001",
        priority="CRITICAL",
        description="Release attestation and promotion-gate controls are configured",
        passed=passed,
        notes="; ".join(missing_items) if missing_items else "release trust controls present",
    )


def check_model_governance_and_qualification_controls() -> AuditResult:
    ci_text = _read_text(REPO_ROOT / ".github" / "workflows" / "ci.yml").lower()
    qualification_workflow_text = _read_text(
        REPO_ROOT / ".github" / "workflows" / "qualification.yml"
    ).lower()
    policy_text = _read_text(REPO_ROOT / "deploy" / "promotion-policy.json").lower()
    missing_items: list[str] = []

    required_paths = [
        REPO_ROOT / "scripts" / "export_agent_model_inventory.py",
        REPO_ROOT / "scripts" / "qualification_gate_summary.py",
        REPO_ROOT / "docs" / "MODEL_PROMOTION_GOVERNANCE.md",
    ]
    missing_items.extend(
        [f"missing artifact: {path}" for path in required_paths if not path.exists()]
    )
    if "export_agent_model_inventory.py" not in ci_text:
        missing_items.append("ci workflow missing model inventory export step")
    if "qualification_gate_summary.py" not in ci_text:
        missing_items.append("ci workflow missing qualification summary step")
    if "schedule:" not in qualification_workflow_text or "cron:" not in qualification_workflow_text:
        missing_items.append("weekly qualification workflow missing schedule trigger")
    if "model_governance" not in policy_text:
        missing_items.append("promotion policy missing model governance block")
    if "qualification_gates" not in policy_text:
        missing_items.append("promotion policy missing qualification gate thresholds")

    passed = not missing_items
    return _result(
        check_id="REL-002",
        priority="HIGH",
        description=(
            "Model governance and qualification-threshold promotion controls are configured"
        ),
        passed=passed,
        notes="; ".join(missing_items)
        if missing_items
        else "model governance and qualification controls present",
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


def check_slo_and_dora_controls() -> AuditResult:
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
    qualification_workflow_text = _read_text(
        REPO_ROOT / ".github" / "workflows" / "qualification.yml"
    ).lower()
    makefile_text = _read_text(REPO_ROOT / "Makefile").lower()

    missing_items: list[str] = []
    for alert_name in (
        "apigatewayerrorbudgetburnfast",
        "apigatewayerrorbudgetburnslow",
        "orchestratorerrorbudgetburnfast",
        "orchestratorerrorbudgetburnslow",
        "podworkeragentlatencyp99high",
        "dedicatedagentruntimelatencyp99high",
        "auditworkeragentlatencyp99high",
    ):
        if alert_name not in alerts_text:
            missing_items.append(f"missing slo alert rule: {alert_name}")
    if "error budget burn (x)" not in dashboard_text:
        missing_items.append("grafana dashboard missing error budget burn panel")
    if "per-agent task p99 (s)" not in dashboard_text:
        missing_items.append("grafana dashboard missing per-agent latency panel")
    if "dora_metrics_summary.py" not in qualification_workflow_text:
        missing_items.append("qualification workflow missing dora metrics summary step")
    if "dora-metrics:" not in makefile_text:
        missing_items.append("makefile missing dora-metrics target")
    if not (REPO_ROOT / "scripts" / "dora_metrics_summary.py").exists():
        missing_items.append("missing scripts/dora_metrics_summary.py")

    passed = not missing_items
    return _result(
        check_id="OBS-011",
        priority="HIGH",
        description=(
            "SLO burn alerts, DORA summary generation, and per-agent latency panels "
            "are configured"
        ),
        passed=passed,
        notes="; ".join(missing_items) if missing_items else "slo and dora controls present",
    )


def check_long_duration_reliability_controls() -> AuditResult:
    makefile_text = _read_text(REPO_ROOT / "Makefile").lower()
    runbook_text = _read_text(REPO_ROOT / "docs" / "OPERATIONS_RUNBOOK.md").lower()
    evidence_dir = REPO_ROOT / "docs" / "evidence"
    evidence_files = sorted(evidence_dir.glob("reliability_qualification_baseline_*.json"))

    required_paths = [
        REPO_ROOT / "scripts" / "reliability_qualification.py",
        REPO_ROOT / "scripts" / "reliability_qualification.ps1",
        REPO_ROOT / "docs" / "CURRENT_TODO.md",
    ]
    missing_items = [f"missing artifact: {path}" for path in required_paths if not path.exists()]
    reliability_doc_reference = [
        REPO_ROOT / "docs" / "TESTING_QUALITY_GATES.md",
        REPO_ROOT
        / "docs"
        / "archive"
        / "2026-06-13"
        / "LONG_DURATION_RELIABILITY_QUALIFICATION.md",
    ]
    if not _has_any_path(reliability_doc_reference):
        missing_items.append("missing reliability qualification documentation reference")
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


def check_no_committed_keys() -> AuditResult:
    import subprocess
    try:
        res_pg = subprocess.run(["git", "log", "--all", "--", "deploy/postgres/certs/server.key"], capture_output=True, text=True)  # noqa: E501
        res_rd = subprocess.run(["git", "log", "--all", "--", "deploy/redis/certs/redis.key"], capture_output=True, text=True)  # noqa: E501
        passed = not res_pg.stdout.strip() and not res_rd.stdout.strip()
        notes = "no key history traced" if passed else "key commits found in history"
    except Exception as e:
        passed = False
        notes = f"failed to check git: {e}"
    return _result(
        check_id="SEC-KEY-001",
        priority="HIGH",
        description="No committed TLS key files are traced in git history",
        passed=passed,
        notes=notes
    )


def check_dr_drill_evidence() -> AuditResult:
    evidence_dir = REPO_ROOT / "docs" / "evidence"
    dr_files = list(evidence_dir.glob("dr_drill_phase26_*.json"))
    p17_files = list(evidence_dir.glob("phase17_dr_release_hardening_*.json"))
    passed = len(dr_files) > 0 or len(p17_files) > 0
    notes = f"found {len(dr_files)} DR drills, {len(p17_files)} phase17 drills" if passed else "no DR drill files found"  # noqa: E501
    return _result(
        check_id="DR-001",
        priority="HIGH",
        description="Disaster recovery drill timed evidence file is present",
        passed=passed,
        notes=notes
    )


def check_prompt_assets_registry() -> AuditResult:
    prompt_dir = REPO_ROOT / "services" / "orchestrator" / "orchestrator" / "prompt_assets"
    json_files = list(prompt_dir.glob("*.json"))
    passed = len(json_files) >= 5
    notes = f"found {len(json_files)} JSON prompt files in registry" if passed else f"found {len(json_files)} files (required >= 5)"  # noqa: E501
    return _result(
        check_id="AI-001",
        priority="HIGH",
        description="Prompt assets folder contains >= 5 JSON registry files",
        passed=passed,
        notes=notes
    )


def check_safety_evals_tests() -> AuditResult:
    eval_file = REPO_ROOT / "tests" / "eval" / "test_safety_evals.py"
    passed = False
    notes = ""
    if eval_file.exists():
        text = _read_text(eval_file)
        tests = re.findall(r"^\s*def\s+(test_[^\s(:]+)", text, flags=re.MULTILINE)
        passed = len(tests) >= 8
        notes = f"found {len(tests)} test cases in safety_evals (required >= 8)"
    else:
        notes = "test_safety_evals.py not found"
        
    return _result(
        check_id="AI-002",
        priority="HIGH",
        description="test_safety_evals.py exists and contains >= 8 tests",
        passed=passed,
        notes=notes
    )


def check_phases_evidence() -> AuditResult:
    evidence_dir = REPO_ROOT / "docs" / "evidence"
    missing = []
    for phase in ["phase22", "phase23", "phase24", "phase25"]:
        matches = list(evidence_dir.glob(f"{phase}*"))
        if not matches:
            missing.append(phase)
    passed = not missing
    notes = "all phase 22-25 evidence present" if passed else f"missing evidence for phases: {', '.join(missing)}"  # noqa: E501
    return _result(
        check_id="PHASE-001",
        priority="HIGH",
        description="Phase 22-25 evidence files are present in docs/evidence/",
        passed=passed,
        notes=notes
    )


def run_audit() -> list[AuditResult]:
    return [
        check_coverage_gate(),
        check_security_workflow(),
        check_non_root_containers(),
        check_environment_template(),
        check_compose_environment_profile_controls(),
        check_protocol_contract_artifacts(),
        check_operational_docs(),
        check_documentation_drift_controls(),
        check_mission_control_typescript_strict(),
        check_mission_control_e2e_controls(),
        check_design_tokens(),
        check_release_trust_controls(),
        check_model_governance_and_qualification_controls(),
        check_tracing_and_pager_controls(),
        check_optional_data_plane_observability_controls(),
        check_slo_and_dora_controls(),
        check_long_duration_reliability_controls(),
        check_compliance_evidence_mapping(),
        check_no_committed_keys(),
        check_dr_drill_evidence(),
        check_prompt_assets_registry(),
        check_safety_evals_tests(),
        check_phases_evidence(),
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
