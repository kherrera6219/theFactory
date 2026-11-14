#!/usr/bin/env python3
"""Brownfield benchmark corpus validator and harness runner.

Discovers MIT-licensed brownfield benchmark projects under
``tests/benchmark/brownfield``, validates manifests and expected files,
supports ``--mode offline|live|auto``, enforces strict honesty scoring
(DRY_RUN, ADVISORY, started_only, and fallback outcomes NEVER pass), and
writes JSON + Markdown evidence scorecards.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_DIR = ROOT / "tests" / "benchmark" / "brownfield"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "evidence"

DISALLOWED_SOURCES = frozenset({"fallback", "advisory", "dry_run", "started_only", "offline"})
DISALLOWED_STATUSES = frozenset(
    {
        "DRY_RUN",
        "ADVISORY",
        "STARTED_ONLY",
        "SKIPPED",
        "ERROR",
        "FAIL",
        "FAILED",
        "BLOCKED",
        "OFFLINE_BASELINE",
    }
)
PASSING_MISSION_STATUSES = frozenset({"PASS", "VERIFIED", "COMPLETE"})
REQUIRED_MANIFEST_KEYS = (
    "id",
    "title",
    "license",
    "language",
    "target_language",
    "mission_type",
    "intent",
    "entrypoint",
    "expected_files",
)


@dataclass(frozen=True)
class BenchmarkProject:
    """Validated representation of a single brownfield benchmark fixture."""

    project_id: str
    path: Path
    manifest: dict[str, Any]
    missing_files: tuple[str, ...]
    validation_errors: tuple[str, ...]

    @property
    def corpus_valid(self) -> bool:
        return not self.missing_files and not self.validation_errors


def _validate_manifest(project_dir: Path, raw: Any) -> tuple[dict[str, Any], list[str], list[str]]:
    errors: list[str] = []
    missing_files: list[str] = []
    if not isinstance(raw, dict):
        return {}, [], ["benchmark.yaml must deserialize to a mapping"]

    manifest = dict(raw)
    for key in REQUIRED_MANIFEST_KEYS:
        val = manifest.get(key)
        if val is None or (isinstance(val, str) and not val.strip()):
            errors.append(f"missing required manifest key: {key}")

    if str(manifest.get("id") or "") != project_dir.name:
        errors.append(f"manifest id '{manifest.get('id')}' != dir '{project_dir.name}'")
    if str(manifest.get("license") or "").upper() != "MIT":
        errors.append("license must be MIT")

    license_path = project_dir / "LICENSE"
    if not license_path.is_file() or "MIT License" not in license_path.read_text(encoding="utf-8"):
        errors.append("MIT LICENSE file missing or invalid")

    expected = manifest.get("expected_files")
    if not isinstance(expected, list) or not expected:
        errors.append("expected_files must be a non-empty list")
    else:
        for rel in expected:
            rel_str = str(rel)
            if not (project_dir / rel_str).is_file():
                missing_files.append(rel_str)

    return manifest, missing_files, errors


def discover_benchmark_projects(
    corpus_dir: Path = DEFAULT_CORPUS_DIR,
) -> list[BenchmarkProject]:
    """Discover and validate all brownfield benchmark fixtures in corpus_dir."""
    if not corpus_dir.exists():
        return []

    projects: list[BenchmarkProject] = []
    for child in sorted(corpus_dir.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        manifest_path = child / "benchmark.yaml"
        if not manifest_path.is_file():
            projects.append(
                BenchmarkProject(
                    project_id=child.name,
                    path=child,
                    manifest={},
                    missing_files=("benchmark.yaml",),
                    validation_errors=("benchmark.yaml not found",),
                )
            )
            continue
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest, missing_files, errors = _validate_manifest(child, raw)
        projects.append(
            BenchmarkProject(
                project_id=child.name,
                path=child,
                manifest=manifest,
                missing_files=tuple(missing_files),
                validation_errors=tuple(errors),
            )
        )
    return projects


def compute_honest_pass(outcome: dict[str, Any]) -> bool:
    """Return True iff outcome is a verified, non-degraded mission execution pass.

    DRY_RUN, ADVISORY, started_only, fallback, degraded, and skipped runs
    strictly evaluate to False.
    """
    if not outcome.get("corpus_valid", False):
        return False
    if any(
        bool(outcome.get(flag))
        for flag in ("fallback_used", "degraded", "started_only", "skipped", "dry_run")
    ):
        return False

    source = str(outcome.get("source") or "").strip().lower()
    if source in DISALLOWED_SOURCES:
        return False

    for status_key in ("status", "runtime_qc_status", "build_status"):
        val = str(outcome.get(status_key) or "").strip().upper()
        if val in DISALLOWED_STATUSES:
            return False

    status = str(outcome.get("status") or "").strip().upper()
    if status not in PASSING_MISSION_STATUSES:
        return False

    return bool(outcome.get("runtime_qc_passed", False))


def _load_project_source_bundle(project: BenchmarkProject) -> dict[str, str]:
    files: dict[str, str] = {}
    for rel in project.manifest.get("expected_files") or []:
        rel_str = str(rel)
        if rel_str in {"LICENSE", "benchmark.yaml"}:
            continue
        target = project.path / rel_str
        if target.is_file():
            files[rel_str] = target.read_text(encoding="utf-8", errors="replace")
    return files


def _http_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    req = urllib_request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(body) if body else {}
    except urllib_error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {"error": body}
        except json.JSONDecodeError:
            parsed = {"error": body}
        return exc.code, parsed
    except Exception as exc:
        return 0, {"error": str(exc)}


def _live_stack_reachable(base_url: str, api_key: str) -> bool:
    headers = {"X-API-Key": api_key} if api_key else {}
    status, body = _http_json("GET", f"{base_url.rstrip('/')}/readyz", headers=headers, timeout=3.0)
    return status == 200 and bool(body.get("ready", False))


def _execute_live_project(
    project: BenchmarkProject,
    *,
    gateway_url: str,
    api_key: str,
    poll_timeout_s: float = 180.0,
) -> dict[str, Any]:
    headers = {"X-API-Key": api_key} if api_key else {}
    entrypoint = str(project.manifest.get("entrypoint") or "")
    entry_path = project.path / entrypoint
    source_code = (
        entry_path.read_text(encoding="utf-8", errors="replace") if entry_path.is_file() else ""
    )
    bundle = _load_project_source_bundle(project)
    payload = {
        "mission_intent": str(project.manifest["intent"]),
        "requested_target_language": str(project.manifest["target_language"]),
        "source_code": source_code,
        "metadata": {
            "mission_type": str(project.manifest["mission_type"]),
            "source_language": str(project.manifest["language"]),
            "benchmark_id": project.project_id,
            "source_files": bundle,
        },
    }

    code, created = _http_json(
        "POST",
        f"{gateway_url.rstrip('/')}/v1/missions",
        payload=payload,
        headers=headers,
        timeout=30.0,
    )
    if code not in {200, 201, 202} or not created.get("mission_id"):
        return {
            "id": project.project_id,
            "corpus_valid": project.corpus_valid,
            "mode": "live",
            "status": "ERROR",
            "source": "live",
            "runtime_qc_passed": False,
            "error": created.get("error") or f"create returned HTTP {code}",
        }

    mission_id = str(created["mission_id"])
    deadline = time.monotonic() + poll_timeout_s
    last_state: dict[str, Any] = created
    while time.monotonic() < deadline:
        st_code, state_body = _http_json(
            "GET",
            f"{gateway_url.rstrip('/')}/v1/missions/{mission_id}",
            headers=headers,
            timeout=15.0,
        )
        if st_code == 200 and state_body:
            last_state = state_body
            cur = str(state_body.get("current_state") or state_body.get("status") or "").upper()
            if cur in {"VERIFIED", "COMPLETE", "FAILED", "CANCELLED", "BLOCKED", "ERROR"}:
                break
        time.sleep(2.0)

    metadata = last_state.get("metadata") or {}
    generated_output = metadata.get("generated_output") or {}
    gen_source = str(generated_output.get("source") or "live").lower()
    qc = metadata.get("runtime_qc") or {}
    qc_passed = bool(qc.get("passed", False))
    cur_state = str(last_state.get("current_state") or last_state.get("status") or "ERROR").upper()

    result: dict[str, Any] = {
        "id": project.project_id,
        "mission_id": mission_id,
        "corpus_valid": project.corpus_valid,
        "mode": "live",
        "language": project.manifest.get("language"),
        "target_language": project.manifest.get("target_language"),
        "mission_type": project.manifest.get("mission_type"),
        "status": cur_state,
        "source": gen_source,
        "fallback_used": gen_source == "fallback" or bool(metadata.get("generation_degraded")),
        "degraded": bool(metadata.get("generation_degraded")),
        "runtime_qc_passed": qc_passed,
        "runtime_qc_status": str(qc.get("status") or ""),
    }
    result["honest_pass"] = compute_honest_pass(result)
    return result


def run_benchmark(
    *,
    mode: str = "auto",
    corpus_dir: Path = DEFAULT_CORPUS_DIR,
    gateway_url: str | None = None,
    api_key: str | None = None,
    live_runner: Any | None = None,
    poll_timeout_s: float = 180.0,
) -> dict[str, Any]:
    """Run offline structural checks or live brownfield missions and build scorecard."""
    if mode not in {"auto", "offline", "live"}:
        raise ValueError(f"Unsupported mode: {mode}")

    resolved_url = gateway_url or os.getenv("API_GATEWAY_URL", "http://127.0.0.1:8100")
    resolved_key = api_key if api_key is not None else os.getenv("FACTORY_API_KEY", "")

    use_live = False
    if mode == "live":
        if live_runner is None and not _live_stack_reachable(resolved_url, resolved_key):
            raise RuntimeError(f"Live mode requested but gateway not ready at {resolved_url}")
        use_live = True
    elif mode == "auto":
        use_live = live_runner is not None or _live_stack_reachable(resolved_url, resolved_key)

    projects = discover_benchmark_projects(corpus_dir)
    results: list[dict[str, Any]] = []

    for project in projects:
        if not project.corpus_valid:
            entry: dict[str, Any] = {
                "id": project.project_id,
                "corpus_valid": False,
                "missing_files": list(project.missing_files),
                "validation_errors": list(project.validation_errors),
                "mode": "live" if use_live else "offline",
                "status": "FAIL",
                "source": "offline" if not use_live else "live",
                "runtime_qc_passed": False,
                "dry_run": not use_live,
            }
            entry["honest_pass"] = compute_honest_pass(entry)
            results.append(entry)
            continue

        if use_live:
            runner = live_runner or _execute_live_project
            live_outcome = runner(
                project,
                gateway_url=resolved_url,
                api_key=resolved_key,
                poll_timeout_s=poll_timeout_s,
            )
            live_outcome.setdefault("corpus_valid", project.corpus_valid)
            live_outcome["honest_pass"] = compute_honest_pass(live_outcome)
            results.append(live_outcome)
        else:
            prov_summary: dict[str, Any] = {}
            executable_with_cache = False
            try:
                import sys as _sys  # noqa: PLC0415

                orch_root = str(ROOT / "services" / "orchestrator")
                if orch_root not in _sys.path:
                    _sys.path.insert(0, orch_root)
                from orchestrator.dependency_provisioner import (  # noqa: PLC0415
                    provision_workspace_dependencies,
                )

                prov_manifest = provision_workspace_dependencies(
                    project.path,
                    mission_id=f"benchmark-{project.project_id}",
                    workspace_id=project.project_id,
                    language=str(project.manifest.get("language") or "python"),
                    execute_fetch=False,
                )
                executable_with_cache = bool(prov_manifest.get("executable_with_cache"))
                prov_summary = {
                    "manifests": prov_manifest.get("manifests", []),
                    "package_count": len(prov_manifest.get("packages") or []),
                    "provisioned_count": len(prov_manifest.get("provisioned_packages") or []),
                    "unmet_reasons": prov_manifest.get("unmet_reasons", {}),
                    "executable_with_cache": executable_with_cache,
                }
            except Exception as exc:  # noqa: BLE001
                prov_summary = {"error": str(exc), "executable_with_cache": False}

            offline_entry: dict[str, Any] = {
                "id": project.project_id,
                "title": project.manifest.get("title"),
                "language": project.manifest.get("language"),
                "target_language": project.manifest.get("target_language"),
                "mission_type": project.manifest.get("mission_type"),
                "corpus_valid": True,
                "missing_files": [],
                "validation_errors": [],
                "mode": "offline",
                "status": "DRY_RUN",
                "source": "dry_run",
                "dry_run": True,
                "runtime_qc_passed": False,
                "executable_with_cache": executable_with_cache,
                "dependency_provisioning": prov_summary,
                "expected_initial_test_pass": bool(
                    project.manifest.get("expected_initial_test_pass", True)
                ),
            }
            offline_entry["honest_pass"] = compute_honest_pass(offline_entry)
            results.append(offline_entry)

    corpus_valid_count = sum(1 for item in results if item.get("corpus_valid"))
    honest_pass_count = sum(1 for item in results if item.get("honest_pass"))
    executable_with_cache_count = sum(
        1 for item in results if item.get("executable_with_cache")
    )
    effective_mode = "live" if use_live else "offline"

    return {
        "schema_version": "brownfield_benchmark.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "requested_mode": mode,
        "effective_mode": effective_mode,
        "total_projects": len(results),
        "corpus_valid_count": corpus_valid_count,
        "executable_with_cache_count": executable_with_cache_count,
        "honest_pass_count": honest_pass_count,
        "honest_pass_rate": round(honest_pass_count / len(results), 4) if results else 0.0,
        "dry_run_count": sum(1 for item in results if item.get("status") == "DRY_RUN"),
        "fallback_count": sum(1 for item in results if item.get("fallback_used")),
        "projects": results,
    }


def render_markdown_summary(scorecard: dict[str, Any]) -> str:
    """Render a compact Markdown scorecard summary for docs/evidence."""
    lines = [
        "# Brownfield Benchmark Scorecard",
        "",
        f"- **Generated at**: `{scorecard.get('generated_at')}`",
        f"- **Effective mode**: `{scorecard.get('effective_mode')}` "
        f"(requested: `{scorecard.get('requested_mode')}`)",
        f"- **Corpus integrity**: `{scorecard.get('corpus_valid_count')}/"
        f"{scorecard.get('total_projects')}` valid MIT fixtures",
        f"- **Honest mission passes**: `{scorecard.get('honest_pass_count')}/"
        f"{scorecard.get('total_projects')}` "
        "(DRY_RUN / ADVISORY / started_only / fallback excluded)",
        "",
        "| Benchmark | Language | Type | Corpus Valid | Status | Source | Honest Pass |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in scorecard.get("projects") or []:
        lines.append(
            f"| `{item.get('id')}` | `{item.get('language') or '?'} -> "
            f"{item.get('target_language') or '?'}` | `{item.get('mission_type') or '?'}` | "
            f"`{item.get('corpus_valid')}` | `{item.get('status')}` | "
            f"`{item.get('source')}` | `{item.get('honest_pass')}` |"
        )
    lines.append("")
    return "\n".join(lines)


def write_evidence_outputs(scorecard: dict[str, Any], output_dir: Path) -> tuple[Path, Path, Path]:
    """Write dated JSON, latest JSON, and latest Markdown evidence artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    day_stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    dated_json = output_dir / f"brownfield_benchmark_{day_stamp}.json"
    latest_json = output_dir / "brownfield_benchmark_latest.json"
    latest_md = output_dir / "brownfield_benchmark_latest.md"

    serialized = json.dumps(scorecard, indent=2) + "\n"
    dated_json.write_text(serialized, encoding="utf-8")
    latest_json.write_text(serialized, encoding="utf-8")
    latest_md.write_text(render_markdown_summary(scorecard), encoding="utf-8")
    return dated_json, latest_json, latest_md


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the brownfield benchmark harness."""
    parser = argparse.ArgumentParser(description="Run or validate the brownfield benchmark suite.")
    parser.add_argument(
        "--mode",
        choices=("auto", "offline", "live"),
        default="auto",
        help="Execution mode (auto selects live if reachable, else offline baseline).",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=DEFAULT_CORPUS_DIR,
        help="Path to the brownfield benchmark corpus directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where evidence JSON and Markdown files are written.",
    )
    parser.add_argument(
        "--gateway-url",
        default=None,
        help="Override API Gateway base URL for live benchmark runs.",
    )
    parser.add_argument(
        "--poll-timeout-s",
        type=float,
        default=180.0,
        help="Per-mission live polling timeout in seconds.",
    )
    args = parser.parse_args(argv)

    scorecard = run_benchmark(
        mode=args.mode,
        corpus_dir=args.corpus_dir,
        gateway_url=args.gateway_url,
        poll_timeout_s=args.poll_timeout_s,
    )
    dated_json, latest_json, latest_md = write_evidence_outputs(scorecard, args.output_dir)
    print(
        f"brownfield benchmark complete: mode={scorecard['effective_mode']} "
        f"corpus_valid={scorecard['corpus_valid_count']}/{scorecard['total_projects']} "
        f"honest_pass={scorecard['honest_pass_count']}/{scorecard['total_projects']} "
        f"artifacts=[{dated_json.name}, {latest_json.name}, {latest_md.name}]"
    )
    if scorecard["corpus_valid_count"] < scorecard["total_projects"]:
        return 1
    if scorecard["effective_mode"] == "live" and scorecard["honest_pass_count"] == 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
