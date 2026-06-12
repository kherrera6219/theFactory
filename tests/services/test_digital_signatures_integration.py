import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

import orchestrator.auth as orchestrator_auth
import orchestrator.build_artifacts as build_artifacts
import orchestrator.main as orchestrator_main

from shared_runtime.crypto_keystore import load_or_create_signing_key
from shared_runtime.crypto_signing import _keystore_path, verify_payload

app = orchestrator_main.app


@pytest.fixture(autouse=True)
def _override_auth_dependencies():
    auth_context = orchestrator_auth.AuthContext(
        api_key="test-key",
        roles={"admin", "internal", "mutate", "read", "worker"},
    )
    app.dependency_overrides[orchestrator_main.MUTATION_AUTH] = lambda: auth_context
    app.dependency_overrides[orchestrator_main.INTERNAL_AUTH] = lambda: auth_context
    yield
    app.dependency_overrides.clear()


def test_build_artifacts_signing_integration(tmp_path, monkeypatch) -> None:
    # Set custom keystore path for testing
    monkeypatch.setenv("ARTIFACT_SIGNING_KEY_PATH", str(tmp_path / "keys" / "test-signing.key"))

    # Test source bundle signing
    artifact = build_artifacts.build_source_bundle_artifact(
        mission_id="mission-test-1",
        requested_target_language="python",
        metadata={
            "source": "builder",
            "source_code": "print('hello world')",
        },
    )
    assert "signature_record" in artifact["verification"]
    assert artifact["verification"]["verification_method"] == "ECDSA-P256-SHA256"

    # Verify signature
    sig_record = artifact["verification"]["signature_record"]
    assert verify_payload("print('hello world')", sig_record) is True

    # Verify that tampered payload fails signature validation
    assert verify_payload("print('hello world!')", sig_record) is False


def test_compliance_report_signing_integration(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARTIFACT_SIGNING_KEY_PATH", str(tmp_path / "keys" / "test-signing.key"))

    # Create dummy compliance report
    report = {
        "report_id": "report-123",
        "mission_id": "mission-1",
        "passed": True,
        "findings": [],
    }

    # Sign compliance report (similar to phases_delivery.py)
    report_to_sign = {k: v for k, v in report.items() if k != "signature_record"}
    key = load_or_create_signing_key(_keystore_path())
    from shared_runtime.crypto_signing import sign_payload
    sig = sign_payload(key, report_to_sign)
    report["signature_record"] = sig

    assert verify_payload(report_to_sign, report["signature_record"]) is True
    # Tampered report fails
    tampered_report_to_verify = {k: v for k, v in report.items() if k != "signature_record"}
    tampered_report_to_verify["passed"] = False
    assert verify_payload(tampered_report_to_verify, report["signature_record"]) is False


def test_upsert_audit_report_signature_validation(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARTIFACT_SIGNING_KEY_PATH", str(tmp_path / "keys" / "test-signing.key"))

    # Mock DB dependency
    async def fake_ensure_db_ready(*args, **kwargs):
        return
    monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", fake_ensure_db_ready)
    
    class FakeMission:
        mission_id = "mission-1"
        project_id = "project-1"
        metadata = {}
        requested_target_language = "python"
        state = "running"

    async def fake_fetch_existing_mission(*args, **kwargs):
        return FakeMission()
    
    monkeypatch.setattr(orchestrator_main, "_fetch_existing_mission", fake_fetch_existing_mission)

    def fake_upsert_audit_report(*args, **kwargs):
        return {
            "mission_id": "mission-1",
            "audit_id": "audit-1",
            "status": "success",
            "report": args[4],
            "created_at": "2026-06-11T00:00:00Z"
        }
    
    monkeypatch.setattr("orchestrator.storage.upsert_audit_report", fake_upsert_audit_report)

    client = TestClient(app)

    # 1. Post report with valid signature
    report_data = {"summary": "all checks passed", "details": "no issues found"}
    key = load_or_create_signing_key(_keystore_path())
    from shared_runtime.crypto_signing import sign_payload
    signature_record = sign_payload(key, report_data)
    report_data["signature_record"] = signature_record

    response = client.post(
        "/internal/audit-reports",
        json={
            "mission_id": "mission-1",
            "audit_id": "audit-1",
            "status": "success",
            "report": report_data,
        },
        headers={"x-api-key": "test-key"},
    )
    assert response.status_code == 200

    # 2. Post report with invalid signature (tampered details)
    tampered_report_data = report_data.copy()
    tampered_report_data["details"] = "tampered details"
    response = client.post(
        "/internal/audit-reports",
        json={
            "mission_id": "mission-1",
            "audit_id": "audit-1",
            "status": "success",
            "report": tampered_report_data,
        },
        headers={"x-api-key": "test-key"},
    )
    assert response.status_code == 422
    assert "invalid digital signature" in response.json()["detail"]

    # 3. Post report without signature in production mode
    # Set environment to production
    from dataclasses import replace
    original_settings = app.state.settings
    app.state.settings = replace(original_settings, environment="production")
    try:
        response = client.post(
            "/internal/audit-reports",
            json={
                "mission_id": "mission-1",
                "audit_id": "audit-1",
                "status": "success",
                "report": {"summary": "unsigned report"},
            },
            headers={"x-api-key": "test-key"},
        )
        assert response.status_code == 422
        assert "signature is required in production" in response.json()["detail"]
    finally:
        # Revert environment
        app.state.settings = original_settings
