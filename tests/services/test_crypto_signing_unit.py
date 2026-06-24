import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

signing = importlib.import_module("shared_runtime.crypto_signing")
keystore = importlib.import_module("shared_runtime.crypto_keystore")


# ---------------------------------------------------------------------------
# crypto_signing
# ---------------------------------------------------------------------------
def test_sign_and_verify_roundtrip_bytes() -> None:
    key = signing.generate_signing_key()
    pub = signing.public_key_to_pem(key)
    data = b"artifact bytes"
    sig = signing.sign(key, data)
    assert signing.verify(pub, data, sig) is True


def test_verify_rejects_tampered_data() -> None:
    key = signing.generate_signing_key()
    pub = signing.public_key_to_pem(key)
    sig = signing.sign(key, b"original")
    assert signing.verify(pub, b"tampered", sig) is False


def test_verify_rejects_wrong_key() -> None:
    key_a = signing.generate_signing_key()
    key_b = signing.generate_signing_key()
    data = b"payload"
    sig = signing.sign(key_a, data)
    # Signature from key_a must not verify under key_b's public key.
    assert signing.verify(signing.public_key_to_pem(key_b), data, sig) is False


def test_ecdsa_is_non_deterministic_but_both_valid() -> None:
    key = signing.generate_signing_key()
    pub = signing.public_key_to_pem(key)
    data = b"same payload"
    sig1 = signing.sign(key, data)
    sig2 = signing.sign(key, data)
    assert sig1 != sig2  # random nonce → different bytes
    assert signing.verify(pub, data, sig1)
    assert signing.verify(pub, data, sig2)


def test_pem_roundtrip() -> None:
    key = signing.generate_signing_key()
    pem = signing.private_key_to_pem(key)
    loaded = signing.private_key_from_pem(pem)
    data = b"x"
    sig = signing.sign(loaded, data)
    assert signing.verify(signing.public_key_to_pem(key), data, sig)


def test_sign_payload_and_verify_payload_dict() -> None:
    key = signing.generate_signing_key()
    payload = {"mission_id": "m-1", "artifact": "code.py", "digest": "abc"}
    record = signing.sign_payload(key, payload)
    assert record["algorithm"] == "ECDSA-P256-SHA256"
    assert "signature" in record and "public_key_pem" in record
    assert signing.verify_payload(payload, record) is True
    # Key reordering must still verify (canonical, sort_keys).
    assert signing.verify_payload({"artifact": "code.py", "digest": "abc", "mission_id": "m-1"}, record)


def test_verify_payload_rejects_mutation() -> None:
    key = signing.generate_signing_key()
    payload = {"a": 1}
    record = signing.sign_payload(key, payload)
    assert signing.verify_payload({"a": 2}, record) is False


def test_verify_payload_rejects_malformed_record() -> None:
    assert signing.verify_payload({"a": 1}, {}) is False
    assert signing.verify_payload({"a": 1}, "not-a-dict") is False
    assert signing.verify_payload({"a": 1}, {"algorithm": "wrong"}) is False

def test_verify_payload_requires_digest() -> None:
    key = signing.generate_signing_key()
    payload = {"a": 1}
    record = signing.sign_payload(key, payload)
    record.pop("digest_sha256")

    assert signing.verify_payload(payload, record) is False


def test_verify_rejects_non_p256_key() -> None:
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP384R1())
    data = b"payload"
    signature = signing.sign(key, data)

    assert signing.verify(signing.public_key_to_pem(key), data, signature) is False


def test_verify_rejects_invalid_base64_signature() -> None:
    key = signing.generate_signing_key()

    assert signing.verify(signing.public_key_to_pem(key), b"payload", "not base64!!!") is False


# ---------------------------------------------------------------------------
# crypto_keystore
# ---------------------------------------------------------------------------
def test_protect_unprotect_roundtrip() -> None:
    secret = b"super-secret-key-bytes"
    # allow_plaintext_fallback covers non-Windows; on Windows DPAPI is used.
    blob = keystore.protect_key(secret, allow_plaintext_fallback=True)
    assert blob != secret  # protected/marked, not raw
    assert keystore.unprotect_key(blob) == secret


def test_unprotect_rejects_unknown_format() -> None:
    import pytest

    with pytest.raises(ValueError):
        keystore.unprotect_key(b"garbage-no-marker")


def test_load_or_create_signing_key_persists_and_reloads(tmp_path) -> None:
    keypath = tmp_path / "keys" / "signing.key"
    key1 = keystore.load_or_create_signing_key(keypath, allow_plaintext_fallback=True)
    assert keypath.exists()
    # Reload returns a key that produces verifiable signatures under the same public key.
    key2 = keystore.load_or_create_signing_key(keypath, allow_plaintext_fallback=True)
    data = b"persisted"
    sig = signing.sign(key2, data)
    assert signing.verify(signing.public_key_to_pem(key1), data, sig) is True


def test_mounted_signing_key_loads_existing_pem_without_modifying_it(
    tmp_path, monkeypatch
) -> None:
    keypath = tmp_path / "mounted-signing-key.pem"
    expected_key = signing.generate_signing_key()
    pem = signing.private_key_to_pem(expected_key)
    keypath.write_bytes(pem)
    monkeypatch.setenv("ARTIFACT_SIGNING_KEY_SOURCE", "mounted")

    loaded = keystore.load_or_create_signing_key(keypath)

    assert keypath.read_bytes() == pem
    data = b"mounted-secret"
    signature = signing.sign(loaded, data)
    assert signing.verify(signing.public_key_to_pem(expected_key), data, signature)


def test_mounted_signing_key_supports_rotation_without_restart(
    tmp_path, monkeypatch
) -> None:
    keypath = tmp_path / "mounted-signing-key.pem"
    first_key = signing.generate_signing_key()
    second_key = signing.generate_signing_key()
    monkeypatch.setenv("ARTIFACT_SIGNING_KEY_SOURCE", "mounted")
    keypath.write_bytes(signing.private_key_to_pem(first_key))
    loaded_first = keystore.load_or_create_signing_key(keypath)

    keypath.write_bytes(signing.private_key_to_pem(second_key))
    loaded_second = keystore.load_or_create_signing_key(keypath)

    data = b"rotated-secret"
    signature = signing.sign(loaded_second, data)
    assert signing.verify(signing.public_key_to_pem(second_key), data, signature)
    assert not signing.verify(signing.public_key_to_pem(loaded_first), data, signature)


def test_production_requires_existing_mounted_pem(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ARTIFACT_SIGNING_KEY_SOURCE", "auto")

    import pytest

    with pytest.raises(RuntimeError, match="requires ARTIFACT_SIGNING_KEY_SOURCE=mounted"):
        keystore.load_or_create_signing_key(tmp_path / "must-not-be-created.key")


def test_raw_pem_is_rejected_without_mounted_source(tmp_path, monkeypatch) -> None:
    keypath = tmp_path / "raw-signing-key.pem"
    keypath.write_bytes(signing.private_key_to_pem(signing.generate_signing_key()))
    monkeypatch.setenv("ARTIFACT_SIGNING_KEY_SOURCE", "protected")

    import pytest

    with pytest.raises(ValueError, match="requires ARTIFACT_SIGNING_KEY_SOURCE=mounted"):
        keystore.load_or_create_signing_key(keypath)


# ---------------------------------------------------------------------------
# sign_artifact / verify_artifact (file-on-disk signing)
# ---------------------------------------------------------------------------
def test_sign_artifact_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(
        "ARTIFACT_SIGNING_KEY_PATH", str(tmp_path / "keys" / "artifact.key")
    )
    artifact = tmp_path / "out.rir.module.json"
    artifact.write_text('{"a": 1}\n', encoding="utf-8")
    record = signing.sign_artifact(artifact)
    assert record["algorithm"] == signing.ALGORITHM
    sidecar = tmp_path / ("out.rir.module.json" + signing.SIGNATURE_SUFFIX)
    assert sidecar.exists()
    assert signing.verify_artifact(artifact) is True


def test_verify_artifact_detects_tampering(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(
        "ARTIFACT_SIGNING_KEY_PATH", str(tmp_path / "keys" / "artifact.key")
    )
    artifact = tmp_path / "out.json"
    artifact.write_text("original", encoding="utf-8")
    signing.sign_artifact(artifact)
    artifact.write_text("tampered", encoding="utf-8")
    assert signing.verify_artifact(artifact) is False


def test_verify_artifact_missing_sidecar_returns_false(tmp_path) -> None:
    artifact = tmp_path / "unsigned.json"
    artifact.write_text("x", encoding="utf-8")
    assert signing.verify_artifact(artifact) is False


def test_verify_artifact_malformed_sidecar_returns_false(tmp_path) -> None:
    artifact = tmp_path / "a.json"
    artifact.write_text("x", encoding="utf-8")
    (tmp_path / ("a.json" + signing.SIGNATURE_SUFFIX)).write_text(
        "not json", encoding="utf-8"
    )
    assert signing.verify_artifact(artifact) is False
