"""LogicNode construction, coercion, and summary helpers for pod-worker."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any


def build_schema_node(
    *,
    pod_name: str,
    node_id: str,
    concept_id: str,
    concept: str,
    domain: str,
    intent: str,
    extraction_language: str,
    target_language: str,
    source_file: str,
    snippet: str,
    agent_id: str,
    extra_payload: dict[str, Any] | None = None,
    types_in: Sequence[str] | None = None,
    types_out: Sequence[str] | None = None,
    purity: str | None = None,
) -> dict[str, Any]:
    """Build a node dict conforming to schemas/logicnode.schema.json."""
    snippet_hash = hashlib.sha256((snippet or "").encode()).hexdigest()
    payload: dict[str, Any] = {
        "origin": "pod-worker",
        "pod_name": pod_name,
        "concept_id": concept_id,
        "concept": concept,
        "domain": domain,
        "node_name": f"{domain}.{concept}",
        "source_language": extraction_language,
        "target_language": target_language or "generic",
    }
    if extra_payload:
        payload.update(extra_payload)

    node: dict[str, Any] = {
        "node_id": node_id,
        "cmd": concept_id,
        "payload": payload,
        "priority": "NORMAL",
        "intent": intent or "",
        "types": {
            "in": [str(item) for item in (types_in or []) if str(item).strip()],
            "out": [str(item) for item in (types_out or []) if str(item).strip()],
        },
        "provenance": {
            "source_ref": source_file or extraction_language,
            "snippet_hash": snippet_hash,
            "miner_agent": agent_id or pod_name,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    }

    if domain:
        node["domain"] = domain
    if concept:
        node["concept"] = concept
    if extraction_language:
        node["source_language"] = extraction_language
    confidence = payload.get("confidence")
    if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
        node["confidence"] = max(0.0, min(1.0, float(confidence)))
    extraction_method = payload.get("extraction_method")
    if extraction_method in ("regex", "ast"):
        node["extraction_method"] = extraction_method
    if purity in ("PURE", "IMPURE", "UNKNOWN"):
        node["purity"] = purity

    return node


def coerce_schema_node(
    logicnode: dict[str, Any],
    *,
    pod_name: str,
    node_id: str,
    extraction_language: str,
    target_language: str,
    agent_id: str,
) -> dict[str, Any]:
    """Return a schema-conformant ``node`` dict for *logicnode*."""
    existing = logicnode.get("node")
    if isinstance(existing, dict) and "provenance" in existing and "cmd" in existing:
        return existing
    concept = str(logicnode.get("concept", "extracted_intent") or "extracted_intent")
    domain = str(logicnode.get("domain", "generic") or "generic")
    extra_payload: dict[str, Any] = {}
    if isinstance(existing, dict):
        legacy_payload = existing.get("payload")
        if isinstance(legacy_payload, dict):
            extra_payload.update(legacy_payload)
        for key in ("node_name", "source_language", "target_language"):
            if key in existing:
                extra_payload[key] = existing[key]
    return build_schema_node(
        pod_name=pod_name,
        node_id=node_id,
        concept_id=concept,
        concept=concept,
        domain=domain,
        intent=str(logicnode.get("intent", "") or ""),
        extraction_language=extraction_language,
        target_language=target_language,
        source_file=str(logicnode.get("source_file", "") or ""),
        snippet=str(extra_payload.get("evidence", "") or ""),
        agent_id=agent_id,
        extra_payload=extra_payload or None,
    )


def routing_stub_logicnode(
    *,
    pod_name: str,
    mission_id: str,
    extraction_language: str,
    target_language: str,
    agent_id: str,
    node_id: str | None = None,
) -> dict[str, Any]:
    """Build a schema-conformant fallback node when extraction yields nothing."""
    stub_node_id = node_id or f"{pod_name}.core.{mission_id}"
    schema_node = build_schema_node(
        pod_name=pod_name,
        node_id=stub_node_id,
        concept_id="core",
        concept="routing_stub",
        domain="core",
        intent="",
        extraction_language=extraction_language,
        target_language=target_language,
        source_file=f"mission://{mission_id}",
        snippet="",
        agent_id=agent_id,
        extra_payload={"node_name": f"{pod_name}-logicnode-core"},
    )
    return {
        "node_id": stub_node_id,
        "concept": "routing_stub",
        "domain": "core",
        "language": extraction_language,
        "agent_id": agent_id,
        "node": schema_node,
    }


def enclosing_function_for_line(
    functions: Sequence[Any], source_line: Any
) -> Any | None:
    """Return the function whose definition most closely precedes *source_line*."""
    if not functions:
        return None
    try:
        line = int(source_line)
    except (TypeError, ValueError):
        return None

    best: Any | None = None
    best_line = -1
    for function in functions:
        candidate_line = getattr(function, "line", None)
        try:
            candidate_line = int(candidate_line)
        except (TypeError, ValueError):
            continue
        if best_line < candidate_line <= line:
            best = function
            best_line = candidate_line
    return best


def logicnodes_from_extraction(
    *,
    pod_name: str,
    mission_id: str,
    target_language: str,
    extraction_language: str,
    concepts: list[Any],
    source_file: str = "",
    agent_id: str = "",
    functions: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    file_hash = hashlib.sha256((source_file or extraction_language).encode()).hexdigest()[:8]
    logicnodes: list[dict[str, Any]] = []
    for concept in concepts:
        concept_id = str(getattr(concept, "concept_id", "") or "core")
        source_line = getattr(concept, "source_line", None)
        line_token = str(source_line) if source_line is not None else "0"
        concept_name = str(getattr(concept, "concept", "") or "extracted_intent")
        domain = str(getattr(concept, "domain", "") or "generic")
        intent = str(getattr(concept, "intent", "") or "")
        node_id = f"{pod_name}.{concept_id}.{mission_id}.{file_hash}.{line_token}"

        types_in: tuple[str, ...] = ()
        types_out: list[str] = []
        types_source: str | None = None
        node_purity: str | None = None
        side_effects: tuple[str, ...] = ()
        op_stream: list[list[str]] = []
        enclosing = enclosing_function_for_line(functions or (), source_line)
        if enclosing is not None:
            arg_types = tuple(getattr(enclosing, "arg_types", ()) or ())
            return_type = getattr(enclosing, "return_type", None)
            if arg_types or return_type:
                types_in = arg_types
                types_out = [return_type] if return_type else []
                types_source = f"ast_signature:{getattr(enclosing, 'name', '') or '?'}"
            candidate_purity = getattr(enclosing, "purity", None)
            if candidate_purity in ("PURE", "IMPURE", "UNKNOWN"):
                node_purity = candidate_purity
            side_effects = tuple(getattr(enclosing, "side_effects", ()) or ())
            op_stream = [
                [str(opcode), str(detail)]
                for opcode, detail in (getattr(enclosing, "ops", ()) or ())
            ]

        schema_node = build_schema_node(
            pod_name=pod_name,
            node_id=node_id,
            concept_id=concept_id,
            concept=concept_name,
            domain=domain,
            intent=intent,
            extraction_language=extraction_language,
            target_language=target_language,
            source_file=source_file,
            snippet=str(getattr(concept, "evidence", "") or ""),
            agent_id=agent_id,
            extra_payload={
                "confidence": getattr(concept, "confidence", 0.0),
                "source_line": getattr(concept, "source_line", None),
                "evidence": getattr(concept, "evidence", ""),
                "extraction_method": getattr(concept, "extraction_method", "regex"),
                "source_range": getattr(concept, "source_range", None),
                **({"types_source": types_source} if types_source else {}),
                **({"side_effects": list(side_effects)} if side_effects else {}),
                **({"op_stream": op_stream} if op_stream else {}),
            },
            types_in=types_in,
            types_out=types_out,
            purity=node_purity,
        )
        logicnodes.append(
            {
                "node_id": node_id,
                "concept": concept_name,
                "domain": domain,
                "language": extraction_language,
                "agent_id": agent_id,
                "node": schema_node,
            }
        )
    return logicnodes


def extract_logicnodes_from_agent_result(result: Any) -> list[dict[str, Any]]:
    logicnodes: list[dict[str, Any]] = []
    artifacts = getattr(result, "artifacts", [])
    if not isinstance(artifacts, list):
        return logicnodes
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        if artifact.get("type") != "logicnode_set":
            continue
        for node in artifact.get("logicnodes", []):
            if isinstance(node, dict):
                logicnodes.append(node)
    return logicnodes


def safe_to_dict(candidate: Any) -> dict[str, Any]:
    if hasattr(candidate, "to_dict") and callable(candidate.to_dict):
        payload = candidate.to_dict()
        if isinstance(payload, dict):
            return payload
    return {}


def summarize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        compact = " ".join(value.split())
        return compact if len(compact) <= 240 else f"{compact[:240]}..."
    if isinstance(value, dict):
        items = list(value.items())[:8]
        summary = {str(key): summarize_value(item) for key, item in items}
        if len(value) > 8:
            summary["_truncated_keys"] = len(value) - 8
        return summary
    if isinstance(value, list):
        summary = [summarize_value(item) for item in value[:8]]
        if len(value) > 8:
            summary.append({"_truncated_items": len(value) - 8})
        return summary
    return str(value)
