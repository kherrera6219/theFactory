#!/usr/bin/env python3
"""Prove each vendored test-runner image can tell a correct artifact from a broken one.

For every image in deploy/sandbox-images this runs a tiny artifact and its
generated-style tests through the *real* hardened sandbox
(`sandbox_exec.run_in_sandbox`: read-only workspace, --network=none,
--cap-drop=ALL) twice -- once correct, once with an off-by-one bug -- and
requires exit 0 for the first and a non-zero exit for the second.

A runner that passes both, or fails both, is not a test runner. This is the
check that would have caught every defect found while building these images:
a CRLF shebang (exit 127 for both), vitest not collecting test_*.ts (exit 1 for
both), and a vite cache write into the read-only vendored node_modules.

Usage:  python scripts/verify_sandbox_images.py [case ...]
Needs a Docker daemon and the images built (`make sandbox-images`).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from orchestrator.sandbox_exec import run_in_sandbox, workspace_root  # noqa: E402


@dataclass(frozen=True)
class Case:
    image: str
    artifact: tuple[str, str]
    tests: tuple[str, str]
    bug: tuple[str, str]


CASES: dict[str, Case] = {
    "java": Case(
        image="thefactory/sandbox-test-java:1",
        artifact=(
            "Main.java",
            "public class Main {\n"
            "  public static int add(int a, int b) { return a + b; }\n"
            "  public static void main(String[] args) { System.out.println(add(2, 3)); }\n"
            "}\n",
        ),
        tests=(
            "test_Main.java",
            "import org.junit.jupiter.api.Test;\n"
            "import static org.junit.jupiter.api.Assertions.assertEquals;\n\n"
            "public class MainTest {\n"
            "  @Test\n  void addsTwoNumbers() { assertEquals(5, Main.add(2, 3)); }\n}\n",
        ),
        bug=("return a + b;", "return a + b + 1;"),
    ),
    "kotlin": Case(
        image="thefactory/sandbox-test-kotlin:1",
        artifact=("main.kt", "fun add(a: Int, b: Int): Int = a + b\n\nfun main() { println(add(2, 3)) }\n"),
        tests=(
            "test_main.kt",
            "import kotlin.test.Test\nimport kotlin.test.assertEquals\n\n"
            "class MainTest {\n    @Test\n    fun addsTwoNumbers() { assertEquals(5, add(2, 3)) }\n}\n",
        ),
        bug=("= a + b", "= a + b + 1"),
    ),
    "scala": Case(
        image="thefactory/sandbox-test-scala:1",
        artifact=(
            "Main.scala",
            "object Main {\n  def add(a: Int, b: Int): Int = a + b\n"
            "  def main(args: Array[String]): Unit = println(add(2, 3))\n}\n",
        ),
        tests=(
            "test_Main.scala",
            "import org.scalatest.funsuite.AnyFunSuite\n\n"
            'class MainSuite extends AnyFunSuite {\n  test("adds") { assert(Main.add(2, 3) == 5) }\n}\n',
        ),
        bug=("= a + b", "= a + b + 1"),
    ),
    "php": Case(
        image="thefactory/sandbox-test-php:1",
        artifact=("calc.php", "<?php\nfunction add(int $a, int $b): int { return $a + $b; }\n"),
        tests=(
            "test_calc.php",
            "<?php\nuse PHPUnit\\Framework\\TestCase;\nrequire_once __DIR__ . '/calc.php';\n\n"
            "final class CalcTest extends TestCase\n{\n"
            "    public function testAdd(): void\n    {\n        $this->assertSame(5, add(2, 3));\n    }\n}\n",
        ),
        bug=("return $a + $b;", "return $a + $b + 1;"),
    ),
    "r": Case(
        image="thefactory/sandbox-test-r:1",
        artifact=("calc.R", "add <- function(a, b) a + b\n"),
        tests=(
            "test_calc.R",
            "library(testthat)\nsource('calc.R')\n\ntest_that('adds', { expect_equal(add(2, 3), 5) })\n",
        ),
        bug=("a + b", "a + b + 1"),
    ),
    "typescript-vitest": Case(
        image="thefactory/sandbox-test-node:1",
        artifact=("calc.ts", "export function add(a: number, b: number): number {\n  return a + b;\n}\n"),
        tests=(
            "test_calc.ts",
            "import { describe, it, expect } from 'vitest';\nimport { add } from './calc';\n\n"
            "describe('add', () => {\n  it('adds', () => { expect(add(2, 3)).toBe(5); });\n});\n",
        ),
        bug=("return a + b;", "return a + b + 1;"),
    ),
    "javascript-node-test": Case(
        image="thefactory/sandbox-test-node:1",
        artifact=("calc.js", "function add(a, b) { return a + b; }\nmodule.exports = { add };\n"),
        tests=(
            "test_calc.js",
            "const test = require('node:test');\nconst assert = require('node:assert');\n"
            "const { add } = require('./calc');\n\n"
            "test('adds', () => { assert.strictEqual(add(2, 3), 5); });\n",
        ),
        bug=("return a + b;", "return a + b + 1;"),
    ),
}


async def _exit_code(case: Case, *, broken: bool) -> tuple[int, str]:
    name, code = case.artifact
    if broken:
        assert case.bug[0] in code, f"bug marker missing for {case.image}"
        code = code.replace(*case.bug)
    test_name, test_code = case.tests
    with tempfile.TemporaryDirectory(prefix="hgr-imgcheck-", dir=workspace_root()) as tmp:
        Path(tmp, name).write_text(code, encoding="utf-8", newline="\n")
        Path(tmp, test_name).write_text(test_code, encoding="utf-8", newline="\n")
        result = await run_in_sandbox(
            docker_bin="docker",
            workspace_dir=tmp,
            base_image=case.image,
            command=f"/opt/factory/run-tests /workspace/{name} {test_name}",
            timeout_seconds=60,
            memory_mb=512,
        )
    if result.infrastructure_error:
        return -1, result.infrastructure_error
    tail = (result.stdout + result.stderr).strip().splitlines()[-3:]
    return (124 if result.timed_out else result.exit_code), " | ".join(tail)


async def _main(selected: list[str]) -> int:
    failures = 0
    for key in selected:
        case = CASES[key]
        good, good_tail = await _exit_code(case, broken=False)
        bad, bad_tail = await _exit_code(case, broken=True)
        ok = good == 0 and bad not in (0, -1, 124)
        failures += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {key:22} correct={good:<4} broken={bad:<4} {case.image}")
        if not ok:
            print(f"      correct: {good_tail[:300]}\n      broken:  {bad_tail[:300]}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("cases", nargs="*", help=f"subset of: {', '.join(CASES)}")
    args = parser.parse_args()
    unknown = [c for c in args.cases if c not in CASES]
    if unknown:
        parser.error(f"unknown case(s) {unknown}; choose from {list(CASES)}")
    return asyncio.run(_main(args.cases or list(CASES)))


if __name__ == "__main__":
    raise SystemExit(main())
