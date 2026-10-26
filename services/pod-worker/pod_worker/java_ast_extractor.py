"""java_ast_extractor.py — Java AST-based extraction.

Architecture notes
------------------
Mirrors the design of ``ast_extractor.py`` for Python:
  - ``extract_java_ast(source)`` returns a ``JavaAstExtractionResult``
  - ``JavaAstExtractor`` (in ``language_extractor.py``) inherits from
    ``JavaExtractor``, calls ``super().extract()`` first (regex runs for
    concept/LogicNode detection), then replaces structural fields with
    AST-derived equivalents including parameter/return types, purity,
    side effects, and statement opcode streams.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

LOGGER = logging.getLogger(__name__)

_PURE_JAVA_QUALIFIERS = frozenset({
    "Math", "StrictMath", "String", "Integer", "Long", "Double", "Float",
    "Boolean", "Objects", "Optional", "Collections", "Arrays", "List", "Map", "Set",
})

_PURE_JAVA_METHODS = frozenset({
    "equals", "hashCode", "toString", "compareTo", "length", "size", "isEmpty",
    "get", "contains", "containsKey", "stream", "filter", "map", "reduce",
    "collect", "of", "valueOf", "parseInt", "parseDouble", "parseLong",
    "abs", "max", "min", "sqrt", "pow", "round", "floor", "ceil",
})


@dataclass(frozen=True, slots=True)
class JavaMethodInfo:
    name: str
    line: int
    return_type: str
    parameters: tuple[str, ...]
    modifiers: tuple[str, ...]
    annotations: tuple[str, ...]
    signature: str
    side_effects: tuple[str, ...] = ()
    purity: str = "UNKNOWN"
    ops: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class JavaClassInfo:
    name: str
    line: int
    kind: str  # "class" | "interface" | "enum" | "annotation"
    extends: str | None
    implements: tuple[str, ...]
    annotations: tuple[str, ...]
    methods: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class JavaImportInfo:
    qualified_name: str
    is_static: bool
    is_wildcard: bool
    line: int


@dataclass
class JavaAstExtractionResult:
    """AST-derived extraction result for one Java file."""

    methods: list[JavaMethodInfo] = field(default_factory=list)
    classes: list[JavaClassInfo] = field(default_factory=list)
    imports: list[JavaImportInfo] = field(default_factory=list)
    package: str | None = None
    success: bool = False
    error: str | None = None


def extract_java_ast(source: str) -> JavaAstExtractionResult:
    """Parse *source* with a Java AST parser and return structured data.

    Returns ``success=False`` when ``javalang`` is unavailable or parsing fails;
    callers should then fall back to the regex extractor.
    """
    try:
        import javalang  # type: ignore[import]
    except ImportError:
        return JavaAstExtractionResult(
            success=False,
            error="javalang not installed — add javalang to pod-worker requirements.txt",
        )

    try:
        tree = javalang.parse.parse(source)
    except Exception as exc:
        LOGGER.debug("Java AST parse failed: %s", exc)
        return JavaAstExtractionResult(success=False, error=str(exc))

    result = JavaAstExtractionResult(
        package=tree.package.name if getattr(tree, "package", None) else None,
        success=True,
    )

    for import_node in getattr(tree, "imports", []) or []:
        result.imports.append(
            JavaImportInfo(
                qualified_name=str(getattr(import_node, "path", "") or ""),
                is_static=bool(getattr(import_node, "static", False)),
                is_wildcard=bool(getattr(import_node, "wildcard", False)),
                line=_line(import_node),
            )
        )

    type_nodes = (
        javalang.tree.ClassDeclaration,
        javalang.tree.InterfaceDeclaration,
        javalang.tree.EnumDeclaration,
        javalang.tree.AnnotationDeclaration,
    )
    for _path, node in tree:
        if isinstance(node, type_nodes):
            result.classes.append(_class_info(node, javalang))
        elif isinstance(
            node,
            (javalang.tree.MethodDeclaration, javalang.tree.ConstructorDeclaration),
        ):
            result.methods.append(_method_info(node))

    return result


def _line(node: Any) -> int:
    position = getattr(node, "position", None)
    line = getattr(position, "line", 0) if position is not None else 0
    return int(line or 0)


def _type_name(node: Any) -> str:
    if node is None:
        return "void"
    if isinstance(node, str):
        return node
    name = getattr(node, "name", None)
    if name:
        dims = getattr(node, "dimensions", None) or []
        suffix = "[]" * len(dims) if isinstance(dims, list) else ""
        return f"{name}{suffix}"
    pattern_type = getattr(node, "pattern_type", None)
    if pattern_type:
        return str(pattern_type)
    return str(node)


def _annotation_names(node: Any) -> tuple[str, ...]:
    return tuple(
        str(getattr(annotation, "name", "") or "")
        for annotation in (getattr(node, "annotations", None) or [])
        if str(getattr(annotation, "name", "") or "")
    )


def _analyse_java_method(
    node: Any,
) -> tuple[tuple[str, ...], str, tuple[tuple[str, str], ...]]:
    """Inspect a javalang MethodDeclaration/ConstructorDeclaration for effects, purity, and ops."""
    body = getattr(node, "body", None)
    if body is None:
        return (), "UNKNOWN", ()

    effects: list[str] = []
    ops: list[tuple[str, str]] = []
    has_unknown_call = False

    try:
        iterator = iter(node)
    except Exception:
        return (), "UNKNOWN", ()

    for _path, sub in iterator:
        if sub is node:
            continue
        cls_name = sub.__class__.__name__
        if cls_name == "ReturnStatement":
            expr = getattr(sub, "expression", None)
            detail = str(getattr(expr, "member", None) or getattr(expr, "value", None) or "value")
            ops.append(("RETURN", detail))
        elif cls_name in {"IfStatement", "SwitchStatement", "TernaryExpression"}:
            ops.append(("BRANCH", cls_name))
        elif cls_name in {"ForStatement", "WhileStatement", "DoStatement"}:
            ops.append(("LOOP", cls_name))
        elif cls_name in {"TryStatement", "ThrowStatement", "SynchronizedStatement"}:
            ops.append(("TRY", cls_name))
            if cls_name == "SynchronizedStatement":
                effects.append("concurrency.lock")
        elif cls_name == "LocalVariableDeclaration":
            decls = getattr(sub, "declarators", None) or []
            for decl in decls:
                vname = str(getattr(decl, "name", "") or "var")
                ops.append(("ASSIGN", vname))
        elif cls_name == "Assignment":
            lhs = getattr(sub, "expressionl", None)
            lhs_name = str(getattr(lhs, "member", None) or "field")
            ops.append(("ASSIGN", lhs_name))
            if getattr(lhs, "qualifier", None) in {"this", "super"}:
                effects.append("state.mutation")
        elif cls_name == "MethodInvocation":
            member = str(getattr(sub, "member", "") or "call")
            qualifier = str(getattr(sub, "qualifier", "") or "")
            full_call = f"{qualifier}.{member}" if qualifier else member
            ops.append(("CALL", full_call))
            if qualifier.startswith(("System.out", "System.err")):
                effects.append("io.stdout")
            elif qualifier.startswith(("Files", "File", "Paths", "FileInputStream", "FileOutputStream")):
                effects.append("io.filesystem")
            elif qualifier.startswith(("HttpClient", "URL", "Socket", "HttpURLConnection")):
                effects.append("io.network")
            elif qualifier in _PURE_JAVA_QUALIFIERS or member in _PURE_JAVA_METHODS:
                pass
            else:
                has_unknown_call = True

    dedup_effects = tuple(dict.fromkeys(effects))
    if dedup_effects:
        purity = "IMPURE"
    elif has_unknown_call:
        purity = "UNKNOWN"
    else:
        purity = "PURE"
    return dedup_effects, purity, tuple(ops[:32])


def _method_info(node: Any) -> JavaMethodInfo:
    name = str(getattr(node, "name", "") or "<anonymous>")
    parameters = tuple(
        _type_name(getattr(parameter, "type", None))
        for parameter in (getattr(node, "parameters", None) or [])
    )
    return_type = _type_name(getattr(node, "return_type", None))
    if node.__class__.__name__ == "ConstructorDeclaration":
        return_type = "<constructor>"
    modifiers = tuple(sorted(str(item) for item in (getattr(node, "modifiers", None) or [])))
    signature = f"{return_type} {name}({', '.join(parameters)})"
    side_effects, purity, ops = _analyse_java_method(node)
    return JavaMethodInfo(
        name=name,
        line=_line(node),
        return_type=return_type,
        parameters=parameters,
        modifiers=modifiers,
        annotations=_annotation_names(node),
        signature=signature,
        side_effects=side_effects,
        purity=purity,
        ops=ops,
    )


def _class_kind(node: Any, javalang: Any) -> str:
    if isinstance(node, javalang.tree.InterfaceDeclaration):
        return "interface"
    if isinstance(node, javalang.tree.EnumDeclaration):
        return "enum"
    if isinstance(node, javalang.tree.AnnotationDeclaration):
        return "annotation"
    return "class"


def _class_info(node: Any, javalang: Any) -> JavaClassInfo:
    extends = getattr(node, "extends", None)
    implements = tuple(
        _type_name(item)
        for item in (getattr(node, "implements", None) or [])
        if _type_name(item)
    )
    methods = tuple(
        str(getattr(item, "name", "") or "")
        for item in (getattr(node, "body", None) or [])
        if isinstance(
            item,
            (javalang.tree.MethodDeclaration, javalang.tree.ConstructorDeclaration),
        )
        and str(getattr(item, "name", "") or "")
    )
    return JavaClassInfo(
        name=str(getattr(node, "name", "") or "<anonymous>"),
        line=_line(node),
        kind=_class_kind(node, javalang),
        extends=_type_name(extends) if extends is not None else None,
        implements=implements,
        annotations=_annotation_names(node),
        methods=methods,
    )
