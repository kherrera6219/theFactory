import asyncio
import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import redis.asyncio as redis
from fastapi import FastAPI
from redis.exceptions import ResponseError

LOGGER = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
STATE_STREAM = os.getenv("STATE_STREAM", "missions.state")
CONSUMER_GROUP = os.getenv("POD_WORKER_GROUP", "pod-workers")
CONSUMER_NAME = os.getenv("POD_WORKER_NAME", f"pod-worker-{uuid.uuid4()}")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8001")
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY", "worker-key")
POD_NAME = os.getenv("POD_NAME", "podA")
SUPPORTED_LANGUAGES = {
    language.strip().lower()
    for language in os.getenv("SUPPORTED_LANGUAGES", "python,typescript,javascript,ruby,php").split(
        ","
    )
    if language.strip()
}
MAX_STREAM_LEN = int(os.getenv("MAX_STREAM_LEN", "20000"))
PAYLOAD_REF_PATTERN = re.compile(r"^registry://")

EVENT_SCHEMA_PATH = Path("/app/schemas/event.envelope.schema.json")
TOPICS_PATH = Path("/app/protocol/topics.yaml")


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
        raise ProtocolValidationError(f"envelope missing required fields: {', '.join(missing)}")

    if schema.get("additionalProperties") is False:
        unknown = [field for field in envelope if field not in properties]
        if unknown:
            raise ProtocolValidationError(f"unexpected envelope fields: {', '.join(unknown)}")

    if envelope.get("topic") not in topics:
        raise ProtocolValidationError(f"unknown topic: {envelope.get('topic')}")
    if not PAYLOAD_REF_PATTERN.match(str(envelope.get("payload_ref", ""))):
        raise ProtocolValidationError("payload_ref must start with registry://")
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
    topic: str, correlation_id: str, payload_ref: str, schema_name: str
) -> dict[str, Any]:
    envelope = {
        "event_id": f"evt-{uuid.uuid4()}",
        "topic": topic,
        "timestamp": datetime.now(UTC).isoformat(),
        "producer": f"pod-worker-{POD_NAME}",
        "correlation_id": correlation_id,
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
        correlation_id=mission_id,
        payload_ref=f"registry://missions/{mission_id}/pod/{POD_NAME}/{topic}",
        schema_name="pod.assignment.v1",
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


async def _request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=5.0) as client:
        return await client.request(
            method,
            f"{ORCHESTRATOR_URL}{path}",
            json=json_body,
            params=params,
            headers={"x-api-key": SERVICE_API_KEY},
        )


async def _has_assignment(mission_id: str) -> bool:
    response = await _request("GET", f"/internal/missions/{mission_id}/pod-assignment")
    if response.status_code == 404:
        return False
    if response.status_code >= 400:
        return False
    assignment = response.json()
    return bool(assignment.get("pod_name"))


async def _handle_running_mission(redis_client: redis.Redis, payload: dict[str, Any]) -> None:
    mission_id = str(payload.get("mission_id", ""))
    if not mission_id:
        return

    target = payload.get("requested_target_language")
    target_language = str(target).lower() if isinstance(target, str) else ""
    if target_language and target_language not in SUPPORTED_LANGUAGES:
        return
    if not target_language and POD_NAME != "podA":
        return
    if await _has_assignment(mission_id):
        return

    details = {
        "assigned_by": "pod-worker",
        "pod_name": POD_NAME,
        "supported_languages": sorted(SUPPORTED_LANGUAGES),
        "reason": "language-match",
    }
    assignment_response = await _request(
        "POST",
        "/internal/pod-assignment",
        json_body={
            "mission_id": mission_id,
            "pod_name": POD_NAME,
            "metadata": details,
        },
    )
    if assignment_response.status_code == 409:
        return
    if assignment_response.status_code >= 400:
        return

    await _request(
        "POST",
        "/internal/logicnodes",
        json_body={
            "mission_id": mission_id,
            "node_id": f"{POD_NAME}.core.{mission_id}",
            "node": {
                "node_name": f"{POD_NAME}-logicnode-core",
                "source_language": target_language or "generic",
                "target_language": target_language or "generic",
                "payload": {"origin": "pod-worker", "pod_name": POD_NAME},
            },
        },
    )
    await _request(
        "POST",
        "/internal/knowledge",
        json_body={
            "mission_id": mission_id,
            "knowledge_id": f"{POD_NAME}.assignment.{mission_id}",
            "content": {
                "summary": f"{POD_NAME} accepted mission for specialist routing.",
                "metadata": {"pod_name": POD_NAME, "source": "pod-worker"},
            },
        },
    )

    await _publish_event(
        redis_client,
        f"cluster.assigned.{POD_NAME}",
        mission_id,
        {
            "mission_id": mission_id,
            "pod_name": POD_NAME,
            "event_type": "MISSION_POD_ASSIGNED",
            "state": payload.get("state", "RUNNING"),
        },
    )
    await _publish_event(
        redis_client,
        "pod.standard.ready",
        mission_id,
        {
            "mission_id": mission_id,
            "pod_name": POD_NAME,
            "event_type": "POD_READY",
            "state": payload.get("state", "RUNNING"),
        },
    )


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
                acknowledge = False
                try:
                    envelope_raw = fields.get("envelope")
                    payload_raw = fields.get("payload")
                    if not envelope_raw or not payload_raw:
                        raise ProtocolValidationError("missing envelope or payload")

                    envelope = json.loads(envelope_raw)
                    _validate_envelope(envelope)
                    payload = json.loads(payload_raw)
                    event_type = str(payload.get("event_type", ""))
                    if event_type == "MISSION_RUNNING":
                        await _handle_running_mission(redis_client, payload)
                        app.state.processed += 1
                    acknowledge = True
                except (ProtocolValidationError, json.JSONDecodeError, KeyError, TypeError) as exc:
                    app.state.errors += 1
                    acknowledge = True
                    LOGGER.warning("discarding invalid state event %s: %s", entry_id, exc)
                except Exception as exc:
                    app.state.errors += 1
                    LOGGER.warning("failed to process state event %s: %s", entry_id, exc)
                finally:
                    if acknowledge:
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
        await app.state.redis.close()


app = FastAPI(title=f"HolyGrail Pod Worker ({POD_NAME})", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, Any]:
    ready = bool(await app.state.redis.ping())
    return {
        "ok": ready,
        "service": "pod-worker",
        "pod_name": POD_NAME,
        "supported_languages": sorted(SUPPORTED_LANGUAGES),
        "state_stream": STATE_STREAM,
        "group": CONSUMER_GROUP,
        "consumer": CONSUMER_NAME,
        "processed": app.state.processed,
        "errors": app.state.errors,
    }
