from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException

from .settings import Settings


@dataclass(frozen=True)
class AuthContext:
    api_key: str
    roles: set[str]


def require_roles(settings: Settings, allowed_roles: set[str]):
    api_key_roles = settings.api_key_roles

    async def _dependency(x_api_key: str | None = Header(default=None)) -> AuthContext:
        if not x_api_key:
            raise HTTPException(status_code=401, detail="x-api-key header is required")

        roles = api_key_roles.get(x_api_key)
        if roles is None:
            raise HTTPException(status_code=401, detail="invalid api key")

        if allowed_roles and roles.isdisjoint(allowed_roles):
            raise HTTPException(status_code=403, detail="insufficient role for endpoint")

        return AuthContext(api_key=x_api_key, roles=roles)

    return _dependency
