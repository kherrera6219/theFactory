"""port_coordinator.py — Two-phase PORT mission helpers.

Provides:
- _setup_port_two_phase(): called from _prepare_ceo_delegation when
  PORT_TWO_PHASE_ENABLED=true to establish phase metadata.
- _run_port_extraction_phase(): called from _prepare_specialist_plan on
  the first pass (port_phase="extraction").
- _run_port_generation_context(): injects source logicnodes into the
  generation pass context.
"""
from __future__ import annotations

import logging
from typing import Any

from .aim_generator import _LANGUAGE_BY_SUFFIX
from .mission_flow import append_chain_event

LOGGER = logging.getLogger(__name__)

_POD_MANAGER_BY_LANGUAGE: dict[str, str] = {
    # Pod A
    "python": "AGENT-12-PODA-MGR",
    "javascript": "AGENT-12-PODA-MGR",
    "typescript": "AGENT-12-PODA-MGR",
    "ruby": "AGENT-12-PODA-MGR",
    "php": "AGENT-12-PODA-MGR",
    # Pod B
    "c": "AGENT-18-PODB-MGR",
    "cpp": "AGENT-18-PODB-MGR",
    "rust": "AGENT-18-PODB-MGR",
    "go": "AGENT-18-PODB-MGR",
    "zig": "AGENT-18-PODB-MGR",
    # Pod C
    "java": "AGENT-24-PODC-MGR",
    "csharp": "AGENT-24-PODC-MGR",
    "scala": "AGENT-24-PODC-MGR",
    "kotlin": "AGENT-24-PODC-MGR",
    # Pod D
    "matlab": "AGENT-30-PODD-MGR",
    "r": "AGENT-30-PODD-MGR",
    "julia": "AGENT-30-PODD-MGR",
    "mathematica": "AGENT-30-PODD-MGR",
    "haskell": "AGENT-30-PODD-MGR",
    "ocaml": "AGENT-30-PODD-MGR",
}

_SPECIALIST_BY_LANGUAGE: dict[str, str] = {
    "python": "AGENT-14-PYTHON",
    "javascript": "AGENT-15-JAVASCRIPT",
    "typescript": "AGENT-15-JAVASCRIPT",
    "ruby": "AGENT-16-RUBY",
    "php": "AGENT-17-PHP",
    "c": "AGENT-20-C",
    "cpp": "AGENT-21-CPP",
    "rust": "AGENT-22-RUST",
    "zig": "AGENT-23-ZIG",
    "java": "AGENT-26-JAVA",
    "csharp": "AGENT-27-CSHARP",
    "scala": "AGENT-28-SCALA",
    "kotlin": "AGENT-29-KOTLIN",
    "matlab": "AGENT-32-MATLAB",
    "r": "AGENT-33-R",
    "julia": "AGENT-34-JULIA",
    "mathematica": "AGENT-35-MATHEMATICA",
    "go": "AGENT-36-GO",
    "haskell": "AGENT-37-HASKELL",
    "ocaml": "AGENT-38-OCAML",
}


def _detect_source_language_from_bundle(
    source_code: str | None,
    prompt: str,
) -> str:
    """Detect source language from file extensions in source bundle or prompt hints."""
    if isinstance(source_code, str) and source_code.strip():
        ext_counts: dict[str, int] = {}
        import re
        for match in re.finditer(r"^## FILE .+?(\.[a-zA-Z0-9]+)$", source_code, re.MULTILINE):
            ext = match.group(1).lower()
            lang = _LANGUAGE_BY_SUFFIX.get(ext)
            if lang:
                ext_counts[lang] = ext_counts.get(lang, 0) + 1
        if ext_counts:
            return max(ext_counts, key=lambda k: ext_counts[k])

    # Fall back to prompt hints
    prompt_lower = str(prompt or "").lower()
    for lang in (
        "python", "javascript", "typescript", "rust", "go", "cpp", "c",
        "java", "csharp", "kotlin", "scala", "ruby", "php", "zig",
        "haskell", "ocaml", "julia", "r", "matlab",
    ):
        if lang in prompt_lower:
            return lang
    return "python"


def _setup_port_two_phase(
    metadata: dict[str, Any],
    mission: Any,
    clusters: list[dict[str, Any]] | None,
) -> None:
    """Populate PORT two-phase metadata after CEO delegation."""
    source_language = _detect_source_language_from_bundle(
        metadata.get("source_code"),
        str(getattr(mission, "prompt", "") or ""),
    )
    target_language = str(
        getattr(mission, "requested_target_language", None)
        or metadata.get("port_target_language")
        or "python"
    ).strip().lower()

    metadata["port_source_language"] = source_language
    metadata["port_target_language"] = target_language
    metadata["port_phase"] = "extraction"

    # Try to extract source/target pod from CEO cluster decomposition
    source_pod_manager = _POD_MANAGER_BY_LANGUAGE.get(source_language, "AGENT-12-PODA-MGR")
    source_specialist = _SPECIALIST_BY_LANGUAGE.get(source_language, "AGENT-14-PYTHON")

    if isinstance(clusters, list):
        for cluster in clusters:
            if not isinstance(cluster, dict):
                continue
            domain = str(cluster.get("domain") or "").lower()
            if "source_extraction" in domain or "extraction" in domain:
                pm = str(cluster.get("pod_manager_agent_id") or "").strip()
                sp = str(cluster.get("specialist_agent_id") or "").strip()
                if pm:
                    source_pod_manager = pm
                if sp:
                    source_specialist = sp
                break

    metadata["port_source_pod_manager_agent_id"] = source_pod_manager
    metadata["port_source_specialist_agent_id"] = source_specialist

    LOGGER.info(
        "PORT two-phase setup: source=%s specialist=%s target=%s",
        source_language,
        source_specialist,
        target_language,
    )


async def run_port_extraction_phase(
    *,
    mission_id: str,
    mission: Any,
    metadata: dict[str, Any],
    settings: Any,
) -> dict[str, Any]:
    """Run the extraction phase for PORT missions.

    Generates AIM and extracts LogicNodes from the source code using the
    source-language specialist. Returns updated metadata fields.
    """
    from .aim_generator import generate_aim
    from .llm_delegation import generate_specialist_plan

    source_language = str(metadata.get("port_source_language") or "python")
    source_specialist = str(
        metadata.get("port_source_specialist_agent_id") or
        _SPECIALIST_BY_LANGUAGE.get(source_language, "AGENT-14-PYTHON")
    )
    source_pod_manager = str(
        metadata.get("port_source_pod_manager_agent_id") or
        _POD_MANAGER_BY_LANGUAGE.get(source_language, "AGENT-12-PODA-MGR")
    )
    source_code = metadata.get("source_code")
    prompt = str(getattr(mission, "prompt", "") or "")

    # Generate AIM from source
    source_aim: dict[str, Any] = {}
    if isinstance(source_code, str) and source_code.strip():
        try:
            source_aim = await generate_aim(
                mission_id=mission_id,
                source_code=source_code,
                prompt=prompt,
                mission_type="PORT",
                requested_target_language=source_language,
                feature_contract=metadata.get("feature_contract") or {},
                settings=settings,
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("port_coordinator: AIM extraction failed for mission %s: %s", mission_id, exc)
            source_aim = {"source": "error", "files": []}

    # Generate specialist plan for source extraction
    try:
        source_plan = await generate_specialist_plan(
            mission_context={
                "mission_id": mission_id,
                "prompt": prompt,
                "requested_target_language": source_language,
                "mission_type": "PORT",
                "source": "port_extraction",
                "port_source_language": source_language,
            },
            requested_target_language=source_language,
            specialist_agent_id=source_specialist,
            pod_manager_agent_id=source_pod_manager,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("port_coordinator: specialist plan failed for mission %s: %s", mission_id, exc)
        source_plan = {"source": "fallback"}

    # Extract LogicNodes from AIM file entries
    source_logicnodes: list[dict[str, Any]] = []
    files = source_aim.get("files") if isinstance(source_aim, dict) else []
    if isinstance(files, list):
        for file_entry in files[:20]:
            if not isinstance(file_entry, dict):
                continue
            for node in (file_entry.get("extracted_concepts") or [])[:10]:
                if isinstance(node, dict):
                    source_logicnodes.append({
                        "domain": node.get("domain", "general"),
                        "concept": node.get("concept", ""),
                        "intent": node.get("intent", ""),
                        "confidence": node.get("confidence", 0.5),
                        "source_language": source_language,
                        "extraction_method": node.get("extraction_method", "aim"),
                    })

    append_chain_event(
        metadata,
        event_type="MISSION_PORT_EXTRACTION_COMPLETE",
        agent_id=source_specialist,
        details={
            "source_language": source_language,
            "logicnode_count": len(source_logicnodes),
            "aim_file_count": len(files) if isinstance(files, list) else 0,
            "source": source_aim.get("source", "unknown"),
        },
    )

    extraction_degraded = (
        source_aim.get("source") in {"error", "fallback"}
        or source_plan.get("source") == "fallback"
    )
    return {
        "port_source_logicnodes": source_logicnodes,
        "port_source_aim": source_aim,
        "port_source_plan": source_plan,
        "port_phase": "generation",
        "extraction_degraded": extraction_degraded,
    }
