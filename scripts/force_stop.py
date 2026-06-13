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

def main():
    print("==============================================")
    print("   theFactory Thorough Cleanup System")
    print("==============================================\n")
    
    # 1. Orchestrated Docker Shutdown
    print("[1/3] Tearing down Docker backend...")
    # We try 'make down' first, which is the graceful path
    # If 'make' isn't in path, we use the direct docker-compose command
    res = subprocess.run("make down", shell=True)
    if res.returncode != 0:
        print("Fallback: Using direct docker compose down...")
        subprocess.run("docker compose --env-file .env -f deploy/docker-compose.yaml down -v", shell=True)
    
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
        print("\nSUCCESS: theFactory stack has been completely purged.")
        print("You can now safely run start_app.bat.")

if __name__ == "__main__":
    main()
