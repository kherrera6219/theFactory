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

    def test_unclassifiable_languages_are_left_alone(self) -> None:
        """Guessing would turn every Rust or Java mission into a DRY_RUN."""
        assert rqca_agent._unmet_dependencies("rust", ["serde"]) == []
        assert rqca_agent._unmet_dependencies("java", ["org.junit"]) == []

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
    """The false PASS that P4 caught, pinned.

    "No invocation was derived" is a reason to withhold judgement on a program
    that might have needed arguments. A parse-or-compile check takes no
    arguments at all, so that reason cannot apply to it -- its exit code is the
    verdict. Without the guard, a live PyQt6 artifact whose `py_compile` reported
    "IndentationError: unexpected indent (line 42)" with exit 1 was recorded as
    PASS: the check found exactly the defect it exists to find, and the verdict
    threw the answer away.
    """
    import inspect

    source = inspect.getsource(rqca_agent)
    assert "syntax_only" in source, "the syntax-only guard is gone"
    # The excusing branch must require `not syntax_only`.
    marker = "if not passed and not exercised and not syntax_only:"
    assert marker in source, (
        "the not-exercised excuse no longer excludes syntax-only runs, so a "
        "compile failure can be recorded as PASS again"
    )
