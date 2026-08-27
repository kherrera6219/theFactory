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
``--tmpfs=/tmp:size=64m,mode=1777,exec``
    The one writable location, capped and discarded with the container.

    ``exec`` is required, not a relaxation. Docker mounts tmpfs ``noexec`` by
    default, and a compiled language has to put its binary *somewhere* writable
    and then run it: with ``/workspace`` read-only and ``/tmp`` noexec there is
    no such place, so every C/C++/Rust run failed — first at link time
    (``cannot open output file /workspace/a.out: Read-only file system``,
    because the compile commands targeted the read-only mount) and then at exec
    time (``/tmp/a.out: Permission denied``). Both were verified by hand against
    ``gcc:13-bookworm`` and ``rust:1.78-slim-bookworm``.

    What ``exec`` costs is close to nothing here. The sample already executes
    arbitrary code by construction — that is the entire purpose of the sandbox —
    so denying execution from tmpfs does not remove a capability an attacker
    lacks, it only removes the ability to compile. Every property the other
    flags provide is untouched: no network, no capabilities, no privilege
    escalation, read-only rootfs, and above all the workspace stays ``:ro``, so
    the sample still cannot rewrite the artifact it is being judged against.
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
import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .sandbox_paths import make_workspace_readable

LOGGER = logging.getLogger(__name__)

# --- Sibling-container workspace addressing --------------------------------
#
# The orchestrator runs `docker run` against the host daemon via a mounted
# socket, so the sandbox is a *sibling* container, not a child. The daemon
# resolves `--volume` source paths on the HOST, not inside the orchestrator --
# so passing a path from the orchestrator's own filesystem (a plain
# `tempfile.TemporaryDirectory()`) silently mounts an empty directory that the
# daemon helpfully creates. The compile step then fails with "no such file", and
# with RQCA_ENFORCEMENT_ENABLED that blocks the mission.
#
# The fix is a shared directory reachable from both sides: bind-mount a host
# directory into the orchestrator at SANDBOX_WORKSPACE_ROOT, create workspaces
# under it, and translate the path back to its host form when building the
# `--volume` argument. Both must be set for translation to happen; with either
# missing the path is passed through unchanged, which is correct for a local
# (non-containerised) orchestrator whose paths the daemon already shares.
_WORKSPACE_ROOT = os.getenv("SANDBOX_WORKSPACE_ROOT", "").strip()
_WORKSPACE_HOST_ROOT = os.getenv("SANDBOX_WORKSPACE_HOST_ROOT", "").strip()


def workspace_root() -> str | None:
    """Directory that sandbox workspaces must be created in.

    Returns ``None`` when unconfigured, which is exactly what
    ``tempfile.TemporaryDirectory(dir=...)`` wants in order to fall back to the
    system temp directory.
    """
    return _WORKSPACE_ROOT or None


def daemon_workspace_path(workspace_dir: str | Path) -> str:
    """Translate a path in this container to the path the Docker daemon sees.

    A no-op unless both roots are configured, or when ``workspace_dir`` lies
    outside the shared root -- in that case there is no correct translation, so
    the original path is returned rather than a fabricated one.
    """
    raw = str(workspace_dir)
    if not _WORKSPACE_ROOT or not _WORKSPACE_HOST_ROOT:
        return raw
    try:
        relative = PurePosixPath(raw.replace("\\", "/")).relative_to(
            PurePosixPath(_WORKSPACE_ROOT.replace("\\", "/"))
        )
    except ValueError:
        LOGGER.warning(
            "sandbox workspace %s is outside SANDBOX_WORKSPACE_ROOT; "
            "the daemon may not be able to resolve it",
            raw,
        )
        return raw
    host_root = _WORKSPACE_HOST_ROOT.replace("\\", "/").rstrip("/")
    return f"{host_root}/{relative.as_posix()}" if relative.parts else host_root

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
    # `exec` is load bearing for compiled languages -- see the module docstring.
    "--tmpfs=/tmp:size=64m,mode=1777,exec",
    "--security-opt=no-new-privileges:true",
    "--cap-drop=ALL",
)

#: The one writable, executable location inside the sandbox. Compiled languages
#: must place build output here: ``/workspace`` is mounted read-only on purpose.
#:
#: nosec B108 -- this is not a host temp path. It names the tmpfs mounted inside
#: a throwaway, single-use container (see SANDBOX_SECURITY_FLAGS): no other
#: process shares that namespace, nothing persists past the run, and the
#: predictable-path/symlink attack B108 guards against has no attacker to
#: mount it. Making it unpredictable would also break the compile commands,
#: which must name the directory they build into.
SANDBOX_BUILD_DIR = "/tmp"  # nosec B108


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
        # Translated, not raw: the daemon resolves this on the host. See
        # daemon_workspace_path.
        f"--volume={daemon_workspace_path(workspace_dir)}:/workspace:ro",
        # Run the command under a plain shell regardless of what the image
        # declares. Without this, an image with its own ENTRYPOINT wraps our
        # command in it: ocaml/opam prefixes `opam exec --`, which tries to
        # write a log into a read-only home and dies before our command runs,
        # and sbtscala launches sbt. Normalising here means one language config
        # cannot behave differently from another because of an image's default.
        "--entrypoint=sh",
        str(base_image),
        "-c",
        command,
    ]


def _make_workspace_readable(workspace_dir: str | Path) -> None:
    """Let the sandbox read the workspace despite ``--cap-drop=ALL``.

    ``tempfile.TemporaryDirectory`` creates 0700 directories owned by the
    orchestrator's service user. Normally the sandbox's root user would read
    them anyway via CAP_DAC_OVERRIDE -- but dropping *all* capabilities takes
    that away, so root becomes subject to the ordinary permission bits and the
    compiler reports ``main.c: Permission denied``, which reads like a bug in
    the generated code rather than a mount-permission problem.

    Widening these bits grants nothing: the mount is read-only, and the contents
    are the artifact we are deliberately handing to the sandbox to execute.
    Failures are logged rather than raised -- on some bind-mount backends chmod
    is a no-op, and the run should proceed and fail on its own merits.

    The chmod/rglob walk itself is delegated to sandbox_paths, which refuses any
    directory that does not resolve under an allowed root and skips entries that
    escape it via symlink. Without that containment a caller-supplied path could
    have this relax permissions anywhere the service user can write (CodeQL
    522/523).
    """
    make_workspace_readable(workspace_dir, workspace_root=_WORKSPACE_ROOT)


def sandbox_executor_url() -> str:
    """Remote executor base URL, or empty when this process runs docker locally.

    Read at call time so tests and compose env changes are honored after import.
    The runner must set ``SANDBOX_RUNNER_MODE=true`` so it cannot loop to itself.
    Only http(s) URLs are accepted.
    """
    runner_mode = os.getenv("SANDBOX_RUNNER_MODE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if runner_mode:
        return ""
    raw = os.getenv("SANDBOX_EXECUTOR_URL", "").strip().rstrip("/")
    if raw.startswith("https://") or raw.startswith("http://"):
        return raw
    return ""


def _sandbox_auth_header() -> str:
    key = os.getenv("INTERNAL_SERVICE_API_KEY", "").strip()
    return f"Bearer {key}" if key else ""


def result_from_payload(payload: dict[str, object], *, fallback_image: str, timeout: int, memory: int) -> SandboxResult:
    return SandboxResult(
        exit_code=int(payload.get("exit_code") or 0),
        stdout=str(payload.get("stdout") or ""),
        stderr=str(payload.get("stderr") or ""),
        timed_out=bool(payload.get("timed_out")),
        timeout_seconds=int(payload.get("timeout_seconds") or timeout),
        memory_limit_mb=int(payload.get("memory_limit_mb") or memory),
        base_image=str(payload.get("base_image") or fallback_image),
    )


async def run_in_sandbox_remote(
    *,
    executor_url: str,
    workspace_dir: str | Path,
    base_image: str,
    command: str,
    timeout_seconds: int = 30,
    memory_mb: int = 256,
    docker_bin: str = "docker",
) -> SandboxResult:
    """POST a sandbox job to the privileged runner. No local docker.sock."""
    timeout = clamp_timeout(timeout_seconds)
    memory = clamp_memory_mb(memory_mb)
    body = json.dumps(
        {
            "workspace_dir": str(workspace_dir),
            "base_image": str(base_image),
            "command": str(command),
            "timeout_seconds": timeout,
            "memory_mb": memory,
            "docker_bin": str(docker_bin or "docker"),
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{executor_url.rstrip('/')}/internal/sandbox/execute",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": _sandbox_auth_header(),
        },
    )
    http_timeout = float(timeout) + _PROCESS_GRACE_SECONDS + 5.0

    def _post() -> SandboxResult:
        try:
            with urllib.request.urlopen(request, timeout=http_timeout) as response:  # nosec B310
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            LOGGER.warning("sandbox executor HTTP %s: %s", exc.code, detail[:300])
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=f"sandbox executor HTTP {exc.code}: {detail[:300]}",
                timed_out=False,
                timeout_seconds=timeout,
                memory_limit_mb=memory,
                base_image=str(base_image),
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            LOGGER.warning("sandbox executor unreachable: %s", exc)
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=f"sandbox executor unreachable: {exc}",
                timed_out=False,
                timeout_seconds=timeout,
                memory_limit_mb=memory,
                base_image=str(base_image),
            )
        if not isinstance(payload, dict):
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr="sandbox executor returned a non-object payload",
                timed_out=False,
                timeout_seconds=timeout,
                memory_limit_mb=memory,
                base_image=str(base_image),
            )
        return result_from_payload(
            payload,
            fallback_image=str(base_image),
            timeout=timeout,
            memory=memory,
        )

    return await asyncio.to_thread(_post)


async def run_in_sandbox_local(
    *,
    docker_bin: str,
    workspace_dir: str | Path,
    base_image: str,
    command: str,
    timeout_seconds: int = 30,
    memory_mb: int = 256,
) -> SandboxResult:
    """Execute *command* against *workspace_dir* with a local ``docker run``.

    Only the sandbox-runner (or a non-containerized orchestrator) should call
    this. Mission orchestrators in compose use :func:`run_in_sandbox_remote`.
    """
    timeout = clamp_timeout(timeout_seconds)
    memory = clamp_memory_mb(memory_mb)
    _make_workspace_readable(workspace_dir)
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

    When ``SANDBOX_EXECUTOR_URL`` is set (and this process is not the runner),
    the job is POSTed to the privileged sandbox-runner. Otherwise this process
    runs ``docker`` locally.

    The workspace is mounted **read-only**; anything the command needs to write
    goes to the container's tmpfs and is discarded.

    A timeout kills the process and returns ``timed_out=True`` rather than
    raising, so a hostile or merely slow sample degrades to a recorded
    non-result instead of propagating an exception into the mission pipeline.
    """
    remote = sandbox_executor_url()
    if remote:
        return await run_in_sandbox_remote(
            executor_url=remote,
            workspace_dir=workspace_dir,
            base_image=base_image,
            command=command,
            timeout_seconds=timeout_seconds,
            memory_mb=memory_mb,
            docker_bin=docker_bin,
        )
    return await run_in_sandbox_local(
        docker_bin=docker_bin,
        workspace_dir=workspace_dir,
        base_image=base_image,
        command=command,
        timeout_seconds=timeout_seconds,
        memory_mb=memory_mb,
    )


async def check_docker_available(docker_bin: str = "docker") -> bool:
    """Return whether a usable Docker daemon is reachable.

    Callers must degrade to a recorded ``DRY_RUN``/skipped result when this is
    false — never to "passed".
    """
    remote = sandbox_executor_url()
    if remote:
        request = urllib.request.Request(
            f"{remote}/internal/sandbox/health",
            method="GET",
            headers={"Authorization": _sandbox_auth_header()},
        )

        def _probe() -> bool:
            try:
                with urllib.request.urlopen(request, timeout=10.0) as response:  # nosec B310
                    return 200 <= int(response.status) < 300
            except (urllib.error.URLError, TimeoutError, OSError):
                return False

        return await asyncio.to_thread(_probe)
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
