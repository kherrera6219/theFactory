"""Artifact classification and offline dependency resolution for RQCA."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

#: Node built-ins, so a JS artifact importing only these is still runnable.
_NODE_BUILTIN_MODULES = frozenset({
    "assert", "buffer", "child_process", "cluster", "console", "crypto", "dns",
    "events", "fs", "http", "http2", "https", "net", "os", "path", "process",
    "querystring", "readline", "stream", "string_decoder", "timers", "tls",
    "tty", "url", "util", "v8", "vm", "worker_threads", "zlib",
})


#: Toolkits whose presence means the artifact draws a window. Running one
#: headless proves nothing: it needs a display server, and its absence is not a
#: defect in the generated code.
_GUI_TOOLKITS = frozenset({
    "pyqt5", "pyqt6", "pyside2", "pyside6", "tkinter", "kivy", "wxpython",
    "pygame", "electron", "gtk", "pygobject", "toga", "dearpygui", "arcade",
})

#: Parse-or-compile commands that prove an artifact is well-formed WITHOUT
#: needing its dependencies present or a display to draw on. This is the right
#: verification for a GUI artifact: the strongest claim honestly available.
#:
#: Every command here must also write NOTHING. `/workspace` is read-only, and
#: `python -m py_compile` emits a `__pycache__` directory beside the source --
#: which failed every *well-formed* artifact with
#: "[Errno 30] Read-only file system: '/workspace/__pycache__'", turning a check
#: for broken code into a check that broke on correct code. `ast.parse` reads
#: and parses without touching the filesystem.
_SYNTAX_ONLY_COMMANDS: dict[str, str] = {
    "python": (
        "python -c \"import ast,sys;"
        "ast.parse(open('/workspace/{filename}',encoding='utf-8').read())\""
    ),
    "javascript": "node --check /workspace/{filename}",
    "typescript": (
        "env HOME=/tmp DENO_DIR=/tmp/deno deno check --quiet /workspace/{filename}"
    ),
    "ruby": "ruby -c /workspace/{filename}",
    "php": "php -l /workspace/{filename}",
}


def _is_gui_artifact(dependencies: Any, generated_code: str) -> bool:
    """True when the artifact draws a user interface.

    Judged from the declared dependencies first, falling back to import lines in
    the source, because a specialist sometimes omits the dependency list.
    """
    declared = " ".join(str(d).lower() for d in dependencies or [])
    if any(toolkit in declared for toolkit in _GUI_TOOLKITS):
        return True
    head = "\n".join(str(generated_code or "").splitlines()[:60]).lower()
    return any(
        f"import {toolkit}" in head or f"from {toolkit}" in head or f"require('{toolkit}" in head
        for toolkit in _GUI_TOOLKITS
    )


#: Tokens that mean the artifact is a long-running server, not a CLI that exits.
_SERVER_MARKERS = frozenset({
    "fastapi", "flask", "django", "starlette", "uvicorn", "gunicorn",
    "aiohttp", "tornado", "hypercorn", "quart",
    "express", "koa", "fastify", "hapi",
    "gin-gonic", "labstack/echo", "gofiber", "actix-web", "axum", "warp",
    "spring-boot", "ktor",
})
# Bare `.listen(` / `app.run(` match EventEmitter, sockets, and many CLIs.
_SERVER_SOURCE_MARKERS = (
    "app.listen(",
    "create_server(",
    "createserver(",
    "uvicorn.run(",
    "http.server",
    "httpserver(",
    "serve_forever(",
)
_SERVER_APP_RUN_FRAMEWORKS = ("flask", "django", "quart", "fastapi")


def _is_server_artifact(dependencies: Any, generated_code: str) -> bool:
    """True when the artifact is a long-running HTTP/process server.

    Executing one as a CLI hangs until the sandbox timeout, then records FAIL
    for a process that never exited -- which is correct server behaviour.
    """
    declared = " ".join(str(d).lower() for d in dependencies or [])
    if any(marker in declared for marker in _SERVER_MARKERS):
        return True
    head = "\n".join(str(generated_code or "").splitlines()[:80]).lower()
    if any(marker in head for marker in _SERVER_SOURCE_MARKERS):
        return True
    return "app.run(" in head and any(name in head for name in _SERVER_APP_RUN_FRAMEWORKS)


def _is_library_artifact(
    generated_output: dict[str, Any] | None,
    generated_code: str,
) -> bool:
    """True when the artifact is a library/module with no program entry point.

    A library has no process to run-to-completion. Import/parse is the strongest
    honest check; executing it as a CLI is a timeout or a started_only PASS.
    """
    payload = generated_output or {}
    output_mode = str(payload.get("output_mode") or "").strip().upper()
    if output_mode in {"LIBRARY", "MODULE", "ANALYZE_ONLY"}:
        return True
    kind = str(payload.get("artifact_class") or payload.get("kind") or "").strip().lower()
    if kind in {"library", "module"}:
        return True
    code = str(generated_code or "")
    if not code.strip():
        return False
    lowered = code.lower()
    has_entry = any(
        token in lowered
        for token in (
            'if __name__ == "__main__"',
            "if __name__ == '__main__'",
            "int main(",
            "fn main(",
            "func main(",
            "public static void main(",
        )
    )
    usage = str(payload.get("usage_example") or "").strip().lower()
    usage_is_import = (
        bool(usage)
        and usage.startswith("import ")
        and " " not in usage.split("import ", 1)[-1].strip().split("\n", 1)[0]
    )
    return (not has_entry) and usage_is_import


#: Input-loop tokens strong enough to classify as interactive. `while True`
#: alone is a normal CLI/REPL and must not force syntax-only.
_INTERACTIVE_INPUT_MARKERS = (
    "msvcrt.kbhit",
    "msvcrt.getch",
    "curses.",
    "turtle.",
    "pygame.",
)


def _is_interactive_artifact(
    generated_output: dict[str, Any] | None,
    generated_code: str,
) -> bool:
    """True when the artifact is a game or input loop that should not exit 0."""
    payload = generated_output or {}
    kind = str(payload.get("artifact_class") or payload.get("kind") or "").strip().lower()
    if kind in {"interactive", "game"}:
        return True
    text = " ".join(
        [
            str(payload.get("filename") or "").strip().lower(),
            str(payload.get("usage_example") or "").strip().lower(),
            str(payload.get("title") or ""),
            "\n".join(str(generated_code or "").splitlines()[:80]).lower(),
        ]
    )
    return any(marker in text for marker in _INTERACTIVE_INPUT_MARKERS)


def _classify_artifact(
    *,
    dependencies: Any,
    generated_code: str,
    generated_output: dict[str, Any] | None = None,
) -> str:
    """Return gui | server | library | interactive | cli."""
    if _is_gui_artifact(dependencies, generated_code):
        return "gui"
    if _is_server_artifact(dependencies, generated_code):
        return "server"
    if _is_library_artifact(generated_output, generated_code):
        return "library"
    if _is_interactive_artifact(generated_output, generated_code):
        return "interactive"
    return "cli"


#: First-path prefixes treated as the language stdlib. Anything else declared
#: as a dependency is assumed to need a network fetch the sandbox cannot do.
_STDLIB_PREFIXES: dict[str, frozenset[str]] = {
    "rust": frozenset({"std", "core", "alloc"}),
    "java": frozenset({"java", "javax"}),
    "kotlin": frozenset({"kotlin", "java", "javax"}),
    "scala": frozenset({"scala", "java", "javax"}),
    "csharp": frozenset({"system"}),
    "c#": frozenset({"system"}),
    "c": frozenset({"stdio", "stdlib", "string", "math", "time", "ctype", "assert"}),
    "cpp": frozenset({"iostream", "string", "vector", "map", "stdio", "cstdlib", "cstdio"}),
    "c++": frozenset({"iostream", "string", "vector", "map", "stdio", "cstdlib", "cstdio"}),
    "julia": frozenset({
        "base", "core", "test", "linearalgebra", "statistics", "random", "printf",
        "dates", "sparsearrays", "serialization", "sockets", "unicode", "logging",
        "markdown", "sha", "uuids", "tomls", "interactiveutils", "distributed",
        "sharedarrays", "mmap", "filewatching", "base64", "crc32c", "libgit2",
        "pkg", "profile", "delimitedfiles",
    }),
    "haskell": frozenset({
        "base", "array", "binary", "bytestring", "containers", "deepseq",
        "directory", "exceptions", "filepath", "ghc-prim", "haskeline", "mtl",
        "parsec", "pretty", "process", "stm", "template-haskell", "text", "time",
        "transformers", "unix",
    }),
    "ruby": frozenset({
        "minitest", "test-unit", "test", "json", "set", "csv", "date", "time",
        "fileutils", "optparse", "securerandom", "digest", "stringio", "strscan",
        "logger", "pp", "prime", "open3", "tempfile", "tmpdir", "benchmark",
        "english", "erb", "forwardable", "ostruct", "pathname", "shellwords",
        "singleton", "timeout", "yaml", "psych", "bigdecimal", "matrix", "racc",
        "rake", "net", "uri", "socket", "zlib", "etc", "io", "objspace", "ripper",
        "coverage", "monitor", "observer", "abbrev", "base64", "delegate",
    }),
    "r": frozenset({
        "base", "stats", "utils", "methods", "graphics", "grdevices", "datasets",
        "tools", "parallel", "grid", "splines", "stats4", "compiler", "tcltk",
    }),
}


#: Test frameworks per language. A declared dependency matching one of these is
#: *test-only* unless the artifact's own source references it.
_TEST_FRAMEWORK_TOKENS: dict[str, tuple[str, ...]] = {
    "python": ("pytest", "hypothesis"),
    "javascript": ("vitest", "jest", "mocha", "chai"),
    "typescript": ("vitest", "jest", "mocha", "chai", "ts-jest"),
    "ruby": ("rspec", "minitest", "test-unit"),
    "php": ("phpunit",),
    "r": ("testthat",),
    "julia": ("test",),
    "java": ("junit", "hamcrest", "mockito", "assertj", "testng"),
    "kotlin": ("kotlin-test", "kotlin.test", "junit", "kotest", "mockk"),
    "scala": ("scalatest", "munit", "junit", "scalacheck", "specs2"),
    "csharp": ("xunit", "nunit", "mstest", "microsoft.net.test.sdk"),
    "c#": ("xunit", "nunit", "mstest", "microsoft.net.test.sdk"),
    "haskell": ("hspec", "hunit", "quickcheck", "tasty"),
    "go": ("testify",),
}


def _split_test_dependencies(
    language: str, dependencies: Any, code: str
) -> tuple[list[str], list[str]]:
    """Return ``(runtime_dependencies, test_only_dependencies)``."""
    names = [str(d).strip() for d in dependencies or [] if str(d).strip()]
    tokens = _TEST_FRAMEWORK_TOKENS.get(str(language or "").strip().lower(), ())
    if not tokens:
        return names, []
    lowered_code = str(code or "").lower()
    runtime: list[str] = []
    test_only: list[str] = []
    for name in names:
        lowered = name.lower()
        segments = {part for part in re.split(r"[.:/@\s]+", lowered) if part}
        token = next(
            (t for t in tokens if t in segments or lowered.startswith(t) or f"-{t}" in lowered),
            None,
        )
        if token is None:
            runtime.append(name)
            continue
        spellings = {token, token.replace("-", "."), token.replace("-", "_")}
        referenced = any(
            re.search(rf"(?<![a-z0-9_]){re.escape(spelling)}(?![a-z0-9_])", lowered_code)
            for spelling in spellings
        )
        (runtime if referenced else test_only).append(name)
    return runtime, test_only


def _provisioned_package_index(
    provisioning_manifest: Mapping[str, Any] | None,
) -> tuple[set[str], dict[str, str]]:
    """Return ``(provisioned_names, unmet_reasons)`` from a provisioning manifest."""
    if not isinstance(provisioning_manifest, Mapping):
        return set(), {}
    provisioned: set[str] = set()
    reasons: dict[str, str] = {}

    def _norm_keys(raw_name: Any) -> set[str]:
        s = str(raw_name or "").strip().lower()
        if not s:
            return set()
        base = s.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0].strip()
        return {s, base, base.replace("_", "-"), base.replace("-", "_")}

    for raw in provisioning_manifest.get("provisioned_packages") or []:
        provisioned.update(_norm_keys(raw))
    for pkg in provisioning_manifest.get("packages") or []:
        if not isinstance(pkg, Mapping):
            continue
        name = pkg.get("name")
        status = str(pkg.get("status") or "").strip().lower()
        reason = str(pkg.get("reason") or status or "not_in_registry").strip()
        if status == "provisioned":
            provisioned.update(_norm_keys(name))
        else:
            for key in _norm_keys(name):
                reasons.setdefault(key, reason)
    raw_reasons = provisioning_manifest.get("unmet_reasons")
    if isinstance(raw_reasons, Mapping):
        for k, v in raw_reasons.items():
            for key in _norm_keys(k):
                reasons.setdefault(key, str(v or "not_in_registry"))
    return provisioned, reasons


def classify_unmet_dependencies(
    language: str,
    dependencies: Any,
    provisioning_manifest: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Map each unmet dependency to not_in_registry, needs_build, or blocked_by_policy."""
    unmet = _unmet_dependencies(
        language, dependencies, provisioning_manifest=provisioning_manifest
    )
    _, known_reasons = _provisioned_package_index(provisioning_manifest)
    if (
        isinstance(provisioning_manifest, Mapping)
        and provisioning_manifest.get("policy_allowed") is False
    ):
        default_reason = "blocked_by_policy"
    else:
        default_reason = "not_in_registry"
    result: dict[str, str] = {}
    for dep in unmet:
        low = dep.lower()
        base = low.split("==")[0].split("[")[0].strip()
        reason = (
            known_reasons.get(low)
            or known_reasons.get(base)
            or known_reasons.get(base.replace("_", "-"))
            or default_reason
        )
        if reason not in {"not_in_registry", "needs_build", "blocked_by_policy"}:
            reason = default_reason
        result[dep] = reason
    return result


def _unmet_dependencies(
    language: str,
    dependencies: Any,
    provisioning_manifest: Mapping[str, Any] | None = None,
) -> list[str]:
    """Dependencies the offline sandbox cannot provide."""
    names = [str(d).strip() for d in dependencies or [] if str(d).strip()]
    if not names:
        return []
    provisioned, _ = _provisioned_package_index(provisioning_manifest)
    if provisioned:
        names = [
            n
            for n in names
            if n.lower() not in provisioned
            and n.split("==")[0].split("[")[0].strip().lower() not in provisioned
            and n.split("==")[0].split("[")[0].strip().lower().replace("_", "-") not in provisioned
        ]
        if not names:
            return []
    normalized = str(language or "").strip().lower()

    if normalized == "python":
        import sys  # noqa: PLC0415

        stdlib = getattr(sys, "stdlib_module_names", frozenset())
        return [
            n
            for n in names
            if n.split(".")[0].split("[")[0].lower() not in {m.lower() for m in stdlib}
        ]

    if normalized == "go":
        return [n for n in names if "." in n.split("/")[0]]

    if normalized in {"javascript", "typescript"}:
        return [
            n
            for n in names
            if n.split("/")[0].removeprefix("node:") not in _NODE_BUILTIN_MODULES
        ]

    prefixes = _STDLIB_PREFIXES.get(normalized)
    if prefixes is not None:
        unmet: list[str] = []
        for name in names:
            first = name.split(".")[0].split("/")[0].split("::")[0].lower()
            if first not in prefixes:
                unmet.append(name)
        return unmet

    return list(names)
