"""Regression tests: stopping the app must not destroy its data.

`stop_app.bat` -> `scripts/force_stop.py` -> `make down*` used to run
`docker compose down -v` unconditionally. `-v` removes every named volume:
`postgres-data`, `redis-data`, `qdrant-data`, `neo4j-data`, `minio-data`,
`milvus-data`, and `mission-control-vault`.

So an ordinary "stop the app" destroyed the mission database, every knowledge
store, and the operator's stored provider API keys. It wiped the database at
least once in practice (2026-06-30), which is how the behaviour was found.

These tests pin the safe default and the explicit opt-in. They are pure string
assertions over the command builder — no Docker daemon and no teardown is ever
executed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from force_stop import build_teardown_commands, parse_args  # noqa: E402

MAKEFILE = ROOT / "Makefile"


@pytest.mark.parametrize("full_dedicated", [True, False])
def test_default_teardown_never_passes_dash_v(full_dedicated: bool) -> None:
    """The regression itself: stopping the app must preserve volumes."""
    make_target, fallback = build_teardown_commands(
        full_dedicated=full_dedicated, wipe_volumes=False
    )
    assert not re.search(r"\bdown\s+-v\b", fallback), fallback
    assert fallback.rstrip().endswith("down"), fallback
    assert "wipe" not in make_target


@pytest.mark.parametrize("full_dedicated", [True, False])
def test_wipe_volumes_opt_in_is_destructive(full_dedicated: bool) -> None:
    """The escape hatch still works when explicitly requested."""
    make_target, fallback = build_teardown_commands(
        full_dedicated=full_dedicated, wipe_volumes=True
    )
    assert fallback.rstrip().endswith("down -v"), fallback
    assert make_target.endswith("-wipe")


def test_default_is_preserve_not_wipe() -> None:
    assert parse_args([]).wipe_volumes is False
    assert parse_args(["--wipe-volumes"]).wipe_volumes is True


def test_topology_detection_selects_the_paired_compose_form() -> None:
    """Tearing a full-dedicated stack down with the base file alone mismatches
    the running containers' compose config — the second standing caution."""
    _, paired = build_teardown_commands(full_dedicated=True, wipe_volumes=False)
    assert "docker-compose.yaml" in paired
    assert "docker-compose.full-dedicated-agents.yaml" in paired
    assert "--profile full-dedicated-agents" in paired

    _, condensed = build_teardown_commands(full_dedicated=False, wipe_volumes=False)
    assert "docker-compose.yaml" in condensed
    assert "full-dedicated-agents.yaml" not in condensed


def _makefile_recipe(target: str) -> str:
    """Return the recipe lines for a Makefile target."""
    text = MAKEFILE.read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(target)}:.*?$\n((?:\t.*\n)*)", text, re.M)
    assert match, f"target {target} not found in Makefile"
    return match.group(1)


@pytest.mark.parametrize("target", ["down", "down-condensed", "monitor-down"])
def test_makefile_down_targets_preserve_volumes(target: str) -> None:
    recipe = _makefile_recipe(target)
    assert "down -v" not in recipe, (
        f"`make {target}` destroys volumes. Stopping the stack must not delete "
        f"the mission database or the operator vault — use `make {target}-wipe`."
    )


@pytest.mark.parametrize(
    "target", ["down-wipe", "down-condensed-wipe", "monitor-down-wipe"]
)
def test_makefile_wipe_targets_exist_and_are_destructive(target: str) -> None:
    assert "down -v" in _makefile_recipe(target)


def test_wipe_targets_warn_before_destroying_operator_data() -> None:
    """A destructive target should say what it is about to destroy."""
    for target in ("down-wipe", "down-condensed-wipe"):
        recipe = _makefile_recipe(target)
        assert "WARNING" in recipe, f"`make {target}` destroys data without warning"
