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
    monkeypatch.setattr(api_gateway_main, "INTERNAL_SERVICE_API_KEY", "internal-key")
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


def test_resolve_mutation_headers_hybrid_mode_requires_internal_key_for_bearer(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "hybrid")
    monkeypatch.setattr(api_gateway_main, "INTERNAL_SERVICE_API_KEY", "")
    monkeypatch.setattr(
        api_gateway_main,
        "_decode_oidc_token",
        lambda _token: {"roles": ["mutate"]},
    )
    with TestClient(api_app):
        try:
            api_gateway_main._resolve_mutation_forward_headers(
                x_api_key=None,
                authorization="Bearer test-token",
            )
        except HTTPException as exc:
            assert exc.status_code == 503
        else:
            raise AssertionError("expected HTTPException for missing internal service key")


def test_resolve_mutation_headers_oidc_mode_requires_bearer(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "oidc")
    monkeypatch.setattr(api_gateway_main, "OIDC_ISSUER_URL", "https://issuer.example")
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
    monkeypatch.setattr(api_gateway_main, "OIDC_ISSUER_URL", "https://issuer.example")
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


def test_require_operator_access_api_key_mode_requires_key(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "api_key")
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", False)
    # Missing key -> 401
    try:
        api_gateway_main._require_operator_access(x_api_key=None, authorization=None)
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("expected HTTPException for missing api key")

    # Unknown key -> 401
    monkeypatch.setattr(
        api_gateway_main, "_gateway_api_key_roles", lambda: {"good-key": {"read"}}
    )
    try:
        api_gateway_main._require_operator_access(x_api_key="bad-key", authorization=None)
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("expected HTTPException for unknown api key")

    # Valid key with read role -> allowed (no exception)
    api_gateway_main._require_operator_access(x_api_key="good-key", authorization=None)


def test_require_operator_access_api_key_mode_bypass(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "api_key")
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)
    # Bypass short-circuits all auth.
    api_gateway_main._require_operator_access(x_api_key=None, authorization=None)


def test_require_operator_access_oidc_mode_requires_bearer(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "oidc")
    monkeypatch.setattr(api_gateway_main, "OIDC_ISSUER_URL", "https://issuer.example")
    monkeypatch.setattr(api_gateway_main, "OIDC_ENFORCE_OPERATOR_ROUTES", True)
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", False)
    with TestClient(api_app):
        try:
            api_gateway_main._require_operator_access(x_api_key=None, authorization=None)
        except HTTPException as exc:
            assert exc.status_code == 401
        else:
            raise AssertionError("expected HTTPException for missing bearer token")


def test_require_operator_access_oidc_requires_operator_role(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "oidc")
    monkeypatch.setattr(api_gateway_main, "OIDC_ISSUER_URL", "https://issuer.example")
    monkeypatch.setattr(api_gateway_main, "OIDC_ENFORCE_OPERATOR_ROUTES", True)
    monkeypatch.setattr(api_gateway_main, "OIDC_OPERATOR_ROLE", "observe")
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", False)
    monkeypatch.setattr(
        api_gateway_main,
        "_decode_oidc_token",
        lambda _token: {"roles": ["mutate"]},
    )
    with TestClient(api_app):
        try:
            api_gateway_main._require_operator_access(
                x_api_key=None,
                authorization="Bearer test-token",
            )
        except HTTPException as exc:
            assert exc.status_code == 403
        else:
            raise AssertionError("expected HTTPException for missing operator role")


def test_require_operator_access_hybrid_allows_api_key(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "hybrid")
    monkeypatch.setattr(api_gateway_main, "OIDC_ENFORCE_OPERATOR_ROUTES", True)
    monkeypatch.setattr(
        api_gateway_main, "_gateway_api_key_roles", lambda: {"operator-key": {"read"}}
    )
    api_gateway_main._require_operator_access(x_api_key="operator-key", authorization=None)


def test_require_operator_access_hybrid_rejects_unknown_api_key(monkeypatch) -> None:
    # Regression: hybrid mode's X-API-Key branch used to grant operator access
    # on ANY non-empty header with zero validation against configured gateway
    # keys, unlike its api_key-mode sibling branch and _require_reader_access's
    # own hybrid-mode X-API-Key branch.
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "hybrid")
    monkeypatch.setattr(api_gateway_main, "OIDC_ENFORCE_OPERATOR_ROUTES", True)
    monkeypatch.setattr(
        api_gateway_main, "_gateway_api_key_roles", lambda: {"good-key": {"read"}}
    )
    try:
        api_gateway_main._require_operator_access(x_api_key="not-a-real-key", authorization=None)
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("expected HTTPException for unknown api key in hybrid mode")


def test_update_state_forwards_internal_key_in_oidc_mode(monkeypatch) -> None:
    _FakeAsyncClient.captured_headers = []
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "oidc")
    monkeypatch.setattr(api_gateway_main, "OIDC_ISSUER_URL", "https://issuer.example")
    monkeypatch.setattr(api_gateway_main, "INTERNAL_SERVICE_API_KEY", "internal-key")
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


def test_operations_summary_requires_oidc_operator_role(monkeypatch) -> None:
    async def _fake_proxy_get_internal(_path: str, *, params: dict[str, Any] | None = None) -> Any:
        assert params is None
        return {"ok": True}

    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "oidc")
    monkeypatch.setattr(api_gateway_main, "OIDC_ISSUER_URL", "https://issuer.example")
    monkeypatch.setattr(api_gateway_main, "OIDC_ENFORCE_OPERATOR_ROUTES", True)
    monkeypatch.setattr(api_gateway_main, "OIDC_OPERATOR_ROLE", "observe")
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", False)
    monkeypatch.setattr(api_gateway_main, "_proxy_get_internal", _fake_proxy_get_internal)
    with TestClient(api_app) as client:
        unauthorized = client.get("/v1/operations/summary")
        assert unauthorized.status_code == 401

        monkeypatch.setattr(
            api_gateway_main,
            "_decode_oidc_token",
            lambda _token: {"roles": ["read"]},
        )
        forbidden = client.get(
            "/v1/operations/summary",
            headers={"Authorization": "Bearer test-token"},
        )
        assert forbidden.status_code == 403

        monkeypatch.setattr(
            api_gateway_main,
            "_decode_oidc_token",
            lambda _token: {"roles": ["observe"]},
        )
        allowed = client.get(
            "/v1/operations/summary",
            headers={"Authorization": "Bearer test-token"},
        )
        assert allowed.status_code == 200
        assert allowed.json()["ok"] is True


def test_validate_startup_auth_config_oidc_requires_issuer(monkeypatch) -> None:
    # H-2: oidc mode without an issuer must fail startup.
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "oidc")
    monkeypatch.setattr(api_gateway_main, "OIDC_ISSUER_URL", "")
    try:
        api_gateway_main._validate_startup_auth_config()
    except RuntimeError as exc:
        assert "OIDC_ISSUER_URL" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for missing OIDC_ISSUER_URL in oidc mode")


def test_prompt_guard_mode_defaults_to_block() -> None:
    # Regression: PROMPT_GUARD_MODE used to default to "log", so OWASP LLM01
    # prompt-injection attempts were only recorded in scan metadata while the
    # mission proceeded to persistence anyway. It must default to "block".
    #
    # Do not read the imported module constant: other tests (and a local
    # `.env`) can mutate PROMPT_GUARD_MODE after import. The source default
    # is the contract.
    source = Path(api_gateway_main.__file__).read_text(encoding="utf-8")
    assert 'os.getenv("PROMPT_GUARD_MODE", "block")' in source


def test_validate_startup_auth_config_hybrid_missing_audience_ok(monkeypatch) -> None:
    # H-2: hybrid mode without audience only warns (does not fail).
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "hybrid")
    monkeypatch.setattr(api_gateway_main, "OIDC_AUDIENCE", "")
    monkeypatch.setattr(api_gateway_main, "OIDC_ISSUER_URL", "")
    api_gateway_main._validate_startup_auth_config()


def test_validate_startup_auth_config_rejects_invalid_auth_mode(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "broken")
    try:
        api_gateway_main._validate_startup_auth_config()
    except RuntimeError as exc:
        assert "AUTH_MODE" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for invalid AUTH_MODE")


def test_validate_startup_auth_config_rejects_wildcard_cors_in_production(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "api_key")
    monkeypatch.setattr(api_gateway_main, "ENVIRONMENT", "production")
    monkeypatch.setattr(api_gateway_main, "CORS_ALLOW_ORIGINS", "https://app.example,*")
    try:
        api_gateway_main._validate_startup_auth_config()
    except RuntimeError as exc:
        assert "CORS_ALLOW_ORIGINS" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for wildcard CORS in production")


def test_validate_startup_auth_config_rejects_admin_bypass_in_production(monkeypatch) -> None:
    # Regression: GATEWAY_ADMIN_BYPASS=true in production used to only log a
    # warning while leaving all operator route authorization disabled — it
    # must fail fast at startup like the adjacent CORS-wildcard check.
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "api_key")
    monkeypatch.setattr(api_gateway_main, "ENVIRONMENT", "production")
    monkeypatch.setattr(api_gateway_main, "CORS_ALLOW_ORIGINS", "https://app.example")
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)
    try:
        api_gateway_main._validate_startup_auth_config()
    except RuntimeError as exc:
        assert "GATEWAY_ADMIN_BYPASS" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for GATEWAY_ADMIN_BYPASS=true in production")


def test_validate_startup_auth_config_allows_admin_bypass_outside_production(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "api_key")
    monkeypatch.setattr(api_gateway_main, "ENVIRONMENT", "development")
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)
    api_gateway_main._validate_startup_auth_config()


def test_previously_unauthenticated_mission_read_routes_now_require_auth(monkeypatch) -> None:
    # Regression: these routes forwarded straight to the orchestrator's
    # /internal/* endpoints with zero caller authentication -- any caller
    # could read mission prompts, source code, audit trails, and build
    # artifacts for any mission_id with no credentials at all.
    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "api_key")
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", False)

    async def _fail_if_reached(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("orchestrator must not be reached without authentication")

    monkeypatch.setattr(api_gateway_main, "_proxy_get_internal", _fail_if_reached)
    monkeypatch.setattr(api_gateway_main, "_proxy_post_internal", _fail_if_reached)

    post_bodies: dict[str, dict[str, Any]] = {
        "/v1/missions": {"prompt": "Build a reporting API"},
        "/v1/pm/feature-contract": {"prompt": "Draft a feature contract"},
        "/v1/builder/preview": {"request": "Add audit dashboard"},
    }

    with TestClient(api_app) as client:
        for method, path in [
            ("post", "/v1/missions"),
            ("get", "/v1/missions/mission-1/pod-assignment"),
            ("get", "/v1/missions/mission-1/chain-trace"),
            ("post", "/v1/pm/feature-contract"),
            ("get", "/v1/missions/mission-1/logicnodes"),
            ("get", "/v1/missions/mission-1/knowledge"),
            ("get", "/v1/missions/mission-1/knowledge-graph"),
            ("get", "/v1/missions/mission-1/audit-reports"),
            ("get", "/v1/missions/mission-1/audit-artifacts"),
            ("get", "/v1/missions/mission-1/audit-events"),
            ("get", "/v1/missions/mission-1/build-artifacts"),
            ("get", "/v1/missions/mission-1/build-artifacts/artifact-1"),
            ("get", "/v1/missions/mission-1/artifact"),
            ("post", "/v1/builder/preview"),
        ]:
            if method == "post":
                response = client.post(path, json=post_bodies.get(path, {}))
            else:
                response = client.get(path)
            assert response.status_code == 401, f"{method.upper()} {path} allowed anonymous access"


def test_maintenance_routes_proxy_call_signatures(monkeypatch) -> None:
    # H-3: diagnostics passed params=, backup omitted json_body — both raised TypeError.
    captured: list[tuple[str, dict[str, Any] | None, dict[str, Any] | None]] = []

    async def _fake_post_internal(path, *, json_body=None, params=None):
        captured.append((path, json_body, params))
        return {"ok": True}

    monkeypatch.setattr(api_gateway_main, "AUTH_MODE", "api_key")
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)
    monkeypatch.setattr(api_gateway_main, "_proxy_post_internal", _fake_post_internal)

    with TestClient(api_app) as client:
        diag = client.post("/v1/maintenance/diagnostics", params={"mission_id": "m-1"})
        assert diag.status_code == 200
        backup = client.post("/v1/maintenance/backup")
        assert backup.status_code == 200

    paths = [c[0] for c in captured]
    assert "/internal/maintenance/diagnostics" in paths
    assert "/internal/maintenance/backup" in paths


def test_read_and_write_rate_limits_use_separate_buckets() -> None:
    """A polling dashboard must not be able to starve mission creation.

    Mission Control issues ~13 read requests per poll cycle on the same
    credential everything else uses. Against one shared 120/min budget that
    exhausted the allowance and mission creation returned 429 -- an open browser
    tab denying service to every other client, including the live test suite.
    """
    import api_gateway.main as gateway

    assert gateway.API_READ_RATE_LIMIT_PER_MINUTE > gateway.API_RATE_LIMIT_PER_MINUTE, (
        "read budget must exceed the write budget or polling still starves writes"
    )
    assert "GET" in gateway._SAFE_METHODS
    assert "POST" not in gateway._SAFE_METHODS, (
        "mission creation must stay on the tighter write budget"
    )


def test_rate_limit_bucket_is_part_of_the_redis_key() -> None:
    """Separate limits are meaningless if both increment the same counter."""
    import asyncio

    import api_gateway.main as gateway

    keys: list[str] = []

    class _Redis:
        async def incr(self, key: str) -> int:
            keys.append(key)
            return 1

        async def expire(self, key: str, ttl: int) -> None:
            return None

    async def _exercise() -> None:
        await gateway._check_rate_limit(_Redis(), "same-caller", limit=10, bucket="read")
        await gateway._check_rate_limit(_Redis(), "same-caller", limit=10, bucket="write")

    asyncio.run(_exercise())
    assert len(keys) == 2 and keys[0] != keys[1], keys
