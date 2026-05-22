import asyncio
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

testdata_agent = importlib.import_module("orchestrator.testdata_agent")
rqca_agent = importlib.import_module("orchestrator.rqca_agent")
llm_delegation = importlib.import_module("orchestrator.llm_delegation")


def test_testdata_manifest_is_safe_and_capped() -> None:
    result = asyncio.run(
        testdata_agent.generate_testdata_manifest(
            mission_id="mission-1",
            generated_output={
                "filename": "solution.py",
                "language": "python",
                "dependencies": ["pytest"],
            },
            integration_tests=None,
            mission_contract={},
            language="python",
            settings=SimpleNamespace(),
        )
    )

    assert result["schema_version"] == "testdata_manifest.v1"
    assert result["base_image"] == "python:3.11-slim"
    assert result["network_required"] is False
    assert result["timeout_seconds"] <= 60
    assert result["memory_limit_mb"] <= 512
    assert result["run_command"] == "python /workspace/solution.py"


def test_rqca_unsupported_language_returns_dry_run() -> None:
    result = asyncio.run(
        rqca_agent.run_runtime_qc(
            mission_id="mission-1",
            generated_output={"filename": "main.rs", "generated_code": "fn main() {}"},
            testdata_manifest={"base_image": "rust:1.78-slim", "run_command": "cargo test"},
            integration_tests=None,
            language="rust",
            settings=SimpleNamespace(docker_bin="docker"),
        )
    )

    assert result["verdict"] == "DRY_RUN"
    assert result["execution_type"] == "dry_run"


def test_rqca_missing_artifact_returns_skipped() -> None:
    result = asyncio.run(
        rqca_agent.run_runtime_qc(
            mission_id="mission-1",
            generated_output={"filename": "solution.py", "generated_code": ""},
            testdata_manifest={},
            integration_tests=None,
            language="python",
            settings=SimpleNamespace(docker_bin="docker"),
        )
    )

    assert result["verdict"] == "SKIPPED"
    assert result["passed"] is True


def test_rqca_assessment_fallback_marks_fail_not_safe() -> None:
    result = asyncio.run(
        llm_delegation.generate_rqca_assessment(
            mission_id="mission-1",
            execution_result={"verdict": "FAIL", "passed": False},
            mission_contract={},
            language="python",
        )
    )

    assert result["qc_verdict"] == "FAIL"
    assert result["deployment_safe"] is False
