import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from orchestrator.settings import load_settings  # noqa: E402


def _base_env(monkeypatch) -> None:
    # Production requires at least one orchestrator key to be set. Also pin
    # the Phase 0 production runtime-default guards (RQCA_ENFORCEMENT_ENABLED,
    # OBJECT_STORAGE_*_KEY) to their passing values — this file's tests are
    # about AGENT_SERVICE_KEY_MODE, not those guards, so they shouldn't be
    # sensitive to whatever those variables happen to be in the ambient
    # environment.
    monkeypatch.setenv("ORCHESTRATOR_ADMIN_API_KEY", "admin-key-with-entropy-1234")
    monkeypatch.setenv("RQCA_ENFORCEMENT_ENABLED", "true")
    monkeypatch.setenv("OBJECT_STORAGE_ACCESS_KEY", "a-real-production-access-key")
    monkeypatch.setenv("OBJECT_STORAGE_SECRET_KEY", "a-real-production-secret")


def test_defaults_to_shared_in_development(monkeypatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("AGENT_SERVICE_KEY_MODE", raising=False)
    settings = load_settings()
    assert settings.environment == "development"
    assert settings.agent_service_key_mode == "shared"


def test_strict_mode_is_read(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SERVICE_KEY_MODE", "STRICT")
    settings = load_settings()
    assert settings.agent_service_key_mode == "strict"


def test_event_driven_control_plane_flag_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv("EVENT_DRIVEN_CONTROL_PLANE_ENABLED", raising=False)
    settings = load_settings()
    assert settings.event_driven_control_plane_enabled is False


def test_event_driven_control_plane_flag_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("EVENT_DRIVEN_CONTROL_PLANE_ENABLED", "true")
    settings = load_settings()
    assert settings.event_driven_control_plane_enabled is True


def test_warns_when_shared_in_production(monkeypatch, caplog) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AGENT_SERVICE_KEY_MODE", "shared")
    with caplog.at_level(logging.WARNING, logger="orchestrator.settings"):
        settings = load_settings()
    assert settings.environment == "production"
    assert any(
        "agent_service_key_mode=shared in production" in rec.message
        for rec in caplog.records
    )


def test_no_warning_when_strict_in_production(monkeypatch, caplog) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AGENT_SERVICE_KEY_MODE", "strict")
    with caplog.at_level(logging.WARNING, logger="orchestrator.settings"):
        load_settings()
    assert not any(
        "agent_service_key_mode=shared in production" in rec.message
        for rec in caplog.records
    )
