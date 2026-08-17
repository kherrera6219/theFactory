from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from ..mission_flow import (
    resolve_pod_manager_agent_id,
    resolve_specialist_agent_id,
)
from .config import _VALID_POD_MANAGER_IDS, _VALID_SPECIALIST_IDS
from .fallbacks import _fallback_logic_clusters, _fallback_pod_group_standard
from .text import (
    _apply_pm_product_clarification_policy,
    _clean_text,
    _cluster_id,
    _normalize_agent_choice,
    _pm_ambiguity_score,
    _pod_standard_coverage_verdict,
    _priority,
    _safe_filename,
    _standard_node_id,
    _string_list,
    _strip_code_fences,
)


def _code_text_trace(value: str) -> dict[str, Any]:
    return {
        "digest_sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
        "length_chars": len(value),
        "size_bytes": len(value.encode("utf-8")),
        "non_ascii_count": sum(1 for char in value if ord(char) > 127),
    }


def _normalize_deliverables(raw: Any, fallback_requirements: list[str]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    source = raw if isinstance(raw, list) else []
    for item in source[:8]:
        if isinstance(item, dict):
            name = _clean_text(str(item.get("name") or ""), max_length=120)
            hint = _clean_text(str(item.get("artifact_hint") or ""), max_length=160)
        else:
            name = _clean_text(str(item), max_length=120)
            hint = ""
        if name:
            items.append({"name": name, "artifact_hint": hint})
    if items:
        return items
    return [
        {"name": _clean_text(req, max_length=120), "artifact_hint": ""}
        for req in fallback_requirements[:4]
        if _clean_text(req, max_length=120)
    ]


def _normalize_pm_feature_contract(
    raw: dict[str, Any],
    *,
    provider: str,
    model: str,
    route: str,
    prompt: str,
    requested_target_language: str | None,
) -> dict[str, Any]:
    intake_status = _clean_text(raw.get("intake_status", "ready"), max_length=32).lower()
    if intake_status not in {"needs_clarification", "ready"}:
        # Fail closed: an unrecognized/hallucinated status (e.g. "unclear",
        # "pending") must not be silently treated as "ready" — that would let
        # a genuinely underspecified mission skip clarification entirely.
        intake_status = "needs_clarification"
    complexity = _clean_text(raw.get("estimated_complexity", "medium"), max_length=24).lower()
    if complexity not in {"low", "medium", "high", "very_high"}:
        complexity = "medium"
    human_approval = raw.get("human_approval_required", False)
    if not isinstance(human_approval, bool):
        human_approval = str(human_approval).strip().lower() in {"1", "true", "yes", "on"}
    target_languages = _string_list(raw.get("target_languages"), limit=4, max_length=32)
    if not target_languages and requested_target_language:
        target_languages = [_clean_text(requested_target_language, max_length=32).lower()]
    functional_requirements = _string_list(raw.get("functional_requirements"), limit=8)
    if not functional_requirements:
        functional_requirements = [_clean_text(prompt, max_length=160) or "Complete mission"]
    acceptance_criteria = _string_list(raw.get("acceptance_criteria"), limit=6)
    if not acceptance_criteria:
        acceptance_criteria = ["Mission completes without error."]
    risk_assessment = {
        "complexity": complexity,
        "risk_score": 0.0,
        "risk_factors": _string_list(raw.get("risk_notes"), limit=5),
    }
    if complexity == "very_high":
        risk_assessment["risk_score"] = 0.9
    elif complexity == "high":
        risk_assessment["risk_score"] = 0.7
    elif complexity == "medium":
        risk_assessment["risk_score"] = 0.4
    else:
        risk_assessment["risk_score"] = 0.2

    contract = {
        "schema_version": "feature_contract.v1",
        "title": _clean_text(raw.get("title", "Mission"), max_length=80) or "Mission",
        "summary": _clean_text(raw.get("summary", prompt), max_length=500),
        "functional_requirements": functional_requirements,
        "non_functional_requirements": _string_list(
            raw.get("non_functional_requirements"), limit=4
        ),
        "acceptance_criteria": acceptance_criteria,
        "target_languages": target_languages,
        "estimated_complexity": complexity,
        "risk_assessment": risk_assessment,
        "human_approval_required": human_approval,
        "risk_notes": _string_list(raw.get("risk_notes"), limit=5),
        "clarifying_questions": _string_list(
            raw.get("clarifying_questions"),
            limit=5,
            max_length=800,
        ),
        "assumptions": _string_list(raw.get("assumptions"), limit=6),
        "out_of_scope": _string_list(raw.get("out_of_scope"), limit=6),
        "deliverables": _normalize_deliverables(raw.get("deliverables"), functional_requirements),
        "engagement_type": _clean_text(raw.get("engagement_type", ""), max_length=32).upper()
        or None,
        "intake_status": intake_status,
        "source": "llm",
        "llm_route": route,
        "model_provider": provider,
        "model": model,
        "created_at": datetime.now(UTC).isoformat(),
    }
    contract["ambiguity_score"] = _pm_ambiguity_score(contract, prompt)
    return _apply_pm_product_clarification_policy(
        contract=contract,
        prompt=prompt,
        requested_target_language=requested_target_language,
    )


def _normalize_mission_contract(
    raw: dict[str, Any],
    *,
    provider: str,
    model: str,
    route: str,
    mission_type: str,
    output_mode: str,
    requested_target_language: str | None,
) -> dict[str, Any]:
    valid_priorities = {"HIGH", "MEDIUM", "LOW"}
    valid_output_formats = {"standalone_script", "library", "service", "analysis_report", "patch"}
    normalized_output_format = _clean_text(
        raw.get("output_format", "standalone_script"), max_length=48
    ).lower()
    if normalized_output_format not in valid_output_formats:
        normalized_output_format = "standalone_script"

    requirements: list[dict[str, Any]] = []
    raw_requirements = raw.get("logicnode_requirements")
    if isinstance(raw_requirements, list):
        for item in raw_requirements[:12]:
            if not isinstance(item, dict):
                continue
            priority = _clean_text(item.get("priority", "MEDIUM"), max_length=16).upper()
            if priority not in valid_priorities:
                priority = "MEDIUM"
            requirements.append(
                {
                    "domain": _clean_text(item.get("domain", "generic"), max_length=64)
                    or "generic",
                    "concept": _clean_text(
                        item.get("concept", "primary_operation"), max_length=64
                    )
                    or "primary_operation",
                    "intent": _clean_text(item.get("intent", "Implement requested behavior")),
                    "priority": priority,
                }
            )
    if not requirements:
        requirements = [
            {
                "domain": "generic",
                "concept": "primary_operation",
                "intent": "Implement the requested mission behavior",
                "priority": "HIGH",
            }
        ]

    target_languages = _string_list(raw.get("target_languages"), limit=4, max_length=32)
    if not target_languages and requested_target_language:
        target_languages = [_clean_text(requested_target_language, max_length=32).lower()]

    acceptance_criteria = _string_list(raw.get("acceptance_criteria"), limit=6)
    if not acceptance_criteria:
        acceptance_criteria = ["Mission output satisfies the requested behavior."]

    return {
        "schema_version": "mission_contract.v1",
        "contract_summary": _clean_text(
            raw.get("contract_summary", "Mission contract generated."), max_length=240
        ),
        "mission_type": _clean_text(raw.get("mission_type", mission_type), max_length=48).upper(),
        "target_languages": target_languages,
        "output_mode": _clean_text(raw.get("output_mode", output_mode), max_length=48).upper(),
        "output_format": normalized_output_format,
        "required_domains": _string_list(raw.get("required_domains"), limit=10, max_length=64),
        "logicnode_requirements": requirements,
        "acceptance_criteria": acceptance_criteria,
        "risk_notes": _string_list(raw.get("risk_notes"), limit=5),
        "source": "llm",
        "llm_route": route,
        "model_provider": provider,
        "model": model,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _normalize_codegen_result(
    raw: dict[str, Any],
    *,
    specialist_agent_id: str,
    target_language: str,
    provider: str,
    model: str,
    route: str,
) -> dict[str, Any] | None:
    raw_generated_code = str(raw.get("generated_code", ""))
    generated_code = _strip_code_fences(raw_generated_code)
    from ..file_tree import codegen_bundle_from_result, first_filename

    generated_code, tree_files = codegen_bundle_from_result(raw, generated_code)
    if len(generated_code.strip()) < 10:
        return None
    language = _clean_text(raw.get("language", target_language), max_length=32).lower()
    filename = _safe_filename(
        raw.get("filename") or (first_filename(tree_files, "") if tree_files else ""),
        f"generated.{language or 'txt'}",
    )
    return {
        "schema_version": "generated_output.v1",
        "generated_code": generated_code,
        "filename": filename,
        "file_count": len(tree_files) if tree_files else 1,
        "files": [{"path": item["path"]} for item in tree_files],
        "language": language or target_language,
        "description": _clean_text(raw.get("description", "Generated output."), max_length=240),
        "dependencies": _string_list(raw.get("dependencies"), limit=20, max_length=80),
        "usage_example": _clean_text(raw.get("usage_example", ""), max_length=240),
        "source": "llm",
        "specialist_agent_id": specialist_agent_id,
        "llm_route": route,
        "model_provider": provider,
        "model": model,
        "generated_at": datetime.now(UTC).isoformat(),
        "code_length_chars": len(generated_code),
        "encoding_trace": {
            "codegen_normalization": {
                "raw": _code_text_trace(raw_generated_code),
                "normalized": _code_text_trace(generated_code),
                "stripped_code_fences": raw_generated_code != generated_code,
            }
        },
    }


def _normalize_logic_clusters(
    raw: dict[str, Any],
    *,
    provider: str,
    model: str,
    route: str,
    mission_contract: dict[str, Any],
    requested_target_language: str | None,
    ceo_delegation: dict[str, Any],
) -> dict[str, Any]:
    default_pod_manager = _normalize_agent_choice(
        ceo_delegation.get("pod_manager_agent_id"),
        allowed_ids=_VALID_POD_MANAGER_IDS,
        fallback=resolve_pod_manager_agent_id(requested_target_language),
    )
    default_specialist = _normalize_agent_choice(
        ceo_delegation.get("specialist_agent_id"),
        allowed_ids=_VALID_SPECIALIST_IDS,
        fallback=resolve_specialist_agent_id(requested_target_language),
    )
    raw_clusters = raw.get("clusters")
    if not isinstance(raw_clusters, list):
        raw_clusters = []
    clusters: list[dict[str, Any]] = []
    for item in raw_clusters[:8]:
        if not isinstance(item, dict):
            continue
        domain = _clean_text(item.get("domain") or item.get("title") or "general", max_length=64)
        cluster_index = len(clusters) + 1
        clusters.append(
            {
                "cluster_id": _clean_text(
                    item.get("cluster_id") or _cluster_id(cluster_index, domain),
                    max_length=80,
                ),
                "title": _clean_text(item.get("title") or domain, max_length=96),
                "domain": domain,
                "priority": _priority(item.get("priority")),
                "pod_manager_agent_id": _normalize_agent_choice(
                    item.get("pod_manager_agent_id"),
                    allowed_ids=_VALID_POD_MANAGER_IDS,
                    fallback=default_pod_manager,
                ),
                "specialist_agent_id": _normalize_agent_choice(
                    item.get("specialist_agent_id"),
                    allowed_ids=_VALID_SPECIALIST_IDS,
                    fallback=default_specialist,
                ),
                "requirement_refs": _string_list(item.get("requirement_refs"), limit=8),
                "depends_on": _string_list(item.get("depends_on"), limit=8, max_length=96),
                "rationale": _clean_text(
                    item.get("rationale") or "Grouped by related domain scope.",
                    max_length=240,
                ),
            }
        )
    if not clusters:
        return _fallback_logic_clusters(
            mission_contract=mission_contract,
            requested_target_language=requested_target_language,
            ceo_delegation=ceo_delegation,
            recommendation={"provider": provider, "model": model},
        )
    return {
        "schema_version": "logic_clusters.v1",
        "clusters": clusters,
        "source": "llm",
        "llm_route": route,
        "model_provider": provider,
        "model": model,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _normalize_pod_group_standard(
    raw: dict[str, Any],
    *,
    provider: str,
    model: str,
    route: str,
    pod_name: str,
    pod_manager_agent_id: str,
    mission_id: str,
    logicnodes: list[dict[str, Any]],
    mission_contract: dict[str, Any],
    source_code: str | None = None,
) -> dict[str, Any]:
    canonical: list[dict[str, Any]] = []
    raw_nodes = raw.get("canonical_logicnodes")
    if isinstance(raw_nodes, list):
        for item in raw_nodes[:20]:
            if not isinstance(item, dict):
                continue
            domain = _clean_text(item.get("domain") or "general", max_length=64)
            concept = _clean_text(item.get("concept") or "primary_operation", max_length=80)
            confidence = item.get("confidence")
            canonical.append(
                {
                    "standard_node_id": _clean_text(
                        item.get("standard_node_id")
                        or _standard_node_id(len(canonical) + 1, domain, concept),
                        max_length=96,
                    ),
                    "domain": domain,
                    "concept": concept,
                    "intent": _clean_text(
                        item.get("intent") or "Implement extracted mission behavior.",
                        max_length=180,
                    ),
                    "source_node_ids": _string_list(
                        item.get("source_node_ids"),
                        limit=20,
                        max_length=96,
                    ),
                    "languages": _string_list(item.get("languages"), limit=6, max_length=32),
                    "confidence": confidence if isinstance(confidence, (int, float)) else None,
                }
            )
    if not canonical:
        return _fallback_pod_group_standard(
            pod_name=pod_name,
            pod_manager_agent_id=pod_manager_agent_id,
            mission_id=mission_id,
            logicnodes=logicnodes,
            mission_contract=mission_contract,
            recommendation={"provider": provider, "model": model},
            source_code=source_code,
        )
    duplicate_count = raw.get("eliminated_duplicates")
    if not isinstance(duplicate_count, int) or duplicate_count < 0:
        duplicate_count = max(0, len(logicnodes) - len(canonical))
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
        "eliminated_duplicates": duplicate_count,
        "summary": _clean_text(
            raw.get("summary")
            or "Pod group standard consolidated from specialist LogicNodes.",
            max_length=260,
        ),
        "source": "llm",
        "llm_route": route,
        "model_provider": provider,
        "model": model,
        "created_at": datetime.now(UTC).isoformat(),
    }

