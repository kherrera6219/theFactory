"""Regression test for Phase 0: agent-runtime must not fall back to the
well-known literal default credential "worker-key" when SERVICE_API_KEY is
unset (Full Whole-App Remediation Plan 2026-07-05, Phase 0 item 5).

Run in a fresh subprocess since the module-level guard fires at import time
and the module is already imported (with a test key set) elsewhere in this
test session.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME_ROOT = ROOT / "services" / "agent-runtime"


def _run_import(env_overrides: dict[str, str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.pop("SERVICE_API_KEY", None)
    env.update(env_overrides)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(AGENT_RUNTIME_ROOT), str(ROOT), env.get("PYTHONPATH", "")]
    )
    return subprocess.run(
        [sys.executable, "-c", "import agent_runtime.main"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_missing_service_api_key_fails_fast() -> None:
    result = _run_import({})
    assert result.returncode != 0
    assert "SERVICE_API_KEY must be set" in result.stderr


def test_configured_service_api_key_imports_cleanly() -> None:
    result = _run_import({"SERVICE_API_KEY": "a-real-service-key"})
    assert result.returncode == 0, result.stderr
