"""Detect the running compose topology and guard against mismatched commands.

theFactory ships two topologies:

* **condensed** — `deploy/docker-compose.yaml` alone. Shared pod workers,
  synthesized non-pod heartbeats. Self-contained and safe to run by itself.
* **full-dedicated** — that base file **plus**
  `deploy/docker-compose.full-dedicated-agents.yaml` and
  `--profile full-dedicated-agents`. The overlay is *additive*: it patches the
  base file's `orchestrator` service and adds 41 per-language agent containers.

Running a **mutating** command (`up`, `down`, `restart`, `create`) against the
base file alone while the full-dedicated overlay is active desyncs those 41
agent containers from the rest of the stack. That has caused a real incident.
Read-only commands (`ps`, `logs`, `config`) are unaffected.

`scripts/force_stop.py` already detects topology before tearing down.
`start_app.bat`, by contrast, chose its topology from a `--condensed` flag with
no reference to what was actually running — so starting with `--condensed`
against a live full-dedicated stack produced exactly the mismatch above. This
module closes that gap and gives both paths one implementation to share.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

# agent-01-pm exists only under the full-dedicated-agents profile, so its
# presence is a reliable signal of the paired-file topology.
_FULL_DEDICATED_SENTINEL = "agent-01-pm"

# Compose stamps every container it creates with the compose files that built
# it. That label is authoritative about topology in a way that a running-service
# census can never be — see `topology_from_config_files`.
_CONFIG_FILES_LABEL = "com.docker.compose.project.config_files"
_PROJECT_LABEL = "com.docker.compose.project"
# The compose files live in deploy/, so that is the project name; it is the same
# assumption the `deploy-` container-name prefix already encodes.
_COMPOSE_PROJECT = "deploy"
_OVERLAY_MARKER = "full-dedicated-agents"

CONDENSED = "condensed"
FULL_DEDICATED = "full-dedicated"
NONE = "none"


def _run_docker(docker_bin: str, args: list[str]) -> list[str]:
    try:
        result = subprocess.run(  # noqa: S603
            [docker_bin, *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _running_container_names(docker_bin: str = "docker") -> list[str]:
    return _run_docker(docker_bin, ["ps", "--format", "{{.Names}}"])


def _running_config_files(docker_bin: str = "docker") -> list[str]:
    """Return the compose-file label of each running container in our project.

    Filtered to our compose project, because every other compose project on the
    machine also carries this label — devonz and ukg both run here.
    """
    return _run_docker(
        docker_bin,
        [
            "ps",
            "--filter",
            f"label={_PROJECT_LABEL}={_COMPOSE_PROJECT}",
            "--format",
            f'{{{{.Label "{_CONFIG_FILES_LABEL}"}}}}',
        ],
    )


def topology_from_config_files(config_files: list[str]) -> str:
    """Derive topology from the compose files that created the containers.

    This is exact where a service census is only a guess. A census asks "is
    agent-01-pm up?", which conflates three different situations with a genuine
    condensed stack:

    * the stack is **mid-startup** and the agents have not been created yet
    * agent-01-pm has **crashed** or is restarting
    * the stack is **partially torn down**

    In all three the census answers "condensed", and the guard then refuses a
    legitimate full-dedicated start. The crashed case is the damaging one: it
    locks the operator out of restarting the very stack the guard protects,
    forcing a full `force_stop` to repair a single container. The mid-startup
    case was observed live on 2026-08-04.

    The label is written at container-creation time and does not depend on what
    happens to be running, so a single surviving container reports the truth.
    A *mixed* result means overlay-created containers are live alongside
    base-only ones, which is precisely the desync state worth flagging — so any
    overlay marker wins.
    """
    if not config_files:
        return NONE
    if any(_OVERLAY_MARKER in entry for entry in config_files):
        return FULL_DEDICATED
    return CONDENSED


def topology_from_container_names(container_names: list[str]) -> str:
    """Census-based fallback for when the compose labels are unavailable.

    Retained for containers not created by compose, and for docker versions
    that do not report the label. Carries the imprecision described in
    `topology_from_config_files`.
    """
    if not container_names:
        return NONE
    if any(_FULL_DEDICATED_SENTINEL in name for name in container_names):
        return FULL_DEDICATED
    # Containers are up but no dedicated agents — treat as condensed only if
    # something recognisably ours is running.
    if any("deploy-" in name or "orchestrator" in name for name in container_names):
        return CONDENSED
    return NONE


def detect_topology(
    container_names: list[str] | None = None,
    config_files: list[str] | None = None,
) -> str:
    """Return ``full-dedicated``, ``condensed``, or ``none``.

    ``none`` means nothing is running — any topology may be started, so no
    guard applies.

    Prefers the compose-file labels and falls back to a container-name census.
    Either input may be injected for testing; injecting *container_names* alone
    exercises the fallback path directly.
    """
    if config_files is not None:
        return topology_from_config_files(config_files)
    if container_names is not None:
        return topology_from_container_names(container_names)

    labelled = _running_config_files()
    if labelled:
        return topology_from_config_files(labelled)
    return topology_from_container_names(_running_container_names())


def check_mismatch(requested: str, running: str) -> str | None:
    """Return an explanatory message when *requested* conflicts with *running*.

    Returns ``None`` when the command is safe: nothing running, or the
    requested topology matches.
    """
    if running == NONE or requested == running:
        return None
    if running == FULL_DEDICATED and requested == CONDENSED:
        return (
            "A full-dedicated stack is currently running (agent-01-pm is up), but a "
            "CONDENSED start was requested.\n"
            "The condensed form uses deploy/docker-compose.yaml alone, which would "
            "desync the 41 dedicated agent containers from the rest of the stack.\n"
            "Use `make up` (or start_app.bat without --condensed), or stop the "
            "running stack first with `python scripts/force_stop.py`."
        )
    return (
        "A condensed stack is currently running, but a FULL-DEDICATED start was "
        "requested.\n"
        "Stop the running stack first with `python scripts/force_stop.py`, then "
        "start the topology you want."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--requested",
        choices=[CONDENSED, FULL_DEDICATED],
        help="Topology about to be started. Omit to only report what is running.",
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Report a mismatch but exit 0 instead of blocking.",
    )
    args = parser.parse_args(argv)

    running = detect_topology()
    print(f"Detected running topology: {running}")

    if running == FULL_DEDICATED:
        print("  up:   make up-full-dedicated")
        print("  down: make down-full-dedicated       (add -wipe to delete volumes)")
    elif running == CONDENSED:
        print("  up:   make up-condensed")
        print("  down: make down-condensed            (add -wipe to delete volumes)")

    if not args.requested:
        return 0

    message = check_mismatch(args.requested, running)
    if message is None:
        return 0

    print(f"\nCOMPOSE TOPOLOGY MISMATCH\n{message}", file=sys.stderr)
    return 0 if args.warn_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
