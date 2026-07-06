from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared_runtime.atomic_io import atomic_write_bytes  # noqa: E402

CERT_DIR = ROOT / "deploy" / "postgres" / "certs"
CERT_FILES = ("ca.crt", "server.crt", "server.key")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a local dev Postgres CA/server TLS cert+key pair."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate and overwrite the CA/certificate pair even if it already exists.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    existing = [name for name in CERT_FILES if (CERT_DIR / name).exists()]
    if existing and not args.force:
        raise SystemExit(
            f"refusing to overwrite existing cert material: {', '.join(existing)} "
            f"in {CERT_DIR} (pass --force to regenerate)"
        )

    now = datetime.now(UTC)

    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "theFactory Postgres CA"),
        ]
    )
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(private_key=ca_key, algorithm=hashes.SHA256())
    )

    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "postgres")])
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(server_name)
        .issuer_name(ca_name)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("postgres"),
                    x509.DNSName("localhost"),
                ]
            ),
            critical=False,
        )
        .sign(private_key=ca_key, algorithm=hashes.SHA256())
    )

    # Atomic per-file writes (temp -> fsync -> replace) so a crash mid-write
    # can't leave a mismatched cert/key pair on disk.
    atomic_write_bytes(CERT_DIR / "ca.crt", ca_cert.public_bytes(serialization.Encoding.PEM))
    atomic_write_bytes(
        CERT_DIR / "server.crt",
        server_cert.public_bytes(serialization.Encoding.PEM),
    )
    atomic_write_bytes(
        CERT_DIR / "server.key",
        server_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ),
    )
    print(f"wrote postgres tls certs to {CERT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
