import asyncio
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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
    # MATLAB has no runnable image (paid licence), so it must always return
    # DRY_RUN regardless of Docker rather than a FAIL that blocks the mission.
    result = asyncio.run(
        rqca_agent.run_runtime_qc(
            mission_id="mission-1",
            generated_output={"filename": "main.m", "generated_code": "disp('x')"},
            testdata_manifest={},
            integration_tests=None,
            language="matlab",
            settings=SimpleNamespace(docker_bin="docker"),
        )
    )

    assert result["verdict"] == "DRY_RUN"
    assert result["execution_type"] == "dry_run"


def test_live_language_set_is_exactly_the_runtime_table() -> None:
    """`_ALL_LIVE_LANGUAGES` is derived, so the two can never disagree."""
    assert set(rqca_agent._ALL_LIVE_LANGUAGES) == set(rqca_agent._LANGUAGE_RUNTIMES)
    for language in ("c", "cpp", "rust", "go", "java", "kotlin", "scala", "haskell"):
        assert language in rqca_agent._ALL_LIVE_LANGUAGES

    # Absent on purpose, and each for a reason that would otherwise be
    # rediscovered by watching missions fail:
    #   csharp  -- dotnet-script is not in the SDK image and --network=none
    #              means it cannot be installed at run time.
    #   matlab / mathematica -- no runnable image without a paid licence or
    #              network activation. Octave is not a substitute: passing it
    #              would assert something untrue about MATLAB compatibility.
    # An absent language returns an honest DRY_RUN. A listed-but-broken one
    # returns FAIL, which RQCA_ENFORCEMENT_ENABLED turns into a blocked mission.
    for language in ("csharp", "c#", "matlab", "mathematica"):
        assert language not in rqca_agent._ALL_LIVE_LANGUAGES


def test_every_runtime_respects_the_sandbox_constraints() -> None:
    """Each command must survive the flags the sandbox actually applies.

    /workspace is read-only and there is no network, so a command may not write
    build output next to the source and may not fetch a toolchain. Both broke a
    language during bring-up and neither is visible from this file, which is why
    it is asserted rather than left to review.
    """
    fetchers = ("apt-get", "apk add", "pip install", "npm install", "curl ", "wget ")
    for language, runtime in rqca_agent._LANGUAGE_RUNTIMES.items():
        command = runtime["run_command"].format(filename="main.src", stem="main")
        assert runtime["base_image"], f"{language} has no base image"
        assert "-o /workspace/" not in command, (
            f"{language} writes build output into the read-only workspace: {command}"
        )
        assert "-outputdir /workspace" not in command, (
            f"{language} writes intermediates into the read-only workspace: {command}"
        )
        for fetcher in fetchers:
            assert fetcher not in command, (
                f"{language} tries to fetch a toolchain, but the sandbox has no "
                f"network: {command}"
            )


def test_jvm_runtimes_use_the_filename_stem_as_the_entry_class() -> None:
    """javac/scalac emit a class named after the file, not after the artifact."""
    for language in ("java", "scala"):
        rendered = rqca_agent._LANGUAGE_RUNTIMES[language]["run_command"].format(
            filename="Widget.x", stem="Widget"
        )
        assert rendered.rstrip().endswith("Widget"), rendered


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


def test_rqca_script_syntax_failure_blocks_before_sandbox() -> None:
    with patch.object(
        rqca_agent,
        "_node_syntax_check",
        new=AsyncMock(
            return_value={
                "verdict": "FAIL",
                "passed": False,
                "execution_type": "node_check",
                "stderr_preview": "SyntaxError",
            }
        ),
    ):
        result = asyncio.run(
            rqca_agent.run_runtime_qc(
                mission_id="mission-1",
                generated_output={
                    "filename": "neon-pong.js",
                    "generated_code": "function broken(",
                    "language": "javascript",
                },
                testdata_manifest={},
                integration_tests=None,
                language="javascript",
                settings=SimpleNamespace(docker_bin="docker"),
            )
        )

    assert result["verdict"] == "FAIL"
    assert result["execution_type"] == "artifact_smoke"
    assert result["artifact_smoke"]["artifact_kind"] == "script"


def test_rqca_html_artifact_reports_static_smoke_without_node_execution() -> None:
    with patch.object(
        rqca_agent,
        "_node_syntax_check",
        new=AsyncMock(
            return_value={
                "verdict": "PASS",
                "passed": True,
                "execution_type": "node_check",
            }
        ),
    ):
        result = asyncio.run(
            rqca_agent.run_runtime_qc(
                mission_id="mission-1",
                generated_output={
                    "filename": "neon-pong.html",
                    "generated_code": (
                        "<!doctype html><html><body><canvas></canvas>"
                        "<script>const ok = true;</script></body></html>"
                    ),
                    "language": "javascript",
                },
                testdata_manifest={},
                integration_tests=None,
                language="javascript",
                settings=SimpleNamespace(docker_bin="docker"),
            )
        )

    assert result["verdict"] == "DRY_RUN"
    assert result["dry_run_reason"] == "HTML browser smoke unavailable in orchestrator runtime."
    assert result["artifact_smoke"]["artifact_kind"] == "html"
    assert result["artifact_smoke"]["checks"]["html_structure"]["has_html_tag"] is True
    assert result["artifact_smoke"]["checks"]["browser_load"]["verdict"] == "DRY_RUN"


def test_rqca_html_artifact_extracts_inline_scripts_with_parser() -> None:
    html = (
        "<!doctype html><html><head><link rel='preload stylesheet' href='app.css'>"
        "<script src='app.js'></script></head><body>"
        "<script>const ok = true;</script></body></html>"
    )

    parser = rqca_agent._parse_html_artifact(html)

    assert parser.has_html_tag is True
    assert parser.has_body_tag is True
    assert parser.external_script_count == 1
    assert parser.external_stylesheet_count == 1
    assert parser.inline_scripts == ["const ok = true;"]


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


def test_rqca_assessment_skipped_is_degraded_not_safe() -> None:
    """When runtime QC could not execute (DRY_RUN/SKIPPED), the assessment must
    be reported as degraded/advisory — not a fake deployment-safe pass."""
    for verdict in ("SKIPPED", "DRY_RUN"):
        result = asyncio.run(
            llm_delegation.generate_rqca_assessment(
                mission_id="mission-1",
                execution_result={"verdict": verdict, "passed": True},
                mission_contract={},
                language="python",
            )
        )
        assert result["qc_verdict"] == "ADVISORY"
        assert result["status"] == "degraded"
        assert result["advisory"] is True
        assert result["deployment_safe"] is False


def test_rqca_compose_yaml_is_hardened_and_sanitized() -> None:
    manifest = {
        "multi_container": True,
        "memory_limit_mb": 256,
        "services": [
            {"name": "test runner!", "image": "python:3.11-slim",
             "command": "python /workspace/output.py"},
            {"name": "db", "image": "postgres:16-alpine",
             "environment": {"POSTGRES_PASSWORD": "p@ss: word\ninjected: true"}},
        ],
    }
    yml = rqca_agent._build_rqca_compose_yml(
        mission_id="mission-1",
        filename="output.py",
        code_tmpdir="/tmp/hgr-rqca-abc",
        testdata_manifest=manifest,
    )
    # Same hardening as the single-container path applied to every service.
    assert "cap_drop:" in yml
    assert "no-new-privileges:true" in yml
    assert "read_only: true" in yml
    assert yml.count("read_only: true") == 2
    assert "cpus:" in yml
    # Service name sanitized to a valid compose key (no spaces / punctuation).
    assert "test-runner-" in yml
    assert "test runner!" not in yml
    # Env value with a newline+colon must not become a structural YAML key.
    assert "\n      injected: true" not in yml
    # The crafted value is emitted as a single quoted scalar.
    assert '"POSTGRES_PASSWORD"' in yml


def test_rqca_resolve_test_command_prefers_test_framework() -> None:
    cmd = rqca_agent._resolve_test_command(
        filename="solution.py",
        test_filename="test_solution.py",
        language="python",
        settings=SimpleNamespace(rqca_test_command_template=""),
    )
    assert cmd is not None
    assert "pytest" in cmd
    assert "test_solution.py" in cmd
    # No test file → no test command (caller falls back to running the artifact).
    assert rqca_agent._resolve_test_command(
        filename="solution.py",
        test_filename="",
        language="python",
        settings=SimpleNamespace(),
    ) is None


def test_rqca_resolve_test_command_honors_operator_template() -> None:
    cmd = rqca_agent._resolve_test_command(
        filename="solution.py",
        test_filename="test_solution.py",
        language="python",
        settings=SimpleNamespace(
            rqca_test_command_template="custom-runner {test_filename}"
        ),
    )
    assert cmd == "custom-runner test_solution.py"


def test_security_analysis_offline_fallback_is_degraded() -> None:
    """The offline security gate must report degraded status, not passed=True."""
    result = llm_delegation._fallback_security_analysis(
        mission_id="mission-1", language="python"
    )
    assert result["passed"] is False
    assert result["status"] == "degraded"
    assert result["advisory"] is True
    assert result["deployment_safe"] is False
    assert result["reason"] == "LLM unavailable — gate bypassed"


def test_pod_audit_offline_fallback_is_degraded() -> None:
    """The offline pod-audit gate must report degraded status, not a fake PASS."""
    result = llm_delegation._fallback_pod_audit_verdict(
        mission_id="mission-1",
        pod_name="podA",
        audit_agent_id="AGENT-13-PODA-AUDIT",
    )
    assert result["passed"] is False
    assert result["verdict"] == "DEGRADED"
    assert result["status"] == "degraded"
    assert result["advisory"] is True
    assert result["reason"] == "LLM unavailable — gate bypassed"
