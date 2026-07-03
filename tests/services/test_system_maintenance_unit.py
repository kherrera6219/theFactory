import asyncio
import json
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from orchestrator.system_maintenance import MaintenanceManager  # noqa: E402


def _read_bundle_json(bundle_path: str, member_name: str) -> dict:
    with tarfile.open(bundle_path, "r:gz") as tar:
        for member in tar.getmembers():
            if member.name.endswith(member_name):
                extracted = tar.extractfile(member)
                assert extracted is not None
                return json.loads(extracted.read())
    raise AssertionError(f"{member_name} not found in bundle")


def test_diagnostic_bundle_redacts_connection_string_passwords(monkeypatch, tmp_path) -> None:
    # Regression: the env sanitizer only excluded var names containing
    # _KEY/_SECRET/_PASSWORD -- real vars like POSTGRES_URL/REDIS_URL embed
    # a plaintext password in the connection string's userinfo segment
    # despite carrying none of those name markers, and VAULT_TOKEN/
    # VAULT_ROLE_ID carried no matching substring at all.
    monkeypatch.setenv("FACTORY_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv(
        "POSTGRES_URL", "postgresql://postgres:CHANGE_ME_super_secret@postgres:5432/factory"
    )
    monkeypatch.setenv("REDIS_URL", "redis://:CHANGE_ME_redis_secret@redis:6379/0")
    monkeypatch.setenv("VAULT_TOKEN", "hvs.super-secret-vault-token")
    monkeypatch.setenv("VAULT_ROLE_ID", "role-id-12345")
    monkeypatch.setenv("SOME_OTHER_SETTING", "harmless-value")

    manager = MaintenanceManager(settings=SimpleNamespace())
    bundle_path = asyncio.run(manager.create_diagnostic_bundle())

    env_data = _read_bundle_json(bundle_path, "environment_sanitized.json")

    assert "VAULT_TOKEN" not in env_data
    assert "VAULT_ROLE_ID" not in env_data
    assert env_data["SOME_OTHER_SETTING"] == "harmless-value"
    assert "CHANGE_ME_super_secret" not in env_data["POSTGRES_URL"]
    assert "CHANGE_ME_redis_secret" not in env_data["REDIS_URL"]
    assert env_data["POSTGRES_URL"].startswith("postgresql://postgres:***@")
