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


# --- Shared live-run policy -------------------------------------------------
#
# Timeouts live here because the two live suites drifted: the extended suite used
# 30s while the mission-flow suite kept a 4.0s default, and under pytest the
# first request exceeds 4s even against a stack answering /readyz in 0.25s. The
# probe caught the resulting OSError, called pytest.skip("not reachable"), and
# the run reported **exit 0 having verified nothing** -- the same
# "a non-verifying run reads as green" failure this module was created to stop,
# reached through timeouts instead of credentials.

def http_timeout_seconds() -> float:
    """Per-request timeout for live-stack calls."""
    return float(os.getenv("LIVE_HTTP_TIMEOUT_SECONDS", "30.0"))


def probe_timeout_seconds() -> float:
    """Timeout for the readiness probe that decides whether to run at all.

    Deliberately generous: treating a slow-but-healthy stack as absent is the
    expensive mistake, because it converts "verified nothing" into a green run.
    """
    return float(os.getenv("LIVE_GATEWAY_PROBE_TIMEOUT_SECONDS", "15.0"))


def live_stack_required() -> bool:
    """True when this run must actually verify something.

    Set ``LIVE_STACK_REQUIRED=1`` for any run whose output will be used as
    evidence. Skipping is right for a developer with no stack; it is wrong for a
    run that is meant to certify a release, where a skip must be a failure.
    """
    return os.getenv("LIVE_STACK_REQUIRED", "").strip().lower() in {"1", "true", "yes", "on"}


def skip_or_fail(reason: str) -> None:
    """Skip the run, or fail it when the caller declared verification mandatory."""
    import pytest  # noqa: PLC0415 -- keeps this module importable outside pytest

    message = (
        f"{reason} NOTHING WAS VERIFIED by this run. Set LIVE_STACK_REQUIRED=1 to "
        "make this a failure instead of a skip when the result is used as evidence."
    )
    if live_stack_required():
        pytest.fail(message, pytrace=False)
    pytest.skip(message)
