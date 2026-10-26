"""ocaml_ast_extractor.py — Structural and signature extraction for OCaml.

Recovers modules, open, types, let bindings, explicit parameter/return type
annotations, purity/side effects, and expression opcodes.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

LOGGER = logging.getLogger(__name__)

OCAML_AST_EXTRACTOR_ENABLED: bool = (
    os.getenv("OCAML_AST_EXTRACTOR_ENABLED", "true").strip().lower()
    in {"1", "true", "yes", "on"}
)


@dataclass(frozen=True, slots=True)
class OcamlFunctionInfo:
    name: str
    line: int
    is_recursive: bool
    signature: str
    arg_types: tuple[str, ...] = ()
    return_type: str | None = None
    side_effects: tuple[str, ...] = ()
    purity: str = "UNKNOWN"
    ops: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class OcamlTypeInfo:
    name: str
    line: int
    kind: str  # "variant" | "record" | "alias" | "abstract"


@dataclass
class OcamlAstExtractionResult:
    """Full structural extraction result for one OCaml source file."""

    module_name: str | None = None
    functions: list[OcamlFunctionInfo] = field(default_factory=list)
    types: list[OcamlTypeInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)


def _parse_ocaml_params(params: str) -> tuple[tuple[str, ...], str | None]:
    """Extract explicit OCaml type annotations from ``(x : int) (y : float) : string``."""
    arg_types = tuple(
        m.group(1).strip()
        for m in re.finditer(r"\(\s*[A-Za-z0-9_']+\s*:\s*([^)]+)\)", params)
        if m.group(1).strip()
    )
    cleaned = re.sub(r"\([^)]*\)", "", params).strip()
    return_type: str | None = None
    if ":" in cleaned:
        ret_candidate = cleaned.rsplit(":", 1)[1].strip()
        if ret_candidate:
            return_type = ret_candidate
    return arg_types, return_type


def _analyse_ocaml_body(body_snippet: str) -> tuple[tuple[str, ...], str, tuple[tuple[str, str], ...]]:
    effects: list[str] = []
    ops: list[tuple[str, str]] = []
    if re.search(r"\b(Printf\.printf|print_endline|print_string|print_int)\b", body_snippet):
        effects.append("io.stdout")
    if re.search(r"\b(In_channel|Out_channel|open_in|open_out)\b", body_snippet):
        effects.append("io.filesystem")
    if ":=" in body_snippet or "<-" in body_snippet:
        effects.append("state.mutation")

    if re.search(r"\b(if\b|match\b|function\b)", body_snippet):
        ops.append(("BRANCH", "match_or_if"))
    if re.search(r"\b(List\.map|List\.fold_left|List\.filter|List\.iter)\b", body_snippet):
        ops.append(("CALL", "List.op"))
    ops.append(("RETURN", "expr"))

    dedup_effects = tuple(dict.fromkeys(effects))
    purity = "IMPURE" if dedup_effects else "PURE"
    return dedup_effects, purity, tuple(ops)


def extract_ocaml_ast(source: str) -> OcamlAstExtractionResult | None:
    """Extract structural definitions from OCaml source code.

    Returns None if parsing fails or if source is invalid.
    """
    if not OCAML_AST_EXTRACTOR_ENABLED:
        return None

    if not source or not source.strip():
        return None

    try:
        result = OcamlAstExtractionResult()

        mod_match = re.search(
            r"^\s*module\s+(?:type\s+)?([A-Z][A-Za-z0-9_']*)", source, re.MULTILINE
        )
        if mod_match:
            result.module_name = mod_match.group(1)

        import_matches = re.finditer(
            r"^\s*open\s+([A-Z][A-Za-z0-9_'.]*)", source, re.MULTILINE
        )
        for match in import_matches:
            result.imports.append(match.group(1))

        exc_matches = re.finditer(
            r"^\s*exception\s+([A-Z][A-Za-z0-9_']*)", source, re.MULTILINE
        )
        for match in exc_matches:
            result.exceptions.append(match.group(1))

        type_matches = re.finditer(
            r"^\s*type\s+(?:'a\s+|'b\s+)?([a-z_][A-Za-z0-9_']*)\s*=\s*([^;\n]+)",
            source,
            re.MULTILINE,
        )
        for match in type_matches:
            name = match.group(1)
            body = match.group(2).strip()
            line_no = source[: match.start()].count("\n") + 1
            kind = "record" if "{" in body else ("variant" if "|" in body else "alias")
            result.types.append(
                OcamlTypeInfo(
                    name=name,
                    line=line_no,
                    kind=kind,
                )
            )

        let_matches = re.finditer(
            r"^\s*let\s+(rec\s+)?([a-z_][A-Za-z0-9_']*)\s*([^=\n]*)=",
            source,
            re.MULTILINE,
        )
        seen_fns: set[str] = set()
        for match in let_matches:
            is_rec = bool(match.group(1))
            fn_name = match.group(2)
            if fn_name in seen_fns or fn_name in {"in", "and"}:
                continue
            seen_fns.add(fn_name)
            line_no = source[: match.start()].count("\n") + 1
            params = match.group(3).strip()
            full_sig = f"let {'rec ' if is_rec else ''}{fn_name} {params}".strip()
            arg_types, return_type = _parse_ocaml_params(params)
            body_snippet = source[match.end() : match.end() + 400]
            side_effects, purity, ops = _analyse_ocaml_body(body_snippet)

            result.functions.append(
                OcamlFunctionInfo(
                    name=fn_name,
                    line=line_no,
                    is_recursive=is_rec,
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
        LOGGER.warning("extract_ocaml_ast failed: %s", exc)
        return None
