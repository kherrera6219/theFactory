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
    # C# has no runnable offline image (dotnet-script is absent from the SDK
    # image and --network=none blocks installing it), so it must always return
    # DRY_RUN rather than a FAIL that RQCA_ENFORCEMENT_ENABLED would turn into a
    # blocked mission.
    result = asyncio.run(
        rqca_agent.run_runtime_qc(
            mission_id="mission-1",
            generated_output={"filename": "Main.cs", "generated_code": "class M {}"},
            testdata_manifest={},
            integration_tests=None,
            language="csharp",
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

    # matlab and mathematica run on licence-free subset interpreters, because the
    # product must work with no external requirements and a per-clone vendor
    # licence is not an option at any price.
    for language in ("matlab", "mathematica"):
        assert language in rqca_agent._ALL_LIVE_LANGUAGES

    # C# is still absent: dotnet-script is not in the SDK image and
    # --network=none means it cannot be installed at run time. An absent
    # language returns an honest DRY_RUN; a listed-but-broken one returns FAIL,
    # which RQCA_ENFORCEMENT_ENABLED turns into a blocked mission.
    for language in ("csharp", "c#"):
        assert language not in rqca_agent._ALL_LIVE_LANGUAGES


def test_substitute_runtimes_declare_what_they_actually_verified() -> None:
    """A subset interpreter must never let a pass read as vendor compatibility.

    Octave is not MATLAB and Mathics is not Mathematica. Running on them is
    honest -- it catches the Python-fallback substitution this gate exists for --
    but only while the report says which interpreter ran and how far the claim
    extends.
    """
    for language in ("matlab", "mathematica"):
        runtime = rqca_agent._LANGUAGE_RUNTIMES[language]
        assert runtime.get("runtime_substitute"), (
            f"{language} runs on a substitute interpreter but does not name it"
        )
        assert runtime.get("verified_scope", "").endswith("subset"), (
            f"{language} must declare a subset scope, got "
            f"{runtime.get('verified_scope')!r}"
        )


def test_wolfram_needs_failure_patterns_because_it_exits_zero_on_bad_input() -> None:
    """Exit code is not a verdict for an expression language.

    Wolfram evaluates an undefined symbol to itself rather than erroring, so
    mathics printed Syntax::sntxf on Python source and still exited 0. Without a
    pattern the verdict would be a FALSE PASS -- worse than the DRY_RUN it
    replaced, because it asserts a verification that never happened.
    """
    patterns = rqca_agent._LANGUAGE_RUNTIMES["mathematica"].get("failure_patterns")
    assert patterns, "mathematica must declare failure patterns"
    assert any("Syntax::" in str(p) for p in patterns), patterns


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


def test_rqca_assessment_started_only_is_advisory_even_if_verdict_says_pass() -> None:
    result = asyncio.run(
        llm_delegation.generate_rqca_assessment(
            mission_id="mission-1",
            execution_result={
                "verdict": "PASS",
                "passed": True,
                "verified_scope_detail": "started_only",
            },
            mission_contract={},
            language="python",
        )
    )
    assert result["qc_verdict"] == "ADVISORY"
    assert result["deployment_safe"] is False


def test_rqca_assessment_fallback_tests_are_advisory_even_if_sandbox_passed() -> None:
    result = asyncio.run(
        llm_delegation.generate_rqca_assessment(
            mission_id="mission-1",
            execution_result={
                "verdict": "PASS",
                "passed": True,
                "verified_scope_detail": "tests",
            },
            mission_contract={},
            language="python",
            integration_tests={"source": "fallback", "test_code": "assert True\n"},
        )
    )
    assert result["qc_verdict"] == "ADVISORY"
    assert result["deployment_safe"] is False
    assert result["advisory"] is True
    assert "cannot fail" in str(result.get("reason") or "")


def test_rqca_assessment_fallback_tests_still_fail_when_sandbox_fails() -> None:
    result = asyncio.run(
        llm_delegation.generate_rqca_assessment(
            mission_id="mission-1",
            execution_result={"verdict": "FAIL", "passed": False},
            mission_contract={},
            language="python",
            integration_tests={"source": "fallback"},
        )
    )
    assert result["qc_verdict"] == "FAIL"
    assert result["deployment_safe"] is False


def test_rqca_assessment_syntax_only_is_advisory_even_if_verdict_says_pass() -> None:
    result = asyncio.run(
        llm_delegation.generate_rqca_assessment(
            mission_id="mission-1",
            execution_result={
                "verdict": "PASS",
                "passed": True,
                "verified_scope_detail": "syntax_only",
            },
            mission_contract={},
            language="python",
        )
    )
    assert result["qc_verdict"] == "ADVISORY"
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


def test_rqca_compose_yaml_clamps_invalid_limits_and_skips_bad_services() -> None:
    yml = rqca_agent._build_rqca_compose_yml(
        mission_id="mission-2",
        filename="output.py",
        code_tmpdir="/tmp/ws",
        testdata_manifest={
            "timeout_seconds": "nope",
            "memory_limit_mb": "nope",
            "cpus": "nope",
            "services": ["bad", {"name": "", "image": "python:3.11-slim"}],
        },
    )
    assert "mem_limit:" in yml
    assert "cpus:" in yml


def test_rqca_extracts_inline_scripts() -> None:
    scripts = rqca_agent._extract_inline_scripts(
        "<html><script>console.log(1)</script><script src='x.js'></script></html>"
    )
    assert any("console.log(1)" in item for item in scripts)


def test_rqca_docker_check_uses_sandbox_executor(monkeypatch) -> None:
    seen: list[str] = []

    async def _probe(*, docker_bin: str = "docker") -> bool:
        seen.append(docker_bin)
        return True

    monkeypatch.setattr("orchestrator.sandbox_exec.check_docker_available", _probe)
    assert asyncio.run(rqca_agent._check_docker_available("docker")) is True
    assert seen == ["docker"]


def test_rqca_compose_available_and_node_syntax_check(monkeypatch) -> None:
    import shutil
    import subprocess

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert rqca_agent._compose_available() is False

    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/docker")

    def _ok(*_args, **_kwargs):
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", _ok)
    assert rqca_agent._compose_available() is True

    def _raise(*_args, **_kwargs):
        raise OSError("no compose")

    monkeypatch.setattr(subprocess, "run", _raise)
    assert rqca_agent._compose_available() is False

    async def _missing(*_args, **_kwargs):
        raise FileNotFoundError("node")

    monkeypatch.setattr(rqca_agent.asyncio, "create_subprocess_exec", _missing)
    missing = asyncio.run(
        rqca_agent._node_syntax_check(
            code="console.log(1)",
            filename="app.js",
            settings=SimpleNamespace(node_bin="node"),
        )
    )
    assert missing["verdict"] == "DRY_RUN"

    class _Hang:
        async def communicate(self):
            raise asyncio.TimeoutError()

        def kill(self) -> None:
            return None

    async def _hang(*_args, **_kwargs):
        return _Hang()

    monkeypatch.setattr(rqca_agent.asyncio, "create_subprocess_exec", _hang)
    timed = asyncio.run(
        rqca_agent._node_syntax_check(
            code="while(true){}",
            filename="app.js",
            settings=SimpleNamespace(node_bin="node"),
            timeout_seconds=0.01,
        )
    )
    assert timed["verdict"] == "TIMEOUT"


def test_rqca_resolve_test_command_prefers_test_framework() -> None:
    cmd = rqca_agent._resolve_test_command(
        filename="solution.py",
        test_filename="test_solution.py",
        language="python",
        settings=SimpleNamespace(rqca_test_command_template=""),
    )
    assert cmd is not None
    assert "unittest" in cmd
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


def test_php_requires_an_opening_tag_before_it_will_run() -> None:
    """PHP echoes a file with no `<?php` tag and exits 0.

    That made a Python artifact renamed `.php` return PASS -- the precise
    substitution this gate exists to catch. Caught by the negative-control audit
    rather than by review, so it is pinned here.
    """
    command = rqca_agent._LANGUAGE_RUNTIMES["php"]["run_command"].format(
        filename="main.php", stem="main"
    )
    assert "<?php" in command, (
        "php runtime no longer verifies the opening tag, so any plain-text file "
        f"will be echoed and pass: {command}"
    )


def test_typescript_runs_on_a_runtime_that_understands_types() -> None:
    """`node` cannot parse type annotations.

    On node, only TypeScript that happened to also be valid JavaScript passed,
    and every genuinely typed artifact FAILED -- which under
    RQCA_ENFORCEMENT_ENABLED blocks the mission.
    """
    runtime = rqca_agent._LANGUAGE_RUNTIMES["typescript"]
    assert "node:" not in runtime["base_image"], runtime["base_image"]


def test_non_official_sandbox_images_are_pinned_by_digest() -> None:
    """Images outside Docker Official Images must be content-addressed.

    These images are the containment for untrusted generated code, so a tag that
    silently moves changes what executes it. Three were floating when this was
    written: `euantorano/zig:master` and two `:latest` tags. Docker Official
    Images are exempt only because they are the project's own curated namespace.
    """
    official_namespaces = {
        "python", "node", "gcc", "rust", "golang", "haskell",
        "eclipse-temurin", "php", "ruby", "r-base", "julia",
    }
    for language, runtime in rqca_agent._LANGUAGE_RUNTIMES.items():
        image = runtime["base_image"]
        if image.split(":")[0].split("/")[0] in official_namespaces and "/" not in image.split(":")[0]:
            continue
        assert "@sha256:" in image, (
            f"{language} uses a non-official image by mutable tag: {image}. "
            "Pin it: docker buildx imagetools inspect <ref> "
            "--format '{{.Manifest.Digest}}'"
        )


def test_runtime_qc_gate_no_longer_requires_the_testdata_agent() -> None:
    """Runtime QC had never run on a mission: the gate skipped before RQCA.

    `phases_runtime` returned SKIPPED("TESTDATA disabled") before
    RQCA_AGENT_ENABLED was consulted, and TESTDATA_AGENT_ENABLED is off by
    default -- so no mission ever reached the sandbox. The 19-language matrix was
    proven by calling run_runtime_qc directly, which bypasses that line.
    RQCA now carries its own runtimes, so a supported language must not be
    skipped just because the testdata agent is off.
    """
    import importlib

    phases_runtime = importlib.import_module("orchestrator.mission_flow_v2.phases_runtime")
    source = Path(phases_runtime.__file__).read_text(encoding="utf-8")

    assert "_LANGUAGE_RUNTIMES" in source, (
        "the runtime-QC gate no longer consults the language runtime table, so a "
        "supported language can be skipped purely because testdata is disabled"
    )
    # The bare testdata-only skip must not come back.
    assert 'reason="TESTDATA disabled",' not in source, (
        "the gate skips on testdata alone again; that is what made runtime QC "
        "dead code on every real mission"
    )


def test_no_live_language_can_resolve_to_a_vacuous_cat_command() -> None:
    """`cat` exits 0 having executed nothing, so it is a PASS that proves nothing.

    testdata_agent used to carry its own smaller language table whose fallback
    was `cat /workspace/<file>`, and because it writes BOTH image and command
    into the manifest, RQCA's setdefault never fired and the verified
    _LANGUAGE_RUNTIMES table was bypassed. A live Go mission passed runtime QC by
    printing its own source. Both tables are now one; this fails if they split
    again.
    """
    for language in sorted(rqca_agent._ALL_LIVE_LANGUAGES):
        filename = "Main.java" if language in {"java", "scala"} else f"main.{language[:3]}"
        command = testdata_agent._default_run_command(filename, language)
        image = testdata_agent._default_base_image(language)
        assert not command.startswith("cat "), (
            f"{language} is executed by RQCA but its default command is {command!r}, "
            "which exits 0 without running anything"
        )
        assert command == rqca_agent._LANGUAGE_RUNTIMES[language]["run_command"].format(
            filename=filename, stem=Path(filename).stem
        ), f"{language} default command diverges from _LANGUAGE_RUNTIMES"
        assert image == rqca_agent._LANGUAGE_RUNTIMES[language]["base_image"], (
            f"{language} default image diverges from _LANGUAGE_RUNTIMES"
        )


class TestInvocationDerivedFromUsageExample:
    """Runtime QC invoked every artifact bare, then failed it for saying so.

    A live Go word counter compiled, ran, and exited 1 with "missing file path
    argument" -- correct behaviour for a tool the harness handed no arguments and
    no input file. The information needed was already present and unused: the
    codegen prompt asks the specialist for "one short usage example", and the
    manifest has carried a decorative `synthetic_inputs` field all along.
    """

    def test_arguments_come_from_the_example(self) -> None:
        derive = rqca_agent._invocation_from_usage_example
        assert derive("go run main.go input.txt", "main.go") == ["input.txt"]
        assert derive("python wordcount.py data.txt", "wordcount.py") == ["data.txt"]
        assert derive("java -cp . Main sample.txt", "Main.java") == ["sample.txt"]
        assert derive("$ node main.js a.json b.json", "main.js") == ["a.json", "b.json"]

    def test_an_unrecognised_example_derives_nothing_rather_than_guessing(self) -> None:
        """Fabricating an invocation is worse than deriving none.

        An earlier version stripped known runner words and turned "just run it"
        into ["run", "it"], which would create files named `run` and `it` and
        hand them to the program. Deriving nothing degrades to "not exercised",
        which is safe.
        """
        derive = rqca_agent._invocation_from_usage_example
        assert derive("just run it", "main.go") == []
        assert derive("", "main.go") == []
        assert derive(None, "main.go") == []
        assert derive("see the README", "main.go") == []

    def test_fixture_content_prefers_the_manifest_then_falls_back(self) -> None:
        """`synthetic_inputs` finally has a consumer."""
        assert rqca_agent._fixture_content(
            {"synthetic_inputs": [{"input_data": "alpha beta"}]}
        ) == "alpha beta"
        fallback = rqca_agent._fixture_content({})
        assert fallback.strip(), "a fixture must never be empty"
        # Repeated tokens, so a counting tool produces something meaningful.
        assert fallback.count("the") > 1


class TestOfflineSandboxDependencyHandling:
    """P1/P2 from docs/CHAT_TO_MISSION_FINDINGS_2026-08-12.md.

    A live chat-driven mission produced a PyQt6 desktop app. The manifest emitted
    `pip install PyQt6` into a --network=none container, the install died on DNS,
    the application never started -- and the verdict was PASS, attributed to
    "no invocation could be derived", which was not the reason.
    """

    def test_install_commands_are_never_emitted(self) -> None:
        """A command that cannot succeed should not be generated at all."""
        for language in ("python", "javascript", "typescript", "go"):
            assert testdata_agent._install_commands(language, ["PyQt6", "express"]) == [], (
                f"{language} still emits installs into an offline sandbox"
            )

    def test_third_party_dependencies_are_detected_as_unmet(self) -> None:
        unmet = rqca_agent._unmet_dependencies
        assert unmet("python", ["PyQt6"]) == ["PyQt6"]
        assert unmet("javascript", ["express", "lodash"]) == ["express", "lodash"]
        # A Go import path is external exactly when its first segment is a host.
        assert unmet("go", ["github.com/foo/bar", "fmt"]) == ["github.com/foo/bar"]

    def test_standard_library_dependencies_are_met(self) -> None:
        """Otherwise every artifact would be reported as unrunnable."""
        unmet = rqca_agent._unmet_dependencies
        assert unmet("python", ["os", "sys", "sqlite3", "json"]) == []
        assert unmet("go", ["bufio", "fmt", "unicode/utf8"]) == []
        assert unmet("javascript", ["fs", "path", "node:crypto"]) == []

    def test_unclassifiable_third_party_deps_are_unmet(self) -> None:
        """Executing rust/java with crates/jars against --network=none is a false run."""
        assert rqca_agent._unmet_dependencies("rust", ["serde"]) == ["serde"]
        assert rqca_agent._unmet_dependencies("java", ["org.junit"]) == ["org.junit"]
        assert rqca_agent._unmet_dependencies("rust", ["std"]) == []
        assert rqca_agent._unmet_dependencies("java", ["java.util"]) == []
        assert rqca_agent._unmet_dependencies("zig", ["some-dep"]) == ["some-dep"]

    def test_gui_artifacts_are_recognised_from_deps_or_imports(self) -> None:
        """Running a GUI app headless proves nothing -- it needs a display."""
        gui = rqca_agent._is_gui_artifact
        assert gui(["PyQt6"], "")
        assert gui([], "import sys\nfrom PyQt6.QtWidgets import QApplication")
        assert gui(["tkinter"], "")
        assert not gui(["requests"], "import sys\nprint(1)")

    def test_gui_languages_have_a_dependency_free_syntax_check(self) -> None:
        """The strongest claim honestly available for a GUI artifact.

        `python -m py_compile` proves a PyQt6 app parses without PyQt6 present
        and without a display, where executing it could prove neither.
        """
        commands = rqca_agent._SYNTAX_ONLY_COMMANDS
        assert "ast.parse" in commands["python"], (
            "python must parse without writing: py_compile emits __pycache__ beside "
            "the source and /workspace is read-only, which failed every well-formed "
            "artifact with '[Errno 30] Read-only file system'"
        )
        assert "py_compile" not in commands["python"]
        for language, command in commands.items():
            assert "/workspace/{filename}" in command, language
            assert "install" not in command, f"{language} syntax check tries to install"
            assert "-o /workspace" not in command, f"{language} writes into the workspace"


def test_a_syntax_check_failure_is_never_excused_as_not_exercised() -> None:
    """A parse-or-compile failure is still a defect."""
    verdict, passed, note = rqca_agent._sandbox_verdict(
        exit_matched=False,
        exercised=False,
        syntax_only=True,
        matched_failure_pattern=None,
    )
    assert verdict == "FAIL"
    assert passed is False
    assert note is None


def test_a_syntax_check_success_is_not_a_functional_pass() -> None:
    """Compile-only success is not evidence the artifact works."""
    verdict, passed, note = rqca_agent._sandbox_verdict(
        exit_matched=True,
        exercised=False,
        syntax_only=True,
        matched_failure_pattern=None,
    )
    assert verdict == "DRY_RUN"
    assert passed is False
    assert note is not None


def test_started_only_is_dry_run_not_pass() -> None:
    """A bare launch is not evidence. Promoting it to PASS authorized delivery."""
    for exit_matched in (True, False):
        verdict, passed, note = rqca_agent._sandbox_verdict(
            exit_matched=exit_matched,
            exercised=False,
            syntax_only=False,
            matched_failure_pattern=None,
        )
        assert verdict == "DRY_RUN", exit_matched
        assert passed is False
        assert note is not None


def test_exercised_exit_code_is_the_verdict() -> None:
    assert rqca_agent._sandbox_verdict(
        exit_matched=True, exercised=True, syntax_only=False, matched_failure_pattern=None
    ) == ("PASS", True, None)
    assert rqca_agent._sandbox_verdict(
        exit_matched=False, exercised=True, syntax_only=False, matched_failure_pattern=None
    ) == ("FAIL", False, None)


def test_failure_pattern_wins_over_started_only() -> None:
    verdict, passed, note = rqca_agent._sandbox_verdict(
        exit_matched=True,
        exercised=False,
        syntax_only=False,
        matched_failure_pattern="Syntax::",
    )
    assert verdict == "FAIL"
    assert passed is False
    assert note is None


def test_server_and_library_artifacts_are_classified() -> None:
    classify = rqca_agent._classify_artifact
    assert classify(
        dependencies=["fastapi"],
        generated_code="from fastapi import FastAPI\napp = FastAPI()\n",
    ) == "server"
    assert classify(
        dependencies=[],
        generated_code="const app = express();\napp.listen(3000);\n",
    ) == "server"
    assert classify(
        dependencies=["PyQt6"],
        generated_code="from PyQt6.QtWidgets import QApplication\n",
    ) == "gui"
    assert classify(
        dependencies=[],
        generated_code="def add(a, b):\n    return a + b\n",
        generated_output={"usage_example": "import adder", "output_mode": "LIBRARY"},
    ) == "library"
    assert classify(
        dependencies=[],
        generated_code="if __name__ == '__main__':\n    print(1)\n",
        generated_output={"usage_example": "python main.py input.txt"},
    ) == "cli"
    assert classify(
        dependencies=[],
        generated_code="import msvcrt\nwhile True:\n    if msvcrt.kbhit():\n        pass\n",
        generated_output={"filename": "snake.py", "usage_example": "python snake.py"},
    ) == "interactive"


def test_while_true_cli_is_not_interactive() -> None:
    assert rqca_agent._classify_artifact(
        dependencies=[],
        generated_code=(
            "def main():\n"
            "    while True:\n"
            "        line = input('> ')\n"
            "        if line == 'q':\n"
            "            break\n"
            "        print(line)\n"
        ),
        generated_output={"filename": "repl.py", "usage_example": "python repl.py"},
    ) == "cli"


def test_bare_listen_is_not_a_server() -> None:
    assert rqca_agent._classify_artifact(
        dependencies=[],
        generated_code="emitter.listen('data', handler)\nprint('ok')\n",
        generated_output={"filename": "cli.js", "usage_example": "node cli.js"},
    ) == "cli"


def test_generated_tests_win_over_manifest_run_command() -> None:
    command, tests_selected = rqca_agent._select_sandbox_command(
        filename="snake.py",
        test_filename="test_snake.py",
        language="python",
        settings=SimpleNamespace(rqca_test_command_template=""),
        testdata_manifest={"run_command": "python /workspace/snake.py"},
    )
    assert tests_selected is True
    assert "unittest" in command
    assert "test_snake.py" in command


def test_no_tests_keeps_manifest_run_command() -> None:
    command, tests_selected = rqca_agent._select_sandbox_command(
        filename="snake.py",
        test_filename="",
        language="python",
        settings=SimpleNamespace(rqca_test_command_template=""),
        testdata_manifest={"run_command": "python /workspace/snake.py"},
    )
    assert tests_selected is False
    assert command == "python /workspace/snake.py"


def test_unbalanced_usage_example_derives_nothing() -> None:
    assert rqca_agent._invocation_from_usage_example('python add.py "oops', "add.py") == []


def test_library_and_interactive_kinds_short_circuit() -> None:
    assert rqca_agent._is_library_artifact({"kind": "library"}, "") is True
    assert rqca_agent._is_library_artifact({}, "") is False
    assert rqca_agent._is_interactive_artifact({"artifact_class": "game"}, "") is True


def test_resolve_test_command_unknown_language_returns_none() -> None:
    assert (
        rqca_agent._resolve_test_command(
            filename="Main.hs",
            test_filename="MainSpec.hs",
            language="haskell",
            settings=SimpleNamespace(rqca_test_command_template=""),
        )
        is None
    )


def test_default_run_command_falls_back_to_cat() -> None:
    assert rqca_agent._default_run_command("Main.hs", "haskell") == "cat /workspace/Main.hs"


def test_html_smoke_degrades_when_inline_script_check_is_dry_run() -> None:
    with patch.object(
        rqca_agent,
        "_node_syntax_check",
        new=AsyncMock(
            return_value={
                "verdict": "DRY_RUN",
                "passed": False,
                "execution_type": "node_check_unavailable",
            }
        ),
    ):
        report = asyncio.run(
            rqca_agent._build_artifact_smoke_report(
                code="<!doctype html><html><body><script>const ok = 1;</script></body></html>",
                filename="index.html",
                language="javascript",
                settings=SimpleNamespace(),
            )
        )
    assert report["verdict"] == "DRY_RUN"
    assert report["passed"] is False


def test_run_runtime_qc_docker_unavailable_is_dry_run(monkeypatch) -> None:
    async def _missing(_docker_bin: str = "docker") -> bool:
        return False

    monkeypatch.setattr(rqca_agent, "_check_docker_available", _missing)
    result = asyncio.run(
        rqca_agent.run_runtime_qc(
            mission_id="mission-nodocker",
            generated_output={"filename": "add.py", "generated_code": "print(1)\n"},
            testdata_manifest={},
            integration_tests=None,
            language="python",
            settings=SimpleNamespace(docker_bin="docker"),
        )
    )
    assert result["verdict"] == "DRY_RUN"
    assert "Docker not available" in str(result.get("dry_run_reason") or "")


def test_run_runtime_qc_gui_without_tests_uses_syntax_only(monkeypatch) -> None:
    captured: dict = {}

    async def _present(_docker_bin: str = "docker") -> bool:
        return True

    async def _exec(**kwargs):
        captured.update(kwargs["testdata_manifest"])
        return {"verdict": "DRY_RUN", "passed": False, "execution_type": "docker_live"}

    monkeypatch.setattr(rqca_agent, "_check_docker_available", _present)
    monkeypatch.setattr(rqca_agent, "_execute_in_sandbox", _exec)
    result = asyncio.run(
        rqca_agent.run_runtime_qc(
            mission_id="mission-gui",
            generated_output={
                "filename": "app.py",
                "generated_code": "import pygame\npygame.init()\n",
                "dependencies": ["pygame"],
            },
            testdata_manifest={},
            integration_tests=None,
            language="python",
            settings=SimpleNamespace(docker_bin="docker", rqca_test_command_template=""),
        )
    )
    assert result["verdict"] == "DRY_RUN"
    assert str(captured.get("verified_scope") or "").endswith("syntax-only")


def test_run_runtime_qc_library_without_syntax_template_is_dry_run(monkeypatch) -> None:
    async def _present(_docker_bin: str = "docker") -> bool:
        return True

    monkeypatch.setattr(rqca_agent, "_check_docker_available", _present)
    result = asyncio.run(
        rqca_agent.run_runtime_qc(
            mission_id="mission-lib",
            generated_output={
                "filename": "lib.go",
                "generated_code": "package lib\nfunc Add(a, b int) int { return a + b }\n",
                "artifact_class": "library",
            },
            testdata_manifest={},
            integration_tests=None,
            language="go",
            settings=SimpleNamespace(docker_bin="docker", rqca_test_command_template=""),
        )
    )
    assert result["verdict"] == "DRY_RUN"
    assert "cannot be executed to completion" in str(result.get("dry_run_reason") or "")


def test_run_runtime_qc_unmet_dependency_is_dry_run(monkeypatch) -> None:
    async def _present(_docker_bin: str = "docker") -> bool:
        return True

    monkeypatch.setattr(rqca_agent, "_check_docker_available", _present)
    result = asyncio.run(
        rqca_agent.run_runtime_qc(
            mission_id="mission-deps",
            generated_output={
                "filename": "cli.py",
                "generated_code": "print('ok')\n",
                "dependencies": ["requests"],
            },
            testdata_manifest={},
            integration_tests=None,
            language="python",
            settings=SimpleNamespace(docker_bin="docker"),
        )
    )
    assert result["verdict"] == "DRY_RUN"
    assert "requests" in str(result.get("dry_run_reason") or "")


def test_run_runtime_qc_fills_runtime_and_invocation(monkeypatch) -> None:
    captured: dict = {}

    async def _present(_docker_bin: str = "docker") -> bool:
        return True

    async def _exec(**kwargs):
        captured.update(kwargs["testdata_manifest"])
        return {"verdict": "PASS", "passed": True, "execution_type": "docker_live"}

    monkeypatch.setattr(rqca_agent, "_check_docker_available", _present)
    monkeypatch.setattr(rqca_agent, "_execute_in_sandbox", _exec)
    result = asyncio.run(
        rqca_agent.run_runtime_qc(
            mission_id="mission-fill",
            generated_output={
                "filename": "add.py",
                "generated_code": "import sys\nprint(int(sys.argv[1])+int(sys.argv[2]))\n",
                "usage_example": "python add.py 1 2",
            },
            testdata_manifest={},
            integration_tests={"test_code": "import unittest\n"},
            language="python",
            settings=SimpleNamespace(docker_bin="docker", rqca_test_command_template=""),
        )
    )
    assert result["verdict"] == "PASS"
    assert captured.get("invocation_args") == ["1", "2"]
    assert "base_image" in captured
    assert "run_command" in captured


def test_execute_in_sandbox_pass_and_invalid_limits(monkeypatch) -> None:
    from orchestrator.sandbox_exec import SandboxResult

    async def _run(**_kwargs):
        return SandboxResult(
            exit_code=0,
            stdout="ok\n",
            stderr="",
            timed_out=False,
            timeout_seconds=30,
            memory_limit_mb=256,
            base_image="python:3.11-slim",
        )

    monkeypatch.setattr(rqca_agent, "run_in_sandbox", _run)
    result = asyncio.run(
        rqca_agent._execute_in_sandbox(
            docker_bin="docker",
            mission_id="mission-exec",
            filename="add.py",
            code="print(2)\n",
            test_code="import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
            testdata_manifest={
                "timeout_seconds": "bad",
                "memory_limit_mb": "nope",
                "invocation_args": ["input.txt"],
                "expected_exit_code": 0,
                "failure_patterns": ["boom"],
            },
            language="python",
            settings=SimpleNamespace(rqca_test_command_template=""),
        )
    )
    assert result["verdict"] == "PASS"
    assert result["execution_type"] == "docker_live"
    assert result["exit_code"] == 0


def test_execute_in_sandbox_timeout_is_not_a_fail(monkeypatch) -> None:
    from orchestrator.sandbox_exec import SandboxResult

    async def _run(**_kwargs):
        return SandboxResult(
            exit_code=124,
            stdout="",
            stderr="killed",
            timed_out=True,
            timeout_seconds=30,
            memory_limit_mb=256,
            base_image="python:3.11-slim",
        )

    monkeypatch.setattr(rqca_agent, "run_in_sandbox", _run)
    result = asyncio.run(
        rqca_agent._execute_in_sandbox(
            docker_bin="docker",
            mission_id="mission-to",
            filename="loop.py",
            code="while True: pass\n",
            test_code="",
            testdata_manifest={"run_command": "python /workspace/loop.py"},
            language="python",
            settings=SimpleNamespace(rqca_test_command_template=""),
        )
    )
    assert result["verdict"] == "TIMEOUT"
    assert result["passed"] is False


def test_execute_in_sandbox_multi_container_without_compose_is_dry_run(monkeypatch) -> None:
    monkeypatch.setattr(rqca_agent, "_compose_available", lambda: False)
    result = asyncio.run(
        rqca_agent._execute_in_sandbox(
            docker_bin="docker",
            mission_id="mission-compose",
            filename="app.py",
            code="print(1)\n",
            test_code="",
            testdata_manifest={
                "multi_container": True,
                "services": [{"name": "runner", "image": "python:3.11-slim"}],
                "run_command": "python /workspace/app.py",
            },
            language="python",
            settings=SimpleNamespace(rqca_test_command_template=""),
        )
    )
    assert result["verdict"] == "DRY_RUN"
    assert "compose plugin" in str(result.get("dry_run_reason") or "")


def test_timeout_report_shape() -> None:
    report = rqca_agent._timeout_report(
        mission_id="mission-to",
        language="python",
        filename="loop.py",
        timeout_seconds=30,
        started_at="2026-08-17T00:00:00+00:00",
    )
    assert report["verdict"] == "TIMEOUT"
    assert report["passed"] is False
    assert report["execution_type"] == "docker_live"
