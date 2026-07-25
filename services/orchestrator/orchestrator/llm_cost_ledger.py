"""llm_cost_ledger.py — Token usage recording and cost summarisation.

Records every LLM call outcome into ``llm_usage_events`` and exposes a
per-mission summary consumed by the Mission Control cost panel and the
``GET /v1/missions/{id}/token-usage`` endpoint.

Pricing table is best-effort and may lag provider changes.  Any call whose
model is not in the table is recorded with ``pricing_known=False`` and
``estimated_cost_usd=NULL``.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from .storage_core import db_connect

# ---------------------------------------------------------------------------
# Pricing table — USD per 1 000 tokens (input, output)
# Update when providers publish new rates.
# ---------------------------------------------------------------------------
_PRICING: dict[str, dict[str, tuple[float, float]]] = {
    "openai": {
        "gpt-5.5": (0.005, 0.015),
        "gpt-5.3-codex": (0.010, 0.030),
        "gpt-4o": (0.0025, 0.010),
        "gpt-4o-mini": (0.000150, 0.000600),
        "o3": (0.010, 0.040),
        "o4-mini": (0.0011, 0.0044),
        "text-embedding-3-large": (0.00013, 0.0),
        "text-embedding-3-small": (0.00002, 0.0),
    },
    "anthropic": {
        "claude-opus-4-7": (0.015, 0.075),
        "claude-sonnet-4-6": (0.003, 0.015),
        "claude-haiku-4-5": (0.00025, 0.00125),
    },
    "gemini": {
        "gemini-3.6-flash": (0.00150, 0.009),          # GA July 2026 — $1.50/$9.00 per 1M
        "gemini-3.5-flash": (0.00150, 0.009),          # GA May 2026 — $1.50/$9.00 per 1M
        "gemini-3.1-pro-preview": (0.00200, 0.012),    # $2.00/$12.00 per 1M (≤200K ctx)
        "gemini-3.1-flash-lite": (0.000075, 0.0003),   # kept for legacy recorded events
        "gemini-embedding-001": (0.000025, 0.0),
    },

}


def _estimate_cost(
    provider: str, model: str, input_tokens: int, output_tokens: int
) -> tuple[float | None, bool]:
    """Return (cost_usd, pricing_known)."""
    rates = _PRICING.get(provider.lower(), {})
    if model not in rates:
        # Try prefix match for versioned model strings
        for key, rate in rates.items():
            if model.startswith(key) or key.startswith(model):
                input_rate, output_rate = rate
                cost = (input_tokens * input_rate + output_tokens * output_rate) / 1000.0
                return round(cost, 8), True
        return None, False
    input_rate, output_rate = rates[model]
    cost = (input_tokens * input_rate + output_tokens * output_rate) / 1000.0
    return round(cost, 8), True


def _insert_usage_sync(
    settings: Any,
    mission_id: str,
    agent_id: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    total: int,
    cost: float | None,
    pricing_known: bool,
    call_succeeded: bool,
    routing_source: str | None,
    created_at: datetime,
) -> None:
    """Synchronous DB write — called via asyncio.to_thread."""
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO llm_usage_events
                    (mission_id, agent_id, provider, model,
                     input_tokens, output_tokens, total_tokens,
                     estimated_cost_usd, pricing_known,
                     call_succeeded, routing_source, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    mission_id, agent_id, provider, model,
                    input_tokens, output_tokens, total,
                    cost, pricing_known,
                    call_succeeded, routing_source,
                    created_at,
                ),
            )


async def record_llm_usage(
    *,
    settings: Any,
    mission_id: str,
    agent_id: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    call_succeeded: bool = True,
    routing_source: str | None = None,
) -> None:
    """Persist one LLM call event. Never raises — cost tracking must not break mission flow."""
    try:
        total = input_tokens + output_tokens
        cost, pricing_known = _estimate_cost(provider, model, input_tokens, output_tokens)
        await asyncio.to_thread(
            _insert_usage_sync,
            settings, mission_id, agent_id, provider, model,
            input_tokens, output_tokens, total,
            cost, pricing_known,
            call_succeeded, routing_source,
            datetime.now(UTC),
        )
    except Exception:  # noqa: BLE001
        pass  # Cost tracking failure must never break mission flow


def _fetch_usage_rows_sync(settings: Any, mission_id: str) -> list:
    """Synchronous DB read — called via asyncio.to_thread."""
    with db_connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    agent_id, provider, model,
                    SUM(input_tokens)::int   AS input_tokens,
                    SUM(output_tokens)::int  AS output_tokens,
                    SUM(total_tokens)::int   AS total_tokens,
                    SUM(estimated_cost_usd)  AS cost_usd,
                    BOOL_AND(pricing_known)  AS pricing_known,
                    COUNT(*)::int            AS call_count
                FROM llm_usage_events
                WHERE mission_id = %s
                GROUP BY agent_id, provider, model
                ORDER BY SUM(total_tokens) DESC
                """,
                (mission_id,),
            )
            return cur.fetchall()


async def get_mission_token_usage(*, settings: Any, mission_id: str) -> dict[str, Any]:
    """Return aggregated token usage summary for a mission."""
    try:
        rows = await asyncio.to_thread(_fetch_usage_rows_sync, settings, mission_id)
    except Exception:  # noqa: BLE001
        rows = []

    by_agent: list[dict[str, Any]] = []
    by_provider: dict[str, dict[str, Any]] = {}
    total_input = total_output = total_tokens = 0
    total_cost: float | None = 0.0
    unknown_pricing = 0
    call_count = 0

    for row in rows:
        agent_id, provider, model, inp, out, tot, cost, pricing_known, calls = row
        by_agent.append({
            "agent_id": agent_id,
            "provider": provider,
            "model": model,
            "input_tokens": inp or 0,
            "output_tokens": out or 0,
            "cost_usd": float(cost) if cost is not None else None,
        })
        total_input += inp or 0
        total_output += out or 0
        total_tokens += tot or 0
        call_count += calls or 0
        if not pricing_known:
            unknown_pricing += 1
            total_cost = None
        elif total_cost is not None and cost is not None:
            total_cost += float(cost)

        pkey = f"{provider}::{model}"
        if pkey not in by_provider:
            by_provider[pkey] = {
                "provider": provider, "model": model,
                "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0,
            }
        by_provider[pkey]["input_tokens"] += inp or 0
        by_provider[pkey]["output_tokens"] += out or 0
        if cost is not None and by_provider[pkey]["estimated_cost_usd"] is not None:
            by_provider[pkey]["estimated_cost_usd"] += float(cost)
        else:
            by_provider[pkey]["estimated_cost_usd"] = None

    return {
        "mission_id": mission_id,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(total_cost, 6) if total_cost is not None else None,
        "unknown_pricing_count": unknown_pricing,
        "call_count": call_count,
        "by_provider": list(by_provider.values()),
        "by_agent": by_agent,
    }
