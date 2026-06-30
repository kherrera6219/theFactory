"""
lifecycle_interface.py — LifecycleEngine Protocol and concrete adapters.

Defines the single interface all lifecycle engines must satisfy and provides
three implementations gated by feature flags in Settings:

    MissionFlowV2Engine  — 11-phase v2 engine (MISSION_FLOW_V2_ENABLED=true)
    LangGraphEngine      — EXPERIMENTAL LangGraph engine (LANGGRAPH_ENABLED=true)
    LegacyV1Engine       — COMPATIBILITY SHIM: coarse v1.1 three-transition engine

Use ``get_lifecycle_engine(settings)`` to obtain the correct engine at runtime.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from fastapi import FastAPI

from .settings import Settings

if TYPE_CHECKING:
    pass

LOGGER = logging.getLogger(__name__)

LIFECYCLE_ENGINE_MISSION_FLOW_V2 = "mission_flow_v2"
LIFECYCLE_ENGINE_LANGGRAPH = "langgraph"
LIFECYCLE_ENGINE_LEGACY_V1 = "legacy_v1"


@runtime_checkable
class LifecycleEngine(Protocol):
    """Unified interface for mission lifecycle advancement.

    Implementations drive a mission through its state transitions.  Each
    engine is stateless w.r.t. individual missions — all per-mission context
    is fetched from storage inside ``advance()``.
    """

    async def advance(self, app: FastAPI, mission_id: str) -> None:
        """Advance ``mission_id`` through its next lifecycle transition(s)."""
        ...


class MissionFlowV2Engine:
    """11-phase Mission Flow v2 engine.

    Active when ``MISSION_FLOW_V2_ENABLED=true`` (default).  Drives missions
    through the full granular phase table defined in ``mission_flow_v2.py``.
    """

    async def advance(self, app: FastAPI, mission_id: str) -> None:
        # Lazy import to avoid circular dep: lifecycle_interface ← runtime ← lifecycle_interface
        from . import runtime as _rt  # noqa: PLC0415
        from .mission_flow_v2 import advance_mission_lifecycle_v2

        settings = app.state.settings
        validator = app.state.envelope_validator
        await advance_mission_lifecycle_v2(
            app=app,
            mission_id=mission_id,
            settings=settings,
            validator=validator,
            emit_state_event_fn=_rt.emit_state_event,
            prepare_chain_fn=_rt._prepare_mission_chain_for_running,
            completion_check_fn=_rt._completion_artifacts_ready,
        )


class LangGraphEngine:
    """EXPERIMENTAL: LangGraph-backed lifecycle engine.

    Active when ``LANGGRAPH_ENABLED=true`` and ``MISSION_FLOW_V2_ENABLED=false``.
    Delegates to ``maybe_advance_mission_lifecycle``; if LangGraph declines
    (dependency unavailable or feature disabled at call time) execution falls
    through to ``LegacyV1Engine``.
    """

    async def advance(self, app: FastAPI, mission_id: str) -> None:
        from . import runtime as _rt  # noqa: PLC0415
        from .langgraph_lifecycle import maybe_advance_mission_lifecycle

        settings = app.state.settings
        validator = app.state.envelope_validator
        handled = await maybe_advance_mission_lifecycle(
            app=app,
            mission_id=mission_id,
            settings=settings,
            validator=validator,
            emit_state_event_fn=_rt.emit_state_event,
        )
        if not handled:
            LOGGER.debug(
                "LangGraph declined mission %s — falling back to LegacyV1Engine",
                mission_id,
            )
            await LegacyV1Engine().advance(app, mission_id)


class LegacyV1Engine:
    """COMPATIBILITY SHIM: original v1.1 coarse-grained lifecycle engine.

    Drives missions through three broad transitions:
        QUEUED → RUNNING → VERIFIED → COMPLETE

    Active when both ``MISSION_FLOW_V2_ENABLED=false`` and
    ``LANGGRAPH_ENABLED=false``.  Kept for backward-compatibility with
    deployments that have not yet adopted the v2 phase table.  Prefer
    ``MissionFlowV2Engine`` for all new deployments.
    """

    async def advance(self, app: FastAPI, mission_id: str) -> None:
        # Lazy imports — runtime imports this module, so we defer to call-time.
        from . import runtime as _rt  # noqa: PLC0415
        from . import storage
        from .mission_flow import CEO_AGENT_ID, append_chain_event, with_chain_defaults
        from .models import MissionState

        settings = app.state.settings
        validator = app.state.envelope_validator

        transitions = [
            (MissionState.queued, MissionState.running, "MISSION_RUNNING"),
            (MissionState.running, MissionState.verified, "MISSION_VERIFIED"),
            (MissionState.verified, MissionState.complete, "MISSION_COMPLETE"),
        ]

        for expected_state, new_state, event_type in transitions:
            if expected_state == MissionState.queued and new_state == MissionState.running:
                prepared = await _rt._prepare_mission_chain_for_running(
                    app=app,
                    settings=settings,
                    validator=validator,
                    mission_id=mission_id,
                )
                if not prepared:
                    return

            if expected_state == MissionState.verified and new_state == MissionState.complete:
                mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
                if mission is None:
                    return
                artifacts_ready, artifact_details = await _rt._completion_artifacts_ready(
                    settings=settings,
                    mission=mission,
                )
                if not artifacts_ready:
                    metadata = with_chain_defaults(
                        mission.metadata, mission.requested_target_language
                    )
                    append_chain_event(
                        metadata,
                        event_type="MISSION_COMPLETION_BLOCKED",
                        agent_id=CEO_AGENT_ID,
                        details=artifact_details,
                    )
                    updated = await asyncio.to_thread(
                        storage.update_mission_metadata,
                        settings,
                        mission_id,
                        metadata,
                    )
                    if updated is not None:
                        mission = updated
                    await asyncio.to_thread(
                        storage.insert_mission_event,
                        settings,
                        mission_id,
                        MissionState.verified,
                        MissionState.verified,
                        "MISSION_COMPLETION_BLOCKED",
                    )
                    redis_ready = bool(getattr(app.state, "redis_ready", False))
                    redis_client = getattr(app.state, "redis", None)
                    if redis_ready and redis_client is not None:
                        try:
                            await _rt.emit_state_event(
                                settings=settings,
                                validator=validator,
                                redis_client=redis_client,
                                mission=mission,
                                event_type="MISSION_COMPLETION_BLOCKED",
                            )
                        except Exception as exc:
                            LOGGER.warning(
                                "failed to emit completion block event for mission %s: %s",
                                mission_id,
                                exc,
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

            if new_state == MissionState.verified:
                try:
                    record = await _rt._ensure_verified_build_artifact(
                        settings=settings,
                        mission=record,
                    )
                except Exception as exc:
                    LOGGER.warning(
                        "failed to package verified build artifact for mission %s: %s",
                        mission_id,
                        exc,
                    )

            redis_ready = bool(getattr(app.state, "redis_ready", False))
            redis_client = getattr(app.state, "redis", None)
            if redis_ready and redis_client is not None:
                try:
                    await _rt.emit_state_event(
                        settings=settings,
                        validator=validator,
                        redis_client=redis_client,
                        mission=record,
                        event_type=event_type,
                    )
                except Exception as exc:
                    LOGGER.warning(
                        "failed to emit transition event %s for mission %s: %s",
                        event_type,
                        mission_id,
                        exc,
                    )

            if event_type == "MISSION_RUNNING":
                await _rt._emit_running_phase_checkpoints(
                    app=app,
                    settings=settings,
                    validator=validator,
                    mission=record,
                )


def get_lifecycle_engine(settings: Settings) -> LifecycleEngine:
    """Return the appropriate LifecycleEngine for the current feature-flag state.

    Priority:
        1. ``MISSION_FLOW_V2_ENABLED=true``  → MissionFlowV2Engine  (default)
        2. ``LANGGRAPH_ENABLED=true``         → LangGraphEngine      (EXPERIMENTAL)
        3. fallback                            → LegacyV1Engine       (COMPATIBILITY SHIM)
    """
    if settings.mission_flow_v2_enabled:
        return MissionFlowV2Engine()
    if settings.langgraph_enabled:
        return LangGraphEngine()
    return LegacyV1Engine()


def get_lifecycle_engine_name(settings: Settings) -> str:
    """Return the stable public identifier for the active lifecycle engine."""
    if settings.mission_flow_v2_enabled:
        return LIFECYCLE_ENGINE_MISSION_FLOW_V2
    if settings.langgraph_enabled:
        return LIFECYCLE_ENGINE_LANGGRAPH
    return LIFECYCLE_ENGINE_LEGACY_V1
