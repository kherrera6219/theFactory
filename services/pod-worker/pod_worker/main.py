import asyncio
import hashlib
import inspect
import json
import logging
import os
import re
import sys
import time
import uuid
from collections.abc import Sequence
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from redis.exceptions import ResponseError

from shared_runtime.agent_keys import (
    configured_agent_service_key_map,
    enforce_production_service_auth_config,
    normalize_agent_id,
    service_api_key_for_agent,
)
from shared_runtime.logging_config import configure_logging
from shared_runtime.protocol import (
    ProtocolValidationError,
    load_event_schema,
    load_topics,
    parse_date_time,
    validate_envelope,
)

from .language_extractor import (
    JavaAstExtractor,
    JavaScriptAstExtractor,
    PythonAstExtractor,
    get_extractor,
)
from .refined_ir import build_refined_ir_module, write_refined_ir_module
from .tracing import configure_tracing

try:
    from orchestrator.agent_base import make_agent, make_specialist_for_language
    from orchestrator.agent_registry import normalize_language
except ModuleNotFoundError:
    ORCHESTRATOR_SERVICE_ROOT = Path(__file__).resolve().parents[3] / "services" / "orchestrator"
    if ORCHESTRATOR_SERVICE_ROOT.exists():
        sys.path.insert(0, str(ORCHESTRATOR_SERVICE_ROOT))
    from orchestrator.agent_base import make_agent, make_specialist_for_language
    from orchestrator.agent_registry import normalize_language

configure_logging("pod-worker")
LOGGER = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
STATE_STREAM = os.getenv("STATE_STREAM", "missions.state")
CONSUMER_GROUP = os.getenv("POD_WORKER_GROUP", "pod-workers")
CONSUMER_NAME = os.getenv("POD_WORKER_NAME", f"pod-worker-{uuid.uuid4()}")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8001")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY", "worker-key")
AGENT_SERVICE_API_KEYS = os.getenv("AGENT_SERVICE_API_KEYS", "")
AGENT_SERVICE_KEY_MODE = os.getenv("AGENT_SERVICE_KEY_MODE", "shared").strip().lower() or "shared"
REQUEST_TIMEOUT_SECONDS = float(os.getenv("ORCHESTRATOR_TIMEOUT_SECONDS", "5.0"))
REQUEST_MAX_RETRIES = int(os.getenv("ORCHESTRATOR_MAX_RETRIES", "3"))
POD_NAME = os.getenv("POD_NAME", "podA")
SUPPORTED_LANGUAGES = {
    language.strip().lower()
    for language in os.getenv("SUPPORTED_LANGUAGES", "python,typescript,javascript,ruby,php").split(
        ","
    )
    if language.strip()
}
AGENT_BINDING = os.getenv("AGENT_BINDING", "")
WORKER_AGENT_ID = os.getenv("WORKER_AGENT_ID", "").strip().upper()
HEARTBEAT_INTERVAL_SECONDS = max(
    5.0,
    float(os.getenv("AGENT_HEARTBEAT_INTERVAL_SECONDS", "15.0")),
)
REFINED_IR_STORE_PATH = os.getenv("REFINED_IR_STORE_PATH", "").strip()
PYTHON_AST_EXTRACTOR_ENABLED = (
    os.getenv("PYTHON_AST_EXTRACTOR_ENABLED", "false").strip().lower() == "true"
)
JS_AST_EXTRACTOR_ENABLED = os.getenv("JS_AST_EXTRACTOR_ENABLED", "false").strip().lower() == "true"
JAVA_AST_EXTRACTOR_ENABLED = (
    os.getenv("JAVA_AST_EXTRACTOR_ENABLED", "false").strip().lower() == "true"
)


MAX_STREAM_LEN = int(os.getenv("MAX_STREAM_LEN", "20000"))
POD_DLQ_STREAM = os.getenv("POD_DLQ_STREAM", "factory:dlq:pod-worker")
PAYLOAD_REF_PATTERN = re.compile(r"^registry://")

EVENT_SCHEMA_PATH = Path("/app/schemas/event.envelope.schema.json")
TOPICS_PATH = Path("/app/protocol/topics.yaml")

TASKS_PROCESSED = Counter(
    "pod_worker_tasks_processed_total",
    "Total mission events processed by pod worker",
    ("pod_name", "agent_id"),
)
TASKS_FAILED = Counter(
    "pod_worker_tasks_failed_total",
    "Total mission events failed by pod worker",
    ("pod_name", "agent_id"),
)
TASK_LATENCY_SECONDS = Histogram(
    "pod_worker_task_latency_seconds",
    "Mission event processing latency for pod worker",
    ("pod_name", "agent_id"),
)
CONCEPTS_EXTRACTED = Counter(
    "pod_worker_concepts_extracted_total",
    "Total computational concepts extracted by pod worker",
    ("pod_name", "agent_id", "language"),
)
EXTRACTION_LATENCY = Histogram(
    "pod_worker_extraction_latency_seconds",
    "Source code extraction latency for pod worker",
    ("pod_name", "agent_id"),
)
AGENT_EXECUTION_LATENCY = Histogram(
    "pod_worker_agent_execution_latency_seconds",
    "Agent execution latency for pod worker mission handling",
    ("pod_name", "agent_id", "category"),
)
AGENT_HEARTBEAT_ATTEMPTS = Counter(
    "pod_worker_agent_heartbeat_attempts_total",
    "Total agent heartbeat attempts emitted by pod worker",
    ("pod_name", "agent_id", "status"),
)
BINDING_SKIPS = Counter(
    "pod_worker_binding_skips_total",
    "Total missions skipped because agent binding did not match",
    ("pod_name", "reason"),
)
INTERNAL_AUTH_REJECTIONS = Counter(
    "pod_worker_internal_auth_rejections_total",
    "Total orchestrator internal endpoint auth rejections observed by pod worker",
    ("pod_name",),
)

INTERNAL_AUTH_FAILURES = 0
LAST_INTERNAL_AUTH_STATUS: int | None = None
_SOURCE_BUNDLE_FILE_PATTERN = re.compile(r"^## FILE (.+)$", re.MULTILINE)


def _get_extractor(language: str):
    """Return the appropriate extractor for *language*.

    Uses AST-backed extractors when their feature flags are true. All flagged
    paths fall back to the standard regex registry when parsing is unavailable.
    """
    if language == "python" and PYTHON_AST_EXTRACTOR_ENABLED:
        return PythonAstExtractor()
    if language in {"javascript", "typescript"} and JS_AST_EXTRACTOR_ENABLED:
        return JavaScriptAstExtractor()
    if language == "java" and JAVA_AST_EXTRACTOR_ENABLED:
        return JavaAstExtractor()
    return get_extractor(language)


def _parse_agent_binding(raw: str) -> tuple[str, ...]:
    candidates = re.split(r"[\s,]+", raw.strip())
    normalized = {candidate.strip().upper() for candidate in candidates if candidate.strip()}
    return tuple(sorted(normalized))


AGENT_BINDINGS = _parse_agent_binding(AGENT_BINDING)
AGENT_BINDING_SET = frozenset(AGENT_BINDINGS)


def _normalize_agent_id(value: Any) -> str | None:
    return normalize_agent_id(value)


def _agent_service_key_env_name(agent_id: str) -> str | None:
    normalized = _normalize_agent_id(agent_id)
    if normalized is None:
        return None
    return f"{normalized.replace('-', '_')}_SERVICE_API_KEY"


def _parse_agent_service_key_map(raw: str) -> dict[str, str]:
    return configured_agent_service_key_map(raw, env={})


def _configured_agent_service_key_map() -> dict[str, str]:
    return configured_agent_service_key_map(AGENT_SERVICE_API_KEYS)


def _service_api_key_for_agent(agent_id: str | None) -> str:
    return service_api_key_for_agent(
        agent_id,
        fallback_key=SERVICE_API_KEY,
        raw_mapping=AGENT_SERVICE_API_KEYS,
        key_mode=AGENT_SERVICE_KEY_MODE,
    )


def _agent_id_from_metadata(metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return None
    for key in ("agent_id", "target_agent_id", "selected_agent_id", "assigned_agent_id"):
        normalized = _normalize_agent_id(metadata.get(key))
        if normalized:
            return normalized

    nested_agent = metadata.get("agent")
    if isinstance(nested_agent, dict):
        for key in ("agent_id", "id"):
            normalized = _normalize_agent_id(nested_agent.get(key))
            if normalized:
                return normalized
    return None


def _agent_id_from_payload(payload: dict[str, Any]) -> str | None:
    for key in ("agent_id", "target_agent_id", "selected_agent_id", "assigned_agent_id"):
        normalized = _normalize_agent_id(payload.get(key))
        if normalized:
            return normalized
    return _agent_id_from_metadata(payload.get("metadata"))


def _effective_worker_agent_id(agent_id: str | None = None) -> str | None:
    normalized_agent_id = _normalize_agent_id(agent_id)
    if normalized_agent_id:
        return normalized_agent_id
    if WORKER_AGENT_ID:
        return WORKER_AGENT_ID
    if len(AGENT_BINDINGS) == 1:
        return AGENT_BINDINGS[0]
    return None


DEFAULT_POD_MANAGER_AGENT_IDS = {
    "poda": "AGENT-12-PODA-MGR",
    "podb": "AGENT-18-PODB-MGR",
    "podc": "AGENT-24-PODC-MGR",
    "podd": "AGENT-30-PODD-MGR",
}


def _default_agent_id_for_event(event_type: str, target_language: str | None) -> str | None:
    effective_agent_id = _effective_worker_agent_id()
    if effective_agent_id:
        return effective_agent_id

    normalized_event_type = str(event_type).strip().upper()
    if normalized_event_type == "MISSION_POD_MANAGER_ASSIGNED":
        return DEFAULT_POD_MANAGER_AGENT_IDS.get(POD_NAME.strip().lower())

    specialist = make_specialist_for_language(normalize_language(target_language))
    if specialist is not None:
        return specialist.agent_id
    return DEFAULT_POD_MANAGER_AGENT_IDS.get(POD_NAME.strip().lower())


def _build_schema_node(
    *,
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
        "pod_name": POD_NAME,
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
            "miner_agent": agent_id or POD_NAME,
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

    return node


def _coerce_schema_node(
    logicnode: dict[str, Any],
    *,
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
    return _build_schema_node(
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


def _routing_stub_logicnode(
    *,
    mission_id: str,
    extraction_language: str,
    target_language: str,
    agent_id: str,
    node_id: str | None = None,
) -> dict[str, Any]:
    """Build a schema-conformant fallback node when extraction yields nothing."""
    stub_node_id = node_id or f"{POD_NAME}.core.{mission_id}"
    schema_node = _build_schema_node(
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
        extra_payload={"node_name": f"{POD_NAME}-logicnode-core"},
    )
    return {
        "node_id": stub_node_id,
        "concept": "routing_stub",
        "domain": "core",
        "language": extraction_language,
        "agent_id": agent_id,
        "node": schema_node,
    }


def _enclosing_function_for_line(
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


def _logicnodes_from_extraction(
    *,
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
        node_id = f"{POD_NAME}.{concept_id}.{mission_id}.{file_hash}.{line_token}"

        # UPG-31: attach real I/O types when an AST extractor recovered a
        # signature for the function enclosing this concept. Only Python, Java,
        # and Haskell currently produce structured type data; every other
        # language leaves these empty, which is now informative.
        types_in: tuple[str, ...] = ()
        types_out: list[str] = []
        types_source: str | None = None
        enclosing = _enclosing_function_for_line(functions or (), source_line)
        if enclosing is not None:
            arg_types = tuple(getattr(enclosing, "arg_types", ()) or ())
            return_type = getattr(enclosing, "return_type", None)
            if arg_types or return_type:
                types_in = arg_types
                types_out = [return_type] if return_type else []
                types_source = f"ast_signature:{getattr(enclosing, 'name', '') or '?'}"

        schema_node = _build_schema_node(
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
            },
            types_in=types_in,
            types_out=types_out,
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


def _extract_logicnodes_from_agent_result(result: Any) -> list[dict[str, Any]]:
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


def _safe_to_dict(candidate: Any) -> dict[str, Any]:
    if hasattr(candidate, "to_dict") and callable(candidate.to_dict):
        payload = candidate.to_dict()
        if isinstance(payload, dict):
            return payload
    return {}


def _summarize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        compact = " ".join(value.split())
        return compact if len(compact) <= 240 else f"{compact[:240]}..."
    if isinstance(value, dict):
        items = list(value.items())[:8]
        summary = {str(key): _summarize_value(item) for key, item in items}
        if len(value) > 8:
            summary["_truncated_keys"] = len(value) - 8
        return summary
    if isinstance(value, list):
        summary = [_summarize_value(item) for item in value[:8]]
        if len(value) > 8:
            summary.append({"_truncated_items": len(value) - 8})
        return summary
    return str(value)


def _focus_domains_for_pod(mission_metadata: Any) -> list[str]:
    if not isinstance(mission_metadata, dict):
        return []
    logic_cluster_doc = mission_metadata.get("logic_clusters")
    if not isinstance(logic_cluster_doc, dict):
        return []
    clusters = logic_cluster_doc.get("clusters")
    if not isinstance(clusters, list):
        return []
    pod_name = POD_NAME.strip().lower()
    focus_domains: list[str] = []
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        assigned_pod = str(
            cluster.get("assigned_pod")
            or cluster.get("pod_name")
            or cluster.get("pod")
            or ""
        ).strip().lower()
        pod_manager_id = str(cluster.get("pod_manager_agent_id") or "").strip().upper()
        if assigned_pod and assigned_pod != pod_name:
            continue
        default_manager_id = DEFAULT_POD_MANAGER_AGENT_IDS.get(pod_name)
        if not assigned_pod and default_manager_id and pod_manager_id != default_manager_id:
            continue
        domain = str(cluster.get("domain") or "").strip()
        if domain and domain not in focus_domains:
            focus_domains.append(domain)
    return focus_domains


# Repo ZIP Import Phase 7: cap raw repo_source_chunk records pulled into a
# specialist's prompt context so a large repo can't blow up the context window.
_MAX_REPO_CHUNK_CONTEXT_RECORDS = 10


async def _fetch_doc_context(mission_id: str, language: str) -> str | None:
    try:
        response = await _request(
            "GET",
            f"/internal/missions/{mission_id}/knowledge",
            params={"limit": 100},
        )
    except Exception:
        return None
    if response.status_code >= 400:
        return None

    try:
        records = response.json()
    except Exception:
        return None
    if not isinstance(records, list):
        return None

    language_key = str(language or "").strip().lower()
    context_parts: list[str] = []
    repo_chunk_count = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        content = record.get("content")
        if not isinstance(content, dict):
            continue
        kind = content.get("kind")
        combined_text = str(content.get("combined_text") or "").strip()
        if not combined_text:
            continue
        if kind == "bootstrap_documentation":
            record_language = str(content.get("language") or "").strip().lower()
            if language_key and record_language and record_language != language_key:
                continue
            context_parts.append(combined_text)
        elif kind == "repo_summary":
            # Not language-filtered: this describes the whole imported repo,
            # not one language-specific doc, so every specialist working the
            # mission should see it regardless of its own target language.
            context_parts.append(combined_text)
        elif kind == "repo_source_chunk" and repo_chunk_count < _MAX_REPO_CHUNK_CONTEXT_RECORDS:
            context_parts.append(combined_text)
            repo_chunk_count += 1
    return "\n\n".join(context_parts) or None


def _summarize_mapping(value: Any) -> dict[str, Any]:
    return _summarize_value(value) if isinstance(value, dict) else {}


def _mission_id_for_request(
    path: str,
    *,
    json_body: dict[str, Any] | None,
    params: dict[str, Any] | None,
) -> str | None:
    if isinstance(json_body, dict):
        mission_id = str(json_body.get("mission_id", "")).strip()
        if mission_id:
            return mission_id
    if isinstance(params, dict):
        mission_id = str(params.get("mission_id", "")).strip()
        if mission_id:
            return mission_id
    match = re.search(r"/missions/([^/]+)", path)
    if match:
        return str(match.group(1)).strip()
    return None


def _bundle_source_segments(source_code: str) -> list[tuple[str, str]]:
    matches = list(_SOURCE_BUNDLE_FILE_PATTERN.finditer(source_code))
    if not matches:
        return []

    segments: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        path = str(match.group(1)).strip()
        if not path:
            continue
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(source_code)
        body = source_code[body_start:body_end].lstrip("\r\n")
        segments.append((path, body))
    return segments


def _subset_source_bundle(source_code: str, assigned_items: list[str]) -> str:
    if not source_code.strip() or not assigned_items:
        return source_code

    wanted = {str(item).strip() for item in assigned_items if str(item).strip()}
    if not wanted:
        return source_code

    segments = _bundle_source_segments(source_code)
    if not segments:
        return source_code

    selected = [(path, body) for path, body in segments if path in wanted]
    if not selected:
        return source_code

    rendered: list[str] = []
    for path, body in selected:
        block = f"## FILE {path}\n{body.rstrip()}".rstrip()
        rendered.append(block)
    return "\n\n".join(rendered).strip() + "\n"


def _partition_payload(payload: dict[str, Any]) -> dict[str, Any]:
    partition = payload.get("partition")
    return partition if isinstance(partition, dict) else {}


def _partition_id(payload: dict[str, Any]) -> str:
    partition = _partition_payload(payload)
    return str(partition.get("partition_id", "")).strip()


def _partition_items(payload: dict[str, Any]) -> list[str]:
    partition = _partition_payload(payload)
    assigned_items = partition.get("assigned_items")
    if not isinstance(assigned_items, list):
        return []
    return [str(item).strip() for item in assigned_items if str(item).strip()]


def _apply_partition_suffix(
    logicnodes: list[dict[str, Any]],
    partition_id: str,
) -> list[dict[str, Any]]:
    if not partition_id:
        return logicnodes

    updated_logicnodes: list[dict[str, Any]] = []
    for logicnode in logicnodes:
        if not isinstance(logicnode, dict):
            continue
        updated = dict(logicnode)
        base_node_id = str(updated.get("node_id", "")).strip() or (
            f"{POD_NAME}.partition.{partition_id}"
        )
        if not base_node_id.endswith(f".{partition_id}"):
            updated["node_id"] = f"{base_node_id}.{partition_id}"
        node_payload = updated.get("node")
        if isinstance(node_payload, dict):
            node_payload = dict(node_payload)
            nested_payload = node_payload.get("payload")
            if not isinstance(nested_payload, dict):
                nested_payload = {}
            else:
                nested_payload = dict(nested_payload)
            nested_payload["partition_id"] = partition_id
            node_payload["payload"] = nested_payload
            updated["node"] = node_payload
        updated_logicnodes.append(updated)
    return updated_logicnodes


def _logicnode_report_payload(
    agent_pipeline: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    result_payload = _safe_to_dict(agent_pipeline.get("result"))
    artifacts = result_payload.get("artifacts")
    if not isinstance(artifacts, list):
        artifacts = []
    report_payload = _safe_to_dict(agent_pipeline.get("report"))
    logicnodes = agent_pipeline.get("logicnodes")
    if not isinstance(logicnodes, list):
        logicnodes = []
    filtered_artifacts = [
        artifact for artifact in artifacts if isinstance(artifact, dict)
    ]
    return logicnodes, filtered_artifacts, report_payload


def _run_agent_pipeline(
    *,
    mission_id: str,
    resolved_agent_id: str,
    payload: dict[str, Any],
    extracted_logicnodes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    agent = make_agent(resolved_agent_id)
    agent_payload = dict(payload)
    if extracted_logicnodes is not None:
        agent_payload["logicnodes"] = extracted_logicnodes
    result = agent.execute(mission_id, agent_payload)
    validation = agent.validate(mission_id, getattr(result, "artifacts", []))
    report = agent.report(mission_id, result, validation)
    AGENT_EXECUTION_LATENCY.labels(
        pod_name=POD_NAME,
        agent_id=resolved_agent_id,
        category=agent.category,
    ).observe(time.perf_counter() - started)
    return {
        "agent": agent,
        "result": result,
        "validation": validation,
        "report": report,
        "logicnodes": _extract_logicnodes_from_agent_result(result),
    }


def _parse_date_time(value: str) -> datetime:
    return parse_date_time(value)


def _load_event_schema() -> dict[str, Any]:
    return load_event_schema(EVENT_SCHEMA_PATH)


def _load_topics() -> set[str]:
    return load_topics(TOPICS_PATH)


def _validate_envelope(envelope: dict[str, Any]) -> None:
    validate_envelope(
        envelope,
        schema=_load_event_schema(),
        topics=_load_topics(),
        payload_ref_pattern=PAYLOAD_REF_PATTERN,
    )


def _build_envelope(
    topic: str, correlation_id: str, payload_ref: str, schema_name: str
) -> dict[str, Any]:
    envelope = {
        "event_id": f"evt-{uuid.uuid4()}",
        "topic": topic,
        "timestamp": datetime.now(UTC).isoformat(),
        "producer": f"pod-worker-{POD_NAME}",
        "correlation_id": correlation_id,
        "payload_ref": payload_ref,
        "schema": schema_name,
        "priority": "NORMAL",
    }
    _validate_envelope(envelope)
    return envelope


async def _publish_event(
    redis_client: redis.Redis, topic: str, mission_id: str, payload: dict[str, Any]
) -> None:
    envelope = _build_envelope(
        topic=topic,
        correlation_id=mission_id,
        payload_ref=f"registry://missions/{mission_id}/pod/{POD_NAME}/{topic}",
        schema_name="pod.assignment.v1",
    )
    await redis_client.xadd(
        STATE_STREAM,
        {"envelope": json.dumps(envelope), "payload": json.dumps(payload)},
        maxlen=MAX_STREAM_LEN,
        approximate=True,
    )


async def _ensure_group(redis_client: redis.Redis) -> None:
    try:
        await redis_client.xgroup_create(
            name=STATE_STREAM,
            groupname=CONSUMER_GROUP,
            id="0",
            mkstream=True,
        )
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def _write_dlq(
    redis_client: redis.Redis,
    entry_id: str,
    fields: dict[str, Any],
    error: str,
) -> bool:
    try:
        await redis_client.xadd(
            POD_DLQ_STREAM,
            {
                "error": error,
                "entry_id": entry_id,
                "pod_name": POD_NAME,
                "envelope": fields.get("envelope", ""),
                "payload": fields.get("payload", ""),
                "ts": datetime.now(UTC).isoformat(),
            },
            maxlen=MAX_STREAM_LEN,
            approximate=True,
        )
        return True
    except Exception as dlq_exc:
        # Callers must not acknowledge (XACK) the original entry when this
        # returns False -- doing so previously removed the message from the
        # consumer group's pending-entries list while it was never actually
        # written to the DLQ, silently losing it forever with only this log
        # line as a trace. Leaving it unacknowledged keeps it visible via
        # XPENDING even though nothing currently reclaims it automatically.
        LOGGER.error("pod-worker failed to write entry %s to DLQ: %s", entry_id, dlq_exc)
        return False


async def _emit_audit_event(
    *,
    mission_id: str | None,
    agent_id: str | None,
    event_type: str,
    status: str = "SUCCESS",
    object_type: str | None = None,
    object_id: str | None = None,
    tool_name: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    payload_summary: dict[str, Any] | None = None,
) -> None:
    if not mission_id:
        return
    effective_agent_id = _effective_worker_agent_id(agent_id) or agent_id or "POD-WORKER"
    try:
        response = await _request(
            "POST",
            "/internal/audit-events",
            json_body={
                "mission_id": mission_id,
                "agent_id": effective_agent_id,
                "service_name": f"pod-worker-{POD_NAME}",
                "event_type": event_type,
                "status": status,
                "object_type": object_type,
                "object_id": object_id,
                "tool_name": tool_name,
                "started_at": started_at or datetime.now(UTC).isoformat(),
                "ended_at": ended_at or datetime.now(UTC).isoformat(),
                "payload_summary": _summarize_mapping(payload_summary),
            },
            agent_id=effective_agent_id,
            emit_audit=False,
        )
        if response.status_code >= 400:
            LOGGER.warning(
                "pod-worker failed to persist audit event %s for mission %s: %s",
                event_type,
                mission_id,
                response.status_code,
            )
    except Exception as exc:
        LOGGER.warning(
            "pod-worker failed to emit audit event %s for mission %s: %s",
            event_type,
            mission_id,
            exc,
        )


async def _request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    agent_id: str | None = None,
    emit_audit: bool = True,
) -> httpx.Response:
    if not path.startswith("/"):
        raise ValueError("request path must start with '/'")
    started_at = datetime.now(UTC).isoformat()
    request_id = f"pod-{POD_NAME}-{uuid.uuid4()}"
    last_response: httpx.Response | None = None
    last_error: Exception | None = None
    api_key = _service_api_key_for_agent(agent_id)
    headers = {"x-api-key": api_key, "x-request-id": request_id}
    normalized_agent_id = _normalize_agent_id(agent_id)
    if normalized_agent_id:
        headers["x-agent-id"] = normalized_agent_id

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        for attempt in range(1, REQUEST_MAX_RETRIES + 1):
            try:
                response = await client.request(
                    method,
                    f"{ORCHESTRATOR_URL}{path}",
                    json=json_body,
                    params=params,
                    headers=headers,
                )
                last_response = response
                if response.status_code in {401, 403}:
                    global INTERNAL_AUTH_FAILURES, LAST_INTERNAL_AUTH_STATUS
                    INTERNAL_AUTH_FAILURES += 1
                    LAST_INTERNAL_AUTH_STATUS = response.status_code
                    INTERNAL_AUTH_REJECTIONS.labels(pod_name=POD_NAME).inc()
                if response.status_code < 500 and response.status_code != 429:
                    return response
            except httpx.HTTPError as exc:
                last_error = exc
            if attempt < REQUEST_MAX_RETRIES:
                await asyncio.sleep(min(2 ** attempt * 0.5, 30.0))

    if last_response is not None:
        if emit_audit and path != "/internal/audit-events":
            await _emit_audit_event(
                mission_id=_mission_id_for_request(path, json_body=json_body, params=params),
                agent_id=agent_id,
                event_type="TOOL_HTTP_REQUEST",
                status="SUCCESS" if last_response.status_code < 400 else "ERROR",
                object_type="http_request",
                object_id=path,
                tool_name="orchestrator_api",
                started_at=started_at,
                ended_at=datetime.now(UTC).isoformat(),
                payload_summary={
                    "method": method,
                    "path": path,
                    "status_code": last_response.status_code,
                },
            )
        return last_response
    if last_error is not None:
        raise last_error
    raise RuntimeError("request failed without response")


async def _post_agent_heartbeat(
    *,
    agent_id: str | None,
    mission_id: str | None,
    state: str,
    queue_depth: int,
    workload_pct: int,
    metadata: dict[str, Any] | None = None,
) -> bool:
    effective_agent_id = _effective_worker_agent_id(agent_id)
    if effective_agent_id is None:
        return False
    response = await _request(
        "POST",
        "/internal/agents/heartbeat",
        json_body={
            "agent_id": effective_agent_id,
            "state": state,
            "queue_depth": max(0, queue_depth),
            "workload_pct": max(0, min(100, workload_pct)),
            "active_mission_ids": [mission_id] if mission_id else [],
            "metadata": {
                "producer": f"pod-worker-{POD_NAME}",
                "pod_name": POD_NAME,
                **(metadata or {}),
            },
        },
        agent_id=effective_agent_id,
    )
    status = "success" if response.status_code < 400 else "error"
    AGENT_HEARTBEAT_ATTEMPTS.labels(
        pod_name=POD_NAME,
        agent_id=effective_agent_id,
        status=status,
    ).inc()
    return response.status_code < 400


async def _has_assignment(mission_id: str) -> bool:
    response = await _request("GET", f"/internal/missions/{mission_id}/pod-assignment")
    if response.status_code == 404:
        return False
    if response.status_code >= 400:
        return False
    assignment = response.json()
    return bool(assignment.get("pod_name"))


async def _fetch_mission_snapshot(mission_id: str) -> dict[str, Any] | None:
    response = await _request("GET", f"/missions/{mission_id}")
    if response.status_code >= 400:
        return None
    mission = response.json()
    return mission if isinstance(mission, dict) else None


async def _fetch_mission_agent_id(mission_id: str) -> str | None:
    mission = await _fetch_mission_snapshot(mission_id)
    if mission is None:
        return None

    for key in ("agent_id", "target_agent_id", "selected_agent_id", "assigned_agent_id"):
        normalized = _normalize_agent_id(mission.get(key))
        if normalized:
            return normalized
    return _agent_id_from_metadata(mission.get("metadata"))


async def _mission_matches_agent_binding(mission_id: str, payload: dict[str, Any]) -> bool:
    if not AGENT_BINDING_SET:
        return True

    mission_agent_id = _agent_id_from_payload(payload)
    if mission_agent_id is None:
        mission_agent_id = await _fetch_mission_agent_id(mission_id)
    if mission_agent_id is None:
        BINDING_SKIPS.labels(pod_name=POD_NAME, reason="agent-unresolved").inc()
        return False
    if mission_agent_id not in AGENT_BINDING_SET:
        BINDING_SKIPS.labels(pod_name=POD_NAME, reason="agent-mismatch").inc()
        return False
    return True


def _mission_targets_supported_language(target_language: str) -> bool:
    if target_language and target_language not in SUPPORTED_LANGUAGES:
        return False
    if not target_language and POD_NAME != "podA":
        return False
    return True


async def _handle_pod_manager_assignment(
    redis_client: redis.Redis,
    payload: dict[str, Any],
) -> None:
    mission_id = str(payload.get("mission_id", ""))
    if not mission_id:
        return

    target = payload.get("requested_target_language")
    target_language = str(target).lower() if isinstance(target, str) else ""
    if not _mission_targets_supported_language(target_language):
        return
    if not await _mission_matches_agent_binding(mission_id, payload):
        return

    mission_snapshot = await _fetch_mission_snapshot(mission_id)
    metadata = mission_snapshot.get("metadata") if isinstance(mission_snapshot, dict) else {}
    resolved_agent_id = (
        _agent_id_from_payload(payload)
        or _agent_id_from_metadata(metadata)
        or await _fetch_mission_agent_id(mission_id)
        or _default_agent_id_for_event("MISSION_POD_MANAGER_ASSIGNED", target_language)
        or "UNBOUND"
    )
    if resolved_agent_id == "UNBOUND":
        return

    await _post_agent_heartbeat(
        agent_id=resolved_agent_id,
        mission_id=mission_id,
        state="RUNNING",
        queue_depth=1,
        workload_pct=44,
        metadata={"event_type": "MISSION_POD_MANAGER_ASSIGNED"},
    )

    if await _has_assignment(mission_id):
        return

    details = {
        "assigned_by": "pod-worker",
        "pod_name": POD_NAME,
        "agent_id": resolved_agent_id,
        "supported_languages": sorted(SUPPORTED_LANGUAGES),
        "reason": "pod-manager-routing",
    }
    assignment_response = await _request(
        "POST",
        "/internal/pod-assignment",
        json_body={
            "mission_id": mission_id,
            "pod_name": POD_NAME,
            "metadata": details,
        },
        agent_id=resolved_agent_id,
    )
    if assignment_response.status_code == 409:
        return
    if assignment_response.status_code >= 400:
        return

    execution_started_at = datetime.now(UTC).isoformat()
    await _emit_audit_event(
        mission_id=mission_id,
        agent_id=resolved_agent_id,
        event_type="AGENT_EXECUTION_STARTED",
        status="STARTED",
        object_type="agent_execution",
        object_id=resolved_agent_id,
        payload_summary={
            "agent_id": resolved_agent_id,
            "event_type": "MISSION_POD_MANAGER_ASSIGNED",
        },
    )
    try:
        agent_pipeline = _run_agent_pipeline(
            mission_id=mission_id,
            resolved_agent_id=resolved_agent_id,
            payload={
                **payload,
                "pod_manager_agent_id": resolved_agent_id,
                "specialist_agent_id": (
                    metadata.get("assigned_specialist_agent_id")
                    if isinstance(metadata, dict)
                    else None
                ),
                "requested_target_language": target_language,
            },
        )
    except Exception as exc:
        await _emit_audit_event(
            mission_id=mission_id,
            agent_id=resolved_agent_id,
            event_type="AGENT_EXECUTION_COMPLETED",
            status="ERROR",
            object_type="agent_execution",
            object_id=resolved_agent_id,
            started_at=execution_started_at,
            ended_at=datetime.now(UTC).isoformat(),
            payload_summary={"agent_id": resolved_agent_id, "error": str(exc)},
        )
        raise
    await _emit_audit_event(
        mission_id=mission_id,
        agent_id=resolved_agent_id,
        event_type="AGENT_EXECUTION_COMPLETED",
        object_type="agent_execution",
        object_id=resolved_agent_id,
        started_at=execution_started_at,
        ended_at=datetime.now(UTC).isoformat(),
        payload_summary={
            "agent_id": resolved_agent_id,
            "category": getattr(agent_pipeline["agent"], "category", "pod_manager"),
            "validation": _summarize_mapping(_safe_to_dict(agent_pipeline["validation"])),
        },
    )

    await _request(
        "POST",
        "/internal/knowledge",
        json_body={
            "mission_id": mission_id,
            "knowledge_id": f"{POD_NAME}.pod-manager.{mission_id}",
            "content": {
                "summary": _safe_to_dict(agent_pipeline["report"]).get(
                    "summary",
                    f"{resolved_agent_id} accepted pod assignment.",
                ),
                "metadata": {
                    "pod_name": POD_NAME,
                    "source": "pod-worker",
                    "agent_id": resolved_agent_id,
                    "agent_category": getattr(agent_pipeline["agent"], "category", "pod_manager"),
                    "validation": _safe_to_dict(agent_pipeline["validation"]),
                    "report": _safe_to_dict(agent_pipeline["report"]),
                },
            },
        },
        agent_id=resolved_agent_id,
    )
    await _emit_audit_event(
        mission_id=mission_id,
        agent_id=resolved_agent_id,
        event_type="AGENT_REPORT_PERSISTED",
        object_type="knowledge",
        object_id=f"{POD_NAME}.pod-manager.{mission_id}",
        payload_summary={"agent_id": resolved_agent_id, "category": "pod_manager"},
    )

    await _publish_event(
        redis_client,
        f"cluster.assigned.{POD_NAME}",
        mission_id,
        {
            "mission_id": mission_id,
            "pod_name": POD_NAME,
            "event_type": "MISSION_POD_ASSIGNED",
            "state": payload.get("state", "POD_ASSIGNED"),
            "agent_id": resolved_agent_id,
        },
    )
    await _post_agent_heartbeat(
        agent_id=resolved_agent_id,
        mission_id=mission_id,
        state="ACTIVE",
        queue_depth=0,
        workload_pct=28,
        metadata={"event_type": "MISSION_POD_MANAGER_ASSIGNED", "status": "complete"},
    )


async def _handle_running_mission(redis_client: redis.Redis, payload: dict[str, Any]) -> None:
    mission_id = str(payload.get("mission_id", ""))
    if not mission_id:
        return

    target = payload.get("requested_target_language")
    target_language = str(target).lower() if isinstance(target, str) else ""
    if not _mission_targets_supported_language(target_language):
        return
    if not await _mission_matches_agent_binding(mission_id, payload):
        return
    has_assignment = await _has_assignment(mission_id)
    mission_snapshot = await _fetch_mission_snapshot(mission_id)
    mission_metadata = (
        mission_snapshot.get("metadata") if isinstance(mission_snapshot, dict) else {}
    )
    resolved_agent_id = (
        _agent_id_from_payload(payload)
        or _agent_id_from_metadata(mission_metadata)
        or await _fetch_mission_agent_id(mission_id)
        or _default_agent_id_for_event("MISSION_RUNNING", target_language)
        or "UNBOUND"
    )
    if (
        isinstance(mission_metadata, dict)
        and mission_metadata.get("scaling_active") is True
        and isinstance(mission_metadata.get("scaling_decision"), dict)
        and int(mission_metadata.get("scaling_decision", {}).get("instance_count", 1)) > 1
    ):
        return

    await _post_agent_heartbeat(
        agent_id=resolved_agent_id,
        mission_id=mission_id,
        state="RUNNING",
        queue_depth=1,
        workload_pct=56,
        metadata={"event_type": "MISSION_RUNNING"},
    )

    if not has_assignment:
        details = {
            "assigned_by": "pod-worker",
            "pod_name": POD_NAME,
            "agent_id": resolved_agent_id,
            "supported_languages": sorted(SUPPORTED_LANGUAGES),
            "reason": "language-match",
        }
        assignment_response = await _request(
            "POST",
            "/internal/pod-assignment",
            json_body={
                "mission_id": mission_id,
                "pod_name": POD_NAME,
                "metadata": details,
            },
            agent_id=resolved_agent_id,
        )
        if assignment_response.status_code >= 400 and assignment_response.status_code != 409:
            return

    # --- Language extraction --------------------------------------------------
    # source_code may arrive directly in the state-stream event (future) or
    # be stored in mission metadata (current path: gateway stores it there so
    # workers can retrieve it via the mission snapshot fetched above).
    source_code = (
        payload.get("source_code")
        or (mission_metadata.get("source_code") if isinstance(mission_metadata, dict) else None)
        or ""
    )
    source_file = str(
        payload.get("source_file")
        or (mission_metadata.get("source_file") if isinstance(mission_metadata, dict) else None)
        or source_code
    )
    extraction_language = target_language or "python"  # default Pod A primary
    extraction_summary: dict = {"language": extraction_language, "concepts_found": 0}
    extracted_logicnodes: list[dict[str, Any]] = []
    focus_domains = _focus_domains_for_pod(mission_metadata)
    doc_context = await _fetch_doc_context(mission_id, extraction_language)

    if source_code:
        started = time.perf_counter()
        extractor = _get_extractor(extraction_language)
        result = extractor.extract(
            source_code,
            focus_domains=focus_domains,
            doc_context=doc_context,
        )
        EXTRACTION_LATENCY.labels(pod_name=POD_NAME, agent_id=resolved_agent_id).observe(
            time.perf_counter() - started
        )
        CONCEPTS_EXTRACTED.labels(
            pod_name=POD_NAME,
            agent_id=resolved_agent_id,
            language=extraction_language,
        ).inc(
            len(result.concepts)
        )
        extraction_summary = result.summary
        extraction_summary["focus_domains"] = focus_domains
        extraction_summary["doc_context_ready"] = bool(doc_context)
        extracted_logicnodes = _logicnodes_from_extraction(
            mission_id=mission_id,
            target_language=target_language,
            extraction_language=extraction_language,
            concepts=result.concepts,
            source_file=source_file,
            agent_id=resolved_agent_id,
            # AST-derived signatures live on a sibling list; pass them so
            # types.in/types.out can be populated where they exist (UPG-31).
            # Read defensively: an extractor result without structural info
            # must degrade to empty types, never fail the mission.
            functions=getattr(result, "functions", None),
        )

    if not extracted_logicnodes:
        extracted_logicnodes = [
            _routing_stub_logicnode(
                mission_id=mission_id,
                extraction_language=extraction_language,
                target_language=target_language,
                agent_id=resolved_agent_id,
            )
        ]

    for logicnode in extracted_logicnodes:
        logicnode["agent_id"] = resolved_agent_id

    execution_started_at = datetime.now(UTC).isoformat()
    await _emit_audit_event(
        mission_id=mission_id,
        agent_id=resolved_agent_id,
        event_type="AGENT_EXECUTION_STARTED",
        status="STARTED",
        object_type="agent_execution",
        object_id=resolved_agent_id,
        payload_summary={"agent_id": resolved_agent_id, "event_type": "MISSION_RUNNING"},
    )
    try:
        agent_pipeline = _run_agent_pipeline(
            mission_id=mission_id,
            resolved_agent_id=resolved_agent_id,
            payload={
                **payload,
                "source_payload": source_code,
                "requested_target_language": extraction_language,
                "agent_id": resolved_agent_id,
            },
            extracted_logicnodes=extracted_logicnodes,
        )
    except Exception as exc:
        await _emit_audit_event(
            mission_id=mission_id,
            agent_id=resolved_agent_id,
            event_type="AGENT_EXECUTION_COMPLETED",
            status="ERROR",
            object_type="agent_execution",
            object_id=resolved_agent_id,
            started_at=execution_started_at,
            ended_at=datetime.now(UTC).isoformat(),
            payload_summary={"agent_id": resolved_agent_id, "error": str(exc)},
        )
        raise

    final_logicnodes = agent_pipeline["logicnodes"] or extracted_logicnodes
    refined_ir_module = build_refined_ir_module(
        mission_id=mission_id,
        agent_id=resolved_agent_id,
        source_language=extraction_language,
        target_language=target_language or extraction_language,
        logicnodes=final_logicnodes,
        source_ref=f"mission://{mission_id}",
    )
    refined_ir_store_record: dict[str, Any] | None = None
    refined_ir_status = "SUCCESS"
    if REFINED_IR_STORE_PATH:
        try:
            store_record = write_refined_ir_module(
                refined_ir_module,
                store_root=REFINED_IR_STORE_PATH,
                mission_id=mission_id,
                agent_id=resolved_agent_id,
            )
            refined_ir_store_record = {
                "path": store_record.relative_path,
                "git_commit": store_record.git_commit,
                "sha256": store_record.sha256,
            }
        except Exception as exc:
            LOGGER.exception("refined_ir write failed for mission %s", mission_id)
            refined_ir_store_record = {"error": str(exc)}
            refined_ir_status = "ERROR"
    if refined_ir_store_record is not None:
        await _emit_audit_event(
            mission_id=mission_id,
            agent_id=resolved_agent_id,
            event_type="TOOL_REFINED_IR_WRITTEN",
            status=refined_ir_status,
            object_type="refined_ir",
            object_id=mission_id,
            tool_name="refined_ir",
            payload_summary=refined_ir_store_record,
        )
    for logicnode in final_logicnodes:
        node_id = str(logicnode.get("node_id", "")).strip() or f"{POD_NAME}.core.{mission_id}"
        node_payload = _coerce_schema_node(
            logicnode,
            node_id=node_id,
            extraction_language=extraction_language,
            target_language=target_language,
            agent_id=resolved_agent_id,
        )
        await _request(
            "POST",
            "/internal/logicnodes",
            json_body={
                "mission_id": mission_id,
                "node_id": node_id,
                "node": node_payload,
            },
            agent_id=resolved_agent_id,
        )

    await _request(
        "POST",
        "/internal/knowledge",
        json_body={
            "mission_id": mission_id,
            "knowledge_id": f"{POD_NAME}.assignment.{mission_id}",
            "content": {
                "summary": _safe_to_dict(agent_pipeline["report"]).get(
                    "summary",
                    f"{POD_NAME} accepted mission for specialist routing.",
                ),
                "metadata": {
                    "pod_name": POD_NAME,
                    "source": "pod-worker",
                    "extraction": extraction_summary,
                    "agent_id": resolved_agent_id,
                    "agent_category": getattr(agent_pipeline["agent"], "category", "specialist"),
                    "agent_result": _safe_to_dict(agent_pipeline["result"]),
                    "validation": _safe_to_dict(agent_pipeline["validation"]),
                    "report": _safe_to_dict(agent_pipeline["report"]),
                    "refined_ir_module": refined_ir_module.model_dump(by_alias=True),
                    "refined_ir_store": refined_ir_store_record,
                },
            },
        },
        agent_id=resolved_agent_id,
    )
    await _emit_audit_event(
        mission_id=mission_id,
        agent_id=resolved_agent_id,
        event_type="AGENT_REPORT_PERSISTED",
        object_type="knowledge",
        object_id=f"{POD_NAME}.assignment.{mission_id}",
        payload_summary={
            "agent_id": resolved_agent_id,
            "logicnode_count": len(final_logicnodes),
            "artifact_count": len(
                _safe_to_dict(agent_pipeline["result"]).get("artifacts", []) or []
            ),
        },
    )
    await _emit_audit_event(
        mission_id=mission_id,
        agent_id=resolved_agent_id,
        event_type="AGENT_EXECUTION_COMPLETED",
        object_type="agent_execution",
        object_id=resolved_agent_id,
        started_at=execution_started_at,
        ended_at=datetime.now(UTC).isoformat(),
        payload_summary={
            "agent_id": resolved_agent_id,
            "category": getattr(agent_pipeline["agent"], "category", "specialist"),
            "logicnode_count": len(final_logicnodes),
            "validation": _summarize_mapping(_safe_to_dict(agent_pipeline["validation"])),
        },
    )

    await _publish_event(
        redis_client,
        f"cluster.assigned.{POD_NAME}",
        mission_id,
        {
            "mission_id": mission_id,
            "pod_name": POD_NAME,
            "event_type": "MISSION_POD_ASSIGNED",
            "state": payload.get("state", "RUNNING"),
            "agent_id": resolved_agent_id,
        },
    )
    await _publish_event(
        redis_client,
        "pod.standard.ready",
        mission_id,
        {
            "mission_id": mission_id,
            "pod_name": POD_NAME,
            "event_type": "POD_READY",
            "state": payload.get("state", "RUNNING"),
            "agent_id": resolved_agent_id,
        },
    )
    await _post_agent_heartbeat(
        agent_id=resolved_agent_id,
        mission_id=mission_id,
        state="ACTIVE",
        queue_depth=0,
        workload_pct=24,
        metadata={"event_type": "MISSION_RUNNING", "status": "complete"},
    )


async def _handle_partition_ready(redis_client: redis.Redis, payload: dict[str, Any]) -> None:
    mission_id = str(payload.get("mission_id", ""))
    partition_id = _partition_id(payload)
    if not mission_id or not partition_id:
        return

    target = payload.get("requested_target_language")
    target_language = str(target).lower() if isinstance(target, str) else ""
    if not _mission_targets_supported_language(target_language):
        return
    if not await _mission_matches_agent_binding(mission_id, payload):
        return

    mission_snapshot = await _fetch_mission_snapshot(mission_id)
    mission_metadata = (
        mission_snapshot.get("metadata")
        if isinstance(mission_snapshot, dict)
        else {}
    )
    resolved_agent_id = (
        _agent_id_from_payload(payload)
        or _agent_id_from_metadata(mission_metadata)
        or await _fetch_mission_agent_id(mission_id)
        or _default_agent_id_for_event("MISSION_RUNNING", target_language)
        or "UNBOUND"
    )
    if resolved_agent_id == "UNBOUND":
        return

    await _post_agent_heartbeat(
        agent_id=resolved_agent_id,
        mission_id=mission_id,
        state="RUNNING",
        queue_depth=1,
        workload_pct=64,
        metadata={"event_type": "MISSION_PARTITION_READY", "partition_id": partition_id},
    )

    source_code = (
        payload.get("source_code")
        or (mission_metadata.get("source_code") if isinstance(mission_metadata, dict) else None)
        or ""
    )
    source_code = _subset_source_bundle(source_code, _partition_items(payload))
    source_file = str(
        payload.get("source_file")
        or (mission_metadata.get("source_file") if isinstance(mission_metadata, dict) else None)
        or source_code
    )
    extraction_language = target_language or "python"
    extraction_summary: dict[str, Any] = {"language": extraction_language, "concepts_found": 0}
    extracted_logicnodes: list[dict[str, Any]] = []
    focus_domains = _focus_domains_for_pod(mission_metadata)
    doc_context = await _fetch_doc_context(mission_id, extraction_language)

    if source_code:
        started = time.perf_counter()
        extractor = _get_extractor(extraction_language)
        result = extractor.extract(
            source_code,
            focus_domains=focus_domains,
            doc_context=doc_context,
        )
        EXTRACTION_LATENCY.labels(pod_name=POD_NAME, agent_id=resolved_agent_id).observe(
            time.perf_counter() - started
        )
        CONCEPTS_EXTRACTED.labels(
            pod_name=POD_NAME,
            agent_id=resolved_agent_id,
            language=extraction_language,
        ).inc(len(result.concepts))
        extraction_summary = result.summary
        extraction_summary["focus_domains"] = focus_domains
        extraction_summary["doc_context_ready"] = bool(doc_context)
        extracted_logicnodes = _logicnodes_from_extraction(
            mission_id=mission_id,
            target_language=target_language,
            extraction_language=extraction_language,
            concepts=result.concepts,
            source_file=source_file,
            agent_id=resolved_agent_id,
            # AST-derived signatures live on a sibling list; pass them so
            # types.in/types.out can be populated where they exist (UPG-31).
            # Read defensively: an extractor result without structural info
            # must degrade to empty types, never fail the mission.
            functions=getattr(result, "functions", None),
        )

    if not extracted_logicnodes:
        extracted_logicnodes = [
            _routing_stub_logicnode(
                mission_id=mission_id,
                extraction_language=extraction_language,
                target_language=target_language,
                agent_id=resolved_agent_id,
            )
        ]

    for logicnode in extracted_logicnodes:
        logicnode["agent_id"] = resolved_agent_id

    execution_started_at = datetime.now(UTC).isoformat()
    await _emit_audit_event(
        mission_id=mission_id,
        agent_id=resolved_agent_id,
        event_type="AGENT_EXECUTION_STARTED",
        status="STARTED",
        object_type="agent_execution",
        object_id=resolved_agent_id,
        payload_summary={
            "agent_id": resolved_agent_id,
            "event_type": "MISSION_PARTITION_READY",
            "partition_id": partition_id,
        },
    )
    try:
        agent_pipeline = _run_agent_pipeline(
            mission_id=mission_id,
            resolved_agent_id=resolved_agent_id,
            payload={
                **payload,
                "source_payload": source_code,
                "requested_target_language": extraction_language,
                "agent_id": resolved_agent_id,
                "partition_id": partition_id,
                "partition_items": _partition_items(payload),
            },
            extracted_logicnodes=extracted_logicnodes,
        )
    except Exception as exc:
        await _emit_audit_event(
            mission_id=mission_id,
            agent_id=resolved_agent_id,
            event_type="AGENT_EXECUTION_COMPLETED",
            status="ERROR",
            object_type="agent_execution",
            object_id=resolved_agent_id,
            started_at=execution_started_at,
            ended_at=datetime.now(UTC).isoformat(),
            payload_summary={
                "agent_id": resolved_agent_id,
                "partition_id": partition_id,
                "error": str(exc),
            },
        )
        raise

    final_logicnodes = _apply_partition_suffix(
        agent_pipeline["logicnodes"] or extracted_logicnodes,
        partition_id,
    )
    refined_ir_module = build_refined_ir_module(
        mission_id=mission_id,
        agent_id=resolved_agent_id,
        source_language=extraction_language,
        target_language=target_language or extraction_language,
        logicnodes=final_logicnodes,
        source_ref=f"mission://{mission_id}/partitions/{partition_id}",
    )
    refined_ir_store_record: dict[str, Any] | None = None
    refined_ir_status = "SUCCESS"
    if REFINED_IR_STORE_PATH:
        try:
            store_record = write_refined_ir_module(
                refined_ir_module,
                store_root=REFINED_IR_STORE_PATH,
                mission_id=mission_id,
                agent_id=resolved_agent_id,
            )
            refined_ir_store_record = {
                "path": store_record.relative_path,
                "git_commit": store_record.git_commit,
                "sha256": store_record.sha256,
            }
        except Exception as exc:
            LOGGER.exception(
                "refined_ir write failed for mission %s partition %s",
                mission_id,
                partition_id,
            )
            refined_ir_store_record = {"error": str(exc)}
            refined_ir_status = "ERROR"
    if refined_ir_store_record is not None:
        await _emit_audit_event(
            mission_id=mission_id,
            agent_id=resolved_agent_id,
            event_type="TOOL_REFINED_IR_WRITTEN",
            status=refined_ir_status,
            object_type="refined_ir",
            object_id=f"{mission_id}:{partition_id}",
            tool_name="refined_ir",
            payload_summary=refined_ir_store_record,
        )

    for logicnode in final_logicnodes:
        node_id = str(logicnode.get("node_id", "")).strip() or (
            f"{POD_NAME}.core.{mission_id}.{partition_id}"
        )
        node_payload = _coerce_schema_node(
            logicnode,
            node_id=node_id,
            extraction_language=extraction_language,
            target_language=target_language,
            agent_id=resolved_agent_id,
        )
        node_payload["payload"]["partition_id"] = partition_id
        await _request(
            "POST",
            "/internal/logicnodes",
            json_body={
                "mission_id": mission_id,
                "node_id": node_id,
                "node": node_payload,
            },
            agent_id=resolved_agent_id,
        )

    (
        partition_logicnodes,
        partition_artifacts,
        partition_report,
    ) = _logicnode_report_payload(agent_pipeline)
    partition_logicnodes = _apply_partition_suffix(
        partition_logicnodes or final_logicnodes,
        partition_id,
    )

    await _request(
        "POST",
        "/internal/knowledge",
        json_body={
            "mission_id": mission_id,
            "knowledge_id": f"{POD_NAME}.partition.{partition_id}.{mission_id}",
            "content": {
                "summary": partition_report.get(
                    "summary",
                    f"{POD_NAME} completed partition {partition_id}.",
                ),
                "metadata": {
                    "pod_name": POD_NAME,
                    "source": "pod-worker",
                    "partition_id": partition_id,
                    "assigned_items": _partition_items(payload),
                    "extraction": extraction_summary,
                    "agent_id": resolved_agent_id,
                    "agent_category": getattr(agent_pipeline["agent"], "category", "specialist"),
                    "agent_result": _safe_to_dict(agent_pipeline["result"]),
                    "validation": _safe_to_dict(agent_pipeline["validation"]),
                    "report": partition_report,
                    "refined_ir_module": refined_ir_module.model_dump(by_alias=True),
                    "refined_ir_store": refined_ir_store_record,
                },
            },
        },
        agent_id=resolved_agent_id,
    )
    await _emit_audit_event(
        mission_id=mission_id,
        agent_id=resolved_agent_id,
        event_type="AGENT_REPORT_PERSISTED",
        object_type="knowledge",
        object_id=f"{POD_NAME}.partition.{partition_id}.{mission_id}",
        payload_summary={
            "agent_id": resolved_agent_id,
            "partition_id": partition_id,
            "artifact_count": len(partition_artifacts),
        },
    )

    await _request(
        "POST",
        f"/internal/missions/{mission_id}/partition-results",
        json_body={
            "partition_id": partition_id,
            "instance_index": int(_partition_payload(payload).get("instance_index", 0)),
            "agent_id": resolved_agent_id,
            "logicnodes": partition_logicnodes,
            "artifacts": partition_artifacts,
            "report": partition_report,
        },
        agent_id=resolved_agent_id,
    )
    await _emit_audit_event(
        mission_id=mission_id,
        agent_id=resolved_agent_id,
        event_type="AGENT_EXECUTION_COMPLETED",
        object_type="agent_execution",
        object_id=resolved_agent_id,
        started_at=execution_started_at,
        ended_at=datetime.now(UTC).isoformat(),
        payload_summary={
            "agent_id": resolved_agent_id,
            "partition_id": partition_id,
            "logicnode_count": len(partition_logicnodes),
            "artifact_count": len(partition_artifacts),
            "validation": _summarize_mapping(_safe_to_dict(agent_pipeline["validation"])),
        },
    )

    await _publish_event(
        redis_client,
        "pod.standard.ready",
        mission_id,
        {
            "mission_id": mission_id,
            "pod_name": POD_NAME,
            "event_type": "MISSION_PARTITION_COMPLETE",
            "state": payload.get("state", "RUNNING"),
            "agent_id": resolved_agent_id,
            "partition_id": partition_id,
        },
    )
    await _post_agent_heartbeat(
        agent_id=resolved_agent_id,
        mission_id=mission_id,
        state="ACTIVE",
        queue_depth=0,
        workload_pct=18,
        metadata={
            "event_type": "MISSION_PARTITION_READY",
            "partition_id": partition_id,
            "status": "complete",
        },
    )


async def _consumer_loop(app: FastAPI) -> None:
    redis_client: redis.Redis = app.state.redis
    while True:
        try:
            records = await redis_client.xreadgroup(
                groupname=CONSUMER_GROUP,
                consumername=CONSUMER_NAME,
                streams={STATE_STREAM: ">"},
                count=20,
                block=5000,
            )
        except asyncio.CancelledError:
            raise
        except ResponseError as exc:
            if "NOGROUP" in str(exc):
                LOGGER.warning(
                    "state stream group %s missing for %s; recreating",
                    CONSUMER_GROUP,
                    STATE_STREAM,
                )
                await _ensure_group(redis_client)
                continue
            raise
        if not records:
            continue

        for _, entries in records:
            for entry_id, fields in entries:
                acknowledge = False
                started = time.perf_counter()
                agent_id = "UNKNOWN"
                try:
                    envelope_raw = fields.get("envelope")
                    payload_raw = fields.get("payload")
                    if not envelope_raw or not payload_raw:
                        raise ProtocolValidationError("missing envelope or payload")

                    envelope = json.loads(envelope_raw)
                    _validate_envelope(envelope)
                    payload = json.loads(payload_raw)
                    agent_id = _agent_id_from_payload(payload) or "UNKNOWN"
                    event_type = str(payload.get("event_type", ""))
                    if event_type == "MISSION_POD_MANAGER_ASSIGNED":
                        await _handle_pod_manager_assignment(redis_client, payload)
                        app.state.processed += 1
                        TASKS_PROCESSED.labels(pod_name=POD_NAME, agent_id=agent_id).inc()
                    elif event_type == "MISSION_RUNNING":
                        await _handle_running_mission(redis_client, payload)
                        app.state.processed += 1
                        TASKS_PROCESSED.labels(pod_name=POD_NAME, agent_id=agent_id).inc()
                    elif event_type == "MISSION_PARTITION_READY":
                        await _handle_partition_ready(redis_client, payload)
                        app.state.processed += 1
                        TASKS_PROCESSED.labels(pod_name=POD_NAME, agent_id=agent_id).inc()
                    acknowledge = True
                except (ProtocolValidationError, json.JSONDecodeError, KeyError, TypeError) as exc:
                    app.state.errors += 1
                    TASKS_FAILED.labels(pod_name=POD_NAME, agent_id="UNKNOWN").inc()
                    LOGGER.warning("discarding invalid state event %s: %s", entry_id, exc)
                    acknowledge = await _write_dlq(redis_client, entry_id, fields, str(exc))
                except Exception as exc:
                    app.state.errors += 1
                    TASKS_FAILED.labels(pod_name=POD_NAME, agent_id="UNKNOWN").inc()
                    LOGGER.warning("failed to process state event %s: %s", entry_id, exc)
                    # Unlike the branch above, this catch-all never used to
                    # acknowledge or DLQ the entry -- since nothing in this
                    # loop ever XCLAIMs/XAUTOCLAIMs pending entries, an
                    # unexpected exception (e.g. an httpx error deep in
                    # _handle_running_mission) permanently orphaned the
                    # message in the consumer group's PEL: never processed
                    # again, never visible in the DLQ, no operator signal at
                    # all beyond a single warning log line.
                    acknowledge = await _write_dlq(redis_client, entry_id, fields, str(exc))
                finally:
                    TASK_LATENCY_SECONDS.labels(
                        pod_name=POD_NAME,
                        agent_id=agent_id,
                    ).observe(
                        time.perf_counter() - started
                    )
                    if acknowledge:
                        await redis_client.xack(STATE_STREAM, CONSUMER_GROUP, entry_id)


async def _agent_heartbeat_loop(app: FastAPI) -> None:
    while True:
        try:
            effective_agent_id = _effective_worker_agent_id()
            if effective_agent_id:
                await _post_agent_heartbeat(
                    agent_id=effective_agent_id,
                    mission_id=None,
                    state="IDLE",
                    queue_depth=0,
                    workload_pct=8,
                    metadata={
                        "binding": list(AGENT_BINDINGS),
                        "supported_languages": sorted(SUPPORTED_LANGUAGES),
                    },
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOGGER.warning("failed to emit pod worker heartbeat: %s", exc)
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global INTERNAL_AUTH_FAILURES, LAST_INTERNAL_AUTH_STATUS
    app.state.redis = redis.from_url(REDIS_URL, decode_responses=True)
    app.state.consumer_task = None
    app.state.heartbeat_task = None
    app.state.processed = 0
    app.state.errors = 0
    INTERNAL_AUTH_FAILURES = 0
    LAST_INTERNAL_AUTH_STATUS = None

    enforce_production_service_auth_config(
        environment=ENVIRONMENT,
        service_api_key=SERVICE_API_KEY,
        key_mode=AGENT_SERVICE_KEY_MODE,
        required_agent_ids=(_effective_worker_agent_id(),),
        raw_mapping=AGENT_SERVICE_API_KEYS,
        service_name="pod-worker",
    )

    if AGENT_SERVICE_KEY_MODE == "shared":
        LOGGER.warning(
            "AGENT_SERVICE_KEY_MODE is 'shared'; all agents without a dedicated key will use "
            "the shared SERVICE_API_KEY. Set AGENT_SERVICE_KEY_MODE=strict in production."
        )
    if AGENT_BINDING_SET:
        _known_agent_pattern = re.compile(r"^AGENT-\d{2}-[A-Z0-9-]+$")
        _invalid_bindings = [aid for aid in AGENT_BINDINGS if not _known_agent_pattern.match(aid)]
        if _invalid_bindings:
            LOGGER.warning(
                "AGENT_BINDING contains unrecognized agent IDs: %s. "
                "These agents will never match any mission event.",
                ", ".join(_invalid_bindings),
            )

    await app.state.redis.ping()
    await _ensure_group(app.state.redis)
    app.state.consumer_task = asyncio.create_task(_consumer_loop(app))
    app.state.heartbeat_task = asyncio.create_task(_agent_heartbeat_loop(app))
    yield

    task = app.state.consumer_task
    if task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    heartbeat_task = app.state.heartbeat_task
    if heartbeat_task is not None:
        heartbeat_task.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat_task
    aclose = getattr(app.state.redis, "aclose", None)
    if callable(aclose):
        await aclose()
    else:
        close = getattr(app.state.redis, "close", None)
        if callable(close):
            result = close()
            if inspect.isawaitable(result):
                await result


app = FastAPI(title=f"HolyGrail Pod Worker ({POD_NAME})", version="0.1.0", lifespan=lifespan)
configure_tracing(app, service_name="pod-worker")


@app.get("/health")
async def health() -> dict[str, Any]:
    ready = False
    redis_client = getattr(app.state, "redis", None)
    if redis_client is not None:
        try:
            ready = bool(await redis_client.ping())
        except Exception:
            ready = False
    return {
        "ok": ready,
        "service": "pod-worker",
        "pod_name": POD_NAME,
        "supported_languages": sorted(SUPPORTED_LANGUAGES),
        "state_stream": STATE_STREAM,
        "group": CONSUMER_GROUP,
        "consumer": CONSUMER_NAME,
        "worker_agent_id": _effective_worker_agent_id(),
        "agent_binding": list(AGENT_BINDINGS),
        "agent_service_key_mode": AGENT_SERVICE_KEY_MODE,
        "configured_agent_service_keys": len(_configured_agent_service_key_map()),
        "processed": app.state.processed,
        "errors": app.state.errors,
        "internal_auth_failures": INTERNAL_AUTH_FAILURES,
        "last_internal_auth_status": LAST_INTERNAL_AUTH_STATUS,
    }


@app.get("/readyz")
async def readyz() -> dict[str, Any]:
    redis_client = getattr(app.state, "redis", None)
    if redis_client is None:
        raise HTTPException(status_code=503, detail="redis unavailable")
    try:
        ready = bool(await redis_client.ping())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"redis unavailable: {exc}") from exc
    if not ready:
        raise HTTPException(status_code=503, detail="redis unavailable")
    return {"ready": True, "service": "pod-worker", "pod_name": POD_NAME}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
