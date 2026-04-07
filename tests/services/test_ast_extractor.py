"""Tests for pod_worker/ast_extractor.py — AST-based Python extraction."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

ast_extractor = importlib.import_module("pod_worker.ast_extractor")
AstClassInfo = ast_extractor.AstClassInfo
AstExtractionResult = ast_extractor.AstExtractionResult
AstFunctionInfo = ast_extractor.AstFunctionInfo
extract_python_ast = ast_extractor.extract_python_ast

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SIMPLE_MODULE = """
import os
from typing import Optional

CONSTANT = 42

def greet(name: str) -> str:
    '''Say hello.'''
    return f"Hello, {name}"

async def fetch_data(url: str, timeout: Optional[float] = None) -> bytes:
    pass

class Animal:
    '''Base animal class.'''

    def __init__(self, name: str) -> None:
        self.name = name

    def speak(self) -> str:
        raise NotImplementedError
"""

_CLASS_HIERARCHY = """
from abc import ABC, abstractmethod

class Base(ABC):
    @abstractmethod
    def run(self) -> None: ...

class Child(Base):
    def run(self) -> None:
        pass

    def extra(self) -> int:
        return 1
"""

_DECORATED_FUNCTIONS = """
import functools

def decorator(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

@decorator
def public_api(x: int, y: int) -> int:
    return x + y

class Service:
    @staticmethod
    def ping() -> bool:
        return True

    @classmethod
    def create(cls) -> "Service":
        return cls()
"""


# ---------------------------------------------------------------------------
# Basic extraction
# ---------------------------------------------------------------------------

class TestExtractPythonAst:
    def test_parses_simple_module(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        assert result.success
        assert result.parse_error is None

    def test_empty_source_returns_empty(self):
        result = extract_python_ast("")
        assert result.success
        assert result.functions == []
        assert result.classes == []
        assert result.imports == []

    def test_whitespace_only_returns_empty(self):
        result = extract_python_ast("   \n  \t  ")
        assert result.success

    def test_syntax_error_returns_failure(self):
        result = extract_python_ast("def broken(: pass")
        assert not result.success
        assert result.parse_error is not None
        assert result.functions == []

    def test_collects_top_level_names(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        assert "greet" in result.top_level_names
        assert "fetch_data" in result.top_level_names
        assert "Animal" in result.top_level_names
        assert "CONSTANT" in result.top_level_names


# ---------------------------------------------------------------------------
# Function extraction
# ---------------------------------------------------------------------------

class TestFunctionExtraction:
    def test_extracts_function_names(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        names = {f.name for f in result.functions}
        assert "greet" in names
        assert "fetch_data" in names

    def test_sync_vs_async(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        by_name = {f.name: f for f in result.functions}
        assert by_name["greet"].is_async is False
        assert by_name["fetch_data"].is_async is True

    def test_method_detection(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        by_name = {f.name: f for f in result.functions}
        assert by_name["greet"].is_method is False
        assert by_name["__init__"].is_method is True
        assert by_name["speak"].is_method is True

    def test_return_annotation(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        by_name = {f.name: f for f in result.functions}
        assert by_name["greet"].return_annotation == "str"
        assert by_name["fetch_data"].return_annotation == "bytes"

    def test_docstring_extracted(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        by_name = {f.name: f for f in result.functions}
        assert by_name["greet"].docstring == "Say hello."

    def test_no_docstring_is_none(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        by_name = {f.name: f for f in result.functions}
        # fetch_data has no docstring
        assert by_name["fetch_data"].docstring is None

    def test_line_number_recorded(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        by_name = {f.name: f for f in result.functions}
        assert by_name["greet"].line > 0

    def test_signature_built(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        by_name = {f.name: f for f in result.functions}
        assert "greet" in by_name["greet"].signature
        assert "name" in by_name["greet"].signature

    def test_arg_types_extracted(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        by_name = {f.name: f for f in result.functions}
        assert "str" in by_name["greet"].arg_types

    def test_decorators_extracted(self):
        result = extract_python_ast(_DECORATED_FUNCTIONS)
        by_name = {f.name: f for f in result.functions}
        assert "decorator" in by_name["public_api"].decorators

    def test_static_method_decorator(self):
        result = extract_python_ast(_DECORATED_FUNCTIONS)
        by_name = {f.name: f for f in result.functions}
        assert "staticmethod" in by_name["ping"].decorators

    def test_classmethod_decorator(self):
        result = extract_python_ast(_DECORATED_FUNCTIONS)
        by_name = {f.name: f for f in result.functions}
        assert "classmethod" in by_name["create"].decorators


# ---------------------------------------------------------------------------
# Class extraction
# ---------------------------------------------------------------------------

class TestClassExtraction:
    def test_extracts_class_names(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        names = {c.name for c in result.classes}
        assert "Animal" in names

    def test_class_docstring(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        by_name = {c.name: c for c in result.classes}
        assert by_name["Animal"].docstring == "Base animal class."

    def test_class_methods_listed(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        by_name = {c.name: c for c in result.classes}
        assert "__init__" in by_name["Animal"].methods
        assert "speak" in by_name["Animal"].methods

    def test_base_classes(self):
        result = extract_python_ast(_CLASS_HIERARCHY)
        by_name = {c.name: c for c in result.classes}
        assert "ABC" in by_name["Base"].bases
        assert "Base" in by_name["Child"].bases

    def test_class_with_no_bases(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        by_name = {c.name: c for c in result.classes}
        assert by_name["Animal"].bases == ()

    def test_class_line_number(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        by_name = {c.name: c for c in result.classes}
        assert by_name["Animal"].line > 0

    def test_abstract_base_with_decorator(self):
        src = """
from abc import ABC, abstractmethod

class Validator(ABC):
    @abstractmethod
    def validate(self, data: dict) -> bool: ...
"""
        result = extract_python_ast(src)
        by_name = {c.name: c for c in result.classes}
        assert "validate" in by_name["Validator"].methods


# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------

class TestImportExtraction:
    def test_plain_import(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        plain = [i for i in result.imports if not i.is_from]
        assert any("os" in i.names for i in plain)

    def test_from_import(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        from_imports = [i for i in result.imports if i.is_from]
        assert any(i.module == "typing" for i in from_imports)

    def test_from_import_names(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        typing_import = next(i for i in result.imports if i.module == "typing")
        assert "Optional" in typing_import.names

    def test_star_import_excluded(self):
        src = "from os.path import *"
        result = extract_python_ast(src)
        assert result.success
        # Star import produces empty names tuple (not "*")
        from_imports = [i for i in result.imports if i.is_from]
        for imp in from_imports:
            assert "*" not in imp.names

    def test_import_alias(self):
        src = "import numpy as np"
        result = extract_python_ast(src)
        plain = [i for i in result.imports if not i.is_from]
        # alias is not stored in names (plain Import stores module name)
        assert any("numpy" in i.names for i in plain)

    def test_import_line_number(self):
        result = extract_python_ast(_SIMPLE_MODULE)
        assert all(i.line > 0 for i in result.imports)


# ---------------------------------------------------------------------------
# Edge cases & robustness
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_nested_function_detected(self):
        src = """
def outer():
    def inner():
        pass
    return inner
"""
        result = extract_python_ast(src)
        names = {f.name for f in result.functions}
        assert "outer" in names
        assert "inner" in names

    def test_multiple_classes(self):
        result = extract_python_ast(_CLASS_HIERARCHY)
        names = {c.name for c in result.classes}
        assert {"Base", "Child"} == names

    def test_complex_annotations_parsed(self):
        src = """
from typing import Dict, List, Optional, Tuple

def process(data: Dict[str, List[int]], flags: Optional[Tuple[str, ...]] = None) -> bool:
    return True
"""
        result = extract_python_ast(src)
        by_name = {f.name: f for f in result.functions}
        assert by_name["process"].return_annotation == "bool"

    def test_result_is_dataclass(self):
        result = extract_python_ast("")
        assert isinstance(result, AstExtractionResult)
        assert isinstance(result.functions, list)
        assert isinstance(result.classes, list)
        assert isinstance(result.imports, list)

    def test_function_info_frozen(self):
        src = "def f(x: int) -> str: return str(x)"
        result = extract_python_ast(src)
        fn = result.functions[0]
        assert isinstance(fn, AstFunctionInfo)
        # frozen=True means direct attribute assignment raises
        with pytest.raises((AttributeError, TypeError)):
            fn.name = "changed"  # type: ignore[misc]

    def test_class_info_frozen(self):
        src = "class Foo: pass"
        result = extract_python_ast(src)
        cls = result.classes[0]
        assert isinstance(cls, AstClassInfo)
        with pytest.raises((AttributeError, TypeError)):
            cls.name = "changed"  # type: ignore[misc]
