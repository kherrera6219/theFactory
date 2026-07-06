from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


@dataclass
class CommandResult:
    command: list[str]
    exit_code: int | None
    executed: bool
    stderr_tail: str | None
    error: str | None


@dataclass
class ReadinessProbe:
    passed: bool
    polls: int
    duration_seconds: float
    last_status_code: int | None
    last_error: str | None


@dataclass
class MissionProbe:
    mission_id: str
    terminal_state: str | None
    polls: int
    duration_seconds: float
    error: str | None


def _command_result(
    command: list[str],
    *,
    completed: subprocess.CompletedProcess[str],
) -> CommandResult:
    stderr_tail = completed.stderr[-500:] if completed.stderr else None
    return CommandResult(
        command=command,
        exit_code=completed.returncode,
        executed=True,
        stderr_tail=stderr_tail,
        error=None,
    )


def _run_command(
    command: list[str],
    *,
    env_overrides: dict[str, str] | None = None,
) -> CommandResult:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    except Exception as exc:
        return CommandResult(
            command=command,
            exit_code=None,
            executed=False,
            stderr_tail=None,
            error=repr(exc),
        )
    return _command_result(command, completed=completed)


def _compose_command(compose_file: str, *tail: str) -> list[str]:
    return ["docker", "compose", "-f", compose_file, *tail]


def _langgraph_env(args: argparse.Namespace) -> dict[str, str]:
    return {
        "LANGGRAPH_ENABLED": "true",
        "LANGGRAPH_FAIL_OPEN": "true",
        "LANGGRAPH_CHECKPOINTER": "postgres",
        "LANGGRAPH_THREAD_PREFIX": args.thread_prefix,
        "LANGGRAPH_CHECKPOINTER_SETUP": "true",
        "LANGGRAPH_CHECKPOINT_NAMESPACE": args.checkpoint_namespace,
        "LANGGRAPH_CHECKPOINTER_POSTGRES_URL": args.checkpointer_postgres_url,
        "TRANSITION_STEP_SECONDS": str(args.transition_step_seconds),
    }


async def _wait_for_ready(
    client: httpx.AsyncClient,
    *,
    endpoint: str,
    timeout_seconds: float,
    poll_seconds: float,
) -> ReadinessProbe:
    deadline = time.monotonic() + timeout_seconds
    polls = 0
    started = time.monotonic()
    last_status: int | None = None
    last_error: str | None = None

    while time.monotonic() < deadline:
        polls += 1
        try:
            response = await client.get(endpoint)
            last_status = response.status_code
            if response.status_code < 400:
                return ReadinessProbe(
                    passed=True,
                    polls=polls,
                    duration_seconds=time.monotonic() - started,
                    last_status_code=last_status,
                    last_error=None,
                )
            last_error = response.text[:300]
        except Exception as exc:
            last_error = repr(exc)
        await asyncio.sleep(poll_seconds)

    return ReadinessProbe(
        passed=False,
        polls=polls,
        duration_seconds=time.monotonic() - started,
        last_status_code=last_status,
        last_error=last_error,
    )


async def _wait_for_mission_terminal(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    mission_id: str,
    timeout_seconds: float,
    poll_seconds: float,
) -> MissionProbe:
    deadline = time.monotonic() + timeout_seconds
    polls = 0
    started = time.monotonic()

    while time.monotonic() < deadline:
        polls += 1
        try:
            response = await client.get(f"{base_url}/v1/missions/{mission_id}")
            if response.status_code >= 400:
                await asyncio.sleep(poll_seconds)
                continue
            payload = response.json()
            state = str(payload.get("state", "")).upper()
            if state in {"COMPLETE", "FAILED"}:
                return MissionProbe(
                    mission_id=mission_id,
                    terminal_state=state,
                    polls=polls,
                    duration_seconds=time.monotonic() - started,
                    error=None,
                )
        except Exception as exc:
            return MissionProbe(
                mission_id=mission_id,
                terminal_state=None,
                polls=polls,
                duration_seconds=time.monotonic() - started,
                error=repr(exc),
            )
        await asyncio.sleep(poll_seconds)

    return MissionProbe(
        mission_id=mission_id,
        terminal_state=None,
        polls=polls,
        duration_seconds=time.monotonic() - started,
        error="mission did not reach terminal state before timeout",
    )


def _validate_runtime(runtime_payload: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if runtime_payload.get("langgraph_enabled") is not True:
        reasons.append("langgraph_enabled is not true")
    if str(runtime_payload.get("langgraph_checkpointer", "")).strip().lower() != "postgres":
        reasons.append("langgraph_checkpointer is not postgres")
    return not reasons, reasons


def _validate_mission_events(
    events: list[dict[str, Any]],
) -> tuple[bool, list[str], dict[str, Any]]:
    event_types = [str(item.get("event_type", "")) for item in events if isinstance(item, dict)]
    event_type_set = set(event_types)
    required = {"MISSION_RUNNING", "MISSION_VERIFIED", "MISSION_COMPLETE"}
    missing = sorted(required - event_type_set)
    diagnostics = {
        "count": len(events),
        "event_types": event_types,
        "required_event_types": sorted(required),
        "missing_required_event_types": missing,
    }
    if missing:
        return False, [f"missing required mission event(s): {', '.join(missing)}"], diagnostics
    return True, [], diagnostics


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


async def run(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    compose_file = args.compose_file
    langgraph_env = _langgraph_env(args)

    preconfigure_command = _compose_command(
        compose_file,
        "up",
        "-d",
        "--build",
        "--force-recreate",
        "--no-deps",
        "orchestrator",
    )
    restart_command = _compose_command(compose_file, "restart", "orchestrator")

    if not args.execute:
        print("== LangGraph Postgres Recovery Qualification ==")
        print("mode=DRY-RUN (no containers were mutated; pass --execute to run for real)")
        print(f"DRY-RUN: would force-recreate orchestrator with env: {langgraph_env}")
        print(f"DRY-RUN: would run: {' '.join(preconfigure_command)}")
        print(
            "DRY-RUN: would submit a qualification mission, wait "
            f"{args.restart_after_seconds}s, then run: {' '.join(restart_command)}"
        )
        print("DRY-RUN: would then verify readiness recovery and mission completion")
        report = {
            "run_timestamp_utc": datetime.now(UTC).isoformat(),
            "dry_run": True,
            "preconfigure_command": preconfigure_command,
            "restart_command": restart_command,
            "langgraph_env": langgraph_env,
            # A dry-run never verified anything, so it must not report a real
            # pass/fail verdict — downstream consumers should ignore this run.
            "pass": None,
            "failure_reasons": [],
        }
        if args.output_file:
            _write_report(Path(args.output_file), report)
        return 0

    preconfigure_result = _run_command(preconfigure_command, env_overrides=langgraph_env)

    runtime_payload: dict[str, Any] = {}
    runtime_ok = False
    runtime_reasons: list[str] = []
    mission_probe = MissionProbe(
        mission_id="",
        terminal_state=None,
        polls=0,
        duration_seconds=0.0,
        error="mission qualification did not start",
    )
    restart_result = CommandResult(
        command=restart_command,
        exit_code=None,
        executed=False,
        stderr_tail=None,
        error="restart command did not run",
    )
    post_restart_ready = ReadinessProbe(
        passed=False,
        polls=0,
        duration_seconds=0.0,
        last_status_code=None,
        last_error="probe did not run",
    )
    event_validation = {
        "count": 0,
        "event_types": [],
        "required_event_types": ["MISSION_COMPLETE", "MISSION_RUNNING", "MISSION_VERIFIED"],
        "missing_required_event_types": [
            "MISSION_COMPLETE",
            "MISSION_RUNNING",
            "MISSION_VERIFIED",
        ],
    }
    event_reasons = ["mission events probe did not run"]
    events_ok = False

    mission_terminal_monotonic: float | None = None
    async with httpx.AsyncClient(timeout=args.http_timeout_seconds) as client:
        startup_ready = await _wait_for_ready(
            client,
            endpoint=args.orchestrator_ready_url,
            timeout_seconds=args.ready_timeout_seconds,
            poll_seconds=args.ready_poll_seconds,
        )

        if startup_ready.passed:
            summary_response = await client.get(f"{base_url}/v1/operations/summary")
            if summary_response.status_code < 400:
                summary_payload = summary_response.json()
                runtime_payload = summary_payload.get("runtime", {})
            runtime_ok, runtime_reasons = _validate_runtime(runtime_payload)

        restart_started_monotonic = None
        if startup_ready.passed and runtime_ok:
            mission_payload = {
                "prompt": "langgraph-postgres-restart-qualification",
                "requested_target_language": "python",
                "metadata": {
                    "source": "langgraph_postgres_recovery_qualification",
                    "checkpoint_namespace": args.checkpoint_namespace,
                },
            }
            mission_headers = {"Idempotency-Key": f"langgraph-qual-{uuid.uuid4()}"}
            mission_response = await client.post(
                f"{base_url}/v1/missions",
                json=mission_payload,
                headers=mission_headers,
            )
            if mission_response.status_code < 400:
                mission_id = str(mission_response.json().get("mission_id", ""))
                if mission_id:
                    await asyncio.sleep(args.restart_after_seconds)
                    restart_started_monotonic = time.monotonic()
                    restart_result = _run_command(restart_command)
                    post_restart_ready = await _wait_for_ready(
                        client,
                        endpoint=args.orchestrator_ready_url,
                        timeout_seconds=args.ready_timeout_seconds,
                        poll_seconds=args.ready_poll_seconds,
                    )
                    mission_probe = await _wait_for_mission_terminal(
                        client,
                        base_url=base_url,
                        mission_id=mission_id,
                        timeout_seconds=args.mission_timeout_seconds,
                        poll_seconds=args.mission_poll_seconds,
                    )
                    mission_terminal_monotonic = time.monotonic()

                    events_response = await client.get(
                        f"{base_url}/v1/missions/{mission_id}/events",
                        params={"limit": args.events_limit},
                    )
                    events_payload: list[dict[str, Any]] = []
                    if events_response.status_code < 400:
                        parsed = events_response.json()
                        if isinstance(parsed, list):
                            events_payload = [item for item in parsed if isinstance(item, dict)]
                    events_ok, event_reasons, event_validation = _validate_mission_events(
                        events_payload
                    )

    failure_reasons: list[str] = []
    if preconfigure_result.exit_code != 0:
        failure_reasons.append(
            "orchestrator preconfigure command failed with exit code "
            f"{preconfigure_result.exit_code}"
        )
    if runtime_reasons:
        failure_reasons.extend(runtime_reasons)
    if restart_result.exit_code != 0:
        failure_reasons.append(
            f"orchestrator restart command failed with exit code {restart_result.exit_code}"
        )
    if not post_restart_ready.passed:
        failure_reasons.append("orchestrator readyz did not recover after restart")
    if mission_probe.terminal_state != "COMPLETE":
        failure_reasons.append(f"mission terminal state is {mission_probe.terminal_state!r}")
    if mission_probe.error:
        failure_reasons.append(mission_probe.error)
    if not events_ok:
        failure_reasons.extend(event_reasons)

    post_restart_completion_seconds = None
    if restart_started_monotonic is not None and mission_terminal_monotonic is not None:
        post_restart_completion_seconds = max(
            0.0, mission_terminal_monotonic - restart_started_monotonic
        )

    report = {
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "config": {
            "base_url": base_url,
            "orchestrator_ready_url": args.orchestrator_ready_url,
            "compose_file": compose_file,
            "checkpoint_namespace": args.checkpoint_namespace,
            "checkpointer_postgres_url": args.checkpointer_postgres_url,
            "transition_step_seconds": args.transition_step_seconds,
            "restart_after_seconds": args.restart_after_seconds,
            "mission_timeout_seconds": args.mission_timeout_seconds,
            "mission_poll_seconds": args.mission_poll_seconds,
            "ready_timeout_seconds": args.ready_timeout_seconds,
            "ready_poll_seconds": args.ready_poll_seconds,
        },
        "langgraph_env": langgraph_env,
        "preconfigure": asdict(preconfigure_result),
        "runtime_payload": runtime_payload,
        "restart_injection": asdict(restart_result),
        "post_restart_readiness": asdict(post_restart_ready),
        "mission_probe": asdict(mission_probe),
        "post_restart_completion_seconds": post_restart_completion_seconds,
        "event_validation": event_validation,
        "pass": not failure_reasons,
        "failure_reasons": failure_reasons,
    }

    if args.output_file:
        _write_report(Path(args.output_file), report)

    print("== LangGraph Postgres Recovery Qualification ==")
    print(f"pass={report['pass']}")
    print(
        f"mission_id={mission_probe.mission_id or 'n/a'} "
        f"terminal_state={mission_probe.terminal_state}"
    )
    print(
        "post_restart_ready="
        f"{post_restart_ready.passed} polls={post_restart_ready.polls} "
        f"duration={post_restart_ready.duration_seconds:.3f}s"
    )
    if failure_reasons:
        for reason in failure_reasons:
            print(f"FAIL: {reason}")
    else:
        print(
            "PASS: mission lifecycle completed through orchestrator restart "
            "with postgres checkpointer"
        )

    return 0 if report["pass"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Qualify LangGraph postgres checkpoint mission recovery "
            "across orchestrator restart."
        )
    )
    parser.add_argument("--base-url", default="http://localhost:8100", help="API gateway base URL")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually force-recreate and restart the live orchestrator container. "
        "Without this flag (the default), the qualification runs in dry-run mode: "
        "it prints the exact commands that would run and mutates nothing.",
    )
    parser.add_argument(
        "--orchestrator-ready-url",
        default="http://localhost:8101/readyz",
        help="Orchestrator readiness endpoint",
    )
    parser.add_argument(
        "--compose-file",
        default="deploy/docker-compose.yaml",
        help="Docker Compose file for orchestrator control",
    )
    parser.add_argument(
        "--thread-prefix",
        default="mission",
        help="LangGraph thread prefix used during qualification",
    )
    parser.add_argument(
        "--checkpoint-namespace",
        default="mission-lifecycle-qualification",
        help="LangGraph checkpoint namespace used during qualification",
    )
    parser.add_argument(
        "--checkpointer-postgres-url",
        default="",
        help="Optional explicit LangGraph checkpointer postgres URL",
    )
    parser.add_argument(
        "--transition-step-seconds",
        type=float,
        default=3.0,
        help="Transition step delay to widen restart disruption window",
    )
    parser.add_argument(
        "--restart-after-seconds",
        type=float,
        default=0.5,
        help="Delay between mission submission and orchestrator restart injection",
    )
    parser.add_argument(
        "--mission-timeout-seconds",
        type=float,
        default=180.0,
        help="Maximum mission terminal-state wait window",
    )
    parser.add_argument(
        "--mission-poll-seconds",
        type=float,
        default=1.0,
        help="Mission status poll interval",
    )
    parser.add_argument(
        "--ready-timeout-seconds",
        type=float,
        default=120.0,
        help="Readiness recovery timeout",
    )
    parser.add_argument(
        "--ready-poll-seconds",
        type=float,
        default=2.0,
        help="Readiness poll interval",
    )
    parser.add_argument(
        "--events-limit",
        type=int,
        default=50,
        help="Mission events fetch limit",
    )
    parser.add_argument(
        "--http-timeout-seconds",
        type=float,
        default=10.0,
        help="HTTP client timeout",
    )
    parser.add_argument(
        "--output-file",
        default="reports/langgraph-postgres-recovery-qualification.json",
        help="JSON report output path",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
