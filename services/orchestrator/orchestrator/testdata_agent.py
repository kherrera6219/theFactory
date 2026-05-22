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


def _default_base_image(language: str) -> str:
    return {
        "python": "python:3.11-slim",
        "javascript": "node:20-slim",
        "typescript": "node:20-slim",
        "java": "eclipse-temurin:21-jre",
        "go": "golang:1.22-alpine",
        "rust": "rust:1.78-slim",
        "ruby": "ruby:3.3-slim",
    }.get(language.lower(), "python:3.11-slim")


def _default_run_command(filename: str, language: str) -> str:
    return {
        "python": f"python /workspace/{filename}",
        "javascript": f"node /workspace/{filename}",
        "typescript": f"node /workspace/{filename}",
    }.get(language.lower(), f"cat /workspace/{filename}")


def _install_commands(language: str, dependencies: list[Any]) -> list[str]:
    cleaned = [str(dep).strip() for dep in dependencies[:5] if str(dep).strip()]
    if language.lower() == "python":
        return [f"pip install {dep}" for dep in cleaned]
    if language.lower() in {"javascript", "typescript"}:
        return [f"npm install {dep}" for dep in cleaned]
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
        "notes": "Deterministic TESTDATA manifest for runtime QC Slice A.",
        "filename": filename,
        "language": normalized_language,
        "test_framework": test_framework,
        "source": "fallback",
        "generated_at": datetime.now(UTC).isoformat(),
    }
    return _clamp_manifest(manifest)
