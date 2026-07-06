"""Regression tests for Phase 0 production runtime-default guards.

Full Whole-App Remediation Plan (2026-07-05), Phase 0: RQCA_ENFORCEMENT_ENABLED
and OBJECT_STORAGE_*_KEY must not silently resolve to insecure defaults in
production.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from orchestrator.settings import load_settings  # noqa: E402


def _base_env(monkeypatch) -> None:
    # Production requires at least one orchestrator key to be set. Also pin
    # every other Phase 0 production guard to its passing value so each test
    # below only exercises the one guard it's named for, regardless of
    # whatever RQCA_ENFORCEMENT_ENABLED/OBJECT_STORAGE_* happen to already be
    # set to in the ambient environment this test runs in.
    monkeypatch.setenv("ORCHESTRATOR_ADMIN_API_KEY", "admin-key-with-entropy-1234")
    monkeypatch.setenv("RQCA_ENFORCEMENT_ENABLED", "true")
    monkeypatch.setenv("OBJECT_STORAGE_ACCESS_KEY", "a-real-production-access-key")
    monkeypatch.setenv("OBJECT_STORAGE_SECRET_KEY", "a-real-production-secret")


def test_rqca_enforcement_defaults_to_true_in_development(monkeypatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("RQCA_ENFORCEMENT_ENABLED", raising=False)
    settings = load_settings()
    assert settings.rqca_enforcement_enabled is True


def test_rqca_enforcement_disabled_in_production_raises(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("RQCA_ENFORCEMENT_ENABLED", "false")
    try:
        load_settings()
    except RuntimeError as exc:
        assert "RQCA_ENFORCEMENT_ENABLED" in str(exc)
    else:
        raise AssertionError(
            "expected RuntimeError for RQCA_ENFORCEMENT_ENABLED=false in production"
        )


def test_rqca_enforcement_enabled_in_production_ok(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("RQCA_ENFORCEMENT_ENABLED", "true")
    settings = load_settings()
    assert settings.rqca_enforcement_enabled is True


def test_default_minio_credentials_in_development_ok(monkeypatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("OBJECT_STORAGE_ACCESS_KEY", "minioadmin")
    monkeypatch.setenv("OBJECT_STORAGE_SECRET_KEY", "minioadmin123")
    settings = load_settings()
    assert settings.object_storage_access_key == "minioadmin"
    assert settings.object_storage_secret_key == "minioadmin123"


def test_default_minio_access_key_in_production_raises(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OBJECT_STORAGE_ACCESS_KEY", "minioadmin")
    monkeypatch.setenv("OBJECT_STORAGE_SECRET_KEY", "a-real-production-secret")
    try:
        load_settings()
    except RuntimeError as exc:
        assert "minioadmin" in str(exc)
    else:
        raise AssertionError(
            "expected RuntimeError for default MinIO access key in production"
        )


def test_default_minio_secret_key_in_production_raises(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OBJECT_STORAGE_ACCESS_KEY", "a-real-production-access-key")
    monkeypatch.setenv("OBJECT_STORAGE_SECRET_KEY", "minioadmin123")
    try:
        load_settings()
    except RuntimeError as exc:
        assert "minioadmin" in str(exc)
    else:
        raise AssertionError(
            "expected RuntimeError for default MinIO secret key in production"
        )


def test_real_minio_credentials_in_production_ok(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OBJECT_STORAGE_ACCESS_KEY", "a-real-production-access-key")
    monkeypatch.setenv("OBJECT_STORAGE_SECRET_KEY", "a-real-production-secret")
    settings = load_settings()
    assert settings.object_storage_access_key == "a-real-production-access-key"
    assert settings.object_storage_secret_key == "a-real-production-secret"
