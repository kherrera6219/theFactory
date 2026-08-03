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
    # Side-effect analysis (UPG-41). ``purity`` is deliberately three-valued:
    # absence of detected effects is NOT proof of purity, because a call to a
    # function this analysis cannot see could do anything.
    side_effects: tuple[str, ...] = ()
    purity: str = "UNKNOWN"  # "PURE" | "IMPURE" | "UNKNOWN"
    # Ordered opcode stream over the function body (UPG-41), as
    # ``("OPCODE", "detail")`` pairs. Replaces the RIR's single synthetic
    # EXTRACT_CONCEPT op with a real statement sequence.
    ops: tuple[tuple[str, str], ...] = ()


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
        side_effects, purity = _analyse_side_effects(node)
        ops = _body_op_stream(node)
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
            side_effects=side_effects,
            purity=purity,
            ops=ops,
        ))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)


# ---------------------------------------------------------------------------
# Side-effect analysis (UPG-41)
#
# Replaces the previous RIR purity derivation, which was
# ``"IMPURE" if payload.get("intent") else "PURE"`` -- purity decided by whether
# an unrelated string happened to be truthy.
#
# The governing rule here is that **absence of evidence is not evidence of
# purity**. A function whose body contains a call this analysis cannot resolve
# could do anything, so it is reported UNKNOWN rather than PURE. Only a function
# that demonstrably touches nothing outside itself earns PURE.
# ---------------------------------------------------------------------------

# Builtins that cannot themselves cause an observable effect. Calling one does
# not prevent a PURE verdict. Deliberately conservative -- anything not on this
# list makes the result UNKNOWN at best.
_PURE_BUILTINS = frozenset({
    "abs", "all", "any", "ascii", "bin", "bool", "bytes", "callable", "chr",
    "complex", "dict", "divmod", "enumerate", "filter", "float", "format",
    "frozenset", "getattr", "hasattr", "hash", "hex", "id", "int", "isinstance",
    "issubclass", "iter", "len", "list", "map", "max", "min", "next", "oct",
    "ord", "pow", "range", "repr", "reversed", "round", "set", "slice", "sorted",
    "str", "sum", "tuple", "type", "zip",
})

# Calls that are unambiguously effectful, mapped to the effect they cause.
_EFFECTFUL_CALLS: dict[str, str] = {
    "print": "io.stdout",
    "open": "io.filesystem",
    "input": "io.stdin",
    "exec": "dynamic_execution",
    "eval": "dynamic_execution",
    "compile": "dynamic_execution",
    "exit": "process_control",
    "quit": "process_control",
    "breakpoint": "process_control",
}

# Module prefixes whose use implies an effect category.
_EFFECTFUL_MODULES: dict[str, str] = {
    "os": "io.filesystem",
    "io": "io.filesystem",
    "shutil": "io.filesystem",
    "pathlib": "io.filesystem",
    "tempfile": "io.filesystem",
    "socket": "io.network",
    "requests": "io.network",
    "httpx": "io.network",
    "urllib": "io.network",
    "http": "io.network",
    "subprocess": "process_control",
    "sys": "process_control",
    "threading": "concurrency",
    "multiprocessing": "concurrency",
    "asyncio": "concurrency",
    "random": "nondeterminism",
    "time": "nondeterminism",
    "datetime": "nondeterminism",
    "uuid": "nondeterminism",
    "secrets": "nondeterminism",
    "logging": "io.logging",
    "sqlite3": "io.database",
    "psycopg": "io.database",
    "redis": "io.database",
}


def _root_name(node: ast.AST) -> str | None:
    """Return the leftmost identifier of a dotted or subscripted expression.

    Both ``cfg.seen`` and ``cfg["seen"]`` must resolve to ``cfg`` — walking only
    ``Attribute`` silently misses every subscript mutation, which is the more
    common way Python code mutates a caller's dict or list.
    """
    current = node
    while isinstance(current, ast.Attribute | ast.Subscript):
        current = current.value
    if isinstance(current, ast.Name):
        return current.id
    return None


_MAX_OPS = 64


def _body_op_stream(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[tuple[str, str], ...]:
    """Return an ordered opcode stream over the function body.

    The RIR previously emitted exactly one synthetic ``EXTRACT_CONCEPT`` op per
    function regardless of what the function did. This walks the real statement
    sequence instead, one op per statement, descending into control-flow bodies
    so a branch's contents are represented rather than collapsed.

    Capped at ``_MAX_OPS`` so a pathological function cannot inflate the RIR
    artifact without bound; truncation is recorded as a final ``TRUNCATED`` op
    so a consumer can see the stream is partial rather than complete.
    """
    ops: list[tuple[str, str]] = []

    def emit(opcode: str, detail: str = "") -> bool:
        if len(ops) >= _MAX_OPS:
            return False
        ops.append((opcode, detail))
        return True

    def walk(statements: list[ast.stmt], depth: int) -> bool:
        for statement in statements:
            if isinstance(statement, ast.Return):
                if not emit("RETURN", _short_expr(statement.value)):
                    return False
            elif isinstance(statement, ast.Assign | ast.AnnAssign | ast.AugAssign):
                targets = (
                    statement.targets
                    if isinstance(statement, ast.Assign)
                    else [statement.target]
                )
                names = ",".join(filter(None, (_node_name(t) for t in targets)))
                if not emit("ASSIGN", names):
                    return False
            elif isinstance(statement, ast.If):
                if not emit("BRANCH", _short_expr(statement.test)):
                    return False
                if not walk(statement.body, depth + 1):
                    return False
                if statement.orelse and not walk(statement.orelse, depth + 1):
                    return False
            elif isinstance(statement, ast.For | ast.AsyncFor | ast.While):
                if not emit("LOOP", type(statement).__name__.upper()):
                    return False
                if not walk(statement.body, depth + 1):
                    return False
            elif isinstance(statement, ast.With | ast.AsyncWith):
                if not emit("CONTEXT", ""):
                    return False
                if not walk(statement.body, depth + 1):
                    return False
            elif isinstance(statement, ast.Try):
                if not emit("TRY", ""):
                    return False
                if not walk(statement.body, depth + 1):
                    return False
                for handler in statement.handlers:
                    if not emit("HANDLE", _short_expr(handler.type)):
                        return False
            elif isinstance(statement, ast.Raise):
                if not emit("RAISE", _short_expr(statement.exc)):
                    return False
            elif isinstance(statement, ast.Expr):
                value = statement.value
                if isinstance(value, ast.Call):
                    if not emit("CALL", _node_name(value.func) or ""):
                        return False
                elif isinstance(value, ast.Constant) and isinstance(value.value, str):
                    continue  # docstring / bare string, not an operation
                elif not emit("EVAL", _short_expr(value)):
                    return False
            elif isinstance(statement, ast.Pass):
                continue
            elif isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                if not emit("DEFINE", statement.name):
                    return False
            elif not emit(type(statement).__name__.upper(), ""):
                return False
        return True

    completed = walk(node.body, 0)
    if not completed:
        ops.append(("TRUNCATED", str(_MAX_OPS)))
    return tuple(ops)


def _short_expr(node: ast.AST | None, limit: int = 48) -> str:
    """Return a short, safe textual form of an expression for op detail."""
    if node is None:
        return ""
    try:
        text = ast.unparse(node)
    except Exception:
        return ""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _analyse_side_effects(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[tuple[str, ...], str]:
    """Return ``(side_effects, purity)`` for one function definition.

    Detected effects:

    * ``global_state`` / ``nonlocal_state`` -- ``global``/``nonlocal`` statements
      and assignments to names declared in them
    * ``argument_mutation`` -- assignment to an attribute or subscript of a
      parameter, which mutates the caller's object
    * ``io.*`` / ``process_control`` / ``concurrency`` / ``nondeterminism`` --
      resolved via ``_EFFECTFUL_CALLS`` and ``_EFFECTFUL_MODULES``
    * ``async_suspension`` -- ``await``, which yields control to a scheduler

    Purity verdict:

    * ``IMPURE`` -- at least one effect was positively identified
    * ``PURE``   -- no effects, and every call resolved to a known-pure builtin
    * ``UNKNOWN`` -- no effects found, but the body calls something this
      analysis cannot resolve, so purity cannot be asserted either way

    That third state is the point of the exercise: the previous implementation
    had no way to say "not determined" and so asserted a purity value for every
    function regardless of whether anything had been examined.
    """
    effects: set[str] = set()
    unresolved_call = False

    # Parameter names -- assignment into one of these mutates the caller's data.
    args = node.args
    param_names = {
        a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)
    }
    if args.vararg:
        param_names.add(args.vararg.arg)
    if args.kwarg:
        param_names.add(args.kwarg.arg)

    declared_global: set[str] = set()

    for child in ast.walk(node):
        # Do not descend into nested function definitions: their effects belong
        # to them, not to this function, unless this function calls them.
        if child is not node and isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            continue

        if isinstance(child, ast.Global):
            effects.add("global_state")
            declared_global.update(child.names)
        elif isinstance(child, ast.Nonlocal):
            effects.add("nonlocal_state")
            declared_global.update(child.names)
        elif isinstance(child, ast.Await):
            effects.add("async_suspension")
        elif isinstance(child, ast.Assign | ast.AugAssign | ast.AnnAssign):
            targets = child.targets if isinstance(child, ast.Assign) else [child.target]
            for target in targets:
                if isinstance(target, ast.Attribute | ast.Subscript):
                    root = _root_name(target)
                    if root and root in param_names:
                        effects.add("argument_mutation")
                    elif root and root not in param_names:
                        # Mutating something that is neither a parameter nor a
                        # local binding reaches outside this function.
                        if root in declared_global:
                            effects.add("global_state")
        elif isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                name = func.id
                if name in _EFFECTFUL_CALLS:
                    effects.add(_EFFECTFUL_CALLS[name])
                elif name not in _PURE_BUILTINS:
                    unresolved_call = True
            elif isinstance(func, ast.Attribute):
                root = _root_name(func)
                if root and root in _EFFECTFUL_MODULES:
                    effects.add(_EFFECTFUL_MODULES[root])
                else:
                    # A method call on an object of unknown provenance.
                    unresolved_call = True
            else:
                unresolved_call = True

    if effects:
        return tuple(sorted(effects)), "IMPURE"
    if unresolved_call:
        return (), "UNKNOWN"
    return (), "PURE"


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
