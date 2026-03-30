from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_backup_artifacts(*, backup_file: Path, manifest_file: Path) -> dict[str, object]:
    if not backup_file.is_file():
        raise RuntimeError(f"backup file not found: {backup_file}")
    if not manifest_file.is_file():
        raise RuntimeError(f"manifest file not found: {manifest_file}")

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise RuntimeError("backup manifest must be a JSON object")

    recorded_file = Path(str(manifest.get("backup_file", "")))
    if recorded_file.name != backup_file.name:
        raise RuntimeError("backup manifest backup_file does not match the provided artifact")

    recorded_size = int(manifest.get("size_bytes", -1))
    actual_size = backup_file.stat().st_size
    if recorded_size != actual_size:
        raise RuntimeError("backup manifest size_bytes does not match the artifact size")

    recorded_sha256 = str(manifest.get("sha256", "")).strip().lower()
    actual_sha256 = _sha256(backup_file)
    if recorded_sha256 != actual_sha256:
        raise RuntimeError("backup manifest sha256 does not match the artifact digest")

    return {
        "backup_file": str(backup_file),
        "manifest_file": str(manifest_file),
        "size_bytes": actual_size,
        "sha256": actual_sha256,
        "verified": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify PostgreSQL backup artifact size and digest against its manifest.",
    )
    parser.add_argument("--backup-file", required=True, type=Path)
    parser.add_argument("--manifest-file", required=True, type=Path)
    parser.add_argument("--output-file", type=Path)
    args = parser.parse_args()

    try:
        result = verify_backup_artifacts(
            backup_file=args.backup_file,
            manifest_file=args.manifest_file,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    if args.output_file is not None:
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        args.output_file.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
