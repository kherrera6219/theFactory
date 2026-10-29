#!/usr/bin/env python3
"""
manage_topology.py — Dynamic Deployment Topology Orchestrator for theFactory.

Provides one-command automated scaling and seamless switching between:
  1. Condensed Mode: Shared pod workers, condensed containers, synthesized heartbeats.
  2. Dedicated Mode: 41 isolated per-language and per-role agent containers.

Guarantees 100% data preservation by never removing or wiping volumes.

Usage:
    python scripts/manage_topology.py --status
    python scripts/manage_topology.py --mode condensed
    python scripts/manage_topology.py --mode dedicated
    python scripts/manage_topology.py --mode dedicated --dry-run
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_DIR = REPO_ROOT / "deploy"
BASE_COMPOSE = DEPLOY_DIR / "docker-compose.yaml"
OVERLAY_COMPOSE = DEPLOY_DIR / "docker-compose.full-dedicated-agents.yaml"
ENV_FILE = REPO_ROOT / ".env"

try:
    from scripts.compose_topology import (
        CONDENSED,
        FULL_DEDICATED,
        NONE,
        current_topology,
    )
except ImportError:
    # Fallback definitions if running standalone
    CONDENSED = "condensed"
    FULL_DEDICATED = "full-dedicated"
    NONE = "none"

    def current_topology(_docker_bin: str = "docker") -> str:
        return CONDENSED


def check_docker_available(docker_bin: str = "docker") -> bool:
    """Verify docker CLI is reachable."""
    if not shutil.which(docker_bin):
        return False
    try:
        res = subprocess.run([docker_bin, "version"], capture_output=True, timeout=5, check=False)
        return res.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def run_command(cmd: Sequence[str], dry_run: bool = False) -> tuple[int, str]:
    """Execute command safely and capture output."""
    if dry_run:
        print(f"  [DRY-RUN] {' '.join(cmd)}")
        return 0, "[DRY-RUN]"
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout


def update_env_autofill(autofill_enabled: bool, env_path: Path = ENV_FILE, dry_run: bool = False) -> None:
    """Update AGENT_AUTOFILL_NON_POD_HEARTBEATS in .env without rewriting other settings."""
    val = "true" if autofill_enabled else "false"
    if not env_path.is_file():
        if not dry_run:
            env_path.write_text(f"AGENT_AUTOFILL_NON_POD_HEARTBEATS={val}\n", encoding="utf-8")
        return

    text = env_path.read_text(encoding="utf-8")
    key = "AGENT_AUTOFILL_NON_POD_HEARTBEATS="
    if key in text:
        lines = []
        for line in text.splitlines():
            if line.strip().startswith(key):
                lines.append(f"{key}{val}")
            else:
                lines.append(line)
        new_text = "\n".join(lines) + "\n"
    else:
        new_text = text.rstrip() + f"\n{key}{val}\n"

    if dry_run:
        print(f"  [DRY-RUN] Update .env: AGENT_AUTOFILL_NON_POD_HEARTBEATS={val}")
    else:
        env_path.write_text(new_text, encoding="utf-8")


def get_topology_status(docker_bin: str = "docker") -> dict[str, str | int]:
    """Get diagnostic state of current deployment topology."""
    active_topo = current_topology(docker_bin)
    # Count running containers in project
    res = subprocess.run(
        [docker_bin, "ps", "--filter", "label=com.docker.compose.project=deploy", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    running_names = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    return {
        "topology": active_topo,
        "running_containers": len(running_names),
        "mode_label": "Dedicated (41 Containers)" if active_topo == FULL_DEDICATED else ("Condensed (Shared Pods)" if active_topo == CONDENSED else "Stopped"),
    }


def switch_topology(
    target_mode: str,
    *,
    dry_run: bool = False,
    no_build: bool = False,
    docker_bin: str = "docker",
) -> int:
    """Seamlessly switch between condensed and dedicated topology."""
    normalized_mode = "dedicated" if target_mode in ("dedicated", "full-dedicated", FULL_DEDICATED) else "condensed"
    print("=" * 72)
    print(" theFactory — Deployment Topology Orchestrator")
    print(f" Target Mode: {normalized_mode.upper()} | Dry-Run: {dry_run}")
    print("=" * 72)

    if not dry_run and not check_docker_available(docker_bin):
        print("ERROR: Docker daemon is not running or docker CLI is unavailable.")
        return 1

    current = current_topology(docker_bin)
    print(f"Current detected topology: {current}")

    if (normalized_mode == "condensed" and current == CONDENSED) or (normalized_mode == "dedicated" and current == FULL_DEDICATED):
        print(f"Already operating in {normalized_mode} mode. No topology change required.")
        return 0

    build_flag = ["--no-build"] if no_build else []

    if normalized_mode == "condensed":
        print("\nSwitching to CONDENSED mode (Shared Pod Workers)...")
        print("1. Updating environment configuration...")
        update_env_autofill(autofill_enabled=True, dry_run=dry_run)

        print("2. Starting condensed stack and cleaning orphan agent containers...")
        condensed_cmd = [
            docker_bin,
            "compose",
            "--env-file",
            str(ENV_FILE),
            "-f",
            str(BASE_COMPOSE),
            "up",
            "-d",
            "--remove-orphans",
            *build_flag,
        ]
        ret, out = run_command(condensed_cmd, dry_run=dry_run)
        if ret != 0:
            print(f"ERROR: Failed to switch to condensed stack:\n{out}")
            return ret

    else:
        print("\nSwitching to FULL DEDICATED mode (41 Dedicated Agent Containers)...")
        print("1. Updating environment configuration...")
        update_env_autofill(autofill_enabled=False, dry_run=dry_run)

        print("2. Launching full-dedicated agent overlay stack...")
        dedicated_cmd = [
            docker_bin,
            "compose",
            "--env-file",
            str(ENV_FILE),
            "-f",
            str(BASE_COMPOSE),
            "-f",
            str(OVERLAY_COMPOSE),
            "--profile",
            "full-dedicated-agents",
            "up",
            "-d",
            *build_flag,
        ]
        ret, out = run_command(dedicated_cmd, dry_run=dry_run)
        if ret != 0:
            print(f"ERROR: Failed to switch to dedicated stack:\n{out}")
            return ret

    print(f"\nSuccessfully transitioned topology to: {normalized_mode.upper()}")
    print("All PostgreSQL mission databases, Redis queues, and knowledge stores preserved intact.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage theFactory deployment topologies.")
    parser.add_argument(
        "--mode",
        choices=["condensed", "dedicated"],
        help="Target topology mode: 'condensed' (lightweight) or 'dedicated' (41 isolated agents)",
    )
    parser.add_argument("--status", action="store_true", help="Print current topology status and container count")
    parser.add_argument("--dry-run", action="store_true", help="Show orchestration steps without mutating containers")
    parser.add_argument("--no-build", action="store_true", help="Skip container build step during stack startup")

    args = parser.parse_args(argv)

    if args.status or not args.mode:
        status = get_topology_status()
        print(f"Current Topology: {status['mode_label']} ({status['topology']})")
        print(f"Running Project Containers: {status['running_containers']}")
        if not args.mode:
            return 0

    return switch_topology(
        target_mode=args.mode,
        dry_run=args.dry_run,
        no_build=args.no_build,
    )


if __name__ == "__main__":
    sys.exit(main())
