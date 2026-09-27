"""Contract-oracle equivalence vectors for BUILD_NEW missions (WQ7 / Sprint 1.2).

Behavioural equivalence (``equivalence_execution``) was only ever able to run on
missions that *transform* existing code: its vectors are projected from the
LogicNodes of the source being ported. A BUILD_NEW mission has no source, so it
was honestly ``skipped`` -- permanently. That left the missions the factory runs
most often with no behavioural evidence at all.

This module supplies the other oracle a new build has: its **contract**. The
acceptance criteria the operator approved say what the program must do; the
vectors here turn each criterion into concrete inputs and an expected result,
which ``equivalence_execution.run_contract_equivalence`` then executes against
the generated artifact in the shared hardened sandbox.

The property that makes this evidence rather than a tautology is
**independence**. The vector author (an LLM call) is shown the contract and the
artifact's *interface* -- function signatures, CLI usage -- and never its body.
An oracle that could read the implementation would write expectations that
mirror whatever the code happens to do, which is the Tester agent's blind spot
and exactly what this exists to avoid. ``interface_for_oracle`` is the only
bridge between the artifact and the prompt, and it emits no statements.

Nothing here fabricates vectors. With no model available the result is an empty
list and an honest reason, never a stub that could be counted.
"""

from __future__ import annotations

import ast
import json
import math
import re
import shlex
from typing import Any

CONTRACT_VECTORS_SCHEMA_VERSION = "contract_vectors.v1"
MAX_CONTRACT_VECTORS = 12
_MAX_JSON_BYTES = 4096
_MAX_STDOUT_EXPECTATION = 2000

VECTOR_KINDS = frozenset({"call", "cli"})
STDOUT_MATCH_MODES = frozenset({"exact", "contains", "json"})

#: Languages whose functions the call driver can import and invoke directly.
CALL_LANGUAGES = frozenset({"python"})


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _strings(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [str(item).strip() for item in value if str(item or "").strip()]
    return items[:limit]


def acceptance_criteria(metadata: dict[str, Any]) -> list[str]:
    """The approved acceptance criteria, feature contract first, de-duplicated."""
    seen: set[str] = set()
    ordered: list[str] = []
    for contract_key in ("feature_contract", "mission_contract"):
        for criterion in _strings(
            _dict(metadata.get(contract_key)).get("acceptance_criteria"), limit=20
        ):
            key = criterion.lower()
            if key not in seen:
                seen.add(key)
                ordered.append(criterion)
    return ordered[:12]


# ---------------------------------------------------------------------------
# Interface extraction -- signatures only, never bodies
# ---------------------------------------------------------------------------


def _python_functions(code: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return []
    functions: list[dict[str, Any]] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_") or node.name == "main":
            continue
        if isinstance(node, ast.AsyncFunctionDef):
            continue  # the call driver invokes synchronously
        args = node.args
        if args.vararg or args.kwarg or args.kwonlyargs or args.posonlyargs:
            # Positional-only invocation is the driver's contract; anything
            # richer would need an invented calling convention.
            continue
        params = [
            {
                "name": arg.arg,
                "annotation": ast.unparse(arg.annotation) if arg.annotation else None,
            }
            for arg in args.args
        ]
        docstring = ast.get_docstring(node) or ""
        functions.append(
            {
                "name": node.name,
                "params": params,
                "returns": ast.unparse(node.returns) if node.returns else None,
                # The first docstring line is part of the interface the author
                # chose to publish; the body is not.
                "summary": docstring.strip().splitlines()[0][:200] if docstring.strip() else "",
            }
        )
    return functions[:20]


def interface_for_oracle(
    *, language: str, code: str, generated_output: dict[str, Any], artifact_kind: str
) -> dict[str, Any]:
    """Describe how the artifact can be exercised without revealing how it works."""
    normalized = str(language or "").strip().lower()
    functions = _python_functions(code) if normalized in CALL_LANGUAGES else []
    usage = str(generated_output.get("usage_example") or "").strip()[:300]
    return {
        "language": normalized,
        "artifact_filename": str(generated_output.get("filename") or "")[:128],
        "artifact_kind": artifact_kind,
        "callable_functions": functions,
        "cli_usage_example": usage,
        "supports_call_vectors": bool(functions),
        "supports_cli_vectors": artifact_kind == "cli",
    }


# ---------------------------------------------------------------------------
# Vector validation -- the LLM's reply is untrusted input
# ---------------------------------------------------------------------------


def _json_size_ok(value: Any) -> bool:
    try:
        return len(json.dumps(value)) <= _MAX_JSON_BYTES
    except (TypeError, ValueError):
        return False


def validate_vectors(
    raw_vectors: Any, *, interface: dict[str, Any], criteria: list[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Keep only vectors that can be executed exactly as written.

    Returns ``(vectors, rejections)``. A rejected vector is dropped with a
    reason, never repaired: repairing an expectation would be the harness
    inventing the oracle's answer.
    """
    functions = {
        fn["name"]: fn for fn in interface.get("callable_functions", []) if isinstance(fn, dict)
    }
    vectors: list[dict[str, Any]] = []
    rejections: list[str] = []
    if not isinstance(raw_vectors, list):
        return vectors, ["reply carried no vector list"]

    for index, raw in enumerate(raw_vectors[: MAX_CONTRACT_VECTORS * 2]):
        label = f"vector {index}"
        if not isinstance(raw, dict):
            rejections.append(f"{label}: not an object")
            continue
        kind = str(raw.get("kind") or "").strip().lower()
        try:
            criterion_index = int(raw.get("criterion_index"))
        except (TypeError, ValueError):
            criterion_index = -1
        if not 0 <= criterion_index < len(criteria):
            rejections.append(f"{label}: does not cite an acceptance criterion")
            continue
        base = {
            "vector_id": f"cv-{len(vectors) + 1}",
            "kind": kind,
            "criterion_index": criterion_index,
            "criterion": criteria[criterion_index][:300],
            "rationale": str(raw.get("rationale") or "")[:300],
        }

        if kind == "call":
            fn_name = str(raw.get("function") or "")
            fn = functions.get(fn_name)
            if fn is None:
                rejections.append(f"{label}: function {fn_name!r} is not in the interface")
                continue
            args = raw.get("args")
            if not isinstance(args, list) or len(args) != len(fn["params"]):
                rejections.append(
                    f"{label}: {fn_name} takes {len(fn['params'])} argument(s)"
                )
                continue
            if "expected" not in raw or not _json_size_ok(args) or not _json_size_ok(
                raw.get("expected")
            ):
                rejections.append(f"{label}: missing or oversized expected value")
                continue
            vectors.append({**base, "function": fn_name, "args": args, "expected": raw["expected"]})
        elif kind == "cli":
            if not interface.get("supports_cli_vectors"):
                rejections.append(f"{label}: artifact is not a command-line program")
                continue
            argv = raw.get("argv", [])
            stdin = raw.get("stdin", "")
            if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
                rejections.append(f"{label}: argv must be a list of strings")
                continue
            if len(argv) > 16 or any(len(a) > 200 for a in argv) or not isinstance(stdin, str):
                rejections.append(f"{label}: argv/stdin out of bounds")
                continue
            if len(stdin) > _MAX_JSON_BYTES:
                rejections.append(f"{label}: stdin too large")
                continue
            expected_exit = raw.get("expected_exit_code", 0)
            if not isinstance(expected_exit, int) or isinstance(expected_exit, bool):
                rejections.append(f"{label}: expected_exit_code must be an integer")
                continue
            stdout = raw.get("expected_stdout")
            match = str(raw.get("stdout_match") or "exact").strip().lower()
            if stdout is not None and (
                not isinstance(stdout, str) or len(stdout) > _MAX_STDOUT_EXPECTATION
            ):
                rejections.append(f"{label}: expected_stdout must be a short string")
                continue
            if match not in STDOUT_MATCH_MODES:
                rejections.append(f"{label}: unknown stdout_match {match!r}")
                continue
            if stdout is None and expected_exit == 0:
                # "It exited 0" is a smoke test. The whole point is an
                # expectation that can fail for a wrong answer.
                rejections.append(f"{label}: states no observable expectation")
                continue
            vectors.append(
                {
                    **base,
                    "argv": argv,
                    "stdin": stdin,
                    "expected_exit_code": expected_exit,
                    "expected_stdout": stdout,
                    "stdout_match": match,
                }
            )
        else:
            rejections.append(f"{label}: unknown kind {kind!r}")
            continue
        if len(vectors) >= MAX_CONTRACT_VECTORS:
            break
    return vectors, rejections


# ---------------------------------------------------------------------------
# Comparison -- deterministic, no LLM judging
# ---------------------------------------------------------------------------


def values_equal(expected: Any, actual: Any) -> bool:
    """JSON-value equality with a tight float tolerance.

    Exact equality would fail ``0.1 + 0.2`` against ``0.3`` -- a representation
    artefact, not a behavioural difference. The tolerance is relative 1e-9, far
    too tight to hide a wrong computation.
    """
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isclose(float(expected), float(actual), rel_tol=1e-9, abs_tol=1e-12)
    if isinstance(expected, list) and isinstance(actual, (list, tuple)):
        return len(expected) == len(actual) and all(
            values_equal(e, a) for e, a in zip(expected, actual, strict=True)
        )
    if isinstance(expected, dict) and isinstance(actual, dict):
        return expected.keys() == actual.keys() and all(
            values_equal(expected[k], actual[k]) for k in expected
        )
    return expected == actual


_TRAILING_WS = re.compile(r"[ \t]+$", re.MULTILINE)


def _normalise_stdout(text: str) -> str:
    return _TRAILING_WS.sub("", text.replace("\r\n", "\n")).strip("\n")


def stdout_matches(expected: str, actual: str, mode: str) -> bool:
    if mode == "contains":
        return _normalise_stdout(expected) in _normalise_stdout(actual)
    if mode == "json":
        try:
            return values_equal(json.loads(expected), json.loads(actual))
        except (json.JSONDecodeError, TypeError):
            return False
    return _normalise_stdout(expected) == _normalise_stdout(actual)


def cli_command(run_command: str, argv: list[str], *, stdin_file: str | None) -> str:
    """Append quoted *argv* (and stdin) to the *last* command of a runtime chain.

    Runtime commands are ``build && run`` chains; arguments and redirection bind
    to the final command, which is the program itself.
    """
    quoted = " ".join(shlex.quote(arg) for arg in argv)
    command = f"{run_command} {quoted}".rstrip()
    if stdin_file:
        command = f"{command} < {shlex.quote(stdin_file)}"
    return command
