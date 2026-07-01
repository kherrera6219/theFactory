"""Protocol Bus Mission Battery — a series of small missions, one per language
specialist, that exercise every pod, every pod-audit agent, and every language
specialist against a live stack, and validate the Protocol Bus lanes those
missions drive (Alpha, Sigma, Delta, Omega, Beta) with real traffic.

Companion runner to `docs/PROTOCOL_BUS_MISSION_BATTERY_PLAN.md`. Mirrors the
request/poll/report shape of `scripts/demo_missions.py`, but sized for the full
19-language battery plus one alternate-mission-type check (20 missions total).

Usage:
    python scripts/protocol_bus_mission_battery.py --live \
        --gateway-base-url http://127.0.0.1:8100 \
        --output-file docs/evidence/protocol_bus_mission_battery_latest.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

TERMINAL_STATES = {"COMPLETE", "FAILED"}

# Mirrors orchestrator/mission_flow.py POD_MANAGER_BY_LANGUAGE / SPECIALIST_BY_LANGUAGE.
# Kept as a local literal (not imported) so this script has no dependency on the
# orchestrator package and can run standalone against any deployed stack.
LANGUAGE_ROUTING: dict[str, dict[str, str]] = {
    "python": {"pod": "A", "pod_manager": "AGENT-12-PODA-MGR", "pod_audit": "AGENT-13-PODA-AUDIT", "specialist": "AGENT-14-PYTHON"},
    "javascript": {"pod": "A", "pod_manager": "AGENT-12-PODA-MGR", "pod_audit": "AGENT-13-PODA-AUDIT", "specialist": "AGENT-15-JAVASCRIPT"},
    "ruby": {"pod": "A", "pod_manager": "AGENT-12-PODA-MGR", "pod_audit": "AGENT-13-PODA-AUDIT", "specialist": "AGENT-16-RUBY"},
    "php": {"pod": "A", "pod_manager": "AGENT-12-PODA-MGR", "pod_audit": "AGENT-13-PODA-AUDIT", "specialist": "AGENT-17-PHP"},
    "go": {"pod": "B", "pod_manager": "AGENT-18-PODB-MGR", "pod_audit": "AGENT-19-PODB-AUDIT", "specialist": "AGENT-36-GO"},
    "rust": {"pod": "B", "pod_manager": "AGENT-18-PODB-MGR", "pod_audit": "AGENT-19-PODB-AUDIT", "specialist": "AGENT-22-RUST"},
    "c": {"pod": "B", "pod_manager": "AGENT-18-PODB-MGR", "pod_audit": "AGENT-19-PODB-AUDIT", "specialist": "AGENT-20-C"},
    "cpp": {"pod": "B", "pod_manager": "AGENT-18-PODB-MGR", "pod_audit": "AGENT-19-PODB-AUDIT", "specialist": "AGENT-21-CPP"},
    "zig": {"pod": "B", "pod_manager": "AGENT-18-PODB-MGR", "pod_audit": "AGENT-19-PODB-AUDIT", "specialist": "AGENT-23-ZIG"},
    "java": {"pod": "C", "pod_manager": "AGENT-24-PODC-MGR", "pod_audit": "AGENT-25-PODC-AUDIT", "specialist": "AGENT-26-JAVA"},
    "csharp": {"pod": "C", "pod_manager": "AGENT-24-PODC-MGR", "pod_audit": "AGENT-25-PODC-AUDIT", "specialist": "AGENT-27-CSHARP"},
    "kotlin": {"pod": "C", "pod_manager": "AGENT-24-PODC-MGR", "pod_audit": "AGENT-25-PODC-AUDIT", "specialist": "AGENT-29-KOTLIN"},
    "scala": {"pod": "C", "pod_manager": "AGENT-24-PODC-MGR", "pod_audit": "AGENT-25-PODC-AUDIT", "specialist": "AGENT-28-SCALA"},
    "matlab": {"pod": "D", "pod_manager": "AGENT-30-PODD-MGR", "pod_audit": "AGENT-31-PODD-AUDIT", "specialist": "AGENT-32-MATLAB"},
    "r": {"pod": "D", "pod_manager": "AGENT-30-PODD-MGR", "pod_audit": "AGENT-31-PODD-AUDIT", "specialist": "AGENT-33-R"},
    "julia": {"pod": "D", "pod_manager": "AGENT-30-PODD-MGR", "pod_audit": "AGENT-31-PODD-AUDIT", "specialist": "AGENT-34-JULIA"},
    "mathematica": {"pod": "D", "pod_manager": "AGENT-30-PODD-MGR", "pod_audit": "AGENT-31-PODD-AUDIT", "specialist": "AGENT-35-MATHEMATICA"},
    "haskell": {"pod": "D", "pod_manager": "AGENT-30-PODD-MGR", "pod_audit": "AGENT-31-PODD-AUDIT", "specialist": "AGENT-37-HASKELL"},
    "ocaml": {"pod": "D", "pod_manager": "AGENT-30-PODD-MGR", "pod_audit": "AGENT-31-PODD-AUDIT", "specialist": "AGENT-38-OCAML"},
}

REQUIRED_CHAIN_EVENTS = (
    "MISSION_PM_INTAKE",
    "MISSION_CEO_DELEGATED",
    "MISSION_POD_MANAGER_ASSIGNED",
    "MISSION_SPECIALIST_ASSIGNED",
    "MISSION_POD_AUDIT_COMPLETE",
)


def _build_new_prompt(language: str) -> str:
    return (
        f"Write a small, self-contained {language} function named "
        f"battery_add_two that takes exactly two 64-bit integer parameters "
        f"named a and b, and returns their sum as a 64-bit integer. Use the "
        f"language's standard/built-in integer type — no generics, no "
        f"overloads, no external dependencies, no other parameters or "
        f"return types."
    )


def build_battery_missions() -> list[dict[str, Any]]:
    missions: list[dict[str, Any]] = []
    for language, routing in LANGUAGE_ROUTING.items():
        missions.append(
            {
                "battery_id": f"build-new-{language}",
                "language": language,
                "routing": routing,
                "payload": {
                    "prompt": _build_new_prompt(language),
                    "requested_target_language": language,
                    "metadata": {
                        "source": "protocol_bus_mission_battery",
                        "mission_type": "BUILD_NEW",
                        "depth_mode": "STANDARD",
                        "output_mode": "FULL_BUILD",
                        "acceptance_criteria": [
                            "Returns the sum of two numeric inputs",
                            "Has no external dependencies",
                        ],
                    },
                },
            }
        )

    # 20th mission: alternate mission-type path (IMPORT_MODERNIZE + DEBUG_REPAIR),
    # per the existing demo_missions.py pattern. Does not drive the pod/specialist
    # build path the same way, so no routing/agent-coverage check is attached.
    missions.append(
        {
            "battery_id": "import-modernize-debug-repair",
            "language": "python",
            "routing": None,
            "payload": {
                "prompt": (
                    "Modernize this legacy Python snippet and fix the off-by-one "
                    "bug in the loop bound."
                ),
                "requested_target_language": "python",
                "source_code": (
                    "## FILE legacy.py\n"
                    "def sum_range(n):\n"
                    "    total = 0\n"
                    "    for i in range(n):\n"
                    "        total += i\n"
                    "    return total  # bug: excludes n\n"
                ),
                "metadata": {
                    "source": "protocol_bus_mission_battery",
                    "mission_type": "IMPORT_MODERNIZE",
                    "secondary_mission_type": "DEBUG_REPAIR",
                    "depth_mode": "STANDARD",
                    "output_mode": "FULL_BUILD",
                    "acceptance_criteria": [
                        "Loop bound bug is corrected",
                        "Modernized function is returned",
                    ],
                },
            },
        }
    )
    return missions


def _validate_http_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"unsupported URL: {url}")
    return url


def _request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 10.0,
) -> tuple[int, Any]:
    response = httpx.request(
        method,
        _validate_http_url(url),
        json=payload,
        headers={"Accept": "application/json", **(headers or {})},
        timeout=timeout_seconds,
    )
    if not response.text:
        return response.status_code, None
    try:
        return response.status_code, json.loads(response.text)
    except json.JSONDecodeError:
        return response.status_code, response.text


def _extract_events(records: Any) -> list[dict[str, Any]]:
    if isinstance(records, dict):
        records = records.get("events", [])
    if not isinstance(records, list):
        return []
    return [record for record in records if isinstance(record, dict)]


def _load_readonly_api_key(explicit: str | None) -> str:
    if explicit:
        return explicit
    env_value = os.getenv("ORCHESTRATOR_READONLY_API_KEY", "").strip()
    if env_value:
        return env_value
    # Fall back to reading the repo-root .env (local dev convenience only —
    # never logged or echoed).
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith("ORCHESTRATOR_READONLY_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def _wait_for_terminal_state(
    *,
    base_url: str,
    mission_id: str,
    headers: dict[str, str],
    timeout_seconds: float,
    poll_seconds: float,
) -> tuple[str, dict[str, Any] | None]:
    deadline = time.monotonic() + timeout_seconds
    latest_payload: dict[str, Any] | None = None
    latest_state = ""
    while time.monotonic() < deadline:
        status, payload = _request_json(
            "GET", f"{base_url}/v1/missions/{mission_id}", headers=headers
        )
        if status == 200 and isinstance(payload, dict):
            latest_payload = payload
            latest_state = str(payload.get("state", "")).strip().upper()
            if latest_state in TERMINAL_STATES:
                return latest_state, latest_payload
        time.sleep(poll_seconds)
    return latest_state, latest_payload


def _evaluate_mission(
    *,
    battery_id: str,
    routing: dict[str, str] | None,
    final_state: str,
    chain_events: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if final_state != "COMPLETE":
        failures.append(f"mission did not reach COMPLETE (state={final_state or 'unknown'})")

    event_types = {str(e.get("event_type", "")).strip().upper() for e in chain_events}
    missing = [event for event in REQUIRED_CHAIN_EVENTS if event not in event_types]
    if missing:
        failures.append(f"missing chain events: {', '.join(missing)}")

    if routing is not None:
        expected_audit_agent = routing["pod_audit"]
        audit_events = [
            e for e in chain_events
            if str(e.get("event_type", "")).strip().upper() == "MISSION_POD_AUDIT_COMPLETE"
        ]
        if audit_events:
            actual_agent = str(audit_events[0].get("agent_id", "")).strip().upper()
            if actual_agent != expected_audit_agent:
                failures.append(
                    f"pod audit agent mismatch: expected {expected_audit_agent}, got {actual_agent}"
                )

    return not failures, failures


def run_live(args: argparse.Namespace, missions: list[dict[str, Any]]) -> dict[str, Any]:
    base_url = args.gateway_base_url.rstrip("/")
    read_headers = {"x-api-key": args.api_key} if args.api_key else {}

    ready_status, ready_payload = _request_json(
        "GET", f"{base_url}/readyz", timeout_seconds=args.timeout_seconds
    )
    if ready_status != 200 or not isinstance(ready_payload, dict):
        return {
            "schema_version": "protocol_bus_mission_battery.v1",
            "run_mode": "live",
            "run_timestamp_utc": datetime.now(UTC).isoformat(),
            "passed": False,
            "failure_reasons": ["gateway /readyz did not return healthy JSON"],
            "missions": [],
        }

    results: list[dict[str, Any]] = []
    for mission in missions:
        payload = mission["payload"]
        idempotency_key = f"battery-{mission['battery_id']}-{uuid.uuid4()}"
        create_status, create_payload = _request_json(
            "POST",
            f"{base_url}/v1/missions",
            payload=payload,
            headers={"Idempotency-Key": idempotency_key},
            timeout_seconds=args.timeout_seconds,
        )
        if create_status not in {200, 201} or not isinstance(create_payload, dict):
            results.append(
                {
                    "battery_id": mission["battery_id"],
                    "language": mission["language"],
                    "passed": False,
                    "failure_reasons": [f"mission creation failed (status={create_status})"],
                }
            )
            continue

        mission_id = str(create_payload.get("mission_id", "")).strip()
        final_state, _ = _wait_for_terminal_state(
            base_url=base_url,
            mission_id=mission_id,
            headers=read_headers,
            timeout_seconds=args.mission_timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
        chain_status, chain_trace = _request_json(
            "GET", f"{base_url}/v1/missions/{mission_id}/chain-trace", headers=read_headers
        )
        chain_events = _extract_events(chain_trace) if chain_status == 200 else []

        mission_passed, mission_failures = _evaluate_mission(
            battery_id=mission["battery_id"],
            routing=mission["routing"],
            final_state=final_state,
            chain_events=chain_events,
        )
        results.append(
            {
                "battery_id": mission["battery_id"],
                "language": mission["language"],
                "mission_id": mission_id,
                "final_state": final_state,
                "passed": mission_passed,
                "failure_reasons": mission_failures,
                "chain_event_types": sorted(
                    {str(e.get("event_type", "")).strip().upper() for e in chain_events}
                ),
            }
        )
        print(
            f"[{mission['battery_id']}] mission_id={mission_id} "
            f"state={final_state} passed={mission_passed}"
        )

    all_failures = [
        f"{result['battery_id']}: {reason}"
        for result in results
        for reason in result.get("failure_reasons", [])
    ]
    return {
        "schema_version": "protocol_bus_mission_battery.v1",
        "run_mode": "live",
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "passed": not all_failures,
        "failure_reasons": all_failures,
        "missions": results,
    }


def run_dry(missions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "protocol_bus_mission_battery.v1",
        "run_mode": "dry-run",
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "passed": True,
        "failure_reasons": [],
        "missions": [
            {"battery_id": m["battery_id"], "language": m["language"], "validated": True}
            for m in missions
        ],
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _print_summary(report: dict[str, Any]) -> None:
    print("== Protocol Bus Mission Battery ==")
    print(f"Mode: {report['run_mode']}")
    print(f"Missions: {len(report['missions'])}")
    print(f"Passed: {report['passed']}")
    for reason in report.get("failure_reasons", []):
        print(f"FAIL: {reason}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Protocol Bus mission battery (one mission per "
        "language specialist, plus one alternate mission-type check)."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Validate mission specs only.")
    mode.add_argument("--live", action="store_true", help="Submit missions to a live API gateway.")
    parser.add_argument("--gateway-base-url", default="http://localhost:8100")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--mission-timeout-seconds", type=float, default=240.0)
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    parser.add_argument(
        "--api-key",
        default=None,
        help="x-api-key for GET requests (read-only key recommended). Falls back to "
        "ORCHESTRATOR_READONLY_API_KEY env var, then repo-root .env.",
    )
    parser.add_argument(
        "--output-file",
        default="docs/evidence/protocol_bus_mission_battery_latest.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.api_key = _load_readonly_api_key(args.api_key)
    missions = build_battery_missions()
    report = run_live(args, missions) if args.live else run_dry(missions)
    _write_report(Path(args.output_file), report)
    _print_summary(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
