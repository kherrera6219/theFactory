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
    _contract_format_text,
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
                "generated_code": "import csv\nimport json\n\n\ndef main():\n    pass\n",
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


# --- the second half: filename literals in CLI examples ---------------------
#
# Fixing the "<format> file" pattern was not enough. The PM rewrites the
# contract during intake and writes its acceptance criteria as CLI examples,
# which match the *explicit* `.ext` pattern instead. The run immediately after
# the first fix still stranded at VERIFIED for exactly this reason.

# The PM's real generated criteria from the live mission.
PM_CRITERIA = [
    "Running `csv2json input.csv` prints a valid pretty-printed JSON array to stdout.",
    "Running `csv2json input.csv -o output.json` writes the JSON output to `output.json` "
    "without printing to stdout.",
    "CSV cell '123' becomes JSON integer 123.",
]


@pytest.mark.parametrize("text", PM_CRITERIA)
def test_filenames_in_cli_examples_are_not_deliverable_formats(text: str) -> None:
    assert _expected_artifact_extensions(text) == set()


def test_an_explicit_format_demand_is_still_detected() -> None:
    """A dot after whitespace is a format requirement, not a filename."""
    assert _expected_artifact_extensions("The deliverable must be a .html file.") == {
        "html",
        "htm",
    }


def test_the_pm_rewritten_contract_no_longer_blocks_on_criteria_alone() -> None:
    """End-to-end with the contract the PM actually produced."""
    report = build_equivalence_report(
        mission_id="mission-pm-contract",
        requested_target_language="python",
        metadata={
            "generated_output": {
                "filename": "csv2json.py",
                "language": "python",
                "generated_code": "import csv\nimport json\n\n\ndef main():\n    pass\n",
                "source": "llm",
            },
            "feature_contract": {
                "summary": (
                    "A zero-dependency Python command-line utility that converts CSV files "
                    "into pretty-printed JSON arrays."
                ),
                "acceptance_criteria": PM_CRITERIA,
            },
        },
        build_artifacts=_artifacts("csv2json.py"),
        enforcement_enabled=True,
    )
    required_failures = [
        check for check in report["checks"] if check["required"] and check["status"] == "fail"
    ]
    assert required_failures == [], [c["check_id"] for c in required_failures]
    assert report["blocking"] is False


# --- the third half: runtime output destinations ----------------------------
#
# The two fixes above were both validated against `acceptance_criteria` alone.
# But `_contract_format_text` reads FIVE fields across TWO contracts — title,
# summary, functional_requirements, acceptance_criteria, deliverables — so the
# third live run still stranded at VERIFIED, on a clause in a field neither
# earlier fix had ever been tested against:
#
#     "Accept optional command-line flag -o/--output to specify output
#      JSON file destination."
#
# That is the tool's runtime output path, not the deliverable's container.

# The full contract the PM produced on the third live run (2026-08-04).
LIVE_FC = {
    "title": "CSV to JSON CLI Converter",
    "summary": (
        "A lightweight Python command-line tool using only standard library modules to "
        "convert CSV files into pretty-printed JSON arrays with automatic type inference "
        "for integers, floats, booleans, and null values."
    ),
    "functional_requirements": [
        "Accept positional argument for input CSV file path.",
        "Accept optional command-line flag -o/--output to specify output JSON file destination.",
        "Read CSV data using standard library 'csv' module and treat the first row as "
        "column header keys.",
        "Perform automatic type inference on field values: convert empty strings to null, "
        "integer strings to int, decimal strings",
        "Format resulting output as a pretty-printed JSON array with standard indentation.",
        "Write formatted JSON to standard output by default, or write to the target output "
        "file if -o/--output is provided.",
    ],
    "acceptance_criteria": [
        "Executing the tool with a valid CSV file outputs a formatted JSON array to stdout.",
        "Executing the tool with -o/--output target.json writes the formatted JSON array to "
        "target.json without stdout payload.",
        "CSV cell with empty value renders as JSON null.",
        "CSV cells containing integer or float numeric strings render as JSON numbers.",
        "CSV cells containing 'true', 'False', 'TRUE' render as JSON booleans.",
        "Running with --help prints clear usage guidelines.",
    ],
}
LIVE_MC = {"acceptance_criteria": LIVE_FC["acceptance_criteria"]}


@pytest.mark.parametrize(
    "text",
    [
        "Accept optional command-line flag -o/--output to specify output JSON file destination.",
        "Write formatted JSON to standard output by default, or write to the target output "
        "file if -o/--output is provided.",
        "Use --output to name the JSON file to write.",
    ],
)
def test_runtime_output_destinations_are_not_deliverables(text: str) -> None:
    assert _expected_artifact_extensions(text) == set()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # The word "output" alone must NOT suppress a real format demand —
        # keying on it would silently re-open the incident this check exists for.
        ("The output must be a single HTML file.", {"html", "htm"}),
        # Nor may "command-line" suppress one.
        ("A command-line tool delivered as a single HTML file.", {"html", "htm"}),
        ("The deliverable is a PDF file.", {"pdf"}),
    ],
)
def test_deliverable_demands_survive_the_runtime_output_rule(
    text: str, expected: set[str]
) -> None:
    """The dangerous direction: a false negative here is silent."""
    assert _expected_artifact_extensions(text) == expected


def test_the_whole_live_contract_names_no_deliverable_format() -> None:
    """Every field, both contracts — the assembly the check actually sees.

    The previous two fixes each passed their own tests and still failed live
    because those tests fed only `acceptance_criteria`. This one goes through
    `_contract_format_text`, so a format demand hiding in `summary`, `title`, or
    `functional_requirements` cannot pass unnoticed again.
    """
    assert _expected_artifact_extensions(_contract_format_text(LIVE_FC, LIVE_MC)) == set()


def test_the_live_mission_check_is_advisory_not_a_required_failure() -> None:
    check = _check_artifact_format(
        LIVE_FC,
        LIVE_MC,
        _artifacts("csv2json.py"),
        {"filename": "csv2json.py", "language": "python"},
        "python",
    )
    assert check["status"] != "fail"
    assert check["required"] is False


def test_the_live_mission_produces_no_blocking_equivalence_report() -> None:
    """End to end: the cascade that stranded the mission must not re-form.

    artifact_format fails (required) -> passed=false -> security compliance
    reports "no passing equivalence evidence" -> blocking -> stuck at VERIFIED.
    """
    report = build_equivalence_report(
        mission_id="mission-live-third-run",
        requested_target_language="python",
        metadata={
            "generated_output": {
                "filename": "csv2json.py",
                "language": "python",
                "generated_code": "import csv\nimport json\n\n\ndef main():\n    pass\n",
                "source": "llm",
            },
            "feature_contract": LIVE_FC,
            "mission_contract": LIVE_MC,
        },
        build_artifacts=_artifacts("csv2json.py"),
        enforcement_enabled=True,
    )
    required_failures = [
        check for check in report["checks"] if check["required"] and check["status"] == "fail"
    ]
    assert required_failures == [], [c["check_id"] for c in required_failures]
    assert report["blocking"] is False
