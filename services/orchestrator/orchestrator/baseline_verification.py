"""Behaviour baseline capture, characterisation tests, and enforced preservation gate (Phase 6)."""

from __future__ import annotations

import ast
import json
import logging
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .dependency_provisioner import offline_sandbox_env
from .rqca_agent import _LANGUAGE_RUNTIMES, _VENDORED_TEST_RUNTIMES
from .sandbox_exec import SandboxResult, run_in_sandbox, workspace_root
from .workspace import WORKSPACE_INTERNAL_DIR, MissionWorkspace, _run_git
from .workspace_indexer import discover_workspace_tests, index_workspace, load_workspace_index

LOGGER = logging.getLogger(__name__)

BASELINE_SCHEMA_VERSION = "baseline.v1"
PRESERVATION_SCHEMA_VERSION = "preservation_gate.v1"
BASELINE_TESTS_BRANCH = "thefactory/baseline-tests"
BASELINE_ARTIFACT_FILENAME = "baseline.json"
DEFAULT_CHAR_PYTEST_PATH = "tests/test_characterisation_baseline.py"

_PYTEST_CASE_RE = re.compile(
    r"^([^\s:]+\.py::[^\s]+)\s+(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b",
    re.MULTILINE,
)
_GO_CASE_RE = re.compile(r"^---\s+(PASS|FAIL|SKIP):\s+([^\s(]+)", re.MULTILINE)
_TAP_CASE_RE = re.compile(r"^(not ok|ok)\s+\d+\s*(?:-\s*)?(.+?)\s*$", re.MULTILINE)
_NODE_CHECK_RE = re.compile(r"^\s*([✔✖]|✓|×|x)\s+(.+?)\s*(?:\([\d.]+m?s\))?\s*$", re.MULTILINE)
_JUNIT_SUMMARY_RE = re.compile(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)")
_PHPUNIT_FAIL_RE = re.compile(r"^\d+\)\s+([A-Za-z0-9_:\\]+)", re.MULTILINE)


def _baseline_file_path(ws: MissionWorkspace) -> Path:
    return Path(ws.workspace_dir) / WORKSPACE_INTERNAL_DIR / BASELINE_ARTIFACT_FILENAME


def load_workspace_baseline(ws: MissionWorkspace) -> dict[str, Any] | None:
    """Load persisted baseline snapshot from ``.thefactory/baseline.json`` if present."""
    path = _baseline_file_path(ws)
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else None
    except Exception:
        return None


def save_workspace_baseline(ws: MissionWorkspace, baseline: dict[str, Any]) -> Path:
    """Persist baseline snapshot inside ``.thefactory/baseline.json`` (excluded from git diffs)."""
    internal_dir = Path(ws.workspace_dir) / WORKSPACE_INTERNAL_DIR
    internal_dir.mkdir(parents=True, exist_ok=True)
    ws._write_git_exclude(ws.workspace_dir)
    path = _baseline_file_path(ws)
    path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _resolve_test_sandbox_image(language: str, command: str) -> str:
    lang = str(language or "").strip().lower()
    cmd_low = str(command or "").strip().lower()
    if "pytest" in cmd_low or lang == "python":
        if "pytest" in cmd_low and "python" in _VENDORED_TEST_RUNTIMES:
            return str(_VENDORED_TEST_RUNTIMES["python"]["image"])
        return str(_LANGUAGE_RUNTIMES.get("python", {}).get("base_image") or "python:3.11-slim")
    if "phpunit" in cmd_low or lang == "php":
        if "phpunit" in cmd_low and "php" in _VENDORED_TEST_RUNTIMES:
            return str(_VENDORED_TEST_RUNTIMES["php"]["image"])
        return str(_LANGUAGE_RUNTIMES.get("php", {}).get("base_image") or "php:8.3-cli")
    if "mvn" in cmd_low or lang == "java":
        if "mvn" in cmd_low and "java" in _VENDORED_TEST_RUNTIMES:
            return str(_VENDORED_TEST_RUNTIMES["java"]["image"])
        return str(_LANGUAGE_RUNTIMES.get("java", {}).get("base_image") or "eclipse-temurin:21-jdk")
    if re.search(r"\bdotnet\b", cmd_low) or lang in {"csharp", "c#"}:
        return str(_VENDORED_TEST_RUNTIMES["csharp"]["image"])
    if re.search(r"\bcargo\b", cmd_low) or lang == "rust":
        return str(_LANGUAGE_RUNTIMES["rust"]["base_image"])
    if re.search(r"\bgo\s+test\b", cmd_low) or lang == "go":
        return str(_LANGUAGE_RUNTIMES["go"]["base_image"])
    if re.search(r"\b(?:npm\s+test|node)\b", cmd_low) or lang in {"javascript", "typescript"}:
        return str(_LANGUAGE_RUNTIMES.get(lang, _LANGUAGE_RUNTIMES["javascript"])["base_image"])
    if re.search(r"\bmake\b", cmd_low) or lang in {"c", "cpp", "c++"}:
        return str(_LANGUAGE_RUNTIMES.get("c", {}).get("base_image") or "gcc:13-bookworm")
    return str(_LANGUAGE_RUNTIMES.get(lang, {}).get("base_image") or "python:3.11-slim")


def _wrap_workspace_test_command(
    test_command: str,
    *,
    language: str,
    characterisation_files: list[str] | None = None,
) -> str:
    cmd = str(test_command or "").strip()
    extra_cmd = ""
    if characterisation_files and language == "python":
        quoted = " ".join(f"/workspace/{Path(p).as_posix()}" for p in characterisation_files)
        extra_cmd = f" && python -m pytest -q -o cache_dir=/tmp/.pytest_cache {quoted}"
    elif characterisation_files and language in {"javascript", "typescript"}:
        quoted = " ".join(f"/workspace/{Path(p).as_posix()}" for p in characterisation_files)
        extra_cmd = f" && node --test {quoted}"

    if "pytest" in cmd and "cache_dir=" not in cmd:
        cmd = f"{cmd} -o cache_dir=/tmp/.pytest_cache"
    return (
        "export HOME=/tmp; export PYTHONDONTWRITEBYTECODE=1; "
        "cd /workspace && "
        f"{cmd}{extra_cmd}"
    )


def _export_workspace_snapshot(
    ws: MissionWorkspace,
    target_dir: Path,
    *,
    revision: str | None = None,
) -> None:
    """Copy a clean workspace snapshot (without ``.git``/``.thefactory``) for sandbox mounting."""
    if revision:
        # Read each tracked file from the target git revision (e.g. "baseline").
        proc = _run_git(ws.workspace_dir, ["ls-tree", "-r", "--name-only", revision], check=False)
        rel_paths = [p.strip() for p in str(proc.stdout or "").splitlines() if p.strip()]
        if rel_paths:
            for rel in rel_paths:
                if rel.startswith(f"{WORKSPACE_INTERNAL_DIR}/") or rel == WORKSPACE_INTERNAL_DIR:
                    continue
                try:
                    raw_proc = _run_git(
                        ws.workspace_dir,
                        ["show", f"{revision}:{rel}"],
                        check=False,
                        text=False,
                    )
                    if raw_proc.returncode == 0:
                        dest = target_dir / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(bytes(raw_proc.stdout))
                except Exception:
                    continue
            return

    for entry in ws.list_files():
        rel = str(entry.get("path") or "")
        if not rel or rel.startswith(f"{WORKSPACE_INTERNAL_DIR}/"):
            continue
        src = Path(ws.workspace_dir) / rel
        if src.is_file():
            dest = target_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def parse_junit_xml(junit_xml: str) -> dict[str, list[str]]:
    """Parse JUnit XML test report text into ``passed``, ``failed``, ``skipped`` test IDs."""
    passed: list[str] = []
    failed: list[str] = []
    skipped: list[str] = []
    if not junit_xml or "<testsuite" not in junit_xml:
        return {"passed": passed, "failed": failed, "skipped": skipped}
    try:
        root = ET.fromstring(junit_xml)  # noqa: S314 - controlled sandbox output
    except ET.ParseError:
        return {"passed": passed, "failed": failed, "skipped": skipped}
    for case in root.iter("testcase"):
        cls = str(case.attrib.get("classname") or "").strip()
        name = str(case.attrib.get("name") or "").strip()
        test_id = f"{cls}::{name}" if cls and name else (name or cls)
        if not test_id:
            continue
        if case.find("failure") is not None or case.find("error") is not None:
            failed.append(test_id)
        elif case.find("skipped") is not None:
            skipped.append(test_id)
        else:
            passed.append(test_id)
    return {"passed": passed, "failed": failed, "skipped": skipped}


def parse_test_results(
    *,
    command: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    junit_xml: str = "",
) -> dict[str, list[str]]:
    """Parse per-test results across pytest, Go, TAP/Node, JUnit XML, and generic runners."""
    if junit_xml.strip():
        junit_parsed = parse_junit_xml(junit_xml)
        if any(junit_parsed.values()):
            return junit_parsed

    combined = f"{stdout or ''}\n{stderr or ''}"
    passed: list[str] = []
    failed: list[str] = []
    skipped: list[str] = []

    for match in _PYTEST_CASE_RE.finditer(combined):
        tid, outcome = match.group(1), match.group(2)
        if outcome in {"PASSED", "XFAIL"} and tid not in passed:
            passed.append(tid)
        elif outcome in {"FAILED", "ERROR", "XPASS"} and tid not in failed:
            failed.append(tid)
        elif outcome == "SKIPPED" and tid not in skipped:
            skipped.append(tid)

    if not passed and not failed:
        for match in _GO_CASE_RE.finditer(combined):
            outcome, tid = match.group(1), match.group(2)
            if outcome == "PASS" and tid not in passed:
                passed.append(tid)
            elif outcome == "FAIL" and tid not in failed:
                failed.append(tid)
            elif outcome == "SKIP" and tid not in skipped:
                skipped.append(tid)

    if not passed and not failed:
        for match in _TAP_CASE_RE.finditer(combined):
            status, raw_name = match.group(1), match.group(2).strip()
            if "# SKIP" in raw_name.upper():
                if raw_name not in skipped:
                    skipped.append(raw_name)
            elif status == "ok" and raw_name not in passed:
                passed.append(raw_name)
            elif status == "not ok" and raw_name not in failed:
                failed.append(raw_name)

    if not passed and not failed:
        for match in _NODE_CHECK_RE.finditer(combined):
            mark, name = match.group(1), match.group(2).strip()
            if mark in {"✔", "✓"} and name not in passed:
                passed.append(name)
            elif mark in {"✖", "×", "x"} and name not in failed:
                failed.append(name)

    if not passed and not failed:
        for match in _PHPUNIT_FAIL_RE.finditer(combined):
            tid = match.group(1).strip()
            if tid and tid not in failed:
                failed.append(tid)

    # Pytest FAILED summary lines ("FAILED tests/test_a.py::test_x - AssertionError")
    for line in combined.splitlines():
        clean = line.strip()
        if clean.startswith("FAILED "):
            tid = clean[7:].split(" - ", 1)[0].strip()
            if tid and tid not in failed:
                failed.append(tid)
                if tid in passed:
                    passed.remove(tid)

    if not passed and not failed:
        suite_id = f"suite:{command.strip()}" if command.strip() else "suite:default"
        junit_match = _JUNIT_SUMMARY_RE.search(combined)
        if junit_match and (int(junit_match.group(2)) > 0 or int(junit_match.group(3)) > 0):
            failed.append(suite_id)
        elif exit_code == 0:
            passed.append(suite_id)
        else:
            failed.append(suite_id)

    # Non-zero exit with zero explicit failures implies an untracked collection/build error.
    if exit_code != 0 and not failed:
        suite_id = f"suite:{command.strip()}" if command.strip() else "suite:default"
        failed.append(suite_id)

    return {"passed": passed, "failed": failed, "skipped": skipped}


def parse_behaviour_change_allowed(
    baseline_policy: str | None,
    explicit_allowed: Any = None,
) -> list[str]:
    """Extract allowed changing test IDs from ``baseline_policy`` and explicit list fields."""
    allowed: list[str] = []
    if isinstance(explicit_allowed, list):
        for item in explicit_allowed:
            text = str(item or "").strip()
            if text and text not in allowed:
                allowed.append(text)
    policy = str(baseline_policy or "").strip()
    if policy.lower().startswith("behaviour_change_allowed:"):
        raw = policy.split(":", 1)[1]
        for item in raw.split(","):
            text = item.strip()
            if text and text not in allowed:
                allowed.append(text)
    return allowed


def _deps_mount_and_env(
    *,
    language: str,
    deps_dir: str | Path | None,
) -> tuple[Path | None, dict[str, str]]:
    if not deps_dir:
        return None, {}
    resolved = Path(deps_dir)
    if not resolved.exists():
        return None, {}
    return resolved, offline_sandbox_env(language, deps_mount="/deps")


async def capture_workspace_baseline(
    ws: MissionWorkspace,
    *,
    test_command: str | None = None,
    language: str | None = None,
    aim: dict[str, Any] | None = None,
    deps_dir: str | Path | None = None,
    revision: str | None = "baseline",
    docker_bin: str = "docker",
    timeout_seconds: int = 120,
    sandbox_runner: Any = None,
) -> dict[str, Any]:
    """Run the imported project's test command on baseline commit and record per-test verdicts."""
    runner = sandbox_runner or run_in_sandbox
    td: dict[str, Any] = {}
    if isinstance(aim, dict) and isinstance(aim.get("test_discovery"), dict):
        td = dict(aim["test_discovery"])
    else:
        td = discover_workspace_tests(ws)

    resolved_cmd = str(test_command or td.get("test_command") or "").strip()
    resolved_lang = str(language or td.get("primary_language") or "python").strip().lower()
    base_commit = ws.base_commit or ws.current_head()

    if not resolved_cmd:
        baseline = {
            "schema_version": BASELINE_SCHEMA_VERSION,
            "workspace_id": ws.workspace_id,
            "commit": base_commit,
            "command": "",
            "language": resolved_lang,
            "status": "no_tests",
            "exit_code": None,
            "passed": [],
            "failed": [],
            "skipped": [],
            "pre_existing_failures": [],
            "characterisation_tests": [],
            "characterisation_files": [],
            "duration_ms": 0.0,
            "stdout_preview": "",
            "stderr_preview": "",
            "reason": "no executable test command discovered in workspace",
            "captured_at": datetime.now(UTC).isoformat(),
        }
        save_workspace_baseline(ws, baseline)
        return baseline

    wrapped_cmd = _wrap_workspace_test_command(resolved_cmd, language=resolved_lang)
    image = _resolve_test_sandbox_image(resolved_lang, resolved_cmd)
    mounted_deps, env_vars = _deps_mount_and_env(language=resolved_lang, deps_dir=deps_dir)

    with tempfile.TemporaryDirectory(
        prefix=f"hgr-base-{ws.workspace_id[:8]}-", dir=workspace_root()
    ) as tmpdir:
        _export_workspace_snapshot(ws, Path(tmpdir), revision=revision)
        result: SandboxResult = await runner(
            docker_bin=docker_bin,
            workspace_dir=tmpdir,
            base_image=image,
            command=wrapped_cmd,
            timeout_seconds=timeout_seconds,
            memory_mb=512,
            deps_dir=mounted_deps,
            env_vars=env_vars,
        )

    if result.infrastructure_error or result.timed_out:
        reason = (
            str(result.infrastructure_error)
            if result.infrastructure_error
            else f"baseline execution timed out after {result.timeout_seconds}s"
        )
        baseline = {
            "schema_version": BASELINE_SCHEMA_VERSION,
            "workspace_id": ws.workspace_id,
            "commit": base_commit,
            "command": resolved_cmd,
            "language": resolved_lang,
            "status": "unverifiable",
            "exit_code": result.exit_code,
            "passed": [],
            "failed": [],
            "skipped": [],
            "pre_existing_failures": [],
            "characterisation_tests": [],
            "characterisation_files": [],
            "duration_ms": result.duration_ms,
            "stdout_preview": result.stdout[:4000],
            "stderr_preview": result.stderr[:4000],
            "reason": reason,
            "captured_at": datetime.now(UTC).isoformat(),
        }
        save_workspace_baseline(ws, baseline)
        return baseline

    parsed = parse_test_results(
        command=resolved_cmd,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
    )
    baseline = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "workspace_id": ws.workspace_id,
        "commit": base_commit,
        "command": resolved_cmd,
        "language": resolved_lang,
        "status": "captured",
        "exit_code": result.exit_code,
        "passed": parsed["passed"],
        "failed": parsed["failed"],
        "skipped": parsed["skipped"],
        "pre_existing_failures": list(parsed["failed"]),
        "characterisation_tests": [],
        "characterisation_files": [],
        "duration_ms": result.duration_ms,
        "stdout_preview": result.stdout[:4000],
        "stderr_preview": result.stderr[:4000],
        "reason": "",
        "captured_at": datetime.now(UTC).isoformat(),
    }
    save_workspace_baseline(ws, baseline)
    return baseline


def generate_characterisation_suite_files(
    ws: MissionWorkspace,
    *,
    target_files: list[str] | None = None,
    language: str = "python",
) -> dict[str, str]:
    """Synthesize deterministic baseline-observing characterisation tests for untested modules."""
    lang = str(language or "python").strip().lower()
    files = ws.list_files()
    selected = (
        [f["path"] for f in files if f["path"] in set(target_files)]
        if target_files
        else [f["path"] for f in files if not Path(f["path"]).name.startswith("test_")]
    )

    if lang == "python":
        py_targets = [p for p in selected if p.endswith(".py")][:6]
        if not py_targets:
            return {}
        lines = [
            '"""Auto-generated characterisation tests capturing current baseline behaviour."""',
            "import importlib.util",
            "from pathlib import Path",
            "",
            "ROOT = Path(__file__).resolve().parents[1]",
            "",
        ]
        for rel in py_targets:
            safe_slug = re.sub(r"[^a-zA-Z0-9_]", "_", rel).strip("_")
            try:
                src = ws.read_file(rel, revision="baseline")
            except Exception:
                src = ws.read_file(rel)
            try:
                tree = ast.parse(src)
                fn_names = [
                    node.name
                    for node in tree.body
                    if isinstance(node, ast.FunctionDef)
                    and not node.name.startswith("_")
                    and not node.args.args
                ][:3]
            except SyntaxError:
                fn_names = []
            lines.extend(
                [
                    f"def test_characterise_{safe_slug}_imports() -> None:",
                    f'    target = ROOT / "{rel}"',
                    "    assert target.is_file()",
                    f'    spec = importlib.util.spec_from_file_location("{safe_slug}", target)',
                    "    assert spec is not None and spec.loader is not None",
                    "    mod = importlib.util.module_from_spec(spec)",
                    "    spec.loader.exec_module(mod)",
                ]
            )
            for fn in fn_names:
                lines.append(f"    assert callable(getattr(mod, {fn!r}, None))")
            lines.append("")
        return {DEFAULT_CHAR_PYTEST_PATH: "\n".join(lines).rstrip() + "\n"}

    if lang in {"javascript", "typescript"}:
        js_targets = [p for p in selected if p.endswith((".js", ".cjs", ".mjs"))][:6]
        if not js_targets:
            return {}
        lines = [
            "import test from 'node:test';",
            "import assert from 'node:assert/strict';",
            "import fs from 'node:fs';",
            "",
        ]
        for rel in js_targets:
            safe_slug = re.sub(r"[^a-zA-Z0-9_]", "_", rel).strip("_")
            lines.extend(
                [
                    f"test('characterise_{safe_slug}_exists', () => {{",
                    f"  assert.equal(fs.existsSync('{rel}'), true);",
                    "});",
                    "",
                ]
            )
        return {"tests/characterisation_baseline.test.mjs": "\n".join(lines)}

    return {}


async def generate_characterisation_tests(
    ws: MissionWorkspace,
    *,
    baseline: dict[str, Any],
    language: str | None = None,
    candidate_files: dict[str, str] | None = None,
    target_files: list[str] | None = None,
    deps_dir: str | Path | None = None,
    docker_bin: str = "docker",
    sandbox_runner: Any = None,
) -> dict[str, Any]:
    """Generate, run against baseline, keep ONLY passing characterisation tests, and commit."""
    runner = sandbox_runner or run_in_sandbox
    idx = load_workspace_index(ws) or index_workspace(ws)
    inferred_lang = str(
        language
        or baseline.get("language")
        or (idx.get("test_discovery") or {}).get("primary_language")
        or "python"
    ).strip().lower()

    generated = dict(
        candidate_files
        if isinstance(candidate_files, dict) and candidate_files
        else generate_characterisation_suite_files(ws, target_files=target_files, language=inferred_lang)
    )
    if not generated:
        return baseline

    char_paths = sorted(generated.keys())
    if inferred_lang == "python":
        cmd = " ".join(
            ["python -m pytest -v -o cache_dir=/tmp/.pytest_cache", *[f"/workspace/{p}" for p in char_paths]]
        )
    elif inferred_lang in {"javascript", "typescript"}:
        cmd = " ".join(["node --test", *[f"/workspace/{p}" for p in char_paths]])
    else:
        cmd = str(baseline.get("command") or "").strip()

    if not cmd:
        return baseline

    image = _resolve_test_sandbox_image(inferred_lang, cmd)
    mounted_deps, env_vars = _deps_mount_and_env(language=inferred_lang, deps_dir=deps_dir)

    with tempfile.TemporaryDirectory(
        prefix=f"hgr-char-{ws.workspace_id[:8]}-", dir=workspace_root()
    ) as tmpdir:
        tmp = Path(tmpdir)
        _export_workspace_snapshot(ws, tmp, revision="baseline")
        for rel, body in generated.items():
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(str(body), encoding="utf-8")
        result: SandboxResult = await runner(
            docker_bin=docker_bin,
            workspace_dir=tmpdir,
            base_image=image,
            command=f"export HOME=/tmp; export PYTHONDONTWRITEBYTECODE=1; cd /workspace && {cmd}",
            timeout_seconds=120,
            memory_mb=512,
            deps_dir=mounted_deps,
            env_vars=env_vars,
        )

    if result.infrastructure_error or result.timed_out:
        updated = {**baseline, "characterisation_status": "unverifiable"}
        save_workspace_baseline(ws, updated)
        return updated

    parsed = parse_test_results(
        command=cmd,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
    )
    passing_ids = list(parsed["passed"])
    failing_ids = set(parsed["failed"])

    # Keep only characterisation assertions that passed on baseline.
    kept_files: dict[str, str] = {}
    for rel, body in generated.items():
        if failing_ids:
            # Prune Python def test_* blocks whose full node ID failed on baseline.
            failing_short = {tid.split("::")[-1] for tid in failing_ids}
            pruned_lines: list[str] = []
            skipping = False
            for line in str(body).splitlines():
                def_match = re.match(r"^def\s+(test_[A-Za-z0-9_]+)\s*\(", line)
                if def_match:
                    skipping = def_match.group(1) in failing_short
                if not skipping:
                    pruned_lines.append(line)
            cleaned_body = "\n".join(pruned_lines).strip()
            if "def test_" in cleaned_body or "test(" in cleaned_body:
                kept_files[rel] = cleaned_body + "\n"
        else:
            kept_files[rel] = str(body)

    if not passing_ids or not kept_files:
        updated = {
            **baseline,
            "characterisation_status": "no_passing_tests",
            "characterisation_discarded": sorted(failing_ids),
        }
        save_workspace_baseline(ws, updated)
        return updated

    commit_sha = ws.write_files(
        kept_files,
        message="thefactory/baseline-tests: commit baseline characterisation suite",
    )
    # Record a branch ref at the characterisation commit for downstream provenance.
    _run_git(ws.workspace_dir, ["branch", "-f", BASELINE_TESTS_BRANCH, commit_sha], check=False)

    combined_passed = list(dict.fromkeys([*baseline.get("passed", []), *passing_ids]))
    updated = {
        **baseline,
        "passed": combined_passed,
        "characterisation_status": "committed",
        "characterisation_tests": passing_ids,
        "characterisation_discarded": sorted(failing_ids),
        "characterisation_files": sorted(kept_files.keys()),
        "baseline_tests_branch": BASELINE_TESTS_BRANCH,
        "baseline_tests_commit": commit_sha,
    }
    save_workspace_baseline(ws, updated)
    return updated


async def evaluate_preservation_gate(
    ws: MissionWorkspace,
    *,
    baseline: dict[str, Any],
    baseline_policy: str = "must_pass_existing_tests",
    behaviour_change_allowed: list[str] | None = None,
    deps_dir: str | Path | None = None,
    docker_bin: str = "docker",
    timeout_seconds: int = 120,
    enforcement_enabled: bool = False,
    sandbox_runner: Any = None,
) -> dict[str, Any]:
    """Re-run baseline & characterisation tests after code edits and judge preservation."""
    runner = sandbox_runner or run_in_sandbox
    allowed_changes = parse_behaviour_change_allowed(baseline_policy, behaviour_change_allowed)
    allowed_set = set(allowed_changes)
    baseline_status = str(baseline.get("status") or "")
    test_command = str(baseline.get("command") or "").strip()
    language = str(baseline.get("language") or "python").strip().lower()
    char_files = [
        str(p)
        for p in (baseline.get("characterisation_files") or [])
        if str(p).strip()
    ]
    baseline_passed = [str(t) for t in (baseline.get("passed") or []) if str(t).strip()]
    pre_existing = [str(t) for t in (baseline.get("pre_existing_failures") or []) if str(t).strip()]

    if baseline_status == "unverifiable":
        return {
            "schema_version": PRESERVATION_SCHEMA_VERSION,
            "verdict": "UNVERIFIABLE",
            "blocking": bool(enforcement_enabled),
            "regressed_tests": [],
            "pre_existing_failures": pre_existing,
            "allowed_changes": allowed_changes,
            "passed": [],
            "failed": [],
            "skipped": [],
            "exit_code": baseline.get("exit_code"),
            "stdout_preview": "",
            "stderr_preview": "",
            "reason": str(baseline.get("reason") or "baseline suite could not be verified"),
            "evaluated_at": datetime.now(UTC).isoformat(),
        }

    if not test_command and not char_files:
        return {
            "schema_version": PRESERVATION_SCHEMA_VERSION,
            "verdict": "UNVERIFIABLE",
            "blocking": bool(enforcement_enabled),
            "regressed_tests": [],
            "pre_existing_failures": pre_existing,
            "allowed_changes": allowed_changes,
            "passed": [],
            "failed": [],
            "skipped": [],
            "exit_code": None,
            "stdout_preview": "",
            "stderr_preview": "",
            "reason": "no baseline test command or characterisation suite available",
            "evaluated_at": datetime.now(UTC).isoformat(),
        }

    effective_cmd = test_command or f"python -m pytest -v /workspace/{' /workspace/'.join(char_files)}"
    wrapped_cmd = _wrap_workspace_test_command(
        effective_cmd,
        language=language,
        characterisation_files=char_files if test_command else None,
    )
    image = _resolve_test_sandbox_image(language, effective_cmd)
    mounted_deps, env_vars = _deps_mount_and_env(language=language, deps_dir=deps_dir)

    with tempfile.TemporaryDirectory(
        prefix=f"hgr-pres-{ws.workspace_id[:8]}-", dir=workspace_root()
    ) as tmpdir:
        _export_workspace_snapshot(ws, Path(tmpdir), revision=None)
        result: SandboxResult = await runner(
            docker_bin=docker_bin,
            workspace_dir=tmpdir,
            base_image=image,
            command=wrapped_cmd,
            timeout_seconds=timeout_seconds,
            memory_mb=512,
            deps_dir=mounted_deps,
            env_vars=env_vars,
        )

    if result.infrastructure_error or result.timed_out:
        reason = (
            str(result.infrastructure_error)
            if result.infrastructure_error
            else f"preservation test run timed out after {result.timeout_seconds}s"
        )
        return {
            "schema_version": PRESERVATION_SCHEMA_VERSION,
            "verdict": "UNVERIFIABLE",
            "blocking": bool(enforcement_enabled),
            "regressed_tests": [],
            "pre_existing_failures": pre_existing,
            "allowed_changes": allowed_changes,
            "passed": [],
            "failed": [],
            "skipped": [],
            "exit_code": result.exit_code,
            "stdout_preview": result.stdout[:4000],
            "stderr_preview": result.stderr[:4000],
            "reason": reason,
            "evaluated_at": datetime.now(UTC).isoformat(),
        }

    parsed = parse_test_results(
        command=effective_cmd,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
    )
    now_passed = set(parsed["passed"])
    now_failed = set(parsed["failed"])

    regressed: list[str] = []
    for test_id in baseline_passed:
        if test_id in allowed_set:
            continue
        short_id = test_id.split("::")[-1]
        if short_id in allowed_set:
            continue
        if test_id in now_failed or short_id in now_failed:
            regressed.append(test_id)
        elif result.exit_code != 0 and test_id not in now_passed:
            regressed.append(test_id)

    # Also treat brand-new failures unrelated to pre_existing baseline failures when baseline had tests.
    pre_existing_set = set(pre_existing)
    if not regressed and result.exit_code != 0:
        for fid in parsed["failed"]:
            short_fid = fid.split("::")[-1]
            if fid not in pre_existing_set and fid not in allowed_set and short_fid not in allowed_set:
                regressed.append(fid)

    verdict = "REGRESSED" if regressed else "PRESERVED"
    blocking = bool(enforcement_enabled and verdict == "REGRESSED")
    return {
        "schema_version": PRESERVATION_SCHEMA_VERSION,
        "verdict": verdict,
        "blocking": blocking,
        "regressed_tests": regressed,
        "pre_existing_failures": pre_existing,
        "allowed_changes": allowed_changes,
        "passed": parsed["passed"],
        "failed": parsed["failed"],
        "skipped": parsed["skipped"],
        "exit_code": result.exit_code,
        "stdout_preview": result.stdout[:4000],
        "stderr_preview": result.stderr[:4000],
        "reason": (
            f"{len(regressed)} baseline test(s) regressed: {', '.join(regressed[:5])}"
            if regressed
            else "all baseline passing tests preserved"
        ),
        "evaluated_at": datetime.now(UTC).isoformat(),
    }
