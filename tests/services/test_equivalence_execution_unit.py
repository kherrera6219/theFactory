"""Phase 5 (UPG-50..53) — behavioural equivalence verification.

The security tests here are the important ones. Executing untrusted generated
code is rated the highest-impact risk in the upgrade plan, and the named failure
mode is *a second, less-hardened execution path*. These tests assert that one
hardened invocation is shared, that every security flag is present, and that a
regression which silently drops one is caught mechanically rather than by
someone reading the diff.

None of these require a Docker daemon: `build_sandbox_args` is deliberately
separable from `run_in_sandbox` for exactly this reason.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from orchestrator import sandbox_exec  # noqa: E402
from orchestrator.equivalence_execution import (  # noqa: E402
    SUPPORTED_LANGUAGES,
    _build_driver,
    _classify,
    _parse_driver_output,
    collect_executable_vectors,
    run_behavioural_equivalence,
)
from orchestrator.equivalence_verifier import attach_behavioural_report  # noqa: E402

# --- UPG-50: the sandbox is shared and hardened ----------------------------


def test_every_security_flag_is_present_in_the_invocation() -> None:
    """A dropped flag must fail a test, not merely look wrong in a diff."""
    args = sandbox_exec.build_sandbox_args(
        docker_bin="docker",
        workspace_dir="/tmp/ws",
        base_image="python:3.11-slim",
        command="python x.py",
        timeout_seconds=10,
        memory_mb=128,
    )
    for flag in (
        "--network=none",
        "--memory-swap=0",
        "--cpus=1",
        "--read-only",
        "--security-opt=no-new-privileges:true",
        "--cap-drop=ALL",
    ):
        assert flag in args, f"sandbox lost its {flag} hardening"
    assert "--rm" in args


def test_tmpfs_is_size_capped_and_executable() -> None:
    """/tmp must stay capped, and must stay executable.

    Asserted by property rather than as one literal string, because the two
    requirements pull in opposite directions and a future edit is likely to drop
    one while "tightening" the other. ``size=`` bounds a runaway sample; ``exec``
    is what makes compiled languages possible at all -- Docker mounts tmpfs
    noexec by default, and with /workspace read-only there is nowhere else a
    compiler can write a binary and then run it. Dropping ``exec`` silently
    reverts every C/C++/Rust run to "/tmp/a.out: Permission denied".
    """
    args = sandbox_exec.build_sandbox_args(
        docker_bin="docker",
        workspace_dir="/tmp/ws",
        base_image="gcc:13-bookworm",
        command="true",
        timeout_seconds=10,
        memory_mb=128,
    )
    tmpfs = [a for a in args if a.startswith("--tmpfs=/tmp:")]
    assert tmpfs, "sandbox lost its /tmp tmpfs entirely"
    options = tmpfs[0].split(":", 1)[1].split(",")
    assert any(option.startswith("size=") for option in options), (
        f"/tmp tmpfs is no longer size-capped: {tmpfs[0]}"
    )
    assert "exec" in options, (
        f"/tmp lost exec, so no compiled language can run: {tmpfs[0]}"
    )


def test_workspace_is_mounted_read_only() -> None:
    """Generated code must not be able to rewrite the artifact being judged."""
    args = sandbox_exec.build_sandbox_args(
        docker_bin="docker",
        workspace_dir="/tmp/ws",
        base_image="python:3.11-slim",
        command="true",
        timeout_seconds=10,
        memory_mb=128,
    )
    mounts = [a for a in args if a.startswith("--volume=")]
    assert mounts, "workspace is not mounted at all"
    for mount in mounts:
        assert mount.endswith(":ro"), f"workspace mount is writable: {mount}"


def test_rqca_and_equivalence_share_one_execution_path() -> None:
    """The plan's named risk: a second, less-hardened executor.

    Both callers must route through `sandbox_exec.run_in_sandbox`, and neither
    may assemble its own `docker run` command line.
    """
    from orchestrator import equivalence_execution, rqca_agent

    assert rqca_agent.run_in_sandbox is sandbox_exec.run_in_sandbox
    assert equivalence_execution.run_in_sandbox is sandbox_exec.run_in_sandbox

    for module in (rqca_agent, equivalence_execution):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert '"--network=none"' not in source, (
            f"{module.__name__} builds its own docker invocation — the hardened "
            "flags must come only from sandbox_exec"
        )


def test_resource_limits_are_clamped_not_trusted() -> None:
    """A caller may request less than the ceiling, never more."""
    assert sandbox_exec.clamp_timeout(99_999) == sandbox_exec.MAX_TIMEOUT_SECONDS
    assert sandbox_exec.clamp_memory_mb(99_999) == sandbox_exec.MAX_MEMORY_MB
    assert sandbox_exec.clamp_timeout(5) == 5
    assert sandbox_exec.clamp_memory_mb(128) == 128
    # Garbage falls back to the default rather than to "unlimited".
    assert sandbox_exec.clamp_timeout(None) == 30
    assert sandbox_exec.clamp_timeout("nonsense") == 30  # type: ignore[arg-type]
    assert sandbox_exec.clamp_memory_mb(0) == sandbox_exec.MIN_MEMORY_MB


def test_memory_limit_is_applied_from_the_clamped_value() -> None:
    args = sandbox_exec.build_sandbox_args(
        docker_bin="docker",
        workspace_dir="/tmp/ws",
        base_image="img",
        command="true",
        timeout_seconds=10,
        memory_mb=99_999,
    )
    assert f"--memory={sandbox_exec.MAX_MEMORY_MB}m" in args


# --- UPG-51: driver construction is injection-safe -------------------------


def test_driver_does_not_interpolate_arguments_into_source() -> None:
    """A hostile argument value must not become executable code."""
    hostile = {"a": '"; import os; os.system("id"); "'}
    driver = _build_driver(artifact_filename="art.py", fn_name="f", args=hostile)
    assert "os.system" not in driver.replace(json.dumps(json.dumps(hostile)), "")
    # The values arrive via json.loads of a single encoded literal.
    assert "json.loads(" in driver
    parsed_literal = json.loads(json.dumps(json.dumps(hostile)))
    assert json.loads(parsed_literal) == hostile


def test_driver_output_is_read_only_from_the_sentinel_line() -> None:
    """The artifact may print anything; only the sentinel verdict is trusted."""
    noisy = 'hello\n{"status": "ok", "result": 999}\n__EQV__{"status": "ok", "result": 4}\n'
    assert _parse_driver_output(noisy) == {"status": "ok", "result": 4}
    assert _parse_driver_output("no verdict here")["status"] == "no_output"
    assert _parse_driver_output("__EQV__not-json")["status"] == "unparseable"


# --- UPG-52: honest counting ----------------------------------------------


def test_running_without_error_is_not_counted_as_passed() -> None:
    """The core honesty rule of this phase.

    Phase 4 leaves `expected` null on purpose. Counting "it ran" as equivalence
    would recreate the check that can never fail.
    """
    vector = {"fn_name": "f", "case": "nominal", "expected": None}
    outcome, _ = _classify(vector, {"status": "ok", "result": 4})
    assert outcome == "executed_without_error"
    assert outcome != "passed"


def test_matching_a_recorded_expectation_passes() -> None:
    vector = {"fn_name": "f", "case": "nominal", "expected": 4}
    assert _classify(vector, {"status": "ok", "result": 4})[0] == "passed"


def test_mismatching_a_recorded_expectation_fails() -> None:
    """Criterion 3: the gate must actually be able to fail."""
    vector = {"fn_name": "f", "case": "nominal", "expected": 4}
    outcome, message = _classify(vector, {"status": "ok", "result": 5})
    assert outcome == "failed"
    assert "expected 4" in message and "got 5" in message


def test_a_raising_artifact_is_a_failure() -> None:
    vector = {"fn_name": "f", "case": "boundary_low", "expected": None}
    outcome, message = _classify(vector, {"status": "raised", "error": "ZeroDivisionError: x"})
    assert outcome == "failed"
    assert "ZeroDivisionError" in message


def test_a_missing_function_is_skipped_not_failed() -> None:
    """Absence of the function is a projection mismatch, not misbehaviour."""
    vector = {"fn_name": "f", "case": "nominal", "expected": None}
    assert _classify(vector, {"status": "missing_function"})[0] == "skipped"


# --- Vector collection -----------------------------------------------------


def _rir(**overrides):
    fn = {
        "fn_id": "n1",
        "name": "add",
        "projection_method": "ast_v1",
        "tests": {
            "equivalence_vectors": [
                {
                    "in": {"case": "nominal", "args": {"arg0": 1, "arg1": 2}},
                    "out": {"expected": None, "executable": True},
                }
            ]
        },
    }
    fn.update(overrides)
    return {"fns": [fn]}


def test_only_executable_vectors_are_collected() -> None:
    assert len(collect_executable_vectors(_rir())) == 1

    non_exec = _rir()
    non_exec["fns"][0]["tests"]["equivalence_vectors"][0]["out"]["executable"] = False
    assert collect_executable_vectors(non_exec) == []


def test_templated_functions_are_never_executed() -> None:
    """A templated projection has no real signature, so there is nothing to
    invoke — attempting it would mean inventing a call."""
    assert collect_executable_vectors(_rir(projection_method="templated_v1")) == []


def test_collection_is_bounded() -> None:
    """One mission must not become hundreds of container starts."""
    many = {
        "fns": [
            {
                "fn_id": f"n{i}",
                "name": "f",
                "projection_method": "ast_v1",
                "tests": {
                    "equivalence_vectors": [
                        {
                            "in": {"case": "nominal", "args": {"a": 1}},
                            "out": {"expected": None, "executable": True},
                        }
                    ]
                },
            }
            for i in range(200)
        ]
    }
    assert len(collect_executable_vectors(many)) == 25


def test_malformed_rir_is_tolerated() -> None:
    for payload in ({}, {"fns": None}, {"fns": [None]}, {"fns": [{"tests": "nope"}]}):
        assert collect_executable_vectors(payload) == []


# --- Degradation: never fail a mission -------------------------------------


def test_unsupported_language_is_skipped_not_failed() -> None:
    report = asyncio.run(
        run_behavioural_equivalence(
            mission_id="m1", language="rust", artifact_filename="a.rs",
            artifact_code="fn main(){}", rir_module=_rir(),
        )
    )
    assert report["status"] == "skipped"
    assert report["equivalence_vectors_passed"] == 0
    assert "rust" in report["reason"]


def test_no_vectors_is_skipped_with_a_stated_reason() -> None:
    report = asyncio.run(
        run_behavioural_equivalence(
            mission_id="m1", language="python", artifact_filename="a.py",
            artifact_code="x=1", rir_module={"fns": []},
        )
    )
    assert report["status"] == "skipped"
    assert "no executable equivalence vectors" in report["reason"]


def test_docker_unavailable_degrades_to_skipped_never_passed(monkeypatch) -> None:
    """Docker being absent must never read as verified."""
    async def _unavailable(_bin="docker"):
        return False

    monkeypatch.setattr(
        "orchestrator.equivalence_execution.check_docker_available", _unavailable
    )
    report = asyncio.run(
        run_behavioural_equivalence(
            mission_id="m1", language="python", artifact_filename="a.py",
            artifact_code="def add(a,b): return a+b", rir_module=_rir(),
        )
    )
    assert report["status"] == "skipped"
    assert report["status"] != "passed"
    assert "docker unavailable" in report["reason"]


def test_a_sandbox_timeout_is_not_a_behavioural_failure(monkeypatch) -> None:
    """A timeout means no verdict was produced — reporting it as a failure of
    the code under test would be wrong."""
    async def _available(_bin="docker"):
        return True

    async def _timeout(**_kwargs):
        return sandbox_exec.SandboxResult(
            exit_code=-1, stdout="", stderr="timeout", timed_out=True,
            timeout_seconds=15, memory_limit_mb=256, base_image="img",
        )

    monkeypatch.setattr(
        "orchestrator.equivalence_execution.check_docker_available", _available
    )
    monkeypatch.setattr("orchestrator.equivalence_execution.run_in_sandbox", _timeout)
    report = asyncio.run(
        run_behavioural_equivalence(
            mission_id="m1", language="python", artifact_filename="a.py",
            artifact_code="def add(a,b): return a+b", rir_module=_rir(),
        )
    )
    assert report["equivalence_vectors_skipped"] == 1
    assert report["equivalence_vectors_failed"] == 0


def test_execution_records_a_real_pass(monkeypatch) -> None:
    """Criterion 2: a real behavioural ratio is reported."""
    async def _available(_bin="docker"):
        return True

    async def _ok(**_kwargs):
        return sandbox_exec.SandboxResult(
            exit_code=0, stdout='__EQV__{"status": "ok", "result": 3}\n', stderr="",
            timed_out=False, timeout_seconds=15, memory_limit_mb=256, base_image="img",
        )

    monkeypatch.setattr(
        "orchestrator.equivalence_execution.check_docker_available", _available
    )
    monkeypatch.setattr("orchestrator.equivalence_execution.run_in_sandbox", _ok)

    rir = _rir()
    rir["fns"][0]["tests"]["equivalence_vectors"][0]["out"]["expected"] = 3
    report = asyncio.run(
        run_behavioural_equivalence(
            mission_id="m1", language="python", artifact_filename="a.py",
            artifact_code="def add(a,b): return a+b", rir_module=rir,
        )
    )
    assert report["status"] == "passed"
    assert report["equivalence_vectors_passed"] == 1
    assert report["equivalence_vectors_total"] == 1


def test_a_wrong_artifact_fails_a_vector(monkeypatch) -> None:
    """Criterion 3: the gate can actually fail."""
    async def _available(_bin="docker"):
        return True

    async def _wrong(**_kwargs):
        return sandbox_exec.SandboxResult(
            exit_code=0, stdout='__EQV__{"status": "ok", "result": 999}\n', stderr="",
            timed_out=False, timeout_seconds=15, memory_limit_mb=256, base_image="img",
        )

    monkeypatch.setattr(
        "orchestrator.equivalence_execution.check_docker_available", _available
    )
    monkeypatch.setattr("orchestrator.equivalence_execution.run_in_sandbox", _wrong)

    rir = _rir()
    rir["fns"][0]["tests"]["equivalence_vectors"][0]["out"]["expected"] = 3
    report = asyncio.run(
        run_behavioural_equivalence(
            mission_id="m1", language="python", artifact_filename="a.py",
            artifact_code="def add(a,b): return 999", rir_module=rir,
        )
    )
    assert report["status"] == "failed"
    assert report["equivalence_vectors_failed"] == 1
    assert report["findings"]


# --- UPG-52/53: report shape and non-enforcement ---------------------------


def _correctness_report():
    return {
        "status": "passed",
        "passed": True,
        "blocking": False,
        "verification_scope": "correctness",
        "findings": ["existing correctness finding"],
    }


def test_behavioural_attaches_as_a_separate_scope() -> None:
    """Criterion 6: both scopes visible, neither merged into the other."""
    enriched = attach_behavioural_report(
        _correctness_report(),
        {"verification_scope": "behavioural", "status": "failed", "findings": ["f[nominal]: boom"]},
    )
    assert enriched["verification_scope"] == "correctness"
    assert enriched["behavioural"]["verification_scope"] == "behavioural"


def test_behavioural_findings_surface_to_the_operator() -> None:
    enriched = attach_behavioural_report(
        _correctness_report(),
        {"status": "failed", "findings": ["f[nominal]: boom"]},
    )
    assert "existing correctness finding" in enriched["findings"]
    assert "[behavioural] f[nominal]: boom" in enriched["findings"]


def test_behavioural_failure_does_not_block_the_mission() -> None:
    """UPG-53: measure before enforcing. Enforcing an unmeasured gate is how
    you teach operators to disable gates."""
    enriched = attach_behavioural_report(
        _correctness_report(),
        {"status": "failed", "findings": ["f[nominal]: boom"], "equivalence_vectors_failed": 3},
    )
    assert enriched["status"] == "passed"
    assert enriched["passed"] is True
    assert enriched["blocking"] is False


def test_flag_off_leaves_the_report_byte_identical() -> None:
    """Criterion 1. Attaching nothing must not perturb the correctness report."""
    original = _correctness_report()
    assert attach_behavioural_report(dict(original), None) == original
    assert attach_behavioural_report(dict(original), {}) == original


@pytest.mark.parametrize("language", sorted(SUPPORTED_LANGUAGES))
def test_supported_languages_are_a_subset_of_the_sandbox_executables(language) -> None:
    from orchestrator.rqca_agent import _LANGUAGE_RUNTIMES

    assert language in _LANGUAGE_RUNTIMES


# --- Sibling-container workspace addressing --------------------------------


def test_workspace_path_is_translated_to_its_host_equivalent(monkeypatch) -> None:
    """The daemon resolves --volume sources on the HOST, not in this container.

    The orchestrator reaches the host daemon through a mounted socket, so the
    sandbox is a sibling container. Passing the orchestrator's own temp path
    makes the daemon silently create and mount an *empty* directory -- the
    compile step then fails with "no such file", and under
    RQCA_ENFORCEMENT_ENABLED that blocks the mission. Nothing about that failure
    points at path translation, which is why it is asserted here.
    """
    monkeypatch.setattr(sandbox_exec, "_WORKSPACE_ROOT", "/sandbox-workspace")
    monkeypatch.setattr(sandbox_exec, "_WORKSPACE_HOST_ROOT", "/host/shared")

    args = sandbox_exec.build_sandbox_args(
        docker_bin="docker",
        workspace_dir="/sandbox-workspace/hgr-rqca-abc123",
        base_image="gcc:13-bookworm",
        command="true",
        timeout_seconds=10,
        memory_mb=128,
    )
    mounts = [a for a in args if a.startswith("--volume=")]
    assert mounts == ["--volume=/host/shared/hgr-rqca-abc123:/workspace:ro"], mounts


def test_workspace_path_passes_through_when_unconfigured(monkeypatch) -> None:
    """A non-containerised orchestrator shares the daemon's filesystem already."""
    monkeypatch.setattr(sandbox_exec, "_WORKSPACE_ROOT", "")
    monkeypatch.setattr(sandbox_exec, "_WORKSPACE_HOST_ROOT", "")
    assert sandbox_exec.daemon_workspace_path("/tmp/hgr-rqca-abc") == "/tmp/hgr-rqca-abc"
    assert sandbox_exec.workspace_root() is None


def test_workspace_outside_the_shared_root_is_not_rewritten(monkeypatch) -> None:
    """There is no correct translation, so don't fabricate one."""
    monkeypatch.setattr(sandbox_exec, "_WORKSPACE_ROOT", "/sandbox-workspace")
    monkeypatch.setattr(sandbox_exec, "_WORKSPACE_HOST_ROOT", "/host/shared")
    assert sandbox_exec.daemon_workspace_path("/tmp/elsewhere") == "/tmp/elsewhere"
