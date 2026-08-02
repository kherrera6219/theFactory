"""Language extraction engine — detects computational concepts in source code.

Each ``LanguageExtractor`` scans source text using the concept catalog patterns
and produces a list of ``ExtractedConcept`` entries compatible with the
LogicNode schema.

This is a **regex-first static analysis** pass. Python can switch to an
AST-backed structural extractor when enabled, while the default shipped path
still avoids LLM calls and keeps the other languages on the regex pipeline.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, replace
from typing import Final

from .concept_catalog import ConceptPattern, get_patterns

LOGGER = logging.getLogger(__name__)

# Maximum source content length we'll scan (guard against huge files).
_MAX_SOURCE_LENGTH: Final[int] = 512_000  # ~500 KB


@dataclass(frozen=True, slots=True)
class FunctionInfo:
    """Detected function/method definition.

    ``arg_types``/``return_type`` are populated only by AST-backed extractors
    that genuinely recover them (UPG-31). Before UPG-31 every AST extractor's
    structured type data was flattened away here, keeping only the raw
    ``signature`` string. Regex extractors leave both empty, and that emptiness
    is now meaningful rather than universal.

    Both default to empty/``None`` so every existing construction site keeps
    working unchanged — this widening is additive.
    """

    name: str
    line: int
    signature: str
    arg_types: tuple[str, ...] = ()
    return_type: str | None = None


@dataclass(frozen=True, slots=True)
class ClassInfo:
    """Detected class definition."""

    name: str
    line: int
    parents: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExtractedConcept:
    """A single concept matched in source code."""

    concept_id: str
    domain: str
    concept: str
    intent: str
    source_language: str
    source_line: int
    confidence: float
    evidence: str
    # Provenance fields — populated by the extractor, forwarded to LogicNode payload.
    extraction_method: str = "regex"  # "regex" | "ast"
    source_range: tuple[int, int] | None = None  # (start_line, end_line); None = single-line


def _split_haskell_type_signature(
    type_signature: str | None,
) -> tuple[tuple[str, ...], str | None]:
    """Split a Haskell type signature into argument types and a return type.

    ``Int -> String -> Bool`` yields ``(("Int", "String"), "Bool")``.

    Splitting is **depth-aware**: arrows nested inside parentheses or brackets
    belong to a higher-order argument, not to the top-level application, so
    ``(Int -> Bool) -> [Int] -> Int`` correctly yields
    ``(("(Int -> Bool)", "[Int]"), "Int")`` rather than four fragments.

    A leading context (``Ord a => a -> a``) is dropped — it constrains types
    rather than being one. Anything unparseable yields ``((), None)``: this is
    deliberately conservative, because an empty result is honest while a wrong
    one silently corrupts the node's declared types (UPG-31).
    """
    if not type_signature:
        return (), None
    text = str(type_signature).strip()
    if not text:
        return (), None

    # Drop a "name ::" prefix if the extractor kept one.
    if "::" in text:
        text = text.split("::", 1)[1].strip()

    parts: list[str] = []
    depth = 0
    current: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
            # Unbalanced brackets mean we cannot trust the parse.
            if depth < 0:
                return (), None
        # A top-level "=>" ends the typeclass context; everything before it is
        # a constraint, not an argument type.
        if depth == 0 and text.startswith("=>", index):
            current = []
            parts = []
            index += 2
            continue
        if depth == 0 and text.startswith("->", index):
            parts.append("".join(current).strip())
            current = []
            index += 2
            continue
        current.append(char)
        index += 1

    if depth != 0:
        return (), None
    parts.append("".join(current).strip())
    parts = [part for part in parts if part]
    if len(parts) < 2:
        # A nullary value (``x :: Int``) has a return type and no arguments.
        return ((), parts[0]) if parts else ((), None)
    return tuple(parts[:-1]), parts[-1]


@dataclass
class ExtractionResult:
    """Aggregated extraction output for one source file."""

    language: str
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    concepts: list[ExtractedConcept] = field(default_factory=list)
    lines_scanned: int = 0
    error: str | None = None

    @property
    def summary(self) -> dict:
        return {
            "language": self.language,
            "functions_found": len(self.functions),
            "classes_found": len(self.classes),
            "imports_found": len(self.imports),
            "concepts_found": len(self.concepts),
            "lines_scanned": self.lines_scanned,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Base extractor
# ---------------------------------------------------------------------------


class LanguageExtractor:
    """Base language extractor using regex-based pattern detection."""

    language: str = "generic"

    # Subclasses override these patterns.
    _function_pattern: re.Pattern[str] | None = None
    _class_pattern: re.Pattern[str] | None = None
    _import_pattern: re.Pattern[str] | None = None

    def extract(
        self,
        source: str,
        focus_domains: list[str] | None = None,
        doc_context: str | None = None,
    ) -> ExtractionResult:
        """Run full extraction pipeline on *source* text."""
        result = ExtractionResult(language=self.language)

        if not source or not source.strip():
            result.error = "empty source"
            return result

        if len(source) > _MAX_SOURCE_LENGTH:
            source = source[:_MAX_SOURCE_LENGTH]
            LOGGER.warning(
                "source truncated to %d bytes for %s extraction",
                _MAX_SOURCE_LENGTH,
                self.language,
            )

        lines = source.splitlines()
        result.lines_scanned = len(lines)

        try:
            result.functions = self._detect_functions(source, lines)
            result.classes = self._detect_classes(source, lines)
            result.imports = self._detect_imports(source)
            result.concepts = self._apply_focus_domains(
                self._apply_doc_context(
                    self._detect_concepts(source, lines),
                    doc_context,
                ),
                focus_domains,
            )
        except Exception as exc:
            LOGGER.warning("extraction failed for %s: %s", self.language, exc)
            result.error = str(exc)

        return result

    # -- structural detection ------------------------------------------------

    def _detect_functions(self, _source: str, lines: list[str]) -> list[FunctionInfo]:
        if self._function_pattern is None:
            return []
        found: list[FunctionInfo] = []
        for idx, line in enumerate(lines, start=1):
            match = self._function_pattern.search(line)
            if match:
                # Patterns with alternating groups (e.g. JS) may have None in some groups;
                # take the first non-None captured group, falling back to the whole match.
                name = next(
                    (g for g in match.groups() if g is not None),
                    match.group(0),
                )
                found.append(FunctionInfo(name=name.strip(), line=idx, signature=line.strip()))
        return found

    def _detect_classes(self, _source: str, lines: list[str]) -> list[ClassInfo]:
        if self._class_pattern is None:
            return []
        found: list[ClassInfo] = []
        for idx, line in enumerate(lines, start=1):
            match = self._class_pattern.search(line)
            if match:
                name = (
                    match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0)
                )
                found.append(ClassInfo(name=name.strip(), line=idx))
        return found

    def _detect_imports(self, source: str) -> list[str]:
        if self._import_pattern is None:
            return []
        return [m.group(0).strip() for m in self._import_pattern.finditer(source)]

    # -- concept detection ---------------------------------------------------

    def _detect_concepts(self, _source: str, lines: list[str]) -> list[ExtractedConcept]:
        patterns = get_patterns(self.language)
        if not patterns:
            return []

        found: list[ExtractedConcept] = []
        seen_ids: set[str] = set()  # deduplicate by concept_id + line

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("//"):
                continue

            for pattern in patterns:
                key = f"{pattern.concept_id}:{idx}"
                if key in seen_ids:
                    continue
                try:
                    if re.search(pattern.regex, stripped, re.IGNORECASE):
                        evidence = stripped[:120]
                        found.append(
                            ExtractedConcept(
                                concept_id=pattern.concept_id,
                                domain=pattern.domain,
                                concept=pattern.concept,
                                intent=pattern.intent,
                                source_language=self.language,
                                source_line=idx,
                                confidence=_compute_confidence(pattern, stripped),
                                evidence=evidence,
                            )
                        )
                        seen_ids.add(key)
                except re.error:
                    continue

        return found

    def _apply_focus_domains(
        self,
        concepts: list[ExtractedConcept],
        focus_domains: list[str] | None,
    ) -> list[ExtractedConcept]:
        normalized_focus = {
            str(domain).strip().lower()
            for domain in focus_domains or []
            if str(domain).strip()
        }
        if not normalized_focus:
            return concepts
        boosted: list[ExtractedConcept] = []
        for concept in concepts:
            if concept.domain.strip().lower() in normalized_focus:
                boosted.append(
                    replace(
                        concept,
                        confidence=round(min(concept.confidence + 0.15, 1.0), 2),
                    )
                )
            else:
                boosted.append(concept)
        return boosted

    def _apply_doc_context(
        self,
        concepts: list[ExtractedConcept],
        doc_context: str | None,
    ) -> list[ExtractedConcept]:
        normalized_context = str(doc_context or "").strip().lower()
        if not normalized_context:
            return concepts
        boosted: list[ExtractedConcept] = []
        for concept in concepts:
            context_hit = (
                concept.domain.strip().lower() in normalized_context
                or concept.concept.strip().lower() in normalized_context
            )
            if context_hit:
                boosted.append(
                    replace(
                        concept,
                        confidence=round(min(concept.confidence + 0.05, 1.0), 2),
                    )
                )
            else:
                boosted.append(concept)
        return boosted


def _compute_confidence(pattern: ConceptPattern, line: str) -> float:
    """Heuristic confidence score for a pattern match.

    Longer matching evidence and more-specific patterns get higher scores.
    """
    base = 0.6
    # Reward longer patterns (more specific)
    if len(pattern.regex) > 30:
        base += 0.1
    # Reward longer evidence lines (more context)
    if len(line) > 40:
        base += 0.05
    # Penalize very short lines (might be noise)
    if len(line) < 10:
        base -= 0.15
    return round(min(max(base, 0.1), 1.0), 2)


# ---------------------------------------------------------------------------
# Pod A — Dynamic Language Extractors
# ---------------------------------------------------------------------------


class PythonExtractor(LanguageExtractor):
    language = "python"
    _function_pattern = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(", re.MULTILINE)
    _class_pattern = re.compile(r"^\s*class\s+(\w+)", re.MULTILINE)
    _import_pattern = re.compile(
        r"^\s*(?:import\s+[\w.]+|from\s+[\w.]+\s+import\s+[\w., ]+)", re.MULTILINE
    )


class PythonAstExtractor(PythonExtractor):
    """Python extractor that uses AST for accurate structural analysis.

    Augments (does not replace) the regex concept detection:
    - AST provides zero-false-positive function/class/import extraction with
      base classes, type annotations, async detection, and decorator info.
    - Regex concept patterns still run unchanged for downstream LogicNode production.
    - Falls back transparently to regex-only on syntax errors.

    Enable via ``PYTHON_AST_EXTRACTOR_ENABLED=true``.
    """

    def extract(
        self,
        source: str,
        focus_domains: list[str] | None = None,
        doc_context: str | None = None,
    ) -> ExtractionResult:
        # Run the full regex pipeline first — this produces the concepts that
        # feed LogicNodes and is always the source of truth for concept detection.
        result = super().extract(source, focus_domains=focus_domains, doc_context=doc_context)

        # Attempt AST-based structural enrichment.
        try:
            from .ast_extractor import extract_python_ast  # local import avoids circular dep
        except ImportError:
            LOGGER.warning("ast_extractor not available; using regex-only extraction")
            return result

        # super().extract() truncates to _MAX_SOURCE_LENGTH internally before
        # scanning, but this call used to receive the original, untruncated
        # `source` -- for files over the cap, AST-derived functions/classes
        # would report line numbers past the end of what the regex pass ever
        # saw (inconsistent with `result.concepts`), and the size guard
        # meant to bound ast.parse() cost was silently bypassed.
        truncated_source = source[:_MAX_SOURCE_LENGTH]
        ast_result = extract_python_ast(truncated_source)
        if not ast_result.success:
            LOGGER.debug(
                "Python AST parse failed (%s) — regex structural info retained",
                ast_result.parse_error,
            )
            return result

        # Replace structural fields with AST-derived versions (more accurate).
        # arg_types/return_annotation were previously discarded here; they are
        # the real signature data LogicNode types.in/types.out need (UPG-31).
        result.functions = [
            FunctionInfo(
                name=f.name,
                line=f.line,
                signature=f.signature,
                arg_types=tuple(f.arg_types or ()),
                return_type=f.return_annotation,
            )
            for f in ast_result.functions
        ]
        result.classes = [
            ClassInfo(
                name=c.name,
                line=c.line,
                parents=c.bases,
            )
            for c in ast_result.classes
        ]
        result.imports = [
            (
                f"from {i.module} import {', '.join(i.names)}"
                if i.is_from
                else f"import {', '.join(i.names)}"
            )
            for i in ast_result.imports
        ]

        LOGGER.debug(
            "AST enrichment applied: %d functions, %d classes, %d imports",
            len(result.functions),
            len(result.classes),
            len(result.imports),
        )
        return result

    def _apply_focus_domains(
        self,
        concepts: list[ExtractedConcept],
        focus_domains: list[str] | None,
    ) -> list[ExtractedConcept]:
        normalized_focus = {
            str(domain).strip().lower()
            for domain in focus_domains or []
            if str(domain).strip()
        }
        if not normalized_focus:
            return concepts
        boosted: list[ExtractedConcept] = []
        for concept in concepts:
            if concept.domain.strip().lower() in normalized_focus:
                boosted.append(
                    replace(
                        concept,
                        confidence=round(min(concept.confidence + 0.15, 1.0), 2),
                    )
                )
            else:
                boosted.append(concept)
        return boosted


class JavaScriptExtractor(LanguageExtractor):
    language = "javascript"
    _function_pattern = re.compile(
        # Paren-less single-arg arrow functions (`x => x + 1`) are a common
        # JS idiom -- without the `\w+\s*=>` alternative, only parenthesized
        # arg lists (`(x) => ...` / `() => ...`) and `function` expressions
        # were matched, silently dropping every bare-identifier arrow
        # function from the extracted function list.
        r"(?:function\s+(\w+)\s*\(|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?"
        r"(?:\([^)]*\)\s*=>|\w+\s*=>|function))",
        re.MULTILINE,
    )
    _class_pattern = re.compile(r"\bclass\s+(\w+)", re.MULTILINE)
    _import_pattern = re.compile(
        r"(?:import\s+.*\s+from\s+['\"][\w./@-]+['\"]|(?:const|let|var)\s+.*=\s*require\s*\()",
        re.MULTILINE,
    )


class JavaScriptAstExtractor(JavaScriptExtractor):
    """JavaScript/TypeScript extractor with AST-backed structural enrichment."""

    def extract(
        self,
        source: str,
        focus_domains: list[str] | None = None,
        doc_context: str | None = None,
    ) -> ExtractionResult:
        result = super().extract(source, focus_domains=focus_domains, doc_context=doc_context)
        try:
            from .js_ast_extractor import extract_js_ast
        except ImportError:
            LOGGER.warning("js_ast_extractor not available; using regex-only extraction")
            return result

        ast_result = extract_js_ast(source)
        if not ast_result.success:
            LOGGER.debug(
                "JS AST parse failed (%s) — regex structural info retained",
                ast_result.error,
            )
            return result

        result.functions = [
            FunctionInfo(name=item.name, line=item.line, signature=item.signature)
            for item in ast_result.functions
        ]
        result.classes = [
            ClassInfo(
                name=item.name,
                line=item.line,
                parents=() if item.extends is None else (item.extends,),
            )
            for item in ast_result.classes
        ]
        result.imports = [
            (
                f"import {', '.join(item.names)} from {item.module}"
                if item.names
                else f"import {item.module}"
            )
            for item in ast_result.imports
        ]
        return result


class RubyExtractor(LanguageExtractor):
    language = "ruby"
    _function_pattern = re.compile(r"^\s*def\s+(\w+)", re.MULTILINE)
    _class_pattern = re.compile(r"^\s*class\s+(\w+)", re.MULTILINE)
    _import_pattern = re.compile(r"^\s*require\s+['\"][\w/.-]+['\"]", re.MULTILINE)


class PhpExtractor(LanguageExtractor):
    language = "php"
    _function_pattern = re.compile(r"\bfunction\s+(\w+)\s*\(", re.MULTILINE)
    _class_pattern = re.compile(r"\bclass\s+(\w+)", re.MULTILINE)
    _import_pattern = re.compile(r"\b(?:use|require_once|include)\s+[\w\\/.]+", re.MULTILINE)


# ---------------------------------------------------------------------------
# Pod B — Systems Language Extractors
# ---------------------------------------------------------------------------


class CExtractor(LanguageExtractor):
    language = "c"
    _function_pattern = re.compile(
        r"^\s*(?:static\s+)?(?:void|int|char|float|double|long|unsigned|signed|size_t)\s+(\w+)\s*\(",
        re.MULTILINE,
    )
    _class_pattern = re.compile(r"\bstruct\s+(\w+)\s*\{", re.MULTILINE)
    _import_pattern = re.compile(r"#\s*include\s+[<\"][\w./]+[>\"]", re.MULTILINE)


class CppExtractor(LanguageExtractor):
    language = "cpp"
    _function_pattern = re.compile(
        r"^\s*(?:virtual\s+)?(?:static\s+)?(?:void|int|auto|bool|std::\w+|const\s+\w+&?)\s+(\w+)\s*\(",
        re.MULTILINE,
    )
    _class_pattern = re.compile(r"\bclass\s+(\w+)", re.MULTILINE)
    _import_pattern = re.compile(r"#\s*include\s+[<\"][\w./]+[>\"]", re.MULTILINE)


class RustExtractor(LanguageExtractor):
    language = "rust"
    _function_pattern = re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", re.MULTILINE)
    _class_pattern = re.compile(r"^\s*(?:pub\s+)?(?:struct|enum|trait)\s+(\w+)", re.MULTILINE)
    _import_pattern = re.compile(r"^\s*use\s+[\w:]+", re.MULTILINE)


class GoExtractor(LanguageExtractor):
    language = "go"
    # Matches plain functions and methods (with receiver).
    _function_pattern = re.compile(
        r"^\s*func\s+(?:\(\s*\w+\s+\*?\w+\s*\)\s+)?(\w+)\s*\(",
        re.MULTILINE,
    )
    # Matches named struct and interface type declarations.
    _class_pattern = re.compile(
        r"^\s*type\s+(\w+)\s+(?:struct|interface)\b",
        re.MULTILINE,
    )
    # Matches single-line and grouped import blocks.
    _import_pattern = re.compile(
        r'^\s*import\s+(?:"[\w./]+"|\()',
        re.MULTILINE,
    )


class ZigExtractor(LanguageExtractor):
    language = "zig"
    _function_pattern = re.compile(r"^\s*(?:pub\s+)?fn\s+(\w+)\s*\(", re.MULTILINE)
    # Matches `const Name = struct {` / `union {` / `enum {` patterns.
    _class_pattern = re.compile(
        r"(?:const|var)\s+(\w+)\s*=\s*(?:packed\s+)?(?:struct|union|enum)\s*\{",
        re.MULTILINE,
    )
    _import_pattern = re.compile(r'@import\s*\(\s*"[\w./]+"', re.MULTILINE)


# ---------------------------------------------------------------------------
# Pod C — Enterprise Language Extractors
# ---------------------------------------------------------------------------


class JavaExtractor(LanguageExtractor):
    language = "java"
    _function_pattern = re.compile(
        r"^\s*(?:public|private|protected)\s+(?:static\s+)?(?:final\s+)?(?:void|int|String|boolean|long|double|[\w<>]+)\s+(\w+)\s*\(",
        re.MULTILINE,
    )
    _class_pattern = re.compile(r"\b(?:class|interface)\s+(\w+)", re.MULTILINE)
    _import_pattern = re.compile(r"^\s*import\s+[\w.*]+;", re.MULTILINE)


class JavaAstExtractor(JavaExtractor):
    """Java extractor with AST-backed structural enrichment."""

    def extract(
        self,
        source: str,
        focus_domains: list[str] | None = None,
        doc_context: str | None = None,
    ) -> ExtractionResult:
        result = super().extract(source, focus_domains=focus_domains, doc_context=doc_context)
        try:
            from .java_ast_extractor import extract_java_ast
        except ImportError:
            LOGGER.warning("java_ast_extractor not available; using regex-only extraction")
            return result

        ast_result = extract_java_ast(source)
        if not ast_result.success:
            LOGGER.debug(
                "Java AST parse failed (%s) — regex structural info retained",
                ast_result.error,
            )
            return result

        # javalang recovers declared parameter and return types; keep them
        # rather than flattening to the raw signature string (UPG-31).
        result.functions = [
            FunctionInfo(
                name=item.name,
                line=item.line,
                signature=item.signature,
                arg_types=tuple(item.parameters or ()),
                return_type=item.return_type or None,
            )
            for item in ast_result.methods
        ]
        result.classes = [
            ClassInfo(
                name=item.name,
                line=item.line,
                parents=tuple(parent for parent in (item.extends, *item.implements) if parent),
            )
            for item in ast_result.classes
        ]
        # javalang's `path` attribute can be empty/None for a malformed or
        # partial parse; without this filter an empty qualified_name was
        # injected into the imports list as a bare "" entry.
        result.imports = [item.qualified_name for item in ast_result.imports if item.qualified_name]
        return result


class CSharpExtractor(LanguageExtractor):
    language = "csharp"
    _function_pattern = re.compile(
        r"^\s*(?:public|private|protected|internal)\s+(?:static\s+)?(?:async\s+)?(?:void|int|string|bool|Task|[\w<>]+)\s+(\w+)\s*\(",
        re.MULTILINE,
    )
    _class_pattern = re.compile(r"\bclass\s+(\w+)", re.MULTILINE)
    _import_pattern = re.compile(r"^\s*using\s+[\w.]+;", re.MULTILINE)


class ScalaExtractor(LanguageExtractor):
    language = "scala"
    _function_pattern = re.compile(r"^\s*def\s+(\w+)", re.MULTILINE)
    _class_pattern = re.compile(r"\b(?:class|object|trait|case\s+class)\s+(\w+)", re.MULTILINE)
    _import_pattern = re.compile(r"^\s*import\s+[\w._{}]+", re.MULTILINE)


class KotlinExtractor(LanguageExtractor):
    language = "kotlin"
    _function_pattern = re.compile(r"^\s*(?:suspend\s+)?fun\s+(\w+)", re.MULTILINE)
    _class_pattern = re.compile(r"\b(?:data\s+)?class\s+(\w+)", re.MULTILINE)
    _import_pattern = re.compile(r"^\s*import\s+[\w.]+", re.MULTILINE)


# ---------------------------------------------------------------------------
# Pod D — Mathematical & Functional Language Extractors
# ---------------------------------------------------------------------------


class MatlabExtractor(LanguageExtractor):
    language = "matlab"
    _function_pattern = re.compile(r"^\s*function\s+(?:[\w,\[\]\s]+=\s*)?(\w+)\s*\(", re.MULTILINE)
    _class_pattern = re.compile(r"^\s*classdef\s+(\w+)", re.MULTILINE)
    _import_pattern = None  # MATLAB doesn't have import statements per se


class RExtractor(LanguageExtractor):
    language = "r"
    _function_pattern = re.compile(r"(\w+)\s*<-\s*function\s*\(", re.MULTILINE)
    _class_pattern = None
    _import_pattern = re.compile(
        r"\blibrary\s*\(\s*[\w.]+\s*\)|\brequire\s*\(\s*[\w.]+\s*\)", re.MULTILINE
    )


class JuliaExtractor(LanguageExtractor):
    language = "julia"
    _function_pattern = re.compile(r"^\s*function\s+(\w+)", re.MULTILINE)
    _class_pattern = re.compile(r"^\s*(?:mutable\s+)?struct\s+(\w+)", re.MULTILINE)
    _import_pattern = re.compile(r"^\s*(?:using|import)\s+[\w.]+", re.MULTILINE)


class MathematicaExtractor(LanguageExtractor):
    language = "mathematica"
    _function_pattern = re.compile(r"(\w+)\s*\[.*?\]\s*:=", re.MULTILINE)
    _class_pattern = None
    _import_pattern = re.compile(r"<<\s*[\w`]+|Needs\s*\[", re.MULTILINE)


class HaskellExtractor(LanguageExtractor):
    language = "haskell"
    # Type signatures serve as the canonical function declaration marker.
    _function_pattern = re.compile(r"^(\w+)\s*::\s*\S", re.MULTILINE)
    # Matches data, newtype, and type alias declarations.
    _class_pattern = re.compile(r"^\s*(?:data|newtype|type)\s+(\w+)", re.MULTILINE)
    _import_pattern = re.compile(
        r"^\s*import\s+(?:qualified\s+)?[\w.]+",
        re.MULTILINE,
    )


class OCamlExtractor(LanguageExtractor):
    language = "ocaml"
    # Matches `let name arg ...` and `let rec name arg ...` top-level bindings.
    _function_pattern = re.compile(
        r"^\s*let\s+(?:rec\s+)?(\w+)\s+\w",
        re.MULTILINE,
    )
    # Matches type and module declarations.
    _class_pattern = re.compile(r"^\s*(?:type|module)\s+(\w+)", re.MULTILINE)
    _import_pattern = re.compile(r"^\s*open\s+[\w.]+", re.MULTILINE)


class GoAstExtractor(GoExtractor):
    """Go extractor with AST-backed structural enrichment."""

    def extract(
        self,
        source: str,
        focus_domains: list[str] | None = None,
        doc_context: str | None = None,
    ) -> ExtractionResult:
        result = super().extract(source, focus_domains=focus_domains, doc_context=doc_context)
        try:
            from .go_ast_extractor import extract_go_ast
        except ImportError:
            LOGGER.warning("go_ast_extractor not available; using regex-only extraction")
            return result

        ast_result = extract_go_ast(source)
        if not ast_result:
            return result

        result.functions = [
            FunctionInfo(name=item.name, line=item.line, signature=item.signature)
            for item in ast_result.functions
        ]
        result.classes = [
            ClassInfo(
                name=item.name,
                line=item.line,
                parents=(),
            )
            for item in ast_result.structs
        ]
        result.imports = ast_result.imports
        return result


class HaskellAstExtractor(HaskellExtractor):
    """Haskell extractor with AST-backed structural enrichment."""

    def extract(
        self,
        source: str,
        focus_domains: list[str] | None = None,
        doc_context: str | None = None,
    ) -> ExtractionResult:
        result = super().extract(source, focus_domains=focus_domains, doc_context=doc_context)
        try:
            from .haskell_ast_extractor import extract_haskell_ast
        except ImportError:
            LOGGER.warning("haskell_ast_extractor not available; using regex-only extraction")
            return result

        ast_result = extract_haskell_ast(source)
        if not ast_result:
            return result

        # Haskell declares types explicitly (``f :: Int -> Bool``), so the
        # arrow-separated signature is real type data rather than an inference
        # (UPG-31). Parsing is conservative: anything ambiguous yields nothing.
        haskell_functions: list[FunctionInfo] = []
        for item in ast_result.functions:
            arg_types, return_type = _split_haskell_type_signature(item.type_signature)
            haskell_functions.append(
                FunctionInfo(
                    name=item.name,
                    line=item.line,
                    signature=item.signature,
                    arg_types=arg_types,
                    return_type=return_type,
                )
            )
        result.functions = haskell_functions
        result.classes = [
            ClassInfo(name=item.name, line=item.line, parents=())
            for item in ast_result.types
        ]
        result.imports = ast_result.imports
        return result


class OCamlAstExtractor(OCamlExtractor):
    """OCaml extractor with AST-backed structural enrichment."""

    def extract(
        self,
        source: str,
        focus_domains: list[str] | None = None,
        doc_context: str | None = None,
    ) -> ExtractionResult:
        result = super().extract(source, focus_domains=focus_domains, doc_context=doc_context)
        try:
            from .ocaml_ast_extractor import extract_ocaml_ast
        except ImportError:
            LOGGER.warning("ocaml_ast_extractor not available; using regex-only extraction")
            return result

        ast_result = extract_ocaml_ast(source)
        if not ast_result:
            return result

        result.functions = [
            FunctionInfo(name=item.name, line=item.line, signature=item.signature)
            for item in ast_result.functions
        ]
        result.classes = [
            ClassInfo(name=item.name, line=item.line, parents=())
            for item in ast_result.types
        ]
        result.imports = ast_result.imports
        return result


class JuliaAstExtractor(JuliaExtractor):
    """Julia extractor with AST-backed structural enrichment."""

    def extract(
        self,
        source: str,
        focus_domains: list[str] | None = None,
        doc_context: str | None = None,
    ) -> ExtractionResult:
        result = super().extract(source, focus_domains=focus_domains, doc_context=doc_context)
        try:
            from .julia_ast_extractor import extract_julia_ast
        except ImportError:
            LOGGER.warning("julia_ast_extractor not available; using regex-only extraction")
            return result

        ast_result = extract_julia_ast(source)
        if not ast_result:
            return result

        result.functions = [
            FunctionInfo(name=item.name, line=item.line, signature=item.signature)
            for item in ast_result.functions
        ]
        result.classes = [
            ClassInfo(name=item.name, line=item.line, parents=())
            for item in ast_result.structs
        ]
        result.imports = ast_result.imports
        return result


# ---------------------------------------------------------------------------
# Extractor registry — language name → extractor class
# ---------------------------------------------------------------------------

_EXTRACTORS: Final[dict[str, type[LanguageExtractor]]] = {
    "python": PythonExtractor,
    "javascript": JavaScriptExtractor,
    "typescript": JavaScriptExtractor,
    "ruby": RubyExtractor,
    "php": PhpExtractor,
    "c": CExtractor,
    "cpp": CppExtractor,
    "rust": RustExtractor,
    "go": GoAstExtractor,
    "zig": ZigExtractor,
    "java": JavaExtractor,
    "csharp": CSharpExtractor,
    "scala": ScalaExtractor,
    "kotlin": KotlinExtractor,
    "matlab": MatlabExtractor,
    "r": RExtractor,
    "julia": JuliaAstExtractor,
    "mathematica": MathematicaExtractor,
    "haskell": HaskellAstExtractor,
    "ocaml": OCamlAstExtractor,
}



def get_extractor(language: str) -> LanguageExtractor:
    """Return the appropriate extractor for *language*, or a generic one."""
    normalized = language.strip().lower()
    cls = _EXTRACTORS.get(normalized, LanguageExtractor)
    return cls()


def supported_languages() -> list[str]:
    """Return sorted list of languages with dedicated extractors."""
    return sorted(_EXTRACTORS.keys())

