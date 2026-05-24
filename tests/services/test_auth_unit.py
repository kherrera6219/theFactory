import sys
from pathlib import Path
from typing import Any
import pytest
from fastapi import HTTPException

# Force absolute imports for the test environment
ROOT = Path(r"C:\software\Holygrail\theFactory")
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

import orchestrator.auth as auth
from orchestrator.settings import Settings

def _make_dummy_settings(**overrides) -> Settings:
    base = {
        "redis_url": "redis://localhost",
        "postgres_url": "postgresql://localhost",
        "intake_stream": "missions.intake",
        "state_stream": "missions.state",
        "max_stream_len": 1000,
        "consumer_group": "orchestrator",
        "consumer_name": "orchestrator-test",
        "auto_transition_enabled": True,
        "transition_step_seconds": 1.0,
        "intake_topic": "intake.feature_contract.created",
        "default_priority": "NORMAL",
        "producer_name": "orchestrator",
        "event_schema_path": Path("."),
        "topics_path": Path("."),
        "admin_api_key": "",
        "internal_service_api_key": "",
        "readonly_api_key": "",
        "extra_api_keys": ""
    }
    base.update(overrides)
    return Settings(**base)

def test_match_api_key():
    api_key_roles = {
        "admin-key": {"admin", "read", "mutate"},
        "viewer-key": {"read"}
    }
    
    # Valid key
    assert auth._match_api_key("admin-key", api_key_roles) == {"admin", "read", "mutate"}
    assert auth._match_api_key("viewer-key", api_key_roles) == {"read"}
    
    # Invalid key
    assert auth._match_api_key("invalid-key", api_key_roles) is None
    
    # Empty case
    assert auth._match_api_key("", api_key_roles) is None

@pytest.mark.asyncio
async def test_require_roles_dependency():
    settings = _make_dummy_settings(
        admin_api_key="admin-key",
        internal_service_api_key="worker-key"
    )
    
    # Test admin requirement
    dep = auth.require_roles(settings, {"admin"})
    
    # Missing header
    with pytest.raises(HTTPException) as exc:
        await dep(x_api_key=None)
    assert exc.value.status_code == 401
    
    # Invalid key
    with pytest.raises(HTTPException) as exc:
        await dep(x_api_key="wrong")
    assert exc.value.status_code == 401
    
    # Insufficient role (worker-key doesn't have admin)
    with pytest.raises(HTTPException) as exc:
        await dep(x_api_key="worker-key")
    assert exc.value.status_code == 403
    
    # Valid
    context = await dep(x_api_key="admin-key")
    assert context.api_key == "admin-key"
    assert "admin" in context.roles

@pytest.mark.asyncio
async def test_require_roles_open_access():
    settings = _make_dummy_settings(readonly_api_key="viewer-key")
    # Empty allowed_roles means any valid key is fine
    dep = auth.require_roles(settings, set())
    context = await dep(x_api_key="viewer-key")
    assert "read" in context.roles
