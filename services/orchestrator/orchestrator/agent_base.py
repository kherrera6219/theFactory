"""
agent_base.py — Executable agent class hierarchy for theFactory.

Provides the BaseAgent abstract class with execute(), validate(), and report()
lifecycle methods, and a set of typed subclasses for each agent category:

  BaseAgent
  ├── InterfaceAgent        (PM)
  ├── ExecutiveAgent        (CEO)
  ├── SupportAgent          (BROKER, ACCOUNTANT, SECURITY, IS, VC, COMPLIANCE,
  │                          HW, TESTER, DEPLOY, DEPABS, TESTDATA, RQCA)
  ├── PodManagerAgent       (PODA-MGR, PODB-MGR, PODC-MGR, PODD-MGR)
  ├── PodAuditAgent         (PODA-AUDIT, PODB-AUDIT, PODC-AUDIT, PODD-AUDIT)
  └── SpecialistAgent
      ├── PythonAgent
      ├── JavaScriptAgent
      ├── RubyAgent
      ├── PhpAgent
      ├── CAgent
      ├── CppAgent
      ├── RustAgent
      ├── ZigAgent
      ├── GoAgent
      ├── JavaAgent
      ├── CSharpAgent
      ├── ScalaAgent
      ├── KotlinAgent
      ├── HaskellAgent
      ├── OcamlAgent
      ├── MatlabAgent
      ├── RAgent
      ├── JuliaAgent
      └── MathematicaAgent

Each class uses its AgentDefinition as an immutable configuration record.
The factory function `make_agent()` resolves the correct class given an agent_id.
"""
from __future__ import annotations

import abc
import logging
import re
from typing import Any

from .agent_registry import AGENT_REGISTRY, AgentDefinition

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class AgentResult:
    """Structured result returned by BaseAgent.execute()."""

    __slots__ = ("agent_id", "mission_id", "status", "artifacts", "metadata", "errors")

    def __init__(
        self,
        *,
        agent_id: str,
        mission_id: str,
        status: str,
        artifacts: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        errors: list[str] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.mission_id = mission_id
        self.status = status  # "ok" | "partial" | "failed"
        self.artifacts: list[dict[str, Any]] = artifacts or []
        self.metadata: dict[str, Any] = metadata or {}
        self.errors: list[str] = errors or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "mission_id": self.mission_id,
            "status": self.status,
            "artifacts": self.artifacts,
            "metadata": self.metadata,
            "errors": self.errors,
        }


class ValidationResult:
    """Structured result returned by BaseAgent.validate()."""

    __slots__ = ("agent_id", "mission_id", "passed", "findings", "blocking")

    def __init__(
        self,
        *,
        agent_id: str,
        mission_id: str,
        passed: bool,
        findings: list[str] | None = None,
        blocking: bool = False,
    ) -> None:
        self.agent_id = agent_id
        self.mission_id = mission_id
        self.passed = passed
        self.findings: list[str] = findings or []
        self.blocking = blocking

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "mission_id": self.mission_id,
            "passed": self.passed,
            "findings": self.findings,
            "blocking": self.blocking,
        }


class AgentReport:
    """Structured report returned by BaseAgent.report()."""

    __slots__ = ("agent_id", "mission_id", "summary", "evidence", "verdict")

    def __init__(
        self,
        *,
        agent_id: str,
        mission_id: str,
        summary: str,
        evidence: list[dict[str, Any]] | None = None,
        verdict: str = "PASS",
    ) -> None:
        self.agent_id = agent_id
        self.mission_id = mission_id
        self.summary = summary
        self.evidence: list[dict[str, Any]] = evidence or []
        self.verdict = verdict  # "PASS" | "FAIL" | "PARTIAL"

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "mission_id": self.mission_id,
            "summary": self.summary,
            "evidence": self.evidence,
            "verdict": self.verdict,
        }


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class BaseAgent(abc.ABC):
    """
    Abstract base class for all 41 theFactory agents.

    Subclasses must implement execute(), validate(), and report(). The
    definition property exposes the immutable AgentDefinition config record.
    """

    def __init__(self, definition: AgentDefinition) -> None:
        self._definition = definition
        self._logger = logging.getLogger(f"{__name__}.{definition.agent_id}")

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def definition(self) -> AgentDefinition:
        """Immutable configuration record for this agent."""
        return self._definition

    @property
    def agent_id(self) -> str:
        return self._definition.agent_id

    @property
    def category(self) -> str:
        return self._definition.category

    @property
    def pod(self) -> str:
        return self._definition.pod

    @property
    def tier(self) -> str:
        return self._definition.tier

    # ------------------------------------------------------------------
    # Capability self-registration
    # ------------------------------------------------------------------

    def capabilities(self) -> dict[str, Any]:
        """Return a dict describing this agent's capabilities for registry queries."""
        return {
            "agent_id": self.agent_id,
            "category": self.category,
            "pod": self.pod,
            "tier": self.tier,
            "specialties": list(self._definition.specialties),
            "role": self._definition.role,
        }

    # ------------------------------------------------------------------
    # Lifecycle methods (must override)
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def execute(
        self,
        mission_id: str,
        payload: dict[str, Any],
    ) -> AgentResult:
        """
        Execute the agent's primary mission task.

        Args:
            mission_id: Unique mission identifier.
            payload: Mission-specific input payload.

        Returns:
            AgentResult with status, artifacts, and metadata.
        """

    @abc.abstractmethod
    def validate(
        self,
        mission_id: str,
        artifacts: list[dict[str, Any]],
    ) -> ValidationResult:
        """
        Validate artifacts produced for this mission.

        Args:
            mission_id: Unique mission identifier.
            artifacts: List of artifact dicts to validate.

        Returns:
            ValidationResult with pass/fail and findings.
        """

    @abc.abstractmethod
    def report(
        self,
        mission_id: str,
        result: AgentResult,
        validation: ValidationResult,
    ) -> AgentReport:
        """
        Produce the final audit-ready report for this agent's contribution.

        Args:
            mission_id: Unique mission identifier.
            result: The AgentResult from execute().
            validation: The ValidationResult from validate().

        Returns:
            AgentReport with summary, evidence, and verdict.
        """

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _make_result(
        self,
        mission_id: str,
        *,
        status: str = "ok",
        artifacts: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        errors: list[str] | None = None,
    ) -> AgentResult:
        return AgentResult(
            agent_id=self.agent_id,
            mission_id=mission_id,
            status=status,
            artifacts=artifacts,
            metadata=metadata,
            errors=errors,
        )

    def _make_validation(
        self,
        mission_id: str,
        *,
        passed: bool,
        findings: list[str] | None = None,
        blocking: bool = False,
    ) -> ValidationResult:
        return ValidationResult(
            agent_id=self.agent_id,
            mission_id=mission_id,
            passed=passed,
            findings=findings,
            blocking=blocking,
        )

    def _make_report(
        self,
        mission_id: str,
        *,
        summary: str,
        evidence: list[dict[str, Any]] | None = None,
        verdict: str = "PASS",
    ) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            mission_id=mission_id,
            summary=summary,
            evidence=evidence,
            verdict=verdict,
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(agent_id={self.agent_id!r})"


# ---------------------------------------------------------------------------
# Category subclasses
# ---------------------------------------------------------------------------


class InterfaceAgent(BaseAgent):
    """PM Agent — mission intake, user intent translation, and delivery validation."""

    def execute(self, mission_id: str, payload: dict[str, Any]) -> AgentResult:
        self._logger.info("InterfaceAgent.execute mission=%s", mission_id)
        artifacts = [{"type": "intake_contract", "mission_id": mission_id, "payload": payload}]
        return self._make_result(mission_id, artifacts=artifacts)

    def validate(self, mission_id: str, artifacts: list[dict[str, Any]]) -> ValidationResult:
        findings = []
        passed = True
        for artifact in artifacts:
            if not artifact.get("mission_id"):
                findings.append("artifact missing mission_id")
                passed = False
        return self._make_validation(mission_id, passed=passed, findings=findings)

    def report(
        self, mission_id: str, result: AgentResult, validation: ValidationResult
    ) -> AgentReport:
        verdict = "PASS" if validation.passed else "FAIL"
        count = len(result.artifacts)
        return self._make_report(
            mission_id,
            summary=f"PM intake translated {count} artifacts. Validation: {verdict}.",
            evidence=[result.to_dict(), validation.to_dict()],
            verdict=verdict,
        )


class ExecutiveAgent(BaseAgent):
    """CEO Agent — cross-pod orchestration, global state, and delegation planning."""

    def execute(self, mission_id: str, payload: dict[str, Any]) -> AgentResult:
        self._logger.info("ExecutiveAgent.execute mission=%s", mission_id)
        delegation = {
            "type": "delegation_plan",
            "mission_id": mission_id,
            "pod_manager_agent_id": payload.get("pod_manager_agent_id", ""),
            "specialist_agent_id": payload.get("specialist_agent_id", ""),
            "rationale": payload.get("rationale", "Delegated by CEO."),
        }
        return self._make_result(mission_id, artifacts=[delegation], metadata=payload)

    def validate(self, mission_id: str, artifacts: list[dict[str, Any]]) -> ValidationResult:
        findings = []
        passed = True
        for artifact in artifacts:
            if artifact.get("type") == "delegation_plan":
                if not artifact.get("pod_manager_agent_id"):
                    findings.append("delegation_plan missing pod_manager_agent_id")
                    passed = False
                if not artifact.get("specialist_agent_id"):
                    findings.append("delegation_plan missing specialist_agent_id")
                    passed = False
        return self._make_validation(
            mission_id, passed=passed, findings=findings, blocking=not passed
        )

    def report(
        self, mission_id: str, result: AgentResult, validation: ValidationResult
    ) -> AgentReport:
        verdict = "PASS" if validation.passed else "FAIL"
        return self._make_report(
            mission_id,
            summary=(
                "CEO delegation plan produced. Pod/specialist routing "
                f"{'confirmed' if validation.passed else 'incomplete'}."
            ),
            evidence=[result.to_dict(), validation.to_dict()],
            verdict=verdict,
        )


class SupportAgent(BaseAgent):
    """Support ring agents.

    Covers: BROKER, ACCOUNTANT, SECURITY, IS, VC, COMPLIANCE, HW, TESTER, DEPLOY,
    DEPABS, TESTDATA, RQCA.
    """

    def execute(self, mission_id: str, payload: dict[str, Any]) -> AgentResult:
        self._logger.info("SupportAgent[%s].execute mission=%s", self.agent_id, mission_id)
        action = {"type": "support_action", "agent_id": self.agent_id, "mission_id": mission_id}
        return self._make_result(
            mission_id,
            artifacts=[action],
            metadata={"role": self._definition.role},
        )

    def validate(self, mission_id: str, artifacts: list[dict[str, Any]]) -> ValidationResult:
        findings = []
        for artifact in artifacts:
            if not artifact.get("agent_id"):
                findings.append("support artifact missing agent_id")
        return self._make_validation(mission_id, passed=not findings, findings=findings)

    def report(
        self, mission_id: str, result: AgentResult, validation: ValidationResult
    ) -> AgentReport:
        verdict = "PASS" if validation.passed else "FAIL"
        code = self._definition.short_code
        return self._make_report(
            mission_id,
            summary=f"{code} completed support action. Status: {result.status}.",
            evidence=[result.to_dict(), validation.to_dict()],
            verdict=verdict,
        )


class PodManagerAgent(BaseAgent):
    """Pod sub-manager agents — coordinate specialist extraction and pod output fusion."""

    def execute(self, mission_id: str, payload: dict[str, Any]) -> AgentResult:
        self._logger.info("PodManagerAgent[%s].execute mission=%s", self.agent_id, mission_id)
        fusion_plan = {
            "type": "pod_fusion_plan",
            "pod": self.pod,
            "mission_id": mission_id,
            "specialist_agent_id": payload.get("specialist_agent_id", ""),
            "source_language": payload.get("requested_target_language", ""),
        }
        return self._make_result(mission_id, artifacts=[fusion_plan], metadata=payload)

    def validate(self, mission_id: str, artifacts: list[dict[str, Any]]) -> ValidationResult:
        findings = []
        passed = True
        for artifact in artifacts:
            if artifact.get("type") == "pod_fusion_plan":
                if not artifact.get("specialist_agent_id"):
                    findings.append("pod_fusion_plan missing specialist_agent_id")
                    passed = False
        return self._make_validation(mission_id, passed=passed, findings=findings)

    def report(
        self, mission_id: str, result: AgentResult, validation: ValidationResult
    ) -> AgentReport:
        verdict = "PASS" if validation.passed else "FAIL"
        return self._make_report(
            mission_id,
            summary=f"{self.pod} fusion plan produced by {self.agent_id}. Routing: {verdict}.",
            evidence=[result.to_dict(), validation.to_dict()],
            verdict=verdict,
        )


class PodAuditAgent(BaseAgent):
    """Pod QC/Audit agents — verify pod-level LogicNode artifacts before release."""

    def execute(self, mission_id: str, payload: dict[str, Any]) -> AgentResult:
        self._logger.info("PodAuditAgent[%s].execute mission=%s", self.agent_id, mission_id)
        logicnodes: list[Any] = payload.get("logicnodes", [])
        audit_findings: list[str] = []
        for node in logicnodes:
            if not isinstance(node, dict) or not node.get("node_id"):
                audit_findings.append("logicnode missing node_id")
        verdict_artifact = {
            "type": "pod_audit_verdict",
            "pod": self.pod,
            "mission_id": mission_id,
            "logicnode_count": len(logicnodes),
            "findings": audit_findings,
            "verdict": "FAIL" if audit_findings else "PASS",
        }
        status = "failed" if audit_findings else "ok"
        return self._make_result(mission_id, status=status, artifacts=[verdict_artifact])

    def validate(self, mission_id: str, artifacts: list[dict[str, Any]]) -> ValidationResult:
        findings = []
        passed = True
        for artifact in artifacts:
            if artifact.get("type") == "pod_audit_verdict":
                if artifact.get("verdict") == "FAIL":
                    findings.extend(artifact.get("findings", []))
                    passed = False
        return self._make_validation(
            mission_id, passed=passed, findings=findings, blocking=not passed
        )

    def report(
        self, mission_id: str, result: AgentResult, validation: ValidationResult
    ) -> AgentReport:
        verdict = "PASS" if validation.passed else "FAIL"
        logicnode_count = 0
        for artifact in result.artifacts:
            if artifact.get("type") == "pod_audit_verdict":
                logicnode_count = artifact.get("logicnode_count", 0)
        return self._make_report(
            mission_id,
            summary=(
                f"{self.pod} audit complete. {logicnode_count} LogicNodes reviewed. "
                f"Verdict: {verdict}."
            ),
            evidence=[result.to_dict(), validation.to_dict()],
            verdict=verdict,
        )


# ---------------------------------------------------------------------------
# Specialist base class
# ---------------------------------------------------------------------------


class SpecialistAgent(BaseAgent):
    """
    Language-specialist agents — extract computational intent into Refined-IR structures.

    Subclasses override language_key and extraction_guidance to provide
    language-specific behaviour. The core execute/validate/report contract
    is defined here and handles the LogicNode artifact lifecycle.
    """

    #: Override in subclasses to match the language key in agent_registry specialties.
    language_key: str = ""

    #: Override to add language-specific extraction notes to reports.
    extraction_guidance: str = "Language-specific intent extraction."

    def execute(self, mission_id: str, payload: dict[str, Any]) -> AgentResult:
        self._logger.info(
            "SpecialistAgent[%s/%s].execute mission=%s",
            self.agent_id,
            self.language_key,
            mission_id,
        )
        source_payload = payload.get("source_payload", "")
        language = payload.get("requested_target_language", self.language_key)
        prebuilt_logicnodes = payload.get("logicnodes")

        if isinstance(prebuilt_logicnodes, list):
            logicnodes = [node for node in prebuilt_logicnodes if isinstance(node, dict)]
        else:
            logicnodes = self._extract_logicnodes(mission_id, source_payload, language)

        artifacts = [
            {
                "type": "logicnode_set",
                "agent_id": self.agent_id,
                "mission_id": mission_id,
                "language": language,
                "logicnode_count": len(logicnodes),
                "logicnodes": logicnodes,
                "guidance": self.extraction_guidance,
            }
        ]
        return self._make_result(
            mission_id,
            artifacts=artifacts,
            metadata={
                "language": language,
                "language_key": self.language_key,
                "pod": self.pod,
            },
        )

    def validate(self, mission_id: str, artifacts: list[dict[str, Any]]) -> ValidationResult:
        findings: list[str] = []
        passed = True
        for artifact in artifacts:
            if artifact.get("type") != "logicnode_set":
                continue
            if artifact.get("logicnode_count", 0) == 0:
                findings.append(
                    f"No LogicNodes extracted for language {artifact.get('language', 'unknown')}"
                )
                passed = False
            for node in artifact.get("logicnodes", []):
                if not isinstance(node, dict):
                    findings.append("logicnode is not a dict")
                    passed = False
                    continue
                if not node.get("node_id"):
                    findings.append("logicnode missing node_id")
                    passed = False
                if not node.get("concept"):
                    findings.append("logicnode missing concept field")
                    passed = False
        return self._make_validation(mission_id, passed=passed, findings=findings)

    def report(
        self, mission_id: str, result: AgentResult, validation: ValidationResult
    ) -> AgentReport:
        verdict = "PASS" if validation.passed else "FAIL"
        logicnode_count = sum(
            a.get("logicnode_count", 0)
            for a in result.artifacts
            if a.get("type") == "logicnode_set"
        )
        return self._make_report(
            mission_id,
            summary=(
                f"{self.agent_id} extracted {logicnode_count} LogicNodes "
                f"({self.language_key.upper() or 'general'}). "
                f"Validation: {verdict}. {self.extraction_guidance}"
            ),
            evidence=[result.to_dict(), validation.to_dict()],
            verdict=verdict,
        )

    # ------------------------------------------------------------------
    # Internal extraction hook
    # ------------------------------------------------------------------

    def _extract_logicnodes(
        self, mission_id: str, source_payload: Any, language: str
    ) -> list[dict[str, Any]]:
        """
        Produce source-reflective LogicNodes from payload.

        Subclasses may override for language-specific extraction.
        The pod-worker's language_extractor handles the full pipeline;
        this method is the class-level integration point for direct invocation.
        """
        source = str(source_payload or "")
        if not source.strip():
            return []
        patterns = (
            ("function", re.compile(r"\b(?:def|function|fn|func)\s+([A-Za-z_][\w]*)")),
            ("class", re.compile(r"\b(?:class|struct|enum|interface)\s+([A-Za-z_][\w]*)")),
            (
                "module_dependency",
                re.compile(r"\b(?:import|from|using|require)\s+([A-Za-z_][\w.]*)"),
            ),
        )
        logicnodes: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for domain, pattern in patterns:
            for match in pattern.finditer(source):
                concept = str(match.group(1)).strip()
                key = (domain, concept.lower())
                if not concept or key in seen:
                    continue
                seen.add(key)
                node_id = f"{mission_id}:{self.language_key or language}:{len(logicnodes)}"
                logicnodes.append(
                    {
                        "node_id": node_id,
                        "domain": domain,
                        "concept": concept,
                        "intent": f"Preserve {domain} behavior for {concept}.",
                        "language": language,
                        "source": "specialist_agent",
                        "agent_id": self.agent_id,
                    }
                )
                if len(logicnodes) >= 20:
                    return logicnodes
        if logicnodes:
            return logicnodes
        return [
            {
                "node_id": f"{mission_id}:{self.language_key or language}:0",
                "domain": "source_behavior",
                "concept": "source_payload",
                "intent": "Preserve behavior described by the provided source payload.",
                "language": language,
                "source": "specialist_agent",
                "agent_id": self.agent_id,
            }
        ]


# ---------------------------------------------------------------------------
# Per-language specialist concrete classes (19 languages, 4 pods)
# ---------------------------------------------------------------------------

# Pod A — Dynamic languages


class PythonAgent(SpecialistAgent):
    language_key = "python"
    extraction_guidance = "PEP 8 style, typing discipline, and packaging standards."


class JavaScriptAgent(SpecialistAgent):
    language_key = "javascript"
    extraction_guidance = "ECMAScript and TypeScript typing with async runtime safety."


class RubyAgent(SpecialistAgent):
    language_key = "ruby"
    extraction_guidance = "Ruby object model, conventions, and maintainable Rails patterns."


class PhpAgent(SpecialistAgent):
    language_key = "php"
    extraction_guidance = "Modern PHP standards and framework-safe backend conventions."


# Pod B — Systems languages


class CAgent(SpecialistAgent):
    language_key = "c"
    extraction_guidance = "Deterministic memory handling and low-level systems discipline."


class CppAgent(SpecialistAgent):
    language_key = "cpp"
    extraction_guidance = "RAII, template hygiene, and safe high-performance abstractions."


class RustAgent(SpecialistAgent):
    language_key = "rust"
    extraction_guidance = "Ownership model correctness with explicit lifetime safety."


class ZigAgent(SpecialistAgent):
    language_key = "zig"
    extraction_guidance = "Explicit allocation and predictable compile-time behavior."


class GoAgent(SpecialistAgent):
    language_key = "go"
    extraction_guidance = "Goroutine/channel concurrency safety and idiomatic Go simplicity."


# Pod C — Enterprise languages


class JavaAgent(SpecialistAgent):
    language_key = "java"
    extraction_guidance = "JVM architecture patterns and enterprise reliability design."


class CSharpAgent(SpecialistAgent):
    language_key = "csharp"
    extraction_guidance = ".NET architecture, async correctness, and API consistency."


class ScalaAgent(SpecialistAgent):
    language_key = "scala"
    extraction_guidance = "Functional-object hybrid patterns and type-level correctness."


class KotlinAgent(SpecialistAgent):
    language_key = "kotlin"
    extraction_guidance = "Null safety and coroutine-driven concurrency design."


class HaskellAgent(SpecialistAgent):
    language_key = "haskell"
    extraction_guidance = "Purely functional correctness, lazy evaluation, and type-class rigor."


class OcamlAgent(SpecialistAgent):
    language_key = "ocaml"
    extraction_guidance = "Strong static inference and module-system-driven reliability."


# Pod D — Mathematical & Functional languages


class MatlabAgent(SpecialistAgent):
    language_key = "matlab"
    extraction_guidance = "Numerical method stability and matrix-oriented workflows."


class RAgent(SpecialistAgent):
    language_key = "r"
    extraction_guidance = "Statistical reproducibility and analytical model integrity."


class JuliaAgent(SpecialistAgent):
    language_key = "julia"
    extraction_guidance = "High-performance numerical kernels and multiple dispatch design."


class MathematicaAgent(SpecialistAgent):
    language_key = "mathematica"
    extraction_guidance = "Symbolic computation correctness and formal expression handling."


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

_SPECIALIST_BY_LANGUAGE: dict[str, type[SpecialistAgent]] = {
    "python": PythonAgent,
    "javascript": JavaScriptAgent,
    "ruby": RubyAgent,
    "php": PhpAgent,
    "c": CAgent,
    "cpp": CppAgent,
    "rust": RustAgent,
    "zig": ZigAgent,
    "go": GoAgent,
    "java": JavaAgent,
    "csharp": CSharpAgent,
    "scala": ScalaAgent,
    "kotlin": KotlinAgent,
    "haskell": HaskellAgent,
    "ocaml": OcamlAgent,
    "matlab": MatlabAgent,
    "r": RAgent,
    "julia": JuliaAgent,
    "mathematica": MathematicaAgent,
}

_CATEGORY_CLASS: dict[str, type[BaseAgent]] = {
    "interface": InterfaceAgent,
    "executive": ExecutiveAgent,
    "support": SupportAgent,
    "pod_manager": PodManagerAgent,
    "pod_audit": PodAuditAgent,
    "specialist": SpecialistAgent,  # fallback; overridden by _SPECIALIST_BY_LANGUAGE
}

_AGENT_ID_TO_DEFINITION: dict[str, AgentDefinition] = {
    agent.agent_id: agent for agent in AGENT_REGISTRY
}


def make_agent(agent_id: str) -> BaseAgent:
    """
    Factory: resolve and instantiate the correct BaseAgent subclass for a given agent_id.

    For specialist agents, resolves the language-specific subclass.
    For all other categories, resolves by category.

    Raises:
        ValueError: if agent_id is not found in the registry.
    """
    definition = _AGENT_ID_TO_DEFINITION.get(agent_id.strip().upper())
    if definition is None:
        raise ValueError(f"Unknown agent_id: {agent_id!r}")

    if definition.category == "specialist" and definition.specialties:
        language = definition.specialties[0]
        cls = _SPECIALIST_BY_LANGUAGE.get(language, SpecialistAgent)
    else:
        cls = _CATEGORY_CLASS.get(definition.category, BaseAgent)  # type: ignore[assignment]

    return cls(definition)


def make_specialist_for_language(language: str) -> SpecialistAgent | None:
    """
    Factory: return the correct SpecialistAgent subclass for a language key.

    Returns None if no specialist is registered for the given language.
    """
    # Find a matching AgentDefinition in the registry
    for definition in AGENT_REGISTRY:
        if definition.category == "specialist" and language in definition.specialties:
            cls = _SPECIALIST_BY_LANGUAGE.get(language, SpecialistAgent)
            return cls(definition)
    return None
