"""
llm_delegation — LLM provider delegation package.

This package was split out of the former 3,493-line ``llm_delegation.py``
monolith (issue #186).  The public API is re-exported here so that existing
``from orchestrator.llm_delegation import ...`` imports continue to resolve
unchanged.

Module map
----------
- ``config``     : environment-derived provider settings, ContextVars
                   (``current_mission_id`` / ``current_settings`` /
                   ``current_agent_id``), retry constants, token-usage
                   recording, and the shared agent-id validation sets.
- ``text``       : prompt-safety text scrubbing, JSON/decision extraction,
                   provider-response text extraction, and small formatting
                   helpers shared across prompts and fallbacks.
- ``health``     : provider health-sample ring buffer and the
                   ``get_provider_health_summary`` telemetry view.
- ``agents``     : agent persona resolution and per-agent LLM recommendations.
- ``providers``  : HTTP transport with retry/backoff and the per-provider
                   (OpenAI / Anthropic / Gemini) call + fallback chain.
- ``prompts``    : prompt-construction helpers (``_build_*`` functions).
- ``normalizers``: response-normalisation helpers (``_normalize_*``).
- ``fallbacks``  : deterministic offline fallbacks (``_fallback_*``).
- ``generators`` : high-level ``generate_*`` entry points plus
                   ``build_deploy_readiness_assessment``.
"""
from __future__ import annotations

# Re-exported transport modules so that tests which patch
# ``llm_delegation.httpx`` / ``llm_delegation.asyncio`` reach the live call
# sites in ``providers`` (which resolve them through the package — issue #186).
import asyncio  # noqa: F401

import httpx  # noqa: F401

from ..mission_flow import CEO_AGENT_ID
from .agents import (
    _agent_recommendation,
    _ceo_recommendation,
    _pm_recommendation,
    _resolve_agent,
    _system_prompt_for_agent,
)
from .config import (
    _LLM_MAX_RETRIES,
    _LLM_RETRY_BASE_SECONDS,
    _PROMPT_CONTEXT_MAX_BYTES,
    ANTHROPIC_API_KEY,
    ANTHROPIC_BASE_URL,
    ANTHROPIC_TIMEOUT_SECONDS,
    ANTHROPIC_VERSION,
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    GEMINI_TIMEOUT_SECONDS,
    LLM_SAFETY_BLOCK_ENABLED,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_TIMEOUT_SECONDS,
    PROMPT_GUARD_BLOCK_ENABLED,
    PROMPT_GUARD_BLOCK_LEVEL,
    _record_usage_event,
    current_agent_id,
    current_mission_id,
    current_settings,
)
from .fallbacks import (
    _fallback_codegen,
    _fallback_delegation,
    _fallback_integration_tests,
    _fallback_logic_clusters,
    _fallback_mission_contract,
    _fallback_pm_feature_contract,
    _fallback_pod_audit_verdict,
    _fallback_pod_group_standard,
    _fallback_pod_manager_delegation,
    _fallback_security_analysis,
    _fallback_specialist_plan,
    _fallback_vc_commit_strategy,
    _looks_like_boilerplate_plan,
    _plan_from_contract,
)
from .generators import (
    generate_ceo_delegation,
    generate_code_from_contract,
    generate_logic_clusters,
    generate_mission_contract,
    generate_pm_feature_contract,
    generate_pod_group_standard,
    generate_pod_manager_delegation,
    generate_specialist_plan,
)
from .generators_artifacts import (
    build_deploy_readiness_assessment,
    generate_compliance_assessment,
    generate_integration_tests,
    generate_master_logic_stream,
    generate_pm_delivery_summary,
    generate_pod_audit_verdict,
    generate_rqca_assessment,
    generate_security_analysis,
    generate_vc_commit_strategy,
)
from .health import (
    CIRCUIT_OPEN_SECONDS,
    CIRCUIT_OPEN_THRESHOLD,
    _provider_health_samples,
    _record_provider_health,
    get_circuit_state,
    get_provider_health_summary,
    is_circuit_open,
    record_failure,
    record_success,
    reset_circuit_breakers,
)
from .normalizers import (
    _normalize_codegen_result,
    _normalize_logic_clusters,
    _normalize_mission_contract,
    _normalize_pm_feature_contract,
    _normalize_pod_group_standard,
    _pod_standard_coverage_verdict,
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
    _call_anthropic,
    _call_gemini,
    _call_openai,
    _call_provider,
    _call_with_agent_system,
    _call_with_recommendation,
    _post_with_retry,
    _retry_delay_for_response,
    check_user_input,
)
from .text import (
    JSON_OBJECT_PATTERN,
    _clean_text,
    _cluster_id,
    _extract_anthropic_text,
    _extract_decision_payload,
    _extract_gemini_text,
    _extract_openai_text,
    _format_upstream_risks,
    _format_upstream_style,
    _language_context,
    _logicnode_languages,
    _logicnode_payload,
    _logicnode_sources,
    _logicnode_text,
    _normalize_agent_choice,
    _normalize_text_list,
    _pm_ambiguity_score,
    _pm_product_clarifying_questions,
    _priority,
    _safe_context_json,
    _safe_filename,
    _sanitize_context_value,
    _standard_node_id,
    _string_list,
    _strip_code_fences,
)

__all__ = [
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_TIMEOUT_SECONDS",
    "ANTHROPIC_VERSION",
    "CEO_AGENT_ID",
    "GEMINI_API_KEY",
    "GEMINI_BASE_URL",
    "GEMINI_TIMEOUT_SECONDS",
    "LLM_SAFETY_BLOCK_ENABLED",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_TIMEOUT_SECONDS",
    "PROMPT_GUARD_BLOCK_ENABLED",
    "PROMPT_GUARD_BLOCK_LEVEL",
    "build_deploy_readiness_assessment",
    "check_user_input",
    "current_agent_id",
    "current_mission_id",
    "current_settings",
    "generate_ceo_delegation",
    "generate_code_from_contract",
    "generate_compliance_assessment",
    "generate_integration_tests",
    "generate_logic_clusters",
    "generate_master_logic_stream",
    "generate_mission_contract",
    "generate_pm_delivery_summary",
    "generate_pm_feature_contract",
    "generate_pod_audit_verdict",
    "generate_pod_group_standard",
    "generate_pod_manager_delegation",
    "generate_rqca_assessment",
    "generate_security_analysis",
    "generate_specialist_plan",
    "generate_vc_commit_strategy",
    "get_circuit_state",
    "get_provider_health_summary",
    "is_circuit_open",
    "record_failure",
    "record_success",
    "reset_circuit_breakers",
    "CIRCUIT_OPEN_SECONDS",
    "CIRCUIT_OPEN_THRESHOLD",
]
