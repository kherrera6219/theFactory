from __future__ import annotations

import importlib
import logging
from typing import Any

from ..mission_flow import (
    CEO_AGENT_ID,
    resolve_pod_manager_agent_id,
    resolve_specialist_agent_id,
)
from .config import _VALID_POD_MANAGER_IDS, _VALID_SPECIALIST_IDS
from .fallbacks import (
    _fallback_codegen,
    _fallback_delegation,
    _fallback_logic_clusters,
    _fallback_mission_contract,
    _fallback_pm_feature_contract,
    _fallback_pod_group_standard,
    _fallback_pod_manager_delegation,
    _fallback_specialist_plan,
)
from .normalizers import (
    _normalize_codegen_result,
    _normalize_logic_clusters,
    _normalize_mission_contract,
    _normalize_pm_feature_contract,
    _normalize_pod_group_standard,
)
from .prompts import (
    _build_codegen_prompt,
    _build_logic_clusters_prompt,
    _build_mission_contract_prompt,
    _build_pm_feature_contract_prompt,
    _build_pod_group_standard_prompt,
    _build_pod_manager_prompt,
    _build_prompt,
    _build_specialist_prompt,
)
from .providers import (
    _call_with_agent_system,
)
from .text import (
    _clean_text,
    _normalize_agent_choice,
    _normalize_text_list,
)

LOGGER = logging.getLogger(__name__)


def _pkg() -> Any:
    """Return the public ``llm_delegation`` package module.

    The recommendation and provider-call helpers are resolved through this
    accessor so that tests which ``monkeypatch.setattr`` them on the package
    namespace still affect these call sites after the monolith was split into
    this package (issue #186).
    """
    return importlib.import_module(__package__)

async def generate_pm_feature_contract(
    *,
    prompt: str,
    mission_type: str,
    depth_mode: str,
    output_mode: str,
    requested_target_language: str | None,
    attachments: list[dict[str, Any]] | None = None,
    global_style_directives: list[str] | None = None,
    source_code: str | None = None,
    conversation_context: dict[str, Any] | None = None,
    user_intent: str | None = None,
) -> dict[str, Any]:
    recommendation = _pkg()._pm_recommendation()
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.6-flash")).strip()

    # OWASP LLM01 — scan the operator-supplied mission description (and any
    # attached file content) before it is embedded in the prompt. On a blocked
    # injection, fall back to the deterministic contract instead of delegating.
    attachment_text = "\n".join(
        str(item.get("content", ""))
        for item in (attachments or [])
        if isinstance(item, dict)
    )
    context_text = str(conversation_context or "")
    if not _pkg().check_user_input(
        f"{prompt}\n{attachment_text}\n{context_text[:4000]}",
        "pm feature contract",
    ):
        return _fallback_pm_feature_contract(
            prompt=prompt,
            mission_type=mission_type,
            requested_target_language=requested_target_language,
            recommendation=recommendation,
        )
    pm_prompt = _build_pm_feature_contract_prompt(
        prompt=prompt,
        mission_type=mission_type,
        depth_mode=depth_mode,
        output_mode=output_mode,
        requested_target_language=requested_target_language,
        recommended_provider=provider,
        recommended_model=model,
        attachments=attachments,
        global_style_directives=global_style_directives,
        source_code=source_code,
        conversation_context=conversation_context,
        user_intent=user_intent,
    )
    parsed, resolved_provider, resolved_model, llm_route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=pm_prompt,
        call_context="pm feature contract",
        agent_id="AGENT-01-PM",
    )
    if not isinstance(parsed, dict):
        return _fallback_pm_feature_contract(
            prompt=prompt,
            mission_type=mission_type,
            requested_target_language=requested_target_language,
            recommendation=recommendation,
        )
    ambiguity_prompt = prompt
    if conversation_context:
        ambiguity_prompt = f"{prompt}\n{context_text[:3000]}"
    normalized = _normalize_pm_feature_contract(
        parsed,
        provider=resolved_provider,
        model=resolved_model,
        route=llm_route,
        prompt=ambiguity_prompt,
        requested_target_language=requested_target_language,
    )
    if str(user_intent or "").strip().lower() == "finalize_plan":
        normalized["intake_status"] = "ready"
        normalized["ambiguity_score"] = min(float(normalized.get("ambiguity_score", 0.0)), 0.35)
    return normalized


async def generate_pod_group_standard(
    *,
    pod_name: str,
    pod_manager_agent_id: str,
    mission_id: str,
    logicnodes: list[dict[str, Any]],
    mission_contract: dict[str, Any],
    source_code: str | None = None,
) -> dict[str, Any]:
    normalized_pod_manager_agent_id = pod_manager_agent_id.strip().upper()
    recommendation = _pkg()._agent_recommendation(normalized_pod_manager_agent_id)
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.6-flash")).strip()

    prompt = _build_pod_group_standard_prompt(
        pod_name=pod_name,
        pod_manager_agent_id=normalized_pod_manager_agent_id,
        mission_id=mission_id,
        logicnodes=logicnodes,
        mission_contract=mission_contract,
        recommended_provider=provider,
        recommended_model=model,
        source_code=source_code,
    )
    parsed, resolved_provider, resolved_model, llm_route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="pod group standard consolidation",
        agent_id=normalized_pod_manager_agent_id,
    )
    if not isinstance(parsed, dict):
        return _fallback_pod_group_standard(
            pod_name=pod_name,
            pod_manager_agent_id=normalized_pod_manager_agent_id,
            mission_id=mission_id,
            logicnodes=logicnodes,
            mission_contract=mission_contract,
            recommendation=recommendation,
            source_code=source_code,
        )
    return _normalize_pod_group_standard(
        parsed,
        provider=resolved_provider,
        model=resolved_model,
        route=llm_route,
        pod_name=pod_name,
        pod_manager_agent_id=normalized_pod_manager_agent_id,
        mission_id=mission_id,
        logicnodes=logicnodes,
        mission_contract=mission_contract,
        source_code=source_code,
    )


async def generate_code_from_contract(
    *,
    mission_context: dict[str, Any],
    specialist_agent_id: str,
    mission_contract: dict[str, Any],
    logicnodes: list[dict[str, Any]] | None,
    target_language: str,
) -> dict[str, Any]:
    recommendation = _pkg()._agent_recommendation(specialist_agent_id)
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.6-flash")).strip()

    prompt = _build_codegen_prompt(
        mission_context=mission_context,
        mission_contract=mission_contract,
        logicnodes=logicnodes or [],
        target_language=target_language,
        specialist_agent_id=specialist_agent_id,
        recommended_provider=provider,
        recommended_model=model,
    )
    parsed, resolved_provider, resolved_model, llm_route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context=f"specialist codegen {specialist_agent_id}",
        agent_id=specialist_agent_id,
    )
    contract_summary = str(mission_contract.get("contract_summary", "mission"))
    if not isinstance(parsed, dict):
        return _fallback_codegen(
            specialist_agent_id=specialist_agent_id,
            target_language=target_language,
            contract_summary=contract_summary,
            recommendation=recommendation,
        )
    normalized = _normalize_codegen_result(
        parsed,
        specialist_agent_id=specialist_agent_id,
        target_language=target_language,
        provider=resolved_provider,
        model=resolved_model,
        route=llm_route,
    )
    if normalized is None:
        return _fallback_codegen(
            specialist_agent_id=specialist_agent_id,
            target_language=target_language,
            contract_summary=contract_summary,
            recommendation=recommendation,
        )
    return normalized


async def generate_logic_clusters(
    *,
    mission_context: dict[str, Any],
    mission_contract: dict[str, Any],
    requested_target_language: str | None,
    ceo_delegation: dict[str, Any],
) -> dict[str, Any]:
    recommendation = _pkg()._ceo_recommendation()
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.6-flash")).strip()

    prompt = _build_logic_clusters_prompt(
        mission_context=mission_context,
        mission_contract=mission_contract,
        ceo_delegation=ceo_delegation,
        requested_target_language=requested_target_language,
        recommended_provider=provider,
        recommended_model=model,
    )
    parsed, resolved_provider, resolved_model, llm_route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="logic cluster decomposition",
        agent_id=CEO_AGENT_ID,
    )
    if not isinstance(parsed, dict):
        return _fallback_logic_clusters(
            mission_contract=mission_contract,
            requested_target_language=requested_target_language,
            ceo_delegation=ceo_delegation,
            recommendation=recommendation,
        )
    return _normalize_logic_clusters(
        parsed,
        provider=resolved_provider,
        model=resolved_model,
        route=llm_route,
        mission_contract=mission_contract,
        requested_target_language=requested_target_language,
        ceo_delegation=ceo_delegation,
    )


async def generate_mission_contract(
    *,
    mission_context: dict[str, Any],
    prompt: str,
    mission_type: str,
    output_mode: str,
    requested_target_language: str | None,
    ceo_delegation: dict[str, Any],
) -> dict[str, Any]:
    recommendation = _pkg()._ceo_recommendation()
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.6-flash")).strip()

    contract_prompt = _build_mission_contract_prompt(
        mission_context=mission_context,
        prompt=prompt,
        mission_type=mission_type,
        output_mode=output_mode,
        requested_target_language=requested_target_language,
        ceo_delegation=ceo_delegation,
        recommended_provider=provider,
        recommended_model=model,
    )
    parsed, resolved_provider, resolved_model, llm_route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=contract_prompt,
        call_context="mission contract",
        agent_id=CEO_AGENT_ID,
    )
    if not isinstance(parsed, dict):
        return _fallback_mission_contract(
            prompt=prompt,
            mission_type=mission_type,
            output_mode=output_mode,
            requested_target_language=requested_target_language,
            recommendation=recommendation,
        )
    return _normalize_mission_contract(
        parsed,
        provider=resolved_provider,
        model=resolved_model,
        route=llm_route,
        mission_type=mission_type,
        output_mode=output_mode,
        requested_target_language=requested_target_language,
    )


async def generate_ceo_delegation(
    *,
    mission_context: dict[str, Any],
    requested_target_language: str | None,
) -> dict[str, Any]:
    recommendation = _pkg()._ceo_recommendation()
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.6-flash")).strip()

    prompt = _build_prompt(
        mission_context=mission_context,
        recommended_provider=provider,
        recommended_model=model,
    )

    parsed, resolved_provider, resolved_model, llm_route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="ceo delegation",
        agent_id=CEO_AGENT_ID,
    )

    if not isinstance(parsed, dict):
        return _fallback_delegation(
            requested_target_language=requested_target_language,
            mission_context=mission_context,
            recommendation=recommendation,
        )

    pod_manager_fallback = resolve_pod_manager_agent_id(requested_target_language)
    specialist_fallback = resolve_specialist_agent_id(requested_target_language)
    pod_manager_agent_id = _normalize_agent_choice(
        parsed.get("pod_manager_agent_id"),
        allowed_ids=_VALID_POD_MANAGER_IDS,
        fallback=pod_manager_fallback,
    )
    specialist_agent_id = _normalize_agent_choice(
        parsed.get("specialist_agent_id"),
        allowed_ids=_VALID_SPECIALIST_IDS,
        fallback=specialist_fallback,
    )
    if pod_manager_agent_id != pod_manager_fallback:
        pod_manager_agent_id = pod_manager_fallback
    return {
        "pod_manager_agent_id": pod_manager_agent_id,
        "specialist_agent_id": specialist_agent_id,
        "rationale": _clean_text(
            parsed.get("rationale", "Delegation synthesized from mission context."),
            max_length=240,
        ),
        "source": "llm",
        "llm_route": llm_route,
        "model_provider": resolved_provider,
        "model": resolved_model,
        "mission_context": mission_context,
    }


async def generate_pod_manager_delegation(
    *,
    mission_context: dict[str, Any],
    requested_target_language: str | None,
    pod_manager_agent_id: str,
    default_specialist_agent_id: str | None = None,
) -> dict[str, Any]:
    normalized_pod_manager_agent_id = pod_manager_agent_id.strip().upper()
    fallback_specialist = (
        default_specialist_agent_id.strip().upper()
        if isinstance(default_specialist_agent_id, str) and default_specialist_agent_id.strip()
        else resolve_specialist_agent_id(requested_target_language)
    )

    recommendation = _pkg()._agent_recommendation(normalized_pod_manager_agent_id)
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.6-flash")).strip()

    prompt = _build_pod_manager_prompt(
        mission_context=mission_context,
        pod_manager_agent_id=normalized_pod_manager_agent_id,
        default_specialist_agent_id=fallback_specialist,
        recommended_provider=provider,
        recommended_model=model,
    )

    parsed, resolved_provider, resolved_model, llm_route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="pod-manager delegation",
        agent_id=normalized_pod_manager_agent_id,
    )
    if not isinstance(parsed, dict):
        return _fallback_pod_manager_delegation(
            pod_manager_agent_id=normalized_pod_manager_agent_id,
            specialist_agent_id=fallback_specialist,
            mission_context=mission_context,
            recommendation=recommendation,
        )

    specialist_agent_id = _normalize_agent_choice(
        parsed.get("specialist_agent_id"),
        allowed_ids=_VALID_SPECIALIST_IDS,
        fallback=fallback_specialist,
    )

    return {
        "pod_manager_agent_id": normalized_pod_manager_agent_id,
        "specialist_agent_id": specialist_agent_id,
        "rationale": _clean_text(
            parsed.get(
                "rationale",
                "Pod manager confirmed specialist routing from mission context.",
            ),
            max_length=240,
        ),
        "source": "llm",
        "llm_route": llm_route,
        "model_provider": resolved_provider,
        "model": resolved_model,
        "mission_context": mission_context,
    }


async def generate_specialist_plan(
    *,
    mission_context: dict[str, Any],
    requested_target_language: str | None,
    specialist_agent_id: str,
    pod_manager_agent_id: str,
) -> dict[str, Any]:
    normalized_specialist_agent_id = specialist_agent_id.strip().upper()
    if not normalized_specialist_agent_id:
        normalized_specialist_agent_id = resolve_specialist_agent_id(requested_target_language)

    normalized_pod_manager_agent_id = pod_manager_agent_id.strip().upper()
    if not normalized_pod_manager_agent_id:
        normalized_pod_manager_agent_id = resolve_pod_manager_agent_id(requested_target_language)

    recommendation = _pkg()._agent_recommendation(normalized_specialist_agent_id)
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.6-flash")).strip()

    prompt = _build_specialist_prompt(
        mission_context=mission_context,
        specialist_agent_id=normalized_specialist_agent_id,
        pod_manager_agent_id=normalized_pod_manager_agent_id,
        recommended_provider=provider,
        recommended_model=model,
    )

    parsed, resolved_provider, resolved_model, llm_route = await _call_with_agent_system(
        recommendation=recommendation,
        prompt=prompt,
        call_context="specialist planning",
        agent_id=normalized_specialist_agent_id,
    )
    if not isinstance(parsed, dict):
        return _fallback_specialist_plan(
            specialist_agent_id=normalized_specialist_agent_id,
            pod_manager_agent_id=normalized_pod_manager_agent_id,
            mission_context=mission_context,
            recommendation=recommendation,
        )

    plan_summary = _clean_text(parsed.get("plan_summary", ""), max_length=280)
    if not plan_summary:
        plan_summary = "Specialist execution plan generated from mission context."

    deliverables = _normalize_text_list(parsed.get("deliverables"), limit=6)
    if not deliverables:
        deliverables = [
            "Produce implementation changes for the assigned mission scope.",
            "Persist logicnode evidence and audit artifacts before completion.",
        ]

    risk_notes = _normalize_text_list(parsed.get("risk_notes"), limit=6)
    if not risk_notes:
        risk_notes = ["No explicit risks returned by model output."]

    return {
        "specialist_agent_id": normalized_specialist_agent_id,
        "pod_manager_agent_id": normalized_pod_manager_agent_id,
        "plan_summary": plan_summary,
        "deliverables": deliverables,
        "risk_notes": risk_notes,
        "source": "llm",
        "llm_route": llm_route,
        "model_provider": resolved_provider,
        "model": resolved_model,
        "mission_context": mission_context,
    }

