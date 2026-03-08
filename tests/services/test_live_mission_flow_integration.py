import json
import os
import time
import uuid
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import pytest

GATEWAY_BASE_URL = os.getenv("LIVE_GATEWAY_URL", "http://localhost:8100").rstrip("/")
ORCHESTRATOR_BASE_URL = os.getenv("LIVE_ORCHESTRATOR_URL", "http://localhost:8101").rstrip("/")
HTTP_TIMEOUT_SECONDS = float(os.getenv("LIVE_HTTP_TIMEOUT_SECONDS", "4.0"))


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
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        status = int(response.status)
        raw = response.read().decode("utf-8")
    if not raw:
        return status, None
    return status, json.loads(raw)


def _require_live_stack() -> None:
    try:
        gateway_status, gateway_ready = _request_json("GET", f"{GATEWAY_BASE_URL}/readyz")
        orchestrator_status, orchestrator_ready = _request_json(
            "GET", f"{ORCHESTRATOR_BASE_URL}/readyz"
        )
    except (URLError, TimeoutError, OSError):
        pytest.skip("Live stack not reachable; skipping live integration tests.")

    if (
        gateway_status != 200
        or not isinstance(gateway_ready, dict)
        or not gateway_ready.get("ready")
    ):
        pytest.skip("Gateway is not ready; skipping live integration tests.")
    if (
        orchestrator_status != 200
        or not isinstance(orchestrator_ready, dict)
        or not orchestrator_ready.get("ready")
    ):
        pytest.skip("Orchestrator is not ready; skipping live integration tests.")


def test_live_runtime_reports_redis_and_db_ready() -> None:
    _require_live_stack()

    gateway_status, gateway_health = _request_json("GET", f"{GATEWAY_BASE_URL}/health")
    orchestrator_status, orchestrator_health = _request_json(
        "GET",
        f"{ORCHESTRATOR_BASE_URL}/health",
    )

    assert gateway_status == 200
    assert orchestrator_status == 200
    assert gateway_health["redis_healthy"] is True
    assert gateway_health["orchestrator_healthy"] is True
    assert orchestrator_health["redis_healthy"] is True
    assert orchestrator_health["db_ready"] is True


def test_live_mission_intake_and_state_flow() -> None:
    _require_live_stack()

    mission_key = f"live-int-{uuid.uuid4().hex}"
    create_status, created = _request_json(
        "POST",
        f"{GATEWAY_BASE_URL}/v1/missions",
        payload={
            "prompt": "Live integration test mission for intake/state verification.",
            "requested_target_language": "python",
            "metadata": {"source": "live-integration-test"},
        },
        headers={"Idempotency-Key": mission_key},
    )
    assert create_status == 200
    assert isinstance(created, dict)
    mission_id = created.get("mission_id")
    assert isinstance(mission_id, str) and mission_id

    deadline = time.time() + 45
    observed_states: set[str] = set()
    latest_events: list[dict[str, Any]] = []

    while time.time() < deadline:
        mission_status, mission_payload = _request_json(
            "GET",
            f"{GATEWAY_BASE_URL}/v1/missions/{mission_id}",
        )
        assert mission_status == 200
        assert isinstance(mission_payload, dict)

        state = mission_payload.get("state")
        if isinstance(state, str) and state:
            observed_states.add(state)

        events_status, events_payload = _request_json(
            "GET",
            f"{GATEWAY_BASE_URL}/v1/missions/{mission_id}/events?limit=20",
        )
        assert events_status == 200
        if isinstance(events_payload, list) and events_payload:
            latest_events = [event for event in events_payload if isinstance(event, dict)]

        if latest_events and observed_states.intersection(
            {"RUNNING", "VERIFYING", "COMPLETE", "VERIFIED", "FAILED"}
        ):
            break

        time.sleep(1.0)

    assert observed_states, "no mission states observed during polling window"
    assert latest_events, "no mission events observed for live mission flow"
    assert any(isinstance(event.get("event_type"), str) for event in latest_events)


def test_live_mission_chain_and_artifact_integrity() -> None:
    _require_live_stack()

    mission_key = f"live-chain-{uuid.uuid4().hex}"
    create_status, created = _request_json(
        "POST",
        f"{GATEWAY_BASE_URL}/v1/missions",
        payload={
            "prompt": "Live integration mission for chain and artifact integrity verification.",
            "requested_target_language": "python",
            "metadata": {"source": "live-chain-artifact-test"},
        },
        headers={"Idempotency-Key": mission_key},
    )
    assert create_status == 200
    assert isinstance(created, dict)
    mission_id = created.get("mission_id")
    assert isinstance(mission_id, str) and mission_id

    deadline = time.time() + 60
    final_state = ""
    while time.time() < deadline:
        mission_status, mission_payload = _request_json(
            "GET",
            f"{GATEWAY_BASE_URL}/v1/missions/{mission_id}",
        )
        assert mission_status == 200
        assert isinstance(mission_payload, dict)
        final_state = str(mission_payload.get("state", "")).upper()
        if final_state in {"COMPLETE", "FAILED"}:
            break
        time.sleep(1.0)

    assert final_state == "COMPLETE", f"expected mission COMPLETE, got {final_state or 'unknown'}"

    chain_status, chain_payload = _request_json(
        "GET",
        f"{GATEWAY_BASE_URL}/v1/missions/{mission_id}/chain-trace",
    )
    assignment_status, assignment_payload = _request_json(
        "GET",
        f"{GATEWAY_BASE_URL}/v1/missions/{mission_id}/pod-assignment",
    )
    logicnodes_status, logicnodes_payload = _request_json(
        "GET",
        f"{GATEWAY_BASE_URL}/v1/missions/{mission_id}/logicnodes?limit=50",
    )
    assert chain_status == 200
    assert assignment_status == 200
    assert logicnodes_status == 200

    assert isinstance(chain_payload, dict)
    events = chain_payload.get("events", [])
    assert isinstance(events, list) and events
    chain_event_types = {
        str(event.get("event_type", "")).upper()
        for event in events
        if isinstance(event, dict)
    }
    required_chain_events = {
        "MISSION_PM_INTAKE",
        "MISSION_CEO_DELEGATED",
        "MISSION_POD_MANAGER_ASSIGNED",
        "MISSION_SPECIALIST_ASSIGNED",
    }
    missing_chain_events = required_chain_events - chain_event_types
    assert not missing_chain_events, f"missing chain events: {sorted(missing_chain_events)}"

    assert isinstance(assignment_payload, dict)
    assert str(assignment_payload.get("pod_name", "")).strip(), "missing pod assignment artifact"

    assert isinstance(logicnodes_payload, list)
    assert len(logicnodes_payload) > 0, "missing logicnode artifacts"
