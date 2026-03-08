import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "qualification_gate_summary.py"

spec = importlib.util.spec_from_file_location("qualification_gate_summary", MODULE_PATH)
assert spec is not None and spec.loader is not None
summary = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = summary
spec.loader.exec_module(summary)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_build_summary_uses_latest_and_history(tmp_path, monkeypatch) -> None:
    policy = {
        "version": 2,
        "requirements": {
            "qualification_gates": {
                "suites": {
                    "operator_route_oidc_matrix": {
                        "required": True,
                        "min_consecutive_passes": 1,
                        "max_age_days": 8,
                        "latest_file": "docs/evidence/operator_route_oidc_matrix_latest.json",
                        "history_file": "docs/evidence/operator_route_oidc_matrix_history.jsonl",
                    }
                }
            }
        },
    }
    _write(
        tmp_path / "docs" / "evidence" / "operator_route_oidc_matrix_latest.json",
        {
            "run_timestamp_utc": "2026-03-08T04:29:52+00:00",
            "pass": True,
            "failure_reasons": [],
        },
    )
    (tmp_path / "docs" / "evidence" / "operator_route_oidc_matrix_history.jsonl").write_text(
        '{"run_timestamp_utc":"2026-03-01T04:29:52+00:00","pass":true}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(summary, "ROOT", tmp_path)

    payload = summary.build_summary(policy)
    assert payload["passed"] is True
    assert payload["suites"]["operator_route_oidc_matrix"]["consecutive_passes"] >= 1


def test_build_summary_fails_when_required_evidence_missing(tmp_path, monkeypatch) -> None:
    policy = {
        "version": 2,
        "requirements": {
            "qualification_gates": {
                "suites": {
                    "operator_route_oidc_matrix": {
                        "required": True,
                        "min_consecutive_passes": 1,
                        "max_age_days": 8,
                        "latest_file": "docs/evidence/operator_route_oidc_matrix_latest.json",
                        "history_file": "docs/evidence/operator_route_oidc_matrix_history.jsonl",
                    }
                }
            }
        },
    }
    monkeypatch.setattr(summary, "ROOT", tmp_path)

    payload = summary.build_summary(policy)
    assert payload["passed"] is False
    assert "missing qualification evidence" in payload["failure_reasons"][0]
