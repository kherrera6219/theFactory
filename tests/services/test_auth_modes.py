"""
test_auth_modes.py

Unit and integration tests for Phase 5: Zero-Trust Multi-Tenant OIDC & Gateway Hardening.
Verifies:
  - Strict OIDC claim enforcement (sub, iss, aud, roles, tenant)
  - Keycloak / Okta / Azure AD token claims
  - Inter-service Mutual TLS (mTLS) context configuration
"""
from __future__ import annotations

import ssl
from pathlib import Path

import pytest
from api_gateway.middleware import (
    build_mtls_ssl_context,
    validate_strict_oidc_claims,
)
from fastapi import HTTPException


def test_validate_strict_oidc_claims_valid() -> None:
    claims = {
        "sub": "user_123456",
        "iss": "https://auth.enterprise.corp/realms/thefactory",
        "aud": "thefactory-api",
        "roles": ["read", "mutate", "observe"],
        "tenant_id": "tenant-corp-1",
    }
    validated = validate_strict_oidc_claims(
        claims,
        required_role="mutate",
        expected_issuer="https://auth.enterprise.corp/realms/thefactory",
        expected_audience="thefactory-api",
        required_tenant="tenant-corp-1",
    )
    assert validated["sub"] == "user_123456"


def test_validate_strict_oidc_claims_missing_sub() -> None:
    claims = {
        "iss": "https://auth.enterprise.corp",
        "aud": "thefactory-api",
        "roles": ["mutate"],
    }
    with pytest.raises(HTTPException) as exc_info:
        validate_strict_oidc_claims(claims)
    assert exc_info.value.status_code == 401
    assert "sub" in exc_info.value.detail


def test_validate_strict_oidc_claims_issuer_mismatch() -> None:
    claims = {
        "sub": "user_123",
        "iss": "https://rogue-issuer.corp",
    }
    with pytest.raises(HTTPException) as exc_info:
        validate_strict_oidc_claims(claims, expected_issuer="https://auth.enterprise.corp")
    assert exc_info.value.status_code == 401
    assert "issuer" in exc_info.value.detail or "iss" in exc_info.value.detail


def test_validate_strict_oidc_claims_audience_mismatch() -> None:
    claims = {
        "sub": "user_123",
        "aud": "other-app",
    }
    with pytest.raises(HTTPException) as exc_info:
        validate_strict_oidc_claims(claims, expected_audience="thefactory-api")
    assert exc_info.value.status_code == 401
    assert "audience" in exc_info.value.detail


def test_validate_strict_oidc_claims_tenant_mismatch() -> None:
    claims = {
        "sub": "user_123",
        "tenant_id": "tenant-beta",
    }
    with pytest.raises(HTTPException) as exc_info:
        validate_strict_oidc_claims(claims, required_tenant="tenant-alpha")
    assert exc_info.value.status_code == 403
    assert "tenant" in exc_info.value.detail


def test_validate_strict_oidc_claims_roles_formats() -> None:
    # 1. Keycloak realm_access.roles
    keycloak_claims = {
        "sub": "user_kc",
        "realm_access": {"roles": ["observe", "mutate"]},
    }
    assert validate_strict_oidc_claims(keycloak_kc := keycloak_claims, required_role="mutate") == keycloak_kc

    # 2. Azure AD groups / Okta groups
    okta_claims = {
        "sub": "user_okta",
        "groups": ["engineering", "mutate"],
    }
    assert validate_strict_oidc_claims(okta_claims, required_role="mutate") == okta_claims

    # 3. OAuth scope string
    scope_claims = {
        "sub": "user_scope",
        "scope": "openid email mutate",
    }
    assert validate_strict_oidc_claims(scope_claims, required_role="mutate") == scope_claims

    # 4. Missing required role -> 403
    with pytest.raises(HTTPException) as exc_info:
        validate_strict_oidc_claims(scope_claims, required_role="admin")
    assert exc_info.value.status_code == 403
    assert "missing 'admin' role" in exc_info.value.detail


def test_build_mtls_ssl_context_missing_files(tmp_path: Path) -> None:
    ca = tmp_path / "ca.crt"
    cert = tmp_path / "client.crt"
    key = tmp_path / "client.key"

    # None if no paths given
    assert build_mtls_ssl_context() is None

    # Missing CA file
    with pytest.raises(ValueError, match="mTLS CA certificate not found"):
        build_mtls_ssl_context(ca_cert=str(ca), client_cert=str(cert), client_key=str(key))

    # CA exists, cert missing
    ca.write_text("dummy ca", encoding="utf-8")
    with pytest.raises(ValueError, match="mTLS client certificate not found"):
        build_mtls_ssl_context(ca_cert=str(ca), client_cert=str(cert), client_key=str(key))

    # Cert exists, key missing
    cert.write_text("dummy cert", encoding="utf-8")
    with pytest.raises(ValueError, match="mTLS client private key not found"):
        build_mtls_ssl_context(ca_cert=str(ca), client_cert=str(cert), client_key=str(key))


def test_build_mtls_ssl_context_with_valid_ca(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ca = tmp_path / "ca.crt"
    cert = tmp_path / "client.crt"
    key = tmp_path / "client.key"
    ca.write_text("ca", encoding="utf-8")
    cert.write_text("cert", encoding="utf-8")
    key.write_text("key", encoding="utf-8")

    class _MockSSLContext:
        verify_mode = None
        def load_cert_chain(self, certfile: str, keyfile: str) -> None:
            pass

    monkeypatch.setattr(ssl, "create_default_context", lambda *_args, **_kwargs: _MockSSLContext())

    ctx = build_mtls_ssl_context(ca_cert=str(ca), client_cert=str(cert), client_key=str(key))
    assert ctx is not None
    assert ctx.verify_mode == ssl.CERT_REQUIRED
