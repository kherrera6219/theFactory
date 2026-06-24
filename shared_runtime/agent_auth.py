"""Per-agent HMAC-SHA256 message signing for the Protocol Bus.

Each agent holds a per-agent shared secret. A message is signed over
``{agent_id}:{timestamp}:{canonical_body}`` so a captured signature cannot be
replayed past ``max_age_seconds`` nor reused by a different agent identity.

The canonical body is the same compact, key-sorted JSON the rest of the codebase
uses for signing/digesting, so signer and verifier agree byte-for-byte.

This is intentionally separate from :mod:`shared_runtime.crypto_signing` (ECDSA
artifact signatures): HMAC is a cheap, symmetric, per-message authenticator for
the live message bus, not a long-lived artifact signature.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time

logger = logging.getLogger(__name__)


def sign_agent_message(agent_id: str, agent_secret: str, payload: dict) -> str:
    """Return a ``"{timestamp}:{hex_signature}"`` header value for *payload*."""
    if not agent_id.strip():
        raise ValueError("agent_id must not be empty")
    if not agent_secret:
        raise ValueError("agent_secret must not be empty")
    timestamp = str(int(time.time()))
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    message = f"{agent_id}:{timestamp}:{body}"
    sig = hmac.new(agent_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return f"{timestamp}:{sig}"


def verify_agent_message(
    agent_id: str,
    agent_secret: str,
    payload: dict,
    signature_header: str,
    max_age_seconds: int = 60,
    max_future_skew_seconds: int = 5,
) -> bool:
    """Return True iff *signature_header* is a fresh, valid signature for *payload*.

    Rejects signatures older than ``max_age_seconds`` (replay window) and uses a
    constant-time comparison to avoid leaking the expected signature via timing.
    """
    if not agent_id.strip() or not agent_secret or not isinstance(signature_header, str):
        return False
    if max_age_seconds <= 0 or max_future_skew_seconds < 0:
        return False
    try:
        timestamp_str, provided_sig = signature_header.split(":", 1)
        timestamp = int(timestamp_str)
        age_seconds = time.time() - timestamp
        if age_seconds > max_age_seconds or age_seconds < -max_future_skew_seconds:
            return False
        if len(provided_sig) != 64 or any(ch not in "0123456789abcdef" for ch in provided_sig):
            return False
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        message = f"{agent_id}:{timestamp_str}:{body}"
        expected = hmac.new(
            agent_secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(provided_sig, expected)
    except (TypeError, ValueError):
        return False
