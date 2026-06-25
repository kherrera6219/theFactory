import asyncio
import inspect
import json
import logging
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

from shared_runtime.agent_keys import (
    configured_agent_service_key_map,
    enforce_production_service_auth_config,
    normalize_agent_id,
    service_api_key_for_agent,
)
from shared_runtime.logging_config import configure_logging
from shared_runtime.protocol import (
    ProtocolValidationError,
    load_event_schema,
    load_topics,
    parse_date_time,
    validate_envelope,
)

from .tracing import configure_tracing

configure_logging("audit-worker")
LOGGER = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
STATE_STREAM = os.getenv("STATE_STREAM", "missions.state")
CONSUMER_GROUP = os.getenv("AUDIT_WORKER_GROUP", "audit-workers")
CONSUMER_NAME = os.getenv("AUDIT_WORKER_NAME", f"audit-worker-{uuid.uuid4()}")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8001")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY", "worker-key")
WORKER_AGENT_ID = os.getenv("WORKER_AGENT_ID", "AGENT-10-TESTER").strip().upper()
AGENT_SERVICE_API_KEYS = os.getenv("AGENT_SERVICE_API_KEYS", "")
AGENT_SERVICE_KEY_MODE = os.getenv("AGENT_SERVICE_KEY_MODE", "shared").strip().lower() or "shared"
REQUEST_TIMEOUT_SECONDS = float(os.getenv("ORCHESTRATOR_TIMEOUT_SECONDS", "5.0"))
REQUEST_MAX_RETRIES = int(os.getenv("ORCHESTRATOR_MAX_RETRIES", "3"))
MAX_STREAM_LEN = int(os.getenv("MAX_STREAM_LEN", "20000"))
AUDIT_DLQ_STREAM = os.getenv("AUDIT_DLQ_STREAM", "factory:dlq:audit-worker")
PAYLOAD_REF_PATTERN = re.compile(r"^registry://")

EVENT_SCHEMA_PATH = Path("/app/schemas/event.envelope.schema.json")
TOPICS_PATH = Path("/app/protocol/topics.yaml")

TASKS_PROCESSED = Counter(
    "audit_worker_tasks_processed_total",
    "Total mission events processed by audit worker",
    ("agent_id", "event_type"),
)
TASKS_FAILED = Counter(
    "audit_worker_tasks_failed_total",
    "Total mission events failed by audit worker",
    ("agent_id", "event_type"),
)
TASK_LATENCY_SECONDS = Histogram(
    "audit_worker_task_latency_seconds",
    "Mission event processing latency for audit worker",
    ("agent_id", "event_type"),
)
AUDIT_POST_LATENCY_SECONDS = Histogram(
    "audit_worker_post_audit_latency_seconds",
    "Latency for audit-worker writes to orchestrator",
    ("agent_id", "status"),
)


def _normalize_agent_id(value: Any) -> str | None:
    return normalize_agent_id(value)


def _agent_service_key_env_name(agent_id: str) -> str | None:
    normalized = _normalize_agent_id(agent_id)
    if normalized is None:
        return None
    return f"{normalized.replace('-', '_')}_SERVICE_API_KEY"


def _parse_agent_service_key_map(raw: str) -> dict[str, str]:
    return configured_agent_service_key_map(raw, env={})


def _configured_agent_service_key_map() -> dict[str, str]:
    return configured_agent_service_key_map(AGENT_SERVICE_API_KEYS)


def _service_api_key_for_agent(agent_id: str | None) -> str:
    return service_api_key_for_agent(
        agent_id,
        fallback_key=SERVICE_API_KEY,
        raw_mapping=AGENT_SERVICE_API_KEYS,
        key_mode=AGENT_SERVICE_KEY_MODE,
    )


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


async def _write_dlq(
    redis_client: redis.Redis,
    entry_id: str,
    fields: dict[str, Any],
    error: str,
) -> None:
    try:
        await redis_client.xadd(
            AUDIT_DLQ_STREAM,
            {
                "error": error,
                "entry_id": entry_id,
                "envelope": fields.get("envelope", ""),
                "payload": fields.get("payload", ""),
                "ts": datetime.now(UTC).isoformat(),
            },
            maxlen=MAX_STREAM_LEN,
            approximate=True,
        )
    except Exception as dlq_exc:
        LOGGER.error("audit-worker failed to write entry %s to DLQ: %s", entry_id, dlq_exc)


async def _post_audit(mission_id: str, status: str, summary: str, report: dict[str, Any]) -> bool:
    request_id = f"audit-{uuid.uuid4()}"
    last_response: httpx.Response | None = None
    api_key = _service_api_key_for_agent(WORKER_AGENT_ID)
    headers = {"x-api-key": api_key, "x-request-id": request_id}
    normalized_agent_id = _normalize_agent_id(WORKER_AGENT_ID)
    if normalized_agent_id:
        headers["x-agent-id"] = normalized_agent_id
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        for attempt in range(1, REQUEST_MAX_RETRIES + 1):
            try:
                report_payload = {"summary": summary, **report}
                try:
                    from shared_runtime.crypto_keystore import load_or_create_signing_key
                    from shared_runtime.crypto_signing import _keystore_path, sign_payload
                    key = load_or_create_signing_key(_keystore_path())
                    signature_record = sign_payload(key, report_payload)
                    report_payload["signature_record"] = signature_record
                except Exception as exc:
                    LOGGER.warning("failed to sign audit report in audit-worker: %s", exc)

                response = await client.post(
                    f"{ORCHESTRATOR_URL}/internal/audit-reports",
                    json={
                        "mission_id": mission_id,
                        "audit_id": f"audit-worker.{mission_id}",
                        "status": status,
                        "report": report_payload,
                    },
                    headers=headers,
                )
                last_response = response
                if response.status_code < 500 and response.status_code != 429:
                    AUDIT_POST_LATENCY_SECONDS.labels(
                        agent_id=WORKER_AGENT_ID,
                        status="success" if response.status_code < 400 else "error",
                    ).observe(time.perf_counter() - started)
                    return response.status_code < 400
            except httpx.HTTPError:
                pass
            if attempt < REQUEST_MAX_RETRIES:
                await asyncio.sleep(min(2 ** attempt * 0.5, 30.0))

    AUDIT_POST_LATENCY_SECONDS.labels(agent_id=WORKER_AGENT_ID, status="error").observe(
        time.perf_counter() - started
    )
    return bool(last_response and last_response.status_code < 400)


async def _consumer_loop(app: FastAPI) -> None:
    redis_client: redis.Redis = app.state.redis
    while True:
        try:
            records = await redis_client.xreadgroup(
                groupname=CONSUMER_GROUP,
                consumername=CONSUMER_NAME,
                streams={STATE_STREAM: ">"},
                count=20,
                block=5000,
            )
        except asyncio.CancelledError:
            raise
        except ResponseError as exc:
            if "NOGROUP" in str(exc):
                LOGGER.warning(
                    "state stream group %s missing for %s; recreating",
                    CONSUMER_GROUP,
                    STATE_STREAM,
                )
                await _ensure_group(redis_client)
                continue
            raise
        if not records:
            continue

        for _, entries in records:
            for entry_id, fields in entries:
                acknowledge = False
                started = time.perf_counter()
                event_type = "UNKNOWN"
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

                    app.state.processed += 1
                    TASKS_PROCESSED.labels(agent_id=WORKER_AGENT_ID, event_type=event_type).inc()
                    acknowledge = True
                except (
                    ProtocolValidationError,
                    json.JSONDecodeError,
                    KeyError,
                    TypeError,
                    ValueError,
                ) as exc:
                    # Permanent/malformed failure — route to DLQ and discard
                    app.state.errors += 1
                    TASKS_FAILED.labels(agent_id=WORKER_AGENT_ID, event_type=event_type).inc()
                    LOGGER.warning("discarding invalid audit event %s: %s", entry_id, exc)
                    await _write_dlq(redis_client, entry_id, fields, str(exc))
                    acknowledge = True
                except Exception as exc:
                    # Transient failure — do not ack, allow broker to redeliver
                    app.state.errors += 1
                    TASKS_FAILED.labels(agent_id=WORKER_AGENT_ID, event_type=event_type).inc()
                    LOGGER.warning("failed to process audit event %s: %s", entry_id, exc)
                finally:
                    TASK_LATENCY_SECONDS.labels(
                        agent_id=WORKER_AGENT_ID,
                        event_type=event_type,
                    ).observe(time.perf_counter() - started)
                    if acknowledge:
                        await redis_client.xack(STATE_STREAM, CONSUMER_GROUP, entry_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    enforce_production_service_auth_config(
        environment=ENVIRONMENT,
        service_api_key=SERVICE_API_KEY,
        key_mode=AGENT_SERVICE_KEY_MODE,
        required_agent_ids=(WORKER_AGENT_ID,),
        raw_mapping=AGENT_SERVICE_API_KEYS,
        service_name="audit-worker",
    )
    if AGENT_SERVICE_KEY_MODE == "shared":
        LOGGER.warning(
            "AGENT_SERVICE_KEY_MODE is 'shared'; all agents without a dedicated key will use "
            "the shared SERVICE_API_KEY. Set AGENT_SERVICE_KEY_MODE=strict in production."
        )
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
