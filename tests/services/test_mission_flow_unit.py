import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

mission_flow = importlib.import_module("orchestrator.mission_flow")


def test_with_chain_defaults_sets_required_fields() -> None:
    metadata = mission_flow.with_chain_defaults({"source": "test"}, "python")
    assert metadata["routing_enforced"] is True
    assert metadata["intake_agent_id"] == "AGENT-01-PM"
    assert metadata["executive_agent_id"] == "AGENT-02-CEO"
    assert metadata["expected_pod_manager_agent_id"] == "AGENT-12-PODA-MGR"
    assert metadata["selected_agent_id"] == "AGENT-01-PM"
    assert isinstance(metadata["chain_trace"], list)


def test_agent_and_language_resolution() -> None:
    assert mission_flow.normalize_agent_id(" agent-02-ceo ") == "AGENT-02-CEO"
    assert mission_flow.resolve_pod_manager_agent_id("rust") == "AGENT-18-PODB-MGR"
    assert mission_flow.resolve_specialist_agent_id("kotlin") == "AGENT-29-KOTLIN"


def test_completion_policy_exempt_flags() -> None:
    assert mission_flow.completion_policy_exempt({"completion_policy_exempt": True}) is True
    assert mission_flow.completion_policy_exempt({"allow_empty_artifacts": True}) is True
    assert mission_flow.completion_policy_exempt({"allow_empty_artifacts": False}) is False


def test_append_chain_event_updates_metadata() -> None:
    metadata = {"chain_trace": []}
    updated = mission_flow.append_chain_event(
        metadata,
        event_type="MISSION_CEO_DELEGATED",
        agent_id="AGENT-02-CEO",
        details={"target_agent_id": "AGENT-12-PODA-MGR"},
        timestamp="2026-03-08T00:00:00+00:00",
    )
    assert updated["last_chain_event_type"] == "MISSION_CEO_DELEGATED"
    assert updated["last_chain_event_at"] == "2026-03-08T00:00:00+00:00"
    assert updated["chain_trace"][0]["details"]["target_agent_id"] == "AGENT-12-PODA-MGR"
