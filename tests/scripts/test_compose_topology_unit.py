"""Regression tests for the compose-topology guard.

theFactory's full-dedicated topology is the base compose file **plus** an
additive overlay. Running a mutating command against the base file alone while
that overlay is active desyncs its 41 dedicated agent containers from the rest
of the stack — a documented incident, and the second of the two standing
operational cautions.

`scripts/force_stop.py` already detected topology before tearing down.
`start_app.bat` did not: it chose its topology from a `--condensed` flag with no
reference to what was actually running, so `start_app.bat --condensed` against a
live full-dedicated stack produced exactly that mismatch. These tests pin the
guard that closes it.

No Docker daemon is required — detection is tested against injected container
name lists.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from compose_topology import (  # noqa: E402
    CONDENSED,
    FULL_DEDICATED,
    NONE,
    check_mismatch,
    detect_topology,
)


def test_dedicated_agent_container_marks_full_dedicated() -> None:
    names = ["deploy-orchestrator-1", "deploy-agent-01-pm-1", "deploy-redis-1"]
    assert detect_topology(names) == FULL_DEDICATED


def test_stack_without_dedicated_agents_is_condensed() -> None:
    names = ["deploy-orchestrator-1", "deploy-redis-1", "deploy-postgres-1"]
    assert detect_topology(names) == CONDENSED


def test_nothing_running_is_none() -> None:
    assert detect_topology([]) == NONE


def test_unrelated_containers_do_not_register_as_our_stack() -> None:
    assert detect_topology(["some-other-project-db-1"]) == NONE


def test_condensed_start_against_running_full_dedicated_is_blocked() -> None:
    """The exact hole: start_app.bat --condensed on a live full-dedicated stack."""
    message = check_mismatch(CONDENSED, FULL_DEDICATED)
    assert message is not None
    assert "desync" in message
    assert "make up" in message


def test_full_dedicated_start_against_running_condensed_is_blocked() -> None:
    message = check_mismatch(FULL_DEDICATED, CONDENSED)
    assert message is not None
    assert "force_stop" in message


@pytest.mark.parametrize("requested", [CONDENSED, FULL_DEDICATED])
def test_nothing_running_permits_any_topology(requested: str) -> None:
    assert check_mismatch(requested, NONE) is None


@pytest.mark.parametrize("topology", [CONDENSED, FULL_DEDICATED])
def test_matching_topology_is_permitted(topology: str) -> None:
    assert check_mismatch(topology, topology) is None


def test_start_app_invokes_the_guard_before_bringing_the_stack_up() -> None:
    """The guard is worthless if the launcher does not call it."""
    script = (ROOT / "start_app.bat").read_text(encoding="utf-8")
    guard_index = script.find("compose_topology.py")
    assert guard_index != -1, "start_app.bat does not run the topology guard"

    for up_command in ("make up-condensed", "make up"):
        up_index = script.find(up_command)
        assert up_index != -1
        assert guard_index < up_index, (
            f"topology guard must run before `{up_command}`"
        )


def test_start_app_aborts_rather_than_warning() -> None:
    script = (ROOT / "start_app.bat").read_text(encoding="utf-8")
    assert "errorlevel 1" in script
    assert "exit /b 1" in script
