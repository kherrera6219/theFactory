"""Tests for the language extraction engine.

Covers all four pod groups with representative source code snippets.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

from pod_worker.language_extractor import (  # noqa: E402
    GoExtractor,
    HaskellExtractor,
    JavaExtractor,
    JavaScriptExtractor,
    MatlabExtractor,
    OCamlExtractor,
    PythonExtractor,
    RustExtractor,
    ZigExtractor,
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

    def test_focus_domains_boost_matching_concepts(self):
        baseline = self.extractor.extract(PYTHON_SAMPLE)
        focused = self.extractor.extract(PYTHON_SAMPLE, focus_domains=["list_operations"])
        baseline_filter = next(
            concept for concept in baseline.concepts if concept.concept_id == "DYN-001-002"
        )
        focused_filter = next(
            concept for concept in focused.concepts if concept.concept_id == "DYN-001-002"
        )
        assert focused_filter.confidence > baseline_filter.confidence

    def test_doc_context_boosts_matching_concepts(self):
        baseline = self.extractor.extract(PYTHON_SAMPLE)
        contextual = self.extractor.extract(
            PYTHON_SAMPLE,
            doc_context="list_operations: list comprehensions, append, filter",
        )
        baseline_filter = next(
            concept for concept in baseline.concepts if concept.concept_id == "DYN-001-002"
        )
        contextual_filter = next(
            concept for concept in contextual.concepts if concept.concept_id == "DYN-001-002"
        )
        assert contextual_filter.confidence > baseline_filter.confidence

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
# Pod B — Go
# ---------------------------------------------------------------------------

GO_SAMPLE = """\
package main

import (
    "fmt"
    "errors"
)

type Server struct {
    host string
    port int
}

type Handler interface {
    Handle(req string) error
}

func NewServer(host string, port int) *Server {
    return &Server{host: host, port: port}
}

func (s *Server) Start() error {
    ch := make(chan string)
    go func() {
        ch <- "ready"
    }()
    msg := <-ch
    if err := s.validate(); err != nil {
        return fmt.Errorf("invalid config: %w", err)
    }
    defer s.cleanup()
    fmt.Println(msg)
    return nil
}

func (s *Server) validate() error {
    if s.port == 0 {
        return errors.New("port must be non-zero")
    }
    return nil
}

func (s *Server) cleanup() {}
"""


class TestGoExtractor:
    def setup_method(self):
        self.extractor = GoExtractor()

    def test_detects_functions(self):
        result = self.extractor.extract(GO_SAMPLE)
        names = [f.name for f in result.functions]
        assert "NewServer" in names
        assert "Start" in names
        assert "validate" in names

    def test_detects_struct_and_interface(self):
        result = self.extractor.extract(GO_SAMPLE)
        names = [c.name for c in result.classes]
        assert "Server" in names
        assert "Handler" in names

    def test_detects_imports(self):
        result = self.extractor.extract(GO_SAMPLE)
        assert len(result.imports) >= 1

    def test_detects_concepts(self):
        result = self.extractor.extract(GO_SAMPLE)
        concept_ids = {c.concept_id for c in result.concepts}
        assert "SYS-020-001" in concept_ids  # define_function
        assert "SYS-020-002" in concept_ids  # goroutine
        assert "SYS-020-003" in concept_ids  # channel_operation
        assert "SYS-020-004" in concept_ids  # defer_call
        assert "SYS-020-005" in concept_ids  # error_check (if err != nil)
        assert "SYS-020-006" in concept_ids  # define_struct
        assert "SYS-020-007" in concept_ids  # define_interface

    def test_confidence_in_range(self):
        result = self.extractor.extract(GO_SAMPLE)
        for concept in result.concepts:
            assert 0.0 < concept.confidence <= 1.0


# ---------------------------------------------------------------------------
# Pod B — Zig
# ---------------------------------------------------------------------------

ZIG_SAMPLE = """\
const std = @import("std");
const math = @import("math.zig");

const Point = struct {
    x: f64,
    y: f64,
};

const Color = enum {
    Red,
    Green,
    Blue,
};

pub fn distance(a: Point, b: Point) f64 {
    const dx = a.x - b.x;
    const dy = a.y - b.y;
    return std.math.sqrt(dx * dx + dy * dy);
}

pub fn allocBuffer(allocator: std.mem.Allocator, size: usize) ![]u8 {
    const buf = try allocator.alloc(u8, size);
    defer allocator.free(buf);
    comptime var N = 16;
    _ = N;
    return buf;
}

fn printPoint(p: Point) void {
    std.debug.print("({d}, {d})\\n", .{ p.x, p.y });
}
"""


class TestZigExtractor:
    def setup_method(self):
        self.extractor = ZigExtractor()

    def test_detects_functions(self):
        result = self.extractor.extract(ZIG_SAMPLE)
        names = [f.name for f in result.functions]
        assert "distance" in names
        assert "allocBuffer" in names
        assert "printPoint" in names

    def test_detects_struct_and_enum(self):
        result = self.extractor.extract(ZIG_SAMPLE)
        names = [c.name for c in result.classes]
        assert "Point" in names
        assert "Color" in names

    def test_detects_imports(self):
        result = self.extractor.extract(ZIG_SAMPLE)
        assert len(result.imports) >= 2

    def test_detects_concepts(self):
        result = self.extractor.extract(ZIG_SAMPLE)
        concept_ids = {c.concept_id for c in result.concepts}
        assert "SYS-021-001" in concept_ids  # define_function
        assert "SYS-021-002" in concept_ids  # comptime_eval
        assert "SYS-021-004" in concept_ids  # define_struct
        assert "SYS-021-005" in concept_ids  # allocator_usage
        assert "SYS-021-006" in concept_ids  # import_module

    def test_confidence_in_range(self):
        result = self.extractor.extract(ZIG_SAMPLE)
        for concept in result.concepts:
            assert 0.0 < concept.confidence <= 1.0


# ---------------------------------------------------------------------------
# Pod D — Haskell
# ---------------------------------------------------------------------------

HASKELL_SAMPLE = """\
module Main where

import Data.List (sort, nub)
import qualified Data.Map.Strict as Map

data Shape = Circle Double
           | Rectangle Double Double
           deriving (Show, Eq)

class Area a where
    area :: a -> Double

instance Area Shape where
    area (Circle r)        = pi * r * r
    area (Rectangle w h)   = w * h

computeAreas :: [Shape] -> [Double]
computeAreas shapes = map area shapes

largestArea :: [Shape] -> Maybe Double
largestArea [] = Nothing
largestArea xs = Just $ maximum $ map area xs

groupByArea :: [Shape] -> Map.Map Double [Shape]
groupByArea shapes = foldr insert Map.empty shapes
  where
    insert s m = Map.insertWith (++) (area s) [s] m

main :: IO ()
main = do
    let shapes = [Circle 5.0, Rectangle 3.0 4.0, Circle 2.0]
    let areas = computeAreas shapes
    print areas
"""


class TestHaskellExtractor:
    def setup_method(self):
        self.extractor = HaskellExtractor()

    def test_detects_functions_via_type_signatures(self):
        result = self.extractor.extract(HASKELL_SAMPLE)
        names = [f.name for f in result.functions]
        assert "computeAreas" in names
        assert "largestArea" in names
        assert "groupByArea" in names

    def test_detects_data_types(self):
        result = self.extractor.extract(HASKELL_SAMPLE)
        names = [c.name for c in result.classes]
        assert "Shape" in names

    def test_detects_imports(self):
        result = self.extractor.extract(HASKELL_SAMPLE)
        assert len(result.imports) >= 2

    def test_detects_concepts(self):
        result = self.extractor.extract(HASKELL_SAMPLE)
        concept_ids = {c.concept_id for c in result.concepts}
        assert "MATH-009-001" in concept_ids  # type_signature
        assert "MATH-009-003" in concept_ids  # define_typeclass
        assert "MATH-009-004" in concept_ids  # typeclass_instance
        assert "MATH-009-005" in concept_ids  # define_data
        assert "MATH-009-009" in concept_ids  # import_module

    def test_confidence_in_range(self):
        result = self.extractor.extract(HASKELL_SAMPLE)
        for concept in result.concepts:
            assert 0.0 < concept.confidence <= 1.0


# ---------------------------------------------------------------------------
# Pod D — OCaml
# ---------------------------------------------------------------------------

OCAML_SAMPLE = """\
open List

type shape =
  | Circle of float
  | Rectangle of float * float

module Geometry = struct
  let pi = 3.14159265358979

  let area = function
    | Circle r        -> pi *. r *. r
    | Rectangle (w, h) -> w *. h

  let perimeter = function
    | Circle r        -> 2.0 *. pi *. r
    | Rectangle (w, h) -> 2.0 *. (w +. h)
end

let compute_areas shapes =
  List.map Geometry.area shapes

let rec total_area shapes =
  match shapes with
  | [] -> 0.0
  | s :: rest -> Geometry.area s +. total_area rest

let () =
  let shapes = [Circle 5.0; Rectangle 3.0 4.0] in
  let areas = compute_areas shapes in
  List.iter (fun a -> Printf.printf "%f\\n" a) areas
"""


class TestOCamlExtractor:
    def setup_method(self):
        self.extractor = OCamlExtractor()

    def test_detects_functions(self):
        result = self.extractor.extract(OCAML_SAMPLE)
        names = [f.name for f in result.functions]
        assert "compute_areas" in names
        assert "total_area" in names

    def test_detects_types_and_modules(self):
        result = self.extractor.extract(OCAML_SAMPLE)
        names = [c.name for c in result.classes]
        assert "shape" in names
        assert "Geometry" in names

    def test_detects_imports(self):
        result = self.extractor.extract(OCAML_SAMPLE)
        assert len(result.imports) >= 1

    def test_detects_concepts(self):
        result = self.extractor.extract(OCAML_SAMPLE)
        concept_ids = {c.concept_id for c in result.concepts}
        assert "MATH-010-001" in concept_ids  # define_function
        assert "MATH-010-002" in concept_ids  # recursive_function
        assert "MATH-010-003" in concept_ids  # match_expression
        assert "MATH-010-004" in concept_ids  # define_type
        assert "MATH-010-005" in concept_ids  # open_module
        assert "MATH-010-008" in concept_ids  # define_module

    def test_confidence_in_range(self):
        result = self.extractor.extract(OCAML_SAMPLE)
        for concept in result.concepts:
            assert 0.0 < concept.confidence <= 1.0


# ---------------------------------------------------------------------------
# Registry and utilities
# ---------------------------------------------------------------------------


class TestExtractorRegistry:
    def test_get_extractor_returns_correct_type(self):
        assert isinstance(get_extractor("python"), PythonExtractor)
        assert isinstance(get_extractor("rust"), RustExtractor)
        assert isinstance(get_extractor("java"), JavaExtractor)
        assert isinstance(get_extractor("matlab"), MatlabExtractor)
        assert isinstance(get_extractor("go"), GoExtractor)
        assert isinstance(get_extractor("zig"), ZigExtractor)
        assert isinstance(get_extractor("haskell"), HaskellExtractor)
        assert isinstance(get_extractor("ocaml"), OCamlExtractor)

    def test_get_extractor_case_insensitive(self):
        assert isinstance(get_extractor("Python"), PythonExtractor)
        assert isinstance(get_extractor("RUST"), RustExtractor)
        assert isinstance(get_extractor("Go"), GoExtractor)
        assert isinstance(get_extractor("ZIG"), ZigExtractor)

    def test_get_extractor_unknown_returns_generic(self):
        ext = get_extractor("brainfuck")
        assert ext.language == "generic"

    def test_supported_languages_not_empty(self):
        langs = supported_languages()
        assert len(langs) >= 19
        assert "python" in langs
        assert "rust" in langs
        assert "java" in langs
        assert "matlab" in langs
        assert "go" in langs
        assert "zig" in langs
        assert "haskell" in langs
        assert "ocaml" in langs

    def test_all_extractors_handle_whitespace_only(self):
        for lang in supported_languages():
            ext = get_extractor(lang)
            result = ext.extract("   \n\n  ")
            assert result.error == "empty source"


# ---------------------------------------------------------------------------
# UPG-31 — Haskell type-signature parsing.
#
# Haskell declares types explicitly, so the arrow-separated signature is real
# type data rather than an inference. Parsing must be depth-aware (arrows
# nested inside parentheses belong to a higher-order argument) and must refuse
# anything ambiguous — an empty result is honest, a wrong one silently corrupts
# the node's declared types.
# ---------------------------------------------------------------------------

from pod_worker.language_extractor import (  # noqa: E402
    _split_haskell_type_signature as _split_hs,
)


@pytest.mark.parametrize(
    ("signature", "expected"),
    [
        ("Int -> String -> Bool", (("Int", "String"), "Bool")),
        ("Int", ((), "Int")),
        ("Map String [Int] -> Maybe Int", (("Map String [Int]",), "Maybe Int")),
        # A "name ::" prefix is stripped.
        ("quicksort :: [Int] -> [Int]", (("[Int]",), "[Int]")),
        # Depth-aware: the inner arrow is part of one higher-order argument.
        ("(Int -> Bool) -> [Int] -> Int", (("(Int -> Bool)", "[Int]"), "Int")),
        ("(a -> b) -> (b -> c) -> a -> c", (("(a -> b)", "(b -> c)", "a"), "c")),
        # A typeclass context constrains types; it is not itself an argument.
        ("Ord a => a -> a -> Bool", (("a", "a"), "Bool")),
    ],
)
def test_haskell_signature_parses_to_types(signature, expected) -> None:
    assert _split_hs(signature) == expected


@pytest.mark.parametrize("signature", [None, "", "   ", "Int -> (Bool", "a -> b)"])
def test_haskell_signature_refuses_ambiguous_input(signature) -> None:
    """Unbalanced or absent input must yield nothing rather than a guess."""
    assert _split_hs(signature) == ((), None)
