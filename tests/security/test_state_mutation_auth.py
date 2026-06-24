import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "services" / "api-gateway"))
sys.path.append(str(ROOT / "services" / "orchestrator"))

import api_gateway.main as api_gateway_main  # noqa: E402
from orchestrator.main import app as orchestrator_app  # noqa: E402

api_app = api_gateway_main.app


def test_gateway_state_mutation_requires_api_key() -> None:
    client = TestClient(api_app)
    response = client.post(
        "/v1/missions/mission-does-not-matter/state",
        json={"new_state": "FAILED"},
    )
    assert response.status_code == 401


def test_state_mutation_requires_api_key() -> None:
    client = TestClient(orchestrator_app)
    response = client.post(
        "/missions/mission-does-not-matter/state",
        json={"new_state": "FAILED"},
    )
    assert response.status_code == 401


def test_orchestrator_create_mission_requires_internal_api_key() -> None:
    client = TestClient(orchestrator_app)
    response = client.post(
        "/missions",
        json={"mission_id": "mission-1", "prompt": "Build API"},
    )
    assert response.status_code == 401


def test_orchestrator_mission_reads_require_api_key() -> None:
    # H-4: mission prompts/metadata/source must not be world-readable.
    client = TestClient(orchestrator_app)
    for path in (
        "/missions",
        "/missions/mission-1",
        "/missions/mission-1/events",
    ):
        response = client.get(path)
        assert response.status_code == 401, path


def test_gateway_mission_reads_require_auth(monkeypatch) -> None:
    # H-4: gateway must not elevate anonymous callers with its internal key.
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "api_key")
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", False)
    client = TestClient(api_app)
    for path in (
        "/v1/missions",
        "/v1/missions/mission-1",
        "/v1/missions/mission-1/events",
    ):
        response = client.get(path)
        assert response.status_code == 401, path


def test_gateway_operations_require_auth_in_api_key_mode(monkeypatch) -> None:
    # C-2: operator routes had no gateway-side auth in api_key mode.
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "api_key")
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", False)
    client = TestClient(api_app)
    for path in (
        "/v1/operations/summary",
        "/v1/operations/events",
        "/v1/missions/mission-1/token-usage",
    ):
        response = client.get(path)
        assert response.status_code == 401, path


def test_gateway_operations_allow_valid_read_key(monkeypatch) -> None:
    # C-2: a configured key with the read role is accepted.
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "api_key")
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", False)
    monkeypatch.setattr(
        api_gateway_main, "_gateway_api_key_roles", lambda: {"read-key": {"read"}}
    )

    async def _fake_internal(_path, *, params=None):
        return {"ok": True}

    monkeypatch.setattr(api_gateway_main, "_proxy_get_internal", _fake_internal)
    client = TestClient(api_app)
    response = client.get(
        "/v1/operations/summary",
        headers={"X-API-Key": "read-key"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True

    forbidden = client.get(
        "/v1/operations/summary",
        headers={"X-API-Key": "unknown-key"},
    )
    assert forbidden.status_code == 401
