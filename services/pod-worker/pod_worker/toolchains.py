"""toolchains.py — Compiler/linter pre-flight check wrappers for Pod Workers.

Provides language-specific toolchain checks (Pod A/B/C/D) before submitting LogicNodes to verification streams.
Falls back gracefully when local compilers are not present on PATH.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)

TOOLCHAINS_ENABLED: bool = (
    os.getenv("POD_WORKER_TOOLCHAINS_ENABLED", "true").strip().lower()
    in {"1", "true", "yes", "on"}
)
TOOLCHAIN_TIMEOUT_SECONDS: float = max(
    1.0,
    float(os.getenv("POD_WORKER_TOOLCHAIN_TIMEOUT_SECONDS", "15")),
)


@dataclass(frozen=True, slots=True)
class ToolchainCheckResult:
    language: str
    passed: bool
    compiler_found: bool
    output: str


def _safe_temp_filename(filename: str | None, fallback_ext: str) -> str:
    """Validate and resolve a single basename filename inside the temp workspace."""
    if not filename:
        return f"main{fallback_ext}"
    raw = str(filename).strip()
    if not raw:
        return f"main{fallback_ext}"
    if "\x00" in raw or raw.startswith(("/", "\\")) or ":" in raw:
        raise ValueError(f"invalid toolchain filename: {filename!r}")
    parts = [part for part in re.split(r"[/\\]+", raw) if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise ValueError(f"invalid toolchain filename traversal: {filename!r}")
    return parts[-1]


def _run_toolchain_command(argv: list[str], language: str) -> ToolchainCheckResult:
    """Execute a local syntax/lint command with bounded timeout."""
    try:
        res = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            timeout=TOOLCHAIN_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        LOGGER.warning("toolchain check timed out after %ss for language=%s", TOOLCHAIN_TIMEOUT_SECONDS, language)
        return ToolchainCheckResult(
            language=language,
            passed=False,
            compiler_found=True,
            output=f"Toolchain check timed out after {TOOLCHAIN_TIMEOUT_SECONDS:g}s",
        )
    return ToolchainCheckResult(
        language=language,
        passed=(res.returncode == 0),
        compiler_found=True,
        output=res.stderr or res.stdout,
    )


def run_toolchain_check(language: str, source_code: str, filename: str | None = None) -> ToolchainCheckResult:
    """Run pre-flight syntax/compiler check for *language* using available local toolchains.

    Returns ToolchainCheckResult with compiler_found=False if toolchain binary is absent.
    """
    lang = language.strip().lower()
    if not TOOLCHAINS_ENABLED or not source_code or not source_code.strip():
        return ToolchainCheckResult(language=lang, passed=True, compiler_found=False, output="Toolchain disabled or empty source")

    ext_map = {
        "python": ".py",
        "javascript": ".js",
        "typescript": ".ts",
        "ruby": ".rb",
        "php": ".php",
        "c": ".c",
        "cpp": ".cpp",
        "rust": ".rs",
        "go": ".go",
        "zig": ".zig",
        "java": ".java",
        "csharp": ".cs",
        "scala": ".scala",
        "kotlin": ".kt",
        "haskell": ".hs",
        "ocaml": ".ml",
        "julia": ".jl",
    }
    ext = ext_map.get(lang, ".txt")
    file_name = _safe_temp_filename(filename, ext)
    if lang == "java":
        m = re.search(r"public\s+class\s+(\w+)", source_code)
        if m:
            file_name = f"{m.group(1)}.java"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir).resolve()
        candidate_path = (tmp_root / file_name).resolve()
        if not candidate_path.is_relative_to(tmp_root):
            raise ValueError(f"filename escapes temporary workspace: {filename!r}")
        file_path = str(candidate_path)
        candidate_path.write_text(source_code, encoding="utf-8")

        if lang == "python":
            if shutil.which("python") or shutil.which("python3"):
                py_bin = "python3" if shutil.which("python3") else "python"
                return _run_toolchain_command([py_bin, "-m", "py_compile", file_path], lang)

        elif lang == "javascript":
            if shutil.which("node"):
                return _run_toolchain_command(["node", "--check", file_path], lang)

        elif lang == "typescript":
            if shutil.which("tsc"):
                return _run_toolchain_command(["tsc", "--noEmit", file_path], lang)

        elif lang == "go":
            if shutil.which("go"):
                return _run_toolchain_command(["go", "vet", file_path], lang)

        elif lang == "rust":
            if shutil.which("rustc"):
                return _run_toolchain_command(
                    ["rustc", "--crate-type=lib", "--emit=metadata", "--out-dir", tmpdir, file_path],
                    lang,
                )

        elif lang in {"c", "cpp"}:
            cc = "g++" if lang == "cpp" else "gcc"
            if shutil.which(cc):
                return _run_toolchain_command([cc, "-fsyntax-only", file_path], lang)

        elif lang == "java":
            if shutil.which("javac"):
                return _run_toolchain_command(["javac", file_path], lang)

        elif lang == "haskell":
            if shutil.which("ghc"):
                return _run_toolchain_command(["ghc", "-fno-code", file_path], lang)

        elif lang == "ocaml":
            if shutil.which("ocamlc"):
                return _run_toolchain_command(["ocamlc", "-c", file_path], lang)

    return ToolchainCheckResult(language=lang, passed=True, compiler_found=False, output="Compiler not installed on local host")
