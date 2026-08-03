"""Shared hardened Docker sandbox for executing untrusted generated code.

Extracted from ``rqca_agent._execute_in_sandbox`` by UPG-50 so that RQCA runtime
QC and behavioural equivalence verification run through **one** invocation with
**one** set of security flags.

Why this module exists rather than a second executor: the upgrade plan's risk
table rates "sandbox execution runs untrusted generated code" as the highest
impact risk in the whole programme, and names a second, less-hardened execution
path as the most likely way that risk is realised. Anything that needs to run
generated code calls :func:`run_in_sandbox`; nothing else builds a ``docker run``
command line.

**Do not relax any flag in :data:`SANDBOX_SECURITY_FLAGS`.** Each one is load
bearing:

``--network=none``
    Generated code cannot exfiltrate the workspace, reach internal services, or
    pull further payloads.
``--read-only`` + ``--volume=…:ro``
    The container filesystem and the mounted workspace are immutable, so a
    sample cannot rewrite the artifact it is being judged against.
``--tmpfs=/tmp:size=64m,mode=1777``
    The one writable location, capped and discarded with the container.
``--cap-drop=ALL`` + ``--security-opt=no-new-privileges:true``
    No Linux capabilities, and no regaining them via setuid binaries.
``--memory`` / ``--memory-swap=0`` / ``--cpus=1``
    Bounded blast radius for a runaway or deliberately hostile sample; disabling
    swap prevents trading memory pressure for unbounded disk use.

Treat every input as hostile: equivalence vectors and generated artifacts are
both attacker-influenced in the threat model this sandbox exists for.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)

# Hard ceilings. A caller may request less, never more.
MAX_TIMEOUT_SECONDS = 60
MAX_MEMORY_MB = 512
MIN_MEMORY_MB = 64

# Grace added to the wall-clock wait so Docker itself can start and tear down
# before we treat the run as hung.
_PROCESS_GRACE_SECONDS = 5.0

# The single source of truth for sandbox hardening. Both RQCA and equivalence
# execution build their command line from this list.
SANDBOX_SECURITY_FLAGS: tuple[str, ...] = (
    "--network=none",
    "--memory-swap=0",
    "--cpus=1",
    "--read-only",
    "--tmpfs=/tmp:size=64m,mode=1777",
    "--security-opt=no-new-privileges:true",
    "--cap-drop=ALL",
)


@dataclass(frozen=True, slots=True)
class SandboxResult:
    """Outcome of one sandboxed execution.

    ``timed_out`` is distinct from a non-zero ``exit_code``: a timeout means the
    sample never produced a verdict, which callers must not report as a
    behavioural failure of the code under test.
    """

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    timeout_seconds: int
    memory_limit_mb: int
    base_image: str

    @property
    def succeeded(self) -> bool:
        return not self.timed_out and self.exit_code == 0


def clamp_timeout(value: int | None, default: int = 30) -> int:
    """Clamp a requested timeout into the permitted range."""
    try:
        candidate = int(value) if value is not None else default
    except (TypeError, ValueError):
        candidate = default
    return max(1, min(candidate, MAX_TIMEOUT_SECONDS))


def clamp_memory_mb(value: int | None, default: int = 256) -> int:
    """Clamp a requested memory limit into the permitted range."""
    try:
        candidate = int(value) if value is not None else default
    except (TypeError, ValueError):
        candidate = default
    return max(MIN_MEMORY_MB, min(candidate, MAX_MEMORY_MB))


def build_sandbox_args(
    *,
    docker_bin: str,
    workspace_dir: str | Path,
    base_image: str,
    command: str,
    timeout_seconds: int,
    memory_mb: int,
) -> list[str]:
    """Return the full ``docker run`` argv for a hardened sandbox execution.

    Exposed separately from :func:`run_in_sandbox` so tests can assert the
    security flags are present without needing a Docker daemon — a regression
    that silently dropped ``--network=none`` would otherwise only be caught by
    someone reading the diff.
    """
    return [
        str(docker_bin),
        "run",
        "--rm",
        *SANDBOX_SECURITY_FLAGS,
        f"--memory={clamp_memory_mb(memory_mb)}m",
        "--workdir=/workspace",
        f"--volume={workspace_dir}:/workspace:ro",
        str(base_image),
        "sh",
        "-c",
        command,
    ]


async def run_in_sandbox(
    *,
    docker_bin: str,
    workspace_dir: str | Path,
    base_image: str,
    command: str,
    timeout_seconds: int = 30,
    memory_mb: int = 256,
) -> SandboxResult:
    """Execute *command* against *workspace_dir* inside the hardened sandbox.

    The workspace is mounted **read-only**; anything the command needs to write
    goes to the container's tmpfs and is discarded.

    A timeout kills the process and returns ``timed_out=True`` rather than
    raising, so a hostile or merely slow sample degrades to a recorded
    non-result instead of propagating an exception into the mission pipeline.
    """
    timeout = clamp_timeout(timeout_seconds)
    memory = clamp_memory_mb(memory_mb)
    args = build_sandbox_args(
        docker_bin=docker_bin,
        workspace_dir=workspace_dir,
        base_image=base_image,
        command=command,
        timeout_seconds=timeout,
        memory_mb=memory,
    )

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=float(timeout) + _PROCESS_GRACE_SECONDS
        )
    except TimeoutError:
        proc.kill()
        # Reap the killed process so it does not linger as a zombie.
        try:
            await asyncio.wait_for(proc.communicate(), timeout=5.0)
        except Exception:  # noqa: BLE001 - best effort cleanup only
            pass
        LOGGER.warning("sandbox execution timed out after %ss", timeout)
        return SandboxResult(
            exit_code=-1,
            stdout="",
            stderr=f"execution exceeded {timeout}s timeout",
            timed_out=True,
            timeout_seconds=timeout,
            memory_limit_mb=memory,
            base_image=str(base_image),
        )

    return SandboxResult(
        exit_code=int(proc.returncode or 0),
        stdout=stdout_bytes.decode("utf-8", errors="replace"),
        stderr=stderr_bytes.decode("utf-8", errors="replace"),
        timed_out=False,
        timeout_seconds=timeout,
        memory_limit_mb=memory,
        base_image=str(base_image),
    )


async def check_docker_available(docker_bin: str = "docker") -> bool:
    """Return whether a usable Docker daemon is reachable.

    Callers must degrade to a recorded ``DRY_RUN``/skipped result when this is
    false — never to "passed".
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            str(docker_bin),
            "version",
            "--format",
            "{{.Server.Version}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=10.0)
        return proc.returncode == 0
    except Exception:  # noqa: BLE001 - any failure means "not available"
        return False
