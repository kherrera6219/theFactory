"""toolchains.py — Compiler/linter pre-flight check wrappers for Pod Workers.

Provides language-specific toolchain checks (Pod A/B/C/D) before submitting LogicNodes to verification streams.
Falls back gracefully when local compilers are not present on PATH.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

TOOLCHAINS_ENABLED: bool = (
    os.getenv("POD_WORKER_TOOLCHAINS_ENABLED", "true").strip().lower()
    in {"1", "true", "yes", "on"}
)


@dataclass(frozen=True, slots=True)
class ToolchainCheckResult:
    language: str
    passed: bool
    compiler_found: bool
    output: str


def run_toolchain_check(language: str, source_code: str) -> ToolchainCheckResult:
    """Run pre-flight syntax/compiler check for *language* using available local toolchains.

    Returns ToolchainCheckResult with compiler_found=False if toolchain binary is absent.
    """
    lang = language.strip().lower()
    if not TOOLCHAINS_ENABLED or not source_code or not source_code.strip():
        return ToolchainCheckResult(language=lang, passed=True, compiler_found=False, output="Toolchain disabled or empty source")

    with tempfile.TemporaryDirectory() as tmpdir:
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
        file_path = os.path.join(tmpdir, f"main{ext}")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(source_code)

        if lang == "python":
            if shutil.which("python") or shutil.which("python3"):
                py_bin = "python3" if shutil.which("python3") else "python"
                res = subprocess.run([py_bin, "-m", "py_compile", file_path], capture_output=True, text=True, check=False)
                return ToolchainCheckResult(language=lang, passed=(res.returncode == 0), compiler_found=True, output=res.stderr or res.stdout)

        elif lang in {"javascript", "typescript"}:
            if shutil.which("node"):
                res = subprocess.run(["node", "--check", file_path], capture_output=True, text=True, check=False)
                return ToolchainCheckResult(language=lang, passed=(res.returncode == 0), compiler_found=True, output=res.stderr or res.stdout)

        elif lang == "go":
            if shutil.which("go"):
                res = subprocess.run(["go", "vet", file_path], capture_output=True, text=True, check=False)
                return ToolchainCheckResult(language=lang, passed=(res.returncode == 0), compiler_found=True, output=res.stderr or res.stdout)

        elif lang == "rust":
            if shutil.which("rustc"):
                res = subprocess.run(["rustc", "--parse-only", file_path], capture_output=True, text=True, check=False)
                return ToolchainCheckResult(language=lang, passed=(res.returncode == 0), compiler_found=True, output=res.stderr or res.stdout)

        elif lang in {"c", "cpp"}:
            cc = "g++" if lang == "cpp" else "gcc"
            if shutil.which(cc):
                res = subprocess.run([cc, "-fsyntax-only", file_path], capture_output=True, text=True, check=False)
                return ToolchainCheckResult(language=lang, passed=(res.returncode == 0), compiler_found=True, output=res.stderr or res.stdout)

        elif lang == "java":
            if shutil.which("javac"):
                res = subprocess.run(["javac", file_path], capture_output=True, text=True, check=False)
                return ToolchainCheckResult(language=lang, passed=(res.returncode == 0), compiler_found=True, output=res.stderr or res.stdout)

        elif lang == "haskell":
            if shutil.which("ghc"):
                res = subprocess.run(["ghc", "-fno-code", file_path], capture_output=True, text=True, check=False)
                return ToolchainCheckResult(language=lang, passed=(res.returncode == 0), compiler_found=True, output=res.stderr or res.stdout)

        elif lang == "ocaml":
            if shutil.which("ocamlc"):
                res = subprocess.run(["ocamlc", "-c", file_path], capture_output=True, text=True, check=False)
                return ToolchainCheckResult(language=lang, passed=(res.returncode == 0), compiler_found=True, output=res.stderr or res.stdout)

    return ToolchainCheckResult(language=lang, passed=True, compiler_found=False, output="Compiler not installed on local host")
