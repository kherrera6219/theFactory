"""
mission_flow_v2.py — 11-phase Mission Flow v2 lifecycle engine.

Provides the expanded state-machine that replaces v1.1's coarse
``QUEUED → RUNNING → VERIFIED → COMPLETE`` with 11 granular phases.

Gated behind ``MISSION_FLOW_V2_ENABLED=true``.  When disabled the
legacy/LangGraph v1.1 engines handle mission progression as before.

Phase order
-----------
1. INTAKE          (gateway receipt)
2. QUEUED          (persisted + queued)
3. PM_INTAKE       (PM intent translation)
4. CEO_DELEGATED   (CEO delegation plan)
5. POD_ASSIGNED    (pod manager assigned)
6. SPECIALIST_ASSIGNED (specialist assigned)
7. RUNNING         (extraction active)
8. GATING          (QC gating pass)
9. FUSION          (artifact fusion)
10. VERIFIED       (verification gate)
11. COMPLETE       (delivered)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from . import storage
from .mission_flow import (
    CEO_AGENT_ID,
    append_chain_event,
    with_chain_defaults,
)
from .models import MissionState

LOGGER = logging.getLogger(__name__)

# ------------------------------------------------------------------
# V2 transition table (ordered)
# ------------------------------------------------------------------

V2_TRANSITIONS: tuple[tuple[MissionState, MissionState, str], ...] = (
    (MissionState.queued, MissionState.pm_intake, "MISSION_PM_INTAKE"),
    (MissionState.pm_intake, MissionState.ceo_delegated, "MISSION_CEO_DELEGATED"),
    (
        MissionState.ceo_delegated,
        MissionState.pod_assigned,
        "MISSION_POD_MANAGER_ASSIGNED",
    ),
    (
        MissionState.pod_assigned,
        MissionState.specialist_assigned,
        "MISSION_SPECIALIST_ASSIGNED",
    ),
    (
        MissionState.specialist_assigned,
        MissionState.running,
        "MISSION_RUNNING",
    ),
    (MissionState.running, MissionState.gating, "MISSION_GATING"),
    (MissionState.gating, MissionState.fusion, "MISSION_FUSION"),
    (MissionState.fusion, MissionState.verified, "MISSION_VERIFIED"),
    (MissionState.verified, MissionState.complete, "MISSION_COMPLETE"),
)

V1_TRANSITIONS: tuple[tuple[MissionState, MissionState, str], ...] = (
    (MissionState.queued, MissionState.running, "MISSION_RUNNING"),
    (MissionState.running, MissionState.verified, "MISSION_VERIFIED"),
    (MissionState.verified, MissionState.complete, "MISSION_COMPLETE"),
)

# Ordered list of all 11 v2 phases (for deterministic progression).
V2_PHASE_ORDER: tuple[MissionState, ...] = (
    MissionState.intake,
    MissionState.queued,
    MissionState.pm_intake,
    MissionState.ceo_delegated,
    MissionState.pod_assigned,
    MissionState.specialist_assigned,
    MissionState.running,
    MissionState.gating,
    MissionState.fusion,
    MissionState.verified,
    MissionState.complete,
)

# Maps v2 event types to the phases they represent.
V2_EVENT_TO_PHASE: dict[str, MissionState] = {
    "MISSION_INTAKE": MissionState.intake,
    "MISSION_QUEUED": MissionState.queued,
    "MISSION_PM_INTAKE": MissionState.pm_intake,
    "MISSION_CEO_DELEGATED": MissionState.ceo_delegated,
    "MISSION_POD_MANAGER_ASSIGNED": MissionState.pod_assigned,
    "MISSION_SPECIALIST_ASSIGNED": MissionState.specialist_assigned,
    "MISSION_RUNNING": MissionState.running,
    "MISSION_GATING": MissionState.gating,
    "MISSION_FUSION": MissionState.fusion,
    "MISSION_VERIFIED": MissionState.verified,
    "MISSION_COMPLETE": MissionState.complete,
}


# ------------------------------------------------------------------
# Backward-compatible v1.1 mapping
# ------------------------------------------------------------------

_V2_TO_V1_MAP: dict[MissionState, MissionState] = {
    MissionState.intake: MissionState.intake,
    MissionState.queued: MissionState.queued,
    MissionState.pm_intake: MissionState.queued,
    MissionState.ceo_delegated: MissionState.queued,
    MissionState.pod_assigned: MissionState.queued,
    MissionState.specialist_assigned: MissionState.queued,
    MissionState.running: MissionState.running,
    MissionState.gating: MissionState.running,
    MissionState.fusion: MissionState.running,
    MissionState.verified: MissionState.verified,
    MissionState.complete: MissionState.complete,
    MissionState.failed: MissionState.failed,
}


def v2_map_state_to_v1(state: MissionState) -> MissionState:
    """Map a v2 state to its canonical v1.1 equivalent.

    This allows APIs to expose backward-compatible state values
    when the consumer does not understand v2 microstates.
    """
    return _V2_TO_V1_MAP.get(state, state)


def v2_phase_index(state: MissionState) -> int:
    """Return the zero-based phase index for a v2 state.

    Returns -1 for states not in the v2 phase model (e.g. ``FAILED``).
    """
    try:
        return V2_PHASE_ORDER.index(state)
    except ValueError:
        return -1


# ------------------------------------------------------------------
# V2 lifecycle driver (legacy path, no LangGraph)
# ------------------------------------------------------------------


async def advance_mission_lifecycle_v2(
    *,
    app: Any,
    mission_id: str,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    prepare_chain_fn: Any,
    completion_check_fn: Any,
) -> None:
    """Drive a mission through all 11 v2 phases.

    This is the legacy (non-LangGraph) v2 driver. It mirrors the
    structure of ``runtime.advance_mission_lifecycle`` but uses the
    full v2 transition table.

    Parameters
    ----------
    app : FastAPI
        Application instance with ``app.state`` references.
    mission_id : str
        Mission to advance.
    settings : Settings
        Application settings (must have ``mission_flow_v2_enabled=True``).
    validator : EnvelopeValidator
        Protocol envelope validator.
    emit_state_event_fn : callable
        Async function to emit state events to Redis streams.
    prepare_chain_fn : callable
        Async function that prepares the mission chain metadata
        (PM intake, CEO delegation, pod/specialist assignment).
    completion_check_fn : callable
        Async function ``(settings, mission) → (bool, dict)``
        that checks whether completion artifacts are ready.
    """

    for expected_state, new_state, event_type in V2_TRANSITIONS:
        # Prepare chain metadata on the first v2 transition
        if (
            expected_state == MissionState.queued
            and new_state == MissionState.pm_intake
        ):
            prepared = await prepare_chain_fn(
                app=app,
                settings=settings,
                validator=validator,
                mission_id=mission_id,
            )
            if not prepared:
                return

        # Completion gate before COMPLETE
        if (
            expected_state == MissionState.verified
            and new_state == MissionState.complete
        ):
            mission = await asyncio.to_thread(
                storage.fetch_mission, settings, mission_id
            )
            if mission is None:
                return
            ready, details = await completion_check_fn(
                settings=settings, mission=mission
            )
            if not ready:
                metadata = with_chain_defaults(
                    mission.metadata,
                    mission.requested_target_language,
                )
                append_chain_event(
                    metadata,
                    event_type="MISSION_COMPLETION_BLOCKED",
                    agent_id=CEO_AGENT_ID,
                    details=details,
                )
                await asyncio.to_thread(
                    storage.update_mission_metadata,
                    settings,
                    mission_id,
                    metadata,
                )
                await asyncio.to_thread(
                    storage.insert_mission_event,
                    settings,
                    mission_id,
                    MissionState.verified,
                    MissionState.verified,
                    "MISSION_COMPLETION_BLOCKED",
                )
                return

        await asyncio.sleep(settings.transition_step_seconds)

        record = await asyncio.to_thread(
            storage.transition_mission_state,
            settings,
            mission_id,
            expected_state,
            new_state,
            event_type,
        )
        if record is None:
            return

        redis_ready = bool(getattr(app.state, "redis_ready", False))
        redis_client = getattr(app.state, "redis", None)
        if redis_ready and redis_client is not None:
            try:
                await emit_state_event_fn(
                    settings=settings,
                    validator=validator,
                    redis_client=redis_client,
                    mission=record,
                    event_type=event_type,
                )
            except Exception as exc:
                LOGGER.warning(
                    "v2: failed to emit %s for mission %s: %s",
                    event_type,
                    mission_id,
                    exc,
                )
