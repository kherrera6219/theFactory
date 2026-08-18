"""go_ast_extractor.py — Regex structural extraction for Go / Systems languages.

Not a language AST. Filename is historical. Recovers package, import, struct,
interface, and method shapes with regular expressions. Real AST recovery is
Python / Java / (typed Haskell signatures where they parse).
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

        # Imports
        # Single import: import "fmt" or import f "fmt"
        single_imports = re.finditer(r'^\s*import\s+(?:[A-Za-z0-9_.]+\s+)?["`]([^"`]+)["`]', source, re.MULTILINE)
        for match in single_imports:
            result.imports.append(match.group(1))

        # Import block: import ( "fmt" \n "os" )
        import_blocks = re.finditer(r'import\s*\(([^)]+)\)', source, re.DOTALL)
        for block in import_blocks:
            for line in block.group(1).splitlines():
                imp_match = re.search(r'["`]([^"`]+)["`]', line)
                if imp_match:
                    result.imports.append(imp_match.group(1))

        # Struct & Interface definitions
        type_matches = re.finditer(
            r'^\s*type\s+([A-Za-z0-9_]+)\s+(struct|interface)\b', source, re.MULTILINE
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
            r'^\s*func\s*(?:\(([^)]+)\)\s*)?([A-Za-z0-9_]+)\s*(\([^)]*\)(?:\s*[^{]+)?)',
            source,
            re.MULTILINE,
        )
        for match in fn_matches:
            receiver = match.group(1).strip() if match.group(1) else None
            fn_name = match.group(2)
            sig_rest = match.group(3).strip()
            line_no = source[: match.start()].count("\n") + 1
            full_sig = f"func ({receiver}) {fn_name}{sig_rest}" if receiver else f"func {fn_name}{sig_rest}"

            result.functions.append(
                GoFunctionInfo(
                    name=fn_name,
                    line=line_no,
                    receiver=receiver,
                    signature=full_sig,
                )
            )

        return result
    except Exception as exc:
        LOGGER.warning("extract_go_ast failed: %s", exc)
        return None
