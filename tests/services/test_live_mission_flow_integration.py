import json
import os
import time
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest
from live_stack_auth import (
    http_timeout_seconds,
    probe_timeout_seconds,
    resolve_internal_service_api_key,
    skip_or_fail,
)

# 127.0.0.1, not localhost: compose binds these ports on IPv4 only
# (ORCHESTRATOR_HOST_BIND defaults to 127.0.0.1), while `localhost` resolves
# ::1 first on Windows and pays a fallback penalty -- measured at 2.09s vs
# 0.02s. That inflated the first request past the old 4s timeout, whose
# OSError the probe read as "stack unreachable", producing a green run that
# verified nothing.
GATEWAY_BASE_URL = os.getenv("LIVE_GATEWAY_URL", "http://127.0.0.1:8100").rstrip("/")
ORCHESTRATOR_BASE_URL = os.getenv("LIVE_ORCHESTRATOR_URL", "http://127.0.0.1:8101").rstrip("/")
# Shared with the extended suite so the two cannot drift again; the 4.0s that
# used to live here made this suite skip against a healthy stack.
HTTP_TIMEOUT_SECONDS = http_timeout_seconds()
PROBE_TIMEOUT_SECONDS = probe_timeout_seconds()
# The delegation chain involves several real LLM calls, so this is minutes, not
# seconds. It covers PM intake through specialist assignment -- not a full build.
CHAIN_TIMEOUT_SECONDS = float(os.getenv("LIVE_MISSION_CHAIN_TIMEOUT_SECONDS", "300.0"))
LIVE_STACK_ENABLED = (
    os.getenv("LIVE_STACK_ENABLED", "").strip().lower()
    in {"1", "true", "yes", "on"}
)
INTERNAL_SERVICE_API_KEY = resolve_internal_service_api_key()


def _request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> tuple[int, Any]:
    request_headers = {"Accept": "application/json"}
    # Authenticate every request from one place. The gateway runs
    # AUTH_MODE=api_key and every /v1/* route calls _require_reader_access,
    # which 401s without an x-api-key carrying the `read` role. Injecting it
    # per-call is what let mission creation go out bare in the sibling suite.
    # /readyz and /health ignore the header harmlessly.
    if INTERNAL_SERVICE_API_KEY:
        request_headers["x-api-key"] = INTERNAL_SERVICE_API_KEY
    if headers:
        request_headers.update(headers)
    body: bytes | None = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    request = Request(url, data=body, method=method, headers=request_headers)
    with urlopen(request, timeout=timeout or HTTP_TIMEOUT_SECONDS) as response:
        status = int(response.status)
        raw = response.read().decode("utf-8")
    if not raw:
        return status, None
    return status, json.loads(raw)


def _require_live_stack() -> None:
    if not LIVE_STACK_ENABLED:
        pytest.skip("Live stack tests are opt-in; set LIVE_STACK_ENABLED=1 to run them.")
    if not INTERNAL_SERVICE_API_KEY:
        skip_or_fail(
            "No gateway credential resolved. Set LIVE_INTERNAL_SERVICE_API_KEY (or "
            "INTERNAL_SERVICE_API_KEY, or LIVE_ENV_FILE) to the value the running stack "
            "was started with."
        )
    try:
        gateway_status, gateway_ready = _request_json(
            "GET", f"{GATEWAY_BASE_URL}/readyz", timeout=PROBE_TIMEOUT_SECONDS
        )
        orchestrator_status, orchestrator_ready = _request_json(
            "GET", f"{ORCHESTRATOR_BASE_URL}/readyz", timeout=PROBE_TIMEOUT_SECONDS
        )
    except (URLError, TimeoutError, OSError) as exc:
        skip_or_fail(f"Live stack not reachable ({type(exc).__name__}).")

    if (
        gateway_status != 200
        or not isinstance(gateway_ready, dict)
        or not gateway_ready.get("ready")
    ):
        skip_or_fail("Gateway is not ready.")
    if (
        orchestrator_status != 200
        or not isinstance(orchestrator_ready, dict)
        or not orchestrator_ready.get("ready")
    ):
        skip_or_fail("Orchestrator is not ready.")


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
    assert create_status in {200, 201}, (
        f"mission creation failed with HTTP {create_status}: {created!r}"
    )
    assert isinstance(created, dict)
    mission_id = created.get("mission_id")
    assert isinstance(mission_id, str) and mission_id

    deadline = time.time() + 45
    observed_states: set[str] = set()
    latest_events: list[dict[str, Any]] = []

    while time.time() < deadline:
        try:
            mission_status, mission_payload = _request_json(
                "GET",
                f"{GATEWAY_BASE_URL}/v1/missions/{mission_id}",
            )
        except HTTPError as exc:
            if exc.code == 404:
                time.sleep(1.0)
                continue
            raise
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
            # Deliberately concrete. The intake phase holds any mission whose PM
            # feature contract scores ambiguity >= 0.7 (mission_flow_v2/
            # phases_intake.py) and parks it in CLARIFYING for an operator. A
            # vague one-liner never reaches the delegation chain this test is
            # about, so the prompt names the input, the output, and the
            # behaviour precisely enough to clear that gate.
            "prompt": (
                "Write a Python command-line tool named wordcount.py that reads a UTF-8 text "
                "file given as its first positional argument and prints each distinct word and "
                "its occurrence count, one 'word count' pair per line, sorted by descending "
                "count and then alphabetically. Words are sequences of letters and digits "
                "compared case-insensitively. Print nothing for an empty file. Exit with "
                "status 1 and a message on stderr if the file does not exist."
            ),
            "requested_target_language": "python",
            "metadata": {"source": "live-chain-artifact-test"},
        },
        headers={"Idempotency-Key": mission_key},
    )
    assert create_status in {200, 201}, (
        f"mission creation failed with HTTP {create_status}: {created!r}"
    )
    assert isinstance(created, dict)
    mission_id = created.get("mission_id")
    assert isinstance(mission_id, str) and mission_id

    # This test inspects the delegation chain and the artifacts that exist once a
    # specialist is assigned -- none of which require the mission to finish. It
    # used to wait for COMPLETE purely as a proxy for "enough time has passed",
    # which made a 60s budget stand in for a full build and reported every
    # unrelated stall as "expected COMPLETE". Waiting for the four chain events
    # themselves is both faster and more precise about what actually failed.
    required_chain_events = {
        "MISSION_PM_INTAKE",
        "MISSION_CEO_DELEGATED",
        "MISSION_POD_MANAGER_ASSIGNED",
        "MISSION_SPECIALIST_ASSIGNED",
    }
    deadline = time.time() + CHAIN_TIMEOUT_SECONDS
    chain_event_types: set[str] = set()
    observed_state = ""
    clarification_sent = False

    while time.time() < deadline:
        try:
            _, mission_payload = _request_json(
                "GET",
                f"{GATEWAY_BASE_URL}/v1/missions/{mission_id}",
            )
        except HTTPError as exc:
            if exc.code == 404:
                time.sleep(1.0)
                continue
            raise
        if isinstance(mission_payload, dict):
            observed_state = str(mission_payload.get("state", "")).upper()

        # CLARIFYING is a deliberate operator hold, not a failure: the PM raises
        # clarifying questions with recommended defaults for almost any prompt
        # (this one scored the maximum 1.0 while still asking only about output
        # separator and ASCII-vs-Unicode). Mission Control answers it with a
        # "proceed with defaults" action, so an unattended test drives the same
        # documented path rather than hunting for a prompt the PM won't question.
        if observed_state == "CLARIFYING" and not clarification_sent:
            clarify_status, clarify_payload = _request_json(
                "POST",
                f"{ORCHESTRATOR_BASE_URL}/missions/{mission_id}/clarify",
                payload={
                    "clarification": (
                        "Proceed with the recommended defaults for every open question: "
                        "space-separated lowercase 'word count' pairs, one per line, and "
                        "ASCII [a-zA-Z0-9]+ word extraction."
                    )
                },
            )
            assert clarify_status == 200, (
                f"failed to resolve the CLARIFYING hold for mission {mission_id}: "
                f"HTTP {clarify_status}: {clarify_payload!r}"
            )
            clarification_sent = True
            time.sleep(2.0)
            continue

        # A second hold means the clarification did not unblock intake -- keep
        # waiting and the only signal at timeout would be "no chain events",
        # which hides the real cause.
        if observed_state == "CLARIFYING":
            raise AssertionError(
                f"Mission {mission_id} returned to CLARIFYING after a clarification was "
                "accepted, so the delegation chain never runs. The PM re-raised questions "
                "rather than proceeding with the supplied defaults."
            )

        chain_status, chain_payload = _request_json(
            "GET",
            f"{GATEWAY_BASE_URL}/v1/missions/{mission_id}/chain-trace",
        )
        if chain_status == 200 and isinstance(chain_payload, dict):
            chain_event_types = {
                str(event.get("event_type", "")).upper()
                for event in chain_payload.get("events", [])
                if isinstance(event, dict)
            }
            if required_chain_events <= chain_event_types:
                break

        if observed_state == "FAILED":
            raise AssertionError(
                f"Mission {mission_id} reached FAILED before completing the delegation chain. "
                f"Chain events observed: {sorted(chain_event_types)}"
            )
        time.sleep(2.0)

    missing_chain_events = required_chain_events - chain_event_types
    assert not missing_chain_events, (
        f"Mission {mission_id} did not produce the full delegation chain within "
        f"{CHAIN_TIMEOUT_SECONDS:.0f}s (state={observed_state or 'unknown'}). "
        f"Missing: {sorted(missing_chain_events)}; observed: {sorted(chain_event_types)}"
    )

    # MISSION_POD_MANAGER_ASSIGNED asserts a pod manager was assigned, so the
    # assignment must be queryable. The orchestrator now writes a provisional
    # record as it emits that event, and a pod worker's claim supersedes it, so
    # this holds on both paths -- previously the record existed only when a
    # worker happened to claim the mission, and a BUILD_NEW mission (nothing to
    # extract) reached VERIFIED with the event emitted and a 404 here.
    # urlopen raises on 4xx, so catch it here -- the bare traceback would hide
    # which of the two records is missing, which is the whole point of the check.
    try:
        assignment_status, assignment_payload = _request_json(
            "GET",
            f"{GATEWAY_BASE_URL}/v1/missions/{mission_id}/pod-assignment",
        )
    except HTTPError as exc:
        raise AssertionError(
            f"mission {mission_id} emitted MISSION_POD_MANAGER_ASSIGNED but "
            f"/pod-assignment returned HTTP {exc.code}. The chain event and the "
            "assignment record must be written together."
        ) from exc
    assert assignment_status == 200, (
        f"mission {mission_id} emitted MISSION_POD_MANAGER_ASSIGNED but "
        f"/pod-assignment returned HTTP {assignment_status}: {assignment_payload!r}"
    )
    assert isinstance(assignment_payload, dict) and assignment_payload.get("pod_name"), (
        f"pod assignment for mission {mission_id} names no pod: {assignment_payload!r}"
    )
    assigned_by = str(
        (assignment_payload.get("metadata") or {}).get("assigned_by") or ""
    ).lower()
    assert assigned_by in {"orchestrator", "pod-worker"}, (
        f"pod assignment for mission {mission_id} has an unrecognised writer "
        f"{assigned_by!r}: {assignment_payload!r}"
    )

    # LogicNodes are the *extraction* artifact and have only source-reading
    # writers, so a BUILD_NEW mission legitimately has none -- it synthesises its
    # logic from the mission contract instead. Asserting a non-empty set here
    # would only be testing whether a pod worker with source to chew on happened
    # to run. Assert the endpoint is healthy and the shape is right.
    logicnodes_status, logicnodes_payload = _request_json(
        "GET",
        f"{GATEWAY_BASE_URL}/v1/missions/{mission_id}/logicnodes?limit=50",
    )
    assert logicnodes_status == 200, (
        f"logicnodes endpoint failed for mission {mission_id}: "
        f"HTTP {logicnodes_status}: {logicnodes_payload!r}"
    )
    assert isinstance(logicnodes_payload, list), (
        f"expected a logicnode list for mission {mission_id}, "
        f"got {type(logicnodes_payload).__name__}"
    )

    # Packaging happens well after the delegation chain closes, so this needs its
    # own wait -- the chain loop above exits at SPECIALIST_ASSIGNED, several
    # phases before MISSION_BUILD_ARTIFACT_PACKAGED.
    artifacts_payload: Any = []
    while time.time() < deadline:
        artifacts_status, artifacts_payload = _request_json(
            "GET",
            f"{GATEWAY_BASE_URL}/v1/missions/{mission_id}/build-artifacts?limit=20",
        )
        assert artifacts_status == 200
        if isinstance(artifacts_payload, list) and artifacts_payload:
            break
        try:
            _, mission_payload = _request_json(
                "GET", f"{GATEWAY_BASE_URL}/v1/missions/{mission_id}"
            )
        except HTTPError:
            mission_payload = None
        if isinstance(mission_payload, dict):
            observed_state = str(mission_payload.get("state", "")).upper()
        if observed_state == "FAILED":
            break
        time.sleep(3.0)

    assert isinstance(artifacts_payload, list), (
        f"expected a build-artifact list, got {type(artifacts_payload).__name__}"
    )
    assert artifacts_payload, (
        f"mission {mission_id} produced no build artifacts within "
        f"{CHAIN_TIMEOUT_SECONDS:.0f}s despite completing the delegation chain "
        f"(state={observed_state or 'unknown'})"
    )
    assert any(
        isinstance(record, dict) and int(record.get("size_bytes") or 0) > 0
        for record in artifacts_payload
    ), f"every build artifact for mission {mission_id} is empty: {artifacts_payload!r}"
