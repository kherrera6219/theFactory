"""Pod-worker toolchain preflight — disabled, missing compiler, mocked compilers."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

from pod_worker import toolchains  # noqa: E402


def test_disabled_or_empty_source_skips_compiler(monkeypatch) -> None:
    monkeypatch.setattr(toolchains, "TOOLCHAINS_ENABLED", False)
    skipped = toolchains.run_toolchain_check("python", "print(1)")
    assert skipped.passed is True
    assert skipped.compiler_found is False
    monkeypatch.setattr(toolchains, "TOOLCHAINS_ENABLED", True)
    empty = toolchains.run_toolchain_check("python", "   ")
    assert empty.compiler_found is False


def test_missing_compiler_is_not_a_failure(monkeypatch) -> None:
    monkeypatch.setattr(toolchains, "TOOLCHAINS_ENABLED", True)
    monkeypatch.setattr(toolchains.shutil, "which", lambda _name: None)
    result = toolchains.run_toolchain_check("rust", "fn main() {}")
    assert result.passed is True
    assert result.compiler_found is False
    assert "not installed" in result.output


def test_python_and_node_and_go_invoke_expected_argv(monkeypatch) -> None:
    monkeypatch.setattr(toolchains, "TOOLCHAINS_ENABLED", True)
    captured: list[list[str]] = []

    def _which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in {"python3", "python", "node", "go"} else None

    def _run(argv, capture_output=True, text=True, check=False):
        captured.append(list(argv))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(toolchains.shutil, "which", _which)
    monkeypatch.setattr(toolchains.subprocess, "run", _run)
    py = toolchains.run_toolchain_check("python", "print(1)\n")
    js = toolchains.run_toolchain_check("javascript", "console.log(1)\n")
    go = toolchains.run_toolchain_check("go", "package main\n")
    assert py.compiler_found and py.passed
    assert js.compiler_found and js.passed
    assert go.compiler_found and go.passed
    assert any(cmd[:3] == ["python3", "-m", "py_compile"] or cmd[:3] == ["python", "-m", "py_compile"] for cmd in captured)
    assert any(cmd[:2] == ["node", "--check"] for cmd in captured)
    assert any(cmd[:2] == ["go", "vet"] for cmd in captured)


def test_compiled_language_checks_use_syntax_only_flags(monkeypatch) -> None:
    monkeypatch.setattr(toolchains, "TOOLCHAINS_ENABLED", True)
    seen: list[list[str]] = []

    def _which(name: str) -> str | None:
        return f"/usr/bin/{name}"

    def _run(argv, **_kwargs):
        seen.append(list(argv))
        return SimpleNamespace(returncode=1, stdout="", stderr="syntax error")

    monkeypatch.setattr(toolchains.shutil, "which", _which)
    monkeypatch.setattr(toolchains.subprocess, "run", _run)
    rust = toolchains.run_toolchain_check("rust", "fn main() {")
    c = toolchains.run_toolchain_check("c", "int main() {")
    java = toolchains.run_toolchain_check("java", "class X {")
    hs = toolchains.run_toolchain_check("haskell", "main =")
    ocaml = toolchains.run_toolchain_check("ocaml", "let x =")
    assert rust.passed is False and rust.compiler_found
    assert c.passed is False
    assert java.passed is False
    assert hs.passed is False
    assert ocaml.passed is False
    assert any("--parse-only" in cmd for cmd in seen)
    assert any("-fsyntax-only" in cmd for cmd in seen)
    assert any(cmd[0] == "javac" for cmd in seen)
    assert any("-fno-code" in cmd for cmd in seen)
    assert any(cmd[:2] == ["ocamlc", "-c"] for cmd in seen)
