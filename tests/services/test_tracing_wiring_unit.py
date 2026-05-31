from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_tracing_is_wired_for_service_entrypoints() -> None:
    expected_wiring = {
        ROOT / "services" / "pod-worker" / "pod_worker" / "main.py": (
            'configure_tracing(app, service_name="pod-worker")'
        ),
        ROOT / "services" / "audit-worker" / "audit_worker" / "main.py": (
            'configure_tracing(app, service_name="audit-worker")'
        ),
        ROOT / "services" / "protocol-bus-mcp" / "protocol_bus" / "mcp_server.py": (
            'configure_tracing(app, service_name="protocol-bus-mcp")'
        ),
        ROOT / "services" / "dashboard" / "dashboard" / "main.py": (
            'configure_tracing(app, service_name="dashboard")'
        ),
    }

    for path, call_snippet in expected_wiring.items():
        text = path.read_text(encoding="utf-8")
        assert call_snippet in text
