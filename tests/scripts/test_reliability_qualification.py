import argparse
import asyncio
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "reliability_qualification.py"
WRAPPER_PATH = ROOT / "scripts" / "reliability_qualification.ps1"

spec = importlib.util.spec_from_file_location("reliability_qualification", MODULE_PATH)
assert spec is not None and spec.loader is not None
reliability = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reliability
spec.loader.exec_module(reliability)


def _args(**overrides) -> argparse.Namespace:
    base = {
        "base_url": "http://localhost:8100",
        "readiness_endpoints": ["http://localhost:8100/readyz", "http://localhost:8101/readyz"],
        "duration_seconds": 60.0,
        "requests_per_second": 2.0,
        "concurrency": 8,
        "min_success_rate": 99.0,
        "max_p95_seconds": 2.5,
        "max_readiness_failures": 8,
        "max_consecutive_readiness_failures": 4,
        "recovery_timeout_seconds": 60.0,
        "recovery_consecutive_successes": 3,
        "output_file": "",
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def test_percentile_and_consecutive_readiness_helpers() -> None:
    assert reliability._percentile([], 95) == 0.0
    assert reliability._percentile([0.42], 95) == 0.42

    samples = [
        reliability.ReadinessSample("a", False, 503, 0.01),
        reliability.ReadinessSample("a", False, 503, 0.01),
        reliability.ReadinessSample("a", True, 200, 0.01),
        reliability.ReadinessSample("a", False, 503, 0.01),
    ]
    assert reliability._max_consecutive_readiness_failures(samples) == 2


def test_parse_args_defaults(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["reliability_qualification.py"])
    args = reliability.parse_args()
    assert args.base_url == "http://localhost:8100"
    assert args.duration_seconds == 300.0
    assert args.requests_per_second == 2.0
    assert args.max_p95_seconds == 2.5


def test_build_report_passes_with_healthy_samples() -> None:
    args = _args()
    mission_samples = [
        reliability.MissionSample(status_code=200, latency_seconds=0.2) for _ in range(10)
    ]
    readiness_samples = [reliability.ReadinessSample("r1", True, 200, 0.01) for _ in range(6)]
    recovery = reliability.RecoveryResult(passed=True, polls=3)
    injection = reliability.InjectionResult(
        configured=False,
        executed=False,
        exit_code=None,
        stderr_tail=None,
        error=None,
    )

    report = reliability._build_report(
        args, mission_samples, readiness_samples, recovery, injection
    )
    assert report["passed"] is True
    assert report["base_url"] == "http://localhost:8100"
    assert report["readiness_endpoints"] == [
        "http://localhost:8100/readyz",
        "http://localhost:8101/readyz",
    ]
    assert report["mission_success_rate_percent"] == 100.0
    assert report["mission_error_samples"] == []
    assert report["readiness_failure_counts_by_endpoint"] == {}
    assert report["readiness_failure_samples"] == []
    assert report["failure_reasons"] == []


def test_build_report_fails_on_latency_readiness_and_recovery() -> None:
    args = _args(
        max_p95_seconds=1.0,
        max_readiness_failures=0,
        max_consecutive_readiness_failures=1,
    )
    mission_samples = [
        reliability.MissionSample(status_code=200, latency_seconds=2.0),
        reliability.MissionSample(status_code=500, latency_seconds=2.0),
    ]
    readiness_samples = [
        reliability.ReadinessSample("r1", False, 503, 0.01),
        reliability.ReadinessSample("r1", False, 503, 0.01),
    ]
    recovery = reliability.RecoveryResult(passed=False, polls=5)
    injection = reliability.InjectionResult(
        configured=True,
        executed=True,
        exit_code=2,
        stderr_tail="boom",
        error=None,
    )

    report = reliability._build_report(
        args, mission_samples, readiness_samples, recovery, injection
    )
    assert report["passed"] is False
    reasons = "\n".join(report["failure_reasons"])
    assert "success rate" in reasons
    assert "p95" in reasons
    assert "readiness failures" in reasons
    assert "max consecutive readiness failures" in reasons
    assert "recovery probe" in reasons
    assert "failure injection command exited" in reasons
    assert report["mission_error_samples"] == [
        {"status_code": 500, "latency_seconds": 2.0, "error": None}
    ]
    assert report["readiness_failure_counts_by_endpoint"] == {"r1": 2}
    assert report["readiness_failure_samples"] == [
        {"endpoint": "r1", "status_code": 503, "latency_seconds": 0.01, "error": None},
        {"endpoint": "r1", "status_code": 503, "latency_seconds": 0.01, "error": None},
    ]


def test_print_report_includes_target_and_failure_diagnostics(capsys) -> None:
    args = _args(max_readiness_failures=0)
    mission_samples = [
        reliability.MissionSample(status_code=502, latency_seconds=0.42, error="bad gateway")
    ]
    readiness_samples = [
        reliability.ReadinessSample(
            "http://localhost:8101/readyz",
            False,
            None,
            0.25,
            "connection refused",
        )
    ]
    recovery = reliability.RecoveryResult(passed=True, polls=1)
    injection = reliability.InjectionResult(
        configured=False,
        executed=False,
        exit_code=None,
        stderr_tail=None,
        error=None,
    )
    report = reliability._build_report(
        args, mission_samples, readiness_samples, recovery, injection
    )

    reliability._print_report(report)

    output = capsys.readouterr().out
    assert "Base URL: http://localhost:8100" in output
    assert "Readiness endpoints:" in output
    assert "Readiness failures by endpoint:" in output
    assert "Mission error samples:" in output
    assert "Readiness failure samples:" in output


def test_run_writes_output_file(monkeypatch, tmp_path) -> None:
    async def _collect(_args):
        mission_samples = [reliability.MissionSample(status_code=200, latency_seconds=0.1)]
        readiness_samples = [reliability.ReadinessSample("ready", True, 200, 0.01)]
        recovery = reliability.RecoveryResult(passed=True, polls=1)
        injection = reliability.InjectionResult(
            configured=False,
            executed=False,
            exit_code=None,
            stderr_tail=None,
            error=None,
        )
        return mission_samples, readiness_samples, recovery, injection

    monkeypatch.setattr(reliability, "collect_qualification_data", _collect)
    output_file = tmp_path / "reliability.json"
    args = _args(output_file=str(output_file))

    exit_code = asyncio.run(reliability.run(args))
    assert exit_code == 0
    assert output_file.exists()


def test_execute_failure_command_uses_argv_without_shell(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _CompletedProcess:
        returncode = 0
        stderr = ""

    def _run(argv, *, capture_output, text, check):
        captured["argv"] = argv
        captured["capture_output"] = capture_output
        captured["text"] = text
        captured["check"] = check
        return _CompletedProcess()

    monkeypatch.setattr(reliability.subprocess, "run", _run)

    result = reliability._execute_failure_command('python -c "print(1)"')

    assert result.executed is True
    assert result.exit_code == 0
    assert captured["argv"] == ["python", "-c", "print(1)"]
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["check"] is False


def test_powershell_wrapper_exposes_reliability_controls() -> None:
    wrapper = WRAPPER_PATH.read_text(encoding="utf-8")

    expected_switches = [
        "--base-url",
        "--readiness-endpoints",
        "--readiness-poll-seconds",
        "--max-readiness-failures",
        "--max-consecutive-readiness-failures",
        "--recovery-timeout-seconds",
        "--recovery-poll-seconds",
        "--recovery-consecutive-successes",
    ]
    for expected_switch in expected_switches:
        assert expected_switch in wrapper
