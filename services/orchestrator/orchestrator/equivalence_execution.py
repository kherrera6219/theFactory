"""Behavioural equivalence verification by execution (UPG-50/51/52).

``equivalence_verifier.py`` answers *does the artifact match its contract*
(format, declared language, acceptance-criteria keywords). That is
``verification_scope: "correctness"`` and it is genuinely useful, but it is not
what the word "verification" promises: an artifact can conform to every contract
term and still compute the wrong answer.

This module adds the missing half. It takes the equivalence vectors Phase 4
attached to the mission's Refined-IR, invokes the generated artifact with each
vector's arguments inside the **shared hardened sandbox**, and records how many
produced a usable result. That is
``verification_scope: "behavioural"``.

Three deliberate limits, so the report cannot overclaim:

1. **Execution is gated** on ``mission_equivalence_python_execution_enabled``,
   which defaults ``false``. Flag off ⇒ the equivalence report is byte-identical
   to before this module existed.
2. **Only vectors marked executable are run.** Phase 4 tags a vector
   ``out.executable = false`` when no real signature was recovered; running those
   would mean inventing an invocation.
3. **A vector with no recorded expectation is a *smoke* result, not a pass.**
   Phase 4 deliberately leaves ``out.expected = null`` because the expected
   output is unknowable without execution. Counting "it ran without crashing" as
   equivalence would recreate exactly the "check that can never fail" problem
   this phase exists to remove — so those are reported separately as
   ``executed_without_error`` and are **not** counted as ``passed``.

Security: every vector argument and every artifact is attacker-influenced.
Nothing here builds its own container invocation — see
:mod:`orchestrator.sandbox_exec`.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from .sandbox_exec import check_docker_available, run_in_sandbox, workspace_root

LOGGER = logging.getLogger(__name__)

BEHAVIOURAL_SCHEMA_VERSION = "1.0.0"

# Python only for now, per UPG-51. Extending across the sandbox's other
# executable languages is a follow-up, not a rewrite: only _build_driver is
# language-specific.
SUPPORTED_LANGUAGES = frozenset({"python"})

_DEFAULT_IMAGE = "python:3.11-slim"
_PER_VECTOR_TIMEOUT_SECONDS = 15
_PER_VECTOR_MEMORY_MB = 256
# Bound total work: a module with hundreds of functions must not turn one
# mission into hundreds of container starts.
_MAX_VECTORS = 25

_DRIVER_FILENAME = "__equivalence_driver__.py"


def _normalise_language(value: Any) -> str:
    return str(value or "").strip().lower()


def collect_executable_vectors(
    rir_module: dict[str, Any], *, limit: int = _MAX_VECTORS
) -> list[dict[str, Any]]:
    """Return the executable equivalence vectors in *rir_module*.

    Each entry carries the owning function's identity so a failure can be
    attributed to a specific function rather than to the mission as a whole.
    """
    collected: list[dict[str, Any]] = []
    functions = rir_module.get("fns")
    if not isinstance(functions, list):
        return collected

    for function in functions:
        if not isinstance(function, dict):
            continue
        # Only AST-derived functions have a real signature to invoke.
        if function.get("projection_method") != "ast_v1":
            continue
        tests = function.get("tests")
        vectors = tests.get("equivalence_vectors") if isinstance(tests, dict) else None
        if not isinstance(vectors, list):
            continue
        for vector in vectors:
            if not isinstance(vector, dict):
                continue
            out = vector.get("out") if isinstance(vector.get("out"), dict) else {}
            if not out.get("executable"):
                continue
            inputs = vector.get("in") if isinstance(vector.get("in"), dict) else {}
            args = inputs.get("args")
            if not isinstance(args, dict):
                continue
            collected.append(
                {
                    "fn_id": str(function.get("fn_id") or ""),
                    "fn_name": str(function.get("name") or ""),
                    "case": str(inputs.get("case") or "nominal"),
                    "args": args,
                    "expected": out.get("expected"),
                    "expected_type": out.get("expected_type"),
                }
            )
            if len(collected) >= limit:
                return collected
    return collected


def _build_driver(
    *, artifact_filename: str, fn_name: str, args: dict[str, Any] | list[Any]
) -> str:
    """Return a Python driver that imports the artifact and calls one function.

    The driver is written into the read-only workspace alongside the artifact
    and prints a single JSON line, so the harness never has to parse arbitrary
    program output.

    Argument values are injected via ``json.loads`` of an embedded literal
    rather than interpolated as source, so a hostile value cannot escape into
    executable code inside the sandbox.
    """
    module_name = Path(artifact_filename).stem
    payload = json.dumps(json.dumps(args))  # double-encoded: a safe str literal
    return f'''\
import importlib.util, json, sys, traceback

_ARGS = json.loads({payload})

def _main():
    spec = importlib.util.spec_from_file_location(
        {module_name!r}, "/workspace/{artifact_filename}"
    )
    if spec is None or spec.loader is None:
        return {{"status": "import_error", "error": "cannot load artifact"}}
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        return {{"status": "import_error", "error": f"{{type(exc).__name__}}: {{exc}}"}}

    target = getattr(module, {fn_name!r}, None)
    if target is None or not callable(target):
        return {{"status": "missing_function", "error": {fn_name!r}}}

    try:
        result = target(*(_ARGS if isinstance(_ARGS, list) else list(_ARGS.values())))
    except Exception as exc:
        return {{
            "status": "raised",
            "error": f"{{type(exc).__name__}}: {{exc}}",
            "traceback": traceback.format_exc()[-800:],
        }}

    try:
        json.dumps(result)
        serialisable = result
    except (TypeError, ValueError):
        serialisable = repr(result)
    return {{"status": "ok", "result": serialisable, "result_type": type(result).__name__}}

print("__EQV__" + json.dumps(_main()))
'''


def _parse_driver_output(stdout: str) -> dict[str, Any]:
    """Extract the driver's JSON verdict from *stdout*.

    The artifact may print anything it likes; only the sentinel-prefixed final
    line is trusted.
    """
    for line in reversed(stdout.splitlines()):
        if line.startswith("__EQV__"):
            try:
                parsed = json.loads(line[len("__EQV__") :])
            except json.JSONDecodeError:
                return {"status": "unparseable", "error": "driver output not JSON"}
            return parsed if isinstance(parsed, dict) else {"status": "unparseable"}
    return {"status": "no_output", "error": "driver produced no verdict line"}


def _classify(vector: dict[str, Any], verdict: dict[str, Any]) -> tuple[str, str]:
    """Return ``(outcome, message)`` for one executed vector.

    ``passed`` is reserved for a vector with a recorded expectation that the
    artifact actually matched. A vector with ``expected = null`` can only reach
    ``executed_without_error`` — it is evidence the function runs on that input,
    not evidence it is correct.
    """
    status = verdict.get("status")
    label = f"{vector['fn_name']}[{vector['case']}]"

    if status == "ok":
        if vector.get("expected") is None:
            return "executed_without_error", f"{label}: returned {verdict.get('result')!r}"
        if verdict.get("result") == vector.get("expected"):
            return "passed", f"{label}: matched expected output"
        return (
            "failed",
            f"{label}: expected {vector['expected']!r}, got {verdict.get('result')!r}",
        )
    if status == "raised":
        return "failed", f"{label}: raised {verdict.get('error')}"
    if status == "missing_function":
        return "skipped", f"{label}: function not found in artifact"
    if status == "import_error":
        return "failed", f"{label}: artifact failed to import — {verdict.get('error')}"
    return "skipped", f"{label}: {verdict.get('error') or status}"


async def run_behavioural_equivalence(
    *,
    mission_id: str,
    language: str,
    artifact_filename: str,
    artifact_code: str,
    rir_module: dict[str, Any],
    docker_bin: str = "docker",
) -> dict[str, Any]:
    """Execute the mission's equivalence vectors and return a behavioural report.

    Never raises: any failure to execute degrades to a recorded ``skipped``
    report. A verification step that can crash a mission is worse than one that
    reports honestly that it could not run.
    """
    normalized = _normalise_language(language)
    base = {
        "schema_version": BEHAVIOURAL_SCHEMA_VERSION,
        "verification_scope": "behavioural",
        "mission_id": mission_id,
        "language": normalized,
        "equivalence_vectors_passed": 0,
        "equivalence_vectors_total": 0,
        "equivalence_vectors_executed_without_error": 0,
        "equivalence_vectors_skipped": 0,
        "findings": [],
        "vector_results": [],
    }

    if normalized not in SUPPORTED_LANGUAGES:
        return {
            **base,
            "status": "skipped",
            "reason": f"behavioural execution not implemented for {normalized or 'unknown'}",
        }

    vectors = collect_executable_vectors(rir_module)
    base["equivalence_vectors_total"] = len(vectors)
    if not vectors:
        return {
            **base,
            "status": "skipped",
            "reason": "no executable equivalence vectors in the mission's Refined-IR",
        }

    if not await check_docker_available(docker_bin):
        return {
            **base,
            "status": "skipped",
            "reason": "docker unavailable — behavioural equivalence not executed",
        }

    passed = 0
    ran_clean = 0
    skipped = 0
    findings: list[str] = []
    results: list[dict[str, Any]] = []

    for vector in vectors:
        try:
            with tempfile.TemporaryDirectory(
                prefix=f"hgr-eqv-{mission_id[:8]}-", dir=workspace_root()
            ) as tmpdir:
                workspace = Path(tmpdir)
                (workspace / artifact_filename).write_text(artifact_code, encoding="utf-8")
                (workspace / _DRIVER_FILENAME).write_text(
                    _build_driver(
                        artifact_filename=artifact_filename,
                        fn_name=vector["fn_name"],
                        args=vector["args"],
                    ),
                    encoding="utf-8",
                )
                sandbox_result = await run_in_sandbox(
                    docker_bin=docker_bin,
                    workspace_dir=tmpdir,
                    base_image=_DEFAULT_IMAGE,
                    command=f"python /workspace/{_DRIVER_FILENAME}",
                    timeout_seconds=_PER_VECTOR_TIMEOUT_SECONDS,
                    memory_mb=_PER_VECTOR_MEMORY_MB,
                )
        except Exception as exc:  # noqa: BLE001 - harness must never raise
            LOGGER.warning("behavioural vector execution error: %s", type(exc).__name__)
            skipped += 1
            results.append(
                {**_vector_identity(vector), "outcome": "skipped", "message": str(exc)[:200]}
            )
            continue

        if sandbox_result.timed_out:
            # A timeout is a non-result, not a behavioural failure of the code.
            skipped += 1
            message = f"{vector['fn_name']}[{vector['case']}]: timed out"
            findings.append(message)
            results.append(
                {**_vector_identity(vector), "outcome": "skipped", "message": message}
            )
            continue

        verdict = _parse_driver_output(sandbox_result.stdout)
        outcome, message = _classify(vector, verdict)
        if outcome == "passed":
            passed += 1
        elif outcome == "executed_without_error":
            ran_clean += 1
        elif outcome == "skipped":
            skipped += 1
        else:
            findings.append(message)
        results.append({**_vector_identity(vector), "outcome": outcome, "message": message})

    executed = len(vectors) - skipped
    failed = executed - passed - ran_clean
    return {
        **base,
        "status": "failed" if failed else "passed",
        "equivalence_vectors_passed": passed,
        "equivalence_vectors_executed_without_error": ran_clean,
        "equivalence_vectors_skipped": skipped,
        "equivalence_vectors_failed": failed,
        "findings": findings,
        "vector_results": results,
        # Stated explicitly so a reader cannot mistake smoke coverage for
        # verified equivalence.
        "note": (
            "`passed` counts only vectors with a recorded expected output that "
            "the artifact matched. `executed_without_error` means the function "
            "ran on those inputs — evidence of executability, not correctness."
        ),
    }


def _vector_identity(vector: dict[str, Any]) -> dict[str, Any]:
    return {
        "fn_id": vector.get("fn_id"),
        "fn_name": vector.get("fn_name"),
        "case": vector.get("case"),
        "args": vector.get("args"),
    }


# ---------------------------------------------------------------------------
# Contract-oracle equivalence (WQ7): BUILD_NEW missions
# ---------------------------------------------------------------------------

_STDIN_FILENAME = "__contract_stdin__.txt"
_CLI_TIMEOUT_SECONDS = 60
_CLI_MEMORY_MB = 512


def _contract_base(
    *, mission_id: str, language: str, vectors: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "schema_version": BEHAVIOURAL_SCHEMA_VERSION,
        "verification_scope": "behavioural",
        # What the expectations were derived from. "contract_oracle" vectors come
        # from the approved acceptance criteria, authored without sight of the
        # implementation; "refined_ir" vectors come from source being ported.
        "verification_basis": "contract_oracle",
        "oracle_independence": "interface_only",
        "mission_id": mission_id,
        "language": language,
        "equivalence_vectors_passed": 0,
        "equivalence_vectors_total": len(vectors),
        "equivalence_vectors_executed_without_error": 0,
        "equivalence_vectors_skipped": 0,
        "equivalence_vectors_failed": 0,
        "criteria_total": 0,
        "criteria_with_vectors": 0,
        "findings": [],
        "vector_results": [],
    }


def _classify_contract_call(vector: dict[str, Any], verdict: dict[str, Any]) -> tuple[str, str]:
    from .contract_oracle import values_equal

    status = verdict.get("status")
    label = f"{vector['vector_id']} {vector['function']}()"
    if status == "ok":
        if values_equal(vector.get("expected"), verdict.get("result")):
            return "passed", f"{label}: matched the contract's expected value"
        return (
            "failed",
            f"{label}: criterion {vector['criterion_index'] + 1} expected "
            f"{vector.get('expected')!r}, got {verdict.get('result')!r}",
        )
    if status == "raised":
        return "failed", f"{label}: raised {verdict.get('error')}"
    if status == "import_error":
        return "failed", f"{label}: artifact failed to import: {verdict.get('error')}"
    if status == "missing_function":
        return "failed", f"{label}: function named in the interface is missing"
    return "skipped", f"{label}: {verdict.get('error') or status}"


def _classify_contract_cli(vector: dict[str, Any], result: Any) -> tuple[str, str]:
    from .contract_oracle import stdout_matches

    label = f"{vector['vector_id']} argv={vector['argv']!r}"
    problems: list[str] = []
    if result.exit_code != vector["expected_exit_code"]:
        problems.append(
            f"exit code {result.exit_code}, expected {vector['expected_exit_code']}"
        )
    expected_stdout = vector.get("expected_stdout")
    mode = vector.get("stdout_match", "exact")
    if expected_stdout is not None and not stdout_matches(expected_stdout, result.stdout, mode):
        problems.append(
            f"stdout ({mode}) expected {expected_stdout[:120]!r}, got {result.stdout[:120]!r}"
        )
    if problems:
        stderr = str(getattr(result, "stderr", "") or "").strip()
        if stderr:
            # The tail carries the compiler or runtime error an operator needs.
            problems.append(f"stderr: {stderr[-240:]!r}")
        return (
            "failed",
            f"{label}: criterion {vector['criterion_index'] + 1}: " + "; ".join(problems),
        )
    return "passed", f"{label}: matched the contract's expected behaviour"


async def _run_one_contract_vector(
    *,
    vector: dict[str, Any],
    mission_id: str,
    artifact_filename: str,
    primary: str,
    siblings: dict[str, str],
    run_command: str,
    runtime_image: str,
    docker_bin: str,
) -> tuple[str, str]:
    from .contract_oracle import cli_command

    kind = vector.get("kind")
    with tempfile.TemporaryDirectory(
        prefix=f"hgr-cqv-{mission_id[:8]}-", dir=workspace_root()
    ) as tmpdir:
        workspace = Path(tmpdir)
        (workspace / artifact_filename).write_text(primary, encoding="utf-8")
        for name, body in siblings.items():
            safe = Path(name).name
            if safe and safe not in {artifact_filename, _DRIVER_FILENAME, _STDIN_FILENAME}:
                (workspace / safe).write_text(body, encoding="utf-8")
        if kind == "call":
            (workspace / _DRIVER_FILENAME).write_text(
                _build_driver(
                    artifact_filename=artifact_filename,
                    fn_name=str(vector["function"]),
                    args=list(vector["args"]),
                ),
                encoding="utf-8",
            )
            command = f"python /workspace/{_DRIVER_FILENAME}"
            image, timeout, memory = _DEFAULT_IMAGE, _PER_VECTOR_TIMEOUT_SECONDS, _PER_VECTOR_MEMORY_MB
        else:
            stdin_path = None
            if vector.get("stdin"):
                (workspace / _STDIN_FILENAME).write_text(str(vector["stdin"]), encoding="utf-8")
                stdin_path = f"/workspace/{_STDIN_FILENAME}"
            command = cli_command(run_command, list(vector["argv"]), stdin_file=stdin_path)
            image, timeout, memory = runtime_image, _CLI_TIMEOUT_SECONDS, _CLI_MEMORY_MB
        result = await run_in_sandbox(
            docker_bin=docker_bin,
            workspace_dir=tmpdir,
            base_image=image,
            command=command,
            timeout_seconds=timeout,
            memory_mb=memory,
        )
    if result.timed_out:
        # A timeout is a non-result, not a behavioural failure of the code.
        return "skipped", f"{vector['vector_id']}: timed out"
    if kind == "call":
        return _classify_contract_call(vector, _parse_driver_output(result.stdout))
    return _classify_contract_cli(vector, result)


async def run_contract_equivalence(
    *,
    mission_id: str,
    language: str,
    artifact_filename: str,
    artifact_code: str,
    contract_vectors: dict[str, Any],
    dependencies: Any = None,
    docker_bin: str = "docker",
) -> dict[str, Any]:
    """Execute contract-derived vectors against a BUILD_NEW artifact.

    Same guarantees as :func:`run_behavioural_equivalence`: never raises, runs
    only through :func:`sandbox_exec.run_in_sandbox`, and ``passed`` means the
    artifact produced the contract's expected result. There is no
    ``executed_without_error`` category here because every accepted vector
    carries an expectation (see ``contract_oracle.validate_vectors``).
    """
    from .contract_oracle import CALL_LANGUAGES
    from .rqca_agent import _LANGUAGE_RUNTIMES, _unbundle_source, _unmet_dependencies

    normalized = _normalise_language(language)
    vectors = [v for v in (contract_vectors.get("vectors") or []) if isinstance(v, dict)][
        :_MAX_VECTORS
    ]
    base = _contract_base(mission_id=mission_id, language=normalized, vectors=vectors)
    base["criteria_total"] = int(contract_vectors.get("criteria_total") or 0)
    base["criteria_with_vectors"] = len({v.get("criterion_index") for v in vectors})
    base["oracle"] = {
        "source": contract_vectors.get("source"),
        "agent_id": contract_vectors.get("agent_id"),
        "model": contract_vectors.get("model"),
        "rejected_vectors": len(contract_vectors.get("rejections") or []),
    }

    if not vectors:
        reason = contract_vectors.get("reason") or "the contract oracle produced no executable vectors"
        return {**base, "status": "skipped", "reason": str(reason)}
    unmet = _unmet_dependencies(normalized, dependencies)
    if unmet:
        return {
            **base,
            "status": "skipped",
            "reason": (
                "artifact requires dependencies the offline sandbox cannot provide: "
                + ", ".join(unmet[:6])
            ),
        }
    runtime = _LANGUAGE_RUNTIMES.get(normalized)
    if runtime is None:
        return {**base, "status": "skipped", "reason": f"no sandbox runtime for {normalized or 'unknown'}"}
    if not await check_docker_available(docker_bin):
        return {**base, "status": "skipped", "reason": "sandbox unavailable"}

    primary, siblings = _unbundle_source(artifact_code, artifact_filename)
    run_command = runtime["run_command"].format(
        filename=artifact_filename, stem=Path(artifact_filename).stem
    )
    if normalized == "zig":
        # `zig run file -- args`: without the separator zig parses them itself.
        run_command = f"{run_command} --"

    counts = {"passed": 0, "failed": 0, "skipped": 0}
    findings: list[str] = []
    results: list[dict[str, Any]] = []
    for vector in vectors:
        if vector.get("kind") == "call" and normalized not in CALL_LANGUAGES:
            outcome, message = "skipped", f"{vector.get('vector_id')}: call vectors need python"
        else:
            try:
                outcome, message = await _run_one_contract_vector(
                    vector=vector,
                    mission_id=mission_id,
                    artifact_filename=artifact_filename,
                    primary=primary,
                    siblings=siblings,
                    run_command=run_command,
                    runtime_image=str(runtime["base_image"]),
                    docker_bin=docker_bin,
                )
            except Exception as exc:  # noqa: BLE001 - harness must never raise
                LOGGER.warning("contract vector execution error: %s", type(exc).__name__)
                outcome, message = "skipped", f"{vector.get('vector_id')}: harness error"
        counts[outcome] += 1
        if outcome != "passed":
            findings.append(message)
        results.append(
            {
                "vector_id": vector.get("vector_id"),
                "kind": vector.get("kind"),
                "criterion_index": vector.get("criterion_index"),
                "outcome": outcome,
                "message": message[:400],
            }
        )

    if counts["failed"]:
        status = "failed"
    elif counts["passed"]:
        status = "passed"
    else:
        status = "skipped"
    report: dict[str, Any] = {
        **base,
        "status": status,
        "equivalence_vectors_passed": counts["passed"],
        "equivalence_vectors_failed": counts["failed"],
        "equivalence_vectors_skipped": counts["skipped"],
        "findings": findings,
        "vector_results": results,
        "runtime_substitute": runtime.get("runtime_substitute"),
        "note": (
            "Vectors were derived from the approved acceptance criteria by an oracle "
            "that saw the artifact's interface but not its implementation. `passed` "
            "means the artifact produced the contract's expected result."
        ),
    }
    if status == "skipped":
        report["reason"] = "every vector was skipped (timeouts or unsupported kinds)"
    return report
