"""auth.py — Stateless token/claim utility functions for the API Gateway.

These functions are pure (no config reads, no module-level state) and are
imported into main.py. Config-reading auth functions (_decode_oidc_token,
_require_operator_access, etc.) live in main.py so that test monkeypatching
on the main module's namespace works correctly.
"""
from __future__ import annotations

from typing import Any

from .config import OIDC_ROLE_CLAIMS, OIDC_SCOPE_CLAIMS


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.strip().lower() != "bearer":
        return None
    candidate = token.strip()
    return candidate or None


def _tokens_from_claim_value(value: Any) -> set[str]:
    if isinstance(value, str):
        raw_items = value.replace(",", " ").split()
        return {item.strip().lower() for item in raw_items if item.strip()}
    if isinstance(value, list):
        normalized: set[str] = set()
        for item in value:
            if isinstance(item, str) and item.strip():
                normalized.add(item.strip().lower())
        return normalized
    return set()


def _claim_includes_required_role(claims: dict[str, Any], required_role: str) -> bool:
    required = required_role.strip().lower()
    if not required:
        return True

    tokens: set[str] = set()
    for claim_name in OIDC_ROLE_CLAIMS + OIDC_SCOPE_CLAIMS:
        tokens.update(_tokens_from_claim_value(claims.get(claim_name)))

    return required in tokens
