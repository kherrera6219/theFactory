import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "mission_artifact_qualification.py"

spec = importlib.util.spec_from_file_location("mission_artifact_qualification", MODULE_PATH)
assert spec is not None and spec.loader is not None
qualification = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = qualification
spec.loader.exec_module(qualification)


def test_parse_args_defaults(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["mission_artifact_qualification.py"])
    args = qualification.parse_args()
    assert args.gateway_base_url == "http://localhost:8100"
    assert args.orchestrator_base_url == "http://localhost:8101"
    assert args.profile_label == "shared-workers"
    assert args.timeout_seconds == 90.0
    assert args.required_chain_events == [
        "MISSION_PM_INTAKE",
        "MISSION_CEO_DELEGATED",
        "MISSION_POD_MANAGER_ASSIGNED",
        "MISSION_SPECIALIST_ASSIGNED",
    ]


def test_extract_event_types_handles_mixed_records() -> None:
    event_types = qualification._extract_event_types(
        [
            {"event_type": "MISSION_PM_INTAKE"},
            {"event_type": " mission_complete "},
            {"other": "value"},
            "not-a-dict",
        ]
    )
    assert event_types == ["MISSION_PM_INTAKE", "MISSION_COMPLETE"]


def test_extract_chain_records_supports_endpoint_payload_shape() -> None:
    records = qualification._extract_chain_records(
        {
            "mission_id": "mission-1",
            "events": [{"event_type": "MISSION_PM_INTAKE"}, {"event_type": "MISSION_COMPLETE"}],
        }
    )
    assert len(records) == 2


def test_validate_http_url_rejects_non_http_schemes() -> None:
    assert (
        qualification._validate_http_url("http://localhost:8100/readyz")
        == "http://localhost:8100/readyz"
    )
    try:
        qualification._validate_http_url("file:///tmp/test.json")
    except ValueError as exc:
        assert "unsupported URL" in str(exc)
    else:
        raise AssertionError("expected ValueError for non-http URL")


def test_evaluate_result_passes_with_required_artifacts() -> None:
    passed, failure_reasons, diagnostics = qualification._evaluate_result(
        final_state="COMPLETE",
        pod_assignment={"pod_name": "podA"},
        logicnodes=[{"node_id": "n-1"}],
        chain_trace=[
            {"event_type": "MISSION_PM_INTAKE"},
            {"event_type": "MISSION_CEO_DELEGATED"},
            {"event_type": "MISSION_POD_MANAGER_ASSIGNED"},
            {"event_type": "MISSION_SPECIALIST_ASSIGNED"},
        ],
        required_chain_events=(
            "MISSION_PM_INTAKE",
            "MISSION_CEO_DELEGATED",
            "MISSION_POD_MANAGER_ASSIGNED",
            "MISSION_SPECIALIST_ASSIGNED",
        ),
    )
    assert passed is True
    assert failure_reasons == []
    assert diagnostics["assignment_present"] is True
    assert diagnostics["logicnode_count"] == 1
    assert diagnostics["missing_chain_events"] == []


def test_evaluate_result_fails_missing_artifacts_and_chain() -> None:
    passed, failure_reasons, diagnostics = qualification._evaluate_result(
        final_state="FAILED",
        pod_assignment={},
        logicnodes=[],
        chain_trace=[{"event_type": "MISSION_PM_INTAKE"}],
        required_chain_events=(
            "MISSION_PM_INTAKE",
            "MISSION_CEO_DELEGATED",
            "MISSION_POD_MANAGER_ASSIGNED",
            "MISSION_SPECIALIST_ASSIGNED",
        ),
    )
    assert passed is False
    assert any("did not reach COMPLETE" in reason for reason in failure_reasons)
    assert any("missing pod assignment artifact" in reason for reason in failure_reasons)
    assert any("missing logicnode artifacts" in reason for reason in failure_reasons)
    assert any("missing required chain events" in reason for reason in failure_reasons)
    assert diagnostics["assignment_present"] is False
    assert diagnostics["logicnode_count"] == 0


def test_run_accepts_201_created_for_mission_creation(tmp_path, monkeypatch) -> None:
    responses = iter(
        [
            (200, {"ready": True}),
            (200, {"ready": True}),
            (201, {"mission_id": "mission-123"}),
            (200, [{"event_type": "MISSION_PM_INTAKE"}]),
            (
                200,
                {
                    "events": [
                        {"event_type": "MISSION_PM_INTAKE"},
                        {"event_type": "MISSION_CEO_DELEGATED"},
                        {"event_type": "MISSION_POD_MANAGER_ASSIGNED"},
                        {"event_type": "MISSION_SPECIALIST_ASSIGNED"},
                    ]
                },
            ),
            (200, {"pod_name": "podA"}),
            (200, [{"node_id": "n-1"}]),
        ]
    )

    def fake_request_json(method: str, url: str, **kwargs):  # type: ignore[no-untyped-def]
        return next(responses)

    monkeypatch.setattr(qualification, "_request_json", fake_request_json)
    monkeypatch.setattr(
        qualification,
        "_wait_for_terminal_state",
        lambda **kwargs: ("COMPLETE", {"mission_id": "mission-123", "state": "COMPLETE"}),
    )

    output_file = tmp_path / "qualification.json"
    history_file = tmp_path / "qualification-history.jsonl"
    args = SimpleNamespace(
        gateway_base_url="http://localhost:8100",
        orchestrator_base_url="http://localhost:8101",
        prompt="Build a policy API",
        language="python",
        source="test",
        profile_label="full-dedicated-test",
        timeout_seconds=1.0,
        poll_seconds=0.01,
        required_chain_events=[
            "MISSION_PM_INTAKE",
            "MISSION_CEO_DELEGATED",
            "MISSION_POD_MANAGER_ASSIGNED",
            "MISSION_SPECIALIST_ASSIGNED",
        ],
        output_file=output_file,
        history_file=history_file,
    )

    assert qualification.run(args) == 0
    assert output_file.exists()
    assert history_file.exists()
