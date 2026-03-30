from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

HTTP_TIMEOUT_SECONDS = 10.0
DEFAULT_REQUIRED_CHAIN_EVENTS = (
    "MISSION_PM_INTAKE",
    "MISSION_CEO_DELEGATED",
    "MISSION_POD_MANAGER_ASSIGNED",
    "MISSION_SPECIALIST_ASSIGNED",
)
TERMINAL_STATES = {"COMPLETE", "FAILED"}


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


def _evaluate_result(
    *,
    final_state: str,
    pod_assignment: Any,
    logicnodes: Any,
    chain_trace: Any,
    required_chain_events: tuple[str, ...],
) -> tuple[bool, list[str], dict[str, Any]]:
    failure_reasons: list[str] = []

    normalized_state = final_state.strip().upper()
    if normalized_state != "COMPLETE":
        failure_reasons.append(
            f"mission did not reach COMPLETE (state={normalized_state or 'unknown'})"
        )

    assignment_present = bool(
        isinstance(pod_assignment, dict) and str(pod_assignment.get("pod_name", "")).strip()
    )
    if not assignment_present:
        failure_reasons.append("missing pod assignment artifact")

    logicnode_count = len(logicnodes) if isinstance(logicnodes, list) else 0
    if logicnode_count < 1:
        failure_reasons.append("missing logicnode artifacts")

    chain_event_types = _extract_event_types(_extract_chain_records(chain_trace))
    missing_chain_events = [
        event_type for event_type in required_chain_events if event_type not in chain_event_types
    ]
    if missing_chain_events:
        failure_reasons.append(
            f"missing required chain events: {', '.join(missing_chain_events)}"
        )

    diagnostics = {
        "assignment_present": assignment_present,
        "logicnode_count": logicnode_count,
        "chain_event_types": chain_event_types,
        "missing_chain_events": missing_chain_events,
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
        status, payload = _request_json(
            "GET",
            f"{gateway_base_url}/v1/missions/{mission_id}",
        )
        if status == 200 and isinstance(payload, dict):
            latest_payload = payload
            latest_state = str(payload.get("state", "")).strip().upper()
            if latest_state in TERMINAL_STATES:
                return latest_state, latest_payload
        time.sleep(poll_seconds)
    return latest_state, latest_payload


def _print_summary(report: dict[str, Any]) -> None:
    print("== Mission Artifact Qualification ==")
    print(f"Timestamp (UTC): {report['run_timestamp_utc']}")
    print(f"Profile label: {report['profile_label']}")
    print(f"Mission id: {report.get('mission_id', '')}")
    print(f"Final state: {report.get('final_state', '')}")
    print(f"Pod assignment present: {report.get('assignment_present')}")
    print(f"Logicnode count: {report.get('logicnode_count')}")
    print(f"Missing chain events: {report.get('missing_chain_events', [])}")
    if report.get("passed"):
        print("PASS: mission artifacts and chain-of-command requirements satisfied")
    else:
        for reason in report.get("failure_reasons", []):
            print(f"FAIL: {reason}")


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _append_history(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(report) + "\n")


def run(args: argparse.Namespace) -> int:
    gateway_base_url = args.gateway_base_url.rstrip("/")
    orchestrator_base_url = args.orchestrator_base_url.rstrip("/")

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
        "metadata": {"source": args.source},
    }
    mission_key = f"{args.profile_label}-{uuid.uuid4()}"
    create_status, create_payload = _request_json(
        "POST",
        f"{gateway_base_url}/v1/missions",
        payload=mission_request,
        headers={"Idempotency-Key": mission_key},
    )
    if create_status != 200 or not isinstance(create_payload, dict):
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

    events_status, mission_events = _request_json(
        "GET",
        f"{gateway_base_url}/v1/missions/{mission_id}/events?limit=200",
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
    if events_status != 200:
        mission_events = []

    passed, failure_reasons, diagnostics = _evaluate_result(
        final_state=final_state,
        pod_assignment=pod_assignment,
        logicnodes=logicnodes,
        chain_trace=chain_trace,
        required_chain_events=tuple(event.strip().upper() for event in args.required_chain_events),
    )

    report = {
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "profile_label": args.profile_label,
        "mission_id": mission_id,
        "final_state": final_state or str((mission_payload or {}).get("state", "")),
        "mission_events": _extract_event_types(mission_events),
        "assignment_present": diagnostics["assignment_present"],
        "logicnode_count": diagnostics["logicnode_count"],
        "chain_event_types": diagnostics["chain_event_types"],
        "missing_chain_events": diagnostics["missing_chain_events"],
        "pass": passed,
        "passed": passed,
        "failure_reasons": failure_reasons,
    }

    _print_summary(report)
    if args.output_file:
        _write_report(Path(args.output_file), report)
    if args.history_file:
        _append_history(Path(args.history_file), report)
    return 0 if passed else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run live mission qualification asserting completion artifacts "
            "(pod assignment + logicnodes) and PM/CEO chain-of-command evidence."
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
        default="shared-workers",
        help="Execution profile label recorded in report",
    )
    parser.add_argument(
        "--prompt",
        default="Artifact qualification mission",
        help="Mission prompt",
    )
    parser.add_argument(
        "--language",
        default="python",
        help="Requested target language",
    )
    parser.add_argument(
        "--source",
        default="mission_artifact_qualification",
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
        "--history-file",
        default="",
        help="Optional JSONL history file for longitudinal qualification tracking",
    )
    parser.add_argument(
        "--output-file",
        default="docs/evidence/mission_artifact_qualification_latest.json",
        help="Output JSON report path",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
