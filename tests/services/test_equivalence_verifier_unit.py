from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

equivalence_verifier = importlib.import_module("orchestrator.equivalence_verifier")


def _generated_output() -> dict[str, object]:
    return {
        "source": "llm",
        "generated_code": "def read_csv(path):\n    return []\n",
        "filename": "solution.py",
        "language": "python",
    }


def _artifact(verified: bool = True) -> dict[str, object]:
    return {
        "artifact_id": "generated-code-output",
        "artifact_type": "generated_code",
        "status": "SUCCESS",
        "digest_sha256": "abc123",
        "verification": {"verified": verified, "verification_method": "sha256"},
    }


def test_mission_requires_equivalence_for_real_generated_output_only() -> None:
    assert equivalence_verifier.mission_requires_equivalence(
        {"generated_output": _generated_output()}
    )
    assert not equivalence_verifier.mission_requires_equivalence(
        {"generated_output": {"source": "fallback", "generated_code": "print('x')"}}
    )
    assert not equivalence_verifier.mission_requires_equivalence({"source_code": "print('x')"})


def test_build_equivalence_report_passes_with_verified_artifact() -> None:
    report = equivalence_verifier.build_equivalence_report(
        mission_id="mission-1",
        requested_target_language="python",
        metadata={
            "generated_output": _generated_output(),
            "feature_contract": {"acceptance_criteria": ["Returns rows"]},
            "application_intelligence_map": {
                "aim_id": "aim-1",
                "detected_languages": ["python"],
            },
        },
        build_artifacts=[_artifact()],
        enforcement_enabled=True,
    )

    assert report["schema_version"] == "equivalence_report.v1"
    assert report["passed"] is True
    assert report["blocking"] is False
    assert report["status"] == "passed"
    assert any(check["check_id"] == "generated_artifact_verified" for check in report["checks"])


def test_build_equivalence_report_blocks_when_required_artifact_fails() -> None:
    report = equivalence_verifier.build_equivalence_report(
        mission_id="mission-1",
        requested_target_language="python",
        metadata={"generated_output": _generated_output()},
        build_artifacts=[_artifact(verified=False)],
        enforcement_enabled=True,
    )

    assert report["passed"] is False
    assert report["blocking"] is True
    assert report["status"] == "blocked"
    assert report["risk_level"] == "high"


def test_build_equivalence_report_is_advisory_when_enforcement_disabled() -> None:
    report = equivalence_verifier.build_equivalence_report(
        mission_id="mission-1",
        requested_target_language="python",
        metadata={"generated_output": _generated_output()},
        build_artifacts=[],
        enforcement_enabled=False,
    )

    assert report["passed"] is False
    assert report["blocking"] is False
    assert report["status"] == "review_required"
