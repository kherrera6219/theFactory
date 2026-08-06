"""RQCA Agent helpers for sandboxed runtime QC."""
from __future__ import annotations

import asyncio
import json
import re
import shlex
import tempfile
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .sandbox_exec import (
    MAX_MEMORY_MB as _SHARED_MAX_MEMORY_MB,
)
from .sandbox_exec import (
    MAX_TIMEOUT_SECONDS as _SHARED_MAX_TIMEOUT_SECONDS,
)
from .sandbox_exec import (
    SANDBOX_BUILD_DIR,
    run_in_sandbox,
    workspace_root,
)

RQCA_SCHEMA_VERSION = "runtime_qc_report.v1"
# Languages that get live Docker execution when RQCA_AGENT_ENABLED=true.
# Dynamic languages run their output directly; compiled languages compile-then-run.
_EXECUTABLE_LANGUAGES = {"python", "javascript", "typescript"}
# C#/.NET is deliberately absent. Its config invoked `dotnet-script`, which is a
# global tool that is NOT present in `mcr.microsoft.com/dotnet/sdk:8.0`
# (verified by running `command -v dotnet-script` in that image) and cannot be
# installed at run time because the sandbox is `--network=none`. Listing it here
# would produce a guaranteed FAIL verdict, and with RQCA_ENFORCEMENT_ENABLED
# that blocks the mission -- strictly worse than the DRY_RUN an unsupported
# language returns. Re-add it with an image that ships a single-file C# runner.
_COMPILED_LANGUAGES = {"c", "cpp", "c++", "rust"}
_ALL_LIVE_LANGUAGES = _EXECUTABLE_LANGUAGES | _COMPILED_LANGUAGES
# Aliased to the shared sandbox ceilings (UPG-50) so RQCA and behavioural
# equivalence cannot drift apart on resource limits.
_MAX_TIMEOUT_SECONDS = _SHARED_MAX_TIMEOUT_SECONDS
_MAX_MEMORY_MB = _SHARED_MAX_MEMORY_MB
_HTML_EXTENSIONS = {"html", "htm"}
_SCRIPT_EXTENSIONS = {"js", "mjs", "cjs", "ts", "tsx", "jsx"}
_NODE_CHECK_LANGUAGES = {"javascript", "typescript"}

# Docker image + compile-and-run command templates for compiled languages.
# The run_command is a shell snippet executed inside the container with
# /workspace mounted READ-ONLY.
#
# Build output therefore goes to SANDBOX_BUILD_DIR (/tmp), the only writable and
# executable location in the sandbox. These templates previously wrote
# `/workspace/a.out`, which made every compiled-language run fail at link time
# with "cannot open output file /workspace/a.out: Read-only file system" -- the
# whole compiled path had never worked. Verified by hand against gcc:13-bookworm
# (C) and rust:1.78-slim-bookworm (Rust); both now compile and run.
# Base images for the interpreted languages. Without these, a manifest that does
# not name an image falls back to `python:3.11-slim` for *every* language, so a
# JavaScript mission ran `node /workspace/main.js` inside the Python image and
# died with "sh: 1: node: not found" (exit 127) -- recorded as a FAIL of the
# generated code, and blocked under RQCA_ENFORCEMENT_ENABLED. The compiled
# languages already had this injection; the interpreted ones were relying on the
# testdata agent to supply an image, and that agent is off by default.
_EXECUTABLE_LANGUAGE_IMAGES: dict[str, str] = {
    "python": "python:3.11-slim",
    "javascript": "node:20-slim",
    "typescript": "node:20-slim",
}

_BUILD_OUTPUT = f"{SANDBOX_BUILD_DIR}/a.out"
_COMPILED_LANGUAGE_CONFIG: dict[str, dict[str, str]] = {
    "c": {
        "base_image": "gcc:13-bookworm",
        "compile_command": f"gcc -Wall -Wextra -o {_BUILD_OUTPUT} /workspace/{{filename}}",
        "run_command": _BUILD_OUTPUT,
    },
    "cpp": {
        "base_image": "gcc:13-bookworm",
        "compile_command": (
            f"g++ -std=c++20 -Wall -Wextra -o {_BUILD_OUTPUT} /workspace/{{filename}}"
        ),
        "run_command": _BUILD_OUTPUT,
    },
    "c++": {
        "base_image": "gcc:13-bookworm",
        "compile_command": (
            f"g++ -std=c++20 -Wall -Wextra -o {_BUILD_OUTPUT} /workspace/{{filename}}"
        ),
        "run_command": _BUILD_OUTPUT,
    },
    "rust": {
        "base_image": "rust:1.78-slim-bookworm",
        "compile_command": f"rustc /workspace/{{filename}} -o {_BUILD_OUTPUT}",
        "run_command": _BUILD_OUTPUT,
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


def _artifact_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _artifact_kind(filename: str, language: str) -> str:
    ext = _artifact_extension(filename)
    if ext in _HTML_EXTENSIONS:
        return "html"
    if ext in _SCRIPT_EXTENSIONS or language.lower() in _NODE_CHECK_LANGUAGES:
        return "script"
    return "generic"


class _HtmlArtifactParser(HTMLParser):
    """Collect lightweight HTML smoke metadata without treating regex as a parser."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.has_html_tag = False
        self.has_body_tag = False
        self.external_script_count = 0
        self.external_stylesheet_count = 0
        self.inline_scripts: list[str] = []
        self._in_inline_script = False
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        attr_map = {name.lower(): value for name, value in attrs}
        if tag_name == "html":
            self.has_html_tag = True
        elif tag_name == "body":
            self.has_body_tag = True
        elif tag_name == "script":
            if attr_map.get("src"):
                self.external_script_count += 1
                self._in_inline_script = False
                self._script_parts = []
            else:
                self._in_inline_script = True
                self._script_parts = []
        elif tag_name == "link":
            rel = attr_map.get("rel") or ""
            if "stylesheet" in rel.lower().split():
                self.external_stylesheet_count += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._in_inline_script:
            self.inline_scripts.append("".join(self._script_parts))
            self._in_inline_script = False
            self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_inline_script:
            self._script_parts.append(data)


def _parse_html_artifact(html: str) -> _HtmlArtifactParser:
    parser = _HtmlArtifactParser()
    parser.feed(html)
    parser.close()
    return parser


def _extract_inline_scripts(html: str) -> list[str]:
    return _parse_html_artifact(html).inline_scripts


async def _node_syntax_check(
    *,
    code: str,
    filename: str,
    settings: Any,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    node_bin = str(getattr(settings, "node_bin", "node") or "node")
    suffix = Path(filename).suffix or ".js"
    started_at = datetime.now(UTC).isoformat()
    with tempfile.TemporaryDirectory(
        prefix="hgr-rqca-node-check-", dir=workspace_root()
    ) as tmpdir:
        check_file = Path(tmpdir) / f"artifact{suffix}"
        check_file.write_text(code, encoding="utf-8")
        try:
            proc = await asyncio.create_subprocess_exec(
                node_bin,
                "--check",
                str(check_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return {
                "verdict": "DRY_RUN",
                "passed": False,
                "execution_type": "node_check_unavailable",
                "reason": f"{node_bin} not available for syntax check.",
                "started_at": started_at,
                "completed_at": datetime.now(UTC).isoformat(),
            }
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            proc.kill()
            return {
                "verdict": "TIMEOUT",
                "passed": False,
                "execution_type": "node_check",
                "stdout_preview": "",
                "stderr_preview": "node --check timed out",
                "started_at": started_at,
                "completed_at": datetime.now(UTC).isoformat(),
            }
    passed = proc.returncode == 0
    return {
        "verdict": "PASS" if passed else "FAIL",
        "passed": passed,
        "execution_type": "node_check",
        "exit_code": int(proc.returncode or 0),
        "stdout_preview": stdout_bytes.decode("utf-8", errors="replace")[:1000],
        "stderr_preview": stderr_bytes.decode("utf-8", errors="replace")[:1000],
        "started_at": started_at,
        "completed_at": datetime.now(UTC).isoformat(),
    }


async def _build_artifact_smoke_report(
    *,
    code: str,
    filename: str,
    language: str,
    settings: Any,
) -> dict[str, Any]:
    kind = _artifact_kind(filename, language)
    if kind == "script":
        node_check = await _node_syntax_check(
            code=code,
            filename=filename,
            settings=settings,
        )
        return {
            "schema_version": "artifact_runtime_smoke.v1",
            "artifact_kind": "script",
            "filename": filename,
            "language": language,
            "verdict": node_check["verdict"],
            "passed": bool(node_check.get("passed", False)),
            "checks": {"node_syntax": node_check},
            "source": "node_check",
            "generated_at": datetime.now(UTC).isoformat(),
        }
    if kind == "html":
        parser = _parse_html_artifact(code)
        lower = code.lower()
        structure = {
            "has_doctype": "<!doctype html" in lower,
            "has_html_tag": parser.has_html_tag and "</html>" in lower,
            "has_body_tag": parser.has_body_tag and "</body>" in lower,
            "external_script_count": parser.external_script_count,
            "external_stylesheet_count": parser.external_stylesheet_count,
        }
        inline_scripts = parser.inline_scripts
        script_checks = [
            await _node_syntax_check(
                code=script,
                filename=f"{Path(filename).stem or 'inline'}-{index}.js",
                settings=settings,
            )
            for index, script in enumerate(inline_scripts, start=1)
            if script.strip()
        ]
        structure_passed = structure["has_html_tag"] and structure["has_body_tag"]
        scripts_passed = all(check.get("passed") for check in script_checks)
        syntax_degraded = any(check.get("verdict") == "DRY_RUN" for check in script_checks)
        verdict = "PASS" if structure_passed and scripts_passed else "FAIL"
        if syntax_degraded and structure_passed:
            verdict = "DRY_RUN"
        return {
            "schema_version": "artifact_runtime_smoke.v1",
            "artifact_kind": "html",
            "filename": filename,
            "language": language,
            "verdict": verdict,
            "passed": verdict == "PASS",
            "checks": {
                "html_structure": structure,
                "inline_script_syntax": script_checks,
                "browser_load": {
                    "verdict": "DRY_RUN",
                    "passed": False,
                    "reason": "Headless browser runtime is not installed in orchestrator.",
                },
            },
            "source": "static_html_and_node_check",
            "generated_at": datetime.now(UTC).isoformat(),
        }
    return {
        "schema_version": "artifact_runtime_smoke.v1",
        "artifact_kind": "generic",
        "filename": filename,
        "language": language,
        "verdict": "SKIPPED",
        "passed": True,
        "skip_reason": "No artifact smoke is defined for this artifact type.",
        "source": "skipped",
        "generated_at": datetime.now(UTC).isoformat(),
    }


# Per-language commands that run the generated test file via the language's
# test framework so pass/fail reflects assertions, not just "artifact exited 0".
# "{filename}" and "{test_filename}" are substituted with shell-quoted paths.
_DEFAULT_TEST_COMMAND_TEMPLATES: dict[str, str] = {
    "python": "python -m pytest -q /workspace/{test_filename}",
    "javascript": "node --test /workspace/{test_filename}",
    "typescript": "node --test /workspace/{test_filename}",
}


def _resolve_test_command(
    *,
    filename: str,
    test_filename: str,
    language: str,
    settings: Any,
) -> str | None:
    """Resolve the command RQCA should run to determine pass/fail.

    Prefers an operator-supplied ``RQCA_TEST_COMMAND_TEMPLATE`` then a built-in
    per-language test-framework template. Returns ``None`` when no test file was
    generated or no template applies, in which case the caller falls back to
    executing the artifact directly. Substituted values are shell-quoted.
    """
    if not test_filename:
        return None
    template = str(getattr(settings, "rqca_test_command_template", "") or "").strip()
    if not template:
        template = _DEFAULT_TEST_COMMAND_TEMPLATES.get(language.lower(), "")
    if not template:
        return None
    return template.format(
        filename=shlex.quote(f"/workspace/{filename}").strip("'"),
        test_filename=shlex.quote(test_filename).strip("'"),
    )


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
    artifact_smoke = await _build_artifact_smoke_report(
        code=code,
        filename=filename,
        language=normalized_language,
        settings=settings,
    )
    if artifact_smoke.get("verdict") in {"FAIL", "TIMEOUT"}:
        return _artifact_smoke_failure_report(
            mission_id=mission_id,
            language=normalized_language,
            filename=filename,
            artifact_smoke=artifact_smoke,
        )
    if _artifact_kind(filename, normalized_language) == "html":
        return _dry_run_report(
            mission_id=mission_id,
            language=normalized_language,
            filename=filename,
            testdata_manifest=testdata_manifest,
            reason="HTML browser smoke unavailable in orchestrator runtime.",
            artifact_smoke=artifact_smoke,
        )
    if normalized_language not in _ALL_LIVE_LANGUAGES:
        return _dry_run_report(
            mission_id=mission_id,
            language=normalized_language,
            filename=filename,
            testdata_manifest=testdata_manifest,
            reason=f"Live execution not supported for {normalized_language}.",
            artifact_smoke=artifact_smoke,
        )
    docker_bin = str(getattr(settings, "docker_bin", "docker") or "docker")
    if not await _check_docker_available(docker_bin):
        return _dry_run_report(
            mission_id=mission_id,
            language=normalized_language,
            filename=filename,
            testdata_manifest=testdata_manifest,
            reason="Docker not available.",
            artifact_smoke=artifact_smoke,
        )
    # Interpreted languages need a runtime image just as much as compiled ones:
    # the sandbox default is the Python image, which has no `node`.
    if normalized_language in _EXECUTABLE_LANGUAGE_IMAGES and not testdata_manifest.get(
        "base_image"
    ):
        testdata_manifest = {
            **testdata_manifest,
            "base_image": _EXECUTABLE_LANGUAGE_IMAGES[normalized_language],
        }
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
    result = await _execute_in_sandbox(
        docker_bin=docker_bin,
        mission_id=mission_id,
        filename=filename,
        code=code,
        test_code=str((integration_tests or {}).get("test_code") or ""),
        testdata_manifest=testdata_manifest,
        language=normalized_language,
        settings=settings,
    )
    result["artifact_smoke"] = artifact_smoke
    return result


# Service names must be valid compose keys; anything else is rejected/sanitized.
_SERVICE_NAME_RE = re.compile(r"[^A-Za-z0-9_-]")


def _safe_service_name(value: Any, fallback: str) -> str:
    name = _SERVICE_NAME_RE.sub("-", str(value or "").strip()) or fallback
    return name[:63]


def _build_rqca_compose_yml(
    mission_id: str,
    filename: str,
    code_tmpdir: str,
    testdata_manifest: dict[str, Any],
) -> str:
    """Build a minimal, hardened docker-compose YAML for multi-container RQCA.

    The manifest's ``services`` list should be a list of dicts with at least
    ``name`` (str) and ``image`` (str).  The first entry is treated as the
    test-runner; additional entries are supporting services (e.g. Postgres).

    Every service carries the same sandbox hardening as the single-container
    path: dropped capabilities, no-new-privileges, read-only root filesystem,
    and CPU/memory caps. All operator-supplied values (image, command, env,
    names) are passed through ``json.dumps`` so they are emitted as quoted YAML
    scalars rather than interpolated verbatim — this prevents manifest
    injection via crafted images/commands/env values.

    Example manifest shape::

        {
          "multi_container": true,
          "services": [
            {"name": "test-runner", "image": "python:3.11-slim",
             "command": "python /workspace/output.py"},
            {"name": "db", "image": "postgres:16-alpine",
             "environment": {"POSTGRES_PASSWORD": "test"}}
          ]
        }

    Supporting services (index > 0) keep an internal network so the test-runner
    can reach them; the test-runner itself has no published ports and a
    read-only mount of the workspace.
    """
    services = testdata_manifest.get("services") or []
    try:
        timeout = int(testdata_manifest.get("timeout_seconds") or 30)
    except (TypeError, ValueError):
        timeout = 30
    try:
        memory_mb = int(testdata_manifest.get("memory_limit_mb") or 256)
    except (TypeError, ValueError):
        memory_mb = 256
    try:
        cpus = float(testdata_manifest.get("cpus") or 1.0)
    except (TypeError, ValueError):
        cpus = 1.0
    timeout = max(1, min(timeout, _MAX_TIMEOUT_SECONDS))
    memory_mb = max(64, min(memory_mb, _MAX_MEMORY_MB))
    cpus = max(0.25, min(cpus, 2.0))

    def _q(value: Any) -> str:
        # Emit any scalar as a JSON string, which is valid YAML and prevents the
        # value from being interpreted as YAML structure or shell tokens.
        return json.dumps(str(value))

    lines: list[str] = ["services:"]
    for i, svc in enumerate(services):
        if not isinstance(svc, dict):
            continue
        name = _safe_service_name(svc.get("name"), f"svc{i}")
        image = str(svc.get("image") or "python:3.11-slim")
        command = svc.get("command", "")
        env = svc.get("environment") or {}

        lines.append(f"  {name}:")
        lines.append(f"    image: {_q(image)}")
        lines.append(f"    mem_limit: {memory_mb}m")
        lines.append(f"    cpus: {cpus}")
        lines.append("    read_only: true")
        lines.append("    tmpfs:")
        lines.append("      - /tmp")
        lines.append("    cap_drop:")
        lines.append("      - ALL")
        lines.append("    security_opt:")
        lines.append("      - no-new-privileges:true")
        if i == 0:
            # test-runner mounts the workspace read-only and is the exit-code source
            lines.append("    working_dir: /workspace")
            lines.append("    volumes:")
            lines.append(f"      - {_q(code_tmpdir + ':/workspace:ro')}")
        if command:
            lines.append(f"    command: {_q(command)}")
        if isinstance(env, dict) and env:
            lines.append("    environment:")
            for k, v in env.items():
                lines.append(f"      {_q(str(k))}: {_q(v)}")
        if i == 0 and len(services) > 1:
            # test-runner waits for supporting services
            dep_names = [
                _safe_service_name(s.get("name"), f"svc{j}")
                for j, s in enumerate(services[1:], start=1)
            ]
            lines.append("    depends_on:")
            for dep in dep_names:
                lines.append(f"      {dep}:")
                lines.append("        condition: service_started")
    return "\n".join(lines) + "\n"


async def _execute_in_sandbox(
    *,
    docker_bin: str,
    mission_id: str,
    filename: str,
    code: str,
    test_code: str,
    testdata_manifest: dict[str, Any],
    language: str,
    settings: Any = None,
) -> dict[str, Any]:
    base_image = str(testdata_manifest.get("base_image") or "python:3.11-slim")
    test_filename = f"test_{filename}" if test_code.strip() else ""
    # When a test file was generated, prefer running the language's test framework
    # against it so pass/fail reflects assertions rather than "artifact exited 0".
    # An explicit manifest run_command still wins for backwards compatibility.
    test_command = _resolve_test_command(
        filename=filename,
        test_filename=test_filename,
        language=language,
        settings=settings,
    )
    run_command = str(
        testdata_manifest.get("run_command")
        or test_command
        or _default_run_command(filename, language)
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
    multi_container = bool(testdata_manifest.get("multi_container"))
    # Set only by the single-container path, which no longer holds a `proc`.
    single_container_exit_code: int | None = None
    with tempfile.TemporaryDirectory(
        prefix=f"hgr-rqca-{mission_id[:8]}-", dir=workspace_root()
    ) as tmpdir:
        workspace = Path(tmpdir)
        (workspace / filename).write_text(code, encoding="utf-8")
        if test_code.strip():
            (workspace / f"test_{filename}").write_text(test_code, encoding="utf-8")

        if multi_container and testdata_manifest.get("services"):
            # ── Multi-container path: build compose file, run with docker compose ──
            # Inject the resolved run/test command into the test-runner service
            # when the manifest didn't specify one, so the same command-selection
            # logic (test framework over bare execution) applies to compose too.
            raw_services = testdata_manifest.get("services") or []
            services_with_command: list[Any] = []
            for idx, svc in enumerate(raw_services):
                if idx == 0 and isinstance(svc, dict) and not svc.get("command"):
                    svc = {**svc, "command": run_command}
                services_with_command.append(svc)
            compose_manifest = {**testdata_manifest, "services": services_with_command}
            compose_yml = _build_rqca_compose_yml(
                mission_id=mission_id,
                filename=filename,
                code_tmpdir=tmpdir,
                testdata_manifest=compose_manifest,
            )
            compose_file = workspace / "docker-compose.rqca.yml"
            compose_file.write_text(compose_yml, encoding="utf-8")
            services = services_with_command
            runner_name = (
                _safe_service_name(
                    services[0].get("name") if isinstance(services[0], dict) else None,
                    "svc0",
                )
                if services else "svc0"
            )
            docker_args = [
                docker_bin, "compose",
                "-f", str(compose_file),
                "up",
                "--abort-on-container-exit",
                f"--exit-code-from={runner_name}",
                "--timeout", str(timeout),
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *docker_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        proc.communicate(), timeout=float(timeout) + 15.0
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    return _timeout_report(
                        mission_id=mission_id, language=language, filename=filename,
                        timeout_seconds=timeout, started_at=started_at,
                    )
            finally:
                # Always tear down the compose stack
                teardown = await asyncio.create_subprocess_exec(
                    docker_bin, "compose", "-f", str(compose_file), "down", "--remove-orphans",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                try:
                    await asyncio.wait_for(teardown.wait(), timeout=30.0)
                except Exception:
                    pass
        else:
            # ── Single-container path (default) ─────────────────────────────────
            install_script = "#!/bin/sh\nset -e\n" + "\n".join(install_commands)
            (workspace / "install.sh").write_text(install_script, encoding="utf-8")
            full_command = (
                f"sh /workspace/install.sh && {run_command}" if install_commands else run_command
            )
            # UPG-50: the hardened docker-run invocation now lives in
            # sandbox_exec so RQCA and behavioural equivalence share exactly one
            # set of security flags. Do not re-inline a docker command here.
            sandbox_result = await run_in_sandbox(
                docker_bin=docker_bin,
                workspace_dir=tmpdir,
                base_image=base_image,
                command=full_command,
                timeout_seconds=timeout,
                memory_mb=memory_mb,
            )
            if sandbox_result.timed_out:
                return _timeout_report(
                    mission_id=mission_id, language=language, filename=filename,
                    timeout_seconds=timeout, started_at=started_at,
                )
            stdout_bytes = sandbox_result.stdout.encode("utf-8", errors="replace")
            stderr_bytes = sandbox_result.stderr.encode("utf-8", errors="replace")
            single_container_exit_code = sandbox_result.exit_code
    exit_code = (
        single_container_exit_code
        if single_container_exit_code is not None
        else int(proc.returncode or 0)
    )
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
    artifact_smoke: dict[str, Any] | None = None,
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
        "artifact_smoke": artifact_smoke,
        "source": "dry_run",
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _artifact_smoke_failure_report(
    *,
    mission_id: str,
    language: str,
    filename: str,
    artifact_smoke: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": RQCA_SCHEMA_VERSION,
        "mission_id": mission_id,
        "verdict": "FAIL",
        "passed": False,
        "execution_type": "artifact_smoke",
        "language": language,
        "filename": filename,
        "artifact_smoke": artifact_smoke,
        "source": "artifact_smoke",
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
