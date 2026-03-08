import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "dedicated_agent_canary_trend.py"

spec = importlib.util.spec_from_file_location("dedicated_agent_canary_trend", MODULE_PATH)
assert spec is not None and spec.loader is not None
trend = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = trend
spec.loader.exec_module(trend)


def test_parse_args_defaults(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["dedicated_agent_canary_trend.py"])
    args = trend.parse_args()
    assert args.gateway_base_url == "http://localhost:8100"
    assert args.orchestrator_base_url == "http://localhost:8101"
    assert args.languages == ["python", "rust", "kotlin", "julia"]
    assert args.report_dir == "docs/evidence/canary-runs"
    assert args.output_file == "docs/evidence/dedicated_agent_canary_trend_latest.json"


def test_build_canary_command() -> None:
    command = trend._build_canary_command(
        python_executable="python",
        gateway_base_url="http://localhost:8100",
        orchestrator_base_url="http://localhost:8101",
        language="python",
        timeout_seconds=60.0,
        poll_seconds=0.5,
        output_file="docs/evidence/report.json",
    )
    assert command[:3] == [
        "python",
        "scripts/dedicated_agent_canary_rollout.py",
        "--gateway-base-url",
    ]
    assert "--language" in command
    assert "python" in command
    assert "--output-file" in command


def test_summarize_runs() -> None:
    runs = [
        trend.CanaryRun(
            language="python",
            command=[],
            exit_code=0,
            report_path="",
            passed=True,
            failure_reasons=[],
            stderr_tail=None,
            error=None,
        ),
        trend.CanaryRun(
            language="rust",
            command=[],
            exit_code=1,
            report_path="",
            passed=False,
            failure_reasons=["missing artifact"],
            stderr_tail="x",
            error=None,
        ),
    ]
    summary = trend._summarize_runs(runs)
    assert summary["total_runs"] == 2
    assert summary["passed_runs"] == 1
    assert summary["failed_runs"] == 1
    assert summary["pass_rate_percent"] == 50.0
    assert summary["failed_languages"] == ["rust"]
    assert summary["all_passed"] is False
