"""Path containment helpers for sandbox workspace permission fixes."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def path_is_contained(candidate: str, root: str) -> bool:
    """True when *candidate* is *root* or a descendant after normalization."""
    base = os.path.realpath(root)
    full = os.path.realpath(candidate)
    return full == base or full.startswith(base + os.sep)


def _allowed_roots(workspace_root: str = "") -> list[str]:
    """Roots a sandbox workspace is permitted to live directly beneath."""
    roots = [os.path.realpath(tempfile.gettempdir())]
    if workspace_root:
        roots.append(os.path.realpath(workspace_root))
    return roots


def contained_workspace(workspace_dir: str | Path, workspace_root: str = "") -> Path | None:
    """Accept a workspace only when it is a direct child of an allowed root.

    Two properties matter here, and the second is why this is written the way
    it is rather than as a plain prefix check.

    **An allowed root itself is rejected.** Accepting it would let
    ``make_workspace_readable(tempfile.gettempdir())`` relax permissions across
    the whole system temp tree -- the escape this containment exists to prevent,
    not an edge case of it.

    **The returned path is rebuilt as** ``<allowed root>/<basename>``, so the
    value that later reaches ``chmod``/``rglob`` is derived from a trusted root
    plus a single name component, never from the caller's string. The directory
    part of the input is discarded by ``os.path.basename`` rather than merely
    inspected, so no input can steer the walk elsewhere even if the checks above
    were somehow bypassed. That distinction is what makes the containment
    *verifiable* instead of asserted, and it is what ``py/path-injection``
    requires -- an earlier version validated the same conditions but passed the
    caller's path through, which is indistinguishable from no check at all to
    any analysis that cannot follow the validator.

    Restricting to direct children costs nothing: sandbox workspaces are always
    created by ``tempfile.TemporaryDirectory(dir=workspace_root())``, so a
    nested path never occurs in practice and is refused rather than guessed at.
    """
    raw = os.path.realpath(str(workspace_dir))
    name = os.path.basename(raw)
    # Character allowlist, not just basename. `safe != name` means the name
    # survived the filter unchanged, so it provably contains no separator, no
    # dot segment and no drive letter -- it cannot denote anything but a single
    # child of whichever root is chosen below. Basename alone establishes the
    # same thing by construction, but only to a reader; this states it as a
    # value test, which is what makes the containment checkable rather than
    # asserted. Sandbox workspaces are named by
    # `tempfile.TemporaryDirectory(prefix="hgr-rqca-...")`, whose alphabet is
    # exactly [a-z0-9_] plus the caller's alphanumeric-and-dash prefix, so no
    # real workspace is rejected by this.
    safe = "".join(ch for ch in name if ch.isalnum() or ch in {"-", "_"})
    if not safe or safe != name:
        LOGGER.warning("sandbox workspace name %r is not a plain child name", name)
        return None

    for root in _allowed_roots(workspace_root):
        if os.path.dirname(raw) != root:
            continue
        # Built from the validated root plus a validated single name -- no part
        # of the caller's path string reaches this join.
        rebuilt = os.path.join(root, safe)
        if not os.path.isdir(rebuilt):
            return None
        return Path(rebuilt)

    LOGGER.warning("sandbox workspace %s is not a direct child of an allowed root", raw)
    return None


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
