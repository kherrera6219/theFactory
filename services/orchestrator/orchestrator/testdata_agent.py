"""TESTDATA Agent helpers for ephemeral runtime-QC manifests."""
from __future__ import annotations

import re
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


def _synthesize_contract_inputs(
    mission_contract: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Derive 4 structured test input fixtures (nominal, boundary, empty_null, malformed_adversarial) from the SOW/contract."""
    contract = mission_contract if isinstance(mission_contract, dict) else {}
    summary = str(contract.get("contract_summary") or "")
    func_reqs = [str(item) for item in (contract.get("functional_requirements") or []) if item]
    criteria = [str(item) for item in (contract.get("acceptance_criteria") or []) if item]
    logic_reqs = [
        f"{item.get('domain', '')} {item.get('concept', '')} {item.get('intent', '')}"
        for item in (contract.get("logicnode_requirements") or [])
        if isinstance(item, dict)
    ]
    full_text = "\n".join([summary, *func_reqs, *criteria, *logic_reqs])
    lowered = full_text.lower()

    if not full_text.strip():
        return [
            {
                "input_id": "t001",
                "category": "nominal",
                "description": "default safe runtime input",
                "input_data": "test",
                "args": [],
            },
            {
                "input_id": "t002",
                "category": "boundary",
                "description": "numeric and length boundary input",
                "input_data": "0\n-1\n2147483647",
                "args": [],
            },
            {
                "input_id": "t003",
                "category": "empty_null",
                "description": "empty stdin edge case",
                "input_data": "",
                "args": [],
            },
            {
                "input_id": "t004",
                "category": "malformed_adversarial",
                "description": "malformed adversarial payload",
                "input_data": "{unclosed_json: [null, \"\x00\", -99999999999999999999",
                "args": [],
            },
        ]

    cli_flags = sorted(set(re.findall(r"--[a-zA-Z0-9][a-zA-Z0-9_-]*", full_text)))[:4]
    numbers = re.findall(r"\b\d+(?:\.\d+)?\b", full_text)
    upper_bound = numbers[0] if numbers else "1000"

    if "csv" in lowered:
        nominal_data = "id,name,value\n1,alpha,42\n2,beta,99\n"
        boundary_data = f"id,name,value\n0,zero,0\n999999,max,{upper_bound}\n"
        malformed_data = 'id,name,value\n1,"unclosed_quote,abc\n,,\n'
    elif "json" in lowered:
        nominal_data = '{"id": 1, "name": "alpha", "value": 42, "items": ["a", "b"]}'
        boundary_data = f'{{"id": 0, "name": "", "value": {upper_bound}, "items": []}}'
        malformed_data = '{"id": 1, "broken": [1, 2, '
    else:
        nominal_data = summary[:120].strip() or "test"
        boundary_data = f"0\n-1\n{upper_bound}"
        malformed_data = "INVALID_INPUT\x00--bad-flag\n{malformed"

    return [
        {
            "input_id": "t001",
            "category": "nominal",
            "description": "contract-derived nominal happy-path input",
            "input_data": nominal_data,
            "args": cli_flags[:2],
        },
        {
            "input_id": "t002",
            "category": "boundary",
            "description": f"contract-derived boundary input (bound={upper_bound})",
            "input_data": boundary_data,
            "args": cli_flags[:1],
        },
        {
            "input_id": "t003",
            "category": "empty_null",
            "description": "empty / whitespace edge-case input",
            "input_data": "",
            "args": [],
        },
        {
            "input_id": "t004",
            "category": "malformed_adversarial",
            "description": "malformed / adversarial input for error-handling verification",
            "input_data": malformed_data,
            "args": ["--invalid-flag"] if cli_flags else [],
        },
    ]


async def generate_testdata_manifest(
    *,
    mission_id: str,
    generated_output: dict[str, Any],
    integration_tests: dict[str, Any] | None,
    mission_contract: dict[str, Any],
    language: str,
    settings: Any,
) -> dict[str, Any]:
    """Return a safe runtime-QC manifest with contract-derived synthetic inputs."""
    _ = settings
    normalized_language = str(language or generated_output.get("language") or "python").lower()
    filename = str(generated_output.get("filename") or f"output.{normalized_language}")
    deps = generated_output.get("dependencies") if isinstance(generated_output, dict) else []
    deps = deps if isinstance(deps, list) else []
    test_framework = str(
        (integration_tests or {}).get("test_framework") or _default_framework(normalized_language)
    )
    synthetic_inputs = _synthesize_contract_inputs(mission_contract)
    has_contract = bool(
        isinstance(mission_contract, dict)
        and (
            mission_contract.get("functional_requirements")
            or mission_contract.get("acceptance_criteria")
            or mission_contract.get("logicnode_requirements")
            or mission_contract.get("contract_summary")
        )
    )
    manifest = {
        "schema_version": TESTDATA_SCHEMA_VERSION,
        "mission_id": mission_id,
        "base_image": _default_base_image(normalized_language),
        "install_commands": _install_commands(normalized_language, deps),
        "env_vars": {},
        "synthetic_inputs": synthetic_inputs,
        "contract_categories": [item["category"] for item in synthetic_inputs],
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
        "notes": (
            "Contract-derived TESTDATA manifest covering nominal, boundary, "
            "empty_null, and malformed_adversarial inputs."
            if has_contract
            else "Deterministic TESTDATA manifest for runtime QC Slice A."
        ),
        "filename": filename,
        "language": normalized_language,
        "test_framework": test_framework,
        "source": "contract_derived" if has_contract else "fallback",
        "generated_at": datetime.now(UTC).isoformat(),
    }
    return _clamp_manifest(manifest)
