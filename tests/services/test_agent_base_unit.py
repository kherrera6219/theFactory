"""Unit tests for services/orchestrator/orchestrator/agent_base.py"""
from __future__ import annotations

import inspect

import pytest
from orchestrator.agent_base import (
    AgentReport,
    AgentResult,
    BaseAgent,
    CAgent,
    CppAgent,
    CSharpAgent,
    ExecutiveAgent,
    GoAgent,
    HaskellAgent,
    InterfaceAgent,
    JavaAgent,
    JavaScriptAgent,
    JuliaAgent,
    KotlinAgent,
    MathematicaAgent,
    MatlabAgent,
    OcamlAgent,
    PhpAgent,
    PodAuditAgent,
    PodManagerAgent,
    PythonAgent,
    RAgent,
    RubyAgent,
    RustAgent,
    ScalaAgent,
    SpecialistAgent,
    SupportAgent,
    ValidationResult,
    ZigAgent,
    make_agent,
    make_specialist_for_language,
)
from orchestrator.agent_registry import AGENT_REGISTRY

# ---------------------------------------------------------------------------
# AgentResult / ValidationResult / AgentReport
# ---------------------------------------------------------------------------


class TestAgentResult:
    def test_defaults(self) -> None:
        r = AgentResult(agent_id="AGENT-01-PM", mission_id="m1", status="ok")
        assert r.agent_id == "AGENT-01-PM"
        assert r.mission_id == "m1"
        assert r.status == "ok"
        assert r.artifacts == []
        assert r.metadata == {}
        assert r.errors == []

    def test_to_dict_keys(self) -> None:
        r = AgentResult(agent_id="a", mission_id="m", status="ok", artifacts=[{"x": 1}])
        d = r.to_dict()
        assert set(d.keys()) == {
            "agent_id", "mission_id", "status", "artifacts", "metadata", "errors"
        }
        assert d["artifacts"] == [{"x": 1}]


class TestValidationResult:
    def test_passed(self) -> None:
        v = ValidationResult(agent_id="a", mission_id="m", passed=True)
        assert v.passed is True
        assert v.findings == []
        assert v.blocking is False

    def test_failed_blocking(self) -> None:
        v = ValidationResult(
            agent_id="a", mission_id="m", passed=False, findings=["err"], blocking=True
        )
        assert v.passed is False
        assert v.findings == ["err"]
        assert v.blocking is True
        assert "blocking" in v.to_dict()


class TestAgentReport:
    def test_verdict_pass(self) -> None:
        r = AgentReport(agent_id="a", mission_id="m", summary="done")
        assert r.verdict == "PASS"
        d = r.to_dict()
        assert d["verdict"] == "PASS"
        assert d["summary"] == "done"


# ---------------------------------------------------------------------------
# BaseAgent — abstract contract
# ---------------------------------------------------------------------------


class TestBaseAgentIsAbstract:
    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            BaseAgent(AGENT_REGISTRY[0])  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# make_agent factory
# ---------------------------------------------------------------------------


class TestMakeAgentFactory:
    def test_pm_returns_interface_agent(self) -> None:
        agent = make_agent("AGENT-01-PM")
        assert isinstance(agent, InterfaceAgent)
        assert agent.agent_id == "AGENT-01-PM"

    def test_ceo_returns_executive_agent(self) -> None:
        agent = make_agent("AGENT-02-CEO")
        assert isinstance(agent, ExecutiveAgent)

    def test_broker_returns_support_agent(self) -> None:
        agent = make_agent("AGENT-03-BROKER")
        assert isinstance(agent, SupportAgent)

    def test_pod_a_mgr_returns_pod_manager_agent(self) -> None:
        agent = make_agent("AGENT-12-PODA-MGR")
        assert isinstance(agent, PodManagerAgent)

    def test_pod_a_audit_returns_pod_audit_agent(self) -> None:
        agent = make_agent("AGENT-13-PODA-AUDIT")
        assert isinstance(agent, PodAuditAgent)

    def test_python_specialist(self) -> None:
        agent = make_agent("AGENT-14-PYTHON")
        assert isinstance(agent, PythonAgent)
        assert isinstance(agent, SpecialistAgent)

    def test_rust_specialist(self) -> None:
        agent = make_agent("AGENT-22-RUST")
        assert isinstance(agent, RustAgent)

    def test_mathematica_specialist(self) -> None:
        agent = make_agent("AGENT-35-MATHEMATICA")
        assert isinstance(agent, MathematicaAgent)

    def test_go_specialist(self) -> None:
        agent = make_agent("AGENT-36-GO")
        assert isinstance(agent, GoAgent)
        assert isinstance(agent, SpecialistAgent)
        assert type(agent) is not BaseAgent

    def test_haskell_specialist(self) -> None:
        agent = make_agent("AGENT-37-HASKELL")
        assert isinstance(agent, HaskellAgent)
        assert isinstance(agent, SpecialistAgent)
        assert type(agent) is not BaseAgent

    def test_ocaml_specialist(self) -> None:
        agent = make_agent("AGENT-38-OCAML")
        assert isinstance(agent, OcamlAgent)
        assert isinstance(agent, SpecialistAgent)
        assert type(agent) is not BaseAgent

    def test_all_specialists_resolve_to_non_base_class(self) -> None:
        """Every specialist registry entry must resolve to a concrete subclass.

        Regression guard for issue #187: GO/HASKELL/OCAML silently fell back to
        the SpecialistAgent base because no concrete subclass was registered.
        """
        specialists = [d for d in AGENT_REGISTRY if d.category == "specialist"]
        assert specialists, "registry has no specialist entries"
        for definition in specialists:
            agent = make_agent(definition.agent_id)
            assert type(agent) is not BaseAgent, definition.agent_id
            assert type(agent) is not SpecialistAgent, (
                f"{definition.agent_id} fell back to the SpecialistAgent base "
                f"instead of a language-specific subclass"
            )

    def test_unknown_agent_id_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown agent_id"):
            make_agent("AGENT-99-BOGUS")

    def test_case_insensitive(self) -> None:
        agent = make_agent("agent-01-pm")
        assert isinstance(agent, InterfaceAgent)

    def test_all_41_agents_resolvable(self) -> None:
        """Every entry in AGENT_REGISTRY must resolve without error."""
        for definition in AGENT_REGISTRY:
            agent = make_agent(definition.agent_id)
            assert agent.agent_id == definition.agent_id

    def test_runtime_class_matches_factory_implementation(self) -> None:
        """Registry runtime classes must map to the documented concrete factory path."""
        synthesized_categories = {"interface", "executive", "support"}
        shared_worker_categories = {"pod_manager", "pod_audit", "specialist"}

        for definition in AGENT_REGISTRY:
            agent = make_agent(definition.agent_id)
            if definition.runtime_class == "synthesized_heartbeat":
                assert definition.category in synthesized_categories
                assert isinstance(agent, (InterfaceAgent, ExecutiveAgent, SupportAgent))
                assert not isinstance(agent, (PodManagerAgent, PodAuditAgent, SpecialistAgent))
            elif definition.runtime_class == "shared_worker":
                assert definition.category in shared_worker_categories
                assert isinstance(agent, (PodManagerAgent, PodAuditAgent, SpecialistAgent))
                assert not isinstance(agent, (InterfaceAgent, ExecutiveAgent, SupportAgent))
            else:
                pytest.fail(
                    f"{definition.agent_id} has unknown runtime_class "
                    f"{definition.runtime_class!r}"
                )

    def test_all_concrete_agent_subclasses_are_registry_reachable(self) -> None:
        """No concrete agent implementation should exist outside the registry path."""

        def all_subclasses(cls: type[BaseAgent]) -> set[type[BaseAgent]]:
            found: set[type[BaseAgent]] = set()
            for child in cls.__subclasses__():
                found.add(child)
                found.update(all_subclasses(child))
            return found

        concrete_classes = {
            cls
            for cls in all_subclasses(BaseAgent)
            if not inspect.isabstract(cls) and cls is not SpecialistAgent
        }
        reachable_classes = {type(make_agent(definition.agent_id)) for definition in AGENT_REGISTRY}

        assert concrete_classes <= reachable_classes


# ---------------------------------------------------------------------------
# make_specialist_for_language factory
# ---------------------------------------------------------------------------


class TestMakeSpecialistForLanguage:
    @pytest.mark.parametrize(
        "language,expected_cls",
        [
            ("python", PythonAgent),
            ("javascript", JavaScriptAgent),
            ("ruby", RubyAgent),
            ("php", PhpAgent),
            ("c", CAgent),
            ("cpp", CppAgent),
            ("rust", RustAgent),
            ("zig", ZigAgent),
            ("go", GoAgent),
            ("java", JavaAgent),
            ("csharp", CSharpAgent),
            ("scala", ScalaAgent),
            ("kotlin", KotlinAgent),
            ("haskell", HaskellAgent),
            ("ocaml", OcamlAgent),
            ("matlab", MatlabAgent),
            ("r", RAgent),
            ("julia", JuliaAgent),
            ("mathematica", MathematicaAgent),
        ],
    )
    def test_language_resolves(self, language: str, expected_cls: type) -> None:
        agent = make_specialist_for_language(language)
        assert agent is not None
        assert isinstance(agent, expected_cls)

    def test_unknown_language_returns_none(self) -> None:
        assert make_specialist_for_language("cobol") is None


# ---------------------------------------------------------------------------
# InterfaceAgent
# ---------------------------------------------------------------------------


class TestInterfaceAgent:
    def setup_method(self) -> None:
        self.agent = make_agent("AGENT-01-PM")

    def test_capabilities(self) -> None:
        caps = self.agent.capabilities()
        assert caps["agent_id"] == "AGENT-01-PM"
        assert caps["category"] == "interface"

    def test_execute_returns_result(self) -> None:
        result = self.agent.execute("m1", {"prompt": "build a service"})
        assert isinstance(result, AgentResult)
        assert result.status == "ok"
        assert len(result.artifacts) == 1
        assert result.artifacts[0]["type"] == "intake_contract"

    def test_validate_passes_with_mission_id(self) -> None:
        result = self.agent.execute("m1", {})
        validation = self.agent.validate("m1", result.artifacts)
        assert isinstance(validation, ValidationResult)
        assert validation.passed is True

    def test_report_pass(self) -> None:
        result = self.agent.execute("m1", {})
        validation = self.agent.validate("m1", result.artifacts)
        report = self.agent.report("m1", result, validation)
        assert isinstance(report, AgentReport)
        assert report.verdict == "PASS"


# ---------------------------------------------------------------------------
# ExecutiveAgent
# ---------------------------------------------------------------------------


class TestExecutiveAgent:
    def setup_method(self) -> None:
        self.agent = make_agent("AGENT-02-CEO")

    def test_execute_with_delegation(self) -> None:
        result = self.agent.execute(
            "m1",
            {
                "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                "specialist_agent_id": "AGENT-14-PYTHON",
                "rationale": "Python target.",
            },
        )
        assert result.status == "ok"
        plan = result.artifacts[0]
        assert plan["type"] == "delegation_plan"
        assert plan["pod_manager_agent_id"] == "AGENT-12-PODA-MGR"

    def test_validate_fails_without_pod_manager(self) -> None:
        result = self.agent.execute("m1", {})
        # Force empty pod_manager_agent_id
        result.artifacts[0]["pod_manager_agent_id"] = ""
        validation = self.agent.validate("m1", result.artifacts)
        assert validation.passed is False
        assert validation.blocking is True

    def test_report_fail_produces_fail_verdict(self) -> None:
        result = self.agent.execute("m1", {})
        result.artifacts[0]["pod_manager_agent_id"] = ""
        validation = self.agent.validate("m1", result.artifacts)
        report = self.agent.report("m1", result, validation)
        assert report.verdict == "FAIL"


# ---------------------------------------------------------------------------
# PodManagerAgent
# ---------------------------------------------------------------------------


class TestPodManagerAgent:
    def setup_method(self) -> None:
        self.agent = make_agent("AGENT-12-PODA-MGR")

    def test_execute_produces_fusion_plan(self) -> None:
        result = self.agent.execute(
            "m1",
            {"specialist_agent_id": "AGENT-14-PYTHON", "requested_target_language": "python"},
        )
        assert result.status == "ok"
        assert result.artifacts[0]["type"] == "pod_fusion_plan"
        assert result.artifacts[0]["pod"] == "Pod A"

    def test_validate_fails_without_specialist(self) -> None:
        result = self.agent.execute("m1", {})
        validation = self.agent.validate("m1", result.artifacts)
        assert validation.passed is False


# ---------------------------------------------------------------------------
# PodAuditAgent
# ---------------------------------------------------------------------------


class TestPodAuditAgent:
    def setup_method(self) -> None:
        self.agent = make_agent("AGENT-13-PODA-AUDIT")

    def test_execute_pass_with_valid_logicnodes(self) -> None:
        result = self.agent.execute(
            "m1",
            {
                "logicnodes": [
                    {"node_id": "n1", "concept": "loop"},
                    {"node_id": "n2", "concept": "io"},
                ]
            },
        )
        assert result.status == "ok"
        assert result.artifacts[0]["verdict"] == "PASS"

    def test_execute_fail_with_missing_node_id(self) -> None:
        result = self.agent.execute("m1", {"logicnodes": [{"concept": "loop"}]})
        assert result.status == "failed"
        assert result.artifacts[0]["verdict"] == "FAIL"

    def test_validate_and_report_round_trip(self) -> None:
        result = self.agent.execute(
            "m1", {"logicnodes": [{"node_id": "n1", "concept": "loop"}]}
        )
        validation = self.agent.validate("m1", result.artifacts)
        report = self.agent.report("m1", result, validation)
        assert report.verdict == "PASS"
        assert "1 LogicNodes" in report.summary


# ---------------------------------------------------------------------------
# SpecialistAgent (Python)
# ---------------------------------------------------------------------------


class TestPythonAgent:
    def setup_method(self) -> None:
        self.agent = make_agent("AGENT-14-PYTHON")

    def test_language_key(self) -> None:
        assert isinstance(self.agent, PythonAgent)
        assert self.agent.language_key == "python"  # type: ignore[attr-defined]

    def test_execute_with_source(self) -> None:
        result = self.agent.execute(
            "m1", {"source_payload": "def foo(): pass", "requested_target_language": "python"}
        )
        assert result.status == "ok"
        assert result.artifacts[0]["type"] == "logicnode_set"
        assert result.artifacts[0]["logicnode_count"] > 0
        assert result.artifacts[0]["logicnodes"][0]["concept"] == "foo"
        assert result.artifacts[0]["logicnodes"][0]["domain"] == "function"

    def test_execute_no_source_produces_empty(self) -> None:
        result = self.agent.execute("m1", {})
        assert result.artifacts[0]["logicnode_count"] == 0

    def test_validate_fails_on_empty_logicnodes(self) -> None:
        result = self.agent.execute("m1", {})
        validation = self.agent.validate("m1", result.artifacts)
        assert validation.passed is False
        assert any("No LogicNodes" in f for f in validation.findings)

    def test_validate_passes_with_logicnodes(self) -> None:
        result = self.agent.execute("m1", {"source_payload": "x = 1"})
        validation = self.agent.validate("m1", result.artifacts)
        assert validation.passed is True

    def test_report_includes_language(self) -> None:
        result = self.agent.execute("m1", {"source_payload": "x = 1"})
        validation = self.agent.validate("m1", result.artifacts)
        report = self.agent.report("m1", result, validation)
        assert "PYTHON" in report.summary.upper() or "python" in report.summary.lower()


# ---------------------------------------------------------------------------
# All 16 specialist language keys
# ---------------------------------------------------------------------------


ALL_SPECIALIST_LANGUAGES = [
    "python", "javascript", "ruby", "php",
    "c", "cpp", "rust", "zig", "go",
    "java", "csharp", "scala", "kotlin", "haskell", "ocaml",
    "matlab", "r", "julia", "mathematica",
]


class TestAllSpecialistLanguages:
    @pytest.mark.parametrize("language", ALL_SPECIALIST_LANGUAGES)
    def test_specialist_execute_validate_report(self, language: str) -> None:
        agent = make_specialist_for_language(language)
        assert agent is not None, f"No specialist for {language}"
        result = agent.execute(
            "m1", {"source_payload": "dummy", "requested_target_language": language}
        )
        assert isinstance(result, AgentResult)
        validation = agent.validate("m1", result.artifacts)
        assert isinstance(validation, ValidationResult)
        report = agent.report("m1", result, validation)
        assert isinstance(report, AgentReport)
        assert report.verdict in {"PASS", "FAIL", "PARTIAL"}

    @pytest.mark.parametrize("language", ALL_SPECIALIST_LANGUAGES)
    def test_specialist_has_extraction_guidance(self, language: str) -> None:
        agent = make_specialist_for_language(language)
        assert agent is not None
        # extraction_guidance must be a non-empty string
        guidance = getattr(agent, "extraction_guidance", "")
        assert isinstance(guidance, str) and len(guidance) > 0


# ---------------------------------------------------------------------------
# Go / Haskell / OCaml specialists (issue #187)
# ---------------------------------------------------------------------------


class TestGoHaskellOcamlSpecialists:
    @pytest.mark.parametrize(
        "agent_id,expected_cls,language_key",
        [
            ("AGENT-36-GO", GoAgent, "go"),
            ("AGENT-37-HASKELL", HaskellAgent, "haskell"),
            ("AGENT-38-OCAML", OcamlAgent, "ocaml"),
        ],
    )
    def test_factory_returns_concrete_class(
        self, agent_id: str, expected_cls: type, language_key: str
    ) -> None:
        agent = make_agent(agent_id)
        assert type(agent) is expected_cls
        assert type(agent) is not BaseAgent
        assert type(agent) is not SpecialistAgent
        assert agent.language_key == language_key  # type: ignore[attr-defined]
        assert agent.extraction_guidance  # type: ignore[attr-defined]

    @pytest.mark.parametrize(
        "agent_id,language_key",
        [
            ("AGENT-36-GO", "go"),
            ("AGENT-37-HASKELL", "haskell"),
            ("AGENT-38-OCAML", "ocaml"),
        ],
    )
    def test_execute_returns_valid_agent_result(
        self, agent_id: str, language_key: str
    ) -> None:
        agent = make_agent(agent_id)
        result = agent.execute(
            "m1",
            {"source_payload": "func main() {}", "requested_target_language": language_key},
        )
        assert isinstance(result, AgentResult)
        assert result.status == "ok"
        assert result.artifacts[0]["type"] == "logicnode_set"
        assert result.artifacts[0]["language"] == language_key
        validation = agent.validate("m1", result.artifacts)
        assert isinstance(validation, ValidationResult)
        report = agent.report("m1", result, validation)
        assert isinstance(report, AgentReport)
        assert report.verdict in {"PASS", "FAIL", "PARTIAL"}

    @pytest.mark.parametrize(
        "agent_id,label",
        [
            ("AGENT-36-GO", "Go"),
            ("AGENT-37-HASKELL", "Haskell"),
            ("AGENT-38-OCAML", "OCaml"),
        ],
    )
    def test_system_prompt_contains_language_and_tooling(
        self, agent_id: str, label: str
    ) -> None:
        from orchestrator.agent_personas import (
            LANGUAGE_PERSONAS,
            build_agent_system_prompt,
            get_language_label,
            get_language_tooling,
        )

        definition = next(d for d in AGENT_REGISTRY if d.agent_id == agent_id)
        language_key = definition.specialties[0]
        # Language label and tooling must be registered (not generic fallbacks).
        assert get_language_label(language_key) == label
        assert language_key in LANGUAGE_PERSONAS
        prompt = build_agent_system_prompt(definition)
        assert label in prompt
        assert get_language_tooling(language_key) in prompt


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------


class TestRepr:
    def test_repr_includes_agent_id(self) -> None:
        agent = make_agent("AGENT-22-RUST")
        r = repr(agent)
        assert "AGENT-22-RUST" in r
        assert "RustAgent" in r
