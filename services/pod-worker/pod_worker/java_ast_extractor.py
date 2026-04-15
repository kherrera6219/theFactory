"""java_ast_extractor.py — Java AST-based extraction stub.

Architecture notes
------------------
Mirrors the design of ``ast_extractor.py`` for Python:
  - ``extract_java_ast(source)`` returns a ``JavaAstExtractionResult``
  - ``JavaAstExtractor`` (in ``language_extractor.py``) should inherit from
    ``JavaExtractor``, call ``super().extract()`` first (regex runs for
    concept/LogicNode detection), then replace structural fields with
    AST-derived equivalents.

Current status: **STUB** — no Java AST parser is bundled with the pod-worker
image.  Returns ``success=False`` so callers fall back to regex silently.

To activate real AST parsing:
  1. Add ``javalang==0.13.*`` to ``services/pod-worker/requirements.txt``.
  2. Replace the stub body below with a ``javalang``-based implementation.
  3. Add ``JAVA_AST_EXTRACTOR_ENABLED`` to ``.env.example`` and wire it in
     ``pod_worker/main.py`` alongside ``PYTHON_AST_EXTRACTOR_ENABLED``.

Known regex extractor limitations this would fix
-------------------------------------------------
- Inner/anonymous classes are not detected by class-name regex.
- Method overloads produce duplicate names (same name, different signature).
- Interface method declarations look identical to class method declarations.
- Annotations (``@Override``, ``@Bean``) are not captured.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class JavaMethodInfo:
    name: str
    line: int
    return_type: str
    parameters: tuple[str, ...]
    modifiers: tuple[str, ...]
    annotations: tuple[str, ...]
    signature: str


@dataclass(frozen=True, slots=True)
class JavaClassInfo:
    name: str
    line: int
    kind: str  # "class" | "interface" | "enum" | "annotation"
    extends: str | None
    implements: tuple[str, ...]
    annotations: tuple[str, ...]
    methods: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class JavaImportInfo:
    qualified_name: str
    is_static: bool
    is_wildcard: bool
    line: int


@dataclass
class JavaAstExtractionResult:
    """AST-derived extraction result for one Java file."""

    methods: list[JavaMethodInfo] = field(default_factory=list)
    classes: list[JavaClassInfo] = field(default_factory=list)
    imports: list[JavaImportInfo] = field(default_factory=list)
    package: str | None = None
    success: bool = False
    error: str | None = None


def extract_java_ast(source: str) -> JavaAstExtractionResult:
    """Parse *source* with a Java AST parser and return structured data.

    Returns a result with ``success=False`` until a Java parser dependency is
    available.  Callers should check ``result.success`` before using the
    structural fields — on ``False`` they should fall back to the regex extractor.
    """
    try:
        import javalang  # noqa: F401  # type: ignore[import]
    except ImportError:
        return JavaAstExtractionResult(
            success=False,
            error="javalang not installed — add javalang to pod-worker requirements.txt",
        )

    # --- Real implementation goes here once javalang is available ---
    # try:
    #     tree = javalang.parse.parse(source)
    #     package = tree.package.name if tree.package else None
    #     imports = _walk_imports(tree)
    #     classes = _walk_types(tree)
    #     methods = _walk_methods(tree)
    #     return JavaAstExtractionResult(methods=methods, classes=classes,
    #                                    imports=imports, package=package, success=True)
    # except javalang.parser.JavaSyntaxError as exc:
    #     LOGGER.debug("Java AST parse failed: %s", exc)
    #     return JavaAstExtractionResult(success=False, error=str(exc))

    return JavaAstExtractionResult(success=False, error="stub — not yet implemented")
