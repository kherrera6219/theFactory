"""storage_logicnodes.py — LogicNode and knowledge-fragment persistence."""
from __future__ import annotations

import json
from typing import Any

from .settings import Settings
from .storage_core import _json_to_dict, _to_iso, db_connect


def upsert_logicnode(
    settings: Settings,
    mission_id: str,
    node_id: str,
    node: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    with db_connect(settings) as conn:
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

    return {
        "mission_id": row[0],
        "node_id": row[1],
        "node": _json_to_dict(row[2]),
        "created_at": _to_iso(row[3]),
    }


def list_logicnodes(settings: Settings, mission_id: str, limit: int) -> list[dict[str, Any]]:
    with db_connect(settings) as conn:
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
    with db_connect(settings) as conn:
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
    with db_connect(settings) as conn:
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


def list_knowledge(settings: Settings, mission_id: str, limit: int) -> list[dict[str, Any]]:
    with db_connect(settings) as conn:
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
