"""Tests for Phase 6: baseline capture, characterisation tests, preservation gate, & PORT dual-run."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ORCH_ROOT = REPO_ROOT / "services" / "orchestrator"
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

from orchestrator.baseline_verification import (  # noqa: E402
    BASELINE_TESTS_BRANCH,
    _resolve_test_sandbox_image,
    _wrap_workspace_test_command,
    capture_workspace_baseline,
    evaluate_preservation_gate,
    generate_characterisation_suite_files,
    generate_characterisation_tests,
    load_workspace_baseline,
    parse_behaviour_change_allowed,
    parse_junit_xml,
    parse_test_results,
)
from orchestrator.equivalence_execution import run_port_dual_equivalence  # noqa: E402
from orchestrator.mission_flow_v2.phases_delivery import _prepare_equivalence_report  # noqa: E402
from orchestrator.mission_flow_v2.phases_runtime import _prepare_runtime_qc  # noqa: E402
from orchestrator.sandbox_exec import SandboxResult  # noqa: E402
from orchestrator.workspace import MissionWorkspace  # noqa: E402

BENCHMARK_ROOT = REPO_ROOT / "tests" / "benchmark" / "brownfield"


def _sbx(
    *,
    exit_code: int = 0,
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
    infrastructure_error: str | None = None,
    base_image: str = "python:3.11-slim",
) -> SandboxResult:
    return SandboxResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        timeout_seconds=30,
        memory_limit_mb=512,
        base_image=base_image,
        infrastructure_error=infrastructure_error,
        duration_ms=12.5,
    )


def test_parsers_junit_tap_go_node_phpunit_and_policy() -> None:
    """Verify multi-ecosystem test output and JUnit XML parsers + policy extraction."""
    junit = """
    <testsuite tests="3" failures="1" errors="0" skipped="1">
      <testcase classname="pkg.MathTest" name="testAdd"/>
      <testcase classname="pkg.MathTest" name="testSub"><failure message="bad"/></testcase>
      <testcase classname="pkg.MathTest" name="testSkip"><skipped/></testcase>
    </testsuite>
    """
    j = parse_junit_xml(junit)
    assert j["passed"] == ["pkg.MathTest::testAdd"]
    assert j["failed"] == ["pkg.MathTest::testSub"]
    assert j["skipped"] == ["pkg.MathTest::testSkip"]
    assert parse_junit_xml("not xml") == {"passed": [], "failed": [], "skipped": []}
    assert parse_test_results(command="pytest", exit_code=1, stdout="", stderr="", junit_xml=junit)["failed"] == [
        "pkg.MathTest::testSub"
    ]

    go_res = parse_test_results(
        command="go test ./...",
        exit_code=1,
        stdout="--- PASS: TestOk (0.00s)\n--- FAIL: TestBad (0.00s)\n--- SKIP: TestLater (0.00s)\n",
        stderr="",
    )
    assert go_res == {"passed": ["TestOk"], "failed": ["TestBad"], "skipped": ["TestLater"]}

    tap_res = parse_test_results(
        command="node --test",
        exit_code=1,
        stdout="ok 1 - passes\nnot ok 2 - regresses\nok 3 - opt # SKIP\n",
        stderr="",
    )
    assert tap_res["passed"] == ["passes"]
    assert tap_res["failed"] == ["regresses"]
    assert tap_res["skipped"] == ["opt # SKIP"]

    node_check_res = parse_test_results(
        command="node --test",
        exit_code=1,
        stdout="  ✔ renders html (2ms)\n  ✖ crashes on null (1ms)\n",
        stderr="",
    )
    assert node_check_res["passed"] == ["renders html"]
    assert node_check_res["failed"] == ["crashes on null"]

    phpunit_res = parse_test_results(
        command="vendor/bin/phpunit",
        exit_code=1,
        stdout="1) UserTest::testAuth\nTests: 2, Assertions: 2, Failures: 1.",
        stderr="",
    )
    assert phpunit_res["failed"] == ["UserTest::testAuth"]

    maven_summary = parse_test_results(
        command="mvn test",
        exit_code=1,
        stdout="Tests run: 4, Failures: 1, Errors: 0",
        stderr="",
    )
    assert maven_summary["failed"] == ["suite:mvn test"]

    assert parse_behaviour_change_allowed(
        "behaviour_change_allowed:test_a, test_b",
        ["test_c", "test_a"],
    ) == ["test_c", "test_a", "test_b"]


@pytest.mark.asyncio
async def test_baseline_capture_benchmark_corpus_and_pre_existing_failures(tmp_path: Path) -> None:
    """Capture baseline across benchmark repos, recording pre-existing failures honestly."""
    ws_py = MissionWorkspace.create_from_local(
        BENCHMARK_ROOT / "flask_legacy_py",
        workspace_id="ws-flask-base",
        root=tmp_path,
    )
    dep_cache = tmp_path / "dep-cache"
    dep_cache.mkdir()

    async def _fake_flask_runner(**kwargs: Any) -> SandboxResult:
        assert kwargs.get("deps_dir") == dep_cache
        assert kwargs.get("env_vars", {}).get("PIP_NO_INDEX") == "1"
        return _sbx(
            exit_code=0,
            stdout="test_app.py::test_health PASSED\ntest_app.py::test_sum PASSED\n",
        )

    baseline = await capture_workspace_baseline(
        ws_py,
        deps_dir=dep_cache,
        sandbox_runner=_fake_flask_runner,
    )
    assert baseline["status"] == "captured"
    assert baseline["passed"] == ["test_app.py::test_health", "test_app.py::test_sum"]
    assert baseline["pre_existing_failures"] == []
    assert load_workspace_baseline(ws_py) == baseline
    assert ws_py.diff("baseline") == ""  # .thefactory/baseline.json never pollutes git diff

    # Pre-existing failure (e.g. c_buffer_lib deliberate off-by-one) is recorded, never blamed onFactory.
    ws_c = MissionWorkspace.create_from_local(
        BENCHMARK_ROOT / "c_buffer_lib",
        workspace_id="ws-c-base",
        root=tmp_path,
    )

    async def _fake_c_runner(**kwargs: Any) -> SandboxResult:
        return _sbx(exit_code=1, stdout="not ok 1 - test_append_overflow\n", stderr="")

    c_base = await capture_workspace_baseline(ws_c, sandbox_runner=_fake_c_runner)
    assert c_base["status"] == "captured"
    assert c_base["pre_existing_failures"] == ["test_append_overflow"]

    # Infrastructure error or timeout renders UNVERIFIABLE, never captured PASS.
    async def _infra_fail_runner(**kwargs: Any) -> SandboxResult:
        return _sbx(exit_code=-1, infrastructure_error="docker daemon down")

    unver = await capture_workspace_baseline(ws_py, sandbox_runner=_infra_fail_runner)
    assert unver["status"] == "unverifiable"
    assert "docker daemon down" in unver["reason"]

    # Workspace without tests captures explicit status="no_tests".
    ws_notest = MissionWorkspace.create_from_files(
        {"notes.txt": "hello world\n"},
        workspace_id="ws-notest",
        root=tmp_path,
    )
    no_test_base = await capture_workspace_baseline(ws_notest, sandbox_runner=_fake_flask_runner)
    assert no_test_base["status"] == "no_tests"


@pytest.mark.asyncio
async def test_characterisation_tests_keep_only_baseline_passing_and_commit(tmp_path: Path) -> None:
    """Characterisation generation keeps only baseline-passing tests and commits to branch."""
    ws = MissionWorkspace.create_from_files(
        {"billing.py": "def compute_total(a: int = 1, b: int = 2) -> int:\n    return a + b\n"},
        workspace_id="ws-char",
        root=tmp_path,
    )
    suite_files = generate_characterisation_suite_files(ws, language="python")
    assert "tests/test_characterisation_baseline.py" in suite_files

    ws_js = MissionWorkspace.create_from_files(
        {"index.js": "export function hi() { return 'hi'; }\n"},
        workspace_id="ws-char-js",
        root=tmp_path,
    )
    js_suite = generate_characterisation_suite_files(ws_js, language="javascript")
    assert "tests/characterisation_baseline.test.mjs" in js_suite

    baseline = await capture_workspace_baseline(ws, test_command="")
    candidate = {
        "tests/test_characterisation_baseline.py": (
            "from billing import compute_total\n\n"
            "def test_char_ok():\n"
            "    assert compute_total() == 3\n\n"
            "def test_char_wrong_hypothesis():\n"
            "    assert compute_total() == 999\n"
        )
    }

    async def _char_runner(**kwargs: Any) -> SandboxResult:
        assert Path(kwargs["workspace_dir"], "tests", "test_characterisation_baseline.py").exists()
        return _sbx(
            exit_code=1,
            stdout=(
                "tests/test_characterisation_baseline.py::test_char_ok PASSED\n"
                "tests/test_characterisation_baseline.py::test_char_wrong_hypothesis FAILED\n"
            ),
        )

    updated = await generate_characterisation_tests(
        ws,
        baseline=baseline,
        candidate_files=candidate,
        sandbox_runner=_char_runner,
    )
    assert updated["characterisation_status"] == "committed"
    assert updated["characterisation_tests"] == ["tests/test_characterisation_baseline.py::test_char_ok"]
    assert updated["baseline_tests_branch"] == BASELINE_TESTS_BRANCH
    committed_body = ws.read_file("tests/test_characterisation_baseline.py")
    assert "test_char_ok" in committed_body
    assert "test_char_wrong_hypothesis" not in committed_body


@pytest.mark.asyncio
async def test_preservation_gate_verdicts_preserved_regressed_allowed_and_unverifiable(
    tmp_path: Path,
) -> None:
    """Preservation gate returns PRESERVED, REGRESSED, allowed-change PRESERVED, and UNVERIFIABLE."""
    ws = MissionWorkspace.create_from_files(
        {
            "calc.py": "def add(a, b):\n    return a + b\n",
            "test_calc.py": "def test_add():\n    assert True\n",
        },
        workspace_id="ws-pres",
        root=tmp_path,
    )
    baseline = await capture_workspace_baseline(
        ws,
        sandbox_runner=lambda **kw: _async_val(
            _sbx(exit_code=0, stdout="test_calc.py::test_add PASSED\n")
        ),
    )

    # 1. Clean edit -> PRESERVED
    preserved = await evaluate_preservation_gate(
        ws,
        baseline=baseline,
        enforcement_enabled=True,
        sandbox_runner=lambda **kw: _async_val(
            _sbx(exit_code=0, stdout="test_calc.py::test_add PASSED\n")
        ),
    )
    assert preserved["verdict"] == "PRESERVED"
    assert preserved["blocking"] is False

    # 2. Injected regression -> REGRESSED + blocking under enforcement
    regressed = await evaluate_preservation_gate(
        ws,
        baseline=baseline,
        enforcement_enabled=True,
        sandbox_runner=lambda **kw: _async_val(
            _sbx(exit_code=1, stdout="test_calc.py::test_add FAILED\n")
        ),
    )
    assert regressed["verdict"] == "REGRESSED"
    assert regressed["blocking"] is True
    assert regressed["regressed_tests"] == ["test_calc.py::test_add"]

    # 3. Same test listed in behaviour_change_allowed -> PRESERVED
    allowed = await evaluate_preservation_gate(
        ws,
        baseline=baseline,
        baseline_policy="behaviour_change_allowed:test_add",
        enforcement_enabled=True,
        sandbox_runner=lambda **kw: _async_val(
            _sbx(exit_code=1, stdout="test_calc.py::test_add FAILED\n")
        ),
    )
    assert allowed["verdict"] == "PRESERVED"
    assert allowed["blocking"] is False
    assert allowed["allowed_changes"] == ["test_add"]

    # 4. Sandbox infra error or timeout -> UNVERIFIABLE (never PASS/PRESERVED)
    unverifiable = await evaluate_preservation_gate(
        ws,
        baseline=baseline,
        enforcement_enabled=True,
        sandbox_runner=lambda **kw: _async_val(_sbx(exit_code=-1, timed_out=True)),
    )
    assert unverifiable["verdict"] == "UNVERIFIABLE"
    assert unverifiable["blocking"] is True
    assert "timed out" in unverifiable["reason"]


@pytest.mark.asyncio
async def test_port_dual_run_equivalence_pass_and_mismatch() -> None:
    """PORT dual-run compares source & target outputs across CLI & call vectors."""
    cli_vectors = [
        {"id": "v1", "kind": "cli", "argv": ["--sum", "2", "3"]},
        {"id": "v2", "kind": "cli", "argv": ["--upper", "hi"], "stdin": "hello"},
    ]

    async def _matching_runner(**kwargs: Any) -> SandboxResult:
        cmd = str(kwargs["command"])
        if "--sum" in cmd:
            return _sbx(exit_code=0, stdout="5\n")
        return _sbx(exit_code=0, stdout="HI\n")

    passed = await run_port_dual_equivalence(
        mission_id="mission-port-ok",
        source_language="python",
        source_filename="cli.py",
        source_code="print(5)\n",
        target_language="go",
        target_filename="main.go",
        target_code="package main\nfunc main() {}\n",
        vectors=cli_vectors,
        sandbox_runner=_matching_runner,
    )
    assert passed["status"] == "passed"
    assert passed["verification_basis"] == "port_dual_run"
    assert passed["pass_ratio"] == 1.0
    assert passed["equivalence_vectors_passed"] == 2

    # Deliberately broken Go port returns wrong stdout & exit_code on v1 -> failed with both shown.
    async def _mismatch_runner(**kwargs: Any) -> SandboxResult:
        ws_dir = Path(kwargs["workspace_dir"])
        if (ws_dir / "main.go").exists():
            return _sbx(exit_code=1, stdout="99\n")
        return _sbx(exit_code=0, stdout="5\n")

    failed = await run_port_dual_equivalence(
        mission_id="mission-port-bad",
        source_language="python",
        source_filename="cli.py",
        source_code="print(5)\n",
        target_language="go",
        target_filename="main.go",
        target_code="package main\nfunc main() {}\n",
        vectors=[cli_vectors[0]],
        sandbox_runner=_mismatch_runner,
    )
    assert failed["status"] == "failed"
    assert failed["pass_ratio"] == 0.0
    vec = failed["vector_results"][0]
    assert vec["source_output"].strip() == "5"
    assert vec["target_output"].strip() == "99"
    assert vec["source_exit_code"] == 0
    assert vec["target_exit_code"] == 1
    assert "exit_code 0 != 1" in vec["mismatch_reason"]

    # Call vector dual-run (Python -> Node)
    async def _call_runner(**kwargs: Any) -> SandboxResult:
        return _sbx(exit_code=0, stdout='__EQV__{"status": "ok", "result": 42}\n')

    call_ok = await run_port_dual_equivalence(
        mission_id="mission-port-call",
        source_language="python",
        source_filename="calc.py",
        source_code="def compute(x): return x\n",
        target_language="javascript",
        target_filename="calc.mjs",
        target_code="export function compute(x) { return x; }\n",
        vectors=[{"id": "c1", "kind": "call", "fn_name": "compute", "args": [42]}],
        sandbox_runner=_call_runner,
    )
    assert call_ok["status"] == "passed"


@pytest.mark.asyncio
async def test_runtime_qc_and_delivery_wire_preservation_gate_and_port_dual_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """End-to-end wiring: REGRESSED blocks COMPLETE on failure and triggers surgical repair."""
    ws = MissionWorkspace.create_from_files(
        {
            "app.py": "def val():\n    return 1\n",
            "test_app.py": "def test_val():\n    assert True\n",
        },
        workspace_id="ws-wiring",
        root=tmp_path,
    )
    ws.branch("mission-p6-wire")
    baseline = {
        "schema_version": "baseline.v1",
        "workspace_id": "ws-wiring",
        "commit": ws.base_commit,
        "command": "python -m pytest -q test_app.py",
        "language": "python",
        "status": "captured",
        "passed": ["test_app.py::test_val"],
        "failed": [],
        "pre_existing_failures": [],
    }

    stored_metadata: dict[str, Any] = {}

    class _FakeStorage:
        def update_mission_metadata(self, settings: Any, mission_id: str, metadata: dict[str, Any]) -> Any:
            stored_metadata[mission_id] = json.loads(json.dumps(metadata))
            return SimpleNamespace(
                mission_id=mission_id,
                requested_target_language="python",
                metadata=metadata,
                state="verified",
                prompt="Fix app",
                title="Fix app",
                mission_type="IMPORT_MODERNIZE",
                depth_mode="STANDARD",
                output_mode="FULL_BUILD",
            )

        def insert_runtime_qc_report(self, *args: Any, **kwargs: Any) -> None:
            return None

        def insert_testdata_manifest(self, *args: Any, **kwargs: Any) -> None:
            return None

        def list_build_artifacts(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
            return []

    async def _noop_audit(*args: Any, **kwargs: Any) -> None:
        return None

    import orchestrator.mission_flow_v2 as pkg

    monkeypatch.setattr(pkg, "storage", _FakeStorage(), raising=False)
    monkeypatch.setattr(pkg, "record_audit_event", _noop_audit, raising=False)

    # First preservation check returns REGRESSED -> triggers surgical repair -> second check returns PRESERVED.
    pres_calls = {"count": 0}

    async def _fake_run_in_sandbox(**kwargs: Any) -> SandboxResult:
        pres_calls["count"] += 1
        if pres_calls["count"] == 1:
            return _sbx(exit_code=1, stdout="test_app.py::test_val FAILED\n")
        return _sbx(exit_code=0, stdout="test_app.py::test_val PASSED\n")

    async def _fake_qc(**kwargs: Any) -> dict[str, Any]:
        return {
            "schema_version": "runtime_qc_report.v1",
            "verdict": "PASS",
            "exit_code": 0,
            "stdout_preview": "ok",
            "stderr_preview": "",
            "execution_type": "real_execution",
            "source": "sandbox",
        }

    async def _fake_assess(**kwargs: Any) -> dict[str, Any]:
        return {"qc_verdict": "PASS", "deployment_safe": True}

    async def _fake_repair(**kwargs: Any) -> dict[str, Any]:
        return {
            "generated_code": "## FILE app.py\ndef val():\n    return 1\n",
            "filename": "app.py",
            "language": "python",
            "source": "llm",
        }

    monkeypatch.setattr("orchestrator.baseline_verification.run_in_sandbox", _fake_run_in_sandbox)
    monkeypatch.setattr("orchestrator.mission_flow_v2.phases_runtime.run_runtime_qc", _fake_qc)
    monkeypatch.setattr("orchestrator.mission_flow_v2.phases_runtime.generate_rqca_assessment", _fake_assess)
    monkeypatch.setattr(pkg, "generate_code_from_contract", _fake_repair, raising=False)

    settings = SimpleNamespace(
        workspace_root=str(tmp_path),
        rqca_agent_enabled=True,
        rqca_enforcement_enabled=True,
        testdata_agent_enabled=False,
        runtime_qc_max_repair_attempts=1,
    )
    mission = SimpleNamespace(
        mission_id="mission-p6-wire",
        requested_target_language="python",
        state="verified",
        prompt="Update app.py",
        title="Update app.py",
        mission_type="IMPORT_MODERNIZE",
        depth_mode="STANDARD",
        output_mode="FULL_BUILD",
        metadata={
            "workspace": {"workspace_id": "ws-wiring", "branch": "thefactory/mission-mission-p6-wire"},
            "baseline": baseline,
            "feature_contract": {"baseline_policy": "must_pass_existing_tests"},
            "mission_contract": {"summary": "Update"},
            "integration_tests": {"test_filename": "test_app.py", "test_cases": ["test_val"]},
            "testdata_manifest": {"base_image": "python:3.11-slim", "timeout_seconds": 30},
            "generated_output": {
                "generated_code": "## FILE app.py\ndef val():\n    return 999\n",
                "filename": "app.py",
                "language": "python",
                "source": "llm",
            },
        },
    )

    updated, ready, report = await _prepare_runtime_qc(app=SimpleNamespace(), settings=settings, mission=mission)
    assert ready is True
    assert report["preservation_report"]["verdict"] == "PRESERVED"
    assert stored_metadata["mission-p6-wire"]["preservation_report"]["verdict"] == "PRESERVED"

    # Now make preservation stay REGRESSED when repair returns fallback -> must block COMPLETE!
    async def _always_regressed(**kwargs: Any) -> SandboxResult:
        return _sbx(exit_code=1, stdout="test_app.py::test_val FAILED\n")

    async def _no_repair(**kwargs: Any) -> dict[str, Any]:
        return {"generated_code": "", "source": "fallback"}

    monkeypatch.setattr("orchestrator.baseline_verification.run_in_sandbox", _always_regressed)
    monkeypatch.setattr(pkg, "generate_code_from_contract", _no_repair, raising=False)
    mission_blocked = SimpleNamespace(
        mission_id="mission-p6-block",
        requested_target_language="python",
        state="verified",
        prompt="Update app.py",
        title="Update app.py",
        mission_type="IMPORT_MODERNIZE",
        depth_mode="STANDARD",
        output_mode="FULL_BUILD",
        metadata={
            "workspace": {"workspace_id": "ws-wiring", "branch": "thefactory/mission-mission-p6-block"},
            "baseline": baseline,
            "feature_contract": {"baseline_policy": "must_pass_existing_tests"},
            "mission_contract": {"summary": "Update"},
            "integration_tests": {"test_filename": "test_app.py", "test_cases": ["test_val"]},
            "testdata_manifest": {"base_image": "python:3.11-slim", "timeout_seconds": 30},
            "generated_output": {
                "generated_code": "## FILE app.py\ndef val():\n    return 999\n",
                "filename": "app.py",
                "language": "python",
                "source": "llm",
            },
        },
    )
    _, blocked_ready, blocked_report = await _prepare_runtime_qc(
        app=SimpleNamespace(), settings=settings, mission=mission_blocked
    )
    assert blocked_ready is False
    assert blocked_report["preservation_report"]["verdict"] == "REGRESSED"

    # Delivery PORT dual-run wiring.
    monkeypatch.setattr("orchestrator.equivalence_execution.check_docker_available", lambda *a: _async_val(True))
    monkeypatch.setattr(
        "orchestrator.equivalence_execution.run_in_sandbox",
        lambda **kw: _async_val(_sbx(exit_code=0, stdout="5\n")),
    )
    port_mission = SimpleNamespace(
        mission_id="mission-p6-port",
        requested_target_language="go",
        state="verified",
        prompt="Port to Go",
        title="Port to Go",
        mission_type="PORT",
        metadata={
            "mission_type": "PORT",
            "port_source_language": "python",
            "port_source_filename": "cli.py",
            "port_target_language": "go",
            "source_code": "print(5)\n",
            "port_dual_vectors": [{"id": "v1", "kind": "cli", "argv": ["5"]}],
            "generated_output": {
                "generated_code": "package main\nimport \"fmt\"\nfunc main(){ fmt.Println(5) }\n",
                "filename": "main.go",
                "language": "go",
                "source": "llm",
            },
        },
    )
    _, eq_ready, eq_report = await _prepare_equivalence_report(
        app=SimpleNamespace(),
        settings=SimpleNamespace(workspace_root=str(tmp_path)),
        mission=port_mission,
    )
    assert eq_ready is True
    assert eq_report["behavioural"]["verification_basis"] == "port_dual_run"
    assert eq_report["behavioural"]["status"] == "passed"


async def _async_val(value: Any) -> Any:
    return value


@pytest.mark.asyncio
async def test_phase6_edge_cases_and_ecosystem_coverage(tmp_path: Path) -> None:
    """Cover image resolution, malformed/missing baselines, characterisation errors, & dual-run edge cases."""
    assert "php" in _resolve_test_sandbox_image("php", "vendor/bin/phpunit")
    assert "java" in _resolve_test_sandbox_image("java", "mvn test")
    assert "csharp" in _resolve_test_sandbox_image("csharp", "dotnet test")
    assert "golang" in _resolve_test_sandbox_image("go", "go test ./...")
    assert "rust" in _resolve_test_sandbox_image("rust", "cargo test")
    assert "node" in _resolve_test_sandbox_image("javascript", "npm test")
    assert "gcc" in _resolve_test_sandbox_image("c", "make test")
    assert "python" in _resolve_test_sandbox_image("unknownlang", "custom test")

    assert "pytest" in _wrap_workspace_test_command(
        "python -m pytest",
        language="python",
        characterisation_files=["tests/test_char.py"],
    )
    assert "node --test" in _wrap_workspace_test_command(
        "npm test",
        language="javascript",
        characterisation_files=["tests/char.test.mjs"],
    )

    ws = MissionWorkspace.create_from_files(
        {
            "broken.py": "def broken(:\n    pass\n",
            "app.py": "def run():\n    return 1\n",
        },
        workspace_id="ws-edge-p6",
        root=tmp_path,
    )
    assert load_workspace_baseline(ws) is None
    thef = Path(ws.workspace_dir) / ".thefactory"
    thef.mkdir(parents=True, exist_ok=True)
    (thef / "baseline.json").write_text("{corrupt", encoding="utf-8")
    assert load_workspace_baseline(ws) is None

    assert generate_characterisation_suite_files(ws, target_files=["broken.py", "app.py"], language="python")
    assert generate_characterisation_suite_files(ws, language="go") == {}

    empty_base = await capture_workspace_baseline(ws, test_command="")
    assert empty_base["status"] == "captured" or empty_base["status"] in {"no_tests", "unverifiable"}

    # Unverifiable characterisation & no_passing_tests branches
    unver_char = await generate_characterisation_tests(
        ws,
        baseline=empty_base,
        candidate_files={"tests/test_c.py": "def test_one():\n    assert False\n"},
        sandbox_runner=lambda **kw: _async_val(_sbx(exit_code=-1, infrastructure_error="no docker")),
    )
    assert unver_char["characterisation_status"] == "unverifiable"

    none_pass = await generate_characterisation_tests(
        ws,
        baseline=empty_base,
        candidate_files={"tests/test_c.py": "def test_one():\n    assert False\n"},
        sandbox_runner=lambda **kw: _async_val(_sbx(exit_code=1, stdout="tests/test_c.py::test_one FAILED\n")),
    )
    assert none_pass["characterisation_status"] == "no_passing_tests"

    # Preservation gate when baseline itself is unverifiable or missing test command
    unver_gate = await evaluate_preservation_gate(
        ws,
        baseline={"status": "unverifiable", "reason": "no sandbox", "passed": [], "failed": []},
        enforcement_enabled=True,
    )
    assert unver_gate["verdict"] == "UNVERIFIABLE"
    assert unver_gate["blocking"] is True

    no_cmd_gate = await evaluate_preservation_gate(
        ws,
        baseline={"status": "no_tests", "command": "", "passed": [], "failed": []},
        enforcement_enabled=False,
    )
    assert no_cmd_gate["verdict"] == "UNVERIFIABLE"

    # Non-pre-existing new failure without prior per-test name -> REGRESSED
    new_fail_gate = await evaluate_preservation_gate(
        ws,
        baseline={"status": "captured", "command": "pytest", "language": "python", "passed": [], "failed": []},
        sandbox_runner=lambda **kw: _async_val(_sbx(exit_code=1, stdout="test_new.py::test_x FAILED\n")),
    )
    assert new_fail_gate["verdict"] == "REGRESSED"

    # PORT dual-run edge cases: no vectors, missing runtime, call on non-call language, infra error, exception
    assert (
        await run_port_dual_equivalence(
            mission_id="m",
            source_language="python",
            source_filename="a.py",
            source_code="x=1",
            target_language="go",
            target_filename="a.go",
            target_code="package main",
            vectors=[],
            sandbox_runner=lambda **kw: _async_val(_sbx()),
        )
    )["status"] == "skipped"
    assert (
        await run_port_dual_equivalence(
            mission_id="m",
            source_language="brainfuck",
            source_filename="a.bf",
            source_code=".",
            target_language="go",
            target_filename="a.go",
            target_code="package main",
            vectors=[{"id": "v1", "kind": "cli", "argv": []}],
            sandbox_runner=lambda **kw: _async_val(_sbx()),
        )
    )["status"] == "skipped"

    async def _flaky_dual(**kwargs: Any) -> SandboxResult:
        cmd = str(kwargs["command"])
        if "--boom" in cmd:
            raise RuntimeError("boom")
        return _sbx(exit_code=0, stdout="", infrastructure_error="sandbox offline")

    edge_dual = await run_port_dual_equivalence(
        mission_id="m",
        source_language="zig",
        source_filename="a.zig",
        source_code="const std = @import(\"std\");",
        target_language="go",
        target_filename="a.go",
        target_code="package main",
        source_siblings={"helper.zig": "// helper"},
        target_siblings={"helper.go": "package main"},
        vectors=[
            {"id": "c-skip", "kind": "call", "fn_name": "f", "args": []},
            {"id": "v-infra", "kind": "cli", "argv": ["ok"]},
            {"id": "v-exc", "kind": "cli", "argv": ["--boom"]},
        ],
        sandbox_runner=_flaky_dual,
    )
    assert edge_dual["status"] == "skipped"
    assert edge_dual["equivalence_vectors_skipped"] == 3

