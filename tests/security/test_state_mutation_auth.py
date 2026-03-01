import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "services" / "api-gateway"))
sys.path.append(str(ROOT / "services" / "orchestrator"))

from api_gateway.main import app as api_app  # noqa: E402
from orchestrator.main import app as orchestrator_app  # noqa: E402


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
