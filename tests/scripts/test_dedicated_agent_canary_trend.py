import argparse
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
    # Full-mode is deliberately one language: it is the only expensive check and
    # the only one that needs credentials. The other three moved to wiring mode.
    assert args.languages == ["python"]
    assert args.wiring_languages == ["rust", "kotlin", "julia"]
    assert args.report_dir == "docs/evidence/canary-runs"
    assert args.output_file == "docs/evidence/dedicated_agent_canary_trend_latest.json"


def test_build_canary_command() -> None:
    command = trend._build_canary_command(
        python_executable="python",
        gateway_base_url="http://localhost:8100",
        orchestrator_base_url="http://localhost:8101",
        language="python",
        mode="full",
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
    assert command[command.index("--mode") + 1] == "full"


def test_summarize_runs() -> None:
    runs = [
        trend.CanaryRun(
            language="python",
            mode="full",
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
            mode="wiring",
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


def test_full_mode_is_skipped_without_credentials(monkeypatch) -> None:
    """No credentials must mean no full-mode run scheduled at all.

    Scheduling one anyway guarantees a completion block and a permanently red
    weekly job, which is what trains people to stop reading the alarm.
    """
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    args = argparse.Namespace(languages=["python"], wiring_languages=["rust", "julia"])
    assert trend._planned_runs(args) == [("rust", "wiring"), ("julia", "wiring")]


def test_full_mode_runs_when_a_credential_is_present(monkeypatch) -> None:
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    args = argparse.Namespace(languages=["python"], wiring_languages=["rust"])
    assert trend._planned_runs(args) == [("python", "full"), ("rust", "wiring")]


def test_blank_credential_does_not_count(monkeypatch) -> None:
    """An empty secret is how an unset GitHub secret arrives; treat it as unset."""
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    args = argparse.Namespace(languages=["python"], wiring_languages=[])
    assert trend._planned_runs(args) == []


def _run(language: str, mode: str, passed: bool) -> "trend.CanaryRun":
    return trend.CanaryRun(
        language=language,
        mode=mode,
        command=[],
        exit_code=0 if passed else 1,
        report_path="",
        passed=passed,
        failure_reasons=[] if passed else ["x"],
        stderr_tail=None,
        error=None,
    )


def test_wiring_only_run_does_not_claim_generation_was_proven() -> None:
    """All-green wiring must still report that generation was NOT proven."""
    summary = trend._summarize_runs([_run("rust", "wiring", True), _run("julia", "wiring", True)])
    assert summary["all_passed"] is True
    assert summary["end_to_end_generation_proven"] is False
    assert "NOT proven" in summary["proof_scope"]


def test_passing_full_mode_run_claims_generation_proven() -> None:
    summary = trend._summarize_runs([_run("python", "full", True), _run("rust", "wiring", True)])
    assert summary["end_to_end_generation_proven"] is True
    assert summary["full_mode_languages"] == ["python"]
    assert summary["wiring_mode_languages"] == ["rust"]


def test_failing_full_mode_run_revokes_the_claim() -> None:
    summary = trend._summarize_runs([_run("python", "full", False), _run("rust", "wiring", True)])
    assert summary["end_to_end_generation_proven"] is False
    assert summary["all_passed"] is False
