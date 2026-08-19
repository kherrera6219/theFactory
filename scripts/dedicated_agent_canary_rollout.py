from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests" / "services"))
from live_stack_auth import resolve_internal_service_api_key  # noqa: E402

HTTP_TIMEOUT_SECONDS = 10.0
# The gateway runs AUTH_MODE=api_key and rejects unauthenticated callers with
# 401. This script sent only an Idempotency-Key, so every mission creation was
# rejected before a mission existed -- invisible until the qualification
# workflow could start its stack for the first time in three weeks, at which
# point all four language canaries "failed" in under a second each without
# running anything. Same resolution the other live scripts use.
API_KEY = resolve_internal_service_api_key()
PM_AGENT_ID = "AGENT-01-PM"
CEO_AGENT_ID = "AGENT-02-CEO"
DEFAULT_REQUIRED_CHAIN_EVENTS = (
    "MISSION_PM_INTAKE",
    "MISSION_CEO_DELEGATED",
    "MISSION_POD_MANAGER_ASSIGNED",
    "MISSION_SPECIALIST_ASSIGNED",
)
TERMINAL_STATES = {"COMPLETE", "FAILED"}
_POD_A_LANGUAGES = {"python", "javascript", "typescript", "ruby", "php"}
_POD_B_LANGUAGES = {"go", "rust", "c", "cpp", "zig"}
_POD_C_LANGUAGES = {"java", "csharp", "kotlin", "scala"}
_POD_D_LANGUAGES = {"matlab", "r", "julia", "mathematica", "haskell", "ocaml"}

POD_MANAGER_BY_LANGUAGE: dict[str, str] = {
    **{language: "AGENT-12-PODA-MGR" for language in _POD_A_LANGUAGES},
    **{language: "AGENT-18-PODB-MGR" for language in _POD_B_LANGUAGES},
    **{language: "AGENT-24-PODC-MGR" for language in _POD_C_LANGUAGES},
    **{language: "AGENT-30-PODD-MGR" for language in _POD_D_LANGUAGES},
}
DEFAULT_POD_MANAGER_AGENT_ID = "AGENT-12-PODA-MGR"


def _validate_http_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"unsupported URL for qualification request: {url}")
    return url


def _request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    request_headers = {"Accept": "application/json"}
    if API_KEY:
        request_headers["x-api-key"] = API_KEY
    if headers:
        request_headers.update(headers)
    response = httpx.request(
        method,
        _validate_http_url(url),
        json=payload,
        headers=request_headers,
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    status = int(response.status_code)
    raw = response.text
    if not raw:
        return status, None
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw


def _resolve_expected_pod_manager(language: str) -> str:
    normalized = language.strip().lower()
    return POD_MANAGER_BY_LANGUAGE.get(normalized, DEFAULT_POD_MANAGER_AGENT_ID)


def _extract_event_types(records: Any) -> list[str]:
    if not isinstance(records, list):
        return []
    event_types: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        event_type = str(record.get("event_type", "")).strip().upper()
        if event_type:
            event_types.append(event_type)
    return event_types


def _extract_chain_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]
    if isinstance(payload, dict):
        events = payload.get("events")
        if isinstance(events, list):
            return [record for record in events if isinstance(record, dict)]
    return []


def _evaluate_canary_result(
    *,
    final_state: str,
    mission_record: Any,
    chain_trace: Any,
    pod_assignment: Any,
    logicnodes: Any,
    expected_pod_manager_agent_id: str,
    required_chain_events: tuple[str, ...],
) -> tuple[bool, list[str], dict[str, Any]]:
    failure_reasons: list[str] = []

    normalized_state = final_state.strip().upper()
    if normalized_state != "COMPLETE":
        failure_reasons.append(
            f"mission did not reach COMPLETE (state={normalized_state or 'unknown'})"
        )

    metadata = mission_record.get("metadata", {}) if isinstance(mission_record, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}
        failure_reasons.append("mission metadata missing or invalid")

    if metadata.get("routing_enforced") is not True:
        failure_reasons.append("routing_enforced metadata flag missing or false")
    if str(metadata.get("intake_agent_id", "")).strip().upper() != PM_AGENT_ID:
        failure_reasons.append("intake_agent_id metadata mismatch")
    if str(metadata.get("executive_agent_id", "")).strip().upper() != CEO_AGENT_ID:
        failure_reasons.append("executive_agent_id metadata mismatch")
    if (
        str(metadata.get("expected_pod_manager_agent_id", "")).strip().upper()
        != expected_pod_manager_agent_id.strip().upper()
    ):
        failure_reasons.append("expected_pod_manager_agent_id metadata mismatch")

    chain_event_types = _extract_event_types(_extract_chain_records(chain_trace))

    # Primary check: normalized-table pod assignment record.
    # Fallback: single-orchestrator deployments write through metadata_json; the
    # MISSION_POD_MANAGER_ASSIGNED chain event signals a successful assignment.
    assignment_present = bool(
        (isinstance(pod_assignment, dict) and str(pod_assignment.get("pod_name", "")).strip())
        or "MISSION_POD_MANAGER_ASSIGNED" in chain_event_types
    )
    if not assignment_present:
        failure_reasons.append("missing pod assignment artifact")

    # Primary check: normalized logicnodes table.
    # Fallback: MISSION_LOGIC_FOLDED chain event indicates logicnodes were processed.
    logicnode_count = len(logicnodes) if isinstance(logicnodes, list) else 0
    if logicnode_count < 1 and "MISSION_LOGIC_FOLDED" not in chain_event_types:
        failure_reasons.append("missing logicnode artifacts")
    missing_chain_events = [
        event_type for event_type in required_chain_events if event_type not in chain_event_types
    ]
    if missing_chain_events:
        failure_reasons.append(
            f"missing required chain events: {', '.join(missing_chain_events)}"
        )

    blocked_events = [event for event in chain_event_types if event == "MISSION_COMPLETION_BLOCKED"]
    if blocked_events:
        failure_reasons.append("completion-blocked event detected during canary")

    diagnostics = {
        "assignment_present": assignment_present,
        "logicnode_count": logicnode_count,
        "chain_event_types": chain_event_types,
        "missing_chain_events": missing_chain_events,
        "routing_enforced": metadata.get("routing_enforced"),
        "intake_agent_id": metadata.get("intake_agent_id"),
        "executive_agent_id": metadata.get("executive_agent_id"),
        "expected_pod_manager_agent_id": metadata.get("expected_pod_manager_agent_id"),
        "completion_blocked_events": len(blocked_events),
    }
    return not failure_reasons, failure_reasons, diagnostics


def _wait_for_terminal_state(
    *,
    gateway_base_url: str,
    mission_id: str,
    timeout_seconds: float,
    poll_seconds: float,
) -> tuple[str, dict[str, Any] | None]:
    deadline = time.monotonic() + timeout_seconds
    latest_payload: dict[str, Any] | None = None
    latest_state = ""
    while time.monotonic() < deadline:
        status, payload = _request_json("GET", f"{gateway_base_url}/v1/missions/{mission_id}")
        if status == 200 and isinstance(payload, dict):
            latest_payload = payload
            latest_state = str(payload.get("state", "")).strip().upper()
            if latest_state in TERMINAL_STATES:
                return latest_state, latest_payload
        time.sleep(poll_seconds)
    return latest_state, latest_payload


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _print_summary(report: dict[str, Any]) -> None:
    print("== Dedicated-Agent Canary Rollout Qualification ==")
    print(f"Timestamp (UTC): {report['run_timestamp_utc']}")
    print(f"Mission id: {report.get('mission_id', '')}")
    print(f"Final state: {report.get('final_state', '')}")
    print(f"Expected pod manager: {report.get('expected_pod_manager_agent_id', '')}")
    print(f"Assignment present: {report.get('assignment_present')}")
    print(f"Logicnode count: {report.get('logicnode_count')}")
    print(f"Rollback recommended: {report.get('rollback_recommended')}")
    if report.get("passed"):
        print("PASS: canary contract and runtime guardrails satisfied")
    else:
        for reason in report.get("failure_reasons", []):
            print(f"FAIL: {reason}")


def run(args: argparse.Namespace) -> int:
    gateway_base_url = args.gateway_base_url.rstrip("/")
    orchestrator_base_url = args.orchestrator_base_url.rstrip("/")
    expected_pod_manager = (
        args.expected_pod_manager_agent_id.strip().upper()
        if args.expected_pod_manager_agent_id
        else _resolve_expected_pod_manager(args.language)
    )

    try:
        gateway_ready_status, gateway_ready_payload = _request_json(
            "GET", f"{gateway_base_url}/readyz"
        )
        orchestrator_ready_status, orchestrator_ready_payload = _request_json(
            "GET", f"{orchestrator_base_url}/readyz"
        )
    except (httpx.HTTPError, TimeoutError, OSError, ValueError) as exc:
        print(f"FAIL: live stack not reachable ({exc})")
        return 2

    if gateway_ready_status != 200 or not isinstance(gateway_ready_payload, dict):
        print("FAIL: gateway /readyz did not return healthy status")
        return 2
    if orchestrator_ready_status != 200 or not isinstance(orchestrator_ready_payload, dict):
        print("FAIL: orchestrator /readyz did not return healthy status")
        return 2

    mission_request = {
        "prompt": args.prompt,
        "requested_target_language": args.language,
        "metadata": {
            "source": args.source,
            "selected_agent_id": PM_AGENT_ID,
            "canary_track": "dedicated-agent",
            "canary_expected_pod_manager_agent_id": expected_pod_manager,
        },
    }
    mission_key = f"dedicated-canary-{uuid.uuid4()}"
    create_status, create_payload = _request_json(
        "POST",
        f"{gateway_base_url}/v1/missions",
        payload=mission_request,
        headers={"Idempotency-Key": mission_key},
    )
    if create_status not in {200, 201} or not isinstance(create_payload, dict):
        print(f"FAIL: mission creation failed (status={create_status})")
        return 1

    mission_id = str(create_payload.get("mission_id", "")).strip()
    if not mission_id:
        print("FAIL: mission response missing mission_id")
        return 1

    final_state, mission_payload = _wait_for_terminal_state(
        gateway_base_url=gateway_base_url,
        mission_id=mission_id,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
    )

    chain_status, chain_trace = _request_json(
        "GET",
        f"{gateway_base_url}/v1/missions/{mission_id}/chain-trace",
    )
    assignment_status, pod_assignment = _request_json(
        "GET",
        f"{gateway_base_url}/v1/missions/{mission_id}/pod-assignment",
    )
    logicnodes_status, logicnodes = _request_json(
        "GET",
        f"{gateway_base_url}/v1/missions/{mission_id}/logicnodes?limit=50",
    )

    if chain_status != 200:
        chain_trace = []
    if assignment_status != 200:
        pod_assignment = None
    if logicnodes_status != 200:
        logicnodes = []

    passed, failure_reasons, diagnostics = _evaluate_canary_result(
        final_state=final_state,
        mission_record=mission_payload or create_payload,
        chain_trace=chain_trace,
        pod_assignment=pod_assignment,
        logicnodes=logicnodes,
        expected_pod_manager_agent_id=expected_pod_manager,
        required_chain_events=tuple(event.strip().upper() for event in args.required_chain_events),
    )

    report = {
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "mission_id": mission_id,
        "profile_label": args.profile_label,
        "requested_target_language": args.language,
        "expected_pod_manager_agent_id": expected_pod_manager,
        "final_state": final_state or str((mission_payload or {}).get("state", "")),
        "assignment_present": diagnostics["assignment_present"],
        "logicnode_count": diagnostics["logicnode_count"],
        "chain_event_types": diagnostics["chain_event_types"],
        "missing_chain_events": diagnostics["missing_chain_events"],
        "routing_enforced": diagnostics["routing_enforced"],
        "intake_agent_id": diagnostics["intake_agent_id"],
        "executive_agent_id": diagnostics["executive_agent_id"],
        "observed_expected_pod_manager_agent_id": diagnostics["expected_pod_manager_agent_id"],
        "completion_blocked_events": diagnostics["completion_blocked_events"],
        "passed": passed,
        "failure_reasons": failure_reasons,
        "rollback_recommended": not passed,
        "rollback_reasons": list(failure_reasons),
    }

    _print_summary(report)
    if args.output_file:
        _write_report(Path(args.output_file), report)
    return 0 if passed else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run dedicated-agent canary qualification with mission metadata contract checks, "
            "chain-of-command validation, and rollback guardrail evaluation."
        )
    )
    parser.add_argument(
        "--gateway-base-url",
        default="http://localhost:8100",
        help="API gateway base URL",
    )
    parser.add_argument(
        "--orchestrator-base-url",
        default="http://localhost:8101",
        help="Orchestrator base URL",
    )
    parser.add_argument(
        "--profile-label",
        default="dedicated-agent-canary",
        help="Execution profile label recorded in report",
    )
    parser.add_argument(
        "--prompt",
        default=(
            "Write a function called sum_integers that accepts a list of integers "
            "and returns their sum. Include a docstring and three unit tests."
        ),
        help="Mission prompt",
    )
    parser.add_argument(
        "--language",
        default="python",
        help="Requested target language",
    )
    parser.add_argument(
        "--expected-pod-manager-agent-id",
        default="",
        help="Optional explicit pod-manager agent id override",
    )
    parser.add_argument(
        "--source",
        default="dedicated_agent_canary_rollout",
        help="Mission metadata source tag",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=90.0,
        help="Max time to wait for terminal mission state",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=1.0,
        help="Polling interval while waiting for terminal state",
    )
    parser.add_argument(
        "--required-chain-events",
        nargs="+",
        default=list(DEFAULT_REQUIRED_CHAIN_EVENTS),
        help="Required chain event types",
    )
    parser.add_argument(
        "--output-file",
        default="docs/evidence/dedicated_agent_canary_rollout_latest.json",
        help="Output JSON report path",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
