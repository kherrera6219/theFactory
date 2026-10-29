#!/usr/bin/env python3
"""
preload_desktop_images.py

Standalone image pre-warming and local cache manager for theFactory Desktop Application.
Pre-pulls, builds, verifies, and retags all container images required by the desktop stack
to eliminate first-launch multi-gigabyte download friction.

Usage:
    python scripts/preload_desktop_images.py --check
    python scripts/preload_desktop_images.py --tag v0.1.0
    python scripts/preload_desktop_images.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

DEFAULT_REGISTRY = "ghcr.io/kherrera6219"
DEFAULT_TAG = "v0.1.0"

SERVICE_IMAGES = [
    "orchestrator",
    "api-gateway",
    "protocol-bus-mcp",
    "dashboard",
    "pod-worker",
    "audit-worker",
    "mission-control",
]

SANDBOX_IMAGES: list[tuple[str, str]] = [
    ("sandbox-test-python", "thefactory/sandbox-test-python:1"),
    ("sandbox-test-java", "thefactory/sandbox-test-java:1"),
    ("sandbox-test-kotlin", "thefactory/sandbox-test-kotlin:1"),
    ("sandbox-test-scala", "thefactory/sandbox-test-scala:1"),
    ("sandbox-test-php", "thefactory/sandbox-test-php:1"),
    ("sandbox-test-r", "thefactory/sandbox-test-r:1"),
    ("sandbox-test-node", "thefactory/sandbox-test-node:1"),
    ("sandbox-csharp", "thefactory/sandbox-csharp:1"),
]


@dataclass
class ImageStatus:
    name: str
    published: str
    target_tag: str
    cached: bool
    source_tag: str = ""
    size_mb: float = 0.0


def detect_app_version(repo_root: Path) -> str:
    """Detect current app version from apps/mission-control/package.json."""
    pkg_json = repo_root / "apps" / "mission-control" / "package.json"
    if pkg_json.is_file():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            ver = str(data.get("version", "")).strip()
            if ver:
                return f"v{ver.lstrip('v')}"
        except Exception:
            pass
    return DEFAULT_TAG


def run_command(cmd: Sequence[str], dry_run: bool = False) -> tuple[int, str]:
    """Execute command and return returncode and captured output."""
    if dry_run:
        return 0, f"[DRY-RUN] {' '.join(cmd)}"
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout


def check_docker_available() -> bool:
    """Verify that docker CLI is available and docker daemon is responding."""
    if not shutil.which("docker"):
        return False
    ret, _ = run_command(["docker", "version", "--format", "{{.Server.Version}}"])
    return ret == 0


def inspect_image(image_ref: str) -> tuple[bool, float]:
    """Inspect image existence and size in megabytes."""
    ret, out = run_command(["docker", "image", "inspect", "--format", "{{.Size}}", image_ref])
    if ret == 0 and out.strip().isdigit():
        size_bytes = int(out.strip())
        return True, round(size_bytes / (1024 * 1024), 1)
    return False, 0.0


def resolve_local_candidate(published: str, local_name: str, tag: str) -> str | None:
    """Check if a local/pre-warmed equivalent of an image already exists in Docker Desktop."""
    candidates = [
        published,
        local_name,
        f"{local_name}:{tag}",
        f"{local_name}:latest",
        f"deploy-{local_name}:latest",
        f"thefactory-{local_name}:{tag}",
        f"thefactory-{local_name}:latest",
    ]
    for cand in candidates:
        if cand:
            cached, _ = inspect_image(cand)
            if cached:
                return cand
    return None


def get_all_target_images(registry: str, tag: str) -> list[tuple[str, str, str]]:
    """Return list of (short_name, published_tag, local_canonical_tag)."""
    targets: list[tuple[str, str, str]] = []
    clean_reg = registry.rstrip("/")
    for svc in SERVICE_IMAGES:
        pub = f"{clean_reg}/thefactory-{svc}:{tag}"
        targets.append((svc, pub, pub))
    for short, local in SANDBOX_IMAGES:
        pub = f"{clean_reg}/thefactory-{short}:{tag}"
        targets.append((short, pub, local))
    return targets


def parse_pull_throughput(line: str) -> tuple[float, float] | None:
    """Parse downloading lines like '12.3MB/114.2MB' into (curr_mb, total_mb)."""
    m = re.search(r"([\d.]+)\s*([a-zA-Z]+)\s*/\s*([\d.]+)\s*([a-zA-Z]+)", line)
    if not m:
        return None
    curr, u1, tot, u2 = float(m.group(1)), m.group(2).upper(), float(m.group(3)), m.group(4).upper()
    mults = {"B": 1 / (1024 * 1024), "KB": 1 / 1024, "MB": 1.0, "GB": 1024.0}
    curr_mb = curr * mults.get(u1, 1.0)
    tot_mb = tot * mults.get(u2, 1.0)
    return curr_mb, tot_mb


def pull_with_progress(image_ref: str, dry_run: bool = False) -> bool:
    """Pull image with real-time throughput tracking."""
    if dry_run:
        print(f"  [DRY-RUN] docker pull {image_ref}")
        return True

    t0 = time.time()
    last_mb = 0.0
    last_t = t0

    proc = subprocess.Popen(
        ["docker", "pull", image_ref],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.stdout is not None
    for raw_line in proc.stdout:
        line = raw_line.strip()
        parsed = parse_pull_throughput(line)
        if parsed:
            curr_mb, tot_mb = parsed
            now = time.time()
            dt = now - last_t
            if dt >= 0.5:
                speed_mb_s = (curr_mb - last_mb) / dt if dt > 0 and curr_mb >= last_mb else 0.0
                pct = (curr_mb / tot_mb * 100) if tot_mb > 0 else 0
                print(
                    f"\r    -> {curr_mb:.1f} MB / {tot_mb:.1f} MB ({pct:.0f}%) - {speed_mb_s:.1f} MB/s",
                    end="",
                    flush=True,
                )
                last_mb = curr_mb
                last_t = now
        elif any(k in line.lower() for k in ("pull complete", "downloaded newer", "digest")):
            print(f"\n    {line}")

    ret = proc.wait()
    print()
    return ret == 0


def preload_images(
    registry: str = DEFAULT_REGISTRY,
    tag: str = DEFAULT_TAG,
    check_only: bool = False,
    dry_run: bool = False,
) -> int:
    """Preload, verify, and retag all required desktop images."""
    print("=" * 72)
    print(" theFactory — Desktop Image Pre-Warming & Cache Manager")
    print(f" Registry: {registry} | Tag: {tag}")
    print("=" * 72)

    if not check_only and not dry_run and not check_docker_available():
        print("ERROR: Docker is not running or not installed.")
        return 1

    targets = get_all_target_images(registry, tag)
    statuses: list[ImageStatus] = []

    print("\nScanning local Docker cache...")
    for short, pub, local in targets:
        cand = resolve_local_candidate(pub, short, tag)
        if cand:
            _, size_mb = inspect_image(cand)
            statuses.append(ImageStatus(name=short, published=pub, target_tag=local, cached=True, source_tag=cand, size_mb=size_mb))
        else:
            statuses.append(ImageStatus(name=short, published=pub, target_tag=local, cached=False))

    cached_count = sum(1 for s in statuses if s.cached)
    total_count = len(statuses)
    print(f"Cache status: {cached_count}/{total_count} images available locally.\n")

    if check_only:
        print(f"{'Image':<24} {'Status':<12} {'Size':<10} {'Source / Target Tag'}")
        print("-" * 72)
        for s in statuses:
            st = "CACHED" if s.cached else "MISSING"
            sz = f"{s.size_mb:.1f} MB" if s.cached else "-"
            ref = s.source_tag if s.cached else s.published
            print(f"{s.name:<24} {st:<12} {sz:<10} {ref}")
        print("-" * 72)
        return 0 if cached_count == total_count else 2

    # Pull or retag missing
    for idx, s in enumerate(statuses, 1):
        if s.cached:
            print(f"[{idx}/{total_count}] {s.name}: Pre-cached locally ({s.source_tag})")
            if s.source_tag != s.target_tag:
                run_command(["docker", "tag", s.source_tag, s.target_tag], dry_run=dry_run)
            if s.target_tag != s.published:
                run_command(["docker", "tag", s.source_tag, s.published], dry_run=dry_run)
            continue

        print(f"[{idx}/{total_count}] {s.name}: Pulling {s.published}...")
        ok = pull_with_progress(s.published, dry_run=dry_run)
        if not ok:
            print(f"  FAILED to pull {s.published}.")
            return 1

        # Retag sandbox image to QC expected local name
        if s.target_tag != s.published:
            run_command(["docker", "tag", s.published, s.target_tag], dry_run=dry_run)

    print("\nAll container images successfully pre-warmed and tagged for theFactory Desktop!")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pre-warm container images for theFactory Desktop.")
    repo_root = Path(__file__).resolve().parent.parent
    default_detected_tag = detect_app_version(repo_root)

    parser.add_argument("--registry", default=DEFAULT_REGISTRY, help="Container registry URL")
    parser.add_argument("--tag", default=default_detected_tag, help="Image version tag")
    parser.add_argument("--check", action="store_true", help="Check local cache status without pulling")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without downloading")

    args = parser.parse_args(argv)
    return preload_images(
        registry=args.registry,
        tag=args.tag,
        check_only=args.check,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
