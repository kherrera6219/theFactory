"""julia_ast_extractor.py — Structural and signature extraction for Julia.

Recovers module headers, using/import, struct, and function bindings with
explicit ``::Type`` parameter/return annotations, purity, side effects, and opcodes.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

LOGGER = logging.getLogger(__name__)

JULIA_AST_EXTRACTOR_ENABLED: bool = (
    os.getenv("JULIA_AST_EXTRACTOR_ENABLED", "true").strip().lower()
    in {"1", "true", "yes", "on"}
)


@dataclass(frozen=True, slots=True)
class JuliaFunctionInfo:
    name: str
    line: int
    signature: str
    arg_types: tuple[str, ...] = ()
    return_type: str | None = None
    side_effects: tuple[str, ...] = ()
    purity: str = "UNKNOWN"
    ops: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class JuliaStructInfo:
    name: str
    line: int
    is_mutable: bool


@dataclass
class JuliaAstExtractionResult:
    """Full structural extraction result for one Julia source file."""

    module_name: str | None = None
    functions: list[JuliaFunctionInfo] = field(default_factory=list)
    structs: list[JuliaStructInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


def _parse_julia_signature(sig: str) -> tuple[tuple[str, ...], str | None]:
    """Extract ``::Type`` parameter and return annotations from a Julia signature."""
    if "(" not in sig or ")" not in sig:
        return (), None
    open_p = sig.find("(")
    close_p = sig.rfind(")")
    params_raw = sig[open_p + 1 : close_p]
    after = sig[close_p + 1 :].strip()

    arg_types: list[str] = []
    for raw_param in params_raw.split(","):
        param = raw_param.strip()
        if "::" in param:
            type_part = param.split("::", 1)[1].split("=", 1)[0].strip()
            if type_part:
                arg_types.append(type_part)

    return_type: str | None = None
    if after.startswith("::"):
        ret_part = after[2:].split("where", 1)[0].strip()
        if ret_part:
            return_type = ret_part

    return tuple(arg_types), return_type


def _analyse_julia_body(
    fn_name: str,
    body_snippet: str,
) -> tuple[tuple[str, ...], str, tuple[tuple[str, str], ...]]:
    effects: list[str] = []
    ops: list[tuple[str, str]] = []
    if fn_name.endswith("!"):
        effects.append("state.mutation")
    if re.search(r"\b(println|print|@info|@warn|@error)\b", body_snippet):
        effects.append("io.stdout")
    if re.search(r"\b(open|read|write|readline)\b", body_snippet):
        effects.append("io.filesystem")

    if re.search(r"\b(if\b|elseif\b)", body_snippet):
        ops.append(("BRANCH", "if"))
    if re.search(r"\b(for\b|while\b)", body_snippet):
        ops.append(("LOOP", "loop"))
    ops.append(("RETURN", "value"))

    dedup_effects = tuple(dict.fromkeys(effects))
    purity = "IMPURE" if dedup_effects else "PURE"
    return dedup_effects, purity, tuple(ops)


def extract_julia_ast(source: str) -> JuliaAstExtractionResult | None:
    """Extract structural definitions from Julia source code.

    Returns None if parsing fails or if source is invalid.
    """
    if not JULIA_AST_EXTRACTOR_ENABLED:
        return None

    if not source or not source.strip():
        return None

    try:
        result = JuliaAstExtractionResult()

        mod_match = re.search(r"^\s*module\s+([A-Z][A-Za-z0-9_']*)", source, re.MULTILINE)
        if mod_match:
            result.module_name = mod_match.group(1)

        import_matches = re.finditer(
            r"^\s*(?:using|import)\s+([A-Za-z0-9_.', ]+)", source, re.MULTILINE
        )
        for match in import_matches:
            pkgs = [p.strip() for p in match.group(1).split(",") if p.strip()]
            result.imports.extend(pkgs)

        struct_matches = re.finditer(
            r"^\s*(mutable\s+)?struct\s+([A-Z][A-Za-z0-9_']*)", source, re.MULTILINE
        )
        for match in struct_matches:
            is_mut = bool(match.group(1))
            name = match.group(2)
            line_no = source[: match.start()].count("\n") + 1
            result.structs.append(
                JuliaStructInfo(
                    name=name,
                    line=line_no,
                    is_mutable=is_mut,
                )
            )

        fn_matches = re.finditer(
            r"^\s*function\s+([a-z_][A-Za-z0-9_!']*\([^)\n]*\)(?:\s*::\s*[A-Za-z0-9_{},.]+)?)",
            source,
            re.MULTILINE,
        )
        seen_fns: set[str] = set()
        for match in fn_matches:
            sig = match.group(1).strip()
            fn_name = sig.split("(")[0].strip()
            if fn_name in seen_fns:
                continue
            seen_fns.add(fn_name)
            line_no = source[: match.start()].count("\n") + 1
            arg_types, return_type = _parse_julia_signature(sig)
            end_pos = source.find("\nend", match.end())
            body_snippet = source[match.end() : end_pos if end_pos > 0 else match.end() + 400]
            side_effects, purity, ops = _analyse_julia_body(fn_name, body_snippet)
            result.functions.append(
                JuliaFunctionInfo(
                    name=fn_name,
                    line=line_no,
                    signature=sig,
                    arg_types=arg_types,
                    return_type=return_type,
                    side_effects=side_effects,
                    purity=purity,
                    ops=ops,
                )
            )

        oneline_matches = re.finditer(
            r"^\s*([a-z_][A-Za-z0-9_!']*\([^)\n]*\)(?:\s*::\s*[A-Za-z0-9_{},.]+)?)\s*=\s*([^\n]+)",
            source,
            re.MULTILINE,
        )
        for match in oneline_matches:
            sig = match.group(1).strip()
            fn_name = sig.split("(")[0].strip()
            if fn_name in seen_fns or fn_name in {"if", "while", "for"}:
                continue
            seen_fns.add(fn_name)
            line_no = source[: match.start()].count("\n") + 1
            arg_types, return_type = _parse_julia_signature(sig)
            side_effects, purity, ops = _analyse_julia_body(fn_name, match.group(2))
            result.functions.append(
                JuliaFunctionInfo(
                    name=fn_name,
                    line=line_no,
                    signature=sig,
                    arg_types=arg_types,
                    return_type=return_type,
                    side_effects=side_effects,
                    purity=purity,
                    ops=ops,
                )
            )

        return result
    except Exception as exc:
        LOGGER.warning("extract_julia_ast failed: %s", exc)
        return None
