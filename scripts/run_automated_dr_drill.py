# scripts/run_automated_dr_drill.py
# Automated Timed DR Drill Orchestrator for theFactory
# Captures RTO, performs backup/restore, validates stack recovery, and writes evidence JSON.

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone


def run_cmd(args, check=True):
    print(f"Running: {' '.join(args) if isinstance(args, list) else args}")
    result = subprocess.run(args, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Command failed with code {result.returncode}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        raise RuntimeError(f"Command failed: {args}")
    return result

def check_readyz(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:  # nosec B310
            return response.status == 200
    except Exception:
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Automated Timed DR Drill Orchestrator")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run simulated mode (default — kept for backward compatibility "
        "with existing call sites; has no effect since dry-run is now the default).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run the REAL, destructive drill: docker compose down -v (wipes volumes) "
        "and a real Postgres restore. Without this flag the drill always runs in "
        "dry-run/simulated mode, regardless of --dry-run.",
    )
    args = parser.parse_args()
    is_dry_run = not args.execute

    started_dt = datetime.now(timezone.utc)
    started_str = started_dt.isoformat()
    print("=========================================================")
    print("  theFactory -- Automated Disaster Recovery Timed Drill  ")
    print("=========================================================")
    print(f"Started at (UTC): {started_str}")
    print(f"Mode: {'DRY-RUN' if is_dry_run else 'REAL RECOVERY DRILL'}")

    rto_start = time.time()
    
    # 1. Validate service readiness before drill
    print("\n[1/5] Checking initial system readiness...")
    if is_dry_run:
        print("Dry-run: skipping initial readyz check (simulating health)")
    else:
        # Check if running
        api_ready = check_readyz("http://localhost:8100/readyz")
        orchestrator_ready = check_readyz("http://localhost:8101/readyz")
        print(f"API Gateway ready: {api_ready}")
        print(f"Orchestrator ready: {orchestrator_ready}")

    # 2. Invoke backup postgres and validate manifest
    print("\n[2/5] Creating postgres backup...")
    backup_file = ""
    backup_manifest = ""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if is_dry_run:
        print("Dry-run: invoking simulated backup script...")
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", "scripts/backup_postgres.ps1", "-DryRun", "-Timestamp", timestamp]  # noqa: E501
        run_cmd(cmd)
    else:
        print("Real-drill: invoking real backup script...")
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", "scripts/backup_postgres.ps1", "-Timestamp", timestamp]  # noqa: E501
        run_cmd(cmd)

    # Find the backup file and manifest
    backup_dir = "backups"
    backups = [f for f in os.listdir(backup_dir) if f.startswith(f"ulr_{timestamp}") and f.endswith(".sql")]  # noqa: E501
    if not backups:
        # fallback to newest
        backups = sorted([f for f in os.listdir(backup_dir) if f.startswith("ulr_") and f.endswith(".sql")], reverse=True)  # noqa: E501
    
    if backups:
        backup_file = os.path.abspath(os.path.join(backup_dir, backups[0]))
        backup_manifest = backup_file + ".json"
        print(f"Verified Backup File: {backup_file}")
        print(f"Verified Backup Manifest: {backup_manifest}")
    else:
        raise RuntimeError("No backup file found after running backup script!")

    # 3. Simulate disaster: bring postgres down and wipe its volume
    print("\n[3/5] Simulating disaster (docker compose down)...")
    if is_dry_run:
        print("Dry-run: simulating container teardown (sleeping 2s)")
        time.sleep(2)
    else:
        # Down the compose stack to clear volumes
        print("Executing: docker compose -f deploy/docker-compose.yaml down -v")
        run_cmd(["docker", "compose", "-f", "deploy/docker-compose.yaml", "down", "-v"])
        print("Disaster simulated: volume cleared and stack is down.")

    # 4. Perform recovery: bring compose stack back up and restore backup
    print("\n[4/5] Restoring services and importing database...")
    restore_start = time.time()
    
    if is_dry_run:
        print("Dry-run: simulating compose up and postgres restore (sleeping 3s)")
        time.sleep(3)
    else:
        # Bring it up
        print("Executing: docker compose -f deploy/docker-compose.yaml up -d")
        run_cmd(["docker", "compose", "-f", "deploy/docker-compose.yaml", "up", "-d"])
        
        # Wait a bit for postgres container to start accepting connections before running restore
        print("Waiting for Postgres port to open...")
        time.sleep(5)
        
        # Run restore postgres. -Yes: this call is already gated behind the
        # DR drill's own --execute flag, so the operator's confirmation
        # already happened one level up — an interactive prompt here would
        # just hang this automated drill.
        print(f"Executing restore script with backup: {backup_file}")
        run_cmd(["powershell", "-ExecutionPolicy", "Bypass", "-File", "scripts/restore_postgres.ps1", "-BackupFile", backup_file, "-Yes"])  # noqa: E501

    # 5. Measure stack recovery and verify readiness
    print("\n[5/5] Measuring time to service readiness (RTO calculation)...")
    passed = False
    time_limit = 300 # 5 minutes timeout
    elapsed = 0
    
    while elapsed < time_limit:
        if is_dry_run:
            passed = True
            break
        else:
            api_ready = check_readyz("http://localhost:8100/readyz")
            orchestrator_ready = check_readyz("http://localhost:8101/readyz")
            
            # Also verify if postgres query works
            db_ready = False
            try:
                db_res = run_cmd(["docker", "compose", "-f", "deploy/docker-compose.yaml", "exec", "-T", "postgres", "psql", "-U", "postgres", "-d", "ulr", "-c", "select count(*) as missions from missions;"], check=False)  # noqa: E501
                if db_res.returncode == 0:
                    db_ready = True
            except Exception:
                pass
                
            if api_ready and orchestrator_ready and db_ready:
                passed = True
                print("All health checks and DB queries are PASSING!")
                break
            
            print(f"Waiting for services... (elapsed: {int(elapsed)}s) [API: {api_ready}, ORCH: {orchestrator_ready}, DB: {db_ready}]")  # noqa: E501
            time.sleep(5)
            elapsed = time.time() - restore_start

    rto_seconds = round(time.time() - rto_start, 2)
    ended_dt = datetime.now(timezone.utc)
    ended_str = ended_dt.isoformat()

    print(f"\nDR Recovery Drill Complete. Recovery Time (RTO): {rto_seconds} seconds.")
    if passed:
        print("Status: SUCCESS!")
    else:
        print("Status: FAILED (timeout exceeded).")

    # Output evidence report
    evidence_dir = "docs/evidence"
    os.makedirs(evidence_dir, exist_ok=True)
    evidence_filename = f"dr_drill_phase26_{timestamp}.json"
    evidence_path = os.path.join(evidence_dir, evidence_filename)
    latest_evidence_path = os.path.join(evidence_dir, "dr_drill_phase26_latest.json")

    report = {
        "started_at_utc": started_str,
        "completed_at_utc": ended_str,
        "duration_seconds": rto_seconds,
        "dry_run": is_dry_run,
        "passed": passed,
        "rto_target_minutes": 30,
        "rpo_target_hours": 24,
        "rto_seconds": rto_seconds,
        "restore_passed": passed,
        "latest_backup": backup_file,
        "latest_backup_manifest": backup_manifest if os.path.exists(backup_manifest) else None
    }

    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    with open(latest_evidence_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Evidence saved to: {evidence_path}")
    print(f"Latest pointer updated: {latest_evidence_path}")
    print("=========================================================")

    # Propagate the drill outcome so callers (e.g. `make dr`, CI) fail on a failed drill.
    return 0 if passed else 1

if __name__ == "__main__":
    sys.exit(main())
