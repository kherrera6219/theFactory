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


def test_orchestrator_livez_is_lightweight() -> None:
    # /livez is the liveness probe the Docker healthcheck + depends_on chain gate
    # on. It must return 200 quickly and perform NO optional-backend readiness
    # probes (those belong to /health and /readyz) — coupling liveness to
    # optional-backend latency wedged the dependent chain on cold starts.
    client = TestClient(orchestrator_app)
    response = client.get("/livez")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["live"] is True
    assert body["service"] == "orchestrator"
    for optional_key in ("qdrant_ready", "milvus_ready", "neo4j_ready", "object_storage_ready"):
        assert optional_key not in body


def test_dashboard_health() -> None:
    client = TestClient(dashboard_app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["service"] == "dashboard"
