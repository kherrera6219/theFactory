"""Credential resolution shared by the live-stack integration tests.

Not a test module (no ``test_`` prefix, so pytest will not collect it). It
exists because both live suites talk to the same api-gateway, which runs
``AUTH_MODE=api_key`` and rejects unauthenticated callers with 401 -- keeping
one copy of that logic is the only way to stop the two from drifting apart
again, which is exactly how one of them shipped sending no credential at all.
"""

from __future__ import annotations

import os
from pathlib import Path


def dotenv_values() -> dict[str, str]:
    """Read the repo ``.env`` so live tests use the credential the running
    stack was actually started with.

    Walks upward from this file because the suite is sometimes run from a git
    worktree, where ``.env`` (gitignored) exists only in the main working tree.
    Values are returned, never written into ``os.environ`` -- mutating the
    environment at import time previously caused an order-dependent flake (see
    ``scripts/operator_route_auth_matrix_qualification.py``).
    """
    override = os.getenv("LIVE_ENV_FILE", "").strip()
    if override:
        candidates = [Path(override)]
    else:
        candidates = [parent / ".env" for parent in Path(__file__).resolve().parents]
    for env_file in candidates:
        if not env_file.is_file():
            continue
        values: dict[str, str] = {}
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            # Deliberately no inline-comment stripping: '#' is a legal character
            # inside a secret, and stripping it corrupts real credentials.
            values[key.strip()] = value.strip()
        return values
    return {}


def resolve_internal_service_api_key() -> str:
    """Resolve the gateway/orchestrator API key, with no well-known fallback.

    ``INTERNAL_SERVICE_API_KEY`` is registered at the gateway with roles
    ``{worker, mutate, internal, read}``, which is what every ``/v1/*`` route
    (``_require_reader_access``) and ``/internal/*`` route demands. Guessing a
    placeholder key here would only turn a missing-config error into an opaque
    401, so callers should skip when this returns an empty string.
    """
    for candidate in (
        os.getenv("LIVE_INTERNAL_SERVICE_API_KEY", ""),
        os.getenv("INTERNAL_SERVICE_API_KEY", ""),
        dotenv_values().get("INTERNAL_SERVICE_API_KEY", ""),
    ):
        if candidate.strip():
            return candidate.strip()
    return ""
