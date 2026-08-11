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
    run_in_sandbox,
    workspace_root,
)

RQCA_SCHEMA_VERSION = "runtime_qc_report.v1"

# --- Language runtimes -----------------------------------------------------
#
# One table per language: the image to run in, and the complete shell snippet
# that turns the artifact into a running program. `{filename}` is the generated
# file, `{stem}` its basename without extension (JVM languages need the class
# name). Anything not listed here returns DRY_RUN rather than executing.
#
# Constraints every command must respect, all of them enforced by
# SANDBOX_SECURITY_FLAGS and each one having broken a language during bring-up:
#   * /workspace is READ-ONLY -- build output and caches go under /tmp
#     (SANDBOX_BUILD_DIR), the only writable+executable location.
#   * There is no network, so nothing may fetch a compiler, package or toolchain
#     at run time.
#   * HOME is not writable, so toolchains that scribble into it (go, ghc,
#     kotlinc, julia, R, zig) need it pointed at /tmp explicitly.
#
# Every entry below was verified by executing a hello-world through the real
# sandbox; see test_every_live_language_has_a_runtime for the guard that keeps
# this table and _ALL_LIVE_LANGUAGES in step.
#
# A language listed here but unable to run is worse than one that is absent: it
# yields FAIL, and RQCA_ENFORCEMENT_ENABLED turns FAIL into a blocked mission,
# whereas an absent language degrades to an honest DRY_RUN.
#
# NOT PRESENT YET:
#   csharp/c# -- its config called `dotnet-script`, absent from
#     mcr.microsoft.com/dotnet/sdk:8.0 and uninstallable offline.
#
# LICENCE-FREE SUBSTITUTES (matlab, mathematica): the vendor runtimes need a
# paid licence (MathWorks) or network activation (Wolfram Engine), and this
# product must run with no external requirements, so neither is an option at any
# price. They run on open-source subset interpreters instead. That is honest
# because of what this gate is actually for: catching a specialist that silently
# emitted Python under the target language's label. Detecting that needs a
# *parser for the language*, not bit-exact vendor semantics -- and both subsets
# reject Python source. Entries carry `runtime_substitute` and `verified_scope`,
# which are copied onto every report so a pass can never be read as full vendor
# compatibility.
_LANGUAGE_RUNTIMES: dict[str, dict[str, Any]] = {
    # -- interpreted ---------------------------------------------------------
    "python": {
        "base_image": "python:3.11-slim",
        "run_command": "python /workspace/{filename}",
    },
    "javascript": {
        "base_image": "node:20-slim",
        "run_command": "node /workspace/{filename}",
    },
    "typescript": {
        # Deno, not node: node cannot parse type annotations, so every genuinely
        # typed artifact FAILED and only TypeScript that happened to be valid
        # JavaScript passed. Deno also type-checks, which is a stronger check
        # than stripping types would give.
        "base_image": "denoland/deno:latest@sha256:b429777c3dcff34a6488f365a1537db1640b2d48379b60f5e6206be034472463",
        "run_command": (
            "env HOME=/tmp DENO_DIR=/tmp/deno deno run --quiet /workspace/{filename}"
        ),
    },
    "ruby": {
        "base_image": "ruby:3.3-slim",
        "run_command": "ruby /workspace/{filename}",
    },
    "php": {
        # The grep guard is load bearing. PHP treats a file with no `<?php` tag
        # as plain text and simply echoes it, exit 0 -- so a Python artifact
        # renamed .php PASSED, the exact substitution this gate exists to catch.
        # Found by the negative-control audit, not by review.
        "base_image": "php:8.3-cli",
        "run_command": (
            "grep -qF '<?php' /workspace/{filename} "
            "&& php -l /workspace/{filename} > /dev/null "
            "&& php /workspace/{filename}"
        ),
    },
    "r": {
        "base_image": "r-base:4.4.1",
        "run_command": "env HOME=/tmp Rscript /workspace/{filename}",
    },
    "julia": {
        "base_image": "julia:1.10",
        "run_command": (
            "env HOME=/tmp JULIA_DEPOT_PATH=/tmp/.julia julia /workspace/{filename}"
        ),
    },
    "ocaml": {
        # The opam switch is not on PATH once the image entrypoint is bypassed.
        "base_image": "ocaml/opam:debian-12-ocaml-5.1@sha256:441d5fcf1d8d9d1ffab06b651f6bf9f87c4562c3b9d7adf774dbb876d503acc5",
        "run_command": (
            "export HOME=/tmp; export PATH=/home/opam/.opam/5.1/bin:$PATH; "
            "ocaml /workspace/{filename}"
        ),
    },
    # -- compiled ------------------------------------------------------------
    "c": {
        "base_image": "gcc:13-bookworm",
        "run_command": (
            "gcc -Wall -Wextra -o /tmp/a.out /workspace/{filename} && /tmp/a.out"
        ),
    },
    "cpp": {
        "base_image": "gcc:13-bookworm",
        "run_command": (
            "g++ -std=c++20 -Wall -Wextra -o /tmp/a.out /workspace/{filename} && /tmp/a.out"
        ),
    },
    "c++": {
        "base_image": "gcc:13-bookworm",
        "run_command": (
            "g++ -std=c++20 -Wall -Wextra -o /tmp/a.out /workspace/{filename} && /tmp/a.out"
        ),
    },
    "rust": {
        "base_image": "rust:1.78-slim-bookworm",
        "run_command": "rustc /workspace/{filename} -o /tmp/a.out && /tmp/a.out",
    },
    "go": {
        "base_image": "golang:1.22-bookworm",
        "run_command": (
            "env HOME=/tmp GOCACHE=/tmp/gocache "
            "go build -o /tmp/a.out /workspace/{filename} && /tmp/a.out"
        ),
    },
    "zig": {
        "base_image": "euantorano/zig:master@sha256:fc57f6939ebd938b0219b78f3f4dbd8bdb3ebb52ee3d756d2abbbfae0057f3bb",
        "run_command": (
            "env HOME=/tmp zig run /workspace/{filename} "
            "--cache-dir /tmp/zig-cache --global-cache-dir /tmp/zig-global"
        ),
    },
    "haskell": {
        "base_image": "haskell:9.6-slim",
        "run_command": (
            "env HOME=/tmp ghc -outputdir /tmp -o /tmp/a.out /workspace/{filename} "
            "&& /tmp/a.out"
        ),
    },
    # -- JVM: the entry class is the filename stem ---------------------------
    "java": {
        "base_image": "eclipse-temurin:21-jdk",
        "run_command": "javac -d /tmp /workspace/{filename} && java -cp /tmp {stem}",
    },
    "kotlin": {
        "base_image": "zenika/kotlin@sha256:6aa73e11c07b361e4cf068dce3745a4bc9f8b0b7d8d0b8cbbcc385539184d46a",
        "run_command": (
            "env HOME=/tmp kotlinc /workspace/{filename} -include-runtime -d /tmp/a.jar "
            "&& java -jar /tmp/a.jar"
        ),
    },
    # -- licence-free subset runtimes ----------------------------------------
    "matlab": {
        # GNU Octave. Verified 2026-08-11 under the real sandbox flags: runs a
        # MATLAB hello-world, and rejects a realistic Python-fallback artifact
        # with a parse error and exit 1.
        "base_image": "gnuoctave/octave:9.2.0@sha256:100d394c57b86469748d26ddafcf73a1074338a66dabcababe2e4e05146772b9",
        "run_command": (
            "env HOME=/tmp octave --no-gui --no-history -q /workspace/{filename}"
        ),
        "runtime_substitute": "octave",
        "verified_scope": "matlab-subset",
    },
    "mathematica": {
        # Mathics3. `--file` is required: `-script` silently does nothing.
        #
        # failure_patterns is not optional here. Wolfram is an expression
        # language, so an undefined symbol evaluates to itself rather than
        # erroring: fed Python source, mathics printed Syntax::sntxf and still
        # exited 0. An exit-code-only verdict would therefore return a FALSE
        # PASS -- strictly worse than the DRY_RUN it replaces, because it would
        # assert a verification that never happened.
        "base_image": "mathicsorg/mathics:latest@sha256:4c6b5cbe02f38ed8980fd4acbac91bb5ac8f3538cafb8c43150d30ca3090fb4e",
        "run_command": "env HOME=/tmp mathics --quiet --file /workspace/{filename}",
        "runtime_substitute": "mathics",
        "verified_scope": "wolfram-language-subset",
        "failure_patterns": ["Syntax::"],
    },
    "scala": {
        "base_image": "sbtscala/scala-sbt:eclipse-temurin-jammy-21.0.2_13_1.9.9_3.4.0@sha256:6a1a1c8f9881cf4d2b9963cb9945e6209087538e79d9237072c6ef09ca4c3ef6",
        "run_command": (
            "env HOME=/tmp scalac -d /tmp /workspace/{filename} "
            "&& env HOME=/tmp scala -cp /tmp {stem}"
        ),
    },
}

# Every image outside Docker Official Images is pinned by digest above.
# `repo:tag@sha256:...` keeps the tag readable while making the daemon resolve
# the exact content: three of them were floating tags (`:master`, two `:latest`)
# and these images are the containment for untrusted generated code, so a
# silently-moved tag changes what executes it. Re-pin deliberately when
# upgrading -- `docker buildx imagetools inspect <ref> --format '{{.Manifest.Digest}}'`.
#
#: Images not published by Docker Official Images or the language's own vendor.
#: Recorded on every report so a surprising verdict can be traced to a
#: third-party toolchain rather than to the generated code. These languages
#: publish no official image; the sandbox's containment (no network, no
#: capabilities, read-only rootfs) applies to them exactly as to the rest.
_UNOFFICIAL_IMAGE_LANGUAGES = frozenset({"kotlin", "scala", "zig", "ocaml"})

_ALL_LIVE_LANGUAGES = frozenset(_LANGUAGE_RUNTIMES)
# Aliased to the shared sandbox ceilings (UPG-50) so RQCA and behavioural
# equivalence cannot drift apart on resource limits.
_MAX_TIMEOUT_SECONDS = _SHARED_MAX_TIMEOUT_SECONDS
_MAX_MEMORY_MB = _SHARED_MAX_MEMORY_MB
_HTML_EXTENSIONS = {"html", "htm"}
_SCRIPT_EXTENSIONS = {"js", "mjs", "cjs", "ts", "tsx", "jsx"}
_NODE_CHECK_LANGUAGES = {"javascript", "typescript"}


def _compose_available() -> bool:
    """True when the docker CLI has a working `compose` subcommand.

    Only consulted on the multi-container branch, so the subprocess cost is paid
    at most once per such mission.
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    docker_bin = shutil.which("docker")
    if not docker_bin:
        return False
    try:
        completed = subprocess.run(  # noqa: S603
            [docker_bin, "compose", "version"],
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


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
    # Fill in the runtime for this language when the manifest does not pin one.
    # Both the image and the command must come from the same entry: supplying an
    # image without its command (or vice versa) is how a JavaScript artifact
    # ended up running `node` inside the Python image.
    runtime = _LANGUAGE_RUNTIMES.get(normalized_language)
    if runtime is not None:
        stem = Path(filename).stem
        testdata_manifest = {**testdata_manifest}
        testdata_manifest.setdefault("base_image", runtime["base_image"])
        testdata_manifest.setdefault(
            "run_command", runtime["run_command"].format(filename=filename, stem=stem)
        )
        for carried in ("failure_patterns", "runtime_substitute", "verified_scope"):
            if runtime.get(carried) is not None:
                testdata_manifest.setdefault(carried, runtime[carried])

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

        if multi_container and testdata_manifest.get("services") and not _compose_available():
            # The compose plugin is not shipped in the orchestrator image (see
            # services/orchestrator/Dockerfile for why). Say so plainly rather
            # than failing deep in a subprocess with "docker: 'compose' is not a
            # docker command", which reads like a defect in the artifact.
            return _dry_run_report(
                mission_id=mission_id,
                language=language,
                filename=filename,
                testdata_manifest=testdata_manifest,
                reason=(
                    "Multi-container runtime QC needs the docker compose plugin, "
                    "which is not installed in the orchestrator image."
                ),
            )

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
    # Some runtimes report a fatal problem without a non-zero exit code, so the
    # exit code alone is not a verdict. Mathics is the case that forced this:
    # Wolfram evaluates an undefined symbol to itself instead of erroring, so
    # Python source produced Syntax::sntxf messages and exit 0. Treating that as
    # a pass would assert a verification that never happened.
    matched_failure_pattern: str | None = None
    raw_patterns = testdata_manifest.get("failure_patterns") or []
    if isinstance(raw_patterns, (list, tuple)):
        combined_output = (
            stdout_bytes.decode("utf-8", errors="replace")
            + stderr_bytes.decode("utf-8", errors="replace")
        )
        for pattern in raw_patterns:
            if str(pattern) and str(pattern) in combined_output:
                matched_failure_pattern = str(pattern)
                passed = False
                break
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
        # Recorded so a surprising verdict can be traced to a third-party
        # toolchain image rather than assumed to be a defect in the artifact.
        "base_image_official": language.strip().lower() not in _UNOFFICIAL_IMAGE_LANGUAGES,
        # Present only when a licence-free subset interpreter stood in for the
        # vendor runtime, so nothing downstream can read this pass as full
        # vendor compatibility.
        "runtime_substitute": testdata_manifest.get("runtime_substitute"),
        "verified_scope": testdata_manifest.get("verified_scope") or language.strip().lower(),
        "failed_on_pattern": matched_failure_pattern,
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
