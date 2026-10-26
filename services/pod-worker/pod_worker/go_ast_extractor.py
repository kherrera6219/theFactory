"""go_ast_extractor.py — Structural and signature extraction for Go.

Recovers package, import, struct, interface, method/function signatures
(parameter types + return types), side effects, purity, and statement opcodes.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

LOGGER = logging.getLogger(__name__)

# Control feature flag
GO_AST_EXTRACTOR_ENABLED: bool = (
    os.getenv("GO_AST_EXTRACTOR_ENABLED", "true").strip().lower()
    in {"1", "true", "yes", "on"}
)


@dataclass(frozen=True, slots=True)
class GoFunctionInfo:
    name: str
    line: int
    receiver: str | None
    signature: str
    arg_types: tuple[str, ...] = ()
    return_type: str | None = None
    side_effects: tuple[str, ...] = ()
    purity: str = "UNKNOWN"
    ops: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class GoStructInfo:
    name: str
    line: int
    is_interface: bool
    fields_or_methods: tuple[str, ...] = ()


@dataclass
class GoAstExtractionResult:
    """Full structural extraction result for one Go/Systems source file."""

    package: str | None = None
    functions: list[GoFunctionInfo] = field(default_factory=list)
    structs: list[GoStructInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


def _parse_go_signature(sig_rest: str) -> tuple[tuple[str, ...], str | None]:
    """Parse Go parameter list and return type from ``(a int, b string) (int, error)``."""
    text = sig_rest.strip()
    if not text.startswith("("):
        return (), None
    depth = 0
    close_idx = -1
    for idx, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                close_idx = idx
                break
    if close_idx < 0:
        return (), None
    params_raw = text[1:close_idx].strip()
    ret_raw = text[close_idx + 1 :].strip()

    arg_types: list[str] = []
    if params_raw:
        pending_names = 0
        for part in params_raw.split(","):
            tokens = part.strip().split()
            if not tokens:
                continue
            if len(tokens) == 1:
                pending_names += 1
            else:
                type_name = " ".join(tokens[1:]).lstrip(".")
                for _ in range(pending_names + 1):
                    arg_types.append(type_name)
                pending_names = 0

    return_type: str | None = None
    if ret_raw:
        if ret_raw.startswith("(") and ret_raw.endswith(")"):
            inner = ret_raw[1:-1].strip()
            parts = [p.strip().split()[-1] for p in inner.split(",") if p.strip()]
            return_type = parts[0] if parts else None
        else:
            return_type = ret_raw.split()[0].strip()

    return tuple(arg_types), return_type


def _extract_brace_body(source: str, start_pos: int) -> str:
    open_brace = source.find("{", start_pos)
    if open_brace < 0:
        return ""
    depth = 0
    for idx in range(open_brace, min(len(source), open_brace + 16384)):
        ch = source[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace + 1 : idx]
    return ""


def _analyse_go_body(body: str) -> tuple[tuple[str, ...], str, tuple[tuple[str, str], ...]]:
    if not body.strip():
        return (), "PURE", ()
    effects: list[str] = []
    ops: list[tuple[str, str]] = []
    has_unknown_call = False

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith(("if ", "switch ", "select ")):
            ops.append(("BRANCH", line.split()[0]))
        elif line.startswith("for ") or line == "for {":
            ops.append(("LOOP", "for"))
        elif line.startswith("defer "):
            ops.append(("CALL", "defer"))
        elif line.startswith("go "):
            ops.append(("CALL", "goroutine"))
            effects.append("concurrency.goroutine")
        elif "<-" in line:
            ops.append(("CALL", "chan_op"))
            effects.append("concurrency.channel")
        elif line.startswith("return") and (len(line) == 6 or line[6].isspace()):
            ops.append(("RETURN", line[6:].strip() or "void"))
        elif ":=" in line or re.search(r"[^=!<>]=(?!=)", line):
            lhs = re.split(r":=|=", line, maxsplit=1)[0].strip()
            ops.append(("ASSIGN", lhs))

        for call_match in re.finditer(r"\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s*\(", line):
            callee = call_match.group(1)
            if callee in {
                "if", "for", "switch", "func", "make", "len", "cap", "append", "new",
                "int", "int8", "int16", "int32", "int64", "uint", "uint8", "uint16",
                "uint32", "uint64", "uintptr", "float32", "float64", "string", "bool",
                "byte", "rune", "complex", "real", "imag", "min", "max",
            }:
                continue
            ops.append(("CALL", callee))
            if callee.startswith(("fmt.Print", "log.")):
                effects.append("io.stdout")
            elif callee.startswith(("os.", "io.", "bufio.", "filepath.")):
                effects.append("io.filesystem")
            elif callee.startswith(("http.", "net.")):
                effects.append("io.network")
            elif callee.startswith(("math.", "strings.", "strconv.", "errors.", "fmt.Sprintf", "fmt.Errorf")):
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


def extract_go_ast(source: str) -> GoAstExtractionResult | None:
    """Extract structural definitions from Go source code.

    Returns None if parsing fails or if source is invalid.
    """
    if not GO_AST_EXTRACTOR_ENABLED:
        return None

    if not source or not source.strip():
        return None

    try:
        result = GoAstExtractionResult()

        # Package declaration
        pkg_match = re.search(r"^\s*package\s+([A-Za-z0-9_]+)", source, re.MULTILINE)
        if pkg_match:
            result.package = pkg_match.group(1)

        # Single import: import "fmt" or import f "fmt"
        single_imports = re.finditer(
            r'^\s*import\s+(?:[A-Za-z0-9_.]+\s+)?["`]([^"`]+)["`]', source, re.MULTILINE
        )
        for match in single_imports:
            result.imports.append(match.group(1))

        # Import block: import ( "fmt" \n "os" )
        import_blocks = re.finditer(r"import\s*\(([^)]+)\)", source, re.DOTALL)
        for block in import_blocks:
            for line in block.group(1).splitlines():
                imp_match = re.search(r'["`]([^"`]+)["`]', line)
                if imp_match:
                    result.imports.append(imp_match.group(1))

        # Struct & Interface definitions
        type_matches = re.finditer(
            r"^\s*type\s+([A-Za-z0-9_]+)\s+(struct|interface)\b", source, re.MULTILINE
        )
        for match in type_matches:
            name = match.group(1)
            kind = match.group(2)
            line_no = source[: match.start()].count("\n") + 1
            result.structs.append(
                GoStructInfo(
                    name=name,
                    line=line_no,
                    is_interface=(kind == "interface"),
                )
            )

        # Functions & Methods
        fn_matches = re.finditer(
            r"^\s*func\s*(?:\(([^)]+)\)\s*)?([A-Za-z0-9_]+)\s*(\([^)]*\)(?:\s*[^{;\n]+)?)",
            source,
            re.MULTILINE,
        )
        for match in fn_matches:
            receiver = match.group(1).strip() if match.group(1) else None
            fn_name = match.group(2)
            sig_rest = match.group(3).strip()
            line_no = source[: match.start()].count("\n") + 1
            full_sig = (
                f"func ({receiver}) {fn_name}{sig_rest}"
                if receiver
                else f"func {fn_name}{sig_rest}"
            )
            arg_types, return_type = _parse_go_signature(sig_rest)
            body = _extract_brace_body(source, match.end())
            side_effects, purity, ops = _analyse_go_body(body)

            result.functions.append(
                GoFunctionInfo(
                    name=fn_name,
                    line=line_no,
                    receiver=receiver,
                    signature=full_sig,
                    arg_types=arg_types,
                    return_type=return_type,
                    side_effects=side_effects,
                    purity=purity,
                    ops=ops,
                )
            )

        return result
    except Exception as exc:
        LOGGER.warning("extract_go_ast failed: %s", exc)
        return None
