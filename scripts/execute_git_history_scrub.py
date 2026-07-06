# execute_git_history_scrub.py - Staged Git history scrub for theFactory
# This script scrubs local TLS key commits locally to preserve safety.
# DO NOT FORCE PUSH to remote origin until Claude Code has finished Phase 25.
#
# This is a one-shot, project-history script kept for reference/re-run in a
# fresh clone only. It rewrites git history, which is irreversible outside a
# backup. Defaults to dry-run; pass --execute to actually rewrite history.
# --force is never passed to git-filter-repo, so its own built-in safety
# check (refuse to run outside a pristine fresh clone) stays active.

import argparse
import os
import shutil
import subprocess
import sys


def run_cmd(args, check=True):
    print(f"Running: {' '.join(args)}")
    result = subprocess.run(args, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error executing command: {' '.join(args)}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        sys.exit(result.returncode)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Staged git history TLS-key scrub (destructive, one-shot)."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually rewrite git history. Without this flag (the default), prints "
        "the exact git-filter-repo commands that would run and exits without "
        "touching the repository.",
    )
    args = parser.parse_args()

    print("=========================================================")
    print("  theFactory -- Staged Git History TLS Key Scrubbing      ")
    print("=========================================================")

    # 1. Check if git repository
    if not os.path.exists(".git"):
        print("Error: This script must be executed from the root of a git repository.")
        sys.exit(1)

    filter_commands = [
        ["git", "filter-repo", "--path", "deploy/postgres/certs/server.key", "--invert-paths"],
        ["git", "filter-repo", "--path", "deploy/redis/certs/redis.key", "--invert-paths"],
    ]

    if not args.execute:
        print("\nDRY-RUN: would run the following history-rewriting commands:")
        for cmd in filter_commands:
            print(f"  {' '.join(cmd)}")
        print(
            "\nDRY-RUN: would then verify no commits reference "
            "deploy/postgres/certs/server.key or deploy/redis/certs/redis.key"
        )
        print("DRY-RUN: would then regenerate fresh local dev certs ('make tls-certs')")
        print(
            "\nNo --force is passed to git-filter-repo, so its own built-in safety "
            "check (refuse to run outside a pristine fresh clone) stays active even "
            "with --execute — this script cannot bypass that guarantee."
        )
        print("Pass --execute to actually rewrite history.")
        return

    # 2. Check if git-filter-repo is available, with dynamic PATH detection for Python user scripts
    import site
    user_site = site.getusersitepackages()
    user_scripts = os.path.join(os.path.dirname(user_site), "Scripts")
    sys_scripts = os.path.join(sys.prefix, "Scripts")

    for path_dir in [user_scripts, sys_scripts]:
        if os.path.exists(path_dir) and path_dir not in os.environ["PATH"]:
            os.environ["PATH"] = path_dir + os.pathsep + os.environ["PATH"]

    if not shutil.which("git-filter-repo"):
        print("git-filter-repo not found on Path. Attempting to install via pip...")
        run_cmd([sys.executable, "-m", "pip", "install", "git-filter-repo"])

        # Re-verify and update PATH again
        user_site = site.getusersitepackages()
        user_scripts = os.path.join(os.path.dirname(user_site), "Scripts")
        for path_dir in [user_scripts, sys_scripts]:
            if os.path.exists(path_dir) and path_dir not in os.environ["PATH"]:
                os.environ["PATH"] = path_dir + os.pathsep + os.environ["PATH"]

        if not shutil.which("git-filter-repo"):
            print("Error: git-filter-repo is required. Please install it ('pip install git-filter-repo') and ensure python scripts are in your Path.")  # noqa: E501
            sys.exit(1)

    print("\n[1/3] Executing git filter-repo to scrub TLS keys locally...")
    # git-filter-repo's own default behavior refuses to run outside a fresh
    # clone (no --force here) — that check is the real backup guarantee.
    for cmd in filter_commands:
        run_cmd(cmd)

    print("\n[2/3] Verifying clean local git log...")
    postgres_log = run_cmd(["git", "log", "--all", "--", "deploy/postgres/certs/server.key"]).stdout.strip()  # noqa: E501
    redis_log = run_cmd(["git", "log", "--all", "--", "deploy/redis/certs/redis.key"]).stdout.strip()  # noqa: E501

    if not postgres_log and not redis_log:
        print("[PASS] Verification PASS: No commits trace deploy/postgres/certs/server.key or deploy/redis/certs/redis.key in history.")  # noqa: E501
    else:
        print("Verification failed! Commits were still found in git history.")
        if postgres_log:
            print(f"Postgres commits:\n{postgres_log}")
        if redis_log:
            print(f"Redis commits:\n{redis_log}")
        sys.exit(1)

    print("\n[3/3] Regenerating fresh local development certs...")
    # Restore local development certificates using make target
    # On Windows, we try running make if available, or fall back to local python scripts if make is absent  # noqa: E501
    if shutil.which("make"):
        run_cmd(["make", "tls-certs"])
    else:
        # Fallback to direct python script if make is not in PATH
        print("make not found in PATH. Attempting to run python certs generation directly...")
        if os.path.exists("scripts/generate_certs.py"):
            run_cmd([sys.executable, "scripts/generate_certs.py"])
        else:
            print("Warning: could not restore dev certs directly. Please run 'make tls-certs' manually.")  # noqa: E501

    print("\n=========================================================")
    print("  Scrub Complete (Staged Locally)                        ")
    print("  DO NOT run 'git push --force' until Phase 25 merges!   ")
    print("=========================================================")

if __name__ == "__main__":
    main()
