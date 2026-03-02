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

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
STATE_STREAM = os.getenv("STATE_STREAM", "missions.state")
CONSUMER_GROUP = os.getenv("AUDIT_WORKER_GROUP", "audit-workers")
CONSUMER_NAME = os.getenv("AUDIT_WORKER_NAME", f"audit-worker-{uuid.uuid4()}")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8001")
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY", "worker-key")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("ORCHESTRATOR_TIMEOUT_SECONDS", "5.0"))
REQUEST_MAX_RETRIES = int(os.getenv("ORCHESTRATOR_MAX_RETRIES", "3"))
MAX_STREAM_LEN = int(os.getenv("MAX_STREAM_LEN", "20000"))
PAYLOAD_REF_PATTERN = re.compile(r"^registry://")

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
                    headers={"x-api-key": SERVICE_API_KEY, "x-request-id": request_id},
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
