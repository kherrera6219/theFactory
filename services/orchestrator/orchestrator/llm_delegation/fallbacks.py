from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..mission_flow import (
    resolve_pod_manager_agent_id,
    resolve_specialist_agent_id,
)
from ..orchestrator_metrics import LLM_FALLBACK_TOTAL
from .config import _VALID_POD_MANAGER_IDS, _VALID_SPECIALIST_IDS
from .text import (
    _clean_text,
    _apply_pm_product_clarification_policy,
    _cluster_id,
    _logicnode_languages,
    _logicnode_payload,
    _logicnode_sources,
    _logicnode_text,
    _normalize_agent_choice,
    _pm_ambiguity_score,
    _pod_standard_coverage_verdict,
    _priority,
    _standard_node_id,
    _string_list,
)


def _fallback_delegation(
    *,
    requested_target_language: str | None,
    mission_context: dict[str, Any],
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    LLM_FALLBACK_TOTAL.labels(agent_id="AGENT-02-CEO", reason="offline").inc()
    pod_manager_agent_id = resolve_pod_manager_agent_id(requested_target_language)
    specialist_agent_id = resolve_specialist_agent_id(requested_target_language)
    return {
        "pod_manager_agent_id": pod_manager_agent_id,
        "specialist_agent_id": specialist_agent_id,
        "rationale": "Deterministic fallback delegation based on target language mapping.",
        "source": "fallback",
        "model_provider": recommendation.get("provider"),
        "model": recommendation.get("model"),
        "mission_context": mission_context,
    }


def _fallback_pod_manager_delegation(
    *,
    pod_manager_agent_id: str,
    specialist_agent_id: str,
    mission_context: dict[str, Any],
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    LLM_FALLBACK_TOTAL.labels(agent_id=pod_manager_agent_id, reason="offline").inc()
    return {
        "pod_manager_agent_id": pod_manager_agent_id,
        "specialist_agent_id": specialist_agent_id,
        "rationale": "Deterministic pod-manager fallback delegation based on language mapping.",
        "source": "fallback",
        "model_provider": recommendation.get("provider"),
        "model": recommendation.get("model"),
        "mission_context": mission_context,
    }


def _fallback_specialist_plan(
    *,
    specialist_agent_id: str,
    pod_manager_agent_id: str,
    mission_context: dict[str, Any],
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    LLM_FALLBACK_TOTAL.labels(agent_id=specialist_agent_id, reason="offline").inc()
    language = str(mission_context.get("requested_target_language") or "general").strip().lower()
    return {
        "specialist_agent_id": specialist_agent_id,
        "pod_manager_agent_id": pod_manager_agent_id,
        "plan_summary": (
            "Fallback specialist plan generated deterministically from mission metadata "
            "and language routing."
        ),
        "deliverables": [
            f"Produce validated implementation for {language} target.",
            "Publish logicnode evidence and audit artifacts before mission verification.",
        ],
        "risk_notes": [
            "Provider output unavailable; deterministic fallback plan used.",
        ],
        "source": "fallback",
        "model_provider": recommendation.get("provider"),
        "model": recommendation.get("model"),
        "mission_context": mission_context,
    }


def _fallback_pm_feature_contract(
    *,
    prompt: str,
    mission_type: str,
    requested_target_language: str | None,
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    LLM_FALLBACK_TOTAL.labels(agent_id="AGENT-01-PM", reason="offline").inc()
    language = _clean_text(requested_target_language or "", max_length=32).lower()
    contract = {
        "schema_version": "feature_contract.v1",
        "title": _clean_text(prompt, max_length=80) or "Mission",
        "summary": _clean_text(prompt, max_length=500),
        "functional_requirements": [_clean_text(prompt, max_length=160) or "Complete mission"],
        "non_functional_requirements": [],
        "acceptance_criteria": ["Mission completes without error."],
        "target_languages": [language] if language else [],
        "estimated_complexity": "medium",
        "human_approval_required": str(mission_type).strip().upper()
        in {"IMPORT_MODERNIZE", "PORT", "DEBUG_REPAIR", "SECURITY_HARDEN"},
        # Carry the degraded state in risk_notes + an explicit degraded flag so the
        # UI/operator can tell the planning model never ran — without forcing an
        # ambiguity-pause (intake_status stays "ready" so mission-flow behavior is
        # unchanged; surfacing is the UI's job via the `degraded` flag).
        "risk_notes": [
            "Planning model (LLM) was unavailable — this is a deterministic fallback "
            "draft, not a scoped contract. Verify provider config (provider, model, "
            "API key) and re-run for a full feature contract.",
        ],
        "clarifying_questions": [],
        "assumptions": [],
        "intake_status": "ready",
        "source": "fallback",
        "degraded": True,
        "degraded_reason": "llm_unavailable",
        "model_provider": recommendation.get("provider"),
        "model": recommendation.get("model"),
        "created_at": datetime.now(UTC).isoformat(),
    }
    contract["ambiguity_score"] = _pm_ambiguity_score(contract, prompt)
    return _apply_pm_product_clarification_policy(
        contract=contract,
        prompt=prompt,
        requested_target_language=requested_target_language,
    )


def _fallback_mission_contract(
    *,
    prompt: str,
    mission_type: str,
    output_mode: str,
    requested_target_language: str | None,
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    LLM_FALLBACK_TOTAL.labels(agent_id="AGENT-01-PM", reason="offline").inc()
    language = _clean_text(requested_target_language or "general", max_length=32).lower()
    return {
        "schema_version": "mission_contract.v1",
        "contract_summary": _clean_text(
            prompt or "Complete the requested mission.",
            max_length=240,
        ),
        "mission_type": _clean_text(mission_type or "BUILD_NEW", max_length=48).upper(),
        "target_languages": [language] if language != "general" else [],
        "output_mode": _clean_text(output_mode or "FULL_BUILD", max_length=48).upper(),
        "output_format": "standalone_script",
        "required_domains": ["generic"],
        "logicnode_requirements": [
            {
                "domain": "generic",
                "concept": "primary_operation",
                "intent": "Implement the requested mission behavior",
                "priority": "HIGH",
            }
        ],
        "acceptance_criteria": ["Mission output satisfies the requested behavior."],
        "risk_notes": ["Mission contract generated via deterministic fallback."],
        "source": "fallback",
        "model_provider": recommendation.get("provider"),
        "model": recommendation.get("model"),
        "created_at": datetime.now(UTC).isoformat(),
    }


def _fallback_codegen(
    *,
    specialist_agent_id: str,
    target_language: str,
    contract_summary: str,
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    LLM_FALLBACK_TOTAL.labels(agent_id=specialist_agent_id, reason="offline").inc()
    language = _clean_text(target_language or "text", max_length=32).lower()
    return {
        "schema_version": "generated_output.v1",
        "generated_code": "",
        "filename": f"generated.{language or 'txt'}",
        "language": language,
        "description": "Code generation unavailable; provider output was not available.",
        "dependencies": [],
        "usage_example": "",
        "source": "fallback",
        "specialist_agent_id": specialist_agent_id,
        "model_provider": recommendation.get("provider"),
        "model": recommendation.get("model"),
        "generated_at": datetime.now(UTC).isoformat(),
        "code_length_chars": 0,
        "risk_notes": [
            _clean_text(contract_summary, max_length=160),
            "Fallback output is not a generated software deliverable.",
        ],
    }


def _fallback_logic_clusters(
    *,
    mission_contract: dict[str, Any],
    requested_target_language: str | None,
    ceo_delegation: dict[str, Any],
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    LLM_FALLBACK_TOTAL.labels(agent_id="AGENT-02-CEO", reason="offline").inc()
    pod_manager_agent_id = _normalize_agent_choice(
        ceo_delegation.get("pod_manager_agent_id"),
        allowed_ids=_VALID_POD_MANAGER_IDS,
        fallback=resolve_pod_manager_agent_id(requested_target_language),
    )
    specialist_agent_id = _normalize_agent_choice(
        ceo_delegation.get("specialist_agent_id"),
        allowed_ids=_VALID_SPECIALIST_IDS,
        fallback=resolve_specialist_agent_id(requested_target_language),
    )
    requirements = mission_contract.get("logicnode_requirements")
    requirement_items = (
        [item for item in requirements if isinstance(item, dict)]
        if isinstance(requirements, list)
        else []
    )
    domains = _string_list(mission_contract.get("required_domains"), limit=8)
    if not domains:
        domains = [
            _clean_text(item.get("domain") or "general", max_length=64)
            for item in requirement_items[:8]
        ]
    if not domains:
        domains = ["general"]
    seen: set[str] = set()
    clusters: list[dict[str, Any]] = []
    for domain in domains:
        normalized_domain = domain or "general"
        key = normalized_domain.lower()
        if key in seen:
            continue
        seen.add(key)
        matching_requirements = [
            _clean_text(
                item.get("concept") or item.get("intent") or normalized_domain,
                max_length=80,
            )
            for item in requirement_items
            if _clean_text(item.get("domain") or "", max_length=64).lower() == key
        ]
        priority = "MEDIUM"
        for item in requirement_items:
            if _clean_text(item.get("domain") or "", max_length=64).lower() == key:
                priority = _priority(item.get("priority"))
                break
        cluster_index = len(clusters) + 1
        clusters.append(
            {
                "cluster_id": _cluster_id(cluster_index, normalized_domain),
                "title": f"{normalized_domain.title()} Cluster",
                "domain": normalized_domain,
                "priority": priority,
                "pod_manager_agent_id": pod_manager_agent_id,
                "specialist_agent_id": specialist_agent_id,
                "requirement_refs": matching_requirements[:8],
                "depends_on": [],
                "rationale": "Deterministic cluster from mission contract domain scope.",
            }
        )
    return {
        "schema_version": "logic_clusters.v1",
        "clusters": clusters[:8],
        "source": "fallback",
        "model_provider": recommendation.get("provider"),
        "model": recommendation.get("model"),
        "created_at": datetime.now(UTC).isoformat(),
    }


def _fallback_pod_group_standard(
    *,
    pod_name: str,
    pod_manager_agent_id: str,
    mission_id: str,
    logicnodes: list[dict[str, Any]],
    mission_contract: dict[str, Any],
    recommendation: dict[str, Any],
    source_code: str | None = None,
) -> dict[str, Any]:
    LLM_FALLBACK_TOTAL.labels(agent_id=f"{pod_name.upper()}-MGR", reason="offline").inc()
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for record in logicnodes[:200]:
        payload = _logicnode_payload(record)
        if not payload:
            continue
        domain = _logicnode_text(payload, "domain", "category", fallback="general")
        concept = _logicnode_text(payload, "concept", "name", "title", fallback="")
        if not concept:
            concept = _logicnode_text(payload, "intent", "summary", fallback="primary_operation")
        intent = _logicnode_text(
            payload,
            "intent",
            "summary",
            "description",
            fallback="Implement extracted mission behavior.",
        )
        key = (domain.lower(), concept.lower())
        source_ids = _logicnode_sources(record, payload)
        languages = _logicnode_languages(record, payload)
        existing = grouped.get(key)
        if existing is None:
            confidence = payload.get("confidence")
            grouped[key] = {
                "domain": domain,
                "concept": concept,
                "intent": intent,
                "source_node_ids": source_ids,
                "languages": languages,
                "confidence": confidence if isinstance(confidence, (int, float)) else None,
            }
            continue
        for source_id in source_ids:
            if source_id not in existing["source_node_ids"]:
                existing["source_node_ids"].append(source_id)
        for language in languages:
            if language not in existing["languages"]:
                existing["languages"].append(language)
        if (
            not existing.get("intent")
            or existing["intent"] == "Implement extracted mission behavior."
        ):
            existing["intent"] = intent

    if not grouped:
        requirements = mission_contract.get("logicnode_requirements")
        if isinstance(requirements, list):
            for item in requirements[:8]:
                if not isinstance(item, dict):
                    continue
                domain = _clean_text(item.get("domain") or "general", max_length=64)
                concept = _clean_text(item.get("concept") or "primary_operation", max_length=80)
                grouped[(domain.lower(), concept.lower())] = {
                    "domain": domain,
                    "concept": concept,
                    "intent": _clean_text(
                        item.get("intent") or "Implement mission contract requirement.",
                        max_length=180,
                    ),
                    "source_node_ids": [],
                    "languages": _string_list(
                        mission_contract.get("target_languages"),
                        limit=6,
                        max_length=32,
                    ),
                    "confidence": None,
                }

    canonical: list[dict[str, Any]] = []
    for item in grouped.values():
        node_index = len(canonical) + 1
        confidence = item.get("confidence")
        canonical.append(
            {
                "standard_node_id": _standard_node_id(
                    node_index,
                    str(item.get("domain") or "general"),
                    str(item.get("concept") or "primary_operation"),
                ),
                "domain": item.get("domain") or "general",
                "concept": item.get("concept") or "primary_operation",
                "intent": item.get("intent") or "Implement extracted mission behavior.",
                "source_node_ids": list(item.get("source_node_ids") or [])[:20],
                "languages": list(item.get("languages") or [])[:6],
                "confidence": confidence if isinstance(confidence, (int, float)) else None,
            }
        )
        if len(canonical) >= 20:
            break

    return {
        "schema_version": "pod_group_standard.v1",
        "pod": pod_name,
        "pod_manager_agent_id": pod_manager_agent_id,
        "mission_id": mission_id,
        "canonical_logicnodes": canonical,
        "coverage_verdict": _pod_standard_coverage_verdict(
            logicnodes=logicnodes,
            canonical_logicnodes=canonical,
            source_code=source_code,
        ),
        "eliminated_duplicates": max(0, len(logicnodes) - len(canonical)),
        "summary": (
            "Deterministic pod group standard produced by consolidating equivalent "
            "LogicNodes for pod-manager fusion."
        ),
        "source": "fallback",
        "model_provider": recommendation.get("provider"),
        "model": recommendation.get("model"),
        "created_at": datetime.now(UTC).isoformat(),
    }


def _fallback_security_analysis(*, mission_id: str, language: str) -> dict[str, Any]:
    """Offline fallback for the security gate.

    The LLM is unavailable, so the gate could not actually run. Report this
    honestly as ``degraded`` with ``passed=False`` rather than a fake green
    ``passed=True``. The ``advisory=True`` flag means the mission can still
    continue (offline development is supported) but the operator sees a warning
    instead of a clean pass.
    """
    LLM_FALLBACK_TOTAL.labels(agent_id="AGENT-05-SECURITY", reason="offline").inc()
    return {
        "schema_version": "security_analysis.v1",
        "mission_id": _clean_text(mission_id, max_length=96),
        "agent_id": "AGENT-05-SECURITY",
        "risk_level": "unknown",
        "deployment_safe": False,
        "threats": [],
        "summary": (
            "Security analysis could not run — LLM provider unavailable. "
            "Gate bypassed (advisory); manual review required before production."
        ),
        "recommendations": ["Perform manual security review before production deployment."],
        "passed": False,
        "status": "degraded",
        "reason": "LLM unavailable — gate bypassed",
        "advisory": True,
        "source": "fallback",
        "created_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# S2-03: Version-control commit strategy (AGENT-07-VC)
# ---------------------------------------------------------------------------


def _fallback_compliance_assessment(*, mission_id: str) -> dict[str, Any]:
    """Offline fallback for the compliance gate.

    Matches _fallback_security_analysis's honesty convention: the LLM is
    unavailable, so report status="degraded" with passed=False rather than a
    fake green pass. The mission is not blocked (advisory=True); the operator
    sees a warning instead.
    """
    LLM_FALLBACK_TOTAL.labels(agent_id="AGENT-08-COMPLIANCE", reason="offline").inc()
    return {
        "schema_version": "compliance_assessment.v1",
        "mission_id": _clean_text(mission_id, max_length=96),
        "agent_id": "AGENT-08-COMPLIANCE",
        "compliance_status": "needs_review",
        "regulatory_notes": [],
        "summary": (
            "Compliance assessment could not run — LLM provider unavailable. "
            "Gate bypassed (advisory); manual review required before production."
        ),
        "recommendations": ["Perform manual compliance review before production deployment."],
        "passed": False,
        "status": "degraded",
        "reason": "LLM unavailable — gate bypassed",
        "advisory": True,
        "source": "fallback",
        "created_at": datetime.now(UTC).isoformat(),
    }


def _fallback_vc_commit_strategy(
    *, mission_id: str, language: str, mission_type: str
) -> dict[str, Any]:
    slug = mission_id[:8]
    mission_lower = mission_type.lower().replace("_", "-")
    return {
        "schema_version": "vc_commit_strategy.v1",
        "mission_id": mission_id,
        "agent_id": "AGENT-07-VC",
        "commit_message": f"feat({language}): {mission_lower} mission {slug} output",
        "branch_name": f"feature/mission-{slug}-{language}",
        "pr_title": f"Mission {slug} — {mission_lower} ({language})",
        "pr_body": f"## Summary\n- Automated output from HGR mission `{mission_id}`.",
        "rollback_steps": ["git revert HEAD", "make down && make up"],
        "conventional_type": "feat",
        "source": "fallback",
        "created_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# S2-04: Integration test generation (AGENT-10-TESTER)
# ---------------------------------------------------------------------------


def _fallback_integration_tests(
    *, mission_id: str, language: str, filename: str
) -> dict[str, Any]:
    if language == "python":
        test_code = (
            f"# Auto-generated stub tests for mission {mission_id[:8]}\n"
            f"import importlib, sys\n\n"
            f"def test_module_importable():\n"
            f"    \"\"\"Verify the generated module imports without error.\"\"\"\n"
            f"    # Adjust import path as needed for your project layout\n"
            f"    assert True, 'Module import check placeholder'\n"
        )
        framework = "pytest"
        test_filename = f"test_{filename}"
    elif language in {"javascript", "typescript"}:
        test_code = (
            f"// Auto-generated stub tests for mission {mission_id[:8]}\n"
            f"describe('{filename}', () => {{\n"
            f"  it('should load without error', () => {{\n"
            f"    expect(true).toBe(true);\n"
            f"  }});\n"
            f"}});\n"
        )
        framework = "jest"
        test_filename = f"{filename.rsplit('.', 1)[0]}.test.{filename.rsplit('.', 1)[-1]}"
    else:
        test_code = f"// Stub test for mission {mission_id[:8]} ({language})\n"
        framework = "unknown"
        test_filename = f"test_{filename}"

    return {
        "schema_version": "integration_tests.v1",
        "mission_id": mission_id,
        "agent_id": "AGENT-10-TESTER",
        "test_filename": test_filename,
        "test_code": test_code,
        "test_cases": [
            {
                "name": "test_placeholder",
                "description": "Stub placeholder — replace with real assertions.",
                "expected_outcome": "Passes without error.",
            }
        ],
        "framework": framework,
        "source": "fallback",
        "created_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# S2-05: Pod audit verdict (AGENT-13/19/25/31-AUDIT)
# ---------------------------------------------------------------------------

_POD_AUDIT_AGENTS: dict[str, str] = {
    "podA": "AGENT-13-PODA-AUDIT",
    "podB": "AGENT-19-PODB-AUDIT",
    "podC": "AGENT-25-PODC-AUDIT",
    "podD": "AGENT-31-PODD-AUDIT",
}
_DEFAULT_AUDIT_AGENT = "AGENT-13-PODA-AUDIT"


def _fallback_pod_audit_verdict(
    *, mission_id: str, pod_name: str, audit_agent_id: str
) -> dict[str, Any]:
    """Offline fallback for the pod-audit gate.

    The LLM could not run the audit, so report ``degraded`` with
    ``passed=False`` rather than granting a fake ``PASS``. ``advisory=True``
    keeps the pipeline moving (offline development) while making the bypass
    visible to operators.
    """
    return {
        "schema_version": "pod_audit_verdict.v1",
        "mission_id": mission_id,
        "pod_name": pod_name,
        "agent_id": audit_agent_id,
        "verdict": "DEGRADED",
        "passed": False,
        "status": "degraded",
        "reason": "LLM unavailable — gate bypassed",
        "advisory": True,
        "quality_score": 0.0,
        "findings": [],
        "summary": (
            "Pod audit could not run — LLM provider unavailable. "
            "Gate bypassed (advisory); rerun with LLM access for an authoritative verdict."
        ),
        "recommendations": ["Rerun pod audit with LLM access for authoritative verdict."],
        "source": "fallback",
        "created_at": datetime.now(UTC).isoformat(),
    }

