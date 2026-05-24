import json
import os
import subprocess
import time
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest

GATEWAY_BASE_URL = os.getenv("LIVE_GATEWAY_URL", "http://localhost:8100").rstrip("/")
ORCHESTRATOR_BASE_URL = os.getenv("LIVE_ORCHESTRATOR_URL", "http://localhost:8101").rstrip("/")
HTTP_TIMEOUT_SECONDS = float(os.getenv("LIVE_HTTP_TIMEOUT_SECONDS", "30.0"))
INTERNAL_SERVICE_API_KEY = os.getenv("LIVE_INTERNAL_SERVICE_API_KEY", "worker-key")
COMPOSE_FILE = os.getenv("LIVE_COMPOSE_FILE", "deploy/docker-compose.yaml")
RUN_DISRUPTION_TESTS = os.getenv("LIVE_ENABLE_DISRUPTION_TESTS", "false").lower() == "true"


def _request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    body: bytes | None = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    request = Request(url, data=body, method=method, headers=request_headers)
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            status = int(response.status)
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        status = int(exc.code)
        raw = exc.read().decode("utf-8") if exc.fp is not None else ""

    if not raw:
        return status, None
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw


def _compose_command(*args: str) -> list[str]:
    return ["docker", "compose", "-f", COMPOSE_FILE, "--profile", "extended-data-plane", *args]


def _compose_run(*args: str, timeout_seconds: float = 120.0) -> None:
    try:
        subprocess.run(
            _compose_command(*args),
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        pytest.skip("Docker CLI is unavailable; skipping disruption qualification.")
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        pytest.skip(f"Docker compose command failed; skipping disruption qualification: {stderr}")


def _require_live_stack() -> dict[str, Any]:
    try:
        gateway_status, gateway_ready = _request_json("GET", f"{GATEWAY_BASE_URL}/readyz")
        orchestrator_status, orchestrator_ready = _request_json(
            "GET", f"{ORCHESTRATOR_BASE_URL}/readyz"
        )
    except (URLError, TimeoutError, OSError):
        pytest.skip("Live stack not reachable; skipping live extended-data-plane tests.")

    if (
        gateway_status != 200
        or not isinstance(gateway_ready, dict)
        or not gateway_ready.get("ready")
    ):
        pytest.skip("Gateway is not ready; skipping live extended-data-plane tests.")
    if (
        orchestrator_status != 200
        or not isinstance(orchestrator_ready, dict)
        or not orchestrator_ready.get("ready")
    ):
        pytest.skip("Orchestrator is not ready; skipping live extended-data-plane tests.")

    health_status, health_payload = _request_json("GET", f"{ORCHESTRATOR_BASE_URL}/health")
    if health_status != 200 or not isinstance(health_payload, dict):
        pytest.skip("Unable to read orchestrator health; skipping live extended-data-plane tests.")
    return health_payload


def _require_optional_adapters_enabled() -> None:
    health_payload = _require_live_stack()
    if not health_payload.get("neo4j_url") or not health_payload.get("object_storage_endpoint"):
        pytest.skip(
            "Optional adapter URLs not configured; enable NEO4J_ENABLED/OBJECT_STORAGE_ENABLED."
        )
    if (
        health_payload.get("neo4j_ready") is not True
        or health_payload.get("object_storage_ready") is not True
    ):
        pytest.skip(
            "Optional adapters are not ready; start compose with --profile extended-data-plane and "
            "enable NEO4J_ENABLED/OBJECT_STORAGE_ENABLED."
        )


def _wait_for_adapter_ready(*, expect_ready: bool, timeout_seconds: float = 120.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status, payload = _request_json("GET", f"{ORCHESTRATOR_BASE_URL}/health")
        if status == 200 and isinstance(payload, dict):
            neo4j_ready = payload.get("neo4j_ready") is True
            object_storage_ready = payload.get("object_storage_ready") is True
            both_ready = neo4j_ready and object_storage_ready
            if expect_ready and both_ready:
                return
            if not expect_ready and (not neo4j_ready or not object_storage_ready):
                return
        time.sleep(1.0)

    expectation = "ready" if expect_ready else "not-ready"
    raise AssertionError(f"Timed out waiting for optional adapters to become {expectation}.")


def _post_internal(path: str, payload: dict[str, Any]) -> tuple[int, Any]:
    return _request_json(
        "POST",
        f"{ORCHESTRATOR_BASE_URL}{path}",
        payload=payload,
        headers={"x-api-key": INTERNAL_SERVICE_API_KEY},
    )


def _create_live_mission() -> str:
    mission_key = f"live-ext-{uuid.uuid4().hex}"
    status, payload = _request_json(
        "POST",
        f"{GATEWAY_BASE_URL}/v1/missions",
        payload={
            "prompt": "Live optional data-plane qualification mission.",
            "requested_target_language": "python",
            "metadata": {"source": "live-extended-data-plane-test"},
        },
        headers={"Idempotency-Key": mission_key},
    )
    assert status in {200, 201}
    assert isinstance(payload, dict)
    mission_id = payload.get("mission_id")
    assert isinstance(mission_id, str) and mission_id
    return mission_id


def _wait_for_mission_record(mission_id: str, timeout_seconds: float = 45.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status, payload = _request_json("GET", f"{GATEWAY_BASE_URL}/v1/missions/{mission_id}")
        if status == 200 and isinstance(payload, dict):
            return
        time.sleep(1.0)
    raise AssertionError(f"Mission {mission_id} was not available via gateway within timeout.")


def _wait_for_mirrors(mission_id: str, knowledge_id: str, audit_id: str) -> None:
    deadline = time.time() + 60.0
    while time.time() < deadline:
        graph_status, graph_payload = _request_json(
            "GET",
            f"{GATEWAY_BASE_URL}/v1/missions/{mission_id}/knowledge-graph?limit=100",
        )
        artifacts_status, artifacts_payload = _request_json(
            "GET",
            f"{GATEWAY_BASE_URL}/v1/missions/{mission_id}/audit-artifacts?limit=100",
        )
        if graph_status == 200 and artifacts_status == 200:
            graph_records = graph_payload if isinstance(graph_payload, list) else []
            artifact_records = artifacts_payload if isinstance(artifacts_payload, list) else []
            has_knowledge = any(
                isinstance(record, dict)
                and isinstance(record.get("target_properties"), dict)
                and record["target_properties"].get("knowledge_id") == knowledge_id
                for record in graph_records
            )
            has_artifact = any(
                isinstance(record, dict)
                and str(record.get("key", "")).endswith(f"/{audit_id}.json")
                for record in artifact_records
            )
            if has_knowledge and has_artifact:
                return
        time.sleep(1.0)
    raise AssertionError("Optional data-plane mirror artifacts were not observed within timeout.")


def test_live_optional_data_plane_roundtrip() -> None:
    _require_optional_adapters_enabled()

    mission_id = _create_live_mission()
    _wait_for_mission_record(mission_id)
    knowledge_id = f"k-{uuid.uuid4().hex[:10]}"
    audit_id = f"a-{uuid.uuid4().hex[:10]}"
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    knowledge_status, _ = _post_internal(
        "/internal/knowledge",
        {
            "mission_id": mission_id,
            "knowledge_id": knowledge_id,
            "content": {"summary": "live optional adapter test"},
            "created_at": created_at,
        },
    )
    assert knowledge_status == 200

    audit_status, _ = _post_internal(
        "/internal/audit-reports",
        {
            "mission_id": mission_id,
            "audit_id": audit_id,
            "status": "FAILED",
            "report": {"summary": "live optional adapter test"},
            "created_at": created_at,
        },
    )
    assert audit_status == 200

    _wait_for_mirrors(mission_id, knowledge_id, audit_id)


def test_live_optional_data_plane_disruption_recovery() -> None:
    if not RUN_DISRUPTION_TESTS:
        pytest.skip("Set LIVE_ENABLE_DISRUPTION_TESTS=true to run disruption qualification.")

    _require_optional_adapters_enabled()

    stopped = False
    try:
        _compose_run("stop", "neo4j", "minio")
        stopped = True
        _wait_for_adapter_ready(expect_ready=False, timeout_seconds=90.0)

        mission_id = _create_live_mission()
        _wait_for_mission_record(mission_id)
        created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        failure_knowledge_id = f"k-down-{uuid.uuid4().hex[:8]}"
        failure_audit_id = f"a-down-{uuid.uuid4().hex[:8]}"

        knowledge_status, _ = _post_internal(
            "/internal/knowledge",
            {
                "mission_id": mission_id,
                "knowledge_id": failure_knowledge_id,
                "content": {"summary": "mirror write should fail-open during outage"},
                "created_at": created_at,
            },
        )
        audit_status, _ = _post_internal(
            "/internal/audit-reports",
            {
                "mission_id": mission_id,
                "audit_id": failure_audit_id,
                "status": "FAILED",
                "report": {"summary": "mirror write should fail-open during outage"},
                "created_at": created_at,
            },
        )
        assert knowledge_status == 200
        assert audit_status == 200
    finally:
        if stopped:
            _compose_run("start", "neo4j", "minio")

    _wait_for_adapter_ready(expect_ready=True, timeout_seconds=180.0)

    mission_id = _create_live_mission()
    _wait_for_mission_record(mission_id)
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    recovery_knowledge_id = f"k-up-{uuid.uuid4().hex[:8]}"
    recovery_audit_id = f"a-up-{uuid.uuid4().hex[:8]}"

    knowledge_status, _ = _post_internal(
        "/internal/knowledge",
        {
            "mission_id": mission_id,
            "knowledge_id": recovery_knowledge_id,
            "content": {"summary": "mirror write should recover after outage"},
            "created_at": created_at,
        },
    )
    audit_status, _ = _post_internal(
        "/internal/audit-reports",
        {
            "mission_id": mission_id,
            "audit_id": recovery_audit_id,
            "status": "FAILED",
            "report": {"summary": "mirror write should recover after outage"},
            "created_at": created_at,
        },
    )
    assert knowledge_status == 200
    assert audit_status == 200
    _wait_for_mirrors(mission_id, recovery_knowledge_id, recovery_audit_id)
