"""ast_extractor.py — AST-based extraction for Python source code.

2026 best practice: use Python's built-in ``ast`` module for accurate
structural analysis. This module augments (not replaces) the regex-based
``LanguageExtractor`` — it runs first; regex is the fallback.

Key improvements over regex:
- Accurate function/method detection (handles decorators, async, inner functions)
- Class hierarchy extraction (base classes, metaclasses)
- Type annotation extraction (argument types, return types)
- Import graph construction (module + name + alias)
- No false positives from comments or string literals
"""
from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from typing import Any

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AstFunctionInfo:
    name: str
    line: int
    is_async: bool
    is_method: bool
    decorators: tuple[str, ...]
    return_annotation: str | None
    arg_types: tuple[str, ...]
    docstring: str | None
    signature: str


@dataclass(frozen=True, slots=True)
class AstClassInfo:
    name: str
    line: int
    bases: tuple[str, ...]
    decorators: tuple[str, ...]
    methods: tuple[str, ...]
    docstring: str | None


@dataclass(frozen=True, slots=True)
class AstImportInfo:
    module: str
    names: tuple[str, ...]
    is_from: bool
    line: int


@dataclass
class AstExtractionResult:
    """Full AST-based extraction result for one Python file."""

    functions: list[AstFunctionInfo] = field(default_factory=list)
    classes: list[AstClassInfo] = field(default_factory=list)
    imports: list[AstImportInfo] = field(default_factory=list)
    top_level_names: list[str] = field(default_factory=list)
    parse_error: str | None = None

    @property
    def success(self) -> bool:
        return self.parse_error is None


# ---------------------------------------------------------------------------
# Node-name helpers
# ---------------------------------------------------------------------------

def _node_name(node: ast.expr | None) -> str:
    """Return a human-readable name for an AST expression node."""
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_node_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Subscript):
        return f"{_node_name(node.value)}[{_node_name(node.slice)}]"
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Tuple):
        return f"({', '.join(_node_name(e) for e in node.elts)})"
    return ast.unparse(node) if hasattr(ast, "unparse") else "<expr>"


def _annotation_str(node: ast.expr | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node) if hasattr(ast, "unparse") else _node_name(node)
    except Exception:
        return None


def _decorator_names(decorators: list[ast.expr]) -> tuple[str, ...]:
    return tuple(_node_name(d) for d in decorators)


def _first_docstring(body: list[ast.stmt]) -> str | None:
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        val = body[0].value.value
        if isinstance(val, str):
            return val[:200].strip()
    return None


def _build_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Construct a readable function signature string."""
    try:
        args = node.args
        parts: list[str] = []
        for arg in args.args:
            ann = _annotation_str(arg.annotation)
            parts.append(f"{arg.arg}: {ann}" if ann else arg.arg)
        ret = _annotation_str(node.returns)
        sig = f"def {node.name}({', '.join(parts)})"
        if ret:
            sig += f" -> {ret}"
        return sig
    except Exception:
        return f"def {node.name}(...)"


# ---------------------------------------------------------------------------
# Visitor
# ---------------------------------------------------------------------------

class _AstVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.functions: list[AstFunctionInfo] = []
        self.classes: list[AstClassInfo] = []
        self.imports: list[AstImportInfo] = []
        self.top_level_names: list[str] = []
        self._class_stack: list[str] = []

    # -- imports ---------------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        self.imports.append(AstImportInfo(
            module="",
            names=tuple(alias.name for alias in node.names),
            is_from=False,
            line=node.lineno,
        ))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.append(AstImportInfo(
            module=node.module or "",
            names=tuple(
                alias.asname or alias.name
                for alias in node.names
                if alias.name != "*"
            ),
            is_from=True,
            line=node.lineno,
        ))
        self.generic_visit(node)

    # -- classes ---------------------------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        methods = [
            n.name
            for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        self.classes.append(AstClassInfo(
            name=node.name,
            line=node.lineno,
            bases=tuple(_node_name(b) for b in node.bases),
            decorators=_decorator_names(node.decorator_list),
            methods=tuple(methods),
            docstring=_first_docstring(node.body),
        ))
        self.generic_visit(node)
        self._class_stack.pop()

    # -- functions / methods ---------------------------------------------------

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        is_method = bool(self._class_stack)
        arg_types = tuple(
            _annotation_str(arg.annotation) or ""
            for arg in node.args.args
            if arg.annotation is not None
        )
        self.functions.append(AstFunctionInfo(
            name=node.name,
            line=node.lineno,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            is_method=is_method,
            decorators=_decorator_names(node.decorator_list),
            return_annotation=_annotation_str(node.returns),
            arg_types=arg_types,
            docstring=_first_docstring(node.body),
            signature=_build_signature(node),
        ))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_python_ast(source: str) -> AstExtractionResult:
    """Parse *source* as Python and return a rich AST extraction result.

    Falls back gracefully on syntax errors — callers should check
    ``result.success`` and fall back to regex extraction if False.
    """
    result = AstExtractionResult()
    if not source or not source.strip():
        return result
    try:
        tree = ast.parse(source, type_comments=True)
    except SyntaxError as exc:
        LOGGER.debug("ast.parse failed: %s", exc)
        result.parse_error = str(exc)
        return result

    visitor = _AstVisitor()
    visitor.visit(tree)
    result.functions = visitor.functions
    result.classes = visitor.classes
    result.imports = visitor.imports

    # Collect top-level names (functions, classes, assignments at module level)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            result.top_level_names.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    result.top_level_names.append(target.id)

    LOGGER.debug(
        "ast extraction: %d functions, %d classes, %d imports",
        len(result.functions),
        len(result.classes),
        len(result.imports),
    )
    return result
