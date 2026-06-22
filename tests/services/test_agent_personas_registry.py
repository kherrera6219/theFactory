import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

agent_personas = importlib.import_module("orchestrator.agent_personas")
agent_registry = importlib.import_module("orchestrator.agent_registry")

AgentPersona = agent_personas.AgentPersona
LanguagePersona = agent_personas.LanguagePersona
AGENT_PERSONAS = agent_personas.AGENT_PERSONAS
LANGUAGE_PERSONAS = agent_personas.LANGUAGE_PERSONAS
AGENT_REGISTRY = agent_registry.AGENT_REGISTRY


def test_all_registry_agents_have_persona() -> None:
    """Guards against drift between agent_registry.py and agent_personas.py."""
    missing = [a.agent_id for a in AGENT_REGISTRY if a.agent_id not in AGENT_PERSONAS]
    assert missing == [], f"Agents missing personas: {missing}"


def test_persona_registry_has_no_orphans() -> None:
    registry_ids = {a.agent_id for a in AGENT_REGISTRY}
    orphans = [agent_id for agent_id in AGENT_PERSONAS if agent_id not in registry_ids]
    assert orphans == [], f"Personas without a registry agent: {orphans}"


def test_persona_records_are_well_formed() -> None:
    for agent in AGENT_REGISTRY:
        persona = AGENT_PERSONAS[agent.agent_id]
        assert isinstance(persona, AgentPersona)
        assert persona.agent_id == agent.agent_id
        assert persona.short_code == agent.short_code
        assert persona.title
        assert persona.primary_function == agent.role
        assert persona.scope
        assert persona.master_instruction
        assert persona.primary_protocol


def test_specialist_personas_carry_their_language() -> None:
    specialists = [a for a in AGENT_REGISTRY if a.category == "specialist"]
    assert specialists
    for agent in specialists:
        persona = AGENT_PERSONAS[agent.agent_id]
        assert persona.specialty_language == agent.specialties[0]


def test_previously_drifted_languages_are_fully_populated() -> None:
    """go/haskell/ocaml were missing from the old label/tooling dicts."""
    for language in ("go", "haskell", "ocaml"):
        persona = LANGUAGE_PERSONAS[language]
        assert isinstance(persona, LanguagePersona)
        assert persona.label
        assert persona.guidance
        assert persona.tooling


def test_every_specialist_language_has_a_language_persona() -> None:
    for agent in AGENT_REGISTRY:
        if agent.category == "specialist" and agent.specialties:
            language = agent.specialties[0]
            assert language in LANGUAGE_PERSONAS, f"missing LanguagePersona for {language}"


def test_language_accessors() -> None:
    assert agent_personas.get_language_label("python") == "Python"
    assert agent_personas.get_language_label("ocaml") == "OCaml"
    # Unknown language falls back to a title-cased key.
    assert agent_personas.get_language_label("brainfuck") == "Brainfuck"
    assert agent_personas.get_language_guidance("python")
    assert agent_personas.get_language_guidance("unknown-lang") == ""
    assert agent_personas.get_language_guidance("unknown-lang", "fallback") == "fallback"
    assert agent_personas.get_language_tooling("python")
    assert agent_personas.get_language_tooling("unknown-lang") == ""
    assert agent_personas.get_language_tooling("unknown-lang", "fallback") == "fallback"
    assert agent_personas.get_language_persona("python") is not None
    assert agent_personas.get_language_persona("unknown-lang") is None


def test_agent_persona_accessor() -> None:
    first = AGENT_REGISTRY[0]
    assert agent_personas.get_agent_persona(first.agent_id) is AGENT_PERSONAS[first.agent_id]
    assert agent_personas.get_agent_persona("AGENT-DOES-NOT-EXIST") is None


def test_registry_agents_expose_phase5_audit_fields() -> None:
    for agent in AGENT_REGISTRY:
        assert agent.pod_assignment == agent.pod
        assert agent.language_keys == agent.specialties
        assert agent.runtime_class in {"shared_worker", "synthesized_heartbeat"}
