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
) -> bool:
    """Return True iff *signature_header* is a fresh, valid signature for *payload*.

    Rejects signatures older than ``max_age_seconds`` (replay window) and uses a
    constant-time comparison to avoid leaking the expected signature via timing.
    """
    try:
        timestamp_str, provided_sig = signature_header.split(":", 1)
        if abs(time.time() - int(timestamp_str)) > max_age_seconds:
            return False
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        message = f"{agent_id}:{timestamp_str}:{body}"
        expected = hmac.new(
            agent_secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(provided_sig, expected)
    except Exception:
        return False
