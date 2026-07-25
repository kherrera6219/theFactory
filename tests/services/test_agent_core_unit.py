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
    assert llm["profile"] == "gemini_flash_high"
    assert llm["provider"] == "gemini"
    assert llm["model"] == "gemini-3.6-flash"
    assert llm["thinking_level"] == "high"

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


def test_llm_recommendation_provider_and_override_branches(monkeypatch) -> None:
    cfg = importlib.import_module("orchestrator.llm_delegation.config")

    # LLM_PROVIDER=openai forces the OpenAI path; a gemini_* profile is mapped to
    # its OpenAI equivalent (gemini_stem -> openai_codegen).
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1")
    monkeypatch.setattr(agent_integrations, "_AGENT_LLM_PROFILE_MAP", {"AGENT-TEST": "gemini_stem"})
    rec = agent_integrations._llm_recommendation_for_agent(_agent(agent_id="AGENT-TEST"))
    assert rec["profile"] == "openai_codegen"
    assert rec["provider"] == "openai"
    assert rec["model"] == "gpt-4.1"

    # LLM_PROVIDER=gemini keeps the Gemini path; gemini_ops_fast carries an OpenAI
    # fallback whose pinned gpt-5.5 is rewritten to the configured OPENAI_MODEL.
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.5")
    monkeypatch.setattr(agent_integrations, "_AGENT_LLM_PROFILE_MAP", {"AGENT-TEST": "gemini_ops_fast"})
    rec = agent_integrations._llm_recommendation_for_agent(_agent(agent_id="AGENT-TEST"))
    assert rec["provider"] == "gemini"
    assert rec["fallback_model"] == "gpt-4o"  # gpt-5.5 rewritten via empty/placeholder guard

    # No LLM_PROVIDER + an OpenAI key but no Gemini key auto-selects OpenAI; the
    # primary openai_exec profile's pinned gpt-5.5 is likewise rewritten.
    monkeypatch.setenv("LLM_PROVIDER", "")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.5")
    monkeypatch.setattr(agent_integrations, "_AGENT_LLM_PROFILE_MAP", {"AGENT-TEST": "openai_exec"})
    rec = agent_integrations._llm_recommendation_for_agent(_agent(agent_id="AGENT-TEST"))
    assert rec["provider"] == "openai"
    assert rec["model"] == "gpt-4o"

    # Auto-detect with a Gemini key present (and no OpenAI key) stays on Gemini.
    monkeypatch.setenv("LLM_PROVIDER", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "g-test-key")
    monkeypatch.setattr(agent_integrations, "_AGENT_LLM_PROFILE_MAP", {"AGENT-TEST": "gemini_flash_high"})
    rec = agent_integrations._llm_recommendation_for_agent(_agent(agent_id="AGENT-TEST"))
    assert rec["provider"] == "gemini"

    # Explicit Gemini mode downgrades an OpenAI-pinned profile to Gemini even when
    # an OpenAI key IS configured (regression guard: previously the agent stayed on
    # OpenAI whenever any OpenAI key was present, silently overriding LLM_PROVIDER=gemini).
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-present-but-should-be-ignored")
    monkeypatch.setattr(agent_integrations, "_AGENT_LLM_PROFILE_MAP", {"AGENT-TEST": "openai_exec"})
    rec = agent_integrations._llm_recommendation_for_agent(_agent(agent_id="AGENT-TEST"))
    assert rec["profile"] == "gemini_flash_high"
    assert rec["provider"] == "gemini"

    # Fallback rewrite leaves a non-placeholder OPENAI_MODEL untouched.
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1")
    monkeypatch.setattr(agent_integrations, "_AGENT_LLM_PROFILE_MAP", {"AGENT-TEST": "gemini_ops_fast"})
    rec = agent_integrations._llm_recommendation_for_agent(_agent(agent_id="AGENT-TEST"))
    assert rec["fallback_model"] == "gpt-4.1"

    # Vault lookup failure is swallowed and falls back to an empty vault.
    class _RaisingVar:
        def get(self):  # noqa: ANN201 - test stub
            raise RuntimeError("vault unavailable")

    monkeypatch.setattr(cfg, "current_vault_secrets", _RaisingVar())
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setattr(agent_integrations, "_AGENT_LLM_PROFILE_MAP", {})
    rec = agent_integrations._llm_recommendation_for_agent(_agent(agent_id="AGENT-TEST"))
    assert rec["provider"] == "gemini"


def test_llm_recommendation_vault_override_takes_priority_over_env(monkeypatch) -> None:
    # Regression: the Settings > "Primary LLM Provider" vault-path override
    # (mission.metadata["vault"]["llm_provider"/"llm_model"], forwarded via
    # current_vault_secrets) must win over LLM_PROVIDER/OPENAI_MODEL env
    # defaults -- this is the actual mechanism the operations-display API and
    # the real generation call path (llm_delegation.agents._agent_recommendation)
    # both consume.
    cfg = importlib.import_module("orchestrator.llm_delegation.config")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1")
    monkeypatch.setattr(agent_integrations, "_AGENT_LLM_PROFILE_MAP", {"AGENT-TEST": "openai_exec"})

    token = cfg.current_vault_secrets.set(
        {"llm_provider": "anthropic", "llm_model": "claude-opus-4-8"}
    )
    try:
        rec = agent_integrations._llm_recommendation_for_agent(_agent(agent_id="AGENT-TEST"))
    finally:
        cfg.current_vault_secrets.reset(token)

    assert rec["provider"] == "anthropic"
    assert rec["model"] == "claude-opus-4-8"
    assert rec["profile"] == "vault_override"
    assert "fallback_provider" not in rec


def test_llm_recommendation_ignores_incomplete_vault_override(monkeypatch) -> None:
    # A vault override missing either field (or naming an unsupported
    # provider) must not silently take effect -- fall through to the normal
    # env-based resolution instead.
    cfg = importlib.import_module("orchestrator.llm_delegation.config")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setattr(agent_integrations, "_AGENT_LLM_PROFILE_MAP", {"AGENT-TEST": "gemini_flash_high"})

    token = cfg.current_vault_secrets.set({"llm_provider": "anthropic", "llm_model": ""})
    try:
        rec = agent_integrations._llm_recommendation_for_agent(_agent(agent_id="AGENT-TEST"))
    finally:
        cfg.current_vault_secrets.reset(token)

    assert rec["provider"] == "gemini"
    assert rec.get("profile") != "vault_override"
