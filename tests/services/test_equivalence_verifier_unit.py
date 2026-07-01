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
    assert report["verification_scope"] == "correctness"
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


def test_artifact_format_gate_ignores_prohibited_extension_mentions() -> None:
    report = equivalence_verifier.build_equivalence_report(
        mission_id="mission-pong",
        requested_target_language="javascript",
        metadata={
            "generated_output": {
                "source": "llm",
                "generated_code": "console.log('pong');",
                "filename": "neon-pong.js",
                "language": "javascript",
            },
            "feature_contract": {
                "summary": "Modern Neon Pong as a single HTML5 file.",
                "acceptance_criteria": [
                    "Deliver one self-contained HTML file with no external .js/.css files.",
                ],
            },
        },
        build_artifacts=[_html_artifact("neon-pong.js")],
        enforcement_enabled=True,
    )

    check = _format_check(report)
    assert check["status"] == "fail"
    assert check["required"] is True
    assert check["evidence"]["expected_extensions"] == ["htm", "html"]


def test_artifact_format_gate_fails_when_required_format_has_no_extension() -> None:
    report = equivalence_verifier.build_equivalence_report(
        mission_id="mission-pong",
        requested_target_language="javascript",
        metadata={
            "generated_output": {
                "source": "llm",
                "generated_code": "<!DOCTYPE html><html></html>",
                "filename": "neon-pong",
                "language": "javascript",
            },
            "feature_contract": {
                "summary": "A single self-contained HTML file implementing Pong.",
            },
        },
        build_artifacts=[_html_artifact("neon-pong")],
        enforcement_enabled=True,
    )

    check = _format_check(report)
    assert check["status"] == "fail"
    assert check["required"] is True
    assert report["blocking"] is True


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


def _content_signature_check(report: dict[str, object]) -> dict[str, object]:
    return next(
        check
        for check in report["checks"]  # type: ignore[index]
        if check["check_id"] == "language_content_signature"
    )


def test_language_content_signature_flags_python_fallback_for_c_mission() -> None:
    # Regression for the 2026-06-30 battery's C mission: the specialist
    # delivered a Python script (a ctypes-based generator) that self-reported
    # "language": "c" instead of real .h/.c source. _check_language_alignment
    # cannot catch this (both values trace back to "c"); this check inspects
    # the code body directly.
    report = equivalence_verifier.build_equivalence_report(
        mission_id="mission-c",
        requested_target_language="c",
        metadata={
            "generated_output": {
                "source": "llm",
                "filename": "generator_harness.py",
                "language": "c",
                "generated_code": (
                    "import ctypes\n"
                    "from pathlib import Path\n\n"
                    "async def write_c_library_files(target_dir: Path) -> None:\n"
                    "    target_dir.mkdir(parents=True, exist_ok=True)\n"
                ),
            },
        },
        build_artifacts=[],
        enforcement_enabled=True,
    )

    check = _content_signature_check(report)
    assert check["status"] == "fail"
    assert check["required"] is True
    assert check["evidence"]["python_signals_matched"] >= 2


def test_language_content_signature_flags_python_fallback_for_r_mission() -> None:
    # Regression for the same battery's R mission: a Python function
    # simulating R's recycling/NA-coercion rules, self-reported as "r".
    report = equivalence_verifier.build_equivalence_report(
        mission_id="mission-r",
        requested_target_language="r",
        metadata={
            "generated_output": {
                "source": "llm",
                "filename": "vectorized_math.py",
                "language": "r",
                "generated_code": (
                    "import math\n"
                    "import warnings\n\n"
                    "def r_vector_add(vector1, vector2):\n"
                    "    return []\n"
                ),
            },
        },
        build_artifacts=[],
        enforcement_enabled=True,
    )

    check = _content_signature_check(report)
    assert check["status"] == "fail"
    assert check["required"] is True


def test_language_content_signature_passes_real_go_source() -> None:
    report = equivalence_verifier.build_equivalence_report(
        mission_id="mission-go",
        requested_target_language="go",
        metadata={
            "generated_output": {
                "source": "llm",
                "filename": "mathutil.go",
                "language": "go",
                "generated_code": (
                    "package mathutil\n\n"
                    "func Add(a, b int) int {\n"
                    "    return a + b\n"
                    "}\n"
                ),
            },
        },
        build_artifacts=[],
        enforcement_enabled=True,
    )

    check = _content_signature_check(report)
    assert check["status"] == "pass"
    assert check["required"] is True


def test_language_content_signature_skips_unscoped_languages() -> None:
    # Languages without a marker table must return manual_review ("not
    # evaluated"), never fail ("assumed wrong") — a false "fail" here would
    # incorrectly flag every mission in every uncovered language.
    report = equivalence_verifier.build_equivalence_report(
        mission_id="mission-kotlin",
        requested_target_language="kotlin",
        metadata={
            "generated_output": {
                "source": "llm",
                "filename": "Main.kt",
                "language": "kotlin",
                "generated_code": "fun main() { println(\"hi\") }",
            },
        },
        build_artifacts=[],
        enforcement_enabled=True,
    )

    check = _content_signature_check(report)
    assert check["status"] == "manual_review"
    assert check["required"] is False


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
