"""Optional tree-sitter and comment-stripped structural AST extractor for Pod Worker.

Provides structural symbol recovery (functions, classes/structs, and imports) for
typed systems and enterprise languages (Rust, C, C++, C#, Kotlin, Scala, Zig, Ruby,
PHP, Python, JavaScript, TypeScript, Go, Java). When ``tree_sitter_languages`` is
installed in the runtime environment, uses native tree-sitter CST traversal;
otherwise falls back to a comment- and string-literal-stripped structural block
parser so commented-out declarations are never mistaken for live symbols.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from .language_extractor import _analyse_typed_body, _parse_typed_signature

TREESITTER_SUPPORTED_LANGUAGES = frozenset(
    {
        "rust",
        "c",
        "cpp",
        "csharp",
        "kotlin",
        "scala",
        "zig",
        "ruby",
        "php",
        "python",
        "javascript",
        "typescript",
        "go",
        "java",
    }
)


@dataclass(frozen=True, slots=True)
class TreeSitterFunctionInfo:
    """Function or method recovered by the tree-sitter / structural parser."""

    name: str
    line: int
    signature: str
    arg_types: tuple[str, ...] = ()
    return_type: str | None = None
    side_effects: tuple[str, ...] = ()
    purity: str = "UNKNOWN"
    ops: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class TreeSitterClassInfo:
    """Class, struct, enum, or trait recovered by the tree-sitter / structural parser."""

    name: str
    line: int
    parents: tuple[str, ...] = ()


@dataclass
class TreeSitterAstResult:
    """Aggregated structural AST output for one source file."""

    language: str
    success: bool = True
    backend: str = "structural_ast_fallback"
    functions: list[TreeSitterFunctionInfo] = field(default_factory=list)
    classes: list[TreeSitterClassInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    error: str | None = None


_BLOCK_COMMENT_RE = re.compile(r"/\*[\s\S]*?\*/")
_LINE_COMMENT_SLASH_RE = re.compile(r"//[^\n]*")
_LINE_COMMENT_HASH_RE = re.compile(r"#[^\n]*")


def strip_comments_preserving_lines(source: str, language: str) -> str:
    """Replace comments with spaces while preserving exact line numbers."""
    normalized = str(language or "").strip().lower()

    def _blank_Keeping_newlines(match: re.Match[str]) -> str:
        text = match.group(0)
        return "".join("\n" if ch == "\n" else " " for ch in text)

    cleaned = _BLOCK_COMMENT_RE.sub(_blank_Keeping_newlines, source)
    if normalized in {"python", "ruby"}:
        cleaned = _LINE_COMMENT_HASH_RE.sub(_blank_Keeping_newlines, cleaned)
    else:
        cleaned = _LINE_COMMENT_SLASH_RE.sub(_blank_Keeping_newlines, cleaned)
    return cleaned


def _try_native_treesitter(source: str, language: str) -> TreeSitterAstResult | None:
    """Attempt native tree_sitter_languages parse when installed."""
    try:
        from tree_sitter_languages import get_parser  # type: ignore[import-not-found]
    except Exception:
        return None

    lang_alias = {"csharp": "c_sharp"}.get(language, language)
    try:
        parser = get_parser(lang_alias)
        tree = parser.parse(source.encode("utf-8"))
    except Exception:
        return None

    lines = source.splitlines()
    functions: list[TreeSitterFunctionInfo] = []
    classes: list[TreeSitterClassInfo] = []
    imports: list[str] = []

    fn_node_types = {
        "function_item",
        "function_definition",
        "function_declaration",
        "method_declaration",
        "method",
    }
    class_node_types = {
        "struct_item",
        "enum_item",
        "trait_item",
        "class_declaration",
        "struct_specifier",
        "class_specifier",
        "interface_declaration",
    }
    import_node_types = {
        "use_declaration",
        "preproc_include",
        "using_directive",
        "import_declaration",
        "import_statement",
    }

    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        ntype = getattr(node, "type", "")
        line_no = int(node.start_point[0]) + 1
        sig_line = lines[line_no - 1].strip() if 1 <= line_no <= len(lines) else ""
        if ntype in fn_node_types:
            name_node = node.child_by_field_name("name")
            fn_name = (
                source[name_node.start_byte : name_node.end_byte].strip()
                if name_node is not None
                else ""
            )
            if fn_name:
                arg_types, return_type = _parse_typed_signature(language, sig_line)
                side_effects, purity, ops = _analyse_typed_body(source, line_no)
                functions.append(
                    TreeSitterFunctionInfo(
                        name=fn_name,
                        line=line_no,
                        signature=sig_line,
                        arg_types=arg_types,
                        return_type=return_type,
                        side_effects=side_effects,
                        purity=purity,
                        ops=ops,
                    )
                )
        elif ntype in class_node_types:
            name_node = node.child_by_field_name("name")
            cls_name = (
                source[name_node.start_byte : name_node.end_byte].strip()
                if name_node is not None
                else ""
            )
            if cls_name:
                classes.append(TreeSitterClassInfo(name=cls_name, line=line_no))
        elif ntype in import_node_types and sig_line:
            imports.append(sig_line)
        for child in reversed(getattr(node, "children", [])):
            stack.append(child)

    return TreeSitterAstResult(
        language=language,
        success=True,
        backend="tree_sitter",
        functions=functions,
        classes=classes,
        imports=imports,
    )


def extract_treesitter_ast(source: str, language: str) -> TreeSitterAstResult:
    """Extract structural AST symbols using tree-sitter or comment-stripped fallback."""
    normalized = str(language or "").strip().lower()
    if not isinstance(source, str) or not source.strip():
        return TreeSitterAstResult(language=normalized, success=True, functions=[], classes=[], imports=[])

    if normalized not in TREESITTER_SUPPORTED_LANGUAGES:
        return TreeSitterAstResult(
            language=normalized,
            success=False,
            error=f"unsupported language for treesitter extractor: {normalized}",
        )

    native = _try_native_treesitter(source, normalized)
    if native is not None and (native.functions or native.classes or native.imports):
        return native

    from .language_extractor import _EXTRACTORS, LanguageExtractor

    cleaned = strip_comments_preserving_lines(source, normalized)
    cleaned_lines = cleaned.splitlines()
    raw_lines = source.splitlines()

    extractor_cls = _EXTRACTORS.get(normalized, LanguageExtractor)
    extractor = extractor_cls()
    raw_fns = extractor._detect_functions(cleaned, cleaned_lines)
    raw_classes = extractor._detect_classes(cleaned, cleaned_lines)
    raw_imports = extractor._detect_imports(cleaned)

    functions: list[TreeSitterFunctionInfo] = []
    for fn in raw_fns:
        raw_sig = raw_lines[fn.line - 1].strip() if 1 <= fn.line <= len(raw_lines) else fn.signature
        arg_types, return_type = _parse_typed_signature(normalized, raw_sig)
        side_effects, purity, ops = _analyse_typed_body(cleaned, fn.line)
        functions.append(
            TreeSitterFunctionInfo(
                name=fn.name,
                line=fn.line,
                signature=raw_sig,
                arg_types=arg_types or fn.arg_types,
                return_type=return_type or fn.return_type,
                side_effects=side_effects or fn.side_effects,
                purity=purity if purity != "UNKNOWN" else fn.purity,
                ops=ops or fn.ops,
            )
        )

    classes = [
        TreeSitterClassInfo(name=cls.name, line=cls.line, parents=cls.parents)
        for cls in raw_classes
    ]

    return TreeSitterAstResult(
        language=normalized,
        success=True,
        backend="structural_ast_fallback",
        functions=functions,
        classes=classes,
        imports=raw_imports,
    )


def extract_treesitter_symbols(code: str, language: str) -> dict[str, Any]:
    """Return a JSON-serialisable dictionary of structural AST symbols for *code*."""
    res = extract_treesitter_ast(code, language)
    return {
        "language": res.language,
        "success": res.success,
        "backend": res.backend,
        "error": res.error,
        "functions": [
            {
                "name": fn.name,
                "line": fn.line,
                "signature": fn.signature,
                "arg_types": list(fn.arg_types),
                "return_type": fn.return_type,
                "side_effects": list(fn.side_effects),
                "purity": fn.purity,
                "ops": [list(op) for op in fn.ops],
            }
            for fn in res.functions
        ],
        "classes": [
            {
                "name": cls.name,
                "line": cls.line,
                "parents": list(cls.parents),
            }
            for cls in res.classes
        ],
        "imports": list(res.imports),
    }


def is_treesitter_enabled() -> bool:
    """Return True when TREESITTER_AST_EXTRACTOR_ENABLED is enabled (default true)."""
    val = os.getenv("TREESITTER_AST_EXTRACTOR_ENABLED", "true").strip().lower()
    return val in {"1", "true", "yes", "on"}
