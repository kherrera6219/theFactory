"""Full-repo workspace code indexer, symbol/call graph builder, and test discovery (Phase 5).

Indexes every tracked file inside a ``MissionWorkspace`` without the legacy
100-file / 12 KB prompt truncation limits:
- Syntax-aware chunking using Python ``ast`` and ``pod_worker`` tree-sitter /
  structural extractors, with sliding-window chunking for configs or oversized
  units (~6,000 chars / ~1,500 tokens with 600-char overlap).
- Incremental ``content_sha256`` deduplication persisted under
  ``<workspace>/.thefactory/index.json`` so unchanged re-imports re-embed 0 chunks.
- Explicit per-file ``projection_method`` (``ast``, ``tree-sitter``,
  ``structural_ast``, ``regex``, or ``sliding_window``).
- Cross-file symbol table, import/call graph, reverse importers/callers, and
  hotspot metrics.
- Multi-ecosystem framework, entrypoint, and test command discovery across
  Python, C#/.NET, C/C++, JavaScript/TypeScript, Java/Maven/Gradle, PHP, Go,
  Rust, and Ruby.
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import logging
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from defusedxml import ElementTree as ET

from . import knowledge_lake
from .dependency_provisioner import normalize_package_name, scan_workspace_manifests
from .workspace import WORKSPACE_INTERNAL_DIR, MissionWorkspace

LOGGER = logging.getLogger(__name__)

INDEX_SCHEMA_VERSION = "workspace_index.v1"
INDEX_FILENAME = "index.json"
DEFAULT_CHUNK_CHARS = 6_000
DEFAULT_CHUNK_OVERLAP = 600
MAX_STORED_FILE_BYTES = 2_000_000

_LANGUAGE_BY_SUFFIX: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cs": "csharp",
    ".csproj": "csharp",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".java": "java",
    ".php": "php",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".hs": "haskell",
    ".ml": "ocaml",
    ".mli": "ocaml",
    ".r": "r",
    ".jl": "julia",
    ".zig": "zig",
}

_SOURCE_CODE_LANGUAGES = frozenset(_LANGUAGE_BY_SUFFIX.values())
_CALL_IDENT_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_CALL_STOPWORDS = frozenset(
    {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "return",
        "sizeof",
        "typeof",
        "function",
        "def",
        "class",
        "struct",
        "new",
        "print",
        "len",
        "range",
        "super",
    }
)
_MANIFEST_NAMES = frozenset(
    {
        "package.json",
        "pom.xml",
        "composer.json",
        "go.mod",
        "cargo.toml",
        "pyproject.toml",
        "requirements.txt",
        "makefile",
        "gemfile",
    }
)


def _pod_worker_root() -> Path | None:
    here = Path(__file__).resolve()
    candidates = (
        here.parents[2] / "pod-worker",
        here.parents[1],
    )
    for candidate in candidates:
        if (candidate / "pod_worker" / "language_extractor.py").is_file():
            return candidate
    return None


def _ensure_pod_worker_on_path() -> bool:
    root = _pod_worker_root()
    if root is None:
        return False
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return True


def _infer_file_language(rel_path: str, declared: str | None = None) -> str:
    low = rel_path.lower()
    suffix = Path(low).suffix
    if suffix in _LANGUAGE_BY_SUFFIX:
        return _LANGUAGE_BY_SUFFIX[suffix]
    name = Path(low).name
    if name in {"makefile", "gnumakefile"}:
        return "c"
    norm = str(declared or "").strip().lower()
    return norm or "text"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _sliding_window_spans(
    lines: list[str],
    *,
    max_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_CHUNK_OVERLAP,
) -> list[tuple[int, int, str]]:
    """Split *lines* into overlapping character-bounded line windows."""
    if not lines:
        return [(1, 1, "")]
    spans: list[tuple[int, int, str]] = []
    idx = 0
    total = len(lines)
    while idx < total:
        buf: list[str] = []
        chars = 0
        start_idx = idx
        while idx < total:
            line = lines[idx]
            addition = len(line) + 1
            if buf and chars + addition > max_chars:
                break
            buf.append(line)
            chars += addition
            idx += 1
        end_idx = idx
        spans.append((start_idx + 1, end_idx, "\n".join(buf)))
        if idx >= total:
            break
        # Step backwards by overlap_chars (at least 1 line forward guaranteed).
        back = 0
        overlap_idx = idx
        while overlap_idx > start_idx + 1 and back < overlap_chars:
            overlap_idx -= 1
            back += len(lines[overlap_idx]) + 1
        idx = max(start_idx + 1, overlap_idx)
    return spans


def _extract_python_structural_units(
    rel_path: str,
    content: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], list[str], str] | None:
    """Use stdlib ``ast`` to extract chunks, symbols, imports, and calls for Python."""
    try:
        tree = ast.parse(content, filename=rel_path)
    except SyntaxError:
        return None

    lines = content.splitlines()
    imports: list[str] = []
    calls: set[str] = set()
    symbols: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

    def _node_calls(node: ast.AST) -> list[str]:
        found: set[str] = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                if isinstance(sub.func, ast.Name):
                    found.add(sub.func.id)
                elif isinstance(sub.func, ast.Attribute):
                    found.add(sub.func.attr)
        return sorted(found - _CALL_STOPWORDS)

    top_ranges: list[tuple[int, int]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = int(getattr(node, "lineno", 1))
            end = int(getattr(node, "end_lineno", start) or start)
            top_ranges.append((start, end))
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            if isinstance(node, ast.ClassDef):
                bases = [ast.unparse(b) for b in node.bases] if hasattr(ast, "unparse") else []
                sig = f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}"
            else:
                args = ast.unparse(node.args) if hasattr(ast, "unparse") else "..."
                prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                sig = f"{prefix} {node.name}({args})"
            node_calls = _node_calls(node)
            symbols.append(
                {
                    "name": node.name,
                    "kind": kind,
                    "path": rel_path,
                    "line": start,
                    "end_line": end,
                    "signature": sig[:240],
                    "calls": node_calls,
                    "projection_method": "ast",
                }
            )
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        m_start = int(getattr(item, "lineno", start))
                        m_end = int(getattr(item, "end_lineno", m_start) or m_start)
                        symbols.append(
                            {
                                "name": f"{node.name}.{item.name}",
                                "kind": "method",
                                "path": rel_path,
                                "line": m_start,
                                "end_line": m_end,
                                "signature": f"def {item.name}(...)"[:240],
                                "calls": _node_calls(item),
                                "projection_method": "ast",
                            }
                        )
            unit_lines = lines[max(0, start - 1) : end]
            unit_text = "\n".join(unit_lines)
            if len(unit_text) <= DEFAULT_CHUNK_CHARS:
                chunks.append(
                    _make_chunk(
                        rel_path=rel_path,
                        language="python",
                        chunk_type=kind,
                        symbol_name=node.name,
                        start_line=start,
                        end_line=end,
                        text=unit_text,
                        signature=sig[:240],
                        projection_method="ast",
                    )
                )
            else:
                for sub_idx, (w_start, w_end, w_text) in enumerate(
                    _sliding_window_spans(unit_lines)
                ):
                    chunks.append(
                        _make_chunk(
                            rel_path=rel_path,
                            language="python",
                            chunk_type=f"{kind}_window",
                            symbol_name=f"{node.name}#part{sub_idx + 1}",
                            start_line=start + w_start - 1,
                            end_line=start + w_end - 1,
                            text=w_text,
                            signature=sig[:240],
                            projection_method="ast",
                        )
                    )

    # Capture module header / top-level statements before or between definitions.
    if not chunks:
        for idx_w, (w_start, w_end, w_text) in enumerate(_sliding_window_spans(lines)):
            chunks.append(
                _make_chunk(
                    rel_path=rel_path,
                    language="python",
                    chunk_type="module",
                    symbol_name=f"{Path(rel_path).stem}#part{idx_w + 1}",
                    start_line=w_start,
                    end_line=w_end,
                    text=w_text,
                    signature=f"module {rel_path}",
                    projection_method="ast",
                )
            )
    elif top_ranges and top_ranges[0][0] > 1:
        header_end = top_ranges[0][0] - 1
        header_text = "\n".join(lines[:header_end]).strip()
        if header_text:
            chunks.insert(
                0,
                _make_chunk(
                    rel_path=rel_path,
                    language="python",
                    chunk_type="module_header",
                    symbol_name=f"{Path(rel_path).stem}#header",
                    start_line=1,
                    end_line=header_end,
                    text=header_text[:DEFAULT_CHUNK_CHARS],
                    signature=f"imports/header {rel_path}",
                    projection_method="ast",
                ),
            )

    unique_imports = sorted({imp for imp in imports if imp})
    return chunks, symbols, unique_imports, sorted(calls - _CALL_STOPWORDS), "ast"


def _make_chunk(
    *,
    rel_path: str,
    language: str,
    chunk_type: str,
    symbol_name: str,
    start_line: int,
    end_line: int,
    text: str,
    signature: str,
    projection_method: str,
) -> dict[str, Any]:
    digest = _sha256_text(text)
    chunk_id = _sha256_text(f"{rel_path}:{start_line}:{end_line}:{digest}")[:24]
    return {
        "chunk_id": chunk_id,
        "path": rel_path,
        "language": language,
        "chunk_type": chunk_type,
        "symbol_name": symbol_name,
        "start_line": int(start_line),
        "end_line": int(end_line),
        "signature": signature,
        "content_sha256": digest,
        "char_count": len(text),
        "projection_method": projection_method,
        "text": text,
    }


def _extract_calls_from_text(text: str, defined_names: set[str] | None = None) -> list[str]:
    found = {m.group(1) for m in _CALL_IDENT_RE.finditer(text)} - _CALL_STOPWORDS
    if defined_names:
        found -= defined_names
    return sorted(found)


def _extract_generic_code_units(
    rel_path: str,
    language: str,
    content: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], list[str], str]:
    """Use ``pod_worker`` tree-sitter / language extractors with sliding-window chunking."""
    symbols: list[dict[str, Any]] = []
    imports: list[str] = []
    projection_method = "regex"

    if _ensure_pod_worker_on_path():
        try:
            from pod_worker.treesitter_extractor import (
                TREESITTER_SUPPORTED_LANGUAGES,
                extract_treesitter_ast,
            )

            if language in TREESITTER_SUPPORTED_LANGUAGES:
                ts_res = extract_treesitter_ast(content, language)
                if getattr(ts_res, "success", False):
                    projection_method = (
                        "tree-sitter"
                        if getattr(ts_res, "backend", "") == "tree_sitter"
                        else "structural_ast"
                    )
                    imports.extend(str(imp) for imp in getattr(ts_res, "imports", []) if imp)
                    for cls in getattr(ts_res, "classes", []):
                        symbols.append(
                            {
                                "name": str(cls.name),
                                "kind": "class",
                                "path": rel_path,
                                "line": int(getattr(cls, "line", 1) or 1),
                                "end_line": int(getattr(cls, "line", 1) or 1),
                                "signature": f"class {cls.name}",
                                "calls": [],
                                "projection_method": projection_method,
                            }
                        )
                    for fn in getattr(ts_res, "functions", []):
                        symbols.append(
                            {
                                "name": str(fn.name),
                                "kind": "function",
                                "path": rel_path,
                                "line": int(getattr(fn, "line", 1) or 1),
                                "end_line": int(getattr(fn, "line", 1) or 1),
                                "signature": str(getattr(fn, "signature", fn.name) or fn.name)[:240],
                                "calls": [],
                                "projection_method": projection_method,
                            }
                        )
        except Exception as exc:
            LOGGER.debug("treesitter extraction skipped for %s: %s", rel_path, exc)

        if not imports or not symbols:
            try:
                from pod_worker.language_extractor import get_extractor

                res = get_extractor(language).extract(content)
                for imp in getattr(res, "imports", []) or []:
                    if imp and str(imp) not in imports:
                        imports.append(str(imp))
                existing_names = {s["name"] for s in symbols}
                for cls in getattr(res, "classes", []) or []:
                    name = str(getattr(cls, "name", "") or "")
                    if name and name not in existing_names:
                        symbols.append(
                            {
                                "name": name,
                                "kind": "class",
                                "path": rel_path,
                                "line": int(getattr(cls, "line", 1) or 1),
                                "end_line": int(getattr(cls, "line", 1) or 1),
                                "signature": f"class {name}",
                                "calls": [],
                                "projection_method": (
                                    projection_method
                                    if projection_method in {"tree-sitter", "structural_ast"}
                                    else "regex"
                                ),
                            }
                        )
                        existing_names.add(name)
                for fn in getattr(res, "functions", []) or []:
                    name = str(getattr(fn, "name", "") or "")
                    if name and name not in existing_names:
                        symbols.append(
                            {
                                "name": name,
                                "kind": "function",
                                "path": rel_path,
                                "line": int(getattr(fn, "line", 1) or 1),
                                "end_line": int(getattr(fn, "line", 1) or 1),
                                "signature": str(getattr(fn, "signature", name) or name)[:240],
                                "calls": [],
                                "projection_method": (
                                    projection_method
                                    if projection_method in {"tree-sitter", "structural_ast"}
                                    else "regex"
                                ),
                            }
                        )
                        existing_names.add(name)
            except Exception as exc:
                LOGGER.debug("regex language extractor failed for %s: %s", rel_path, exc)

    # Supplement imports/calls accurately for CommonJS / PHP / Go / C# / C where regex might miss.
    if language == "javascript" and not imports:
        imports.extend(re.findall(r"""require\(\s*['"]([^'"]+)['"]\s*\)""", content))
        imports.extend(re.findall(r"""from\s+['"]([^'"]+)['"]""", content))
    elif language == "c" and not imports:
        imports.extend(re.findall(r'#include\s+[<"]([^>"]+)[>"]', content))
    elif language == "php" and not imports:
        imports.extend(re.findall(r"(?:require|require_once|include|use)\s+['\"]?([^'\";\s]+)", content))
    elif language == "csharp" and not imports:
        imports.extend(re.findall(r"^\s*using\s+([A-Za-z0-9_.]+)\s*;", content, re.MULTILINE))
    elif language == "go" and not imports:
        imports.extend(re.findall(r'"([^"]+)"', content))

    lines = content.splitlines()
    calls = _extract_calls_from_text(content)
    chunks: list[dict[str, Any]] = []
    if symbols and len(lines) > 0:
        sorted_syms = sorted(symbols, key=lambda s: int(s.get("line") or 1))
        first_line = max(1, int(sorted_syms[0].get("line") or 1))
        if first_line > 1:
            header_text = "\n".join(lines[: first_line - 1]).strip()
            if header_text:
                chunks.append(
                    _make_chunk(
                        rel_path=rel_path,
                        language=language,
                        chunk_type="module_header",
                        symbol_name=f"{Path(rel_path).stem}#header",
                        start_line=1,
                        end_line=first_line - 1,
                        text=header_text[:DEFAULT_CHUNK_CHARS],
                        signature=f"header {rel_path}",
                        projection_method=projection_method,
                    )
                )
        for idx, sym in enumerate(sorted_syms):
            start_ln = max(1, int(sym.get("line") or 1))
            next_ln = (
                int(sorted_syms[idx + 1].get("line") or len(lines) + 1) - 1
                if idx + 1 < len(sorted_syms)
                else len(lines)
            )
            end_ln = max(start_ln, min(len(lines), next_ln))
            sym["end_line"] = end_ln
            unit_lines = lines[start_ln - 1 : end_ln]
            sym["calls"] = _extract_calls_from_text("\n".join(unit_lines), {sym["name"]})
            unit_text = "\n".join(unit_lines)
            if len(unit_text) <= DEFAULT_CHUNK_CHARS:
                chunks.append(
                    _make_chunk(
                        rel_path=rel_path,
                        language=language,
                        chunk_type=str(sym.get("kind") or "symbol"),
                        symbol_name=str(sym["name"]),
                        start_line=start_ln,
                        end_line=end_ln,
                        text=unit_text,
                        signature=str(sym.get("signature") or sym["name"]),
                        projection_method=projection_method,
                    )
                )
            else:
                for sub_i, (ws_l, we_l, w_text) in enumerate(_sliding_window_spans(unit_lines)):
                    chunks.append(
                        _make_chunk(
                            rel_path=rel_path,
                            language=language,
                            chunk_type=f"{sym.get('kind', 'symbol')}_window",
                            symbol_name=f"{sym['name']}#part{sub_i + 1}",
                            start_line=start_ln + ws_l - 1,
                            end_line=start_ln + we_l - 1,
                            text=w_text,
                            signature=str(sym.get("signature") or sym["name"]),
                            projection_method=projection_method,
                        )
                    )

    if not chunks:
        proj = projection_method if language in _SOURCE_CODE_LANGUAGES else "sliding_window"
        for idx_w, (w_start, w_end, w_text) in enumerate(_sliding_window_spans(lines)):
            chunks.append(
                _make_chunk(
                    rel_path=rel_path,
                    language=language,
                    chunk_type="file_window",
                    symbol_name=f"{Path(rel_path).name}#part{idx_w + 1}",
                    start_line=w_start,
                    end_line=w_end,
                    text=w_text,
                    signature=f"file {rel_path}",
                    projection_method=proj,
                )
            )

    return chunks, symbols, sorted(set(imports)), calls, projection_method


def chunk_workspace_file(rel_path: str, content: str) -> dict[str, Any]:
    """Produce syntax-aware chunks, symbols, imports, and calls for a single file."""
    language = _infer_file_language(rel_path)
    if language == "python":
        py_result = _extract_python_structural_units(rel_path, content)
        if py_result is not None:
            chunks, symbols, imports, calls, projection_method = py_result
            return {
                "path": rel_path,
                "language": language,
                "projection_method": projection_method,
                "chunks": chunks,
                "symbols": symbols,
                "imports": imports,
                "calls": calls,
            }

    if language != "python" and language in _SOURCE_CODE_LANGUAGES:
        chunks, symbols, imports, calls, projection_method = _extract_generic_code_units(
            rel_path, language, content
        )
    else:
        lines = content.splitlines()
        chunks = [
            _make_chunk(
                rel_path=rel_path,
                language=language,
                chunk_type="config" if Path(rel_path).name.lower() in _MANIFEST_NAMES else "text",
                symbol_name=f"{Path(rel_path).name}#part{idx + 1}",
                start_line=w_start,
                end_line=w_end,
                text=w_text,
                signature=f"file {rel_path}",
                projection_method="sliding_window",
            )
            for idx, (w_start, w_end, w_text) in enumerate(_sliding_window_spans(lines))
        ]
        symbols, imports, calls, projection_method = [], [], [], "sliding_window"

    return {
        "path": rel_path,
        "language": language,
        "projection_method": projection_method,
        "chunks": chunks,
        "symbols": symbols,
        "imports": imports,
        "calls": calls,
    }


def _resolve_relative_import(source_path: str, imp: str, all_paths: set[str]) -> str | None:
    clean = str(imp or "").strip().strip("'\"")
    if not clean:
        return None
    if clean in all_paths:
        return clean
    src_dir = Path(source_path).parent
    if clean.startswith("."):
        for ext in ("", ".js", ".cjs", ".mjs", ".ts", ".py", ".h", ".c"):
            cand = (src_dir / f"{clean}{ext}").as_posix()
            # normalize ../ segments
            norm_parts: list[str] = []
            for part in cand.split("/"):
                if part in {"", "."}:
                    continue
                if part == ".." and norm_parts:
                    norm_parts.pop()
                elif part != "..":
                    norm_parts.append(part)
            resolved = "/".join(norm_parts)
            if resolved in all_paths:
                return resolved
    dotted = clean.replace(".", "/")
    for ext in (".py", ".java", ".cs", ".php", ".h"):
        candidate = f"{dotted}{ext}"
        if candidate in all_paths:
            return candidate
        tail = Path(candidate).name
        matches = [p for p in all_paths if p == candidate or p.endswith(f"/{tail}")]
        if len(matches) == 1:
            return matches[0]
    header_matches = [p for p in all_paths if p == clean or p.endswith(f"/{clean}")]
    if header_matches:
        return sorted(header_matches)[0]
    return None


def build_symbol_graph(file_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Construct cross-file symbol table, import edges, call edges, and hotspot rankings."""
    all_paths = {str(item["path"]) for item in file_records}
    symbol_index: dict[str, list[dict[str, Any]]] = {}
    symbols: list[dict[str, Any]] = []
    import_edges: list[dict[str, str]] = []
    call_edges: list[dict[str, Any]] = []
    importers_by_path: dict[str, set[str]] = {p: set() for p in all_paths}
    imports_by_path: dict[str, list[str]] = {}
    callers_by_path: dict[str, set[str]] = {p: set() for p in all_paths}
    projection_methods: dict[str, str] = {}

    for rec in file_records:
        path = str(rec["path"])
        projection_methods[path] = str(rec.get("projection_method") or "sliding_window")
        for sym in rec.get("symbols") or []:
            symbols.append(sym)
            short_name = str(sym["name"]).split(".")[-1]
            symbol_index.setdefault(short_name, []).append(sym)

    for rec in file_records:
        src = str(rec["path"])
        resolved_targets: list[str] = []
        for imp in rec.get("imports") or []:
            target_path = _resolve_relative_import(src, str(imp), all_paths)
            import_edges.append(
                {
                    "source": src,
                    "import_spec": str(imp),
                    "target": target_path or str(imp),
                    "internal": bool(target_path),
                }
            )
            if target_path and target_path != src:
                importers_by_path.setdefault(target_path, set()).add(src)
                resolved_targets.append(target_path)
        imports_by_path[src] = sorted(set(resolved_targets))

        for callee in rec.get("calls") or []:
            matches = symbol_index.get(str(callee), [])
            for target_sym in matches:
                target_path = str(target_sym["path"])
                if target_path != src:
                    callers_by_path.setdefault(target_path, set()).add(src)
                call_edges.append(
                    {
                        "caller_path": src,
                        "callee_symbol": target_sym["name"],
                        "callee_path": target_path,
                    }
                )

    fan_in_scores: list[dict[str, Any]] = []
    for rec in file_records:
        path = str(rec["path"])
        fan_in = len(importers_by_path.get(path, set()) | callers_by_path.get(path, set()))
        fn_count = len(rec.get("symbols") or [])
        chunk_chars = sum(int(c.get("char_count") or 0) for c in (rec.get("chunks") or []))
        fan_in_scores.append(
            {
                "path": path,
                "language": rec.get("language"),
                "fan_in": fan_in,
                "symbol_count": fn_count,
                "char_count": chunk_chars,
                "score": fan_in * 10 + fn_count * 2 + round(chunk_chars / 2000.0, 2),
            }
        )
    hotspots = sorted(fan_in_scores, key=lambda item: item["score"], reverse=True)[:10]

    return {
        "symbols": symbols,
        "import_edges": import_edges,
        "call_edges": call_edges,
        "imports_by_path": imports_by_path,
        "importers_by_path": {k: sorted(v) for k, v in importers_by_path.items() if v},
        "callers_by_path": {k: sorted(v) for k, v in callers_by_path.items() if v},
        "projection_methods": projection_methods,
        "hotspots": hotspots,
    }


def _read_text_map(ws: MissionWorkspace) -> dict[str, str]:
    contents: dict[str, str] = {}
    for entry in ws.list_files():
        rel = str(entry["path"])
        if int(entry.get("size_bytes") or 0) > MAX_STORED_FILE_BYTES:
            continue
        try:
            text = ws.read_file(rel)
        except OSError:
            continue
        if "\x00" in text:
            continue
        contents[rel] = text
    return contents


def _parse_csproj_metadata(rel_path: str, text: str) -> dict[str, Any]:
    frameworks: list[str] = []
    is_test = False
    target_framework = ""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        root = None
    if root is not None:
        for elem in root.iter():
            tag = elem.tag.split("}")[-1].lower()
            if tag == "targetframework" and elem.text:
                target_framework = elem.text.strip()
            elif tag == "packagereference":
                inc = str(elem.attrib.get("Include") or "").lower()
                if any(tok in inc for tok in ("xunit", "nunit", "mstest", "microsoft.net.test.sdk")):
                    is_test = True
                    frameworks.append(inc)
    low = text.lower()
    if any(tok in low for tok in ("xunit", "nunit", "mstest", "microsoft.net.test.sdk")):
        is_test = True
    return {
        "path": rel_path,
        "target_framework": target_framework,
        "is_test": is_test,
        "test_packages": sorted(set(frameworks)),
    }


def discover_workspace_tests(
    ws: MissionWorkspace,
    files_by_path: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Detect frameworks, entrypoints, test files, and test commands from repo contents."""
    text_map = files_by_path if files_by_path is not None else _read_text_map(ws)
    all_paths = sorted(text_map)
    non_meta_paths = [
        p for p in all_paths if Path(p).name.lower() not in {"benchmark.yaml", "license", "license.txt"}
    ]

    detected_languages: list[str] = []
    language_counts: dict[str, int] = {}
    for rel in non_meta_paths:
        lang = _infer_file_language(rel)
        if lang in _SOURCE_CODE_LANGUAGES and Path(rel).suffix:
            language_counts[lang] = language_counts.get(lang, 0) + 1
    detected_languages = sorted(language_counts)

    frameworks: list[str] = []
    language_versions: dict[str, str] = {}
    entrypoints: list[str] = []
    test_files: list[str] = []
    test_frameworks: list[str] = []
    suites: list[dict[str, str]] = []

    # 1. C# / .NET
    csproj_paths = [p for p in non_meta_paths if p.lower().endswith(".csproj")]
    cs_tests = [
        p for p in non_meta_paths if p.lower().endswith(".cs") and ("test" in p.lower() or "[fact]" in text_map[p].lower())
    ]
    if csproj_paths:
        frameworks.append("dotnet-console")
        for cp in csproj_paths:
            info = _parse_csproj_metadata(cp, text_map[cp])
            if info["target_framework"]:
                language_versions["csharp"] = info["target_framework"]
            if info["is_test"] or cs_tests:
                test_frameworks.append("xunit" if "xunit" in text_map[cp].lower() else "dotnet-test")
                cmd = f"dotnet test {cp} --nologo"
                suites.append({"language": "csharp", "framework": test_frameworks[-1], "command": cmd})
        test_files.extend(cs_tests)
        entrypoints.extend(
            p for p in non_meta_paths if p.lower().endswith(".cs") and p not in cs_tests
        )

    # 2. C / Makefile / CMake
    makefiles = [p for p in non_meta_paths if Path(p).name.lower() in {"makefile", "gnumakefile"}]
    c_tests = [
        p
        for p in non_meta_paths
        if Path(p).suffix in {".c", ".cpp", ".cc"}
        and (Path(p).name.startswith("test_") or "/tests/" in f"/{p.lower()}")
    ]
    if makefiles and any(Path(p).suffix in {".c", ".h", ".cpp"} for p in non_meta_paths):
        mk_text = text_map[makefiles[0]]
        if re.search(r"-std=(c99|gnu99)", mk_text):
            frameworks.append("c99-make")
            language_versions["c"] = "c99"
        else:
            frameworks.append("make-c")
        if re.search(r"^test\s*:", mk_text, re.MULTILINE):
            test_frameworks.append("makefile-test")
            suites.append({"language": "c", "framework": "make-test", "command": "make test"})
        test_files.extend(c_tests)
        entrypoints.extend(
            p for p in non_meta_paths if p.endswith(".c") and p not in c_tests
        )

    # 3. Node / JavaScript / TypeScript
    pkg_paths = [p for p in non_meta_paths if Path(p).name == "package.json"]
    js_tests = [
        p
        for p in non_meta_paths
        if Path(p).suffix in {".js", ".cjs", ".mjs", ".ts", ".tsx"}
        and (
            ".test." in p.lower()
            or ".spec." in p.lower()
            or p.lower().startswith("test/")
            or p.lower().startswith("tests/")
        )
    ]
    for pkg_p in pkg_paths:
        try:
            pkg_obj = json.loads(text_map[pkg_p])
        except json.JSONDecodeError:
            pkg_obj = {}
        if not isinstance(pkg_obj, dict):
            continue
        deps = {
            **(pkg_obj.get("dependencies") if isinstance(pkg_obj.get("dependencies"), dict) else {}),
            **(pkg_obj.get("devDependencies") if isinstance(pkg_obj.get("devDependencies"), dict) else {}),
        }
        scripts = pkg_obj.get("scripts") if isinstance(pkg_obj.get("scripts"), dict) else {}
        main_entry = str(pkg_obj.get("main") or "").strip()
        if main_entry and main_entry in non_meta_paths:
            entrypoints.append(main_entry)
        if "express" in {str(k).lower() for k in deps}:
            is_esm = str(pkg_obj.get("type") or "").lower() == "module"
            frameworks.append("express-esm" if is_esm else "express-commonjs")
            ver = str(deps.get("express") or "").strip()
            if ver:
                language_versions["express"] = ver
        test_script = str(scripts.get("test") or "").strip()
        if test_script and "no test specified" not in test_script.lower():
            pkg_dir = Path(pkg_p).parent.as_posix()
            cmd = test_script if pkg_dir in {"", "."} else f"cd {pkg_dir} && {test_script}"
            tfw = "vitest" if "vitest" in test_script else ("jest" if "jest" in test_script else "node-test")
            test_frameworks.append(tfw)
            suites.append({"language": "javascript", "framework": tfw, "command": cmd})
        elif js_tests:
            test_frameworks.append("node-test")
            suites.append({"language": "javascript", "framework": "node-test", "command": f"node {js_tests[0]}"})
        test_files.extend(js_tests)

    # 4. Java / Maven / Gradle
    pom_paths = [p for p in non_meta_paths if Path(p).name == "pom.xml"]
    java_tests = [
        p
        for p in non_meta_paths
        if p.endswith(".java") and ("src/test/" in p or p.endswith("Test.java") or p.endswith("Tests.java"))
    ]
    for pom_p in pom_paths:
        pom_text = text_map[pom_p]
        is_java8 = "1.8" in pom_text or ">8<" in pom_text
        frameworks.append("maven-java8" if is_java8 else "maven")
        if is_java8:
            language_versions["java"] = "1.8"
        if "junit" in pom_text.lower() or java_tests:
            test_frameworks.append("junit")
        pom_dir = Path(pom_p).parent.as_posix()
        cmd = "mvn -q test" if pom_dir in {"", "."} else f"cd {pom_dir} && mvn -q test"
        suites.append({"language": "java", "framework": "junit", "command": cmd})
        test_files.extend(java_tests)
        entrypoints.extend(
            p for p in non_meta_paths if p.endswith(".java") and "src/main/" in p
        )

    # 5. PHP / Composer
    composer_paths = [p for p in non_meta_paths if Path(p).name == "composer.json"]
    php_tests = [
        p
        for p in non_meta_paths
        if p.endswith(".php") and (p.lower().startswith("tests/") or p.endswith("Test.php"))
    ]
    for comp_p in composer_paths:
        try:
            comp_obj = json.loads(text_map[comp_p])
        except json.JSONDecodeError:
            comp_obj = {}
        req = comp_obj.get("require") if isinstance(comp_obj.get("require"), dict) else {}
        req_dev = comp_obj.get("require-dev") if isinstance(comp_obj.get("require-dev"), dict) else {}
        php_ver = str(req.get("php") or "")
        if "7" in php_ver:
            frameworks.append("composer-php7")
            language_versions["php"] = php_ver
        else:
            frameworks.append("composer")
            if php_ver:
                language_versions["php"] = php_ver
        has_phpunit = "phpunit/phpunit" in {str(k).lower() for k in {**req, **req_dev}} or bool(php_tests)
        if has_phpunit:
            test_frameworks.append("phpunit")
            test_dir = "tests" if any(p.startswith("tests/") for p in php_tests) else ""
            cmd = f"vendor/bin/phpunit {test_dir}".strip()
            suites.append({"language": "php", "framework": "phpunit", "command": cmd})
        test_files.extend(php_tests)
        entrypoints.extend(
            p for p in non_meta_paths if p.endswith(".php") and p not in php_tests
        )

    # 6. Python
    py_files = [p for p in non_meta_paths if Path(p).suffix == ".py"]
    py_tests = [
        p
        for p in py_files
        if Path(p).name.startswith("test_")
        or Path(p).name.endswith("_test.py")
        or p.startswith("tests/")
    ]
    py_src = [p for p in py_files if p not in py_tests]
    if py_files:
        combined_py = "\n".join(text_map[p] for p in py_files)
        if re.search(r"(?:from\s+flask\s+import|import\s+flask\b)", combined_py):
            frameworks.append("flask")
        elif re.search(r"(?:from\s+fastapi\s+import|import\s+fastapi\b)", combined_py):
            frameworks.append("fastapi")
        elif re.search(r"(?:from\s+django|import\s+django\b)", combined_py):
            frameworks.append("django")
        elif re.search(r"\bargparse\b", combined_py):
            frameworks.append("python-argparse")
        for cand in ("app.py", "main.py", "cli.py", "server.py"):
            if cand in py_src:
                entrypoints.append(cand)
        if not entrypoints and py_src:
            entrypoints.append(py_src[0])
        if py_tests:
            test_frameworks.append("pytest")
            if len(py_tests) == 1 and "/" not in py_tests[0]:
                cmd = f"python -m pytest -q {py_tests[0]}"
            else:
                cmd = "python -m pytest -q"
            suites.append({"language": "python", "framework": "pytest", "command": cmd})
            test_files.extend(py_tests)

    # 7. Go modules (including nested reference_go/ in PORT benchmarks)
    go_mods = [p for p in non_meta_paths if Path(p).name == "go.mod"]
    go_tests = [p for p in non_meta_paths if p.endswith("_test.go")]
    if go_mods or go_tests:
        if not go_mods:
            frameworks.append("go-stdlib")
        mod_dirs = sorted({Path(gm).parent.as_posix() for gm in go_mods}) or ["."]
        for gdir in mod_dirs:
            dir_has_tests = any(
                (t.startswith(f"{gdir}/") if gdir != "." else "/" not in t)
                for t in go_tests
            )
            if dir_has_tests or go_mods:
                test_frameworks.append("go-test")
                cmd = "go test ./..." if gdir in {"", "."} else f"cd {gdir} && go test ./..."
                suites.append({"language": "go", "framework": "go-test", "command": cmd})
        test_files.extend(go_tests)
        for p in non_meta_paths:
            if p.endswith(".go") and not p.endswith("_test.go") and p not in entrypoints:
                entrypoints.append(p)

    # Choose primary language: prefer root/majority source language (and Python over reference_go/).
    primary_language = "unknown"
    if language_counts:
        root_lang_counts: dict[str, int] = {}
        for rel in non_meta_paths:
            lang = _infer_file_language(rel)
            if lang in _SOURCE_CODE_LANGUAGES and Path(rel).suffix:
                weight = 3 if "/" not in rel else (1 if rel.startswith("reference_") else 2)
                root_lang_counts[lang] = root_lang_counts.get(lang, 0) + weight
        primary_language = sorted(
            root_lang_counts.items(),
            key=lambda kv: (-kv[1], kv[0]),
        )[0][0]

    ordered_commands: list[str] = []
    for suite in suites:
        cmd = suite["command"].strip()
        if cmd and cmd not in ordered_commands:
            ordered_commands.append(cmd)
    test_command = " && ".join(ordered_commands) if ordered_commands else None

    unique_frameworks = list(dict.fromkeys(frameworks))
    return {
        "primary_language": primary_language,
        "detected_languages": detected_languages,
        "language_versions": language_versions,
        "frameworks": unique_frameworks,
        "source_framework": unique_frameworks[0] if unique_frameworks else None,
        "entrypoints": list(dict.fromkeys(entrypoints))[:12],
        "has_tests": bool(test_files or suites),
        "test_files": sorted(set(test_files)),
        "test_frameworks": list(dict.fromkeys(test_frameworks)),
        "test_framework": test_frameworks[0] if test_frameworks else None,
        "test_command": test_command,
        "suites": suites,
    }


def _annotate_dependencies(
    deps: list[dict[str, Any]],
    *,
    language_versions: dict[str, str],
) -> list[dict[str, Any]]:
    """Annotate parsed dependencies with lightweight EOL / legacy flags."""
    annotated: list[dict[str, Any]] = []
    for dep in deps:
        name = normalize_package_name(str(dep.get("name") or ""))
        ver = str(dep.get("version") or "latest")
        flags: list[str] = []
        if name == "php" or ("php" in language_versions and language_versions["php"].startswith(("^7", "7"))):
            if name in {"php", "phpunit", "phpunit/phpunit"}:
                flags.append("legacy_php7_eol")
        if name == "flask" and ver.startswith(("0.", "1.")):
            flags.append("legacy_eol")
        if name == "log4j" or "log4j-core" in name:
            flags.append("check_cve_2021_44228")
        if name == "express" and ver.startswith(("^3", "3.")):
            flags.append("legacy_eol")
        annotated.append({**dep, "risk_flags": flags})
    return annotated


def _index_file_path(ws: MissionWorkspace) -> Path:
    return ws.workspace_dir / WORKSPACE_INTERNAL_DIR / INDEX_FILENAME


def load_workspace_index(ws: MissionWorkspace) -> dict[str, Any] | None:
    """Load persisted ``.thefactory/index.json`` for *ws* if present and valid."""
    path = _index_file_path(ws)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _persist_workspace_index(ws: MissionWorkspace, payload: dict[str, Any]) -> Path:
    internal_dir = ws.workspace_dir / WORKSPACE_INTERNAL_DIR
    internal_dir.mkdir(parents=True, exist_ok=True)
    ws._write_git_exclude(ws.workspace_dir)
    out = _index_file_path(ws)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return out


def _sync_new_chunks_to_knowledge_lake(
    chunks: list[dict[str, Any]],
    *,
    workspace_id: str,
    settings: Any,
) -> int:
    if not chunks or settings is None:
        return 0
    mirrored = 0
    for chunk in chunks:
        try:
            coro = knowledge_lake.index_documentation(
                settings=settings,
                language=str(chunk.get("language") or "text"),
                doc_id=f"ws.{workspace_id}.{chunk['chunk_id']}",
                text=str(chunk.get("text") or ""),
                concept=str(chunk.get("symbol_name") or chunk.get("path") or "code"),
                source=f"workspace:{workspace_id}:{chunk.get('path')}",
            )
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None and loop.is_running():
                # Do not block active loop; caller may mirror async separately.
                coro.close()
                break
            if asyncio.run(coro):
                mirrored += 1
        except Exception as exc:
            LOGGER.debug("workspace chunk mirror skipped: %s", exc)
    return mirrored


def index_workspace(
    ws: MissionWorkspace,
    *,
    settings: Any = None,
    embed_fn: Callable[[str], list[float] | None] | None = None,
    mirror_knowledge: bool = False,
) -> dict[str, Any]:
    """Index every file in *ws* with SHA-256 deduplication, symbol graph, and test discovery."""
    existing = load_workspace_index(ws) or {}
    prior_chunks_by_sha: dict[str, dict[str, Any]] = {}
    for chunk in existing.get("chunks") or []:
        if isinstance(chunk, dict) and chunk.get("content_sha256"):
            prior_chunks_by_sha[str(chunk["content_sha256"])] = chunk

    entries = ws.list_files()
    files_by_path: dict[str, str] = {}
    file_records: list[dict[str, Any]] = []
    all_chunks: list[dict[str, Any]] = []
    new_chunks: list[dict[str, Any]] = []
    reused_count = 0
    reembedded_count = 0

    for entry in entries:
        rel_path = str(entry["path"])
        if int(entry.get("size_bytes") or 0) > MAX_STORED_FILE_BYTES:
            continue
        try:
            content = ws.read_file(rel_path)
        except OSError:
            continue
        if "\x00" in content:
            continue
        files_by_path[rel_path] = content
        unit = chunk_workspace_file(rel_path, content)
        deduped_chunks: list[dict[str, Any]] = []
        for chunk in unit["chunks"]:
            sha = str(chunk["content_sha256"])
            prior = prior_chunks_by_sha.get(sha)
            if prior is not None and str(prior.get("path") or "") == rel_path:
                reused_chunk = dict(prior)
                reused_chunk["chunk_id"] = chunk["chunk_id"]
                reused_chunk["start_line"] = chunk["start_line"]
                reused_chunk["end_line"] = chunk["end_line"]
                deduped_chunks.append(reused_chunk)
                reused_count += 1
                continue

            if embed_fn is not None:
                vec = embed_fn(str(chunk["text"]))
                if vec is not None:
                    chunk["embedding_dim"] = len(vec)
                reembedded_count += 1
            elif prior is None:
                reembedded_count += 1
            else:
                reused_count += 1
            deduped_chunks.append(chunk)
            new_chunks.append(chunk)

        unit["chunks"] = deduped_chunks
        unit["file_sha256"] = str(entry.get("sha256") or _sha256_text(content))
        unit["size_bytes"] = int(entry.get("size_bytes") or len(content.encode("utf-8")))
        unit["estimated_lines"] = int(entry.get("estimated_lines") or len(content.splitlines()))
        file_records.append(unit)
        all_chunks.extend(deduped_chunks)

    if mirror_knowledge and new_chunks and settings is not None:
        _sync_new_chunks_to_knowledge_lake(
            new_chunks,
            workspace_id=ws.workspace_id,
            settings=settings,
        )

    symbol_graph = build_symbol_graph(file_records)
    test_discovery = discover_workspace_tests(ws, files_by_path=files_by_path)
    raw_deps, manifests_found, manifest_warnings = scan_workspace_manifests(
        ws.workspace_dir,
        language_hint=test_discovery.get("primary_language"),
    )
    dependency_inventory = _annotate_dependencies(
        raw_deps,
        language_versions=test_discovery.get("language_versions") or {},
    )

    index_stats = {
        "total_files": len(file_records),
        "total_chunks": len(all_chunks),
        "new_chunks": len(new_chunks),
        "reused_chunks": reused_count,
        "chunks_reembedded": reembedded_count,
        "dedup_hit_ratio": (
            round(reused_count / max(len(all_chunks), 1), 4) if all_chunks else 1.0
        ),
        "total_symbols": len(symbol_graph["symbols"]),
        "total_import_edges": len(symbol_graph["import_edges"]),
        "total_call_edges": len(symbol_graph["call_edges"]),
    }

    payload: dict[str, Any] = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "workspace_id": ws.workspace_id,
        "base_commit": ws.base_commit,
        "indexed_at": datetime.now(UTC).isoformat(),
        "index_stats": index_stats,
        "files": [
            {
                "path": r["path"],
                "language": r["language"],
                "projection_method": r["projection_method"],
                "file_sha256": r["file_sha256"],
                "size_bytes": r["size_bytes"],
                "estimated_lines": r["estimated_lines"],
                "chunk_count": len(r["chunks"]),
                "symbol_count": len(r["symbols"]),
                "imports": r["imports"],
            }
            for r in file_records
        ],
        "chunks": all_chunks,
        "symbol_graph": symbol_graph,
        "test_discovery": test_discovery,
        "manifests_found": manifests_found,
        "manifest_warnings": manifest_warnings,
        "dependency_inventory": dependency_inventory,
    }
    _persist_workspace_index(ws, payload)
    return payload


def search_workspace_chunks(
    ws: MissionWorkspace,
    query: str,
    *,
    top_k: int = 12,
    path_filter: list[str] | None = None,
    index_data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve relevant workspace chunks ranked by lexical overlap and symbol match."""
    data = index_data if isinstance(index_data, dict) else load_workspace_index(ws)
    if not isinstance(data, dict):
        data = index_workspace(ws)

    chunks = data.get("chunks") or []
    allowed = {str(p).strip() for p in (path_filter or []) if str(p).strip()}
    tokens = {tok for tok in re.findall(r"[A-Za-z0-9_]{2,}", str(query or "").lower())}
    scored: list[tuple[float, dict[str, Any]]] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        path = str(chunk.get("path") or "")
        if allowed and path not in allowed:
            continue
        haystack = " ".join(
            [
                path.lower(),
                str(chunk.get("symbol_name") or "").lower(),
                str(chunk.get("signature") or "").lower(),
                str(chunk.get("text") or "").lower()[:3000],
            ]
        )
        chunk_tokens = set(re.findall(r"[A-Za-z0-9_]{2,}", haystack))
        overlap = len(tokens & chunk_tokens) if tokens else 1
        sym_bonus = (
            2.5
            if tokens and any(t in str(chunk.get("symbol_name") or "").lower() for t in tokens)
            else 0.0
        )
        path_bonus = (
            2.0 if tokens and any(t in path.lower() for t in tokens) else 0.0
        )
        score = overlap + sym_bonus + path_bonus
        if score > 0 or allowed:
            scored.append((score, chunk))

    scored.sort(
        key=lambda item: (-item[0], str(item[1].get("path") or ""), int(item[1].get("start_line") or 0))
    )
    return [item for _, item in scored[:top_k]]
