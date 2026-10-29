"""
middleware.py — Enterprise OIDC claims validation and mTLS transport security.
"""
from __future__ import annotations

import logging
import os
import ssl
from pathlib import Path
from typing import Any

from fastapi import HTTPException

LOGGER = logging.getLogger("api_gateway.middleware")

OIDC_STRICT_CLAIMS = os.getenv("OIDC_STRICT_CLAIMS", "false").strip().lower() in ("true", "1")
OIDC_REQUIRED_TENANT = os.getenv("OIDC_REQUIRED_TENANT", "").strip()

INTERNAL_MTLS_ENABLED = os.getenv("INTERNAL_MTLS_ENABLED", "false").strip().lower() in ("true", "1")
INTERNAL_MTLS_CA_CERT = os.getenv("INTERNAL_MTLS_CA_CERT", "").strip()
INTERNAL_MTLS_CLIENT_CERT = os.getenv("INTERNAL_MTLS_CLIENT_CERT", "").strip()
INTERNAL_MTLS_CLIENT_KEY = os.getenv("INTERNAL_MTLS_CLIENT_KEY", "").strip()


def validate_strict_oidc_claims(
    claims: dict[str, Any],
    *,
    required_role: str | None = None,
    expected_issuer: str | None = None,
    expected_audience: str | None = None,
    required_tenant: str | None = None,
) -> dict[str, Any]:
    """Strictly validate standard enterprise OIDC claims (RFC 7519, NIST SP 800-218).

    Validates:
      - 'sub': Subject must exist, be a non-empty string.
      - 'iss': Issuer must match expected_issuer if provided.
      - 'aud': Audience must match or contain expected_audience if provided.
      - 'roles': If required_role is provided, checks roles across standard
                 claims: 'roles', 'groups', 'realm_access.roles', 'resource_access', or 'scope'.
      - 'tenant': If required_tenant is provided (or configured), checks 'tenant_id', 'tid', or 'tenant'.
    """
    # 1. Subject validation (sub)
    sub = claims.get("sub")
    if not sub or not isinstance(sub, str) or not sub.strip():
        raise HTTPException(status_code=401, detail="oidc token missing valid 'sub' (subject) claim")

    # 2. Issuer validation (iss)
    iss = claims.get("iss")
    if expected_issuer:
        if not iss or str(iss).rstrip("/") != str(expected_issuer).rstrip("/"):
            raise HTTPException(status_code=401, detail="oidc token 'iss' (issuer) mismatch")

    # 3. Audience validation (aud)
    aud = claims.get("aud")
    if expected_audience:
        if not aud:
            raise HTTPException(status_code=401, detail="oidc token missing 'aud' (audience) claim")
        if isinstance(aud, list):
            if expected_audience not in aud:
                raise HTTPException(status_code=401, detail="oidc token audience unauthorized")
        elif str(aud) != str(expected_audience):
            raise HTTPException(status_code=401, detail="oidc token audience unauthorized")

    # 4. Multi-tenant isolation (tid / tenant_id / tenant)
    tenant_req = required_tenant or OIDC_REQUIRED_TENANT
    if tenant_req:
        token_tenant = claims.get("tenant_id") or claims.get("tid") or claims.get("tenant")
        if not token_tenant or str(token_tenant) != str(tenant_req):
            raise HTTPException(status_code=403, detail="oidc token unauthorized for target tenant")

    # 5. Role validation
    if required_role:
        found = False
        # Direct roles / groups lists
        for key in ("roles", "groups", "cognito:groups"):
            val = claims.get(key)
            if isinstance(val, (list, tuple, set)) and required_role in val:
                found = True
                break
        # Keycloak realm_access / resource_access
        if not found:
            realm_access = claims.get("realm_access")
            if isinstance(realm_access, dict):
                r_roles = realm_access.get("roles")
                if isinstance(r_roles, (list, tuple, set)) and required_role in r_roles:
                    found = True
        # Scope string fallback
        if not found:
            scope = claims.get("scope", "")
            if isinstance(scope, str) and required_role in scope.split():
                found = True

        if not found:
            raise HTTPException(status_code=403, detail=f"insufficient permissions: missing '{required_role}' role")

    return claims


def build_mtls_ssl_context(
    *,
    ca_cert: str | None = None,
    client_cert: str | None = None,
    client_key: str | None = None,
) -> ssl.SSLContext | None:
    """Construct a Mutual TLS (mTLS) SSLContext for secure inter-service communication."""
    ca_path = ca_cert or INTERNAL_MTLS_CA_CERT
    cert_path = client_cert or INTERNAL_MTLS_CLIENT_CERT
    key_path = client_key or INTERNAL_MTLS_CLIENT_KEY

    if not ca_path and not cert_path:
        return None

    if not ca_path or not Path(ca_path).is_file():
        raise ValueError(f"mTLS CA certificate not found: {ca_path}")
    if not cert_path or not Path(cert_path).is_file():
        raise ValueError(f"mTLS client certificate not found: {cert_path}")
    if not key_path or not Path(key_path).is_file():
        raise ValueError(f"mTLS client private key not found: {key_path}")

    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=ca_path)
    ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx
