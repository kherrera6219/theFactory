"""test_ast_extractors_extended.py — Unit tests for Haskell, OCaml, Julia, Go, and Java AST extractors."""

from pod_worker.go_ast_extractor import extract_go_ast
from pod_worker.haskell_ast_extractor import extract_haskell_ast
from pod_worker.julia_ast_extractor import extract_julia_ast
from pod_worker.language_extractor import get_extractor
from pod_worker.ocaml_ast_extractor import extract_ocaml_ast
from pod_worker.toolchains import run_toolchain_check


def test_haskell_ast_extractor_basic():
    source = """
module Main where

import Data.List
import qualified Data.Map as Map

data Person = Person String Int
type Name = String

hello :: String -> String
hello name = "Hello " ++ name

add :: Int -> Int -> Int
add x y = x + y
"""
    result = extract_haskell_ast(source)
    assert result is not None
    assert result.module_name == "Main"
    assert "Data.List" in result.imports
    assert len(result.types) >= 2
    assert len(result.functions) >= 2
    fn_names = [f.name for f in result.functions]
    assert "hello" in fn_names
    assert "add" in fn_names


def test_ocaml_ast_extractor_basic():
    source = """
module StringUtils

open Base
open Printf

exception EmptyString of string

type point = { x : float; y : float }

let rec factorial n =
    if n <= 1 then 1 else n * factorial (n - 1)

let greet name =
    printf "Hello %s" name
"""
    result = extract_ocaml_ast(source)
    assert result is not None
    assert result.module_name == "StringUtils"
    assert "Base" in result.imports
    assert "EmptyString" in result.exceptions
    assert len(result.types) >= 1
    assert len(result.functions) >= 2
    fn_names = [f.name for f in result.functions]
    assert "factorial" in fn_names
    assert "greet" in fn_names


def test_julia_ast_extractor_basic():
    source = """
module GeometryUtils

using LinearAlgebra
import Base: show

struct Point
    x::Float64
    y::Float64
end

mutable struct Circle
    radius::Float64
end

function area(c::Circle)
    return pi * c.radius^2
end

scale(p::Point, s) = Point(p.x * s, p.y * s)
"""
    result = extract_julia_ast(source)
    assert result is not None
    assert result.module_name == "GeometryUtils"
    assert "LinearAlgebra" in result.imports
    assert len(result.structs) >= 2
    assert len(result.functions) >= 2
    fn_names = [f.name for f in result.functions]
    assert "area" in fn_names
    assert "scale" in fn_names


def test_go_ast_extractor_basic():
    source = """
package main

import (
    "fmt"
    "net/http"
)

type Server struct {
    Port int
}

func (s *Server) Start() error {
    return http.ListenAndServe(":8080", nil)
}

func main() {
    fmt.Println("Starting...")
}
"""
    result = extract_go_ast(source)
    assert result is not None
    assert "fmt" in result.imports
    assert len(result.structs) >= 1
    assert len(result.functions) >= 2


def test_language_extractor_registry():
    ocaml_ext = get_extractor("ocaml")
    res_ocaml = ocaml_ext.extract("module Test\nlet add x y = x + y")
    assert res_ocaml.language == "ocaml"
    assert len(res_ocaml.functions) >= 1

    julia_ext = get_extractor("julia")
    res_julia = julia_ext.extract("module Test\nfunction foo() return 42 end")
    assert res_julia.language == "julia"
    assert len(res_julia.functions) >= 1


def test_toolchain_checker_python():
    code = "def hello():\n    return 42\n"
    res = run_toolchain_check("python", code)
    assert res.language == "python"
    assert res.passed is True
