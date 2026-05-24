from __future__ import annotations

import base64
import json
import time
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .data_plane_metrics import (
    observe_optional_adapter_operation,
    set_optional_adapter_enabled,
    set_optional_adapter_ready,
)
from .storage_core import factory_json_dumps
from .settings import Settings

_SCHEMA_CACHE: set[str] = set()
_ADAPTER = "neo4j"


def _cache_key(settings: Settings) -> str:
    return (
        f"{settings.neo4j_url.rstrip('/')}:"
        f"{settings.neo4j_database}:"
        f"{settings.neo4j_username}"
    )


def _request_json(
    settings: Settings,
    path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from .tracing import current_trace_id, current_span_id
    url = _validated_http_url(settings.neo4j_url, path, service="neo4j")
    auth = f"{settings.neo4j_username}:{settings.neo4j_password}".encode("utf-8")
    token = base64.b64encode(auth).decode("ascii")
    body = factory_json_dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Basic {token}",
    }
    trace_id = current_trace_id()
    if trace_id:
        headers["x-trace-id"] = trace_id
    span_id = current_span_id()
    if span_id:
        headers["x-span-id"] = span_id

    request = Request(
        url,
        method="POST",
        data=body,
        headers=headers,
    )
    with urlopen(request, timeout=settings.neo4j_timeout_seconds) as response:  # nosec B310
        raw = response.read().decode("utf-8")
    if not raw:
        return {}
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def _validated_http_url(base_url: str, path: str, *, service: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{service} url must use http or https")
    if not path.startswith("/"):
        raise ValueError("request path must start with '/'")
    return f"{base_url.rstrip('/')}{path}"


def _execute_cypher(
    settings: Settings,
    statement: str,
    parameters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    payload = {
        "statements": [
            {
                "statement": statement,
                "parameters": parameters or {},
            }
        ]
    }
    response = _request_json(
        settings,
        f"/db/{settings.neo4j_database}/tx/commit",
        payload,
    )

    errors = response.get("errors", []) if isinstance(response, dict) else []
    if errors:
        first = errors[0] if isinstance(errors[0], dict) else {}
        code = str(first.get("code", "Neo4jError"))
        message = str(first.get("message", "unknown neo4j error"))
        raise RuntimeError(f"{code}: {message}")

    results = response.get("results", []) if isinstance(response, dict) else []
    return results if isinstance(results, list) else []


def _query_rows(
    settings: Settings,
    statement: str,
    parameters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    results = _execute_cypher(settings, statement, parameters)
    if not results:
        return []
    first = results[0] if isinstance(results[0], dict) else {}
    columns = first.get("columns", []) if isinstance(first, dict) else []
    data = first.get("data", []) if isinstance(first, dict) else []
    if not isinstance(columns, list) or not isinstance(data, list):
        return []

    rows: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        row = entry.get("row", [])
        if not isinstance(row, list):
            continue
        rows.append({str(columns[i]): row[i] for i in range(min(len(columns), len(row)))})
    return rows


def ensure_schema(settings: Settings) -> None:
    set_optional_adapter_enabled(_ADAPTER, enabled=settings.neo4j_enabled)
    if not settings.neo4j_enabled:
        return

    cache_key = _cache_key(settings)
    if cache_key in _SCHEMA_CACHE:
        return

    started = time.perf_counter()
    success = False
    try:
        _execute_cypher(
            settings,
            "CREATE CONSTRAINT mission_id_unique IF NOT EXISTS "
            "FOR (m:Mission) REQUIRE m.mission_id IS UNIQUE",
        )
        _execute_cypher(
            settings,
            "CREATE CONSTRAINT knowledge_composite_unique IF NOT EXISTS "
            "FOR (k:Knowledge) REQUIRE (k.mission_id, k.knowledge_id) IS UNIQUE",
        )
        _execute_cypher(
            settings,
            "CREATE CONSTRAINT audit_composite_unique IF NOT EXISTS "
            "FOR (a:AuditReport) REQUIRE (a.mission_id, a.audit_id) IS UNIQUE",
        )
        _SCHEMA_CACHE.add(cache_key)
        success = True
    finally:
        observe_optional_adapter_operation(
            adapter=_ADAPTER,
            operation="ensure_schema",
            duration_seconds=time.perf_counter() - started,
            success=success,
        )


def neo4j_ready(settings: Settings) -> bool:
    set_optional_adapter_enabled(_ADAPTER, enabled=settings.neo4j_enabled)
    if not settings.neo4j_enabled:
        set_optional_adapter_ready(_ADAPTER, ready=False)
        return False

    started = time.perf_counter()
    ready = False
    try:
        ensure_schema(settings)
        rows = _query_rows(settings, "RETURN 1 AS ok")
        ready = bool(rows and rows[0].get("ok") == 1)
    except Exception:
        set_optional_adapter_ready(_ADAPTER, ready=False)
        observe_optional_adapter_operation(
            adapter=_ADAPTER,
            operation="ready_check",
            duration_seconds=time.perf_counter() - started,
            success=False,
        )
        return False
    set_optional_adapter_ready(_ADAPTER, ready=ready)
    observe_optional_adapter_operation(
        adapter=_ADAPTER,
        operation="ready_check",
        duration_seconds=time.perf_counter() - started,
        success=ready,
    )
    return ready


def upsert_knowledge(
    settings: Settings,
    mission_id: str,
    knowledge_id: str,
    content: dict[str, Any],
    created_at: str,
) -> None:
    started = time.perf_counter()
    success = False
    try:
        ensure_schema(settings)
        _execute_cypher(
            settings,
            "MERGE (m:Mission {mission_id: $mission_id}) "
            "ON CREATE SET m.created_at = $created_at "
            "SET m.updated_at = $created_at "
            "MERGE (k:Knowledge {mission_id: $mission_id, knowledge_id: $knowledge_id}) "
            "SET k.content_json = $content_json, "
            "    k.created_at = $created_at, "
            "    k.updated_at = $created_at "
            "MERGE (m)-[:HAS_KNOWLEDGE]->(k)",
            {
                "mission_id": mission_id,
                "knowledge_id": knowledge_id,
                "content_json": json.dumps(content, separators=(",", ":"), sort_keys=True),
                "created_at": created_at,
            },
        )
        success = True
    finally:
        observe_optional_adapter_operation(
            adapter=_ADAPTER,
            operation="upsert_knowledge",
            duration_seconds=time.perf_counter() - started,
            success=success,
        )


def upsert_audit_report(
    settings: Settings,
    mission_id: str,
    audit_id: str,
    status: str,
    report: dict[str, Any],
    created_at: str,
) -> None:
    started = time.perf_counter()
    success = False
    try:
        ensure_schema(settings)
        _execute_cypher(
            settings,
            "MERGE (m:Mission {mission_id: $mission_id}) "
            "ON CREATE SET m.created_at = $created_at "
            "SET m.updated_at = $created_at "
            "MERGE (a:AuditReport {mission_id: $mission_id, audit_id: $audit_id}) "
            "SET a.status = $status, "
            "    a.report_json = $report_json, "
            "    a.created_at = $created_at, "
            "    a.updated_at = $created_at "
            "MERGE (m)-[:HAS_AUDIT_REPORT]->(a)",
            {
                "mission_id": mission_id,
                "audit_id": audit_id,
                "status": status,
                "report_json": json.dumps(report, separators=(",", ":"), sort_keys=True),
                "created_at": created_at,
            },
        )
        success = True
    finally:
        observe_optional_adapter_operation(
            adapter=_ADAPTER,
            operation="upsert_audit_report",
            duration_seconds=time.perf_counter() - started,
            success=success,
        )


def list_mission_graph(settings: Settings, mission_id: str, limit: int) -> list[dict[str, Any]]:
    started = time.perf_counter()
    success = False
    try:
        ensure_schema(settings)
        query_limit = max(1, min(limit, 500))
        rows = _query_rows(
            settings,
            "MATCH (m:Mission {mission_id: $mission_id})-[rel]->(n) "
            "RETURN type(rel) AS relation_type, "
            "       labels(n) AS target_labels, "
            "       properties(n) AS target_properties "
            "ORDER BY coalesce(n.created_at, '') DESC "
            "LIMIT $limit",
            {
                "mission_id": mission_id,
                "limit": query_limit,
            },
        )

        results: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            labels = row.get("target_labels", [])
            props = row.get("target_properties", {})
            results.append(
                {
                    "relation_type": str(row.get("relation_type", "")),
                    "target_labels": labels if isinstance(labels, list) else [],
                    "target_properties": props if isinstance(props, dict) else {},
                }
            )
        success = True
        return results
    finally:
        observe_optional_adapter_operation(
            adapter=_ADAPTER,
            operation="list_mission_graph",
            duration_seconds=time.perf_counter() - started,
            success=success,
        )
