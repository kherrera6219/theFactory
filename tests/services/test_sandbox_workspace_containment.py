"""Workspace containment for sandbox chmod / rglob."""
from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
ORCH = ROOT / "services" / "orchestrator"
if str(ORCH) not in sys.path:
    sys.path.insert(0, str(ORCH))


def test_contained_workspace_accepts_tempdir_child(tmp_path: Path) -> None:
    from orchestrator.sandbox_paths import contained_workspace, make_workspace_readable

    workspace = tmp_path / "ws"
    workspace.mkdir()
    secret = workspace / "main.c"
    secret.write_text("int main(){return 0;}\n", encoding="utf-8")
    os.chmod(workspace, 0o700)
    os.chmod(secret, 0o600)

    with patch("orchestrator.sandbox_paths.tempfile.gettempdir", return_value=str(tmp_path)):
        assert contained_workspace(workspace) == workspace.resolve()
        make_workspace_readable(workspace)

    assert stat.S_IMODE(workspace.stat().st_mode) == 0o755
    assert stat.S_IMODE(secret.stat().st_mode) == 0o644


def test_contained_workspace_rejects_escape(tmp_path: Path) -> None:
    from orchestrator.sandbox_paths import contained_workspace, make_workspace_readable

    outside = Path(tempfile.gettempdir()).resolve()
    assert contained_workspace(outside, workspace_root=str(tmp_path)) is None
    before = stat.S_IMODE(outside.stat().st_mode)
    make_workspace_readable(outside, workspace_root=str(tmp_path))
    assert stat.S_IMODE(outside.stat().st_mode) == before
