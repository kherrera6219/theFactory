"""Unit tests for the brownfield benchmark corpus and harness runner."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "run_brownfield_benchmark.py"

spec = importlib.util.spec_from_file_location("run_brownfield_benchmark", MODULE_PATH)
assert spec is not None and spec.loader is not None
benchmark_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = benchmark_mod
spec.loader.exec_module(benchmark_mod)


def test_discover_seven_valid_mit_benchmark_projects() -> None:
    projects = benchmark_mod.discover_benchmark_projects()
    ids = [project.project_id for project in projects]

    assert ids == [
        "c_buffer_lib",
        "csharp_net_console",
        "express_cjs_node",
        "flask_legacy_py",
        "maven_legacy_java8",
        "php7_legacy_app",
        "port_cli_py_to_go",
    ]
    assert all(project.corpus_valid for project in projects), [
        (p.project_id, p.missing_files, p.validation_errors) for p in projects
    ]


def test_compute_honest_pass_blocks_non_verified_and_degraded_sources() -> None:
    base = {
        "corpus_valid": True,
        "status": "VERIFIED",
        "source": "gemini",
        "runtime_qc_passed": True,
    }
    assert benchmark_mod.compute_honest_pass(base) is True

    for forbidden_source in ("fallback", "advisory", "dry_run", "started_only", "offline"):
        assert benchmark_mod.compute_honest_pass({**base, "source": forbidden_source}) is False

    for forbidden_status in ("DRY_RUN", "ADVISORY", "STARTED_ONLY", "SKIPPED", "FAILED"):
        assert benchmark_mod.compute_honest_pass({**base, "status": forbidden_status}) is False

    assert benchmark_mod.compute_honest_pass({**base, "fallback_used": True}) is False
    assert benchmark_mod.compute_honest_pass({**base, "degraded": True}) is False
    assert benchmark_mod.compute_honest_pass({**base, "runtime_qc_passed": False}) is False
    assert benchmark_mod.compute_honest_pass({**base, "corpus_valid": False}) is False


def test_run_benchmark_offline_never_claims_honest_pass(tmp_path: Path) -> None:
    scorecard = benchmark_mod.run_benchmark(mode="offline")

    assert scorecard["effective_mode"] == "offline"
    assert scorecard["total_projects"] == 7
    assert scorecard["corpus_valid_count"] == 7
    assert scorecard["honest_pass_count"] == 0
    assert scorecard["dry_run_count"] == 7
    assert all(item["status"] == "DRY_RUN" for item in scorecard["projects"])
    assert all(item["honest_pass"] is False for item in scorecard["projects"])

    dated_json, latest_json, latest_md = benchmark_mod.write_evidence_outputs(scorecard, tmp_path)
    assert dated_json.is_file()
    assert latest_json.is_file()
    assert latest_md.is_file()
    assert json.loads(latest_json.read_text(encoding="utf-8"))["corpus_valid_count"] == 7
    assert "Brownfield Benchmark Scorecard" in latest_md.read_text(encoding="utf-8")


def test_run_benchmark_live_mode_scores_mock_outcomes() -> None:
    def fake_live_runner(project, **_kwargs):
        if project.project_id == "c_buffer_lib":
            return {
                "id": project.project_id,
                "status": "VERIFIED",
                "source": "fallback",
                "fallback_used": True,
                "runtime_qc_passed": True,
            }
        return {
            "id": project.project_id,
            "status": "VERIFIED",
            "source": "openai",
            "runtime_qc_passed": True,
        }

    scorecard = benchmark_mod.run_benchmark(mode="live", live_runner=fake_live_runner)
    assert scorecard["effective_mode"] == "live"
    assert scorecard["total_projects"] == 7
    assert scorecard["honest_pass_count"] == 6
    by_id = {item["id"]: item for item in scorecard["projects"]}
    assert by_id["c_buffer_lib"]["honest_pass"] is False
    assert by_id["flask_legacy_py"]["honest_pass"] is True
