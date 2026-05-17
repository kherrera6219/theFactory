import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

agent_integrations = importlib.import_module("orchestrator.agent_integrations")
agent_personas = importlib.import_module("orchestrator.agent_personas")
agent_registry = importlib.import_module("orchestrator.agent_registry")

AgentDefinition = agent_registry.AgentDefinition


def _agent(**overrides: object) -> AgentDefinition:
    defaults: dict[str, object] = {
        "index": 999,
        "agent_id": "AGENT-99-CUSTOM",
        "short_code": "CUSTOM",
        "name": "Custom Agent",
        "tier": "Custom Tier",
        "pod": "Pod X",
        "role": "Custom role",
        "category": "support",
        "specialties": (),
    }
    defaults.update(overrides)
    return AgentDefinition(**defaults)


def test_persona_dedupe_and_specialty_helpers() -> None:
    assert agent_personas._dedupe(["", "  ", "value", "value"]) == ["value"]
    assert agent_personas._specialty_label(_agent(category="specialist", specialties=())) is None


def test_persona_job_title_and_scope_fallbacks() -> None:
    manager = _agent(category="pod_manager", short_code="PODX-MGR", pod="Pod X")
    audit = _agent(category="pod_audit", short_code="PODX-AUDIT", pod="Pod X")
    fallback = _agent(category="support", short_code="UNKNOWN")
    assert agent_personas._job_title_for_agent(manager) == "Pod X Coordination Manager"
    assert agent_personas._job_title_for_agent(audit) == "Pod X Audit and Verification Lead"
    assert agent_personas._job_title_for_agent(fallback) == "Custom Agent"
    assert (
        agent_personas._job_scope_for_agent(fallback)
        == "Owns scoped mission outcomes aligned to assigned category responsibilities."
    )


def test_persona_tools_data_system_paths_and_model_route() -> None:
    specialist = _agent(category="specialist", specialties=("python",))
    tools = agent_personas._tools_for_agent(
        specialist,
        llm_recommendation={"provider": "openai", "model": "gpt-5.5"},
        data_systems=[
            {"name": "redis", "status": "implemented"},
            {"name": "qdrant", "status": ""},
            {"name": None, "status": "planned"},
        ],
    )
    assert "redis (implemented)" in tools
    assert "qdrant" in tools
    assert "Primary model route: openai/gpt-5.5" in tools


def test_persona_tools_without_full_model_route() -> None:
    tools = agent_personas._tools_for_agent(
        _agent(category="support"),
        llm_recommendation={"provider": "openai", "model": ""},
        data_systems=[],
    )
    assert all("Primary model route:" not in item for item in tools)


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        ("interface", "omega"),
        ("executive", "alpha"),
        ("pod_manager", "alpha"),
        ("pod_audit", "delta"),
        ("specialist", "beta"),
        ("support", "rho"),
    ],
)
def test_persona_default_primary_protocol(category: str, expected: str) -> None:
    assert agent_personas._default_primary_protocol(_agent(category=category)) == expected


def test_persona_model_routing_optional_fields() -> None:
    route = agent_personas._model_routing(
        {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "mode": "thinking",
            "reasoning_effort": "high",
            "thinking_mode": "enabled",
            "thinking_budget_tokens": 8192,
            "thinking_level": "high",
            "fallback_provider": "openai",
            "fallback_model": "gpt-5.5",
        }
    )
    assert route["mode"] == "thinking"
    assert route["reasoning_effort"] == "high"
    assert route["thinking_mode"] == "enabled"
    assert route["thinking_budget_tokens"] == 8192
    assert route["thinking_level"] == "high"
    assert route["fallback_provider"] == "openai"
    assert route["fallback_model"] == "gpt-5.5"


def test_persona_model_routing_omits_mode_when_empty() -> None:
    route = agent_personas._model_routing({"provider": "openai", "model": "gpt-5.5"})
    assert "mode" not in route


def test_persona_standard_mappings_and_missing_source_branches(monkeypatch) -> None:
    normal_agent = _agent(short_code="BROKER")
    assert "preventive handling" in agent_personas._role_mapping_for_standard(
        normal_agent, "owasp-top-10-2021"
    )
    assert "recognized production security" in agent_personas._role_mapping_for_standard(
        normal_agent, "unknown-standard"
    )

    monkeypatch.setattr(
        agent_personas,
        "_BASELINE_STANDARD_IDS",
        ("missing-standard",),
    )
    monkeypatch.setattr(agent_personas, "_CATEGORY_STANDARD_IDS", {})
    monkeypatch.setattr(agent_personas, "_SHORT_CODE_STANDARD_IDS", {})
    assert agent_personas._standards_alignment_for_agent(normal_agent) == []
    assert agent_personas._evidence_sources_for_agent(normal_agent) == []


def test_persona_master_instruction_default_fallback() -> None:
    text = agent_personas._master_instruction(
        _agent(short_code="UNKNOWN", role="Custom guardrail execution"),
        protocols=[],
        llm_recommendation={},
    )
    assert "AGENT-99-CUSTOM" in text
    assert "custom guardrail execution" in text


def test_integration_protocol_topic_store_and_llm_fallback_paths(monkeypatch) -> None:
    unknown = _agent(category="unknown", pod="Unknown Pod")
    specialist = _agent(category="specialist", pod="Unknown Pod")
    pod_manager = _agent(category="pod_manager", pod="Unknown Pod")
    pod_audit = _agent(category="pod_audit", pod="Unknown Pod")

    assert agent_integrations._protocols_for_agent(unknown) == ["rho"]
    assert agent_integrations._topic_bindings_for_agent(pod_manager)["consume"] == [
        "artifact.rir.rejected",
        "artifact.rir.verified",
    ]
    assert agent_integrations._topic_bindings_for_agent(pod_audit)["consume"] == [
        "artifact.rir.submitted",
    ]
    assert agent_integrations._topic_bindings_for_agent(specialist)["consume"] == [
        "mission.state.running",
    ]
    specialist_with_known_pod = _agent(category="specialist", pod="Pod A")
    assert "cluster.assigned.podA" in agent_integrations._topic_bindings_for_agent(
        specialist_with_known_pod
    )["consume"]
    unknown_topics = agent_integrations._topic_bindings_for_agent(_agent(category="unknown"))
    assert "agent.heartbeat" in unknown_topics["publish"]
    assert unknown_topics["consume"] == []

    specialist_stores = {
        store["name"] for store in agent_integrations._store_bindings_for_agent(specialist)
    }
    assert "qdrant" in specialist_stores
    assert "neo4j" not in specialist_stores

    llm = agent_integrations._llm_recommendation_for_agent(_agent(agent_id="AGENT-XX-UNKNOWN"))
    assert llm["profile"] == "openai_exec"
    assert llm["provider"] == "openai"

    records = [
        {"protocols": ["rho"], "data_systems": [{"name": "redis"}], "llm_recommendation": None},
        {
            "protocols": ["alpha"],
            "data_systems": [{"name": "postgresql"}],
            "llm_recommendation": {"provider": "", "model": ""},
        },
        {
            "protocols": ["beta"],
            "data_systems": [{"name": "qdrant"}],
            "llm_recommendation": {"provider": "openai", "model": "gpt-5.5"},
        },
    ]

    monkeypatch.setattr(
        agent_integrations,
        "AGENT_REGISTRY",
        (_agent(agent_id="AGENT-A"), _agent(agent_id="AGENT-B"), _agent(agent_id="AGENT-C")),
    )
    monkeypatch.setattr(
        agent_integrations,
        "build_agent_integration_record",
        lambda agent: records.pop(0),
    )
    snapshot = agent_integrations.build_agent_integrations_snapshot()
    assert snapshot["protocols"] == ["alpha", "beta", "rho"]
    assert snapshot["data_systems"] == ["postgresql", "qdrant", "redis"]
    assert snapshot["llm_provider_counts"] == {"openai": 1}
    assert snapshot["llm_model_counts"] == {"gpt-5.5": 1}


def test_agent_registry_normalize_language() -> None:
    assert agent_registry.normalize_language(None) == ""
    assert agent_registry.normalize_language(" py ") == "python"
    assert agent_registry.normalize_language(" C++ ") == "cpp"
    assert agent_registry.normalize_language("unknown-lang") == "unknown-lang"
