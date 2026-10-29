"""
test_manage_topology.py

Unit tests for Dynamic Deployment Topology Orchestrator.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.manage_topology import (
    CONDENSED,
    FULL_DEDICATED,
    get_topology_status,
    main,
    switch_topology,
    update_env_autofill,
)


def test_update_env_autofill(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\nAGENT_AUTOFILL_NON_POD_HEARTBEATS=true\nBAZ=qux\n", encoding="utf-8")

    update_env_autofill(autofill_enabled=False, env_path=env_file)
    content = env_file.read_text(encoding="utf-8")
    assert "AGENT_AUTOFILL_NON_POD_HEARTBEATS=false" in content
    assert "FOO=bar" in content
    assert "BAZ=qux" in content

    update_env_autofill(autofill_enabled=True, env_path=env_file)
    content2 = env_file.read_text(encoding="utf-8")
    assert "AGENT_AUTOFILL_NON_POD_HEARTBEATS=true" in content2


def test_get_topology_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.manage_topology.current_topology", lambda _b: CONDENSED)
    mock_run = MagicMock()
    mock_run.return_value.stdout = "deploy-orchestrator\ndeploy-api-gateway\n"
    monkeypatch.setattr("subprocess.run", mock_run)

    status = get_topology_status()
    assert status["topology"] == CONDENSED
    assert status["running_containers"] == 2
    assert "Condensed" in str(status["mode_label"])


def test_switch_topology_already_in_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.manage_topology.current_topology", lambda _b: CONDENSED)
    ret = switch_topology("condensed", dry_run=True)
    assert ret == 0


def test_switch_topology_condensed_to_dedicated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("scripts.manage_topology.current_topology", lambda _b: CONDENSED)
    monkeypatch.setattr("scripts.manage_topology.ENV_FILE", tmp_path / ".env")
    ret = switch_topology("dedicated", dry_run=True)
    assert ret == 0


def test_switch_topology_dedicated_to_condensed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("scripts.manage_topology.current_topology", lambda _b: FULL_DEDICATED)
    monkeypatch.setattr("scripts.manage_topology.ENV_FILE", tmp_path / ".env")
    ret = switch_topology("condensed", dry_run=True)
    assert ret == 0


def test_main_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.manage_topology.get_topology_status", lambda: {"topology": "condensed", "running_containers": 1, "mode_label": "Condensed"})
    monkeypatch.setattr("scripts.manage_topology.switch_topology", lambda **_kw: 0)

    assert main(["--status"]) == 0
    assert main(["--mode", "dedicated", "--dry-run"]) == 0
