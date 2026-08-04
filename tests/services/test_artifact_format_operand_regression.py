"""Regression tests for the artifact-format false positive found live.

A real mission — "Build a Python command-line tool that converts CSV files to
JSON" — generated correct Python (`csv2json.py`) and was then failed with:

    Delivered artifact format '.py' does not match the contracted
    deliverable format(s): ['csv', 'json']

`_check_artifact_format` was built for contracts that name the deliverable's own
container ("deliver a single self-contained HTML file"). It could not tell that
apart from a data-processing tool naming formats it *operates on*. The acceptance
criterion "Running the tool on a valid CSV file..." matched `<format> file` and
became a required deliverable format.

The consequence was not cosmetic. The required failure cascaded:

    artifact_format FAILS (false positive)
      -> equivalence passed=false            (advisory, did not block)
        -> security_compliance: "no passing equivalence evidence"
          -> status=blocked, blocking=TRUE   -> mission stranded at VERIFIED

So an advisory check reached through security compliance and hard-blocked a
correct mission. Every data-conversion mission would hit it (2026-08-04).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from orchestrator.equivalence_verifier import (  # noqa: E402
    _check_artifact_format,
    _expected_artifact_extensions,
    build_equivalence_report,
)

# The real acceptance criteria from the live mission.
LIVE_CRITERIA = [
    "Running the tool on a valid CSV file without -o outputs a formatted JSON array to stdout.",
    "Running the tool with -o <file_path> writes the identical formatted JSON array to the "
    "specified output file.",
]


def _artifacts(filename: str):
    return [
        {
            "artifact_type": "generated_code",
            "artifact_id": "a1",
            "digest_sha256": "0" * 64,
            "manifest": {"filename": filename},
            "verification": {"verified": True, "verification_scope": "integrity"},
        }
    ]


# --- operand vs deliverable -------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Running the tool on a valid CSV file without -o outputs a formatted JSON array.",
        "Convert a CSV file to JSON.",
        "Parse the input JSON file and emit a report.",
        "Accepts a YAML file as input.",
        "Reads a CSV file from disk.",
    ],
)
def test_formats_the_tool_operates_on_are_not_deliverables(text: str) -> None:
    assert _expected_artifact_extensions(text) == set()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Deliver a single self-contained HTML file.", {"html", "htm"}),
        ("Produce a markdown file summarising the results.", {"md", "markdown"}),
    ],
)
def test_genuine_deliverable_formats_are_still_detected(text: str, expected: set[str]) -> None:
    """The check must keep doing the job it was built for."""
    assert _expected_artifact_extensions(text) == expected


# --- the live regression, end to end ----------------------------------------


def test_python_artifact_is_not_failed_for_a_contract_naming_data_formats() -> None:
    """The exact live scenario: .py delivered, contract mentions csv/json."""
    check = _check_artifact_format(
        {"acceptance_criteria": LIVE_CRITERIA},
        {},
        _artifacts("csv2json.py"),
        {"filename": "csv2json.py", "language": "python"},
        "python",
    )
    assert check["status"] != "fail"
    assert check["required"] is False



def test_a_genuine_format_mismatch_still_fails() -> None:
    """The original Neon Pong incident: .js delivered against an HTML contract.
    That must remain a required failure."""
    check = _check_artifact_format(
        {"acceptance_criteria": ["Deliver a single self-contained HTML file."]},
        {},
        _artifacts("game.js"),
        {"filename": "game.js", "language": "javascript"},
        "html",
    )
    assert check["status"] == "fail"
    assert check["required"] is True


def test_matching_format_still_passes() -> None:
    check = _check_artifact_format(
        {"acceptance_criteria": ["Deliver a single self-contained HTML file."]},
        {},
        _artifacts("game.html"),
        {"filename": "game.html", "language": "html"},
        "html",
    )
    assert check["status"] == "pass"


# --- end-to-end through the report -----------------------------------------


def test_the_live_mission_no_longer_produces_a_required_failure() -> None:
    """Reproduces the whole report for the live mission's shape."""
    report = build_equivalence_report(
        mission_id="mission-regression",
        requested_target_language="python",
        metadata={
            "generated_output": {
                "filename": "csv2json.py",
                "language": "python",
                "generated_code": "import csv, json, argparse\n\n\ndef main():\n    pass\n",
                "source": "llm",
            },
            "feature_contract": {"acceptance_criteria": LIVE_CRITERIA},
        },
        build_artifacts=_artifacts("csv2json.py"),
        enforcement_enabled=True,
    )
    required_failures = [
        check for check in report["checks"] if check["required"] and check["status"] == "fail"
    ]
    assert required_failures == [], [c["check_id"] for c in required_failures]
    assert report["blocking"] is False
    assert report["passed"] is True
