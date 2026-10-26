"""js_ast_extractor.py — JavaScript/TypeScript AST-based extraction.

Architecture notes
------------------
This module mirrors the design of ``ast_extractor.py`` for Python:
  - ``extract_js_ast(source)`` returns a ``JsAstExtractionResult``
  - ``JavaScriptAstExtractor`` (in ``language_extractor.py``) inherits from
    ``JavaScriptExtractor``, calls ``super().extract()`` first (regex runs
    for concept/LogicNode detection), then replaces structural fields with
    AST-derived equivalents including parameter/return types, purity,
    side effects, and statement opcode streams.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

LOGGER = logging.getLogger(__name__)

_PURE_JS_CALLS = frozenset({
    "Math.abs", "Math.ceil", "Math.floor", "Math.max", "Math.min", "Math.pow",
    "Math.round", "Math.sqrt", "Math.trunc", "Number", "String", "Boolean",
    "BigInt", "parseInt", "parseFloat", "isNaN", "isFinite", "JSON.parse",
    "JSON.stringify", "Object.keys", "Object.values", "Object.entries",
    "Object.assign", "Object.freeze", "Array.isArray", "Array.from",
})

_PURE_JS_METHODS = frozenset({
    "map", "filter", "reduce", "slice", "concat", "find", "findIndex",
    "some", "every", "includes", "indexOf", "join", "split", "trim",
    "toLowerCase", "toUpperCase", "startsWith", "endsWith", "replace",
})


@dataclass(frozen=True, slots=True)
class JsFunctionInfo:
    name: str
    line: int
    is_async: bool
    is_arrow: bool
    is_method: bool
    signature: str
    arg_types: tuple[str, ...] = ()
    return_type: str | None = None
    side_effects: tuple[str, ...] = ()
    purity: str = "UNKNOWN"
    ops: tuple[tuple[str, str], ...] = ()


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

    ts_signatures = _extract_ts_signatures(source)
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
    _walk_js_tree(tree, result, ts_signatures)
    return result


def _parse_ts_param_types(param_block: str) -> tuple[str, ...]:
    if not param_block.strip():
        return ()
    types: list[str] = []
    for raw_param in param_block.split(","):
        param = raw_param.strip()
        if not param or ":" not in param:
            continue
        type_part = param.split(":", 1)[1].split("=", 1)[0].strip()
        if type_part:
            types.append(type_part)
    return tuple(types)


def _extract_ts_signatures(
    source: str,
) -> dict[str, tuple[tuple[str, ...], str | None]]:
    """Recover explicit TypeScript parameter and return types before stripping."""
    signatures: dict[str, tuple[tuple[str, ...], str | None]] = {}
    patterns = (
        re.compile(
            r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)"
            r"(?:\s*:\s*([A-Za-z0-9_$.<>,\[\]|&?]+))?"
        ),
        re.compile(
            r"(?:const|let|var)\s+(\w+)\s*(?::[^=]+)?=\s*(?:async\s*)?\(([^)]*)\)"
            r"(?:\s*:\s*([A-Za-z0-9_$.<>,\[\]|&?]+))?\s*=>"
        ),
        re.compile(
            r"^\s*(?:public\s+|private\s+|protected\s+|async\s+|static\s+)*"
            r"(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)\s*:\s*([A-Za-z0-9_$.<>,\[\]|&?]+)",
            re.MULTILINE,
        ),
    )
    for pattern in patterns:
        for match in pattern.finditer(source):
            fn_name = match.group(1).strip()
            if fn_name in {"if", "for", "while", "switch", "catch", "constructor"}:
                continue
            arg_types = _parse_ts_param_types(match.group(2))
            ret_type = match.group(3).strip() if match.group(3) else None
            if arg_types or ret_type:
                signatures[fn_name] = (arg_types, ret_type)
    return signatures


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


def _callee_name(callee: Any) -> str:
    if callee is None:
        return ""
    ntype = _node_type(callee)
    if ntype == "Identifier":
        return _name(callee)
    if ntype == "MemberExpression":
        obj = _callee_name(getattr(callee, "object", None))
        prop = _name(getattr(callee, "property", None))
        return f"{obj}.{prop}" if obj and prop else (prop or obj)
    return _name(callee)


def _params(node: Any) -> str:
    names = [
        _name(param, "arg")
        for param in (getattr(node, "params", None) or [])
        if _name(param, "arg")
    ]
    return ", ".join(names)


def _analyse_js_body(
    fn_node: Any,
    *,
    is_async: bool,
) -> tuple[tuple[str, ...], str, tuple[tuple[str, str], ...]]:
    """Inspect an esprima function node for side effects, purity, and opcodes."""
    effects: list[str] = []
    ops: list[tuple[str, str]] = []
    has_unknown_call = False

    if is_async:
        effects.append("io.async")

    body = getattr(fn_node, "body", None)
    if body is None:
        return tuple(dict.fromkeys(effects)), "IMPURE" if effects else "UNKNOWN", ()

    def _visit(sub: Any) -> None:
        nonlocal has_unknown_call
        ntype = _node_type(sub)
        if not ntype:
            return
        if ntype in {"FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"} and sub is not fn_node:
            return

        if ntype == "ReturnStatement":
            arg = getattr(sub, "argument", None)
            ops.append(("RETURN", _name(arg, "value") if arg is not None else "void"))
        elif ntype in {"IfStatement", "SwitchStatement", "ConditionalExpression"}:
            ops.append(("BRANCH", ntype))
        elif ntype in {
            "ForStatement",
            "ForInStatement",
            "ForOfStatement",
            "WhileStatement",
            "DoWhileStatement",
        }:
            ops.append(("LOOP", ntype))
        elif ntype in {"TryStatement", "ThrowStatement"}:
            ops.append(("TRY", ntype))
        elif ntype == "AwaitExpression":
            ops.append(("AWAIT", "await"))
            effects.append("io.async")
        elif ntype == "VariableDeclarator":
            target_name = _name(getattr(sub, "id", None), "var")
            ops.append(("ASSIGN", target_name))
        elif ntype == "AssignmentExpression":
            left = getattr(sub, "left", None)
            left_name = _callee_name(left) or _name(left, "target")
            ops.append(("ASSIGN", left_name))
            if left_name.startswith(("this.", "window.", "global.", "globalThis.")):
                effects.append("state.mutation")
        elif ntype == "CallExpression":
            cname = _callee_name(getattr(sub, "callee", None))
            ops.append(("CALL", cname or "anonymous"))
            method_tail = cname.rsplit(".", 1)[-1] if "." in cname else ""
            if cname.startswith("console."):
                effects.append("io.stdout")
            elif cname == "fetch" or cname.startswith(("axios.", "http.", "https.")):
                effects.append("io.network")
            elif cname.startswith("fs."):
                effects.append("io.filesystem")
            elif cname in _PURE_JS_CALLS or method_tail in _PURE_JS_METHODS:
                pass
            else:
                has_unknown_call = True

        for val in vars(sub).values() if hasattr(sub, "__dict__") else []:
            if hasattr(val, "type"):
                _visit(val)
            elif isinstance(val, list):
                for item in val:
                    if hasattr(item, "type"):
                        _visit(item)

    _visit(body)
    if _node_type(body) != "BlockStatement" and not any(op[0] == "RETURN" for op in ops):
        ops.append(("RETURN", _name(body, "expr")))

    dedup_effects = tuple(dict.fromkeys(effects))
    if dedup_effects:
        purity = "IMPURE"
    elif has_unknown_call:
        purity = "UNKNOWN"
    else:
        purity = "PURE"
    return dedup_effects, purity, tuple(ops[:32])


def _record_function(
    result: JsAstExtractionResult,
    *,
    name: str,
    node: Any,
    ts_signatures: dict[str, tuple[tuple[str, ...], str | None]],
    is_arrow: bool = False,
    is_method: bool = False,
) -> None:
    if not name:
        return
    if any(existing.name == name and existing.line == _line(node) for existing in result.functions):
        return
    is_async = bool(getattr(node, "async", False))
    prefix = "async " if is_async else ""
    if is_method:
        signature = f"{prefix}{name}({_params(node)})"
    elif is_arrow:
        signature = f"{prefix}const {name} = ({_params(node)}) =>"
    else:
        signature = f"{prefix}function {name}({_params(node)})"

    arg_types, return_type = ts_signatures.get(name, ((), None))
    side_effects, purity, ops = _analyse_js_body(node, is_async=is_async)
    result.functions.append(
        JsFunctionInfo(
            name=name,
            line=_line(node),
            is_async=is_async,
            is_arrow=is_arrow,
            is_method=is_method,
            signature=signature,
            arg_types=arg_types,
            return_type=return_type,
            side_effects=side_effects,
            purity=purity,
            ops=ops,
        )
    )


def _record_class(
    result: JsAstExtractionResult,
    node: Any,
    ts_signatures: dict[str, tuple[tuple[str, ...], str | None]],
) -> None:
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
            ts_signatures=ts_signatures,
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


def _walk_js_tree(
    node: Any,
    result: JsAstExtractionResult,
    ts_signatures: dict[str, tuple[tuple[str, ...], str | None]],
) -> None:
    node_type = _node_type(node)
    if node_type == "FunctionDeclaration":
        _record_function(
            result,
            name=_name(getattr(node, "id", None), "<anonymous>"),
            node=node,
            ts_signatures=ts_signatures,
        )
    elif node_type == "VariableDeclarator":
        init = getattr(node, "init", None)
        init_type = _node_type(init)
        if init_type in {"ArrowFunctionExpression", "FunctionExpression"}:
            _record_function(
                result,
                name=_name(getattr(node, "id", None)),
                node=init,
                ts_signatures=ts_signatures,
                is_arrow=init_type == "ArrowFunctionExpression",
            )
    elif node_type == "ClassDeclaration":
        _record_class(result, node, ts_signatures)
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
            _walk_js_tree(value, result, ts_signatures)
        elif isinstance(value, list):
            for item in value:
                if hasattr(item, "type"):
                    _walk_js_tree(item, result, ts_signatures)
