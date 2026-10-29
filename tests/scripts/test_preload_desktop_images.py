"""
test_preload_desktop_images.py

Unit tests for standalone desktop image pre-warming and caching tool.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.preload_desktop_images import (
    DEFAULT_REGISTRY,
    DEFAULT_TAG,
    SANDBOX_IMAGES,
    SERVICE_IMAGES,
    detect_app_version,
    get_all_target_images,
    main,
    parse_pull_throughput,
    preload_images,
    pull_with_progress,
    resolve_local_candidate,
)


def test_detect_app_version(tmp_path: Path) -> None:
    # No package.json returns DEFAULT_TAG
    assert detect_app_version(tmp_path) == DEFAULT_TAG

    # Valid package.json
    pkg_dir = tmp_path / "apps" / "mission-control"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "package.json").write_text('{"version": "1.4.2"}', encoding="utf-8")
    assert detect_app_version(tmp_path) == "v1.4.2"


def test_get_all_target_images() -> None:
    targets = get_all_target_images(DEFAULT_REGISTRY, "v1.0.0")
    assert len(targets) == len(SERVICE_IMAGES) + len(SANDBOX_IMAGES)

    # Check service image structure
    orch = next(t for t in targets if t[0] == "orchestrator")
    assert orch[1] == f"{DEFAULT_REGISTRY}/thefactory-orchestrator:v1.0.0"
    assert orch[2] == orch[1]

    # Check sandbox image structure
    py_sandbox = next(t for t in targets if t[0] == "sandbox-test-python")
    assert py_sandbox[1] == f"{DEFAULT_REGISTRY}/thefactory-sandbox-test-python:v1.0.0"
    assert py_sandbox[2] == "thefactory/sandbox-test-python:1"


def test_parse_pull_throughput() -> None:
    line = "e387034c44c5: Downloading [=====> ] 15.5MB/100.0MB"
    parsed = parse_pull_throughput(line)
    assert parsed is not None
    curr, tot = parsed
    assert pytest.approx(curr, 0.1) == 15.5
    assert pytest.approx(tot, 0.1) == 100.0

    # Non-matching line
    assert parse_pull_throughput("Already exists") is None


def test_resolve_local_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    # If image inspect returns True for candidate
    def _mock_inspect(ref: str) -> tuple[bool, float]:
        if ref == "deploy-orchestrator:latest":
            return True, 180.0
        return False, 0.0

    monkeypatch.setattr("scripts.preload_desktop_images.inspect_image", _mock_inspect)

    cand = resolve_local_candidate(
        published="ghcr.io/kherrera6219/thefactory-orchestrator:v1.0.0",
        local_name="orchestrator",
        tag="v1.0.0",
    )
    assert cand == "deploy-orchestrator:latest"


def test_pull_with_progress_dry_run() -> None:
    assert pull_with_progress("any-image:latest", dry_run=True) is True


def test_preload_images_check_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    # All cached scenario
    monkeypatch.setattr("scripts.preload_desktop_images.inspect_image", lambda _ref: (True, 150.0))
    ret = preload_images(check_only=True, dry_run=True)
    assert ret == 0

    # Some missing scenario
    monkeypatch.setattr("scripts.preload_desktop_images.inspect_image", lambda _ref: (False, 0.0))
    ret_missing = preload_images(check_only=True, dry_run=True)
    assert ret_missing == 2


def test_preload_images_dry_run_pull_and_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.preload_desktop_images.inspect_image", lambda _ref: (False, 0.0))
    ret = preload_images(check_only=False, dry_run=True)
    assert ret == 0


def test_main_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.preload_desktop_images.preload_images", lambda **kwargs: 0)
    assert main(["--check", "--dry-run"]) == 0
