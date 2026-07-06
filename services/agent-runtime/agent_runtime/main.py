from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import re
import sys
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

from shared_runtime.logging_config import configure_logging
from shared_runtime.protocol import (
    ProtocolValidationError,
    load_event_schema,
    load_topics,
    parse_date_time,
    validate_envelope,
)

from .tracing import configure_tracing

try:
    from orchestrator.agent_base import make_agent
    from orchestrator.agent_registry import normalize_language
except ModuleNotFoundError:
    ORCHESTRATOR_SERVICE_ROOT = Path(__file__).resolve().parents[3] / "services" / "orchestrator"
    if ORCHESTRATOR_SERVICE_ROOT.exists():
        sys.path.insert(0, str(ORCHESTRATOR_SERVICE_ROOT))
    from orchestrator.agent_base import make_agent
    from orchestrator.agent_registry import normalize_language

configure_logging("agent-runtime")
LOGGER = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
STATE_STREAM = os.getenv("STATE_STREAM", "missions.state")
CONSUMER_GROUP = os.getenv("AGENT_RUNTIME_GROUP", "agent-runtime")
CONSUMER_NAME = os.getenv("AGENT_RUNTIME_NAME", f"agent-runtime-{uuid.uuid4()}")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8001")
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY", "")
if not SERVICE_API_KEY:
    raise RuntimeError(
        "SERVICE_API_KEY must be set — no default credential is allowed for "
        "agent-runtime's calls to the orchestrator's internal API."
    )
REQUEST_TIMEOUT_SECONDS = float(os.getenv("ORCHESTRATOR_TIMEOUT_SECONDS", "5.0"))
REQUEST_MAX_RETRIES = int(os.getenv("ORCHESTRATOR_MAX_RETRIES", "3"))
MAX_STREAM_LEN = int(os.getenv("MAX_STREAM_LEN", "20000"))
WORKER_AGENT_ID = os.getenv("WORKER_AGENT_ID", "").strip().upper()
HEARTBEAT_INTERVAL_SECONDS = max(
    5.0,
    float(os.getenv("AGENT_HEARTBEAT_INTERVAL_SECONDS", "15.0")),
)
PAYLOAD_REF_PATTERN = re.compile(r"^registry://")

EVENT_SCHEMA_PATH = Path("/app/schemas/event.envelope.schema.json")
TOPICS_PATH = Path("/app/protocol/topics.yaml")

TASKS_PROCESSED = Counter(
    "agent_runtime_tasks_processed_total",
    "Total mission events processed by dedicated agent runtime",
    ("agent_id",),
)
TASKS_FAILED = Counter(
    "agent_runtime_tasks_failed_total",
    "Total mission events failed by dedicated agent runtime",
    ("agent_id",),
)
TASK_LATENCY_SECONDS = Histogram(
    "agent_runtime_task_latency_seconds",
    "Mission event processing latency for dedicated agent runtime",
    ("agent_id",),
)
AGENT_EXECUTION_LATENCY = Histogram(
    "agent_runtime_execution_latency_seconds",
    "Agent execution latency for dedicated agent runtime",
    ("agent_id", "category"),
)
AGENT_HEARTBEAT_ATTEMPTS = Counter(
    "agent_runtime_heartbeat_attempts_total",
    "Total heartbeat attempts emitted by dedicated agent runtime",
    ("agent_id", "status"),
)
AGENT_CIRCUIT_OPEN = Counter(
    "agent_runtime_circuit_open_total",
    "Total circuit breaker trips for dedicated agent runtime",
    ("agent_id",),
)


# ---------------------------------------------------------------------------
# Circuit breaker (2026 best practice: fail-fast when orchestrator unreachable)
# ---------------------------------------------------------------------------

class _CircuitBreaker:
    """Simple half-open circuit breaker for orchestrator connectivity.

    States:
        CLOSED  — normal operation
        OPEN    — orchestrator unreachable; reject requests immediately
        HALF    — test probe allowed; close if probe succeeds

    Recovery: after RECOVERY_SECONDS in OPEN state, move to HALF to probe.
    """

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF = "HALF"

    FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_FAILURE_THRESHOLD", "5"))
    RECOVERY_SECONDS = float(os.getenv("CIRCUIT_RECOVERY_SECONDS", "30.0"))

    def __init__(self) -> None:
        self.state = self.CLOSED
        self._failures = 0
        self._opened_at: float = 0.0

    def record_success(self) -> None:
        self._failures = 0
        self.state = self.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.FAILURE_THRESHOLD:
            if self.state != self.OPEN:
                LOGGER.warning(
                    "circuit breaker OPEN after %d consecutive failures for agent %s",
                    self._failures,
                    WORKER_AGENT_ID or "<unknown>",
                )
                AGENT_CIRCUIT_OPEN.labels(agent_id=WORKER_AGENT_ID or "unknown").inc()
            self.state = self.OPEN
            self._opened_at = time.time()

    def is_open(self) -> bool:
        if self.state == self.OPEN:
            if time.time() - self._opened_at >= self.RECOVERY_SECONDS:
                LOGGER.info("circuit breaker entering HALF-OPEN for probe")
                self.state = self.HALF
                return False
            return True
        return False


_CIRCUIT: _CircuitBreaker = _CircuitBreaker()


def _worker_agent():
    if not WORKER_AGENT_ID:
        raise RuntimeError("WORKER_AGENT_ID is required for agent-runtime")
    return make_agent(WORKER_AGENT_ID)


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


async def _emit_audit_event(
    *,
    mission_id: str | None,
    event_type: str,
    status: str = "SUCCESS",
    object_type: str | None = None,
    object_id: str | None = None,
    tool_name: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    payload_summary: dict[str, Any] | None = None,
) -> None:
    if not mission_id:
        return
    try:
        response = await _request(
            "POST",
            "/internal/audit-events",
            json_body={
                "mission_id": mission_id,
                "agent_id": WORKER_AGENT_ID or "AGENT-RUNTIME",
                "service_name": "agent-runtime",
                "event_type": event_type,
                "status": status,
                "object_type": object_type,
                "object_id": object_id,
                "tool_name": tool_name,
                "started_at": started_at or datetime.now(UTC).isoformat(),
                "ended_at": ended_at or datetime.now(UTC).isoformat(),
                "payload_summary": _summarize_mapping(payload_summary),
            },
            emit_audit=False,
        )
        if response.status_code >= 400:
            LOGGER.warning(
                "agent-runtime failed to persist audit event %s for mission %s: %s",
                event_type,
                mission_id,
                response.status_code,
            )
    except Exception as exc:
        LOGGER.warning(
            "agent-runtime failed to emit audit event %s for mission %s: %s",
            event_type,
            mission_id,
            exc,
        )


async def _request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    emit_audit: bool = True,
) -> httpx.Response:
    """Make an HTTP request to the orchestrator, honouring the circuit breaker.

    2026 best practice: fail-fast when orchestrator is unreachable to prevent
    cascade failures across all agent workers.
    """
    if not path.startswith("/"):
        raise ValueError("request path must start with '/'")
    if _CIRCUIT.is_open():
        raise RuntimeError(
            f"circuit breaker OPEN — orchestrator unreachable; retry after "
            f"{_CircuitBreaker.RECOVERY_SECONDS}s"
        )
    started_at = datetime.now(UTC).isoformat()
    request_id = f"agent-runtime-{uuid.uuid4()}"
    headers = {
        "x-api-key": SERVICE_API_KEY,
        "x-request-id": request_id,
        "x-agent-id": WORKER_AGENT_ID,
    }
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
                    headers=headers,
                )
                last_response = response
                if response.status_code < 500 and response.status_code != 429:
                    _CIRCUIT.record_success()
                    return response
                _CIRCUIT.record_failure()
            except httpx.HTTPError as exc:
                last_error = exc
                _CIRCUIT.record_failure()
            if attempt < REQUEST_MAX_RETRIES:
                await asyncio.sleep(0.1 * attempt)
    if last_response is not None:
        if emit_audit and path != "/internal/audit-events":
            await _emit_audit_event(
                mission_id=_mission_id_for_request(path, json_body=json_body, params=params),
                event_type="TOOL_HTTP_REQUEST",
                status="SUCCESS" if last_response.status_code < 400 else "ERROR",
                object_type="http_request",
                object_id=path,
                tool_name="orchestrator_api",
                started_at=started_at,
                ended_at=datetime.now(UTC).isoformat(),
                payload_summary={
                    "method": method,
                    "path": path,
                    "status_code": last_response.status_code,
                },
            )
        return last_response
    if last_error is not None:
        raise last_error
    raise RuntimeError("request failed without response")


async def _fetch_mission_snapshot(mission_id: str) -> dict[str, Any] | None:
    response = await _request("GET", f"/missions/{mission_id}")
    if response.status_code >= 400:
        return None
    payload = response.json()
    return payload if isinstance(payload, dict) else None


async def _fetch_pod_assignment(mission_id: str) -> dict[str, Any] | None:
    response = await _request("GET", f"/internal/missions/{mission_id}/pod-assignment")
    if response.status_code >= 400:
        return None
    payload = response.json()
    return payload if isinstance(payload, dict) else None


async def _fetch_logicnodes(mission_id: str) -> list[dict[str, Any]]:
    response = await _request(
        "GET",
        "/v1/operations/logicnodes",
        params={"mission_id": mission_id, "limit": 400},
    )
    if response.status_code >= 400:
        return []
    payload = response.json()
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def _safe_to_dict(candidate: Any) -> dict[str, Any]:
    if hasattr(candidate, "to_dict") and callable(candidate.to_dict):
        payload = candidate.to_dict()
        if isinstance(payload, dict):
            return payload
    return {}


def _summarize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        compact = " ".join(value.split())
        return compact if len(compact) <= 240 else f"{compact[:240]}..."
    if isinstance(value, dict):
        items = list(value.items())[:8]
        summary = {str(key): _summarize_value(item) for key, item in items}
        if len(value) > 8:
            summary["_truncated_keys"] = len(value) - 8
        return summary
    if isinstance(value, list):
        summary = [_summarize_value(item) for item in value[:8]]
        if len(value) > 8:
            summary.append({"_truncated_items": len(value) - 8})
        return summary
    return str(value)


def _summarize_mapping(value: Any) -> dict[str, Any]:
    return _summarize_value(value) if isinstance(value, dict) else {}


def _mission_id_for_request(
    path: str,
    *,
    json_body: dict[str, Any] | None,
    params: dict[str, Any] | None,
) -> str | None:
    if isinstance(json_body, dict):
        mission_id = str(json_body.get("mission_id", "")).strip()
        if mission_id:
            return mission_id
    if isinstance(params, dict):
        mission_id = str(params.get("mission_id", "")).strip()
        if mission_id:
            return mission_id
    match = re.search(r"/missions/([^/]+)", path)
    if match:
        return str(match.group(1)).strip()
    return None


def _event_types_for_agent(agent: Any) -> set[str]:
    if agent.category == "interface":
        return {"MISSION_QUEUED"}
    if agent.category == "executive":
        return {"MISSION_PM_INTAKE"}
    if agent.category == "pod_audit":
        return {"MISSION_VERIFIED", "MISSION_FAILED"}
    short_code = agent.definition.short_code
    if short_code == "TESTER":
        return {"MISSION_VERIFIED", "MISSION_FAILED"}
    if short_code == "DEPLOY":
        return {"MISSION_COMPLETE"}
    return {"MISSION_RUNNING"}


def _agent_supports_language(agent: Any, target_language: str) -> bool:
    if agent.definition.short_code != "HW":
        return True
    return normalize_language(target_language) in {"c", "cpp", "rust", "zig"}


def _pod_name_matches(agent: Any, pod_assignment: dict[str, Any] | None) -> bool:
    if agent.category != "pod_audit":
        return True
    if not isinstance(pod_assignment, dict):
        return False
    pod_name = str(pod_assignment.get("pod_name", "")).strip().lower()
    expected = agent.pod.strip().lower().replace(" ", "")
    return pod_name == expected


def _run_agent_pipeline(agent: Any, *, mission_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    result = agent.execute(mission_id, payload)
    validation = agent.validate(mission_id, getattr(result, "artifacts", []))
    report = agent.report(mission_id, result, validation)
    AGENT_EXECUTION_LATENCY.labels(agent_id=agent.agent_id, category=agent.category).observe(
        time.perf_counter() - started
    )
    return {
        "result": result,
        "validation": validation,
        "report": report,
    }


async def _post_agent_heartbeat(
    *,
    state: str,
    mission_id: str | None,
    metadata: dict[str, Any],
) -> bool:
    response = await _request(
        "POST",
        "/internal/agents/heartbeat",
        json_body={
            "agent_id": WORKER_AGENT_ID,
            "state": state,
            "queue_depth": 1 if mission_id else 0,
            "workload_pct": 44 if mission_id else 8,
            "active_mission_ids": [mission_id] if mission_id else [],
            "metadata": {
                "producer": f"agent-runtime-{WORKER_AGENT_ID}",
                **metadata,
            },
        },
    )
    status = "success" if response.status_code < 400 else "error"
    AGENT_HEARTBEAT_ATTEMPTS.labels(agent_id=WORKER_AGENT_ID, status=status).inc()
    return response.status_code < 400


async def _persist_pipeline_output(
    *,
    agent: Any,
    mission_id: str,
    pipeline: dict[str, Any],
) -> None:
    report = _safe_to_dict(pipeline["report"])
    validation = _safe_to_dict(pipeline["validation"])
    result = _safe_to_dict(pipeline["result"])
    if agent.category == "pod_audit" or agent.definition.short_code == "TESTER":
        await _request(
            "POST",
            "/internal/audit-reports",
            json_body={
                "mission_id": mission_id,
                "audit_id": f"{agent.agent_id}.{mission_id}",
                "status": report.get("verdict", "PASS"),
                "report": {
                    "summary": report.get("summary", f"{agent.agent_id} completed audit."),
                    "agent_id": agent.agent_id,
                    "validation": validation,
                    "result": result,
                    "report": report,
                },
            },
        )
        await _emit_audit_event(
            mission_id=mission_id,
            event_type="AGENT_REPORT_PERSISTED",
            object_type="audit_report",
            object_id=f"{agent.agent_id}.{mission_id}",
            payload_summary={"agent_id": agent.agent_id, "category": agent.category},
        )
        return

    await _request(
        "POST",
        "/internal/knowledge",
        json_body={
            "mission_id": mission_id,
            "knowledge_id": f"{agent.agent_id}.{mission_id}",
            "content": {
                "summary": report.get("summary", f"{agent.agent_id} processed mission."),
                "metadata": {
                    "agent_id": agent.agent_id,
                    "agent_category": agent.category,
                    "validation": validation,
                    "result": result,
                    "report": report,
                },
            },
        },
    )
    await _emit_audit_event(
        mission_id=mission_id,
        event_type="AGENT_REPORT_PERSISTED",
        object_type="knowledge",
        object_id=f"{agent.agent_id}.{mission_id}",
        payload_summary={"agent_id": agent.agent_id, "category": agent.category},
    )


async def _process_event(payload: dict[str, Any]) -> bool:
    mission_id = str(payload.get("mission_id", "")).strip()
    if not mission_id:
        return False

    agent = _worker_agent()
    event_type = str(payload.get("event_type", "")).strip().upper()
    if event_type not in _event_types_for_agent(agent):
        return False

    mission = await _fetch_mission_snapshot(mission_id)
    if mission is None:
        return False
    target_language = str(mission.get("requested_target_language") or "").strip().lower()
    if not _agent_supports_language(agent, target_language):
        return False

    pod_assignment = await _fetch_pod_assignment(mission_id)
    if not _pod_name_matches(agent, pod_assignment):
        return False

    logicnodes = await _fetch_logicnodes(mission_id) if agent.category == "pod_audit" else []
    await _post_agent_heartbeat(
        state="RUNNING",
        mission_id=mission_id,
        metadata={"event_type": event_type, "category": agent.category},
    )
    execution_started_at = datetime.now(UTC).isoformat()
    await _emit_audit_event(
        mission_id=mission_id,
        event_type="AGENT_EXECUTION_STARTED",
        status="STARTED",
        object_type="agent_execution",
        object_id=agent.agent_id,
        payload_summary={"agent_id": agent.agent_id, "event_type": event_type},
    )
    try:
        pipeline = _run_agent_pipeline(
            agent,
            mission_id=mission_id,
            payload={
                "event_type": event_type,
                "mission": mission,
                "requested_target_language": target_language,
                "logicnodes": logicnodes,
                "pod_assignment": pod_assignment,
                "rationale": payload.get("event_type", ""),
            },
        )
    except Exception as exc:
        await _emit_audit_event(
            mission_id=mission_id,
            event_type="AGENT_EXECUTION_COMPLETED",
            status="ERROR",
            object_type="agent_execution",
            object_id=agent.agent_id,
            started_at=execution_started_at,
            ended_at=datetime.now(UTC).isoformat(),
            payload_summary={"agent_id": agent.agent_id, "error": str(exc)},
        )
        raise
    await _emit_audit_event(
        mission_id=mission_id,
        event_type="AGENT_EXECUTION_COMPLETED",
        object_type="agent_execution",
        object_id=agent.agent_id,
        started_at=execution_started_at,
        ended_at=datetime.now(UTC).isoformat(),
        payload_summary={
            "agent_id": agent.agent_id,
            "category": agent.category,
            "artifact_count": len(_safe_to_dict(pipeline["result"]).get("artifacts", []) or []),
            "validation": _summarize_mapping(_safe_to_dict(pipeline["validation"])),
        },
    )
    await _persist_pipeline_output(agent=agent, mission_id=mission_id, pipeline=pipeline)
    await _post_agent_heartbeat(
        state="ACTIVE",
        mission_id=mission_id,
        metadata={"event_type": event_type, "category": agent.category, "status": "complete"},
    )
    return True


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
                try:
                    envelope_raw = fields.get("envelope")
                    payload_raw = fields.get("payload")
                    if not envelope_raw or not payload_raw:
                        raise ProtocolValidationError("missing envelope or payload")
                    envelope = json.loads(envelope_raw)
                    _validate_envelope(envelope)
                    payload = json.loads(payload_raw)
                    processed = await _process_event(payload)
                    if processed:
                        app.state.processed += 1
                        TASKS_PROCESSED.labels(agent_id=WORKER_AGENT_ID).inc()
                    acknowledge = True
                except (ProtocolValidationError, json.JSONDecodeError, KeyError, TypeError) as exc:
                    app.state.errors += 1
                    TASKS_FAILED.labels(agent_id=WORKER_AGENT_ID).inc()
                    acknowledge = True
                    LOGGER.warning("discarding invalid state event %s: %s", entry_id, exc)
                except Exception as exc:
                    app.state.errors += 1
                    TASKS_FAILED.labels(agent_id=WORKER_AGENT_ID).inc()
                    LOGGER.warning("failed to process state event %s: %s", entry_id, exc)
                finally:
                    TASK_LATENCY_SECONDS.labels(agent_id=WORKER_AGENT_ID).observe(
                        time.perf_counter() - started
                    )
                    if acknowledge:
                        await redis_client.xack(STATE_STREAM, CONSUMER_GROUP, entry_id)


async def _heartbeat_loop(app: FastAPI) -> None:
    while True:
        try:
            agent = _worker_agent()
            await _post_agent_heartbeat(
                state="IDLE",
                mission_id=None,
                metadata={"category": agent.category, "pod": agent.pod},
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOGGER.warning("failed to emit agent-runtime heartbeat: %s", exc)
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _worker_agent()
    app.state.redis = redis.from_url(REDIS_URL, decode_responses=True)
    app.state.consumer_task = None
    app.state.heartbeat_task = None
    app.state.processed = 0
    app.state.errors = 0
    await app.state.redis.ping()
    await _ensure_group(app.state.redis)
    app.state.consumer_task = asyncio.create_task(_consumer_loop(app))
    app.state.heartbeat_task = asyncio.create_task(_heartbeat_loop(app))
    yield

    for task_name in ("consumer_task", "heartbeat_task"):
        task = getattr(app.state, task_name, None)
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


app = FastAPI(title="HolyGrail Dedicated Agent Runtime", version="0.1.0", lifespan=lifespan)
configure_tracing(app, service_name="agent-runtime")


@app.get("/health")
async def health() -> dict[str, Any]:
    ready = False
    redis_client = getattr(app.state, "redis", None)
    if redis_client is not None:
        try:
            ready = bool(await redis_client.ping())
        except Exception:
            ready = False
    agent = _worker_agent()
    return {
        "ok": ready,
        "service": "agent-runtime",
        "worker_agent_id": WORKER_AGENT_ID,
        "category": agent.category,
        "pod": agent.pod,
        "event_types": sorted(_event_types_for_agent(agent)),
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
    _worker_agent()
    return {"ready": True, "service": "agent-runtime", "worker_agent_id": WORKER_AGENT_ID}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
