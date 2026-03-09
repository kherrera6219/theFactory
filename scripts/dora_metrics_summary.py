from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = REPO_ROOT / "docs" / "evidence"


def _run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _parse_iso(value: str) -> datetime:
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _event_timestamp(payload: dict[str, Any]) -> datetime | None:
    for key in ("evaluated_at", "generated_at", "finished_at", "started_at", "ts"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return _parse_iso(value)
    return None


def load_deployments(lookback_days: int) -> list[dict[str, Any]]:
    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    output = _run_git(
        "for-each-ref",
        "--sort=-creatordate",
        "--format=%(refname:short)|%(creatordate:iso-strict)|%(objectname)",
        "refs/tags",
    )
    deployments: list[dict[str, Any]] = []
    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        tag, created_at, commit_sha = raw_line.split("|", 2)
        if not tag.startswith("v"):
            continue
        deployed_at = _parse_iso(created_at)
        if deployed_at < cutoff:
            continue
        commit_timestamp = _parse_iso(_run_git("show", "-s", "--format=%cI", commit_sha).strip())
        lead_time_hours = round(
            max(0.0, (deployed_at - commit_timestamp).total_seconds() / 3600.0),
            2,
        )
        deployments.append(
            {
                "tag": tag,
                "commit": commit_sha,
                "deployed_at": deployed_at.isoformat(),
                "commit_timestamp": commit_timestamp.isoformat(),
                "lead_time_hours": lead_time_hours,
            }
        )
    return deployments


def load_qualification_histories() -> dict[str, list[dict[str, Any]]]:
    histories: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(EVIDENCE_DIR.glob("*_history.jsonl")):
        suite_name = path.name.replace("_history.jsonl", "")
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            payload = json.loads(raw_line)
            if not isinstance(payload, dict):
                continue
            timestamp = _event_timestamp(payload)
            if timestamp is None:
                continue
            histories[suite_name].append(
                {
                    "passed": bool(payload.get("passed", False)),
                    "timestamp": timestamp,
                }
            )
    return histories


def compute_dora_summary(
    *,
    deployments: list[dict[str, Any]],
    qualification_histories: dict[str, list[dict[str, Any]]],
    lookback_days: int,
) -> dict[str, Any]:
    lead_times = [float(record["lead_time_hours"]) for record in deployments]
    total_qualification_runs = 0
    failed_qualification_runs = 0
    restore_durations_minutes: list[float] = []

    for suite_events in qualification_histories.values():
        events = sorted(suite_events, key=lambda item: item["timestamp"])
        open_failure_started_at: datetime | None = None
        for event in events:
            total_qualification_runs += 1
            if not bool(event["passed"]):
                failed_qualification_runs += 1
                if open_failure_started_at is None:
                    open_failure_started_at = event["timestamp"]
                continue
            if open_failure_started_at is not None:
                restore_durations_minutes.append(
                    max(
                        0.0,
                        (event["timestamp"] - open_failure_started_at).total_seconds() / 60.0,
                    )
                )
                open_failure_started_at = None

    deployment_frequency_per_week = round(len(deployments) / max(1.0, lookback_days / 7.0), 2)
    lead_time_hours_mean = round(mean(lead_times), 2) if lead_times else None
    lead_time_hours_p95 = (
        round(sorted(lead_times)[int(0.95 * (len(lead_times) - 1))], 2) if lead_times else None
    )
    change_failure_rate = (
        round(failed_qualification_runs / total_qualification_runs, 4)
        if total_qualification_runs
        else None
    )
    mttr_minutes = round(mean(restore_durations_minutes), 2) if restore_durations_minutes else None

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "lookback_days": lookback_days,
        "methodology": {
            "deployment_frequency": "release tags matching v* within lookback window",
            "lead_time": "tag creation time minus tagged commit timestamp",
            "change_failure_rate": "qualification history failures divided by total runs",
            "mttr": "time from failed qualification run to next passing run per suite",
        },
        "deployments": deployments,
        "qualification_suite_count": len(qualification_histories),
        "metrics": {
            "deployment_frequency_per_week": deployment_frequency_per_week,
            "lead_time_hours_mean": lead_time_hours_mean,
            "lead_time_hours_p95": lead_time_hours_p95,
            "change_failure_rate": change_failure_rate,
            "mean_time_to_restore_minutes": mttr_minutes,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate DORA metrics summary from repo evidence."
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=84,
        help="Window for release-tag deployment frequency and lead-time calculations.",
    )
    parser.add_argument(
        "--output-file",
        default="docs/evidence/dora_metrics_latest.json",
        help="Path for generated DORA metrics summary JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    deployments = load_deployments(max(7, args.lookback_days))
    qualification_histories = load_qualification_histories()
    summary = compute_dora_summary(
        deployments=deployments,
        qualification_histories=qualification_histories,
        lookback_days=max(7, args.lookback_days),
    )
    output_path = Path(args.output_file)
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    output_label = (
        output_path.relative_to(REPO_ROOT) if output_path.is_relative_to(REPO_ROOT) else output_path
    )
    print(
        f"wrote DORA summary to {output_label}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
