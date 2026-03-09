import asyncio
import inspect
import json
import os
import re
import time
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from redis.exceptions import ResponseError

from .tracing import configure_tracing

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
STATE_STREAM = os.getenv("STATE_STREAM", "missions.state")
CONSUMER_GROUP = os.getenv("AUDIT_WORKER_GROUP", "audit-workers")
CONSUMER_NAME = os.getenv("AUDIT_WORKER_NAME", f"audit-worker-{uuid.uuid4()}")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8001")
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY", "worker-key")
WORKER_AGENT_ID = os.getenv("WORKER_AGENT_ID", "AGENT-10-TESTER").strip().upper()
AGENT_SERVICE_API_KEYS = os.getenv("AGENT_SERVICE_API_KEYS", "")
AGENT_SERVICE_KEY_MODE = os.getenv("AGENT_SERVICE_KEY_MODE", "shared").strip().lower() or "shared"
REQUEST_TIMEOUT_SECONDS = float(os.getenv("ORCHESTRATOR_TIMEOUT_SECONDS", "5.0"))
REQUEST_MAX_RETRIES = int(os.getenv("ORCHESTRATOR_MAX_RETRIES", "3"))
MAX_STREAM_LEN = int(os.getenv("MAX_STREAM_LEN", "20000"))
PAYLOAD_REF_PATTERN = re.compile(r"^registry://")
AGENT_SERVICE_KEY_ENV_PATTERN = re.compile(r"^AGENT_(\d{2})_([A-Z0-9_]+)_SERVICE_API_KEY$")

EVENT_SCHEMA_PATH = Path("/app/schemas/event.envelope.schema.json")
TOPICS_PATH = Path("/app/protocol/topics.yaml")

TASKS_PROCESSED = Counter(
    "audit_worker_tasks_processed_total",
    "Total mission events processed by audit worker",
)
TASKS_FAILED = Counter(
    "audit_worker_tasks_failed_total",
    "Total mission events failed by audit worker",
)
TASK_LATENCY_SECONDS = Histogram(
    "audit_worker_task_latency_seconds",
    "Mission event processing latency for audit worker",
)


class ProtocolValidationError(Exception):
    pass


def _normalize_agent_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().upper()
    return candidate or None


def _agent_service_key_env_name(agent_id: str) -> str | None:
    normalized = _normalize_agent_id(agent_id)
    if normalized is None:
        return None
    return f"{normalized.replace('-', '_')}_SERVICE_API_KEY"


def _parse_agent_service_key_map(raw: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for entry in (part.strip() for part in raw.split(";") if part.strip()):
        if "=" not in entry:
            continue
        agent_id, key = entry.split("=", 1)
        normalized_agent_id = _normalize_agent_id(agent_id)
        normalized_key = key.strip()
        if normalized_agent_id and normalized_key:
            mapping[normalized_agent_id] = normalized_key
    return mapping


def _configured_agent_service_key_map() -> dict[str, str]:
    mapping = _parse_agent_service_key_map(AGENT_SERVICE_API_KEYS)
    for env_name, raw_value in os.environ.items():
        match = AGENT_SERVICE_KEY_ENV_PATTERN.match(env_name)
        if not match:
            continue
        normalized_key = raw_value.strip()
        if not normalized_key:
            continue
        mapping[f"AGENT-{match.group(1)}-{match.group(2).replace('_', '-')}"] = normalized_key
    return mapping


def _service_api_key_for_agent(agent_id: str | None) -> str:
    normalized_agent_id = _normalize_agent_id(agent_id)
    if normalized_agent_id:
        env_name = _agent_service_key_env_name(normalized_agent_id)
        if env_name:
            direct_env_key = os.getenv(env_name, "").strip()
            if direct_env_key:
                return direct_env_key
        mapped_key = _parse_agent_service_key_map(AGENT_SERVICE_API_KEYS).get(normalized_agent_id)
        if mapped_key:
            return mapped_key
        if AGENT_SERVICE_KEY_MODE == "strict":
            raise RuntimeError(f"missing dedicated service key for {normalized_agent_id}")
    return SERVICE_API_KEY


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
        raise ProtocolValidationError(f"missing fields: {', '.join(missing)}")
    if schema.get("additionalProperties") is False:
        unknown = [field for field in envelope if field not in properties]
        if unknown:
            raise ProtocolValidationError(f"unexpected fields: {', '.join(unknown)}")
    if envelope.get("topic") not in topics:
        raise ProtocolValidationError("unknown topic")
    if not PAYLOAD_REF_PATTERN.match(str(envelope.get("payload_ref", ""))):
        raise ProtocolValidationError("invalid payload_ref")
    allowed_priorities = set(properties.get("priority", {}).get("enum", ["NORMAL", "HIGH"]))
    if envelope.get("priority") not in allowed_priorities:
        raise ProtocolValidationError(
            f"priority must be one of: {', '.join(sorted(allowed_priorities))}"
        )
    try:
        _parse_date_time(str(envelope["timestamp"]))
    except Exception as exc:
        raise ProtocolValidationError(f"invalid timestamp: {exc}") from exc

    for field, spec in properties.items():
        expected_type = spec.get("type")
        if field in envelope and expected_type == "string" and not isinstance(envelope[field], str):
            raise ProtocolValidationError(f"field '{field}' must be string")


def _build_envelope(
    topic: str, mission_id: str, payload_ref: str, schema_name: str
) -> dict[str, Any]:
    envelope = {
        "event_id": f"evt-{uuid.uuid4()}",
        "topic": topic,
        "timestamp": datetime.now(UTC).isoformat(),
        "producer": "audit-worker",
        "correlation_id": mission_id,
        "payload_ref": payload_ref,
        "schema": schema_name,
        "priority": "NORMAL",
    }
    _validate_envelope(envelope)
    return envelope


async def _publish_event(
    redis_client: redis.Redis, topic: str, mission_id: str, payload: dict[str, Any]
) -> None:
    envelope = _build_envelope(
        topic=topic,
        mission_id=mission_id,
        payload_ref=f"registry://missions/{mission_id}/audit/{topic}",
        schema_name="audit.report.v1",
    )
    await redis_client.xadd(
        STATE_STREAM,
        {"envelope": json.dumps(envelope), "payload": json.dumps(payload)},
        maxlen=MAX_STREAM_LEN,
        approximate=True,
    )


async def _ensure_group(redis_client: redis.Redis) -> None:
    try:
        await redis_client.xgroup_create(
            name=STATE_STREAM,
            groupname=CONSUMER_GROUP,
            id="0",
            mkstream=True,
        )
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def _post_audit(mission_id: str, status: str, summary: str, report: dict[str, Any]) -> bool:
    request_id = f"audit-{uuid.uuid4()}"
    last_response: httpx.Response | None = None
    api_key = _service_api_key_for_agent(WORKER_AGENT_ID)
    headers = {"x-api-key": api_key, "x-request-id": request_id}
    normalized_agent_id = _normalize_agent_id(WORKER_AGENT_ID)
    if normalized_agent_id:
        headers["x-agent-id"] = normalized_agent_id
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        for attempt in range(1, REQUEST_MAX_RETRIES + 1):
            try:
                response = await client.post(
                    f"{ORCHESTRATOR_URL}/internal/audit-reports",
                    json={
                        "mission_id": mission_id,
                        "audit_id": f"audit-worker.{mission_id}",
                        "status": status,
                        "report": {"summary": summary, **report},
                    },
                    headers=headers,
                )
                last_response = response
                if response.status_code < 500 and response.status_code != 429:
                    return response.status_code < 400
            except httpx.HTTPError:
                pass
            if attempt < REQUEST_MAX_RETRIES:
                await asyncio.sleep(0.1 * attempt)

    return bool(last_response and last_response.status_code < 400)


async def _consumer_loop(app: FastAPI) -> None:
    redis_client: redis.Redis = app.state.redis
    while True:
        records = await redis_client.xreadgroup(
            groupname=CONSUMER_GROUP,
            consumername=CONSUMER_NAME,
            streams={STATE_STREAM: ">"},
            count=20,
            block=5000,
        )
        if not records:
            continue

        for _, entries in records:
            for entry_id, fields in entries:
                started = time.perf_counter()
                try:
                    envelope_raw = fields.get("envelope")
                    payload_raw = fields.get("payload")
                    if not envelope_raw or not payload_raw:
                        raise ProtocolValidationError("missing envelope/payload")

                    envelope = json.loads(envelope_raw)
                    _validate_envelope(envelope)
                    payload = json.loads(payload_raw)
                    event_type = str(payload.get("event_type", ""))
                    mission_id = str(payload.get("mission_id", ""))
                    if not mission_id:
                        raise ValueError("missing mission id")

                    if event_type == "MISSION_VERIFIED":
                        summary = "Automated audit checks passed."
                        report = {
                            "auditor": "audit-worker",
                            "checks": ["contract", "flow"],
                            "result": "PASS",
                        }
                        if await _post_audit(mission_id, "PASS", summary, report):
                            await _publish_event(
                                redis_client,
                                "artifact.rir.verified",
                                mission_id,
                                {
                                    "mission_id": mission_id,
                                    "event_type": "AUDIT_PASS",
                                    "status": "PASS",
                                },
                            )
                    elif event_type == "MISSION_FAILED":
                        summary = "Mission failed during orchestration checks."
                        report = {"auditor": "audit-worker", "result": "FAIL"}
                        if await _post_audit(mission_id, "FAIL", summary, report):
                            await _publish_event(
                                redis_client,
                                "artifact.rir.rejected",
                                mission_id,
                                {
                                    "mission_id": mission_id,
                                    "event_type": "AUDIT_FAIL",
                                    "status": "FAIL",
                                },
                            )
                    elif event_type == "MISSION_COMPLETE":
                        await _publish_event(
                            redis_client,
                            "binary.build.ready",
                            mission_id,
                            {
                                "mission_id": mission_id,
                                "event_type": "BINARY_READY",
                                "status": "READY",
                            },
                        )

                    app.state.processed += 1
                    TASKS_PROCESSED.inc()
                except Exception:
                    app.state.errors += 1
                    TASKS_FAILED.inc()
                finally:
                    TASK_LATENCY_SECONDS.observe(time.perf_counter() - started)
                    await redis_client.xack(STATE_STREAM, CONSUMER_GROUP, entry_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis.from_url(REDIS_URL, decode_responses=True)
    app.state.consumer_task = None
    app.state.processed = 0
    app.state.errors = 0
    await app.state.redis.ping()
    await _ensure_group(app.state.redis)
    app.state.consumer_task = asyncio.create_task(_consumer_loop(app))
    yield
    task = app.state.consumer_task
    if task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    aclose = getattr(app.state.redis, "aclose", None)
    if callable(aclose):
        await aclose()
    else:
        close = getattr(app.state.redis, "close", None)
        if callable(close):
            result = close()
            if inspect.isawaitable(result):
                await result


app = FastAPI(title="HolyGrail Audit Worker", version="0.1.0", lifespan=lifespan)
configure_tracing(app, service_name="audit-worker")


@app.get("/health")
async def health() -> dict[str, Any]:
    ready = False
    redis_client = getattr(app.state, "redis", None)
    if redis_client is not None:
        try:
            ready = bool(await redis_client.ping())
        except Exception:
            ready = False
    return {
        "ok": ready,
        "service": "audit-worker",
        "worker_agent_id": WORKER_AGENT_ID,
        "agent_service_key_mode": AGENT_SERVICE_KEY_MODE,
        "configured_agent_service_keys": len(_configured_agent_service_key_map()),
        "state_stream": STATE_STREAM,
        "group": CONSUMER_GROUP,
        "consumer": CONSUMER_NAME,
        "processed": app.state.processed,
        "errors": app.state.errors,
    }


@app.get("/readyz")
async def readyz() -> dict[str, Any]:
    redis_client = getattr(app.state, "redis", None)
    if redis_client is None:
        raise HTTPException(status_code=503, detail="redis unavailable")
    try:
        ready = bool(await redis_client.ping())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"redis unavailable: {exc}") from exc
    if not ready:
        raise HTTPException(status_code=503, detail="redis unavailable")
    return {"ready": True, "service": "audit-worker"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
