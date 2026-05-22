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
    # Java is not in _ALL_LIVE_LANGUAGES so must always get DRY_RUN regardless of Docker.
    # (Rust, C, C++, C# are now supported compiled languages via S3-02.)
    result = asyncio.run(
        rqca_agent.run_runtime_qc(
            mission_id="mission-1",
            generated_output={"filename": "Main.java", "generated_code": "public class Main {}"},
            testdata_manifest={"base_image": "eclipse-temurin:21", "run_command": "java Main"},
            integration_tests=None,
            language="java",
            settings=SimpleNamespace(docker_bin="docker"),
        )
    )

    assert result["verdict"] == "DRY_RUN"
    assert result["execution_type"] == "dry_run"


def test_rqca_compiled_language_live_languages_set() -> None:
    """Rust, C, C++, C# are now in the live execution set (S3-02)."""
    assert "rust" in rqca_agent._ALL_LIVE_LANGUAGES
    assert "c" in rqca_agent._ALL_LIVE_LANGUAGES
    assert "cpp" in rqca_agent._ALL_LIVE_LANGUAGES
    assert "csharp" in rqca_agent._ALL_LIVE_LANGUAGES
    assert "c#" in rqca_agent._ALL_LIVE_LANGUAGES
    # Java still unsupported — validate it stays out
    assert "java" not in rqca_agent._ALL_LIVE_LANGUAGES


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
