from __future__ import annotations

import logging
import time

from prometheus_client import REGISTRY, Counter, Gauge, Histogram

LOGGER = logging.getLogger(__name__)


def _get_metric(name: str):
    return REGISTRY._names_to_collectors.get(name)

# Using a helper to avoid "Duplicated timeseries" error in tests
REQUEST_COUNTER = _get_metric("orchestrator_http_requests_total") or Counter(
    "orchestrator_http_requests_total",
    "Total HTTP requests served by orchestrator",
    ("method", "path", "status_code"),
)

REQUEST_LATENCY = _get_metric("orchestrator_http_request_duration_seconds") or Histogram(
    "orchestrator_http_request_duration_seconds",
    "HTTP request latency in seconds for orchestrator",
    ("method", "path"),
)

LLM_FALLBACK_TOTAL = _get_metric("llm_fallback_total") or Counter(
    "llm_fallback_total",
    "Count of silent LLM fallbacks",
    ("agent_id", "reason"),
)

# ---------------------------------------------------------------------------
# Mission lifecycle metrics
#
# The core mission workflow (queued → running → verified → complete/failed)
# previously had zero Prometheus instrumentation, leaving stuck missions
# undetectable. These metrics are wired into ``insert_mission_event`` (the
# authoritative previous→new transition record) via ``record_mission_transition``.
# ---------------------------------------------------------------------------

MISSION_TRANSITIONS_TOTAL = _get_metric("factory_mission_transitions_total") or Counter(
    "factory_mission_transitions_total",
    "Total mission state transitions",
    ("from_state", "to_state", "engine"),  # engine = v2 | langgraph | legacy
)

MISSION_OUTCOMES_TOTAL = _get_metric("factory_mission_outcomes_total") or Counter(
    "factory_mission_outcomes_total",
    "Total mission terminal outcomes",
    ("outcome",),  # complete | failed | timeout
)

MISSIONS_ACTIVE = _get_metric("factory_missions_active") or Gauge(
    "factory_missions_active",
    "Currently active missions by state",
    ("state",),  # QUEUED | RUNNING | VERIFIED
)

MISSION_DURATION_SECONDS = _get_metric("factory_mission_duration_seconds") or Histogram(
    "factory_mission_duration_seconds",
    "Mission duration from intake to terminal state",
    ("outcome",),  # complete | failed
    buckets=(30, 60, 120, 300, 600, 1200, 1800, 3600),
)

# Unix timestamp of the most recent mission transition. Consumed by the
# MissionStuckInRunning alert to detect missions wedged in RUNNING.
MISSION_LAST_TRANSITION_TIMESTAMP = (
    _get_metric("factory_mission_last_transition_timestamp")
    or Gauge(
        "factory_mission_last_transition_timestamp",
        "Unix timestamp of the most recent mission state transition",
    )
)

# Active-gauge states we track explicitly. Other intermediate states are not
# surfaced on the gauge to keep cardinality bounded and the alert query simple.
_ACTIVE_GAUGE_STATES = {"QUEUED", "RUNNING", "VERIFIED"}
_TERMINAL_STATES = {"COMPLETE", "FAILED"}


def record_mission_transition(
    *,
    from_state: str | None,
    to_state: str,
    engine: str,
    started_at_epoch: float | None = None,
) -> None:
    """Record Prometheus metrics for a single mission state transition.

    Never raises — observability must not break the mission pipeline. Called
    from ``insert_mission_event`` where authoritative previous→new state is known.

    ``from_state``/``to_state`` are the upper-case ``MissionState`` values.
    ``engine`` is ``v2`` | ``langgraph`` | ``legacy``.
    ``started_at_epoch`` is the mission's intake/created Unix timestamp, used to
    compute duration when reaching a terminal state.
    """
    try:
        from_label = from_state or "none"
        MISSION_TRANSITIONS_TOTAL.labels(
            from_state=from_label, to_state=to_state, engine=engine
        ).inc()
        MISSION_LAST_TRANSITION_TIMESTAMP.set(time.time())

        # Maintain the active gauge: decrement the state being left, increment
        # the state being entered. Only states in _ACTIVE_GAUGE_STATES count.
        if from_state in _ACTIVE_GAUGE_STATES and from_state != to_state:
            MISSIONS_ACTIVE.labels(state=from_state).dec()
        if to_state in _ACTIVE_GAUGE_STATES and from_state != to_state:
            MISSIONS_ACTIVE.labels(state=to_state).inc()

        if to_state in _TERMINAL_STATES:
            outcome = "complete" if to_state == "COMPLETE" else "failed"
            MISSION_OUTCOMES_TOTAL.labels(outcome=outcome).inc()
            if started_at_epoch is not None:
                duration = max(0.0, time.time() - started_at_epoch)
                MISSION_DURATION_SECONDS.labels(outcome=outcome).observe(duration)
    except Exception:  # noqa: BLE001
        LOGGER.warning("failed to record mission transition metric", exc_info=True)
