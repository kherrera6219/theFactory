from __future__ import annotations

import hmac
import inspect
import json
import logging
import os
import re
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from shared_runtime import protocol as protocol_guard
from shared_runtime.agent_auth import verify_agent_message
from shared_runtime.logging_config import configure_logging

from .tracing import configure_tracing

configure_logging("protocol-bus-mcp")

try:
    import redis.asyncio as redis
except ModuleNotFoundError:
    redis = None

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
MCP_PORT = int(os.getenv("MCP_PORT", "8090"))
MAX_STREAM_LEN = int(os.getenv("MAX_STREAM_LEN", "20000"))
MAX_MESSAGE_BYTES = int(os.getenv("MAX_MESSAGE_BYTES", "1048576"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
_MCP_API_KEY_RAW = os.getenv("MCP_API_KEY", "").strip()
if not _MCP_API_KEY_RAW:
    if ENVIRONMENT == "production":
        raise RuntimeError(
            "MCP_API_KEY must be explicitly set in production. "
            "Generate a stable value with: openssl rand -hex 32. "
            "Auto-generation is not permitted in production because the key "
            "changes on every container restart, silently breaking all clients."
        )
    # Development: auto-generate but log loudly so operators notice.
    _DEV_SESSION_NOTICE = (
        "MCP_API_KEY is not set. A random session key has been generated. "
        "This key will change on every restart. Set MCP_API_KEY explicitly "
        "in .env (see .env.example) to avoid breaking clients on restart."
    )
MCP_API_KEY = _MCP_API_KEY_RAW if _MCP_API_KEY_RAW else secrets.token_hex(32)
MAX_RECIPIENTS = int(os.getenv("MAX_RECIPIENTS", "32"))

# Per-agent HMAC message signing (opt-in, backward compatible). When enabled, the
# X-Agent-Signature header is verified against a per-agent secret resolved from
# AGENT_HMAC_SECRET_{SHORT_CODE} env vars (SHORT_CODE = agent id minus the AGENT-
# prefix, dashes → underscores; e.g. AGENT-31-PYTHON → AGENT_HMAC_SECRET_31_PYTHON).
AGENT_HMAC_SIGNING_ENABLED = (
    os.getenv("AGENT_HMAC_SIGNING_ENABLED", "false").strip().lower()
    in ("1", "true", "yes", "on")
)
AGENT_HMAC_MAX_AGE_SECONDS = int(os.getenv("AGENT_HMAC_MAX_AGE_SECONDS", "60"))


def _agent_hmac_secret(agent_id: str) -> str | None:
    """Resolve the per-agent HMAC secret env var for *agent_id*.

    AGENT-31-PYTHON → AGENT_HMAC_SECRET_31_PYTHON. Returns None if unset/blank.
    """
    short_code = agent_id.strip().upper()
    if short_code.startswith("AGENT-"):
        short_code = short_code[len("AGENT-"):]
    env_name = f"AGENT_HMAC_SECRET_{short_code.replace('-', '_')}"
    secret = os.getenv(env_name, "").strip()
    return secret or None

LOGGER = logging.getLogger(__name__)
AGENT_ID_PATTERN = re.compile(r"^AGENT-\d{2}-[A-Z0-9-]+$")

ALLOWED_PROTOCOLS = ("alpha", "beta", "delta", "sigma", "omega", "rho")
PRIORITY_LEVELS = ("low", "normal", "high", "critical")

REQUEST_COUNTER = Counter(
    "protocol_bus_mcp_http_requests_total",
    "Total HTTP requests served by protocol-bus MCP",
    ("method", "path", "status_code"),
)
REQUEST_LATENCY = Histogram(
    "protocol_bus_mcp_http_request_duration_seconds",
    "HTTP request latency in seconds for protocol-bus MCP",
    ("method", "path"),
)
MESSAGES_QUEUED = Counter(
    "protocol_bus_mcp_messages_queued_total",
    "Total protocol messages queued by MCP",
    ("protocol",),
)
DLQ_WRITES = Counter(
    "protocol_bus_mcp_dlq_writes_total",
    "Total dead-letter writes by MCP",
    ("protocol",),
)
MESSAGES_DEDUPLICATED = Counter(
    "protocol_bus_mcp_messages_deduplicated_total",
    "Total duplicate messages rejected by MCP",
    ("protocol",),
)
MESSAGES_REPLAYED = Counter(
    "protocol_bus_mcp_messages_replayed_total",
    "Total replayed messages rejected by MCP",
    ("protocol",),
)
# 2026 best practice: backpressure threshold — 503 when queue exceeds limit
BACKPRESSURE_QUEUE_LIMIT = int(os.getenv("MCP_BACKPRESSURE_LIMIT", "10000"))
def _message_dedup_ttl_seconds() -> int:
    raw = (
        os.getenv("MCP_DEDUP_TTL_SECONDS")
        or os.getenv("MESSAGE_DEDUP_TTL_SECONDS")
        or "300"
    )
    return int(raw)


# Message deduplication TTL — correlation_id seen within this window = duplicate.
# MCP_DEDUP_TTL_SECONDS is the canonical name; MESSAGE_DEDUP_TTL_SECONDS remains
# accepted for older compose overlays.
MESSAGE_DEDUP_TTL_SECONDS = _message_dedup_ttl_seconds()
# Message TTL — streams older than this age (seconds) are pruned (via XTRIM approximate)
MESSAGE_TTL_SECONDS = int(os.getenv("MCP_MESSAGE_TTL_SECONDS", "3600"))


def _parse_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def _is_valid_agent_id(value: str) -> bool:
    return bool(AGENT_ID_PATTERN.fullmatch(value.strip()))


class AlphaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str = Field(min_length=1, max_length=32)
    priority: Literal["low", "normal", "high", "critical"]
    target_pod: str = Field(min_length=1, max_length=64)
    directive_type: str = Field(min_length=1, max_length=120)
    directive: dict[str, Any] = Field(default_factory=dict)
    global_style_directives: list[str] = Field(default_factory=list)
    risk_assessment: dict[str, Any] | None = None


class BetaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str = Field(min_length=1, max_length=32)
    logicnode_id: str = Field(min_length=1, max_length=120)
    confidence_score: float = Field(ge=0.0, le=1.0)
    source_language: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)


class DeltaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str = Field(min_length=1, max_length=32)
    audit_result: Literal["pass", "fail", "warning"]
    verification_method: str = Field(min_length=1, max_length=120)
    tolerance_score: float = Field(ge=0.0, le=1.0)
    findings: dict[str, Any] = Field(default_factory=dict)


class SigmaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str = Field(min_length=1, max_length=32)
    knowledge_type: str = Field(min_length=1, max_length=120)
    # reserved for future semantic routing — not computed, stored, or matched today
    embedding_ref: str = Field(min_length=1, max_length=255)
    relevance_scope: str = Field(min_length=1, max_length=120)
    content: dict[str, Any] = Field(default_factory=dict)


class OmegaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str = Field(min_length=1, max_length=32)
    feature_contract: dict[str, Any] = Field(default_factory=dict)
    visual_blueprint: dict[str, Any] = Field(default_factory=dict)
    user_intent: str = Field(min_length=1, max_length=2000)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    global_style_directives: list[str] = Field(default_factory=list)


class RhoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str = Field(min_length=1, max_length=32)
    token_budget: int = Field(ge=0)
    rate_limit_action: str = Field(min_length=1, max_length=120)
    agent_target: str = Field(min_length=1, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventEnvelope(BaseModel):
    """Canonical event envelope — the single source of truth for the published
    envelope shape, mirroring ``schemas/event.envelope.schema.json``.

    The orchestrator and api-gateway validate dict payloads against that JSON
    Schema via ``jsonschema``; this Pydantic model is the typed counterpart so
    the MCP layer shares the same contract. The ``tests/services/
    test_envelope_schema_contract.py`` contract test asserts the two
    representations stay in sync across all six protocol types.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    event_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    timestamp: str
    producer: str
    correlation_id: str
    payload_ref: str = Field(pattern=r"^registry://")
    schema_: str = Field(alias="schema")
    priority: Literal["NORMAL", "HIGH"]

    @model_validator(mode="after")
    def _validate_timestamp(self) -> "EventEnvelope":
        _parse_datetime(self.timestamp)
        return self


class MessageEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    message_id: str
    schema_version: str = Field(min_length=1, max_length=32)
    protocol: Literal["alpha", "beta", "delta", "sigma", "omega", "rho"]
    sender: str = Field(min_length=1, max_length=120)
    recipient: str | list[str]
    correlation_id: str
    priority: Literal["low", "normal", "high", "critical"]
    timestamp: str
    payload: dict[str, Any]

    @model_validator(mode="after")
    def _validate_timestamp(self) -> "MessageEnvelope":
        _parse_datetime(self.timestamp)
        return self


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str = Field(default="v1", min_length=1, max_length=32)
    protocol: Literal["alpha", "beta", "delta", "sigma", "omega", "rho"]
    sender: str = Field(min_length=1, max_length=120)
    recipient: str | list[str]
    correlation_id: str | None = Field(default=None, max_length=120)
    priority: Literal["low", "normal", "high", "critical"] = "normal"
    payload: dict[str, Any] = Field(default_factory=dict)


def _validate_protocol_payload(protocol: str, payload: dict[str, Any]) -> dict[str, Any]:
    validator_map: dict[str, type[BaseModel]] = {
        "alpha": AlphaPayload,
        "beta": BetaPayload,
        "delta": DeltaPayload,
        "sigma": SigmaPayload,
        "omega": OmegaPayload,
        "rho": RhoPayload,
    }
    validator = validator_map.get(protocol)
    if validator is None:
        raise ValueError(f"unsupported protocol: {protocol}")
    validated = validator.model_validate(payload)
    return validated.model_dump(mode="json")


def _normalized_recipients(value: str | list[str]) -> list[str]:
    if isinstance(value, str):
        recipient = value.strip()
        if not recipient:
            raise HTTPException(status_code=422, detail="recipient must not be empty")
        if recipient.lower() != "broadcast" and not _is_valid_agent_id(recipient):
            raise HTTPException(status_code=422, detail=f"invalid recipient id: {recipient}")
        return [recipient]

    recipients = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if not recipients:
        raise HTTPException(status_code=422, detail="recipient list must not be empty")
    if len(recipients) > MAX_RECIPIENTS:
        raise HTTPException(
            status_code=422,
            detail=f"recipient list exceeds maximum allowed recipients ({MAX_RECIPIENTS})",
        )
    invalid = [
        recipient
        for recipient in recipients
        if recipient.lower() != "broadcast" and not _is_valid_agent_id(recipient)
    ]
    if invalid:
        raise HTTPException(status_code=422, detail=f"invalid recipient id: {invalid[0]}")
    return sorted(set(recipients))


def _resolve_channels(protocol: str, recipients: list[str]) -> list[str]:
    channels: list[str] = []
    for recipient in recipients:
        if recipient.lower() == "broadcast":
            channels.append(f"protocol:{protocol}:broadcast")
        else:
            channels.append(f"protocol:{protocol}:{recipient}")
    return sorted(set(channels))


async def _write_dlq(redis_client: Any, protocol: str, payload: dict[str, Any], error: str) -> None:
    if redis_client is None:
        return
    dlq_key = f"dlq:{protocol}"
    await redis_client.xadd(
        dlq_key,
        {
            "error": error,
            "payload": json.dumps(payload),
            "ts": datetime.now(UTC).isoformat(),
        },
        maxlen=MAX_STREAM_LEN,
        approximate=True,
    )
    DLQ_WRITES.labels(protocol=protocol).inc()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not _MCP_API_KEY_RAW:
        LOGGER.error(_DEV_SESSION_NOTICE)
    LOGGER.info(
        "protocol-bus-mcp starting (environment=%s, mcp_api_key_set=%s)",
        ENVIRONMENT,
        bool(_MCP_API_KEY_RAW),
    )
    app.state.redis = None
    app.state.redis_ready = False
    if redis is not None:
        try:
            app.state.redis = redis.from_url(REDIS_URL, decode_responses=True)
            app.state.redis_ready = bool(await app.state.redis.ping())
        except Exception as exc:
            LOGGER.warning("protocol-bus-mcp failed to initialize redis client: %s", exc)
            app.state.redis = None
            app.state.redis_ready = False
    yield
    redis_client = getattr(app.state, "redis", None)
    if redis_client is not None:
        aclose = getattr(redis_client, "aclose", None)
        if callable(aclose):
            await aclose()
        else:
            close = getattr(redis_client, "close", None)
            if callable(close):
                result = close()
                if inspect.isawaitable(result):
                    await result


app = FastAPI(title="HolyGrail Protocol Bus MCP", version="0.1.0", lifespan=lifespan)
configure_tracing(app, service_name="protocol-bus-mcp")


@app.middleware("http")
async def _request_metrics(request: Request, call_next):
    started = time.perf_counter()
    method = request.method
    status_code = "500"
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        return response
    finally:
        route = request.scope.get("route")
        path = route.path if route is not None else request.url.path
        REQUEST_COUNTER.labels(method=method, path=path, status_code=status_code).inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(time.perf_counter() - started)


@app.get("/health")
async def health() -> dict[str, Any]:
    redis_client = getattr(app.state, "redis", None)
    redis_ready = False
    if redis_client is not None:
        try:
            redis_ready = bool(await redis_client.ping())
            app.state.redis_ready = redis_ready
        except Exception as exc:
            LOGGER.warning("protocol-bus-mcp redis ping failed during health check: %s", exc)
            redis_ready = False
            app.state.redis_ready = False
    return {
        "ok": redis_ready,
        "service": "protocol-bus-mcp",
        "redis_ready": redis_ready,
        "allowed_protocols": list(ALLOWED_PROTOCOLS),
        "max_message_bytes": MAX_MESSAGE_BYTES,
    }


@app.get("/readyz")
async def readyz() -> dict[str, Any]:
    redis_client = getattr(app.state, "redis", None)
    if redis_client is None:
        app.state.redis_ready = False
        raise HTTPException(status_code=503, detail="redis unavailable")
    try:
        redis_ready = bool(await redis_client.ping())
        app.state.redis_ready = redis_ready
    except Exception as exc:
        app.state.redis_ready = False
        LOGGER.warning("protocol-bus-mcp redis ping failed during readiness check")
        raise HTTPException(status_code=503, detail="redis unavailable") from exc
    if not redis_ready:
        raise HTTPException(status_code=503, detail="redis unavailable")
    return {"ready": True, "service": "protocol-bus-mcp", "redis_ready": redis_ready}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/dlq")
async def list_dlq(protocol: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    if protocol not in ALLOWED_PROTOCOLS:
        raise HTTPException(status_code=422, detail=f"unsupported protocol: {protocol}")

    redis_client = getattr(app.state, "redis", None)
    if redis_client is None or not bool(getattr(app.state, "redis_ready", False)):
        raise HTTPException(status_code=503, detail="redis unavailable")

    stream = f"dlq:{protocol}"
    entries = await redis_client.xrevrange(stream, count=min(max(limit, 1), 200))
    sliced = entries[offset : offset + limit]
    return {
        "protocol": protocol,
        "stream": stream,
        "count": len(sliced),
        "offset": offset,
        "items": [
            {
                "entry_id": entry_id,
                "error": values.get("error", ""),
                "payload": values.get("payload", ""),
                "ts": values.get("ts", ""),
            }
            for entry_id, values in sliced
        ],
    }


@app.post("/send")
async def send_message(
    request: Request,
    x_agent_id: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    x_agent_signature: str | None = Header(default=None),
) -> JSONResponse:
    raw_body = await request.body()
    if len(raw_body) > MAX_MESSAGE_BYTES:
        raise HTTPException(status_code=413, detail="payload exceeds 1MB limit")

    try:
        body = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON payload: {exc}") from exc

    try:
        payload = SendMessageRequest.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    if not _is_valid_agent_id(payload.sender):
        raise HTTPException(status_code=422, detail=f"invalid sender id: {payload.sender}")
    if MCP_API_KEY and not hmac.compare_digest(
        (x_api_key or "").strip().encode("utf-8"),
        MCP_API_KEY.encode("utf-8"),
    ):
        LOGGER.warning("protocol-bus-mcp rejected request due to invalid api key")
        raise HTTPException(status_code=403, detail="invalid mcp api key")
    if (x_agent_id or "").strip() != payload.sender:
        LOGGER.warning(
            "protocol-bus-mcp rejected sender mismatch header=%s sender=%s",
            (x_agent_id or "").strip(),
            payload.sender,
        )
        raise HTTPException(status_code=403, detail="sender identity mismatch")

    # Per-agent HMAC signing (opt-in). When enabled, every sender must present a
    # valid X-Agent-Signature over the message payload, signed with that agent's
    # secret. When disabled, the header is ignored — backward compatible.
    if AGENT_HMAC_SIGNING_ENABLED:
        if not x_agent_signature:
            LOGGER.warning(
                "protocol-bus-mcp rejected sender=%s: missing X-Agent-Signature "
                "while AGENT_HMAC_SIGNING_ENABLED",
                payload.sender,
            )
            raise HTTPException(status_code=401, detail="missing agent signature")
        secret = _agent_hmac_secret(payload.sender)
        if not secret:
            LOGGER.warning(
                "protocol-bus-mcp rejected sender=%s: no HMAC secret configured",
                payload.sender,
            )
            raise HTTPException(status_code=401, detail="agent signing secret not configured")
        if not verify_agent_message(
            payload.sender,
            secret,
            payload.payload,
            x_agent_signature,
            max_age_seconds=AGENT_HMAC_MAX_AGE_SECONDS,
        ):
            LOGGER.warning(
                "protocol-bus-mcp rejected sender=%s: invalid agent signature",
                payload.sender,
            )
            raise HTTPException(status_code=401, detail="invalid agent signature")

    recipients = _normalized_recipients(payload.recipient)
    channels = _resolve_channels(payload.protocol, recipients)

    try:
        protocol_payload = _validate_protocol_payload(payload.protocol, payload.payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    envelope = MessageEnvelope(
        message_id=f"msg-{uuid.uuid4()}",
        schema_version=payload.schema_version,
        protocol=payload.protocol,
        sender=payload.sender,
        recipient=recipients if len(recipients) > 1 else recipients[0],
        correlation_id=payload.correlation_id or f"corr-{uuid.uuid4()}",
        priority=payload.priority,
        timestamp=datetime.now(UTC).isoformat(),
        payload=protocol_payload,
    )
    envelope_json = json.dumps(envelope.model_dump(mode="json"))

    redis_client = getattr(app.state, "redis", None)
    if redis_client is None or not bool(getattr(app.state, "redis_ready", False)):
        raise HTTPException(status_code=503, detail="redis unavailable")

    # Replay detection: reject events whose correlation_id was already processed
    # within the TTL window. This guards against replay attacks before the
    # message is published to any Redis stream.
    try:
        await protocol_guard.check_replay(
            envelope.correlation_id,
            redis_client,
            ttl_seconds=MESSAGE_DEDUP_TTL_SECONDS,
        )
    except protocol_guard.ReplayDetectedError as exc:
        MESSAGES_REPLAYED.labels(protocol=payload.protocol).inc()
        LOGGER.warning(
            "protocol-bus-mcp: replay rejected correlation_id=%s",
            envelope.correlation_id,
        )
        raise HTTPException(
            status_code=409,
            detail=f"replay detected for correlation_id: {envelope.correlation_id}",
        ) from exc
    except Exception as exc:
        # A Redis failure during replay detection must fail closed (503) —
        # silently skipping the guard would let replays through unnoticed.
        LOGGER.error("protocol-bus-mcp: replay check failed: %s", exc)
        raise HTTPException(
            status_code=503, detail="Replay detection service unavailable"
        ) from exc

    # 2026 best practice: message deduplication via Redis SET NX EX.
    # A Redis failure here must fail closed (503) — silently skipping the dedup
    # guard would let duplicate messages through unnoticed.
    dedup_key = f"mcp:dedup:{envelope.correlation_id}"
    try:
        already_seen = not await redis_client.set(
            dedup_key, "1", nx=True, ex=MESSAGE_DEDUP_TTL_SECONDS
        )
    except Exception as exc:
        LOGGER.error("protocol-bus-mcp: dedup check failed: %s", exc)
        raise HTTPException(status_code=503, detail="Dedup service unavailable") from exc
    if already_seen:
        MESSAGES_DEDUPLICATED.labels(protocol=payload.protocol).inc()
        LOGGER.info(
            "protocol-bus-mcp: duplicate message rejected correlation_id=%s",
            envelope.correlation_id,
        )
        # Return 200 (idempotent) rather than 409 — clients shouldn't error on dedup
        return JSONResponse(
            status_code=200,
            content={
                "message_id": envelope.message_id,
                "schema_version": payload.schema_version,
                "protocol": payload.protocol,
                "channels": channels,
                "queued_at": envelope.timestamp,
                "deduplicated": True,
            },
        )

    # 2026 best practice: backpressure — check queue depth before accepting more.
    # Failing open here would let the system be flooded silently, so a Redis
    # failure must fail closed (503). Every resolved channel is inspected: if
    # ANY channel is over the limit, the request is rejected.
    try:
        queue_depths = {
            channel: await redis_client.xlen(channel) for channel in channels
        }
    except Exception as exc:
        LOGGER.error("protocol-bus-mcp: backpressure check failed: %s", exc)
        raise HTTPException(
            status_code=503, detail="Backpressure service unavailable"
        ) from exc
    for channel, queue_depth in queue_depths.items():
        if queue_depth > BACKPRESSURE_QUEUE_LIMIT:
            LOGGER.warning(
                "protocol-bus-mcp: backpressure triggered channel=%s queue_depth=%d limit=%d",
                channel, queue_depth, BACKPRESSURE_QUEUE_LIMIT,
            )
            raise HTTPException(
                status_code=503,
                detail="queue backpressure limit exceeded; retry later",
                headers={"Retry-After": "5"},
            )

    try:
        for channel in channels:
            await redis_client.xadd(
                channel,
                {
                    "envelope": envelope_json,
                    "payload": json.dumps(protocol_payload),
                    "sender": payload.sender,
                },
                maxlen=MAX_STREAM_LEN,
                approximate=True,
            )
        MESSAGES_QUEUED.labels(protocol=payload.protocol).inc()
    except Exception as exc:
        await _write_dlq(redis_client, payload.protocol, body, str(exc))
        LOGGER.exception("protocol-bus-mcp failed to publish protocol message")
        raise HTTPException(status_code=503, detail="failed to publish message") from exc

    return JSONResponse(
        status_code=200,
        content={
            "message_id": envelope.message_id,
            "schema_version": payload.schema_version,
            "protocol": payload.protocol,
            "channels": channels,
            "queued_at": envelope.timestamp,
        },
    )
