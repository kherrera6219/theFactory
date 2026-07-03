import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

from pod_worker.language_extractor import (  # noqa: E402
    _MAX_SOURCE_LENGTH,
    JavaAstExtractor,
    JavaScriptExtractor,
    PythonAstExtractor,
)


def test_java_ast_extractor_drops_empty_qualified_name_imports(monkeypatch) -> None:
    # Regression: javalang's `path` attribute can be empty/None for a
    # malformed or partial parse; without filtering, an empty
    # qualified_name was injected into the imports list as a bare "" entry.
    from pod_worker import java_ast_extractor

    def _fake_extract_java_ast(_source: str) -> java_ast_extractor.JavaAstExtractionResult:
        return java_ast_extractor.JavaAstExtractionResult(
            success=True,
            imports=[
                java_ast_extractor.JavaImportInfo(
                    qualified_name="", is_static=False, is_wildcard=False, line=1
                ),
                java_ast_extractor.JavaImportInfo(
                    qualified_name="java.util.List", is_static=False, is_wildcard=False, line=2
                ),
            ],
        )

    monkeypatch.setattr(java_ast_extractor, "extract_java_ast", _fake_extract_java_ast)
    extractor = JavaAstExtractor()
    result = extractor.extract("import java.util.List;\nclass Foo {}\n")

    assert result.imports == ["java.util.List"]


def test_python_ast_extractor_truncates_source_consistently_with_regex_pass() -> None:
    # Regression: the regex pipeline (super().extract()) truncates source to
    # _MAX_SOURCE_LENGTH internally, but extract_python_ast() used to receive
    # the original, untruncated source -- for files over the cap, AST-derived
    # functions/classes reflected content past what the regex pass ever saw,
    # and the size guard meant to bound ast.parse() cost was bypassed.
    line = "# " + "a" * 97 + "\n"  # exactly 100 chars per line
    assert len(line) == 100
    padding = line * (_MAX_SOURCE_LENGTH // 100)
    assert len(padding) == _MAX_SOURCE_LENGTH
    source = padding + "def past_the_cap():\n    return 1\n"

    extractor = PythonAstExtractor()
    result = extractor.extract(source)

    names = {fn.name for fn in result.functions}
    assert "past_the_cap" not in names


def test_javascript_extractor_detects_paren_less_arrow_function() -> None:
    # Regression: the function-detection regex only matched parenthesized
    # arg lists (`(x) => ...`) and `function` expressions, silently dropping
    # every bare single-identifier arrow function (`x => x + 1`) -- a common
    # JS idiom -- from the extracted function list with no error or log.
    extractor = JavaScriptExtractor()
    result = extractor.extract(
        "const arrowNoParen = x => x + 1;\n"
        "const arrowWithParens = (a, b) => a + b;\n"
        "function namedFn() { return 1; }\n"
    )
    names = {fn.name for fn in result.functions}
    assert "arrowNoParen" in names
    assert "arrowWithParens" in names
    assert "namedFn" in names
