"""rate_limit.py — Redis-backed sliding-window rate limiter for the API Gateway."""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

from fastapi import Request

from .config import (
    API_RATE_LIMIT_PER_MINUTE,
    RATE_LIMIT_HMAC_KEY,
    RATE_LIMIT_KEY_PREFIX,
    RATE_LIMIT_WINDOW_SECONDS,
)


def _client_identifier(request: Request) -> str:
    api_key = request.headers.get("x-api-key")
    if api_key:
        # HMAC-SHA256 is intentional here: this is a rate-limit bucket key, not password storage.
        # Fast, deterministic, keyed hashing is required — bcrypt/argon2 would break rate limiting
        # (non-deterministic salts) and add unacceptable per-request latency.
        digest = hmac.digest(
            RATE_LIMIT_HMAC_KEY, api_key.encode("utf-8"), "sha256"
        ).hex()
        return f"api-key:{digest}"

    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client is not None else "unknown"
    return f"ip:{client_ip}"


async def _check_rate_limit(redis_client: Any, identifier: str) -> tuple[bool, int, int]:
    window = int(time.time() // RATE_LIMIT_WINDOW_SECONDS)
    identifier_hash = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    key = f"{RATE_LIMIT_KEY_PREFIX}:{identifier_hash}:{window}"
    current = int(await redis_client.incr(key))
    if current == 1:
        await redis_client.expire(key, RATE_LIMIT_WINDOW_SECONDS + 5)

    retry_after = RATE_LIMIT_WINDOW_SECONDS - int(time.time() % RATE_LIMIT_WINDOW_SECONDS)
    remaining = max(0, API_RATE_LIMIT_PER_MINUTE - current)
    return current > API_RATE_LIMIT_PER_MINUTE, retry_after, remaining
