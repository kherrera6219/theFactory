from __future__ import annotations

from ..models import MissionState

V2_TRANSITIONS: tuple[tuple[MissionState, MissionState, str], ...] = (
    (MissionState.queued, MissionState.pm_intake, "MISSION_PM_INTAKE"),
    (MissionState.pm_intake, MissionState.fetch, "MISSION_FETCH"),
    (MissionState.fetch, MissionState.ceo_delegated, "MISSION_CEO_DELEGATED"),
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


V2_PHASE_ORDER: tuple[MissionState, ...] = (
    MissionState.intake,
    MissionState.queued,
    MissionState.pm_intake,
    MissionState.clarifying,
    MissionState.fetch,
    MissionState.ceo_delegated,
    MissionState.pod_assigned,
    MissionState.specialist_assigned,
    MissionState.running,
    MissionState.gating,
    MissionState.fusion,
    MissionState.verified,
    MissionState.complete,
)


V2_EVENT_TO_PHASE: dict[str, MissionState] = {
    "MISSION_INTAKE": MissionState.intake,
    "MISSION_QUEUED": MissionState.queued,
    "MISSION_PM_INTAKE": MissionState.pm_intake,
    "MISSION_CLARIFYING": MissionState.clarifying,
    "MISSION_FETCH": MissionState.fetch,
    "MISSION_FETCH_COMPLETE": MissionState.fetch,
    "MISSION_CEO_DELEGATED": MissionState.ceo_delegated,
    "MISSION_POD_MANAGER_ASSIGNED": MissionState.pod_assigned,
    "MISSION_SPECIALIST_ASSIGNED": MissionState.specialist_assigned,
    "MISSION_RUNNING": MissionState.running,
    "MISSION_GATING": MissionState.gating,
    "MISSION_FUSION": MissionState.fusion,
    "MISSION_VERIFIED": MissionState.verified,
    "MISSION_COMPLETE": MissionState.complete,
}


_V2_TO_V1_MAP: dict[MissionState, MissionState] = {
    MissionState.intake: MissionState.intake,
    MissionState.queued: MissionState.queued,
    MissionState.pm_intake: MissionState.queued,
    MissionState.clarifying: MissionState.queued,
    MissionState.fetch: MissionState.queued,
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

