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
    """Build a node dict conforming to schemas/logicnode.schema.json.

    This is the **only** place a schema node is constructed — both
    ``_coerce_schema_node`` and ``_logicnodes_from_extraction`` route through
    it, so enriching here enriches every node in the system.

    Since UPG-30 the descriptive fields are *also* promoted to first-class
    optional top-level properties. ``payload`` still carries every value it
    carried before, so nothing that reads ``payload.domain`` breaks — the new
    fields are duplicates, not moves.

    ``types_in``/``types_out`` are populated only when an AST extractor
    genuinely recovered a signature (UPG-31). They stay empty for regex-only
    languages, and that emptiness is now meaningful rather than universal.
    """
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
        # The concept identifier doubles as the command identifier for the node.
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

    # UPG-30: promote descriptive fields out of the free-form payload. Only
    # fields the extractor actually produced are emitted — an absent field
    # means "not determined", never a default. `paradigm`, `purity`,
    # `complexity`, `source_license`, and `tags` are reserved in the schema and
    # deliberately left unpopulated until Phase 4 can derive them honestly.
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
    # UPG-41 fills the `purity` slot UPG-30 reserved. Only emitted when
    # side-effect analysis actually ran and produced a verdict — "UNKNOWN" is a
    # real answer meaning "not determined", distinct from the field being absent
    # because nothing analysed it.
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
    """Return a schema-conformant ``node`` dict for *logicnode*.

    Logicnodes produced by the extractor already carry a schema-valid ``node``;
    those returned by agent pipelines may not, so build one from the available
    descriptive fields here so the orchestrator write boundary accepts them.
    """
    existing = logicnode.get("node")
    if isinstance(existing, dict) and "provenance" in existing and "cmd" in existing:
        return existing
    concept = str(logicnode.get("concept", "extracted_intent") or "extracted_intent")
    domain = str(logicnode.get("domain", "generic") or "generic")
    extra_payload: dict[str, Any] = {}
    if isinstance(existing, dict):
        # Preserve any descriptive fields the agent attached under the legacy
        # shape by folding them into the schema-free payload object.
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
    """Return the function whose definition most closely precedes *source_line*.

    Concepts are extracted per-match and carry a line number; signatures are
    extracted per-function and carry a definition line. They arrive as sibling
    lists with no explicit link, so the two are correlated by position: the
    innermost enclosing function is the one with the greatest definition line at
    or before the concept's line.

    This is a heuristic, and it is kept deliberately narrow (UPG-31):

    * a concept above the first function returns ``None`` rather than guessing;
    * a non-integer or missing line returns ``None``;
    * the match is only *used* when the function actually carries type data, so
      a wrong correlation cannot invent types that were never declared.
    """
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
    # Discriminate node_id by source file + line so that multiple occurrences of
    # the same concept across files/lines do not collapse to one row under the
    # ON CONFLICT(node_id) upsert (last-write-wins) and silently lose data.
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

        # UPG-31: attach real I/O types when an AST extractor recovered a
        # signature for the function enclosing this concept. Only Python, Java,
        # and Haskell currently produce structured type data; every other
        # language leaves these empty, which is now informative.
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
            # UPG-41: side-effect analysis result for the enclosing function.
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
                # Machine-readable provenance for the declared types: a consumer
                # can tell a real AST-derived signature from an absent one
                # without reading documentation (plan principle 5).
                **({"types_source": types_source} if types_source else {}),
                # The specific effects behind an IMPURE verdict, so a consumer
                # can see *why* rather than only *that* (UPG-41).
                **({"side_effects": list(side_effects)} if side_effects else {}),
                # Real statement sequence for the enclosing function, which the
                # RIR projects into its op stream instead of one synthetic
                # EXTRACT_CONCEPT (UPG-41).
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
