"""Stop theFactory stack and clear lingering local port bindings.

**Volumes are preserved by default.** This script previously ran
``docker compose down -v`` unconditionally, which removes every named volume —
``postgres-data``, ``redis-data``, ``qdrant-data``, ``neo4j-data``,
``minio-data``, ``milvus-data``, and ``mission-control-vault``. That meant an
ordinary "stop the app" destroyed the mission database, every knowledge store,
and the operator's stored provider credentials. It wiped the database at least
once in practice (2026-06-30), which is how the behaviour was discovered.

Pass ``--wipe-volumes`` to opt in to the destructive teardown. This mirrors the
dry-run-by-default convention already applied to every other destructive script
in this repository.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time


def run_cmd(cmd):
    try:
        # Using subprocess.run for better control
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)  # nosec B602
        return result.stdout
    except Exception:
        return ""

def _is_full_dedicated_running():
    # agent-01-pm only ever exists under the full-dedicated-agents profile
    # (deploy/docker-compose.full-dedicated-agents.yaml) — its presence is a
    # reliable signal that this deployment is running the paired-file
    # topology rather than condensed (base file alone).
    output = run_cmd("docker ps --format \"{{.Names}}\"")
    return any("agent-01-pm" in line for line in output.splitlines())

def kill_port(port):
    print(f"Checking port {port}...")
    # Specifically look for LISTENING state on the port
    output = run_cmd("netstat -aon | findstr LISTENING")
    pids = set()
    for line in output.splitlines():
        if f":{port}" in line:
            parts = line.strip().split()
            if len(parts) > 4:
                pids.add(parts[-1])
    
    for pid in pids:
        print(f"Force-terminating PID {pid} (holding port {port})...")
        subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)  # nosec B602

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stop theFactory stack and clear local port bindings. "
            "Volumes are PRESERVED unless --wipe-volumes is passed."
        )
    )
    parser.add_argument(
        "--wipe-volumes",
        action="store_true",
        help=(
            "Also delete every named volume: the mission database, Redis, Qdrant, "
            "Neo4j, MinIO, Milvus, and the operator vault (stored provider API "
            "keys). Irreversible."
        ),
    )
    return parser.parse_args(argv)


def build_teardown_commands(*, full_dedicated: bool, wipe_volumes: bool) -> tuple[str, str]:
    """Return ``(make_target, fallback_cmd)`` for the detected topology.

    Topology detection matters independently of the volume question: tearing
    down a condensed (base-file-only) deployment with the full-dedicated
    paired-file form, or vice versa, silently mismatches the running containers'
    actual compose config.
    """
    volume_flag = " -v" if wipe_volumes else ""
    wipe_suffix = "-wipe" if wipe_volumes else ""
    if full_dedicated:
        make_target = f"make down-full-dedicated{wipe_suffix}"
        fallback_cmd = (
            "docker compose --env-file .env -f deploy/docker-compose.yaml "
            "-f deploy/docker-compose.full-dedicated-agents.yaml "
            f"--profile full-dedicated-agents down{volume_flag}"
        )
    else:
        make_target = f"make down-condensed{wipe_suffix}"
        fallback_cmd = (
            "docker compose --env-file .env -f deploy/docker-compose.yaml "
            f"down{volume_flag}"
        )
    return make_target, fallback_cmd


def main(argv: list[str] | None = None):
    args = parse_args(argv)

    print("==============================================")
    print("   theFactory Thorough Cleanup System")
    print("==============================================\n")

    # 1. Orchestrated Docker Shutdown
    print("[1/3] Tearing down Docker backend...")
    full_dedicated = _is_full_dedicated_running()
    if full_dedicated:
        print("Detected full-dedicated-agent topology running.")
    else:
        print("Detected condensed topology (or nothing running) — using condensed teardown.")

    if args.wipe_volumes:
        print(
            "\n  *** --wipe-volumes: DELETING the mission database, knowledge\n"
            "  *** stores, and the operator vault (provider API keys). Irreversible.\n"
        )
    else:
        print("Volumes will be PRESERVED (pass --wipe-volumes to delete them).")

    make_target, fallback_cmd = build_teardown_commands(
        full_dedicated=full_dedicated, wipe_volumes=args.wipe_volumes
    )

    import shutil

    # Try matching 'make' target first if make is installed, otherwise fallback to direct docker compose.
    if shutil.which("make"):
        try:
            res = subprocess.run(shlex.split(make_target), check=False)  # nosec B602 B603
            if res.returncode != 0:
                print("Fallback: Using direct docker compose down...")
                subprocess.run(shlex.split(fallback_cmd), check=False)  # nosec B602 B603
        except FileNotFoundError:
            print("Fallback: Using direct docker compose down...")
            subprocess.run(shlex.split(fallback_cmd), check=False)  # nosec B602 B603
    else:
        print("GNU Make not found on PATH — using direct docker compose down...")
        subprocess.run(shlex.split(fallback_cmd), check=False)  # nosec B602 B603


    
    # 2. Aggressive Port Cleanup
    print("\n[2/3] Cleaning up lingering local processes and port bindings...")
    # Essential ports: 3000 (Local UI), 3100 (Docker UI), 8100-8102 (APIs), 8180 (Dashboard)
    target_ports = [3000, 3100, 8100, 8101, 8102, 8180]
    for port in target_ports:
        kill_port(port)
    
    # 3. Final Verification and Sweep
    print("\n[3/3] Final Verification...")
    time.sleep(1) # Give OS a moment to release sockets
    failed_ports = []
    for port in target_ports:
        output = run_cmd("netstat -aon | findstr LISTENING")
        is_active = False
        for line in output.splitlines():
            if f":{port}" in line:
                is_active = True
                break
        
        if is_active:
            print(f"  [X] Port {port} is STILL ACTIVE")
            failed_ports.append(port)
        else:
            print(f"  [OK] Port {port} is clear")
            
    if failed_ports:
        print(f"\nCleanup finished with warnings. Ports {failed_ports} could not be cleared.")
        print("You may need to close the related command windows manually.")
        sys.exit(1)
    else:
        print("\nSUCCESS: theFactory stack is stopped and local ports are clear.")
        if args.wipe_volumes:
            print("All named volumes were DELETED — the next start begins from empty stores.")
        else:
            print("Volumes preserved: missions, knowledge stores, and the vault are intact.")
        print("You can now safely run start_app.bat.")


if __name__ == "__main__":
    main()
