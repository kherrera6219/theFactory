from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Header, HTTPException

from .settings import Settings


@dataclass(frozen=True)
class AuthContext:
    api_key: str
    roles: set[str]


def _match_api_key(candidate: str, api_key_roles: dict[str, set[str]]) -> set[str] | None:
    # Walk every configured key and use a constant-time compare on each. Dict
    # .get(key) leaks timing via hash lookup + Python's short-circuiting `==`
    # on str; hmac.compare_digest is the safe primitive.
    candidate_bytes = candidate.encode("utf-8")
    matched: set[str] | None = None
    for stored_key, roles in api_key_roles.items():
        if hmac.compare_digest(candidate_bytes, stored_key.encode("utf-8")):
            matched = roles
    return matched


def require_roles(settings: Settings, allowed_roles: set[str]):
    api_key_roles = settings.api_key_roles

    async def _dependency(x_api_key: str | None = Header(default=None)) -> AuthContext:
        if not x_api_key:
            raise HTTPException(status_code=401, detail="x-api-key header is required")

        roles = _match_api_key(x_api_key, api_key_roles)
        if roles is None:
            raise HTTPException(status_code=401, detail="invalid api key")

        if allowed_roles and roles.isdisjoint(allowed_roles):
            raise HTTPException(status_code=403, detail="insufficient role for endpoint")

        return AuthContext(api_key=x_api_key, roles=roles)

    return _dependency
