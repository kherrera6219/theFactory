"""Signing-key protection at rest (Local-First Security Standard §3, §6).

The ECDSA signing private key must never sit in plaintext on disk. On Windows desktop
deployments this is done with **DPAPI** (`CryptProtectData`/`CryptUnprotectData`,
`CurrentUser` scope) so only the authenticated Windows user can unprotect it — no
external key-management system, matching the local-first standard.

DPAPI is Windows-only. On the (non-Windows) Docker backend, DPAPI is unavailable; the
documented equivalent is to supply the key via a mounted secret / KMS. This module
therefore exposes a single API that uses DPAPI when available and otherwise stores the
key bytes verbatim **only when explicitly allowed** (dev/backend), logging the downgrade.

DPAPI is called through ``ctypes`` — no extra dependency.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

LOGGER = logging.getLogger(__name__)

_IS_WINDOWS = sys.platform == "win32"


# ---------------------------------------------------------------------------
# DPAPI via ctypes (Windows only)
# ---------------------------------------------------------------------------
def _dpapi_available() -> bool:
    return _IS_WINDOWS


def _dpapi_protect(data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _to_blob(raw: bytes) -> DATA_BLOB:
        buf = ctypes.create_string_buffer(raw, len(raw))
        return DATA_BLOB(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    blob_in = _to_blob(data)
    blob_out = DATA_BLOB()
    # CRYPTPROTECT_LOCAL_MACHINE = 0x4 would broaden scope; we use CurrentUser (flags=0).
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _dpapi_unprotect(blob: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(blob, len(blob))
    blob_in = DATA_BLOB(len(blob), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


# DPAPI-protected blobs are prefixed so we never mistake a plaintext fallback blob for one.
_DPAPI_MAGIC = b"DPAPIv1:"
_PLAIN_MAGIC = b"PLAINv1:"


def protect_key(data: bytes, *, allow_plaintext_fallback: bool = False) -> bytes:
    """Protect key bytes for at-rest storage.

    On Windows: DPAPI (CurrentUser). Elsewhere: raises unless
    ``allow_plaintext_fallback`` is True (backend/dev), in which case the bytes are
    stored verbatim behind a ``PLAINv1:`` marker and the downgrade is logged.
    """
    if _dpapi_available():
        return _DPAPI_MAGIC + _dpapi_protect(data)
    if not allow_plaintext_fallback:
        raise RuntimeError(
            "DPAPI unavailable on this platform and plaintext fallback not allowed. "
            "Supply the signing key via a mounted secret / KMS on the backend."
        )
    LOGGER.warning(
        "DPAPI unavailable; storing signing key WITHOUT OS protection "
        "(allow_plaintext_fallback=True). Use a mounted secret / KMS in production."
    )
    return _PLAIN_MAGIC + data


def unprotect_key(blob: bytes) -> bytes:
    """Reverse :func:`protect_key`."""
    if blob.startswith(_DPAPI_MAGIC):
        if not _dpapi_available():
            raise RuntimeError("DPAPI-protected key cannot be read on this platform")
        return _dpapi_unprotect(blob[len(_DPAPI_MAGIC):])
    if blob.startswith(_PLAIN_MAGIC):
        return blob[len(_PLAIN_MAGIC):]
    raise ValueError("unrecognised protected-key format")


def load_or_create_signing_key(
    keystore_path: str | os.PathLike[str], *, allow_plaintext_fallback: bool | None = None
):
    """Load the protected ECDSA signing key, generating + persisting it on first use.

    Returns an ``ec.EllipticCurvePrivateKey``. The on-disk file holds the
    DPAPI-protected (or, on the backend, fallback-marked) PKCS8 PEM.
    """
    from shared_runtime import crypto_signing

    if allow_plaintext_fallback is None:
        # Default: allow fallback off-Windows (backend); never silently plaintext on Windows.
        allow_plaintext_fallback = not _IS_WINDOWS

    path = Path(keystore_path)
    if path.exists():
        return crypto_signing.private_key_from_pem(unprotect_key(path.read_bytes()))

    key = crypto_signing.generate_signing_key()
    pem = crypto_signing.private_key_to_pem(key)
    protected = protect_key(pem, allow_plaintext_fallback=allow_plaintext_fallback)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write so a crash can't leave a half-written key file.
    from shared_runtime.atomic_io import atomic_write_bytes

    atomic_write_bytes(path, protected)
    return key
