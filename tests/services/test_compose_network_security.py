from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_COMPOSE = ROOT / "deploy" / "docker-compose.yaml"
PROD_COMPOSE = ROOT / "deploy" / "docker-compose.prod.yaml"
ENV_EXAMPLE = ROOT / ".env.example"


def _host_bind_defaults_from_port_specs(compose_text: str) -> dict[str, str]:
    defaults: dict[str, str] = {}
    for match in re.finditer(r'\$\{(?P<name>[A-Z0-9_]+_HOST_BIND):-(?P<default>[^}]+)\}', compose_text):
        defaults[match.group("name")] = match.group("default")
    return defaults


def test_compose_host_published_ports_default_to_loopback() -> None:
    compose_text = BASE_COMPOSE.read_text(encoding="utf-8")
    bind_defaults = _host_bind_defaults_from_port_specs(compose_text)

    expected_bind_vars = {
        "REDIS_HOST_BIND",
        "QDRANT_HOST_BIND",
        "NEO4J_HTTP_HOST_BIND",
        "NEO4J_BOLT_HOST_BIND",
        "POSTGRES_HOST_BIND",
        "MINIO_HOST_BIND",
        "MINIO_CONSOLE_HOST_BIND",
        "MILVUS_HOST_BIND",
        "MILVUS_METRICS_HOST_BIND",
        "JAEGER_UI_HOST_BIND",
        "OTLP_GRPC_HOST_BIND",
        "OTLP_HTTP_HOST_BIND",
        "ORCHESTRATOR_HOST_BIND",
        "API_GATEWAY_HOST_BIND",
        "MCP_HOST_BIND",
        "DASHBOARD_HOST_BIND",
        "MISSION_CONTROL_HOST_BIND",
    }

    assert expected_bind_vars <= bind_defaults.keys()
    assert all(bind_defaults[name] == "127.0.0.1" for name in expected_bind_vars)
    assert ":-0.0.0.0}" not in compose_text


def test_env_example_documents_compose_host_bind_controls() -> None:
    env_text = ENV_EXAMPLE.read_text(encoding="utf-8")
    bind_defaults = _host_bind_defaults_from_port_specs(BASE_COMPOSE.read_text(encoding="utf-8"))

    for bind_var in bind_defaults:
        assert f"{bind_var}=127.0.0.1" in env_text


def test_production_compose_requires_tls_object_storage() -> None:
    prod_text = PROD_COMPOSE.read_text(encoding="utf-8")

    assert 'OBJECT_STORAGE_ENABLED: "true"' in prod_text
    assert 'OBJECT_STORAGE_REQUIRE_TLS: "true"' in prod_text
    assert "Override OBJECT_STORAGE_ENDPOINT to a TLS endpoint" in prod_text


def test_orchestrator_does_not_mount_docker_sock() -> None:
    compose_text = BASE_COMPOSE.read_text(encoding="utf-8")
    orchestrator_start = compose_text.find("\n  orchestrator:")
    next_service = compose_text.find("\n  api-gateway:", orchestrator_start + 1)
    if next_service < 0:
        next_service = compose_text.find("\n  protocol-bus", orchestrator_start + 1)
    block = compose_text[orchestrator_start:next_service if next_service > 0 else None]
    assert "/var/run/docker.sock" not in block
    assert "SANDBOX_EXECUTOR_URL" in block
    assert "sandbox-runner:" in compose_text
    assert compose_text.count("/var/run/docker.sock:/var/run/docker.sock") == 1


def test_production_compose_uses_canonical_protocol_bus_dedup_ttl() -> None:
    prod_text = PROD_COMPOSE.read_text(encoding="utf-8")

    assert 'MCP_DEDUP_TTL_SECONDS: "600"' in prod_text
    assert "MESSAGE_DEDUP_TTL_SECONDS" not in prod_text
