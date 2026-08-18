from __future__ import annotations

import importlib
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from ..mission_flow import CEO_AGENT_ID
from .fallbacks import (
    _fallback_compliance_assessment,
    _fallback_integration_tests,
    _fallback_pod_audit_verdict,
    _fallback_security_analysis,
    _fallback_vc_commit_strategy,
)
from .providers import _call_with_agent_system
from .text import (
    _clean_text,
    _string_list,
)

LOGGER = logging.getLogger(__name__)

# Upper bound on the number of unified LogicNodes the Grand Fusion keeps. The
# previous hard-coded ``[:20]``/``[:10]`` slices silently dropped real nodes;
# this cap is generous and configurable so large missions are not truncated.
MAX_FUSION_NODES = int(os.getenv("MAX_FUSION_NODES", "500"))


def _pkg() -> Any:
    """Return the public ``llm_delegation`` package module.

    Recommendation helpers are resolved through this accessor so that tests
    which ``monkeypatch.setattr`` them on the package namespace still affect
    these call sites after the monolith was split into this package (#186).
    """
    return importlib.import_module(__package__)


_POD_AUDIT_AGENTS: dict[str, str] = {
    "podA": "AGENT-13-PODA-AUDIT",
    "podB": "AGENT-19-PODB-AUDIT",
    "podC": "AGENT-25-PODC-AUDIT",
    "podD": "AGENT-31-PODD-AUDIT",
}
# Case-insensitive lookup: _POD_AUDIT_AGENTS keys are mixed-case ("podA"), so a
# naive .lower() on the caller's pod_name before lookup would never match and
# silently fall back to the default for every pod except A. Match case-
# insensitively instead, keeping the mixed-case values as the canonical agent ids.
_POD_AUDIT_AGENTS_BY_LOWER: dict[str, str] = {
    key.lower(): value for key, value in _POD_AUDIT_AGENTS.items()
}
_DEFAULT_AUDIT_AGENT = "AGENT-13-PODA-AUDIT"

def build_deploy_readiness_assessment(
    *,
    mission_id: str,
    metadata: dict[str, Any],
    build_artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the Deploy Agent's deterministic packaging-readiness fallback."""
    artifacts = build_artifacts if isinstance(build_artifacts, list) else []
    has_packaged_artifact = any(
        isinstance(artifact, dict)
        and str(artifact.get("artifact_type") or artifact.get("type") or "").lower()
        in {"generated_code", "source_bundle_package"}
        for artifact in artifacts
    ) or bool(
        isinstance(metadata.get("mission_artifacts"), dict)
        and metadata["mission_artifacts"].get("build_packaged")
    )
    checks = [
        {
            "name": "packaged_artifact",
            "passed": has_packaged_artifact,
            "summary": "Mission has a generated-code or source-bundle build artifact.",
        },
        {
            "name": "completion_evidence",
            "passed": bool(metadata.get("delivery_summary") or metadata.get("generated_output")),
            "summary": "Mission contains completion evidence for operator review.",
        },
        {
            "name": "pod_standard",
            "passed": bool(metadata.get("pod_group_standards")),
            "summary": "Mission contains a pod group standard for traceability.",
        },
    ]
    blockers = [check["name"] for check in checks if not check["passed"]]
    return {
        "schema_version": "deploy_readiness.v1",
        "mission_id": _clean_text(mission_id, max_length=96),
        "agent_id": "AGENT-11-DEPLOY",
        "ready": not blockers,
        "blockers": blockers,
        "checks": checks,
        "source": "fallback",
        "created_at": datetime.now(UTC).isoformat(),
    }


async def generate_rqca_assessment(
    *,
    mission_id: str,
    execution_result: dict[str, Any],
    mission_contract: dict[str, Any],
    language: str,
    integration_tests: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Interpret runtime-QC execution results with deterministic fallback."""
    _ = mission_id, mission_contract, language
    verdict = str(execution_result.get("verdict") or "SKIPPED").strip().upper()
    passed = bool(execution_result.get("passed", False))
    scope_detail = str(execution_result.get("verified_scope_detail") or "").strip().lower()
    tests_source = ""
    if isinstance(integration_tests, dict):
        tests_source = str(integration_tests.get("source") or "").strip().lower()
    # Placeholder Tester fallbacks assert True / expect(true). Exit 0 is not
    # evidence — same class as started_only. A real FAIL still stands.
    if tests_source == "fallback" and verdict != "FAIL":
        return {
            "qc_verdict": "ADVISORY",
            "status": "degraded",
            "reason": (
                "Runtime QC ran Tester fallback tests (source=fallback) that "
                "cannot fail; the exit code is not evidence of correctness"
            ),
            "advisory": True,
            "confidence": "LOW",
            "execution_verdict": verdict,
            "findings": [],
            "remediation": [],
            "deployment_safe": False,
            "source": "advisory",
            "assessed_at": datetime.now(UTC).isoformat(),
        }
    # started_only / syntax_only are not a pass unless tests actually ran.
    if verdict in {"DRY_RUN", "SKIPPED"} or (
        scope_detail in {"started_only", "syntax_only"} and verdict != "FAIL"
    ):
        if scope_detail == "started_only":
            reason = (
                "Runtime QC launched the artifact with no derived invocation, "
                "so the exit code is not evidence of correctness"
            )
        elif scope_detail == "syntax_only":
            reason = (
                "Runtime QC only compiled or parsed the artifact; no tests ran, "
                "so the exit code is not evidence of correctness"
            )
        else:
            reason = (
                "Runtime QC did not fully execute the artifact "
                f"({verdict}); gate is advisory, not a pass"
            )
        return {
            "qc_verdict": "ADVISORY",
            "status": "degraded",
            "reason": reason,
            "advisory": True,
            "confidence": "LOW",
            "execution_verdict": verdict,
            "findings": [],
            "remediation": [],
            "deployment_safe": False,
            "source": "advisory",
            "assessed_at": datetime.now(UTC).isoformat(),
        }
    if passed:
        qc_verdict = "PASS"
        findings = ["Runtime execution completed with the expected exit code."]
        remediation: list[str] = []
    else:
        qc_verdict = "FAIL"
        findings = ["Runtime execution did not complete as expected."]
        remediation = ["Inspect stderr/stdout previews and repair the generated artifact."]
    return {
        "qc_verdict": qc_verdict,
        "confidence": "LOW",
        "execution_verdict": verdict,
        "findings": findings,
        "remediation": remediation,
        "deployment_safe": passed,
        "source": "fallback",
        "assessed_at": datetime.now(UTC).isoformat(),
    }


async def generate_pm_delivery_summary(
    *,
    mission_context: dict[str, Any],
    generated_output: dict[str, Any],
    build_artifacts: list[dict[str, Any]],
    feature_contract: dict[str, Any],
    mission_contract: dict[str, Any],
) -> dict[str, Any]:
    """PM Agent produces a final delivery summary for completed missions."""
    recommendation = _pkg()._agent_recommendation("AGENT-01-PM")
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.7-flash")).strip()


    primary_artifact = next(
        (
            artifact
            for artifact in build_artifacts
            if artifact.get("artifact_type") == "generated_code"
        ),
        build_artifacts[0] if build_artifacts else {},
    )
    manifest = primary_artifact.get("manifest") if isinstance(primary_artifact, dict) else {}
    if not isinstance(manifest, dict):
        manifest = {}
    artifact_text = (
        primary_artifact.get("artifact_text")
        if isinstance(primary_artifact, dict)
        else ""
    )
    code_preview = str(generated_output.get("generated_code") or artifact_text or "")[:600]
    filename = str(
        generated_output.get("filename")
        or manifest.get("filename")
        or primary_artifact.get("artifact_id")
        or "mission artifact"
    )
    language = str(
        generated_output.get("language")
        or manifest.get("language")
        or mission_context.get("requested_target_language")
        or "unknown"
    )
    criteria = (
        feature_contract.get("acceptance_criteria")
        or mission_contract.get("acceptance_criteria")
        or []
    )
    contract_summary = (
        mission_contract.get("contract_summary")
        or feature_contract.get("summary")
        or mission_context.get("prompt")
        or "Completed mission"
    )
    artifact_type = (
        primary_artifact.get("artifact_type")
        if isinstance(primary_artifact, dict)
        else None
    )

    prompt = (
        "You are AGENT-01-PM. The mission is complete. Produce a concise "
        "operator delivery summary tied to acceptance criteria and artifacts.\n"
        f"Recommended model: {provider}/{model}\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission: {_clean_text(contract_summary, max_length=300)}\n"
        f"Primary artifact: {filename} ({artifact_type or 'none'}, {language})\n"
        f"Artifact count: {len(build_artifacts)}\n"
        f"Output preview:\n{_clean_text(code_preview, max_length=600)}\n"
        f"Acceptance criteria: {json.dumps(_string_list(criteria, limit=6))}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "delivery_title": "short title for what was delivered",\n'
        '  "delivery_summary": "1-2 sentence summary for the operator",\n'
        '  "criteria_met": ["criteria that appear to be satisfied"],\n'
        '  "criteria_unmet": ["criteria that may need verification"],\n'
        '  "usage_notes": "how to use or inspect the delivered artifact",\n'
        '  "recommendations": ["optional follow-up suggestions"]\n'
        "}\n"
    )

    parsed, resolved_provider, resolved_model, _route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="pm delivery summary",
        agent_id="AGENT-01-PM",
    )
    if not isinstance(parsed, dict):
        return {
            "delivery_title": f"Delivered: {filename}",
            "delivery_summary": (
                "Mission complete. Review the delivered artifact and verify it "
                "against the acceptance criteria."
            ),
            "criteria_met": [],
            "criteria_unmet": _string_list(criteria, limit=6),
            "usage_notes": "Open the delivered artifact and verify it before release.",
            "recommendations": [],
            "primary_artifact_type": artifact_type,
            "source": "fallback",
        }

    return {
        "delivery_title": _clean_text(
            parsed.get("delivery_title") or f"Delivered: {filename}",
            max_length=120,
        ),
        "delivery_summary": _clean_text(
            parsed.get("delivery_summary") or "Mission complete.",
            max_length=500,
        ),
        "criteria_met": _string_list(parsed.get("criteria_met"), limit=6),
        "criteria_unmet": _string_list(parsed.get("criteria_unmet"), limit=6),
        "usage_notes": _clean_text(parsed.get("usage_notes", ""), max_length=300),
        "recommendations": _string_list(parsed.get("recommendations"), limit=4),
        "primary_artifact_type": artifact_type,
        "source": "llm",
        "model_provider": resolved_provider,
        "model": resolved_model,
    }


async def generate_master_logic_stream(
    *,
    pod_group_standards: dict[str, dict[str, Any]],
    mission_contract: dict[str, Any],
    mission_context: dict[str, Any],
) -> dict[str, Any]:
    """CEO fuses pod Group Standards into a unified Master Logic Stream (Phase 9).

    Merges LogicNodes from all pods, eliminates cross-pod duplicates, and orders
    by dependency for downstream code generation. Falls back to deterministic
    deduplication when LLM is unavailable.
    """
    if not pod_group_standards:
        return {
            "master_logic_stream": [],
            "total_unified_nodes": 0,
            "eliminated_across_pods": 0,
            "ready_for_codegen": False,
            "source": "empty",
        }

    recommendation = _pkg()._ceo_recommendation()
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.7-flash")).strip()


    pods_summary = []
    total_input_nodes = 0
    for pod_name, standard in pod_group_standards.items():
        nodes = standard.get("canonical_logicnodes") or []
        total_input_nodes += len(nodes)
        pods_summary.append({
            "pod": pod_name,
            "node_count": len(nodes),
            "nodes": [
                {"domain": n.get("domain"), "concept": n.get("concept"), "intent": n.get("intent")}
                for n in nodes[:15]
            ],
        })

    contract_summary = _clean_text(mission_contract.get("contract_summary", ""), max_length=300)
    required_domains = mission_contract.get("required_domains") or []
    acceptance_criteria = mission_contract.get("acceptance_criteria") or []

    prompt = (
        "You are AGENT-02-CEO performing Logic Folding — the Grand Fusion.\n"
        f"Recommended model: {provider}/{model}\n"
        "Merge LogicNodes from all pods into a single ordered Master Logic Stream.\n"
        "Remove cross-pod duplicates. Order by dependency (inputs before outputs).\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission: {contract_summary}\n"
        f"Required domains: {json.dumps(required_domains[:10])}\n"
        f"Acceptance criteria: {json.dumps(acceptance_criteria[:4])}\n"
        f"Total input nodes across all pods: {total_input_nodes}\n"
        f"Pod inputs:\n{json.dumps(pods_summary, indent=2)}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "master_logic_stream": [\n'
        '    {"node_id": "unified-001", "domain": "domain", "concept": "concept",\n'
        '     "canonical_intent": "intent", "source_pods": ["podA"], "dependency_order": 1}\n'
        "  ],\n"
        '  "total_unified_nodes": 18,\n'
        '  "eliminated_across_pods": 4,\n'
        '  "ready_for_codegen": true\n'
        "}\n\n"
        "Keep master_logic_stream to 5-25 nodes. Order by dependency_order (lowest first).\n"
    )

    parsed, resolved_provider, resolved_model, _route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="ceo logic fusion",
        agent_id=CEO_AGENT_ID,
    )

    if not isinstance(parsed, dict):
        all_nodes: list[dict[str, Any]] = []
        # Dedup on (domain, concept): the same concept name in different domains
        # is a distinct node and must not collapse. Keying on bare concept lost
        # real cross-domain nodes.
        seen_keys: set[tuple[str, str]] = set()
        order = 1
        for pod_name, standard in pod_group_standards.items():
            for node in standard.get("canonical_logicnodes") or []:
                if len(all_nodes) >= MAX_FUSION_NODES:
                    break
                concept = str(node.get("concept") or "")
                domain = str(node.get("domain") or "generic")
                dedup_key = (domain, concept)
                if dedup_key not in seen_keys:
                    seen_keys.add(dedup_key)
                    all_nodes.append({
                        "node_id": f"unified-{order:03d}",
                        "domain": domain,
                        "concept": concept,
                        "canonical_intent": node.get("intent", ""),
                        "source_pods": [pod_name],
                        "dependency_order": order,
                    })
                    order += 1
            if len(all_nodes) >= MAX_FUSION_NODES:
                break
        eliminated = max(0, total_input_nodes - len(all_nodes))
        return {
            "master_logic_stream": all_nodes,
            "total_unified_nodes": len(all_nodes),
            "eliminated_across_pods": eliminated,
            "ready_for_codegen": len(all_nodes) > 0,
            "source": "fallback",
        }

    stream = parsed.get("master_logic_stream") or []
    if not isinstance(stream, list):
        stream = []

    return {
        "master_logic_stream": stream[:MAX_FUSION_NODES],
        "total_unified_nodes": int(parsed.get("total_unified_nodes") or len(stream)),
        "eliminated_across_pods": int(parsed.get("eliminated_across_pods") or 0),
        "ready_for_codegen": bool(parsed.get("ready_for_codegen", True)),
        "source": "llm",
        "model_provider": resolved_provider,
        "model": resolved_model,
    }


# ---------------------------------------------------------------------------
# S2-02: Security threat analysis (AGENT-05-SECURITY)
# ---------------------------------------------------------------------------


async def generate_security_analysis(
    *,
    mission_id: str,
    mission_context: dict[str, Any],
    generated_output: dict[str, Any] | None,
    mission_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    """Run AGENT-05-SECURITY's threat analysis over the generated code artifact.

    Returns a ``security_analysis.v1`` document with a threat list, risk level,
    and deployment recommendation.  Falls back deterministically when LLM is
    unavailable so the gating phase is never blocked by provider outages.
    """
    recommendation = _pkg()._agent_recommendation("AGENT-05-SECURITY")
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.7-flash")).strip()


    code_snippet = _clean_text(
        str((generated_output or {}).get("generated_code") or ""), max_length=4000
    )
    language = _clean_text(
        str(
            (generated_output or {}).get("language")
            or mission_context.get("requested_target_language")
            or "unknown"
        ),
        max_length=32,
    )
    contract_summary = _clean_text(
        str((mission_contract or {}).get("contract_summary") or ""), max_length=300
    )

    prompt = (
        "You are AGENT-05-SECURITY performing a threat-analysis code review.\n"
        f"Recommended model: {provider}/{model}\n"
        "Analyse the generated code for security vulnerabilities, injection risks,\n"
        "secrets/credential exposure, and unsafe dependencies.\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission ID: {_clean_text(mission_id, max_length=96)}\n"
        f"Language: {language}\n"
        f"Contract summary: {contract_summary}\n"
        f"Code artifact (truncated to 4000 chars):\n```\n{code_snippet}\n```\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "schema_version": "security_analysis.v1",\n'
        '  "risk_level": "low|medium|high|critical",\n'
        '  "deployment_safe": true,\n'
        '  "threats": [\n'
        '    {"id": "T001", "category": "injection", "severity": "high",\n'
        '     "description": "...", "line_hint": null, "remediation": "..."}\n'
        "  ],\n"
        '  "summary": "One-paragraph executive summary.",\n'
        '  "recommendations": ["..."],\n'
        '  "passed": true\n'
        "}\n\n"
        "Limit threats list to 10 items. risk_level must be one of: low, medium, high, critical.\n"
        "Set deployment_safe=false only if risk_level is high or critical.\n"
    )

    parsed, resolved_provider, resolved_model, _route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="security threat analysis",
        agent_id="AGENT-05-SECURITY",
    )

    if not isinstance(parsed, dict):
        return _fallback_security_analysis(mission_id=mission_id, language=language)

    valid_risk_levels = {"low", "medium", "high", "critical"}
    risk_level = _clean_text(parsed.get("risk_level", "low"), max_length=16).lower()
    if risk_level not in valid_risk_levels:
        risk_level = "low"
    deployment_safe = bool(parsed.get("deployment_safe", True))
    threats_raw = parsed.get("threats") or []
    threats: list[dict[str, Any]] = []
    if isinstance(threats_raw, list):
        for item in threats_raw[:10]:
            if not isinstance(item, dict):
                continue
            threats.append({
                "id": _clean_text(item.get("id", ""), max_length=16) or f"T{len(threats)+1:03d}",
                "category": _clean_text(item.get("category", "unknown"), max_length=64),
                "severity": _clean_text(item.get("severity", "low"), max_length=16).lower(),
                "description": _clean_text(item.get("description", ""), max_length=240),
                "line_hint": item.get("line_hint"),
                "remediation": _clean_text(item.get("remediation", ""), max_length=240),
            })
    passed = risk_level not in {"high", "critical"} and deployment_safe
    return {
        "schema_version": "security_analysis.v1",
        "mission_id": _clean_text(mission_id, max_length=96),
        "agent_id": "AGENT-05-SECURITY",
        "risk_level": risk_level,
        "deployment_safe": deployment_safe,
        "threats": threats,
        "summary": _clean_text(
            parsed.get("summary", "Security analysis complete."), max_length=600
        ),
        "recommendations": _string_list(parsed.get("recommendations"), limit=8),
        "passed": passed,
        "source": "llm",
        "model_provider": resolved_provider,
        "model": resolved_model,
        "created_at": datetime.now(UTC).isoformat(),
    }


async def generate_vc_commit_strategy(
    *,
    mission_id: str,
    mission_context: dict[str, Any],
    generated_output: dict[str, Any] | None,
    delivery_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    """Ask AGENT-07-VC to produce a commit strategy for the generated artifact.

    Returns a ``vc_commit_strategy.v1`` document with a conventional-commit
    message, branch name, PR summary, and rollback plan.
    """
    recommendation = _pkg()._agent_recommendation("AGENT-07-VC")
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.7-flash")).strip()


    language = _clean_text(
        str(
            (generated_output or {}).get("language")
            or mission_context.get("requested_target_language")
            or "unknown"
        ),
        max_length=32,
    )
    filename = _clean_text(
        str((generated_output or {}).get("filename") or "output"), max_length=128
    )
    delivery_title = _clean_text(
        str((delivery_summary or {}).get("delivery_title") or "Mission output"), max_length=200
    )
    mission_type = _clean_text(
        str(mission_context.get("mission_type") or "BUILD_NEW"), max_length=48
    ).upper()

    prompt = (
        "You are AGENT-07-VC generating a version-control commit strategy.\n"
        f"Recommended model: {provider}/{model}\n"
        "Produce a conventional-commit message, feature branch name, PR summary, "
        "and rollback plan for the generated artifact.\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission ID: {_clean_text(mission_id, max_length=96)}\n"
        f"Mission type: {mission_type}\n"
        f"Language: {language}\n"
        f"Primary artifact: {filename}\n"
        f"Delivery summary: {delivery_title}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "schema_version": "vc_commit_strategy.v1",\n'
        '  "commit_message": "feat(scope): description\\n\\nBody text.",\n'
        '  "branch_name": "feature/mission-<id>-short-slug",\n'
        '  "pr_title": "...",\n'
        '  "pr_body": "## Summary\\n- bullet",\n'
        '  "rollback_steps": ["git revert <sha>", "..."],\n'
        '  "conventional_type": "feat|fix|chore|refactor|docs|test|perf"\n'
        "}\n\n"
        "Keep commit_message under 72 chars for the subject line.\n"
    )

    parsed, resolved_provider, resolved_model, _route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="vc commit strategy",
        agent_id="AGENT-07-VC",
    )

    if not isinstance(parsed, dict):
        return _fallback_vc_commit_strategy(
            mission_id=mission_id, language=language, mission_type=mission_type
        )

    valid_types = {"feat", "fix", "chore", "refactor", "docs", "test", "perf"}
    conv_type = _clean_text(parsed.get("conventional_type", "feat"), max_length=16).lower()
    if conv_type not in valid_types:
        conv_type = "feat"

    return {
        "schema_version": "vc_commit_strategy.v1",
        "mission_id": _clean_text(mission_id, max_length=96),
        "agent_id": "AGENT-07-VC",
        "commit_message": _clean_text(parsed.get("commit_message", ""), max_length=500)
            or f"feat: mission {mission_id[:8]} output",
        "branch_name": _clean_text(parsed.get("branch_name", ""), max_length=120)
            or f"feature/mission-{mission_id[:8]}",
        "pr_title": _clean_text(parsed.get("pr_title", ""), max_length=200)
            or delivery_title,
        "pr_body": _clean_text(parsed.get("pr_body", ""), max_length=2000),
        "rollback_steps": _string_list(parsed.get("rollback_steps"), limit=5),
        "conventional_type": conv_type,
        "source": "llm",
        "model_provider": resolved_provider,
        "model": resolved_model,
        "created_at": datetime.now(UTC).isoformat(),
    }


async def generate_compliance_assessment(
    *,
    mission_id: str,
    mission_context: dict[str, Any],
    generated_output: dict[str, Any] | None,
    mission_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    """Ask AGENT-08-COMPLIANCE to assess regulatory/governance compliance considerations.

    Distinct from AGENT-05-SECURITY's vulnerability/threat analysis and from
    security_compliance.py's deterministic PII/dependency-license scan: this is
    a lightweight LLM opinion on data-handling, third-party licensing, and
    audit-trail/documentation considerations for the generated artifact.
    Returns a ``compliance_assessment.v1`` document. Falls back deterministically
    when the LLM is unavailable so this gate never blocks mission delivery.
    """
    recommendation = _pkg()._agent_recommendation("AGENT-08-COMPLIANCE")
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.7-flash")).strip()


    language = _clean_text(
        str(
            (generated_output or {}).get("language")
            or mission_context.get("requested_target_language")
            or "unknown"
        ),
        max_length=32,
    )
    dependencies = _string_list((generated_output or {}).get("dependencies"), limit=20)
    contract_summary = _clean_text(
        str((mission_contract or {}).get("contract_summary") or ""), max_length=300
    )

    prompt = (
        "You are AGENT-08-COMPLIANCE assessing regulatory and governance compliance.\n"
        f"Recommended model: {provider}/{model}\n"
        "Review the mission output for data-handling/privacy considerations, "
        "third-party dependency licensing considerations, and audit-trail/"
        "documentation completeness. This is not a security vulnerability scan.\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission ID: {_clean_text(mission_id, max_length=96)}\n"
        f"Language: {language}\n"
        f"Contract summary: {contract_summary}\n"
        f"Dependencies: {', '.join(dependencies) or 'none declared'}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "schema_version": "compliance_assessment.v1",\n'
        '  "compliance_status": "compliant|needs_review|non_compliant",\n'
        '  "regulatory_notes": [\n'
        '    {"area": "data_privacy|licensing|audit_trail", "concern": "...", '
        '"recommendation": "..."}\n'
        "  ],\n"
        '  "summary": "One-paragraph executive summary.",\n'
        '  "recommendations": ["..."],\n'
        '  "passed": true\n'
        "}\n\n"
        "Limit regulatory_notes to 10 items. compliance_status must be one of: "
        "compliant, needs_review, non_compliant.\n"
    )

    parsed, resolved_provider, resolved_model, _route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="compliance assessment",
        agent_id="AGENT-08-COMPLIANCE",
    )

    if not isinstance(parsed, dict):
        return _fallback_compliance_assessment(mission_id=mission_id)

    valid_statuses = {"compliant", "needs_review", "non_compliant"}
    compliance_status = _clean_text(
        parsed.get("compliance_status", "needs_review"), max_length=16
    ).lower()
    if compliance_status not in valid_statuses:
        compliance_status = "needs_review"
    notes_raw = parsed.get("regulatory_notes") or []
    regulatory_notes: list[dict[str, Any]] = []
    if isinstance(notes_raw, list):
        for item in notes_raw[:10]:
            if not isinstance(item, dict):
                continue
            regulatory_notes.append({
                "area": _clean_text(item.get("area", "unknown"), max_length=32),
                "concern": _clean_text(item.get("concern", ""), max_length=240),
                "recommendation": _clean_text(item.get("recommendation", ""), max_length=240),
            })
    passed = compliance_status != "non_compliant" and bool(parsed.get("passed", True))
    return {
        "schema_version": "compliance_assessment.v1",
        "mission_id": _clean_text(mission_id, max_length=96),
        "agent_id": "AGENT-08-COMPLIANCE",
        "compliance_status": compliance_status,
        "regulatory_notes": regulatory_notes,
        "summary": _clean_text(
            parsed.get("summary", "Compliance assessment complete."), max_length=600
        ),
        "recommendations": _string_list(parsed.get("recommendations"), limit=8),
        "passed": passed,
        "source": "llm",
        "model_provider": resolved_provider,
        "model": resolved_model,
        "created_at": datetime.now(UTC).isoformat(),
    }


async def generate_integration_tests(
    *,
    mission_id: str,
    mission_context: dict[str, Any],
    generated_output: dict[str, Any] | None,
    mission_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    """Ask AGENT-10-TESTER to generate integration tests for the generated artifact.

    Returns an ``integration_tests.v1`` document containing test code and a
    manifest of test cases.  Falls back to a stub test when LLM is unavailable.
    """
    recommendation = _pkg()._agent_recommendation("AGENT-10-TESTER")
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.7-flash")).strip()


    language = _clean_text(
        str(
            (generated_output or {}).get("language")
            or mission_context.get("requested_target_language")
            or "python"
        ),
        max_length=32,
    ).lower()
    filename = _clean_text(
        str((generated_output or {}).get("filename") or "output"), max_length=128
    )
    code_snippet = _clean_text(
        str((generated_output or {}).get("generated_code") or ""), max_length=3000
    )
    contract_summary = _clean_text(
        str((mission_contract or {}).get("contract_summary") or ""), max_length=300
    )
    acceptance_criteria = _string_list(
        (mission_contract or {}).get("acceptance_criteria"), limit=6
    )

    prompt = (
        "You are AGENT-10-TESTER generating integration tests.\n"
        f"Recommended model: {provider}/{model}\n"
        "Write tests that verify the acceptance criteria of the generated artifact.\n"
        "If the artifact is an interactive game or a process that does not exit, "
        "write unit tests of extractable logic (collision, score, movement) — "
        "do not spawn the interactive process.\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission ID: {_clean_text(mission_id, max_length=96)}\n"
        f"Language: {language}\n"
        f"Artifact filename: {filename}\n"
        f"Contract summary: {contract_summary}\n"
        f"Acceptance criteria: {json.dumps(acceptance_criteria)}\n"
        f"Code artifact (truncated):\n```\n{code_snippet}\n```\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "schema_version": "integration_tests.v1",\n'
        '  "test_filename": "test_output.py",\n'
        '  "test_code": "import ...",\n'
        '  "test_cases": [\n'
        '    {"name": "test_happy_path", "description": "...", "expected_outcome": "..."}\n'
        "  ],\n"
        '  "framework": "pytest|jest|mocha|gtest|junit|rspec"\n'
        "}\n\n"
        "Limit test_cases to 8. test_code must be runnable in the target language.\n"
    )

    parsed, resolved_provider, resolved_model, _route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="integration test generation",
        agent_id="AGENT-10-TESTER",
    )

    if not isinstance(parsed, dict):
        return _fallback_integration_tests(
            mission_id=mission_id, language=language, filename=filename
        )

    test_cases_raw = parsed.get("test_cases") or []
    test_cases: list[dict[str, Any]] = []
    if isinstance(test_cases_raw, list):
        for item in test_cases_raw[:8]:
            if not isinstance(item, dict):
                continue
            test_cases.append({
                "name": _clean_text(item.get("name", ""), max_length=120),
                "description": _clean_text(item.get("description", ""), max_length=240),
                "expected_outcome": _clean_text(item.get("expected_outcome", ""), max_length=240),
            })

    return {
        "schema_version": "integration_tests.v1",
        "mission_id": _clean_text(mission_id, max_length=96),
        "agent_id": "AGENT-10-TESTER",
        "test_filename": _clean_text(
            parsed.get("test_filename", f"test_{filename}"), max_length=200
        ),
        "test_code": _clean_text(parsed.get("test_code", ""), max_length=10000),
        "test_cases": test_cases,
        "framework": _clean_text(parsed.get("framework", "pytest"), max_length=32),
        "source": "llm",
        "model_provider": resolved_provider,
        "model": resolved_model,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _logicnodes_are_unstated(nodes: Any) -> bool:
    """True when nodes are empty or only routing stubs. Those are not a quality score."""
    if not isinstance(nodes, list) or not nodes:
        return True
    stated = 0
    for node in nodes:
        if not isinstance(node, dict):
            continue
        cmd = str(node.get("cmd") or "").strip().lower()
        payload = node.get("payload") if isinstance(node.get("payload"), dict) else {}
        origin = str(payload.get("origin") or payload.get("concept") or "").strip().lower()
        if cmd in {"routing_stub", "stub"} or origin in {"routing_stub", "stub"}:
            continue
        stated += 1
    return stated == 0


async def generate_pod_audit_verdict(
    *,
    mission_id: str,
    pod_name: str,
    mission_context: dict[str, Any],
    pod_group_standard: dict[str, Any],
    generated_output: dict[str, Any] | None,
) -> dict[str, Any]:
    """Ask the appropriate pod QC/Audit agent to verdict the pod's output.

    ``pod_name`` must be one of ``podA``, ``podB``, ``podC``, ``podD``.
    Selects the correct audit agent (13/19/25/31) and returns a
    ``pod_audit_verdict.v1`` document.
    """
    normalized_pod = pod_name.strip().lower()
    audit_agent_id = _POD_AUDIT_AGENTS_BY_LOWER.get(normalized_pod, _DEFAULT_AUDIT_AGENT)
    recommendation = _pkg()._agent_recommendation(audit_agent_id)
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.7-flash")).strip()


    nodes = pod_group_standard.get("canonical_logicnodes") or []
    if _logicnodes_are_unstated(nodes):
        return {
            "schema_version": "pod_audit_verdict.v1",
            "mission_id": _clean_text(mission_id, max_length=96),
            "pod_name": pod_name,
            "agent_id": audit_agent_id,
            "verdict": "WARN",
            "passed": True,
            "quality_score": 0.0,
            "findings": [
                {
                    "id": "F000",
                    "severity": "info",
                    "description": (
                        "No extracted LogicNodes to audit on this BUILD_NEW path. "
                        "Codegen already produced the artifact; this is not a quality score."
                    ),
                }
            ],
            "summary": (
                "Pod audit skipped scoring: there is no extracted LogicNode graph "
                "to review. Do not treat this as a 0.96 PASS."
            ),
            "recommendations": [
                "Use runtime QC and generated tests to judge BUILD_NEW quality."
            ],
            "source": "no_extractable_logicnodes",
            "model_provider": provider,
            "model": model,
            "created_at": datetime.now(UTC).isoformat(),
        }

    canonical_count = len(nodes)
    eliminated = int(pod_group_standard.get("eliminated_duplicates") or 0)
    contract_summary = _clean_text(
        str(mission_context.get("contract_summary") or ""), max_length=300
    )
    language = _clean_text(
        str(
            (generated_output or {}).get("language")
            or mission_context.get("requested_target_language")
            or "unknown"
        ),
        max_length=32,
    )

    prompt = (
        f"You are {audit_agent_id} performing QC audit of pod {pod_name}.\n"
        f"Recommended model: {provider}/{model}\n"
        "Review the pod's group standard and generated output for quality, "
        "completeness, and contract alignment.\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission ID: {_clean_text(mission_id, max_length=96)}\n"
        f"Pod: {pod_name}\n"
        f"Language: {language}\n"
        f"Contract summary: {contract_summary}\n"
        f"Canonical LogicNodes produced: {canonical_count}\n"
        f"Duplicates eliminated: {eliminated}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "schema_version": "pod_audit_verdict.v1",\n'
        '  "verdict": "PASS|FAIL|WARN",\n'
        '  "passed": true,\n'
        '  "quality_score": 0.85,\n'
        '  "findings": [\n'
        '    {"id": "F001", "severity": "warn", "description": "..."}\n'
        "  ],\n"
        '  "summary": "Pod audit complete.",\n'
        '  "recommendations": ["..."]\n'
        "}\n\n"
        "verdict must be PASS, FAIL, or WARN. quality_score is 0.0–1.0.\n"
        "Limit findings to 6 items.\n"
    )

    parsed, resolved_provider, resolved_model, _route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context=f"pod audit {pod_name}",
        agent_id=audit_agent_id,
    )

    if not isinstance(parsed, dict):
        return _fallback_pod_audit_verdict(
            mission_id=mission_id,
            pod_name=pod_name,
            audit_agent_id=audit_agent_id,
        )

    valid_verdicts = {"PASS", "FAIL", "WARN"}
    verdict = _clean_text(parsed.get("verdict", "PASS"), max_length=8).upper()
    if verdict not in valid_verdicts:
        verdict = "PASS"

    findings_raw = parsed.get("findings") or []
    findings: list[dict[str, Any]] = []
    if isinstance(findings_raw, list):
        for item in findings_raw[:6]:
            if not isinstance(item, dict):
                continue
            findings.append({
                "id": _clean_text(item.get("id", ""), max_length=16) or f"F{len(findings)+1:03d}",
                "severity": _clean_text(item.get("severity", "info"), max_length=16).lower(),
                "description": _clean_text(item.get("description", ""), max_length=240),
            })

    try:
        quality_score = max(0.0, min(1.0, float(parsed.get("quality_score") or 0.8)))
    except (TypeError, ValueError):
        quality_score = 0.8

    return {
        "schema_version": "pod_audit_verdict.v1",
        "mission_id": _clean_text(mission_id, max_length=96),
        "pod_name": pod_name,
        "agent_id": audit_agent_id,
        "verdict": verdict,
        "passed": verdict != "FAIL",
        "quality_score": round(quality_score, 4),
        "findings": findings,
        "summary": _clean_text(
            parsed.get("summary", "Pod audit complete."), max_length=600
        ),
        "recommendations": _string_list(parsed.get("recommendations"), limit=6),
        "source": "llm",
        "model_provider": resolved_provider,
        "model": resolved_model,
        "created_at": datetime.now(UTC).isoformat(),
    }

