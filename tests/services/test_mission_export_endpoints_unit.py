"""Unit tests for mission patch/SBOM export routes and CycloneDX signing (F1 & F2)."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared_runtime"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

crypto_keystore = importlib.import_module("shared_runtime.crypto_keystore")
crypto_signing = importlib.import_module("shared_runtime.crypto_signing")
deploy_exporter = importlib.import_module("orchestrator.deploy_exporter")
orchestrator_auth = importlib.import_module("orchestrator.auth")
orchestrator_main = importlib.import_module("orchestrator.main")
orchestrator_models = importlib.import_module("orchestrator.models")
orchestrator_missions = importlib.import_module("orchestrator.routes.missions")

MissionRecord = orchestrator_models.MissionRecord
MissionState = orchestrator_models.MissionState


def _sample_mission(mission_id: str = "mission-export-1") -> MissionRecord:
    return MissionRecord(
        mission_id=mission_id,
        prompt="Build sample utility",
        requested_target_language="python",
        metadata={
            "source_code": "## FILE src/app.py\ndef greet():\n    return 'hi'\n",
            "generated_output": {
                "filename": "src/app.py",
                "language": "python",
                "dependencies": ["fastapi==0.141.1"],
                "code": "## FILE src/app.py\ndef greet(name: str = 'world'):\n    return f'hello {name}'\n",
            },
        },
        state=MissionState.complete,
        created_at="2026-11-13T00:00:00+00:00",
    )


def test_orchestrator_export_patch_and_sbom_require_internal_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F1: Orchestrator /export/patch and /export/sbom must enforce INTERNAL_AUTH_DEP."""
    monkeypatch.setenv("ARTIFACT_SIGNING_KEY_PATH", str(tmp_path / "keys" / "route-signing.key"))
    monkeypatch.setenv("ARTIFACT_SIGNING_KEY_SOURCE", "auto")
    app = orchestrator_main.app
    app.dependency_overrides.clear()

    async def _db_ready(_app: object) -> tuple[bool, bool]:
        return True, True

    async def _fetch_existing(_app: object, mission_id: str) -> MissionRecord:
        return _sample_mission(mission_id)

    monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _db_ready)
    monkeypatch.setattr(orchestrator_main, "_fetch_existing_mission", _fetch_existing)
    monkeypatch.setattr(orchestrator_missions.storage, "list_build_artifacts", lambda *_args: [])

    client = TestClient(app)

    try:
        # Anonymous requests must be rejected with 401 before touching mission data.
        patch_anon = client.get("/missions/mission-export-1/export/patch")
        sbom_anon = client.get("/missions/mission-export-1/export/sbom")
        assert patch_anon.status_code == 401
        assert sbom_anon.status_code == 401

        # Invalid API key must also be rejected with 401.
        patch_bad = client.get(
            "/missions/mission-export-1/export/patch",
            headers={"x-api-key": "invalid-key-should-fail"},
        )
        sbom_bad = client.get(
            "/missions/mission-export-1/export/sbom",
            headers={"x-api-key": "invalid-key-should-fail"},
        )
        assert patch_bad.status_code == 401
        assert sbom_bad.status_code == 401

        # Authenticated internal caller (matching internal/admin/worker role) must succeed (200)
        # even when _fetch_existing_mission returns a MissionRecord model.
        auth_ctx = orchestrator_auth.AuthContext(
            api_key="test-internal-key",
            roles={"internal", "read"},
        )
        app.dependency_overrides[orchestrator_main.INTERNAL_AUTH] = lambda: auth_ctx

        patch_ok = client.get("/missions/mission-export-1/export/patch")
        sbom_ok = client.get("/missions/mission-export-1/export/sbom")
        assert patch_ok.status_code == 200
        assert "+++ b/src/app.py" in patch_ok.text
        assert sbom_ok.status_code == 200
        assert sbom_ok.json()["bomFormat"] == "CycloneDX"
    finally:
        app.dependency_overrides.clear()


def test_generate_cyclonedx_sbom_uses_ecdsa_and_verifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F2: SBOM signing must use ECDSA-P256-SHA256 via sign_payload(key, payload) and verify."""
    key_path = tmp_path / "keys" / "sbom-signing.key"
    monkeypatch.setenv("ARTIFACT_SIGNING_KEY_PATH", str(key_path))
    monkeypatch.setenv("ARTIFACT_SIGNING_KEY_SOURCE", "auto")

    sbom = deploy_exporter.generate_cyclonedx_sbom(
        mission_id="mission-sbom-ecdsa",
        generated_output={
            "filename": "src/app.py",
            "language": "python",
            "dependencies": ["fastapi==0.141.1"],
            "code": "def run():\n    return 1\n",
        },
        sbom_delta={"remaining": ["uvicorn==0.30.0"]},
    )

    sig_record = sbom["metadata"].get("signature_record")
    assert isinstance(sig_record, dict)
    assert sig_record["algorithm"] == "ECDSA-P256-SHA256"
    assert sig_record.get("public_key_pem")
    assert sbom["signature"]["algorithm"] == "ECDSA-P256-SHA256"

    sbom_core = {
        "bomFormat": sbom["bomFormat"],
        "specVersion": sbom["specVersion"],
        "serialNumber": sbom["serialNumber"],
        "version": sbom["version"],
        "components": sbom["components"],
    }
    assert crypto_signing.verify_payload(json.dumps(sbom_core, sort_keys=True), sig_record) is True

    # Tampering with a component must invalidate verification.
    tampered_core = {**sbom_core, "components": [*sbom["components"], {"name": "evil", "version": "1.0.0"}]}
    assert (
        crypto_signing.verify_payload(json.dumps(tampered_core, sort_keys=True), sig_record)
        is False
    )

    props = {p["name"]: p["value"] for p in sbom["metadata"]["properties"]}
    assert props["thefactory:signed"] == "true"
    assert props["thefactory:signing_algorithm"] == "ECDSA-P256-SHA256"


def test_generate_cyclonedx_sbom_signing_failure_fails_closed_without_hmac_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F2: When key loading fails, SBOM must fail closed without hardcoded HMAC fallback."""

    def _boom(_path: object) -> None:
        raise RuntimeError("keystore unavailable")

    monkeypatch.setattr(crypto_keystore, "load_or_create_signing_key", _boom)

    sbom = deploy_exporter.generate_cyclonedx_sbom(
        mission_id="mission-sbom-fail",
        generated_output={
            "filename": "src/app.py",
            "language": "python",
            "code": "print(1)\n",
        },
    )

    assert sbom["signature"] is None
    assert sbom["metadata"].get("signature_record") is None
    props = {p["name"]: p["value"] for p in sbom["metadata"]["properties"]}
    assert props["thefactory:signed"] == "false"
    assert props["thefactory:signing_algorithm"] != "HMAC-SHA256"
    assert props["thefactory:signature"] == ""
