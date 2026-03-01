import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api-gateway"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

api_gateway_main = importlib.import_module("api_gateway.main")
orchestrator_main = importlib.import_module("orchestrator.main")

api_app = api_gateway_main.app
orchestrator_app = orchestrator_main.app


class FakeRedis:
    def __init__(self) -> None:
        self._kv: dict[str, str] = {}
        self.xadd_calls: list[tuple[str, dict[str, str]]] = []

    async def ping(self) -> bool:
        return True

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:
        if nx and key in self._kv:
            return False
        self._kv[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self._kv.get(key)

    async def delete(self, key: str) -> int:
        return 1 if self._kv.pop(key, None) is not None else 0

    async def xadd(
        self,
        stream: str,
        fields: dict[str, str],
        maxlen: int | None = None,
        approximate: bool = False,
    ) -> str:
        self.xadd_calls.append((stream, fields))
        return f"{len(self.xadd_calls)}-0"

    async def incr(self, key: str) -> int:
        current = int(self._kv.get(key, "0"))
        current += 1
        self._kv[key] = str(current)
        return current

    async def expire(self, key: str, seconds: int) -> bool:
        return True

    async def aclose(self) -> None:
        return None

    async def close(self) -> None:
        return None


class FakeTask:
    def __init__(self, *, done: bool = False) -> None:
        self._done = done

    def done(self) -> bool:
        return self._done

    def cancel(self) -> None:
        self._done = True

    def __await__(self):
        async def _cancelled():
            raise asyncio.CancelledError

        return _cancelled().__await__()


def test_gateway_idempotency_reuses_initial_result() -> None:
    fake_redis = FakeRedis()
    with TestClient(api_app) as client:
        api_app.state.redis = fake_redis
        api_app.state.redis_ready = True

        payload = {
            "prompt": "Build an API for payments",
            "requested_target_language": "python",
            "metadata": {"source": "test"},
        }
        headers = {"Idempotency-Key": "mission-key-123"}

        first = client.post("/v1/missions", json=payload, headers=headers)
        second = client.post("/v1/missions", json=payload, headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["mission_id"] == second.json()["mission_id"]
        assert len(fake_redis.xadd_calls) == 1


def test_gateway_idempotency_rejects_payload_mismatch() -> None:
    fake_redis = FakeRedis()
    with TestClient(api_app) as client:
        api_app.state.redis = fake_redis
        api_app.state.redis_ready = True

        first_payload = {"prompt": "Build service A", "metadata": {"source": "test"}}
        second_payload = {"prompt": "Build service B", "metadata": {"source": "test"}}
        headers = {"Idempotency-Key": "mission-key-xyz"}

        first = client.post("/v1/missions", json=first_payload, headers=headers)
        second = client.post("/v1/missions", json=second_payload, headers=headers)

        assert first.status_code == 200
        assert second.status_code == 409
        assert "different mission payload" in second.json()["detail"]


def test_gateway_readyz_returns_503_on_dependency_failure(monkeypatch) -> None:
    async def _dependency_status() -> dict[str, bool]:
        return {"orchestrator_healthy": False, "redis_healthy": True}

    monkeypatch.setattr(api_gateway_main, "_dependency_status", _dependency_status)
    client = TestClient(api_app)
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["detail"]["ready"] is False


def test_gateway_metrics_endpoint_exposes_prometheus_payload() -> None:
    client = TestClient(api_app)
    client.get("/")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "api_gateway_http_requests_total" in response.text


def test_gateway_adds_security_headers() -> None:
    client = TestClient(api_app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"


def test_gateway_rate_limit_blocks_excess_requests(monkeypatch) -> None:
    fake_redis = FakeRedis()
    monkeypatch.setattr(api_gateway_main, "API_RATE_LIMIT_PER_MINUTE", 1)
    with TestClient(api_app) as client:
        api_app.state.redis = fake_redis
        api_app.state.redis_ready = True

        payload = {
            "prompt": "Build API once",
            "requested_target_language": "python",
            "metadata": {"source": "test"},
        }
        first = client.post("/v1/missions", json=payload)
        second = client.post("/v1/missions", json=payload)

    assert first.status_code == 200
    assert second.status_code == 429


def test_orchestrator_readyz_reports_ready(monkeypatch) -> None:
    async def _runtime_ready(_: Any) -> tuple[bool, bool]:
        return True, True

    monkeypatch.setattr(orchestrator_main, "ensure_runtime_ready", _runtime_ready)
    with TestClient(orchestrator_app) as client:
        orchestrator_app.state.protocol_ready = True
        orchestrator_app.state.consumer_task = FakeTask(done=False)
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_orchestrator_readyz_returns_503_when_consumer_not_running(monkeypatch) -> None:
    async def _runtime_ready(_: Any) -> tuple[bool, bool]:
        return True, True

    monkeypatch.setattr(orchestrator_main, "ensure_runtime_ready", _runtime_ready)
    with TestClient(orchestrator_app) as client:
        orchestrator_app.state.protocol_ready = True
        orchestrator_app.state.consumer_task = FakeTask(done=True)
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["detail"]["consumer_running"] is False
