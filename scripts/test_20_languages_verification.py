"""
Test suite to verify basic functionality of all 20 code languages and their specialist agents in theFactory.
"""
from __future__ import annotations

import json
import os
import sys
import time

# Ensure search paths
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.extend([
    os.path.join(ROOT, "services", "orchestrator"),
    os.path.join(ROOT, "services", "pod-worker"),
    os.path.join(ROOT, "shared_runtime"),
])

from orchestrator.agent_base import (  # noqa: E402
    SpecialistAgent,
    make_specialist_for_language,
)
from orchestrator.mission_flow import (  # noqa: E402
    LANGUAGE_TO_POD_MAP,
    POD_MANAGER_BY_LANGUAGE,
    SPECIALIST_BY_LANGUAGE,
)
from pod_worker.language_extractor import get_extractor  # noqa: E402
from pod_worker.toolchains import run_toolchain_check  # noqa: E402

SNIPPETS: dict[str, dict[str, str]] = {
    "python": {
        "filename": "calc.py",
        "code": """def add(a: int, b: int) -> int:
    return a + b

class Calculator:
    def multiply(self, x: int, y: int) -> int:
        return x * y
""",
    },
    "javascript": {
        "filename": "calc.js",
        "code": """function add(a, b) {
    return a + b;
}

class Calculator {
    multiply(x, y) {
        return x * y;
    }
}
""",
    },
    "typescript": {
        "filename": "calc.ts",
        "code": """function add(a: number, b: number): number {
    return a + b;
}

class Calculator {
    multiply(x: number, y: number): number {
        return x * y;
    }
}
""",
    },
    "ruby": {
        "filename": "calc.rb",
        "code": """def add(a, b)
  a + b
end

class Calculator
  def multiply(x, y)
    x * y
  end
end
""",
    },
    "php": {
        "filename": "calc.php",
        "code": """<?php
function add($a, $b) {
    return $a + $b;
}

class Calculator {
    public function multiply($x, $y) {
        return $x * $y;
    }
}
""",
    },
    "c": {
        "filename": "calc.c",
        "code": """#include <stdio.h>

int add(int a, int b) {
    return a + b;
}

int main(void) {
    return add(1, 2);
}
""",
    },
    "cpp": {
        "filename": "calc.cpp",
        "code": """#include <iostream>

int add(int a, int b) {
    return a + b;
}

class Calculator {
public:
    int multiply(int x, int y) {
        return x * y;
    }
};
""",
    },
    "rust": {
        "filename": "calc.rs",
        "code": """fn add(a: i32, b: i32) -> i32 {
    a + b
}

pub struct Calculator;

impl Calculator {
    pub fn multiply(&self, x: i32, y: i32) -> i32 {
        x * y
    }
}
""",
    },
    "go": {
        "filename": "calc.go",
        "code": """package main

func Add(a int, b int) int {
    return a + b
}

type Calculator struct{}

func (c *Calculator) Multiply(x int, y int) int {
    return x * y
}
""",
    },
    "zig": {
        "filename": "calc.zig",
        "code": """const std = @import("std");

pub fn add(a: i32, b: i32) i32 {
    return a + b;
}

pub const Calculator = struct {
    pub fn multiply(x: i32, y: i32) i32 {
        return x * y;
    }
};
""",
    },
    "java": {
        "filename": "Calculator.java",
        "code": """package com.holygrail.example;

public class Calculator {
    public static int add(int a, int b) {
        return a + b;
    }

    public int multiply(int x, int y) {
        return x * y;
    }
}
""",
    },
    "csharp": {
        "filename": "Calculator.cs",
        "code": """namespace HolyGrail.Example;

public class Calculator {
    public static int Add(int a, int b) {
        return a + b;
    }

    public int Multiply(int x, int y) {
        return x * y;
    }
}
""",
    },
    "scala": {
        "filename": "Calculator.scala",
        "code": """package com.holygrail.example

class Calculator {
  def add(a: Int, b: Int): Int = a + b
  def multiply(x: Int, y: Int): Int = x * y
}
""",
    },
    "kotlin": {
        "filename": "Calculator.kt",
        "code": """package com.holygrail.example

class Calculator {
    fun add(a: Int, b: Int): Int = a + b
    fun multiply(x: Int, y: Int): Int = x * y
}
""",
    },
    "r": {
        "filename": "calc.R",
        "code": """add <- function(a, b) {
  return(a + b)
}

multiply <- function(x, y) {
  return(x * y)
}
""",
    },
    "matlab": {
        "filename": "calc.m",
        "code": """function res = add(a, b)
    res = a + b;
end

function out = multiply(x, y)
    out = x * y;
end
""",
    },
    "julia": {
        "filename": "calc.jl",
        "code": """function add(a::Int, b::Int)::Int
    return a + b
end

struct Calculator
end

function multiply(c::Calculator, x::Int, y::Int)::Int
    return x * y
end
""",
    },
    "mathematica": {
        "filename": "calc.wl",
        "code": """AddNumbers[a_, b_] := a + b;
MultiplyNumbers[x_, y_] := x * y;
""",
    },
    "haskell": {
        "filename": "Calculator.hs",
        "code": """module Calculator where

add :: Int -> Int -> Int
add a b = a + b

multiply :: Int -> Int -> Int
multiply x y = x * y
""",
    },
    "ocaml": {
        "filename": "calculator.ml",
        "code": """let add a b = a + b

let multiply x y = x * y

module Calculator = struct
  let compute a b = add a b
end
""",
    },
}

def run_tests():
    print("=" * 80)
    print("theFactory — 20 Language Specialists Functional Verification")
    print("=" * 80)

    results = []
    all_passed = True

    for lang in sorted(SPECIALIST_BY_LANGUAGE.keys()):
        lang_res = {
            "language": lang,
            "pod": str(LANGUAGE_TO_POD_MAP.get(lang)),
            "specialist_id": SPECIALIST_BY_LANGUAGE.get(lang),
            "pod_mgr_id": POD_MANAGER_BY_LANGUAGE.get(lang),
            "agent_class": None,
            "agent_instance": False,
            "validation_pass": False,
            "extractor_pass": False,
            "functions_found": 0,
            "classes_found": 0,
            "concepts_found": 0,
            "toolchain_pass": False,
            "report_generated": False,
            "passed": False,
        }

        try:
            # 1. Agent Specialist Instantiation
            agent = make_specialist_for_language(lang)
            lang_res["agent_class"] = type(agent).__name__
            lang_res["agent_instance"] = isinstance(agent, SpecialistAgent) and type(agent) is not SpecialistAgent

            # 2. Source Snippet & Extractor
            snippet = SNIPPETS.get(lang)
            if not snippet:
                raise ValueError(f"Missing snippet for language: {lang}")

            code = snippet["code"]
            filename = snippet["filename"]

            extractor = get_extractor(lang)
            extraction = extractor.extract(code)
            lang_res["extractor_pass"] = (extraction.error is None)
            lang_res["functions_found"] = len(extraction.functions)
            lang_res["classes_found"] = len(extraction.classes)
            lang_res["concepts_found"] = len(extraction.concepts)

            # 3. Toolchain Preflight Syntax Check
            tc_res = run_toolchain_check(lang, code)
            lang_res["toolchain_pass"] = tc_res.passed

            # 4. Agent Validation
            artifacts = [
                {
                    "path": filename,
                    "content": code,
                    "language": lang,
                }
            ]
            val = agent.validate(f"mission-test-{lang}", artifacts)
            lang_res["validation_pass"] = val.passed

            # 5. Agent Execution & Reporting
            agent_result = agent.execute(f"mission-test-{lang}", {"code": code, "language": lang})
            agent_report = agent.report(f"mission-test-{lang}", agent_result, val)
            lang_res["report_generated"] = bool(agent_report and agent_report.agent_id == agent.agent_id)

            # Total pass criteria
            lang_res["passed"] = (
                lang_res["agent_instance"]
                and lang_res["extractor_pass"]
                and lang_res["validation_pass"]
                and lang_res["toolchain_pass"]
                and lang_res["report_generated"]
            )
        except Exception as e:
            lang_res["error"] = str(e)
            lang_res["passed"] = False

        if not lang_res["passed"]:
            all_passed = False

        status_str = "PASS" if lang_res["passed"] else "FAIL"
        print(
            f"[{status_str:4}] {lang:12} | "
            f"Specialist: {lang_res['specialist_id']:20} ({lang_res['agent_class']:18}) | "
            f"Extractor: Fns={lang_res['functions_found']}, Classes={lang_res['classes_found']} | "
            f"Validate: {'OK' if lang_res['validation_pass'] else 'FAIL'}"
        )
        results.append(lang_res)

    print("=" * 80)
    passed_count = sum(1 for r in results if r["passed"])
    print(f"Summary: {passed_count}/{len(results)} Languages Functional (All 20 Tested)")
    print("=" * 80)

    # Save evidence
    os.makedirs(os.path.join(ROOT, "docs", "evidence"), exist_ok=True)
    evidence_path = os.path.join(ROOT, "docs", "evidence", "language_verification_20_languages.json")
    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "total_languages": len(results),
                "passed_languages": passed_count,
                "all_passed": all_passed,
                "languages": results,
            },
            f,
            indent=2,
        )
    print(f"Detailed evidence written to: {evidence_path}")
    return all_passed

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
