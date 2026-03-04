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

from .language_extractor import get_extractor

LOGGER = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
STATE_STREAM = os.getenv("STATE_STREAM", "missions.state")
CONSUMER_GROUP = os.getenv("POD_WORKER_GROUP", "pod-workers")
CONSUMER_NAME = os.getenv("POD_WORKER_NAME", f"pod-worker-{uuid.uuid4()}")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8001")
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY", "worker-key")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("ORCHESTRATOR_TIMEOUT_SECONDS", "5.0"))
REQUEST_MAX_RETRIES = int(os.getenv("ORCHESTRATOR_MAX_RETRIES", "3"))
POD_NAME = os.getenv("POD_NAME", "podA")
SUPPORTED_LANGUAGES = {
    language.strip().lower()
    for language in os.getenv("SUPPORTED_LANGUAGES", "python,typescript,javascript,ruby,php").split(
        ","
    )
    if language.strip()
}
AGENT_BINDING = os.getenv("AGENT_BINDING", "")
MAX_STREAM_LEN = int(os.getenv("MAX_STREAM_LEN", "20000"))
PAYLOAD_REF_PATTERN = re.compile(r"^registry://")

EVENT_SCHEMA_PATH = Path("/app/schemas/event.envelope.schema.json")
TOPICS_PATH = Path("/app/protocol/topics.yaml")

TASKS_PROCESSED = Counter(
    "pod_worker_tasks_processed_total",
    "Total mission events processed by pod worker",
    ("pod_name",),
)
TASKS_FAILED = Counter(
    "pod_worker_tasks_failed_total",
    "Total mission events failed by pod worker",
    ("pod_name",),
)
TASK_LATENCY_SECONDS = Histogram(
    "pod_worker_task_latency_seconds",
    "Mission event processing latency for pod worker",
    ("pod_name",),
)
CONCEPTS_EXTRACTED = Counter(
    "pod_worker_concepts_extracted_total",
    "Total computational concepts extracted by pod worker",
    ("pod_name", "language"),
)
EXTRACTION_LATENCY = Histogram(
    "pod_worker_extraction_latency_seconds",
    "Source code extraction latency for pod worker",
    ("pod_name",),
)
BINDING_SKIPS = Counter(
    "pod_worker_binding_skips_total",
    "Total missions skipped because agent binding did not match",
    ("pod_name", "reason"),
)


class ProtocolValidationError(Exception):
    pass


def _parse_agent_binding(raw: str) -> tuple[str, ...]:
    candidates = re.split(r"[\s,]+", raw.strip())
    normalized = {candidate.strip().upper() for candidate in candidates if candidate.strip()}
    return tuple(sorted(normalized))


AGENT_BINDINGS = _parse_agent_binding(AGENT_BINDING)
AGENT_BINDING_SET = frozenset(AGENT_BINDINGS)


def _normalize_agent_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().upper()
    return candidate or None


def _agent_id_from_metadata(metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return None
    for key in ("agent_id", "target_agent_id", "selected_agent_id", "assigned_agent_id"):
        normalized = _normalize_agent_id(metadata.get(key))
        if normalized:
            return normalized

    nested_agent = metadata.get("agent")
    if isinstance(nested_agent, dict):
        for key in ("agent_id", "id"):
            normalized = _normalize_agent_id(nested_agent.get(key))
            if normalized:
                return normalized
    return None


def _agent_id_from_payload(payload: dict[str, Any]) -> str | None:
    for key in ("agent_id", "target_agent_id", "selected_agent_id", "assigned_agent_id"):
        normalized = _normalize_agent_id(payload.get(key))
        if normalized:
            return normalized
    return _agent_id_from_metadata(payload.get("metadata"))


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
    if not path.startswith("/"):
        raise ValueError("request path must start with '/'")
    request_id = f"pod-{POD_NAME}-{uuid.uuid4()}"
    last_response: httpx.Response | None = None
    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        for attempt in range(1, REQUEST_MAX_RETRIES + 1):
            try:
                response = await client.request(
                    method,
                    f"{ORCHESTRATOR_URL}{path}",
                    json=json_body,
                    params=params,
                    headers={"x-api-key": SERVICE_API_KEY, "x-request-id": request_id},
                )
                last_response = response
                if response.status_code < 500 and response.status_code != 429:
                    return response
            except httpx.HTTPError as exc:
                last_error = exc
            if attempt < REQUEST_MAX_RETRIES:
                await asyncio.sleep(0.1 * attempt)

    if last_response is not None:
        return last_response
    if last_error is not None:
        raise last_error
    raise RuntimeError("request failed without response")


async def _has_assignment(mission_id: str) -> bool:
    response = await _request("GET", f"/internal/missions/{mission_id}/pod-assignment")
    if response.status_code == 404:
        return False
    if response.status_code >= 400:
        return False
    assignment = response.json()
    return bool(assignment.get("pod_name"))


async def _fetch_mission_agent_id(mission_id: str) -> str | None:
    response = await _request("GET", f"/missions/{mission_id}")
    if response.status_code >= 400:
        return None
    mission = response.json()
    if not isinstance(mission, dict):
        return None

    for key in ("agent_id", "target_agent_id", "selected_agent_id", "assigned_agent_id"):
        normalized = _normalize_agent_id(mission.get(key))
        if normalized:
            return normalized
    return _agent_id_from_metadata(mission.get("metadata"))


async def _mission_matches_agent_binding(mission_id: str, payload: dict[str, Any]) -> bool:
    if not AGENT_BINDING_SET:
        return True

    mission_agent_id = _agent_id_from_payload(payload)
    if mission_agent_id is None:
        mission_agent_id = await _fetch_mission_agent_id(mission_id)
    if mission_agent_id is None:
        BINDING_SKIPS.labels(pod_name=POD_NAME, reason="agent-unresolved").inc()
        return False
    if mission_agent_id not in AGENT_BINDING_SET:
        BINDING_SKIPS.labels(pod_name=POD_NAME, reason="agent-mismatch").inc()
        return False
    return True


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
    if not await _mission_matches_agent_binding(mission_id, payload):
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

    # --- Language extraction --------------------------------------------------
    source_code = payload.get("source_code", "")
    extraction_language = target_language or "python"  # default Pod A primary
    extraction_summary: dict = {"language": extraction_language, "concepts_found": 0}

    if source_code:
        started = time.perf_counter()
        extractor = get_extractor(extraction_language)
        result = extractor.extract(source_code)
        EXTRACTION_LATENCY.labels(pod_name=POD_NAME).observe(time.perf_counter() - started)
        CONCEPTS_EXTRACTED.labels(pod_name=POD_NAME, language=extraction_language).inc(
            len(result.concepts)
        )
        extraction_summary = result.summary

        # Create one LogicNode per extracted concept
        for concept in result.concepts:
            node_id = f"{POD_NAME}.{concept.concept_id}.{mission_id}"
            await _request(
                "POST",
                "/internal/logicnodes",
                json_body={
                    "mission_id": mission_id,
                    "node_id": node_id,
                    "node": {
                        "node_name": f"{concept.domain}.{concept.concept}",
                        "source_language": extraction_language,
                        "target_language": target_language or "generic",
                        "payload": {
                            "origin": "pod-worker",
                            "pod_name": POD_NAME,
                            "concept_id": concept.concept_id,
                            "domain": concept.domain,
                            "concept": concept.concept,
                            "intent": concept.intent,
                            "confidence": concept.confidence,
                            "source_line": concept.source_line,
                            "evidence": concept.evidence,
                        },
                    },
                },
            )
    else:
        # No source code attached — create a stub LogicNode for routing
        await _request(
            "POST",
            "/internal/logicnodes",
            json_body={
                "mission_id": mission_id,
                "node_id": f"{POD_NAME}.core.{mission_id}",
                "node": {
                    "node_name": f"{POD_NAME}-logicnode-core",
                    "source_language": extraction_language,
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
                "metadata": {
                    "pod_name": POD_NAME,
                    "source": "pod-worker",
                    "extraction": extraction_summary,
                },
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
                started = time.perf_counter()
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
                        TASKS_PROCESSED.labels(pod_name=POD_NAME).inc()
                    acknowledge = True
                except (ProtocolValidationError, json.JSONDecodeError, KeyError, TypeError) as exc:
                    app.state.errors += 1
                    TASKS_FAILED.labels(pod_name=POD_NAME).inc()
                    acknowledge = True
                    LOGGER.warning("discarding invalid state event %s: %s", entry_id, exc)
                except Exception as exc:
                    app.state.errors += 1
                    TASKS_FAILED.labels(pod_name=POD_NAME).inc()
                    LOGGER.warning("failed to process state event %s: %s", entry_id, exc)
                finally:
                    TASK_LATENCY_SECONDS.labels(pod_name=POD_NAME).observe(
                        time.perf_counter() - started
                    )
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
        close = getattr(app.state.redis, "close", None)
        if callable(close):
            result = close()
            if inspect.isawaitable(result):
                await result


app = FastAPI(title=f"HolyGrail Pod Worker ({POD_NAME})", version="0.1.0", lifespan=lifespan)


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
        "service": "pod-worker",
        "pod_name": POD_NAME,
        "supported_languages": sorted(SUPPORTED_LANGUAGES),
        "state_stream": STATE_STREAM,
        "group": CONSUMER_GROUP,
        "consumer": CONSUMER_NAME,
        "agent_binding": list(AGENT_BINDINGS),
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
    return {"ready": True, "service": "pod-worker", "pod_name": POD_NAME}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
