"""Atomic file writes (Local-First Error Handling Standard §11, §15).

A partially-written file must never replace a previously-valid one. These helpers
implement the standard's atomic-write pattern:

1. Write new content to a sibling ``<name>.tmp`` file.
2. Flush + ``fsync`` so the bytes are durably on disk.
3. (Optional) verify the temp file's SHA-256 matches the intended content.
4. ``os.replace`` the temp file into place — atomic on POSIX and Windows/NTFS.
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
from pathlib import Path
from typing import Any


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
    tmp = dest.with_name(dest.name + ".tmp")

    # 1+2: write to temp and force to disk. Use explicit binary mode ("wb") so
    # Windows does not apply text-mode newline translation (which would corrupt
    # the byte stream and trip the SHA-256 verify below).
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())

    # 3: verify the temp file content.
    if verify:
        written = tmp.read_bytes()
        if hashlib.sha256(written).hexdigest() != hashlib.sha256(data).hexdigest():
            tmp.unlink(missing_ok=True)
            raise OSError(f"atomic_write verification failed for {dest}")

    # 5 (precaution): keep a backup of the existing valid file before replacing.
    if dest.exists():
        backup = dest.with_name(dest.name + ".bak")
        try:
            backup.write_bytes(dest.read_bytes())
        except OSError:
            # Backup is best-effort; proceed with the atomic replace regardless.
            pass

    # 4: atomic replace.
    try:
        os.replace(tmp, dest)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


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
