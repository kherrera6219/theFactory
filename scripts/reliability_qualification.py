from __future__ import annotations

import argparse
import asyncio
import ctypes
import json
import os
import shlex
import statistics
import subprocess  # nosec B404
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx


@dataclass
class MissionSample:
    status_code: int | None
    latency_seconds: float
    error: str | None = None


@dataclass
class ReadinessSample:
    endpoint: str
    ok: bool
    status_code: int | None
    latency_seconds: float
    error: str | None = None


@dataclass
class RecoveryResult:
    passed: bool
    polls: int


@dataclass
class InjectionResult:
    configured: bool
    executed: bool
    exit_code: int | None
    stderr_tail: str | None
    error: str | None


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100)[max(0, min(99, int(pct) - 1))]


def _max_consecutive_readiness_failures(samples: list[ReadinessSample]) -> int:
    current: dict[str, int] = {}
    max_seen = 0
    for sample in samples:
        if sample.ok:
            current[sample.endpoint] = 0
            continue
        current[sample.endpoint] = current.get(sample.endpoint, 0) + 1
        if current[sample.endpoint] > max_seen:
            max_seen = current[sample.endpoint]
    return max_seen


async def _send_mission(
    client: httpx.AsyncClient, base_url: str, index: int, semaphore: asyncio.Semaphore
) -> MissionSample:
    payload = {
        "prompt": f"reliability-qualification-{index}",
        "requested_target_language": "python",
        "metadata": {"source": "reliability_qualification"},
    }
    headers = {"Idempotency-Key": f"reliability-{uuid.uuid4()}"}

    async with semaphore:
        started = time.perf_counter()
        try:
            response = await client.post(f"{base_url}/v1/missions", json=payload, headers=headers)
            latency = time.perf_counter() - started
            return MissionSample(status_code=response.status_code, latency_seconds=latency)
        except Exception as exc:
            latency = time.perf_counter() - started
            return MissionSample(status_code=None, latency_seconds=latency, error=repr(exc))


async def _probe_ready_endpoint(client: httpx.AsyncClient, endpoint: str) -> ReadinessSample:
    started = time.perf_counter()
    try:
        response = await client.get(endpoint)
        latency = time.perf_counter() - started
        return ReadinessSample(
            endpoint=endpoint,
            ok=response.status_code < 400,
            status_code=response.status_code,
            latency_seconds=latency,
        )
    except Exception as exc:
        latency = time.perf_counter() - started
        return ReadinessSample(
            endpoint=endpoint,
            ok=False,
            status_code=None,
            latency_seconds=latency,
            error=repr(exc),
        )


async def _monitor_readiness(
    client: httpx.AsyncClient,
    endpoints: list[str],
    interval_seconds: float,
    stop_event: asyncio.Event,
    sink: list[ReadinessSample],
) -> None:
    while not stop_event.is_set():
        batch = await asyncio.gather(
            *[_probe_ready_endpoint(client, endpoint) for endpoint in endpoints]
        )
        sink.extend(batch)
        await asyncio.sleep(interval_seconds)


async def _run_recovery_probe(
    client: httpx.AsyncClient,
    endpoints: list[str],
    timeout_seconds: float,
    poll_seconds: float,
    consecutive_successes: int,
) -> RecoveryResult:
    deadline = time.monotonic() + timeout_seconds
    healthy_streak = 0
    polls = 0
    while time.monotonic() < deadline:
        polls += 1
        batch = await asyncio.gather(
            *[_probe_ready_endpoint(client, endpoint) for endpoint in endpoints]
        )
        if all(sample.ok for sample in batch):
            healthy_streak += 1
            if healthy_streak >= consecutive_successes:
                return RecoveryResult(passed=True, polls=polls)
        else:
            healthy_streak = 0
        await asyncio.sleep(poll_seconds)
    return RecoveryResult(passed=False, polls=polls)


def _execute_failure_command(command: str) -> InjectionResult:
    try:
        argv = _split_command(command)
    except ValueError as exc:
        return InjectionResult(
            configured=True,
            executed=False,
            exit_code=None,
            stderr_tail=None,
            error=repr(exc),
        )
    if not argv:
        return InjectionResult(
            configured=True,
            executed=False,
            exit_code=None,
            stderr_tail=None,
            error="ValueError('failure command is empty')",
        )
    try:
        # Reliability qualification executes only explicit argv-parsed commands.
        # Command is parsed into argv and executed with shell=False.
        completed = subprocess.run(  # nosec B603
            argv,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        return InjectionResult(
            configured=True,
            executed=False,
            exit_code=None,
            stderr_tail=None,
            error=repr(exc),
        )
    stderr_tail = completed.stderr[-500:] if completed.stderr else None
    return InjectionResult(
        configured=True,
        executed=True,
        exit_code=completed.returncode,
        stderr_tail=stderr_tail,
        error=None,
    )


def _split_command(command: str) -> list[str]:
    if not command.strip():
        raise ValueError("failure command is empty")
    if os.name != "nt":
        return shlex.split(command, posix=True)

    command_line_to_argv = ctypes.windll.shell32.CommandLineToArgvW
    command_line_to_argv.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    command_line_to_argv.restype = ctypes.POINTER(ctypes.c_wchar_p)
    local_free = ctypes.windll.kernel32.LocalFree
    local_free.argtypes = [ctypes.c_void_p]
    local_free.restype = ctypes.c_void_p

    argc = ctypes.c_int()
    argv_ptr = command_line_to_argv(command, ctypes.byref(argc))
    if not argv_ptr:
        raise ValueError("failed to parse command line")
    try:
        return [argv_ptr[index] for index in range(argc.value)]
    finally:
        local_free(argv_ptr)


async def _schedule_failure_injection(delay_seconds: float, command: str) -> InjectionResult:
    await asyncio.sleep(delay_seconds)
    return await asyncio.to_thread(_execute_failure_command, command)


async def collect_qualification_data(
    args: argparse.Namespace,
) -> tuple[list[MissionSample], list[ReadinessSample], RecoveryResult, InjectionResult]:
    base_url = args.base_url.rstrip("/")
    endpoints = [endpoint.strip() for endpoint in args.readiness_endpoints if endpoint.strip()]
    total_requests = max(1, int(args.duration_seconds * args.requests_per_second))
    dispatch_interval = 1.0 / args.requests_per_second
    semaphore = asyncio.Semaphore(args.concurrency)
    readiness_samples: list[ReadinessSample] = []

    async with httpx.AsyncClient(timeout=args.timeout_seconds) as client:
        stop_event = asyncio.Event()
        monitor_task = asyncio.create_task(
            _monitor_readiness(
                client=client,
                endpoints=endpoints,
                interval_seconds=args.readiness_poll_seconds,
                stop_event=stop_event,
                sink=readiness_samples,
            )
        )
        injection_task: asyncio.Task[InjectionResult] | None = None
        if args.failure_command:
            injection_task = asyncio.create_task(
                _schedule_failure_injection(
                    delay_seconds=args.failure_inject_after_seconds,
                    command=args.failure_command,
                )
            )

        mission_tasks: list[asyncio.Task[MissionSample]] = []
        next_dispatch = time.perf_counter()
        for index in range(total_requests):
            sleep_for = next_dispatch - time.perf_counter()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            mission_tasks.append(
                asyncio.create_task(_send_mission(client, base_url, index, semaphore))
            )
            next_dispatch += dispatch_interval

        mission_samples = await asyncio.gather(*mission_tasks)
        stop_event.set()
        await monitor_task

        recovery_result = await _run_recovery_probe(
            client=client,
            endpoints=endpoints,
            timeout_seconds=args.recovery_timeout_seconds,
            poll_seconds=args.recovery_poll_seconds,
            consecutive_successes=args.recovery_consecutive_successes,
        )

        injection_result = InjectionResult(
            configured=False,
            executed=False,
            exit_code=None,
            stderr_tail=None,
            error=None,
        )
        if injection_task is not None:
            injection_result = await injection_task

    return mission_samples, readiness_samples, recovery_result, injection_result


def _build_report(
    args: argparse.Namespace,
    mission_samples: list[MissionSample],
    readiness_samples: list[ReadinessSample],
    recovery_result: RecoveryResult,
    injection_result: InjectionResult,
) -> dict:
    total_requests = len(mission_samples)
    success_count = sum(
        1
        for sample in mission_samples
        if sample.status_code is not None and sample.status_code < 400
    )
    mission_errors = total_requests - success_count
    success_rate = (success_count / total_requests) * 100 if total_requests else 0.0
    latencies = [sample.latency_seconds for sample in mission_samples]
    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    max_latency = max(latencies) if latencies else 0.0
    readiness_failures = sum(1 for sample in readiness_samples if not sample.ok)
    max_consecutive = _max_consecutive_readiness_failures(readiness_samples)
    readiness_failure_counts_by_endpoint: dict[str, int] = {}
    for sample in readiness_samples:
        if sample.ok:
            continue
        readiness_failure_counts_by_endpoint[sample.endpoint] = (
            readiness_failure_counts_by_endpoint.get(sample.endpoint, 0) + 1
        )

    failure_reasons: list[str] = []
    if success_rate < args.min_success_rate:
        failure_reasons.append(
            f"success rate {success_rate:.2f}% below threshold {args.min_success_rate:.2f}%"
        )
    if p95 > args.max_p95_seconds:
        failure_reasons.append(f"p95 {p95:.3f}s above threshold {args.max_p95_seconds:.3f}s")
    if readiness_failures > args.max_readiness_failures:
        failure_reasons.append(
            "readiness failures "
            f"{readiness_failures} above threshold {args.max_readiness_failures}"
        )
    if max_consecutive > args.max_consecutive_readiness_failures:
        failure_reasons.append(
            "max consecutive readiness failures "
            f"{max_consecutive} above threshold {args.max_consecutive_readiness_failures}"
        )
    if not recovery_result.passed:
        failure_reasons.append(
            "recovery probe did not reach required healthy streak before timeout"
        )
    if injection_result.configured and not injection_result.executed:
        failure_reasons.append("failure injection command did not execute")
    if (
        injection_result.configured
        and injection_result.executed
        and injection_result.exit_code != 0
    ):
        failure_reasons.append(
            f"failure injection command exited with code {injection_result.exit_code}"
        )

    status_counts: dict[str, int] = {}
    for sample in mission_samples:
        key = "exception" if sample.status_code is None else str(sample.status_code)
        status_counts[key] = status_counts.get(key, 0) + 1

    return {
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "readiness_endpoints": list(args.readiness_endpoints),
        "duration_seconds": args.duration_seconds,
        "requests_per_second": args.requests_per_second,
        "concurrency": args.concurrency,
        "total_requests": total_requests,
        "mission_success_rate_percent": round(success_rate, 3),
        "mission_error_count": mission_errors,
        "mission_status_counts": status_counts,
        "mission_error_samples": _mission_error_samples(mission_samples),
        "latency_p50_seconds": round(p50, 4),
        "latency_p95_seconds": round(p95, 4),
        "latency_max_seconds": round(max_latency, 4),
        "readiness_checks_total": len(readiness_samples),
        "readiness_failures_total": readiness_failures,
        "readiness_failure_counts_by_endpoint": readiness_failure_counts_by_endpoint,
        "readiness_failure_samples": _readiness_failure_samples(readiness_samples),
        "max_consecutive_readiness_failures": max_consecutive,
        "recovery_probe": asdict(recovery_result),
        "failure_injection": asdict(injection_result),
        "thresholds": {
            "min_success_rate_percent": args.min_success_rate,
            "max_p95_seconds": args.max_p95_seconds,
            "max_readiness_failures": args.max_readiness_failures,
            "max_consecutive_readiness_failures": args.max_consecutive_readiness_failures,
            "recovery_timeout_seconds": args.recovery_timeout_seconds,
            "recovery_consecutive_successes": args.recovery_consecutive_successes,
        },
        "passed": not failure_reasons,
        "failure_reasons": failure_reasons,
    }


def _mission_error_samples(
    mission_samples: list[MissionSample],
    *,
    limit: int = 5,
) -> list[dict[str, object]]:
    samples: list[dict[str, object]] = []
    for sample in mission_samples:
        if sample.status_code is not None and sample.status_code < 400:
            continue
        samples.append(
            {
                "status_code": sample.status_code,
                "latency_seconds": round(sample.latency_seconds, 4),
                "error": sample.error,
            }
        )
        if len(samples) >= limit:
            break
    return samples


def _readiness_failure_samples(
    readiness_samples: list[ReadinessSample],
    *,
    limit: int = 10,
) -> list[dict[str, object]]:
    samples: list[dict[str, object]] = []
    for sample in readiness_samples:
        if sample.ok:
            continue
        samples.append(
            {
                "endpoint": sample.endpoint,
                "status_code": sample.status_code,
                "latency_seconds": round(sample.latency_seconds, 4),
                "error": sample.error,
            }
        )
        if len(samples) >= limit:
            break
    return samples


def _print_report(report: dict) -> None:
    print("== Reliability Qualification Report ==")
    print(f"Timestamp (UTC): {report['run_timestamp_utc']}")
    print(f"Base URL: {report['base_url']}")
    print(f"Readiness endpoints: {report['readiness_endpoints']}")
    print(f"Duration: {report['duration_seconds']}s")
    print(f"Requests per second: {report['requests_per_second']}")
    print(f"Concurrency: {report['concurrency']}")
    print(f"Total mission requests: {report['total_requests']}")
    print(f"Mission success rate: {report['mission_success_rate_percent']:.2f}%")
    print(f"Mission status counts: {report['mission_status_counts']}")
    print(f"Latency p50: {report['latency_p50_seconds']:.3f}s")
    print(f"Latency p95: {report['latency_p95_seconds']:.3f}s")
    print(f"Latency max: {report['latency_max_seconds']:.3f}s")
    print(
        "Readiness checks: "
        f"{report['readiness_checks_total']} total, {report['readiness_failures_total']} failed"
    )
    if report["readiness_failure_counts_by_endpoint"]:
        print(
            "Readiness failures by endpoint: "
            f"{report['readiness_failure_counts_by_endpoint']}"
        )
    print(f"Max consecutive readiness failures: {report['max_consecutive_readiness_failures']}")
    print(
        "Recovery probe: "
        f"passed={report['recovery_probe']['passed']} polls={report['recovery_probe']['polls']}"
    )
    if report["failure_injection"]["configured"]:
        print(
            "Failure injection: "
            f"executed={report['failure_injection']['executed']} "
            f"exit_code={report['failure_injection']['exit_code']}"
        )
    if report["passed"]:
        print("PASS: reliability qualification thresholds met")
        return
    if report["mission_error_samples"]:
        print(f"Mission error samples: {report['mission_error_samples']}")
    if report["readiness_failure_samples"]:
        print(f"Readiness failure samples: {report['readiness_failure_samples']}")
    for reason in report["failure_reasons"]:
        print(f"FAIL: {reason}")


def _write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


async def run(args: argparse.Namespace) -> int:
    mission_samples, readiness_samples, recovery_result, injection_result = (
        await collect_qualification_data(args)
    )
    report = _build_report(
        args=args,
        mission_samples=mission_samples,
        readiness_samples=readiness_samples,
        recovery_result=recovery_result,
        injection_result=injection_result,
    )
    _print_report(report)
    if args.output_file:
        _write_report(Path(args.output_file), report)
    return 0 if report["passed"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run long-duration reliability qualification against the API gateway."
    )
    parser.add_argument("--base-url", default="http://localhost:8100", help="API gateway base URL")
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=300.0,
        help="Total load duration in seconds",
    )
    parser.add_argument(
        "--requests-per-second",
        type=float,
        default=2.0,
        help="Average request dispatch rate",
    )
    parser.add_argument("--concurrency", type=int, default=12, help="Concurrent request workers")
    parser.add_argument("--timeout-seconds", type=float, default=10.0, help="HTTP timeout")
    parser.add_argument(
        "--min-success-rate",
        type=float,
        default=99.0,
        help="Minimum mission success rate percentage",
    )
    parser.add_argument(
        "--max-p95-seconds",
        type=float,
        default=2.5,
        help="Maximum p95 mission latency",
    )
    parser.add_argument(
        "--readiness-endpoints",
        nargs="+",
        default=["http://localhost:8100/readyz", "http://localhost:8101/readyz"],
        help="Ready endpoints to probe while load is running",
    )
    parser.add_argument(
        "--readiness-poll-seconds",
        type=float,
        default=5.0,
        help="Readiness probe interval while load is running",
    )
    parser.add_argument(
        "--max-readiness-failures",
        type=int,
        default=8,
        help="Maximum failed readiness checks allowed",
    )
    parser.add_argument(
        "--max-consecutive-readiness-failures",
        type=int,
        default=4,
        help="Maximum consecutive readiness failures allowed per endpoint",
    )
    parser.add_argument(
        "--failure-command",
        default="",
        help="Optional shell command to inject a failure during the run",
    )
    parser.add_argument(
        "--failure-inject-after-seconds",
        type=float,
        default=90.0,
        help="Seconds to wait before running the failure command",
    )
    parser.add_argument(
        "--recovery-timeout-seconds",
        type=float,
        default=120.0,
        help="Max time to wait for post-load readiness recovery",
    )
    parser.add_argument(
        "--recovery-poll-seconds",
        type=float,
        default=3.0,
        help="Readiness poll interval during recovery probe",
    )
    parser.add_argument(
        "--recovery-consecutive-successes",
        type=int,
        default=3,
        help="Required consecutive healthy probe cycles for recovery",
    )
    parser.add_argument(
        "--output-file",
        default="reports/reliability-qualification.json",
        help="Optional JSON report output path",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
