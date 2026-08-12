"""TESTDATA Agent helpers for ephemeral runtime-QC manifests."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

TESTDATA_SCHEMA_VERSION = "testdata_manifest.v1"
_MAX_TIMEOUT_SECONDS = 60
_MAX_MEMORY_MB = 512


def _default_framework(language: str) -> str:
    return {
        "python": "pytest",
        "javascript": "node",
        "typescript": "node",
        "java": "junit",
        "csharp": "nunit",
        "go": "go test",
        "rust": "cargo test",
        "ruby": "rspec",
        "kotlin": "junit",
        "scala": "scalatest",
        "r": "testthat",
        "julia": "Test",
    }.get(language.lower(), "generic")


# Delegated to rqca_agent._LANGUAGE_RUNTIMES so there is ONE answer to "how do
# you run this language". These used to be a second, smaller table whose command
# fell back to `cat /workspace/<file>` for anything outside python/js/ts -- and
# because this module writes both image and command into the manifest, RQCA's
# setdefault never fired and the verified table was bypassed. A live Go mission
# therefore "passed" runtime QC by printing its own source: exit 0, verdict PASS,
# nothing executed. A vacuous pass is worse than a skip, because it asserts a
# verification that never happened.
def _default_base_image(language: str) -> str:
    from .rqca_agent import _LANGUAGE_RUNTIMES  # noqa: PLC0415

    runtime = _LANGUAGE_RUNTIMES.get(language.strip().lower())
    return runtime["base_image"] if runtime else "python:3.11-slim"


def _default_run_command(filename: str, language: str) -> str:
    from pathlib import Path as _Path  # noqa: PLC0415

    from .rqca_agent import _LANGUAGE_RUNTIMES  # noqa: PLC0415

    runtime = _LANGUAGE_RUNTIMES.get(language.strip().lower())
    if runtime:
        return runtime["run_command"].format(filename=filename, stem=_Path(filename).stem)
    # No known runtime. `cat` is deliberate here and only reachable for languages
    # RQCA refuses to execute anyway (run_runtime_qc dry-runs anything outside
    # _ALL_LIVE_LANGUAGES), so it can never produce a passing verdict.
    return f"cat /workspace/{filename}"


def _install_commands(language: str, dependencies: list[Any]) -> list[str]:
    """Always empty: the runtime-QC sandbox has no network, by design.

    This used to emit ``pip install <dep>`` / ``npm install <dep>``. Those ran
    inside a ``--network=none`` container, so they always failed on DNS
    resolution, the artifact never started, and the wasted run was still scored
    PASS. A command that cannot succeed should not be generated at all.

    Unmet dependencies are now detected before execution -- see
    ``rqca_agent._unmet_dependencies`` -- and reported as a DRY_RUN naming them,
    which is the honest outcome for an artifact that cannot run here.

    Kept as a function rather than deleted: the manifest schema still carries
    ``install_commands``, and a sandbox profile with a curated offline package
    mirror would populate it.
    """
    _ = language, dependencies
    return []


def _clamp_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    result = dict(manifest)
    result["network_required"] = False
    try:
        timeout = int(result.get("timeout_seconds") or 30)
    except (TypeError, ValueError):
        timeout = 30
    try:
        memory = int(result.get("memory_limit_mb") or 256)
    except (TypeError, ValueError):
        memory = 256
    result["timeout_seconds"] = max(1, min(timeout, _MAX_TIMEOUT_SECONDS))
    result["memory_limit_mb"] = max(64, min(memory, _MAX_MEMORY_MB))
    return result


async def generate_testdata_manifest(
    *,
    mission_id: str,
    generated_output: dict[str, Any],
    integration_tests: dict[str, Any] | None,
    mission_contract: dict[str, Any],
    language: str,
    settings: Any,
) -> dict[str, Any]:
    """Return a safe runtime-QC manifest with deterministic fallback behavior."""
    _ = mission_contract, settings
    normalized_language = str(language or generated_output.get("language") or "python").lower()
    filename = str(generated_output.get("filename") or f"output.{normalized_language}")
    deps = generated_output.get("dependencies") if isinstance(generated_output, dict) else []
    deps = deps if isinstance(deps, list) else []
    test_framework = str(
        (integration_tests or {}).get("test_framework") or _default_framework(normalized_language)
    )
    manifest = {
        "schema_version": TESTDATA_SCHEMA_VERSION,
        "mission_id": mission_id,
        "base_image": _default_base_image(normalized_language),
        "install_commands": _install_commands(normalized_language, deps),
        "env_vars": {},
        "synthetic_inputs": [
            {
                "input_id": "t001",
                "description": "default safe runtime input",
                "input_data": "test",
            }
        ],
        "run_command": _default_run_command(filename, normalized_language),
        "expected_exit_code": 0,
        "timeout_seconds": 30,
        "memory_limit_mb": 256,
        "network_required": False,
        # Multi-container support: when an LLM-enriched manifest sets
        # multi_container=True and populates services[], rqca_agent.py will
        # build and run a docker-compose stack instead of a single container.
        "multi_container": False,
        "services": [],
        "notes": "Deterministic TESTDATA manifest for runtime QC Slice A.",
        "filename": filename,
        "language": normalized_language,
        "test_framework": test_framework,
        "source": "fallback",
        "generated_at": datetime.now(UTC).isoformat(),
    }
    return _clamp_manifest(manifest)
