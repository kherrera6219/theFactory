"""Path containment helpers for sandbox workspace permission fixes."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def path_is_contained(candidate: str, root: str) -> bool:
    """True when *candidate* is *root* or a descendant after normalization."""
    base = os.path.abspath(root)
    full = os.path.abspath(candidate)
    return full == base or full.startswith(base + os.sep)


def contained_workspace(workspace_dir: str | Path, workspace_root: str = "") -> Path | None:
    """Accept a workspace only when it stays under an allowed root."""
    raw = os.path.abspath(str(workspace_dir))
    allowed = [os.path.abspath(tempfile.gettempdir())]
    if workspace_root:
        allowed.append(os.path.abspath(workspace_root))
    if not any(path_is_contained(raw, root) for root in allowed):
        LOGGER.warning("sandbox workspace %s is outside allowed roots", raw)
        return None
    if not os.path.isdir(raw):
        return None
    return Path(raw)


def make_workspace_readable(workspace_dir: str | Path, workspace_root: str = "") -> None:
    """chmod a sandbox workspace only after containment is proven."""
    root = contained_workspace(workspace_dir, workspace_root=workspace_root)
    if root is None:
        return
    try:
        root.chmod(0o755)
        for entry in root.rglob("*"):
            try:
                entry.resolve().relative_to(root.resolve())
            except ValueError:
                continue
            entry.chmod(0o755 if entry.is_dir() else 0o644)
    except OSError as exc:
        LOGGER.warning("could not relax sandbox workspace permissions on %s: %s", root, exc)
