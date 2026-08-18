"""ocaml_ast_extractor.py — Regex structural extraction for OCaml.

Not a language AST. Filename is historical. Recovers modules, open, types,
let bindings, and exceptions with regular expressions.
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

        # Module declaration: module Main = struct ... end or module type SIG = sig ... end
        mod_match = re.search(r"^\s*module\s+(?:type\s+)?([A-Z][A-Za-z0-9_']*)", source, re.MULTILINE)
        if mod_match:
            result.module_name = mod_match.group(1)

        # Imports: open List or open Base.Map
        import_matches = re.finditer(
            r"^\s*open\s+([A-Z][A-Za-z0-9_'.]*)", source, re.MULTILINE
        )
        for match in import_matches:
            result.imports.append(match.group(1))

        # Exceptions: exception Invalid_argument of string
        exc_matches = re.finditer(
            r"^\s*exception\s+([A-Z][A-Za-z0-9_']*)", source, re.MULTILINE
        )
        for match in exc_matches:
            result.exceptions.append(match.group(1))

        # Type definitions: type 'a t = ... or type point = { x : float; y : float }
        type_matches = re.finditer(
            r"^\s*type\s+(?:'a\s+|'b\s+)?([a-z_][A-Za-z0-9_']*)\s*=\s*([^;\n]+)", source, re.MULTILINE
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

        # Let bindings: let rec foo x y = ... or let bar = ...
        let_matches = re.finditer(
            r"^\s*let\s+(rec\s+)?([a-z_][A-Za-z0-9_']*)\s*([^=\n]*)=", source, re.MULTILINE
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

            result.functions.append(
                OcamlFunctionInfo(
                    name=fn_name,
                    line=line_no,
                    is_recursive=is_rec,
                    signature=full_sig,
                )
            )

        return result
    except Exception as exc:
        LOGGER.warning("extract_ocaml_ast failed: %s", exc)
        return None
