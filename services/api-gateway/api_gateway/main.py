import hashlib
import json
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from .tracing import configure_tracing, current_trace_id

try:
    import redis.asyncio as redis
except ModuleNotFoundError:
    redis = None

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8001")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
INTAKE_STREAM = os.getenv("INTAKE_STREAM", "missions.intake")
INTAKE_TOPIC = os.getenv("INTAKE_TOPIC", "intake.feature_contract.created")
MAX_STREAM_LEN = int(os.getenv("MAX_STREAM_LEN", "20000"))
CORS_ALLOW_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3100")
INTERNAL_SERVICE_API_KEY = os.getenv("INTERNAL_SERVICE_API_KEY", "worker-key")
IDEMPOTENCY_TTL_SECONDS = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "86400"))
IDEMPOTENCY_KEY_PREFIX = "idempotency:missions"
API_RATE_LIMIT_PER_MINUTE = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "120"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_KEY_PREFIX = "ratelimit:api-gateway"
PAYLOAD_REF_PATTERN = re.compile(r"^registry://")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "offline").strip().lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.3-codex")
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20"))
OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "medium").strip().lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1").rstrip("/")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()
ANTHROPIC_TIMEOUT_SECONDS = float(os.getenv("ANTHROPIC_TIMEOUT_SECONDS", "20"))
ANTHROPIC_VERSION = os.getenv("ANTHROPIC_VERSION", "2023-06-01").strip()
ANTHROPIC_THINKING_MODE = os.getenv("ANTHROPIC_THINKING_MODE", "enabled").strip().lower()
ANTHROPIC_THINKING_BUDGET_TOKENS = int(os.getenv("ANTHROPIC_THINKING_BUDGET_TOKENS", "8192"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
).rstrip("/")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip()
GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "20"))
GEMINI_THINKING_BUDGET = int(os.getenv("GEMINI_THINKING_BUDGET", "-1"))
GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "medium").strip().lower()

REQUEST_COUNTER = Counter(
    "api_gateway_http_requests_total",
    "Total HTTP requests served by api-gateway",
    ("method", "path", "status_code"),
)
REQUEST_LATENCY = Histogram(
    "api_gateway_http_request_duration_seconds",
    "HTTP request latency in seconds for api-gateway",
    ("method", "path"),
)
LOGGER = logging.getLogger(__name__)

if Path("/app/schemas").exists() and Path("/app/protocol").exists():
    REPO_ROOT = Path("/app")
else:
    REPO_ROOT = Path(__file__).resolve().parents[3]
EVENT_SCHEMA_PATH = Path(
    os.getenv("EVENT_SCHEMA_PATH", str(REPO_ROOT / "schemas/event.envelope.schema.json"))
)
TOPICS_PATH = Path(os.getenv("TOPICS_PATH", str(REPO_ROOT / "protocol/topics.yaml")))


class ProtocolValidationError(Exception):
    pass


class MissionCreate(BaseModel):
    prompt: str = Field(min_length=3)
    requested_target_language: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MissionRecord(BaseModel):
    mission_id: str
    prompt: str
    requested_target_language: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
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
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def _load_event_schema() -> dict[str, Any]:
    if not EVENT_SCHEMA_PATH.exists():
        raise ProtocolValidationError(f"event schema not found: {EVENT_SCHEMA_PATH}")
    return json.loads(EVENT_SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_topics() -> set[str]:
    if not TOPICS_PATH.exists():
        raise ProtocolValidationError(f"topics file not found: {TOPICS_PATH}")
    topics: set[str] = set()
    for raw_line in TOPICS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("- "):
            topics.add(line[2:].strip())
    if not topics:
        raise ProtocolValidationError("no topics configured")
    return topics


def _validate_envelope(envelope: dict[str, Any]) -> None:
    schema = _load_event_schema()
    topics = _load_topics()
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    missing = [field for field in required if field not in envelope]
    if missing:
        raise ProtocolValidationError(f"envelope missing required fields: {', '.join(missing)}")

    if schema.get("additionalProperties") is False:
        unknown = [field for field in envelope if field not in properties]
        if unknown:
            raise ProtocolValidationError(f"unexpected envelope fields: {', '.join(unknown)}")

    if envelope["topic"] not in topics:
        raise ProtocolValidationError(f"topic '{envelope['topic']}' is not in protocol catalog")
    if not PAYLOAD_REF_PATTERN.match(str(envelope["payload_ref"])):
        raise ProtocolValidationError("payload_ref must start with registry://")
    if envelope.get("priority") not in {"NORMAL", "HIGH"}:
        raise ProtocolValidationError("priority must be NORMAL or HIGH")
    try:
        _parse_date_time(str(envelope["timestamp"]))
    except Exception as exc:
        raise ProtocolValidationError(f"invalid timestamp: {exc}") from exc

    for field, spec in properties.items():
        expected_type = spec.get("type")
        if field in envelope and expected_type == "string" and not isinstance(envelope[field], str):
            raise ProtocolValidationError(f"field '{field}' must be string")


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


async def _dependency_status() -> dict[str, bool]:
    redis_client = getattr(app.state, "redis", None)
    orchestrator_healthy = False
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            response = await client.get(f"{ORCHESTRATOR_URL}/health")
            orchestrator_healthy = response.status_code == 200
    except Exception:
        orchestrator_healthy = False

    redis_healthy = False
    if redis_client is not None:
        try:
            redis_healthy = bool(await redis_client.ping())
            app.state.redis_ready = redis_healthy
        except Exception:
            redis_healthy = False
            app.state.redis_ready = False

    return {"orchestrator_healthy": orchestrator_healthy, "redis_healthy": redis_healthy}


def _client_identifier(request: Request) -> str:
    api_key = request.headers.get("x-api-key")
    if api_key:
        return f"api-key:{hashlib.sha256(api_key.encode('utf-8')).hexdigest()}"

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
    return normalized.startswith("gemini-3-") or normalized.startswith("gemini-3.1-")


def _to_gemini_thinking_level(reasoning_effort: str | None) -> str:
    effort = (reasoning_effort or "").strip().lower()
    if effort in {"none", "minimal", "low"}:
        return "low"
    if effort in {"high", "xhigh"}:
        return "high"
    return "medium"


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
    except Exception as exc:
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
    except Exception as exc:
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = None
    app.state.redis_ready = False

    if redis is not None:
        app.state.redis = redis.from_url(REDIS_URL, decode_responses=True)
        try:
            await app.state.redis.ping()
            app.state.redis_ready = True
        except Exception:
            app.state.redis_ready = False

    yield

    if app.state.redis is not None:
        aclose = getattr(app.state.redis, "aclose", None)
        if callable(aclose):
            await aclose()
        else:
            await app.state.redis.close()


app = FastAPI(title="HolyGrail API Gateway", version="0.3.0", lifespan=lifespan)
configure_tracing(app, service_name="api-gateway")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in CORS_ALLOW_ORIGINS.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _request_metrics(request, call_next):
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


@app.middleware("http")
async def _security_and_rate_limit(request: Request, call_next):
    response: Response
    rate_limit_headers: dict[str, str] = {}
    path = request.url.path
    is_probe = path in {"/health", "/readyz", "/metrics"}

    if API_RATE_LIMIT_PER_MINUTE > 0 and not is_probe:
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
                        },
                    )
                rate_limit_headers = {
                    "X-RateLimit-Limit": str(API_RATE_LIMIT_PER_MINUTE),
                    "X-RateLimit-Remaining": str(remaining),
                }
            except Exception:
                LOGGER.warning("rate limiter unavailable for request path %s", path)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cache-Control"] = "no-store"
    trace_id = current_trace_id()
    if trace_id:
        response.headers["X-Trace-Id"] = trace_id
    for key, value in rate_limit_headers.items():
        response.headers[key] = value
    return response


@app.get("/health")
async def health() -> dict[str, Any]:
    dependency_status = await _dependency_status()

    return {
        "ok": True,
        "service": "api-gateway",
        "orchestrator_url": ORCHESTRATOR_URL,
        "orchestrator_healthy": dependency_status["orchestrator_healthy"],
        "redis_url": REDIS_URL,
        "redis_healthy": dependency_status["redis_healthy"],
        "intake_stream": INTAKE_STREAM,
        "intake_topic": INTAKE_TOPIC,
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


@app.post("/v1/missions")
async def create_mission(
    payload: MissionCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> MissionRecord:
    redis_client = getattr(app.state, "redis", None)
    if redis_client is None:
        raise HTTPException(status_code=503, detail="redis dependency is not installed")
    try:
        ready = bool(await redis_client.ping())
        app.state.redis_ready = ready
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"redis unavailable: {exc}") from exc

    idempotency_redis_key: str | None = None
    request_hash: str | None = None
    if idempotency_key is not None:
        trimmed_key = idempotency_key.strip()
        if not trimmed_key:
            raise HTTPException(status_code=400, detail="Idempotency-Key must not be empty")
        if len(trimmed_key) > 256:
            raise HTTPException(status_code=400, detail="Idempotency-Key must be <= 256 characters")

        request_hash = _request_hash(payload)
        idempotency_redis_key = _idempotency_redis_key(trimmed_key)
        in_progress_record = {"status": "processing", "request_hash": request_hash}
        acquired = await _save_idempotency_record(
            redis_client,
            idempotency_redis_key,
            in_progress_record,
            nx=True,
        )
        if not acquired:
            existing = await _load_idempotency_record(redis_client, idempotency_redis_key)
            if existing is None:
                acquired = await _save_idempotency_record(
                    redis_client,
                    idempotency_redis_key,
                    in_progress_record,
                    nx=True,
                )
                if not acquired:
                    raise HTTPException(
                        status_code=409,
                        detail="request with this Idempotency-Key is in progress",
                    )
            else:
                if existing.get("request_hash") != request_hash:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Idempotency-Key reuse detected with a different mission payload; "
                            "use a new key"
                        ),
                    )
                if existing.get("status") == "completed" and isinstance(
                    existing.get("mission"), dict
                ):
                    return MissionRecord(**existing["mission"])
                raise HTTPException(
                    status_code=409,
                    detail="request with this Idempotency-Key is in progress",
                )

    mission_id = f"mission-{uuid.uuid4()}"
    created_at = datetime.now(UTC).isoformat()
    mission_payload = {
        "mission_id": mission_id,
        "prompt": payload.prompt,
        "requested_target_language": payload.requested_target_language,
        "metadata": payload.metadata,
        "created_at": created_at,
        "state": "INTAKE",
    }
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
        if idempotency_redis_key is not None:
            await redis_client.delete(idempotency_redis_key)
        raise HTTPException(status_code=422, detail=f"invalid protocol envelope: {exc}") from exc
    except Exception as exc:
        if idempotency_redis_key is not None:
            await redis_client.delete(idempotency_redis_key)
        raise HTTPException(status_code=502, detail=f"failed to enqueue mission: {exc}") from exc

    if idempotency_redis_key is not None and request_hash is not None:
        try:
            await _save_idempotency_record(
                redis_client,
                idempotency_redis_key,
                {
                    "status": "completed",
                    "request_hash": request_hash,
                    "mission": mission_payload,
                },
            )
        except Exception as exc:
            LOGGER.warning(
                "mission %s queued but failed to persist idempotency completion: %s",
                mission_id,
                exc,
            )

    return MissionRecord(**mission_payload)


async def _proxy_get(path: str, *, params: dict[str, Any] | None = None) -> Any:
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(f"{ORCHESTRATOR_URL}{path}", params=params)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"orchestrator unavailable: {exc}") from exc
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="resource not found")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="orchestrator query failed")
    return response.json()


async def _proxy_get_internal(path: str, *, params: dict[str, Any] | None = None) -> Any:
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(
                f"{ORCHESTRATOR_URL}{path}",
                params=params,
                headers={"x-api-key": INTERNAL_SERVICE_API_KEY},
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"orchestrator unavailable: {exc}") from exc
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="resource not found")
    if response.status_code in {401, 403}:
        raise HTTPException(status_code=502, detail="orchestrator internal auth rejected request")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="orchestrator internal query failed")
    return response.json()


@app.get("/v1/missions/{mission_id}")
async def get_mission(mission_id: str) -> dict[str, Any]:
    return await _proxy_get(f"/missions/{mission_id}")


@app.get("/v1/missions")
async def list_missions(limit: int = Query(default=20, ge=1, le=200)) -> list[dict[str, Any]]:
    return await _proxy_get("/missions", params={"limit": limit})


@app.get("/v1/missions/{mission_id}/events")
async def get_mission_events(
    mission_id: str, limit: int = Query(default=50, ge=1, le=500)
) -> list[dict[str, Any]]:
    return await _proxy_get(f"/missions/{mission_id}/events", params={"limit": limit})


@app.get("/v1/missions/{mission_id}/pod-assignment")
async def get_mission_pod_assignment(mission_id: str) -> dict[str, Any]:
    return await _proxy_get_internal(f"/internal/missions/{mission_id}/pod-assignment")


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


@app.get("/v1/missions/{mission_id}/audit-reports")
async def get_mission_audit_reports(
    mission_id: str, limit: int = Query(default=50, ge=1, le=500)
) -> list[dict[str, Any]]:
    return await _proxy_get_internal(
        f"/internal/missions/{mission_id}/audit-reports", params={"limit": limit}
    )


@app.get("/v1/operations/summary")
async def get_operations_summary() -> dict[str, Any]:
    return await _proxy_get_internal("/internal/operations/summary")


@app.get("/v1/operations/agents")
async def get_operations_agents(
    mission_limit: int = Query(default=1000, ge=50, le=5000),
    assignment_limit: int = Query(default=1000, ge=50, le=5000),
    event_limit: int = Query(default=300, ge=50, le=2000),
) -> dict[str, Any]:
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
) -> list[dict[str, Any]]:
    return await _proxy_get_internal("/internal/operations/events", params={"limit": limit})


@app.get("/v1/operations/agent-events")
async def get_operations_agent_events(
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[dict[str, Any]]:
    return await _proxy_get_internal("/internal/operations/agent-events", params={"limit": limit})


@app.get("/v1/operations/agent-integrations")
async def get_operations_agent_integrations() -> dict[str, Any]:
    return await _proxy_get_internal("/internal/operations/agent-integrations")


@app.get("/v1/operations/logicnodes")
async def get_operations_logicnodes(
    limit: int = Query(default=200, ge=1, le=1000),
    mission_id: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": limit}
    if mission_id:
        params["mission_id"] = mission_id
    return await _proxy_get_internal("/internal/operations/logicnodes", params=params)


@app.get("/v1/operations/pod-assignments")
async def get_operations_pod_assignments(
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[dict[str, Any]]:
    return await _proxy_get_internal(
        "/internal/operations/pod-assignments",
        params={"limit": limit},
    )


@app.get("/v1/operations/projects")
async def get_operations_projects(
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    return await _proxy_get_internal("/internal/operations/projects", params={"limit": limit})


@app.get("/v1/operations/alerts")
async def get_operations_alerts(
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    return await _proxy_get_internal("/internal/operations/alerts", params={"limit": limit})


@app.post("/v1/builder/preview")
async def create_builder_preview(payload: BuilderPreviewRequest) -> dict[str, Any]:
    normalized_request = _normalize_builder_text(payload.request)
    if len(normalized_request) < 3:
        raise HTTPException(status_code=400, detail="request must be at least 3 characters")

    provider = (payload.provider or LLM_PROVIDER).strip().lower()
    selected_model = None
    if isinstance(payload.model, str):
        candidate_model = payload.model.strip()
        if candidate_model:
            selected_model = candidate_model

    normalized_payload = BuilderPreviewRequest(
        request=normalized_request,
        constraints=payload.constraints,
        view_mode=payload.view_mode,
        provider=provider,
        model=selected_model,
        reasoning_effort=payload.reasoning_effort,
        thinking_budget=payload.thinking_budget,
    )

    if provider == "openai":
        if not OPENAI_API_KEY:
            return _build_offline_builder_preview(
                normalized_payload,
                source="offline",
                notice="OPENAI_API_KEY not configured. Returned deterministic preview.",
            )

        generated = await _openai_builder_preview(
            normalized_payload,
            model=selected_model or OPENAI_MODEL,
            reasoning_effort=payload.reasoning_effort or OPENAI_REASONING_EFFORT,
        )
        if generated is not None:
            return generated

        return _build_offline_builder_preview(
            normalized_payload,
            source="openai-fallback",
            notice="Live LLM request failed. Returned deterministic preview.",
        )

    if provider == "anthropic":
        if not ANTHROPIC_API_KEY:
            return _build_offline_builder_preview(
                normalized_payload,
                source="offline",
                notice="ANTHROPIC_API_KEY not configured. Returned deterministic preview.",
            )

        generated = await _anthropic_builder_preview(
            normalized_payload,
            model=selected_model or ANTHROPIC_MODEL,
            thinking_mode=ANTHROPIC_THINKING_MODE,
            thinking_budget=payload.thinking_budget
            if payload.thinking_budget is not None
            else ANTHROPIC_THINKING_BUDGET_TOKENS,
        )
        if generated is not None:
            return generated

        return _build_offline_builder_preview(
            normalized_payload,
            source="anthropic-fallback",
            notice="Live LLM request failed. Returned deterministic preview.",
        )

    if provider == "gemini":
        if not GEMINI_API_KEY:
            return _build_offline_builder_preview(
                normalized_payload,
                source="offline",
                notice="GEMINI_API_KEY not configured. Returned deterministic preview.",
            )

        generated = await _gemini_builder_preview(
            normalized_payload,
            model=selected_model or GEMINI_MODEL,
            thinking_budget=payload.thinking_budget
            if payload.thinking_budget is not None
            else GEMINI_THINKING_BUDGET,
            thinking_level=payload.reasoning_effort or GEMINI_THINKING_LEVEL,
        )
        if generated is not None:
            return generated

        return _build_offline_builder_preview(
            normalized_payload,
            source="gemini-fallback",
            notice="Live LLM request failed. Returned deterministic preview.",
        )

    return _build_offline_builder_preview(normalized_payload, source="offline")


@app.post("/v1/missions/{mission_id}/state")
async def update_mission_state(
    mission_id: str,
    payload: MissionStateUpdate,
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="x-api-key header is required")

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/missions/{mission_id}/state",
                json=payload.model_dump(),
                headers={"x-api-key": x_api_key},
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"orchestrator unavailable: {exc}") from exc

    if response.status_code in {401, 403}:
        raise HTTPException(status_code=response.status_code, detail=response.json().get("detail"))
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="mission not found")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="orchestrator mutation failed")
    return response.json()


@app.get("/")
def index() -> dict[str, str]:
    return {"name": "HolyGrail API Gateway", "status": "ready"}
