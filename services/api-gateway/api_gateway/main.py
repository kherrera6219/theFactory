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
IDEMPOTENCY_TTL_SECONDS = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "86400"))
IDEMPOTENCY_KEY_PREFIX = "idempotency:missions"
API_RATE_LIMIT_PER_MINUTE = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "120"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_KEY_PREFIX = "ratelimit:api-gateway"
PAYLOAD_REF_PATTERN = re.compile(r"^registry://")

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
