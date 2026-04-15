"""js_ast_extractor.py — JavaScript/TypeScript AST-based extraction stub.

Architecture notes
------------------
This module mirrors the design of ``ast_extractor.py`` for Python:
  - ``extract_js_ast(source)`` returns a ``JsAstExtractionResult``
  - ``JsAstExtractor`` (in ``language_extractor.py``) should inherit from
    ``JavaScriptExtractor``, call ``super().extract()`` first (regex runs
    for concept/LogicNode detection), then replace structural fields with
    AST-derived equivalents.

Current status: **STUB** — no JavaScript AST parser is bundled with the
pod-worker image.  The function returns ``success=False`` so callers fall
back to regex silently.

To activate real AST parsing:
  1. Add ``esprima==4.*`` (or ``pyjsparser``) to ``services/pod-worker/requirements.txt``.
  2. Replace the stub body below with an ``esprima``-based implementation.
  3. Add ``JS_AST_EXTRACTOR_ENABLED`` to ``.env.example`` and wire it in
     ``pod_worker/main.py`` alongside ``PYTHON_AST_EXTRACTOR_ENABLED``.

Known regex extractor limitations this would fix
-------------------------------------------------
- Class shorthand methods (no ``function`` keyword) are invisible to regex.
- Arrow function names assigned to class fields are not detected.
- TypeScript-specific syntax (``interface``, ``type``, generics) is unparsed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

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

    Returns a result with ``success=False`` until a JS parser dependency is
    available.  Callers should check ``result.success`` before using the
    structural fields — on ``False`` they should fall back to the regex extractor.
    """
    try:
        import esprima  # noqa: F401  # type: ignore[import]
    except ImportError:
        return JsAstExtractionResult(
            success=False,
            error="esprima not installed — add esprima to pod-worker requirements.txt",
        )

    # --- Real implementation goes here once esprima is available ---
    # try:
    #     tree = esprima.parseScript(source, loc=True)
    #     functions = _walk_functions(tree)
    #     classes = _walk_classes(tree)
    #     imports = _walk_imports(tree)
    #     return JsAstExtractionResult(functions=functions, classes=classes,
    #                                  imports=imports, success=True)
    # except Exception as exc:
    #     LOGGER.debug("JS AST parse failed: %s", exc)
    #     return JsAstExtractionResult(success=False, error=str(exc))

    return JsAstExtractionResult(success=False, error="stub — not yet implemented")
