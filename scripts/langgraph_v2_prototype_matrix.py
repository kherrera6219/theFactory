from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class QualificationRun:
    name: str
    command: list[str]
    exit_code: int | None
    report_path: str
    passed: bool
    stderr_tail: str | None
    error: str | None


def _run_command(command: list[str]) -> tuple[int | None, str | None, str | None]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:
        return None, None, repr(exc)
    stderr_tail = completed.stderr[-500:] if completed.stderr else None
    return completed.returncode, stderr_tail, None


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_pass_flag(report: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = report.get(key)
        if isinstance(value, bool):
            return value
    return False


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")


def _build_baseline_command(
    *,
    python_executable: str,
    gateway_base_url: str,
    orchestrator_base_url: str,
    timeout_seconds: float,
    poll_seconds: float,
    output_file: str,
) -> list[str]:
    return [
        python_executable,
        "scripts/mission_artifact_qualification.py",
        "--gateway-base-url",
        gateway_base_url,
        "--orchestrator-base-url",
        orchestrator_base_url,
        "--profile-label",
        "v1_1_baseline",
        "--timeout-seconds",
        str(timeout_seconds),
        "--poll-seconds",
        str(poll_seconds),
        "--output-file",
        output_file,
    ]


def _build_prototype_command(
    *,
    python_executable: str,
    gateway_base_url: str,
    orchestrator_ready_url: str,
    compose_file: str,
    output_file: str,
) -> list[str]:
    return [
        python_executable,
        "scripts/langgraph_postgres_recovery_qualification.py",
        "--base-url",
        gateway_base_url,
        "--orchestrator-ready-url",
        orchestrator_ready_url,
        "--compose-file",
        compose_file,
        "--output-file",
        output_file,
    ]


def run(args: argparse.Namespace) -> int:
    python_executable = args.python_executable or sys.executable
    baseline_report_path = Path(args.baseline_output_file)
    prototype_report_path = Path(args.prototype_output_file)

    baseline_command = _build_baseline_command(
        python_executable=python_executable,
        gateway_base_url=args.gateway_base_url,
        orchestrator_base_url=args.orchestrator_base_url,
        timeout_seconds=args.mission_timeout_seconds,
        poll_seconds=args.mission_poll_seconds,
        output_file=str(baseline_report_path),
    )
    prototype_command = _build_prototype_command(
        python_executable=python_executable,
        gateway_base_url=args.gateway_base_url,
        orchestrator_ready_url=args.orchestrator_ready_url,
        compose_file=args.compose_file,
        output_file=str(prototype_report_path),
    )

    baseline_exit, baseline_stderr, baseline_error = _run_command(baseline_command)
    baseline_payload = _read_json(baseline_report_path)
    baseline_passed = _resolve_pass_flag(baseline_payload, "passed", "pass")

    prototype_exit, prototype_stderr, prototype_error = _run_command(prototype_command)
    prototype_payload = _read_json(prototype_report_path)
    prototype_passed = _resolve_pass_flag(prototype_payload, "pass", "passed")

    baseline_run = QualificationRun(
        name="v1_1_baseline",
        command=baseline_command,
        exit_code=baseline_exit,
        report_path=str(baseline_report_path),
        passed=baseline_passed,
        stderr_tail=baseline_stderr,
        error=baseline_error,
    )
    prototype_run = QualificationRun(
        name="langgraph_v2_prototype",
        command=prototype_command,
        exit_code=prototype_exit,
        report_path=str(prototype_report_path),
        passed=prototype_passed,
        stderr_tail=prototype_stderr,
        error=prototype_error,
    )

    failure_reasons: list[str] = []
    if not baseline_run.passed:
        failure_reasons.append("v1.1 baseline qualification failed")
    if not prototype_run.passed and not args.allow_prototype_failure:
        failure_reasons.append("LangGraph v2 prototype qualification failed")
    if baseline_run.error:
        failure_reasons.append(f"baseline execution error: {baseline_run.error}")
    if prototype_run.error:
        failure_reasons.append(f"prototype execution error: {prototype_run.error}")

    report = {
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "allow_prototype_failure": args.allow_prototype_failure,
        "pass": not failure_reasons,
        "failure_reasons": failure_reasons,
        "v1_1_baseline_passed": baseline_run.passed,
        "langgraph_v2_prototype_passed": prototype_run.passed,
        "runs": [asdict(baseline_run), asdict(prototype_run)],
    }
    _write_json(Path(args.output_file), report)
    if args.history_file:
        _append_jsonl(
            Path(args.history_file),
            {
                "run_timestamp_utc": report["run_timestamp_utc"],
                "pass": report["pass"],
                "v1_1_baseline_passed": baseline_run.passed,
                "langgraph_v2_prototype_passed": prototype_run.passed,
                "failure_reasons": list(report["failure_reasons"]),
                "output_file": args.output_file,
            },
        )

    print("== LangGraph v2 Prototype Matrix Qualification ==")
    print(f"baseline_passed={baseline_run.passed}")
    print(f"prototype_passed={prototype_run.passed}")
    print(f"allow_prototype_failure={args.allow_prototype_failure}")
    print(f"output={args.output_file}")
    if failure_reasons:
        for reason in failure_reasons:
            print(f"FAIL: {reason}")
    else:
        print("PASS: baseline is preserved and prototype matrix qualification executed")
    return 0 if report["pass"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run v1.1 baseline and LangGraph v2 prototype qualification side-by-side "
            "behind feature-flag controls."
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
        help="Orchestrator base URL for baseline mission qualification",
    )
    parser.add_argument(
        "--orchestrator-ready-url",
        default="http://localhost:8101/readyz",
        help="Orchestrator readiness URL for LangGraph restart qualification",
    )
    parser.add_argument(
        "--compose-file",
        default="deploy/docker-compose.yaml",
        help="Compose file for LangGraph restart qualification control",
    )
    parser.add_argument(
        "--mission-timeout-seconds",
        type=float,
        default=90.0,
        help="Baseline mission qualification timeout",
    )
    parser.add_argument(
        "--mission-poll-seconds",
        type=float,
        default=1.0,
        help="Baseline mission qualification poll interval",
    )
    parser.add_argument(
        "--allow-prototype-failure",
        action="store_true",
        default=False,
        help="Do not fail overall matrix if prototype track fails",
    )
    parser.add_argument(
        "--python-executable",
        default="",
        help="Python executable used for child script invocation",
    )
    parser.add_argument(
        "--baseline-output-file",
        default="docs/evidence/mission_artifact_qualification_v1_1_latest.json",
        help="Output report path for v1.1 baseline run",
    )
    parser.add_argument(
        "--prototype-output-file",
        default="docs/evidence/langgraph_postgres_recovery_qualification_latest.json",
        help="Output report path for LangGraph prototype run",
    )
    parser.add_argument(
        "--output-file",
        default="docs/evidence/langgraph_v2_prototype_matrix_latest.json",
        help="Output matrix summary report path",
    )
    parser.add_argument(
        "--history-file",
        default="docs/evidence/langgraph_v2_prototype_matrix_history.jsonl",
        help="Append-only JSONL history file",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
