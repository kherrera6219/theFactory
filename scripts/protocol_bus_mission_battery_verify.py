"""Verify the 20 chat-driven Protocol Bus mission battery missions.

Companion to docs/PROTOCOL_BUS_MISSION_BATTERY_PLAN.md. Unlike
protocol_bus_mission_battery.py (which submits missions directly via the API,
bypassing the PM Agent chat/clarification flow), this battery's missions were
created through the real Mission Control chat UI so the PM Agent's clarifying-
question dialogue is genuinely exercised. This script only polls the already-
created missions to a terminal state and checks chain-trace agent coverage.

Usage:
    python scripts/protocol_bus_mission_battery_verify.py \
        --gateway-base-url http://127.0.0.1:8100 \
        --output-file docs/evidence/protocol_bus_mission_battery_latest.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

TERMINAL_STATES = {"COMPLETE", "FAILED"}

REQUIRED_CHAIN_EVENTS = (
    "MISSION_PM_INTAKE",
    "MISSION_CEO_DELEGATED",
    "MISSION_POD_MANAGER_ASSIGNED",
    "MISSION_SPECIALIST_ASSIGNED",
    "MISSION_POD_AUDIT_COMPLETE",
)

# Mirrors orchestrator/mission_flow.py POD_MANAGER_BY_LANGUAGE / SPECIALIST_BY_LANGUAGE.
LANGUAGE_ROUTING: dict[str, dict[str, str]] = {
    "python": {"pod_manager": "AGENT-12-PODA-MGR", "pod_audit": "AGENT-13-PODA-AUDIT", "specialist": "AGENT-14-PYTHON"},
    "javascript": {"pod_manager": "AGENT-12-PODA-MGR", "pod_audit": "AGENT-13-PODA-AUDIT", "specialist": "AGENT-15-JAVASCRIPT"},
    "ruby": {"pod_manager": "AGENT-12-PODA-MGR", "pod_audit": "AGENT-13-PODA-AUDIT", "specialist": "AGENT-16-RUBY"},
    "php": {"pod_manager": "AGENT-12-PODA-MGR", "pod_audit": "AGENT-13-PODA-AUDIT", "specialist": "AGENT-17-PHP"},
    "go": {"pod_manager": "AGENT-18-PODB-MGR", "pod_audit": "AGENT-19-PODB-AUDIT", "specialist": "AGENT-36-GO"},
    "rust": {"pod_manager": "AGENT-18-PODB-MGR", "pod_audit": "AGENT-19-PODB-AUDIT", "specialist": "AGENT-22-RUST"},
    "c": {"pod_manager": "AGENT-18-PODB-MGR", "pod_audit": "AGENT-19-PODB-AUDIT", "specialist": "AGENT-20-C"},
    "cpp": {"pod_manager": "AGENT-18-PODB-MGR", "pod_audit": "AGENT-19-PODB-AUDIT", "specialist": "AGENT-21-CPP"},
    "zig": {"pod_manager": "AGENT-18-PODB-MGR", "pod_audit": "AGENT-19-PODB-AUDIT", "specialist": "AGENT-23-ZIG"},
    "java": {"pod_manager": "AGENT-24-PODC-MGR", "pod_audit": "AGENT-25-PODC-AUDIT", "specialist": "AGENT-26-JAVA"},
    "csharp": {"pod_manager": "AGENT-24-PODC-MGR", "pod_audit": "AGENT-25-PODC-AUDIT", "specialist": "AGENT-27-CSHARP"},
    "kotlin": {"pod_manager": "AGENT-24-PODC-MGR", "pod_audit": "AGENT-25-PODC-AUDIT", "specialist": "AGENT-29-KOTLIN"},
    "scala": {"pod_manager": "AGENT-24-PODC-MGR", "pod_audit": "AGENT-25-PODC-AUDIT", "specialist": "AGENT-28-SCALA"},
    "matlab": {"pod_manager": "AGENT-30-PODD-MGR", "pod_audit": "AGENT-31-PODD-AUDIT", "specialist": "AGENT-32-MATLAB"},
    "r": {"pod_manager": "AGENT-30-PODD-MGR", "pod_audit": "AGENT-31-PODD-AUDIT", "specialist": "AGENT-33-R"},
    "julia": {"pod_manager": "AGENT-30-PODD-MGR", "pod_audit": "AGENT-31-PODD-AUDIT", "specialist": "AGENT-34-JULIA"},
    "mathematica": {"pod_manager": "AGENT-30-PODD-MGR", "pod_audit": "AGENT-31-PODD-AUDIT", "specialist": "AGENT-35-MATHEMATICA"},
    "haskell": {"pod_manager": "AGENT-30-PODD-MGR", "pod_audit": "AGENT-31-PODD-AUDIT", "specialist": "AGENT-37-HASKELL"},
    "ocaml": {"pod_manager": "AGENT-30-PODD-MGR", "pod_audit": "AGENT-31-PODD-AUDIT", "specialist": "AGENT-38-OCAML"},
}

# The 20 missions created through the live Mission Control chat UI in this session.
BATTERY_MISSIONS: list[dict[str, Any]] = [
    {"battery_id": "chat-go", "language": "go", "mission_id": "mission-3c760af1-abc0-45f4-a70c-50cf80181d63", "clarify_style": "vague-answered"},
    {"battery_id": "chat-rust", "language": "rust", "mission_id": "mission-e3126366-1967-40cc-b527-9b12572bbdf2", "clarify_style": "detailed-sow"},
    {"battery_id": "chat-c", "language": "c", "mission_id": "mission-508b752b-cf37-4da5-9565-7e170c1cbee2", "clarify_style": "vague-assumptions"},
    {"battery_id": "chat-cpp", "language": "cpp", "mission_id": "mission-560c06fb-225c-4ba7-9aa8-7bf7d03a2509", "clarify_style": "detailed-sow"},
    {"battery_id": "chat-zig", "language": "zig", "mission_id": "mission-9b6d1eb5-4e99-4095-9e0e-ef48a1a8153e", "clarify_style": "vague-answered"},
    {"battery_id": "chat-java", "language": "java", "mission_id": "mission-72292418-0d23-4855-951f-3f5dec5a225f", "clarify_style": "detailed-sow-then-assumptions"},
    {"battery_id": "chat-csharp", "language": "csharp", "mission_id": "mission-e3a685c4-e85a-46ae-a48f-d3c88ad79594", "clarify_style": "vague-answered"},
    {"battery_id": "chat-kotlin", "language": "kotlin", "mission_id": "mission-684131bb-6fc1-43e7-89c7-21ea36efec9e", "clarify_style": "detailed-sow"},
    {"battery_id": "chat-scala", "language": "scala", "mission_id": "mission-d08c44a0-729d-4e6c-a1db-eb1f4980d396", "clarify_style": "vague-assumptions"},
    {"battery_id": "chat-matlab", "language": "matlab", "mission_id": "mission-914361c1-64db-4159-8bf6-47ce4f567840", "clarify_style": "detailed-sow"},
    {"battery_id": "chat-r", "language": "r", "mission_id": "mission-91ac234b-80f7-4c92-aa3f-1b9441169675", "clarify_style": "vague-answered"},
    {"battery_id": "chat-julia", "language": "julia", "mission_id": "mission-26e54a90-1719-4861-a5fd-d583429207f7", "clarify_style": "detailed-sow"},
    {"battery_id": "chat-mathematica", "language": "mathematica", "mission_id": "mission-52e2c1b9-18a1-4d1b-93a0-f110834205e7", "clarify_style": "vague-assumptions"},
    {"battery_id": "chat-haskell", "language": "haskell", "mission_id": "mission-a30388d7-71d7-46d4-87d5-e3d8fcaf856a", "clarify_style": "detailed-sow"},
    {"battery_id": "chat-ocaml", "language": "ocaml", "mission_id": "mission-3ecb98f8-4cbd-4215-a34d-ad2811f61fef", "clarify_style": "vague-answered"},
    {"battery_id": "chat-python", "language": "python", "mission_id": "mission-b5f9f2b7-8db2-4581-a630-c3857578c5ac", "clarify_style": "vague-assumptions"},
    {"battery_id": "chat-javascript", "language": "javascript", "mission_id": "mission-4941126c-778c-47d4-afd2-ce9d31b66a8a", "clarify_style": "detailed-sow"},
    {"battery_id": "chat-ruby", "language": "ruby", "mission_id": "mission-0c1c9892-7a59-4df1-b28d-7e9ffac333df", "clarify_style": "vague-no-clarify-needed"},
    {"battery_id": "chat-php", "language": "php", "mission_id": "mission-8e9f2073-81ed-47bc-aa0c-1c88b8272f4e", "clarify_style": "detailed-sow"},
    {"battery_id": "chat-modernize-python", "language": "python", "mission_id": "mission-2bac5166-b408-4cc9-a344-863cb657d50a", "clarify_style": "vague-assumptions", "routing_exempt": True, "mission_type": "IMPORT_MODERNIZE+DEBUG_REPAIR"},
]


def _validate_http_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"unsupported URL: {url}")
    return url


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 10.0,
) -> tuple[int, Any]:
    response = httpx.request(
        method,
        _validate_http_url(url),
        headers={"Accept": "application/json", **(headers or {})},
        timeout=timeout_seconds,
    )
    if not response.text:
        return response.status_code, None
    try:
        return response.status_code, json.loads(response.text)
    except json.JSONDecodeError:
        return response.status_code, response.text


def _load_readonly_api_key(explicit: str | None) -> str:
    if explicit:
        return explicit
    env_value = os.getenv("ORCHESTRATOR_READONLY_API_KEY", "").strip()
    if env_value:
        return env_value
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith("ORCHESTRATOR_READONLY_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def _extract_events(records: Any) -> list[dict[str, Any]]:
    if isinstance(records, dict):
        records = records.get("events", [])
    if not isinstance(records, list):
        return []
    return [r for r in records if isinstance(r, dict)]


def _wait_for_terminal_state(
    *, base_url: str, mission_id: str, headers: dict[str, str],
    timeout_seconds: float, poll_seconds: float,
) -> str:
    deadline = time.monotonic() + timeout_seconds
    latest_state = ""
    while time.monotonic() < deadline:
        status, payload = _request_json("GET", f"{base_url}/v1/missions/{mission_id}", headers=headers)
        if status == 200 and isinstance(payload, dict):
            latest_state = str(payload.get("state", "")).strip().upper()
            if latest_state in TERMINAL_STATES:
                return latest_state
        time.sleep(poll_seconds)
    return latest_state


def run(args: argparse.Namespace) -> dict[str, Any]:
    base_url = args.gateway_base_url.rstrip("/")
    headers = {"x-api-key": args.api_key} if args.api_key else {}

    results: list[dict[str, Any]] = []
    for mission in BATTERY_MISSIONS:
        mission_id = mission["mission_id"]
        final_state = _wait_for_terminal_state(
            base_url=base_url, mission_id=mission_id, headers=headers,
            timeout_seconds=args.mission_timeout_seconds, poll_seconds=args.poll_seconds,
        )
        chain_status, chain_trace = _request_json(
            "GET", f"{base_url}/v1/missions/{mission_id}/chain-trace", headers=headers
        )
        chain_events = _extract_events(chain_trace) if chain_status == 200 else []
        event_types = {str(e.get("event_type", "")).strip().upper() for e in chain_events}
        missing_events = [e for e in REQUIRED_CHAIN_EVENTS if e not in event_types]

        agent_check: dict[str, Any] = {}
        if not mission.get("routing_exempt"):
            routing = LANGUAGE_ROUTING.get(mission["language"])
            if routing:
                audit_events = [
                    e for e in chain_events
                    if str(e.get("event_type", "")).strip().upper() == "MISSION_POD_AUDIT_COMPLETE"
                ]
                actual_audit_agent = (
                    str(audit_events[0].get("agent_id", "")).strip().upper() if audit_events else None
                )
                agent_check = {
                    "expected_pod_audit_agent": routing["pod_audit"],
                    "actual_pod_audit_agent": actual_audit_agent,
                    "match": actual_audit_agent == routing["pod_audit"],
                }

        passed = final_state == "COMPLETE" and not missing_events and agent_check.get("match", True)
        results.append({
            **mission,
            "final_state": final_state,
            "missing_chain_events": missing_events,
            "agent_check": agent_check,
            "passed": passed,
        })
        print(f"[{mission['battery_id']}] language={mission['language']} state={final_state} passed={passed}")

    passed_count = sum(1 for r in results if r["passed"])
    return {
        "schema_version": "protocol_bus_mission_battery_verify.v1",
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "total_missions": len(results),
        "passed_missions": passed_count,
        "passed": passed_count == len(results),
        "missions": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Poll and verify the chat-driven mission battery.")
    parser.add_argument("--gateway-base-url", default="http://localhost:8100")
    parser.add_argument("--mission-timeout-seconds", type=float, default=300.0)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--output-file", default="docs/evidence/protocol_bus_mission_battery_latest.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.api_key = _load_readonly_api_key(args.api_key)
    report = run(args)
    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Passed: {report['passed_missions']}/{report['total_missions']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
