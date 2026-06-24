import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "dashboard"))

dashboard_main = importlib.import_module("dashboard.main")


class DummyResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


def test_snapshot_success(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str) -> DummyResponse:
            return DummyResponse(200, {"ok": True})

    monkeypatch.setattr(dashboard_main.httpx, "AsyncClient", FakeClient)
    result = asyncio.run(dashboard_main.snapshot())
    assert result.ok is True
    assert result.api_gateway_status == 200


def test_snapshot_failure(monkeypatch) -> None:
    class FailingClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str) -> DummyResponse:
            raise RuntimeError("network down")

    monkeypatch.setattr(dashboard_main.httpx, "AsyncClient", FailingClient)
    result = asyncio.run(dashboard_main.snapshot())
    assert result.ok is False
    # Error responses expose only the exception type, not the raw message,
    # to avoid leaking sensitive content (CodeQL clear-text logging hardening).
    assert result.error is not None
    assert "RuntimeError" in result.error
    assert "network down" not in result.error


def test_index_contains_dashboard_title() -> None:
    html = dashboard_main.index()
    assert "HolyGrail Dashboard" in html
