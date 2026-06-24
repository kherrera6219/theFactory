"""Atomic file writes (Local-First Error Handling Standard §11, §15).

A partially-written file must never replace a previously-valid one. These helpers
implement the standard's atomic-write pattern:

1. Write new content to a unique sibling temporary file.
2. Flush + ``fsync`` so the bytes are durably on disk.
3. (Optional) verify the temp file's SHA-256 matches the intended content.
4. ``os.replace`` the unique temp file into place — atomic on POSIX and Windows/NTFS.
5. If the replace fails, keep a ``<name>.bak`` copy of the previous valid file so
   nothing is lost.

Correctness rests on two OS guarantees: ``os.replace`` is atomic (destination is
either the old file or the new one, never a truncated mix), and ``fsync`` forces
the temp bytes to disk *before* the rename so a crash cannot leave an empty file
in place.

Stdlib-only — no new dependency.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

_PATH_LOCKS: dict[Path, threading.Lock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


def _path_lock(path: Path) -> threading.Lock:
    resolved = path.resolve(strict=False)
    with _PATH_LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(resolved, threading.Lock())


def _replace_with_retry(src: Path, dest: Path) -> None:
    for attempt in range(10):
        try:
            os.replace(src, dest)
            return
        except PermissionError as exc:
            is_windows_sharing_violation = os.name == "nt" and exc.winerror in {5, 32}
            if not is_windows_sharing_violation or attempt == 9:
                raise
            time.sleep(0.01 * (attempt + 1))

def atomic_write_bytes(path: str | os.PathLike[str], data: bytes, *, verify: bool = True) -> None:
    """Atomically write ``data`` to ``path`` (temp → fsync → verify → replace → .bak).

    Args:
        path: destination file path.
        data: exact bytes to write.
        verify: when True, re-read the temp file and confirm its SHA-256 before
            replacing — guards against a silent short write.

    Raises:
        OSError: if the write/replace fails. On replace failure the previous file
            is preserved (and a ``.bak`` copy is left when one could be made).
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=dest.parent,
        prefix=f".{dest.name}.",
        suffix=".tmp",
    )
    tmp = Path(tmp_name)
    try:
        # 1+2: write to a unique sibling temp file and force it to disk.
        # Explicit binary mode prevents Windows newline translation.
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())

        # 3: verify the temp file content.
        if verify:
            written = tmp.read_bytes()
            if hashlib.sha256(written).hexdigest() != hashlib.sha256(data).hexdigest():
                raise OSError(f"atomic_write verification failed for {dest}")

        # Serialize the backup-and-replace window for this destination. Windows
        # denies replacement while another thread has the destination open.
        with _path_lock(dest):
            # 5 (precaution): keep a backup of the existing valid file before replacing.
            if dest.exists():
                backup = dest.with_name(dest.name + ".bak")
                try:
                    backup.write_bytes(dest.read_bytes())
                except OSError:
                    # Backup is best-effort; proceed with the atomic replace regardless.
                    pass

            # 4: atomic replace.
            _replace_with_retry(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)


def atomic_write_text(
    path: str | os.PathLike[str], text: str, *, encoding: str = "utf-8", verify: bool = True
) -> None:
    """Atomically write ``text`` to ``path``. See :func:`atomic_write_bytes`."""
    atomic_write_bytes(path, text.encode(encoding), verify=verify)


def atomic_write_json(
    path: str | os.PathLike[str], obj: Any, *, indent: int = 2, verify: bool = True
) -> None:
    """Atomically write ``obj`` as pretty JSON (trailing newline)."""
    atomic_write_text(path, json.dumps(obj, indent=indent) + "\n", verify=verify)
