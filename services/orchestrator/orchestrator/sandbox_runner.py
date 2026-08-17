"""Privileged sandbox executor — the only process that should mount docker.sock.

Condensed topology still runs RQCA *verdicts* in the orchestrator. This
service only executes ``docker run`` with :data:`SANDBOX_SECURITY_FLAGS`.
The orchestrator calls it when ``SANDBOX_EXECUTOR_URL`` is set so the
mission orchestrator no longer needs host-root socket access.

AGENT-41-RQCA remains the named verdict owner. In condensed deploy this
runner is the privilege boundary; the dedicated overlay may point the
same URL at ``agent-41-rqca`` once that worker serves this API.
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .sandbox_exec import (
    SandboxResult,
    clamp_memory_mb,
    clamp_timeout,
    run_in_sandbox_local,
)

LOGGER = logging.getLogger(__name__)

app = FastAPI(title="HGR sandbox runner", docs_url=None, redoc_url=None)


class SandboxExecuteRequest(BaseModel):
    workspace_dir: str = Field(min_length=1, max_length=1024)
    base_image: str = Field(min_length=1, max_length=256)
    command: str = Field(min_length=1, max_length=8000)
    timeout_seconds: int = 30
    memory_mb: int = 256
    docker_bin: str = Field(default="docker", max_length=128)


def _expected_key() -> str:
    return os.getenv("INTERNAL_SERVICE_API_KEY", "").strip()


def _authorize(authorization: str | None) -> None:
    expected = _expected_key()
    if not expected:
        raise HTTPException(status_code=503, detail="sandbox runner key is not configured")
    provided = (authorization or "").strip()
    if provided.lower().startswith("bearer "):
        provided = provided[7:].strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


def result_to_payload(result: SandboxResult) -> dict[str, Any]:
    return {
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timed_out": result.timed_out,
        "timeout_seconds": result.timeout_seconds,
        "memory_limit_mb": result.memory_limit_mb,
        "base_image": result.base_image,
    }


@app.get("/livez")
async def livez() -> dict[str, bool]:
    return {"ok": True}


@app.get("/internal/sandbox/health")
async def sandbox_health(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _authorize(authorization)
    return {"ok": True, "runner": "sandbox-runner"}


@app.post("/internal/sandbox/execute")
async def sandbox_execute(
    payload: SandboxExecuteRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _authorize(authorization)
    timeout = clamp_timeout(payload.timeout_seconds)
    memory = clamp_memory_mb(payload.memory_mb)
    docker_bin = payload.docker_bin.strip() or "docker"
    if any(ch in docker_bin for ch in ("/", "\\", " ", "\t")):
        # Refuse path-like or spaced binaries; runner uses the image default.
        docker_bin = "docker"
    LOGGER.info(
        "sandbox-runner execute image=%s timeout=%s memory=%s",
        payload.base_image,
        timeout,
        memory,
    )
    result = await run_in_sandbox_local(
        docker_bin=docker_bin,
        workspace_dir=payload.workspace_dir,
        base_image=payload.base_image,
        command=payload.command,
        timeout_seconds=timeout,
        memory_mb=memory,
    )
    return result_to_payload(result)
