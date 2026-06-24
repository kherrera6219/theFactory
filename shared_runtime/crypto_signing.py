"""ECDSA P-256 digital signatures (Local-First Security Standard §6).

Signs artifacts / reports / audit bundles so importers can verify authenticity, and
verifies signatures before trusting imported data.

Key points:

- Algorithm is **ECDSA over NIST P-256 (secp256r1) with SHA-256** — recorded as
  ``ECDSA-P256-SHA256`` in every signature record.
- ECDSA is **non-deterministic** (a random nonce is used), so signing the same payload
  twice produces different bytes — both valid. Verification therefore *checks validity*,
  it never compares signature bytes.
- A signature record pairs the signature with the SHA-256 digest of the canonical payload,
  giving both tamper-evidence (hash) and authenticity (signature).

Depends on the already-present ``cryptography`` package.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

ALGORITHM = "ECDSA-P256-SHA256"

LOGGER = logging.getLogger(__name__)

# Default on-disk location of the protected ECDSA signing key. Overridable so
# each service can point at its mounted secret / KMS-provisioned key.
_DEFAULT_KEYSTORE_PATH = "/app/secrets/artifact-signing-key.pem"
# Sidecar suffix appended to an artifact path to hold its signature record.
SIGNATURE_SUFFIX = ".sig.json"


def generate_signing_key() -> ec.EllipticCurvePrivateKey:
    """Generate a fresh ECDSA P-256 (secp256r1) private key."""
    return ec.generate_private_key(ec.SECP256R1())


def private_key_to_pem(key: ec.EllipticCurvePrivateKey) -> bytes:
    """Serialise a private key to unencrypted PKCS8 PEM (protect at rest via keystore)."""
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def private_key_from_pem(pem: bytes) -> ec.EllipticCurvePrivateKey:
    """Load a private key from PEM."""
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise ValueError("not an EC private key")
    if not isinstance(key.curve, ec.SECP256R1):
        raise ValueError("EC private key must use P-256")
    return key


def public_key_to_pem(key: ec.EllipticCurvePrivateKey) -> bytes:
    """Serialise the public half of a key pair to PEM (distributed with signatures)."""
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _canonical_bytes(payload: Any) -> bytes:
    """Deterministic byte representation of a payload for signing/verifying."""
    if isinstance(payload, (bytes, bytearray)):
        return bytes(payload)
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(private_key: ec.EllipticCurvePrivateKey, data: bytes) -> str:
    """Sign raw bytes; return a base64-encoded DER signature."""
    digest = hashlib.sha256(data).digest()
    signature = private_key.sign(digest, ec.ECDSA(Prehashed(hashes.SHA256())))
    return base64.b64encode(signature).decode("ascii")


def verify(public_key_pem: bytes, data: bytes, signature_b64: str) -> bool:
    """Return True iff ``signature_b64`` is a valid signature of ``data``."""
    try:
        public_key = serialization.load_pem_public_key(public_key_pem)
        if not isinstance(public_key, ec.EllipticCurvePublicKey):
            return False
        if not isinstance(public_key.curve, ec.SECP256R1):
            return False
        signature = base64.b64decode(signature_b64, validate=True)
        digest = hashlib.sha256(data).digest()
        public_key.verify(signature, digest, ec.ECDSA(Prehashed(hashes.SHA256())))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def sign_payload(private_key: ec.EllipticCurvePrivateKey, payload: Any) -> dict[str, str]:
    """Sign a JSON-serialisable payload (or str/bytes) and return a signature record.

    The record carries everything an importer needs to verify: the algorithm, the
    base64 signature, the signer's public key (PEM), the canonical SHA-256 digest, and
    a timestamp.
    """
    data = _canonical_bytes(payload)
    return {
        "algorithm": ALGORITHM,
        "signature": sign(private_key, data),
        "public_key_pem": public_key_to_pem(private_key).decode("ascii"),
        "digest_sha256": hashlib.sha256(data).hexdigest(),
        "signed_at": datetime.now(UTC).isoformat(),
    }


def verify_payload(payload: Any, signature_record: dict[str, Any]) -> bool:
    """Verify a payload against a signature record produced by :func:`sign_payload`.

    Checks both the SHA-256 digest (tamper-evidence) and the ECDSA signature
    (authenticity). Returns False on any mismatch or malformed record.
    """
    if not isinstance(signature_record, dict):
        return False
    if signature_record.get("algorithm") != ALGORITHM:
        return False
    data = _canonical_bytes(payload)
    expected_digest = signature_record.get("digest_sha256")
    if not isinstance(expected_digest, str):
        return False
    if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), expected_digest):
        return False
    pem = signature_record.get("public_key_pem")
    signature = signature_record.get("signature")
    if not isinstance(pem, str) or not isinstance(signature, str):
        return False
    return verify(pem.encode("ascii"), data, signature)


def _keystore_path() -> str:
    return os.getenv("ARTIFACT_SIGNING_KEY_PATH", "").strip() or _DEFAULT_KEYSTORE_PATH


def sign_artifact(
    artifact_path: str | os.PathLike[str],
    *,
    keystore_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Sign the file at *artifact_path*, writing a ``<path>.sig.json`` sidecar.

    The signature record (see :func:`sign_payload`) is computed over the artifact's
    raw bytes so an importer can later verify the file on disk byte-for-byte. The
    signing key is loaded (or created on first use) via the protected keystore.
    Returns the signature record.
    """
    from shared_runtime.crypto_keystore import load_or_create_signing_key

    path = Path(artifact_path)
    key = load_or_create_signing_key(keystore_path or _keystore_path())
    record = sign_payload(key, path.read_bytes())
    sidecar = Path(str(path) + SIGNATURE_SUFFIX)
    from shared_runtime.atomic_io import atomic_write_json

    atomic_write_json(sidecar, record)
    return record


def verify_artifact(artifact_path: str | os.PathLike[str]) -> bool:
    """Verify the file at *artifact_path* against its ``<path>.sig.json`` sidecar.

    Returns False if the sidecar is missing, malformed, or the signature does not
    match the current file bytes.
    """
    path = Path(artifact_path)
    sidecar = Path(str(path) + SIGNATURE_SUFFIX)
    if not sidecar.exists():
        return False
    try:
        record = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return verify_payload(path.read_bytes(), record)
