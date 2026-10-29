"""
test_20_languages_functional.py

Functional verification test for all 20 code languages and their specialist agents in theFactory.
Asserts that every language:
1. Resolves to the correct Pod Manager and Specialist Agent definition.
2. Resolves to a concrete, non-base SpecialistAgent instance with valid guidance.
3. Successfully extracts symbols, functions, and concepts using its dedicated language extractor.
4. Passes specialist validation, execution, and reporting.
"""
from __future__ import annotations

import pytest
from orchestrator.agent_base import (
    SpecialistAgent,
    make_specialist_for_language,
)
from orchestrator.mission_flow import (
    LANGUAGE_TO_POD_MAP,
    POD_MANAGER_BY_LANGUAGE,
    SPECIALIST_BY_LANGUAGE,
)
from pod_worker.language_extractor import get_extractor
from pod_worker.toolchains import run_toolchain_check

LANG_SNIPPETS = {
    "c": ("calc.c", "#include <stdio.h>\nint add(int a, int b) { return a + b; }\nint main(void) { return add(1, 2); }\n"),
    "cpp": ("calc.cpp", "#include <iostream>\nint add(int a, int b) { return a + b; }\nclass Calculator { public: int multiply(int x, int y) { return x * y; } };\n"),
    "csharp": ("Calculator.cs", "namespace HolyGrail.Example;\npublic class Calculator {\n    public static int Add(int a, int b) => a + b;\n    public int Multiply(int x, int y) => x * y;\n}\n"),
    "go": ("calc.go", "package main\nfunc Add(a int, b int) int { return a + b }\ntype Calculator struct{}\nfunc (c *Calculator) Multiply(x int, y int) int { return x * y }\n"),
    "haskell": ("Calculator.hs", "module Calculator where\nadd :: Int -> Int -> Int\nadd a b = a + b\nmultiply :: Int -> Int -> Int\nmultiply x y = x * y\n"),
    "java": ("Calculator.java", "package com.holygrail.example;\npublic class Calculator {\n    public static int add(int a, int b) { return a + b; }\n    public int multiply(int x, int y) { return x * y; }\n}\n"),
    "javascript": ("calc.js", "function add(a, b) { return a + b; }\nclass Calculator { multiply(x, y) { return x * y; } }\n"),
    "julia": ("calc.jl", "function add(a::Int, b::Int)::Int\n    return a + b\nend\nstruct Calculator\nend\nfunction multiply(c::Calculator, x::Int, y::Int)::Int\n    return x * y\nend\n"),
    "kotlin": ("Calculator.kt", "package com.holygrail.example\nclass Calculator {\n    fun add(a: Int, b: Int): Int = a + b\n    fun multiply(x: Int, y: Int): Int = x * y\n}\n"),
    "mathematica": ("calc.wl", "AddNumbers[a_, b_] := a + b;\nMultiplyNumbers[x_, y_] := x * y;\n"),
    "matlab": ("calc.m", "function res = add(a, b)\n    res = a + b;\nend\nfunction out = multiply(x, y)\n    out = x * y;\nend\n"),
    "ocaml": ("calculator.ml", "let add a b = a + b\nlet multiply x y = x * y\nmodule Calculator = struct\n  let compute a b = add a b\nend\n"),
    "php": ("calc.php", "<?php\nfunction add($a, $b) { return $a + $b; }\nclass Calculator { public function multiply($x, $y) { return $x * $y; } }\n"),
    "python": ("calc.py", "def add(a: int, b: int) -> int:\n    return a + b\nclass Calculator:\n    def multiply(self, x: int, y: int) -> int:\n        return x * y\n"),
    "r": ("calc.R", "add <- function(a, b) { return(a + b) }\nmultiply <- function(x, y) { return(x * y) }\n"),
    "ruby": ("calc.rb", "def add(a, b)\n  a + b\nend\nclass Calculator\n  def multiply(x, y)\n    x * y\n  end\nend\n"),
    "rust": ("calc.rs", "fn add(a: i32, b: i32) -> i32 { a + b }\npub struct Calculator;\nimpl Calculator {\n    pub fn multiply(&self, x: i32, y: i32) -> i32 { x * y }\n}\n"),
    "scala": ("Calculator.scala", "package com.holygrail.example\nclass Calculator {\n  def add(a: Int, b: Int): Int = a + b\n  def multiply(x: Int, y: Int): Int = x * y\n}\n"),
    "typescript": ("calc.ts", "function add(a: number, b: number): number { return a + b; }\nclass Calculator { multiply(x: number, y: number): number { return x * y; } }\n"),
    "zig": ("calc.zig", "const std = @import(\"std\");\npub fn add(a: i32, b: i32) i32 { return a + b; }\npub const Calculator = struct { pub fn multiply(x: i32, y: i32) i32 { return x * y; } };\n"),
}

@pytest.mark.parametrize("language", sorted(SPECIALIST_BY_LANGUAGE.keys()))
def test_language_specialist_and_extractor_functional(language: str) -> None:
    # 1. Routing assertions
    pod = LANGUAGE_TO_POD_MAP.get(language)
    assert pod is not None, f"Missing pod mapping for {language}"
    spec_id = SPECIALIST_BY_LANGUAGE.get(language)
    assert spec_id is not None, f"Missing specialist id for {language}"
    pod_mgr = POD_MANAGER_BY_LANGUAGE.get(language)
    assert pod_mgr is not None, f"Missing pod manager for {language}"

    # 2. Specialist instance
    agent = make_specialist_for_language(language)
    assert isinstance(agent, SpecialistAgent)
    assert type(agent) is not SpecialistAgent
    assert len(agent.extraction_guidance) > 10

    # 3. Source extraction
    filename, code = LANG_SNIPPETS[language]
    extractor = get_extractor(language)
    res = extractor.extract(code)
    assert res.error is None, f"Extraction error in {language}: {res.error}"
    assert len(res.functions) > 0, f"No functions extracted for {language}"

    # 4. Toolchain check
    tc_res = run_toolchain_check(language, code, filename=filename)
    assert tc_res.passed is True, f"Toolchain preflight failed for {language}: {tc_res.output}"

    # 5. Agent validate and execute
    val = agent.validate(f"test-{language}", [{"path": filename, "content": code, "language": language}])
    assert val.passed is True
    exec_res = agent.execute(f"test-{language}", {"code": code, "language": language})
    assert exec_res is not None
    rep = agent.report(f"test-{language}", exec_res, val)
    assert rep.agent_id == agent.agent_id
