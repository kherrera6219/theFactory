"""The Windows installer runs `docker compose up --no-build` with no source tree.

Every service the base compose file builds from source must therefore be
replaced by a published image in deploy/docker-compose.installer.yaml, and the
release workflow must publish every image the installed app pulls -- otherwise
a user's first start fails trying to build or pull something that does not
exist.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "deploy" / "docker-compose.yaml"
OVERLAY = ROOT / "deploy" / "docker-compose.installer.yaml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
FACTORY_STACK = ROOT / "apps" / "mission-control" / "electron" / "factory-stack.ts"


def _services(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["services"]


def test_installer_overlay_replaces_every_build_context() -> None:
    base = _services(BASE)
    overlay = _services(OVERLAY)
    built = {
        name for name, spec in base.items()
        if "build" in spec and "sandbox-images" not in (spec.get("profiles") or [])
    }
    assert built, "expected services built from source in the base compose file"
    uncovered = sorted(built - {n for n, s in overlay.items() if s.get("image")})
    assert not uncovered, f"installer would try to build from source: {uncovered}"


def test_installer_images_are_pinned_to_the_app_release() -> None:
    for name, spec in _services(OVERLAY).items():
        image = spec["image"]
        assert image.endswith(":${FACTORY_IMAGE_TAG:-latest}"), (name, image)
        assert "thefactory-" in image


def test_release_publishes_every_image_the_installed_app_pulls() -> None:
    release = yaml.safe_load(RELEASE.read_text(encoding="utf-8"))
    matrix = release["jobs"]["publish-images"]["strategy"]["matrix"]["include"]
    published = {entry["service"] for entry in matrix}

    overlay_images = {
        re.search(r"/thefactory-([a-z0-9-]+):", spec["image"]).group(1)
        for spec in _services(OVERLAY).values()
    }
    stack_source = FACTORY_STACK.read_text(encoding="utf-8")
    sandbox = set(re.findall(r'published: "([a-z0-9-]+)"', stack_source))
    service = set(re.findall(r'^\s+"([a-z0-9-]+)",$', stack_source.split("SERVICE_IMAGES")[1]
                             .split("] as const")[0], re.MULTILINE))

    assert sandbox, "factory-stack.ts lists no sandbox images"
    missing = sorted((overlay_images | sandbox | service) - published)
    assert not missing, f"installed app would pull images the release never publishes: {missing}"


def test_sandbox_images_match_what_runtime_qc_runs() -> None:
    rqca = (ROOT / "services" / "orchestrator" / "orchestrator" / "rqca_agent.py").read_text(
        encoding="utf-8"
    )
    used = set(re.findall(r'"(thefactory/sandbox-[a-z0-9-]+:\d+)"', rqca))
    shipped = set(re.findall(r'local: "(thefactory/sandbox-[a-z0-9-]+:\d+)"',
                             FACTORY_STACK.read_text(encoding="utf-8")))
    assert used and used <= shipped, f"runtime QC needs images the installer never tags: {used - shipped}"
