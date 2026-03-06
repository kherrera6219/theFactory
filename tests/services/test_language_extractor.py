"""Tests for the language extraction engine.

Covers all four pod groups with representative source code snippets.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

from pod_worker.language_extractor import (  # noqa: E402
    JavaExtractor,
    JavaScriptExtractor,
    MatlabExtractor,
    PythonExtractor,
    RustExtractor,
    get_extractor,
    supported_languages,
)

# ---------------------------------------------------------------------------
# Pod A — Python
# ---------------------------------------------------------------------------

PYTHON_SAMPLE = '''\
import json
from pathlib import Path

class DataProcessor:
    """Processes mission data."""

    def __init__(self, items):
        self.items = items

    async def run(self):
        filtered = [x for x in self.items if x > 0]
        mapped = list(map(str, filtered))
        result = json.dumps(mapped)
        try:
            Path("output.json").write_text(result)
        except IOError:
            raise RuntimeError("write failed")
        return result
'''


class TestPythonExtractor:
    def setup_method(self):
        self.extractor = PythonExtractor()

    def test_detects_functions(self):
        result = self.extractor.extract(PYTHON_SAMPLE)
        names = [f.name for f in result.functions]
        assert "__init__" in names
        assert "run" in names

    def test_detects_classes(self):
        result = self.extractor.extract(PYTHON_SAMPLE)
        names = [c.name for c in result.classes]
        assert "DataProcessor" in names

    def test_detects_imports(self):
        result = self.extractor.extract(PYTHON_SAMPLE)
        assert len(result.imports) >= 2

    def test_detects_concepts(self):
        result = self.extractor.extract(PYTHON_SAMPLE)
        concept_ids = {c.concept_id for c in result.concepts}
        # Should detect: filter_collection, map_collection, json_encode,
        # define_class, define_function, async_function, try_catch, raise
        assert "DYN-005-001" in concept_ids  # define_function
        assert "DYN-014-001" in concept_ids  # define_class
        assert "DYN-006-001" in concept_ids  # async_function
        assert "DYN-007-001" in concept_ids  # try_catch

    def test_empty_source(self):
        result = self.extractor.extract("")
        assert result.error == "empty source"
        assert len(result.concepts) == 0

    def test_confidence_in_range(self):
        result = self.extractor.extract(PYTHON_SAMPLE)
        for concept in result.concepts:
            assert 0.0 < concept.confidence <= 1.0

    def test_summary_dict(self):
        result = self.extractor.extract(PYTHON_SAMPLE)
        summary = result.summary
        assert summary["language"] == "python"
        assert summary["functions_found"] >= 2
        assert summary["classes_found"] >= 1


# ---------------------------------------------------------------------------
# Pod A — JavaScript
# ---------------------------------------------------------------------------

JS_SAMPLE = """\
import express from 'express';
const axios = require('axios');

class ApiService {
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
    }

    async fetchData(endpoint) {
        try {
            const response = await fetch(`${this.baseUrl}/${endpoint}`);
            const data = JSON.parse(await response.text());
            return data.filter(item => item.active).map(item => item.name);
        } catch (error) {
            throw new Error('fetch failed');
        }
    }
}
"""


class TestJavaScriptExtractor:
    def setup_method(self):
        self.extractor = JavaScriptExtractor()

    def test_detects_class(self):
        result = self.extractor.extract(JS_SAMPLE)
        assert any(c.name == "ApiService" for c in result.classes)

    def test_detects_concepts(self):
        result = self.extractor.extract(JS_SAMPLE)
        concept_ids = {c.concept_id for c in result.concepts}
        assert "DYN-006-002" in concept_ids  # await
        assert "DYN-007-001" in concept_ids  # try_catch
        assert "DYN-001-001" in concept_ids  # filter
        assert "DYN-010-002" in concept_ids  # JSON.parse

    def test_detects_imports(self):
        result = self.extractor.extract(JS_SAMPLE)
        assert len(result.imports) >= 1


# ---------------------------------------------------------------------------
# Pod B — Rust
# ---------------------------------------------------------------------------

RUST_SAMPLE = """\
use std::collections::HashMap;

pub struct Config {
    values: HashMap<String, String>,
}

impl Config {
    pub fn new() -> Self {
        Config { values: HashMap::new() }
    }

    pub async fn load(&mut self, path: &str) -> Result<(), Box<dyn std::error::Error>> {
        let content = std::fs::read_to_string(path)?;
        match content.lines().count() {
            0 => Err("empty file".into()),
            _ => Ok(()),
        }
    }
}

trait Loadable {
    fn load_from(&mut self, source: &str) -> Option<usize>;
}
"""


class TestRustExtractor:
    def setup_method(self):
        self.extractor = RustExtractor()

    def test_detects_functions(self):
        result = self.extractor.extract(RUST_SAMPLE)
        names = [f.name for f in result.functions]
        assert "new" in names
        assert "load" in names

    def test_detects_structs_and_traits(self):
        result = self.extractor.extract(RUST_SAMPLE)
        names = [c.name for c in result.classes]
        assert "Config" in names
        assert "Loadable" in names

    def test_detects_concepts(self):
        result = self.extractor.extract(RUST_SAMPLE)
        concept_ids = {c.concept_id for c in result.concepts}
        assert "SYS-012-001" in concept_ids  # define_function (fn)
        assert "SYS-013-001" in concept_ids  # define_struct
        assert "SYS-013-003" in concept_ids  # impl_block
        assert "SYS-013-004" in concept_ids  # define_trait
        assert "SYS-011-001" in concept_ids  # Result type
        assert "SYS-015-001" in concept_ids  # async fn
        assert "SYS-016-001" in concept_ids  # use module


# ---------------------------------------------------------------------------
# Pod C — Java
# ---------------------------------------------------------------------------

JAVA_SAMPLE = """\
import java.util.*;
import java.util.stream.Collectors;

public class OrderService extends BaseService implements Serializable {

    private final List<Order> orders = new ArrayList<>();

    public List<String> getActiveOrderIds() {
        return orders.stream()
            .filter(o -> o.isActive())
            .map(Order::getId)
            .collect(Collectors.toList());
    }

    @Override
    public void processOrder(Order order) throws OrderException {
        try {
            synchronized (orders) {
                orders.add(order);
            }
        } catch (Exception e) {
            throw new OrderException("processing failed", e);
        }
    }
}
"""


class TestJavaExtractor:
    def setup_method(self):
        self.extractor = JavaExtractor()

    def test_detects_class(self):
        result = self.extractor.extract(JAVA_SAMPLE)
        assert any(c.name == "OrderService" for c in result.classes)

    def test_detects_methods(self):
        result = self.extractor.extract(JAVA_SAMPLE)
        names = [f.name for f in result.functions]
        assert "getActiveOrderIds" in names
        assert "processOrder" in names

    def test_detects_concepts(self):
        result = self.extractor.extract(JAVA_SAMPLE)
        concept_ids = {c.concept_id for c in result.concepts}
        assert "ENT-001-001" in concept_ids  # define_class
        assert "ENT-001-002" in concept_ids  # inheritance (extends)
        assert "ENT-001-003" in concept_ids  # implements
        assert "ENT-004-003" in concept_ids  # stream_operations
        assert "ENT-003-001" in concept_ids  # try_catch
        assert "ENT-005-001" in concept_ids  # annotation (@Override)
        assert "ENT-007-002" in concept_ids  # synchronized


# ---------------------------------------------------------------------------
# Pod D — MATLAB
# ---------------------------------------------------------------------------

MATLAB_SAMPLE = """\
function result = analyzeData(data)
    A = data' * data;
    eigenvals = eig(A);
    d = det(A);
    mu = mean(eigenvals);
    sigma = std(eigenvals);
    [U, S, V] = svd(A);
    figure;
    plot(eigenvals);
end
"""


class TestMatlabExtractor:
    def setup_method(self):
        self.extractor = MatlabExtractor()

    def test_detects_function(self):
        result = self.extractor.extract(MATLAB_SAMPLE)
        assert any(f.name == "analyzeData" for f in result.functions)

    def test_detects_concepts(self):
        result = self.extractor.extract(MATLAB_SAMPLE)
        concept_ids = {c.concept_id for c in result.concepts}
        assert "MATH-004-001" in concept_ids  # eigenvalues
        assert "MATH-001-004" in concept_ids  # determinant
        assert "MATH-005-001" in concept_ids  # mean
        assert "MATH-005-002" in concept_ids  # std dev
        assert "MATH-004-002" in concept_ids  # svd
        assert "MATH-003-001" in concept_ids  # plot


# ---------------------------------------------------------------------------
# Registry and utilities
# ---------------------------------------------------------------------------


class TestExtractorRegistry:
    def test_get_extractor_returns_correct_type(self):
        assert isinstance(get_extractor("python"), PythonExtractor)
        assert isinstance(get_extractor("rust"), RustExtractor)
        assert isinstance(get_extractor("java"), JavaExtractor)
        assert isinstance(get_extractor("matlab"), MatlabExtractor)

    def test_get_extractor_case_insensitive(self):
        assert isinstance(get_extractor("Python"), PythonExtractor)
        assert isinstance(get_extractor("RUST"), RustExtractor)

    def test_get_extractor_unknown_returns_generic(self):
        ext = get_extractor("brainfuck")
        assert ext.language == "generic"

    def test_supported_languages_not_empty(self):
        langs = supported_languages()
        assert len(langs) >= 15
        assert "python" in langs
        assert "rust" in langs
        assert "java" in langs
        assert "matlab" in langs

    def test_all_extractors_handle_whitespace_only(self):
        for lang in supported_languages():
            ext = get_extractor(lang)
            result = ext.extract("   \n\n  ")
            assert result.error == "empty source"
