import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "dedicated_agent_canary_rollout.py"

spec = importlib.util.spec_from_file_location("dedicated_agent_canary_rollout", MODULE_PATH)
assert spec is not None and spec.loader is not None
canary = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = canary
spec.loader.exec_module(canary)


def test_parse_args_defaults(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["dedicated_agent_canary_rollout.py"])
    args = canary.parse_args()
    assert args.gateway_base_url == "http://localhost:8100"
    assert args.orchestrator_base_url == "http://localhost:8101"
    assert args.profile_label == "dedicated-agent-canary"
    assert args.language == "python"
    assert args.required_chain_events == [
        "MISSION_PM_INTAKE",
        "MISSION_CEO_DELEGATED",
        "MISSION_POD_MANAGER_ASSIGNED",
        "MISSION_SPECIALIST_ASSIGNED",
    ]


def test_resolve_expected_pod_manager_defaults_and_mapping() -> None:
    assert canary._resolve_expected_pod_manager("python") == "AGENT-12-PODA-MGR"
    assert canary._resolve_expected_pod_manager("rust") == "AGENT-18-PODB-MGR"
    assert canary._resolve_expected_pod_manager("kotlin") == "AGENT-24-PODC-MGR"
    assert canary._resolve_expected_pod_manager("julia") == "AGENT-30-PODD-MGR"
    assert canary._resolve_expected_pod_manager("unknown-language") == "AGENT-12-PODA-MGR"


def test_validate_http_url_rejects_non_http_schemes() -> None:
    assert canary._validate_http_url("https://example.test/readyz") == "https://example.test/readyz"
    try:
        canary._validate_http_url("file:///tmp/test.json")
    except ValueError as exc:
        assert "unsupported URL" in str(exc)
    else:
        raise AssertionError("expected ValueError for non-http URL")


def test_evaluate_canary_result_passes() -> None:
    passed, failure_reasons, diagnostics = canary._evaluate_canary_result(
        final_state="COMPLETE",
        mission_record={
            "metadata": {
                "routing_enforced": True,
                "intake_agent_id": "AGENT-01-PM",
                "executive_agent_id": "AGENT-02-CEO",
                "expected_pod_manager_agent_id": "AGENT-12-PODA-MGR",
            }
        },
        chain_trace=[
            {"event_type": "MISSION_PM_INTAKE"},
            {"event_type": "MISSION_CEO_DELEGATED"},
            {"event_type": "MISSION_POD_MANAGER_ASSIGNED"},
            {"event_type": "MISSION_SPECIALIST_ASSIGNED"},
        ],
        pod_assignment={"pod_name": "podA"},
        logicnodes=[{"node_id": "node-1"}],
        expected_pod_manager_agent_id="AGENT-12-PODA-MGR",
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
    assert diagnostics["completion_blocked_events"] == 0


def test_evaluate_canary_result_fails_with_guardrail_reasons() -> None:
    passed, failure_reasons, diagnostics = canary._evaluate_canary_result(
        final_state="FAILED",
        mission_record={"metadata": {"routing_enforced": False}},
        chain_trace=[
            {"event_type": "MISSION_PM_INTAKE"},
            {"event_type": "MISSION_COMPLETION_BLOCKED"},
        ],
        pod_assignment={},
        logicnodes=[],
        expected_pod_manager_agent_id="AGENT-12-PODA-MGR",
        required_chain_events=(
            "MISSION_PM_INTAKE",
            "MISSION_CEO_DELEGATED",
            "MISSION_POD_MANAGER_ASSIGNED",
            "MISSION_SPECIALIST_ASSIGNED",
        ),
    )
    assert passed is False
    assert any("did not reach COMPLETE" in reason for reason in failure_reasons)
    assert any("routing_enforced metadata flag" in reason for reason in failure_reasons)
    assert any("missing pod assignment artifact" in reason for reason in failure_reasons)
    assert any("missing logicnode artifacts" in reason for reason in failure_reasons)
    assert any("missing required chain events" in reason for reason in failure_reasons)
    assert any("completion-blocked event detected" in reason for reason in failure_reasons)
    assert diagnostics["completion_blocked_events"] == 1


def test_run_accepts_201_created_for_mission_creation(tmp_path, monkeypatch) -> None:
    responses = iter(
        [
            (200, {"ready": True}),
            (200, {"ready": True}),
            (201, {"mission_id": "mission-123"}),
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

    monkeypatch.setattr(canary, "_request_json", fake_request_json)
    monkeypatch.setattr(
        canary,
        "_wait_for_terminal_state",
        lambda **kwargs: (
            "COMPLETE",
            {
                "mission_id": "mission-123",
                "state": "COMPLETE",
                "metadata": {
                    "routing_enforced": True,
                    "intake_agent_id": "AGENT-01-PM",
                    "executive_agent_id": "AGENT-02-CEO",
                    "expected_pod_manager_agent_id": "AGENT-12-PODA-MGR",
                },
            },
        ),
    )

    output_file = tmp_path / "canary.json"
    args = SimpleNamespace(
        gateway_base_url="http://localhost:8100",
        orchestrator_base_url="http://localhost:8101",
        prompt="Build a policy API",
        language="python",
        source="test",
        profile_label="dedicated-agent-canary-test",
        timeout_seconds=1.0,
        poll_seconds=0.01,
        expected_pod_manager_agent_id="AGENT-12-PODA-MGR",
        required_chain_events=[
            "MISSION_PM_INTAKE",
            "MISSION_CEO_DELEGATED",
            "MISSION_POD_MANAGER_ASSIGNED",
            "MISSION_SPECIALIST_ASSIGNED",
        ],
        output_file=output_file,
    )

    assert canary.run(args) == 0
    assert output_file.exists()


def _blocked_at_verified(**overrides):
    """The exact shape of the 2026-08-24 qualification failure.

    Mission routes correctly and folds logic, then the completion gate blocks it
    because a credential-less stack produced source="fallback" output that
    cannot package. See docs/CANARY_BUILD_ARTIFACT_REGRESSION.md.
    """
    metadata = {
        "routing_enforced": True,
        "intake_agent_id": "AGENT-01-PM",
        "executive_agent_id": "AGENT-02-CEO",
        "expected_pod_manager_agent_id": "AGENT-18-PODB-MGR",
    }
    metadata.update(overrides.pop("metadata", {}))
    payload = dict(
        final_state="VERIFIED",
        mission_record={"metadata": metadata},
        chain_trace=[
            {"event_type": event}
            for event in (
                "MISSION_PM_INTAKE",
                "MISSION_CEO_DELEGATED",
                "MISSION_POD_MANAGER_ASSIGNED",
                "MISSION_SPECIALIST_ASSIGNED",
                "MISSION_LOGIC_FOLDED",
                "MISSION_BUILD_ARTIFACT_FAILED",
                "MISSION_COMPLETION_BLOCKED",
            )
        ],
        pod_assignment=None,
        logicnodes=[],
        expected_pod_manager_agent_id="AGENT-18-PODB-MGR",
        required_chain_events=canary.DEFAULT_REQUIRED_CHAIN_EVENTS,
    )
    payload.update(overrides)
    return payload


def test_full_mode_still_fails_a_completion_blocked_mission() -> None:
    """The regression must stay visible to the contract that claims to catch it."""
    passed, reasons, diagnostics = canary._evaluate_canary_result(
        **_blocked_at_verified(), mode=canary.FULL_MODE
    )
    assert passed is False
    assert any("did not reach COMPLETE" in reason for reason in reasons)
    assert any("completion-blocked" in reason for reason in reasons)
    assert diagnostics["build_artifact_failed"] is True


def test_wiring_mode_accepts_the_expected_completion_block() -> None:
    passed, reasons, diagnostics = canary._evaluate_canary_result(
        **_blocked_at_verified(), mode=canary.WIRING_MODE
    )
    assert passed is True
    assert reasons == []
    # The block is tolerated, not hidden.
    assert diagnostics["completion_blocked_events"] == 1
    assert diagnostics["build_artifact_failed"] is True
    assert "NOT proven" in diagnostics["proves"]


def test_wiring_mode_still_fails_on_broken_routing() -> None:
    """Wiring mode must not be a rubber stamp -- real defects still fail it."""
    passed, reasons, _ = canary._evaluate_canary_result(
        **_blocked_at_verified(metadata={"routing_enforced": False}),
        mode=canary.WIRING_MODE,
    )
    assert passed is False
    assert any("routing_enforced" in reason for reason in reasons)


def test_wiring_mode_still_fails_when_the_mission_never_gets_going() -> None:
    passed, reasons, _ = canary._evaluate_canary_result(
        **_blocked_at_verified(final_state="CLARIFYING"), mode=canary.WIRING_MODE
    )
    assert passed is False
    assert any("neither VERIFIED nor COMPLETE" in reason for reason in reasons)


def test_wiring_mode_treats_verified_as_terminal() -> None:
    """Otherwise every wiring run burns its full timeout before reporting."""
    assert "VERIFIED" in canary.WIRING_TERMINAL_STATES
    assert "VERIFIED" not in canary.TERMINAL_STATES
