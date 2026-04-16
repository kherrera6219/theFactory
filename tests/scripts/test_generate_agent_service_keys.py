import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "generate_agent_service_keys.py"

spec = importlib.util.spec_from_file_location("generate_agent_service_keys", MODULE_PATH)
assert spec is not None and spec.loader is not None
generate_agent_service_keys = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = generate_agent_service_keys
spec.loader.exec_module(generate_agent_service_keys)


def test_main_writes_all_agent_keys(tmp_path: Path, monkeypatch) -> None:
    output_file = tmp_path / ".env.agent-service-keys.local"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_agent_service_keys.py",
            "--output-file",
            str(output_file),
        ],
    )

    assert generate_agent_service_keys.main() == 0
    payload = output_file.read_text(encoding="utf-8")

    assert "AGENT_SERVICE_KEY_MODE=strict" in payload
    assert "INTERNAL_SERVICE_API_KEY=" in payload
    assert "AGENT_01_PM_SERVICE_API_KEY=" in payload
    assert "AGENT_35_MATHEMATICA_SERVICE_API_KEY=" in payload
    assert "AGENT_38_OCAML_SERVICE_API_KEY=" in payload
    agent_key_lines = [
        line
        for line in payload.splitlines()
        if line.startswith("AGENT_") and "_SERVICE_API_KEY=" in line
    ]
    assert len(agent_key_lines) == 38
