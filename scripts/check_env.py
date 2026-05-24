import os
import sys
from pathlib import Path

def check_env():
    # Base path is the repository root (one level up from scripts/)
    repo_root = Path(__file__).resolve().parent.parent
    paths = [repo_root / '.env', repo_root / 'deploy' / '.env']
    
    found = False
    for p in paths:
        if p.exists():
            found = True
            with open(p, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'CHANGE_ME' in content:
                    print(f"ERROR: Unset CHANGE_ME values in {p}")
                    sys.exit(1)
    
    if not found:
        # Check current working directory as fallback
        cwd_env = Path('.env')
        if cwd_env.exists():
             with open(cwd_env, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'CHANGE_ME' in content:
                    print(f"ERROR: Unset CHANGE_ME values in .env (CWD)")
                    sys.exit(1)
             found = True

    if not found:
        print("WARNING: No .env file found in repo root or deploy/. Proceeding with defaults.")

if __name__ == "__main__":
    check_env()
