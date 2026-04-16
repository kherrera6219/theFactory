import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "services" / "api-gateway"))
sys.path.append(str(ROOT / "services" / "orchestrator"))
sys.path.append(str(ROOT / "services" / "dashboard"))

from api_gateway.main import app as api_app  # noqa: E402
from dashboard.main import app as dashboard_app  # noqa: E402
from orchestrator.main import app as orchestrator_app  # noqa: E402


def test_api_gateway_health() -> None:
    client = TestClient(api_app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_orchestrator_health() -> None:
    client = TestClient(orchestrator_app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_dashboard_health() -> None:
    client = TestClient(dashboard_app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["service"] == "dashboard"
