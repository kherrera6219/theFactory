"""storage_logicnodes.py — LogicNode and knowledge-fragment persistence."""
from __future__ import annotations

import json
import logging
from typing import Any

from .settings import Settings
from .storage_core import _json_to_dict, _to_iso, get_connection

LOGGER = logging.getLogger(__name__)


def upsert_logicnode(
    settings: Settings,
    mission_id: str,
    node_id: str,
    node: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    """Insert or update one mission LogicNode and mirror it when configured."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mission_logicnodes (mission_id, node_id, node_json, created_at)
                VALUES (%s, %s, %s::jsonb, %s::timestamptz)
                ON CONFLICT (mission_id, node_id) DO UPDATE SET
                    node_json = EXCLUDED.node_json,
                    created_at = EXCLUDED.created_at
                RETURNING mission_id, node_id, node_json, created_at
                """,
                (mission_id, node_id, json.dumps(node), created_at),
            )
            row = cur.fetchone()

    result = {
        "mission_id": row[0],
        "node_id": row[1],
        "node": _json_to_dict(row[2]),
        "created_at": _to_iso(row[3]),
    }

    # Mirror into Neo4j graph when enabled — non-fatal if Neo4j is unavailable.
    if settings.neo4j_enabled:
        try:
            from . import neo4j_store
            neo4j_store.upsert_logicnode(
                settings, mission_id, node_id, node, created_at
            )
        except Exception as exc:  # nosec B110
            LOGGER.warning(
                "neo4j logicnode mirror failed for %s/%s: %s", mission_id, node_id, exc
            )

    return result


def upsert_logicnodes_batch(
    conn: Any,
    mission_id: str,
    nodes: list[dict[str, Any]],
) -> int:
    """Bulk-upsert LogicNodes on an existing connection.

    Each item in ``nodes`` must provide ``node_id``, ``node`` (dict), and
    ``created_at`` (ISO timestamp). Uses ``executemany`` with the same
    ON CONFLICT upsert as ``upsert_logicnode``. Returns rows affected.

    The caller owns the connection; this does not mirror into Neo4j. Pass a
    pooled connection from ``get_connection()``.
    """
    if not nodes:
        return 0

    params = [
        (
            mission_id,
            node["node_id"],
            json.dumps(node["node"]),
            node["created_at"],
        )
        for node in nodes
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO mission_logicnodes (mission_id, node_id, node_json, created_at)
            VALUES (%s, %s, %s::jsonb, %s::timestamptz)
            ON CONFLICT (mission_id, node_id) DO UPDATE SET
                node_json = EXCLUDED.node_json,
                created_at = EXCLUDED.created_at
            """,
            params,
        )
        return cur.rowcount


def list_logicnodes(settings: Settings, mission_id: str, limit: int) -> list[dict[str, Any]]:
    """List recent LogicNodes for one mission."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mission_id, node_id, node_json, created_at
                FROM mission_logicnodes
                WHERE mission_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (mission_id, limit),
            )
            rows = cur.fetchall()

    return [
        {
            "mission_id": row[0],
            "node_id": row[1],
            "node": _json_to_dict(row[2]),
            "created_at": _to_iso(row[3]),
        }
        for row in rows
    ]


def list_recent_logicnodes(settings: Settings, limit: int) -> list[dict[str, Any]]:
    """List recent LogicNodes across missions."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mission_id, node_id, node_json, created_at
                FROM mission_logicnodes
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "mission_id": row[0],
            "node_id": row[1],
            "node": _json_to_dict(row[2]),
            "created_at": _to_iso(row[3]),
        }
        for row in rows
    ]


def upsert_knowledge(
    settings: Settings,
    mission_id: str,
    knowledge_id: str,
    content: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    """Insert or update one mission knowledge fragment."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mission_knowledge (mission_id, knowledge_id, content_json, created_at)
                VALUES (%s, %s, %s::jsonb, %s::timestamptz)
                ON CONFLICT (mission_id, knowledge_id) DO UPDATE SET
                    content_json = EXCLUDED.content_json,
                    created_at = EXCLUDED.created_at
                RETURNING mission_id, knowledge_id, content_json, created_at
                """,
                (mission_id, knowledge_id, json.dumps(content), created_at),
            )
            row = cur.fetchone()

    return {
        "mission_id": row[0],
        "knowledge_id": row[1],
        "content": _json_to_dict(row[2]),
        "created_at": _to_iso(row[3]),
    }


def upsert_knowledge_batch(
    conn: Any,
    mission_id: str,
    items: list[dict[str, Any]],
) -> int:
    """Bulk-upsert knowledge fragments on an existing connection.

    Each item in ``items`` must provide ``knowledge_id``, ``content`` (dict),
    and ``created_at`` (ISO timestamp). Uses ``executemany`` with the same
    ON CONFLICT upsert as ``upsert_knowledge``. Returns rows affected.

    The caller owns the connection; pass a pooled connection from
    ``get_connection()``.
    """
    if not items:
        return 0

    params = [
        (
            mission_id,
            item["knowledge_id"],
            json.dumps(item["content"]),
            item["created_at"],
        )
        for item in items
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO mission_knowledge (mission_id, knowledge_id, content_json, created_at)
            VALUES (%s, %s, %s::jsonb, %s::timestamptz)
            ON CONFLICT (mission_id, knowledge_id) DO UPDATE SET
                content_json = EXCLUDED.content_json,
                created_at = EXCLUDED.created_at
            """,
            params,
        )
        return cur.rowcount


def list_knowledge(settings: Settings, mission_id: str, limit: int) -> list[dict[str, Any]]:
    """List recent knowledge fragments for one mission."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mission_id, knowledge_id, content_json, created_at
                FROM mission_knowledge
                WHERE mission_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (mission_id, limit),
            )
            rows = cur.fetchall()

    return [
        {
            "mission_id": row[0],
            "knowledge_id": row[1],
            "content": _json_to_dict(row[2]),
            "created_at": _to_iso(row[3]),
        }
        for row in rows
    ]
