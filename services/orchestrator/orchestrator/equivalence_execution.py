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

# Polyglot direct-call behavioural equivalence across Python, JavaScript, and TypeScript.
SUPPORTED_LANGUAGES = frozenset({"python", "javascript", "typescript"})

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


def _build_js_ts_driver(
    *, artifact_filename: str, fn_name: str, args: dict[str, Any] | list[Any]
) -> str:
    """Return a JavaScript/TypeScript driver that imports the artifact and calls one function."""
    payload = json.dumps(json.dumps(args))
    target_path = json.dumps(f"/workspace/{artifact_filename}")
    fn_literal = json.dumps(fn_name)
    return f"""\
const _ARGS = JSON.parse({payload});
const _TARGET_PATH = {target_path};
const _FN_NAME = {fn_literal};

async function _main() {{
  let mod;
  try {{
    mod = await import("file://" + _TARGET_PATH);
  }} catch (err) {{
    return {{ status: "import_error", error: String(err && err.message ? err.message : err) }};
  }}
  const target = (mod && mod[_FN_NAME]) || (mod && mod.default && mod.default[_FN_NAME]);
  if (typeof target !== "function") {{
    return {{ status: "missing_function", error: _FN_NAME }};
  }}
  const argList = Array.isArray(_ARGS) ? _ARGS : Object.values(_ARGS || {{}});
  try {{
    const result = await target(...argList);
    return {{ status: "ok", result: result, result_type: typeof result }};
  }} catch (err) {{
    return {{
      status: "raised",
      error: String(err && err.message ? err.message : err),
      traceback: String(err && err.stack ? err.stack : "").slice(-800),
    }};
  }}
}}

_main().then((verdict) => {{
  console.log("__EQV__" + JSON.stringify(verdict));
}});
"""


def _driver_spec_for_language(language: str) -> tuple[str, str, str]:
    """Return (driver_filename, base_image, command) for direct-call equivalence."""
    normalized = _normalise_language(language)
    if normalized in {"javascript", "typescript"}:
        from .rqca_agent import _LANGUAGE_RUNTIMES

        runtime = _LANGUAGE_RUNTIMES.get(normalized, {})
        base_image = str(runtime.get("base_image") or "node:20-slim")
        driver_filename = (
            "__equivalence_driver__.ts"
            if normalized == "typescript"
            else "__equivalence_driver__.mjs"
        )
        run_cmd = str(runtime.get("run_command") or "node /workspace/{filename}").format(
            filename=driver_filename,
            stem=Path(driver_filename).stem,
        )
        return driver_filename, base_image, run_cmd
    return _DRIVER_FILENAME, _DEFAULT_IMAGE, f"python /workspace/{_DRIVER_FILENAME}"


def _build_driver(
    *,
    artifact_filename: str,
    fn_name: str,
    args: dict[str, Any] | list[Any],
    language: str = "python",
) -> str:
    """Return a language driver that imports the artifact and calls one function.

    The driver is written into the read-only workspace alongside the artifact
    and prints a single JSON line, so the harness never has to parse arbitrary
    program output.

    Argument values are injected via ``json.loads`` of an embedded literal
    rather than interpolated as source, so a hostile value cannot escape into
    executable code inside the sandbox.
    """
    if _normalise_language(language) in {"javascript", "typescript"}:
        return _build_js_ts_driver(
            artifact_filename=artifact_filename, fn_name=fn_name, args=args
        )
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

    driver_filename, driver_image, driver_command = _driver_spec_for_language(normalized)

    for vector in vectors:
        try:
            with tempfile.TemporaryDirectory(
                prefix=f"hgr-eqv-{mission_id[:8]}-", dir=workspace_root()
            ) as tmpdir:
                workspace = Path(tmpdir)
                (workspace / artifact_filename).write_text(artifact_code, encoding="utf-8")
                (workspace / driver_filename).write_text(
                    _build_driver(
                        artifact_filename=artifact_filename,
                        fn_name=vector["fn_name"],
                        args=vector["args"],
                        language=normalized,
                    ),
                    encoding="utf-8",
                )
                sandbox_result = await run_in_sandbox(
                    docker_bin=docker_bin,
                    workspace_dir=tmpdir,
                    base_image=driver_image,
                    command=driver_command,
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

        if sandbox_result.infrastructure_error or sandbox_result.timed_out:
            # A timeout or harness failure is a non-result, not a behavioural
            # failure of the code.
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
    language: str = "python",
) -> tuple[str, str]:
    from .contract_oracle import cli_command

    kind = vector.get("kind")
    driver_filename, driver_image, driver_command = _driver_spec_for_language(language)
    with tempfile.TemporaryDirectory(
        prefix=f"hgr-cqv-{mission_id[:8]}-", dir=workspace_root()
    ) as tmpdir:
        workspace = Path(tmpdir)
        (workspace / artifact_filename).write_text(primary, encoding="utf-8")
        for name, body in siblings.items():
            safe = Path(name).name
            if safe and safe not in {
                artifact_filename,
                _DRIVER_FILENAME,
                driver_filename,
                _STDIN_FILENAME,
            }:
                (workspace / safe).write_text(body, encoding="utf-8")
        if kind == "call":
            (workspace / driver_filename).write_text(
                _build_driver(
                    artifact_filename=artifact_filename,
                    fn_name=str(vector["function"]),
                    args=list(vector["args"]),
                    language=language,
                ),
                encoding="utf-8",
            )
            command = driver_command
            image, timeout, memory = driver_image, _PER_VECTOR_TIMEOUT_SECONDS, _PER_VECTOR_MEMORY_MB
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
    if result.infrastructure_error:
        return "skipped", f"{vector['vector_id']}: {result.infrastructure_error}"
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
                    language=normalized,
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


async def _execute_vector_against_artifact(
    *,
    mission_id: str,
    side: str,
    language: str,
    filename: str,
    primary_code: str,
    siblings: dict[str, str],
    vector: dict[str, Any],
    runtime: dict[str, Any],
    docker_bin: str,
    runner: Any,
) -> Any:
    """Execute one CLI or call vector against a single source/target artifact inside the sandbox."""
    from .contract_oracle import cli_command

    kind = str(vector.get("kind") or "cli").strip().lower()
    driver_filename, driver_image, driver_command = _driver_spec_for_language(language)
    base_cmd = str(runtime["run_command"]).format(filename=filename, stem=Path(filename).stem)
    if language == "zig":
        base_cmd = f"{base_cmd} --"

    with tempfile.TemporaryDirectory(
        prefix=f"hgr-dual-{side}-{mission_id[:6]}-", dir=workspace_root()
    ) as tmpdir:
        ws_dir = Path(tmpdir)
        target_path = ws_dir / filename
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(primary_code, encoding="utf-8")
        for s_name, s_body in siblings.items():
            safe_rel = Path(s_name).as_posix().lstrip("/")
            if safe_rel and not safe_rel.startswith("..") and safe_rel != filename:
                s_dest = ws_dir / safe_rel
                s_dest.parent.mkdir(parents=True, exist_ok=True)
                s_dest.write_text(s_body, encoding="utf-8")

        if kind == "call":
            (ws_dir / driver_filename).write_text(
                _build_driver(
                    artifact_filename=filename,
                    fn_name=str(vector.get("fn_name") or vector.get("function") or ""),
                    args=vector.get("args") or [],
                    language=language,
                ),
                encoding="utf-8",
            )
            command, image, timeout, memory = (
                driver_command,
                driver_image,
                _PER_VECTOR_TIMEOUT_SECONDS,
                _PER_VECTOR_MEMORY_MB,
            )
        else:
            stdin_path = None
            if vector.get("stdin"):
                (ws_dir / _STDIN_FILENAME).write_text(str(vector["stdin"]), encoding="utf-8")
                stdin_path = f"/workspace/{_STDIN_FILENAME}"
            argv = [str(a) for a in (vector.get("argv") or [])]
            command = cli_command(base_cmd, argv, stdin_file=stdin_path)
            image = str(runtime["base_image"])
            timeout, memory = _CLI_TIMEOUT_SECONDS, _CLI_MEMORY_MB

        return await runner(
            docker_bin=docker_bin,
            workspace_dir=tmpdir,
            base_image=image,
            command=command,
            timeout_seconds=timeout,
            memory_mb=memory,
        )


async def run_port_dual_equivalence(
    *,
    mission_id: str,
    source_language: str,
    source_filename: str,
    source_code: str,
    target_language: str,
    target_filename: str,
    target_code: str,
    vectors: list[dict[str, Any]],
    docker_bin: str = "docker",
    source_siblings: dict[str, str] | None = None,
    target_siblings: dict[str, str] | None = None,
    sandbox_runner: Any = None,
) -> dict[str, Any]:
    """Compare source and ported artifacts side-by-side in the sandbox across I/O vectors."""
    from .contract_oracle import CALL_LANGUAGES
    from .rqca_agent import _LANGUAGE_RUNTIMES, _unbundle_source

    src_lang = _normalise_language(source_language)
    tgt_lang = _normalise_language(target_language)
    limited = [v for v in vectors if isinstance(v, dict)][:_MAX_VECTORS]
    base: dict[str, Any] = {
        "schema_version": BEHAVIOURAL_SCHEMA_VERSION,
        "verification_scope": "behavioural",
        "verification_basis": "port_dual_run",
        "mission_id": mission_id,
        "source_language": src_lang,
        "target_language": tgt_lang,
        "language": tgt_lang,
        "equivalence_vectors_total": len(limited),
        "equivalence_vectors_passed": 0,
        "equivalence_vectors_failed": 0,
        "equivalence_vectors_skipped": 0,
        "pass_ratio": 0.0,
        "findings": [],
        "vector_results": [],
    }

    if not limited:
        return {**base, "status": "skipped", "reason": "no I/O vectors provided for PORT dual-run"}
    src_runtime = _LANGUAGE_RUNTIMES.get(src_lang)
    tgt_runtime = _LANGUAGE_RUNTIMES.get(tgt_lang)
    if src_runtime is None or tgt_runtime is None:
        return {
            **base,
            "status": "skipped",
            "reason": f"sandbox runtime missing for {src_lang or '?'} or {tgt_lang or '?'}",
        }
    if sandbox_runner is None and not await check_docker_available(docker_bin):
        return {**base, "status": "skipped", "reason": "sandbox unavailable"}

    runner = sandbox_runner or run_in_sandbox
    src_primary, src_sibs = _unbundle_source(source_code, source_filename)
    tgt_primary, tgt_sibs = _unbundle_source(target_code, target_filename)
    if source_siblings:
        src_sibs = {**src_sibs, **source_siblings}
    if target_siblings:
        tgt_sibs = {**tgt_sibs, **target_siblings}

    passed = 0
    failed = 0
    skipped = 0
    findings: list[str] = []
    results: list[dict[str, Any]] = []

    for idx, vec in enumerate(limited):
        vec_id = str(vec.get("vector_id") or vec.get("id") or f"dual-{idx + 1}")
        kind = str(vec.get("kind") or "cli").strip().lower()
        vec_input = {
            "kind": kind,
            "argv": vec.get("argv") or [],
            "stdin": vec.get("stdin") or "",
            "fn_name": vec.get("fn_name") or vec.get("function") or "",
            "args": vec.get("args") or [],
        }

        if kind == "call" and (src_lang not in CALL_LANGUAGES or tgt_lang not in CALL_LANGUAGES):
            skipped += 1
            reason = f"{vec_id}: call vectors require CALL_LANGUAGES on both sides"
            findings.append(reason)
            results.append(
                {
                    "vector_id": vec_id,
                    "kind": kind,
                    "input": vec_input,
                    "outcome": "skipped",
                    "mismatch_reason": reason,
                }
            )
            continue

        try:
            src_res = await _execute_vector_against_artifact(
                mission_id=mission_id,
                side="src",
                language=src_lang,
                filename=source_filename,
                primary_code=src_primary,
                siblings=src_sibs,
                vector=vec,
                runtime=src_runtime,
                docker_bin=docker_bin,
                runner=runner,
            )
            tgt_res = await _execute_vector_against_artifact(
                mission_id=mission_id,
                side="tgt",
                language=tgt_lang,
                filename=target_filename,
                primary_code=tgt_primary,
                siblings=tgt_sibs,
                vector=vec,
                runtime=tgt_runtime,
                docker_bin=docker_bin,
                runner=runner,
            )
        except Exception as exc:  # noqa: BLE001 - verification never crashes a mission
            skipped += 1
            reason = f"{vec_id}: harness error ({type(exc).__name__})"
            findings.append(reason)
            results.append(
                {
                    "vector_id": vec_id,
                    "kind": kind,
                    "input": vec_input,
                    "outcome": "skipped",
                    "mismatch_reason": reason,
                }
            )
            continue

        if (
            src_res.infrastructure_error
            or tgt_res.infrastructure_error
            or src_res.timed_out
            or tgt_res.timed_out
        ):
            skipped += 1
            reason = (
                src_res.infrastructure_error
                or tgt_res.infrastructure_error
                or f"{vec_id}: timed out in sandbox"
            )
            findings.append(f"{vec_id}: {reason}")
            results.append(
                {
                    "vector_id": vec_id,
                    "kind": kind,
                    "input": vec_input,
                    "outcome": "skipped",
                    "mismatch_reason": str(reason),
                }
            )
            continue

        if kind == "call":
            src_verdict = _parse_driver_output(src_res.stdout)
            tgt_verdict = _parse_driver_output(tgt_res.stdout)
            src_val = src_verdict.get("result")
            tgt_val = tgt_verdict.get("result")
            matched = (
                src_verdict.get("status") == "ok"
                and tgt_verdict.get("status") == "ok"
                and src_val == tgt_val
            )
            src_out_str = json.dumps(src_verdict)
            tgt_out_str = json.dumps(tgt_verdict)
            mismatch = (
                ""
                if matched
                else f"source={src_out_str[:160]} target={tgt_out_str[:160]}"
            )
        else:
            src_out_str = str(src_res.stdout or "")
            tgt_out_str = str(tgt_res.stdout or "")
            matched = (
                int(src_res.exit_code) == int(tgt_res.exit_code)
                and src_out_str.rstrip() == tgt_out_str.rstrip()
            )
            reasons: list[str] = []
            if int(src_res.exit_code) != int(tgt_res.exit_code):
                reasons.append(f"exit_code {src_res.exit_code} != {tgt_res.exit_code}")
            if src_out_str.rstrip() != tgt_out_str.rstrip():
                reasons.append(
                    f"stdout source={src_out_str[:120]!r} != target={tgt_out_str[:120]!r}"
                )
            mismatch = "; ".join(reasons)

        if matched:
            passed += 1
            outcome = "passed"
        else:
            failed += 1
            outcome = "failed"
            findings.append(f"{vec_id}: {mismatch}")

        results.append(
            {
                "vector_id": vec_id,
                "kind": kind,
                "input": vec_input,
                "outcome": outcome,
                "source_exit_code": int(src_res.exit_code),
                "target_exit_code": int(tgt_res.exit_code),
                "source_output": src_out_str[:400],
                "target_output": tgt_out_str[:400],
                "mismatch_reason": mismatch,
            }
        )

    executed = passed + failed
    pass_ratio = round(passed / executed, 4) if executed > 0 else 0.0
    status = "failed" if failed else ("passed" if passed else "skipped")
    return {
        **base,
        "status": status,
        "equivalence_vectors_passed": passed,
        "equivalence_vectors_failed": failed,
        "equivalence_vectors_skipped": skipped,
        "pass_ratio": pass_ratio,
        "findings": findings,
        "vector_results": results,
        "reason": "" if status != "skipped" else "all PORT dual-run vectors were skipped",
    }
