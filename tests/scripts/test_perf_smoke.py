import argparse
import asyncio
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "perf_smoke.py"

spec = importlib.util.spec_from_file_location("perf_smoke", MODULE_PATH)
assert spec is not None and spec.loader is not None
perf_smoke = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = perf_smoke
spec.loader.exec_module(perf_smoke)


def test_percentile_handles_empty_and_single_values() -> None:
    assert perf_smoke._percentile([], 50) == 0.0
    assert perf_smoke._percentile([0.5], 95) == 0.5


def test_parse_args_defaults(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["perf_smoke.py"])
    args = perf_smoke.parse_args()
    assert args.base_url == "http://localhost:8100"
    assert args.requests == 40
    assert args.concurrency == 10
    assert args.min_success_rate == 99.0


def test_run_returns_zero_when_thresholds_met(monkeypatch, capsys) -> None:
    async def _send_success(_client, _base_url, _index, _semaphore, **_kwargs):
        return perf_smoke.Sample(status_code=200, latency_seconds=0.05)

    monkeypatch.setattr(perf_smoke, "_send_mission", _send_success)
    args = argparse.Namespace(
        base_url="http://localhost:8100",
        requests=5,
        concurrency=2,
        timeout_seconds=5.0,
        min_success_rate=99.0,
        max_p95_seconds=1.0,
        api_key=None,
    )

    exit_code = asyncio.run(perf_smoke.run(args))
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "PASS: performance smoke thresholds met" in output


def test_run_returns_one_when_success_rate_or_latency_fail(monkeypatch, capsys) -> None:
    async def _send_mixed(_client, _base_url, index, _semaphore, **_kwargs):
        if index == 0:
            return perf_smoke.Sample(status_code=500, latency_seconds=0.2)
        return perf_smoke.Sample(status_code=200, latency_seconds=2.5)

    monkeypatch.setattr(perf_smoke, "_send_mission", _send_mixed)
    args = argparse.Namespace(
        base_url="http://localhost:8100",
        requests=3,
        concurrency=2,
        timeout_seconds=5.0,
        min_success_rate=99.0,
        max_p95_seconds=1.0,
        api_key=None,
    )

    exit_code = asyncio.run(perf_smoke.run(args))
    output = capsys.readouterr().out
    assert exit_code == 1
    assert "FAIL: success rate" in output
    assert "FAIL: p95" in output
