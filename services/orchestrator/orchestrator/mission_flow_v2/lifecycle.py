from __future__ import annotations

import asyncio
import importlib
import logging
from typing import Any

from ..agent_scaling import all_partitions_complete
from ..llm_delegation import build_deploy_readiness_assessment
from ..llm_delegation import current_mission_id as _llm_current_mission_id
from ..llm_delegation import current_settings as _llm_current_settings
from ..mission_flow import CEO_AGENT_ID, append_chain_event, with_chain_defaults
from ..models import MissionState
from .base import (
    RUNTIME_PHASES,
    _chain_event_exists,
    _setting_bool,
)
from .phases_build import (
    _ensure_verified_build_artifact,
    _persist_runtime_phase_artifact,
    _prepare_pod_assignment,
    _prepare_specialist_assignment,
    _prepare_specialist_plan,
    _produce_pod_group_standard,
)
from .phases_delivery import (
    _prepare_delivery_summary,
    _prepare_equivalence_report,
    _prepare_security_compliance_report,
)
from .phases_intake import (
    _emit_partition_work_items,
    _prepare_ceo_delegation,
    _prepare_fetch_phase,
    _prepare_pm_intake,
)
from .phases_runtime import (
    _prepare_depabs_execution,
    _prepare_dependency_absorption_reports,
    _prepare_fusion,
    _prepare_runtime_qc,
)
from .transitions import (
    V2_TRANSITIONS,
)

LOGGER = logging.getLogger(__name__)


def _pkg() -> Any:
    """Return the public ``mission_flow_v2`` package module (see base._pkg)."""
    return importlib.import_module(__package__)


async def _advance_running_to_gating(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    mission_id: str,
) -> bool:
    mission = await asyncio.to_thread(_pkg().storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False
    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    if metadata.get("scaling_active"):
        if not metadata.get("scaling_partition_events_emitted"):
            mission = await _emit_partition_work_items(
                app=app,
                settings=settings,
                validator=validator,
                mission=mission,
            )
            metadata = with_chain_defaults(
                mission.metadata,
                mission.requested_target_language,
            )
        if not all_partitions_complete(metadata):
            return False
    return True


async def _delta_audit_gate(*, settings: Any, mission: Any) -> tuple[bool, dict[str, Any]]:
    """Require a consumed Delta audit verdict before a mission may COMPLETE.

    Returns ``(True, {})`` unchanged when ``EVENT_DRIVEN_CONTROL_PLANE_ENABLED``
    is off, so the flag-off path is byte-identical.

    With the flag on, three states are distinguished, and only the first passes:
    a consumed passing verdict; a consumed failing verdict; and no verdict at
    all -- which is what a down consumer looks like. Treating "no verdict" as
    permission would recreate exactly the silent completion this gate exists to
    prevent.
    """
    # _setting_bool, not bool(getattr(...)): a non-bool settings value (a mock,
    # a stray string) must fall back to the default rather than read as True.
    # A gate that switches itself on because a value was the wrong type is a
    # gate that blocks missions nobody asked it to block.
    if not _setting_bool(settings, "event_driven_control_plane_enabled", False):
        return True, {}

    metadata = mission.metadata if isinstance(mission.metadata, dict) else {}
    gate = metadata.get("delta_audit_gate")
    if not isinstance(gate, dict):
        return False, {
            "reason": "no Delta audit verdict has been consumed for this mission",
            "gate": "delta_audit",
            "consumer": "protocol-bus-orchestrator",
            "hint": (
                "the Delta consumer may be down; the verdict must be consumed off "
                "the bus, not merely produced"
            ),
        }
    if not gate.get("passed"):
        return False, {
            "reason": "consumed Delta audit verdict did not pass",
            "gate": "delta_audit",
            "audit_result": gate.get("audit_result"),
            "pod": gate.get("pod"),
        }
    return True, {}


async def _advance_verified_to_complete(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission_id: str,
    completion_check_fn: Any,
) -> bool:
    mission = await asyncio.to_thread(_pkg().storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False
    ready, details = await completion_check_fn(settings=settings, mission=mission)
    if ready:
        # EDCP: COMPLETE also requires a Delta audit verdict that was actually
        # CONSUMED off the bus, not merely produced. Folded into the same
        # ready/details pair so it reuses the MISSION_COMPLETION_BLOCKED path
        # below rather than duplicating it. Inert with the flag off.
        ready, details = await _delta_audit_gate(settings=settings, mission=mission)
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
            _pkg().storage.update_mission_metadata,
            settings,
            mission_id,
            metadata,
        )
        await asyncio.to_thread(
            _pkg().storage.insert_mission_event,
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
                await emit_state_event_fn(
                    settings=settings,
                    validator=validator,
                    redis_client=redis_client,
                    mission=mission,
                    event_type="MISSION_COMPLETION_BLOCKED",
                )
            except Exception as exc:
                LOGGER.warning(
                    "v2: failed to emit completion block event for mission %s: %s",
                    mission_id,
                    type(exc).__name__,
                )
        return False

    mission, equivalence_ready, equivalence_report = await _prepare_equivalence_report(
        app=app,
        settings=settings,
        mission=mission,
    )
    if not equivalence_ready:
        await asyncio.to_thread(
            _pkg().storage.insert_mission_event,
            settings,
            mission_id,
            MissionState.verified,
            MissionState.verified,
            "MISSION_EQUIVALENCE_BLOCKED",
        )
        redis_ready = bool(getattr(app.state, "redis_ready", False))
        redis_client = getattr(app.state, "redis", None)
        if redis_ready and redis_client is not None:
            try:
                await emit_state_event_fn(
                    settings=settings,
                    validator=validator,
                    redis_client=redis_client,
                    mission=mission,
                    event_type="MISSION_EQUIVALENCE_BLOCKED",
                )
            except Exception as exc:
                LOGGER.warning(
                    "v2: failed to emit equivalence block event for mission %s: %s",
                    mission_id,
                    type(exc).__name__,
                )
        LOGGER.info(
            "v2: mission %s blocked by equivalence report %s",
            mission_id,
            equivalence_report.get("report_id"),
        )
        return False

    (
        mission,
        security_compliance_ready,
        security_compliance_report,
    ) = await _prepare_security_compliance_report(
        app=app,
        settings=settings,
        mission=mission,
    )
    if not security_compliance_ready:
        await asyncio.to_thread(
            _pkg().storage.insert_mission_event,
            settings,
            mission_id,
            MissionState.verified,
            MissionState.verified,
            "MISSION_SECURITY_COMPLIANCE_BLOCKED",
        )
        redis_ready = bool(getattr(app.state, "redis_ready", False))
        redis_client = getattr(app.state, "redis", None)
        if redis_ready and redis_client is not None:
            try:
                await emit_state_event_fn(
                    settings=settings,
                    validator=validator,
                    redis_client=redis_client,
                    mission=mission,
                    event_type="MISSION_SECURITY_COMPLIANCE_BLOCKED",
                )
            except Exception as exc:
                LOGGER.warning(
                    "v2: failed to emit security/compliance block event for "
                    "mission %s: %s",
                    mission_id,
                    type(exc).__name__,
                )
        LOGGER.info(
            "v2: mission %s blocked by security/compliance report %s",
            mission_id,
            security_compliance_report.get("report_id"),
        )
        return False

    mission, dependency_absorption_ready, dependency_absorption_report = (
        await _prepare_dependency_absorption_reports(
            app=app,
            settings=settings,
            mission=mission,
        )
    )
    if not dependency_absorption_ready:
        await asyncio.to_thread(
            _pkg().storage.insert_mission_event,
            settings,
            mission_id,
            MissionState.verified,
            MissionState.verified,
            "MISSION_DEPENDENCY_ABSORPTION_BLOCKED",
        )
        redis_ready = bool(getattr(app.state, "redis_ready", False))
        redis_client = getattr(app.state, "redis", None)
        if redis_ready and redis_client is not None:
            try:
                await emit_state_event_fn(
                    settings=settings,
                    validator=validator,
                    redis_client=redis_client,
                    mission=mission,
                    event_type="MISSION_DEPENDENCY_ABSORPTION_BLOCKED",
                )
            except Exception as exc:
                LOGGER.warning(
                    "v2: failed to emit dependency absorption block event for "
                    "mission %s: %s",
                    mission_id,
                    type(exc).__name__,
                )
        LOGGER.info(
            "v2: mission %s blocked by dependency absorption report %s",
            mission_id,
            dependency_absorption_report.get("report_id"),
        )
        return False

    mission = await _prepare_depabs_execution(
        app=app,
        settings=settings,
        mission=mission,
    )
    mission, runtime_qc_ready, runtime_qc_report = await _prepare_runtime_qc(
        app=app,
        settings=settings,
        mission=mission,
    )
    if not runtime_qc_ready:
        # The state event alone left no cause an operator could read: it lands in
        # mission_events, not in metadata.chain_trace, so /chain-trace showed a
        # mission parked at VERIFIED with every gate passed and nothing saying
        # why. Every other stop in this lifecycle records a reason; this one must
        # too. Observed on javascript/ocaml/python in the 2026-08-27 language
        # coverage run -- docs/LANGUAGE_COVERAGE_FINDINGS_2026-08-27.md.
        qc_metadata = with_chain_defaults(
            mission.metadata,
            mission.requested_target_language,
        )
        append_chain_event(
            qc_metadata,
            event_type="MISSION_COMPLETION_BLOCKED",
            agent_id=CEO_AGENT_ID,
            details={
                "gate": "runtime_qc",
                "reason": "runtime QC did not pass, so the mission may not complete",
                "verdict": runtime_qc_report.get("verdict"),
                "exit_code": runtime_qc_report.get("exit_code"),
                "filename": runtime_qc_report.get("filename"),
                "execution_type": runtime_qc_report.get("execution_type"),
                "stderr_excerpt": str(runtime_qc_report.get("stderr_preview") or "")[:400],
            },
        )
        await asyncio.to_thread(
            _pkg().storage.update_mission_metadata,
            settings,
            mission_id,
            qc_metadata,
        )
        # Both events on purpose: MISSION_COMPLETION_BLOCKED is what the
        # operations alert counts (routes/operations.py), while
        # MISSION_RUNTIME_QC_BLOCKED keeps the specific cause in state history.
        await asyncio.to_thread(
            _pkg().storage.insert_mission_event,
            settings,
            mission_id,
            MissionState.verified,
            MissionState.verified,
            "MISSION_COMPLETION_BLOCKED",
        )
        await asyncio.to_thread(
            _pkg().storage.insert_mission_event,
            settings,
            mission_id,
            MissionState.verified,
            MissionState.verified,
            "MISSION_RUNTIME_QC_BLOCKED",
        )
        LOGGER.info(
            "v2: mission %s blocked by runtime QC report %s (exit=%s)",
            mission_id,
            runtime_qc_report.get("verdict"),
            runtime_qc_report.get("exit_code"),
        )
        return False

    # S2-06: Deploy readiness assessment
    mission = (
        await asyncio.to_thread(_pkg().storage.fetch_mission, settings, mission_id) or mission
    )
    _deploy_meta = with_chain_defaults(mission.metadata, mission.requested_target_language)
    _build_artifacts_for_deploy = await asyncio.to_thread(
        _pkg().storage.list_build_artifacts, settings, mission_id, 50
    )
    deploy_readiness = build_deploy_readiness_assessment(
        mission_id=mission_id,
        metadata=_deploy_meta,
        build_artifacts=_build_artifacts_for_deploy,
    )
    _deploy_meta["deploy_readiness"] = deploy_readiness
    if not _chain_event_exists(_deploy_meta, "MISSION_DEPLOY_READINESS_ASSESSED"):
        append_chain_event(
            _deploy_meta,
            event_type="MISSION_DEPLOY_READINESS_ASSESSED",
            agent_id="AGENT-11-DEPLOY",
            details={
                "ready": deploy_readiness.get("ready"),
                "blockers": deploy_readiness.get("blockers"),
                "source": deploy_readiness.get("source"),
            },
        )
    await asyncio.to_thread(
        _pkg().storage.update_mission_metadata, settings, mission_id, _deploy_meta
    )
    if not deploy_readiness.get("ready", True):
        LOGGER.info(
            "v2: mission %s deploy readiness check failed - blockers: %s",
            mission_id,
            deploy_readiness.get("blockers"),
        )

    mission = await _prepare_delivery_summary(
        app=app,
        settings=settings,
        mission=mission,
    )
    return True


async def _advance_runtime_phases(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    mission_id: str,
    record: Any,
    new_state: MissionState,
    event_type: str,
) -> Any:
    record = await _persist_runtime_phase_artifact(
        settings=settings,
        mission=record,
        event_type=event_type,
    )
    if new_state == MissionState.verified:
        try:
            record = await _ensure_verified_build_artifact(
                app=app,
                settings=settings,
                mission=record,
            )
        except Exception as exc:
            LOGGER.warning(
                "v2: failed to package verified build artifact for mission %s: %s",
                mission_id,
                type(exc).__name__,
            )
    if new_state == MissionState.running:
        record = await _emit_partition_work_items(
            app=app,
            settings=settings,
            validator=validator,
            mission=record,
        )
    return record


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
        Legacy compatibility hook. The v2 driver now performs its own
        PM, CEO, pod-manager, and specialist stage preparation.
    completion_check_fn : callable
        Async function ``(settings, mission) -> (bool, dict)``
        that checks whether completion artifacts are ready.
    """

    # Bind mission context so _record_usage_event can capture tokens/cost
    # for every LLM call that runs within this lifecycle advance.
    _t1 = _llm_current_mission_id.set(mission_id)
    _t2 = _llm_current_settings.set(settings)

    stage_preparers = {
        MissionState.queued: _prepare_pm_intake,
        MissionState.pm_intake: _prepare_fetch_phase,   # Phase 8: IS Agent
        MissionState.fetch: _prepare_ceo_delegation,    # Phase 8: CEO after FETCH
        MissionState.ceo_delegated: _prepare_pod_assignment,
        MissionState.pod_assigned: _prepare_specialist_assignment,
        MissionState.specialist_assigned: _prepare_specialist_plan,
    }

    _ = prepare_chain_fn

    try:
        mission = await asyncio.to_thread(_pkg().storage.fetch_mission, settings, mission_id)
        if mission is None:
            return
        current_state = mission.state
        # Skip transitions the mission has already passed. Without this, a
        # re-invocation of this driver for a mission already at e.g. running
        # or verified (the lifecycle-recovery loop restarts one of these
        # tasks for every in-flight mission on every orchestrator restart)
        # would unconditionally re-run the queued->pm_intake preparer before
        # the atomic transition_mission_state compare-and-swap catches the
        # state mismatch and exits — silently regenerating and overwriting
        # the mission's LLM-derived feature_contract/mission_charter with a
        # fresh, non-deterministic result on every restart.
        try:
            start_index = next(
                index
                for index, (expected_state, _new_state, _event_type) in enumerate(V2_TRANSITIONS)
                if expected_state == current_state
            )
        except StopIteration:
            return
        pending_transitions = V2_TRANSITIONS[start_index:]

        for expected_state, new_state, event_type in pending_transitions:
            preparer = stage_preparers.get(expected_state)
            if preparer is not None:
                prepared = await preparer(
                    app=app,
                    settings=settings,
                    validator=validator,
                    emit_state_event_fn=emit_state_event_fn,
                    mission_id=mission_id,
                )
                if not prepared:
                    return

            if expected_state == MissionState.running and new_state == MissionState.gating:
                if not await _advance_running_to_gating(
                    app=app,
                    settings=settings,
                    validator=validator,
                    mission_id=mission_id,
                ):
                    return

            # Completion gate before COMPLETE
            if expected_state == MissionState.verified and new_state == MissionState.complete:
                if not await _advance_verified_to_complete(
                    app=app,
                    settings=settings,
                    validator=validator,
                    emit_state_event_fn=emit_state_event_fn,
                    mission_id=mission_id,
                    completion_check_fn=completion_check_fn,
                ):
                    return

            await asyncio.sleep(settings.transition_step_seconds)

            record = await asyncio.to_thread(
                _pkg().storage.transition_mission_state,
                settings,
                mission_id,
                expected_state,
                new_state,
                event_type,
            )
            if record is None:
                return

            if new_state in RUNTIME_PHASES:
                record = await _advance_runtime_phases(
                    app=app,
                    settings=settings,
                    validator=validator,
                    mission_id=mission_id,
                    record=record,
                    new_state=new_state,
                    event_type=event_type,
                )

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
                        type(exc).__name__,
                    )

            if new_state == MissionState.gating:
                record = await _produce_pod_group_standard(
                    app=app,
                    settings=settings,
                    validator=validator,
                    emit_state_event_fn=emit_state_event_fn,
                    mission=record,
                )

            if new_state == MissionState.fusion:
                record = await _prepare_fusion(
                    app=app,
                    settings=settings,
                    validator=validator,
                    emit_state_event_fn=emit_state_event_fn,
                    mission=record,
                )
    finally:
        _llm_current_mission_id.reset(_t1)
        _llm_current_settings.reset(_t2)
