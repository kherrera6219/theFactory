from __future__ import annotations

import argparse
import ast
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
REQUIRED_CHAIN_EVENTS = (
    "MISSION_PM_INTAKE",
    "MISSION_CEO_DELEGATED",
    "MISSION_POD_MANAGER_ASSIGNED",
    "MISSION_SPECIALIST_ASSIGNED",
)
PROTECTED_READ_ENDPOINTS = ("mission_detail", "mission_events")


def _validate_http_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"unsupported smoke-test URL: {url}")
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
        return int(response.status_code), None
    try:
        return int(response.status_code), json.loads(response.text)
    except json.JSONDecodeError:
        return int(response.status_code), response.text


def _load_env_file_value(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() == key:
            return value.strip().strip('"').strip("'")
    return ""


def _service_key_headers(env_file: str) -> dict[str, str]:
    value = os.environ.get("INTERNAL_SERVICE_API_KEY", "").strip()
    if not value:
        value = _load_env_file_value(Path(env_file), "INTERNAL_SERVICE_API_KEY")
    return {"x-api-key": value} if value else {}


def _extract_events(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("events"), list):
        return [item for item in payload["events"] if isinstance(item, dict)]
    return []


def _extract_event_types(payload: Any) -> list[str]:
    return [
        str(event.get("event_type", "")).strip().upper()
        for event in _extract_events(payload)
        if str(event.get("event_type", "")).strip()
    ]


def _extract_chain_trace_event_types(payload: Any) -> list[str]:
    if isinstance(payload, dict) and isinstance(payload.get("chain_trace"), list):
        return [
            str(record.get("event_type", "")).strip().upper()
            for record in payload["chain_trace"]
            if isinstance(record, dict) and str(record.get("event_type", "")).strip()
        ]
    return _extract_event_types(payload)


def _extract_metadata_chain_event_types(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return []
    raw_trace = metadata.get("chain_trace")
    if not isinstance(raw_trace, list):
        return []
    return [
        str(record.get("event_type", "")).strip().upper()
        for record in raw_trace
        if isinstance(record, dict) and str(record.get("event_type", "")).strip()
    ]


def _response_snippet(payload: Any, *, max_chars: int = 300) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, sort_keys=True)
    return text[:max_chars]


def _is_valid_python(source: str) -> tuple[bool, str | None]:
    try:
        ast.parse(source)
    except SyntaxError as exc:
        return False, f"{exc.msg} at line {exc.lineno}"
    return True, None


def _artifact_text(record: Any) -> str:
    if not isinstance(record, dict):
        return ""
    for key in ("artifact_text", "content", "source", "text"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _find_python_artifact(records: Any) -> dict[str, Any] | None:
    if not isinstance(records, list):
        return None
    for record in records:
        if not isinstance(record, dict):
            continue
        artifact_type = str(record.get("artifact_type", "")).lower()
        artifact_id = str(record.get("artifact_id", "")).lower()
        manifest = record.get("manifest") if isinstance(record.get("manifest"), dict) else {}
        language = str(manifest.get("language", "")).lower()
        if (
            "python" in artifact_type
            or artifact_id.endswith(".py")
            or artifact_id == "generated_code"
            or language == "python"
        ):
            return record
    return records[0] if records else None


def _routing_mismatches(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["mission detail payload missing"]
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return ["mission metadata missing"]
    checks = (
        ("assigned_pod_manager_agent_id", "expected_pod_manager_agent_id"),
        ("assigned_specialist_agent_id", "expected_specialist_agent_id"),
    )
    mismatches: list[str] = []
    for assigned_key, expected_key in checks:
        assigned = str(metadata.get(assigned_key, "")).strip().upper()
        expected = str(metadata.get(expected_key, "")).strip().upper()
        if expected and assigned and assigned != expected:
            mismatches.append(f"{assigned_key}={assigned} expected {expected}")
        elif expected and not assigned:
            mismatches.append(f"{assigned_key} missing expected {expected}")
    return mismatches


def _wait_for_terminal_state(
    *,
    gateway_base_url: str,
    mission_id: str,
    headers: dict[str, str],
    timeout_seconds: float,
    poll_seconds: float,
) -> tuple[str, dict[str, Any] | None, list[str], list[dict[str, Any]]]:
    deadline = time.monotonic() + timeout_seconds
    latest_payload: dict[str, Any] | None = None
    observed_states: list[str] = []
    poll_statuses: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        status, payload = _request_json(
            "GET",
            f"{gateway_base_url}/v1/missions/{mission_id}",
            headers=headers,
        )
        if not poll_statuses or poll_statuses[-1].get("status") != status:
            poll_statuses.append(
                {"status": status, "payload_snippet": _response_snippet(payload)}
            )
        if status == 200 and isinstance(payload, dict):
            latest_payload = payload
            state = str(payload.get("state", "")).strip().upper()
            if state and (not observed_states or observed_states[-1] != state):
                observed_states.append(state)
            if state in TERMINAL_STATES:
                return state, latest_payload, observed_states, poll_statuses
        time.sleep(poll_seconds)
    state = str((latest_payload or {}).get("state", "")).strip().upper()
    return state, latest_payload, observed_states, poll_statuses


def _check_readiness(gateway_base_url: str, orchestrator_base_url: str) -> tuple[dict[str, Any], list[str]]:
    probes: dict[str, Any] = {}
    failures: list[str] = []
    endpoints = {
        "gateway_health": f"{gateway_base_url}/health",
        "gateway_ready": f"{gateway_base_url}/readyz",
        "orchestrator_health": f"{orchestrator_base_url}/health",
        "orchestrator_ready": f"{orchestrator_base_url}/readyz",
    }
    for name, url in endpoints.items():
        try:
            status, payload = _request_json("GET", url)
        except (httpx.HTTPError, OSError, TimeoutError, ValueError) as exc:
            probes[name] = {"ok": False, "error": str(exc)}
            failures.append(f"{name} unreachable: {exc}")
            continue
        probes[name] = {"status": status, "payload": payload}
        if status != 200:
            failures.append(f"{name} returned {status}")
    return probes, failures


def _build_mission_payload(prompt: str) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "requested_target_language": "python",
        "metadata": {
            "source": "phase13_smoke",
            "mission_type": "BUILD_NEW",
            "depth_mode": "STANDARD",
            "output_mode": "FULL_BUILD",
            # Phase 13 smoke submits a finalized build spec. Without this marker
            # PM intake can correctly pause for optional clarification, which
            # validates a different branch than this smoke is intended to cover.
            "user_intent": "finalize_plan",
        },
    }


def run(args: argparse.Namespace) -> int:
    gateway_base_url = args.gateway_base_url.rstrip("/")
    orchestrator_base_url = args.orchestrator_base_url.rstrip("/")
    read_headers = _service_key_headers(args.env_file)
    report: dict[str, Any] = {
        "schema_version": "phase13_smoke.v1",
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "gateway_base_url": gateway_base_url,
        "orchestrator_base_url": orchestrator_base_url,
        "passed": False,
        "failure_reasons": [],
        "protected_read_auth_configured": bool(read_headers),
    }

    readiness, failures = _check_readiness(gateway_base_url, orchestrator_base_url)
    report["readiness"] = readiness
    if failures:
        report["failure_reasons"] = failures
        _write_report(Path(args.output_file), report)
        _print_summary(report)
        return 2

    mission_payload = _build_mission_payload(args.prompt)
    create_status, create_payload = _request_json(
        "POST",
        f"{gateway_base_url}/v1/missions",
        payload=mission_payload,
        headers={"Idempotency-Key": f"phase13-smoke-{uuid.uuid4()}"},
    )
    report["mission_create_status"] = create_status
    report["mission_create_payload"] = create_payload
    if create_status not in {200, 201} or not isinstance(create_payload, dict):
        report["failure_reasons"] = [f"mission creation failed with status {create_status}"]
        _write_report(Path(args.output_file), report)
        _print_summary(report)
        return 1

    mission_id = str(create_payload.get("mission_id", "")).strip()
    report["mission_id"] = mission_id
    if not mission_id:
        report["failure_reasons"] = ["mission create response missing mission_id"]
        _write_report(Path(args.output_file), report)
        _print_summary(report)
        return 1

    final_state, final_payload, observed_states, poll_statuses = _wait_for_terminal_state(
        gateway_base_url=gateway_base_url,
        mission_id=mission_id,
        headers=read_headers,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
    )
    report["final_state"] = final_state
    report["observed_states"] = observed_states
    report["mission_poll_statuses"] = poll_statuses
    report["final_mission_payload"] = final_payload
    report["metadata_chain_event_types"] = _extract_metadata_chain_event_types(final_payload)

    events_status, events_payload = _request_json(
        "GET",
        f"{gateway_base_url}/v1/missions/{mission_id}/events?limit=200",
        headers=read_headers,
    )
    chain_status, chain_payload = _request_json(
        "GET", f"{gateway_base_url}/v1/missions/{mission_id}/chain-trace"
    )
    artifacts_status, artifacts_payload = _request_json(
        "GET", f"{gateway_base_url}/v1/missions/{mission_id}/build-artifacts?limit=20"
    )
    report["events_status"] = events_status
    report["chain_trace_status"] = chain_status
    report["artifacts_status"] = artifacts_status
    if events_status >= 400:
        report["events_error"] = _response_snippet(events_payload)
    if chain_status >= 400:
        report["chain_trace_error"] = _response_snippet(chain_payload)
    report["mission_event_types"] = _extract_event_types(events_payload)
    report["chain_event_types"] = _extract_chain_trace_event_types(chain_payload)
    if not report["chain_event_types"]:
        report["chain_event_types"] = report["metadata_chain_event_types"]
        report["chain_event_source"] = "mission_metadata_fallback"
    else:
        report["chain_event_source"] = "chain_trace_endpoint"

    artifacts = artifacts_payload if isinstance(artifacts_payload, list) else []
    report["build_artifact_count"] = len(artifacts)
    artifact = _find_python_artifact(artifacts)
    artifact_detail: Any = artifact
    if isinstance(artifact, dict) and artifact.get("artifact_id"):
        detail_status, detail_payload = _request_json(
            "GET",
            f"{gateway_base_url}/v1/missions/{mission_id}/build-artifacts/{artifact['artifact_id']}",
        )
        report["artifact_detail_status"] = detail_status
        if detail_status == 200:
            artifact_detail = detail_payload
    source = _artifact_text(artifact_detail)
    python_valid, python_error = _is_valid_python(source) if source else (False, "no artifact text")
    report["python_artifact_valid"] = python_valid
    report["python_artifact_error"] = python_error

    missing_events = [
        event_type for event_type in REQUIRED_CHAIN_EVENTS if event_type not in report["chain_event_types"]
    ]
    failure_reasons: list[str] = []
    if final_state != "COMPLETE":
        failure_reasons.append(f"mission did not reach COMPLETE (state={final_state or 'unknown'})")
    if not read_headers:
        failure_reasons.append(
            "protected mission reads were unauthenticated; set INTERNAL_SERVICE_API_KEY or --env-file"
        )
    for endpoint_name in PROTECTED_READ_ENDPOINTS:
        if endpoint_name == "mission_events" and events_status in {401, 403}:
            failure_reasons.append(f"{endpoint_name} returned {events_status}")
    if chain_status >= 400 and report.get("chain_event_source") != "mission_metadata_fallback":
        failure_reasons.append(f"chain_trace endpoint returned {chain_status}")
    if missing_events:
        failure_reasons.append(f"missing required chain events: {', '.join(missing_events)}")
    if not artifacts:
        failure_reasons.append("missing build artifacts")
    if not python_valid:
        failure_reasons.append(f"python artifact syntax check failed: {python_error}")
    routing_mismatches = _routing_mismatches(final_payload)
    if routing_mismatches:
        failure_reasons.extend(
            f"routing invariant mismatch: {mismatch}" for mismatch in routing_mismatches
        )

    report["missing_chain_events"] = missing_events
    report["routing_mismatches"] = routing_mismatches
    report["failure_reasons"] = failure_reasons
    report["passed"] = not failure_reasons
    _write_report(Path(args.output_file), report)
    _print_summary(report)
    return 0 if report["passed"] else 1


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _print_summary(report: dict[str, Any]) -> None:
    print("== Phase 13 Smoke ==")
    print(f"Mission id: {report.get('mission_id', '')}")
    print(f"Final state: {report.get('final_state', '')}")
    print(f"Observed states: {report.get('observed_states', [])}")
    print(f"Build artifact count: {report.get('build_artifact_count', 0)}")
    print(f"Python artifact valid: {report.get('python_artifact_valid')}")
    if report.get("passed"):
        print("PASS: Phase 13 smoke requirements satisfied")
    else:
        for reason in report.get("failure_reasons", []):
            print(f"FAIL: {reason}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Phase 13 live end-to-end smoke test.")
    parser.add_argument("--gateway-base-url", default="http://localhost:8100")
    parser.add_argument("--orchestrator-base-url", default="http://localhost:8101")
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--prompt",
        default=(
            "Write a Python function named reverse_string(value: str) -> str that "
            "returns the reversed input string. Include a docstring and three pytest tests."
        ),
    )
    parser.add_argument(
        "--output-file",
        default="docs/evidence/phase13_smoke_latest.json",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
