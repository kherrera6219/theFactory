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


def _html_artifact(filename: str) -> dict[str, object]:
    return {
        "artifact_id": "generated-code-output",
        "artifact_type": "generated_code",
        "status": "SUCCESS",
        "digest_sha256": "abc123",
        "manifest": {"filename": filename},
        "verification": {"verified": True, "verification_method": "sha256"},
    }


def _format_check(report: dict[str, object]) -> dict[str, object]:
    return next(
        check
        for check in report["checks"]  # type: ignore[index]
        if check["check_id"] == "artifact_format_matches_contract"
    )


def test_artifact_format_gate_fails_when_html_contract_gets_js_file() -> None:
    # Regression for the 2026-06-29 Neon Pong mission: the contract demanded a
    # single self-contained HTML file but the artifact was delivered as `.js`.
    report = equivalence_verifier.build_equivalence_report(
        mission_id="mission-pong",
        requested_target_language="javascript",
        metadata={
            "generated_output": {
                "source": "llm",
                "generated_code": "(function(){ /* ... */ })();",
                "filename": "neon-pong.js",
                "language": "javascript",
            },
            "feature_contract": {
                "summary": "A single self-contained HTML file implementing Pong.",
                "acceptance_criteria": [
                    "Opening the single HTML file directly in Chrome boots the title screen.",
                ],
            },
        },
        build_artifacts=[_html_artifact("neon-pong.js")],
        enforcement_enabled=True,
    )

    check = _format_check(report)
    assert check["status"] == "fail"
    assert check["required"] is True
    assert report["passed"] is False
    assert report["blocking"] is True


def test_artifact_format_gate_passes_when_html_contract_gets_html_file() -> None:
    report = equivalence_verifier.build_equivalence_report(
        mission_id="mission-pong",
        requested_target_language="javascript",
        metadata={
            "generated_output": {
                "source": "llm",
                "generated_code": "<!DOCTYPE html><html><body><canvas></canvas></body></html>",
                "filename": "neon-pong.html",
                "language": "javascript",
            },
            "feature_contract": {
                "summary": "A single self-contained HTML file implementing Pong.",
                "acceptance_criteria": ["Opening the single HTML file boots the title screen."],
            },
        },
        build_artifacts=[_html_artifact("neon-pong.html")],
        enforcement_enabled=True,
    )

    assert _format_check(report)["status"] == "pass"


def test_artifact_format_gate_is_advisory_without_explicit_format() -> None:
    report = equivalence_verifier.build_equivalence_report(
        mission_id="mission-1",
        requested_target_language="python",
        metadata={
            "generated_output": _generated_output(),
            "feature_contract": {"acceptance_criteria": ["Returns rows"]},
        },
        build_artifacts=[_artifact()],
        enforcement_enabled=True,
    )

    check = _format_check(report)
    assert check["status"] == "manual_review"
    assert check["required"] is False
    assert report["passed"] is True


def test_acceptance_criteria_reports_per_criterion_coverage() -> None:
    report = equivalence_verifier.build_equivalence_report(
        mission_id="mission-1",
        requested_target_language="python",
        metadata={
            "generated_output": {
                "source": "llm",
                "generated_code": "def parse_invoice(record):\n    return record\n",
                "filename": "solution.py",
                "language": "python",
            },
            "feature_contract": {
                "acceptance_criteria": [
                    "Parses an invoice record correctly.",
                    "Sends an email notification to the accounting team.",
                ]
            },
        },
        build_artifacts=[_artifact()],
        enforcement_enabled=True,
    )

    check = next(
        c for c in report["checks"] if c["check_id"] == "acceptance_criteria_mapped"
    )
    statuses = {item["criterion"]: item["status"] for item in check["evidence"]["criteria_status"]}
    assert statuses["Parses an invoice record correctly."] == "covered"
    assert statuses["Sends an email notification to the accounting team."] == "needs_review"
    # Acceptance heuristics are advisory: an uncovered criterion does not block.
    assert check["required"] is False
    assert report["passed"] is True
