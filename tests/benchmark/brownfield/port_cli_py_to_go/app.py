from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def summarize_events(lines: list[str]) -> dict[str, Any]:
    """Aggregate JSONL category event counts and elapsed milliseconds."""
    by_category: dict[str, dict[str, int]] = {}
    total_events = 0
    total_ms = 0

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        category = str(payload.get("category") or "").strip()
        if not category:
            raise ValueError("category is required")
        ms = int(payload.get("ms", 0))
        if ms < 0:
            raise ValueError("ms must be non-negative")
        bucket = by_category.setdefault(category, {"count": 0, "total_ms": 0})
        bucket["count"] += 1
        bucket["total_ms"] += ms
        total_events += 1
        total_ms += ms

    ordered = {key: by_category[key] for key in sorted(by_category)}
    return {
        "total_events": total_events,
        "total_ms": total_ms,
        "by_category": ordered,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate JSONL telemetry events.")
    parser.add_argument("--input", required=True, help="Path to JSONL input file or '-' for stdin")
    args = parser.parse_args(argv)

    if args.input == "-":
        lines = sys.stdin.read().splitlines()
    else:
        lines = Path(args.input).read_text(encoding="utf-8").splitlines()
    result = summarize_events(lines)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
