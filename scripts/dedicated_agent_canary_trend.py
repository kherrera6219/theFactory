from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FULL_MODE = "full"
WIRING_MODE = "wiring"


def _planned_runs(args: argparse.Namespace) -> list[tuple[str, str]]:
    """Pair each language with the contract it will be judged against.

    Full-mode languages are only scheduled when credentials are actually
    present. Running them without credentials guarantees a completion block and
    a red job, which would train everyone to ignore this alarm -- the precise
    failure this split exists to prevent.
    """
    planned: list[tuple[str, str]] = []
    if _credentials_present():
        planned.extend((language, FULL_MODE) for language in args.languages)
    planned.extend((language, WIRING_MODE) for language in args.wiring_languages)
    return planned


def _credentials_present() -> bool:
    return any(
        os.getenv(name, "").strip()
        for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")
    )


@dataclass
class CanaryRun:
    language: str
    mode: str
    command: list[str]
    exit_code: int | None
    report_path: str
    passed: bool
    failure_reasons: list[str]
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


def _build_canary_command(
    *,
    python_executable: str,
    gateway_base_url: str,
    orchestrator_base_url: str,
    language: str,
    mode: str,
    timeout_seconds: float,
    poll_seconds: float,
    output_file: str,
) -> list[str]:
    return [
        python_executable,
        "scripts/dedicated_agent_canary_rollout.py",
        "--gateway-base-url",
        gateway_base_url,
        "--orchestrator-base-url",
        orchestrator_base_url,
        "--language",
        language,
        "--timeout-seconds",
        str(timeout_seconds),
        "--poll-seconds",
        str(poll_seconds),
        "--output-file",
        output_file,
        "--mode",
        mode,
    ]


def _summarize_runs(runs: list[CanaryRun]) -> dict[str, Any]:
    total = len(runs)
    passed_count = sum(1 for run in runs if run.passed)
    failed_count = total - passed_count
    pass_rate = round((passed_count / total) * 100.0, 2) if total else 0.0
    failed_languages = [run.language for run in runs if not run.passed]
    full_runs = [run for run in runs if run.mode == FULL_MODE]
    # The headline claim. A run with no full-mode language proves the pipeline
    # is wired and nothing more; say so in the evidence rather than letting a
    # green check imply the factory built something.
    end_to_end_proven = bool(full_runs) and all(run.passed for run in full_runs)
    return {
        "total_runs": total,
        "passed_runs": passed_count,
        "failed_runs": failed_count,
        "pass_rate_percent": pass_rate,
        "failed_languages": failed_languages,
        "all_passed": failed_count == 0,
        "full_mode_languages": [run.language for run in full_runs],
        "wiring_mode_languages": [run.language for run in runs if run.mode == WIRING_MODE],
        "end_to_end_generation_proven": end_to_end_proven,
        "proof_scope": (
            "generation proven end to end"
            if end_to_end_proven
            else "pipeline wiring only -- generation NOT proven (no LLM credentials)"
        ),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")


def run(args: argparse.Namespace) -> int:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    python_executable = args.python_executable or sys.executable
    report_dir = Path(args.report_dir)
    run_rows: list[CanaryRun] = []

    for language, mode in _planned_runs(args):
        language_key = language.strip().lower()
        per_run_report = report_dir / f"dedicated_agent_canary_{language_key}_{timestamp}.json"
        command = _build_canary_command(
            python_executable=python_executable,
            gateway_base_url=args.gateway_base_url,
            orchestrator_base_url=args.orchestrator_base_url,
            language=language_key,
            mode=mode,
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
            output_file=str(per_run_report),
        )
        exit_code, stderr_tail, error = _run_command(command)
        report_payload = _read_json(per_run_report)
        if report_payload:
            passed = bool(report_payload.get("passed"))
        else:
            passed = exit_code == 0 and error is None
        failure_reasons: list[str] = []
        if isinstance(report_payload.get("failure_reasons"), list):
            failure_reasons = [
                str(item)
                for item in report_payload["failure_reasons"]
                if isinstance(item, (str, int, float))
            ]
        if error:
            failure_reasons.append(error)
        run_rows.append(
            CanaryRun(
                language=language_key,
                mode=mode,
                command=command,
                exit_code=exit_code,
                report_path=str(per_run_report),
                passed=passed,
                failure_reasons=failure_reasons,
                stderr_tail=stderr_tail,
                error=error,
            )
        )

    summary = _summarize_runs(run_rows)
    output_payload = {
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "gateway_base_url": args.gateway_base_url,
        "orchestrator_base_url": args.orchestrator_base_url,
        "languages": [row.language for row in run_rows],
        "summary": summary,
        "runs": [asdict(row) for row in run_rows],
    }
    _write_json(Path(args.output_file), output_payload)
    if args.history_file:
        _append_jsonl(
            Path(args.history_file),
            {
                "run_timestamp_utc": output_payload["run_timestamp_utc"],
                "pass": summary["all_passed"],
                "summary": summary,
                "languages": list(args.languages),
                "output_file": args.output_file,
            },
        )

    print("== Dedicated-Agent Canary Trend Qualification ==")
    print(f"full-mode={','.join(summary['full_mode_languages']) or '(none - no LLM credentials)'}")
    print(f"wiring-mode={','.join(summary['wiring_mode_languages']) or '(none)'}")
    print(f"pass_rate={summary['pass_rate_percent']}%")
    print(f"proof_scope={summary['proof_scope']}")
    print(f"output={args.output_file}")
    if not summary["end_to_end_generation_proven"]:
        print(
            "NOTE: end-to-end generation was NOT proven this run. Set "
            "GEMINI_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY to enable the "
            "full-mode canary."
        )
    if summary["all_passed"]:
        print("PASS: all canary routes satisfied qualification contract")
    else:
        print("FAIL: one or more language canaries failed")
        for row in run_rows:
            if row.passed:
                continue
            print(f"  - {row.language}: {', '.join(row.failure_reasons) or 'qualification failed'}")
    return 0 if summary["all_passed"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run dedicated-agent canary rollout repeatedly across language routes and "
            "emit trend evidence."
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
        "--languages",
        nargs="+",
        default=["python"],
        help=(
            "Languages judged against the FULL contract (must reach COMPLETE). "
            "Requires live LLM credentials; skipped entirely when none are set, "
            "because without them a completion block is guaranteed."
        ),
    )
    parser.add_argument(
        "--wiring-languages",
        nargs="+",
        default=["rust", "kotlin", "julia"],
        help=(
            "Languages judged against the WIRING contract: routing and chain "
            "events must be correct and the mission must reach VERIFIED, but a "
            "completion block is accepted. Cheap and deterministic; proves the "
            "pipeline is connected, NOT that generation works."
        ),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=360.0,
        help="Per-language canary timeout (seconds)",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=10.0,
        help="Per-language canary poll interval (seconds)",
    )
    parser.add_argument(
        "--python-executable",
        default="",
        help="Python executable used to run canary child processes",
    )
    parser.add_argument(
        "--report-dir",
        default="docs/evidence/canary-runs",
        help="Directory for per-language canary reports",
    )
    parser.add_argument(
        "--output-file",
        default="docs/evidence/dedicated_agent_canary_trend_latest.json",
        help="Output trend report JSON path",
    )
    parser.add_argument(
        "--history-file",
        default="docs/evidence/dedicated_agent_canary_trend_history.jsonl",
        help="Append-only JSONL history file",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
