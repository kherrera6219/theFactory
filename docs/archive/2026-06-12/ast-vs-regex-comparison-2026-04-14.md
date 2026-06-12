# Python AST vs Regex Extractor Comparison

Document version: 2026.04.14  
Last updated: 2026-04-14  
Status: Review Artifact  
Audience: Developers, reviewers, and maintainers

**Date:** 2026-04-14  
**Fixture:** `tests/fixtures/extractors/python_sample.py`  
**Extractor versions:** `PythonExtractor` (regex) · `PythonAstExtractor` (AST-augmented)

---

## Summary

On the golden Python fixture both extractors produce **identical structural output**.
The fixture covers the most common real-world patterns: plain functions, async functions,
static methods, class inheritance, and stdlib imports.

The AST extractor's value appears in edge cases that are outside the fixture:
comments/strings that look like code, multi-line signatures, decorator chains, and nested
class definitions.

---

## Structural fields comparison

### Functions (6 detected by both)

| Function | Regex line | AST line | Match |
|---|---|---|---|
| `__init__` | 13 | 13 | ✅ |
| `process` | 16 | 16 | ✅ |
| `validate` | 20 | 20 | ✅ |
| `log_event` | 27 | 27 | ✅ |
| `fetch_mission` | 31 | 31 | ✅ |
| `_internal_helper` | 36 | 36 | ✅ |

### Classes (2 detected by both)

| Class | Regex line | AST line | Match |
|---|---|---|---|
| `DataProcessor` | 10 | 10 | ✅ |
| `AuditLogger` | 24 | 24 | ✅ |

### Imports (3 detected by both)

Both extractors detect all three imports:
- `import json`
- `from pathlib import Path`
- `from typing import Optional`

### Concepts (LogicNodes)

Both produce 14 concepts. All have `extraction_method="regex"` — concept detection
is always regex-based; the AST extractor does not alter it.

---

## Key differences (not visible in this fixture)

| Scenario | Regex | AST |
|---|---|---|
| Function defined inside string literal | False positive possible | ✅ No false positive |
| Decorator on function (`@staticmethod`) | Name resolved correctly | ✅ Decorator captured too |
| Multi-line function signature | Single-line only | ✅ Full signature |
| Nested function inside another function | Detected | ✅ Detected with nesting context |
| SyntaxError in source | Returns regex result | Falls back to regex result |

---

## Conclusion

Enable `PYTHON_AST_EXTRACTOR_ENABLED=true` in production when:
- Source files contain decorator-heavy code
- Multi-line signatures are common (type-annotated Python)
- False positives from string literals are causing bad LogicNode attribution

The regex extractor remains the default for broad language coverage and zero-dep
operation. The AST extractor is an opt-in quality upgrade for Python-heavy workloads.
