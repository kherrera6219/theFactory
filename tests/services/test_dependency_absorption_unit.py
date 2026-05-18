import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

dependency_absorption = importlib.import_module("orchestrator.dependency_absorption")


def test_dependency_inventory_reads_aim_generated_and_package_manifests() -> None:
    metadata = {
        "application_intelligence_map": {"detected_dependencies": ["csv", "requests"]},
        "generated_output": {"dependencies": ["left-pad"]},
        "source_code": (
            "## FILE package.json\n"
            '{"dependencies":{"react":"19.0.0","clsx":"2.1.1"}}\n'
            "## FILE requirements.txt\n"
            "pydantic==2.8.0\n"
        ),
    }

    inventory = dependency_absorption.build_dependency_inventory(
        mission_id="mission-1",
        metadata=metadata,
    )

    names = {item["normalized_name"] for item in inventory["dependencies"]}
    assert {"csv", "requests", "left-pad", "react", "clsx", "pydantic"} <= names
    assert inventory["dependency_count"] == 6


def test_security_dependency_is_safety_blocked_not_absorbed() -> None:
    reports = dependency_absorption.build_dependency_absorption_reports(
        mission_id="mission-1",
        metadata={
            "application_intelligence_map": {
                "detected_dependencies": ["cryptography"],
            }
        },
    )

    classification = reports["dependency_classification_report"]["classifications"][0]
    assert classification["decision"] == "keep"
    assert classification["safety_blocked"] is True
    assert classification["risk_level"] == "high"
    assert reports["dependency_absorption_report"]["safety_block_count"] == 1


def test_small_pure_utility_gets_absorption_plan_when_gates_pass() -> None:
    reports = dependency_absorption.build_dependency_absorption_reports(
        mission_id="mission-1",
        metadata={
            "generated_output": {"dependencies": ["left-pad"]},
            "equivalence_report": {"passed": True},
            "security_compliance_report": {"passed": True, "blocking": False},
        },
    )

    absorption = reports["dependency_absorption_report"]
    assert absorption["status"] == "planned"
    assert absorption["planned_replacements"][0]["name"] == "left-pad"
    assert absorption["planned_replacements"][0]["status"] == "ready_for_planning"
    assert absorption["modified_output_created"] is False


def test_small_pure_utility_plan_is_gated_without_evidence() -> None:
    reports = dependency_absorption.build_dependency_absorption_reports(
        mission_id="mission-1",
        metadata={"generated_output": {"dependencies": ["clsx"]}},
    )

    plan = reports["dependency_absorption_report"]["planned_replacements"][0]
    assert plan["status"] == "gated"
    assert plan["blocked_by"] == [
        "equivalence_report",
        "security_compliance_report",
    ]
