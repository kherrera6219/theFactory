import logging
import os
import re
import shutil
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shared_runtime.atomic_io import atomic_write_json

LOGGER = logging.getLogger(__name__)

# Name-based denylist substrings for env vars excluded outright from
# diagnostic bundles. This used to only check _KEY/_SECRET/_PASSWORD, which
# missed real vars like VAULT_TOKEN/VAULT_ROLE_ID (no matching substring) --
# every credential-shaped suffix actually used in this repo's .env.example
# is covered here.
_SENSITIVE_ENV_NAME_MARKERS = (
    "_KEY",
    "_SECRET",
    "_PASSWORD",
    "_TOKEN",
    "_CREDENTIAL",
    "_ROLE_ID",
)
# Connection strings (POSTGRES_URL, REDIS_URL, etc.) embed a plaintext
# password in the URL's userinfo segment even though the var name itself
# carries no _KEY/_SECRET/_PASSWORD/_TOKEN marker. Redact that segment
# regardless of which env var it came from.
_URL_USERINFO_PATTERN = re.compile(r"(://[^:/@\s]*:)[^@/\s]+(@)")


def _sanitize_env_value(value: str) -> str:
    return _URL_USERINFO_PATTERN.sub(r"\1***\2", value)

class MaintenanceManager:
    def __init__(self, settings: Any):
        self.settings = settings
        self.base_dir = Path(os.getenv("FACTORY_DATA_ROOT", "/data"))
        self.backup_dir = self.base_dir / "backups"
        self.diag_dir = self.base_dir / "diagnostics"
        
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.diag_dir.mkdir(parents=True, exist_ok=True)

    async def create_diagnostic_bundle(self, mission_id: str | None = None) -> str:
        """Generate a sanitized tarball of logs, health, and metadata."""
        bundle_id = f"diag-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
        bundle_path = self.diag_dir / f"{bundle_id}.tar.gz"
        tmp_work_dir = self.diag_dir / bundle_id
        tmp_work_dir.mkdir()

        try:
            # 1. Collect System Health
            # Mocking app for health check call if needed, or calling static parts
            # For now, we'll just write a basic status file
            status = {
                "timestamp": datetime.now(UTC).isoformat(),
                "version": "1.1.0",
                "mission_id_context": mission_id,
                "os": os.name,
            }
            atomic_write_json(tmp_work_dir / "system_status.json", status)

            # 2. Collect Sanitized Environment (No Secrets)
            env_data = {
                k: _sanitize_env_value(v)
                for k, v in os.environ.items()
                if not any(marker in k for marker in _SENSITIVE_ENV_NAME_MARKERS)
            }
            atomic_write_json(tmp_work_dir / "environment_sanitized.json", env_data)

            # 3. Create the tarball
            with tarfile.open(bundle_path, "w:gz") as tar:
                tar.add(tmp_work_dir, arcname=bundle_id)

            return str(bundle_path)
        finally:
            shutil.rmtree(tmp_work_dir)

    async def run_full_backup(self) -> str:
        """Trigger a compressed backup of all stateful volumes."""
        # Note: In a containerized environment, we target the mounted volumes
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        backup_file = self.backup_dir / f"factory-full-backup-{timestamp}.tar.gz"
        
        # In this implementation, we assume volumes are mapped to /data/stores
        # (Postgres, Qdrant, etc.)
        stores_dir = self.base_dir / "stores"
        if not stores_dir.exists():
            return "ERROR: Stores directory not found for backup"

        with tarfile.open(backup_file, "w:gz") as tar:
            tar.add(stores_dir, arcname="stores")
            
        return str(backup_file)

def get_maintenance_manager(app: Any) -> MaintenanceManager:
    if not hasattr(app.state, "maintenance_manager"):
        app.state.maintenance_manager = MaintenanceManager(app.state.settings)
    return app.state.maintenance_manager
