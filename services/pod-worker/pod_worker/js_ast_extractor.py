"""js_ast_extractor.py — JavaScript/TypeScript AST-based extraction.

Architecture notes
------------------
This module mirrors the design of ``ast_extractor.py`` for Python:
  - ``extract_js_ast(source)`` returns a ``JsAstExtractionResult``
  - ``JsAstExtractor`` (in ``language_extractor.py``) should inherit from
    ``JavaScriptExtractor``, call ``super().extract()`` first (regex runs
    for concept/LogicNode detection), then replace structural fields with
    AST-derived equivalents.

Known regex extractor limitations this would fix
-------------------------------------------------
- Class shorthand methods (no ``function`` keyword) are invisible to regex.
- Arrow function names assigned to class fields are not detected.
- TypeScript-specific syntax (``interface``, ``type``, generics) is unparsed.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class JsFunctionInfo:
    name: str
    line: int
    is_async: bool
    is_arrow: bool
    is_method: bool
    signature: str


@dataclass(frozen=True, slots=True)
class JsClassInfo:
    name: str
    line: int
    extends: str | None
    methods: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class JsImportInfo:
    module: str
    names: tuple[str, ...]
    is_default: bool
    line: int


@dataclass
class JsAstExtractionResult:
    """AST-derived extraction result for one JS/TS file."""

    functions: list[JsFunctionInfo] = field(default_factory=list)
    classes: list[JsClassInfo] = field(default_factory=list)
    imports: list[JsImportInfo] = field(default_factory=list)
    success: bool = False
    error: str | None = None


def extract_js_ast(source: str) -> JsAstExtractionResult:
    """Parse *source* with a JavaScript AST parser and return structured data.

    Returns ``success=False`` when ``esprima`` is unavailable or parsing fails;
    callers should then fall back to the regex extractor.
    """
    try:
        import esprima  # type: ignore[import]
    except ImportError:
        return JsAstExtractionResult(
            success=False,
            error="esprima not installed — add esprima to pod-worker requirements.txt",
        )

    clean_source = _strip_ts_syntax(source)
    try:
        tree = esprima.parseModule(clean_source, loc=True, tolerant=True)
    except Exception:
        try:
            tree = esprima.parseScript(clean_source, loc=True, tolerant=True)
        except Exception as exc:
            LOGGER.debug("JS AST parse failed: %s", exc)
            return JsAstExtractionResult(success=False, error=str(exc))

    result = JsAstExtractionResult(success=True)
    _walk_js_tree(tree, result)
    return result


def _strip_ts_syntax(source: str) -> str:
    """Remove a conservative subset of TypeScript syntax before esprima parse."""
    cleaned = _remove_type_declarations(source)
    cleaned = re.sub(r"\b(public|private|protected|readonly)\s+", "", cleaned)
    cleaned = re.sub(
        r":\s*[A-Za-z_$][A-Za-z0-9_$.<>,\[\]|&?\s]*(?=\s*[,)=;{])",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\s+as\s+[A-Za-z_$][A-Za-z0-9_$.<>,\[\]|&?\s]*", "", cleaned)
    return cleaned


def _remove_type_declarations(source: str) -> str:
    lines = source.splitlines()
    kept: list[str] = []
    skipping = False
    brace_depth = 0
    for line in lines:
        stripped = line.strip()
        starts_type = bool(re.match(r"^(?:export\s+)?(?:interface|type)\s+\w", stripped))
        if starts_type and not skipping:
            skipping = True
            brace_depth = line.count("{") - line.count("}")
            if brace_depth <= 0 and (";" in line or "=" in line):
                skipping = False
            continue
        if skipping:
            brace_depth += line.count("{") - line.count("}")
            if brace_depth <= 0 and ("}" in line or ";" in line):
                skipping = False
            continue
        kept.append(line)
    return "\n".join(kept)


def _node_type(node: Any) -> str:
    return str(getattr(node, "type", "") or "")


def _line(node: Any) -> int:
    loc = getattr(node, "loc", None)
    start = getattr(loc, "start", None) if loc is not None else None
    return int(getattr(start, "line", 0) or 0)


def _name(node: Any, fallback: str = "") -> str:
    if node is None:
        return fallback
    value = getattr(node, "name", None)
    if value:
        return str(value)
    value = getattr(node, "value", None)
    if value:
        return str(value)
    return fallback


def _params(node: Any) -> str:
    names = [
        _name(param, "arg")
        for param in (getattr(node, "params", None) or [])
        if _name(param, "arg")
    ]
    return ", ".join(names)


def _record_function(
    result: JsAstExtractionResult,
    *,
    name: str,
    node: Any,
    is_arrow: bool = False,
    is_method: bool = False,
) -> None:
    if not name:
        return
    if any(existing.name == name and existing.line == _line(node) for existing in result.functions):
        return
    prefix = "async " if bool(getattr(node, "async", False)) else ""
    if is_method:
        signature = f"{prefix}{name}({_params(node)})"
    elif is_arrow:
        signature = f"{prefix}const {name} = ({_params(node)}) =>"
    else:
        signature = f"{prefix}function {name}({_params(node)})"
    result.functions.append(
        JsFunctionInfo(
            name=name,
            line=_line(node),
            is_async=bool(getattr(node, "async", False)),
            is_arrow=is_arrow,
            is_method=is_method,
            signature=signature,
        )
    )


def _record_class(result: JsAstExtractionResult, node: Any) -> None:
    name = _name(getattr(node, "id", None), "<anonymous>")
    body = getattr(getattr(node, "body", None), "body", None) or []
    methods = tuple(
        _name(getattr(member, "key", None))
        for member in body
        if _node_type(member) == "MethodDefinition" and _name(getattr(member, "key", None))
    )
    result.classes.append(
        JsClassInfo(
            name=name,
            line=_line(node),
            extends=_name(getattr(node, "superClass", None)) or None,
            methods=methods,
        )
    )
    for member in body:
        if _node_type(member) != "MethodDefinition":
            continue
        value = getattr(member, "value", None)
        _record_function(
            result,
            name=_name(getattr(member, "key", None)),
            node=value or member,
            is_method=True,
        )


def _record_import(result: JsAstExtractionResult, node: Any) -> None:
    source = _name(getattr(node, "source", None))
    specifiers = getattr(node, "specifiers", None) or []
    names = tuple(
        _name(getattr(specifier, "local", None))
        for specifier in specifiers
        if _name(getattr(specifier, "local", None))
    )
    result.imports.append(
        JsImportInfo(
            module=source,
            names=names,
            is_default=any(
                _node_type(specifier) == "ImportDefaultSpecifier" for specifier in specifiers
            ),
            line=_line(node),
        )
    )


def _walk_js_tree(node: Any, result: JsAstExtractionResult) -> None:
    node_type = _node_type(node)
    if node_type == "FunctionDeclaration":
        _record_function(result, name=_name(getattr(node, "id", None), "<anonymous>"), node=node)
    elif node_type == "VariableDeclarator":
        init = getattr(node, "init", None)
        init_type = _node_type(init)
        if init_type in {"ArrowFunctionExpression", "FunctionExpression"}:
            _record_function(
                result,
                name=_name(getattr(node, "id", None)),
                node=init,
                is_arrow=init_type == "ArrowFunctionExpression",
            )
    elif node_type == "ClassDeclaration":
        _record_class(result, node)
    elif node_type == "ImportDeclaration":
        _record_import(result, node)
    elif node_type == "CallExpression":
        callee = getattr(node, "callee", None)
        if _name(callee) == "require":
            args = getattr(node, "arguments", None) or []
            if args:
                result.imports.append(
                    JsImportInfo(
                        module=_name(args[0]),
                        names=(),
                        is_default=False,
                        line=_line(node),
                    )
                )

    for value in vars(node).values() if hasattr(node, "__dict__") else []:
        if hasattr(value, "type"):
            _walk_js_tree(value, result)
        elif isinstance(value, list):
            for item in value:
                if hasattr(item, "type"):
                    _walk_js_tree(item, result)
