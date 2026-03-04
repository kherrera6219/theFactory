import importlib
import sys
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api-gateway"))

api_gateway_main = importlib.import_module("api_gateway.main")
api_app = api_gateway_main.app


class _DummyResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAsyncClient:
    captured_headers: list[dict[str, str]] = []

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def post(
        self,
        url: str,
        json: dict[str, Any],
        headers: dict[str, str],
    ) -> _DummyResponse:
        self.__class__.captured_headers.append(headers)
        return _DummyResponse(200, {"ok": True, "url": url, "payload": json})


def test_extract_bearer_token() -> None:
    assert api_gateway_main._extract_bearer_token("Bearer token-1") == "token-1"
    assert api_gateway_main._extract_bearer_token("bearer token-2") == "token-2"
    assert api_gateway_main._extract_bearer_token("Basic abc") is None
    assert api_gateway_main._extract_bearer_token(None) is None


def test_claim_includes_required_role() -> None:
    claims = {"roles": ["read", "mutate"], "scope": "openid profile"}
    assert api_gateway_main._claim_includes_required_role(claims, "mutate") is True
    assert api_gateway_main._claim_includes_required_role(claims, "admin") is False


def test_resolve_mutation_headers_api_key_mode_requires_key(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "api_key")
    with TestClient(api_app):
        try:
            api_gateway_main._resolve_mutation_forward_headers(
                x_api_key=None,
                authorization=None,
            )
        except HTTPException as exc:
            assert exc.status_code == 401
        else:
            raise AssertionError("expected HTTPException for missing api key")


def test_resolve_mutation_headers_hybrid_mode_allows_api_key(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "hybrid")
    headers = api_gateway_main._resolve_mutation_forward_headers(
        x_api_key="operator-key",
        authorization=None,
    )
    assert headers == {"x-api-key": "operator-key"}


def test_resolve_mutation_headers_hybrid_mode_allows_bearer(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "hybrid")
    monkeypatch.setattr(
        api_gateway_main,
        "_decode_oidc_token",
        lambda _token: {"roles": ["mutate"]},
    )
    headers = api_gateway_main._resolve_mutation_forward_headers(
        x_api_key=None,
        authorization="Bearer test-token",
    )
    assert headers == {"x-api-key": api_gateway_main.INTERNAL_SERVICE_API_KEY}


def test_resolve_mutation_headers_oidc_mode_requires_bearer(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "oidc")
    with TestClient(api_app):
        try:
            api_gateway_main._resolve_mutation_forward_headers(
                x_api_key=None,
                authorization=None,
            )
        except HTTPException as exc:
            assert exc.status_code == 401
        else:
            raise AssertionError("expected HTTPException for missing bearer token")


def test_resolve_mutation_headers_oidc_mode_requires_role(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "oidc")
    monkeypatch.setattr(
        api_gateway_main,
        "_decode_oidc_token",
        lambda _token: {"roles": ["read"]},
    )
    with TestClient(api_app):
        try:
            api_gateway_main._resolve_mutation_forward_headers(
                x_api_key=None,
                authorization="Bearer test-token",
            )
        except HTTPException as exc:
            assert exc.status_code == 403
        else:
            raise AssertionError("expected HTTPException for missing oidc role")


def test_update_state_forwards_internal_key_in_oidc_mode(monkeypatch) -> None:
    _FakeAsyncClient.captured_headers = []
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "oidc")
    monkeypatch.setattr(
        api_gateway_main,
        "_decode_oidc_token",
        lambda _token: {"roles": ["mutate"]},
    )
    monkeypatch.setattr(api_gateway_main.httpx, "AsyncClient", _FakeAsyncClient)

    with TestClient(api_app) as client:
        response = client.post(
            "/v1/missions/mission-1/state",
            headers={"Authorization": "Bearer token-1"},
            json={"new_state": "FAILED"},
        )

    assert response.status_code == 200
    assert _FakeAsyncClient.captured_headers[-1] == {
        "x-api-key": api_gateway_main.INTERNAL_SERVICE_API_KEY
    }


def test_update_state_forwards_caller_key_in_hybrid_mode(monkeypatch) -> None:
    _FakeAsyncClient.captured_headers = []
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "hybrid")
    monkeypatch.setattr(api_gateway_main.httpx, "AsyncClient", _FakeAsyncClient)

    with TestClient(api_app) as client:
        response = client.post(
            "/v1/missions/mission-1/state",
            headers={"x-api-key": "operator-key"},
            json={"new_state": "FAILED"},
        )

    assert response.status_code == 200
    assert _FakeAsyncClient.captured_headers[-1] == {"x-api-key": "operator-key"}
