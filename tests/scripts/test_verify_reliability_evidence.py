import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "verify_reliability_evidence.py"

spec = importlib.util.spec_from_file_location("verify_reliability_evidence", MODULE_PATH)
assert spec is not None and spec.loader is not None
verify_reliability_evidence = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = verify_reliability_evidence
spec.loader.exec_module(verify_reliability_evidence)


def _payload(**overrides):
    payload = {
        "run_timestamp_utc": "2026-06-26T12:00:00+00:00",
        "base_url": "http://localhost:8100",
        "readiness_endpoints": ["http://localhost:8100/readyz", "http://localhost:8101/readyz"],
        "readiness_failure_counts_by_endpoint": {},
        "mission_error_samples": [],
        "readiness_failure_samples": [],
        "recovery_probe": {"passed": True, "polls": 3},
        "failure_injection": {"configured": False, "executed": False},
        "thresholds": {"min_success_rate_percent": 99.0},
        "passed": True,
        "failure_reasons": [],
    }
    payload.update(overrides)
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_verify_reliability_evidence_passes_current_shape(tmp_path: Path) -> None:
    evidence_file = tmp_path / "reliability.json"
    _write_json(evidence_file, _payload())

    result = verify_reliability_evidence.verify_reliability_evidence(
        evidence_file=evidence_file
    )

    assert result["verified"] is True
    assert result["base_url"] == "http://localhost:8100"


def test_verify_reliability_evidence_rejects_missing_diagnostics(tmp_path: Path) -> None:
    evidence_file = tmp_path / "reliability.json"
    payload = _payload()
    del payload["readiness_failure_samples"]
    _write_json(evidence_file, payload)

    with pytest.raises(RuntimeError, match="readiness_failure_samples"):
        verify_reliability_evidence.verify_reliability_evidence(evidence_file=evidence_file)


def test_verify_reliability_evidence_rejects_failed_unless_allowed(tmp_path: Path) -> None:
    evidence_file = tmp_path / "reliability.json"
    _write_json(evidence_file, _payload(passed=False, failure_reasons=["p95 above threshold"]))

    with pytest.raises(RuntimeError, match="did not pass"):
        verify_reliability_evidence.verify_reliability_evidence(evidence_file=evidence_file)

    result = verify_reliability_evidence.verify_reliability_evidence(
        evidence_file=evidence_file,
        require_passed=False,
    )
    assert result["passed"] is False
