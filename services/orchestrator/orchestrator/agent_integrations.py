from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any, Final

from .agent_personas import build_agent_persona_profile
from .agent_registry import AGENT_REGISTRY, AgentDefinition

_MISSION_STATE_TOPICS: Final[tuple[str, ...]] = (
    "mission.state.queued",
    "mission.state.running",
    "mission.state.verified",
    "mission.state.complete",
    "mission.state.failed",
)
_POD_TOPICS: Final[dict[str, str]] = {
    "poda": "cluster.assigned.podA",
    "podb": "cluster.assigned.podB",
    "podc": "cluster.assigned.podC",
    "podd": "cluster.assigned.podD",
}
_LLM_PROFILES: Final[dict[str, dict[str, Any]]] = {
    "gemini_flash_high": {
        "provider": "gemini",
        "model": "gemini-3.5-flash",
        "mode": "thinking",
        "thinking_level": "high",
        "reason": (
            "Test default: route all agents to Gemini Flash 3.5 with high thinking "
            "for efficient, single-provider validation."
        ),
    },
    "openai_exec": {
        "provider": "openai",
        "model": "gpt-5.5",
        "mode": "thinking",
        "reasoning_effort": "high",
        "reason": "Best fit for deep orchestration and multi-step planning.",
    },
    "openai_instant_ops": {
        "provider": "openai",
        "model": "gpt-5.5",
        "mode": "thinking",
        "reasoning_effort": "low",
        "reason": (
            "Stable low-latency profile for high-frequency "
            "operational math and budgeting flows."
        ),
    },
    "openai_codegen": {
        "provider": "openai",
        "model": "gpt-5.5",
        "mode": "thinking",
        "reasoning_effort": "xhigh",
        "reason": "Best fit for long-horizon coding and agentic code changes.",
    },
    "openai_deep_audit": {
        "provider": "openai",
        "model": "gpt-5.5",
        "mode": "thinking",
        "reasoning_effort": "xhigh",
        "reason": "Highest-quality analysis for policy, security, and correctness audits.",
    },
    "openai_audit": {
        "provider": "openai",
        "model": "gpt-5.5",
        "mode": "thinking",
        "reasoning_effort": "high",
        "reason": "Strong quality with efficient latency for routine code and quality validation.",
    },
    "gemini_ops_fast": {
        "provider": "gemini",
        "model": "gemini-3.5-flash",
        "mode": "thinking",
        "thinking_level": "low",
        "fallback_provider": "openai",
        "fallback_model": "gpt-5.5",
        "reason": "Latest GA Flash model (Google I/O May 2026) — best throughput for high-volume operational and routing traffic.",
    },
    "gemini_ops_balanced": {
        "provider": "gemini",
        "model": "gemini-3.5-flash",
        "mode": "thinking",
        "thinking_level": "medium",
        "fallback_provider": "openai",
        "fallback_model": "gpt-5.5",
        "reason": "Latest GA Flash model (Google I/O May 2026) — balanced quality/speed for delivery and release coordination.",
    },
    "gemini_stem": {
        "provider": "gemini",
        "model": "gemini-3.5-flash",
        "mode": "thinking",
        "thinking_level": "high",
        "fallback_provider": "openai",
        "fallback_model": "gpt-5.5",
        "reason": "GA Flash model (Google I/O May 2026) — strong technical and mathematical reasoning at lower latency than pro-preview.",
    },
    "gemini_knowledge": {
        "provider": "gemini",
        "model": "gemini-3.5-flash",
        "mode": "thinking",
        "thinking_level": "high",
        "fallback_provider": "openai",
        "fallback_model": "gpt-5.5",
        "reason": "GA Flash model (Google I/O May 2026) — large-context knowledge indexing, retrieval, and synthesis.",
    },
}
_AGENT_LLM_PROFILE_MAP: Final[dict[str, str]] = {
    "AGENT-01-PM": "openai_exec",
    "AGENT-02-CEO": "openai_exec",
    "AGENT-03-BROKER": "gemini_ops_fast",
    "AGENT-04-ACCOUNTANT": "openai_instant_ops",
    "AGENT-05-SECURITY": "openai_deep_audit",
    "AGENT-06-IS": "gemini_knowledge",
    "AGENT-07-VC": "openai_codegen",
    "AGENT-08-COMPLIANCE": "openai_deep_audit",
    "AGENT-09-HW": "gemini_stem",
    "AGENT-10-TESTER": "openai_codegen",
    "AGENT-11-DEPLOY": "gemini_ops_balanced",
    "AGENT-12-PODA-MGR": "openai_exec",
    "AGENT-13-PODA-AUDIT": "openai_audit",
    "AGENT-14-PYTHON": "openai_codegen",
    "AGENT-15-JAVASCRIPT": "openai_codegen",
    "AGENT-16-RUBY": "openai_codegen",
    "AGENT-17-PHP": "openai_codegen",
    "AGENT-18-PODB-MGR": "openai_exec",
    "AGENT-19-PODB-AUDIT": "openai_audit",
    "AGENT-20-C": "openai_codegen",
    "AGENT-21-CPP": "openai_codegen",
    "AGENT-22-RUST": "openai_codegen",
    "AGENT-23-ZIG": "openai_codegen",
    "AGENT-24-PODC-MGR": "openai_exec",
    "AGENT-25-PODC-AUDIT": "openai_audit",
    "AGENT-26-JAVA": "openai_codegen",
    "AGENT-27-CSHARP": "openai_codegen",
    "AGENT-28-SCALA": "openai_codegen",
    "AGENT-29-KOTLIN": "openai_codegen",
    "AGENT-30-PODD-MGR": "gemini_stem",
    "AGENT-31-PODD-AUDIT": "gemini_stem",
    "AGENT-32-MATLAB": "gemini_stem",
    "AGENT-33-R": "gemini_stem",
    "AGENT-34-JULIA": "gemini_stem",
    "AGENT-35-MATHEMATICA": "gemini_stem",
    "AGENT-36-GO": "openai_codegen",
    "AGENT-37-HASKELL": "gemini_stem",
    "AGENT-38-OCAML": "gemini_stem",
    "AGENT-39-DEPABS": "openai_codegen",
    "AGENT-40-TESTDATA": "gemini_ops_fast",
    "AGENT-41-RQCA": "openai_audit",
}


def _normalize_pod_key(value: str) -> str:
    return value.strip().lower().replace(" ", "")


def _pod_topic(agent: AgentDefinition) -> str | None:
    return _POD_TOPICS.get(_normalize_pod_key(agent.pod))


def _protocols_for_agent(agent: AgentDefinition) -> list[str]:
    if agent.category == "interface":
        return ["alpha", "omega", "rho"]
    if agent.category == "executive":
        return ["alpha", "beta", "delta", "omega", "rho", "sigma"]
    if agent.category == "support":
        if agent.short_code == "BROKER":
            return ["omega", "rho"]
        if agent.short_code == "IS":
            return ["omega", "rho", "sigma"]
        return ["omega", "rho", "sigma"]
    if agent.category == "pod_manager":
        return ["alpha", "beta", "delta", "rho"]
    if agent.category == "pod_audit":
        return ["delta", "sigma", "rho"]
    if agent.category == "specialist":
        return ["beta", "delta", "sigma", "rho"]
    return ["rho"]


def _topic_bindings_for_agent(agent: AgentDefinition) -> dict[str, list[str]]:
    consume: set[str] = set()
    publish: set[str] = {"agent.heartbeat", "agent.state.changed"}
    pod_topic = _pod_topic(agent)

    if agent.category == "interface":
        consume.update(_MISSION_STATE_TOPICS)
    elif agent.category == "executive":
        consume.update(_MISSION_STATE_TOPICS)
        consume.update({"artifact.rir.verified", "artifact.rir.rejected", "pod.standard.ready"})
        publish.update(
            {
                "fusion.requested",
                "cluster.assigned.podA",
                "cluster.assigned.podB",
                "cluster.assigned.podC",
                "cluster.assigned.podD",
            }
        )
    elif agent.category == "support":
        consume.update(_MISSION_STATE_TOPICS)
        if agent.short_code == "BROKER":
            publish.add("incident.runtime.errorlog")
        elif agent.short_code == "TESTER":
            consume.update(
                {"artifact.rir.verified", "artifact.rir.rejected", "mission.state.verified"}
            )
            publish.add("incident.runtime.errorlog")
        elif agent.short_code == "DEPLOY":
            consume.update({"mission.state.complete", "pod.standard.ready"})
        elif agent.short_code == "HW":
            consume.add("cluster.assigned.podB")
        elif agent.short_code == "IS":
            consume.update({"artifact.rir.verified", "pod.standard.ready"})
        elif agent.short_code == "DEPABS":
            consume.update({"artifact.rir.submitted", "mission.state.running"})
            publish.update(
                {
                    "dependency.absorption.plan",
                    "dependency.absorption.report",
                    "dependency.sbom.delta",
                }
            )
        elif agent.short_code == "TESTDATA":
            consume.update(_MISSION_STATE_TOPICS)
            publish.update({"test.environment.ready", "test.environment.torn_down"})
        elif agent.short_code == "RQCA":
            consume.update({"mission.state.verified", "mission.state.complete"})
            publish.update({"runtime.qc.report", "runtime.qc.verdict"})
    elif agent.category == "pod_manager":
        if pod_topic:
            consume.add(pod_topic)
        consume.update({"artifact.rir.verified", "artifact.rir.rejected"})
        publish.update({"fusion.requested", "pod.standard.ready"})
    elif agent.category == "pod_audit":
        if pod_topic:
            consume.add(pod_topic)
        consume.add("artifact.rir.submitted")
        publish.update({"artifact.rir.verified", "artifact.rir.rejected"})
    elif agent.category == "specialist":
        if pod_topic:
            consume.add(pod_topic)
        consume.add("mission.state.running")
        publish.add("artifact.rir.submitted")

    return {
        "publish": sorted(publish),
        "consume": sorted(consume),
    }


def _store_bindings_for_agent(agent: AgentDefinition) -> list[dict[str, Any]]:
    stores: list[dict[str, Any]] = [
        {
            "name": "redis",
            "status": "implemented",
            "usage": [
                "protocol bus pub/sub and stream transport",
                "idempotency/cache primitives",
            ],
        },
        {
            "name": "postgresql",
            "status": "implemented",
            "usage": [
                "mission state and event timeline",
                "agent telemetry and operational records",
            ],
        },
    ]

    if agent.category in {"specialist", "pod_manager", "pod_audit"} or agent.short_code == "IS":
        stores.append(
            {
                "name": "qdrant",
                "status": "implemented",
                "usage": [
                    "vector-backed knowledge retrieval for refinement and validation",
                ],
            }
        )
        stores.append(
            {
                "name": "milvus",
                "status": "feature_flagged",
                "usage": [
                    "alternate Knowledge Lake vector storage for retrieval and indexing",
                ],
            }
        )

    if agent.short_code in {"IS", "SECURITY", "COMPLIANCE"} or agent.category == "pod_audit":
        stores.append(
            {
                "name": "neo4j",
                "status": "feature_flagged",
                "usage": [
                    "knowledge graph traversal",
                    "compliance and provenance relationship analysis",
                ],
            }
        )

    new_artifact_agents = {"VC", "DEPLOY", "TESTER", "DEPABS", "TESTDATA", "RQCA"}
    if agent.short_code in new_artifact_agents or agent.category in {"pod_manager", "pod_audit"}:
        stores.append(
            {
                "name": "object_storage",
                "status": "feature_flagged",
                "usage": [
                    "large artifact retention for binaries, bundles, and audit evidence",
                ],
            }
        )

    return stores


def _llm_recommendation_for_agent(agent: AgentDefinition) -> dict[str, Any]:
    import os
    try:
        from .llm_delegation.config import current_vault_secrets
        vault = current_vault_secrets.get() or {}
    except Exception:
        vault = {}

    openai_key = vault.get("openai_api_key") or os.getenv("OPENAI_API_KEY", "").strip()
    gemini_key = vault.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "").strip()

    llm_provider = os.getenv("LLM_PROVIDER", "").strip().lower()

    if llm_provider == "openai":
        use_openai = True
    elif llm_provider == "gemini":
        use_openai = False
    else:
        if openai_key and not gemini_key:
            use_openai = True
        else:
            use_openai = False

    if use_openai:
        profile_key = _AGENT_LLM_PROFILE_MAP.get(agent.agent_id, "openai_exec")
        if profile_key.startswith("gemini_"):
            mapping = {
                "gemini_ops_fast": "openai_instant_ops",
                "gemini_ops_balanced": "openai_exec",
                "gemini_stem": "openai_codegen",
                "gemini_knowledge": "openai_deep_audit",
                "gemini_flash_high": "openai_exec",
            }
            profile_key = mapping.get(profile_key, "openai_exec")
    else:
        profile_key = _AGENT_LLM_PROFILE_MAP.get(agent.agent_id, "gemini_flash_high")
        if profile_key.startswith("openai_") and not openai_key:
            profile_key = "gemini_flash_high"

    profile = _LLM_PROFILES.get(profile_key, _LLM_PROFILES["gemini_flash_high"])
    recommendation = dict(profile)
    recommendation["profile"] = profile_key
    recommendation["rank"] = "primary"

    if recommendation.get("provider") == "openai" and recommendation.get("model") == "gpt-5.5":
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4o").strip()
        if openai_model == "gpt-5.5" or not openai_model:
            openai_model = "gpt-4o"
        recommendation["model"] = openai_model

    if recommendation.get("fallback_provider") == "openai" and recommendation.get("fallback_model") == "gpt-5.5":
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4o").strip()
        if openai_model == "gpt-5.5" or not openai_model:
            openai_model = "gpt-4o"
        recommendation["fallback_model"] = openai_model

    return recommendation


def build_agent_integration_record(agent: AgentDefinition) -> dict[str, Any]:
    topic_bindings = _topic_bindings_for_agent(agent)
    protocols = _protocols_for_agent(agent)
    data_systems = _store_bindings_for_agent(agent)
    llm_recommendation = _llm_recommendation_for_agent(agent)
    return {
        "index": agent.index,
        "agent_id": agent.agent_id,
        "short_code": agent.short_code,
        "name": agent.name,
        "tier": agent.tier,
        "pod": agent.pod,
        "role": agent.role,
        "category": agent.category,
        "specialties": list(agent.specialties),
        "protocols": protocols,
        "protocol_bus": {
            "publish_topics": topic_bindings["publish"],
            "consume_topics": topic_bindings["consume"],
        },
        "data_systems": data_systems,
        "llm_recommendation": llm_recommendation,
        "persona_profile": build_agent_persona_profile(
            agent,
            protocols=protocols,
            llm_recommendation=llm_recommendation,
            data_systems=data_systems,
        ),
    }


def build_agent_integrations_snapshot() -> dict[str, Any]:
    records = [build_agent_integration_record(agent) for agent in AGENT_REGISTRY]
    protocols = sorted({protocol for record in records for protocol in record["protocols"]})
    stores = sorted(
        {
            store["name"]
            for record in records
            for store in record["data_systems"]
            if isinstance(store, dict) and isinstance(store.get("name"), str)
        }
    )
    provider_counts: Counter[str] = Counter()
    model_counts: Counter[str] = Counter()
    for record in records:
        recommendation = record.get("llm_recommendation")
        if not isinstance(recommendation, dict):
            continue
        provider = recommendation.get("provider")
        model = recommendation.get("model")
        if isinstance(provider, str) and provider:
            provider_counts[provider] += 1
        if isinstance(model, str) and model:
            model_counts[model] += 1

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_agents": len(records),
        "persona_profile_framework": "8-part-v1",
        "persona_profile_sections": [
            "job_role",
            "education_certifications",
            "traits_skills",
            "methods_procedures",
            "tools",
            "master_instruction",
            "protocol",
            "api_configuration",
        ],
        "persona_profile_extensions": ["standards_alignment", "evidence_sources"],
        "standards_evidence_last_verified": "2026-03-02",
        "protocols": protocols,
        "data_systems": stores,
        "implemented_data_plane": ["postgresql", "qdrant", "redis"],
        "reserved_data_plane": [],
        "feature_flagged_data_plane": ["milvus", "neo4j", "object_storage"],
        "planned_data_plane": [],
        "llm_strategy_version": "2026-03-02",
        "llm_provider_counts": dict(sorted(provider_counts.items())),
        "llm_model_counts": dict(sorted(model_counts.items())),
        "agents": records,
    }
