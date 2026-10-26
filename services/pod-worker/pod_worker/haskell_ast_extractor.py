"""haskell_ast_extractor.py — Structural and signature extraction for Haskell.

Recovers module headers, imports, data/type definitions, ``::`` signatures,
purity/IO monad effects, and expression opcodes.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

LOGGER = logging.getLogger(__name__)

HASKELL_AST_EXTRACTOR_ENABLED: bool = (
    os.getenv("HASKELL_AST_EXTRACTOR_ENABLED", "true").strip().lower()
    in {"1", "true", "yes", "on"}
)


@dataclass(frozen=True, slots=True)
class HaskellFunctionInfo:
    name: str
    line: int
    type_signature: str | None
    signature: str
    side_effects: tuple[str, ...] = ()
    purity: str = "UNKNOWN"
    ops: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class HaskellDataInfo:
    name: str
    line: int
    kind: str  # "data" | "newtype" | "type"
    constructors: tuple[str, ...] = ()


@dataclass
class HaskellAstExtractionResult:
    """Full structural extraction result for one Haskell/Functional source file."""

    module_name: str | None = None
    functions: list[HaskellFunctionInfo] = field(default_factory=list)
    types: list[HaskellDataInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


def _analyse_haskell_binding(
    type_sig: str | None,
    rhs: str,
) -> tuple[tuple[str, ...], str, tuple[tuple[str, str], ...]]:
    effects: list[str] = []
    ops: list[tuple[str, str]] = []
    sig_str = (type_sig or "").strip()
    if re.search(r"\bIO\b", sig_str):
        effects.append("io.monad")
    if re.search(r"\b(putStrLn|putStr|print)\b", rhs):
        effects.append("io.stdout")
    if re.search(r"\b(readFile|writeFile|appendFile)\b", rhs):
        effects.append("io.filesystem")

    if re.search(r"\b(if\b|case\b)", rhs):
        ops.append(("BRANCH", "conditional"))
    if re.search(r"\b(map|foldr|foldl|filter)\b", rhs):
        ops.append(("CALL", "higher_order"))
    if re.search(r"\bdo\b", rhs):
        ops.append(("CALL", "do_block"))
    ops.append(("RETURN", rhs.splitlines()[0].strip()[:40] or "expr"))

    dedup_effects = tuple(dict.fromkeys(effects))
    purity = "IMPURE" if dedup_effects else "PURE"
    return dedup_effects, purity, tuple(ops)


def extract_haskell_ast(source: str) -> HaskellAstExtractionResult | None:
    """Extract structural definitions from Haskell/Functional source code.

    Returns None if parsing fails or if source is invalid.
    """
    if not HASKELL_AST_EXTRACTOR_ENABLED:
        return None

    if not source or not source.strip():
        return None

    try:
        result = HaskellAstExtractionResult()

        mod_match = re.search(r"^\s*module\s+([A-Za-z0-9_.]+)", source, re.MULTILINE)
        if mod_match:
            result.module_name = mod_match.group(1)

        import_matches = re.finditer(
            r"^\s*import\s+(?:qualified\s+)?([A-Za-z0-9_.]+)", source, re.MULTILINE
        )
        for match in import_matches:
            result.imports.append(match.group(1))

        type_matches = re.finditer(
            r"^\s*(data|newtype|type)\s+([A-Za-z0-9_]+)", source, re.MULTILINE
        )
        for match in type_matches:
            kind = match.group(1)
            name = match.group(2)
            line_no = source[: match.start()].count("\n") + 1
            result.types.append(
                HaskellDataInfo(
                    name=name,
                    line=line_no,
                    kind=kind,
                )
            )

        sig_map: dict[str, tuple[int, str]] = {}
        sig_matches = re.finditer(
            r"^\s*([a-z_][A-Za-z0-9_']*)\s*::\s*(.+)$", source, re.MULTILINE
        )
        for match in sig_matches:
            fn_name = match.group(1)
            type_sig = match.group(2).strip()
            line_no = source[: match.start()].count("\n") + 1
            sig_map[fn_name] = (line_no, type_sig)

        binding_matches = re.finditer(
            r"^\s*([a-z_][A-Za-z0-9_']*)\s+([^=\n]*)=\s*([^\n]*)", source, re.MULTILINE
        )
        seen_fns: set[str] = set()
        for match in binding_matches:
            fn_name = match.group(1)
            if fn_name in seen_fns or fn_name in {"where", "let", "in", "case", "if"}:
                continue
            seen_fns.add(fn_name)
            line_no = source[: match.start()].count("\n") + 1
            sig_tuple = sig_map.get(fn_name)
            type_sig = sig_tuple[1] if sig_tuple else None
            full_sig = f"{fn_name} :: {type_sig}" if type_sig else fn_name
            rhs = match.group(3).strip()
            side_effects, purity, ops = _analyse_haskell_binding(type_sig, rhs)

            result.functions.append(
                HaskellFunctionInfo(
                    name=fn_name,
                    line=line_no,
                    type_signature=type_sig,
                    signature=full_sig,
                    side_effects=side_effects,
                    purity=purity,
                    ops=ops,
                )
            )

        return result
    except Exception as exc:
        LOGGER.warning("extract_haskell_ast failed: %s", exc)
        return None
