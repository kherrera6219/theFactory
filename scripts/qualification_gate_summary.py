from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SUITES: dict[str, dict[str, Any]] = {
    "operator_route_oidc_matrix": {
        "latest_file": "docs/evidence/operator_route_oidc_matrix_latest.json",
        "history_file": "docs/evidence/operator_route_oidc_matrix_history.jsonl",
    },
    "dedicated_agent_canary_trend": {
        "latest_file": "docs/evidence/dedicated_agent_canary_trend_latest.json",
        "history_file": "docs/evidence/dedicated_agent_canary_trend_history.jsonl",
    },
    "langgraph_v2_prototype_matrix": {
        "latest_file": "docs/evidence/langgraph_v2_prototype_matrix_latest.json",
        "history_file": "docs/evidence/langgraph_v2_prototype_matrix_history.jsonl",
    },
    "mission_artifact_qualification": {
        "latest_file": "docs/evidence/mission_artifact_qualification_latest.json",
        "history_file": "docs/evidence/mission_artifact_qualification_history.jsonl",
    },
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _parse_timestamp(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    candidate = raw.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _resolve_pass_flag(payload: dict[str, Any]) -> bool | None:
    for key in ("pass", "passed"):
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    summary = payload.get("summary")
    if isinstance(summary, dict):
        all_passed = summary.get("all_passed")
        if isinstance(all_passed, bool):
            return all_passed
    return None


def _extract_failure_reasons(payload: dict[str, Any]) -> list[str]:
    value = payload.get("failure_reasons")
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    summary = payload.get("summary")
    if isinstance(summary, dict):
        failed_languages = summary.get("failed_languages")
        if isinstance(failed_languages, list) and failed_languages:
            return [f"failed languages: {', '.join(str(item) for item in failed_languages)}"]
    return []


def _normalize_run(payload: dict[str, Any], *, source_path: str) -> dict[str, Any] | None:
    passed = _resolve_pass_flag(payload)
    timestamp = _parse_timestamp(
        payload.get("run_timestamp_utc")
        or payload.get("generated_at")
        or payload.get("evaluated_at")
    )
    if passed is None or timestamp is None:
        return None
    return {
        "run_timestamp_utc": timestamp.isoformat(),
        "passed": passed,
        "failure_reasons": _extract_failure_reasons(payload),
        "source_path": source_path,
        "output_file": str(payload.get("output_file", "")).strip() or source_path,
    }


def _collect_suite_runs(config: dict[str, Any]) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    seen: set[tuple[str, bool, str]] = set()

    history_file = ROOT / str(config.get("history_file", "")).strip()
    latest_file = ROOT / str(config.get("latest_file", "")).strip()

    for payload in _read_jsonl(history_file):
        normalized = _normalize_run(payload, source_path=str(history_file))
        if normalized is None:
            continue
        key = (
            normalized["run_timestamp_utc"],
            normalized["passed"],
            normalized["output_file"],
        )
        if key in seen:
            continue
        seen.add(key)
        runs.append(normalized)

    latest_payload = _read_json(latest_file)
    if latest_payload:
        normalized = _normalize_run(latest_payload, source_path=str(latest_file))
        if normalized is not None:
            key = (
                normalized["run_timestamp_utc"],
                normalized["passed"],
                normalized["output_file"],
            )
            if key not in seen:
                runs.append(normalized)

    runs.sort(key=lambda item: item["run_timestamp_utc"])
    return runs


def _summarize_suite(
    name: str,
    config: dict[str, Any],
    *,
    now: datetime,
) -> tuple[dict[str, Any], list[str]]:
    runs = _collect_suite_runs(config)
    required = bool(config.get("required", False))
    min_consecutive = max(1, int(config.get("min_consecutive_passes", 1)))
    max_age_days = float(config.get("max_age_days", 8))
    failure_reasons: list[str] = []

    latest_run = runs[-1] if runs else None
    consecutive_passes = 0
    for run in reversed(runs):
        if not run["passed"]:
            break
        consecutive_passes += 1

    latest_age_days: float | None = None
    latest_passed = False
    latest_output_file = None
    if latest_run is None:
        if required:
            failure_reasons.append("missing qualification evidence")
    else:
        latest_passed = bool(latest_run["passed"])
        latest_output_file = latest_run["output_file"]
        latest_dt = _parse_timestamp(latest_run["run_timestamp_utc"])
        if latest_dt is not None:
            latest_age_days = round((now - latest_dt).total_seconds() / 86400.0, 3)
            if latest_age_days > max_age_days:
                failure_reasons.append(
                    f"latest evidence age {latest_age_days}d exceeds {max_age_days}d"
                )
        if not latest_passed:
            failure_reasons.extend(latest_run["failure_reasons"] or ["latest qualification failed"])
        if consecutive_passes < min_consecutive:
            failure_reasons.append(
                f"consecutive passes {consecutive_passes} below required {min_consecutive}"
            )

    suite_report = {
        "required": required,
        "passed": not failure_reasons,
        "latest_run_timestamp_utc": latest_run["run_timestamp_utc"] if latest_run else None,
        "latest_age_days": latest_age_days,
        "latest_output_file": latest_output_file,
        "latest_passed": latest_passed,
        "consecutive_passes": consecutive_passes,
        "min_consecutive_passes": min_consecutive,
        "max_age_days": max_age_days,
        "history_points": len(runs),
        "failure_reasons": failure_reasons,
    }
    return suite_report, [f"{name}: {reason}" for reason in failure_reasons]


def build_summary(policy: dict[str, Any]) -> dict[str, Any]:
    requirements = policy.get("requirements", {}) if isinstance(policy, dict) else {}
    gate_policy = requirements.get("qualification_gates", {})
    suite_policy = gate_policy.get("suites", {}) if isinstance(gate_policy, dict) else {}
    suites = {
        name: {**DEFAULT_SUITES.get(name, {}), **config}
        for name, config in suite_policy.items()
        if isinstance(config, dict)
    }
    now = datetime.now(UTC)
    if not suites:
        suites = {
            name: {**config, "required": True, "min_consecutive_passes": 1, "max_age_days": 8}
            for name, config in DEFAULT_SUITES.items()
        }

    suite_reports: dict[str, Any] = {}
    failure_reasons: list[str] = []
    for name, config in suites.items():
        suite_report, suite_failures = _summarize_suite(name, config, now=now)
        suite_reports[name] = suite_report
        failure_reasons.extend(suite_failures)

    return {
        "generated_at": now.isoformat(),
        "policy_version": int(policy.get("version", 0)) if isinstance(policy, dict) else 0,
        "passed": not failure_reasons,
        "failure_reasons": failure_reasons,
        "suites": suite_reports,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize qualification evidence for release-threshold promotion gating."
    )
    parser.add_argument(
        "--policy-file",
        default="deploy/promotion-policy.json",
        help="Promotion policy JSON used to resolve suite thresholds",
    )
    parser.add_argument(
        "--output-file",
        default="docs/evidence/qualification_gate_summary_latest.json",
        help="Output JSON report path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    policy_path = Path(args.policy_file)
    policy = _read_json(policy_path)
    if not policy:
        raise RuntimeError(f"unable to read promotion policy: {policy_path}")
    payload = build_summary(policy)
    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output_file}")
    if payload["passed"]:
        print("PASS: qualification evidence satisfies configured thresholds")
        return 0
    print("FAIL: qualification evidence does not satisfy configured thresholds")
    for reason in payload["failure_reasons"]:
        print(f"- {reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
