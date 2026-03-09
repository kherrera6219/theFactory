import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "dora_metrics_summary.py"

spec = importlib.util.spec_from_file_location("dora_metrics_summary", MODULE_PATH)
assert spec is not None and spec.loader is not None
dora_metrics_summary = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = dora_metrics_summary
spec.loader.exec_module(dora_metrics_summary)


def test_compute_dora_summary_aggregates_metrics() -> None:
    deployments = [
        {
            "tag": "v1.0.0",
            "commit": "abc",
            "deployed_at": "2026-03-09T00:00:00+00:00",
            "commit_timestamp": "2026-03-08T12:00:00+00:00",
            "lead_time_hours": 12.0,
        },
        {
            "tag": "v1.1.0",
            "commit": "def",
            "deployed_at": "2026-03-02T00:00:00+00:00",
            "commit_timestamp": "2026-03-01T06:00:00+00:00",
            "lead_time_hours": 18.0,
        },
    ]
    qualification_histories = {
        "operator_route_oidc_matrix": [
            {"passed": False, "timestamp": datetime(2026, 3, 1, 0, 0, tzinfo=UTC)},
            {"passed": True, "timestamp": datetime(2026, 3, 1, 1, 0, tzinfo=UTC)},
        ],
        "mission_artifact_qualification": [
            {"passed": True, "timestamp": datetime(2026, 3, 2, 0, 0, tzinfo=UTC)},
        ],
    }

    summary = dora_metrics_summary.compute_dora_summary(
        deployments=deployments,
        qualification_histories=qualification_histories,
        lookback_days=14,
    )

    assert summary["metrics"]["deployment_frequency_per_week"] == 1.0
    assert summary["metrics"]["lead_time_hours_mean"] == 15.0
    assert summary["metrics"]["lead_time_hours_p95"] == 12.0
    assert summary["metrics"]["change_failure_rate"] == 0.3333
    assert summary["metrics"]["mean_time_to_restore_minutes"] == 60.0


def test_load_qualification_histories_reads_history_files(tmp_path, monkeypatch) -> None:
    evidence_dir = tmp_path / "docs" / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "suite_a_history.jsonl").write_text(
        json.dumps({"passed": False, "evaluated_at": "2026-03-01T00:00:00+00:00"}) + "\n",
        encoding="utf-8",
    )
    (evidence_dir / "suite_b_history.jsonl").write_text(
        json.dumps({"passed": True, "generated_at": "2026-03-02T00:00:00+00:00"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(dora_metrics_summary, "EVIDENCE_DIR", evidence_dir)

    histories = dora_metrics_summary.load_qualification_histories()

    assert sorted(histories) == ["suite_a", "suite_b"]
    assert histories["suite_a"][0]["passed"] is False


def test_load_deployments_filters_non_release_tags(monkeypatch) -> None:
    def _run_git(*args: str) -> str:
        if args[:2] == ("for-each-ref", "--sort=-creatordate"):
            return "\n".join(
                [
                    "v1.0.0|2026-03-09T00:00:00+00:00|abc123",
                    "scratch|2026-03-08T00:00:00+00:00|zzz999",
                ]
            )
        if args[:3] == ("show", "-s", "--format=%cI"):
            return "2026-03-08T00:00:00+00:00\n"
        raise AssertionError(f"unexpected git args: {args}")

    monkeypatch.setattr(dora_metrics_summary, "_run_git", _run_git)

    deployments = dora_metrics_summary.load_deployments(lookback_days=30)

    assert len(deployments) == 1
    assert deployments[0]["tag"] == "v1.0.0"
