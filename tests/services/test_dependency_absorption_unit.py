import asyncio
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


def test_execute_absorption_splices_ready_python_plan() -> None:
    result = asyncio.run(
        dependency_absorption.execute_absorption(
            mission_id="mission-1",
            source_code="import left-pad\n\nprint('x')\n",
            language="python",
            absorption_report={
                "planned_replacements": [
                    {"name": "left-pad", "status": "ready_for_planning"}
                ]
            },
            settings=None,
        )
    )

    assert result["status"] == "executed"
    assert result["absorption_count"] == 1
    assert "import left-pad" not in result["modified_source"]
    assert "def left_pad" in result["modified_source"]


def test_execute_absorption_ignores_gated_plan() -> None:
    result = asyncio.run(
        dependency_absorption.execute_absorption(
            mission_id="mission-1",
            source_code="import left-pad\n",
            language="python",
            absorption_report={
                "planned_replacements": [{"name": "left-pad", "status": "gated"}]
            },
            settings=None,
        )
    )

    assert result["status"] == "nothing_to_absorb"
    assert result["absorption_count"] == 0


def test_validate_js_syntax_accepts_valid_and_rejects_invalid() -> None:
    import shutil

    if shutil.which("node") is None:
        # node not available — validator must fail open (skip) rather than block.
        assert dependency_absorption.validate_js_syntax("this is ) not js (") is True
        return
    assert dependency_absorption.validate_js_syntax("const x = 1;\n") is True
    assert dependency_absorption.validate_js_syntax("const x = ;;;\n") is False


def test_js_import_present_only_matches_import_positions() -> None:
    src = (
        "import slugify from 'slugify';\n"
        "const x = require('left-pad');\n"
        "const label = 'this mentions clsx but does not import it';\n"
    )
    assert dependency_absorption._js_import_present(src, "slugify") is True
    assert dependency_absorption._js_import_present(src, "left-pad") is True
    # clsx appears only inside an unrelated string literal — must not match.
    assert dependency_absorption._js_import_present(src, "clsx") is False


def test_detect_used_symbols_js_ignores_string_literal_mentions() -> None:
    src = "const label = 'uses left-pad in a string';\n"
    assert dependency_absorption._detect_used_symbols(src, "left-pad", "javascript") == []


def test_splice_replacement_js_rejects_broken_syntax() -> None:
    import shutil

    if shutil.which("node") is None:
        return  # validation skipped without node; nothing to assert
    source, status, _reason = dependency_absorption._splice_replacement(
        source="import lp from 'left-pad';\nconsole.log(lp);\n",
        library="left-pad",
        language="javascript",
        replacement={"replacement_code": "\nfunction broken( {\n"},
    )
    assert status == "syntax_error"
    # On failure the original source is returned unchanged.
    assert "import lp from 'left-pad'" in source


def test_splice_replacement_js_accepts_valid_replacement() -> None:
    source, status, _reason = dependency_absorption._splice_replacement(
        source="import lp from 'left-pad';\nconsole.log(lp(1, 3));\n",
        library="left-pad",
        language="javascript",
        replacement={
            "replacement_code": (
                "\nfunction leftPad(v, w, c = ' ') { "
                "return String(v).padStart(w, c); }\n"
            )
        },
    )
    assert status == "ok"
    assert "import lp from 'left-pad'" not in source
    assert "function leftPad" in source


def test_build_sbom_delta_uses_inventory_dependencies() -> None:
    result = dependency_absorption.build_sbom_delta(
        original_dependencies=[{"name": "left-pad"}, {"name": "cryptography"}],
        absorption_result={"splices": [{"library": "left-pad", "status": "ok"}]},
        survival_justifications=[{"name": "cryptography"}],
    )

    assert result["removed"] == ["left-pad"]
    assert result["remaining"] == ["cryptography"]
    assert result["kept_with_justification"] == ["cryptography"]
    assert result["reduction_percent"] == 50.0
