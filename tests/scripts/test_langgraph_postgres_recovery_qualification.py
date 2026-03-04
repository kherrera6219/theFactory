import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "langgraph_postgres_recovery_qualification.py"

spec = importlib.util.spec_from_file_location(
    "langgraph_postgres_recovery_qualification", MODULE_PATH
)
assert spec is not None and spec.loader is not None
qualification = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = qualification
spec.loader.exec_module(qualification)


def test_parse_args_defaults(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["langgraph_postgres_recovery_qualification.py"])
    args = qualification.parse_args()
    assert args.base_url == "http://localhost:8100"
    assert args.orchestrator_ready_url == "http://localhost:8101/readyz"
    assert args.transition_step_seconds == 3.0
    assert args.restart_after_seconds == 0.5


def test_langgraph_env_and_runtime_validation(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["langgraph_postgres_recovery_qualification.py"])
    args = qualification.parse_args()
    env = qualification._langgraph_env(args)
    assert env["LANGGRAPH_ENABLED"] == "true"
    assert env["LANGGRAPH_CHECKPOINTER"] == "postgres"
    assert env["LANGGRAPH_CHECKPOINTER_SETUP"] == "true"

    ok, reasons = qualification._validate_runtime(
        {"langgraph_enabled": True, "langgraph_checkpointer": "postgres"}
    )
    assert ok is True
    assert reasons == []

    ok, reasons = qualification._validate_runtime(
        {"langgraph_enabled": False, "langgraph_checkpointer": "none"}
    )
    assert ok is False
    assert "langgraph_enabled is not true" in reasons
    assert "langgraph_checkpointer is not postgres" in reasons


def test_validate_mission_events() -> None:
    ok, reasons, diagnostics = qualification._validate_mission_events(
        [
            {"event_type": "MISSION_RUNNING"},
            {"event_type": "MISSION_VERIFIED"},
            {"event_type": "MISSION_COMPLETE"},
        ]
    )
    assert ok is True
    assert reasons == []
    assert diagnostics["missing_required_event_types"] == []

    ok, reasons, diagnostics = qualification._validate_mission_events(
        [
            {"event_type": "MISSION_RUNNING"},
            {"event_type": "MISSION_COMPLETE"},
        ]
    )
    assert ok is False
    assert "MISSION_VERIFIED" in reasons[0]
    assert diagnostics["missing_required_event_types"] == ["MISSION_VERIFIED"]


def test_compose_command() -> None:
    command = qualification._compose_command(
        "deploy/docker-compose.yaml",
        "restart",
        "orchestrator",
    )
    assert command == [
        "docker",
        "compose",
        "-f",
        "deploy/docker-compose.yaml",
        "restart",
        "orchestrator",
    ]
