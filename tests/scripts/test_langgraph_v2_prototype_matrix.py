import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "langgraph_v2_prototype_matrix.py"

spec = importlib.util.spec_from_file_location("langgraph_v2_prototype_matrix", MODULE_PATH)
assert spec is not None and spec.loader is not None
matrix = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = matrix
spec.loader.exec_module(matrix)


def test_parse_args_defaults(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["langgraph_v2_prototype_matrix.py"])
    args = matrix.parse_args()
    assert args.gateway_base_url == "http://localhost:8100"
    assert args.orchestrator_base_url == "http://localhost:8101"
    assert args.orchestrator_ready_url == "http://localhost:8101/readyz"
    assert args.compose_file == "deploy/docker-compose.yaml"
    assert args.allow_prototype_failure is False


def test_resolve_pass_flag() -> None:
    assert matrix._resolve_pass_flag({"passed": True}, "passed", "pass") is True
    assert matrix._resolve_pass_flag({"pass": True}, "passed", "pass") is True
    assert matrix._resolve_pass_flag({"pass": False}, "passed", "pass") is False
    assert matrix._resolve_pass_flag({}, "passed", "pass") is False


def test_build_commands() -> None:
    baseline = matrix._build_baseline_command(
        python_executable="python",
        gateway_base_url="http://localhost:8100",
        orchestrator_base_url="http://localhost:8101",
        timeout_seconds=90.0,
        poll_seconds=1.0,
        output_file="baseline.json",
    )
    assert baseline[0] == "python"
    assert "scripts/mission_artifact_qualification.py" in baseline
    assert "--profile-label" in baseline
    assert "v1_1_baseline" in baseline

    prototype = matrix._build_prototype_command(
        python_executable="python",
        gateway_base_url="http://localhost:8100",
        orchestrator_ready_url="http://localhost:8101/readyz",
        compose_file="deploy/docker-compose.yaml",
        output_file="prototype.json",
    )
    assert prototype[0] == "python"
    assert "scripts/langgraph_postgres_recovery_qualification.py" in prototype
    assert "--compose-file" in prototype
    assert "deploy/docker-compose.yaml" in prototype
