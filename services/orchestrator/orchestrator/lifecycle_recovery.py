"""lifecycle_recovery.py — Bootstrap recovery of in-flight lifecycle tasks on startup.

On each orchestrator start, ``lifecycle_recovery_loop`` re-queues missions in
every active transition state. The intentional CLARIFYING operator hold and
terminal states remain paused. Recovery retries until the database and protocol
validator are ready.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from .models import MissionState
from .runtime import ensure_runtime_ready, start_lifecycle_task

if TYPE_CHECKING:
    from fastapi import FastAPI

LOGGER = logging.getLogger(__name__)


def _recoverable_lifecycle_states() -> tuple[MissionState, ...]:
    from .mission_flow_v2.transitions import V2_TRANSITIONS

    non_resumable_states = {
        MissionState.intake,
        MissionState.clarifying,
        MissionState.complete,
        MissionState.failed,
    }
    return tuple(
        expected_state
        for expected_state, _new_state, _event_type in V2_TRANSITIONS
        if expected_state not in non_resumable_states
    )


async def _recover_inflight_lifecycle_tasks(app: "FastAPI") -> bool:
    from . import storage
    from .main import LIFECYCLE_RECOVERY_MAX_MISSIONS, _initialize_app_state  # lazy

    _initialize_app_state(app)
    settings = app.state.settings
    if not settings.auto_transition_enabled:
        app.state.lifecycle_recovery_bootstrapped = True
        app.state.lifecycle_recovery_recovered_count = 0
        app.state.lifecycle_recovery_scanned_count = 0
        app.state.lifecycle_recovery_last_at = datetime.now(UTC).isoformat()
        app.state.lifecycle_recovery_last_error = None
        return True

    redis_ready, db_ready = await ensure_runtime_ready(app)
    protocol_ready = bool(getattr(app.state, "protocol_ready", False))
    if not db_ready or not protocol_ready:
        if not db_ready:
            app.state.lifecycle_recovery_last_error = "database unavailable"
        elif not protocol_ready:
            app.state.lifecycle_recovery_last_error = "protocol unavailable"
        return False

    _ = redis_ready  # keep visible for diagnostics
    missions = await asyncio.to_thread(
        storage.list_missions_in_states,
        settings,
        _recoverable_lifecycle_states(),
        LIFECYCLE_RECOVERY_MAX_MISSIONS,
    )

    recovered = 0
    for mission in missions:
        task = app.state.lifecycle_tasks.get(mission.mission_id)
        if task is not None and not task.done():
            continue
        start_lifecycle_task(app, mission.mission_id)
        recovered += 1

    app.state.lifecycle_recovery_bootstrapped = True
    app.state.lifecycle_recovery_recovered_count = recovered
    app.state.lifecycle_recovery_scanned_count = len(missions)
    app.state.lifecycle_recovery_last_at = datetime.now(UTC).isoformat()
    app.state.lifecycle_recovery_last_error = None
    return True


async def lifecycle_recovery_loop(app: "FastAPI") -> None:
    from .main import LIFECYCLE_RECOVERY_RETRY_SECONDS  # lazy

    while True:
        try:
            recovered = await _recover_inflight_lifecycle_tasks(app)
            if recovered:
                return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            app.state.lifecycle_recovery_last_error = str(exc)
            LOGGER.exception("lifecycle recovery loop iteration failed")
        await asyncio.sleep(LIFECYCLE_RECOVERY_RETRY_SECONDS)
