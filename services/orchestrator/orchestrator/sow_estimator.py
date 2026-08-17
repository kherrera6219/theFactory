"""Factory-run cost estimator (LLM tokens + wall-clock). Pure — no I/O.

Estimates follow the Cone of Uncertainty: a range (likely / high) plus a
spend cap, never a single-point bid. Overhead multipliers cover retries,
system prompts, and context (1.7× likely, 2.0× high). Rates come from
``llm_cost_ledger`` so this module cannot drift from the live price table.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .llm_cost_ledger import _estimate_cost

LIKELY_OVERHEAD = 1.7
HIGH_OVERHEAD = 2.0
CAP_FACTOR = 1.5

_COMPLEXITY_SCALE = {
    "low": 0.7,
    "medium": 1.0,
    "high": 1.5,
    "very_high": 2.2,
}

# Typical successful-path calls: (agent_id, input_tokens, output_tokens)
_CALL_GRAPH: dict[str, list[tuple[str, int, int]]] = {
    "BUILD_NEW": [
        ("AGENT-01-PM", 2500, 800),
        ("AGENT-02-CEO", 1800, 600),
        ("AGENT-SPECIALIST", 4000, 2500),
        ("AGENT-10-TESTER", 2000, 1500),
        ("AGENT-41-RQCA", 1500, 400),
        ("AGENT-05-SECURITY", 1200, 400),
    ],
    "IMPORT_MODERNIZE": [
        ("AGENT-01-PM", 3000, 900),
        ("AGENT-02-CEO", 2000, 700),
        ("AGENT-SPECIALIST", 5000, 2800),
        ("AGENT-10-TESTER", 2200, 1600),
        ("AGENT-41-RQCA", 1600, 400),
        ("AGENT-05-SECURITY", 1400, 400),
    ],
    "PORT": [
        ("AGENT-01-PM", 3000, 900),
        ("AGENT-02-CEO", 2000, 700),
        ("AGENT-SPECIALIST-EXTRACT", 3500, 1800),
        ("AGENT-SPECIALIST-GENERATE", 5000, 3000),
        ("AGENT-10-TESTER", 2400, 1700),
        ("AGENT-41-RQCA", 1800, 500),
        ("AGENT-05-SECURITY", 1400, 400),
    ],
    "ANALYZE_ONLY": [
        ("AGENT-01-PM", 2200, 700),
        ("AGENT-02-CEO", 1200, 400),
        ("AGENT-SPECIALIST", 2500, 1200),
    ],
    "DEBUG_REPAIR": [
        ("AGENT-01-PM", 2500, 800),
        ("AGENT-02-CEO", 1800, 600),
        ("AGENT-SPECIALIST", 4500, 2600),
        ("AGENT-10-TESTER", 2000, 1500),
        ("AGENT-41-RQCA", 1500, 400),
    ],
}

_MINUTES = {
    "BUILD_NEW": (8, 20),
    "IMPORT_MODERNIZE": (12, 30),
    "PORT": (15, 40),
    "ANALYZE_ONLY": (5, 12),
    "DEBUG_REPAIR": (10, 25),
}


def _call_graph_for(mission_type: str) -> list[tuple[str, int, int]]:
    return list(_CALL_GRAPH.get(str(mission_type or "BUILD_NEW").upper(), _CALL_GRAPH["BUILD_NEW"]))


def estimate_mission_cost(
    *,
    mission_type: str = "BUILD_NEW",
    complexity: str = "medium",
    provider: str = "gemini",
    model: str = "gemini-3.7-flash",
) -> dict[str, Any]:
    """Return a range estimate. No I/O. Does not invent labor dollars."""
    scale = _COMPLEXITY_SCALE.get(str(complexity or "medium").strip().lower(), 1.0)
    raw = 0.0
    pricing_known = True
    for _agent, inp, out in _call_graph_for(mission_type):
        cost, known = _estimate_cost(
            provider,
            model,
            int(inp * scale),
            int(out * scale),
        )
        if not known or cost is None:
            pricing_known = False
        else:
            raw += cost
    likely = round(raw * LIKELY_OVERHEAD, 6) if pricing_known else None
    high = round(raw * HIGH_OVERHEAD, 6) if pricing_known else None
    cap = round(high * CAP_FACTOR, 6) if high is not None else None
    low_m, high_m = _MINUTES.get(str(mission_type or "BUILD_NEW").upper(), (8, 20))
    return {
        "likely_usd": likely,
        "high_usd": high,
        "cap_usd": cap,
        "pricing_known": pricing_known,
        "provider": provider,
        "model": model,
        "estimated_minutes_low": int(round(low_m * scale)),
        "estimated_minutes_high": int(round(high_m * scale)),
        "basis": (
            f"{mission_type} / {complexity} / {len(_call_graph_for(mission_type))} calls / "
            f"{provider}:{model} / overhead {LIKELY_OVERHEAD}×–{HIGH_OVERHEAD}×"
        ),
        "pricing_as_of": datetime.now(UTC).date().isoformat(),
    }


def estimate_change_order(
    *,
    prior: dict[str, Any] | None,
    mission_type: str = "IMPORT_MODERNIZE",
    complexity: str = "medium",
    provider: str = "gemini",
    model: str = "gemini-3.7-flash",
) -> dict[str, Any]:
    """Quote the new factory run and the delta versus the prior accepted bid.

    A change order is still a full factory run (tokens for this mission). The
    delta is informational: how this quote compares to the last accepted SOW.
    """
    fresh = estimate_mission_cost(
        mission_type=mission_type,
        complexity=complexity,
        provider=provider,
        model=model,
    )
    prior = prior if isinstance(prior, dict) else {}
    prior_likely = prior.get("likely_usd")
    prior_cap = prior.get("cap_usd")
    delta_likely = None
    if (
        fresh.get("pricing_known")
        and isinstance(fresh.get("likely_usd"), (int, float))
        and isinstance(prior_likely, (int, float))
    ):
        delta_likely = round(float(fresh["likely_usd"]) - float(prior_likely), 6)
    fresh["change_order"] = True
    fresh["prior_likely_usd"] = prior_likely if isinstance(prior_likely, (int, float)) else None
    fresh["prior_cap_usd"] = prior_cap if isinstance(prior_cap, (int, float)) else None
    fresh["delta_likely_usd"] = delta_likely
    fresh["basis"] = (
        f"change_order vs prior likely={prior_likely} cap={prior_cap} | {fresh.get('basis')}"
    )
    return fresh
