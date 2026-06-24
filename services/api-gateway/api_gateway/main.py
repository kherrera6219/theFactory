import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from shared_runtime.agent_keys import normalize_agent_id
from shared_runtime.logging_config import configure_logging
from shared_runtime.protocol import (
    ProtocolValidationError,
    load_event_schema,
    load_topics,
    parse_date_time,
    validate_envelope,
)

from .tracing import configure_tracing, current_trace_id

try:
    import redis.asyncio as redis
    from redis.exceptions import ConnectionError as _RedisConnectionError
except ModuleNotFoundError:
    redis = None
    _RedisConnectionError = type(None)  # never matched; keeps except clauses uniform

try:
    import jwt
    from jwt import PyJWKClient
except ModuleNotFoundError:
    jwt = None
    PyJWKClient = None

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8001")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
INTAKE_STREAM = os.getenv("INTAKE_STREAM", "missions.intake")
STATE_STREAM = os.getenv("STATE_STREAM", "missions.state")
INTAKE_TOPIC = os.getenv("INTAKE_TOPIC", "intake.feature_contract.created")
MAX_STREAM_LEN = int(os.getenv("MAX_STREAM_LEN", "20000"))
CORS_ALLOW_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3100")
INTERNAL_SERVICE_API_KEY = os.getenv("INTERNAL_SERVICE_API_KEY", "")
# Gateway-side API key registry used to authorize callers in api_key mode.
# Mirrors the orchestrator's role model so the gateway never elevates anonymous
# callers with its own privileged INTERNAL_SERVICE_API_KEY.
#   ORCHESTRATOR_ADMIN_API_KEY    -> {admin, mutate, internal, read}
#   ORCHESTRATOR_READONLY_API_KEY -> {read}
#   ORCHESTRATOR_API_KEYS         -> "key=role1,role2;otherkey=role3"
ORCHESTRATOR_ADMIN_API_KEY = os.getenv("ORCHESTRATOR_ADMIN_API_KEY", "").strip()
ORCHESTRATOR_READONLY_API_KEY = os.getenv("ORCHESTRATOR_READONLY_API_KEY", "").strip()
ORCHESTRATOR_API_KEYS = os.getenv("ORCHESTRATOR_API_KEYS", "")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
AUTH_MODE = os.getenv("AUTH_MODE", "api_key").strip().lower()
ALLOWED_AUTH_MODES = {"api_key", "hybrid", "oidc"}
OIDC_ISSUER_URL = os.getenv("OIDC_ISSUER_URL", "").strip()
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", "").strip()
OIDC_JWKS_URL = os.getenv("OIDC_JWKS_URL", "").strip()
OIDC_SHARED_SECRET = os.getenv("OIDC_SHARED_SECRET", "").strip()
OIDC_REQUIRED_ROLE = os.getenv("OIDC_REQUIRED_ROLE", "mutate").strip().lower() or "mutate"
OIDC_OPERATOR_ROLE = os.getenv("OIDC_OPERATOR_ROLE", "observe").strip().lower() or "observe"
OIDC_ENFORCE_OPERATOR_ROUTES = (
    os.getenv("OIDC_ENFORCE_OPERATOR_ROUTES", "true").strip().lower()
    in {"1", "true", "yes", "on"}
)
# DANGER: when true, ALL operator-route authorization is disabled. Defaults to "false";
# set true only for local dev debugging. A startup warning is logged if enabled in production.
GATEWAY_ADMIN_BYPASS: bool = (
    os.getenv("GATEWAY_ADMIN_BYPASS", "false").strip().lower() in {"1", "true", "yes", "on"}
)
OIDC_ROLE_CLAIMS = tuple(
    claim.strip()
    for claim in os.getenv("OIDC_ROLE_CLAIMS", "roles,role,permissions").split(",")
    if claim.strip()
)
OIDC_SCOPE_CLAIMS = tuple(
    claim.strip()
    for claim in os.getenv("OIDC_SCOPE_CLAIMS", "scope,scp").split(",")
    if claim.strip()
)
OIDC_ALLOWED_ALGORITHMS = [
    algorithm.strip()
    for algorithm in os.getenv("OIDC_ALLOWED_ALGORITHMS", "RS256").split(",")
    if algorithm.strip()
] or ["RS256"]
OIDC_LEEWAY_SECONDS = max(0.0, float(os.getenv("OIDC_LEEWAY_SECONDS", "60")))
IDEMPOTENCY_TTL_SECONDS = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "86400"))
IDEMPOTENCY_KEY_PREFIX = "idempotency:missions"
API_RATE_LIMIT_PER_MINUTE = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "120"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_KEY_PREFIX = "ratelimit:api-gateway"
RATE_LIMIT_HMAC_KEY = os.getenv("RATE_LIMIT_HMAC_KEY", "ratelimit-default").encode()
LIVE_STREAM_BLOCK_MS = int(os.getenv("LIVE_STREAM_BLOCK_MS", "5000"))
LIVE_STREAM_KEEPALIVE_SECONDS = float(os.getenv("LIVE_STREAM_KEEPALIVE_SECONDS", "15"))
LIVE_STREAM_COUNT = int(os.getenv("LIVE_STREAM_COUNT", "50"))
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = [
    "Accept",
    "Authorization",
    "Content-Type",
    "Idempotency-Key",
    "X-API-Key",
]
CORS_EXPOSE_HEADERS = [
    "Retry-After",
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-Trace-Id",
]
PAYLOAD_REF_PATTERN = re.compile(r"^registry://")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20"))
OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "high").strip().lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1").rstrip("/")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8").strip()
ANTHROPIC_TIMEOUT_SECONDS = float(os.getenv("ANTHROPIC_TIMEOUT_SECONDS", "20"))
ANTHROPIC_VERSION = os.getenv("ANTHROPIC_VERSION", "2023-06-01").strip()
ANTHROPIC_THINKING_MODE = os.getenv("ANTHROPIC_THINKING_MODE", "enabled").strip().lower()
ANTHROPIC_THINKING_BUDGET_TOKENS = int(os.getenv("ANTHROPIC_THINKING_BUDGET_TOKENS", "8192"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
).rstrip("/")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "20"))
GEMINI_THINKING_BUDGET = int(os.getenv("GEMINI_THINKING_BUDGET", "-1"))
GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "high").strip().lower()
ALLOWED_LLM_MODELS: dict[str, str] = {
    "gpt-5.5": "openai",
    "claude-opus-4-8": "anthropic",
    "gemini-3.5-flash": "gemini",
}


def _registered_prometheus_collector(name: str) -> Any | None:
    collectors = getattr(REGISTRY, "_names_to_collectors", {})
    candidate_names = [name]
    if name.endswith("_total"):
        candidate_names.append(name.removesuffix("_total"))
    else:
        candidate_names.append(f"{name}_total")
    for candidate_name in candidate_names:
        collector = collectors.get(candidate_name)
        if collector is not None:
            return collector
    return None


def _counter(name: str, documentation: str, labelnames: tuple[str, ...] = ()) -> Any:
    collector = _registered_prometheus_collector(name)
    if collector is not None:
        return collector
    try:
        return Counter(name, documentation, labelnames)
    except ValueError:
        collector = _registered_prometheus_collector(name)
        if collector is not None:
            return collector
        raise


def _histogram(name: str, documentation: str, labelnames: tuple[str, ...] = ()) -> Any:
    collector = _registered_prometheus_collector(name)
    if collector is not None:
        return collector
    try:
        return Histogram(name, documentation, labelnames)
    except ValueError:
        collector = _registered_prometheus_collector(name)
        if collector is not None:
            return collector
        raise


REQUEST_COUNTER = _counter(
    "api_gateway_http_requests_total",
    "Total HTTP requests served by api-gateway",
    ("method", "path", "status_code"),
)
REQUEST_LATENCY = _histogram(
    "api_gateway_http_request_duration_seconds",
    "HTTP request latency in seconds for api-gateway",
    ("method", "path"),
)
LIVE_STREAM_CONNECTIONS = _counter(
    "api_gateway_live_stream_connections_total",
    "Total SSE live-stream connections accepted by api-gateway",
)
LIVE_STREAM_EVENTS = _counter(
    "api_gateway_live_stream_events_total",
    "Total events emitted by api-gateway live stream",
    ("event_type",),
)
LIVE_STREAM_ERRORS = _counter(
    "api_gateway_live_stream_errors_total",
    "Total errors observed in api-gateway live stream",
    ("reason",),
)
AUTH_FAILURES_TOTAL = _counter(
    "factory_auth_failures_total",
    "Authentication failures",
    # reason = invalid_key | expired_token | insufficient_role | missing_auth
    ("reason", "route_prefix"),
)
configure_logging("api-gateway")
LOGGER = logging.getLogger(__name__)
VALID_AUTH_MODES = {"api_key", "hybrid", "oidc"}
if AUTH_MODE not in VALID_AUTH_MODES:
    _invalid_auth_mode_msg = (
        f"Invalid AUTH_MODE '{AUTH_MODE}'. "
        f"Valid values: {', '.join(sorted(VALID_AUTH_MODES))}. "
        f"Falling back to api_key."
    )
    if ENVIRONMENT == "production":
        raise RuntimeError(
            f"Invalid AUTH_MODE '{AUTH_MODE}' in production. "
            f"Valid values: {', '.join(sorted(VALID_AUTH_MODES))}. "
            f"Set AUTH_MODE to a valid value before starting the service."
        )
    LOGGER.error(_invalid_auth_mode_msg)
    AUTH_MODE = "api_key"
LOGGER.info("api-gateway auth mode active: %s (environment=%s)", AUTH_MODE, ENVIRONMENT)
_OIDC_JWKS_CLIENT: Any | None = None

if Path("/app/schemas").exists() and Path("/app/protocol").exists():
    REPO_ROOT = Path("/app")
else:
    REPO_ROOT = Path(__file__).resolve().parents[3]
EVENT_SCHEMA_PATH = Path(
    os.getenv("EVENT_SCHEMA_PATH", str(REPO_ROOT / "schemas/event.envelope.schema.json"))
)
TOPICS_PATH = Path(os.getenv("TOPICS_PATH", str(REPO_ROOT / "protocol/topics.yaml")))
PM_AGENT_ID = "AGENT-01-PM"
CEO_AGENT_ID = "AGENT-02-CEO"
DEFAULT_POD_MANAGER_AGENT_ID = "AGENT-12-PODA-MGR"
ROUTING_VERSION = "v1.1"
_POD_A_LANGUAGES = {"python", "javascript", "typescript", "ruby", "php"}
_POD_B_LANGUAGES = {"go", "rust", "c", "cpp", "zig"}
_POD_C_LANGUAGES = {"java", "csharp", "kotlin", "scala"}
_POD_D_LANGUAGES = {"matlab", "r", "julia", "mathematica", "haskell", "ocaml"}
POD_MANAGER_BY_LANGUAGE: dict[str, str] = {
    **{language: "AGENT-12-PODA-MGR" for language in _POD_A_LANGUAGES},
    **{language: "AGENT-18-PODB-MGR" for language in _POD_B_LANGUAGES},
    **{language: "AGENT-24-PODC-MGR" for language in _POD_C_LANGUAGES},
    **{language: "AGENT-30-PODD-MGR" for language in _POD_D_LANGUAGES},
}


_METADATA_MAX_BYTES = 4096


class MissionAttachment(BaseModel):
    file_id: str
    filename: str
    content_type: str
    size_bytes: int = 0
    purpose: str | None = "reference"

class MissionCreate(BaseModel):
    prompt: str = Field(min_length=3)
    requested_target_language: str | None = None
    source_code: str | None = Field(default=None, max_length=512_000)
    attachments: list[MissionAttachment] = Field(default_factory=list)
    global_style_directives: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def __get_validators__(cls):
        yield from super().__get_validators__()

    def model_post_init(self, __context: Any) -> None:
        serialized = json.dumps(self.metadata, separators=(",", ":"))
        if len(serialized.encode("utf-8")) > _METADATA_MAX_BYTES:
            raise ValueError(
                f"metadata exceeds maximum allowed size of {_METADATA_MAX_BYTES} bytes"
            )


class MissionRecord(BaseModel):
    mission_id: str
    prompt: str
    requested_target_language: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    project_id: str | None = None
    state: str
    created_at: str


class MissionStateUpdate(BaseModel):
    new_state: str
    expected_state: str | None = None


class BuilderPreviewRequest(BaseModel):
    request: str = Field(min_length=3, max_length=4000)
    constraints: list[str] = Field(default_factory=list)
    view_mode: str | None = Field(default=None, pattern="^(desktop|tablet|mobile)$")
    provider: str | None = Field(default=None, pattern="^(openai|anthropic|gemini|offline)$")
    model: str | None = Field(default=None, min_length=2, max_length=120)
    reasoning_effort: str | None = Field(
        default=None,
        pattern="^(none|minimal|low|medium|high|xhigh)$",
    )
    thinking_budget: int | None = Field(default=None, ge=-1, le=65536)


def _parse_date_time(value: str) -> datetime:
    return parse_date_time(value)


def _load_event_schema() -> dict[str, Any]:
    return load_event_schema(EVENT_SCHEMA_PATH)


def _load_topics() -> set[str]:
    return load_topics(TOPICS_PATH)


def _validate_envelope(envelope: dict[str, Any]) -> None:
    validate_envelope(
        envelope,
        schema=_load_event_schema(),
        topics=_load_topics(),
        payload_ref_pattern=PAYLOAD_REF_PATTERN,
    )


def _build_envelope(*, correlation_id: str, payload_ref: str) -> dict[str, Any]:
    envelope = {
        "event_id": f"evt-{uuid.uuid4()}",
        "topic": INTAKE_TOPIC,
        "timestamp": datetime.now(UTC).isoformat(),
        "producer": "api-gateway",
        "correlation_id": correlation_id,
        "payload_ref": payload_ref,
        "schema": "missions.intake.v1",
        "priority": "NORMAL",
    }
    _validate_envelope(envelope)
    return envelope


def _request_hash(payload: MissionCreate) -> str:
    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_agent_id(value: Any) -> str | None:
    return normalize_agent_id(value)


def _normalize_language(value: str | None) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def _normalize_project_id(value: Any, *, fallback: str) -> str:
    candidate = re.sub(r"[^a-z0-9._-]+", "-", str(value or "").strip().lower()).strip("-.")
    if not candidate:
        return fallback
    return candidate if candidate.startswith("project-") else f"project-{candidate}"


def _resolve_project_id(metadata: dict[str, Any], *, mission_id: str) -> str:
    explicit = metadata.get("project_id")
    if isinstance(explicit, str) and explicit.strip():
        return _normalize_project_id(explicit, fallback="project-unknown")
    source = metadata.get("source")
    if isinstance(source, str) and source.strip():
        return _normalize_project_id(source, fallback="project-unknown")
    return _normalize_project_id(mission_id, fallback="project-unknown")


def _resolve_pod_manager_agent(requested_target_language: str | None) -> str:
    normalized_language = _normalize_language(requested_target_language)
    return POD_MANAGER_BY_LANGUAGE.get(normalized_language, DEFAULT_POD_MANAGER_AGENT_ID)


def _normalize_mission_metadata(
    metadata: Any,
    *,
    mission_id: str | None = None,
    requested_target_language: str | None,
) -> dict[str, Any]:
    if metadata is None:
        normalized: dict[str, Any] = {}
    elif isinstance(metadata, dict):
        normalized = dict(metadata)
    else:
        raise HTTPException(status_code=422, detail="metadata must be an object")

    provided_agent = _normalize_agent_id(
        normalized.get("agent_id")
        or normalized.get("selected_agent_id")
        or normalized.get("target_agent_id")
        or normalized.get("assigned_agent_id")
    )
    if provided_agent is not None and provided_agent != PM_AGENT_ID:
        raise HTTPException(
            status_code=422,
            detail=(
                "mission intake must route through AGENT-01-PM; "
                "set agent_id/selected_agent_id to AGENT-01-PM"
            ),
        )

    chain_trace = normalized.get("chain_trace")
    if isinstance(chain_trace, list):
        normalized_chain_trace = [record for record in chain_trace if isinstance(record, dict)]
    else:
        normalized_chain_trace = []

    if not any(
        str(record.get("event_type", "")) == "MISSION_PM_INTAKE"
        for record in normalized_chain_trace
    ):
        normalized_chain_trace.append(
            {
                "event_type": "MISSION_PM_INTAKE",
                "agent_id": PM_AGENT_ID,
                "details": {"source": "api-gateway-intake"},
            }
        )

    normalized["routing_version"] = ROUTING_VERSION
    normalized["routing_enforced"] = True
    normalized["intake_agent_id"] = PM_AGENT_ID
    normalized["executive_agent_id"] = CEO_AGENT_ID
    normalized["expected_pod_manager_agent_id"] = _resolve_pod_manager_agent(
        requested_target_language
    )
    normalized["agent_id"] = PM_AGENT_ID
    normalized["selected_agent_id"] = PM_AGENT_ID
    explicit_project_id = normalized.get("project_id")
    if isinstance(explicit_project_id, str) and explicit_project_id.strip():
        normalized["project_id"] = _normalize_project_id(
            explicit_project_id,
            fallback="project-unknown",
        )
    else:
        source = normalized.get("source")
        if isinstance(source, str) and source.strip():
            normalized["project_id"] = _normalize_project_id(
                source,
                fallback="project-unknown",
            )
        else:
            normalized.pop("project_id", None)
    if "project_name" not in normalized:
        source = normalized.get("source")
        if isinstance(source, str) and source.strip():
            normalized["project_name"] = source.strip()
    normalized["chain_trace"] = normalized_chain_trace
    normalized["last_chain_event_type"] = "MISSION_PM_INTAKE"
    normalized["last_chain_event_at"] = None
    return normalized


def _idempotency_redis_key(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    return f"{IDEMPOTENCY_KEY_PREFIX}:{digest}"


async def _load_idempotency_record(redis_client: Any, redis_key: str) -> dict[str, Any] | None:
    raw = await redis_client.get(redis_key)
    if not raw:
        return None
    try:
        record = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return record if isinstance(record, dict) else None


async def _save_idempotency_record(
    redis_client: Any,
    redis_key: str,
    record: dict[str, Any],
    *,
    nx: bool = False,
) -> bool:
    saved = await redis_client.set(
        redis_key,
        json.dumps(record),
        ex=IDEMPOTENCY_TTL_SECONDS,
        nx=nx,
    )
    return bool(saved)


async def _reconcile_idempotent_mission(
    redis_client: Any,
    redis_key: str,
    request_hash: str,
    mission_id: str,
) -> MissionRecord | None:
    try:
        existing_mission = await _proxy_get_internal(f"/missions/{mission_id}")
    except HTTPException as exc:
        if exc.status_code == 404:
            return None
        raise

    mission_record = MissionRecord(**existing_mission)
    if not mission_record.project_id:
        mission_record.project_id = _resolve_project_id(
            mission_record.metadata,
            mission_id=mission_record.mission_id,
        )
    await _save_idempotency_record(
        redis_client,
        redis_key,
        {
            "status": "completed",
            "request_hash": request_hash,
            "mission_id": mission_id,
            "mission": mission_record.model_dump(mode="json"),
        },
    )
    return mission_record


async def _dependency_status() -> dict[str, bool]:
    redis_client = getattr(app.state, "redis", None)
    orchestrator_healthy = False
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(f"{ORCHESTRATOR_URL}/health")
            orchestrator_healthy = response.status_code == 200
    except httpx.RequestError as exc:
        LOGGER.warning("orchestrator health check failed: %s", exc)
        orchestrator_healthy = False

    redis_healthy = False
    if redis_client is not None:
        try:
            redis_healthy = bool(await redis_client.ping())
            app.state.redis_ready = redis_healthy
        except Exception as exc:
            LOGGER.warning("redis ping failed: %s", exc)
            redis_healthy = False
            app.state.redis_ready = False

    return {"orchestrator_healthy": orchestrator_healthy, "redis_healthy": redis_healthy}


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


def _sse_event_block(*, event_name: str, data: dict[str, Any], event_id: str | None = None) -> str:
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
    yield _sse_event_block(
        event_name="connected",
        data=connected_payload,
    )

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
            # resilience: any unhandled error inside the SSE loop would kill the stream — keep broadcasting
            LOGGER.warning("state stream sse read failure: %s", exc)
            LIVE_STREAM_ERRORS.labels(reason="read_failure").inc()
            error_payload = {"detail": "stream read failure"}
            yield _sse_event_block(event_name="stream_error", data=error_payload)
            await asyncio.sleep(1.0)


def _gateway_api_key_roles() -> dict[str, set[str]]:
    """Build the gateway's API-key→roles map from configured keys.

    Mirrors the orchestrator's role model so api_key-mode callers are
    authorized at the gateway instead of being silently elevated with the
    privileged internal service key.
    """
    mapping: dict[str, set[str]] = {}
    if ORCHESTRATOR_ADMIN_API_KEY:
        mapping[ORCHESTRATOR_ADMIN_API_KEY] = {"admin", "mutate", "internal", "read"}
    if INTERNAL_SERVICE_API_KEY.strip():
        mapping.setdefault(
            INTERNAL_SERVICE_API_KEY.strip(), {"worker", "mutate", "internal", "read"}
        )
    if ORCHESTRATOR_READONLY_API_KEY:
        mapping.setdefault(ORCHESTRATOR_READONLY_API_KEY, {"read"})
    for entry in (part.strip() for part in ORCHESTRATOR_API_KEYS.split(";") if part.strip()):
        if "=" not in entry:
            continue
        key, roles_csv = entry.split("=", 1)
        roles = {role.strip().lower() for role in roles_csv.split(",") if role.strip()}
        if key.strip() and roles:
            mapping[key.strip()] = roles
    return mapping


def _match_gateway_api_key(candidate: str) -> set[str] | None:
    # Constant-time compare against every configured key to avoid leaking which
    # keys exist via timing. Mirrors orchestrator.auth._match_api_key.
    candidate_bytes = candidate.encode("utf-8")
    matched: set[str] | None = None
    for stored_key, roles in _gateway_api_key_roles().items():
        if hmac.compare_digest(candidate_bytes, stored_key.encode("utf-8")):
            matched = roles
    return matched


def _require_api_key_role(x_api_key: str | None, required_role: str) -> None:
    """Validate ``X-API-Key`` against configured gateway keys for api_key mode.

    Raises 401 if the header is missing or unknown, 403 if the key lacks the
    required role.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="x-api-key header is required")
    roles = _match_gateway_api_key(x_api_key)
    if roles is None:
        raise HTTPException(status_code=401, detail="invalid api key")
    if required_role and required_role not in roles:
        raise HTTPException(status_code=403, detail="insufficient role for endpoint")


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.strip().lower() != "bearer":
        return None
    candidate = token.strip()
    return candidate or None


def _tokens_from_claim_value(value: Any) -> set[str]:
    if isinstance(value, str):
        raw_items = value.replace(",", " ").split()
        return {item.strip().lower() for item in raw_items if item.strip()}
    if isinstance(value, list):
        normalized: set[str] = set()
        for item in value:
            if isinstance(item, str) and item.strip():
                normalized.add(item.strip().lower())
        return normalized
    return set()


def _claim_includes_required_role(claims: dict[str, Any], required_role: str) -> bool:
    required = required_role.strip().lower()
    if not required:
        return True

    tokens: set[str] = set()
    for claim_name in OIDC_ROLE_CLAIMS + OIDC_SCOPE_CLAIMS:
        tokens.update(_tokens_from_claim_value(claims.get(claim_name)))

    return required in tokens


def _decode_oidc_token(token: str) -> dict[str, Any]:
    if jwt is None:
        raise HTTPException(status_code=503, detail="oidc auth dependencies are unavailable")

    decode_kwargs: dict[str, Any] = {
        "algorithms": OIDC_ALLOWED_ALGORITHMS or ["RS256"],
        "leeway": OIDC_LEEWAY_SECONDS,
        "options": {
            "verify_aud": bool(OIDC_AUDIENCE),
            "verify_iss": bool(OIDC_ISSUER_URL),
        },
    }
    if OIDC_AUDIENCE:
        decode_kwargs["audience"] = OIDC_AUDIENCE
    if OIDC_ISSUER_URL:
        decode_kwargs["issuer"] = OIDC_ISSUER_URL

    try:
        if OIDC_SHARED_SECRET:
            decoded = jwt.decode(token, OIDC_SHARED_SECRET, **decode_kwargs)
        else:
            if PyJWKClient is None:
                raise HTTPException(
                    status_code=503,
                    detail="oidc jwks validation is unavailable",
                )
            jwks_url = OIDC_JWKS_URL
            if not jwks_url and OIDC_ISSUER_URL:
                jwks_url = f"{OIDC_ISSUER_URL.rstrip('/')}/.well-known/jwks.json"
            if not jwks_url:
                raise HTTPException(
                    status_code=503,
                    detail="oidc jwks configuration is missing",
                )
            global _OIDC_JWKS_CLIENT
            if _OIDC_JWKS_CLIENT is None:
                _OIDC_JWKS_CLIENT = PyJWKClient(jwks_url)
            signing_key = _OIDC_JWKS_CLIENT.get_signing_key_from_jwt(token)
            decoded = jwt.decode(token, signing_key.key, **decode_kwargs)
    except HTTPException:
        raise
    except Exception as exc:
        # PyJWT raises many subtypes (InvalidSignatureError, ExpiredSignatureError, etc.)
        # Log class only — the exception message may contain token fragments.
        LOGGER.warning("oidc bearer token rejected: %s", type(exc).__name__)
        # Surface expiry distinctly so observability can separate expired tokens
        # from genuinely invalid ones (drives factory_auth_failures_total reason).
        if type(exc).__name__ == "ExpiredSignatureError":
            raise HTTPException(status_code=401, detail="expired bearer token") from exc
        raise HTTPException(status_code=401, detail="invalid bearer token") from exc

    if not isinstance(decoded, dict):
        raise HTTPException(status_code=401, detail="invalid bearer token")
    return decoded


def _resolve_mutation_forward_headers(
    *,
    x_api_key: str | None,
    authorization: str | None,
) -> dict[str, str]:
    bearer_token = _extract_bearer_token(authorization)
    mode = AUTH_MODE

    if mode == "api_key":
        if not x_api_key:
            raise HTTPException(status_code=401, detail="x-api-key header is required")
        return {"x-api-key": x_api_key}

    if mode == "hybrid":
        if bearer_token:
            claims = _decode_oidc_token(bearer_token)
            if not _claim_includes_required_role(claims, OIDC_REQUIRED_ROLE):
                raise HTTPException(status_code=403, detail="insufficient oidc role for endpoint")
            return {"x-api-key": _require_internal_service_api_key()}
        if x_api_key:
            return {"x-api-key": x_api_key}
        raise HTTPException(
            status_code=401,
            detail="authorization bearer token or x-api-key header is required",
        )

    if mode == "oidc":
        if not bearer_token:
            raise HTTPException(status_code=401, detail="authorization bearer token is required")
        claims = _decode_oidc_token(bearer_token)
        if not _claim_includes_required_role(claims, OIDC_REQUIRED_ROLE):
            raise HTTPException(status_code=403, detail="insufficient oidc role for endpoint")
        return {"x-api-key": _require_internal_service_api_key()}

    raise HTTPException(status_code=500, detail="gateway auth mode configuration error")


def _require_internal_service_api_key() -> str:
    configured_key = INTERNAL_SERVICE_API_KEY.strip()
    if configured_key:
        return configured_key

    LOGGER.error(
        "INTERNAL_SERVICE_API_KEY is required for internal gateway forwarding when AUTH_MODE=%s",
        AUTH_MODE,
    )
    raise HTTPException(status_code=503, detail="gateway internal auth is not configured")


def _require_operator_access(
    *,
    x_api_key: str | None,
    authorization: str | None,
) -> None:
    if GATEWAY_ADMIN_BYPASS:
        return

    mode = AUTH_MODE

    if mode == "api_key":
        # Operator routes proxy to privileged internal orchestrator endpoints using
        # the gateway's internal key, so the gateway MUST authorize the caller here.
        # Minimum `read` role required — never skip auth for non-health routes.
        _require_api_key_role(x_api_key, "read")
        return

    if not OIDC_ENFORCE_OPERATOR_ROUTES:
        return

    bearer_token = _extract_bearer_token(authorization)

    if mode == "hybrid":
        if bearer_token:
            claims = _decode_oidc_token(bearer_token)
            if not _claim_includes_required_role(claims, OIDC_OPERATOR_ROLE):
                raise HTTPException(
                    status_code=403,
                    detail="insufficient oidc role for operator route",
                )
            return
        if x_api_key:
            return
        raise HTTPException(
            status_code=401,
            detail="authorization bearer token or x-api-key header is required",
        )

    if mode == "oidc":
        if not bearer_token:
            raise HTTPException(status_code=401, detail="authorization bearer token is required")
        claims = _decode_oidc_token(bearer_token)
        if not _claim_includes_required_role(claims, OIDC_OPERATOR_ROLE):
            raise HTTPException(status_code=403, detail="insufficient oidc role for operator route")
        return

    raise HTTPException(status_code=500, detail="gateway auth mode configuration error")


def _require_reader_access(
    *,
    x_api_key: str | None,
    authorization: str | None,
) -> None:
    """Require minimum read authorization for resource-read routes.

    Mission prompts, metadata, and source code must not be world-readable.
    Enforced across all auth modes (api_key validates X-API-Key with `read`
    role; hybrid/oidc validate a bearer token carrying the read role, or an
    X-API-Key in hybrid mode).
    """
    if GATEWAY_ADMIN_BYPASS:
        return

    mode = AUTH_MODE

    if mode == "api_key":
        _require_api_key_role(x_api_key, "read")
        return

    bearer_token = _extract_bearer_token(authorization)

    if mode == "hybrid":
        if bearer_token:
            claims = _decode_oidc_token(bearer_token)
            if not _claim_includes_required_role(claims, "read"):
                raise HTTPException(
                    status_code=403, detail="insufficient oidc role for endpoint"
                )
            return
        if x_api_key:
            _require_api_key_role(x_api_key, "read")
            return
        raise HTTPException(
            status_code=401,
            detail="authorization bearer token or x-api-key header is required",
        )

    if mode == "oidc":
        if not bearer_token:
            raise HTTPException(status_code=401, detail="authorization bearer token is required")
        claims = _decode_oidc_token(bearer_token)
        if not _claim_includes_required_role(claims, "read"):
            raise HTTPException(status_code=403, detail="insufficient oidc role for endpoint")
        return

    raise HTTPException(status_code=500, detail="gateway auth mode configuration error")


def _normalize_builder_text(value: str) -> str:
    return " ".join(value.split())


def _collect_distinct_lines(value: str, limit: int) -> list[str]:
    lines: list[str] = []
    for raw_line in value.splitlines():
        candidate = raw_line.strip().lstrip("-*").strip()
        if not candidate:
            continue
        if candidate in lines:
            continue
        lines.append(candidate)
        if len(lines) >= limit:
            break
    return lines


def _build_offline_builder_preview(
    payload: BuilderPreviewRequest,
    *,
    source: str = "offline",
    notice: str | None = None,
) -> dict[str, Any]:
    normalized_request = _normalize_builder_text(payload.request)
    constraints = [
        _normalize_builder_text(item)
        for item in payload.constraints
        if isinstance(item, str) and _normalize_builder_text(item)
    ][:5]
    key_constraint = constraints[0] if constraints else "Preserve existing architecture boundaries."

    response: dict[str, Any] = {
        "request_id": f"builder-{uuid.uuid4()}",
        "source": source,
        "generated_at": datetime.now(UTC).isoformat(),
        "plan": [
            {
                "title": "Scope and acceptance criteria",
                "description": f"Clarify boundaries for: {normalized_request[:180]}",
            },
            {
                "title": "Implementation slices",
                "description": (
                    "Deliver in thin vertical slices across API, UI, and persistence "
                    "with rollback safety."
                ),
            },
            {
                "title": "Validation and hardening",
                "description": "Add tests, lint, and production checks before merge.",
            },
        ],
        "diff_summary": [
            f"Proposed change request: {normalized_request[:220]}",
            f"Primary constraint: {key_constraint[:180]}",
            f"Viewport target: {payload.view_mode or 'desktop'}",
        ],
        "risk_notes": [
            "Verify backward compatibility for existing mission routes and payload contracts.",
            "Guard UI changes with loading/error states to avoid stale operator actions.",
            "Validate input sanitization and idempotency for mutation endpoints.",
        ],
        "test_plan": [
            "Add unit tests for parsing and route behavior.",
            "Run service tests, lint checks, and frontend build verification.",
            "Run smoke tests against local docker stack before release.",
        ],
    }
    if notice:
        response["notice"] = notice
    return response


def _extract_openai_text(payload: dict[str, Any]) -> str | None:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    if isinstance(output_text, list):
        collected = [item.strip() for item in output_text if isinstance(item, str) and item.strip()]
        if collected:
            return "\n".join(collected)

    output_items = payload.get("output")
    if isinstance(output_items, list):
        collected_parts: list[str] = []
        for item in output_items:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                text_value = block.get("text")
                if isinstance(text_value, str) and text_value.strip():
                    collected_parts.append(text_value.strip())
        if collected_parts:
            return "\n".join(collected_parts)

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
    return None


def _build_builder_prompt(payload: BuilderPreviewRequest) -> str:
    constraints_text = "\n".join(
        f"- {_normalize_builder_text(item)}"
        for item in payload.constraints
        if isinstance(item, str) and _normalize_builder_text(item)
    )
    user_prompt = payload.request
    if constraints_text:
        user_prompt = f"{payload.request}\n\nConstraints:\n{constraints_text}"
    if payload.view_mode:
        user_prompt = f"{user_prompt}\n\nViewport: {payload.view_mode}"
    return user_prompt


def _extract_anthropic_text(payload: dict[str, Any]) -> str | None:
    content = payload.get("content")
    if not isinstance(content, list):
        return None

    collected: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text":
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            collected.append(text.strip())

    if collected:
        return "\n".join(collected)
    return None


def _extract_gemini_text(payload: dict[str, Any]) -> str | None:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return None

    collected: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                collected.append(text.strip())

    if collected:
        return "\n".join(collected)
    return None


def _is_gemini_3_model(model: str) -> bool:
    normalized = model.strip().lower()
    return (
        normalized.startswith("gemini-3-")
        or normalized.startswith("gemini-3.1-")
        or normalized.startswith("gemini-3.5-")
    )


def _to_gemini_thinking_level(reasoning_effort: str | None) -> str:
    effort = (reasoning_effort or "").strip().lower()
    if effort in {"none", "minimal", "low"}:
        return "low"
    if effort in {"high", "xhigh"}:
        return "high"
    return "medium"


def _resolve_preview_model_route(provider: str, model: str | None) -> tuple[str, str | None]:
    normalized_provider = provider.strip().lower()
    selected_model = model.strip() if isinstance(model, str) and model.strip() else None
    if selected_model is None:
        return normalized_provider, None
    resolved_provider = ALLOWED_LLM_MODELS.get(selected_model)
    if resolved_provider is None:
        raise HTTPException(
            status_code=400,
            detail="model must be one of: " + ", ".join(sorted(ALLOWED_LLM_MODELS)),
        )
    if normalized_provider not in {"offline", resolved_provider}:
        raise HTTPException(
            status_code=400,
            detail=f"model {selected_model} must use provider {resolved_provider}",
        )
    return resolved_provider, selected_model


async def _openai_builder_preview(
    payload: BuilderPreviewRequest,
    *,
    model: str,
    reasoning_effort: str | None,
) -> dict[str, Any] | None:
    user_prompt = _build_builder_prompt(payload)

    request_payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You are a software architect. Provide concise implementation guidance "
                    "for a local enterprise application."
                ),
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    }
    if reasoning_effort:
        request_payload["reasoning"] = {"effort": reasoning_effort}
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{OPENAI_BASE_URL}/responses",
                json=request_payload,
                headers=headers,
            )
    except httpx.RequestError as exc:
        LOGGER.warning("openai preview request failed: %s", exc)
        return None

    if response.status_code >= 400:
        LOGGER.warning(
            "openai preview returned non-success status: %s",
            response.status_code,
        )
        return None

    try:
        payload_json = response.json()
    except ValueError:
        LOGGER.warning("openai preview returned non-json payload")
        return None

    llm_text = _extract_openai_text(payload_json)
    if llm_text is None:
        LOGGER.warning("openai preview response did not contain readable text")
        return None

    summary_lines = _collect_distinct_lines(llm_text, 8)
    preview = _build_offline_builder_preview(payload, source="openai")
    if summary_lines:
        preview["plan"][0]["description"] = summary_lines[0]
        preview["diff_summary"] = summary_lines[:4]
        if len(summary_lines) > 4:
            preview["risk_notes"] = summary_lines[4:7]
    preview["notice"] = "Generated from live LLM output."
    return preview


async def _anthropic_builder_preview(
    payload: BuilderPreviewRequest,
    *,
    model: str,
    thinking_mode: str,
    thinking_budget: int,
) -> dict[str, Any] | None:
    user_prompt = _build_builder_prompt(payload)
    request_payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 1200,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if thinking_mode == "enabled":
        request_payload["thinking"] = {
            "type": "enabled",
            "budget_tokens": max(1024, thinking_budget),
        }
    elif thinking_mode == "adaptive":
        request_payload["thinking"] = {"type": "adaptive"}

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=ANTHROPIC_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{ANTHROPIC_BASE_URL}/messages",
                json=request_payload,
                headers=headers,
            )
    except httpx.RequestError as exc:
        LOGGER.warning("anthropic preview request failed: %s", exc)
        return None

    if response.status_code >= 400:
        LOGGER.warning(
            "anthropic preview returned non-success status: %s",
            response.status_code,
        )
        return None

    try:
        payload_json = response.json()
    except ValueError:
        LOGGER.warning("anthropic preview returned non-json payload")
        return None

    llm_text = _extract_anthropic_text(payload_json)
    if llm_text is None:
        LOGGER.warning("anthropic preview response did not contain readable text")
        return None

    summary_lines = _collect_distinct_lines(llm_text, 8)
    preview = _build_offline_builder_preview(payload, source="anthropic")
    if summary_lines:
        preview["plan"][0]["description"] = summary_lines[0]
        preview["diff_summary"] = summary_lines[:4]
        if len(summary_lines) > 4:
            preview["risk_notes"] = summary_lines[4:7]
    preview["notice"] = "Generated from live LLM output."
    return preview


async def _gemini_builder_preview(
    payload: BuilderPreviewRequest,
    *,
    model: str,
    thinking_budget: int,
    thinking_level: str | None,
) -> dict[str, Any] | None:
    user_prompt = _build_builder_prompt(payload)
    generation_config: dict[str, Any] = {
        "temperature": 0.2,
        "maxOutputTokens": 1200,
    }
    if _is_gemini_3_model(model):
        generation_config["thinkingConfig"] = {
            "thinkingLevel": _to_gemini_thinking_level(thinking_level),
        }
    elif thinking_budget >= 0:
        generation_config["thinkingConfig"] = {"thinkingBudget": thinking_budget}

    request_payload = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": generation_config,
    }
    try:
        async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{GEMINI_BASE_URL}/models/{model}:generateContent",
                params={"key": GEMINI_API_KEY},
                json=request_payload,
                headers={"Content-Type": "application/json"},
            )
    except Exception as exc:
        LOGGER.warning("gemini preview request failed: %s", exc)
        return None

    if response.status_code >= 400:
        LOGGER.warning(
            "gemini preview returned non-success status: %s",
            response.status_code,
        )
        return None

    try:
        payload_json = response.json()
    except ValueError:
        LOGGER.warning("gemini preview returned non-json payload")
        return None

    llm_text = _extract_gemini_text(payload_json)
    if llm_text is None:
        LOGGER.warning("gemini preview response did not contain readable text")
        return None

    summary_lines = _collect_distinct_lines(llm_text, 8)
    preview = _build_offline_builder_preview(payload, source="gemini")
    if summary_lines:
        preview["plan"][0]["description"] = summary_lines[0]
        preview["diff_summary"] = summary_lines[:4]
        if len(summary_lines) > 4:
            preview["risk_notes"] = summary_lines[4:7]
    preview["notice"] = "Generated from live LLM output."
    return preview


def _configured_cors_origins() -> list[str]:
    return [origin.strip() for origin in CORS_ALLOW_ORIGINS.split(",") if origin.strip()]


def _validate_startup_auth_config() -> None:
    """Fail fast or warn on insecure auth configuration at startup."""
    if AUTH_MODE not in ALLOWED_AUTH_MODES:
        allowed = ", ".join(sorted(ALLOWED_AUTH_MODES))
        raise RuntimeError(f"AUTH_MODE must be one of: {allowed}")

    if ENVIRONMENT == "production" and "*" in _configured_cors_origins():
        raise RuntimeError("CORS_ALLOW_ORIGINS cannot include '*' in production")

    if GATEWAY_ADMIN_BYPASS and ENVIRONMENT == "production":
        LOGGER.warning(
            "GATEWAY_ADMIN_BYPASS=true in production — ALL operator route "
            "authorization is DISABLED. Set GATEWAY_ADMIN_BYPASS=false."
        )

    if "HS256" in OIDC_ALLOWED_ALGORITHMS:
        LOGGER.warning(
            "OIDC_ALLOWED_ALGORITHMS includes HS256 — algorithm confusion attack "
            "risk (attacker uses the public key as the HMAC secret). Use RS256 only."
        )

    if AUTH_MODE in {"hybrid", "oidc"}:
        if not OIDC_AUDIENCE:
            LOGGER.warning("OIDC_AUDIENCE not set — JWT audience verification disabled")
        if AUTH_MODE == "oidc" and not OIDC_ISSUER_URL:
            raise RuntimeError("OIDC_ISSUER_URL required when AUTH_MODE=oidc")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_startup_auth_config()

    app.state.redis = None
    app.state.redis_ready = False

    if redis is not None:
        app.state.redis = redis.from_url(REDIS_URL, decode_responses=True)
        try:
            await app.state.redis.ping()
            app.state.redis_ready = True
        except (ConnectionError, TimeoutError, OSError, _RedisConnectionError) as exc:
            LOGGER.warning("redis startup ping failed, marking not ready: %s", exc)
            app.state.redis_ready = False

    yield

    if app.state.redis is not None:
        aclose = getattr(app.state.redis, "aclose", None)
        if callable(aclose):
            await aclose()
        else:
            await app.state.redis.close()


_OPENAPI_TAGS = [
    {"name": "system", "description": "Liveness, readiness, and Prometheus metrics. Public, unauthenticated."},
    {"name": "missions", "description": "Mission lifecycle: create, inspect, stream state, and retrieve artifacts."},
    {"name": "mission-evidence", "description": "Per-mission audit reports, build artifacts, knowledge, and logic nodes."},
    {"name": "operations", "description": "Operator/console aggregate views across all missions and agents."},
    {"name": "builder", "description": "Builder and PM authoring endpoints (feature contracts, previews)."},
    {"name": "maintenance", "description": "Operator maintenance actions (diagnostics, backups)."},
]

# Paths that are intentionally public (no X-API-Key required). Everything else
# is gated by an api_key dependency in the route body and is documented as such.
_PUBLIC_PATHS = {"/", "/health", "/readyz", "/metrics"}


def _openapi_tag_for_path(path: str) -> str:
    if path in _PUBLIC_PATHS:
        return "system"
    if path.startswith("/v1/operations"):
        return "operations"
    if path.startswith("/v1/maintenance"):
        return "maintenance"
    if path.startswith("/v1/builder") or path.startswith("/v1/pm"):
        return "builder"
    if path.startswith("/v1/missions") and any(
        path.endswith(suffix) or f"/{suffix}" in path
        for suffix in (
            "audit-reports", "audit-artifacts", "audit-events", "build-artifacts",
            "knowledge", "knowledge-graph", "logicnodes", "token-usage",
            "chain-trace", "pod-assignment",
        )
    ):
        return "mission-evidence"
    return "missions"


app = FastAPI(
    title="HolyGrail API Gateway",
    version="0.3.0",
    lifespan=lifespan,
    description=(
        "Public ingress for theFactory (Holy Grail Refinery). Mission, operations, "
        "builder, and maintenance routes require an `X-API-Key` header; system "
        "health/metrics routes are public."
    ),
    openapi_tags=_OPENAPI_TAGS,
)
configure_tracing(app, service_name="api-gateway")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_configured_cors_origins(),
    allow_credentials=False,
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=CORS_ALLOW_HEADERS,
    expose_headers=CORS_EXPOSE_HEADERS,
)


def _custom_openapi() -> dict[str, Any]:
    """Enrich the generated schema with security, tags, and auth error responses.

    Authentication is enforced inside route bodies via the ``X-API-Key`` header
    dependency rather than FastAPI ``Security`` objects, so the generated schema
    would otherwise show no security requirement and omit 401/403. This hook
    declares the ``api_key`` scheme, applies it to every non-public operation,
    groups operations by tag, and documents the auth failure responses.
    """
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=_OPENAPI_TAGS,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["api_key"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "Gateway API key. Role (read/mutate/admin) is derived from the key.",
    }
    auth_responses = {
        "401": {"description": "Missing or invalid X-API-Key header."},
        "403": {"description": "API key lacks the required role for this operation."},
    }
    for path, operations in schema.get("paths", {}).items():
        tag = _openapi_tag_for_path(path)
        is_public = path in _PUBLIC_PATHS
        for method, operation in operations.items():
            if method not in {"get", "post", "put", "delete", "patch"}:
                continue
            operation["tags"] = [tag]
            if not is_public:
                operation["security"] = [{"api_key": []}]
                operation.setdefault("responses", {})
                for code, body in auth_responses.items():
                    operation["responses"].setdefault(code, body)
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi


def _request_correlation_id(request: Request) -> str:
    header = (
        request.headers.get("x-request-id")
        or request.headers.get("x-correlation-id")
        or ""
    ).strip()
    if header:
        return header[:128]
    return uuid.uuid4().hex


@app.middleware("http")
async def _request_metrics_and_audit(request: Request, call_next):
    """Combined metrics + structured audit log middleware.

    2026 best practice (OWASP API Security): log every request with
    method, path, status, duration, trace-id, and sanitised identity.
    No secrets or request bodies are logged.
    """
    started = time.perf_counter()
    method = request.method
    status_code = "500"
    trace_id = current_trace_id()
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        return response
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        route = request.scope.get("route")
        path = route.path if route is not None else request.url.path
        REQUEST_COUNTER.labels(method=method, path=path, status_code=status_code).inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(elapsed_ms / 1000)
        # Structured audit log — no secrets, no bodies
        _client_ip = (request.client.host if request.client else "unknown")
        LOGGER.info(
            "audit",
            extra={
                "audit": True,
                "method": method,
                "path": path,
                "status": status_code,
                "duration_ms": round(elapsed_ms, 2),
                "trace_id": trace_id or "",
                "client_ip_hash": hashlib.sha256(_client_ip.encode()).hexdigest()[:16],
            },
        )



@app.middleware("http")
async def _security_hardening_headers(request: Request, call_next):
    """Inject high-integrity enterprise security headers (OWASP 2026)."""
    response = await call_next(request)
    
    # 2026 Enterprise baseline headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0" # Disabled in favor of strict CSP
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
    
    # Strict Transport Security (HSTS) if not on plain HTTP dev
    if ENVIRONMENT != "development":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

    return response


def _classify_auth_failure_reason(status_code: int, detail: str) -> str:
    """Map an auth-related HTTP error to a factory_auth_failures_total reason.

    reason = invalid_key | expired_token | insufficient_role | missing_auth
    """
    text = (detail or "").lower()
    if status_code == 403 or "insufficient" in text:
        return "insufficient_role"
    if "expired" in text:
        return "expired_token"
    if "required" in text or "missing" in text:
        return "missing_auth"
    return "invalid_key"


def _route_prefix(path: str) -> str:
    """Collapse a request path to a low-cardinality route prefix label."""
    parts = [p for p in path.split("/") if p]
    if not parts:
        return "/"
    if parts[0] == "v1" and len(parts) >= 2:
        return f"/v1/{parts[1]}"
    return f"/{parts[0]}"


@app.exception_handler(HTTPException)
async def _auth_failure_metrics_handler(request: Request, exc: HTTPException):
    """Record authentication/authorization failures, then delegate to the
    default HTTPException rendering so response behavior is unchanged."""
    if exc.status_code in (401, 403):
        try:
            AUTH_FAILURES_TOTAL.labels(
                reason=_classify_auth_failure_reason(exc.status_code, str(exc.detail)),
                route_prefix=_route_prefix(request.url.path),
            ).inc()
        except Exception:  # noqa: BLE001
            LOGGER.warning("failed to record auth failure metric", exc_info=True)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


@app.middleware("http")
async def _security_and_rate_limit(request: Request, call_next):
    response: Response
    rate_limit_headers: dict[str, str] = {}
    path = request.url.path
    correlation_id = _request_correlation_id(request)
    request.state.correlation_id = correlation_id
    is_probe = path in {"/health", "/readyz", "/metrics"}
    is_stream = path == "/v1/stream/state"

    if API_RATE_LIMIT_PER_MINUTE > 0 and not is_probe and not is_stream:
        redis_client = getattr(app.state, "redis", None)
        redis_ready = bool(getattr(app.state, "redis_ready", False))
        if redis_client is not None and redis_ready:
            try:
                limited, retry_after, remaining = await _check_rate_limit(
                    redis_client, _client_identifier(request)
                )
                if limited:
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "rate limit exceeded"},
                        headers={
                            "Retry-After": str(retry_after),
                            "X-RateLimit-Limit": str(API_RATE_LIMIT_PER_MINUTE),
                            "X-RateLimit-Remaining": "0",
                            "X-Correlation-Id": correlation_id,
                        },
                    )
                rate_limit_headers = {
                    "X-RateLimit-Limit": str(API_RATE_LIMIT_PER_MINUTE),
                    "X-RateLimit-Remaining": str(remaining),
                }
            except (ConnectionError, TimeoutError, OSError, _RedisConnectionError) as exc:
                # resilience: fail-open — request proceeds without rate-limit enforcement
                LOGGER.warning("rate limiter unavailable for %s: %s — failing open", path, exc)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Correlation-Id"] = correlation_id
    trace_id = current_trace_id()
    if trace_id:
        response.headers["X-Trace-Id"] = trace_id
    for key, value in rate_limit_headers.items():
        response.headers[key] = value
    return response


_URL_CREDENTIAL_RE = re.compile(r"(?P<prefix>[a-zA-Z][a-zA-Z0-9+.\-]*://[^:@/]*):[^@/]*@")


def _redact_url_credentials(url: str) -> str:
    """Mask any password embedded in a URL's userinfo so health/diagnostic
    output never leaks secrets (e.g. the Redis connection password)."""
    if not url:
        return url
    return _URL_CREDENTIAL_RE.sub(r"\g<prefix>:***@", url)


@app.get("/health")
async def health() -> dict[str, Any]:
    dependency_status = await _dependency_status()

    return {
        "ok": True,
        "service": "api-gateway",
        "orchestrator_url": ORCHESTRATOR_URL,
        "orchestrator_healthy": dependency_status["orchestrator_healthy"],
        "redis_url": _redact_url_credentials(REDIS_URL),
        "redis_healthy": dependency_status["redis_healthy"],
        "intake_stream": INTAKE_STREAM,
        "state_stream": STATE_STREAM,
        "intake_topic": INTAKE_TOPIC,
        "auth_mode": AUTH_MODE,
        "oidc_role_required": OIDC_REQUIRED_ROLE if AUTH_MODE != "api_key" else None,
        "oidc_operator_role_required": (
            OIDC_OPERATOR_ROLE if AUTH_MODE != "api_key" and OIDC_ENFORCE_OPERATOR_ROUTES else None
        ),
        "oidc_enforce_operator_routes": OIDC_ENFORCE_OPERATOR_ROUTES,
    }


@app.get("/readyz")
async def readyz() -> dict[str, Any]:
    dependency_status = await _dependency_status()
    ready = all(dependency_status.values())
    if not ready:
        raise HTTPException(
            status_code=503,
            detail={
                "ready": False,
                "service": "api-gateway",
                **dependency_status,
            },
        )
    return {
        "ready": True,
        "service": "api-gateway",
        **dependency_status,
    }


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/v1/stream/state")
async def stream_state_events(
    mission_id: str | None = Query(default=None, min_length=1),
    include_agent_events: bool = Query(default=True),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> StreamingResponse:
    _require_operator_access(x_api_key=x_api_key, authorization=authorization)

    redis_client = getattr(app.state, "redis", None)
    if redis_client is None:
        raise HTTPException(status_code=503, detail="redis dependency is not installed")
    try:
        app.state.redis_ready = bool(await redis_client.ping())
    except (ConnectionError, TimeoutError, OSError, _RedisConnectionError) as exc:
        app.state.redis_ready = False
        raise HTTPException(status_code=503, detail=f"redis unavailable: {exc}") from exc

    LIVE_STREAM_CONNECTIONS.inc()
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    generator = _state_stream_sse_generator(
        redis_client,
        mission_id=mission_id,
        include_agent_events=include_agent_events,
        last_event_id=last_event_id,
    )
    return StreamingResponse(generator, media_type="text/event-stream", headers=headers)




def _prepare_initial_mission_payload(
    mission_id: str,
    payload: MissionCreate,
    created_at: str
) -> dict[str, Any]:
    """Construct the initial mission data structure."""
    mission_payload = {
        "mission_id": mission_id,
        "prompt": payload.prompt,
        "requested_target_language": payload.requested_target_language,
        "metadata": payload.metadata,
        "project_id": payload.metadata.get("project_id"),
        "created_at": created_at,
        "state": "INTAKE",
    }
    chain_trace = mission_payload["metadata"].get("chain_trace")
    if isinstance(chain_trace, list):
        for entry in chain_trace:
            if isinstance(entry, dict) and str(entry.get("event_type", "")) == "MISSION_PM_INTAKE" and not entry.get("ts"):
                entry["ts"] = created_at
    mission_payload["metadata"]["last_chain_event_at"] = created_at
    return mission_payload

async def _persist_mission_upstream(
    mission_id: str,
    payload: MissionCreate,
    metadata: dict[str, Any],
    created_at: str
) -> dict[str, Any]:
    """Proxy the mission creation to the orchestrator persistence layer."""
    return await _proxy_post_internal(
        "/missions",
        json_body={
            "mission_id": mission_id,
            "prompt": payload.prompt,
            "requested_target_language": payload.requested_target_language,
            "attachments": [a.model_dump() for a in payload.attachments],
            "global_style_directives": payload.global_style_directives,
            "metadata": metadata,
            "project_id": metadata.get("project_id"),
            "created_at": created_at,
        },
    )

async def _emit_intake_telemetry(
    redis_client: Any,
    mission_id: str,
    mission_payload: dict[str, Any]
) -> None:
    """Publish mission intake event to the Protocol Bus."""
    payload_ref = f"registry://missions/{mission_id}/intake"
    try:
        envelope = _build_envelope(correlation_id=mission_id, payload_ref=payload_ref)
        await redis_client.xadd(
            INTAKE_STREAM,
            {"envelope": json.dumps(envelope), "payload": json.dumps(mission_payload)},
            maxlen=MAX_STREAM_LEN,
            approximate=True,
        )
    except (ProtocolValidationError, json.JSONDecodeError) as exc:
        LOGGER.warning("mission intake telemetry envelope validation failed for %s: %s", mission_id, exc)
    except (ConnectionError, TimeoutError, OSError, _RedisConnectionError) as exc:
        LOGGER.warning("failed to publish mission intake telemetry for %s: %s", mission_id, exc)


async def _handle_mission_idempotency(
    redis_client: Any, 
    idempotency_key: str, 
    payload: MissionCreate,
    provisional_mission_id: str
) -> tuple[str | None, MissionRecord | None]:
    """Process idempotency logic and return (mission_id, existing_record)."""
    trimmed_key = idempotency_key.strip()
    if not trimmed_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key must not be empty")
    if len(trimmed_key) > 256:
        raise HTTPException(status_code=400, detail="Idempotency-Key must be <= 256 characters")

    request_hash = _request_hash(payload)
    redis_key = _idempotency_redis_key(trimmed_key)
    
    in_progress_record = {
        "status": "processing",
        "request_hash": request_hash,
        "mission_id": provisional_mission_id,
    }
    
    acquired = await _save_idempotency_record(redis_client, redis_key, in_progress_record, nx=True)
    if not acquired:
        existing = await _load_idempotency_record(redis_client, redis_key)
        if existing is None:
            await asyncio.sleep(0.05)
            acquired = await _save_idempotency_record(redis_client, redis_key, in_progress_record, nx=True)
            if not acquired:
                raise HTTPException(status_code=409, detail="request with this Idempotency-Key is in progress")
        else:
            if existing.get("request_hash") != request_hash:
                raise HTTPException(status_code=409, detail="Idempotency-Key reuse detected with different payload")
            if existing.get("status") == "completed" and isinstance(existing.get("mission"), dict):
                return None, MissionRecord(**existing["mission"])
            
            existing_id = str(existing.get("mission_id") or "").strip()
            if existing.get("status") == "upstream_unknown" and existing_id:
                reconciled = await _reconcile_idempotent_mission(redis_client, redis_key, request_hash, existing_id)
                if reconciled is not None:
                    return None, reconciled
                return existing_id, None
            raise HTTPException(status_code=409, detail="request with this Idempotency-Key is in progress")
    
    return provisional_mission_id, None



@app.post("/v1/missions", status_code=201)
async def create_mission(
    payload: MissionCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> MissionRecord:
    redis_client = getattr(app.state, "redis", None)
    if redis_client is None:
        raise HTTPException(status_code=503, detail="redis dependency is not installed")
    try:
        app.state.redis_ready = bool(await redis_client.ping())
    except (ConnectionError, TimeoutError, OSError, _RedisConnectionError) as exc:
        raise HTTPException(status_code=503, detail=f"redis unavailable: {exc}") from exc

    provisional_id = f"mission-{uuid.uuid4()}"
    normalized_metadata = _normalize_mission_metadata(
        payload.metadata, 
        mission_id=provisional_id,
        requested_target_language=payload.requested_target_language
    )
    if payload.source_code:
        normalized_metadata["source_code"] = payload.source_code
    
    payload = payload.model_copy(update={"metadata": normalized_metadata})

    mission_id = provisional_id
    idempotency_redis_key = None
    request_hash = None

    if idempotency_key:
        mission_id, existing = await _handle_mission_idempotency(redis_client, idempotency_key, payload, provisional_id)
        if existing:
            return existing
        idempotency_redis_key = _idempotency_redis_key(idempotency_key.strip())
        request_hash = _request_hash(payload)

    created_at = datetime.now(UTC).isoformat()
    mission_payload = _prepare_initial_mission_payload(mission_id, payload, created_at)

    try:
        persisted = await _persist_mission_upstream(mission_id, payload, mission_payload["metadata"], created_at)
    except Exception as exc:
        # save idempotency state before re-raising so clients can reconcile on retry
        LOGGER.warning("mission %s upstream persist failed: %s", mission_id, exc)
        if idempotency_redis_key:
            await _save_idempotency_record(redis_client, idempotency_redis_key, {
                "status": "upstream_unknown", "request_hash": request_hash,
                "mission_id": mission_id, "last_error": str(exc)
            })
        raise

    # Merge persisted state
    mission_payload.update({
        "state": str(persisted.get("state", "QUEUED")),
        "created_at": str(persisted.get("created_at", created_at)),
        "metadata": persisted.get("metadata") if isinstance(persisted.get("metadata"), dict) else mission_payload["metadata"],
        "project_id": str(persisted.get("project_id") or mission_payload["metadata"].get("project_id") or mission_payload["project_id"] or _resolve_project_id(mission_payload["metadata"], mission_id=mission_id))
    })

    await _emit_intake_telemetry(redis_client, mission_id, mission_payload)

    if idempotency_redis_key:
        try:
            await _save_idempotency_record(redis_client, idempotency_redis_key, {
                "status": "completed", "request_hash": request_hash,
                "mission_id": mission_id, "mission": mission_payload
            })
        except (ConnectionError, TimeoutError, OSError, _RedisConnectionError) as exc:
            LOGGER.warning("mission %s queued but failed to persist idempotency completion: %s", mission_id, exc)

    return MissionRecord(**mission_payload)



async def _proxy_get_internal(path: str, *, params: dict[str, Any] | None = None) -> Any:
    internal_key = _require_internal_service_api_key()
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(
                f"{ORCHESTRATOR_URL}{path}",
                params=params,
                headers={"x-api-key": internal_key},
            )
    except httpx.RequestError as exc:
        LOGGER.warning("orchestrator internal query failed for %s: %s", path, exc)
        raise HTTPException(status_code=502, detail="orchestrator unavailable") from exc
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="resource not found")
    if response.status_code in {401, 403}:
        raise HTTPException(status_code=502, detail="orchestrator internal auth rejected request")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="orchestrator internal query failed")
    return response.json()


async def _proxy_post_internal(
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = 4.0,
) -> Any:
    internal_key = _require_internal_service_api_key()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{ORCHESTRATOR_URL}{path}",
                json=json_body,
                params=params,
                headers={"x-api-key": internal_key},
            )
    except httpx.RequestError as exc:
        LOGGER.warning("orchestrator internal mutation failed for %s: %s", path, exc)
        raise HTTPException(status_code=502, detail="orchestrator unavailable") from exc
    if response.status_code in {401, 403}:
        raise HTTPException(status_code=502, detail="orchestrator internal auth rejected request")
    if response.status_code >= 400:
        try:
            payload = response.json()
        except ValueError as exc:
            LOGGER.warning("orchestrator returned non-json error body: %s", exc)
            payload = {}
        detail = payload.get("detail") if isinstance(payload, dict) else None
        raise HTTPException(
            status_code=502,
            detail=str(detail or "orchestrator internal write failed"),
        )
    return response.json()


@app.get("/v1/missions/{mission_id}")
async def get_mission(
    mission_id: str,
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    _require_reader_access(x_api_key=x_api_key, authorization=authorization)
    return await _proxy_get_internal(f"/missions/{mission_id}")


@app.get("/v1/missions")
async def list_missions(
    limit: int = Query(default=20, ge=1, le=200),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> list[dict[str, Any]]:
    _require_reader_access(x_api_key=x_api_key, authorization=authorization)
    return await _proxy_get_internal("/missions", params={"limit": limit})


@app.get("/v1/missions/{mission_id}/events")
async def get_mission_events(
    mission_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> list[dict[str, Any]]:
    _require_reader_access(x_api_key=x_api_key, authorization=authorization)
    return await _proxy_get_internal(f"/missions/{mission_id}/events", params={"limit": limit})


@app.get("/v1/missions/{mission_id}/pod-assignment")
async def get_mission_pod_assignment(mission_id: str) -> dict[str, Any]:
    return await _proxy_get_internal(f"/internal/missions/{mission_id}/pod-assignment")


@app.get("/v1/missions/{mission_id}/chain-trace")
async def get_mission_chain_trace(mission_id: str) -> dict[str, Any]:
    return await _proxy_get_internal(f"/internal/missions/{mission_id}/chain-trace")


@app.post("/v1/pm/feature-contract")
async def create_pm_feature_contract(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = str(payload.get("prompt") or payload.get("request") or "").strip()
    if len(prompt) < 3:
        raise HTTPException(status_code=400, detail="prompt must be at least 3 characters")
    return await _proxy_post_internal(
        "/internal/pm/feature-contract",
        json_body={**payload, "prompt": prompt},
        # LLM-backed endpoint: the orchestrator calls Gemini (high thinking),
        # which routinely exceeds the 4s default. Match/exceed the UI's 60s.
        timeout=90.0,
    )


@app.get("/v1/missions/{mission_id}/logicnodes")
async def get_mission_logicnodes(
    mission_id: str, limit: int = Query(default=50, ge=1, le=500)
) -> list[dict[str, Any]]:
    return await _proxy_get_internal(
        f"/internal/missions/{mission_id}/logicnodes", params={"limit": limit}
    )


@app.get("/v1/missions/{mission_id}/knowledge")
async def get_mission_knowledge(
    mission_id: str, limit: int = Query(default=50, ge=1, le=500)
) -> list[dict[str, Any]]:
    return await _proxy_get_internal(
        f"/internal/missions/{mission_id}/knowledge", params={"limit": limit}
    )


@app.get("/v1/missions/{mission_id}/knowledge-graph")
async def get_mission_knowledge_graph(
    mission_id: str, limit: int = Query(default=50, ge=1, le=500)
) -> list[dict[str, Any]]:
    return await _proxy_get_internal(
        f"/internal/missions/{mission_id}/knowledge-graph",
        params={"limit": limit},
    )


@app.get("/v1/missions/{mission_id}/audit-reports")
async def get_mission_audit_reports(
    mission_id: str, limit: int = Query(default=50, ge=1, le=500)
) -> list[dict[str, Any]]:
    return await _proxy_get_internal(
        f"/internal/missions/{mission_id}/audit-reports", params={"limit": limit}
    )


@app.get("/v1/missions/{mission_id}/audit-artifacts")
async def get_mission_audit_artifacts(
    mission_id: str, limit: int = Query(default=50, ge=1, le=500)
) -> list[dict[str, Any]]:
    return await _proxy_get_internal(
        f"/internal/missions/{mission_id}/audit-artifacts",
        params={"limit": limit},
    )


@app.get("/v1/missions/{mission_id}/audit-events")
async def get_mission_audit_events(
    mission_id: str, limit: int = Query(default=100, ge=1, le=1000)
) -> list[dict[str, Any]]:
    return await _proxy_get_internal(
        f"/internal/missions/{mission_id}/audit-events",
        params={"limit": limit},
    )


@app.get("/v1/missions/{mission_id}/build-artifacts")
async def get_mission_build_artifacts(
    mission_id: str, limit: int = Query(default=50, ge=1, le=500)
) -> list[dict[str, Any]]:
    return await _proxy_get_internal(
        f"/internal/missions/{mission_id}/build-artifacts",
        params={"limit": limit},
    )


@app.get("/v1/missions/{mission_id}/build-artifacts/{artifact_id}")
async def get_mission_build_artifact(
    mission_id: str,
    artifact_id: str,
) -> dict[str, Any]:
    return await _proxy_get_internal(
        f"/internal/missions/{mission_id}/build-artifacts/{artifact_id}",
    )


@app.get("/v1/missions/{mission_id}/artifact")
async def download_mission_artifact(
    mission_id: str,
    artifact_type: str = Query(default="generated_code"),
) -> Response:
    records = await _proxy_get_internal(
        f"/internal/missions/{mission_id}/build-artifacts",
        params={"limit": 50},
    )
    for record in records:
        if not isinstance(record, dict):
            continue
        if str(record.get("artifact_type", "")) != artifact_type:
            continue
        artifact_id = record.get("artifact_id")
        if not artifact_id:
            continue
        full_record = await _proxy_get_internal(
            f"/internal/missions/{mission_id}/build-artifacts/{artifact_id}",
        )
        if not isinstance(full_record, dict):
            continue
        artifact_text = full_record.get("artifact_text")
        if not isinstance(artifact_text, str) or not artifact_text:
            continue
        manifest = full_record.get("manifest") if isinstance(full_record.get("manifest"), dict) else {}
        filename = str(manifest.get("filename") or "artifact.txt")
        filename = filename.replace("\\", "_").replace("/", "_").replace("..", "_")
        language = str(manifest.get("language") or "text").strip().lower()
        media_types = {
            "python": "text/x-python",
            "javascript": "application/javascript",
            "typescript": "application/typescript",
            "java": "text/x-java-source",
            "go": "text/x-go",
            "rust": "text/plain",
        }
        return Response(
            content=artifact_text,
            media_type=media_types.get(language, "text/plain"),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    raise HTTPException(status_code=404, detail=f"No {artifact_type} artifact found")


@app.get("/v1/missions/{mission_id}/token-usage")
async def get_mission_token_usage(
    mission_id: str,
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> Any:
    _require_operator_access(x_api_key=x_api_key, authorization=authorization)
    return await _proxy_get_internal(f"/missions/{mission_id}/token-usage")


@app.get("/v1/operations/summary")
async def get_operations_summary(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    _require_operator_access(x_api_key=x_api_key, authorization=authorization)
    return await _proxy_get_internal("/internal/operations/summary")


@app.get("/v1/operations/agents")
async def get_operations_agents(
    mission_limit: int = Query(default=1000, ge=50, le=5000),
    assignment_limit: int = Query(default=1000, ge=50, le=5000),
    event_limit: int = Query(default=300, ge=50, le=2000),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    _require_operator_access(x_api_key=x_api_key, authorization=authorization)
    return await _proxy_get_internal(
        "/internal/operations/agents",
        params={
            "mission_limit": mission_limit,
            "assignment_limit": assignment_limit,
            "event_limit": event_limit,
        },
    )


@app.get("/v1/operations/events")
async def get_operations_events(
    limit: int = Query(default=200, ge=1, le=1000),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> list[dict[str, Any]]:
    _require_operator_access(x_api_key=x_api_key, authorization=authorization)
    return await _proxy_get_internal("/internal/operations/events", params={"limit": limit})


@app.get("/v1/operations/agent-events")
async def get_operations_agent_events(
    limit: int = Query(default=200, ge=1, le=1000),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> list[dict[str, Any]]:
    _require_operator_access(x_api_key=x_api_key, authorization=authorization)
    return await _proxy_get_internal("/internal/operations/agent-events", params={"limit": limit})


@app.get("/v1/operations/agent-integrations")
async def get_operations_agent_integrations(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    _require_operator_access(x_api_key=x_api_key, authorization=authorization)
    return await _proxy_get_internal("/internal/operations/agent-integrations")


@app.get("/v1/operations/logicnodes")
async def get_operations_logicnodes(
    limit: int = Query(default=200, ge=1, le=1000),
    mission_id: str | None = Query(default=None),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> list[dict[str, Any]]:
    _require_operator_access(x_api_key=x_api_key, authorization=authorization)
    params: dict[str, Any] = {"limit": limit}
    if mission_id:
        params["mission_id"] = mission_id
    return await _proxy_get_internal("/internal/operations/logicnodes", params=params)


@app.get("/v1/operations/pod-assignments")
async def get_operations_pod_assignments(
    limit: int = Query(default=200, ge=1, le=1000),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> list[dict[str, Any]]:
    _require_operator_access(x_api_key=x_api_key, authorization=authorization)
    return await _proxy_get_internal(
        "/internal/operations/pod-assignments",
        params={"limit": limit},
    )


@app.get("/v1/operations/projects")
async def get_operations_projects(
    limit: int = Query(default=100, ge=1, le=500),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> list[dict[str, Any]]:
    _require_operator_access(x_api_key=x_api_key, authorization=authorization)
    return await _proxy_get_internal("/internal/operations/projects", params={"limit": limit})


@app.get("/v1/operations/projects/{project_id}/audit-events")
async def get_project_audit_events(
    project_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    mission_id: str | None = Query(default=None),
    agent_id: str | None = Query(default=None),
    tool_name: str | None = Query(default=None),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> list[dict[str, Any]]:
    _require_operator_access(x_api_key=x_api_key, authorization=authorization)
    params: dict[str, Any] = {"limit": limit}
    if mission_id:
        params["mission_id"] = mission_id
    if agent_id:
        params["agent_id"] = agent_id
    if tool_name:
        params["tool_name"] = tool_name
    return await _proxy_get_internal(
        f"/internal/operations/projects/{project_id}/audit-events",
        params=params,
    )


@app.get("/v1/operations/alerts")
async def get_operations_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> list[dict[str, Any]]:
    _require_operator_access(x_api_key=x_api_key, authorization=authorization)
    return await _proxy_get_internal("/internal/operations/alerts", params={"limit": limit})



async def _dispatch_llm_preview(
    payload: BuilderPreviewRequest,
    provider: str,
    selected_model: str | None
) -> dict[str, Any] | None:
    """Unified LLM preview dispatcher."""
    if provider == "openai":
        if not OPENAI_API_KEY:
            return None
        return await _openai_builder_preview(
            payload, 
            model=selected_model or OPENAI_MODEL,
            reasoning_effort=payload.reasoning_effort or OPENAI_REASONING_EFFORT
        )
    if provider == "anthropic":
        if not ANTHROPIC_API_KEY:
            return None
        return await _anthropic_builder_preview(
            payload,
            model=selected_model or ANTHROPIC_MODEL,
            thinking_mode=ANTHROPIC_THINKING_MODE,
            thinking_budget=payload.thinking_budget if payload.thinking_budget is not None else ANTHROPIC_THINKING_BUDGET_TOKENS
        )
    if provider == "gemini":
        if not GEMINI_API_KEY:
            return None
        return await _gemini_builder_preview(
            payload,
            model=selected_model or GEMINI_MODEL,
            thinking_budget=payload.thinking_budget if payload.thinking_budget is not None else GEMINI_THINKING_BUDGET,
            thinking_level=payload.reasoning_effort or GEMINI_THINKING_LEVEL
        )
    return None



@app.post("/v1/builder/preview")
async def create_builder_preview(payload: BuilderPreviewRequest) -> dict[str, Any]:
    normalized_request = _normalize_builder_text(payload.request)
    if len(normalized_request) < 3:
        raise HTTPException(status_code=400, detail="request must be at least 3 characters")

    provider, selected_model = _resolve_preview_model_route(
        (payload.provider or LLM_PROVIDER).strip().lower(),
        payload.model,
    )

    normalized_payload = payload.model_copy(update={
        "request": normalized_request,
        "provider": provider,
        "model": selected_model
    })

    if provider != "offline":
        # Check whether the provider's API key is configured before dispatching.
        _key_map = {
            "openai": OPENAI_API_KEY,
            "anthropic": ANTHROPIC_API_KEY,
            "gemini": GEMINI_API_KEY,
        }
        if not _key_map.get(provider):
            return _build_offline_builder_preview(
                normalized_payload,
                source="offline",
                notice="provider not configured — returned deterministic preview.",
            )
        generated = await _dispatch_llm_preview(normalized_payload, provider, selected_model)
        if generated:
            return generated
        # Key was present but the live request failed — return provider-labelled fallback.
        source_map = {"openai": "openai-fallback", "anthropic": "anthropic-fallback", "gemini": "gemini-fallback"}
        return _build_offline_builder_preview(
            normalized_payload,
            source=source_map.get(provider, "offline"),
            notice="Live LLM request failed. Returned deterministic preview.",
        )

    return _build_offline_builder_preview(
        normalized_payload,
        source="offline",
        notice="Deterministic preview requested.",
    )



@app.post("/v1/missions/{mission_id}/state")
async def update_mission_state(
    mission_id: str,
    payload: MissionStateUpdate,
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    forward_headers = _resolve_mutation_forward_headers(
        x_api_key=x_api_key,
        authorization=authorization,
    )

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/missions/{mission_id}/state",
                json=payload.model_dump(),
                headers=forward_headers,
            )
    except httpx.RequestError as exc:
        LOGGER.exception("orchestrator mission state update failed for mission %s", mission_id)
        raise HTTPException(status_code=502, detail="orchestrator unavailable") from exc

    if response.status_code in {401, 403}:
        raise HTTPException(status_code=response.status_code, detail=response.json().get("detail"))
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="mission not found")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="orchestrator mutation failed")
    return response.json()




@app.post("/v1/maintenance/diagnostics")
async def create_gateway_diagnostics(
    mission_id: str | None = Query(default=None),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    _require_operator_access(x_api_key=x_api_key, authorization=authorization)
    return await _proxy_post_internal("/internal/maintenance/diagnostics", params={"mission_id": mission_id})


@app.post("/v1/maintenance/backup")
async def trigger_gateway_backup(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    _require_operator_access(x_api_key=x_api_key, authorization=authorization)
    return await _proxy_post_internal("/internal/maintenance/backup")


@app.get("/")
def index() -> dict[str, str]:
    return {"name": "HolyGrail API Gateway", "status": "ready"}
