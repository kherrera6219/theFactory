"""Regression tests for PostgreSQL backup artifact verification."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "verify_backup_artifacts.py"

spec = importlib.util.spec_from_file_location("verify_backup_artifacts", MODULE_PATH)
assert spec is not None and spec.loader is not None
verify_backup_artifacts = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = verify_backup_artifacts
spec.loader.exec_module(verify_backup_artifacts)


def test_verify_backup_artifacts_accepts_matching_manifest(tmp_path: Path) -> None:
    backup = tmp_path / "ulr_20260329_000000.sql"
    backup.write_text("-- backup\nCREATE TABLE missions(id text);\n", encoding="utf-8")
    digest = verify_backup_artifacts._sha256(backup)
    manifest = tmp_path / "ulr_20260329_000000.sql.json"
    manifest.write_text(
        json.dumps(
            {
                "backup_file": str(backup),
                "size_bytes": backup.stat().st_size,
                "sha256": digest,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = verify_backup_artifacts.verify_backup_artifacts(
        backup_file=backup,
        manifest_file=manifest,
    )

    assert result["verified"] is True
    assert result["sha256"] == digest


def test_verify_backup_artifacts_rejects_digest_mismatch(tmp_path: Path) -> None:
    backup = tmp_path / "ulr_20260329_000000.sql"
    backup.write_text("-- backup\nCREATE TABLE missions(id text);\n", encoding="utf-8")
    manifest = tmp_path / "ulr_20260329_000000.sql.json"
    manifest.write_text(
        json.dumps(
            {
                "backup_file": str(backup),
                "size_bytes": backup.stat().st_size,
                "sha256": "deadbeef",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="sha256"):
        verify_backup_artifacts.verify_backup_artifacts(
            backup_file=backup,
            manifest_file=manifest,
        )
