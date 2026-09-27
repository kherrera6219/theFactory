"""P4: sandbox executor URL routes docker.sock off the orchestrator."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from urllib.error import URLError

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT))

from fastapi import HTTPException  # noqa: E402
from orchestrator import sandbox_exec  # noqa: E402
from orchestrator.sandbox_runner import SandboxExecuteRequest, _authorize  # noqa: E402
from pydantic import ValidationError  # noqa: E402


def test_sandbox_executor_url_requires_http_and_respects_runner_mode(monkeypatch) -> None:
    monkeypatch.delenv("SANDBOX_RUNNER_MODE", raising=False)
    monkeypatch.setenv("SANDBOX_EXECUTOR_URL", "http://sandbox-runner:8020")
    assert sandbox_exec.sandbox_executor_url() == "http://sandbox-runner:8020"
    monkeypatch.setenv("SANDBOX_RUNNER_MODE", "true")
    assert sandbox_exec.sandbox_executor_url() == ""
    monkeypatch.delenv("SANDBOX_RUNNER_MODE", raising=False)
    monkeypatch.setenv("SANDBOX_EXECUTOR_URL", "file:///etc/passwd")
    assert sandbox_exec.sandbox_executor_url() == ""


def test_run_in_sandbox_posts_to_executor_when_url_set(monkeypatch) -> None:
    monkeypatch.delenv("SANDBOX_RUNNER_MODE", raising=False)
    monkeypatch.setenv("SANDBOX_EXECUTOR_URL", "http://sandbox-runner:8020")
    monkeypatch.setenv("INTERNAL_SERVICE_API_KEY", "test-internal-key-32chars-minimum")

    captured: dict[str, object] = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "exit_code": 0,
                    "stdout": "ok\n",
                    "stderr": "",
                    "timed_out": False,
                    "timeout_seconds": 30,
                    "memory_limit_mb": 256,
                    "base_image": "python:3.12-slim",
                }
            ).encode("utf-8")

    def _urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["auth"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(sandbox_exec.urllib.request, "urlopen", _urlopen)

    async def _local(**kwargs):
        raise AssertionError("local docker must not run when executor URL is set")

    monkeypatch.setattr(sandbox_exec, "run_in_sandbox_local", _local)
    result = asyncio.run(
        sandbox_exec.run_in_sandbox(
            docker_bin="docker",
            workspace_dir="/sandbox-workspace/job",
            base_image="python:3.12-slim",
            command="pytest -q",
        )
    )
    assert result.succeeded is True
    assert result.stdout == "ok\n"
    assert captured["url"] == "http://sandbox-runner:8020/internal/sandbox/execute"
    assert captured["body"]["command"] == "pytest -q"
    assert "Bearer " in str(captured["auth"])


def test_run_in_sandbox_remote_records_unreachable_executor(monkeypatch) -> None:
    def _urlopen(request, timeout=None):
        raise URLError("connection refused")

    monkeypatch.setattr(sandbox_exec.urllib.request, "urlopen", _urlopen)
    result = asyncio.run(
        sandbox_exec.run_in_sandbox_remote(
            executor_url="http://sandbox-runner:8020",
            workspace_dir="/tmp/ws",
            base_image="python:3.12-slim",
            command="true",
        )
    )
    assert result.succeeded is False
    assert "unreachable" in result.stderr


def test_sandbox_runner_rejects_missing_or_wrong_key(monkeypatch) -> None:
    monkeypatch.delenv("INTERNAL_SERVICE_API_KEY", raising=False)
    with pytest.raises(HTTPException) as missing:
        _authorize("Bearer anything")
    assert missing.value.status_code == 503
    monkeypatch.setenv("INTERNAL_SERVICE_API_KEY", "correct-key")
    with pytest.raises(HTTPException) as denied:
        _authorize("Bearer wrong-key")
    assert denied.value.status_code == 401
    _authorize("Bearer correct-key")


def test_run_in_sandbox_local_returns_success_and_timeout(monkeypatch, tmp_path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "main.py").write_text("print(1)\n", encoding="utf-8")

    class _Proc:
        def __init__(self, hang: bool) -> None:
            self.hang = hang
            self.returncode = 0
            self.killed = False

        async def communicate(self):
            if self.hang:
                raise TimeoutError()
            return b"ok\n", b""

        def kill(self) -> None:
            self.killed = True

    async def _exec(*_args, **_kwargs):
        return _Proc(hang=False)

    monkeypatch.setattr(sandbox_exec.asyncio, "create_subprocess_exec", _exec)
    result = asyncio.run(
        sandbox_exec.run_in_sandbox_local(
            docker_bin="docker",
            workspace_dir=workspace,
            base_image="python:3.12-slim",
            command="pytest -q",
        )
    )
    assert result.succeeded is True
    assert result.stdout == "ok\n"

    async def _hang(*_args, **_kwargs):
        return _Proc(hang=True)

    monkeypatch.setattr(sandbox_exec.asyncio, "create_subprocess_exec", _hang)
    timed = asyncio.run(
        sandbox_exec.run_in_sandbox_local(
            docker_bin="docker",
            workspace_dir=workspace,
            base_image="python:3.12-slim",
            command="sleep 99",
            timeout_seconds=1,
        )
    )
    assert timed.timed_out is True
    assert "exceeded" in timed.stderr


def test_check_docker_available_local_and_remote(monkeypatch) -> None:
    monkeypatch.delenv("SANDBOX_EXECUTOR_URL", raising=False)
    monkeypatch.delenv("SANDBOX_RUNNER_MODE", raising=False)

    class _Proc:
        returncode = 0

        async def communicate(self):
            return b"27.0.0", b""

    async def _exec(*_args, **_kwargs):
        return _Proc()

    monkeypatch.setattr(sandbox_exec.asyncio, "create_subprocess_exec", _exec)
    assert asyncio.run(sandbox_exec.check_docker_available()) is True

    async def _boom(*_args, **_kwargs):
        raise OSError("no docker")

    monkeypatch.setattr(sandbox_exec.asyncio, "create_subprocess_exec", _boom)
    assert asyncio.run(sandbox_exec.check_docker_available()) is False

    monkeypatch.setenv("SANDBOX_EXECUTOR_URL", "http://sandbox-runner:8020")

    def _urlopen(request, timeout=None):
        raise sandbox_exec.urllib.error.URLError("down")

    monkeypatch.setattr(sandbox_exec.urllib.request, "urlopen", _urlopen)
    assert asyncio.run(sandbox_exec.check_docker_available()) is False


def test_sandbox_runner_execute_calls_local(monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from orchestrator.sandbox_runner import app

    monkeypatch.setenv("INTERNAL_SERVICE_API_KEY", "runner-key")

    async def _local(**kwargs):
        assert kwargs["command"] == "pytest -q"
        return sandbox_exec.SandboxResult(
            exit_code=0,
            stdout="ok",
            stderr="",
            timed_out=False,
            timeout_seconds=30,
            memory_limit_mb=256,
            base_image="python:3.12-slim",
        )

    monkeypatch.setattr("orchestrator.sandbox_runner.run_in_sandbox_local", _local)
    client = TestClient(app)
    response = client.post(
        "/internal/sandbox/execute",
        headers={"Authorization": "Bearer runner-key"},
        json={
            "workspace_dir": "/sandbox-workspace/job",
            "base_image": "python:3.12-slim",
            "command": "pytest -q",
        },
    )
    assert response.status_code == 200
    assert response.json()["exit_code"] == 0
    assert client.get("/livez").json() == {"ok": True}


def test_sandbox_execute_request_requires_workspace_and_command() -> None:
    parsed = SandboxExecuteRequest(
        workspace_dir="/sandbox-workspace/job",
        base_image="python:3.12-slim",
        command="pytest -q",
    )
    assert parsed.timeout_seconds == 30
    with pytest.raises(ValidationError):
        SandboxExecuteRequest(workspace_dir="", base_image="python:3.12-slim", command="x")


class TestInfrastructureErrors:
    """A harness failure must never be recorded as a defect in the artifact.

    `docker run` reports a missing image as exit 125, and runtime QC recorded
    that as FAIL: a Docker Hub rate limit (hit for real on 2026-09-27) or a
    factory image that was never built would block a correct mission.
    """

    def test_missing_image_is_an_infrastructure_error_and_nothing_runs(
        self, monkeypatch, tmp_path
    ) -> None:
        calls: list[tuple] = []

        async def _quiet(_bin, *args, timeout):
            calls.append(args)
            return (1, "Error response from daemon: pull access denied")

        async def _must_not_run(*_a, **_k):
            raise AssertionError("docker run must not start without the image")

        sandbox_exec._PRESENT_IMAGES.discard("thefactory/absent:1")
        monkeypatch.setattr(sandbox_exec, "_docker_quiet", _quiet)
        monkeypatch.setattr(sandbox_exec.asyncio, "create_subprocess_exec", _must_not_run)
        result = asyncio.run(
            sandbox_exec.run_in_sandbox_local(
                docker_bin="docker", workspace_dir=tmp_path,
                base_image="thefactory/absent:1", command="true",
            )
        )
        assert result.infrastructure_error and "pull access denied" in result.infrastructure_error
        assert result.succeeded is False
        assert [c[0] for c in calls] == ["image", "pull"]

    def test_present_image_is_checked_once(self, monkeypatch) -> None:
        calls: list[tuple] = []

        async def _quiet(_bin, *args, timeout):
            calls.append(args)
            return (0, "")

        sandbox_exec._PRESENT_IMAGES.discard("python:3.11-slim")
        monkeypatch.setattr(sandbox_exec, "_docker_quiet", _quiet)
        assert asyncio.run(sandbox_exec.ensure_sandbox_image("docker", "python:3.11-slim")) is None
        assert asyncio.run(sandbox_exec.ensure_sandbox_image("docker", "python:3.11-slim")) is None
        assert len(calls) == 1

    def test_unreachable_executor_is_an_infrastructure_error(self, monkeypatch) -> None:
        monkeypatch.delenv("SANDBOX_RUNNER_MODE", raising=False)

        def _boom(*_a, **_k):
            raise URLError("connection refused")

        monkeypatch.setattr(sandbox_exec.urllib.request, "urlopen", _boom)
        result = asyncio.run(
            sandbox_exec.run_in_sandbox_remote(
                executor_url="http://sandbox-runner:8020", workspace_dir="/w",
                base_image="python:3.11-slim", command="true",
            )
        )
        assert result.infrastructure_error == "sandbox executor unreachable: URLError"

    def test_infrastructure_error_survives_the_runner_round_trip(self) -> None:
        from orchestrator.sandbox_runner import result_to_payload

        original = sandbox_exec.SandboxResult(
            exit_code=-1, stdout="", stderr="x", timed_out=False, timeout_seconds=30,
            memory_limit_mb=256, base_image="img", infrastructure_error="image unavailable",
        )
        payload = json.loads(json.dumps(result_to_payload(original)))
        restored = sandbox_exec.result_from_payload(
            payload, fallback_image="img", timeout=30, memory=256
        )
        assert restored.infrastructure_error == "image unavailable"
        clean = sandbox_exec.result_from_payload(
            {"exit_code": 0}, fallback_image="img", timeout=30, memory=256
        )
        assert clean.infrastructure_error is None

    def test_runtime_qc_reports_dry_run_not_fail(self, monkeypatch) -> None:
        from types import SimpleNamespace

        from orchestrator import rqca_agent

        async def _infra(**_kwargs):
            return sandbox_exec.SandboxResult(
                exit_code=-1, stdout="", stderr="", timed_out=False, timeout_seconds=30,
                memory_limit_mb=256, base_image="golang:1.22-bookworm",
                infrastructure_error="sandbox image golang:1.22-bookworm is unavailable: 429",
            )

        monkeypatch.setattr(rqca_agent, "run_in_sandbox", _infra)
        report = asyncio.run(
            rqca_agent._execute_in_sandbox(
                docker_bin="docker", mission_id="mission-infra", filename="main.go",
                code="package main\nfunc main() {}\n", test_code="",
                testdata_manifest={"base_image": "golang:1.22-bookworm",
                                   "run_command": "go run /workspace/main.go"},
                language="go", settings=SimpleNamespace(),
            )
        )
        assert report["verdict"] == "DRY_RUN"
        assert "infrastructure" in str(report.get("dry_run_reason"))
