"""RQCA Agent helpers for sandboxed runtime QC."""
from __future__ import annotations

import asyncio
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RQCA_SCHEMA_VERSION = "runtime_qc_report.v1"
# Languages that get live Docker execution when RQCA_AGENT_ENABLED=true.
# Dynamic languages run their output directly; compiled languages compile-then-run.
_EXECUTABLE_LANGUAGES = {"python", "javascript", "typescript"}
_COMPILED_LANGUAGES = {"c", "cpp", "c++", "rust", "csharp", "c#"}
_ALL_LIVE_LANGUAGES = _EXECUTABLE_LANGUAGES | _COMPILED_LANGUAGES
_MAX_TIMEOUT_SECONDS = 60
_MAX_MEMORY_MB = 512

# Docker image + compile-and-run command templates for compiled languages.
# The run_command is a shell snippet executed inside the container with /workspace mounted.
_COMPILED_LANGUAGE_CONFIG: dict[str, dict[str, str]] = {
    "c": {
        "base_image": "gcc:13-bookworm",
        "compile_command": "gcc -Wall -Wextra -o /workspace/a.out /workspace/{filename}",
        "run_command": "/workspace/a.out",
    },
    "cpp": {
        "base_image": "gcc:13-bookworm",
        "compile_command": "g++ -std=c++20 -Wall -Wextra -o /workspace/a.out /workspace/{filename}",
        "run_command": "/workspace/a.out",
    },
    "c++": {
        "base_image": "gcc:13-bookworm",
        "compile_command": "g++ -std=c++20 -Wall -Wextra -o /workspace/a.out /workspace/{filename}",
        "run_command": "/workspace/a.out",
    },
    "rust": {
        "base_image": "rust:1.78-slim-bookworm",
        "compile_command": "rustc /workspace/{filename} -o /workspace/a.out",
        "run_command": "/workspace/a.out",
    },
    "csharp": {
        "base_image": "mcr.microsoft.com/dotnet/sdk:8.0",
        "compile_command": "dotnet-script /workspace/{filename}",
        "run_command": "",  # dotnet-script compiles + runs in one step
    },
    "c#": {
        "base_image": "mcr.microsoft.com/dotnet/sdk:8.0",
        "compile_command": "dotnet-script /workspace/{filename}",
        "run_command": "",
    },
}


async def _check_docker_available(docker_bin: str = "docker") -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            docker_bin,
            "info",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=5.0)
        return proc.returncode == 0
    except Exception:
        return False


def _default_run_command(filename: str, language: str) -> str:
    return {
        "python": f"python /workspace/{filename}",
        "javascript": f"node /workspace/{filename}",
        "typescript": f"node /workspace/{filename}",
    }.get(language.lower(), f"cat /workspace/{filename}")


async def run_runtime_qc(
    *,
    mission_id: str,
    generated_output: dict[str, Any],
    testdata_manifest: dict[str, Any],
    integration_tests: dict[str, Any] | None,
    language: str,
    settings: Any,
) -> dict[str, Any]:
    normalized_language = str(language or generated_output.get("language") or "python").lower()
    filename = str(generated_output.get("filename") or f"output.{normalized_language}")
    code = str(generated_output.get("generated_code") or "")
    if not code.strip():
        return _skipped_report(
            mission_id=mission_id,
            language=normalized_language,
            filename=filename,
            reason="No generated code artifact to execute.",
        )
    if normalized_language not in _ALL_LIVE_LANGUAGES:
        return _dry_run_report(
            mission_id=mission_id,
            language=normalized_language,
            filename=filename,
            testdata_manifest=testdata_manifest,
            reason=f"Live execution not supported for {normalized_language}.",
        )
    docker_bin = str(getattr(settings, "docker_bin", "docker") or "docker")
    if not await _check_docker_available(docker_bin):
        return _dry_run_report(
            mission_id=mission_id,
            language=normalized_language,
            filename=filename,
            testdata_manifest=testdata_manifest,
            reason="Docker not available.",
        )
    # Inject compiled-language defaults into the testdata manifest when the
    # language has a known compile-then-run config and the manifest doesn't
    # already specify a base_image.
    if normalized_language in _COMPILED_LANGUAGES:
        compiled_cfg = _COMPILED_LANGUAGE_CONFIG.get(normalized_language, {})
        if compiled_cfg and not testdata_manifest.get("base_image"):
            testdata_manifest = {**testdata_manifest}
            testdata_manifest.setdefault("base_image", compiled_cfg["base_image"])
            if compiled_cfg.get("run_command"):
                run_cmd = (
                    compiled_cfg["compile_command"].format(filename=filename)
                    + " && "
                    + compiled_cfg["run_command"]
                )
            else:
                run_cmd = compiled_cfg["compile_command"].format(filename=filename)
            testdata_manifest.setdefault("run_command", run_cmd)
    return await _execute_in_sandbox(
        docker_bin=docker_bin,
        mission_id=mission_id,
        filename=filename,
        code=code,
        test_code=str((integration_tests or {}).get("test_code") or ""),
        testdata_manifest=testdata_manifest,
        language=normalized_language,
    )


async def _execute_in_sandbox(
    *,
    docker_bin: str,
    mission_id: str,
    filename: str,
    code: str,
    test_code: str,
    testdata_manifest: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    base_image = str(testdata_manifest.get("base_image") or "python:3.11-slim")
    run_command = str(
        testdata_manifest.get("run_command") or _default_run_command(filename, language)
    )
    install_commands = [
        str(command) for command in (testdata_manifest.get("install_commands") or [])[:10]
    ]
    try:
        timeout = int(testdata_manifest.get("timeout_seconds") or 30)
    except (TypeError, ValueError):
        timeout = 30
    try:
        memory_mb = int(testdata_manifest.get("memory_limit_mb") or 256)
    except (TypeError, ValueError):
        memory_mb = 256
    timeout = max(1, min(timeout, _MAX_TIMEOUT_SECONDS))
    memory_mb = max(64, min(memory_mb, _MAX_MEMORY_MB))
    started_at = datetime.now(UTC).isoformat()
    with tempfile.TemporaryDirectory(prefix=f"hgr-rqca-{mission_id[:8]}-") as tmpdir:
        workspace = Path(tmpdir)
        (workspace / filename).write_text(code, encoding="utf-8")
        if test_code.strip():
            (workspace / f"test_{filename}").write_text(test_code, encoding="utf-8")
        install_script = "#!/bin/sh\nset -e\n" + "\n".join(install_commands)
        (workspace / "install.sh").write_text(install_script, encoding="utf-8")
        full_command = (
            f"sh /workspace/install.sh && {run_command}" if install_commands else run_command
        )
        docker_args = [
            docker_bin,
            "run",
            "--rm",
            "--network=none",
            f"--memory={memory_mb}m",
            "--memory-swap=0",
            "--cpus=1",
            "--read-only",
            "--tmpfs=/tmp:size=64m,mode=1777",
            "--security-opt=no-new-privileges:true",
            "--cap-drop=ALL",
            "--workdir=/workspace",
            f"--volume={tmpdir}:/workspace:ro",
            base_image,
            "sh",
            "-c",
            full_command,
        ]
        proc = await asyncio.create_subprocess_exec(
            *docker_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=float(timeout) + 5.0
            )
        except asyncio.TimeoutError:
            proc.kill()
            return _timeout_report(
                mission_id=mission_id,
                language=language,
                filename=filename,
                timeout_seconds=timeout,
                started_at=started_at,
            )
    exit_code = int(proc.returncode or 0)
    expected_exit_code = int(testdata_manifest.get("expected_exit_code") or 0)
    passed = exit_code == expected_exit_code
    return {
        "schema_version": RQCA_SCHEMA_VERSION,
        "mission_id": mission_id,
        "verdict": "PASS" if passed else "FAIL",
        "passed": passed,
        "execution_type": "docker_live",
        "exit_code": exit_code,
        "expected_exit_code": expected_exit_code,
        "stdout_preview": stdout_bytes.decode("utf-8", errors="replace")[:2000],
        "stderr_preview": stderr_bytes.decode("utf-8", errors="replace")[:1000],
        "base_image": base_image,
        "language": language,
        "filename": filename,
        "timeout_seconds": timeout,
        "memory_limit_mb": memory_mb,
        "started_at": started_at,
        "completed_at": datetime.now(UTC).isoformat(),
        "source": "live_execution",
    }


def _dry_run_report(
    *,
    mission_id: str,
    language: str,
    filename: str,
    testdata_manifest: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    manifest_valid = bool(
        testdata_manifest.get("base_image") and testdata_manifest.get("run_command")
    )
    return {
        "schema_version": RQCA_SCHEMA_VERSION,
        "mission_id": mission_id,
        "verdict": "DRY_RUN",
        "passed": manifest_valid,
        "execution_type": "dry_run",
        "dry_run_reason": reason,
        "manifest_valid": manifest_valid,
        "language": language,
        "filename": filename,
        "source": "dry_run",
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _timeout_report(
    *,
    mission_id: str,
    language: str,
    filename: str,
    timeout_seconds: int,
    started_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": RQCA_SCHEMA_VERSION,
        "mission_id": mission_id,
        "verdict": "TIMEOUT",
        "passed": False,
        "execution_type": "docker_live",
        "language": language,
        "filename": filename,
        "timeout_seconds": timeout_seconds,
        "started_at": started_at,
        "completed_at": datetime.now(UTC).isoformat(),
        "source": "live_execution",
    }


def _skipped_report(
    *,
    mission_id: str,
    language: str,
    filename: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": RQCA_SCHEMA_VERSION,
        "mission_id": mission_id,
        "verdict": "SKIPPED",
        "passed": True,
        "execution_type": "skipped",
        "skip_reason": reason,
        "language": language,
        "filename": filename,
        "source": "skipped",
        "generated_at": datetime.now(UTC).isoformat(),
    }
