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

DEFAULT_REQUIRED_CHAIN_EVENTS = (
    "MISSION_PM_INTAKE",
    "MISSION_CEO_DELEGATED",
    "MISSION_POD_MANAGER_ASSIGNED",
    "MISSION_SPECIALIST_ASSIGNED",
)
TERMINAL_STATES = {"COMPLETE", "FAILED"}


def build_demo_missions() -> list[dict[str, Any]]:
    return [
        {
            "demo_id": "build-new-python-cli",
            "expected_behavior": "BUILD_NEW generated-output path",
            "payload": {
                "prompt": (
                    "Build a Python CLI function named summarize_expenses that "
                    "accepts CSV text and returns totals by category."
                ),
                "requested_target_language": "python",
                "metadata": {
                    "source": "phase18_demo",
                    "mission_type": "BUILD_NEW",
                    "depth_mode": "STANDARD",
                    "output_mode": "FULL_BUILD",
                    "acceptance_criteria": [
                        "Parses CSV text without file system access",
                        "Returns category totals as a dictionary",
                        "Includes deterministic unit-test examples",
                    ],
                },
            },
            "required_evidence": [
                "mission reaches COMPLETE",
                "chain trace includes PM/CEO/pod/specialist events",
                (
                    "generated_code artifact is available when live LLM or fused "
                    "fallback output succeeds"
                ),
            ],
        },
        {
            "demo_id": "analyze-only-service-map",
            "expected_behavior": "ANALYZE_ONLY source intelligence path",
            "payload": {
                "prompt": "Analyze this small service and identify its public API and risks.",
                "requested_target_language": "python",
                "source_code": (
                    "## FILE app.py\n"
                    "from fastapi import FastAPI\n\n"
                    "app = FastAPI()\n\n"
                    "@app.get('/health')\n"
                    "def health():\n"
                    "    return {'ok': True}\n"
                ),
                "metadata": {
                    "source": "phase18_demo",
                    "mission_type": "ANALYZE_ONLY",
                    "depth_mode": "STANDARD",
                    "output_mode": "ANALYZE_ONLY",
                    "acceptance_criteria": [
                        "Produces source inventory or AIM evidence",
                        "Does not require generated output",
                        "Surfaces risk or modernization observations",
                    ],
                },
            },
            "required_evidence": [
                "mission reaches COMPLETE",
                "source_code is packaged or analyzed",
                "AIM/equivalence/security evidence is present when enabled",
            ],
        },
        {
            "demo_id": "import-modernize-debug-repair",
            "expected_behavior": "IMPORT_MODERNIZE and DEBUG_REPAIR source-bundle path",
            "payload": {
                "prompt": (
                    "Modernize and repair the supplied Python function so divide handles "
                    "zero safely and returns an explicit error object."
                ),
                "requested_target_language": "python",
                "source_code": (
                    "## FILE calculator.py\n"
                    "def divide(a, b):\n"
                    "    return a / b\n"
                    "\n"
                    "## FILE test_calculator.py\n"
                    "def test_divide_zero():\n"
                    "    assert divide(1, 0)['error'] == 'division_by_zero'\n"
                ),
                "metadata": {
                    "source": "phase18_demo",
                    "mission_type": "IMPORT_MODERNIZE",
                    "secondary_mission_type": "DEBUG_REPAIR",
                    "depth_mode": "STANDARD",
                    "output_mode": "PATCH_PROPOSAL",
                    "acceptance_criteria": [
                        "Identifies the divide-by-zero defect",
                        "Proposes a minimal modernization/repair patch",
                        "Preserves source-bundle audit evidence",
                    ],
                },
            },
            "required_evidence": [
                "mission reaches COMPLETE",
                "source bundle produces build/package evidence",
                "repair intent is reflected in PM/CEO contract metadata",
            ],
        },
    ]


def _validate_http_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"unsupported URL for demo request: {url}")
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


def _extract_event_types(records: Any) -> list[str]:
    if isinstance(records, dict):
        records = records.get("events", [])
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


def validate_demo_specs(demos: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    demo_ids: set[str] = set()
    expected_types = {"BUILD_NEW", "ANALYZE_ONLY", "IMPORT_MODERNIZE"}
    seen_types: set[str] = set()

    for demo in demos:
        demo_id = str(demo.get("demo_id", "")).strip()
        if not demo_id:
            failures.append("demo missing demo_id")
        if demo_id in demo_ids:
            failures.append(f"duplicate demo_id: {demo_id}")
        demo_ids.add(demo_id)

        payload = demo.get("payload")
        if not isinstance(payload, dict):
            failures.append(f"{demo_id}: payload missing")
            continue
        if len(str(payload.get("prompt", "")).strip()) < 3:
            failures.append(f"{demo_id}: prompt too short")
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            failures.append(f"{demo_id}: metadata missing")
            continue
        mission_type = str(metadata.get("mission_type", "")).strip().upper()
        output_mode = str(metadata.get("output_mode", "")).strip().upper()
        if not mission_type:
            failures.append(f"{demo_id}: mission_type missing")
        if not output_mode:
            failures.append(f"{demo_id}: output_mode missing")
        seen_types.add(mission_type)
        if mission_type in {"ANALYZE_ONLY", "IMPORT_MODERNIZE", "DEBUG_REPAIR"} and not str(
            payload.get("source_code", "")
        ).strip():
            failures.append(f"{demo_id}: source_code required for source-bearing demo")
        if mission_type == "ANALYZE_ONLY" and output_mode != "ANALYZE_ONLY":
            failures.append(f"{demo_id}: ANALYZE_ONLY demo must use ANALYZE_ONLY output_mode")

    missing_types = sorted(expected_types - seen_types)
    if missing_types:
        failures.append(f"missing required demo mission type(s): {', '.join(missing_types)}")
    if not any(
        str(demo.get("payload", {}).get("metadata", {}).get("secondary_mission_type", ""))
        .strip()
        .upper()
        == "DEBUG_REPAIR"
        for demo in demos
    ):
        failures.append("missing DEBUG_REPAIR coverage in modernization demo")

    return not failures, failures


def _wait_for_terminal_state(
    *,
    base_url: str,
    mission_id: str,
    timeout_seconds: float,
    poll_seconds: float,
) -> tuple[str, dict[str, Any] | None]:
    deadline = time.monotonic() + timeout_seconds
    latest_payload: dict[str, Any] | None = None
    latest_state = ""
    while time.monotonic() < deadline:
        status, payload = _request_json("GET", f"{base_url}/v1/missions/{mission_id}")
        if status == 200 and isinstance(payload, dict):
            latest_payload = payload
            latest_state = str(payload.get("state", "")).strip().upper()
            if latest_state in TERMINAL_STATES:
                return latest_state, latest_payload
        time.sleep(poll_seconds)
    return latest_state, latest_payload


def _evaluate_live_demo(
    *,
    final_state: str,
    chain_trace: Any,
    logicnodes: Any,
    build_artifacts: Any,
    required_chain_events: tuple[str, ...],
) -> tuple[bool, list[str], dict[str, Any]]:
    failures: list[str] = []
    normalized_state = final_state.strip().upper()
    if normalized_state != "COMPLETE":
        failures.append(f"mission did not reach COMPLETE (state={normalized_state or 'unknown'})")

    chain_event_types = _extract_event_types(chain_trace)
    missing_events = [
        event_type for event_type in required_chain_events if event_type not in chain_event_types
    ]
    if missing_events:
        failures.append(f"missing required chain events: {', '.join(missing_events)}")

    logicnode_count = len(logicnodes) if isinstance(logicnodes, list) else 0
    artifact_count = len(build_artifacts) if isinstance(build_artifacts, list) else 0
    diagnostics = {
        "chain_event_types": chain_event_types,
        "missing_chain_events": missing_events,
        "logicnode_count": logicnode_count,
        "build_artifact_count": artifact_count,
    }
    return not failures, failures, diagnostics


def run_dry(demos: list[dict[str, Any]]) -> dict[str, Any]:
    passed, failures = validate_demo_specs(demos)
    return {
        "schema_version": "phase18_demo_missions.v1",
        "run_mode": "dry",
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "passed": passed,
        "failure_reasons": failures,
        "demos": demos,
    }


def run_live(args: argparse.Namespace, demos: list[dict[str, Any]]) -> dict[str, Any]:
    base_url = args.gateway_base_url.rstrip("/")
    passed, failures = validate_demo_specs(demos)
    if not passed:
        return {
            "schema_version": "phase18_demo_missions.v1",
            "run_mode": "live",
            "run_timestamp_utc": datetime.now(UTC).isoformat(),
            "passed": False,
            "failure_reasons": failures,
            "demos": [],
        }

    ready_status, ready_payload = _request_json(
        "GET", f"{base_url}/readyz", timeout_seconds=args.timeout_seconds
    )
    if ready_status != 200 or not isinstance(ready_payload, dict):
        return {
            "schema_version": "phase18_demo_missions.v1",
            "run_mode": "live",
            "run_timestamp_utc": datetime.now(UTC).isoformat(),
            "passed": False,
            "failure_reasons": ["gateway /readyz did not return healthy JSON"],
            "demos": [],
        }

    results: list[dict[str, Any]] = []
    for demo in demos:
        payload = demo["payload"]
        idempotency_key = f"phase18-{demo['demo_id']}-{uuid.uuid4()}"
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
                    "demo_id": demo["demo_id"],
                    "passed": False,
                    "failure_reasons": [f"mission creation failed (status={create_status})"],
                }
            )
            continue

        mission_id = str(create_payload.get("mission_id", "")).strip()
        final_state, _mission_payload = _wait_for_terminal_state(
            base_url=base_url,
            mission_id=mission_id,
            timeout_seconds=args.mission_timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
        chain_status, chain_trace = _request_json(
            "GET", f"{base_url}/v1/missions/{mission_id}/chain-trace"
        )
        logic_status, logicnodes = _request_json(
            "GET", f"{base_url}/v1/missions/{mission_id}/logicnodes?limit=100"
        )
        artifacts_status, build_artifacts = _request_json(
            "GET", f"{base_url}/v1/missions/{mission_id}/build-artifacts?limit=20"
        )
        if chain_status != 200:
            chain_trace = []
        if logic_status != 200:
            logicnodes = []
        if artifacts_status != 200:
            build_artifacts = []

        demo_passed, demo_failures, diagnostics = _evaluate_live_demo(
            final_state=final_state,
            chain_trace=chain_trace,
            logicnodes=logicnodes,
            build_artifacts=build_artifacts,
            required_chain_events=tuple(args.required_chain_events),
        )
        results.append(
            {
                "demo_id": demo["demo_id"],
                "mission_id": mission_id,
                "final_state": final_state,
                "passed": demo_passed,
                "failure_reasons": demo_failures,
                **diagnostics,
            }
        )

    all_failures = [
        f"{result['demo_id']}: {reason}"
        for result in results
        for reason in result.get("failure_reasons", [])
    ]
    return {
        "schema_version": "phase18_demo_missions.v1",
        "run_mode": "live",
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "passed": not all_failures,
        "failure_reasons": all_failures,
        "demos": results,
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _print_summary(report: dict[str, Any]) -> None:
    print("== Phase 18 Demo Missions ==")
    print(f"Mode: {report['run_mode']}")
    print(f"Timestamp (UTC): {report['run_timestamp_utc']}")
    print(f"Passed: {report['passed']}")
    for reason in report.get("failure_reasons", []):
        print(f"FAIL: {reason}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or validate reproducible Phase 18 demo missions."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Validate demo payloads only.")
    mode.add_argument("--live", action="store_true", help="Submit demos to a live API gateway.")
    parser.add_argument("--gateway-base-url", default="http://localhost:8100")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--mission-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument(
        "--required-chain-events",
        nargs="+",
        default=list(DEFAULT_REQUIRED_CHAIN_EVENTS),
    )
    parser.add_argument(
        "--output-file",
        default="docs/evidence/phase18_demo_missions_latest.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    demos = build_demo_missions()
    report = run_live(args, demos) if args.live else run_dry(demos)
    _write_report(Path(args.output_file), report)
    _print_summary(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
