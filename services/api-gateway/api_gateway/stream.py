"""stream.py — Server-Sent Events (SSE) streaming helpers for the API Gateway."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator

from prometheus_client import Counter

from .config import (
    INTAKE_STREAM,
    LIVE_STREAM_BLOCK_MS,
    LIVE_STREAM_COUNT,
    LIVE_STREAM_KEEPALIVE_SECONDS,
    STATE_STREAM,
)

LOGGER = logging.getLogger(__name__)

LIVE_STREAM_CONNECTIONS = Counter(
    "api_gateway_live_stream_connections_total",
    "Total SSE live-stream connections accepted by api-gateway",
)
LIVE_STREAM_EVENTS = Counter(
    "api_gateway_live_stream_events_total",
    "Total events emitted by api-gateway live stream",
    ("event_type",),
)
LIVE_STREAM_ERRORS = Counter(
    "api_gateway_live_stream_errors_total",
    "Total errors observed in api-gateway live stream",
    ("reason",),
)


def _parse_stream_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _decode_state_stream_event(entry_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    payload = _parse_stream_json(fields.get("payload"))
    envelope = _parse_stream_json(fields.get("envelope"))
    event_type = str(payload.get("event_type") or fields.get("event_type") or "").strip()
    mission_id_raw = payload.get("mission_id") or fields.get("mission_id")
    mission_id = str(mission_id_raw).strip() if mission_id_raw is not None else ""
    state_raw = payload.get("state") or fields.get("state")
    state = str(state_raw).strip().upper() if state_raw is not None else ""
    created_at_raw = payload.get("created_at") or fields.get("created_at")
    created_at = str(created_at_raw).strip() if created_at_raw is not None else ""
    topic_raw = envelope.get("topic")
    topic = str(topic_raw).strip() if topic_raw is not None else ""
    producer_raw = envelope.get("producer")
    producer = str(producer_raw).strip() if producer_raw is not None else ""
    return {
        "stream_id": entry_id,
        "event_type": event_type,
        "mission_id": mission_id or None,
        "state": state or None,
        "topic": topic or None,
        "producer": producer or None,
        "created_at": created_at or None,
        "payload": payload,
    }


def _sse_event_block(
    *, event_name: str, data: dict[str, Any], event_id: str | None = None
) -> str:
    lines: list[str] = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_name}")
    lines.append(f"data: {json.dumps(data, separators=(',', ':'))}")
    return "\n".join(lines) + "\n\n"


def _is_stream_event_allowed(
    event: dict[str, Any],
    *,
    mission_id: str | None,
    include_agent_events: bool,
) -> bool:
    event_type = str(event.get("event_type", "")).upper()
    if not include_agent_events and event_type.startswith("AGENT_"):
        return False
    if mission_id and str(event.get("mission_id") or "") != mission_id:
        return False
    return True


async def _state_stream_sse_generator(
    redis_client: Any,
    *,
    mission_id: str | None,
    include_agent_events: bool,
    last_event_id: str | None,
) -> AsyncIterator[str]:
    stream_cursor = last_event_id.strip() if isinstance(last_event_id, str) else ""
    if not stream_cursor:
        stream_cursor = "$"

    connected_payload = {
        "stream": INTAKE_STREAM,
        "state_stream": STATE_STREAM,
        "mission_id": mission_id,
        "include_agent_events": include_agent_events,
    }
    yield _sse_event_block(event_name="connected", data=connected_payload)

    last_keepalive = time.monotonic()
    while True:
        try:
            entries = await redis_client.xread(
                streams={STATE_STREAM: stream_cursor},
                count=max(1, LIVE_STREAM_COUNT),
                block=max(100, LIVE_STREAM_BLOCK_MS),
            )
            emitted = False
            for _, records in entries or []:
                for entry_id, fields in records:
                    stream_cursor = entry_id
                    event_payload = _decode_state_stream_event(entry_id, fields)
                    if not _is_stream_event_allowed(
                        event_payload,
                        mission_id=mission_id,
                        include_agent_events=include_agent_events,
                    ):
                        continue
                    emitted = True
                    event_type = str(event_payload.get("event_type") or "STREAM_EVENT")
                    LIVE_STREAM_EVENTS.labels(event_type=event_type).inc()
                    yield _sse_event_block(
                        event_name="state_event",
                        data=event_payload,
                        event_id=entry_id,
                    )
            if emitted:
                last_keepalive = time.monotonic()
                continue

            if (time.monotonic() - last_keepalive) >= LIVE_STREAM_KEEPALIVE_SECONDS:
                last_keepalive = time.monotonic()
                yield ": keepalive\n\n"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LIVE_STREAM_ERRORS.labels(reason="read_failure").inc()
            LOGGER.warning("state stream sse read failure: %s", exc)
            yield _sse_event_block(
                event_name="stream_error", data={"detail": "stream read failure"}
            )
            await asyncio.sleep(1.0)
