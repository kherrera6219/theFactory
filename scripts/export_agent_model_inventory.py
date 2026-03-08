from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_ROOT = ROOT / "services" / "orchestrator"
if str(ORCHESTRATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_ROOT))

from orchestrator.agent_integrations import build_agent_integrations_snapshot  # noqa: E402


def _classify_lifecycle(model: str) -> str:
    normalized = model.strip().lower()
    if not normalized:
        return "unknown"
    if any(token in normalized for token in ("preview", "experimental", "-exp", " beta", "-beta")):
        return "preview"
    if "latest" in normalized:
        return "rolling"
    return "stable"


def _production_approved(lifecycle: str) -> bool:
    return lifecycle == "stable"


def build_inventory() -> dict[str, Any]:
    snapshot = build_agent_integrations_snapshot()
    lifecycle_counts: Counter[str] = Counter()
    model_index: dict[tuple[str, str], dict[str, Any]] = {}
    agent_rows: list[dict[str, Any]] = []

    for record in snapshot.get("agents", []):
        if not isinstance(record, dict):
            continue
        recommendation = record.get("llm_recommendation")
        if not isinstance(recommendation, dict):
            continue

        provider = str(recommendation.get("provider", "")).strip().lower()
        model = str(recommendation.get("model", "")).strip()
        lifecycle = _classify_lifecycle(model)
        fallback_model = str(recommendation.get("fallback_model", "")).strip()
        fallback_lifecycle = _classify_lifecycle(fallback_model) if fallback_model else "none"
        agent_row = {
            "agent_id": str(record.get("agent_id", "")).strip(),
            "provider": provider,
            "model": model,
            "lifecycle": lifecycle,
            "production_approved": _production_approved(lifecycle),
            "fallback_provider": str(recommendation.get("fallback_provider", "")).strip().lower(),
            "fallback_model": fallback_model,
            "fallback_lifecycle": fallback_lifecycle,
            "fallback_production_approved": (
                _production_approved(fallback_lifecycle) if fallback_model else True
            ),
        }
        agent_rows.append(agent_row)
        lifecycle_counts[lifecycle] += 1

        key = (provider, model)
        if key not in model_index:
            model_index[key] = {
                "provider": provider,
                "model": model,
                "lifecycle": lifecycle,
                "production_approved": _production_approved(lifecycle),
                "agents": [],
            }
        model_index[key]["agents"].append(agent_row["agent_id"])

    model_rows = sorted(
        model_index.values(),
        key=lambda item: (str(item.get("provider", "")), str(item.get("model", ""))),
    )
    for row in model_rows:
        row["agents"] = sorted(str(agent_id) for agent_id in row.get("agents", []))

    blocked_agents = [
        row["agent_id"]
        for row in agent_rows
        if not row["production_approved"] or not row["fallback_production_approved"]
    ]

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "services/orchestrator/orchestrator/agent_integrations.py",
        "summary": {
            "total_agents": len(agent_rows),
            "lifecycle_counts": dict(sorted(lifecycle_counts.items())),
            "blocked_agent_count": len(blocked_agents),
            "blocked_agents": sorted(blocked_agents),
        },
        "models": model_rows,
        "agents": sorted(agent_rows, key=lambda item: item["agent_id"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export machine-readable LLM model inventory for promotion governance."
    )
    parser.add_argument(
        "--output-file",
        default="docs/evidence/agent_model_inventory_latest.json",
        help="Output inventory JSON path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_inventory()
    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
