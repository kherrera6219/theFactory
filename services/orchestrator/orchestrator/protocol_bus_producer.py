"""Protocol Bus producer helpers — POST typed messages to the protocol-bus-mcp
``/send`` endpoint.

The bus authenticates each request with the shared ``X-API-Key`` (validated via
``hmac.compare_digest`` against ``MCP_API_KEY``) and requires the ``X-Agent-Id``
header to equal the envelope ``sender``. Senders must match the bus
``AGENT_ID_PATTERN`` (``^AGENT-\\d{2}-[A-Z0-9-]+$``).

All sends are fire-and-forget: failures are logged and swallowed so a bus outage
never blocks mission flow.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any
from urllib.request import Request, urlopen  # noqa: S310 — only http/https; patched in tests

LOGGER = logging.getLogger(__name__)


def _protocol_bus_url(settings: Any) -> str | None:
    url = str(
        getattr(settings, "protocol_bus_url", "")
        or getattr(settings, "mcp_url", "")
        or ""
    ).strip()
    return url or None


def _protocol_bus_api_key(settings: Any) -> str:
    return str(
        getattr(settings, "protocol_bus_api_key", "")
        or getattr(settings, "mcp_api_key", "")
        or ""
    )


def send_protocol_message(
    *,
    settings: Any,
    protocol: str,
    sender: str,
    recipient: str | list[str],
    payload: dict[str, Any],
    priority: str = "normal",
    correlation_id: str | None = None,
    timeout: float = 5.0,
) -> bool:
    """POST a single message to the Protocol Bus ``/send`` endpoint.

    Returns True when the bus accepts the message (HTTP < 300). Returns False —
    never raises — on a missing URL, network error, or non-2xx response, so
    callers can treat this as fire-and-forget telemetry.
    """
    bus_url = _protocol_bus_url(settings)
    if not bus_url:
        LOGGER.debug(
            "protocol_bus_producer: Protocol Bus URL not configured, skipping %s send",
            protocol,
        )
        return False

    request_body = {
        "schema_version": "v1",
        "protocol": protocol,
        "sender": sender,
        "recipient": recipient,
        "correlation_id": correlation_id or f"{protocol}-{uuid.uuid4()}",
        "priority": priority,
        "payload": payload,
    }

    try:
        body = json.dumps(request_body, separators=(",", ":")).encode("utf-8")
        req = Request(
            f"{bus_url.rstrip('/')}/send",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": _protocol_bus_api_key(settings),
                "X-Agent-Id": sender,
            },
        )
        with urlopen(req, timeout=timeout) as resp:  # nosec B310
            status = resp.status
        if status < 300:
            LOGGER.info(
                "protocol_bus_producer: %s message sent sender=%s recipient=%s",
                protocol,
                sender,
                recipient,
            )
            return True
        LOGGER.warning(
            "protocol_bus_producer: %s send returned HTTP %s (sender=%s)",
            protocol,
            status,
            sender,
        )
        return False
    except Exception as exc:
        LOGGER.warning(
            "protocol_bus_producer: %s send failed (sender=%s): %s",
            protocol,
            sender,
            exc,
        )
        return False


def send_alpha_directive(
    *,
    settings: Any,
    sender: str,
    recipient: str,
    target_pod: str,
    directive_type: str,
    directive: dict[str, Any],
    priority: str = "normal",
    global_style_directives: list[str] | None = None,
    correlation_id: str | None = None,
) -> bool:
    """Send a Protocol Alpha (directive) message — e.g. CEO → Pod Manager.

    Builds a bus-valid ``AlphaPayload`` (``schema_version``/``priority``/
    ``target_pod``/``directive_type``/``directive``/``global_style_directives``)
    and posts it to the recipient's Alpha lane. Fire-and-forget.
    """
    payload = {
        "schema_version": "v1",
        "priority": priority,
        "target_pod": target_pod,
        "directive_type": directive_type,
        "directive": directive,
        "global_style_directives": global_style_directives or [],
    }
    return send_protocol_message(
        settings=settings,
        protocol="alpha",
        sender=sender,
        recipient=recipient,
        payload=payload,
        priority=priority,
        correlation_id=correlation_id,
    )
