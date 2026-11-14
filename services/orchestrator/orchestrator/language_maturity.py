"""Per-language Factory maturity matrix computed from live runtime tables (Phase 5).

Reads directly from ``rqca_agent``, ``dependency_provisioner``, ``aim_generator``,
``pod_worker.treesitter_extractor``, and ``equivalence_execution`` so documentation,
PM PORT recommendations, and scripts share one canonical source of truth.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from .aim_generator import _SUPPORTED_EXTRACTOR_LANGUAGES
from .dependency_provisioner import _ECOSYSTEM_BY_LANGUAGE
from .equivalence_execution import SUPPORTED_LANGUAGES as EQUIVALENCE_CALL_LANGUAGES
from .rqca_agent import (
    _DEFAULT_TEST_COMMAND_TEMPLATES,
    _LANGUAGE_RUNTIMES,
    _UNOFFICIAL_IMAGE_LANGUAGES,
    _VENDORED_TEST_RUNTIMES,
)

# Languages in the 20-key pod model rendered in predictable display order.
_CANONICAL_LANGUAGES: tuple[str, ...] = (
    "python",
    "javascript",
    "typescript",
    "go",
    "rust",
    "java",
    "csharp",
    "kotlin",
    "scala",
    "c",
    "cpp",
    "php",
    "ruby",
    "r",
    "julia",
    "haskell",
    "ocaml",
    "zig",
    "matlab",
    "mathematica",
)

_NATIVE_AST_LANGUAGES = frozenset({"python", "javascript", "typescript", "java", "go", "haskell", "ocaml", "julia"})


def _treesitter_languages() -> frozenset[str]:
    try:
        mod = importlib.import_module("pod_worker.treesitter_extractor")
        langs = getattr(mod, "TREESITTER_SUPPORTED_LANGUAGES", frozenset())
        return frozenset(str(x).lower() for x in langs)
    except Exception:
        # Local dev imports pod_worker via sibling path when not yet on sys.path.
        from .workspace_indexer import _ensure_pod_worker_on_path

        if _ensure_pod_worker_on_path():
            try:
                mod = importlib.import_module("pod_worker.treesitter_extractor")
                langs = getattr(mod, "TREESITTER_SUPPORTED_LANGUAGES", frozenset())
                return frozenset(str(x).lower() for x in langs)
            except Exception:
                return frozenset()
        return frozenset()


def get_language_maturity_table() -> list[dict[str, Any]]:
    """Return one maturity record per supported Factory language from live code tables."""
    ts_langs = _treesitter_languages()
    rows: list[dict[str, Any]] = []

    for lang in _CANONICAL_LANGUAGES:
        runtime = _LANGUAGE_RUNTIMES.get(lang)
        vendored_test = _VENDORED_TEST_RUNTIMES.get(lang)
        builtin_runner = _DEFAULT_TEST_COMMAND_TEMPLATES.get(lang)
        dep_ecosystem = _ECOSYSTEM_BY_LANGUAGE.get(lang)
        extractor_supported = lang in _SUPPORTED_EXTRACTOR_LANGUAGES
        has_treesitter = lang in ts_langs
        has_call_equiv = lang in EQUIVALENCE_CALL_LANGUAGES
        unofficial_image = lang in _UNOFFICIAL_IMAGE_LANGUAGES
        runtime_sub = runtime.get("runtime_substitute") if isinstance(runtime, dict) else None

        if lang == "python":
            extraction_mode = "ast + regex"
        elif lang in _NATIVE_AST_LANGUAGES and has_treesitter:
            extraction_mode = "ast/structural + tree-sitter"
        elif has_treesitter:
            extraction_mode = "tree-sitter/structural + regex"
        elif extractor_supported:
            extraction_mode = "regex"
        else:
            extraction_mode = "unsupported"

        if vendored_test is not None:
            test_runner_support = f"vendored ({vendored_test['image']})"
        elif builtin_runner is not None:
            test_runner_support = "stdlib/runtime built-in"
        elif lang in {"go", "rust"}:
            test_runner_support = f"toolchain built-in ({'go test' if lang == 'go' else 'cargo test'})"
        else:
            test_runner_support = "compile/run only"

        has_runtime = runtime is not None
        has_tests = vendored_test is not None or builtin_runner is not None or lang in {"go", "rust"}
        has_deps = dep_ecosystem is not None

        if has_runtime and has_tests and has_deps and has_call_equiv:
            maturity_tier = "Tier 1 — Full Production"
            port_score = 100
        elif has_runtime and has_tests and has_deps:
            maturity_tier = "Tier 1 — Full Production"
            port_score = 90
        elif has_runtime and has_tests and not unofficial_image and not runtime_sub:
            maturity_tier = "Tier 2 — Standard"
            port_score = 75
        elif has_runtime and (not runtime_sub):
            maturity_tier = "Tier 2 — Standard (no dep cache)" if not has_deps else "Tier 2 — Standard"
            port_score = 65
        else:
            maturity_tier = "Tier 3 — Subset / Advisory"
            port_score = 35

        notes: list[str] = []
        if unofficial_image:
            notes.append("third-party community runtime image")
        if runtime_sub:
            notes.append(f"open-source substitute: {runtime_sub}")
        if has_call_equiv:
            notes.append("direct-call + process equivalence")
        elif has_runtime:
            notes.append("process/CLI equivalence")

        rows.append(
            {
                "language": lang,
                "maturity_tier": maturity_tier,
                "port_score": port_score,
                "extraction_mode": extraction_mode,
                "sandbox_runtime": str(runtime.get("base_image")) if runtime else None,
                "test_runner_support": test_runner_support,
                "dependency_ecosystem": dep_ecosystem or "none",
                "behavioural_equivalence": (
                    "direct-call + process" if has_call_equiv else ("process/CLI" if has_runtime else "none")
                ),
                "unofficial_image": unofficial_image,
                "runtime_substitute": runtime_sub,
                "notes": "; ".join(notes),
            }
        )

    return rows


def recommend_port_target_languages(
    *,
    source_language: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return ranked PORT target languages backed by Tier 1 / Tier 2 sandbox support."""
    src = str(source_language or "").strip().lower()
    rows = [
        row
        for row in get_language_maturity_table()
        if row["language"] != src and row["sandbox_runtime"] is not None
    ]
    rows.sort(key=lambda r: (-int(r["port_score"]), r["language"]))
    return rows[:limit]


def format_language_maturity_summary() -> str:
    """Compact maturity summary string suitable for injecting into the PM Feature Contract prompt."""
    rows = get_language_maturity_table()
    lines = ["Factory Language Maturity Matrix (live runtime & test support):"]
    for row in rows:
        lines.append(
            f"- {row['language']}: {row['maturity_tier']} | extract={row['extraction_mode']} | "
            f"tests={row['test_runner_support']} | deps={row['dependency_ecosystem']} | "
            f"equiv={row['behavioural_equivalence']}"
        )
    return "\n".join(lines)


def format_language_maturity_markdown() -> str:
    """Render deterministic Markdown matching ``scripts/validate_documentation.py`` headers."""
    rows = get_language_maturity_table()
    lines = [
        "# Per-Language Maturity Matrix",
        "",
        "Document version: 1.0.0",
        "Last updated: 2026-11-13",
        "Status: Generated from live runtime, provisioning, extraction, and equivalence tables",
        "Audience: Operators, Engineering, PM Agent",
        "",
        "<!-- AUTO-GENERATED by scripts/generate_language_maturity.py. Do not edit manually. -->",
        "",
        "This matrix reflects the live capabilities of the Factory's extraction, dependency",
        "provisioning, offline sandbox execution, vendored test runners, and behavioural",
        "equivalence subsystems. The PM Agent cites this table when recommending PORT targets.",
        "",
        "| Language | Tier | Extraction | Sandbox Image | Test Runner | Dependency Cache | Behavioural Equivalence | Notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| `{language}` | {tier} | {extract} | `{image}` | {tests} | {deps} | {equiv} | {notes} |".format(
                language=row["language"],
                tier=row["maturity_tier"],
                extract=row["extraction_mode"],
                image=row["sandbox_runtime"] or "none",
                tests=row["test_runner_support"],
                deps=row["dependency_ecosystem"],
                equiv=row["behavioural_equivalence"],
                notes=row["notes"] or "—",
            )
        )
    lines.append("")
    return "\n".join(lines)


def write_language_maturity_doc(output_path: str | Path) -> Path:
    """Write ``docs/LANGUAGE_MATURITY.md`` cleanly with LF line endings."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(format_language_maturity_markdown(), encoding="utf-8", newline="\n")
    return target
