# Phase 22 — Runtime QC: TESTDATA and RQCA Agent Activation

**Status:** Slice A implemented locally; live Docker sandbox remains opt-in
**Last updated:** 2026-05-20
**Depends on:** Generated-output/build-artifact path from Phases 3/10,
equivalence/security evidence from Phases 12/13, Phase 18 demo harness, and
Phase 21 core pod evidence. Phase 15 token ledger, Tester-generated
integration tests, Deploy Agent lifecycle wiring, and pod-audit LLM enforcement
remain useful follow-ons but are not hard prerequisites for the first Runtime
QC slice.

---

## Problem

AGENT-40-TESTDATA and AGENT-41-RQCA are the last two fully unimplemented
agents in the registry. Together they close the loop that `WHAT_THEFACTORY_IS_AND_IS_NOT.md`
explicitly promises: "It launches built or patched applications in a sandboxed
environment and validates them through automated browser sessions."

That promise is currently false. Phase 22 starts making it true with a
bounded first runtime-QC slice: generated artifacts get a testdata manifest,
Python/JavaScript artifacts can execute in an opt-in Docker sandbox, and other
languages receive explicit dry-run evidence. Browser automation and
multi-container environments remain later slices.

**AGENT-40-TESTDATA** owns ephemeral test environment lifecycle, schema
provisioning, and synthetic data generation. Without it, the Tester agent's
generated tests (Phase 20) have nowhere to run. The generated code artifact
has no execution environment. Integration test evidence is theoretical.

**AGENT-41-RQCA** (Runtime QC Agent) owns browser and CLI-based runtime
quality control in sandboxed environments. It is what turns "we generated
code" into "we verified the generated code runs and behaves correctly."
Without it, the equivalence report (Phase 12) is LLM-judged only, the
deploy readiness assessment (Phase 21) has limited evidence, and the system
cannot claim runtime validation.

---

## Scope and constraints

Both agents operate on generated code artifacts produced earlier in the
mission. Neither modifies source or mission state directly — they produce
QC evidence artifacts that feed the existing audit chain.

**Hard constraints for this phase:**
- All execution happens in Docker containers isolated from the host. No
  generated code runs on the host filesystem or touches production data.
- Generated code execution is strictly opt-in behind feature flags.
- Timeout and resource limits are mandatory on every sandbox operation.
- No browser automation requires internet access — sandbox is network-isolated.
- The default compose stack must not mount the Docker socket. Any Docker socket
  access is isolated to an explicit operator-selected sandbox profile.
- Mission flow never fails due to TESTDATA or RQCA agent errors — both are
  non-critical path. Evidence is produced when execution succeeds; absence
  of evidence is recorded but does not block COMPLETE.

---

## Review Update — 2026-05-20

Validated against the current repo:

- `AGENT-40-TESTDATA` and `AGENT-41-RQCA` exist in the registry and persona
  matrix, but there are no `testdata_agent.py` or `rqca_agent.py` runtime
  modules yet.
- Mission Flow v2 already tracks `requires_runtime_qc` in PM feature-contract
  metadata, but no runtime-QC lifecycle stage is wired.
- Phase 21 delivered core pod evidence and provider-health telemetry, but it
  did not wire Deploy Agent readiness into COMPLETE or activate LLM pod-audit
  enforcement. Phase 22 should consume existing generated-output,
  equivalence, security/compliance, dependency, and build-artifact metadata
  directly instead of waiting for that wiring.
- Mission Control frontend notes already define the needed `testdata_manifest`
  and `runtime_qc_report` types/panels, but those fields are not yet present in
  the live chain trace types.
- The latest migration in the current repo is `V005`; the runtime-QC migration
  should therefore be `V006_runtime_qc_schema.sql`, not V007.

Plan corrections:

- Treat Phase 22 as **Slice A** only: manifest generation, dry-run evidence,
  and opt-in Docker execution for Python and JavaScript/TypeScript artifacts.
- Keep browser automation, screenshots, multi-container apps, database
  provisioning, and long-running QC sessions out of this phase.
- Do not require Phase 20 Tester-generated integration tests. If tests are
  absent, RQCA should execute the generated artifact with the TESTDATA manifest
  and record the reduced evidence quality.
- Make persistence additive: store summary data in the new runtime-QC tables
  and also expose the latest report through mission metadata/chain trace.

---

## Implementation Update — 2026-05-20

Completed in this pass:

- Added `testdata_agent.py` with deterministic safe manifest generation,
  default language frameworks/images, network-disabled policy, and resource
  caps.
- Added `rqca_agent.py` with dry-run/skipped reports and opt-in Docker
  execution for Python and JavaScript/TypeScript artifacts.
- Added `generate_rqca_assessment()` deterministic fallback assessment.
- Added `V006_runtime_qc_schema.sql`, storage helpers, internal runtime-QC and
  testdata-manifest endpoints, and public redacted runtime-QC endpoint.
- Wired TESTDATA/RQCA into the Mission Flow v2 completion gate behind
  `TESTDATA_AGENT_ENABLED=false`, `RQCA_AGENT_ENABLED=false`, and
  `RQCA_ENFORCEMENT_ENABLED=false`.
- Exposed `testdata_manifest` and `runtime_qc_report` through chain trace.
- Added Mission Control Runtime QC and Test Environment panels.

Still gated:

- Live Docker execution requires operator opt-in and Docker availability.
- Browser automation, screenshots, multi-container environments, database
  provisioning, and long-running QC sessions remain future slices.

---

## Change 1 — TESTDATA Agent: ephemeral environment and test data

### 1a. Add `testdata_agent.py` to orchestrator

```
services/orchestrator/orchestrator/testdata_agent.py
```

The TESTDATA agent is responsible for:
1. Determining what environment a generated artifact needs to run
2. Generating synthetic test input data matched to the artifact's interface
3. Producing an environment manifest the RQCA agent can use to launch the sandbox

```python
"""testdata_agent.py — Ephemeral test environment design and synthetic data generation."""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

LOGGER = logging.getLogger(__name__)

TESTDATA_SCHEMA_VERSION = "testdata_manifest.v1"


async def generate_testdata_manifest(
    *,
    mission_id: str,
    generated_output: dict[str, Any],
    integration_tests: dict[str, Any] | None,
    mission_contract: dict[str, Any],
    language: str,
    settings: Any,
) -> dict[str, Any]:
    """
    TESTDATA Agent designs the ephemeral execution environment and generates
    synthetic test inputs for the generated artifact.

    Returns a manifest the RQCA agent uses to configure the sandbox.
    """
    from .llm_delegation import (
        _agent_recommendation,
        _call_with_recommendation,
        _clean_text,
        _system_prompt_for_agent,
    )

    recommendation = _agent_recommendation("AGENT-40-TESTDATA")
    filename = str(generated_output.get("filename") or f"output.{language}")
    deps = generated_output.get("dependencies") or []
    code_preview = str(generated_output.get("generated_code") or "")[:1500]
    test_framework = (integration_tests or {}).get("test_framework") or _default_framework(language)
    test_code = (integration_tests or {}).get("test_code") or ""
    contract_summary = _clean_text(
        mission_contract.get("contract_summary") or "mission", max_length=200
    )

    prompt = (
        "You are AGENT-40-TESTDATA. Design a minimal ephemeral execution "
        "environment for this generated artifact and produce synthetic test inputs.\n"
        "Return only JSON. No markdown.\n\n"
        f"Language: {language}\n"
        f"Generated file: {filename}\n"
        f"Dependencies declared: {', '.join(deps[:10]) or 'none'}\n"
        f"Test framework: {test_framework}\n"
        f"Mission: {contract_summary}\n\n"
        f"Code preview:\n{_clean_text(code_preview, max_length=1500)}\n\n"
        "Required JSON:\n"
        "{\n"
        '  "base_image": "python:3.11-slim | node:20-slim | openjdk:21-slim | etc",\n'
        '  "install_commands": ["pip install X", "npm install Y"],\n'
        '  "env_vars": {"KEY": "safe_test_value"},\n'
        '  "synthetic_inputs": [\n'
        '    {"input_id": "t001", "description": "normal case", '
        '"input_data": "safe test string or JSON"}\n'
        '  ],\n'
        '  "run_command": "python output.py | pytest test_output.py | etc",\n'
        '  "expected_exit_code": 0,\n'
        '  "timeout_seconds": 30,\n'
        '  "memory_limit_mb": 256,\n'
        '  "network_required": false,\n'
        '  "notes": "one sentence about this environment"\n'
        "}\n\n"
        "Keep environment minimal. No internet access in sandbox. "
        "Use only open-source packages declared in dependencies. "
        "Synthetic inputs must be safe strings — no credentials, PII, or "
        "executable content.\n"
    )
    system = _system_prompt_for_agent("AGENT-40-TESTDATA")
    parsed, provider, model, route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context=f"testdata manifest {mission_id}",
        system_prompt=system,
    )
    if not isinstance(parsed, dict):
        return _fallback_testdata_manifest(
            language=language,
            filename=filename,
            deps=deps,
            test_framework=test_framework,
        )
    # Safety enforcement: never allow network access unless explicitly safe
    if parsed.get("network_required"):
        parsed["network_required"] = False
        parsed["notes"] = (
            str(parsed.get("notes") or "") +
            " [network_required overridden to false by safety policy]"
        )
    # Enforce resource caps
    parsed["timeout_seconds"] = min(int(parsed.get("timeout_seconds") or 30), 60)
    parsed["memory_limit_mb"] = min(int(parsed.get("memory_limit_mb") or 256), 512)
    return {
        **parsed,
        "schema_version": TESTDATA_SCHEMA_VERSION,
        "mission_id": mission_id,
        "filename": filename,
        "language": language,
        "test_framework": test_framework,
        "source": "llm",
        "model_provider": provider,
        "model": model,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _default_framework(language: str) -> str:
    return {
        "python": "pytest",
        "javascript": "jest",
        "typescript": "jest",
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


def _fallback_testdata_manifest(
    *,
    language: str,
    filename: str,
    deps: list[str],
    test_framework: str,
) -> dict[str, Any]:
    base_images = {
        "python": "python:3.11-slim",
        "javascript": "node:20-slim",
        "typescript": "node:20-slim",
        "java": "openjdk:21-slim",
        "go": "golang:1.22-alpine",
        "rust": "rust:1.78-slim",
        "ruby": "ruby:3.3-slim",
    }
    return {
        "schema_version": TESTDATA_SCHEMA_VERSION,
        "base_image": base_images.get(language.lower(), "python:3.11-slim"),
        "install_commands": [f"pip install {d}" for d in deps[:5]]
        if language == "python" else [],
        "env_vars": {},
        "synthetic_inputs": [
            {"input_id": "t001", "description": "default input", "input_data": "test"}
        ],
        "run_command": f"python {filename}" if language == "python" else f"node {filename}",
        "expected_exit_code": 0,
        "timeout_seconds": 30,
        "memory_limit_mb": 256,
        "network_required": False,
        "notes": "Fallback manifest — LLM environment design unavailable.",
        "filename": filename,
        "language": language,
        "test_framework": test_framework,
        "source": "fallback",
        "generated_at": datetime.now(UTC).isoformat(),
    }
```

### 1b. Wire into DELIVERY phase

In `mission_flow_v2.py`, after Tester agent runs and before COMPLETE, when
`TESTDATA_AGENT_ENABLED=true` and `generated_output` exists:

```python
from .testdata_agent import generate_testdata_manifest

testdata_manifest = await generate_testdata_manifest(
    mission_id=mission_id,
    generated_output=metadata["generated_output"],
    integration_tests=metadata.get("integration_tests"),
    mission_contract=metadata.get("mission_contract", {}),
    language=mission.requested_target_language or "python",
    settings=settings,
)
metadata["testdata_manifest"] = testdata_manifest
append_chain_event(
    metadata,
    event_type="MISSION_TESTDATA_MANIFEST_READY",
    agent_id="AGENT-40-TESTDATA",
    details={
        "base_image": testdata_manifest.get("base_image"),
        "timeout_seconds": testdata_manifest.get("timeout_seconds"),
        "synthetic_input_count": len(testdata_manifest.get("synthetic_inputs") or []),
        "source": testdata_manifest.get("source"),
    },
)
```

### 1c. Persist testdata manifest as a build artifact

Store `testdata_manifest` as `artifact_type="testdata_manifest"` alongside
`generated_code` and `integration_tests` in the build artifact table.

---

## Change 2 — RQCA Agent: sandboxed execution and runtime QC verdict

The RQCA agent executes the generated artifact in a Docker sandbox and
reports what happened. This is the most infrastructure-intensive component
in the system. It is implemented in two slices:

**Slice A** (this phase): Docker-based Python and JavaScript execution only.
Other languages use a dry-run path that validates the sandbox manifest without
executing.

**Slice B** (future): Browser automation via Playwright for web artifacts,
multi-language execution, longer-running QC sessions.

### 2a. Add `rqca_agent.py` to orchestrator

```
services/orchestrator/orchestrator/rqca_agent.py
```

```python
"""rqca_agent.py — Runtime QC Agent: sandboxed execution and verdict production."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

RQCA_SCHEMA_VERSION = "runtime_qc_report.v1"

# Languages supported for live execution in Slice A
_EXECUTABLE_LANGUAGES = {"python", "javascript", "typescript"}

# Docker executable — checked at runtime
_DOCKER_BIN = os.getenv("DOCKER_BIN", "docker")

# Resource ceiling — never exceeded regardless of testdata_manifest values
_MAX_TIMEOUT_SECONDS = 60
_MAX_MEMORY_MB = 512


async def run_runtime_qc(
    *,
    mission_id: str,
    generated_output: dict[str, Any],
    testdata_manifest: dict[str, Any],
    integration_tests: dict[str, Any] | None,
    language: str,
    settings: Any,
) -> dict[str, Any]:
    """
    RQCA Agent executes the generated artifact in an isolated Docker sandbox
    and produces a structured runtime QC report.
    """
    filename = str(generated_output.get("filename") or f"output.{language}")
    code = str(generated_output.get("generated_code") or "")
    test_code = (integration_tests or {}).get("test_code") or ""

    if language.lower() not in _EXECUTABLE_LANGUAGES:
        return _dry_run_report(
            mission_id=mission_id,
            language=language,
            filename=filename,
            testdata_manifest=testdata_manifest,
            reason=f"Live execution not yet supported for {language} in Slice A.",
        )

    if not code.strip():
        return _no_artifact_report(mission_id=mission_id, language=language)

    # Check Docker availability
    docker_available = await _check_docker_available()
    if not docker_available:
        return _dry_run_report(
            mission_id=mission_id,
            language=language,
            filename=filename,
            testdata_manifest=testdata_manifest,
            reason="Docker not available in this environment.",
        )

    try:
        return await _execute_in_sandbox(
            mission_id=mission_id,
            filename=filename,
            code=code,
            test_code=test_code,
            testdata_manifest=testdata_manifest,
            language=language,
        )
    except Exception as exc:
        LOGGER.warning("RQCA sandbox execution failed for %s: %s", mission_id, exc)
        return _sandbox_error_report(
            mission_id=mission_id,
            language=language,
            filename=filename,
            error=str(exc),
        )


async def _check_docker_available() -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            _DOCKER_BIN, "info",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=5.0)
        return proc.returncode == 0
    except Exception:
        return False


async def _execute_in_sandbox(
    *,
    mission_id: str,
    filename: str,
    code: str,
    test_code: str,
    testdata_manifest: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    """Execute generated code in an isolated Docker container."""
    base_image = str(testdata_manifest.get("base_image") or "python:3.11-slim")
    install_cmds = testdata_manifest.get("install_commands") or []
    env_vars = testdata_manifest.get("env_vars") or {}
    run_command = str(testdata_manifest.get("run_command") or _default_run_cmd(filename, language))
    timeout = min(int(testdata_manifest.get("timeout_seconds") or 30), _MAX_TIMEOUT_SECONDS)
    memory_mb = min(int(testdata_manifest.get("memory_limit_mb") or 256), _MAX_MEMORY_MB)

    started_at = datetime.now(UTC).isoformat()

    with tempfile.TemporaryDirectory(prefix=f"hgr-rqca-{mission_id[:8]}-") as tmpdir:
        workspace = Path(tmpdir)

        # Write generated code
        (workspace / filename).write_text(code, encoding="utf-8")

        # Write test file if available
        test_filename = ""
        if test_code.strip():
            test_filename = f"test_{filename}"
            (workspace / test_filename).write_text(test_code, encoding="utf-8")

        # Write install script
        install_script = "#!/bin/sh\nset -e\n"
        for cmd in install_cmds[:10]:
            safe_cmd = str(cmd).replace('"', '\\"')
            install_script += f"{safe_cmd}\n"
        (workspace / "install.sh").write_text(install_script)

        # Build Docker run command
        docker_args = [
            _DOCKER_BIN, "run",
            "--rm",
            "--network=none",                          # network isolation
            f"--memory={memory_mb}m",
            "--memory-swap=0",                         # no swap
            "--cpus=1",                                # single CPU
            "--read-only",
            "--tmpfs=/tmp:size=64m,mode=1777",
            "--security-opt=no-new-privileges:true",
            "--cap-drop=ALL",
            f"--workdir=/workspace",
            f"--volume={tmpdir}:/workspace:ro",
        ]
        # Inject safe env vars
        for k, v in list(env_vars.items())[:10]:
            safe_k = str(k).replace("=", "_").replace(" ", "_")[:64]
            safe_v = str(v)[:256]
            docker_args += ["-e", f"{safe_k}={safe_v}"]

        # Full command: install then run
        if install_cmds:
            full_cmd = f"sh /workspace/install.sh && {run_command}"
        else:
            full_cmd = run_command

        docker_args += [base_image, "sh", "-c", full_cmd]

        proc = await asyncio.create_subprocess_exec(
            *docker_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=float(timeout) + 5.0
            )
        except asyncio.TimeoutError:
            proc.kill()
            return _timeout_report(
                mission_id=mission_id,
                language=language,
                filename=filename,
                timeout_seconds=timeout,
                started_at=started_at,
            )

        exit_code = proc.returncode or 0
        stdout_text = stdout_bytes.decode("utf-8", errors="replace")[:4000]
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")[:2000]
        expected_exit = int(testdata_manifest.get("expected_exit_code") or 0)
        passed = exit_code == expected_exit

        return {
            "schema_version": RQCA_SCHEMA_VERSION,
            "mission_id": mission_id,
            "verdict": "PASS" if passed else "FAIL",
            "passed": passed,
            "exit_code": exit_code,
            "expected_exit_code": expected_exit,
            "stdout_preview": stdout_text[:2000],
            "stderr_preview": stderr_text[:1000],
            "execution_type": "docker_live",
            "base_image": base_image,
            "language": language,
            "filename": filename,
            "timeout_seconds": timeout,
            "memory_limit_mb": memory_mb,
            "started_at": started_at,
            "completed_at": datetime.now(UTC).isoformat(),
            "source": "live_execution",
        }


def _default_run_cmd(filename: str, language: str) -> str:
    return {
        "python": f"python /workspace/{filename}",
        "javascript": f"node /workspace/{filename}",
        "typescript": f"node /workspace/{filename}",
    }.get(language.lower(), f"cat /workspace/{filename}")


def _dry_run_report(
    *,
    mission_id: str,
    language: str,
    filename: str,
    testdata_manifest: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    """Validate the manifest without executing — for unsupported languages."""
    manifest_valid = bool(
        testdata_manifest.get("base_image") and
        testdata_manifest.get("run_command")
    )
    return {
        "schema_version": RQCA_SCHEMA_VERSION,
        "mission_id": mission_id,
        "verdict": "DRY_RUN",
        "passed": manifest_valid,
        "execution_type": "dry_run",
        "dry_run_reason": reason,
        "manifest_valid": manifest_valid,
        "language": language,
        "filename": filename,
        "source": "dry_run",
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _timeout_report(
    *,
    mission_id: str,
    language: str,
    filename: str,
    timeout_seconds: int,
    started_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": RQCA_SCHEMA_VERSION,
        "mission_id": mission_id,
        "verdict": "TIMEOUT",
        "passed": False,
        "execution_type": "docker_live",
        "language": language,
        "filename": filename,
        "timeout_seconds": timeout_seconds,
        "started_at": started_at,
        "completed_at": datetime.now(UTC).isoformat(),
        "source": "live_execution",
    }


def _sandbox_error_report(
    *, mission_id: str, language: str, filename: str, error: str
) -> dict[str, Any]:
    return {
        "schema_version": RQCA_SCHEMA_VERSION,
        "mission_id": mission_id,
        "verdict": "ERROR",
        "passed": False,
        "execution_type": "docker_live",
        "language": language,
        "filename": filename,
        "error_summary": error[:500],
        "source": "live_execution",
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _no_artifact_report(*, mission_id: str, language: str) -> dict[str, Any]:
    return {
        "schema_version": RQCA_SCHEMA_VERSION,
        "mission_id": mission_id,
        "verdict": "SKIPPED",
        "passed": True,
        "execution_type": "skipped",
        "skip_reason": "No generated code artifact to execute.",
        "language": language,
        "source": "skipped",
        "generated_at": datetime.now(UTC).isoformat(),
    }
```

### 2b. Add `generate_rqca_assessment()` to `llm_delegation.py`

After sandbox execution, the RQCA agent uses its model (claude-sonnet-4-6)
to reason about the execution result and produce a structured verdict:

```python
async def generate_rqca_assessment(
    *,
    mission_id: str,
    execution_result: dict[str, Any],
    mission_contract: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    """
    RQCA Agent interprets sandbox execution results and produces a
    QC verdict with remediation guidance.
    """
    recommendation = _agent_recommendation("AGENT-41-RQCA")
    verdict = execution_result.get("verdict", "UNKNOWN")

    # For non-executed cases, produce a lightweight advisory
    if verdict in {"DRY_RUN", "SKIPPED"}:
        return {
            "qc_verdict": "ADVISORY",
            "confidence": "LOW",
            "execution_verdict": verdict,
            "findings": [],
            "remediation": [],
            "deployment_safe": True,
            "source": "advisory",
        }

    stdout = _clean_text(
        str(execution_result.get("stdout_preview") or ""), max_length=1000
    )
    stderr = _clean_text(
        str(execution_result.get("stderr_preview") or ""), max_length=500
    )
    exit_code = execution_result.get("exit_code", 0)
    passed = execution_result.get("passed", False)
    contract_summary = _clean_text(
        mission_contract.get("contract_summary") or "mission", max_length=200
    )
    acceptance = "; ".join(
        _clean_text(str(item), max_length=80)
        for item in (mission_contract.get("acceptance_criteria") or [])[:4]
    )

    prompt = (
        "You are AGENT-41-RQCA. Interpret this sandbox execution result and "
        "produce a QC verdict.\n"
        "Return only JSON. No markdown.\n\n"
        f"Language: {language}\n"
        f"Mission: {contract_summary}\n"
        f"Acceptance criteria: {acceptance}\n"
        f"Execution verdict: {verdict}\n"
        f"Exit code: {exit_code} (expected: "
        f"{execution_result.get('expected_exit_code', 0)})\n"
        f"stdout:\n{stdout}\n"
        f"stderr:\n{stderr}\n\n"
        "Required JSON:\n"
        "{\n"
        '  "qc_verdict": "PASS | WARN | FAIL | INCONCLUSIVE",\n'
        '  "confidence": "HIGH | MEDIUM | LOW",\n'
        '  "execution_verdict": "PASS | FAIL | TIMEOUT | ERROR | DRY_RUN",\n'
        '  "findings": ["specific runtime observations"],\n'
        '  "remediation": ["actionable fixes if verdict is FAIL"],\n'
        '  "acceptance_coverage": "what criteria were visibly satisfied",\n'
        '  "deployment_safe": true\n'
        "}\n\n"
        "PASS: execution succeeded and output appears correct.\n"
        "WARN: execution succeeded but output has concerns.\n"
        "FAIL: execution failed or output clearly wrong.\n"
        "INCONCLUSIVE: execution ran but cannot determine correctness.\n"
    )
    system = _system_prompt_for_agent("AGENT-41-RQCA")
    parsed, provider, model, route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context=f"rqca assessment {mission_id}",
        system_prompt=system,
    )
    if not isinstance(parsed, dict):
        return {
            "qc_verdict": "PASS" if passed else "FAIL",
            "confidence": "LOW",
            "execution_verdict": verdict,
            "findings": [],
            "remediation": [],
            "deployment_safe": passed,
            "source": "fallback",
        }
    return {
        **parsed,
        "source": "llm",
        "model_provider": provider,
        "model": model,
        "assessed_at": datetime.now(UTC).isoformat(),
    }
```

### 2c. Wire RQCA into VERIFIED phase

In `mission_flow_v2.py`, after equivalence verification and before COMPLETE,
when `RQCA_AGENT_ENABLED=true` and `generated_output` and `testdata_manifest`
exist:

```python
from .rqca_agent import run_runtime_qc
from .llm_delegation import generate_rqca_assessment

execution_result = await run_runtime_qc(
    mission_id=mission_id,
    generated_output=metadata["generated_output"],
    testdata_manifest=metadata.get("testdata_manifest", {}),
    integration_tests=metadata.get("integration_tests"),
    language=mission.requested_target_language or "python",
    settings=settings,
)
qc_assessment = await generate_rqca_assessment(
    mission_id=mission_id,
    execution_result=execution_result,
    mission_contract=metadata.get("mission_contract", {}),
    language=mission.requested_target_language or "python",
)
metadata["runtime_qc_report"] = {
    **execution_result,
    "qc_assessment": qc_assessment,
}
append_chain_event(
    metadata,
    event_type="MISSION_RUNTIME_QC_COMPLETE",
    agent_id="AGENT-41-RQCA",
    details={
        "execution_verdict": execution_result.get("verdict"),
        "qc_verdict": qc_assessment.get("qc_verdict"),
        "execution_type": execution_result.get("execution_type"),
        "deployment_safe": qc_assessment.get("deployment_safe"),
        "source": execution_result.get("source"),
    },
)
# RQCA FAIL never blocks COMPLETE by default — advisory evidence only
# Set RQCA_ENFORCEMENT_ENABLED=true to gate COMPLETE on QC pass
if rqca_enforcement and qc_assessment.get("qc_verdict") == "FAIL":
    raise MissionBlockedByRQCA(
        f"RQCA blocked mission: {qc_assessment.get('findings', [])}"
    )
```

---

## Change 3 — Schema migration V006

Create `V006_runtime_qc_schema.sql` because the current repository has
migrations `V001` through `V005`:

```sql
-- Runtime QC execution log
CREATE TABLE IF NOT EXISTS mission_runtime_qc (
    id BIGSERIAL PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
    execution_type TEXT NOT NULL,  -- docker_live | dry_run | skipped
    verdict TEXT NOT NULL,         -- PASS | FAIL | TIMEOUT | ERROR | DRY_RUN | SKIPPED
    qc_verdict TEXT,               -- PASS | WARN | FAIL | INCONCLUSIVE | ADVISORY
    exit_code INTEGER,
    language TEXT,
    filename TEXT,
    base_image TEXT,
    stdout_preview TEXT,
    stderr_preview TEXT,
    execution_result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    qc_assessment_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mission_runtime_qc_mission_created
ON mission_runtime_qc (mission_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_mission_runtime_qc_verdict
ON mission_runtime_qc (verdict, qc_verdict);

-- Testdata manifests
CREATE TABLE IF NOT EXISTS mission_testdata_manifests (
    id BIGSERIAL PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
    manifest_json JSONB NOT NULL,
    language TEXT,
    base_image TEXT,
    test_framework TEXT,
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Add storage helpers:
- `insert_runtime_qc_report(settings, mission_id, execution_result, qc_assessment)`
- `insert_testdata_manifest(settings, mission_id, manifest)`
- `get_runtime_qc_report(settings, mission_id)`

---

## Change 4 — API exposure

### 4a. Internal routes

Add to `routes/internal.py`:
```python
GET /internal/missions/{mission_id}/runtime-qc
GET /internal/missions/{mission_id}/testdata-manifest
```

Also include `testdata_manifest` and `runtime_qc_report` in the existing
mission chain-trace payload so Mission Control can render the new panels from
the same mission-detail fetch it already uses.

### 4b. Public routes

Add to `routes/` (public tier):
```python
GET /v1/missions/{mission_id}/runtime-qc
```

Returns the runtime QC report with execution verdict, QC verdict, stdout
preview, and deployment safety assessment. Redacts stderr details in
non-admin contexts.

---

## Change 5 — Mission Control UI

### 5a. Runtime QC panel in Mission Detail

When `metadata.runtime_qc_report` is present, render a "Runtime QC" panel:

```tsx
{runtimeQc && (
  <RuntimeQCPanel
    executionVerdict={runtimeQc.verdict}
    qcVerdict={runtimeQc.qc_assessment?.qc_verdict}
    executionType={runtimeQc.execution_type}
    deploymentSafe={runtimeQc.qc_assessment?.deployment_safe}
    findings={runtimeQc.qc_assessment?.findings || []}
    remediation={runtimeQc.qc_assessment?.remediation || []}
    stdoutPreview={runtimeQc.stdout_preview}
    baseImage={runtimeQc.base_image}
    language={runtimeQc.language}
  />
)}
```

Color coding: PASS → green, WARN → amber, FAIL → red, DRY_RUN/ADVISORY → grey.

### 5b. TESTDATA panel in Mission Detail

When `metadata.testdata_manifest` is present, render a collapsible
"Test Environment" panel showing base image, install commands, synthetic
input count, and run command.

---

## Change 6 — docker-compose sandbox profile

Add an optional `rqca-sandbox` profile to `docker-compose.yaml` that
grants the orchestrator Docker socket access for sandbox execution.

**Critical security note:** Docker socket access is a high-privilege
capability. This profile is NEVER included in the default compose stack.
It must be explicitly opted in by the operator.

Do not imply that a read-only socket mount makes Docker safe. The Docker API
can still create privileged containers even when the socket path is mounted
read-only. The isolation boundary is the dedicated host/profile policy plus
the child-container runtime restrictions.

```yaml
# In deploy/docker-compose.yaml under orchestrator service:
# Add to profiles: ["rqca-sandbox"] — NOT default
volumes:
  - /var/run/docker.sock:/var/run/docker.sock     # rqca-sandbox profile only
```

Document clearly in `.env.example` and `OPERATIONS_RUNBOOK.md`:
- `RQCA_AGENT_ENABLED=false` must remain false unless the rqca-sandbox
  compose profile is active.
- The Docker socket grants the orchestrator container root-equivalent access
  to the host. Only enable on machines dedicated to theFactory.
- Generated code runs in `--network=none --read-only --cap-drop=ALL`
  containers. The sandbox isolation is enforced at the Docker level, not
  just in code.

---

## Settings

Add to `settings.py` and `.env.example`:

```bash
# Phase 22 — Runtime QC Agents
TESTDATA_AGENT_ENABLED=false     # Testdata manifest generation
RQCA_AGENT_ENABLED=false         # Sandbox execution and QC verdict
RQCA_ENFORCEMENT_ENABLED=false   # Block COMPLETE on RQCA FAIL verdict
DOCKER_BIN=docker                # Path to Docker binary for sandbox execution
```

---

## Non-Goals

- Do not implement browser automation (Playwright) in this phase.
  Web UI validation is Slice B.
- Do not implement multi-container test environments or docker-compose-based
  sandboxes. Single container only.
- Do not implement test result persistence across missions (regression baseline).
  That is a future quality-trend phase.
- Do not implement RQCA for missions without generated_code artifacts. Analysis
  and documentation missions are out of scope for runtime execution.
- Do not grant the orchestrator persistent Docker socket access in any
  non-sandbox profile. The socket mount is strictly opt-in.

---

## Validation

### TESTDATA Agent
- [x] `TESTDATA_AGENT_ENABLED=false`: no testdata call, no metadata key added.
- [x] Flag enabled with Python `generated_output`: `testdata_manifest` in
      chain trace with `base_image="python:3.11-slim"` and
      `network_required=false`.
- [x] Manifest network access is forced to `false`.
- [x] `timeout_seconds > 60` is capped to 60.
- [x] `memory_limit_mb > 512` is capped to 512.
- [x] `MISSION_TESTDATA_MANIFEST_READY` event is emitted in chain trace.
- [x] Fallback manifest returned without requiring provider calls.

### RQCA Agent — dry run
- [x] `RQCA_AGENT_ENABLED=false`: no RQCA call, no metadata key.
- [x] Flag enabled for `language="rust"`: returns `DRY_RUN` verdict (not
      supported in Slice A).
- [x] `MISSION_RUNTIME_QC_COMPLETE` event in chain trace with
      `execution_type="dry_run"`.

### RQCA Agent — live execution (requires Docker)
- [x] `_check_docker_available()` returns False when Docker absent —
      falls back to dry_run without raising.
- [ ] Simple Python `print("hello")` generated artifact executes, exits 0,
      returns `verdict="PASS"`.
- [ ] Python artifact with `sys.exit(1)` returns `verdict="FAIL"` with
      `exit_code=1`.
- [ ] Execution timeout after configured seconds returns `verdict="TIMEOUT"`.
- [ ] Execution never mounts host filesystem outside tmpdir.
- [ ] Execution never has network access (`--network=none` verified in Docker args).
- [ ] `RQCA_ENFORCEMENT_ENABLED=false`: FAIL verdict does not block COMPLETE.
- [ ] Enforcement + FAIL verdict: mission does not reach COMPLETE state.

### Schema migration
- [x] `V006_runtime_qc_schema.sql` is present and sequenced after V001–V005.
- [ ] `mission_runtime_qc` table accepts insert and select for a test row.
- [ ] `mission_testdata_manifests` table accepts insert and select.

### API
- [x] `GET /v1/missions/{id}/runtime-qc` returns a redacted runtime-QC payload
      when data exists.
- [ ] `GET /v1/missions/{id}/runtime-qc` returns 200 for a completed mission
      with QC data.
- [ ] `GET /v1/missions/{id}/runtime-qc` returns 404 for a mission without
      QC data.
- [x] Stderr detail redacted in public response.
- [x] Chain trace exposes `testdata_manifest` and `runtime_qc_report`.

### Mission Control
- [x] Runtime QC panel renders runtime-QC verdict data when present.
- [ ] Runtime QC panel renders for FAIL verdict (red chip + remediation list).
- [ ] DRY_RUN verdict renders with grey chip and dry_run_reason text.
- [x] Test Environment panel renders with base_image and synthetic input count.

### Full suite
- [x] Focused backend pytest passes on touched files.
- [x] Focused ruff check passes on touched files.
- [x] `npm --prefix apps/mission-control run lint` passes.
- [x] `npm --prefix apps/mission-control run test` passes.
- [ ] RQCA and TESTDATA failures are never propagated as mission FAILED state
      unless enforcement flags are explicitly set.
- [ ] No test in the standard suite requires Docker to be running.
      Docker-dependent tests are tagged `@pytest.mark.requires_docker` and
      excluded from `make test`.
