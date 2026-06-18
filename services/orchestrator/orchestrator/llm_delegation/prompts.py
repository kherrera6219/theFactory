from __future__ import annotations

import json
from typing import Any

from ..hw_agent import build_hw_context_block
from .text import (
    _clean_text,
    _format_knowledge_context,
    _format_upstream_risks,
    _format_upstream_style,
    _language_context,
    _safe_context_json,
    _string_list,
)


def _build_prompt(
    *,
    mission_context: dict[str, Any],
    recommended_provider: str,
    recommended_model: str,
) -> str:
    mission_type = str(mission_context.get("mission_type") or "BUILD_NEW").strip().upper()
    language = str(mission_context.get("requested_target_language") or "auto").strip().lower()
    feature_contract = mission_context.get("feature_contract")
    complexity = ""
    if isinstance(feature_contract, dict):
        complexity = str(feature_contract.get("estimated_complexity") or "").strip().lower()
    type_strategy = {
        "BUILD_NEW": (
            "Select the pod whose language specialist has the strongest code generation "
            "capability for the requested language."
        ),
        "DEBUG_REPAIR": (
            "Select the pod whose specialist has the deepest static analysis and "
            "fault-isolation capability for the source language."
        ),
        "SECURITY_HARDEN": (
            "Select the pod whose specialist understands security-sensitive patterns. "
            "Flag Security and Compliance agents before COMPLETE."
        ),
        "PORT": (
            "This is a PORT mission. It MUST produce exactly two logic clusters:\n"
            "  Cluster 1 (EXTRACTION): domain=source_extraction, priority=HIGH.\n"
            "    Assigned to the SOURCE language pod manager and specialist.\n"
            "    Purpose: extract intent and LogicNodes from the original source.\n"
            "  Cluster 2 (GENERATION): domain=target_generation, priority=MEDIUM.\n"
            "    Assigned to the TARGET language pod manager and specialist.\n"
            "    depends_on: [Cluster 1 title].\n"
            "    Purpose: generate target-language implementation from extracted intent.\n"
            "Identify source and target language from the prompt. "
            "Assign each cluster to the CORRECT pod."
        ),
        "REDUCE_DEPENDENCIES": (
            "Select the pod whose specialist can identify import-level intent and "
            "generate replacement code. Flag DEPABS requirements."
        ),
        "IMPORT_MODERNIZE": (
            "Select the pod whose specialist understands legacy patterns in the "
            "source language. Modernization requires extraction and generation."
        ),
        "ANALYZE_ONLY": (
            "Select the pod whose specialist can produce the richest LogicNode "
            "coverage. No code generation is required."
        ),
    }
    strategy = type_strategy.get(mission_type, type_strategy["BUILD_NEW"])
    complexity_note = (
        " High-complexity mission: consider multiple clusters and parallel pod ownership."
        if complexity in {"high", "very_high"}
        else ""
    )

    risk_assessment = mission_context.get("risk_assessment") or {}
    risk_score = float(risk_assessment.get("risk_score", 0.0))
    risk_note = ""
    if risk_score > 0.6:
        risk_note = f"\nATTENTION: High risk mission (score {risk_score}). Prioritize pods with strong security/audit specialists and plan for rigorous verification cycles."

    style_directives = mission_context.get("global_style_directives") or []
    style_note = ""
    if style_directives:
        style_note = f"\nTEAM STYLE DIRECTIVES: {'; '.join(style_directives)}. Ensure these are propagated to all assigned pod managers and specialists."

    return (
        "You are AGENT-02-CEO in a strict chain-of-command runtime. Act as a strategic executive.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Return only JSON with keys: pod_manager_agent_id, specialist_agent_id, rationale.\n\n"
        f"Mission type: {mission_type}\n"
        f"Target language: {language}\n"
        f"Strategic guidance: {strategy}{complexity_note}{risk_note}{style_note}\n\n"
        "Your rationale must explain why this pod, why this specialist, and any "
        "cross-pod or support-agent dependencies flagged by mission type.\n\n"
        "Mission context JSON:\n"
        f"{_safe_context_json(mission_context)}\n"
        "Valid pod manager ids: AGENT-12-PODA-MGR, AGENT-18-PODB-MGR, "
        "AGENT-24-PODC-MGR, AGENT-30-PODD-MGR."
    )


def _build_pod_manager_prompt(
    *,
    mission_context: dict[str, Any],
    pod_manager_agent_id: str,
    default_specialist_agent_id: str,
    recommended_provider: str,
    recommended_model: str,
) -> str:
    pod_family_strategy = {
        "AGENT-12-PODA-MGR": (
            "Pod A owns dynamic language execution. Prioritize runtime ergonomics, "
            "package boundaries, async behavior, and scripting surface clarity."
        ),
        "AGENT-18-PODB-MGR": (
            "Pod B owns systems language execution. Prioritize memory safety, "
            "concurrency, compile-time contracts, and dependency minimization."
        ),
        "AGENT-24-PODC-MGR": (
            "Pod C owns JVM and enterprise language execution. Prioritize layered "
            "architecture, type contracts, build tooling, and operational stability."
        ),
        "AGENT-30-PODD-MGR": (
            "Pod D owns functional and data-oriented language execution. Prioritize "
            "pure transformations, schema boundaries, pipeline semantics, and proofability."
        ),
    }
    mission_type = str(mission_context.get("mission_type") or "BUILD_NEW").strip().upper()
    strategy = pod_family_strategy.get(
        pod_manager_agent_id.strip().upper(),
        "Use pod-family expertise to select the specialist with the strongest mission fit.",
    )
    risk_context = _format_upstream_risks(mission_context)
    style_context = _format_upstream_style(mission_context)

    return (
        f"You are {pod_manager_agent_id} (pod manager) in a strict delegation chain.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Return only JSON with keys: specialist_agent_id, rationale.\n"
        f"Default specialist_agent_id: {default_specialist_agent_id}\n"
        f"Mission type: {mission_type}\n"
        f"Pod-family strategy: {strategy}\n"
        f"{risk_context}{style_context}"
        "Your rationale must identify language fit, risk fit, and whether the pod "
        "needs cross-pod or support-agent follow-up. Explicitly mention if team style "
        "directives were factored into specialist choice.\n"
        "Mission context JSON:\n"
        f"{_safe_context_json(mission_context)}"
    )


def _build_specialist_prompt(
    *,
    mission_context: dict[str, Any],
    specialist_agent_id: str,
    pod_manager_agent_id: str,
    recommended_provider: str,
    recommended_model: str,
) -> str:
    language = str(mission_context.get("requested_target_language") or "").strip().lower()
    risk_context = _format_upstream_risks(mission_context)
    style_context = _format_upstream_style(mission_context)
    return (
        f"You are {specialist_agent_id}, delegated by {pod_manager_agent_id}.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        f"{_language_context(language)}"
        f"{risk_context}{style_context}"
        "Return only JSON with keys: plan_summary, deliverables, risk_notes.\n"
        "deliverables and risk_notes must be arrays of short strings.\n"
        "Mission context JSON:\n"
        f"{_safe_context_json(mission_context)}"
    )


def _build_mission_contract_prompt(
    *,
    mission_context: dict[str, Any],
    prompt: str,
    mission_type: str,
    output_mode: str,
    requested_target_language: str | None,
    ceo_delegation: dict[str, Any],
    recommended_provider: str,
    recommended_model: str,
) -> str:
    safe_prompt = _clean_text(prompt, max_length=1200)
    safe_mission_type = _clean_text(mission_type or "BUILD_NEW", max_length=48).upper()
    safe_output_mode = _clean_text(output_mode or "FULL_BUILD", max_length=48).upper()
    safe_language = _clean_text(requested_target_language or "auto", max_length=32).lower()
    safe_delegation = json.dumps(
        {
            "pod_manager_agent_id": ceo_delegation.get("pod_manager_agent_id"),
            "specialist_agent_id": ceo_delegation.get("specialist_agent_id"),
            "rationale": ceo_delegation.get("rationale"),
            "source": ceo_delegation.get("source"),
        },
        sort_keys=True,
    )
    delegation_rationale = _clean_text(ceo_delegation.get("rationale", ""), max_length=280)
    risk_context = _format_upstream_risks(mission_context)
    feature_contract = mission_context.get("feature_contract")
    feature_summary = ""
    if isinstance(feature_contract, dict):
        feature_summary = json.dumps(
            {
                "title": feature_contract.get("title"),
                "summary": feature_contract.get("summary"),
                "functional_requirements": feature_contract.get("functional_requirements"),
                "acceptance_criteria": feature_contract.get("acceptance_criteria"),
            },
            sort_keys=True,
        )
    return (
        "You are AGENT-02-CEO. Produce the durable Mission Contract for this mission.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Return only JSON. No markdown, prose, or code fences.\n\n"
        f"Mission type: {safe_mission_type}\n"
        f"Output mode: {safe_output_mode}\n"
        f"Requested target language: {safe_language}\n"
        f"CEO delegation JSON: {safe_delegation}\n"
        + (f"CEO delegation rationale: {delegation_rationale}\n" if delegation_rationale else "")
        + (f"PM feature contract JSON: {feature_summary}\n" if feature_summary else "")
        + risk_context
        + f"User prompt: {safe_prompt}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "contract_summary": "one sentence describing the requested deliverable",\n'
        '  "mission_type": "BUILD_NEW | IMPORT_MODERNIZE | PORT | DEBUG_REPAIR | ANALYZE_ONLY",\n'
        '  "target_languages": ["language names"],\n'
        '  "output_mode": "FULL_BUILD | ANALYZE_ONLY | PLAN_ONLY | PATCH_PROPOSAL | APPLY_PATCH",\n'
        '  "output_format": "standalone_script | library | service | analysis_report | patch",\n'
        '  "required_domains": ["short domain names"],\n'
        '  "logicnode_requirements": [\n'
        '    {"domain": "domain", "concept": "concept", '
        '"intent": "testable intent", "priority": "HIGH | MEDIUM | LOW"}\n'
        "  ],\n"
        '  "acceptance_criteria": ["testable pass/fail criteria"],\n'
        '  "risk_notes": ["material risks or constraints"]\n'
        "}\n\n"
        "Keep arrays concise. Use 1-12 logicnode requirements and 1-6 acceptance criteria.\n"
        f"Safe mission context: {_safe_context_json(mission_context)}"
    )


def _build_pm_feature_contract_prompt(
    *,
    prompt: str,
    mission_type: str,
    depth_mode: str,
    output_mode: str,
    requested_target_language: str | None,
    recommended_provider: str,
    recommended_model: str,
    attachments: list[dict[str, Any]] | None = None,
    global_style_directives: list[str] | None = None,
    source_code: str | None = None,
    conversation_context: dict[str, Any] | None = None,
    user_intent: str | None = None,
) -> str:
    safe_prompt = _clean_text(prompt, max_length=1200)
    safe_user_intent = _clean_text(user_intent or "draft", max_length=32).lower()

    docs_context = ""
    if attachments:
        docs_context = "Attached Reference Documents:\n"
        for att in attachments:
            docs_context += (
                f"- {att.get('filename')} (Type: {att.get('content_type')}, "
                f"Purpose: {att.get('purpose')})\n"
            )
            extracted = str(att.get("content") or "").strip()
            if extracted:
                docs_context += (
                    f"\n## Attached Document: {att.get('filename')}\n"
                    f"{extracted[:2000]}"
                )
                if len(extracted) > 2000:
                    docs_context += "..."
                docs_context += "\n"
        docs_context += "\n"

    style_context = ""
    if global_style_directives:
        style_context = "Global Style & Team Directives:\n"
        for directive in global_style_directives:
            style_context += f"- {directive}\n"
        style_context += "\n"

    source_code_context = ""
    if source_code:
        source_code_context = f"\n\nAttached Workspace Files & Diagrams:\n{source_code}\n\n"

    conversation_context_text = ""
    if isinstance(conversation_context, dict) and conversation_context:
        conversation_context_text = (
            "\nConversation context JSON (authoritative for this chat session):\n"
            f"{_clean_text(json.dumps(conversation_context, sort_keys=True), max_length=5000)}\n\n"
        )

    return (
        "You are AGENT-01-PM. Convert the operator request and attached context into a product-level "
        "Feature Contract for a software factory mission. Act as a proactive product partner.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Return only JSON. No markdown, prose, or code fences.\n\n"
        f"Mission type: {_clean_text(mission_type or 'BUILD_NEW', max_length=48).upper()}\n"
        f"Depth mode: {_clean_text(depth_mode or 'STANDARD', max_length=48).upper()}\n"
        f"Output mode: {_clean_text(output_mode or 'FULL_BUILD', max_length=48).upper()}\n"
        f"User intent: {safe_user_intent}\n"
        "Requested target language: "
        f"{_clean_text(requested_target_language or 'auto', max_length=32).lower()}\n"
        f"{docs_context}{style_context}"
        f"Operator request: {safe_prompt}\n"
        f"{conversation_context_text}"
        f"{source_code_context}\n"
        "Required JSON keys:\n"
        "{\n"
        '  "title": "short title",\n'
        '  "summary": "one paragraph",\n'
        '  "intake_status": "needs_clarification | ready",\n'
        '  "functional_requirements": ["specific requirements"],\n'
        '  "non_functional_requirements": ["constraints"],\n'
        '  "acceptance_criteria": ["testable pass/fail criteria"],\n'
        '  "assumptions": ["assumptions you are making in order to proceed"],\n'
        '  "target_languages": ["language names"],\n'
        '  "estimated_complexity": "low | medium | high | very_high",\n'
        '  "human_approval_required": true,\n'
        '  "risk_notes": ["material risks or constraints"],\n'
        '  "clarifying_questions": ["specific, answerable questions about missing execution detail"]\n'
        "}\n\n"
        "Intake discipline (this is the core of your job — do not skip it):\n"
        "- Before writing requirements, check whether the request actually specifies, at minimum: "
        "the runtime/platform target, the libraries or dependency constraints, the input/data "
        "shape, the expected user interface or output format, the scope boundaries (what is "
        "explicitly out of scope), and the definition of done.\n"
        "- Use the conversation context and decision_memory as authoritative. Do not ask for a "
        "decision that is already answered anywhere in that context.\n"
        "- If the user_intent is finalize_plan, produce the best complete contract using explicit "
        "assumptions and recommended defaults. Only set needs_clarification for a hard blocker "
        "that makes execution impossible.\n"
        "- If an execution-critical dimension is still missing and user_intent is not finalize_plan, "
        'set "intake_status":"needs_clarification" and return 1-3 specific, answerable '
        "clarifying_questions that target exactly those gaps. Include a recommended default in "
        "each question. Do NOT pad with generic requirements.\n"
        '- Set "intake_status":"ready" when the request is concrete enough to build, or when '
        "user_intent is finalize_plan and reasonable defaults can close remaining gaps; "
        "in that case list every material assumption you are relying on under "
        '"assumptions".\n'
        "- Clarifying questions must be concrete and decision-shaped (e.g. \"No GUI library was "
        "named — should the desktop window use pygame or tkinter?\"), never generic (\"What "
        "features would you like?\").\n"
    )


def _build_codegen_prompt(
    *,
    mission_context: dict[str, Any],
    mission_contract: dict[str, Any],
    logicnodes: list[dict[str, Any]],
    target_language: str,
    specialist_agent_id: str,
    recommended_provider: str,
    recommended_model: str,
) -> str:
    contract_summary = _clean_text(
        mission_contract.get("contract_summary", "Implement the mission"), max_length=280
    )
    acceptance = "\n".join(
        f"- {_clean_text(item, max_length=140)}"
        for item in (mission_contract.get("acceptance_criteria") or [])[:6]
    ) or "- Satisfy the mission contract."
    requirements = []
    raw_requirements = mission_contract.get("logicnode_requirements")
    if isinstance(raw_requirements, list):
        for item in raw_requirements[:12]:
            if isinstance(item, dict):
                requirements.append(
                    "- "
                    f"{_clean_text(item.get('domain'), max_length=48)}."
                    f"{_clean_text(item.get('concept'), max_length=48)}: "
                    f"{_clean_text(item.get('intent'), max_length=140)}"
                )
    logicnode_lines = []
    for node in logicnodes[:12]:
        if isinstance(node, dict):
            logicnode_lines.append(_clean_text(json.dumps(node, sort_keys=True), max_length=220))
    risk_context = _format_upstream_risks(mission_context)
    knowledge_context = _format_knowledge_context(mission_context.get("knowledge_context"))
    hw_context = build_hw_context_block(
        mission_type=str(mission_context.get("mission_type") or "BUILD_NEW"),
        language=target_language,
        logic_clusters=(
            mission_context.get("logic_clusters")
            if isinstance(mission_context.get("logic_clusters"), dict)
            else None
        ),
    )
    # PORT mission — inject source behavior context
    port_source_context = ""
    port_nodes = mission_context.get("port_source_logicnodes") or []
    if port_nodes and isinstance(port_nodes, list):
        source_lang = _clean_text(
            str(mission_context.get("port_source_language") or "source"), max_length=32
        )
        node_lines = "\n".join(
            f"- {_clean_text(str(n.get('domain') or ''), max_length=32)}"
            f".{_clean_text(str(n.get('concept') or ''), max_length=48)}: "
            f"{_clean_text(str(n.get('intent') or ''), max_length=100)}"
            for n in port_nodes[:15]
            if isinstance(n, dict)
        )
        if node_lines:
            port_source_context = (
                f"\nSource behavior extracted from original {source_lang} code:\n"
                f"{node_lines}\n"
                f"Preserve this behavior in your {target_language} implementation.\n"
            )

    return (
        f"You are {specialist_agent_id}, a {target_language} specialist.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Generate a single complete source file that satisfies the mission contract.\n"
        "Return only JSON. No markdown, prose, or code fences.\n\n"
        f"Mission: {contract_summary}\n"
        f"Target language: {_clean_text(target_language, max_length=32)}\n"
        f"{_language_context(target_language)}"
        f"{knowledge_context}"
        f"{risk_context}"
        f"{hw_context}"
        f"{port_source_context}"
        f"Acceptance criteria:\n{acceptance}\n\n"
        f"Contract requirements:\n{chr(10).join(requirements) or '- primary_operation'}\n\n"
        f"Extracted logicnode context:\n{chr(10).join(logicnode_lines) or '- none'}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "generated_code": "complete source code string",\n'
        '  "filename": "safe filename",\n'
        '  "language": "target language",\n'
        '  "description": "one sentence",\n'
        '  "dependencies": ["package names"],\n'
        '  "usage_example": "one short usage example"\n'
        "}\n"
        f"Safe mission context: {_safe_context_json(mission_context)}"
    )


def _build_logic_clusters_prompt(
    *,
    mission_context: dict[str, Any],
    mission_contract: dict[str, Any],
    ceo_delegation: dict[str, Any],
    requested_target_language: str | None,
    recommended_provider: str,
    recommended_model: str,
) -> str:
    safe_language = _clean_text(requested_target_language or "auto", max_length=32).lower()
    contract_summary = _clean_text(
        mission_contract.get("contract_summary", "mission"), max_length=500
    )
    required_domains = _string_list(mission_contract.get("required_domains"), limit=10)
    requirements = mission_contract.get("logicnode_requirements")
    safe_requirements = requirements if isinstance(requirements, list) else []
    safe_delegation = json.dumps(
        {
            "pod_manager_agent_id": ceo_delegation.get("pod_manager_agent_id"),
            "specialist_agent_id": ceo_delegation.get("specialist_agent_id"),
        },
        sort_keys=True,
    )
    mission_type = str(
        mission_context.get("mission_type") or mission_contract.get("mission_type") or "BUILD_NEW"
    ).strip().upper()
    cluster_guidance = (
        "Decompose into 1-8 clusters. Rules:\n"
        "  - Each cluster must be ownable by a single pod manager.\n"
        "  - Clusters that can run in parallel should share priority level.\n"
        "  - Dependent clusters must list upstream titles in depends_on.\n"
        "  - DEBUG_REPAIR: one cluster per suspected fault domain.\n"
        "  - PORT: source extraction and target generation are separate clusters.\n"
        "  - SECURITY_HARDEN: include a security_audit cluster.\n"
        "  - REDUCE_DEPENDENCIES: include a dependency_absorption cluster.\n"
    )
    risk_context = _format_upstream_risks(mission_context)
    return (
        "You are AGENT-02-CEO. Decompose this mission contract into logic clusters.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Return only JSON. No markdown, prose, or code fences.\n\n"
        f"Mission type: {mission_type}\n"
        f"Requested target language: {safe_language}\n"
        f"Mission summary: {contract_summary}\n"
        f"Required domains: {json.dumps(required_domains)}\n"
        f"CEO delegation JSON: {safe_delegation}\n"
        f"Logicnode requirements JSON: {json.dumps(safe_requirements, sort_keys=True)}\n\n"
        f"{cluster_guidance}\n"
        f"{risk_context}"
        "Required JSON shape:\n"
        "{\n"
        '  "clusters": [\n'
        "    {\n"
        '      "title": "short cluster title",\n'
        '      "domain": "domain",\n'
        '      "priority": "HIGH | MEDIUM | LOW",\n'
        '      "pod_manager_agent_id": "assigned pod manager id",\n'
        '      "specialist_agent_id": "assigned specialist id",\n'
        '      "requirement_refs": ["requirement concept names"],\n'
        '      "depends_on": ["upstream cluster titles"],\n'
        '      "rationale": "why this work is grouped together"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Keep clusters coarse enough for pod-level ownership.\n"
        f"Safe mission context: {_safe_context_json(mission_context)}"
    )


def _build_pod_group_standard_prompt(
    *,
    pod_name: str,
    pod_manager_agent_id: str,
    mission_id: str,
    logicnodes: list[dict[str, Any]],
    mission_contract: dict[str, Any],
    recommended_provider: str,
    recommended_model: str,
    source_code: str | None = None,
) -> str:
    safe_nodes = [
        _clean_text(json.dumps(record, sort_keys=True), max_length=420)
        for record in logicnodes[:40]
        if isinstance(record, dict)
    ]
    contract_summary = _clean_text(
        mission_contract.get("contract_summary", "mission"), max_length=320
    )
    source_line_count = len([line for line in str(source_code or "").splitlines() if line.strip()])
    return (
        f"You are {pod_manager_agent_id}, the sub-manager for {pod_name}.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Consolidate specialist LogicNodes into a canonical pod group standard.\n"
        "Deduplicate semantically equivalent nodes across languages and preserve source ids.\n"
        "Call out thin coverage when the canonical standard is too small for the source scope.\n"
        "Return only JSON. No markdown, prose, or code fences.\n\n"
        f"Mission id: {_clean_text(mission_id, max_length=96)}\n"
        f"Mission summary: {contract_summary}\n"
        f"Approximate source line count: {source_line_count}\n"
        f"LogicNodes JSON lines:\n{chr(10).join(safe_nodes) or '- none'}\n\n"
        "Required JSON shape:\n"
        "{\n"
        '  "canonical_logicnodes": [\n'
        "    {\n"
        '      "domain": "domain",\n'
        '      "concept": "canonical concept",\n'
        '      "intent": "canonical intent",\n'
        '      "source_node_ids": ["source logicnode ids"],\n'
        '      "languages": ["languages represented"],\n'
        '      "confidence": 0.0\n'
        "    }\n"
        "  ],\n"
        '  "eliminated_duplicates": 0,\n'
        '  "summary": "one sentence"\n'
        "}\n"
    )

